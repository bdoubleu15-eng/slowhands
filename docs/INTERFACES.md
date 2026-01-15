# SlowHands Interface Contracts

This document defines all interfaces, data models, and contracts used in SlowHands.

## Core Interfaces

### Agent Interface

```python
from abc import ABC, abstractmethod
from typing import Generator
from dataclasses import dataclass

@dataclass
class AgentStep:
    """Represents a single step in the agent loop."""
    step_number: int
    phase: str  # "think", "act", "observe", "respond"
    content: str
    tool_call: Optional["ToolCall"] = None
    tool_result: Optional["ToolResult"] = None

class AgentInterface(ABC):
    """Abstract interface for the agent."""

    @abstractmethod
    def run(self, task: str) -> str:
        """
        Run the agent on a task until completion.

        Args:
            task: The user's request/task description

        Returns:
            The final response from the agent
        """
        pass

    @abstractmethod
    def step(self) -> AgentStep:
        """
        Execute a single step of the agent loop.

        Returns:
            AgentStep with details about what happened
        """
        pass

    @abstractmethod
    def stream(self, task: str) -> Generator[AgentStep, None, None]:
        """
        Stream agent steps as they happen.

        Yields:
            AgentStep for each step in the loop
        """
        pass

    @abstractmethod
    def reset(self) -> None:
        """Reset the agent state for a new task."""
        pass
```

### Tool Interface

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

@dataclass
class ToolResult:
    """Result of a tool execution."""
    success: bool
    output: str
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        if self.success:
            return self.output
        return f"Error: {self.error}"

@dataclass
class ToolCall:
    """Represents a request to call a tool."""
    tool_name: str
    arguments: Dict[str, Any]
    call_id: str  # Unique identifier for this call

class BaseTool(ABC):
    """Abstract base class for all tools."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique name for this tool."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Description shown to the LLM."""
        pass

    @property
    @abstractmethod
    def parameters(self) -> Dict[str, Any]:
        """JSON Schema for tool parameters."""
        pass

    @abstractmethod
    def execute(self, **kwargs) -> ToolResult:
        """
        Execute the tool with given arguments.

        Args:
            **kwargs: Tool-specific arguments

        Returns:
            ToolResult with success status and output
        """
        pass

    def validate(self, kwargs: Dict[str, Any]) -> bool:
        """Validate arguments against schema."""
        required = self.parameters.get("required", [])
        return all(key in kwargs for key in required)

    def format_for_llm(self) -> Dict[str, Any]:
        """Format tool for OpenAI function calling."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters
            }
        }
```

### LLM Interface

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class LLMResponse:
    """Response from the LLM."""
    content: Optional[str]
    tool_calls: List[ToolCall]
    finish_reason: str  # "stop", "tool_calls", "length"
    usage: Dict[str, int]  # token counts

class LLMInterface(ABC):
    """Abstract interface for LLM communication."""

    @abstractmethod
    def chat(self, messages: List["Message"]) -> str:
        """
        Simple chat completion.

        Args:
            messages: Conversation history

        Returns:
            The assistant's response text
        """
        pass

    @abstractmethod
    def chat_with_tools(
        self,
        messages: List["Message"],
        tools: List[BaseTool]
    ) -> LLMResponse:
        """
        Chat with tool-calling capability.

        Args:
            messages: Conversation history
            tools: Available tools

        Returns:
            LLMResponse with content and/or tool calls
        """
        pass
```

### Memory Interface

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Literal, Optional

@dataclass
class Message:
    """A single message in the conversation."""
    role: Literal["system", "user", "assistant", "tool"]
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    name: Optional[str] = None  # For tool messages
    tool_call_id: Optional[str] = None  # For tool results

    def to_openai_format(self) -> Dict[str, Any]:
        """Convert to OpenAI API format."""
        msg = {"role": self.role, "content": self.content}
        if self.name:
            msg["name"] = self.name
        if self.tool_call_id:
            msg["tool_call_id"] = self.tool_call_id
        return msg

class MemoryInterface(ABC):
    """Abstract interface for memory management."""

    @abstractmethod
    def add(self, message: Message) -> None:
        """Add a message to memory."""
        pass

    @abstractmethod
    def get_history(self, limit: Optional[int] = None) -> List[Message]:
        """Get conversation history."""
        pass

    @abstractmethod
    def get_context(self) -> str:
        """Get formatted context for the LLM."""
        pass

    @abstractmethod
    def clear(self) -> None:
        """Clear all memory."""
        pass

    @abstractmethod
    def save(self, path: str) -> None:
        """Persist memory to disk."""
        pass

    @abstractmethod
    def load(self, path: str) -> None:
        """Load memory from disk."""
        pass
```

---

## UI Widget Interfaces

### Base Widget Interface

```python
from abc import ABC, abstractmethod
from textual.widget import Widget
from textual.reactive import reactive
from rich.text import Text

class StatusWidgetInterface(ABC):
    """Interface for status display widgets."""
    
    status: reactive[str]
    
    @abstractmethod
    def update_status(self, status: str, **kwargs) -> None:
        """Update the widget status."""
        pass
    
    @abstractmethod
    def render(self) -> Text:
        """Render the widget content."""
        pass
```

### Agent Status Widget

```python
from textual.widgets import Static
from textual.reactive import reactive
from textual.timer import Timer
from rich.text import Text

class AgentStatusWidget(Static):
    """Rich status widget showing agent state with animations."""
    
    # Reactive properties auto-refresh on change
    status: reactive[str] = reactive("idle")
    step: reactive[int] = reactive(0)
    tokens: reactive[int] = reactive(0)
    elapsed: reactive[float] = reactive(0.0)
    
    # Animation frames per status
    ANIMATIONS = {
        "idle": ["⬤", "⬤", "⬤"],
        "thinking": ["🧠", "💭", "💡", "🤔"],
        "acting": ["⚡", "🔧", "⚙️", "🛠️"],
        "responding": ["💬", "📝", "✍️", "📤"],
        "error": ["❌", "⚠️", "❌"],
        "success": ["✅", "🎉", "✅"],
    }
    
    def __init__(self, agent_name: str = "Agent", **kwargs):
        """
        Initialize the status widget.
        
        Args:
            agent_name: Display name for this agent
        """
        super().__init__(**kwargs)
        self.agent_name = agent_name
        self._animation_frame = 0
        self._timer: Optional[Timer] = None
    
    def on_mount(self) -> None:
        """Start animation timer on mount."""
        self._timer = self.set_interval(0.3, self._animate)
    
    def _animate(self) -> None:
        """Advance animation frame."""
        self._animation_frame += 1
        if self.status != "idle":
            self.refresh()
    
    def update_status(
        self, 
        status: str, 
        step: int = 0, 
        tokens: int = 0, 
        elapsed: float = 0.0
    ) -> None:
        """
        Update all status properties.
        
        Args:
            status: Current status (idle, thinking, acting, responding, error, success)
            step: Current step number
            tokens: Total tokens used
            elapsed: Elapsed time in seconds
        """
        self.status = status
        self.step = step
        self.tokens = tokens
        self.elapsed = elapsed
        self.refresh()
    
    def render(self) -> Text:
        """Render the status bar with animations."""
        frames = self.ANIMATIONS.get(self.status, self.ANIMATIONS["idle"])
        icon = frames[self._animation_frame % len(frames)]
        
        status_colors = {
            "idle": "dim white",
            "thinking": "yellow",
            "acting": "cyan",
            "responding": "green",
            "error": "red",
            "success": "green",
        }
        color = status_colors.get(self.status, "white")
        
        return Text.assemble(
            (f" {icon} ", ""),
            (self.agent_name, "bold"),
            ("  │  ", "dim"),
            (self.status.upper(), f"bold {color}"),
            ("  │  ", "dim"),
            ("Step ", "dim"),
            (f"{self.step}", "cyan"),
            ("  │  ", "dim"),
            ("Tokens ", "dim"),
            (f"{self.tokens:,}", "green"),
            ("  │  ", "dim"),
            ("Time ", "dim"),
            (f"{self.elapsed:.1f}s", "yellow"),
        )
```

### System Stats Widget

```python
from collections import deque
from textual.widgets import Static
from rich.table import Table

class SystemStatsWidget(Static):
    """Dashboard widget showing system statistics with sparklines."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.stats = {
            "cpu": deque([0] * 20, maxlen=20),
            "memory": deque([0] * 20, maxlen=20),
            "tokens_per_min": deque([0] * 20, maxlen=20),
        }
        self._timer: Optional[Timer] = None
    
    def on_mount(self) -> None:
        """Start stats update timer."""
        self._timer = self.set_interval(1.0, self._update_stats)
    
    def _update_stats(self) -> None:
        """Update stats (override for real data)."""
        # Default: simulate stats
        import random
        self.stats["cpu"].append(random.uniform(10, 40))
        self.stats["memory"].append(random.uniform(30, 50))
        self.refresh()
    
    def render(self) -> Table:
        """Render stats table with sparklines."""
        table = Table.grid(padding=(0, 1))
        table.add_column(justify="right", style="bold")
        table.add_column(justify="left")
        table.add_column(justify="left", style="cyan")
        
        bars = "▁▂▃▄▅▆▇█"
        
        for label, data in self.stats.items():
            if data:
                max_val = max(data) or 1
                sparkline = "".join(
                    bars[min(int(v / max_val * 7), 7)] 
                    for v in data
                )
                current = f"{list(data)[-1]:.0f}%"
            else:
                sparkline = "▁" * 20
                current = "0%"
            table.add_row(label.upper(), current, sparkline)
        
        return table
```

### Activity Log Widget

```python
from datetime import datetime
from textual.widgets import RichLog
from rich.text import Text

class ActivityLog(RichLog):
    """Scrollable activity log with timestamps and icons."""
    
    # Event type configuration
    ICONS = {
        "info": "ℹ️",
        "success": "✅",
        "warning": "⚠️",
        "error": "❌",
        "tool": "🔧",
        "think": "🧠",
        "speak": "💬",
        "file": "📄",
        "code": "💻",
    }
    
    COLORS = {
        "info": "blue",
        "success": "green",
        "warning": "yellow",
        "error": "red",
        "tool": "cyan",
        "think": "yellow",
        "speak": "green",
        "file": "magenta",
        "code": "cyan",
    }
    
    def __init__(self, **kwargs):
        super().__init__(highlight=True, markup=True, wrap=True, **kwargs)
    
    def log_event(
        self, 
        event_type: str, 
        message: str, 
        details: str = ""
    ) -> None:
        """
        Log an event with timestamp and formatting.
        
        Args:
            event_type: Type of event (info, success, error, tool, etc.)
            message: Main message text
            details: Optional additional details
        """
        timestamp = datetime.now().strftime("%H:%M:%S")
        icon = self.ICONS.get(event_type, "•")
        color = self.COLORS.get(event_type, "white")
        
        self.write(Text.assemble(
            (f"[{timestamp}] ", "dim"),
            (f"{icon} ", ""),
            (message, color),
            (f" {details}", "dim") if details else ("", ""),
        ))
```

### Context Panel Widget

```python
from typing import List
from textual.widgets import Static
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.console import Group

class ContextPanel(Static):
    """Panel showing current context and memory state."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.files_count = 0
        self.tools_count = 0
        self.conversation_count = 0
        self.memory_items: List[str] = []
    
    def update_context(
        self,
        files: int = 0,
        tools: int = 0,
        conversation: int = 0,
        memory: List[str] = None
    ) -> None:
        """
        Update context display.
        
        Args:
            files: Number of tracked files
            tools: Number of tool calls
            conversation: Number of messages
            memory: List of recent memory items
        """
        self.files_count = files
        self.tools_count = tools
        self.conversation_count = conversation
        self.memory_items = memory or []
        self.refresh()
    
    def render(self) -> Panel:
        """Render context panel with metrics and memory."""
        # Metrics grid
        table = Table.grid(padding=(0, 2))
        table.add_column(justify="center")
        table.add_column(justify="center")
        table.add_column(justify="center")
        
        table.add_row(
            Text.assemble(
                ("📁 ", ""), 
                (f"{self.files_count}", "cyan bold"), 
                ("\nFiles", "dim")
            ),
            Text.assemble(
                ("🔧 ", ""), 
                (f"{self.tools_count}", "green bold"), 
                ("\nTools", "dim")
            ),
            Text.assemble(
                ("💬 ", ""), 
                (f"{self.conversation_count}", "yellow bold"), 
                ("\nMsgs", "dim")
            ),
        )
        
        # Memory section
        memory_text = ""
        for item in self.memory_items[-3:]:
            truncated = f"{item[:40]}..." if len(item) > 40 else item
            memory_text += f"• {truncated}\n"
        
        content = Group(
            table,
            Text("\n"),
            Text("Recent Memory:", style="bold underline"),
            Text(memory_text if memory_text else "(empty)", style="dim"),
        )
        
        return Panel(
            content,
            title="📊 Context",
            border_style="blue",
            padding=(0, 1),
        )
```

### Command Palette (Modal)

```python
from textual.screen import ModalScreen
from textual.widgets import Input, Static
from textual.containers import Vertical
from textual.binding import Binding
from textual import on
from rich.text import Text

class CommandPalette(ModalScreen):
    """Modal command palette for quick actions."""
    
    BINDINGS = [
        Binding("escape", "dismiss", "Close"),
    ]
    
    COMMANDS = [
        ("reset", "Reset all agents", "🔄"),
        ("clear", "Clear current pane", "🧹"),
        ("files", "Show project files", "📁"),
        ("tools", "Show tool history", "🔧"),
        ("help", "Show help", "❓"),
        ("theme", "Toggle theme", "🎨"),
        ("export", "Export conversation", "💾"),
        ("quit", "Quit application", "🚪"),
    ]
    
    def compose(self) -> ComposeResult:
        """Compose the palette UI."""
        with Vertical(id="palette-container"):
            yield Input(placeholder="Type a command...", id="palette-input")
            yield Static(id="palette-results")
    
    def on_mount(self) -> None:
        """Focus input and show all commands."""
        self.query_one("#palette-input").focus()
        self._update_results("")
    
    @on(Input.Changed, "#palette-input")
    def filter_commands(self, event: Input.Changed) -> None:
        """Filter commands as user types."""
        self._update_results(event.value)
    
    def _update_results(self, query: str) -> None:
        """Update displayed commands based on query."""
        results = self.query_one("#palette-results", Static)
        
        filtered = [
            cmd for cmd in self.COMMANDS 
            if query.lower() in cmd[0].lower() 
            or query.lower() in cmd[1].lower()
        ]
        
        if not filtered:
            results.update("[dim]No commands found[/dim]")
            return
        
        text = Text()
        for cmd, desc, icon in filtered[:8]:
            text.append(f"\n  {icon} ", style="")
            text.append(cmd, style="bold cyan")
            text.append(f"  {desc}", style="dim")
        
        results.update(text)
    
    @on(Input.Submitted, "#palette-input")
    def execute_command(self, event: Input.Submitted) -> None:
        """Execute selected command."""
        cmd = event.value.strip().lower()
        self.dismiss(cmd)  # Return command to caller
```

---

## Teacher Agent Interface

```python
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class TeacherResponse:
    """Response from the teacher agent."""
    answer: str
    sources: List[str] = field(default_factory=list)
    confidence: float = 1.0

class TeacherAgentInterface(ABC):
    """Interface for the teacher/explainer agent."""
    
    @abstractmethod
    def ask(self, question: str) -> TeacherResponse:
        """
        Ask the teacher a question.
        
        Args:
            question: User's question about code/project
            
        Returns:
            TeacherResponse with answer and sources
        """
        pass
    
    @abstractmethod
    def explain_step(self, step: AgentStep) -> str:
        """
        Explain what happened in an agent step.
        
        Args:
            step: The step to explain
            
        Returns:
            Human-readable explanation
        """
        pass
    
    @abstractmethod
    def reset(self) -> None:
        """Reset teacher state."""
        pass
```

---

## Project Context Interface

```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

@dataclass
class FileState:
    """State of a tracked file."""
    path: str
    last_modified: datetime
    content_hash: str
    size: int

@dataclass
class ToolHistoryEntry:
    """Record of a tool call."""
    tool_name: str
    arguments: Dict[str, Any]
    result: str
    success: bool
    timestamp: datetime = field(default_factory=datetime.now)

class ProjectContextInterface(ABC):
    """Interface for project context management."""
    
    @abstractmethod
    def scan_project(self) -> None:
        """Scan and index project files."""
        pass
    
    @abstractmethod
    def get_file_state(self, path: str) -> Optional[FileState]:
        """Get state of a specific file."""
        pass
    
    @abstractmethod
    def add_tool_call(
        self, 
        tool_name: str, 
        arguments: Dict, 
        result: str, 
        success: bool
    ) -> None:
        """Record a tool call."""
        pass
    
    @abstractmethod
    def get_recent_tools(self, limit: int = 10) -> List[ToolHistoryEntry]:
        """Get recent tool calls."""
        pass
    
    @abstractmethod
    def get_summary(self) -> str:
        """Get formatted context summary for LLM."""
        pass
```

---

## Data Models

### Configuration

```python
from dataclasses import dataclass, field
from typing import List, Literal, Optional

@dataclass
class Config:
    """Application configuration."""

    # Provider Settings
    provider: Literal["openai", "anthropic", "deepseek"] = "openai"
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    deepseek_api_key: Optional[str] = None
    
    # Model Settings
    model: str = "gpt-4"
    temperature: float = 0.7
    max_tokens: int = 4096

    # Agent Settings
    slow_mode: bool = True
    pause_duration: float = 2.0
    max_iterations: int = 10
    verbose: bool = True

    # Memory Settings
    max_history_length: int = 50
    persist_memory: bool = False
    memory_file: str = "memory.json"

    # Safety Settings
    allow_code_execution: bool = True
    allowed_paths: List[str] = field(default_factory=lambda: ["."])

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables."""
        from os import getenv
        return cls(
            provider=getenv("LLM_PROVIDER", "openai"),
            openai_api_key=getenv("OPENAI_API_KEY"),
            anthropic_api_key=getenv("ANTHROPIC_API_KEY"),
            deepseek_api_key=getenv("DEEPSEEK_API_KEY"),
            model=getenv("MODEL_NAME", "gpt-4"),
            slow_mode=getenv("SLOW_MODE", "true").lower() == "true",
            pause_duration=float(getenv("PAUSE_DURATION", "2.0")),
        )
```

---

## Event Types

```python
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Literal

@dataclass
class AgentEvent:
    """Event emitted during agent execution."""
    event_type: Literal[
        "task_started",
        "thinking",
        "tool_called",
        "tool_result",
        "response",
        "error",
        "task_completed"
    ]
    timestamp: datetime
    data: Dict[str, Any]

    def to_log_format(self) -> str:
        """Format for logging."""
        return f"[{self.timestamp}] {self.event_type}: {self.data}"

@dataclass
class UIEvent:
    """Event for UI updates."""
    event_type: Literal[
        "status_changed",
        "step_received",
        "message_added",
        "context_updated",
        "error_occurred"
    ]
    source: str  # "coder" or "teacher"
    data: Dict[str, Any]
```

---

## Error Types

```python
class SlowHandsError(Exception):
    """Base exception for SlowHands."""
    pass

class ConfigurationError(SlowHandsError):
    """Invalid configuration."""
    pass

class ToolExecutionError(SlowHandsError):
    """Tool failed to execute."""
    def __init__(self, tool_name: str, message: str):
        self.tool_name = tool_name
        super().__init__(f"Tool '{tool_name}' failed: {message}")

class LLMError(SlowHandsError):
    """LLM API error."""
    pass

class MaxIterationsError(SlowHandsError):
    """Agent exceeded maximum iterations."""
    pass

class UIError(SlowHandsError):
    """UI rendering or interaction error."""
    pass
```

---

## Interface Diagram

```mermaid
classDiagram
    class AgentInterface {
        <<interface>>
        +run(task) str
        +step() AgentStep
        +stream(task) Generator
        +reset() void
    }

    class TeacherAgentInterface {
        <<interface>>
        +ask(question) TeacherResponse
        +explain_step(step) str
        +reset() void
    }

    class BaseTool {
        <<abstract>>
        +name str
        +description str
        +parameters dict
        +execute(**kwargs) ToolResult
        +validate(kwargs) bool
        +format_for_llm() dict
    }

    class LLMInterface {
        <<interface>>
        +chat(messages) str
        +chat_with_tools(messages, tools) LLMResponse
    }

    class MemoryInterface {
        <<interface>>
        +add(message) void
        +get_history(limit) List
        +get_context() str
        +clear() void
    }

    class ProjectContextInterface {
        <<interface>>
        +scan_project() void
        +add_tool_call(...) void
        +get_recent_tools(limit) List
        +get_summary() str
    }

    class AgentStatusWidget {
        +status str
        +step int
        +tokens int
        +update_status(...) void
        +render() Text
    }

    class ActivityLog {
        +log_event(type, msg) void
        +write(content) void
    }

    class CommandPalette {
        +COMMANDS List
        +compose() ComposeResult
        +filter_commands(query) void
    }

    AgentInterface --> LLMInterface : uses
    AgentInterface --> MemoryInterface : uses
    AgentInterface --> BaseTool : registers
    AgentInterface --> ProjectContextInterface : shares
    TeacherAgentInterface --> ProjectContextInterface : reads
```

---

*These interfaces define the contracts between components. Implementations can vary as long as they satisfy these interfaces.*
