"""
Tests for agent tools.
"""

import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from src.tools import (
    FileOpsTool,
    CodeRunnerTool,
    GitTool,
    TerminalTool,
    WebSearchTool,
    BaseTool,
    ToolResult
)


class TestBaseTool:
    """Test base tool functionality."""

    def test_base_tool_abstract(self):
        """BaseTool should be abstract."""
        with pytest.raises(TypeError):
            BaseTool()


class TestFileOpsTool:
    """Test file operations tool."""

    def test_initialization(self, tmp_path):
        """Tool should initialize with workspace path."""
        tool = FileOpsTool(workspace_path=str(tmp_path))
        assert tool.name == "file_ops"
        assert "file system operations" in tool.description.lower()
        assert "action" in tool.parameters["properties"]

    def test_validate_parameters(self, tmp_path):
        """Tool should validate required parameters."""
        tool = FileOpsTool(workspace_path=str(tmp_path))
        assert tool.validate({"action": "read", "path": "test.txt"})
        assert not tool.validate({"action": "read"})  # Missing path


class TestCodeRunnerTool:
    """Test code runner tool."""

    def test_initialization(self):
        """Tool should initialize."""
        tool = CodeRunnerTool()
        assert tool.name == "run_python"
        assert "python code" in tool.description.lower()
        assert "code" in tool.parameters["properties"]


class TestGitTool:
    """Test Git tool."""

    def test_initialization(self, tmp_path):
        """Tool should initialize with workspace path."""
        tool = GitTool(workspace_path=str(tmp_path))
        assert tool.name == "git"
        assert "git" in tool.description.lower()
        assert "action" in tool.parameters["properties"]

    @patch("subprocess.run")
    def test_git_status(self, mock_run, tmp_path):
        """Git status command should work."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="On branch main",
            stderr=""
        )
        tool = GitTool(workspace_path=str(tmp_path))
        result = tool.execute(action="status")
        assert result.success is True
        assert "On branch main" in result.output

    def test_validate_parameters(self, tmp_path):
        """Tool should validate required parameters."""
        tool = GitTool(workspace_path=str(tmp_path))
        assert tool.validate({"action": "status"})
        assert not tool.validate({})  # Missing action


class TestTerminalTool:
    """Test terminal tool."""

    def test_initialization(self, tmp_path):
        """Tool should initialize with workspace path."""
        tool = TerminalTool(workspace_path=str(tmp_path))
        assert tool.name == "terminal"
        assert "terminal commands" in tool.description.lower()
        assert "command" in tool.parameters["properties"]

    def test_dangerous_command_detection(self, tmp_path):
        """Tool should detect dangerous commands."""
        tool = TerminalTool(workspace_path=str(tmp_path))
        assert tool._is_command_dangerous("rm -rf /") is True
        assert tool._is_command_dangerous("ls -la") is False

    @patch("subprocess.run")
    def test_safe_command_execution(self, mock_run, tmp_path):
        """Safe command should execute."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="file1.txt\nfile2.txt",
            stderr="",
        )
        tool = TerminalTool(workspace_path=str(tmp_path))
        result = tool.execute(command="ls -la")
        assert result.success is True
        assert "file1.txt" in result.output


class TestWebSearchTool:
    """Test web search tool."""

    def test_initialization(self):
        """Tool should initialize with API key."""
        tool = WebSearchTool(api_key="test_key")
        assert tool.name == "web_search"
        assert "search" in tool.description.lower()
        assert "query" in tool.parameters["properties"]
        assert tool.enabled is True

    def test_disabled_without_api_key(self):
        """Tool should be disabled without API key."""
        tool = WebSearchTool()
        assert tool.enabled is False

    @patch("requests.get")
    def test_search_with_results(self, mock_get, tmp_path):
        """Search should return formatted results."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "organic_results": [
                {
                    "title": "Test Result",
                    "link": "https://example.com",
                    "snippet": "Test snippet"
                }
            ]
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        tool = WebSearchTool(api_key="test_key")
        result = tool.execute(query="test query", num_results=1)
        assert result.success is True
        assert "Test Result" in result.output
        assert "example.com" in result.output

    def test_fallback_without_api_key(self):
        """Tool should provide fallback without API key."""
        tool = WebSearchTool()
        result = tool.execute(query="test query")
        assert result.success is True
        assert "google.com" in result.output.lower()


class TestToolResult:
    """Test tool result class."""

    def test_ok_result(self):
        """Successful result should have success=True."""
        result = ToolResult.ok("Operation successful")
        assert result.success is True
        assert result.output == "Operation successful"
        assert result.error is None

    def test_fail_result(self):
        """Failed result should have success=False."""
        result = ToolResult.fail("Operation failed")
        assert result.success is False
        assert result.output == ""
        assert result.error == "Operation failed"

    def test_result_str(self):
        """String representation should show output or error."""
        success = ToolResult.ok("Success")
        failure = ToolResult.fail("Failure")
        assert str(success) == "Success"
        assert "Failure" in str(failure)