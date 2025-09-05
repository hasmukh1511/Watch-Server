import asyncio
import logging
from datetime import datetime

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Store connected clients and their last heartbeat
connected_clients = {}

async def heartbeat_checker():
    """
    Check every 2 minutes if clients are still connected
    """
    while True:
        await asyncio.sleep(120)  # 2 minutes
        current_time = datetime.now()
        disconnected_clients = []
        
        for client_id, client_data in connected_clients.items():
            last_heartbeat = client_data.get('last_heartbeat')
            if last_heartbeat and (current_time - last_heartbeat).total_seconds() > 150:  # 2.5 minutes
                disconnected_clients.append(client_id)
                logger.warning(f"Client {client_id} disconnected due to heartbeat timeout")
        
        # Remove disconnected clients
        for client_id in disconnected_clients:
            if client_id in connected_clients:
                del connected_clients[client_id]

def update_heartbeat(client_id: str):
    """
    Update the heartbeat for a client
    """
    if client_id in connected_clients:
        connected_clients[client_id]['last_heartbeat'] = datetime.now()

def register_client(client_id: str, websocket, user_type: str):
    """
    Register a new client
    """
    connected_clients[client_id] = {
        'websocket': websocket,
        'last_heartbeat': datetime.now(),
        'connection_time': datetime.now(),
        'user_type': user_type
    }
    logger.info(f"✅ Registered client: {client_id} (Type: {user_type})")

def remove_client(client_id: str):
    """
    Remove a client
    """
    if client_id in connected_clients:
        del connected_clients[client_id]
        logger.info(f"✅ Removed client: {client_id}")