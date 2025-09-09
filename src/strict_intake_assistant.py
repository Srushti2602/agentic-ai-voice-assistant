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
import httpx

load_dotenv(".env.local")
from empathetic_rewriter import EmpatheticRewriter
rewriter = EmpatheticRewriter()

# Event emitter configuration
FLOW_EVENTS_URL = os.getenv("FLOW_EVENTS_URL", "http://localhost:8000/events")

async def emit_event(session_id: str, event: dict):
    try:
        async with httpx.AsyncClient(timeout=2.0) as c:
            await c.post(f"{FLOW_EVENTS_URL}/{session_id}", json=event)
    except Exception:
        pass  

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


def last_ai_block(msgs) -> str:
    out = []
    for m in reversed(msgs):
        # If Pydantic AIMessage
        if isinstance(m, AIMessage):
            out.append(m.content if isinstance(m.content, str) else "")
            continue
        # If dict message
        elif isinstance(m, dict) and (m.get("role") or m.get("type")) in ("assistant", "ai"):
            c = m.get("content")
            out.append(c if isinstance(c, str) else "")
            continue
        # Stop when you see a human message
        if isinstance(m, HumanMessage) or (
            isinstance(m, dict) and (m.get("role") or m.get("type")) == "user"
        ):
            break
    # Use only most recent (if single output required)
    return out[0] if out else ""


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

    async def update(
        self,
        ask_prompt: str,
        input_key: str,
        next_name: Optional[str],
        system_prompt: Optional[str] = None,
        validate_regex: Optional[str] = None,
    ):
        dbg(f"[DB] Updated step {self.name}: ask_prompt='{ask_prompt}', input_key='{input_key}'")
        self.ask_prompt = ask_prompt
        self.input_key = input_key
        self.next_name = next_name
        self.system_prompt = system_prompt
        self.validate_regex = validate_regex
        return True


async def delete_step(flow_name: str, step_name: str) -> bool:
    """Delete a step from the database and fix next_name references."""
    client = await supa()
    
    # Get flow_id
    try:
        flow_resp = await (
            client.table("flows")
            .select("id")
            .eq("name", flow_name)
            .single()
            .execute()
        )
        flow_id = flow_resp.data["id"]
    except Exception as e:
        dbg(f"[DB] Flow not found: {flow_name}")
        return False
    
    # Get the step to delete
    try:
        step_resp = await (
            client.table("intake_steps")
            .select("*")
            .eq("flow_id", flow_id)
            .eq("name", step_name)
            .single()
            .execute()
        )
        step_to_delete = step_resp.data
    except Exception as e:
        dbg(f"[DB] Step not found: {step_name}")
        return False
    
    # Find steps that point to this step and update their next_name
    try:
        # Find steps that have next_name pointing to the step we're deleting
        pointing_steps_resp = await (
            client.table("intake_steps")
            .select("*")
            .eq("flow_id", flow_id)
            .eq("next_name", step_name)
            .execute()
        )
        
        # Update their next_name to point to what the deleted step was pointing to
        for pointing_step in pointing_steps_resp.data or []:
            new_next_name = step_to_delete.get("next_name", None)
            await (
                client.table("intake_steps")
                .update({"next_name": new_next_name})
                .eq("id", pointing_step["id"])
                .execute()
            )
            dbg(f"[DB] Updated step {pointing_step['name']} next_name: {new_next_name}")
    except Exception as e:
        dbg(f"[DB] Error updating next_name references: {e}")
        return False
    
    # Delete the step
    try:
        await (
            client.table("intake_steps")
            .delete()
            .eq("flow_id", flow_id)
            .eq("name", step_name)
            .execute()
        )
        dbg(f"[DB] Deleted step: {step_name}")
        
        # Reorder remaining steps to fill gaps
        await reorder_steps_after_delete(flow_id, step_to_delete["order_index"])
        return True
    except Exception as e:
        dbg(f"[DB] Error deleting step {step_name}: {e}")
        return False


async def reorder_steps_after_delete(flow_id: str, deleted_order_index: int):
    """Reorder steps after deletion to fill gaps in order_index."""
    client = await supa()
    
    try:
        # Get all steps with order_index greater than the deleted one
        steps_resp = await (
            client.table("intake_steps")
            .select("id, order_index")
            .eq("flow_id", flow_id)
            .gt("order_index", deleted_order_index)
            .order("order_index", desc=False)
            .execute()
        )
        
        # Decrement their order_index by 1
        for step in steps_resp.data or []:
            new_order = step["order_index"] - 1
            await (
                client.table("intake_steps")
                .update({"order_index": new_order})
                .eq("id", step["id"])
                .execute()
            )
        
        dbg(f"[DB] Reordered {len(steps_resp.data or [])} steps after deletion")
    except Exception as e:
        dbg(f"[DB] Error reordering steps: {e}")


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


# ---------- Flow editing helpers (DB) ----------
async def fetch_flow_id(flow_name: str) -> str:
    """Return flow_id for a given flow name or raise ValueError if not found."""
    client = await supa()
    try:
        flow_resp = await (
            client.table("flows").select("id").eq("name", flow_name).single().execute()
        )
    except Exception as e:
        raise ValueError(f"Flow not found: {flow_name}") from e
    return flow_resp.data["id"]


async def load_flow_steps_raw(flow_name: str) -> List[Dict[str, Any]]:
    """Return raw intake_steps rows for a flow, ordered by order_index."""
    client = await supa()
    flow_id = await fetch_flow_id(flow_name)
    rows_resp = await (
        client.table("intake_steps")
        .select("*")
        .eq("flow_id", flow_id)
        .order("order_index", desc=False)
        .execute()
    )
    return rows_resp.data or []


def _slugify(text: str) -> str:
    s = (text or "").strip().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = s.strip("_")
    return s or "step"


async def _ensure_unique_step_name(client: AsyncClient, flow_id: str, base: str) -> str:
    """Ensure step name unique for a flow by appending _2, _3, ... if needed."""
    name = base
    idx = 2
    while True:
        try:
            res = await (
                client.table("intake_steps")
                .select("id")
                .eq("flow_id", flow_id)
                .eq("name", name)
                .limit(1)
                .execute()
            )
            if not (res.data or []):
                return name
        except Exception:
            # If select fails for any reason, return base to avoid infinite loop
            return name
        name = f"{base}_{idx}"
        idx += 1


async def insert_step_after_db(
    flow_name: str,
    insert_after: str,
    ask_prompt: str,
    name: Optional[str] = None,
    input_key: Optional[str] = None,
    validate_regex: Optional[str] = None,
    system_prompt: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Insert a new step after an existing step, shifting order_index and fixing next_name.

    Returns the refreshed ordered steps rows for the flow.
    """
    client = await supa()
    flow_id = await fetch_flow_id(flow_name)

    # Fetch predecessor step
    try:
        pred_resp = await (
            client.table("intake_steps")
            .select("*")
            .eq("flow_id", flow_id)
            .eq("name", insert_after)
            .single()
            .execute()
        )
    except Exception as e:
        raise ValueError(f"insert_after step not found: {insert_after}") from e

    pred = pred_resp.data
    old_next = (pred.get("next_name") or "").strip() or None
    pred_order = int(pred.get("order_index") or 0)

    # Generate defaults and ensure uniqueness
    candidate = _slugify(name or ask_prompt or "new_question")
    unique_name = await _ensure_unique_step_name(client, flow_id, candidate)
    final_input_key = _slugify(input_key or unique_name)

    # Shift subsequent steps' order_index by +1
    try:
        subs_resp = await (
            client.table("intake_steps")
            .select("id, order_index")
            .eq("flow_id", flow_id)
            .gt("order_index", pred_order)
            .order("order_index", desc=False)
            .execute()
        )
        for row in subs_resp.data or []:
            try:
                await (
                    client.table("intake_steps")
                    .update({"order_index": int(row["order_index"]) + 1})
                    .eq("id", row["id"])  # primary key update by id
                    .execute()
                )
            except Exception as e:
                dbg(f"[DB][WARN] order_index shift failed for id={row.get('id')}: {e!r}")
    except Exception as e:
        dbg(f"[DB][WARN] Could not shift subsequent order_index: {e!r}")

    # Insert new step with next_name=old_next and order_index right after predecessor
    new_row = {
        "flow_id": flow_id,
        "name": unique_name,
        "order_index": pred_order + 1,
        "system_prompt": system_prompt,
        "ask_prompt": ask_prompt,
        "input_key": final_input_key,
        "validate_regex": validate_regex,
        "next_name": old_next,
    }
    try:
        await client.table("intake_steps").insert(new_row).execute()
    except Exception as e:
        raise ValueError(f"Failed to insert new step: {e!r}")

    # Update predecessor to point to new step
    try:
        await (
            client.table("intake_steps")
            .update({"next_name": unique_name})
            .eq("flow_id", flow_id)
            .eq("name", insert_after)
            .execute()
        )
    except Exception as e:
        dbg(f"[DB][WARN] failed to update predecessor.next_name: {e!r}")

    # Return refreshed steps
    return await load_flow_steps_raw(flow_name)


async def update_step_db(
    flow_name: str,
    step_name: str,
    patch: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Update allowed fields on a step and return refreshed ordered steps.

    For simplicity we do not handle reordering here (order_index moves). Use insert-after
    for adding steps in the correct place.
    """
    client = await supa()
    flow_id = await fetch_flow_id(flow_name)

    allowed = {"ask_prompt", "input_key", "validate_regex", "system_prompt", "next_name"}
    data = {k: v for k, v in (patch or {}).items() if k in allowed}
    if not data:
        return await load_flow_steps_raw(flow_name)

    try:
        await (
            client.table("intake_steps")
            .update(data)
            .eq("flow_id", flow_id)
            .eq("name", step_name)
            .execute()
        )
    except Exception as e:
        raise ValueError(f"Failed to update step '{step_name}': {e!r}")

    return await load_flow_steps_raw(flow_name)


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
        
        # 3) empathetic rewrite of the question
        text = await rewriter.rewrite(base_question)

        # 4) Context-aware empathy & advice additions for some key steps
        if show_greeting:
            greet = await rewriter.greeting(agent="Michelle Ross", firm="Pearson Specter Personal Injury")
            text = f"{greet} {text}"

        messages.append(AIMessage(content=text))
        
        # Emit event when entering a node
        session_id = state.get("session_id", "default")
        await emit_event(session_id, {
            "event": "node_entered", 
            "node_id": step.name,
            "collected_data": collected_data,
            "completed_steps": completed_steps
        })
        
        return {
            **state,
            "messages": messages,
            "collected_data": collected_data,
            "completed_steps": completed_steps,
            "current_step": current_step,
            "human_cursor": state.get("human_cursor", 0),
            "session_id": session_id,
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

        # ✨ NEW: Extract and validate the user input using EmpatheticRewriter
        question = render(step.ask_prompt, collected_data)  # Get the original question
        is_valid, extracted_value, error_message = await rewriter.extract_and_validate(question, user_text)
        
        if not is_valid and error_message:
            # If extraction failed, ask for clarification
            dbg(f"[STORE] step='{step.name}' validation failed: {error_message}")
            messages.append(AIMessage(content=error_message))
            return {
                **state,
                "messages": messages,
                "collected_data": collected_data,
                "completed_steps": completed_steps,
                "current_step": step.name,  # Stay on the same step
                "human_cursor": human_cursor + 1,  # Move cursor to wait for new input
                "session_id": session_id,
            }

        # Use extracted value instead of raw user text
        final_value = extracted_value if extracted_value else user_text
        LOW_INJURY_RESPONSES = ["none", "no", "no injuries", "not injured", "nil", "negative", "n/a","no.", "none.", "not applicable"]
        quick = None
        lv = (final_value or "").lower()

        if step.name == "injuries":
            if lv in LOW_INJURY_RESPONSES or lv.startswith("no"):
                quick = "That's a relief to hear. Let's continue with the next steps."
            elif any(w in lv for w in ["severe", "serious", "bleeding", "broken", "fracture", "head", "brain", "unconscious"]):
                quick = "That sounds very serious. Please get medical help."

        elif step.name == "medical_treatment":
            # If user said no treatment, acknowledge and move on
            if lv in ("no", "none", ""):
                # Optional: also check collected injuries if you like
                quick = "Thanks for letting me know. Let's continue."

        elif step.name == "witnesses":
            if lv and lv not in ("no", "none"):
                quick = "Could you share the names of the witnesses if you know them?"

        if quick:
            messages.append(AIMessage(content=quick))

        dbg(f"[STORE] step='{step.name}' extracted_value={final_value!r} (from raw: {user_text!r})")

        # Emit event when user input is heard
        await emit_event(session_id, {
            "event": "user_heard", 
            "node_id": step.name, 
            "text": user_text,
            "extracted_value": final_value,  # Include extracted value in event
            "collected_data": collected_data,
            "completed_steps": completed_steps
        })

        # Store the EXTRACTED value, not the raw user text
        collected_data[step.input_key] = final_value  # ← This is the key fix!

        if step.name not in completed_steps:
            completed_steps.append(step.name)

        try:
            run_id = await get_or_create_run_id(flow_id, session_id)
            if run_id:
                # Save the extracted value to database
                await save_answer(run_id, step.name, step.input_key, final_value)
            else:
                dbg("[STORE][WARN] No run_id. Skipping save.")
        except Exception as e:
            dbg(f"[STORE][ERR] {e}")

        next_step = step.next_name
        dbg(f"[STORE] step='{step.name}' moving_to='{next_step or 'END'}'")

        # If this is the final step, emit completion event
        final_current_step = next_step if next_step else ""
        if not final_current_step:  # Flow is complete
            await emit_event(session_id, {
                "event": "node_entered",
                "node_id": "completed",
                "collected_data": collected_data,
                "completed_steps": completed_steps
            })

        return {
            **state,
            "messages": messages,
            "collected_data": collected_data,
            "completed_steps": completed_steps,
            "current_step": final_current_step,
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
        if s.next_name and s.next_name.strip() and s.next_name in steps:
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

        return last_ai_block(result.get("messages", [])) or "(no AI)"

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

        return last_ai_block(result.get("messages", [])) or "(no AI)"