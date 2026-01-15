"""
Code Runner Tool

Allows the agent to execute Python code.
This is powerful but needs safety measures.
"""

import sys
import io
import traceback
import multiprocessing
from typing import Dict, Any, Optional
from contextlib import redirect_stdout, redirect_stderr

from .base import BaseTool, ToolResult


def _execute_code_in_subprocess(
    code: str,
    allow_imports: bool,
    result_queue: "multiprocessing.Queue",
) -> None:
    """Run code in a subprocess and return results via the queue."""
    stdout_buffer = io.StringIO()
    stderr_buffer = io.StringIO()

    exec_globals = {
        "__builtins__": __builtins__,
        "__name__": "__main__",
    }

    if allow_imports:
        import math
        import json
        import datetime
        import re
        import random
        import collections
        exec_globals.update({
            "math": math,
            "json": json,
            "datetime": datetime,
            "re": re,
            "random": random,
            "collections": collections,
        })

    try:
        with redirect_stdout(stdout_buffer), redirect_stderr(stderr_buffer):
            exec(code, exec_globals)

        stdout = stdout_buffer.getvalue()
        stderr = stderr_buffer.getvalue()
        result_queue.put({
            "stdout": stdout,
            "stderr": stderr,
            "error_type": None,
            "error_msg": None,
        })
    except SyntaxError as e:
        error_msg = f"Syntax Error on line {e.lineno}:\n{e.text}\n{e.msg}"
        result_queue.put({
            "stdout": stdout_buffer.getvalue(),
            "stderr": stderr_buffer.getvalue(),
            "error_type": "SyntaxError",
            "error_msg": error_msg,
        })
    except Exception as e:
        tb = traceback.format_exc()
        error_msg = f"{type(e).__name__}: {e}\n\n[Traceback]\n{tb}"
        result_queue.put({
            "stdout": stdout_buffer.getvalue(),
            "stderr": stderr_buffer.getvalue(),
            "error_type": type(e).__name__,
            "error_msg": error_msg,
        })
    finally:
        stdout_buffer.close()
        stderr_buffer.close()


class CodeRunnerTool(BaseTool):
    """
    Tool for executing Python code.

    Executes code in a subprocess and captures output.
    Useful for testing code, running calculations, or validating ideas.

    Safety features:
    - Timeout limit
    - Captured stdout/stderr
    - Exception handling
    """

    def __init__(self, timeout: int = 30, allow_imports: bool = True, allow_interactive: bool = False):
        """
        Initialize the code runner.

        Args:
            timeout: Maximum execution time in seconds
            allow_imports: Whether to allow import statements
        """
        self.timeout = timeout
        self.allow_imports = allow_imports
        self.allow_interactive = allow_interactive

    @property
    def name(self) -> str:
        return "run_python"

    @property
    def description(self) -> str:
        return """Execute Python code and return the output.
The code runs in an isolated environment.
Use print() to output results.
Standard library imports are available.
Interactive input() is not supported by default.
Use this to test code, run calculations, or validate logic."""

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Python code to execute"
                }
            },
            "required": ["code"]
        }

    def execute(self, code: str) -> ToolResult:
        """
        Execute Python code.

        Args:
            code: Python code to run

        Returns:
            ToolResult with stdout, stderr, and any errors
        """
        if not self.allow_interactive and "input(" in code:
            return ToolResult.fail(
                "Interactive input() is not supported in run_python.",
                error_type="InteractiveNotSupported",
            )

        ctx = multiprocessing.get_context()
        result_queue: "multiprocessing.Queue" = ctx.Queue()
        process = ctx.Process(
            target=_execute_code_in_subprocess,
            args=(code, self.allow_imports, result_queue),
        )
        process.start()
        process.join(timeout=self.timeout)

        if process.is_alive():
            process.terminate()
            process.join()
            return ToolResult.fail(
                f"Execution timed out after {self.timeout} seconds.",
                error_type="Timeout",
            )

        result: Optional[Dict[str, Any]] = None
        if not result_queue.empty():
            result = result_queue.get_nowait()

        if not result:
            return ToolResult.fail(
                "Execution failed: no result returned from subprocess.",
                error_type="ExecutionError",
            )

        stdout = result.get("stdout", "")
        stderr = result.get("stderr", "")
        error_type = result.get("error_type")
        error_msg = result.get("error_msg")

        if error_msg:
            return ToolResult.fail(
                error_msg,
                error_type=error_type,
                stdout=stdout,
                stderr=stderr,
            )

        output_parts = []
        if stdout:
            output_parts.append(stdout.rstrip())
        if stderr:
            output_parts.append(f"[stderr]\n{stderr.rstrip()}")

        output = "\n".join(output_parts) if output_parts else "(no output)"
        return ToolResult.ok(
            output,
            stdout=stdout,
            stderr=stderr,
            success=True,
        )


# === For testing/debugging ===

if __name__ == "__main__":
    tool = CodeRunnerTool()

    # Test simple code
    print("Test 1: Simple print")
    result = tool.execute(code='print("Hello, World!")')
    print(f"  Result: {result}\n")

    # Test calculation
    print("Test 2: Math calculation")
    result = tool.execute(code='import math\nprint(f"Pi = {math.pi:.4f}")')
    print(f"  Result: {result}\n")

    # Test error
    print("Test 3: Error handling")
    result = tool.execute(code='print(undefined_variable)')
    print(f"  Result: {result}\n")

    # Test syntax error
    print("Test 4: Syntax error")
    result = tool.execute(code='print("missing quote)')
    print(f"  Result: {result}\n")
