"""
Stability-focused tests for timeouts, provider validation, and error paths.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import Config
from src.tools.code_runner import CodeRunnerTool
from src.llm import LLMInterface
from src.reliability import LLMError


def test_code_runner_timeout():
    tool = CodeRunnerTool(timeout=0.1)
    result = tool.execute(code="while True:\n    pass")
    assert result.success is False
    assert "timed out" in (result.error or "").lower()
    assert result.metadata.get("error_type") == "Timeout"


def test_config_validate_provider_keys():
    config = Config(provider="deepseek", deepseek_api_key="test-key")
    assert config.validate() == []

    config = Config(provider="openai", openai_api_key="")
    errors = config.validate()
    assert any("OPENAI_API_KEY" in error for error in errors)


def test_anthropic_tool_calling_not_supported():
    pytest.importorskip("anthropic")
    config = Config(provider="anthropic", anthropic_api_key="test-key")
    llm = LLMInterface(config)
    with pytest.raises(LLMError):
        llm.chat_with_tools(
            messages=[{"role": "user", "content": "hello"}],
            tools=[],
        )
