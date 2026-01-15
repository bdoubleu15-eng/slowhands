"""
Connection Manager

Manages WebSocket connections and message queuing.
"""

import asyncio
import time
import uuid
import logging
from typing import Dict, Optional, List
from dataclasses import dataclass, field

from fastapi import WebSocket

from .message_queue import MessageQueue
from .config import load_config
from .logging_config import get_logger

logger = get_logger("connection_manager")

@dataclass
class ConnectionInfo:
    """Information about a WebSocket connection."""
    websocket: WebSocket
    connection_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    connected_at: float = field(default_factory=time.time)
    last_ping: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    last_ping_latency_ms: Optional[float] = None
    ping_sent_at: Optional[float] = None
    reconnect_count: int = 0


class ConnectionManager:
    """Manages WebSocket connections and message queuing."""
    
    def __init__(self, message_queue_max_size: int = 100, connection_timeout: float = 300.0):
        self.connections: Dict[WebSocket, ConnectionInfo] = {}
        self.message_queue = MessageQueue(max_size=message_queue_max_size)
        self.connection_timeout = connection_timeout  # Seconds before considering connection stale
        self._cleanup_task: Optional[asyncio.Task] = None
    
    @property
    def active_connections(self) -> list[WebSocket]:
        """Get list of active WebSocket connections."""
        return list(self.connections.keys())
    
    def _start_cleanup_task(self):
        """Start background task to clean up stale connections."""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_stale_connections())
    
    async def _cleanup_stale_connections(self):
        """Background task to periodically clean up stale connections."""
        while True:
            try:
                await asyncio.sleep(30)  # Check every 30 seconds
                await self.check_and_cleanup_stale_connections()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup task: {e}")
    
    async def check_and_cleanup_stale_connections(self):
        """Check for and remove stale connections."""
        now = time.time()
        stale_connections = []
        
        for websocket, info in self.connections.items():
            time_since_activity = now - info.last_activity
            if time_since_activity > self.connection_timeout:
                stale_connections.append(websocket)
        
        for websocket in stale_connections:
            logger.info(f"Removing stale connection (inactive for {now - self.connections[websocket].last_activity:.1f}s)")
            await self.disconnect(websocket)
        
        if stale_connections:
            logger.info(f"Cleaned up {len(stale_connections)} stale connection(s)")
    
    async def connect(self, websocket: WebSocket):
        """Accept a WebSocket connection and register it."""
        await websocket.accept()
        info = ConnectionInfo(websocket=websocket)
        self.connections[websocket] = info
        logger.info(f"WebSocket connected: {info.connection_id}. Total connections: {len(self.connections)}")
        
        # Start cleanup task if not already running
        self._start_cleanup_task()
        
        # Process any queued messages for this new connection
        await self._process_queued_messages(websocket)
    
    async def _process_queued_messages(self, websocket: WebSocket):
        """Process queued messages for a newly connected client."""
        if self.message_queue.is_empty():
            return
        
        async def send_to_websocket(message: dict):
            try:
                await websocket.send_json(message)
                # Update activity time
                if websocket in self.connections:
                    self.connections[websocket].last_activity = time.time()
            except Exception as e:
                logger.error(f"Error sending queued message: {e}")
                raise
        
        processed = await self.message_queue.process_all(send_to_websocket)
        if processed > 0:
            logger.info(f"Sent {processed} queued messages to new connection")
    
    async def disconnect(self, websocket: WebSocket):
        """Disconnect a WebSocket connection."""
        if websocket in self.connections:
            del self.connections[websocket]
        logger.info(f"WebSocket disconnected. Total connections: {len(self.connections)}")
    
    def update_activity(self, websocket: WebSocket):
        """Update last activity time for a connection."""
        if websocket in self.connections:
            self.connections[websocket].last_activity = time.time()
    
    def update_ping(self, websocket: WebSocket):
        """Update last ping time for a connection (called when pong received)."""
        if websocket in self.connections:
            info = self.connections[websocket]
            now = time.time()
            # Calculate latency if we have a ping_sent_at timestamp
            if info.ping_sent_at is not None:
                info.last_ping_latency_ms = (now - info.ping_sent_at) * 1000
            info.last_ping = now
            info.last_activity = now
            info.ping_sent_at = None  # Reset for next ping
    
    def record_ping_sent(self, websocket: WebSocket):
        """Record when a ping was sent (for latency calculation)."""
        if websocket in self.connections:
            self.connections[websocket].ping_sent_at = time.time()
    
    def get_connection_stats(self) -> list[dict]:
        """Get statistics for all connections."""
        now = time.time()
        stats = []
        for websocket, info in self.connections.items():
            stats.append({
                "connection_id": info.connection_id,
                "connected_at": info.connected_at,
                "uptime_seconds": round(now - info.connected_at, 1),
                "last_activity_seconds_ago": round(now - info.last_activity, 1),
                "last_ping_seconds_ago": round(now - info.last_ping, 1) if info.last_ping else None,
                "last_ping_latency_ms": round(info.last_ping_latency_ms, 2) if info.last_ping_latency_ms else None,
                "reconnect_count": info.reconnect_count,
            })
        return stats
    
    async def broadcast(self, message: dict, correlation_id: Optional[str] = None):
        """
        Send message to all connected clients.
        If no clients are connected, queue the message.
        
        Args:
            message: Message dict to broadcast
            correlation_id: Optional correlation ID for tracking
        """
        msg_type = message.get("type", "unknown")
        cid = correlation_id or message.get("correlation_id", "no-cid")
        
        if not self.connections:
            # No connections available, queue the message
            await self.message_queue.enqueue(message)
            logger.info(f"[{cid}] No active connections, queued {msg_type}. Queue size: {self.message_queue.size()}")
            return
        
        connection_count = len(self.connections)
        connection_ids = [info.connection_id for info in self.connections.values()]
        logger.info(f"[{cid}] Broadcasting {msg_type} to {connection_count} connection(s): {connection_ids}")
        
        failed_connections = []
        successful_sends = []
        
        for websocket, info in list(self.connections.items()):
            try:
                await websocket.send_json(message)
                # Update activity time on successful send
                info.last_activity = time.time()
                successful_sends.append(info.connection_id)
            except Exception as e:
                logger.error(f"[{cid}] Error broadcasting to connection {info.connection_id}: {e}")
                failed_connections.append(websocket)
        
        # Log broadcast results
        if successful_sends:
            logger.info(f"[{cid}] Broadcast {msg_type} succeeded: {successful_sends}")
        if failed_connections:
            logger.warning(f"[{cid}] Broadcast {msg_type} failed for {len(failed_connections)} connection(s)")
        
        # Remove failed connections
        for websocket in failed_connections:
            await self.disconnect(websocket)
        
        # If all connections failed, queue the message
        if not self.connections:
            await self.message_queue.enqueue(message)
            logger.info(f"[{cid}] All connections failed, queued {msg_type}. Queue size: {self.message_queue.size()}")
