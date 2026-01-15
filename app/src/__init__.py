"""
SlowHands - A Learning-Focused AI Coding Agent

This package contains the core components of SlowHands:
- agent: The main agent orchestrator
- llm: LLM interface for OpenAI
- memory: Conversation and state management
- tools: Modular tool implementations
- config: Configuration loading
"""

from .agent import Agent
from .config import Config

__version__ = "0.1.0"
__all__ = ["Agent", "Config"]
