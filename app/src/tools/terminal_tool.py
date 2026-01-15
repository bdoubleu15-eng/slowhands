"""
Terminal Command Execution Tool

Allows the agent to execute shell commands in a controlled environment.
Safety: Restricted to workspace directory with command timeout and validation.
"""

import subprocess
import shlex
import os
import time
from pathlib import Path
from typing import Dict, Any, Optional
from .base import BaseTool, ToolResult


class TerminalTool(BaseTool):
    """
    Tool for executing terminal commands.

    Supports:
    - Running shell commands (bash, sh, etc.)
    - Capturing stdout/stderr
    - Setting working directory (within workspace)
    - Timeout protection

    Safety Features:
    - Commands restricted to workspace directory
    - Timeout (30 seconds default)
    - Basic command validation (no absolute path execution outside workspace)
    """

    # List of potentially dangerous commands (partial matches)
    DANGEROUS_COMMANDS = [
        "rm -rf", "rm -fr", "rm -r", "rm -f",
        "mkfs", "dd", "format",
        "shutdown", "reboot", "halt",
        "> /dev/sda", "> /dev/sdb",
        "chmod 777", "chown root",
        "wget", "curl", "nc", "netcat", "ssh", "scp"
    ]

    def __init__(self, workspace_path: str = None, command_timeout: float = 30.0):
        """
        Initialize the terminal tool.

        Args:
            workspace_path: Base directory for command execution.
                           Defaults to current working directory.
            command_timeout: Maximum execution time in seconds.
        """
        self.workspace_path = Path(workspace_path) if workspace_path else Path.cwd()
        self.command_timeout = command_timeout
        # Ensure workspace exists
        self.workspace_path.mkdir(parents=True, exist_ok=True)

    @property
    def name(self) -> str:
        return "terminal"

    @property
    def description(self) -> str:
        return """Execute terminal commands in a controlled environment.
Use this to run shell commands, check system status, or execute scripts.

Safety restrictions:
- Commands run within the workspace directory
- Maximum execution time: 30 seconds
- Potentially dangerous commands are blocked

Example commands:
- ls -la: List files
- pwd: Print working directory
- python --version: Check Python version
- echo "Hello": Print text

Only use for necessary system interactions. Prefer file operations or code runner for most tasks."""

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Shell command to execute"
                },
                "working_dir": {
                    "type": "string",
                    "description": "Working directory (relative to workspace, optional)"
                },
                "timeout": {
                    "type": "number",
                    "description": "Timeout in seconds (optional, max 60)"
                }
            },
            "required": ["command"]
        }

    def _is_command_dangerous(self, command: str) -> bool:
        """
        Check if command appears dangerous.

        Args:
            command: Command string

        Returns:
            True if command contains dangerous patterns
        """
        cmd_lower = command.lower()
        for dangerous in self.DANGEROUS_COMMANDS:
            if dangerous in cmd_lower:
                return True

        # Check for absolute path references outside workspace
        # Simple heuristic: starts with / and not in workspace
        parts = shlex.split(command)
        for part in parts:
            if part.startswith('/') and not part.startswith(str(self.workspace_path)):
                # Might be an absolute path outside workspace
                return True

        return False

    def _resolve_working_dir(self, working_dir: Optional[str] = None) -> Path:
        """
        Resolve working directory within workspace.

        Args:
            working_dir: Relative path within workspace

        Returns:
            Absolute Path object

        Raises:
            ValueError: If path is outside workspace
        """
        if working_dir:
            resolved = (self.workspace_path / working_dir).resolve()
        else:
            resolved = self.workspace_path.resolve()

        workspace_resolved = self.workspace_path.resolve()

        # Check if path is within workspace
        try:
            resolved.relative_to(workspace_resolved)
        except ValueError:
            raise ValueError(f"Working directory {working_dir} is outside workspace")

        # Ensure directory exists
        resolved.mkdir(parents=True, exist_ok=True)
        return resolved

    def execute(self, command: str, working_dir: Optional[str] = None,
                timeout: Optional[float] = None) -> ToolResult:
        """
        Execute a terminal command.

        Args:
            command: Shell command to execute
            working_dir: Working directory (relative to workspace)
            timeout: Timeout in seconds (overrides default)

        Returns:
            ToolResult with command output
        """
        # Validate command
        if not command or not command.strip():
            return ToolResult.fail("Command cannot be empty")

        if self._is_command_dangerous(command):
            return ToolResult.fail(f"Command blocked for safety: {command}")

        # Resolve working directory
        try:
            cwd = self._resolve_working_dir(working_dir)
        except ValueError as e:
            return ToolResult.fail(str(e))

        # Determine timeout
        cmd_timeout = timeout if timeout is not None else self.command_timeout
        if cmd_timeout > 60:  # Safety cap
            cmd_timeout = 60

        start_time = time.time()
        try:
            # Use shell=True for convenience but be careful
            result = subprocess.run(
                command,
                shell=True,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=cmd_timeout,
                env={**os.environ, "PYTHONPATH": ""}  # Don't inherit PYTHONPATH for safety
            )

            execution_time = time.time() - start_time

            if result.returncode == 0:
                output = result.stdout.strip() or "Command executed successfully (no output)"
                return ToolResult.ok(
                    output,
                    metadata={
                        "return_code": result.returncode,
                        "stderr": result.stderr.strip(),
                        "execution_time": round(execution_time, 2),
                        "working_dir": str(cwd)
                    }
                )
            else:
                error_msg = result.stderr.strip() or f"Command failed with exit code {result.returncode}"
                # Include stdout if it contains useful info
                if result.stdout.strip():
                    error_msg = f"{error_msg}\n\nStdout:\n{result.stdout.strip()}"

                return ToolResult.fail(
                    error_msg,
                    metadata={
                        "return_code": result.returncode,
                        "stdout": result.stdout.strip(),
                        "execution_time": round(execution_time, 2),
                        "working_dir": str(cwd)
                    }
                )

        except subprocess.TimeoutExpired:
            execution_time = time.time() - start_time
            return ToolResult.fail(
                f"Command timed out after {execution_time:.1f} seconds",
                metadata={
                    "execution_time": round(execution_time, 2),
                    "working_dir": str(cwd)
                }
            )
        except FileNotFoundError:
            return ToolResult.fail(f"Shell not found or command not executable: {command}")
        except Exception as e:
            return ToolResult.fail(f"Unexpected error executing command: {e}")