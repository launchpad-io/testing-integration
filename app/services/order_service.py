# app/services/order_service.py - Simplified version without SyncOperation
from sqlalchemy.orm import Session
from app.services.tiktok_client import TikTokShopClient
from app.models.tiktok_models import TikTokShop, TikTokOrder
from app.models.schemas import OrderListResponse, OrderBase
from typing import Dict, Any, List
import uuid

class OrderService:
    def __init__(self, db: Session):
        self.db = db
    
    def _get_shop_token(self, shop_id: str) -> str:
        """Get access token for shop"""
        shop = self.db.query(TikTokShop).filter(
            TikTokShop.shop_id == shop_id
        ).first()
        
        if not shop:
            raise ValueError("Shop not found")
        
        return shop.access_token
    
    async def search_orders(self, shop_id: str, **kwargs) -> OrderListResponse:
        """Search orders from TikTok Shop"""
        access_token = self._get_shop_token(shop_id)
        
        async with TikTokShopClient() as client:
            response = await client.get_order_list(
                access_token=access_token,
                shop_id=shop_id,
                **kwargs
            )
            
            data = response.get("data", {})
            orders = []
            
            for order_data in data.get("order_list", []):
                # Save or update order in database
                order = self.db.query(TikTokOrder).filter(
                    TikTokOrder.order_id == order_data["order_id"]
                ).first()
                
                if not order:
                    order = TikTokOrder(
                        id=str(uuid.uuid4()),
                        shop_id=shop_id,
                        order_id=order_data["order_id"]
                    )
                    self.db.add(order)
                
                # Update order data
                order.order_status = order_data["order_status"]
                order.payment_status = order_data.get("payment_status")
                order.fulfillment_type = order_data.get("fulfillment_type")
                order.buyer_info = order_data.get("buyer_info", {})
                order.recipient_address = order_data.get("recipient_address", {})
                order.line_items = order_data.get("line_items", [])
                order.payment_info = order_data.get("payment_info", {})
                order.shipping_info = order_data.get("shipping_info", {})
                order.create_time = order_data.get("create_time")
                order.update_time = order_data.get("update_time")
                
                orders.append(OrderBase(**order_data))
            
            self.db.commit()
            
            return OrderListResponse(
                total=data.get("total_count", 0),
                orders=orders,
                has_more=data.get("has_more", False)
            )
    
    async def get_order_detail(self, shop_id: str, order_id: str) -> OrderBase:
        """Get order details from TikTok Shop"""
        access_token = self._get_shop_token(shop_id)
        
        async with TikTokShopClient() as client:
            response = await client.get_order_detail(
                access_token=access_token,
                shop_id=shop_id,
                order_ids=[order_id]
            )
            
            data = response.get("data", {})
            order_list = data.get("order_list", [])
            
            if not order_list:
                return None
            
            order_data = order_list[0]
            
            # Update order in database
            order = self.db.query(TikTokOrder).filter(
                TikTokOrder.order_id == order_id
            ).first()
            
            if order:
                order.order_status = order_data["order_status"]
                order.payment_status = order_data.get("payment_status")
                order.fulfillment_type = order_data.get("fulfillment_type")
                order.buyer_info = order_data.get("buyer_info", {})
                order.recipient_address = order_data.get("recipient_address", {})
                order.line_items = order_data.get("line_items", [])
                order.payment_info = order_data.get("payment_info", {})
                order.shipping_info = order_data.get("shipping_info", {})
                order.update_time = order_data.get("update_time")
                self.db.commit()
            
            return OrderBase(**order_data)
    
    async def sync_recent_orders(self, shop_id: str, days: int = 7) -> int:
        """Sync recent orders from TikTok Shop"""
        from datetime import datetime, timedelta
        
        # Calculate time range
        end_time = int(datetime.now().timestamp())
        start_time = int((datetime.now() - timedelta(days=days)).timestamp())
        
        total_synced = 0
        page_number = 1
        has_more = True
        
        while has_more:
            result = await self.search_orders(
                shop_id=shop_id,
                page_size=100,
                page_number=page_number,
                create_time_from=start_time,
                create_time_to=end_time
            )
            
            total_synced += len(result.orders)
            has_more = result.has_more
            page_number += 1
        
        return total_synced