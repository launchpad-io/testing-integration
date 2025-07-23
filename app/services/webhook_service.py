# app/services/webhook_service.py - Simplified version
import hmac
import hashlib
import json
from typing import Dict, Any
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

class WebhookService:
    def __init__(self):
        self.max_retry_attempts = 3  # Add this line
        
    async def verify_signature(self, signature: str, body: bytes) -> bool:
        """Verify TikTok webhook signature"""
        expected_signature = hmac.new(
            settings.TIKTOK_APP_SECRET.encode('utf-8'),
            body,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(signature, expected_signature)
    
    async def process_webhook(self, data: Dict[str, Any]):
        """Process TikTok webhook event"""
        event_type = data.get("type")
        shop_id = data.get("shop_id")
        event_data = data.get("data", {})
        
        logger.info(f"Processing webhook: type={event_type}, shop_id={shop_id}")
        
        # Handle different event types
        if event_type == "order_status_change":
            await self._handle_order_status_change(shop_id, event_data)
        elif event_type == "product_status_change":
            await self._handle_product_status_change(shop_id, event_data)
        elif event_type == "authorization_revoked":
            await self._handle_authorization_revoked(shop_id, event_data)
        else:
            logger.warning(f"Unknown webhook event type: {event_type}")
    
    async def _handle_order_status_change(self, shop_id: str, data: Dict[str, Any]):
        """Handle order status change event"""
        order_id = data.get("order_id")
        new_status = data.get("order_status")
        logger.info(f"Order status changed: order_id={order_id}, status={new_status}")
        # TODO: Update order in database and notify relevant services
    
    async def _handle_product_status_change(self, shop_id: str, data: Dict[str, Any]):
        """Handle product status change event"""
        product_id = data.get("product_id")
        new_status = data.get("product_status")
        logger.info(f"Product status changed: product_id={product_id}, status={new_status}")
        # TODO: Update product in database
    
    async def _handle_authorization_revoked(self, shop_id: str, data: Dict[str, Any]):
        """Handle authorization revoked event"""
        logger.warning(f"Authorization revoked for shop: {shop_id}")
        # TODO: Mark shop as inactive in database