"""
Service Layer

Encapsulates business logic for the agent and connection management.
"""

import asyncio
import time
import uuid
import logging
from typing import Optional

from .agent import Agent, AgentStep
from .config import load_config
from .connection_manager import ConnectionManager
from .logging_config import get_logger, set_correlation_id

logger = get_logger("services")

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

    async def start_stream_chat(self, message: str, correlation_id: Optional[str] = None):
        """Start a streaming chat in the background."""
        asyncio.create_task(self._stream_agent_response(message, correlation_id))

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

    async def _stream_agent_response(self, message: str, correlation_id: Optional[str] = None):
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
            }, correlation_id=cid)
            return
        
        try:
            loop = asyncio.get_event_loop()
            
            self.agent.memory.add_user_message(message)
            self.agent.current_step = 0
            self.agent.is_running = True
            
            max_step_retries = 3
            step_retry_delay = 1.0
            
            while self.agent.is_running and self.agent.current_step < self.agent.config.max_iterations:
                step = None
                step_error = None
                retry_count = 0
                
                # Retry logic for agent.step() calls
                while retry_count < max_step_retries:
                    try:
                        step = await loop.run_in_executor(None, self.agent.step)
                        step_error = None
                        break  # Success
                        
                    except Exception as e:
                        step_error = e
                        retry_count += 1
                        
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
                            }, correlation_id=cid)
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
                    }, correlation_id=cid)
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
                    }, correlation_id=cid)
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
                    
                    await self.connection_manager.broadcast(step_response, correlation_id=cid)
                except Exception as e:
                    logger.error(f"[{cid}] Error broadcasting step: {e}")
                
                if step.phase == "respond":
                    self.agent.is_running = False
                    try:
                        await self.connection_manager.broadcast({
                            "type": "complete",
                            "step_number": step.step_number,
                            "phase": "complete",
                            "content": step.content,
                            "correlation_id": cid,
                        }, correlation_id=cid)
                        logger.info(f"[{cid}] Stream completed successfully")
                    except Exception as e:
                        logger.error(f"[{cid}] Error broadcasting completion: {e}")
                    break

        except KeyboardInterrupt:
            logger.info(f"[{cid}] Stream interrupted by user")
            await self.connection_manager.broadcast({
                "type": "error",
                "step_number": self.agent.current_step if self.agent else 0,
                "phase": "error",
                "content": "Processing interrupted",
                "correlation_id": cid,
            }, correlation_id=cid)
        except Exception as e:
            logger.exception(f"[{cid}] Unexpected error in stream: {e}")
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
            }, correlation_id=cid)
