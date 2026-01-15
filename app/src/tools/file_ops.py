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
    current working directory to prevent accidental damage.
    """

    def __init__(self, allowed_paths: List[str] = None):
        """
        Initialize the file operations tool.

        Args:
            allowed_paths: List of paths where operations are allowed.
                           Defaults to current directory only.
        """
        self.allowed_paths = allowed_paths or ["."]

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

        Ensures the path is within allowed directories.
        """
        # Convert to absolute path
        resolved = Path(path).resolve()

        # Check if it's within allowed paths
        for allowed in self.allowed_paths:
            allowed_resolved = Path(allowed).resolve()
            try:
                resolved.relative_to(allowed_resolved)
                return resolved
            except ValueError:
                continue

        # Also allow if it's under current directory
        cwd = Path.cwd()
        try:
            resolved.relative_to(cwd)
            return resolved
        except ValueError:
            pass

        raise ValueError(f"Path '{path}' is outside allowed directories")

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
