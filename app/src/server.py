"""
FastAPI Server Module

Provides HTTP and WebSocket API for the SlowHands agent.
This bridges the Electron frontend to the Python backend.
"""

import asyncio
import json
import logging
import time
from typing import Optional, Dict, List
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
import uuid

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .config import load_config
from .agent import Agent, AgentStep
from .logging_config import setup_logging, get_logger
from .message_queue import MessageQueue

# Setup logging
setup_logging(level="INFO")
logger = get_logger("server")

# #region debug log
def _dbg_log(location: str, message: str, data: dict, hypothesis_id: str) -> None:
    try:
        payload = {
            "id": f"log_{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}",
            "timestamp": int(time.time() * 1000),
            "location": location,
            "message": message,
            "data": data,
            "sessionId": "debug-session",
            "runId": "run1",
            "hypothesisId": hypothesis_id,
        }
        with open("/home/dub/projects/slowhands/.cursor/debug.log", "a") as f:
            f.write(json.dumps(payload) + "\n")
    except Exception:
        pass
# #endregion

# Global agent instance
agent: Optional[Agent] = None


class ChatRequest(BaseModel):
    """Request body for chat endpoint."""
    message: str


class ChatResponse(BaseModel):
    """Response from chat endpoint."""
    response: str
    steps: int
    success: bool
    error: Optional[str] = None


class AgentStepResponse(BaseModel):
    """WebSocket message for agent step updates."""
    type: str  # "step", "complete", "error"
    step_number: int
    phase: str
    content: str
    tool_name: Optional[str] = None
    tool_success: Optional[bool] = None
    correlation_id: Optional[str] = None


# ============================================
# WebSocket Message Schemas (Pydantic)
# ============================================

class WSMessageBase(BaseModel):
    """Base class for WebSocket messages."""
    type: str
    correlation_id: Optional[str] = None


class WSChatMessage(WSMessageBase):
    """Chat message from client to server."""
    type: str = "chat"
    content: str


class WSStopMessage(WSMessageBase):
    """Stop message from client to server."""
    type: str = "stop"


class WSPingMessage(WSMessageBase):
    """Ping message from client to server."""
    type: str = "ping"


class WSOpenFileMessage(WSMessageBase):
    """Request to open a file from client to server."""
    type: str = "open_file"
    path: str


class WSFileContentMessage(WSMessageBase):
    """File content response from server to client."""
    type: str = "file_content"
    path: str
    content: str
    size: int = 0
    lines: int = 0


class WSPongMessage(WSMessageBase):
    """Pong response from server to client."""
    type: str = "pong"


class WSStepMessage(WSMessageBase):
    """Step update from server to client."""
    type: str = "step"
    step_number: int
    phase: str  # "think", "act", "respond"
    content: str
    tool_name: Optional[str] = None
    tool_success: Optional[bool] = None


class WSCompleteMessage(WSMessageBase):
    """Completion message from server to client."""
    type: str = "complete"
    step_number: int
    phase: str = "complete"
    content: str


class WSErrorMessage(WSMessageBase):
    """Error message from server to client."""
    type: str = "error"
    step_number: int = 0
    phase: str = "error"
    content: str


class WSStoppedMessage(WSMessageBase):
    """Stopped message from server to client."""
    type: str = "stopped"
    step_number: int
    phase: str = "stopped"
    content: str


def parse_ws_message(data: dict) -> Optional[WSMessageBase]:
    """Parse incoming WebSocket message into typed schema."""
    msg_type = data.get("type")
    try:
        if msg_type == "chat":
            return WSChatMessage(**data)
        elif msg_type == "stop":
            return WSStopMessage(**data)
        elif msg_type == "ping":
            return WSPingMessage(**data)
        elif msg_type == "open_file":
            return WSOpenFileMessage(**data)
        else:
            return None
    except Exception as e:
        logger.warning(f"Failed to parse WebSocket message: {e}")
        return None


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


# WebSocket connection manager
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


# Initialize connection manager with message queue
config_for_manager = load_config()
manager = ConnectionManager(message_queue_max_size=config_for_manager.message_queue_max_size)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize agent on startup."""
    global agent
    
    logger.info("Starting SlowHands server...")
    
    try:
        config = load_config()
        # Disable slow mode for API usage
        config.slow_mode = False
        config.verbose = False
        
        agent = Agent(config)
        logger.info(f"Agent initialized with {config.provider} provider")
    except Exception as e:
        logger.error(f"Failed to initialize agent: {e}")
        agent = None
    
    yield
    
    logger.info("Shutting down SlowHands server...")


# Create FastAPI app
app = FastAPI(
    title="SlowHands API",
    description="API for the SlowHands AI coding agent",
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS for Electron app
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for Electron
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """Health check endpoint with connection and queue stats."""
    return {
        "status": "healthy",
        "agent_ready": agent is not None,
        "agent_status": agent.get_status() if agent else None,
        "connections": {
            "count": len(manager.connections),
            "details": manager.get_connection_stats(),
        },
        "message_queue": manager.message_queue.get_stats(),
    }


@app.get("/api/files")
async def list_workspace_files():
    """List files in the workspace directory."""
    config = load_config()
    workspace_path = Path(config.workspace_path)
    
    if not workspace_path.exists():
        workspace_path.mkdir(parents=True, exist_ok=True)
        return {"files": [], "workspace": str(workspace_path)}
    
    def get_file_tree(path: Path, base_path: Path) -> List[dict]:
        """Recursively build file tree."""
        items = []
        try:
            for item in sorted(path.iterdir()):
                rel_path = str(item.relative_to(base_path))
                if item.is_dir():
                    items.append({
                        "name": item.name,
                        "path": rel_path,
                        "type": "directory",
                        "children": get_file_tree(item, base_path)
                    })
                else:
                    items.append({
                        "name": item.name,
                        "path": rel_path,
                        "type": "file",
                        "size": item.stat().st_size
                    })
        except PermissionError:
            pass
        return items
    
    files = get_file_tree(workspace_path, workspace_path)
    return {"files": files, "workspace": str(workspace_path)}


@app.get("/api/files/{file_path:path}")
async def read_file(file_path: str):
    """Read a file from the workspace."""
    config = load_config()
    workspace_path = Path(config.workspace_path)
    full_path = workspace_path / file_path
    
    # Security check - ensure path is within workspace
    try:
        full_path.resolve().relative_to(workspace_path.resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied: path outside workspace")
    
    if not full_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {file_path}")
    
    if not full_path.is_file():
        raise HTTPException(status_code=400, detail=f"Not a file: {file_path}")
    
    try:
        content = full_path.read_text()
        return {
            "path": file_path,
            "content": content,
            "size": len(content),
            "lines": content.count('\n') + 1
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading file: {e}")


@app.post("/agent/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Send a message to the agent and get a response.
    
    This is a synchronous endpoint - it waits for the full response.
    For streaming, use the WebSocket endpoint.
    """
    if not agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    logger.info(f"Chat request: {request.message[:50]}...")
    
    try:
        # Run agent in thread pool to not block
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, agent.run, request.message)
        
        return ChatResponse(
            response=response,
            steps=agent.current_step,
            success=True
        )
    except Exception as e:
        logger.error(f"Chat error: {e}")
        return ChatResponse(
            response="",
            steps=0,
            success=False,
            error=str(e)
        )


@app.post("/agent/stream")
async def stream_chat(request: ChatRequest):
    """
    Send a message and stream the response via WebSocket.
    
    This endpoint triggers the stream, responses come via WebSocket.
    """
    if not agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    logger.info(f"Stream request: {request.message[:50]}...")
    
    # Start streaming in background
    asyncio.create_task(_stream_agent_response(request.message))
    
    return {"status": "streaming", "message": "Check WebSocket for updates"}


def _is_transient_error(error: Exception) -> bool:
    """
    Determine if an error is transient and should be retried.
    
    Args:
        error: Exception to check
        
    Returns:
        True if error is transient, False otherwise
    """
    transient_error_types = (
        ConnectionError,
        TimeoutError,
        asyncio.TimeoutError,
        OSError,
    )
    
    error_str = str(error).lower()
    transient_keywords = [
        "timeout",
        "connection",
        "network",
        "temporary",
        "unavailable",
        "retry",
    ]
    
    if isinstance(error, transient_error_types):
        return True
    
    if any(keyword in error_str for keyword in transient_keywords):
        return True
    
    return False


async def _stream_agent_response(message: str, correlation_id: Optional[str] = None):
    """Stream agent response to all WebSocket clients with improved error handling."""
    cid = correlation_id or f"req_{uuid.uuid4().hex[:8]}"
    logger.info(f"[{cid}] Starting stream for message: {message[:50]}...")
    
    # #region debug log
    _dbg_log(
        "server.py:_stream_agent_response",
        "stream_start",
        {"message_len": len(message), "message_preview": message[:80], "correlation_id": cid},
        "A",
    )
    # #endregion
    if not agent:
        await manager.broadcast({
            "type": "error",
            "step_number": 0,
            "phase": "error",
            "content": "Agent not initialized. Please restart the server.",
            "correlation_id": cid,
        }, correlation_id=cid)
        return
    
    try:
        loop = asyncio.get_event_loop()
        
        # We need to yield steps as they come, so we'll use a different approach
        agent.memory.add_user_message(message)
        agent.current_step = 0
        agent.is_running = True
        
        max_step_retries = 3
        step_retry_delay = 1.0
        
        while agent.is_running and agent.current_step < agent.config.max_iterations:
            step = None
            step_error = None
            retry_count = 0
            
            # Retry logic for agent.step() calls
            while retry_count < max_step_retries:
                try:
                    step = await loop.run_in_executor(None, agent.step)
                    step_error = None
                    break  # Success, exit retry loop
                    
                except Exception as e:
                    step_error = e
                    retry_count += 1
                    
                    if _is_transient_error(e) and retry_count < max_step_retries:
                        wait_time = step_retry_delay * retry_count
                        logger.warning(
                            f"Transient error in agent step (attempt {retry_count}/{max_step_retries}): {e}. "
                            f"Retrying in {wait_time}s..."
                        )
                        await manager.broadcast({
                            "type": "step",
                            "step_number": agent.current_step,
                            "phase": "think",
                            "content": f"Encountered temporary issue, retrying... (attempt {retry_count}/{max_step_retries})",
                            "correlation_id": cid,
                        }, correlation_id=cid)
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        # Permanent error or max retries reached
                        logger.error(f"Error in agent step after {retry_count} attempts: {e}")
                        break
            
            # Handle step execution result
            if step_error:
                # Failed after retries
                error_message = (
                    f"I encountered an error while processing your request: {step_error}. "
                    f"I tried {retry_count} times but was unable to continue. "
                    f"Please check the server logs for more details."
                )
                await manager.broadcast({
                    "type": "error",
                    "step_number": agent.current_step,
                    "phase": "error",
                    "content": error_message,
                    "correlation_id": cid,
                }, correlation_id=cid)
                # #region debug log
                _dbg_log(
                    "server.py:_stream_agent_response",
                    "step_error_after_retries",
                    {"step_number": agent.current_step, "error": str(step_error)},
                    "B",
                )
                # #endregion
                agent.is_running = False
                break
            
            if not step:
                # Should not happen, but handle gracefully
                logger.error(f"[{cid}] agent.step() returned None")
                await manager.broadcast({
                    "type": "error",
                    "step_number": agent.current_step,
                    "phase": "error",
                    "content": "Internal error: agent step returned no result",
                    "correlation_id": cid,
                }, correlation_id=cid)
                break
            
            # Broadcast step to clients
            try:
                step_response = {
                    "type": "step",
                    "step_number": step.step_number,
                    "phase": step.phase,
                    "content": step.content,
                    "tool_name": step.tool_call.name if step.tool_call else None,
                    "tool_success": step.tool_result.success if step.tool_result else None,
                    "correlation_id": cid,
                }
                
                # Include file operation data for editor updates
                if step.tool_call and step.tool_call.name == "file_ops":
                    args = step.tool_call.arguments or {}
                    action = args.get("action")
                    file_path = args.get("path")
                    
                    if action == "write" and file_path:
                        step_response["file_op"] = {
                            "action": "write",
                            "path": file_path,
                            "content": args.get("content", ""),
                        }
                        logger.info(f"[{cid}] File write: {file_path}")
                    elif action == "read" and file_path and step.tool_result:
                        step_response["file_op"] = {
                            "action": "read", 
                            "path": file_path,
                            "content": step.tool_result.output or "",
                        }
                # #region debug log
                _dbg_log(
                    "server.py:_stream_agent_response",
                    "step_broadcast",
                    {
                        "step_number": step.step_number,
                        "phase": step.phase,
                        "content_len": len(step.content or ""),
                        "correlation_id": cid,
                    },
                    "A",
                )
                # #endregion
                await manager.broadcast(step_response, correlation_id=cid)
            except Exception as e:
                logger.error(f"[{cid}] Error broadcasting step: {e}")
                # Continue processing even if broadcast fails
            
            if step.phase == "respond":
                agent.is_running = False
                # Send completion message
                try:
                    await manager.broadcast({
                        "type": "complete",
                        "step_number": step.step_number,
                        "phase": "complete",
                        "content": step.content,
                        "correlation_id": cid,
                    }, correlation_id=cid)
                    # #region debug log
                    _dbg_log(
                        "server.py:_stream_agent_response",
                        "complete_broadcast",
                        {
                            "step_number": step.step_number,
                            "content_len": len(step.content or ""),
                            "correlation_id": cid,
                        },
                        "A",
                    )
                    # #endregion
                    logger.info(f"[{cid}] Stream completed successfully")
                except Exception as e:
                    logger.error(f"[{cid}] Error broadcasting completion: {e}")
                break
                
    except KeyboardInterrupt:
        logger.info(f"[{cid}] Stream interrupted by user")
        await manager.broadcast({
            "type": "error",
            "step_number": agent.current_step if agent else 0,
            "phase": "error",
            "content": "Processing interrupted",
            "correlation_id": cid,
        }, correlation_id=cid)
    except Exception as e:
        logger.exception(f"[{cid}] Unexpected error in stream: {e}")
        error_message = (
            f"An unexpected error occurred: {e}. "
            f"The agent was processing: '{message[:100]}...' "
            f"Please check the server logs for details."
        )
        await manager.broadcast({
            "type": "error",
            "step_number": agent.current_step if agent else 0,
            "phase": "error",
            "content": error_message,
            "correlation_id": cid,
        }, correlation_id=cid)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time updates.
    
    Clients connect here to receive streaming agent updates.
    Messages can also be sent via WebSocket for a full duplex experience.
    """
    await manager.connect(websocket)
    
    try:
        while True:
            # Receive messages from client
            data = await websocket.receive_text()
            
            try:
                raw_message = json.loads(data)
                # #region debug log
                _dbg_log(
                    "server.py:websocket_endpoint",
                    "ws_message_received",
                    {"type": raw_message.get("type"), "has_content": "content" in raw_message},
                    "C",
                )
                # #endregion
                
                # Parse and validate message using Pydantic schemas
                parsed_message = parse_ws_message(raw_message)
                
                if isinstance(parsed_message, WSChatMessage):
                    # Update activity
                    manager.update_activity(websocket)
                    # Generate correlation ID for this request
                    correlation_id = parsed_message.correlation_id or f"req_{uuid.uuid4().hex[:8]}"
                    logger.info(f"[{correlation_id}] Received chat request from connection")
                    # Start streaming response
                    asyncio.create_task(_stream_agent_response(parsed_message.content, correlation_id=correlation_id))
                    
                elif isinstance(parsed_message, WSStopMessage):
                    # Update activity
                    manager.update_activity(websocket)
                    # Stop the agent
                    stop_cid = parsed_message.correlation_id or f"stop_{uuid.uuid4().hex[:8]}"
                    if agent:
                        agent.is_running = False
                        agent._shutdown_requested = True
                        logger.info(f"[{stop_cid}] Agent stop requested via WebSocket")
                        await websocket.send_json(
                            WSStoppedMessage(
                                step_number=agent.current_step if agent else 0,
                                content="Agent stopped by user",
                                correlation_id=stop_cid,
                            ).model_dump()
                        )
                        
                elif isinstance(parsed_message, WSPingMessage):
                    manager.update_ping(websocket)
                    await websocket.send_json(WSPongMessage().model_dump())
                
                elif isinstance(parsed_message, WSOpenFileMessage):
                    # Handle file open request
                    manager.update_activity(websocket)
                    config = load_config()
                    workspace_path = Path(config.workspace_path)
                    file_path = workspace_path / parsed_message.path
                    
                    try:
                        # Security check
                        file_path.resolve().relative_to(workspace_path.resolve())
                        
                        if file_path.exists() and file_path.is_file():
                            content = file_path.read_text()
                            await websocket.send_json(
                                WSFileContentMessage(
                                    path=parsed_message.path,
                                    content=content,
                                    size=len(content),
                                    lines=content.count('\n') + 1,
                                ).model_dump()
                            )
                        else:
                            await websocket.send_json(
                                WSErrorMessage(content=f"File not found: {parsed_message.path}").model_dump()
                            )
                    except ValueError:
                        await websocket.send_json(
                            WSErrorMessage(content="Access denied: path outside workspace").model_dump()
                        )
                    except Exception as e:
                        await websocket.send_json(
                            WSErrorMessage(content=f"Error reading file: {e}").model_dump()
                        )
                    
                else:
                    # Unknown or unparseable message type
                    manager.update_activity(websocket)
                    await websocket.send_json(
                        WSErrorMessage(
                            content=f"Unknown message type: {raw_message.get('type')}"
                        ).model_dump()
                    )
                    
            except json.JSONDecodeError:
                await websocket.send_json(
                    WSErrorMessage(content="Invalid JSON").model_dump()
                )
                
    except WebSocketDisconnect:
        await manager.disconnect(websocket)


@app.post("/agent/reset")
async def reset_agent():
    """Reset the agent conversation history."""
    if not agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    agent.reset()
    return {"status": "reset", "message": "Agent conversation cleared"}


@app.post("/agent/stop")
async def stop_agent():
    """Stop the agent mid-execution."""
    if not agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    agent.is_running = False
    agent._shutdown_requested = True
    stop_cid = f"stop_{uuid.uuid4().hex[:8]}"
    logger.info(f"[{stop_cid}] Agent stop requested")
    
    # Broadcast stop to all clients
    await manager.broadcast({
        "type": "stopped",
        "step_number": agent.current_step,
        "phase": "stopped",
        "content": "Agent stopped by user",
        "correlation_id": stop_cid,
    }, correlation_id=stop_cid)
    
    return {"status": "stopped", "message": "Agent stopped", "correlation_id": stop_cid}


# For running directly
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8765)
