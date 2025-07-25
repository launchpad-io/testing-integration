# app/api/v1/endpoints/websocket.py
"""
WebSocket endpoints for real-time data updates
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from typing import Dict, Set, Optional
import json
import asyncio
import logging
from datetime import datetime
from app.core.dependencies import get_current_user_ws
from app.services.tiktok_realtime_service import TikTokRealtimeService

router = APIRouter()
logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manage WebSocket connections"""
    
    def __init__(self):
        # Store active connections by user_id and subscription type
        self.active_connections: Dict[str, Dict[str, WebSocket]] = {}
        self.subscriptions: Dict[str, Set[str]] = {}
    
    async def connect(self, websocket: WebSocket, user_id: str, client_id: str):
        """Accept new WebSocket connection"""
        await websocket.accept()
        
        if user_id not in self.active_connections:
            self.active_connections[user_id] = {}
            self.subscriptions[user_id] = set()
        
        self.active_connections[user_id][client_id] = websocket
        logger.info(f"User {user_id} connected with client {client_id}")
    
    def disconnect(self, user_id: str, client_id: str):
        """Remove WebSocket connection"""
        if user_id in self.active_connections:
            self.active_connections[user_id].pop(client_id, None)
            
            # Clean up if no more connections for user
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
                self.subscriptions.pop(user_id, None)
        
        logger.info(f"User {user_id} disconnected client {client_id}")
    
    async def subscribe(self, user_id: str, event_types: Set[str]):
        """Subscribe user to specific event types"""
        if user_id in self.subscriptions:
            self.subscriptions[user_id].update(event_types)
        else:
            self.subscriptions[user_id] = event_types
    
    async def unsubscribe(self, user_id: str, event_types: Set[str]):
        """Unsubscribe user from event types"""
        if user_id in self.subscriptions:
            self.subscriptions[user_id] -= event_types
    
    async def send_personal_message(self, message: str, user_id: str):
        """Send message to specific user"""
        if user_id in self.active_connections:
            disconnected_clients = []
            
            for client_id, websocket in self.active_connections[user_id].items():
                try:
                    await websocket.send_text(message)
                except Exception as e:
                    logger.error(f"Error sending to {user_id}/{client_id}: {e}")
                    disconnected_clients.append(client_id)
            
            # Clean up disconnected clients
            for client_id in disconnected_clients:
                self.disconnect(user_id, client_id)
    
    async def broadcast(self, message: str, event_type: str):
        """Broadcast message to all subscribed users"""
        for user_id, event_types in self.subscriptions.items():
            if event_type in event_types:
                await self.send_personal_message(message, user_id)


# Global connection manager
manager = ConnectionManager()


@router.websocket("/ws/{user_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    user_id: str,
    client_id: str = Query(...),
    token: Optional[str] = Query(None)
):
    """WebSocket endpoint for real-time updates"""
    
    # Validate user token (simplified for example)
    if not token:
        await websocket.close(code=4001, reason="Unauthorized")
        return
    
    await manager.connect(websocket, user_id, client_id)
    
    try:
        # Send initial connection success message
        await websocket.send_json({
            "type": "connection",
            "status": "connected",
            "timestamp": datetime.utcnow().isoformat()
        })
        
        while True:
            # Receive messages from client
            data = await websocket.receive_json()
            
            message_type = data.get("type")
            
            if message_type == "subscribe":
                # Subscribe to event types
                event_types = set(data.get("events", []))
                await manager.subscribe(user_id, event_types)
                
                await websocket.send_json({
                    "type": "subscription",
                    "status": "subscribed",
                    "events": list(event_types)
                })
            
            elif message_type == "unsubscribe":
                # Unsubscribe from event types
                event_types = set(data.get("events", []))
                await manager.unsubscribe(user_id, event_types)
                
                await websocket.send_json({
                    "type": "subscription",
                    "status": "unsubscribed",
                    "events": list(event_types)
                })
            
            elif message_type == "ping":
                # Respond to ping
                await websocket.send_json({
                    "type": "pong",
                    "timestamp": datetime.utcnow().isoformat()
                })
            
    except WebSocketDisconnect:
        manager.disconnect(user_id, client_id)
    except Exception as e:
        logger.error(f"WebSocket error for {user_id}: {e}")
        manager.disconnect(user_id, client_id)


# Event broadcasting functions
async def broadcast_order_update(order_data: Dict):
    """Broadcast order updates to subscribed users"""
    message = json.dumps({
        "type": "order_update",
        "data": order_data,
        "timestamp": datetime.utcnow().isoformat()
    })
    
    await manager.broadcast(message, "orders")


async def broadcast_video_metrics(video_data: Dict):
    """Broadcast video metric updates"""
    message = json.dumps({
        "type": "video_metrics",
        "data": video_data,
        "timestamp": datetime.utcnow().isoformat()
    })
    
    await manager.broadcast(message, "videos")


async def broadcast_gmv_update(gmv_data: Dict):
    """Broadcast GMV updates"""
    message = json.dumps({
        "type": "gmv_update",
        "data": gmv_data,
        "timestamp": datetime.utcnow().isoformat()
    })
    
    await manager.broadcast(message, "gmv")


# Background task for sending periodic updates
async def send_periodic_updates():
    """Send periodic updates to connected clients"""
    while True:
        try:
            # Get latest metrics from database
            # This is a simplified example
            
            # Send dashboard updates every 30 seconds
            for user_id in manager.active_connections:
                dashboard_data = {
                    "total_gmv": 125000.50,
                    "active_campaigns": 5,
                    "total_creators": 45,
                    "last_order_time": datetime.utcnow().isoformat()
                }
                
                message = json.dumps({
                    "type": "dashboard_update",
                    "data": dashboard_data,
                    "timestamp": datetime.utcnow().isoformat()
                })
                
                await manager.send_personal_message(message, user_id)
            
        except Exception as e:
            logger.error(f"Error in periodic updates: {e}")
        
        await asyncio.sleep(30)  # Update every 30 seconds