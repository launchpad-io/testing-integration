# app/utils/validators.py
from typing import List
from app.core.config import settings
from urllib.parse import urlparse

# Whitelist of allowed redirect URIs
ALLOWED_REDIRECT_URIS = [
    "http://localhost:3000/callback",
    "https://launchpaid.ai/callback",
]

def is_valid_redirect_uri(uri: str) -> bool:
    """Validate if redirect URI is whitelisted"""
    if settings.DEBUG:
        parsed = urlparse(uri)
        if parsed.hostname in ['localhost', '127.0.0.1']:
            return True
    return uri in ALLOWED_REDIRECT_URIS

def validate_webhook_payload(data: dict) -> bool:
    """Validate webhook payload structure"""
    required_fields = ['type', 'shop_id', 'data']
    for field in required_fields:
        if field not in data:
            return False
    
    valid_event_types = [
        'order_status_change',
        'product_status_change',
        'authorization_revoked',
        'inventory_update',
        'refund_created',
        'shipment_update'
    ]
    
    if data['type'] not in valid_event_types:
        return False
    
    return True