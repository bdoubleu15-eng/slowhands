"""
Tools Module

Tools are the agent's "hands" - they let it interact with the world.
Each tool does one specific thing (read files, run code, etc.).

Available tools:
- FileOpsTool: Read, write, and list files
- CodeRunnerTool: Execute Python code
"""

from .base import BaseTool, ToolResult
from .file_ops import FileOpsTool
from .code_runner import CodeRunnerTool

__all__ = [
    "BaseTool",
    "ToolResult",
    "FileOpsTool",
    "CodeRunnerTool",
]
