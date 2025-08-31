# data_handler.py
import json
import logging
from datetime import datetime
from heartbeat import connected_clients, update_heartbeat

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def handle_data_reception(websocket, client_id: str, data: dict):
    """
    Handle incoming data from child devices
    """
    try:
        logger.info(f"📨 Received data from {client_id}: {data}")
        
        # Update heartbeat
        update_heartbeat(client_id)
        
        # Extract data type and payload
        data_type = data.get('type', 'unknown')
        payload = data.get('payload', {})
        
        # Handle different data types
        if data_type == 'heartbeat':
            # Just update heartbeat, no further action needed
            logger.debug(f"Heartbeat received from {client_id}")
            response = {"status": "success", "type": "heartbeat_ack"}
            await websocket.send_text(json.dumps(response))
        
        elif data_type in ['camera', 'microphone', 'screen', 'directory', 'files', 'location']:
            await forward_to_parent(client_id, data_type, payload)
            response = {"status": "success", "type": f"{data_type}_ack"}
            await websocket.send_text(json.dumps(response))
        
        else:
            logger.warning(f"❓ Unknown data type received from {client_id}: {data_type}")
            response = {"status": "error", "message": f"Unknown data type: {data_type}"}
            await websocket.send_text(json.dumps(response))
    
    except Exception as e:
        logger.error(f"❌ Error handling data from {client_id}: {str(e)}")
        error_response = {"status": "error", "message": f"Processing error: {str(e)}"}
        await websocket.send_text(json.dumps(error_response))

async def handle_parent_command(websocket, client_id: str, data: dict):
    """
    Handle commands from parent to child devices
    """
    try:
        logger.info(f"🎛️ Received command from parent {client_id}: {data}")
        
        # Update heartbeat
        update_heartbeat(client_id)
        
        # Extract command details
        command = data.get('command', 'unknown')
        target_child = data.get('target_child', '')
        payload = data.get('payload', {})
        
        # Validate command
        if not target_child:
            error_response = {"status": "error", "message": "Target child not specified"}
            await websocket.send_text(json.dumps(error_response))
            return
        
        # Find target child connection
        if target_child in connected_clients:
            child_conn = connected_clients[target_child]['websocket']
            message = {
                'type': 'command',
                'command': command,
                'payload': payload,
                'timestamp': datetime.now().isoformat()
            }
            await child_conn.send_text(json.dumps(message))
            logger.info(f"✅ Command {command} sent to {target_child}")
            
            # Send success response to parent
            success_response = {
                "status": "success",
                "message": f"Command {command} sent to {target_child}",
                "command": command
            }
            await websocket.send_text(json.dumps(success_response))
        else:
            logger.warning(f"❌ Target child {target_child} not found for command {command}")
            error_response = {
                "status": "error",
                "message": f"Target child {target_child} not found or offline"
            }
            await websocket.send_text(json.dumps(error_response))
    
    except Exception as e:
        logger.error(f"❌ Error handling parent command: {str(e)}")
        error_response = {
            "status": "error",
            "message": f"Error executing command: {str(e)}"
        }
        await websocket.send_text(json.dumps(error_response))

async def forward_to_parent(child_id: str, data_type: str, payload: dict):
    """
    Forward data from child to parent
    """
    try:
        # Find parent connection
        parent_conn = None
        parent_id = None
        
        for client_id, client_data in connected_clients.items():
            if client_data.get('user_type') == 'parent':
                parent_conn = client_data['websocket']
                parent_id = client_id
                break
        
        if parent_conn:
            message = {
                'type': data_type,
                'from': child_id,
                'payload': payload,
                'timestamp': datetime.now().isoformat()
            }
            await parent_conn.send_text(json.dumps(message))
            logger.info(f"📤 Data forwarded from {child_id} to parent {parent_id}: {data_type}")
        else:
            logger.warning(f"⚠️ No parent connection found to forward data from {child_id}")
    
    except Exception as e:
        logger.error(f"❌ Error forwarding data to parent: {str(e)}")