"""
Tools Module

Tools are the agent's "hands" - they let it interact with the world.
Each tool does one specific thing (read files, run code, etc.).

Available tools:
- FileOpsTool: Read, write, and list files
- CodeRunnerTool: Execute Python code
- GitTool: Git version control operations
- TerminalTool: Execute terminal commands
- WebSearchTool: Search the web for information
"""

from .base import BaseTool, ToolResult
from .file_ops import FileOpsTool
from .code_runner import CodeRunnerTool
from .git_tool import GitTool
from .terminal_tool import TerminalTool
from .web_search_tool import WebSearchTool

__all__ = [
    "BaseTool",
    "ToolResult",
    "FileOpsTool",
    "CodeRunnerTool",
    "GitTool",
    "TerminalTool",
    "WebSearchTool",
]
