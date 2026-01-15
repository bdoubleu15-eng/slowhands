# 🖐️ SlowHands - Learning AI Agent

A beautiful, educational AI agent with **tmux-style terminal UI** and **modern web interface** that shows you exactly how AI thinks, acts, and responds step-by-step.

```
╔═══════════════════════════════════════════════════════════════════════════════╗
║                                                                               ║
║   🤖 CODER AGENT              │  👨‍🏫 TEACHER AGENT                             ║
║   ─────────────────────────── │  ────────────────────────────                 ║
║   🧠 Thinking (Step 1)...     │  📚 Ask me anything!                          ║
║   ⚡ Using tool: file_ops     │                                               ║
║   ✅ File created             │  Q: What is the agent doing?                  ║
║   💬 Response generated       │  A: It's writing a Python file...             ║
║                               │                                               ║
║   ▌Enter coding task...       │  ▌Ask a question...                           ║
║                               │                                               ║
╚═══════════════════════════════════════════════════════════════════════════════╝
```

## ✨ Features

### Terminal UI (Textual)
- **Tmux-style split panes** - Coder agent on left, Teacher on right
- **Real-time streaming** - Watch text appear character by character
- **Command palette** - Press `Ctrl+P` for quick actions
- **System stats dashboard** - CPU, Memory, Token sparklines
- **Activity logging** - Timestamped events with icons
- **Syntax highlighting** - Beautiful code display
- **Animated status** - Icons animate while thinking/acting

### Web UI (Streamlit)
- **Modern dark theme** - Beautiful gradient backgrounds
- **Streaming effects** - Animated cursor while typing
- **Live metrics** - Files, tools, tokens, time
- **Activity sidebar** - Recent events log
- **Step visualization** - Expandable step cards
- **Context panel** - See what the agent knows

## 🚀 Quick Start

### 1. Install Dependencies

```bash
cd slowhands
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows
pip install -r app/requirements.txt
```

### 2. Configure API Key

Create a `config/.env` file:
```bash
GEMINI_API_KEY=your-key-here
# Or for other providers:
# OPENAI_API_KEY=sk-...
# ANTHROPIC_API_KEY=sk-ant-...
# DEEPSEEK_API_KEY=sk-...
```

### 3. Launch the UI

**Terminal UI (recommended):**
```bash
python app/run_ui.py
```

**Web UI:**
```bash
python app/run_ui.py --web
# Or directly:
streamlit run app/ui/streamlit_app.py
```

## ⌨️ Keyboard Shortcuts (Terminal UI)

| Key | Action |
|-----|--------|
| `Ctrl+P` | Command palette |
| `Ctrl+R` | Reset agents |
| `Ctrl+L` | Clear current pane |
| `Tab` | Switch panes |
| `F1` | Help screen |
| `Ctrl+C` | Quit |

## 🎨 UI Components

### Terminal Widgets

```python
# Status widget with animated icons
AgentStatusWidget("Coder")  # Shows: 🧠 CODER │ THINKING │ Step 3 │ Tokens 1,234

# System stats with sparklines
SystemStatsWidget()  # Shows: CPU 23% ▂▃▅▆▃▂▁ MEM 45% ▄▄▅▅▆▆▅

# Activity log with timestamps
ActivityLog()  # Shows: [14:23:01] 🔧 Using tool: file_ops

# Context panel with memory visualization
ContextPanel()  # Shows files, tools, messages counts
```

### Web UI Features

- **Streaming text** - Characters appear with cursor effect
- **Step cards** - Color-coded by phase (think/act/respond)
- **Metrics row** - Live updating stats
- **Collapsible context** - See recent activity
- **Source citations** - Teacher shows references

## 📁 Project Structure

```
slowhands/
├── app/
│   ├── ui/
│   │   ├── terminal_app.py     # Textual TUI (tmux-style)
│   │   ├── streamlit_app.py    # Streamlit web UI
│   │   └── themes/
│   │       └── default.tcss    # Terminal theme CSS
│   ├── src/
│   │   ├── agent.py            # Core agent logic
│   │   ├── context_agent.py    # Context-aware agent
│   │   ├── teacher.py          # Teacher agent
│   │   ├── context.py          # Project context
│   │   ├── config.py           # Configuration
│   │   └── tools/              # Agent tools
│   ├── run_ui.py               # UI launcher
│   └── requirements.txt        # Dependencies
├── config/
│   └── .env                    # API keys (create this)
├── docs/
├── examples/
└── debug/
```

## 🔧 Configuration

Edit `.env` or use the sidebar in the web UI:

```bash
# LLM Provider (openai, anthropic, deepseek)
LLM_PROVIDER=openai

# Model settings
MODEL_NAME=gpt-4
MAX_TOKENS=4096
TEMPERATURE=0.7

# UI settings
SLOW_MODE=true
PAUSE_DURATION=1.5
```

## 🤖 Using the Agents

### Coder Agent
Give it coding tasks:
- "Create a Python function to calculate factorial"
- "Write a Flask API with user authentication"
- "Refactor this code to use async/await"

Watch it:
1. 🧠 **Think** - Plan the approach
2. ⚡ **Act** - Use tools (file_ops, code_runner, etc.)
3. 📊 **Observe** - See tool results
4. 💬 **Respond** - Get the final answer

### Teacher Agent
Ask questions:
- "What is the agent doing?"
- "Explain how Python decorators work"
- "What files were created?"

Special commands:
- `!files` - List project files
- `!tools` - Show recent tool calls
- `!tree` - Show file tree
- `!help` - Show all commands

## 📚 Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         User Interface                          │
│  ┌─────────────────────┐  ┌─────────────────────┐               │
│  │   Terminal (TUI)    │  │    Web (Streamlit)  │               │
│  │   • Textual         │  │    • Dark theme     │               │
│  │   • Tmux-style      │  │    • Streaming      │               │
│  └─────────────────────┘  └─────────────────────┘               │
└─────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────────┐
│                          Agent Layer                            │
│  ┌─────────────────────┐  ┌─────────────────────┐               │
│  │   Coder Agent       │  │   Teacher Agent     │               │
│  │   • Context-aware   │  │   • Explains code   │               │
│  │   • Tool usage      │  │   • Answers Qs      │               │
│  └─────────────────────┘  └─────────────────────┘               │
└─────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────────┐
│                         Core Services                           │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐        │
│  │  Config  │  │  Context │  │   LLM    │  │  Tools   │        │
│  │  .env    │  │  Memory  │  │  Client  │  │  Suite   │        │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘        │
└─────────────────────────────────────────────────────────────────┘
```

## 🎯 Educational Purpose

SlowHands is designed to help you understand how AI agents work by:

1. **Showing the process** - Not just the result, but each step
2. **Explaining as it goes** - Teacher agent provides context
3. **Visual feedback** - Animations make it engaging
4. **Open source** - Explore and modify the code

## 📝 License

MIT License - Feel free to use, modify, and learn from this project!

---

<p align="center">
  Made with 🖐️ by developers who like to take it slow
</p>
