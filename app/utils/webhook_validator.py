# app/utils/webhook_validator.py
from typing import Dict

def validate_webhook_payload(data: Dict) -> bool:
    """Validate webhook payload structure"""
    # Check for required fields
    required_fields = ['type', 'shop_id', 'data']
    
    for field in required_fields:
        if field not in data:
            return False
    
    # Validate event type
    valid_event_types = [
        'order_status_change',
        'product_status_change',
        'authorization_revoked',
        'inventory_update',
        'refund_created',
        'shipment_update',
        'test_event'
    ]
    
    if data.get('type') not in valid_event_types:
        return False
    
    # Basic validation passed
    return True