# server.py
import os
import json
import subprocess
import asyncio
from typing import Dict, Set
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Body
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from src.strict_intake_assistant import (
    StrictIntakeAssistant,
    load_flow_steps_raw,
    insert_step_after_db,
    update_step_db,
    delete_step,
)

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"]
)

# live session cache
assistants: Dict[str, StrictIntakeAssistant] = {}
states: Dict[str, dict] = {}

# ws subscribers
subs: Dict[str, Set[WebSocket]] = {}

# voice agent process tracking
voice_processes: Dict[str, subprocess.Popen] = {}

async def broadcast(session_id: str, event: dict):
    print(f"DEBUG Broadcasting to session {session_id}: {event}")
    print(f"DEBUG Active subscribers for {session_id}: {len(subs.get(session_id, set()))}")
    for ws in list(subs.get(session_id, set())):
        try:
            msg = json.dumps(event)
            await ws.send_text(msg)
            print(f"DEBUG Sent to WebSocket: {msg}")
        except Exception as e:
            print(f"ERROR WebSocket send failed: {e}")
            subs[session_id].discard(ws)

@app.get("/api/flows/{name}/steps")
async def get_steps(name: str):
    # Return ordered rows including order_index so UI can render correctly
    rows = await load_flow_steps_raw(name)
    out = []
    for r in rows:
        out.append({
            "name": r.get("name"),
            "ask_prompt": r.get("ask_prompt"),
            "input_key": r.get("input_key"),
            "next_name": r.get("next_name"),
            "system_prompt": r.get("system_prompt"),
            "validate_regex": r.get("validate_regex"),
            "order_index": r.get("order_index"),
        })
    return out


@app.post("/api/flows/{name}/steps/insert_after")
async def insert_step_after(name: str, payload: dict = Body(...)):
    """Insert a new step after an existing step and return refreshed ordered steps."""
    insert_after = payload.get("insert_after")
    ask_prompt = payload.get("ask_prompt")
    step_name = payload.get("name")
    input_key = payload.get("input_key")
    validate_regex = payload.get("validate_regex")
    system_prompt = payload.get("system_prompt")

    if not insert_after or not ask_prompt:
        return {"ok": False, "error": "insert_after and ask_prompt are required"}

    try:
        rows = await insert_step_after_db(
            flow_name=name,
            insert_after=insert_after,
            ask_prompt=ask_prompt,
            name=step_name,
            input_key=input_key,
            validate_regex=validate_regex,
            system_prompt=system_prompt,
        )
        # Normalize response similar to GET /steps
        out = []
        for r in rows:
            out.append({
                "name": r.get("name"),
                "ask_prompt": r.get("ask_prompt"),
                "input_key": r.get("input_key"),
                "next_name": r.get("next_name"),
                "system_prompt": r.get("system_prompt"),
                "validate_regex": r.get("validate_regex"),
                "order_index": r.get("order_index"),
            })
        return {"ok": True, "steps": out}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.patch("/api/flows/{name}/steps/{step}")
async def patch_step(name: str, step: str, payload: dict = Body(...)):
    """Update fields for a step and return refreshed ordered steps."""
    try:
        rows = await update_step_db(name, step, payload or {})
        out = []
        for r in rows:
            out.append({
                "name": r.get("name"),
                "ask_prompt": r.get("ask_prompt"),
                "input_key": r.get("input_key"),
                "next_name": r.get("next_name"),
                "system_prompt": r.get("system_prompt"),
                "validate_regex": r.get("validate_regex"),
                "order_index": r.get("order_index"),
            })
        return {"ok": True, "steps": out}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.delete("/api/flows/{name}/steps/{step}")
async def delete_step_endpoint(name: str, step: str):
    """Delete a step and return refreshed ordered steps."""
    try:
        success = await delete_step(name, step)
        if success:
            # Return updated steps list
            rows = await load_flow_steps_raw(name)
            out = []
            for r in rows:
                out.append({
                    "name": r.get("name"),
                    "ask_prompt": r.get("ask_prompt"),
                    "input_key": r.get("input_key"),
                    "next_name": r.get("next_name"),
                    "system_prompt": r.get("system_prompt"),
                    "validate_regex": r.get("validate_regex"),
                    "order_index": r.get("order_index"),
                })
            return {"ok": True, "steps": out}
        else:
            return {"ok": False, "error": "Failed to delete step"}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.post("/api/intake/start")
async def start(payload: dict = Body(...)):
    flow = payload.get("flow_name", "injury_intake_strict")
    session_id = payload.get("session_id") or f"ui_{os.urandom(4).hex()}"
    launch_voice = payload.get("launch_voice", False)
    
    # Create text-based assistant for UI interaction
    assistant = await StrictIntakeAssistant.create(flow)
    assistants[session_id] = assistant
    first = await assistant.start(session_id)
    # expose state
    st = (await assistant.app.aget_state({"configurable":{"thread_id":session_id}})).values
    states[session_id] = st
    await broadcast(session_id, {
        "event":"node_entered",
        "node_id": st.get("current_step"),
        "collected_data": st.get("collected_data", {}),
        "completed_steps": st.get("completed_steps", [])
    })
    
    # Launch voice agent if requested
    if launch_voice:
        try:
            # Launch the voice agent process with the same session_id
            env = os.environ.copy()
            env["FORCED_SESSION_ID"] = session_id  # Pass session ID to voice agent
            voice_process = subprocess.Popen([
                "uv", "run", "python", "src/agent.py", "console"
            ], cwd=os.getcwd(), env=env)
            voice_processes[session_id] = voice_process
            await broadcast(session_id, {"event": "voice_agent_started", "process_id": voice_process.pid})
        except Exception as e:
            await broadcast(session_id, {"event": "voice_agent_error", "error": str(e)})
    
    return {"session_id": session_id, "reply": first, "state": st, "voice_launched": launch_voice}

@app.post("/api/intake/message")
async def message(payload: dict = Body(...)):
    session_id = payload["session_id"]
    text = payload["message"]
    assistant = assistants.get(session_id)
    if not assistant:
        assistant = await StrictIntakeAssistant.create(payload.get("flow_name","injury_intake_strict"))
        assistants[session_id] = assistant
        await assistant.start(session_id)
    await broadcast(session_id, {"event":"user_heard","text": text})
    reply = await assistant.handle_user(text, session_id)
    st = (await assistant.app.aget_state({"configurable":{"thread_id":session_id}})).values
    states[session_id] = st
    await broadcast(session_id, {
        "event":"node_entered",
        "node_id": st.get("current_step"),
        "collected_data": st.get("collected_data", {}),
        "completed_steps": st.get("completed_steps", [])
    })
    return {"reply": reply, "state": st}

@app.get("/api/intake/state/{session_id}")
async def get_state(session_id: str):
    return states.get(session_id, {})

@app.post("/events/{session_id}")
async def post_event(session_id: str, payload: dict = Body(...)):
    await broadcast(session_id, payload)
    return {"ok": True}

@app.post("/api/voice/stop/{session_id}")
async def stop_voice_agent(session_id: str):
    if session_id in voice_processes:
        try:
            process = voice_processes[session_id]
            process.terminate()
            await asyncio.sleep(1)  # Give it time to terminate gracefully
            if process.poll() is None:  # Still running
                process.kill()
            del voice_processes[session_id]
            await broadcast(session_id, {"event": "voice_agent_stopped"})
            return {"ok": True, "message": "Voice agent stopped"}
        except Exception as e:
            return {"ok": False, "error": str(e)}
    return {"ok": False, "message": "No voice agent running for this session"}

@app.websocket("/ws")
async def ws(ws: WebSocket):
    await ws.accept()
    print("DEBUG WebSocket connection accepted")
    session_id = None
    try:
        init = await ws.receive_json()
        session_id = init.get("session_id")
        print(f"DEBUG WebSocket subscribed to session: {session_id}")
        subs.setdefault(session_id, set()).add(ws)
        print(f"DEBUG Total subscribers for {session_id}: {len(subs[session_id])}")
        while True:
            await ws.receive_text()  # keepalive if you want
    except WebSocketDisconnect:
        print(f"DEBUG WebSocket disconnected for session: {session_id}")
        pass
    finally:
        if session_id:
            subs.get(session_id, set()).discard(ws)
            print(f"DEBUG Removed WebSocket subscriber for session: {session_id}")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))