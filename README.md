# SlowHands

An AI coding assistant that shows its work - watch the one agent code in real-time, while the other explains the why's and how's and whatever's of the code to you. I know nothing about coding, so this has been a fun project for me! AND YES I KNOW I USED AI THE WHOLE TIME TO HELP ME MAKE ALL THIS BUT YOU CAN TELL ME HOW HORIBLE OF A PERSON THAT MAKES ME AGAIN IF YOU WANT!

## Features

- **Visible AI Reasoning**: Watch the agent's thought process as it codes
- **Real-time Code Streaming**: See code appear character-by-character in the editor
- **Monaco Editor**: Full-featured code editor with syntax highlighting and responsive, native-feeling input
- **Professional UI**: VS Code-inspired interface with Codicons, dropdown menus, and polished loading animations
- **Multi-Provider LLM Support**: Works with Gemini, OpenAI, Anthropic, or DeepSeek
- **Tool Integration**: File operations, code execution, Git, terminal, and web search

## Available Tools

| Tool | Description |
|------|-------------|
| `file_ops` | Read, write, and list files within the workspace |
| `run_python` | Execute Python code in a sandboxed environment |
| `git` | Version control operations (status, diff, log, commit, branch) |
| `terminal` | Execute shell commands with safety restrictions |
| `web_search` | Search the web for current information (requires API key) |

## Project Structure

```
slowhands/
├── app/                    # Python backend
│   ├── src/
│   │   ├── agent.py       # Main agent orchestrator
│   │   ├── llm.py         # LLM integration (multi-provider)
│   │   ├── server.py      # FastAPI WebSocket server
│   │   ├── config.py      # Configuration management
│   │   ├── memory.py      # Conversation history
│   │   ├── reliability.py # Rate limiting, circuit breaker
│   │   ├── services.py    # Agent service layer
│   │   ├── connection_manager.py  # WebSocket connections
│   │   └── tools/         # Agent tools
│   │       ├── file_ops.py
│   │       ├── code_runner.py
│   │       ├── git_tool.py
│   │       ├── terminal_tool.py
│   │       └── web_search_tool.py
│   ├── tests/             # Python tests
│   └── run_server.py      # Server entry point
├── frontend/              # TypeScript/Electron frontend
│   ├── src/
│   │   ├── main.ts        # Main frontend code
│   │   ├── api.ts         # API client
│   │   ├── editor.ts      # Monaco editor manager
│   │   ├── ui.ts          # UI state management
│   │   └── style.css      # Styles
│   └── electron/          # Electron main process
├── config/                # Configuration files
├── docs/                  # Documentation
│   ├── ARCHITECTURE.md    # System architecture
│   ├── SECURITY.md        # Security guidelines
│   └── dev/               # Development notes
├── examples/              # Example scripts
│   ├── basic/             # Simple examples
│   └── advanced/          # Complex examples
├── workspace/             # Agent sandbox directory
└── slowhands.sh           # Launch script
```

## Quick Start

```bash
# Start all services
./slowhands.sh
```

Or manually:

```bash
# Terminal 1: Start backend
cd app && source ../venv/bin/activate && python run_server.py

# Terminal 2: Start frontend
cd frontend && npm run dev
```

## Requirements

- Python 3.12+
- Node.js 18+
- API key for your chosen LLM provider

## Configuration

Copy the example environment file and configure:

```bash
cp config/.env.example config/.env
# Edit config/.env with your settings
```

### LLM Provider Settings

| Variable | Description |
|----------|-------------|
| `LLM_PROVIDER` | Provider: `gemini`, `openai`, `anthropic`, or `deepseek` |
| `GEMINI_API_KEY` | Google Gemini API key |
| `OPENAI_API_KEY` | OpenAI API key |
| `ANTHROPIC_API_KEY` | Anthropic API key |
| `DEEPSEEK_API_KEY` | DeepSeek API key |
| `MODEL` | Model name (e.g., `gemini-2.0-flash`) |

### Agent Settings

| Variable | Description | Default |
|----------|-------------|---------|
| `SLOW_MODE` | Show step-by-step execution | `true` |
| `MAX_ITERATIONS` | Safety limit for agent loops | `10` |
| `VERBOSE` | Enable detailed logging | `true` |

### Safety Settings

| Variable | Description | Default |
|----------|-------------|---------|
| `ALLOW_CODE_EXECUTION` | Enable Python code execution | `true` |
| `ALLOW_GIT_OPERATIONS` | Enable Git operations | `true` |
| `ALLOW_TERMINAL_EXECUTION` | Enable terminal commands | `true` |
| `ENABLE_DEBUG_LOGGING` | Enable debug file logging | `false` |

See `config/.env.example` for all available options.

## Safety Features

SlowHands includes multiple layers of safety:

1. **Workspace Isolation**: File operations restricted to the workspace directory
2. **Command Filtering**: Dangerous terminal commands are blocked
3. **Code Sandboxing**: Python execution in isolated subprocess with timeout
4. **Path Validation**: All file paths validated against traversal attacks
5. **Prompt Injection Protection**: System prompt includes safeguards against override attempts
6. **Rate Limiting**: API calls rate-limited to prevent abuse
7. **Circuit Breaker**: Automatic failover on repeated API errors

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Server health check with metrics |
| POST | `/agent/chat` | Synchronous chat |
| POST | `/agent/stream` | Start streaming response |
| POST | `/agent/reset` | Reset conversation |
| POST | `/agent/stop` | Stop agent execution |
| WS | `/ws` | WebSocket for real-time updates |

## Development

```bash
# Run tests
cd app && python -m pytest tests/

# Check types (frontend)
cd frontend && npm run typecheck
```

## Documentation

- [Architecture](docs/ARCHITECTURE.md) - System design and components
- [Security](docs/SECURITY.md) - Security guidelines and configuration

## License

MIT
