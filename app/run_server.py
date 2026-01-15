#!/usr/bin/env python3
"""
SlowHands API Server Entry Point

Run with:
    python run_server.py
    
Or for development with auto-reload:
    uvicorn src.server:app --reload --host 127.0.0.1 --port 8765
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import uvicorn


def main():
    """Start the SlowHands API server."""
    print("=" * 50)
    print("  SlowHands API Server")
    print("=" * 50)
    print()
    print("Starting server on http://127.0.0.1:8765")
    print("WebSocket endpoint: ws://127.0.0.1:8765/ws")
    print()
    print("Press Ctrl+C to stop")
    print()
    
    uvicorn.run(
        "src.server:app",
        host="127.0.0.1",
        port=8765,
        reload=False,
        log_level="info"
    )


if __name__ == "__main__":
    main()
