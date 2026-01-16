"""
WebSocket Message Types

Pydantic models for WebSocket communication.
"""

from typing import Optional
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)

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


class WSResumeSessionMessage(WSMessageBase):
    """Request to resume a session from client to server."""
    type: str = "resume_session"
    session_id: str
    last_correlation_id: Optional[str] = None


class WSSessionStateMessage(WSMessageBase):
    """Session state response from server to client."""
    type: str = "session_state"
    session_id: str
    is_new: bool = False
    agent_running: bool = False
    last_correlation_id: Optional[str] = None
    pending_messages: int = 0



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
        elif msg_type == "resume_session":
            return WSResumeSessionMessage(**data)
        elif msg_type == "transcribe":
            return WSTranscribeMessage(**data)
        else:
            return None
    except Exception as e:
        logger.warning(f"Failed to parse WebSocket message: {e}")
        return None
