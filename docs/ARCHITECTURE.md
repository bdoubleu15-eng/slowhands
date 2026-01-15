# SlowHands Architecture

This document describes the high-level logical architecture of SlowHands, a learning-focused AI coding agent with a VS Code-style desktop interface.

## System Overview

```mermaid
graph TB
    subgraph "User Interface Layer"
        Desktop[Electron Desktop App<br/>Monaco Editor]
    end

    subgraph "API Layer"
        Server[FastAPI Server<br/>HTTP + WebSocket]
    end

    subgraph "Agent Layer"
        Agent[Coder Agent<br/>Think-Act-Observe Loop]
    end

    subgraph "Core Services"
        Config[Configuration]
        LLM[LLM Interface<br/>Gemini]
        Memory[Memory Store]
    end

    subgraph "Capabilities"
        Tools[Tool Registry]
        FileOps[File Operations]
        CodeRunner[Code Runner]
    end

    Desktop -->|WebSocket| Server
    Server --> Agent
    
    Agent --> LLM
    Agent --> Tools
    Agent --> Memory
    
    Tools --> FileOps
    Tools --> CodeRunner
    
    LLM --> Config
```

## Communication Architecture

The frontend and backend communicate via HTTP and WebSocket:

```mermaid
sequenceDiagram
    participant UI as Electron Frontend
    participant WS as WebSocket
    participant API as FastAPI Server
    participant Agent as Python Agent
    participant LLM as Gemini API

    UI->>WS: Connect on startup
    Note over UI,WS: ws://127.0.0.1:8765/ws
    
    UI->>WS: {type: "chat", content: "..."}
    WS->>API: Handle message
    API->>Agent: stream(message)
    
    loop Agent Loop
        Agent->>LLM: Generate response
        LLM-->>Agent: Tokens
        Agent-->>API: AgentStep
        API-->>WS: {type: "step", ...}
        WS-->>UI: Update output
    end
    
    Agent-->>API: Final response
    API-->>WS: {type: "complete", ...}
    WS-->>UI: Show result
```

## API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/health` | Server health check |
| POST | `/agent/chat` | Synchronous chat (waits for full response) |
| POST | `/agent/stream` | Start streaming response |
| POST | `/agent/reset` | Reset conversation history |
| WS | `/ws` | Real-time bidirectional communication |

### WebSocket Message Types

**Client to Server:**
```json
{"type": "chat", "content": "Your message here"}
{"type": "ping"}
```

**Server to Client:**
```json
{"type": "step", "step_number": 1, "phase": "think", "content": "..."}
{"type": "complete", "step_number": 3, "phase": "complete", "content": "..."}
{"type": "error", "content": "Error message"}
{"type": "pong"}
```

## User Interface Architecture

SlowHands provides a VS Code-style desktop interface built with Electron and Monaco Editor:

```mermaid
graph TB
    subgraph "Desktop UI Components"
        App[SlowHands Electron App]
        
        subgraph "Layout"
            TitleBar[Title Bar + Toolbar]
            ActivityBar[Activity Bar]
            Sidebar[Sidebar + Agent Panel]
            Editor[Monaco Editor]
            StatusBar[Status Bar]
        end
        
        subgraph "Sidebar Components"
            Explorer[File Explorer]
            AgentPanel[Agent Chat Panel]
            AgentInput[Message Input]
            AgentOutput[Response Output]
        end
    end

    App --> TitleBar
    App --> ActivityBar
    App --> Sidebar
    App --> Editor
    App --> StatusBar
    
    Sidebar --> Explorer
    Sidebar --> AgentPanel
    AgentPanel --> AgentInput
    AgentPanel --> AgentOutput
```

### Key UI Features

| Component | Purpose |
|-----------|---------|
| Title Bar | Draggable window area + File/Edit/View/Help menus |
| Activity Bar | Navigation icons (Explorer, Search, Debug) |
| Sidebar | Resizable file explorer + agent chat panel |
| Agent Panel | Input for messages, shows last 2 output lines |
| Monaco Editor | Full VS Code editor with syntax highlighting |
| Status Bar | Connection status, model info |

### Theme (Light)

```css
:root {
    --bg-titlebar: #f0f0f0;
    --bg-activity-bar: #f3f3f3;
    --bg-sidebar: #f8f8f8;
    --bg-editor: #ffffff;
    --bg-statusbar: #0078d4;
    --text-primary: #1e1e1e;
    --accent: #0078d4;
}
```

## The Agent Loop

The core reasoning loop follows Think → Act → Observe pattern:

```mermaid
flowchart TD
    Start([User Input]) --> Think

    subgraph Loop["Agent Loop"]
        Think[/"THINK<br/>LLM analyzes task<br/>and decides next action"/]
        Think --> Decide{Need to<br/>use a tool?}

        Decide -->|Yes| Act[/"ACT<br/>Execute the<br/>selected tool"/]
        Act --> Observe[/"OBSERVE<br/>Process tool result<br/>Update memory"/]
        Observe --> Think

        Decide -->|No| Respond[/"RESPOND<br/>Generate final<br/>answer"/]
    end

    Respond --> End([Output to User])
```

## Configuration

```mermaid
graph TD
    ENV[config/.env file] --> Config
    Defaults[Default values] --> Config
    
    Config --> Server
    Config --> Agent
    Config --> LLM
```

### Configuration Options

| Option | Default | Description |
|--------|---------|-------------|
| `LLM_PROVIDER` | gemini | LLM provider (openai, anthropic, deepseek, gemini) |
| `GEMINI_API_KEY` | - | Your Gemini API key |
| `MODEL` | gemini-2.0-flash | Model to use |
| `MAX_ITERATIONS` | 10 | Loop safety limit |
| `REQUEST_TIMEOUT` | 60.0 | API request timeout in seconds |

## File Map

| File | Responsibility |
|------|----------------|
| **Backend** | |
| `app/src/server.py` | FastAPI server with WebSocket |
| `app/src/agent.py` | Agent loop logic |
| `app/src/llm.py` | LLM API communication (Gemini) |
| `app/src/config.py` | Configuration loading |
| `app/src/memory.py` | Conversation history |
| `app/src/tools/base.py` | Tool base class |
| `app/src/tools/file_ops.py` | File operations |
| `app/src/tools/code_runner.py` | Code execution |
| `app/run_server.py` | Server entry point |
| **Frontend** | |
| `frontend/electron/main.ts` | Electron main process |
| `frontend/electron/preload.ts` | Electron preload script |
| `frontend/src/main.ts` | Monaco editor + WebSocket client |
| `frontend/src/style.css` | Light theme styles |
| `frontend/index.html` | UI layout |

## Running the Application

### 1. Start the Python Backend

```bash
cd app
pip install -r requirements.txt
python run_server.py
```

Server runs on `http://127.0.0.1:8765`

### 2. Start the Electron Frontend

```bash
cd frontend
npm install
npm run dev
```

## Future Extensions

```mermaid
graph TB
    Current[Current Features]
    
    Current --> UI[UI Enhancements]
    Current --> Agents[More Agents]
    Current --> Tools[More Tools]
    
    UI --> Themes[Custom Themes]
    UI --> Tabs[Multi-Tab Editor]
    UI --> Terminal[Integrated Terminal]
    
    Agents --> Planner[Planner Agent]
    Agents --> Reviewer[Code Reviewer]
    Agents --> Tester[Test Writer]
    
    Tools --> Git[Git Operations]
    Tools --> Search[Web Search]
    Tools --> DB[Database Access]
```

---

*View this file in Obsidian or [Mermaid Live Editor](https://mermaid.live) to see the diagrams rendered.*
