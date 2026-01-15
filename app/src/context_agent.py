"""
Context-Aware Agent

Extends the base Agent to record tool calls and state
to the shared ProjectContext for the Teacher Agent to access.
"""

from typing import Optional
from .agent import Agent
from .config import Config
from .context import get_global_context, ProjectContext


class ContextAwareAgent(Agent):
    """
    Agent that records its actions to shared project context.

    This extends the base Agent to:
    1. Record all tool calls to ProjectContext
    2. Share its memory with the context
    3. Update file states when files are modified
    """

    def __init__(self, config: Optional[Config] = None, context: Optional[ProjectContext] = None):
        """
        Initialize context-aware agent.

        Args:
            config: Configuration object
            context: Project context (uses global context if None)
        """
        super().__init__(config)
        self.context = context or get_global_context()

        # Share agent's memory with context
        self.context.set_coder_memory(self.memory)

        # Update context with current project state
        self.context.scan_project()

    def _handle_tool_calls(self, response):
        """
        Override to record tool calls to context.

        Calls parent implementation, then records the tool call
        and updates project context if files were modified.
        """
        # Call parent implementation
        step = super()._handle_tool_calls(response)

        # Record tool call to context
        if step.tool_call and step.tool_result:
            self.context.record_tool_call(
                tool_name=step.tool_call.name,
                arguments=step.tool_call.arguments,
                result=step.tool_result.output,
                success=step.tool_result.success
            )

            # If file operation, update context
            if step.tool_call.name == "file_ops":
                self._handle_file_operation(step.tool_call.arguments, step.tool_result)

        return step

    def _handle_file_operation(self, arguments: dict, result):
        """
        Handle file operations to update context.

        Args:
            arguments: Tool call arguments
            result: Tool result
        """
        action = arguments.get("action")

        if action == "write":
            # File was written - update context
            file_path = arguments.get("path")
            if file_path and result.success:
                # Rescan project to pick up changes
                self.context.scan_project(max_files=100)

        elif action == "read":
            # File was read - could cache content
            pass

    def reset(self) -> None:
        """Reset agent and context tracking."""
        super().reset()
        # Clear context tool history but keep file states
        self.context.tool_history.clear()

    def get_context_info(self) -> dict:
        """Get information about current context state."""
        return {
            "files_tracked": len(self.context.file_states),
            "recent_tools": len(self.context.tool_history),
            "project_root": str(self.context.project_root)
        }