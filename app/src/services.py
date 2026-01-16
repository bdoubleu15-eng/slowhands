"""
Service Layer

Encapsulates business logic for the agent and connection management.
"""

import asyncio
import json
import time
import uuid
import logging
from pathlib import Path
from typing import Optional, Any

from .agent import Agent, AgentStep
from .config import load_config, Config
from .connection_manager import ConnectionManager
from .logging_config import get_logger, set_correlation_id

logger = get_logger("services")

# Default state file location
DEFAULT_STATE_FILE = Path.home() / ".slowhands" / "agent_state.json"

class AgentService:
    """
    Service for managing the AI Agent lifecycle and execution.
    Handles communication with the ConnectionManager for streaming updates.
    """

    def __init__(self, connection_manager: ConnectionManager):
        self.connection_manager = connection_manager
        self.agent: Optional[Agent] = None
        
    def initialize_agent(self) -> bool:
        """Initialize the agent with configuration."""
        try:
            config = load_config()
            # Disable slow mode for API usage
            config.slow_mode = False
            config.verbose = False
            
            self.agent = Agent(config)
            logger.info(f"Agent initialized with {config.provider} provider")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize agent: {e}")
            self.agent = None
            return False

    def get_status(self) -> Optional[dict]:
        """Get the current status of the agent."""
        if not self.agent:
            return None
        return self.agent.get_status()

    def reset_agent(self):
        """Reset the agent's memory."""
        if self.agent:
            self.agent.reset()

    async def save_state(self, state_file: Optional[Path] = None) -> bool:
        """
        Save agent state to disk for recovery on restart.
        
        Args:
            state_file: Optional path to save state to (defaults to ~/.slowhands/agent_state.json)
            
        Returns:
            True if state was saved successfully, False otherwise
        """
        state_path = state_file or DEFAULT_STATE_FILE
        
        try:
            # Ensure directory exists
            state_path.parent.mkdir(parents=True, exist_ok=True)
            
            state: dict[str, Any] = {
                "saved_at": time.time(),
                "version": "1.0",
            }
            
            # Save agent state if available
            if self.agent:
                state["agent"] = {
                    "current_step": self.agent.current_step,
                    "is_running": self.agent.is_running,
                    "status": self.agent.get_status(),
                }
                
                # Save memory/conversation history if available
                if hasattr(self.agent, 'memory') and self.agent.memory:
                    try:
                        # Save recent messages from memory
                        messages = []
                        if hasattr(self.agent.memory, 'messages'):
                            for msg in self.agent.memory.messages[-20:]:  # Last 20 messages
                                messages.append({
                                    "role": getattr(msg, 'role', 'unknown'),
                                    "content": getattr(msg, 'content', str(msg))[:1000],  # Truncate long content
                                })
                        state["memory"] = {"messages": messages}
                    except Exception as e:
                        logger.warning(f"Could not save memory state: {e}")
            
            # Save session information from connection manager
            if self.connection_manager:
                sessions = []
                for session_id, session in self.connection_manager.sessions.items():
                    sessions.append({
                        "session_id": session.session_id,
                        "last_correlation_id": session.last_correlation_id,
                        "agent_running": session.agent_running,
                        "pending_count": len(session.pending_messages),
                    })
                state["sessions"] = sessions
            
            # Write state to file
            with open(state_path, 'w') as f:
                json.dump(state, f, indent=2)
            
            logger.info(f"Agent state saved to {state_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save agent state: {e}")
            return False
    
    async def load_state(self, state_file: Optional[Path] = None) -> Optional[dict]:
        """
        Load saved agent state from disk.
        
        Args:
            state_file: Optional path to load state from
            
        Returns:
            State dict if loaded successfully, None otherwise
        """
        state_path = state_file or DEFAULT_STATE_FILE
        
        try:
            if not state_path.exists():
                logger.debug(f"No saved state found at {state_path}")
                return None
            
            with open(state_path, 'r') as f:
                state = json.load(f)
            
            logger.info(f"Loaded agent state from {state_path} (saved at {state.get('saved_at', 'unknown')})")
            return state
            
        except Exception as e:
            logger.error(f"Failed to load agent state: {e}")
            return None

    async def stop_agent(self, correlation_id: Optional[str] = None):
        """Stop the agent execution."""
        if not self.agent:
            return
            
        self.agent.is_running = False
        self.agent._shutdown_requested = True
        
        cid = correlation_id or f"stop_{uuid.uuid4().hex[:8]}"
        logger.info(f"[{cid}] Agent stop requested")
        
        # Broadcast stop to all clients
        await self.connection_manager.broadcast({
            "type": "stopped",
            "step_number": self.agent.current_step,
            "phase": "stopped",
            "content": "Agent stopped by user",
            "correlation_id": cid,
        }, correlation_id=cid)
        
        return cid

    def run_chat(self, message: str) -> str:
        """Run a synchronous chat request."""
        if not self.agent:
            raise RuntimeError("Agent not initialized")
        
        return self.agent.run(message)

    async def start_stream_chat(self, message: str, correlation_id: Optional[str] = None, 
                                session_id: Optional[str] = None):
        """Start a streaming chat in the background."""
        asyncio.create_task(self._stream_agent_response(message, correlation_id, session_id))

    def _is_transient_error(self, error: Exception) -> bool:
        """Determine if an error is transient and should be retried."""
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

    def _is_permanent_error(self, error: Exception) -> bool:
        """Determine if an error is permanent and should NOT be retried."""
        permanent_keywords = [
            "invalid",
            "not found",
            "permission denied",
            "syntax error",
            "authentication",
            "authorization",
            "forbidden",
            "malformed",
        ]
        error_str = str(error).lower()
        return any(kw in error_str for kw in permanent_keywords)

    async def _run_step_with_timeout(self, loop, timeout: float = 60.0) -> Optional[AgentStep]:
        """
        Run agent.step() with a timeout wrapper.
        
        Args:
            loop: Event loop for executor
            timeout: Maximum time to wait for step completion
            
        Returns:
            AgentStep from the agent, or error step on timeout
        """
        try:
            return await asyncio.wait_for(
                loop.run_in_executor(None, self.agent.step),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            logger.error(f"Agent step timed out after {timeout}s")
            # Signal the agent to stop
            if self.agent:
                self.agent._shutdown_requested = True
                self.agent.is_running = False
            return AgentStep(
                step_number=self.agent.current_step if self.agent else 0,
                phase="error",
                content=f"Agent step timed out after {timeout}s. The operation took too long to complete."
            )

    async def _stream_agent_response(self, message: str, correlation_id: Optional[str] = None,
                                      session_id: Optional[str] = None):
        """Stream agent response to all WebSocket clients."""
        cid = correlation_id or f"req_{uuid.uuid4().hex[:8]}"
        set_correlation_id(cid)
        
        logger.info(f"Starting stream for message: {message[:50]}...")
        
        if not self.agent:
            await self.connection_manager.broadcast({
                "type": "error",
                "step_number": 0,
                "phase": "error",
                "content": "Agent not initialized. Please restart the server.",
                "correlation_id": cid,
            }, correlation_id=cid, session_id=session_id)
            return
        
        try:
            loop = asyncio.get_event_loop()
            
            self.agent.memory.add_user_message(message)
            self.agent.current_step = 0
            self.agent.is_running = True
            
            max_step_retries = 3
            step_retry_delay = 1.0
            
            # Get step timeout from config (default 60s)
            step_timeout = getattr(self.agent.config, 'agent_step_timeout', 60.0)
            
            while self.agent.is_running and self.agent.current_step < self.agent.config.max_iterations:
                step = None
                step_error = None
                retry_count = 0
                
                # Retry logic for agent.step() calls
                while retry_count < max_step_retries:
                    try:
                        # Use timeout wrapper instead of direct executor call
                        step = await self._run_step_with_timeout(loop, timeout=step_timeout)
                        
                        # Check if step indicates timeout error
                        if step and step.phase == "error" and "timed out" in step.content:
                            step_error = asyncio.TimeoutError(step.content)
                            retry_count += 1
                            if retry_count < max_step_retries:
                                wait_time = step_retry_delay * retry_count
                                logger.warning(f"Step timed out, retrying in {wait_time}s...")
                                await self.connection_manager.broadcast({
                                    "type": "step",
                                    "step_number": self.agent.current_step,
                                    "phase": "think",
                                    "content": f"Step timed out, retrying... (attempt {retry_count}/{max_step_retries})",
                                    "correlation_id": cid,
                                }, correlation_id=cid, session_id=session_id)
                                await asyncio.sleep(wait_time)
                                # Reset agent state for retry
                                self.agent.is_running = True
                                self.agent._shutdown_requested = False
                                continue
                            break
                        
                        step_error = None
                        break  # Success
                        
                    except Exception as e:
                        step_error = e
                        retry_count += 1
                        
                        # Don't retry permanent errors
                        if self._is_permanent_error(e):
                            logger.error(f"Permanent error in agent step: {e}")
                            break
                        
                        if self._is_transient_error(e) and retry_count < max_step_retries:
                            wait_time = step_retry_delay * retry_count
                            logger.warning(
                                f"Transient error in agent step (attempt {retry_count}/{max_step_retries}): {e}. "
                                f"Retrying in {wait_time}s..."
                            )
                            await self.connection_manager.broadcast({
                                "type": "step",
                                "step_number": self.agent.current_step,
                                "phase": "think",
                                "content": f"Encountered temporary issue, retrying... (attempt {retry_count}/{max_step_retries})",
                                "correlation_id": cid,
                            }, correlation_id=cid, session_id=session_id)
                            await asyncio.sleep(wait_time)
                            continue
                        else:
                            logger.error(f"Error in agent step after {retry_count} attempts: {e}")
                            break
                
                if step_error:
                    error_message = (
                        f"I encountered an error while processing your request: {step_error}. "
                        f"I tried {retry_count} times but was unable to continue. "
                        f"Please check the server logs for more details."
                    )
                    await self.connection_manager.broadcast({
                        "type": "error",
                        "step_number": self.agent.current_step,
                        "phase": "error",
                        "content": error_message,
                        "correlation_id": cid,
                    }, correlation_id=cid, session_id=session_id)
                    self.agent.is_running = False
                    break
                
                if not step:
                    logger.error(f"[{cid}] agent.step() returned None")
                    await self.connection_manager.broadcast({
                        "type": "error",
                        "step_number": self.agent.current_step,
                        "phase": "error",
                        "content": "Internal error: agent step returned no result",
                        "correlation_id": cid,
                    }, correlation_id=cid, session_id=session_id)
                    break
                
                # Broadcast step
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
                    
                    await self.connection_manager.broadcast(step_response, correlation_id=cid, session_id=session_id)
                except Exception as e:
                    logger.error(f"[{cid}] Error broadcasting step: {e}")
                
                if step.phase == "respond":
                    self.agent.is_running = False
                    # Update session state
                    if session_id:
                        self.connection_manager.update_session_state(session_id, agent_running=False)
                    try:
                        await self.connection_manager.broadcast({
                            "type": "complete",
                            "step_number": step.step_number,
                            "phase": "complete",
                            "content": step.content,
                            "correlation_id": cid,
                        }, correlation_id=cid, session_id=session_id)
                        logger.info(f"[{cid}] Stream completed successfully")
                    except Exception as e:
                        logger.error(f"[{cid}] Error broadcasting completion: {e}")
                    break

        except KeyboardInterrupt:
            logger.info(f"[{cid}] Stream interrupted by user")
            if session_id:
                self.connection_manager.update_session_state(session_id, agent_running=False)
            await self.connection_manager.broadcast({
                "type": "error",
                "step_number": self.agent.current_step if self.agent else 0,
                "phase": "error",
                "content": "Processing interrupted",
                "correlation_id": cid,
            }, correlation_id=cid, session_id=session_id)
        except Exception as e:
            logger.exception(f"[{cid}] Unexpected error in stream: {e}")
            if session_id:
                self.connection_manager.update_session_state(session_id, agent_running=False)
            error_message = (
                f"An unexpected error occurred: {e}. "
                f"Please check the server logs for details."
            )
            await self.connection_manager.broadcast({
                "type": "error",
                "step_number": self.agent.current_step if self.agent else 0,
                "phase": "error",
                "content": error_message,
                "correlation_id": cid,
            }, correlation_id=cid, session_id=session_id)
