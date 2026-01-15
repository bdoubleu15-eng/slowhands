"""
Memory Module

Manages conversation history and working memory.
This is like the agent's "short-term memory" - it remembers
what's been said and done in the current session.
"""

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import List, Literal, Optional, Dict, Any
from pathlib import Path


@dataclass
class Message:
    """
    A single message in the conversation.

    This matches the OpenAI message format, making it easy
    to send to the LLM.
    """
    role: Literal["system", "user", "assistant", "tool"]
    content: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    # Optional fields for tool messages
    name: Optional[str] = None           # Tool name (for tool messages)
    tool_call_id: Optional[str] = None   # Links tool result to tool call
    tool_calls: Optional[List[Dict[str, Any]]] = None  # Tool calls from assistant

    def to_openai_format(self) -> Dict[str, Any]:
        """
        Convert to OpenAI API format.

        The API expects a specific format - this handles the conversion.
        """
        msg: Dict[str, Any] = {
            "role": self.role,
            "content": self.content
        }

        # Add optional fields if present
        if self.name:
            msg["name"] = self.name
        if self.tool_call_id:
            msg["tool_call_id"] = self.tool_call_id
        if self.tool_calls:
            msg["tool_calls"] = self.tool_calls

        return msg

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Message":
        """Create from dictionary."""
        return cls(**data)


class Memory:
    """
    Manages conversation history and working memory.

    Key concepts:
    - messages: The conversation history (what's been said)
    - working_memory: Temporary data for current task (like a scratchpad)

    In slow mode, we'll display each message as it's added
    so you can follow along.
    """

    def __init__(self, max_history: int = 50):
        """
        Initialize memory.

        Args:
            max_history: Maximum number of messages to keep
                         (prevents memory from growing too large)
        """
        self.messages: List[Message] = []
        self.working_memory: Dict[str, Any] = {}
        self.max_history = max_history

        # System message - sets the agent's behavior
        self._system_message: Optional[Message] = None

    def set_system_message(self, content: str) -> None:
        """
        Set the system message.

        The system message tells the LLM how to behave.
        It's always included at the start of the conversation.
        """
        self._system_message = Message(role="system", content=content)

    def add(self, message: Message) -> None:
        """
        Add a message to memory.

        This is called after every interaction:
        - User sends a message → add it
        - Assistant responds → add it
        - Tool returns result → add it
        """
        self.messages.append(message)

        # Trim old messages if we exceed max
        if len(self.messages) > self.max_history:
            # Keep the most recent messages
            self.messages = self.messages[-self.max_history:]

    def add_user_message(self, content: str) -> None:
        """Convenience method to add a user message."""
        self.add(Message(role="user", content=content))

    def add_assistant_message(self, content: str) -> None:
        """Convenience method to add an assistant message."""
        self.add(Message(role="assistant", content=content))

    def add_assistant_tool_calls(self, content: str, tool_calls: List[Dict[str, Any]]) -> None:
        """Add an assistant message that includes tool calls."""
        self.add(Message(role="assistant", content=content or "", tool_calls=tool_calls))

    def add_tool_result(self, tool_name: str, result: str, call_id: str) -> None:
        """
        Add a tool result to memory.

        Args:
            tool_name: Name of the tool that was called
            result: The tool's output
            call_id: ID linking this to the tool call
        """
        self.add(Message(
            role="tool",
            content=result,
            name=tool_name,
            tool_call_id=call_id
        ))

    def get_history(self, limit: Optional[int] = None) -> List[Message]:
        """
        Get conversation history.

        Args:
            limit: Max messages to return (None = all)

        Returns:
            List of messages, oldest first
        """
        if limit:
            return self.messages[-limit:]
        return self.messages.copy()

    def get_messages_for_llm(self) -> List[Dict[str, Any]]:
        """
        Get messages formatted for the OpenAI API.

        This includes the system message at the start.
        """
        messages = []

        # Always include system message first
        if self._system_message:
            messages.append(self._system_message.to_openai_format())

        # Add conversation history
        for msg in self.messages:
            messages.append(msg.to_openai_format())

        return messages

    def clear(self) -> None:
        """Clear all messages (but keep system message)."""
        self.messages = []
        self.working_memory = {}

    def save(self, path: str) -> None:
        """
        Save memory to a JSON file.

        Useful for persisting conversations between sessions.
        """
        data = {
            "system_message": self._system_message.to_dict() if self._system_message else None,
            "messages": [msg.to_dict() for msg in self.messages],
            "working_memory": self.working_memory
        }

        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    def load(self, path: str) -> None:
        """Load memory from a JSON file."""
        if not Path(path).exists():
            return

        with open(path, "r") as f:
            data = json.load(f)

        if data.get("system_message"):
            self._system_message = Message.from_dict(data["system_message"])

        self.messages = [Message.from_dict(m) for m in data.get("messages", [])]
        self.working_memory = data.get("working_memory", {})

    def __len__(self) -> int:
        """Number of messages in memory."""
        return len(self.messages)

    def __str__(self) -> str:
        """String representation for debugging."""
        return f"Memory({len(self.messages)} messages)"


# === For testing/debugging ===

if __name__ == "__main__":
    # Demo the memory system
    memory = Memory()

    memory.set_system_message("You are a helpful coding assistant.")
    memory.add_user_message("Hello!")
    memory.add_assistant_message("Hi! How can I help you today?")

    print("Messages for LLM:")
    for msg in memory.get_messages_for_llm():
        print(f"  [{msg['role']}]: {msg['content'][:50]}...")
