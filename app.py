import os
import json
import logging
import asyncio
from datetime import datetime, timedelta
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, status, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from auth import authenticate_user, create_access_token, verify_token, token_blacklist
from heartbeat import register_client, remove_client, heartbeat_checker, connected_clients
from data_handler import handle_data_reception, handle_parent_command

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Watch Server", 
              description="Parent-Child Monitoring Server",
              version="1.0.0",
              docs_url="/docs" if os.environ.get("DEBUG", "false").lower() == "true" else None,
              redoc_url=None)

# Production CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=json.loads(os.environ.get("CORS_ORIGINS", '["http://localhost:3000", "http://127.0.0.1:3000"]')),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security headers middleware
@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response

# Root endpoint
@app.get("/")
async def root():
    return {
        "message": "Watch Server is running", 
        "status": "production",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat(),
        "endpoints": {
            "health": "/health",
            "auth": "/auth", 
            "clients": "/clients",
            "websocket": "/ws/{client_id}"
        }
    }

# Health check endpoint
@app.get("/health")
async def health_check():
    return {
        "status": "healthy", 
        "server": "Watch Server",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    }

# Connected clients endpoint
@app.get("/clients")
async def get_connected_clients():
    """Get list of currently connected clients"""
    clients_info = []
    for client_id, client_data in connected_clients.items():
        clients_info.append({
            "client_id": client_id,
            "user_type": client_data.get('user_type', 'unknown'),
            "last_heartbeat": client_data.get('last_heartbeat'),
            "connection_time": client_data.get('connection_time')
        })
    return {
        "clients": clients_info, 
        "count": len(clients_info),
        "server": "Watch Server"
    }

# WebSocket connections
active_connections = {}

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    try:
        await websocket.accept()
        
        # Wait for authentication token as first message
        auth_message = await websocket.receive_text()
        auth_data = json.loads(auth_message)
        
        token = auth_data.get('token')
        if not token:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        
        # Authenticate user
        user = verify_token(token)
        if not user:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        
        user_type = user['role']
        username = user['sub']
        
        # Register client
        register_client(client_id, websocket, user_type)
        logger.info(f"✅ {user_type.capitalize()} client connected: {client_id} (User: {username})")
        
        # Send connection confirmation
        await websocket.send_text(json.dumps({
            "status": "connected",
            "client_id": client_id,
            "user_type": user_type,
            "server": "Watch Server",
            "message": "Connection established successfully"
        }))
        
        try:
            while True:
                # Receive data from client
                data = await websocket.receive_text()
                data_dict = json.loads(data)
                
                # Handle based on user type
                if user_type == 'child':
                    await handle_data_reception(websocket, client_id, data_dict)
                elif user_type == 'parent':
                    await handle_parent_command(websocket, client_id, data_dict)
                    
        except WebSocketDisconnect:
            logger.info(f"🔌 Client disconnected: {client_id}")
            remove_client(client_id)
        except Exception as e:
            logger.error(f"❌ Error with client {client_id}: {str(e)}")
            remove_client(client_id)
            
    except Exception as e:
        logger.error(f"❌ WebSocket connection error: {str(e)}")
        try:
            await websocket.close()
        except:
            pass

@app.post("/auth")
async def login(username: str, password: str):
    """Authenticate user and return JWT token"""
    user = authenticate_user(username, password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    access_token = create_access_token(
        data={"sub": user["username"], "role": user["role"]}
    )
    
    # Calculate expiry based on user role
    if user["role"] == "child":
        expires_in = 365 * 24 * 60  # 365 days in minutes
        expiry_message = "Token valid for 365 days (Child device)"
    else:
        expires_in = 7 * 24 * 60  # 7 days in minutes
        expiry_message = "Token valid for 7 days (Parent device)"
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_type": user["role"],
        "expires_in": expires_in,
        "expiry_message": expiry_message,
        "client_id": user["username"],
        "server": "Watch Server"
    }

@app.post("/logout")
async def logout(token: str):
    """Invalidate JWT token"""
    token_blacklist.add(token)
    return {
        "message": "Successfully logged out",
        "server": "Watch Server"
    }

@app.on_event("startup")
async def startup_event():
    # Start heartbeat checker
    asyncio.create_task(heartbeat_checker())
    logger.info("🚀 Watch Server started successfully in production mode")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "0.0.0.0")
    debug = os.environ.get("DEBUG", "false").lower() == "true"
    
    uvicorn.run(app, host=host, port=port, log_level="info" if not debug else "debug")