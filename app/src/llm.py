"""
LLM Interface Module

Handles communication with supported LLM APIs.
This is where we send prompts and receive responses.

Includes reliability features:
- Retry logic with exponential backoff
- Request timeouts
- Rate limiting (RPM/TPM)
- Circuit breaker pattern
"""

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

from openai import OpenAI
from openai import (
    RateLimitError as OpenAIRateLimitError,
    APITimeoutError as OpenAIAPITimeoutError,
    APIConnectionError as OpenAIAPIConnectionError,
)

# Optional imports for other providers
try:
    import anthropic
    from anthropic import Anthropic, AnthropicError, RateLimitError as AnthropicRateLimitError
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    Anthropic = None
    AnthropicError = None
    AnthropicRateLimitError = None

try:
    from google import genai
    from google.genai import types as genai_types
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    genai = None
    genai_types = None
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

from .config import Config
from .reliability import (
    RateLimiter,
    CircuitBreaker,
    CircuitOpenError,
    LLMError,
)

logger = logging.getLogger(__name__)

# #region debug log
def _dbg_log(location: str, message: str, data: dict, hypothesis_id: str) -> None:
    try:
        payload = {
            "id": f"log_{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}",
            "timestamp": int(time.time() * 1000),
            "location": location,
            "message": message,
            "data": data,
            "sessionId": "debug-session",
            "runId": "run1",
            "hypothesisId": hypothesis_id,
        }
        with open("/home/dub/projects/slowhands/.cursor/debug.log", "a") as f:
            f.write(json.dumps(payload) + "\n")
    except Exception:
        pass
# #endregion


@dataclass
class ToolCall:
    """
    Represents a tool call from the LLM.

    When the LLM decides to use a tool, it returns one of these.
    """
    id: str                    # Unique ID for this call
    name: str                  # Tool name (e.g., "read_file")
    arguments: Dict[str, Any]  # Arguments to pass to the tool


@dataclass
class LLMResponse:
    """
    Response from the LLM.

    The LLM can either:
    1. Return text content (a direct response)
    2. Request tool calls (wants to use tools)
    3. Both (rare, but possible)
    """
    content: Optional[str]           # Text response (if any)
    tool_calls: List[ToolCall]       # Tool calls (if any)
    finish_reason: str               # Why the LLM stopped
    usage: Dict[str, int] = field(default_factory=dict)  # Token counts

    @property
    def has_tool_calls(self) -> bool:
        """Check if this response includes tool calls."""
        return len(self.tool_calls) > 0


class LLMInterface:
    """
    Interface for communicating with the LLM.

    This wraps the OpenAI client and provides:
    - Simple chat (text in, text out)
    - Chat with tools (text in, text or tool calls out)
    - Retry logic with exponential backoff
    - Rate limiting (RPM/TPM tracking)
    - Circuit breaker pattern
    - Token counting
    """

    def _get_retriable_exceptions(self):
        """Get retriable exceptions based on provider."""
        exceptions = []

        if self.provider in ["openai", "deepseek"]:
            exceptions.extend([
                OpenAIRateLimitError,
                OpenAIAPITimeoutError,
                OpenAIAPIConnectionError,
            ])

        if self.provider == "anthropic" and ANTHROPIC_AVAILABLE:
            exceptions.extend([
                AnthropicRateLimitError,
                AnthropicError,
            ])

        return tuple(exceptions)

    def __init__(self, config: Config):
        """
        Initialize the LLM interface.

        Args:
            config: Application configuration
        """
        self.config = config
        self.provider = config.provider
        self.model = config.model
        self.temperature = config.temperature
        self.max_tokens = config.max_tokens

        # Initialize client based on provider
        if self.provider == "openai":
            self.client = OpenAI(
                api_key=config.openai_api_key,
                timeout=config.request_timeout,
            )
            self.api_type = "openai"
        elif self.provider == "deepseek":
            # DeepSeek uses OpenAI-compatible API
            self.client = OpenAI(
                api_key=config.deepseek_api_key,
                base_url="https://api.deepseek.com",
                timeout=config.request_timeout,
            )
            self.api_type = "openai"  # Same API format as OpenAI
        elif self.provider == "anthropic":
            if not ANTHROPIC_AVAILABLE:
                raise ImportError("Anthropic package not installed. Run: pip install anthropic")
            self.client = Anthropic(
                api_key=config.anthropic_api_key,
                timeout=config.request_timeout * 1000,  # Anthropic uses milliseconds
            )
            self.api_type = "anthropic"
        elif self.provider == "gemini":
            if not GEMINI_AVAILABLE:
                raise ImportError("Google GenAI package not installed. Run: pip install google-genai")
            self.client = genai.Client(api_key=config.gemini_api_key)
            self.api_type = "gemini"
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")

        # Track usage for the session
        self.total_tokens_used = 0

        # Reliability components
        self.rate_limiter = RateLimiter(
            rpm_limit=config.rate_limit_rpm,
            tpm_limit=config.rate_limit_tpm,
        )
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=config.circuit_breaker_threshold,
            reset_timeout=config.circuit_breaker_timeout,
        )

        logger.debug(
            f"LLMInterface initialized: model={self.model}, "
            f"timeout={config.request_timeout}s, "
            f"retries={config.retry_attempts}"
        )

    def _create_retry_decorator(self):
        """Create a retry decorator based on config settings."""
        return retry(
            stop=stop_after_attempt(self.config.retry_attempts),
            wait=wait_exponential(
                min=self.config.retry_min_wait,
                max=self.config.retry_max_wait,
            ),
            retry=retry_if_exception_type(self._get_retriable_exceptions()),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            reraise=True,
        )

    def chat(self, messages: List[Dict[str, Any]]) -> str:
        """
        Simple chat completion with reliability features.

        This is the basic "send messages, get text back" flow.

        Args:
            messages: List of messages in OpenAI format

        Returns:
            The assistant's response text

        Raises:
            CircuitOpenError: If circuit breaker is open
            LLMError: If API call fails after retries
        """
        # Check circuit breaker
        self.circuit_breaker.check()

        # Estimate tokens and check rate limits
        estimated_tokens = sum(self.count_tokens(str(m)) for m in messages) + 500
        self.rate_limiter.check_and_wait(estimated_tokens=estimated_tokens)

        try:
            response = self._chat_with_retry(messages)

            # Extract content and usage based on provider
            if self.api_type == "openai":
                content = response.choices[0].message.content or ""
                usage = response.usage
            elif self.api_type == "anthropic":
                # Anthropic response format
                content = response.content[0].text
                usage = response.usage
            elif self.api_type == "gemini":
                # Gemini response format
                content = response.text or ""
                usage = response.usage_metadata
            else:
                raise ValueError(f"Unsupported API type: {self.api_type}")

            # Track token usage
            if usage:
                if hasattr(usage, 'total_tokens'):
                    total_tokens = usage.total_tokens
                elif hasattr(usage, 'total_token_count'):
                    # Gemini uses total_token_count
                    total_tokens = usage.total_token_count
                elif hasattr(usage, 'input_tokens'):
                    total_tokens = usage.input_tokens + usage.output_tokens
                else:
                    total_tokens = 0
                self.total_tokens_used += total_tokens
                self.rate_limiter.record_request(total_tokens)

            # Record success
            self.circuit_breaker.record_success()
            total_for_log = 'unknown'
            if usage:
                if hasattr(usage, 'total_tokens'):
                    total_for_log = usage.total_tokens
                elif hasattr(usage, 'total_token_count'):
                    total_for_log = usage.total_token_count
            logger.debug(f"Chat completed, tokens used: {total_for_log}")

            return content

        except self._get_retriable_exceptions() as e:
            self.circuit_breaker.record_failure()
            logger.error(f"LLM API error after retries: {e}")
            raise LLMError(f"API error after {self.config.retry_attempts} retries: {e}") from e

    def _chat_with_retry(self, messages: List[Dict[str, Any]]):
        """Internal method that performs the actual API call with retry logic."""
        retry_decorator = self._create_retry_decorator()

        @retry_decorator
        def _do_call():
            if self.api_type == "openai":
                return self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                )
            elif self.api_type == "anthropic":
                # Convert messages to Anthropic format
                system_message = None
                conversation_messages = []

                for msg in messages:
                    if msg["role"] == "system":
                        system_message = msg["content"]
                    else:
                        # Anthropic expects content as string or list of content blocks
                        conversation_messages.append({
                            "role": msg["role"],
                            "content": msg["content"]
                        })

                return self.client.messages.create(
                    model=self.model,
                    messages=conversation_messages,
                    system=system_message,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                )
            elif self.api_type == "gemini":
                # Convert messages to Gemini format
                system_instruction = None
                contents = []

                for msg in messages:
                    if msg["role"] == "system":
                        system_instruction = msg["content"]
                    elif msg["role"] == "user":
                        contents.append(genai_types.Content(
                            role="user",
                            parts=[genai_types.Part(text=msg["content"])]
                        ))
                    elif msg["role"] == "assistant":
                        contents.append(genai_types.Content(
                            role="model",
                            parts=[genai_types.Part(text=msg["content"])]
                        ))

                config = genai_types.GenerateContentConfig(
                    temperature=self.temperature,
                    max_output_tokens=self.max_tokens,
                    system_instruction=system_instruction,
                )

                return self.client.models.generate_content(
                    model=self.model,
                    contents=contents,
                    config=config,
                )
            else:
                raise ValueError(f"Unsupported API type: {self.api_type}")

        return _do_call()

    def chat_with_tools(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
    ) -> LLMResponse:
        """
        Chat with tool-calling capability and reliability features.

        This is more advanced - the LLM can either respond with text
        OR request to use one or more tools.

        Args:
            messages: Conversation history in OpenAI format
            tools: List of available tools in OpenAI format

        Returns:
            LLMResponse with content and/or tool calls

        Raises:
            CircuitOpenError: If circuit breaker is open
            LLMError: If API call fails after retries
        """
        if self.api_type not in ["openai", "gemini"]:
            raise LLMError(
                "Tool calling is only supported for OpenAI-compatible providers and Gemini. "
                "Switch to OpenAI, DeepSeek, or Gemini to use tools."
            )
        # #region debug log
        _dbg_log(
            "llm.py:chat_with_tools",
            "llm_request_start",
            {"provider": self.provider, "model": self.model, "msg_count": len(messages)},
            "F",
        )
        # #endregion

        # Check circuit breaker
        self.circuit_breaker.check()

        # Estimate tokens and check rate limits
        estimated_tokens = sum(self.count_tokens(str(m)) for m in messages)
        estimated_tokens += sum(self.count_tokens(str(t)) for t in tools) if tools else 0
        estimated_tokens += 500  # Buffer for response
        self.rate_limiter.check_and_wait(estimated_tokens=estimated_tokens)

        try:
            response = self._chat_with_tools_retry(messages, tools)

            # Track token usage and parse response based on API type
            usage = {}
            tool_calls = []
            content = None
            finish_reason = "stop"

            if self.api_type == "openai":
                if response.usage:
                    usage = {
                        "prompt_tokens": response.usage.prompt_tokens,
                        "completion_tokens": response.usage.completion_tokens,
                        "total_tokens": response.usage.total_tokens,
                    }
                    self.total_tokens_used += response.usage.total_tokens
                    self.rate_limiter.record_request(response.usage.total_tokens)

                # Parse the response
                choice = response.choices[0]
                message = choice.message
                content = message.content
                finish_reason = choice.finish_reason or "stop"

                # Extract tool calls if any
                if message.tool_calls:
                    for tc in message.tool_calls:
                        try:
                            args = json.loads(tc.function.arguments)
                        except json.JSONDecodeError:
                            logger.warning(f"Failed to parse tool arguments: {tc.function.arguments}")
                            args = {}

                        tool_calls.append(ToolCall(
                            id=tc.id,
                            name=tc.function.name,
                            arguments=args
                        ))

            elif self.api_type == "gemini":
                # Gemini response format
                if response.usage_metadata:
                    total_tokens = response.usage_metadata.total_token_count or 0
                    usage = {
                        "prompt_tokens": response.usage_metadata.prompt_token_count or 0,
                        "completion_tokens": response.usage_metadata.candidates_token_count or 0,
                        "total_tokens": total_tokens,
                    }
                    self.total_tokens_used += total_tokens
                    self.rate_limiter.record_request(total_tokens)

                # Parse content and function calls from Gemini response
                if response.candidates and len(response.candidates) > 0:
                    candidate = response.candidates[0]
                    finish_reason = str(candidate.finish_reason) if candidate.finish_reason else "stop"

                    if candidate.content and candidate.content.parts:
                        text_parts = []
                        for i, part in enumerate(candidate.content.parts):
                            if hasattr(part, 'text') and part.text:
                                text_parts.append(part.text)
                            elif hasattr(part, 'function_call') and part.function_call:
                                fc = part.function_call
                                # Gemini doesn't provide IDs, so we generate one
                                tool_calls.append(ToolCall(
                                    id=f"call_{i}_{fc.name}",
                                    name=fc.name,
                                    arguments=dict(fc.args) if fc.args else {}
                                ))
                        content = "\n".join(text_parts) if text_parts else None

            # Record success
            self.circuit_breaker.record_success()

            logger.debug(
                f"Chat with tools completed: "
                f"tokens={usage.get('total_tokens', 'unknown')}, "
                f"tool_calls={len(tool_calls)}"
            )
            # #region debug log
            _dbg_log(
                "llm.py:chat_with_tools",
                "llm_request_success",
                {
                    "tool_calls": len(tool_calls),
                    "content_len": len(content or ""),
                    "finish_reason": finish_reason,
                },
                "F",
            )
            # #endregion

            return LLMResponse(
                content=content,
                tool_calls=tool_calls,
                finish_reason=finish_reason,
                usage=usage
            )

        except self._get_retriable_exceptions() as e:
            self.circuit_breaker.record_failure()
            logger.error(f"LLM API error after retries: {e}")
            # #region debug log
            _dbg_log(
                "llm.py:chat_with_tools",
                "llm_request_error",
                {"error": str(e)},
                "F",
            )
            # #endregion
            raise LLMError(f"API error after {self.config.retry_attempts} retries: {e}") from e

    def _chat_with_tools_retry(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
    ):
        """Internal method that performs the actual API call with retry logic."""
        retry_decorator = self._create_retry_decorator()

        @retry_decorator
        def _do_call():
            if self.api_type == "openai":
                return self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=tools if tools else None,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                )
            elif self.api_type == "gemini":
                # Convert messages to Gemini format
                system_instruction = None
                contents = []

                for msg in messages:
                    if msg["role"] == "system":
                        system_instruction = msg["content"]
                    elif msg["role"] == "user":
                        contents.append(genai_types.Content(
                            role="user",
                            parts=[genai_types.Part(text=msg["content"])]
                        ))
                    elif msg["role"] == "assistant":
                        contents.append(genai_types.Content(
                            role="model",
                            parts=[genai_types.Part(text=msg["content"])]
                        ))
                    elif msg["role"] == "tool":
                        # Tool result message
                        contents.append(genai_types.Content(
                            role="user",
                            parts=[genai_types.Part(
                                function_response=genai_types.FunctionResponse(
                                    name=msg.get("name", "tool"),
                                    response={"result": msg["content"]}
                                )
                            )]
                        ))

                # Convert OpenAI tool format to Gemini function declarations
                gemini_tools = None
                if tools:
                    function_declarations = []
                    for tool in tools:
                        if tool.get("type") == "function":
                            func = tool["function"]
                            function_declarations.append(genai_types.FunctionDeclaration(
                                name=func["name"],
                                description=func.get("description", ""),
                                parameters=func.get("parameters", {})
                            ))
                    if function_declarations:
                        gemini_tools = [genai_types.Tool(function_declarations=function_declarations)]

                config = genai_types.GenerateContentConfig(
                    temperature=self.temperature,
                    max_output_tokens=self.max_tokens,
                    system_instruction=system_instruction,
                    tools=gemini_tools,
                )

                return self.client.models.generate_content(
                    model=self.model,
                    contents=contents,
                    config=config,
                )
            elif self.api_type == "anthropic":
                # Anthropic tool use requires different format
                # For now, raise error - tool calling not implemented for Anthropic
                raise NotImplementedError(
                    "Tool calling not yet implemented for Anthropic provider. "
                    "Switch to OpenAI or DeepSeek for tool calling support."
                )
            else:
                raise ValueError(f"Unsupported API type: {self.api_type}")

        return _do_call()

    def format_tool_for_api(self, tool: Any) -> Dict[str, Any]:
        """
        Format a tool for the OpenAI API.

        Tools need to be in a specific format. This converts
        our tool objects to the API format.

        Args:
            tool: A tool object with name, description, parameters

        Returns:
            Tool in OpenAI API format
        """
        return {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters
            }
        }

    def count_tokens(self, text: str) -> int:
        """
        Estimate token count for a string.

        This is a rough estimate - actual count may vary.
        Rule of thumb: ~4 characters per token for English.
        """
        return len(text) // 4

    def get_status(self) -> dict:
        """Get current status of LLM interface including reliability metrics."""
        return {
            "model": self.model,
            "total_tokens_used": self.total_tokens_used,
            "rate_limiter": self.rate_limiter.get_current_usage(),
            "circuit_breaker": self.circuit_breaker.get_status(),
        }


# === For testing/debugging ===

if __name__ == "__main__":
    from .config import load_config
    from .logging_config import setup_logging

    setup_logging(level="DEBUG")

    config = load_config()

    missing_key = (
        (config.provider == "openai" and not config.openai_api_key) or
        (config.provider == "anthropic" and not config.anthropic_api_key) or
        (config.provider == "deepseek" and not config.deepseek_api_key) or
        (config.provider == "gemini" and not config.gemini_api_key)
    )
    if missing_key:
        print("No API key set. Add the provider-specific API key to config/.env.")
    else:
        llm = LLMInterface(config)

        # Test simple chat
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Say hello in one word."}
        ]

        response = llm.chat(messages)
        print(f"Response: {response}")
        print(f"Tokens used: {llm.total_tokens_used}")
        print(f"Status: {llm.get_status()}")
