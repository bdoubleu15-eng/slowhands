# SlowHands 🖐️

An AI coding assistant that shows its work - watch the agent think, plan, and write code in real-time.

## Features

- **Visible AI Reasoning**: Watch the agent's thought process as it codes
- **Real-time Code Streaming**: See code appear character-by-character in the editor
- **Monaco Editor**: Full-featured code editor with syntax highlighting
- **Tool Integration**: File operations, code execution, and more

## Project Structure

```
slowhands/
├── app/                    # Python backend
│   ├── src/
│   │   ├── agent.py       # Main agent orchestrator
│   │   ├── llm.py         # LLM integration (Gemini)
│   │   ├── server.py      # FastAPI WebSocket server
│   │   ├── tools/         # Agent tools (file_ops, code_runner)
│   │   └── ...
│   ├── tests/             # Python tests
│   └── run_server.py      # Server entry point
├── frontend/              # TypeScript/Electron frontend
│   ├── src/
│   │   ├── main.ts        # Main frontend code
│   │   └── style.css      # Styles
│   └── electron/          # Electron main process
├── config/                # Configuration files
├── docs/                  # Documentation
├── examples/              # Example scripts
└── slowhands.sh          # Launch script
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
- Gemini API key (set in config/config.yaml)

## Configuration

Create `config/config.yaml`:

```yaml
provider: gemini
model: gemini-3-pro-preview
api_key: your-api-key-here
```

## License

MIT
