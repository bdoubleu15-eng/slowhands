"""
Git Operations Tool

Allows the agent to perform basic Git operations.
Safety: Restricted to workspace directory by default.
"""

import subprocess
import os
from pathlib import Path
from typing import Dict, Any, List, Optional
from .base import BaseTool, ToolResult


class GitTool(BaseTool):
    """
    Tool for Git operations within the workspace.

    Supports:
    - status: Show working directory status
    - diff: Show changes
    - log: Show commit history
    - add: Stage files
    - commit: Commit staged changes
    - branch: List/create/delete branches
    - checkout: Switch branches

    Safety: All operations are restricted to the workspace directory.
    """

    def __init__(self, workspace_path: str = None):
        """
        Initialize the Git tool.

        Args:
            workspace_path: Base directory for Git operations.
                           Defaults to current working directory.
        """
        self.workspace_path = Path(workspace_path) if workspace_path else Path.cwd()
        # Ensure workspace exists
        self.workspace_path.mkdir(parents=True, exist_ok=True)

    @property
    def name(self) -> str:
        return "git"

    @property
    def description(self) -> str:
        return """Perform Git version control operations.
Actions:
- status: Show the working directory status
- diff: Show changes between commits, commit and working tree, etc.
- log: Show commit history
- add: Add file contents to the index (stage files)
- commit: Record changes to the repository
- branch: List, create, or delete branches
- checkout: Switch branches or restore working tree files

Use this to manage version control for your code projects.
All operations are limited to the workspace directory for safety."""

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["status", "diff", "log", "add", "commit", "branch", "checkout"],
                    "description": "The Git operation to perform"
                },
                "path": {
                    "type": "string",
                    "description": "File or directory path (relative to workspace, optional for some actions)"
                },
                "message": {
                    "type": "string",
                    "description": "Commit message (required for 'commit' action)"
                },
                "branch_name": {
                    "type": "string",
                    "description": "Branch name (for 'branch' or 'checkout' actions)"
                },
                "create_branch": {
                    "type": "boolean",
                    "description": "Create branch if it doesn't exist (for 'branch' action)"
                },
                "delete_branch": {
                    "type": "boolean",
                    "description": "Delete branch (for 'branch' action)"
                }
            },
            "required": ["action"]
        }

    def _run_git_command(self, args: List[str], cwd: Path = None) -> ToolResult:
        """
        Run a Git command and return the result.

        Args:
            args: List of arguments for git command
            cwd: Working directory for the command

        Returns:
            ToolResult with command output
        """
        if cwd is None:
            cwd = self.workspace_path

        try:
            # Ensure we're running within the workspace
            cwd = cwd.resolve()
            if not str(cwd).startswith(str(self.workspace_path.resolve())):
                return ToolResult.fail(f"Git operations restricted to workspace: {self.workspace_path}")

            result = subprocess.run(
                ["git"] + args,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=30  # Safety timeout
            )

            if result.returncode == 0:
                return ToolResult.ok(
                    result.stdout.strip() or "Command executed successfully.",
                    metadata={
                        "return_code": result.returncode,
                        "stderr": result.stderr.strip()
                    }
                )
            else:
                error_msg = result.stderr.strip() or "Git command failed"
                return ToolResult.fail(
                    error_msg,
                    metadata={
                        "return_code": result.returncode,
                        "stdout": result.stdout.strip()
                    }
                )

        except subprocess.TimeoutExpired:
            return ToolResult.fail("Git command timed out after 30 seconds")
        except FileNotFoundError:
            return ToolResult.fail("Git is not installed or not in PATH")
        except Exception as e:
            return ToolResult.fail(f"Unexpected error running git command: {e}")

    def _resolve_path(self, path: str) -> Path:
        """
        Resolve a relative path within the workspace.

        Args:
            path: Relative path string

        Returns:
            Absolute Path object

        Raises:
            ValueError: If path is outside workspace
        """
        resolved = (self.workspace_path / path).resolve()
        workspace_resolved = self.workspace_path.resolve()

        # Check if path is within workspace
        try:
            resolved.relative_to(workspace_resolved)
        except ValueError:
            raise ValueError(f"Path {path} is outside workspace directory")

        return resolved

    def execute(self, action: str, path: Optional[str] = None, message: Optional[str] = None,
                branch_name: Optional[str] = None, create_branch: bool = False,
                delete_branch: bool = False) -> ToolResult:
        """
        Execute a Git operation.

        Args:
            action: One of "status", "diff", "log", "add", "commit", "branch", "checkout"
            path: File or directory path (optional)
            message: Commit message (for commit)
            branch_name: Branch name (for branch/checkout)
            create_branch: Create branch if it doesn't exist
            delete_branch: Delete branch

        Returns:
            ToolResult with the operation result
        """
        # Determine working directory
        cwd = self.workspace_path
        if path:
            try:
                resolved_path = self._resolve_path(path)
                # If path is a directory, use it as cwd
                if resolved_path.is_dir():
                    cwd = resolved_path
                else:
                    # For file operations, use parent directory
                    cwd = resolved_path.parent
            except ValueError as e:
                return ToolResult.fail(str(e))

        # Dispatch based on action
        if action == "status":
            return self._run_git_command(["status"], cwd=cwd)

        elif action == "diff":
            args = ["diff"]
            if path:
                # Show diff for specific file
                args.append(str(self._resolve_path(path)))
            return self._run_git_command(args, cwd=cwd)

        elif action == "log":
            args = ["log", "--oneline", "-10"]  # Last 10 commits
            return self._run_git_command(args, cwd=cwd)

        elif action == "add":
            if not path:
                return ToolResult.fail("Path is required for 'add' action")
            resolved_path = self._resolve_path(path)
            return self._run_git_command(["add", str(resolved_path)], cwd=cwd)

        elif action == "commit":
            if not message:
                return ToolResult.fail("Commit message is required")
            return self._run_git_command(["commit", "-m", message], cwd=cwd)

        elif action == "branch":
            args = ["branch"]
            if delete_branch and branch_name:
                args = ["branch", "-d", branch_name]
            elif create_branch and branch_name:
                args = ["checkout", "-b", branch_name]
            elif branch_name:
                # List branches, show current with asterisk
                args = ["branch"]
                result = self._run_git_command(args, cwd=cwd)
                if result.success:
                    # Highlight the requested branch if it exists
                    lines = result.output.split('\n')
                    for i, line in enumerate(lines):
                        if line.strip().lstrip('* ') == branch_name:
                            lines[i] = f"* {line.strip()}" if not line.startswith('*') else line
                            result.output = '\n'.join(lines)
                            break
                return result
            else:
                # Just list branches
                args = ["branch"]
            return self._run_git_command(args, cwd=cwd)

        elif action == "checkout":
            if not branch_name:
                return ToolResult.fail("Branch name is required for checkout")
            args = ["checkout", branch_name]
            return self._run_git_command(args, cwd=cwd)

        else:
            return ToolResult.fail(f"Unknown Git action: {action}")