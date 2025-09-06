from typing import Dict, List, TypedDict, Annotated, Optional, Tuple, Any
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
from supabase import AsyncClient, create_async_client
import os
import uuid
import re
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv(".env.local")
from empathetic_rewriter import EmpatheticRewriter
rewriter = EmpatheticRewriter()  

# ---------- Debug helper ----------
DEBUG = os.getenv("INTAKE_DEBUG", "1") not in ("", "0", "false", "False")


def dbg(*args: Any):
    if DEBUG:
        print(*args)


# ---------- Farewell detection ----------
FAREWELL_RE = re.compile(r"\b(bye|goodbye|thanks(?: you)?|thank you|end|stop|finish|done|quit|exit)\b", re.I)

def is_farewell(txt: str) -> bool:
    return bool(txt and FAREWELL_RE.search(txt))


# ---------- State ----------
class IntakeState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    collected_data: Dict[str, str]
    current_step: str
    completed_steps: List[str]
    human_cursor: int
    session_id: str


# ---------- Helpers ----------
def render(template: str, data: Dict[str, str]) -> str:
    out = template
    for k, v in (data or {}).items():
        out = out.replace(f"{{{k}}}", v)
    return out


def last_ai_text(msgs) -> str:
    for m in reversed(msgs):
        if isinstance(m, AIMessage):
            return m.content
        if isinstance(m, dict) and (m.get("role") or m.get("type")) in ("assistant", "ai"):
            c = m.get("content")
            return c if isinstance(c, str) else ""
    return ""


# ---------- Steps ----------
class Step:
    def __init__(
        self,
        name: str,
        ask_prompt: str,
        input_key: str,
        next_name: Optional[str],
        system_prompt: Optional[str] = None,
        validate_regex: Optional[str] = None,
    ):
        self.name = name
        self.ask_prompt = ask_prompt
        self.input_key = input_key
        self.next_name = next_name
        self.system_prompt = system_prompt
        self.validate_regex = validate_regex


# ---------- Supabase async client singleton ----------
_client: Optional[AsyncClient] = None


async def supa() -> AsyncClient:
    global _client
    if _client is None:
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_ANON_KEY")
        if not url or not key:
            raise ValueError("Missing SUPABASE_URL or SUPABASE_ANON_KEY")
        _client = await create_async_client(url, key)
        dbg("[DB] Async Supabase client created")
    return _client


# ---------- DB helpers ----------
async def _select_one_id(client: AsyncClient, table: str, filters: Dict[str, str]) -> Optional[str]:
    try:
        q = client.table(table).select("id")
        for k, v in filters.items():
            q = q.eq(k, v)
        res = await q.limit(1).execute()
        rows = res.data or []
        if rows:
            rid = rows[0].get("id")
            dbg(f"[DB] _select_one_id {table} filters={filters} -> {rid}")
            return rid
        dbg(f"[DB] _select_one_id {table} filters={filters} -> not found")
        return None
    except Exception as e:
        dbg(f"[DB][ERR] _select_one_id({table}) failed: {e!r}")
        return None


async def get_or_create_run_id(flow_id: str, session_id: str) -> Optional[str]:
    client = await supa()
    filters = {"flow_id": flow_id, "session_id": session_id}
    dbg(f"[DB] get_or_create_run_id {filters}")

    # 1) Try to find existing
    rid = await _select_one_id(client, "intake_runs", filters)
    if rid:
        return rid

    # 2) Create or get using upsert on unique key (flow_id, session_id)
    #    No .select() chain after insert/upsert in v2.
    try:
        ins = await client.table("intake_runs").upsert(
            {"flow_id": flow_id, "session_id": session_id},
            on_conflict="flow_id,session_id",
        ).execute()
        rows = ins.data or []
        if rows and isinstance(rows, list):
            rid = rows[0].get("id")
            if rid:
                dbg(f"[DB] upsert returned id={rid}")
                return rid
        dbg("[DB] upsert returned no rows. Will re-select.")
    except Exception as e:
        dbg(f"[DB][ERR] upsert intake_runs failed: {e!r}")

    # 3) Re-select to be safe
    rid = await _select_one_id(client, "intake_runs", filters)
    if not rid:
        dbg("[DB][WARN] Could not create or read run_id. Check RLS policies.")
    return rid


async def save_answer(run_id: Optional[str], step_name: str, input_key: str, value: str):
    if not run_id:
        dbg(f"[DB][WARN] Invalid run_id: {run_id}. Skipping save_answer.")
        return
    client = await supa()
    try:
        dbg(f"[DB] insert intake_answers run_id={run_id} step={step_name} key={input_key} value={value!r}")
        res = await client.table("intake_answers").insert(
            {
                "run_id": run_id,
                "step_name": step_name,
                "input_key": input_key,
                "value": value,
            }
        ).execute()
        dbg(f"[DB] intake_answers insert ok. rows={len(res.data or [])}")
    except Exception as e:
        dbg(f"[DB][ERR] Save answer error: {e!r}")


async def mark_run_completed(run_id: str):
    try:
        client = await supa()
        await (
            client.table("intake_runs")
            .update({"completed_at": datetime.now(timezone.utc).isoformat()})
            .eq("id", run_id)
            .execute()
        )
        dbg(f"[DB] marked run completed {run_id}")
    except Exception as e:
        dbg(f"[DB][WARN] mark_run_completed skipped: {e!r}")


async def save_session_end(flow_id: str, session_id: str, reason_text: str):
    run_id = await get_or_create_run_id(flow_id, session_id)
    if run_id:
        await save_answer(run_id, "session_end", "end_reason", reason_text or "user_ended")
        await mark_run_completed(run_id)


# ---------- Load flow and steps async ----------
async def load_flow_and_steps(flow_name: str) -> Tuple[Dict[str, Step], str, str]:
    client = await supa()
    dbg(f"[DB] Loading flow '{flow_name}'")

    # flow row
    try:
        flow_resp = await (
            client.table("flows")
            .select("id")
            .eq("name", flow_name)
            .single()
            .execute()
        )
    except Exception as e:
        raise ValueError(f"Flow not found: {flow_name}") from e

    flow_id = flow_resp.data["id"]
    dbg(f"[DB] flow_id={flow_id}")

    # steps in order
    try:
        rows_resp = await (
            client.table("intake_steps")
            .select("*")
            .eq("flow_id", flow_id)
            .order("order_index", desc=False)  # v2 signature
            .execute()
        )
    except Exception as e:
        raise ValueError(f"No steps in DB for flow: {flow_name}") from e

    rows = rows_resp.data or []
    if not rows:
        raise ValueError(f"No steps in DB for flow: {flow_name}")

    steps: Dict[str, Step] = {}
    for r in rows:
        steps[r["name"].strip()] = Step(
            name=r["name"].strip(),
            ask_prompt=r["ask_prompt"],
            input_key=r["input_key"],
            next_name=(r.get("next_name") or "").strip() or None,
            system_prompt=r.get("system_prompt"),
            validate_regex=r.get("validate_regex"),
        )

    entry_name = rows[0]["name"].strip()
    dbg(f"[DB] Loaded {len(steps)} steps. Entry step='{entry_name}'. Order: {[r['name'] for r in rows]}")
    return steps, flow_id, entry_name


# ---------- Nodes ----------
def make_ask_node(step: Step):
    async def node(state: IntakeState) -> IntakeState:
        current_step = state.get("current_step", "")
        if not current_step or current_step.upper() == "END":
            return state
        if current_step != step.name:
            return state
        messages = list(state.get("messages", []))
        collected_data = dict(state.get("collected_data", {}))
        completed_steps = list(state.get("completed_steps", []))

        # 1) render original template
        base_question = render(step.ask_prompt, collected_data)
        # 2) special greeting hook if this is your first step
        is_first = step.name == state.get("current_step")
        show_greeting = not completed_steps  # first turn only
        if show_greeting:
            greet = await rewriter.greeting(agent="Michelle Ross", firm="Pearson Specter Personal Injury")
            messages.append(AIMessage(content=greet))

        # 3) empathetic rewrite of the question
        text = await rewriter.rewrite(base_question)

        # 4) Context-aware empathy & advice additions for some key steps
        if step.name == "medical_treatment":
            injuries = collected_data.get("injuries", "").lower()
            medical_treatment = collected_data.get("medical_treatment", "").lower()
            if injuries in ("none", "no", "no injuries", "not injured") and step.input_key == "medical_treatment":
                # Skip medical treatment question / move directly with a comforting message
                text = "I’m glad to hear you weren’t injured. Let’s continue."
            elif medical_treatment in ("no", "none", ""):
                # Append gentle advice about calling for help
                text += " If you feel unwell or have concerns, please call 911 or seek immediate medical help."

        if step.name == "injuries":
            injuries = collected_data.get("injuries", "").lower()
            if injuries in ("none", "no", "no injuries", "not injured"):
                # Soften injury question or move on compassionately
                text = "Thank you for letting me know. Let's continue with the next steps."

        messages.append(AIMessage(content=text))
        return {
            **state,
            "messages": messages,
            "collected_data": collected_data,
            "completed_steps": completed_steps,
            "current_step": current_step,
            "human_cursor": state.get("human_cursor", 0),
            "session_id": state.get("session_id", "default"),
        }
    return node




def make_store_node(step: Step, flow_id: str):
    async def node(state: IntakeState) -> IntakeState:
        if state.get("current_step") != step.name:
            return state

        messages = list(state.get("messages", []))
        collected_data = dict(state.get("collected_data", {}))
        completed_steps = list(state.get("completed_steps", []))
        human_cursor = state.get("human_cursor", 0)
        session_id = state.get("session_id", "default")

        humans = [m for m in messages if isinstance(m, HumanMessage)]
        dbg(
            f"[STORE] step='{step.name}' human_cursor={human_cursor} humans_seen={len(humans)} "
            f"completed={completed_steps} collected={collected_data}"
        )

        if human_cursor >= len(humans):
            # No new user input yet. Pause the graph.
            from langgraph.types import interrupt
            dbg(f"[STORE] step='{step.name}' interrupt waiting for human input")
            return interrupt(state)

        user_text = (humans[human_cursor].content or "").strip()
        dbg(f"[STORE] step='{step.name}' captured_user_text={user_text!r}")

        collected_data[step.input_key] = user_text

        if step.name not in completed_steps:
            completed_steps.append(step.name)

        try:
            run_id = await get_or_create_run_id(flow_id, session_id)
            if run_id:
                await save_answer(run_id, step.name, step.input_key, user_text)
            else:
                dbg("[STORE][WARN] No run_id. Skipping save.")
        except Exception as e:
            dbg(f"[STORE][ERR] {e}")

        next_step = step.next_name
        dbg(f"[STORE] step='{step.name}' moving_to='{next_step or 'END'}'")

        return {
            **state,
            "messages": messages,
            "collected_data": collected_data,
            "completed_steps": completed_steps,
            "current_step": next_step if next_step else "",
            "human_cursor": human_cursor + 1,
            "session_id": session_id,
        }

    return node


# ---------- Build graph ----------
async def build_graph_from_db(flow_name: str):
    steps, flow_id, entry = await load_flow_and_steps(flow_name)
    g = StateGraph(IntakeState)

    for s in steps.values():
        g.add_node(f"ask_{s.name}", make_ask_node(s))
        g.add_node(f"store_{s.name}", make_store_node(s, flow_id=flow_id))

    g.set_entry_point(f"ask_{entry}")

    for s in steps.values():
        g.add_edge(f"ask_{s.name}", f"store_{s.name}")
        if s.next_name:
            g.add_edge(f"store_{s.name}", f"ask_{s.next_name}")
        else:
            g.add_edge(f"store_{s.name}", END)

    app = g.compile(checkpointer=MemorySaver())
    dbg(f"[GRAPH] Compiled. Entry='ask_{entry}'. Nodes={len(steps)*2} with MemorySaver")
    return app, flow_id, entry


# ---------- Public wrapper ----------
class StrictIntakeAssistant:
    def __init__(self, app, flow_id, entry):
        self.app = app
        self.flow_id = flow_id
        self.entry = entry
        self.debug = True

    @classmethod
    async def create(cls, flow_name: str = "injury_intake_strict"):
        app, flow_id, entry = await build_graph_from_db(flow_name)
        return cls(app, flow_id, entry)

    def _log_state(self, prefix: str, state: dict):
        if self.debug:
            print(f"\n=== {prefix} ===")
            print(f"Collected Data: {state.get('collected_data', {})}")
            print(f"Current Step: {state.get('current_step', '')}")
            print(f"Completed Steps: {state.get('completed_steps', [])}")
            msgs = state.get("messages", [])
            print(f"Message Count: {len(msgs)}")
            # Show last 3 messages for clarity
            for i, m in enumerate(msgs[-3:], start=max(0, len(msgs)-3)):
                role = "AI" if isinstance(m, AIMessage) else "HUMAN" if isinstance(m, HumanMessage) else type(m).__name__
                preview = (m.content[:120] + "...") if isinstance(m.content, str) and len(m.content) > 120 else m.content
                print(f"  [{i}] {role}: {preview!r}")
            print("=" * (len(prefix) + 8))

    async def start(self, session_id: str) -> str:
        cfg = {"configurable": {"thread_id": session_id}}

        initial_state: IntakeState = {
            "messages": [],
            "collected_data": {},
            "current_step": self.entry,
            "completed_steps": [],
            "human_cursor": 0,
            "session_id": session_id,
        }

        self._log_state("STARTING STATE", initial_state)
        result = await self.app.ainvoke(initial_state, cfg)
        self._log_state("STATE AFTER START", result)

        return last_ai_text(result.get("messages", [])) or "(no AI)"

    async def handle_user(self, user_text: str, session_id: str) -> str:
        cfg = {"configurable": {"thread_id": session_id}}

        current_state = await self.app.aget_state(cfg)
        current_values = current_state.values if current_state else {}
        dbg(f"[HANDLE] session={session_id} input={user_text!r}")

        current_step = current_values.get("current_step", "")

        # A) If the flow has FINISHED already...
        if not current_step or current_step.upper() == "END":
            # Only now do we honor farewell and close this run
            if is_farewell(user_text):
                try:
                    await save_session_end(self.flow_id, session_id, user_text.strip())
                finally:
                    # rotate to a fresh session id for the *next* intake
                    # (this keeps the next conversation in a new run_id)
                    # Note: This would need to be handled by the calling agent
                    pass
                return "Thanks, your intake is saved. We'll follow up shortly. Goodbye!"

            # If they speak after END but not saying bye, remind and keep waiting for bye
            return "Your intake is complete. Say 'bye' when you're ready to end, or tell me if you want to add anything."

        # B) Normal in-flow handling (NO ending on 'bye' mid-step)
        messages = list(current_values.get("messages", []))
        messages.append(HumanMessage(content=user_text.strip()))
        new_state = {**current_values, "messages": messages, "session_id": session_id}

        self._log_state("STATE BEFORE ainvoke", new_state)
        result = await self.app.ainvoke(new_state, cfg)
        self._log_state("STATE AFTER ainvoke", result)

        return last_ai_text(result.get("messages", [])) or "(no AI)"