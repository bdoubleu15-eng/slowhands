"""
Base Tool Module

Defines the interface that all tools must implement.
Think of this as a "contract" - any tool you create must
follow this pattern.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class ToolResult:
    """
    Result of a tool execution.

    Every tool returns one of these after running.
    It tells us:
    - Did it work? (success)
    - What happened? (output)
    - What went wrong? (error, if any)
    """
    success: bool
    output: str
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        """String representation for logging/display."""
        if self.success:
            return self.output
        return f"Error: {self.error}"

    @classmethod
    def ok(cls, output: str, **metadata) -> "ToolResult":
        """Create a successful result."""
        return cls(success=True, output=output, metadata=metadata)

    @classmethod
    def fail(cls, error: str, **metadata) -> "ToolResult":
        """Create a failed result."""
        return cls(success=False, output="", error=error, metadata=metadata)


class BaseTool(ABC):
    """
    Abstract base class for all tools.

    To create a new tool:
    1. Inherit from BaseTool
    2. Implement the abstract properties (name, description, parameters)
    3. Implement the execute() method

    Example:
        class MyTool(BaseTool):
            @property
            def name(self) -> str:
                return "my_tool"

            @property
            def description(self) -> str:
                return "Does something useful"

            @property
            def parameters(self) -> Dict[str, Any]:
                return {
                    "type": "object",
                    "properties": {
                        "input": {"type": "string"}
                    },
                    "required": ["input"]
                }

            def execute(self, input: str) -> ToolResult:
                return ToolResult.ok(f"Processed: {input}")
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Unique name for this tool.

        This is what the LLM uses to call the tool.
        Keep it short and descriptive (e.g., "read_file", "run_code").
        """
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """
        Description shown to the LLM.

        Explain what the tool does and when to use it.
        The LLM reads this to decide which tool to use.
        """
        pass

    @property
    @abstractmethod
    def parameters(self) -> Dict[str, Any]:
        """
        JSON Schema for tool parameters.

        Defines what arguments the tool accepts.
        Uses JSON Schema format (same as OpenAI function calling).

        Example:
            {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path to read"
                    }
                },
                "required": ["path"]
            }
        """
        pass

    @abstractmethod
    def execute(self, **kwargs) -> ToolResult:
        """
        Execute the tool with given arguments.

        This is where the actual work happens.
        Arguments come from the LLM's tool call.

        Args:
            **kwargs: Tool-specific arguments

        Returns:
            ToolResult with success status and output
        """
        pass

    def validate(self, kwargs: Dict[str, Any]) -> bool:
        """
        Validate arguments against the schema.

        Override this for custom validation logic.
        Default implementation just checks required fields.
        """
        required = self.parameters.get("required", [])
        return all(key in kwargs for key in required)

    def format_for_llm(self) -> Dict[str, Any]:
        """
        Format this tool for the OpenAI API.

        Returns the tool in the format expected by
        OpenAI's function calling feature.
        """
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters
            }
        }

    def __repr__(self) -> str:
        """String representation for debugging."""
        return f"Tool({self.name})"
