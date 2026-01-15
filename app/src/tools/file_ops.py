"""
File Operations Tool

Allows the agent to read, write, and list files.
This is one of the most important tools - it lets the
agent see and modify code.
"""

import os
from pathlib import Path
from typing import Dict, Any, List

from .base import BaseTool, ToolResult


class FileOpsTool(BaseTool):
    """
    Tool for file system operations.

    Supports:
    - read: Read file contents
    - write: Write content to a file
    - list: List files in a directory
    - exists: Check if a file/directory exists

    Safety: By default, only allows operations within the
    workspace directory to prevent accidental damage.
    """

    def __init__(self, workspace_path: str = None, allowed_paths: List[str] = None):
        """
        Initialize the file operations tool.

        Args:
            workspace_path: Base directory for all file operations.
                           All paths are relative to this directory.
            allowed_paths: List of additional paths where operations are allowed.
        """
        self.workspace_path = Path(workspace_path) if workspace_path else Path.cwd()
        # Ensure workspace exists
        self.workspace_path.mkdir(parents=True, exist_ok=True)
        # Allowed paths include workspace and any additional paths
        self.allowed_paths = [str(self.workspace_path)] + (allowed_paths or [])

    @property
    def name(self) -> str:
        return "file_ops"

    @property
    def description(self) -> str:
        return """Perform file system operations.
Actions:
- read: Read the contents of a file
- write: Write content to a file (creates or overwrites)
- list: List files and directories at a path
- exists: Check if a path exists

Use this to view code, create files, or explore the project structure."""

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["read", "write", "list", "exists"],
                    "description": "The file operation to perform"
                },
                "path": {
                    "type": "string",
                    "description": "File or directory path (relative to working directory)"
                },
                "content": {
                    "type": "string",
                    "description": "Content to write (required for 'write' action)"
                }
            },
            "required": ["action", "path"]
        }

    def execute(self, action: str, path: str, content: str = None) -> ToolResult:
        """
        Execute a file operation.

        Args:
            action: One of "read", "write", "list", "exists"
            path: File or directory path
            content: Content to write (for write action)

        Returns:
            ToolResult with the operation result
        """
        # Resolve and validate the path
        try:
            resolved_path = self._resolve_path(path)
        except ValueError as e:
            return ToolResult.fail(str(e))

        # Dispatch to the appropriate method
        if action == "read":
            return self._read_file(resolved_path)
        elif action == "write":
            if content is None:
                return ToolResult.fail("'content' is required for write action")
            return self._write_file(resolved_path, content)
        elif action == "list":
            return self._list_directory(resolved_path)
        elif action == "exists":
            return self._check_exists(resolved_path)
        else:
            return ToolResult.fail(f"Unknown action: {action}")

    def _resolve_path(self, path: str) -> Path:
        """
        Resolve and validate a path.

        Relative paths are resolved relative to workspace_path.
        Ensures the path is within allowed directories.
        """
        path_obj = Path(path)
        
        # If path is relative, make it relative to workspace
        if not path_obj.is_absolute():
            resolved = (self.workspace_path / path).resolve()
        else:
            resolved = path_obj.resolve()

        # Check if it's within allowed paths
        for allowed in self.allowed_paths:
            allowed_resolved = Path(allowed).resolve()
            try:
                resolved.relative_to(allowed_resolved)
                return resolved
            except ValueError:
                continue

        raise ValueError(f"Path '{path}' is outside allowed directories (workspace: {self.workspace_path})")

    def _read_file(self, path: Path) -> ToolResult:
        """Read a file's contents."""
        try:
            if not path.exists():
                return ToolResult.fail(f"File not found: {path}")

            if not path.is_file():
                return ToolResult.fail(f"Not a file: {path}")

            content = path.read_text()
            return ToolResult.ok(
                content,
                path=str(path),
                size=len(content),
                lines=content.count('\n') + 1
            )
        except PermissionError:
            return ToolResult.fail(f"Permission denied: {path}")
        except Exception as e:
            return ToolResult.fail(f"Error reading file: {e}")

    def _write_file(self, path: Path, content: str) -> ToolResult:
        """Write content to a file."""
        try:
            # Create parent directories if needed
            path.parent.mkdir(parents=True, exist_ok=True)

            # Write the file
            path.write_text(content)

            return ToolResult.ok(
                f"Successfully wrote {len(content)} bytes to {path}",
                path=str(path),
                size=len(content)
            )
        except PermissionError:
            return ToolResult.fail(f"Permission denied: {path}")
        except Exception as e:
            return ToolResult.fail(f"Error writing file: {e}")

    def _list_directory(self, path: Path) -> ToolResult:
        """List contents of a directory."""
        try:
            if not path.exists():
                return ToolResult.fail(f"Directory not found: {path}")

            if not path.is_dir():
                return ToolResult.fail(f"Not a directory: {path}")

            # List contents
            items = []
            for item in sorted(path.iterdir()):
                prefix = "📁 " if item.is_dir() else "📄 "
                items.append(f"{prefix}{item.name}")

            if not items:
                return ToolResult.ok("(empty directory)", path=str(path))

            return ToolResult.ok(
                "\n".join(items),
                path=str(path),
                count=len(items)
            )
        except PermissionError:
            return ToolResult.fail(f"Permission denied: {path}")
        except Exception as e:
            return ToolResult.fail(f"Error listing directory: {e}")

    def _check_exists(self, path: Path) -> ToolResult:
        """Check if a path exists."""
        exists = path.exists()
        path_type = "directory" if path.is_dir() else "file" if path.is_file() else "unknown"

        if exists:
            return ToolResult.ok(
                f"Yes, {path} exists (type: {path_type})",
                exists=True,
                type=path_type
            )
        else:
            return ToolResult.ok(
                f"No, {path} does not exist",
                exists=False
            )


# === For testing/debugging ===

if __name__ == "__main__":
    tool = FileOpsTool()

    # Test listing current directory
    result = tool.execute(action="list", path=".")
    print("Current directory:")
    print(result.output)
