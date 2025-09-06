#!/bin/bash

# Load environment variables
source .env.local

# Check if required variables are set
if [ -z "$LIVEKIT_URL" ] || [ -z "$LIVEKIT_API_KEY" ] || [ -z "$LIVEKIT_API_SECRET" ]; then
    echo "❌ Missing required environment variables:"
    echo "   LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET"
    echo "   Please check your .env.local file"
    exit 1
fi

echo "🚀 Starting LiveKit Cloud job..."
echo "   Room: injury-demo-room"
echo "   Agent Identity: srushti-agent-1"
echo "   LiveKit URL: $LIVEKIT_URL"

# Start the LiveKit Cloud job
curl -u "$LIVEKIT_API_KEY:$LIVEKIT_API_SECRET" \
  -H "Content-Type: application/json" \
  -X POST "$LIVEKIT_URL/v1/agents/jobs" \
  -d '{
    "template": { "url": "docker.io/livekit/agents:latest" },
    "room": "injury-demo-room",
    "identity": "srushti-agent-1"
  }'

echo ""
echo "✅ LiveKit Cloud job request sent!"
echo "The agent should now join the injury-demo-room"
