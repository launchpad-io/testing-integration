
# app/services/webhook_retry_worker.py
import asyncio
from datetime import datetime, timedelta
# Use async session
from app.models.database import AsyncSessionLocal
from app.models.tiktok_models import WebhookEvent
from app.services.webhook_service import WebhookService
import logging

logger = logging.getLogger(__name__)

class WebhookRetryWorker:
    """Background worker to retry failed webhooks"""
    
    def __init__(self):
        self.check_interval = 300  # Check every 5 minutes
        self.max_age_hours = 24  # Don't retry webhooks older than 24 hours
    
    async def start(self):
        """Start the webhook retry worker"""
        logger.info("Webhook retry worker started")
        
        while True:
            try:
                await self.process_failed_webhooks()
                await asyncio.sleep(self.check_interval)
            except asyncio.CancelledError:
                logger.info("Webhook retry worker stopped")
                break
            except Exception as e:
                logger.error(f"Error in webhook retry worker: {e}")
                await asyncio.sleep(60)
    
    async def process_failed_webhooks(self):
        """Process failed webhooks that need retry (fully async)."""

        async with AsyncSessionLocal() as db:
            try:
                from sqlalchemy import select

                cutoff_time = datetime.utcnow() - timedelta(hours=self.max_age_hours)

                result = await db.execute(
                    select(WebhookEvent).where(
                        WebhookEvent.status == "retrying",
                        WebhookEvent.received_at > cutoff_time,
                        WebhookEvent.retry_count < WebhookService.max_retry_attempts  # type: ignore
                    ).limit(10)
                )
                failed_events = result.scalars().all()

                retry_count = 0
                webhook_service = WebhookService()

                for event in failed_events:
                    try:
                        logger.info(f"Retrying webhook {event.webhook_id}")
                        await webhook_service.retry_failed_event(event.id)
                        retry_count += 1
                        await asyncio.sleep(1)
                    except Exception as e:
                        logger.error(f"Failed to retry webhook {event.id}: {e}")

                if retry_count:
                    logger.info(f"Retried {retry_count} failed webhooks")

                await db.commit()
            except Exception as e:
                logger.error(f"Error during webhook retry cycle: {e}")