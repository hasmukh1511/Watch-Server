import os
import json
import logging
import asyncio
from datetime import datetime, timedelta
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, status, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from auth import authenticate_user, create_access_token, verify_token, ACCESS_TOKEN_EXPIRE_MINUTES
from heartbeat import register_client, remove_client, heartbeat_checker, connected_clients
from data_handler import handle_data_reception, handle_parent_command

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Parent Control Server")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Root endpoint
@app.get("/")
async def root():
    return {
        "message": "Parent Control Server is running", 
        "endpoints": {
            "health": "/health",
            "auth": "/auth",
            "clients": "/clients",
            "websocket": "/ws/{client_id}"
        },
        "timestamp": datetime.now().isoformat()
    }

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

# Connected clients endpoint
@app.get("/clients")
async def get_connected_clients():
    """Get list of currently connected clients"""
    clients_info = []
    for client_id, client_data in connected_clients.items():
        clients_info.append({
            "client_id": client_id,
            "user_type": client_data.get('user_type', 'unknown'),
            "last_heartbeat": client_data.get('last_heartbeat')
        })
    
    return {"clients": clients_info}

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
            "user_type": user_type
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
    user = authenticate_user(username, password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user["username"], "role": user["role"]}, 
        expires_delta=access_token_expires
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_type": user["role"],
        "client_id": user["username"] + "_" + str(os.urandom(4).hex())
    }

@app.on_event("startup")
async def startup_event():
    # Start heartbeat checker
    asyncio.create_task(heartbeat_checker())
    logger.info("🚀 Parent Control Server started")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="127.0.0.1", port=port)