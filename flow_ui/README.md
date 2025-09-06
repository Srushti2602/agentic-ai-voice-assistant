# Intake Flow Visualizer

A React Flow-based visualization tool for your LangGraph + Supabase injury intake process.

## 🎯 What This Shows

This React application provides a **real-time visual representation** of your existing intake flow:

- **Visual Flow Diagram**: See each step of your LangGraph intake process
- **Real-time Progress**: Track which step the user is currently on
- **Data Collection**: View collected answers as they come in
- **Session Management**: Monitor active intake sessions

## 🏗️ Architecture Overview

```
┌─────────────────────┐    ┌──────────────────────┐    ┌─────────────────────┐
│   React Flow UI     │    │   Python Backend     │    │     Supabase        │
│                     │    │                      │    │                     │
│ • Visual flow       │◄──►│ • StrictIntakeAsst   │◄──►│ • flows table       │
│ • Real-time updates │    │ • LangGraph          │    │ • intake_steps      │
│ • Session panel     │    │ • LiveKit voice      │    │ • intake_runs       │
│ • Progress tracking │    │ • WebSocket events   │    │ • intake_answers    │
└─────────────────────┘    └──────────────────────┘    └─────────────────────┘
```

## 🔄 How Your Existing Flow Works

Your current system uses:

1. **Database-Driven Steps**: Flow steps are stored in Supabase (`flows` + `intake_steps` tables)
2. **LangGraph Structure**: Each step creates `ask_{step}` and `store_{step}` nodes
3. **Voice Interface**: LiveKit handles voice input/output
4. **State Management**: LangGraph manages conversation state with checkpointing

## 📊 What the Visualization Shows

### Node Types
- **🟢 START**: Entry point of the flow
- **🔵 ASK Nodes**: Questions being asked to the user (from your `ask_prompt`)
- **🟣 STORE Nodes**: Data storage operations (saving to Supabase)
- **🔴 END**: Flow completion

### Visual States
- **🟦 Active**: Currently executing step (blue border)
- **✅ Completed**: Finished steps (green background)  
- **⭕ Pending**: Not yet reached (gray)
- **📝 Data**: Shows collected values in each node

## 🚀 Running the Visualization

```bash
# Start the React app
cd flow_ui
npm start
```

The app runs on `http://localhost:3000` and shows:
- Interactive flow diagram with zoom/pan
- Real-time session panel
- Progress tracking
- Collected data display

## 🔌 Connecting to Your Backend

Currently in **demo mode**. To connect to your actual Python backend:

### 1. Add API Endpoints to Your Python Backend

Add these endpoints to your `server.py` or create a new FastAPI router:

```python
from fastapi import FastAPI, WebSocket
from strict_intake_assistant import StrictIntakeAssistant

app = FastAPI()

@app.post("/api/intake/start")
async def start_intake_session():
    assistant = await StrictIntakeAssistant.create()
    session_id = f"web_{uuid.uuid4()}"
    response = await assistant.start(session_id)
    return {
        "session_id": session_id,
        "initial_message": response,
        "current_step": assistant.entry
    }

@app.post("/api/intake/message")
async def handle_message(payload: dict):
    session_id = payload["session_id"]
    message = payload["message"]
    # Use your existing assistant.handle_user(message, session_id)
    response = await assistant.handle_user(message, session_id)
    return {"response": response}

@app.get("/api/intake/state/{session_id}")
async def get_session_state(session_id: str):
    # Get current state from LangGraph checkpointer
    cfg = {"configurable": {"thread_id": session_id}}
    state = await assistant.app.aget_state(cfg)
    return state.values if state else {}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    # Stream real-time events from your intake process
```

### 2. Update React Configuration

In `src/hooks/useIntakeAPI.ts`, uncomment the API calls and set the correct:
- `API_BASE_URL`: Your Python server URL (probably `http://localhost:8000`)
- `WS_URL`: WebSocket endpoint for real-time updates

### 3. Enable Real-time Updates

The visualization will automatically:
- Connect via WebSocket to your backend
- Update the flow diagram as steps complete
- Show collected data in real-time
- Track progress through the intake

## 📁 Project Structure

```
flow_ui/
├── src/
│   ├── components/
│   │   ├── IntakeFlowVisualizer.tsx    # Main flow diagram
│   │   ├── SessionPanel.tsx            # Session info & controls
│   │   └── nodes/
│   │       └── StepNode.tsx           # Custom React Flow nodes
│   ├── hooks/
│   │   └── useIntakeAPI.ts            # Backend integration
│   ├── types/
│   │   └── IntakeTypes.ts             # TypeScript interfaces
│   └── App.tsx                        # Main app component
├── package.json
└── README.md
```

## 🎨 Customization

### Adding New Node Types
Create custom nodes in `src/components/nodes/` for different step types:
- Validation nodes
- Conditional branches  
- External API calls

### Styling
Modify `src/App.css` and node styles to match your brand colors.

### Real-time Features
Add more WebSocket event types:
- `step_started`
- `validation_failed` 
- `user_input_received`
- `ai_response_generated`

## 🔧 Integration Points

This visualization integrates with your existing system at these points:

1. **Flow Definition**: Reads from your Supabase `flows` and `intake_steps` tables
2. **Session State**: Connects to your LangGraph checkpointer state
3. **Real-time Events**: WebSocket connection to your Python backend
4. **Data Collection**: Shows data from your `intake_answers` table

## 📈 Benefits

- **Debug Your Flow**: See exactly where users get stuck
- **Monitor Progress**: Track completion rates by step
- **Real-time Insights**: Watch intake sessions as they happen
- **User Experience**: Provide visual feedback during voice calls
- **Analytics**: Identify bottlenecks in your intake process

## 🚀 Next Steps

1. **Connect to Backend**: Add the API endpoints to your Python server
2. **Real-time WebSocket**: Stream events from your LangGraph execution
3. **Database Integration**: Load actual flow steps from Supabase
4. **Voice Integration**: Show voice transcription in real-time
5. **Analytics Dashboard**: Add metrics and completion rates

Your intake flow visualization is ready! 🎉