"""
WebSocket endpoints for real-time features
"""
import json
import asyncio
from typing import Dict, Set, Optional, Any
from datetime import datetime
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
import structlog

from models.schemas import (
    WebSocketMessage,
    PriceUpdateMessage,
    AnomalyAlertMessage,
    PredictionCompleteMessage,
)
from dependencies import get_redis, verify_websocket_token

logger = structlog.get_logger()
router = APIRouter()


class ConnectionManager:
    """Manage WebSocket connections"""
    
    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        self.connection_metadata: Dict[WebSocket, Dict[str, Any]] = {}
    
    async def connect(self, websocket: WebSocket, user_id: str, subscription_type: str = "all"):
        """Connect a WebSocket client"""
        await websocket.accept()
        
        if subscription_type not in self.active_connections:
            self.active_connections[subscription_type] = set()
        
        self.active_connections[subscription_type].add(websocket)
        self.connection_metadata[websocket] = {
            "user_id": user_id,
            "subscription_type": subscription_type,
            "connected_at": datetime.utcnow(),
            "last_ping": datetime.utcnow(),
        }
        
        logger.info(
            "WebSocket connected",
            user_id=user_id,
            subscription_type=subscription_type,
            total_connections=sum(len(conns) for conns in self.active_connections.values())
        )
    
    def disconnect(self, websocket: WebSocket):
        """Disconnect a WebSocket client"""
        metadata = self.connection_metadata.get(websocket, {})
        user_id = metadata.get("user_id", "unknown")
        subscription_type = metadata.get("subscription_type", "all")
        
        if subscription_type in self.active_connections:
            self.active_connections[subscription_type].discard(websocket)
        
        self.connection_metadata.pop(websocket, None)
        
        logger.info(
            "WebSocket disconnected",
            user_id=user_id,
            subscription_type=subscription_type,
            total_connections=sum(len(conns) for conns in self.active_connections.values())
        )
    
    async def send_personal_message(self, message: str, websocket: WebSocket):
        """Send message to specific WebSocket"""
        try:
            await websocket.send_text(message)
        except Exception as e:
            logger.error(f"Error sending personal message: {e}")
            self.disconnect(websocket)
    
    async def broadcast_to_subscription(self, message: WebSocketMessage, subscription_type: str = "all"):
        """Broadcast message to all connections of a specific type"""
        if subscription_type not in self.active_connections:
            return
        
        connections = list(self.active_connections[subscription_type])
        if not connections:
            return
        
        message_str = message.json()
        disconnected_connections = []
        
        for connection in connections:
            try:
                await connection.send_text(message_str)
            except Exception as e:
                logger.error(f"Error broadcasting message: {e}")
                disconnected_connections.append(connection)
        
        # Clean up disconnected connections
        for connection in disconnected_connections:
            self.disconnect(connection)
    
    async def send_to_user(self, message: WebSocketMessage, user_id: str):
        """Send message to all connections of a specific user"""
        message_str = message.json()
        disconnected_connections = []
        
        for connections in self.active_connections.values():
            for connection in connections:
                metadata = self.connection_metadata.get(connection, {})
                if metadata.get("user_id") == user_id:
                    try:
                        await connection.send_text(message_str)
                    except Exception as e:
                        logger.error(f"Error sending message to user: {e}")
                        disconnected_connections.append(connection)
        
        # Clean up disconnected connections
        for connection in disconnected_connections:
            self.disconnect(connection)
    
    def get_connection_stats(self) -> Dict[str, Any]:
        """Get connection statistics"""
        stats = {
            "total_connections": sum(len(conns) for conns in self.active_connections.values()),
            "connections_by_type": {
                sub_type: len(conns) for sub_type, conns in self.active_connections.items()
            },
            "active_users": len(set(
                metadata.get("user_id") 
                for metadata in self.connection_metadata.values() 
                if metadata.get("user_id")
            ))
        }
        return stats


# Global connection manager
manager = ConnectionManager()


@router.websocket("/prices")
async def websocket_price_updates(
    websocket: WebSocket,
    token: str = Query(..., description="Authentication token"),
    materials: Optional[str] = Query(None, description="Comma-separated material IDs"),
    redis=Depends(get_redis),
):
    """
    WebSocket endpoint for real-time price updates
    
    Clients can subscribe to price updates for specific materials or all materials.
    """
    try:
        # Verify authentication token
        user = await verify_websocket_token(token)
        if not user:
            await websocket.close(code=1008, reason="Invalid authentication")
            return
        
        # Parse material filter
        material_filter = set(materials.split(",")) if materials else None
        
        await manager.connect(websocket, user.id, "price_updates")
        
        try:
            while True:
                # Wait for incoming messages (ping/pong, subscription changes, etc.)
                try:
                    data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                    message = json.loads(data)
                    
                    if message.get("type") == "ping":
                        await websocket.send_text(json.dumps({
                            "type": "pong",
                            "timestamp": datetime.utcnow().isoformat()
                        }))
                    
                    elif message.get("type") == "subscribe_materials":
                        # Update material filter
                        new_materials = message.get("materials", [])
                        material_filter = set(new_materials) if new_materials else None
                        
                        await websocket.send_text(json.dumps({
                            "type": "subscription_updated",
                            "materials": list(material_filter) if material_filter else None,
                            "timestamp": datetime.utcnow().isoformat()
                        }))
                    
                except asyncio.TimeoutError:
                    # Send ping to keep connection alive
                    await websocket.send_text(json.dumps({
                        "type": "ping",
                        "timestamp": datetime.utcnow().isoformat()
                    }))
                
        except WebSocketDisconnect:
            logger.info(f"Price updates WebSocket disconnected for user {user.id}")
        
    except Exception as e:
        logger.error(f"Error in price updates WebSocket: {e}", exc_info=True)
        try:
            await websocket.close(code=1011, reason="Internal server error")
        except:
            pass
    finally:
        manager.disconnect(websocket)


@router.websocket("/notifications")
async def websocket_notifications(
    websocket: WebSocket,
    token: str = Query(..., description="Authentication token"),
    types: Optional[str] = Query(None, description="Comma-separated notification types"),
):
    """
    WebSocket endpoint for real-time notifications
    
    Clients receive notifications about anomalies, predictions, and other events.
    """
    try:
        # Verify authentication token
        user = await verify_websocket_token(token)
        if not user:
            await websocket.close(code=1008, reason="Invalid authentication")
            return
        
        # Parse notification type filter
        type_filter = set(types.split(",")) if types else None
        
        await manager.connect(websocket, user.id, "notifications")
        
        try:
            while True:
                try:
                    data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                    message = json.loads(data)
                    
                    if message.get("type") == "ping":
                        await websocket.send_text(json.dumps({
                            "type": "pong",
                            "timestamp": datetime.utcnow().isoformat()
                        }))
                    
                    elif message.get("type") == "subscribe_types":
                        # Update notification type filter
                        new_types = message.get("types", [])
                        type_filter = set(new_types) if new_types else None
                        
                        await websocket.send_text(json.dumps({
                            "type": "subscription_updated",
                            "types": list(type_filter) if type_filter else None,
                            "timestamp": datetime.utcnow().isoformat()
                        }))
                
                except asyncio.TimeoutError:
                    # Send ping to keep connection alive
                    await websocket.send_text(json.dumps({
                        "type": "ping",
                        "timestamp": datetime.utcnow().isoformat()
                    }))
                
        except WebSocketDisconnect:
            logger.info(f"Notifications WebSocket disconnected for user {user.id}")
        
    except Exception as e:
        logger.error(f"Error in notifications WebSocket: {e}", exc_info=True)
        try:
            await websocket.close(code=1011, reason="Internal server error")
        except:
            pass
    finally:
        manager.disconnect(websocket)


@router.websocket("/predictions/{batch_id}")
async def websocket_prediction_status(
    websocket: WebSocket,
    batch_id: str,
    token: str = Query(..., description="Authentication token"),
    redis=Depends(get_redis),
):
    """
    WebSocket endpoint for real-time prediction status updates
    
    Clients can monitor the progress of batch predictions.
    """
    try:
        # Verify authentication token
        user = await verify_websocket_token(token)
        if not user:
            await websocket.close(code=1008, reason="Invalid authentication")
            return
        
        # Check if batch exists
        batch_data = await redis.get(f"batch:{batch_id}")
        if not batch_data:
            await websocket.close(code=1008, reason="Batch not found")
            return
        
        await manager.connect(websocket, user.id, f"prediction_status_{batch_id}")
        
        try:
            while True:
                # Check batch status periodically
                try:
                    batch_data = await redis.get(f"batch:{batch_id}")
                    if batch_data:
                        batch_status = json.loads(batch_data)
                        
                        await websocket.send_text(json.dumps({
                            "type": "status_update",
                            "batch_id": batch_id,
                            "status": batch_status.get("status"),
                            "completed_predictions": batch_status.get("completed_predictions", 0),
                            "total_predictions": batch_status.get("total_predictions", 0),
                            "failed_predictions": batch_status.get("failed_predictions", 0),
                            "timestamp": datetime.utcnow().isoformat()
                        }))
                        
                        # If batch is complete, close connection
                        if batch_status.get("status") in ["completed", "failed"]:
                            break
                    
                    await asyncio.sleep(2)  # Check every 2 seconds
                
                except asyncio.TimeoutError:
                    continue
        
        except WebSocketDisconnect:
            logger.info(f"Prediction status WebSocket disconnected for batch {batch_id}")
        
    except Exception as e:
        logger.error(f"Error in prediction status WebSocket: {e}", exc_info=True)
        try:
            await websocket.close(code=1011, reason="Internal server error")
        except:
            pass
    finally:
        manager.disconnect(websocket)


# Function to broadcast messages (called from other services)
async def broadcast_price_update(
    material_id: str,
    old_price: float,
    new_price: float,
    price_change_percent: float,
    source: str = "system"
):
    """Broadcast price update to connected clients"""
    message = PriceUpdateMessage(
        material_id=material_id,
        old_price=old_price,
        new_price=new_price,
        price_change_percent=price_change_percent,
        source=source,
        timestamp=datetime.utcnow(),
        data={}
    )
    
    await manager.broadcast_to_subscription(message, "price_updates")
    
    logger.info(
        "Price update broadcasted",
        material_id=material_id,
        price_change_percent=price_change_percent,
        connections=len(manager.active_connections.get("price_updates", set()))
    )


async def broadcast_anomaly_alert(
    material_id: str,
    anomaly_score: float,
    current_price: float,
    expected_price: float,
    severity: str = "medium"
):
    """Broadcast anomaly alert to connected clients"""
    message = AnomalyAlertMessage(
        material_id=material_id,
        anomaly_score=anomaly_score,
        current_price=current_price,
        expected_price=expected_price,
        severity=severity,
        timestamp=datetime.utcnow(),
        data={}
    )
    
    await manager.broadcast_to_subscription(message, "notifications")
    
    logger.info(
        "Anomaly alert broadcasted",
        material_id=material_id,
        anomaly_score=anomaly_score,
        severity=severity,
        connections=len(manager.active_connections.get("notifications", set()))
    )


async def broadcast_prediction_complete(
    batch_id: str,
    status: str,
    results_count: int,
    errors_count: int,
    user_id: str = None
):
    """Broadcast prediction completion to connected clients"""
    message = PredictionCompleteMessage(
        batch_id=batch_id,
        status=status,
        results_count=results_count,
        errors_count=errors_count,
        timestamp=datetime.utcnow(),
        data={}
    )
    
    if user_id:
        # Send to specific user
        await manager.send_to_user(message, user_id)
    else:
        # Broadcast to all notification subscribers
        await manager.broadcast_to_subscription(message, "notifications")
    
    logger.info(
        "Prediction completion broadcasted",
        batch_id=batch_id,
        status=status,
        user_id=user_id,
    )


@router.get("/stats")
async def get_websocket_stats(
    user=Depends(verify_websocket_token),
):
    """Get WebSocket connection statistics"""
    if not user or not user.is_staff:
        return {"error": "Unauthorized"}
    
    return manager.get_connection_stats()