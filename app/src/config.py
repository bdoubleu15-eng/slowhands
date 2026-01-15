"""
Configuration Module

Loads settings from environment variables and .env file.
This is the first file to understand - it's simple and foundational.
"""

import os
from dataclasses import dataclass, field
from typing import List, Optional
from pathlib import Path

# Load .env file if it exists
from dotenv import load_dotenv
PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = PROJECT_ROOT / "config" / ".env"
load_dotenv(dotenv_path=ENV_PATH)


@dataclass
class Config:
    """
    Application configuration.

    All settings are loaded from environment variables.
    See .env.example for available options.
    """

    # === API Settings ===
    provider: str = "gemini"  # "openai", "anthropic", "deepseek", "gemini"
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    deepseek_api_key: str = ""
    gemini_api_key: str = ""
    model: str = "gemini-3-pro-preview"
    temperature: float = 0.7
    max_tokens: int = 4096

    # === Agent Settings ===
    slow_mode: bool = True          # Show step-by-step execution
    pause_duration: float = 2.0      # Seconds between steps
    max_iterations: int = 10         # Safety limit
    verbose: bool = True             # Detailed logging

    # === Memory Settings ===
    max_history_length: int = 50
    persist_memory: bool = False
    memory_file: str = "memory.json"

    # === Safety Settings ===
    allow_code_execution: bool = True
    allowed_paths: List[str] = field(default_factory=lambda: ["."])

    # === Reliability Settings ===
    request_timeout: float = 60.0           # Seconds before API request timeout
    retry_attempts: int = 3                 # Max retry attempts for failed API calls
    retry_min_wait: float = 1.0             # Min seconds between retries
    retry_max_wait: float = 60.0            # Max seconds between retries
    rate_limit_rpm: int = 60                # Max requests per minute (0 = disabled)
    rate_limit_tpm: int = 90000             # Max tokens per minute (0 = disabled)
    circuit_breaker_threshold: int = 5      # Failures before circuit opens
    circuit_breaker_timeout: float = 60.0   # Seconds before circuit resets
    
    # === Tool Retry Settings ===
    tool_retry_attempts: int = 3            # Max retry attempts for failed tool calls
    tool_retry_min_wait: float = 1.0        # Min seconds between tool retries
    tool_retry_max_wait: float = 10.0      # Max seconds between tool retries
    message_queue_max_size: int = 100       # Max size of message queue

    @classmethod
    def from_env(cls) -> "Config":
        """
        Load configuration from environment variables.

        This is the main way to create a Config object.
        Environment variables override defaults.
        """
        def get_bool(key: str, default: bool) -> bool:
            """Helper to parse boolean env vars."""
            value = os.getenv(key, str(default)).lower()
            return value in ("true", "1", "yes")

        def get_float(key: str, default: float) -> float:
            """Helper to parse float env vars."""
            try:
                return float(os.getenv(key, default))
            except ValueError:
                return default

        def get_int(key: str, default: int) -> int:
            """Helper to parse int env vars."""
            try:
                return int(os.getenv(key, default))
            except ValueError:
                return default

        return cls(
            # API
            provider=os.getenv("LLM_PROVIDER", "gemini"),
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
            deepseek_api_key=os.getenv("DEEPSEEK_API_KEY", ""),
            gemini_api_key=os.getenv("GEMINI_API_KEY", ""),
            model=os.getenv("MODEL", "gemini-3-pro-preview"),
            temperature=get_float("TEMPERATURE", 0.7),
            max_tokens=get_int("MAX_TOKENS", 4096),

            # Agent
            slow_mode=get_bool("SLOW_MODE", True),
            pause_duration=get_float("PAUSE_DURATION", 2.0),
            max_iterations=get_int("MAX_ITERATIONS", 10),
            verbose=get_bool("VERBOSE", True),

            # Memory
            max_history_length=get_int("MAX_HISTORY_LENGTH", 50),
            persist_memory=get_bool("PERSIST_MEMORY", False),

            # Safety
            allow_code_execution=get_bool("ALLOW_CODE_EXECUTION", True),

            # Reliability
            request_timeout=get_float("REQUEST_TIMEOUT", 60.0),
            retry_attempts=get_int("RETRY_ATTEMPTS", 3),
            retry_min_wait=get_float("RETRY_MIN_WAIT", 1.0),
            retry_max_wait=get_float("RETRY_MAX_WAIT", 60.0),
            rate_limit_rpm=get_int("RATE_LIMIT_RPM", 60),
            rate_limit_tpm=get_int("RATE_LIMIT_TPM", 90000),
            circuit_breaker_threshold=get_int("CIRCUIT_BREAKER_THRESHOLD", 5),
            circuit_breaker_timeout=get_float("CIRCUIT_BREAKER_TIMEOUT", 60.0),
            
            # Tool Retry
            tool_retry_attempts=get_int("TOOL_RETRY_ATTEMPTS", 3),
            tool_retry_min_wait=get_float("TOOL_RETRY_MIN_WAIT", 1.0),
            tool_retry_max_wait=get_float("TOOL_RETRY_MAX_WAIT", 10.0),
            message_queue_max_size=get_int("MESSAGE_QUEUE_MAX_SIZE", 100),
        )

    def validate(self) -> List[str]:
        """
        Validate the configuration.

        Returns:
            List of error messages (empty if valid)
        """
        errors = []

        # Validate provider
        valid_providers = ["openai", "anthropic", "deepseek", "gemini"]
        if self.provider not in valid_providers:
            errors.append(f"LLM_PROVIDER must be one of: {', '.join(valid_providers)}")

        # Validate API key based on provider
        if self.provider == "openai" and not self.openai_api_key:
            errors.append("OPENAI_API_KEY is required when using OpenAI provider.")
        elif self.provider == "anthropic" and not self.anthropic_api_key:
            errors.append("ANTHROPIC_API_KEY is required when using Anthropic provider.")
        elif self.provider == "deepseek" and not self.deepseek_api_key:
            errors.append("DEEPSEEK_API_KEY is required when using DeepSeek provider.")
        elif self.provider == "gemini" and not self.gemini_api_key:
            errors.append("GEMINI_API_KEY is required when using Gemini provider.")

        if self.temperature < 0 or self.temperature > 2:
            errors.append("TEMPERATURE must be between 0 and 2")

        if self.max_iterations < 1:
            errors.append("MAX_ITERATIONS must be at least 1")

        return errors

    def __post_init__(self):
        """Validate after initialization."""
        errors = self.validate()
        if errors:
            # Only raise error if we have an API key (meaning we're trying to use the agent)
            has_api_key = any([
                self.openai_api_key,
                self.anthropic_api_key,
                self.deepseek_api_key,
                self.gemini_api_key
            ])
            if has_api_key:
                raise ValueError(f"Configuration errors: {errors}")


# === Convenience function ===

def load_config() -> Config:
    """
    Load configuration from environment.

    Usage:
        from src.config import load_config
        config = load_config()
    """
    return Config.from_env()


# === For testing/debugging ===

if __name__ == "__main__":
    # Run this file directly to see current config
    config = load_config()
    print("Current Configuration:")
    print(f"  Provider: {config.provider}")
    print(f"  Model: {config.model}")
    print(f"  Slow Mode: {config.slow_mode}")
    print(f"  Pause Duration: {config.pause_duration}s")
    print(f"  Max Iterations: {config.max_iterations}")
    api_key_set = (
        config.openai_api_key or 
        config.anthropic_api_key or 
        config.deepseek_api_key or 
        config.gemini_api_key
    )
    print(f"  API Key Set: {'Yes' if api_key_set else 'No'}")
