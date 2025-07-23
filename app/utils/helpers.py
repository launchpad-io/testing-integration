# app/utils/helpers.py
from typing import Dict, Any
import json
from datetime import datetime

def parse_tiktok_timestamp(timestamp: int) -> datetime:
    """Convert TikTok timestamp (seconds) to datetime"""
    return datetime.fromtimestamp(timestamp)

def format_tiktok_timestamp(dt: datetime) -> int:
    """Convert datetime to TikTok timestamp (seconds)"""
    return int(dt.timestamp())

def extract_error_message(response: Dict[str, Any]) -> str:
    """Extract error message from TikTok API response"""
    if "message" in response:
        return response["message"]
    elif "error" in response:
        if isinstance(response["error"], dict):
            return response["error"].get("message", "Unknown error")
        return str(response["error"])
    return "Unknown error occurred"

# app/utils/signature.py
import hashlib
import hmac
import time
from urllib.parse import quote, urlencode
from typing import Dict, Any, Optional

class TikTokSignature:
    """Generate signatures for TikTok Shop API requests"""
    
    @staticmethod
    def generate_signature(
        app_secret: str,
        path: str,
        params: Dict[str, Any],
        body: Optional[str] = None
    ) -> str:
        """
        Generate signature for TikTok Shop API request
        """
        # Sort parameters by key
        sorted_params = sorted(params.items())
        
        # Build the base string
        base_string_parts = []
        
        # Add path
        base_string_parts.append(path)
        
        # Add sorted parameters
        for key, value in sorted_params:
            if value is not None:
                base_string_parts.append(f"{key}{value}")
        
        # Add body if present
        if body:
            base_string_parts.append(body)
        
        # Join all parts
        base_string = "".join(base_string_parts)
        
        # Generate HMAC-SHA256 signature
        signature = hmac.new(
            app_secret.encode('utf-8'),
            base_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return signature
    
    @staticmethod
    def prepare_request_params(
        app_key: str,
        app_secret: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        access_token: Optional[str] = None,
        shop_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Prepare all parameters including signature for API request
        """
        if params is None:
            params = {}
        
        # Add required parameters
        timestamp = str(int(time.time()))
        
        # Build all parameters
        all_params = {
            "app_key": app_key,
            "timestamp": timestamp,
            **params
        }
        
        # Add access token if provided
        if access_token:
            all_params["access_token"] = access_token
            
        # Add shop_id if provided
        if shop_id:
            all_params["shop_id"] = shop_id
        
        # Generate signature
        signature = TikTokSignature.generate_signature(
            app_secret=app_secret,
            path=path,
            params=all_params
        )
        
        # Add signature to parameters
        all_params["sign"] = signature
        
        return all_params

# app/utils/__init__.py
# This file can be empty