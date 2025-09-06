from dotenv import load_dotenv
import os
import jwt
import time

# Load environment variables
load_dotenv(".env.local")

# Get credentials from environment variables
API_KEY = os.getenv("LIVEKIT_API_KEY")
API_SECRET = os.getenv("LIVEKIT_API_SECRET")

def generate_token(room_name: str, identity: str) -> str:
    """Generate a LiveKit token for a specific room and user identity"""
    if not API_KEY or not API_SECRET:
        raise ValueError("Missing LIVEKIT_API_KEY or LIVEKIT_API_SECRET in .env.local")

    # Token claims
    now = int(time.time())
    claims = {
        "iss": API_KEY,  # Issuer - your API key
        "sub": identity,  # Subject - user identity
        "jti": f"{identity}-{now}",  # Unique token ID
        "exp": now + 3600,  # Expiration - 1 hour from now
        "nbf": now,  # Not valid before current time
        "room": room_name,  # Room name
        "video": {
            "room": room_name,
            "roomJoin": True,
            "canPublish": True,
            "canSubscribe": True,
            "canPublishData": True
        }
    }

    # Generate JWT token
    token = jwt.encode(claims, API_SECRET, algorithm='HS256')
    return token

if __name__ == "__main__":
    room_name = "injury-demo-room"
    identity = "client-user-1"  # Unique identifier for the client

    try:
        token = generate_token(room_name, identity)
        print("\nGenerated LiveKit Token:")
        print("------------------------")
        print(token)
        print("\nAdd this token to your React client's .env file as:")
        print("REACT_APP_LIVEKIT_TOKEN=" + token)
    except Exception as e:
        print(f"Error generating token: {e}")