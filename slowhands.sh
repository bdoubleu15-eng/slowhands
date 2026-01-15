#!/bin/bash
# SlowHands Launcher
# Completely restarts all services

PROJECT_DIR="/home/dub/projects/slowhands"

echo "🖐️ SlowHands - Full Restart"
echo "============================"

# Step 1: Kill existing processes
echo "🔪 Stopping existing services..."

# Kill any Python server on port 8765
fuser -k 8765/tcp 2>/dev/null
# Kill any process running run_server.py
pkill -f "python run_server.py" 2>/dev/null
# Kill any Vite dev server (frontend)
pkill -f "vite" 2>/dev/null
# Kill any process on common frontend ports
fuser -k 5173/tcp 2>/dev/null
fuser -k 5174/tcp 2>/dev/null

# Wait for processes to die
sleep 2

echo "✅ Services stopped"

# Step 2: Start backend
echo ""
echo "🚀 Starting backend server..."
cd "$PROJECT_DIR"
source venv/bin/activate
cd app
python run_server.py &
BACKEND_PID=$!

# Wait for backend to be ready
echo "⏳ Waiting for backend to be ready..."
for i in {1..15}; do
    if curl -s http://127.0.0.1:8765/health > /dev/null 2>&1; then
        echo "✅ Backend ready (PID: $BACKEND_PID)"
        break
    fi
    if [ $i -eq 15 ]; then
        echo "❌ Backend failed to start!"
        exit 1
    fi
    sleep 1
done

# Step 3: Start frontend
echo ""
echo "🚀 Starting frontend..."
cd "$PROJECT_DIR/frontend"

# Install dependencies if needed
if [ ! -d "node_modules" ]; then
    echo "📦 Installing frontend dependencies..."
    npm install
fi

# Start frontend dev server
npm run dev &
FRONTEND_PID=$!

# Wait for frontend to be ready
echo "⏳ Waiting for frontend to be ready..."
for i in {1..10}; do
    if curl -s http://localhost:5173 > /dev/null 2>&1; then
        echo "✅ Frontend ready (PID: $FRONTEND_PID)"
        break
    fi
    sleep 1
done

echo ""
echo "============================"
echo "🖐️ SlowHands is running!"
echo ""
echo "   Backend:  http://127.0.0.1:8765"
echo "   Frontend: http://localhost:5173"
echo ""
echo "Press Ctrl+C to stop all services"
echo "============================"

# Handle Ctrl+C to cleanup
cleanup() {
    echo ""
    echo "🛑 Shutting down..."
    kill $BACKEND_PID 2>/dev/null
    kill $FRONTEND_PID 2>/dev/null
    pkill -f "python run_server.py" 2>/dev/null
    pkill -f "vite" 2>/dev/null
    echo "👋 Goodbye!"
    exit 0
}

trap cleanup SIGINT SIGTERM

# Keep script running and wait for both processes
wait
