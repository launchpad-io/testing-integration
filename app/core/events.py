# app/core/events.py
"""
Event-driven system for real-time updates using Redis Pub/Sub
"""

import json
import asyncio
from typing import Dict, Any, Callable, List
from datetime import datetime
import redis.asyncio as redis
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)


class EventType:
    """Event type constants"""
    # Order events
    ORDER_CREATED = "order.created"
    ORDER_UPDATED = "order.updated"
    ORDER_CANCELLED = "order.cancelled"
    
    # Video events
    VIDEO_POSTED = "video.posted"
    VIDEO_METRICS_UPDATED = "video.metrics.updated"
    VIDEO_DELETED = "video.deleted"
    
    # Product events
    PRODUCT_UPDATED = "product.updated"
    INVENTORY_CHANGED = "inventory.changed"
    
    # Campaign events
    DELIVERABLE_SUBMITTED = "deliverable.submitted"
    DELIVERABLE_APPROVED = "deliverable.approved"
    CAMPAIGN_MILESTONE = "campaign.milestone"
    
    # Creator events
    CREATOR_CONNECTED = "creator.connected"
    CREATOR_PERFORMANCE_UPDATE = "creator.performance.update"
    
    # System events
    SYNC_STARTED = "sync.started"
    SYNC_COMPLETED = "sync.completed"
    SYNC_FAILED = "sync.failed"


class Event:
    """Event data structure"""
    
    def __init__(
        self,
        event_type: str,
        data: Dict[str, Any],
        source: str,
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.event_id = str(uuid.uuid4())
        self.event_type = event_type
        self.data = data
        self.source = source
        self.user_id = user_id
        self.metadata = metadata or {}
        self.timestamp = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "data": self.data,
            "source": self.source,
            "user_id": self.user_id,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat()
        }
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict())
    
    @classmethod
    def from_json(cls, json_str: str) -> 'Event':
        data = json.loads(json_str)
        event = cls(
            event_type=data["event_type"],
            data=data["data"],
            source=data["source"],
            user_id=data.get("user_id"),
            metadata=data.get("metadata", {})
        )
        event.event_id = data["event_id"]
        event.timestamp = datetime.fromisoformat(data["timestamp"])
        return event


class EventBus:
    """Central event bus for publishing and subscribing to events"""
    
    def __init__(self):
        self.redis_client = None
        self.pubsub = None
        self.handlers: Dict[str, List[Callable]] = {}
        self.running = False
    
    async def connect(self):
        """Connect to Redis"""
        self.redis_client = await redis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True
        )
        self.pubsub = self.redis_client.pubsub()
        logger.info("EventBus connected to Redis")
    
    async def disconnect(self):
        """Disconnect from Redis"""
        if self.pubsub:
            await self.pubsub.close()
        if self.redis_client:
            await self.redis_client.close()
        logger.info("EventBus disconnected")
    
    async def publish(self, event: Event):
        """Publish an event"""
        if not self.redis_client:
            await self.connect()
        
        # Publish to Redis channel
        channel = f"events:{event.event_type}"
        await self.redis_client.publish(channel, event.to_json())
        
        # Also publish to user-specific channel if user_id is present
        if event.user_id:
            user_channel = f"events:user:{event.user_id}"
            await self.redis_client.publish(user_channel, event.to_json())
        
        logger.info(f"Published event {event.event_id} of type {event.event_type}")
    
    def subscribe(self, event_type: str, handler: Callable):
        """Subscribe to an event type"""
        if event_type not in self.handlers:
            self.handlers[event_type] = []
        
        self.handlers[event_type].append(handler)
        logger.info(f"Subscribed handler to {event_type}")
    
    async def start(self):
        """Start listening for events"""
        if not self.pubsub:
            await self.connect()
        
        self.running = True
        
        # Subscribe to all registered event types
        for event_type in self.handlers.keys():
            channel = f"events:{event_type}"
            await self.pubsub.subscribe(channel)
            logger.info(f"Subscribed to channel: {channel}")
        
        # Start message handler
        asyncio.create_task(self._handle_messages())
    
    async def stop(self):
        """Stop listening for events"""
        self.running = False
        await self.disconnect()
    
    async def _handle_messages(self):
        """Handle incoming messages"""
        async for message in self.pubsub.listen():
            if message["type"] == "message":
                try:
                    # Parse event
                    event = Event.from_json(message["data"])
                    
                    # Call all handlers for this event type
                    handlers = self.handlers.get(event.event_type, [])
                    
                    for handler in handlers:
                        try:
                            if asyncio.iscoroutinefunction(handler):
                                await handler(event)
                            else:
                                handler(event)
                        except Exception as e:
                            logger.error(f"Handler error for {event.event_type}: {e}")
                
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
            
            if not self.running:
                break


# Global event bus instance
event_bus = EventBus()


# Event handler decorators
def on_event(event_type: str):
    """Decorator to register event handlers"""
    def decorator(func):
        event_bus.subscribe(event_type, func)
        return func
    return decorator


# Example event handlers
@on_event(EventType.ORDER_CREATED)
async def handle_order_created(event: Event):
    """Handle order created events"""
    logger.info(f"New order created: {event.data}")
    
    # Update analytics
    from app.external.analytics_service_client import AnalyticsServiceClient
    analytics_client = AnalyticsServiceClient()
    
    await analytics_client.track_order(
        order_id=event.data["order_id"],
        shop_id=event.data["shop_id"],
        amount=event.data["total_amount"]
    )
    
    # Broadcast to WebSocket clients
    from app.api.v1.endpoints.websocket import broadcast_order_update
    await broadcast_order_update(event.data)


@on_event(EventType.VIDEO_METRICS_UPDATED)
async def handle_video_metrics(event: Event):
    """Handle video metrics updates"""
    logger.info(f"Video metrics updated: {event.data}")
    
    # Check if video meets campaign requirements
    if event.data.get("is_deliverable"):
        from app.external.campaign_service_client import CampaignServiceClient
        campaign_client = CampaignServiceClient()
        
        await campaign_client.check_deliverable_performance(
            video_id=event.data["video_id"],
            metrics=event.data["metrics"]
        )


# Utility functions for publishing common events
async def publish_order_event(order_data: Dict[str, Any], event_type: str = EventType.ORDER_CREATED):
    """Publish order-related events"""
    event = Event(
        event_type=event_type,
        data=order_data,
        source="integration-service",
        user_id=order_data.get("creator_id"),
        metadata={
            "shop_id": order_data.get("shop_id"),
            "order_id": order_data.get("order_id")
        }
    )
    
    await event_bus.publish(event)


async def publish_video_event(video_data: Dict[str, Any], event_type: str = EventType.VIDEO_POSTED):
    """Publish video-related events"""
    event = Event(
        event_type=event_type,
        data=video_data,
        source="integration-service",
        user_id=video_data.get("creator_id"),
        metadata={
            "video_id": video_data.get("video_id"),
            "campaign_id": video_data.get("campaign_id")
        }
    )
    
    await event_bus.publish(event)