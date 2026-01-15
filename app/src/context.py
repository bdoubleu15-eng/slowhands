"""
Project Context Module

Shared context system for tracking project state between agents.
This enables the Teacher Agent to answer questions about:
- Current project files and structure
- Coder agent's conversation history
- Recent tool calls and file modifications
- Agent's reasoning process
"""

import os
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set
from datetime import datetime
import hashlib

from .memory import Memory


@dataclass
class FileState:
    """Tracks state of a single file."""
    path: str
    last_modified: datetime
    size: int
    content_hash: str  # For detecting changes
    content: Optional[str] = None  # Optional: store actual content

    @classmethod
    def from_path(cls, path: str, store_content: bool = False) -> "FileState":
        """Create FileState from file path."""
        stat = os.stat(path)
        content = None
        content_hash = ""

        if store_content and os.path.isfile(path):
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            content_hash = hashlib.md5(content.encode()).hexdigest()
        else:
            # Just hash metadata for speed
            metadata = f"{path}-{stat.st_mtime}-{stat.st_size}"
            content_hash = hashlib.md5(metadata.encode()).hexdigest()

        return cls(
            path=path,
            last_modified=datetime.fromtimestamp(stat.st_mtime),
            size=stat.st_size,
            content_hash=content_hash,
            content=content
        )


@dataclass
class ToolCallRecord:
    """Record of a tool call made by the coder agent."""
    timestamp: datetime
    tool_name: str
    arguments: Dict[str, Any]
    result: str
    success: bool

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "tool_name": self.tool_name,
            "arguments": self.arguments,
            "result": self.result[:500] + "..." if len(self.result) > 500 else self.result,
            "success": self.success
        }


class ProjectContext:
    """
    Shared context for tracking project state.

    This class acts as a central repository for project information
    that both the Coder Agent and Teacher Agent can access.
    """

    def __init__(self, project_root: str = "."):
        """
        Initialize project context.

        Args:
            project_root: Root directory of the project
        """
        self.project_root = Path(project_root).resolve()
        self.coder_memory: Optional[Memory] = None
        self.file_states: Dict[str, FileState] = {}
        self.tool_history: List[ToolCallRecord] = []
        self._ignored_patterns = {".git", "__pycache__", ".venv", "venv", "node_modules"}

        # Initialize with current file states
        self.scan_project()

    def set_coder_memory(self, memory: Memory) -> None:
        """Set reference to coder agent's memory."""
        self.coder_memory = memory

    def scan_project(self, max_files: int = 1000) -> None:
        """
        Scan project directory to build file tree.

        Args:
            max_files: Maximum number of files to scan (performance limit)
        """
        self.file_states.clear()
        files_scanned = 0

        for root, dirs, files in os.walk(self.project_root):
            # Skip ignored directories
            dirs[:] = [d for d in dirs if d not in self._ignored_patterns]

            for file in files:
                if files_scanned >= max_files:
                    break

                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, self.project_root)

                # Skip binary files and large files
                if self._should_skip_file(file_path):
                    continue

                try:
                    file_state = FileState.from_path(file_path, store_content=False)
                    self.file_states[rel_path] = file_state
                    files_scanned += 1
                except (IOError, OSError, UnicodeDecodeError):
                    # Skip files we can't read
                    continue

    def _should_skip_file(self, file_path: str) -> bool:
        """Determine if a file should be skipped during scanning."""
        # Skip large files (>1MB)
        try:
            if os.path.getsize(file_path) > 1024 * 1024:
                return True
        except OSError:
            return True

        # Skip binary files by extension
        binary_extensions = {'.pyc', '.so', '.dll', '.exe', '.jpg', '.png', '.pdf', '.zip'}
        if any(file_path.endswith(ext) for ext in binary_extensions):
            return True

        return False

    def record_tool_call(self, tool_name: str, arguments: Dict[str, Any],
                        result: str, success: bool = True) -> None:
        """
        Record a tool call made by the coder agent.

        Args:
            tool_name: Name of the tool used
            arguments: Arguments passed to the tool
            result: Output/result of the tool
            success: Whether the tool call succeeded
        """
        record = ToolCallRecord(
            timestamp=datetime.now(),
            tool_name=tool_name,
            arguments=arguments,
            result=result,
            success=success
        )
        self.tool_history.append(record)

        # Keep only recent history
        if len(self.tool_history) > 50:
            self.tool_history = self.tool_history[-50:]

    def get_recent_tools(self, limit: int = 10) -> List[ToolCallRecord]:
        """Get most recent tool calls."""
        return self.tool_history[-limit:] if self.tool_history else []

    def get_file_tree(self) -> Dict[str, Any]:
        """
        Get project file tree structure.

        Returns:
            Nested dictionary representing file tree
        """
        tree = {}

        for rel_path in sorted(self.file_states.keys()):
            parts = rel_path.split(os.sep)
            current = tree

            for i, part in enumerate(parts):
                if i == len(parts) - 1:
                    # File
                    file_state = self.file_states[rel_path]
                    current[part] = {
                        "type": "file",
                        "size": file_state.size,
                        "modified": file_state.last_modified.isoformat()
                    }
                else:
                    # Directory
                    if part not in current:
                        current[part] = {"type": "dir", "children": {}}
                    current = current[part]["children"]

        return tree

    def get_file_content(self, file_path: str) -> Optional[str]:
        """
        Get content of a file.

        Args:
            file_path: Relative path to file from project root

        Returns:
            File content or None if file doesn't exist or can't be read
        """
        abs_path = self.project_root / file_path

        if not abs_path.exists() or not abs_path.is_file():
            return None

        try:
            with open(abs_path, 'r', encoding='utf-8') as f:
                return f.read()
        except (IOError, UnicodeDecodeError):
            return None

    def get_conversation_summary(self) -> str:
        """
        Get summary of coder agent's conversation.

        Returns:
            Summary of recent conversation
        """
        if not self.coder_memory:
            return "No conversation history available."

        messages = self.coder_memory.get_history(limit=10)
        summary_parts = []

        for msg in messages:
            role = msg.role.upper()
            content_preview = msg.content[:100] + "..." if len(msg.content) > 100 else msg.content
            summary_parts.append(f"[{role}]: {content_preview}")

        return "\n".join(summary_parts)

    def get_context_summary(self) -> str:
        """
        Get comprehensive context summary for Teacher Agent.

        Returns:
            Multi-line summary of project state
        """
        # File tree summary
        file_count = len(self.file_states)
        python_files = [f for f in self.file_states.keys() if f.endswith('.py')]

        # Recent tools
        recent_tools = self.get_recent_tools(limit=5)
        tool_summary = "\n".join(
            f"- {tool.tool_name}: {tool.result[:80]}..."
            for tool in recent_tools[-3:]
        ) if recent_tools else "No recent tool calls"

        # Conversation summary
        conv_summary = self.get_conversation_summary()

        return f"""PROJECT CONTEXT SUMMARY:
Project Root: {self.project_root}
Total Files: {file_count}
Python Files: {len(python_files)}

RECENT TOOL CALLS:
{tool_summary}

RECENT CONVERSATION:
{conv_summary}

Available commands:
- !files: List project files
- !tree: Show file tree
- !content <file>: Show file content
- !tools: Show recent tool calls
- !conv: Show conversation history
- !help: Show this help"""

    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary for serialization."""
        return {
            "project_root": str(self.project_root),
            "file_count": len(self.file_states),
            "recent_tools": [tool.to_dict() for tool in self.tool_history[-10:]],
            "conversation_summary": self.get_conversation_summary()
        }


# Global context instance
_global_context: Optional[ProjectContext] = None

def get_global_context() -> ProjectContext:
    """Get or create global project context instance."""
    global _global_context
    if _global_context is None:
        _global_context = ProjectContext()
    return _global_context

def set_global_context(context: ProjectContext) -> None:
    """Set global project context instance."""
    global _global_context
    _global_context = context