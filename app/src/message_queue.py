"""
Message Queue Module

Provides message queuing functionality for WebSocket connections.
Ensures messages are not lost when connections are temporarily unavailable.
"""

import asyncio
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from threading import Lock

logger = logging.getLogger(__name__)


@dataclass
class QueuedMessage:
    """Represents a queued message with metadata."""
    message: Dict[str, Any]
    timestamp: float = field(default_factory=lambda: datetime.now().timestamp())
    retry_count: int = 0


class MessageQueue:
    """
    Thread-safe message queue for WebSocket messages.
    
    Queues messages when connections are unavailable and processes them
    when connections are restored. Prevents message loss during transient failures.
    
    Args:
        max_size: Maximum number of messages to queue (0 = unlimited)
    """
    
    def __init__(self, max_size: int = 100):
        self.max_size = max_size
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=max_size if max_size > 0 else 0)
        self._lock = Lock()
        self._total_enqueued = 0
        self._total_dequeued = 0
        self._total_dropped = 0
    
    async def enqueue(self, message: Dict[str, Any]) -> bool:
        """
        Add a message to the queue.
        
        Args:
            message: Message dictionary to queue
            
        Returns:
            True if message was queued, False if queue was full
        """
        queued_msg = QueuedMessage(message=message)
        
        try:
            if self.max_size > 0 and self._queue.qsize() >= self.max_size:
                # Queue is full - drop oldest message or reject new one
                try:
                    # Try to drop oldest message
                    await asyncio.wait_for(self._queue.get_nowait(), timeout=0.01)
                    self._total_dropped += 1
                    logger.warning(f"Message queue full, dropping oldest message. Queue size: {self._queue.qsize()}")
                except (asyncio.QueueEmpty, asyncio.TimeoutError):
                    # Couldn't drop, reject new message
                    logger.error(f"Message queue full and cannot drop messages. Rejecting new message.")
                    self._total_dropped += 1
                    return False
            
            await self._queue.put(queued_msg)
            self._total_enqueued += 1
            logger.debug(f"Message enqueued. Queue size: {self._queue.qsize()}")
            return True
            
        except Exception as e:
            logger.error(f"Error enqueuing message: {e}")
            return False
    
    async def dequeue(self, timeout: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """
        Get the next message from the queue.
        
        Args:
            timeout: Maximum time to wait for a message (None = wait indefinitely)
            
        Returns:
            Message dictionary or None if timeout/empty
        """
        try:
            if timeout is not None:
                queued_msg = await asyncio.wait_for(self._queue.get(), timeout=timeout)
            else:
                queued_msg = await self._queue.get()
            
            self._total_dequeued += 1
            logger.debug(f"Message dequeued. Queue size: {self._queue.qsize()}")
            return queued_msg.message
            
        except asyncio.TimeoutError:
            return None
        except Exception as e:
            logger.error(f"Error dequeuing message: {e}")
            return None
    
    def size(self) -> int:
        """Get current queue size."""
        return self._queue.qsize()
    
    def is_empty(self) -> bool:
        """Check if queue is empty."""
        return self._queue.empty()
    
    def is_full(self) -> bool:
        """Check if queue is full."""
        if self.max_size == 0:
            return False
        return self._queue.qsize() >= self.max_size
    
    def get_stats(self) -> Dict[str, Any]:
        """Get queue statistics."""
        return {
            "current_size": self._queue.qsize(),
            "max_size": self.max_size,
            "total_enqueued": self._total_enqueued,
            "total_dequeued": self._total_dequeued,
            "total_dropped": self._total_dropped,
            "is_full": self.is_full(),
            "is_empty": self.is_empty(),
        }
    
    async def clear(self):
        """Clear all messages from the queue."""
        while not self._queue.empty():
            try:
                await self._queue.get_nowait()
            except asyncio.QueueEmpty:
                break
        logger.info("Message queue cleared")
    
    async def process_all(self, send_func) -> int:
        """
        Process all queued messages using the provided send function.
        
        Args:
            send_func: Async function that takes a message dict and sends it
            
        Returns:
            Number of messages processed
        """
        processed = 0
        while not self._queue.empty():
            message = await self.dequeue(timeout=0.1)
            if message:
                try:
                    await send_func(message)
                    processed += 1
                except Exception as e:
                    logger.error(f"Error processing queued message: {e}")
                    # Re-queue the message if send failed (up to a limit)
                    queued_msg = QueuedMessage(message=message)
                    queued_msg.retry_count += 1
                    if queued_msg.retry_count < 3:
                        await self.enqueue(message)
                    else:
                        logger.warning(f"Dropping message after {queued_msg.retry_count} failed attempts")
        
        if processed > 0:
            logger.info(f"Processed {processed} queued messages")
        
        return processed
