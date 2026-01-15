"""
Tests for the Agent module.

These tests verify the core agent functionality.
Run with: pytest app/tests/test_agent.py -v
"""

import pytest
from unittest.mock import Mock, patch

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import Config
from src.memory import Memory, Message
from src.tools.base import BaseTool, ToolResult
from src.tools.file_ops import FileOpsTool
from src.tools.code_runner import CodeRunnerTool


# === Config Tests ===

class TestConfig:
    """Tests for the Config class."""

    def test_default_values(self):
        """Test that default config values are set."""
        config = Config(provider="gemini", gemini_api_key="test-key")

        assert config.model == "gemini-3-pro-preview"
        assert config.slow_mode == True
        assert config.max_iterations == 10

    def test_validation_missing_key(self):
        """Test that missing API key produces error."""
        config = Config()
        errors = config.validate()

        assert len(errors) > 0
        assert "OPENAI_API_KEY" in errors[0]


# === Memory Tests ===

class TestMemory:
    """Tests for the Memory class."""

    def test_add_message(self):
        """Test adding messages to memory."""
        memory = Memory()

        memory.add_user_message("Hello")
        memory.add_assistant_message("Hi there!")

        assert len(memory) == 2

    def test_message_format(self):
        """Test message formatting for LLM."""
        memory = Memory()
        memory.set_system_message("Be helpful.")
        memory.add_user_message("Hello")

        messages = memory.get_messages_for_llm()

        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"

    def test_max_history(self):
        """Test that old messages are trimmed."""
        memory = Memory(max_history=5)

        for i in range(10):
            memory.add_user_message(f"Message {i}")

        assert len(memory) == 5
        # Should keep the most recent
        assert "Message 9" in memory.messages[-1].content


# === Tool Tests ===

class TestToolResult:
    """Tests for ToolResult."""

    def test_ok_result(self):
        """Test creating successful result."""
        result = ToolResult.ok("Success!")

        assert result.success == True
        assert result.output == "Success!"
        assert result.error is None

    def test_fail_result(self):
        """Test creating failed result."""
        result = ToolResult.fail("Something went wrong")

        assert result.success == False
        assert result.error == "Something went wrong"


class TestFileOpsTool:
    """Tests for FileOpsTool."""

    def test_list_directory(self, tmp_path):
        """Test listing a directory."""
        # Create a test file
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello")

        tool = FileOpsTool(allowed_paths=[str(tmp_path)])
        result = tool.execute(action="list", path=str(tmp_path))

        assert result.success
        assert "test.txt" in result.output

    def test_read_file(self, tmp_path):
        """Test reading a file."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello world")

        tool = FileOpsTool(allowed_paths=[str(tmp_path)])
        result = tool.execute(action="read", path=str(test_file))

        assert result.success
        assert result.output == "hello world"

    def test_write_file(self, tmp_path):
        """Test writing a file."""
        test_file = tmp_path / "new.txt"

        tool = FileOpsTool(allowed_paths=[str(tmp_path)])
        result = tool.execute(
            action="write",
            path=str(test_file),
            content="new content"
        )

        assert result.success
        assert test_file.read_text() == "new content"

    def test_file_not_found(self, tmp_path):
        """Test reading non-existent file."""
        tool = FileOpsTool(allowed_paths=[str(tmp_path)])
        result = tool.execute(action="read", path=str(tmp_path / "missing.txt"))

        assert not result.success
        assert "not found" in result.error.lower()


class TestCodeRunnerTool:
    """Tests for CodeRunnerTool."""

    def test_simple_print(self):
        """Test running simple code."""
        tool = CodeRunnerTool()
        result = tool.execute(code='print("hello")')

        assert result.success
        assert "hello" in result.output

    def test_calculation(self):
        """Test running a calculation."""
        tool = CodeRunnerTool()
        result = tool.execute(code='print(2 + 2)')

        assert result.success
        assert "4" in result.output

    def test_syntax_error(self):
        """Test handling syntax errors."""
        tool = CodeRunnerTool()
        result = tool.execute(code='print("unclosed')

        assert not result.success
        assert "Syntax" in result.error

    def test_runtime_error(self):
        """Test handling runtime errors."""
        tool = CodeRunnerTool()
        result = tool.execute(code='print(undefined_var)')

        assert not result.success
        assert "NameError" in result.error


# === Integration Tests ===

class TestAgentIntegration:
    """Integration tests (require mocking LLM)."""

    @pytest.fixture
    def mock_config(self):
        """Create a test config."""
        return Config(
            provider="openai",
            model="gpt-4",
            openai_api_key="test-key",
            slow_mode=False,
            verbose=False,
            max_iterations=3
        )

    def test_memory_persists(self, mock_config):
        """Test that memory persists across steps."""
        memory = Memory()
        memory.add_user_message("Hello")
        memory.add_assistant_message("Hi!")

        # Save and load
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            memory.save(f.name)

            new_memory = Memory()
            new_memory.load(f.name)

            assert len(new_memory) == 2


# === Run Tests ===

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
