#!/usr/bin/env python3

import os
import json
import jwt
import time
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from dotenv import load_dotenv

# Load environment variables
load_dotenv(".env.local")

class InjuryAssistantServer(SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed_path = urlparse(self.path)
        
        if parsed_path.path == '/':
            # Serve the main test client page
            self.path = '/test_client.html'
            return SimpleHTTPRequestHandler.do_GET(self)
        
        elif parsed_path.path == '/simple':
            # Serve the simple test page
            self.path = '/simple_test.html'
            return SimpleHTTPRequestHandler.do_GET(self)
        
        elif parsed_path.path == '/token':
            # Generate and return a token
            self.generate_token_endpoint()
        
        else:
            # Serve static files
            return SimpleHTTPRequestHandler.do_GET(self)
    
    def generate_token_endpoint(self):
        """API endpoint to generate LiveKit tokens"""
        try:
            # Parse query parameters
            query_params = parse_qs(urlparse(self.path).query)
            room_name = query_params.get('room', ['injury-assistant-demo'])[0]
            participant_name = query_params.get('participant', ['test-user'])[0]
            
            # Generate token
            token = self.generate_livekit_token(room_name, participant_name)
            
            if token:
                response = {
                    'success': True,
                    'token': token,
                    'room': room_name,
                    'participant': participant_name,
                    'server': 'wss://injury-helpline-a20au6fh.livekit.cloud'
                }
            else:
                response = {
                    'success': False,
                    'error': 'Failed to generate token'
                }
            
            # Send JSON response
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')  # Enable CORS
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())
            
        except Exception as e:
            self.send_error(500, f"Token generation failed: {str(e)}")
    
    def generate_livekit_token(self, room_name: str, participant_name: str):
        """Generate a LiveKit access token using JWT"""
        
        api_key = os.getenv("LIVEKIT_API_KEY")
        api_secret = os.getenv("LIVEKIT_API_SECRET")
        
        if not api_key or not api_secret:
            print("❌ Missing LIVEKIT_API_KEY or LIVEKIT_API_SECRET")
            return None
        
        # Create JWT payload
        now = int(time.time())
        payload = {
            "iss": api_key,
            "sub": participant_name,
            "iat": now,
            "exp": now + 3600,  # Token expires in 1 hour
            "video": {
                "room": room_name,
                "roomJoin": True,
                "canPublish": True,
                "canSubscribe": True,
                "canPublishData": True
            }
        }
        
        # Generate JWT token
        jwt_token = jwt.encode(payload, api_secret, algorithm="HS256")
        
        print(f"🔑 Generated token for {participant_name} in room {room_name}")
        
        return jwt_token

def run_server(port=3000):
    """Run the local development server"""
    
    print(f"🚀 Starting Injury Assistant Development Server")
    print(f"📍 Server running at: http://localhost:{port}")
    print(f"🏥 Test Client: http://localhost:{port}/")
    print(f"🔑 Token API: http://localhost:{port}/token?room=ROOM&participant=NAME")
    print(f"⏹️  Press Ctrl+C to stop")
    print("-" * 60)
    
    server_address = ('', port)
    httpd = HTTPServer(server_address, InjuryAssistantServer)
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print(f"\n🛑 Server stopped")
        httpd.server_close()

if __name__ == "__main__":
    run_server(3000)
