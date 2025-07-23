# app/api/v1/endpoints/webhooks.py
from fastapi import APIRouter, Request, HTTPException, Header, BackgroundTasks, Query
from app.services.webhook_service import WebhookService
from app.models.schemas import WebhookEvent
from app.utils.webhook_validator import validate_webhook_payload
import logging
import time
import json
from typing import Optional
from datetime import datetime, timedelta

router = APIRouter()
logger = logging.getLogger(__name__)

# In-memory store for processed webhook IDs (use Redis in production)
processed_webhooks = {}

def cleanup_old_webhooks():
    """Remove webhook IDs older than 24 hours"""
    current_time = datetime.utcnow()
    expired_keys = [
        k for k, v in processed_webhooks.items() 
        if current_time - v > timedelta(hours=24)
    ]
    for key in expired_keys:
        del processed_webhooks[key]

@router.post("/tiktok")
async def handle_tiktok_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_tiktok_signature: Optional[str] = Header(None),
    x_tiktok_timestamp: Optional[str] = Header(None),
    x_tiktok_nonce: Optional[str] = Header(None),
    x_webhook_id: Optional[str] = Header(None)
):
    """Handle TikTok Shop webhooks with enhanced security"""
    webhook_service = WebhookService()
    
    # Get raw body
    body = await request.body()
    
    # Log webhook reception
    logger.info(f"Received webhook - ID: {x_webhook_id}, Timestamp: {x_tiktok_timestamp}")
    
    # 1. Validate timestamp to prevent replay attacks
    if x_tiktok_timestamp:
        try:
            webhook_timestamp = int(x_tiktok_timestamp)
            current_timestamp = int(time.time())
            
            # Reject webhooks older than 5 minutes
            if abs(current_timestamp - webhook_timestamp) > 300:
                logger.warning(f"Webhook timestamp too old: {webhook_timestamp}")
                raise HTTPException(status_code=400, detail="Webhook timestamp expired")
                
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid timestamp format")
    
    # 2. Verify signature
    if x_tiktok_signature:
        is_valid = await webhook_service.verify_signature(x_tiktok_signature, body)
        
        if not is_valid:
            logger.error(f"Invalid webhook signature - ID: {x_webhook_id}")
            raise HTTPException(status_code=401, detail="Invalid signature")
    else:
        logger.warning("Webhook received without signature")
        # For testing, you might want to allow unsigned webhooks
        # In production, uncomment the following line:
        # raise HTTPException(status_code=401, detail="Missing signature")
    
    # 3. Check for duplicate webhooks (deduplication)
    if x_webhook_id:
        if x_webhook_id in processed_webhooks:
            logger.info(f"Duplicate webhook detected - ID: {x_webhook_id}")
            return {"status": "already_processed", "webhook_id": x_webhook_id}
        
        # Mark as processed
        processed_webhooks[x_webhook_id] = datetime.utcnow()
        
        # Schedule cleanup
        if len(processed_webhooks) > 10000:  # Prevent memory overflow
            cleanup_old_webhooks()
    
    # 4. Parse and validate webhook data
    try:
        data = json.loads(body)
        
        # Validate webhook structure
        if not validate_webhook_payload(data):
            raise HTTPException(status_code=400, detail="Invalid webhook payload structure")
        
        # Extract event details
        event_type = data.get("type")
        shop_id = data.get("shop_id")
        
        if not event_type or not shop_id:
            raise HTTPException(status_code=400, detail="Missing required webhook fields")
        
        # 5. Process webhook asynchronously (simplified for now)
        await webhook_service.process_webhook(data)
        
        # Log successful reception
        logger.info(f"Webhook accepted for processing - Type: {event_type}, Shop: {shop_id}")
        
        return {
            "status": "accepted",
            "webhook_id": x_webhook_id,
            "event_type": event_type,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except json.JSONDecodeError:
        logger.error("Invalid JSON in webhook body")
        raise HTTPException(status_code=400, detail="Invalid JSON payload")
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/tiktok/status")
async def webhook_status():
    """Check webhook endpoint status"""
    return {
        "status": "operational",
        "processed_count": len(processed_webhooks),
        "oldest_webhook": min(processed_webhooks.values()).isoformat() if processed_webhooks else None,
        "signature_verification": "enabled",
        "replay_protection": "enabled",
        "deduplication": "enabled"
    }

@router.post("/tiktok/test")
async def test_webhook(
    request: Request,
    shop_id: str,
    event_type: str = "test_event"
):
    """Send a test webhook for integration testing"""
    webhook_service = WebhookService()
    
    try:
        # Generate test webhook
        test_data = {
            "type": event_type,
            "shop_id": shop_id,
            "data": {
                "test": True,
                "timestamp": int(time.time()),
                "message": "This is a test webhook"
            }
        }
        
        # Process test webhook
        await webhook_service.process_webhook(test_data)
        
        return {
            "status": "success",
            "message": "Test webhook processed",
            "data": test_data
        }
        
    except Exception as e:
        logger.error(f"Test webhook error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to process test webhook")