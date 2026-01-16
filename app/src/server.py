"""
FastAPI Server Module

Provides HTTP and WebSocket API for the SlowHands agent.
This bridges the Electron frontend to the Python backend.
"""

import asyncio
import json
import signal
import uuid
import time
from typing import Optional, List
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .config import load_config
from .logging_config import setup_logging, get_logger, set_correlation_id
from .connection_manager import ConnectionManager
from .services import AgentService
from .ws_types import (
    parse_ws_message,
    WSChatMessage,
    WSStopMessage,
    WSPingMessage,
    WSOpenFileMessage,
    WSPongMessage,
    WSFileContentMessage,
    WSErrorMessage,
    WSStoppedMessage,
    WSResumeSessionMessage,
    WSSessionStateMessage,
)

# Setup logging
setup_logging(level="INFO", json_format=True)
logger = get_logger("server")

# Global shutdown state
_shutdown_event: Optional[asyncio.Event] = None
_shutdown_timeout: float = 30.0  # Max time to wait for graceful shutdown


async def _graceful_shutdown(app: FastAPI) -> None:
    """
    Perform graceful shutdown sequence:
    1. Signal agent to stop
    2. Wait for in-flight operations
    3. Save state
    4. Close WebSocket connections
    """
    logger.info("Initiating graceful shutdown sequence...")
    
    service: AgentService = getattr(app.state, 'agent_service', None)
    manager: ConnectionManager = getattr(app.state, 'connection_manager', None)
    
    # Step 1: Stop the agent if running
    if service and service.agent and service.agent.is_running:
        logger.info("Stopping running agent...")
        await service.stop_agent(correlation_id="shutdown")
        
        # Wait briefly for agent to stop
        for _ in range(10):  # Max 1 second
            if not service.agent.is_running:
                break
            await asyncio.sleep(0.1)
    
    # Step 2: Save agent state
    if service:
        try:
            await service.save_state()
            logger.info("Agent state saved successfully")
        except Exception as e:
            logger.error(f"Failed to save agent state: {e}")
    
    # Step 3: Notify clients and close connections
    if manager:
        # Broadcast shutdown notification to all clients
        try:
            await manager.broadcast({
                "type": "server_shutdown",
                "content": "Server is shutting down gracefully",
                "correlation_id": "shutdown",
            }, correlation_id="shutdown")
        except Exception as e:
            logger.warning(f"Error broadcasting shutdown notification: {e}")
        
        # Close all WebSocket connections
        for websocket in list(manager.connections.keys()):
            try:
                await websocket.close(code=1001, reason="Server shutting down")
            except Exception as e:
                logger.debug(f"Error closing WebSocket: {e}")
            await manager.disconnect(websocket)
        
        # Cancel cleanup task if running
        if manager._cleanup_task and not manager._cleanup_task.done():
            manager._cleanup_task.cancel()
            try:
                await manager._cleanup_task
            except asyncio.CancelledError:
                pass
    
    logger.info("Graceful shutdown complete")


def _setup_signal_handlers(app: FastAPI, loop: asyncio.AbstractEventLoop) -> None:
    """Set up signal handlers for graceful shutdown."""
    global _shutdown_event
    _shutdown_event = asyncio.Event()
    
    def signal_handler(sig: signal.Signals) -> None:
        logger.info(f"Received signal {sig.name}, initiating shutdown...")
        _shutdown_event.set()
    
    # Register signal handlers (Unix only for SIGTERM)
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, lambda s=sig: signal_handler(s))
            logger.debug(f"Registered handler for {sig.name}")
        except NotImplementedError:
            # Windows doesn't support add_signal_handler for all signals
            signal.signal(sig, lambda s, f, sig=sig: signal_handler(sig))
            logger.debug(f"Registered fallback handler for {sig.name}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize services on startup, handle graceful shutdown."""
    global _shutdown_event
    logger.info("Starting SlowHands server...")
    
    # Initialize Connection Manager
    config = load_config()
    app.state.connection_manager = ConnectionManager(
        message_queue_max_size=config.message_queue_max_size
    )
    
    # Initialize Agent Service
    app.state.agent_service = AgentService(app.state.connection_manager)
    success = app.state.agent_service.initialize_agent()
    
    if not success:
        logger.error("Agent service failed to initialize")
    
    # Set up signal handlers
    try:
        loop = asyncio.get_running_loop()
        _setup_signal_handlers(app, loop)
    except Exception as e:
        logger.warning(f"Could not set up signal handlers: {e}")
    
    logger.info("SlowHands server started successfully")
    
    try:
        yield
    finally:
        # Graceful shutdown
        logger.info("Shutting down SlowHands server...")
        await _graceful_shutdown(app)


# Create FastAPI app
app = FastAPI(
    title="SlowHands API",
    description="API for the SlowHands AI coding agent",
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS for Electron app with configurable origins
# Default: localhost ports for development, can be configured via ALLOWED_CORS_ORIGINS
_config = load_config()
_cors_origins = getattr(_config, 'allowed_cors_origins', [
    "http://localhost:*",
    "http://127.0.0.1:*",
    "https://localhost:*",
    "https://127.0.0.1:*",
])
# For Electron file:// and app:// protocols, we need regex patterns
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_origin_regex=r"^(file://|app://|electron://).*$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    """Middleware to handle correlation IDs."""
    correlation_id = request.headers.get("X-Correlation-ID", f"req_{uuid.uuid4().hex[:8]}")
    set_correlation_id(correlation_id)
    response = await call_next(request)
    response.headers["X-Correlation-ID"] = correlation_id
    return response


# ============================================
# HTTP Models
# ============================================

class ChatRequest(BaseModel):
    """Request body for chat endpoint."""
    message: str


class ChatResponse(BaseModel):
    """Response from chat endpoint."""
    response: str
    steps: int
    success: bool
    error: Optional[str] = None


# ============================================
# Endpoints
# ============================================

@app.get("/health")
async def health_check():
    """Health check endpoint with connection, session, and queue stats."""
    manager: ConnectionManager = app.state.connection_manager
    service: AgentService = app.state.agent_service
    
    return {
        "status": "healthy",
        "agent_ready": service.agent is not None,
        "agent_status": service.get_status(),
        "connections": {
            "count": len(manager.connections),
            "details": manager.get_connection_stats(),
        },
        "sessions": manager.get_session_stats(),
        "message_queue": manager.message_queue.get_stats(),
    }


class OpenWorkspaceRequest(BaseModel):
    """Request body for opening a workspace."""
    folder_path: str


@app.post("/api/workspace/open")
async def open_workspace(request: OpenWorkspaceRequest):
    """Set the workspace to a new folder path and return file tree."""
    folder_path = Path(request.folder_path)
    
    # Validate path exists and is a directory
    if not folder_path.exists():
        raise HTTPException(status_code=404, detail=f"Path not found: {request.folder_path}")
    
    if not folder_path.is_dir():
        raise HTTPException(status_code=400, detail=f"Path is not a directory: {request.folder_path}")
    
    # Update workspace path in app state
    app.state.workspace_path = str(folder_path.resolve())
    logger.info(f"Workspace opened: {app.state.workspace_path}")
    
    # Build and return file tree
    def get_file_tree(path: Path, base_path: Path) -> List[dict]:
        """Recursively build file tree."""
        items = []
        try:
            for item in sorted(path.iterdir()):
                # Skip hidden files and common ignore patterns
                if item.name.startswith('.'):
                    continue
                if item.name in ('node_modules', '__pycache__', 'venv', '.git'):
                    continue
                    
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
    
    files = get_file_tree(folder_path, folder_path)
    return {"files": files, "workspace": str(folder_path)}


@app.get("/api/workspace")
async def get_workspace():
    """Get the current workspace path."""
    workspace_path = getattr(app.state, 'workspace_path', None)
    if not workspace_path:
        config = load_config()
        workspace_path = config.workspace_path
    return {"workspace": workspace_path}


@app.get("/api/files")
async def list_workspace_files():
    """List files in the workspace directory."""
    # Use dynamic workspace path if set, otherwise fall back to config
    workspace_path_str = getattr(app.state, 'workspace_path', None)
    if workspace_path_str:
        workspace_path = Path(workspace_path_str)
    else:
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
    # Use dynamic workspace path if set, otherwise fall back to config
    workspace_path_str = getattr(app.state, 'workspace_path', None)
    if workspace_path_str:
        workspace_path = Path(workspace_path_str)
    else:
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
    """
    service: AgentService = app.state.agent_service
    if not service.agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    logger.info(f"Chat request: {request.message[:50]}...")
    
    try:
        # Run agent in thread pool
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, service.run_chat, request.message)
        
        return ChatResponse(
            response=response,
            steps=service.agent.current_step,
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
    """
    service: AgentService = app.state.agent_service
    if not service.agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    logger.info(f"Stream request: {request.message[:50]}...")
    
    # Start streaming in background
    await service.start_stream_chat(request.message)
    
    return {"status": "streaming", "message": "Check WebSocket for updates"}


@app.post("/agent/reset")
async def reset_agent():
    """Reset the agent conversation history."""
    service: AgentService = app.state.agent_service
    if not service.agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    service.reset_agent()
    return {"status": "reset", "message": "Agent conversation cleared"}


@app.post("/agent/stop")
async def stop_agent():
    """Stop the agent mid-execution."""
    service: AgentService = app.state.agent_service
    if not service.agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    cid = await service.stop_agent()
    
    return {"status": "stopped", "message": "Agent stopped", "correlation_id": cid}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time updates.
    Supports session resumption for reconnecting clients.
    """
    manager: ConnectionManager = app.state.connection_manager
    service: AgentService = app.state.agent_service
    
    await manager.connect(websocket)
    
    # Track session for this connection
    current_session_id: Optional[str] = None
    
    try:
        while True:
            # Receive messages from client
            data = await websocket.receive_text()
            
            try:
                raw_message = json.loads(data)
                
                # Parse and validate message
                parsed_message = parse_ws_message(raw_message)
                
                if isinstance(parsed_message, WSResumeSessionMessage):
                    # Handle session resume request
                    manager.update_activity(websocket)
                    session, is_new = manager.get_or_create_session(parsed_message.session_id)
                    current_session_id = session.session_id
                    manager.link_connection_to_session(websocket, session.session_id)
                    
                    # Send session state
                    await websocket.send_json(
                        WSSessionStateMessage(
                            session_id=session.session_id,
                            is_new=is_new,
                            agent_running=session.agent_running,
                            last_correlation_id=session.last_correlation_id,
                            pending_messages=len(session.pending_messages),
                        ).model_dump()
                    )
                    
                    # If resuming and there are pending messages, replay them
                    if not is_new and parsed_message.last_correlation_id:
                        pending = manager.get_pending_messages(
                            session.session_id, 
                            since_correlation_id=parsed_message.last_correlation_id
                        )
                        for msg in pending:
                            await websocket.send_json(msg)
                        if pending:
                            logger.info(f"Replayed {len(pending)} pending messages for session {session.session_id}")
                
                elif isinstance(parsed_message, WSChatMessage):
                    manager.update_activity(websocket)
                    correlation_id = parsed_message.correlation_id or f"req_{uuid.uuid4().hex[:8]}"
                    logger.info(f"[{correlation_id}] Received chat request from connection")
                    
                    # Update session state
                    if current_session_id:
                        manager.update_session_state(current_session_id, agent_running=True, last_correlation_id=correlation_id)
                    
                    await service.start_stream_chat(parsed_message.content, correlation_id=correlation_id, session_id=current_session_id)
                    
                elif isinstance(parsed_message, WSStopMessage):
                    manager.update_activity(websocket)
                    stop_cid = parsed_message.correlation_id or f"stop_{uuid.uuid4().hex[:8]}"
                    
                    # Update session state
                    if current_session_id:
                        manager.update_session_state(current_session_id, agent_running=False)
                    
                    await service.stop_agent(correlation_id=stop_cid)
                        
                elif isinstance(parsed_message, WSPingMessage):
                    manager.update_ping(websocket)
                    await websocket.send_json(WSPongMessage().model_dump())
                
                elif isinstance(parsed_message, WSOpenFileMessage):
                    manager.update_activity(websocket)
                    # Use dynamic workspace path if set
                    workspace_path_str = getattr(app.state, 'workspace_path', None)
                    if workspace_path_str:
                        workspace_path = Path(workspace_path_str)
                    else:
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
        # Update session state on disconnect
        if current_session_id:
            manager.update_session_state(current_session_id, agent_running=False)
        await manager.disconnect(websocket)

# For running directly
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8765)
