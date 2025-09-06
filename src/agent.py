import logging
import os
import re
import json
import asyncio
import uuid
from datetime import datetime
from dotenv import load_dotenv
from livekit.agents import (
    Agent,
    AgentFalseInterruptionEvent,
    AgentSession,
    JobContext,
    JobProcess,
    MetricsCollectedEvent,
    RoomInputOptions,
    WorkerOptions,
    cli,
    metrics,
)
from livekit.plugins import cartesia, deepgram, noise_cancellation
from strict_intake_assistant import StrictIntakeAssistant, emit_event
from livekit.plugins import silero
import httpx

logger = logging.getLogger("agent")

# Load environment variables
load_dotenv(".env.local")
load_dotenv(".env")
print("Loading environment variables")

# Check for required environment variables
required_vars = ["LIVEKIT_URL", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET"]
optional_vars = ["DEEPGRAM_API_KEY", "CARTESIA_API_KEY"]

missing_vars = []
for var in required_vars:
    value = os.getenv(var)
    if not value:
        missing_vars.append(var)
    else:
        print(f"{var}: {value[:8]}{'*' * (len(value) - 8) if len(value) > 8 else value}")

for var in optional_vars:
    value = os.getenv(var)
    if value:
        print(f"{var}: {value[:8]}{'*' * (len(value) - 8) if len(value) > 8 else value}")
    else:
        print(f" {var} not set (optional)")

if missing_vars:
    print(f" Missing required environment variables: {', '.join(missing_vars)}")
    print("Please create a .env file with the following variables:")
    for var in missing_vars:
        print(f"  {var}=your_{var.lower()}_here")
    exit(1)


class StrictIntakeInjuryAgent(Agent):
    """Strict Intake Assistant with Supabase-driven flow"""
    
    def __init__(self, model_name: str = "qwen2.5:3b") -> None:
        super().__init__(
            instructions="You are Michelle, a professional intake specialist for Srushti Jagtap law firm.",
        )
        
        # Initialize placeholders - actual initialization happens in initialize_conversation
        self.assistant = None
        # Use forced session ID if provided, otherwise generate new one
        forced_session = os.getenv("FORCED_SESSION_ID")
        if forced_session:
            self.session_id = forced_session
            print(f"🔗 Using forced session ID: {self.session_id}")
        else:
            self.session_id = f"injury_{uuid.uuid4()}"   # e.g., injury_7a3b...
            print(f"🆔 Generated new session ID: {self.session_id}")
        self.initialized = False

    def new_session(self):
        """Rotate to a fresh session/thread for the next intake."""
        self.session_id = f"injury_{uuid.uuid4()}"
    
    async def initialize_conversation(self) -> str:
        """Initialize the strict intake conversation"""
        if not self.initialized:
            self.initialized = True
            try:
                # Create the assistant first if not already created
                if self.assistant is None:
                    self.assistant = await StrictIntakeAssistant.create(flow_name="injury_intake_strict")
                
                response = await self.assistant.start(self.session_id)
                if not response:
                    return "Thank you for calling Srushti Jagtap. I'm having technical difficulties. Please try again."
                return response
            except Exception as e:
                print(f" Initialization error: {e}")
                return "Thank you for calling Srushti Jagtap. I'm having technical difficulties. Please try again."
        return "Hello! How can I help you today?"
    
    async def handle_user_message(self, user_msg: str) -> str:
        """Handle user messages using strict intake workflow"""
        if not user_msg or not user_msg.strip():
            return "I didn't catch that. Could you please repeat?"
        
        try:
            response = await self.assistant.handle_user(user_msg.strip(), self.session_id)
            if not response:
                return "I apologize, I didn't generate a proper response. Could you please repeat that?"
            
            # Check if this was a farewell that ended the session
            if "Thanks, your intake is saved" in response and "Goodbye!" in response:
                # Emit session ended event for old session
                old = self.session_id
                self.new_session()
                print(f" Session completed. New session ID: {self.session_id}")
                await emit_event(old, {"event": "session_ended"})
                await emit_event(self.session_id, {
                    "event": "session_started",
                    "session_id": self.session_id,
                    "flow_name": "injury_intake_strict"
                })
            
            return response
        except Exception as e:
            print(f" Message handling error: {e}")
            return "I apologize, but I encountered a technical issue. Could you please repeat your response so I can assist you properly?"
    
    def get_initial_greeting(self) -> str:
        """Get the initial greeting message from LangGraph assistant"""
        return "Initializing conversation..."  # This will be replaced by initialize_conversation


def prewarm(proc: JobProcess):
    pass


# -------------------------------------------------------------------
# Minimal, sequential voice loop (lock + queue + pause/resume)
# -------------------------------------------------------------------

# Single shared session with SHORT endpointing (snappy turn-taking)
session = AgentSession(
    stt=deepgram.STT(
        model="nova-3",
        language="multi",
        endpointing_ms=1800,     
        interim_results=True,    
    ),
    tts=cartesia.TTS(voice="6f84f4b8-58a2-430c-8c79-688dad597532"),
    turn_detection="vad",
    vad=silero.VAD.load(),
)

# Lock to serialize TTS and pause/resume mic while the bot is speaking
speaking_lock = asyncio.Lock()

# Global reference for event emission
global_injury_assistant = None

async def speak(text: str):
    if not text or not text.strip():
        return
    async with speaking_lock:
        try:
            # await session.pause_listening()
            # # Pause mic while TTS plays (use whichever is available)
            # if hasattr(session, "pause_listening"):
            #     session.pause_listening()
            # elif hasattr(session, "pause_input_audio"):
            #     session.pause_input_audio()

            print(f"[TTS] → {text[:80]}")
            if global_injury_assistant:
                await emit_event(global_injury_assistant.session_id, {"event":"prompt_spoken","text": text})
            await session.say(text)
            print("[TTS] ✓ done")
        finally:
            # small tail to avoid clipping user
            # await asyncio.sleep(0.3)
            # if hasattr(session, "resume_listening"):
            #     session.resume_listening()
            # elif hasattr(session, "resume_input_audio"):
            #     session.resume_input_audio()
            pass


async def speak_all(text_or_list):
    """Speak every line/sentence in order; keeps mic paused while talking."""
    if not text_or_list:
        return
    items = []
    if isinstance(text_or_list, (list, tuple)):
        items = [str(x).strip() for x in text_or_list if str(x).strip()]
    else:
        s = str(text_or_list).strip()
        # split on newlines or sentence ends; keep it simple & readable
        items = [p.strip() for p in re.split(r"(?:\n+|(?<=[.!?])\s+)", s) if p.strip()]
    for chunk in items:
        await speak(chunk)

# Queue to strictly sequence: FINAL transcript → LLM → speak
message_queue = asyncio.Queue()

async def worker(injury_assistant: StrictIntakeInjuryAgent):
    while True:
        user_text = await message_queue.get()
        try:
            reply = await injury_assistant.handle_user_message(user_text)
            await speak_all(reply)
        except Exception as e:
            print(f" worker error: {e}")
        finally:
            message_queue.task_done()

# Only enqueue FINAL transcripts (ignore partials)
@session.on("user_input_transcribed")
def on_user_input_transcribed(ev):
    if not getattr(ev, "is_final", True):
        print(f"… partial: {getattr(ev, 'transcript', '')}")
        return
    transcript = (getattr(ev, "transcript", "") or "").strip()
    if transcript:
        print(f" final: {transcript}")
        # tell UI what the user said
        if global_injury_assistant:
            asyncio.create_task(emit_event(global_injury_assistant.session_id, {"event":"user_heard","text": transcript}))
        asyncio.create_task(message_queue.put(transcript))

# Optional: handle false interruptions--
@session.on("agent_false_interruption")
def _on_agent_false_interruption(ev: AgentFalseInterruptionEvent):
    logger.info("false positive interruption, resuming")

# Metrics hook (kept as-is, wired in entrypoint)
# -------------------------------------------------------------------


async def entrypoint(ctx: JobContext):
    global global_injury_assistant
    
    # Use a unique identity for the agent
    agent_identity = "srushti-agent-1"
    
    injury_assistant = StrictIntakeInjuryAgent(model_name="qwen2.5:3b")
    global_injury_assistant = injury_assistant  # Set global reference for event emission
    from langchain_ollama import ChatOllama
    session_llm = ChatOllama(model="qwen2.5:3b", temperature=0.3, timeout=60)  
    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)

    async def log_usage():
        summary = usage_collector.get_summary()
        logger.info(f"Usage: {summary}")
    
    ctx.add_shutdown_callback(log_usage)
    
    try:
        # Connect to the room
        await ctx.connect()
        print(f"Connected to room as {agent_identity}")
        print("Agent joined room:", ctx.room.name)

        # Start the voice session
        await session.start(
            agent=injury_assistant,
            room=ctx.room,
            room_input_options=RoomInputOptions(
                noise_cancellation=noise_cancellation.BVC(),
                participant_identity=agent_identity,
            ),
        )

        # Start the worker that consumes user finals in order
        asyncio.create_task(worker(injury_assistant))

        # Initialize conversation and speak first prompt BEFORE listening for user
        initial_greeting = await injury_assistant.initialize_conversation()
        print(f"\n🤖 Srushti (Strict Intake + Supabase): {initial_greeting}")
        
        # Emit session started event
        await emit_event(injury_assistant.session_id, {
            "event": "session_started",
            "session_id": injury_assistant.session_id,
            "flow_name": "injury_intake_strict"
        })
        
        # Also emit current node if available
        if injury_assistant.assistant:
            state = await injury_assistant.assistant.app.aget_state(
                {"configurable": {"thread_id": injury_assistant.session_id}}
            )
            cur = (state.values or {}).get("current_step")
            if cur is not None:
                await emit_event(injury_assistant.session_id, {"event": "node_entered", "node_id": cur})
        
        await speak_all(initial_greeting)
        print("Strict Intake + Supabase injury assistant with database-driven flow ready!")
        
        # Keep the connection alive
        while True:
            await asyncio.sleep(1)
            
    except Exception as e:
        print(f"Error in session: {e}")
        raise


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))