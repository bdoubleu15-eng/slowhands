#!/bin/bash
# SlowHands Launcher
# Ensures all services are running, then launches the UI

PROJECT_DIR="/home/dub/projects/slowhands"
BACKEND_URL="http://127.0.0.1:8765"
FRONTEND_URL="http://localhost:5173"
MAX_WAIT_BACKEND=30
MAX_WAIT_FRONTEND=30

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}🖐️ SlowHands${NC}"
echo "============================"
echo ""

# Function to check if a service is running
check_service() {
    local url=$1
    local name=$2
    if curl -s --connect-timeout 2 --max-time 5 "$url" > /dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

# Function to check if a port is in use
check_port() {
    local port=$1
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

# Function to get PID of process on a port
get_port_pid() {
    local port=$1
    lsof -ti :$port 2>/dev/null
}

# Function to wait for a service to be ready
wait_for_service() {
    local url=$1
    local name=$2
    local max_wait=$3
    local count=0
    
    echo -e "${YELLOW}⏳ Checking $name...${NC}"
    while [ $count -lt $max_wait ]; do
        if check_service "$url" "$name"; then
            echo -e "${GREEN}✅ $name is ready${NC}"
            return 0
        fi
        sleep 1
        count=$((count + 1))
        if [ $((count % 5)) -eq 0 ]; then
            echo -e "${YELLOW}   Still waiting... (${count}s)${NC}"
        fi
    done
    echo -e "${RED}❌ $name failed to start after ${max_wait}s${NC}"
    return 1
}

# Step 1: Always restart backend for development
echo "📡 Backend Service"
echo "------------------"

echo -e "${YELLOW}🔄 Always restarting backend for development...${NC}"

# Kill existing backend if running
if check_port 8765; then
    OLD_PID=$(get_port_pid 8765)
    echo -e "${YELLOW}⚠️  Killing existing backend (PID: $OLD_PID)${NC}"
    kill $OLD_PID 2>/dev/null
    sleep 2
fi

echo "🚀 Starting backend server..."

cd "$PROJECT_DIR"

# Check if venv exists
if [ ! -d "venv" ]; then
    echo -e "${RED}❌ Virtual environment not found!${NC}"
    echo "   Please create it with: python3 -m venv venv"
    exit 1
fi

source venv/bin/activate

# Check if dependencies are installed
if ! python -c "import uvicorn" 2>/dev/null; then
    echo "📦 Installing backend dependencies..."
    cd app
    pip install -q -r requirements.txt
    cd ..
fi

cd app
python run_server.py > /tmp/slowhands-backend.log 2>&1 &
BACKEND_PID=$!
cd "$PROJECT_DIR"

echo "   Started backend (PID: $BACKEND_PID)"
echo "   Logs: /tmp/slowhands-backend.log"

if ! wait_for_service "$BACKEND_URL/health" "Backend" $MAX_WAIT_BACKEND; then
    echo -e "${RED}❌ Failed to start backend${NC}"
    echo "   Check logs: /tmp/slowhands-backend.log"
    exit 1
fi

echo ""

# Step 2: Always restart frontend dev server for development
echo "🎨 Frontend Dev Server"
echo "----------------------"

echo -e "${YELLOW}🔄 Always restarting frontend dev server for development...${NC}"

# Kill existing frontend if running
if check_port 5173; then
    OLD_PID=$(get_port_pid 5173)
    echo -e "${YELLOW}⚠️  Killing existing frontend (PID: $OLD_PID)${NC}"
    kill $OLD_PID 2>/dev/null
    sleep 2
fi

echo "🚀 Starting frontend dev server..."

cd "$PROJECT_DIR/frontend"

# Install dependencies if needed
if [ ! -d "node_modules" ]; then
    echo "📦 Installing frontend dependencies..."
    npm install
fi

# Start frontend dev server
npm run dev > /tmp/slowhands-frontend.log 2>&1 &
FRONTEND_PID=$!

echo "   Started frontend dev server (PID: $FRONTEND_PID)"
echo "   Logs: /tmp/slowhands-frontend.log"

if ! wait_for_service "$FRONTEND_URL" "Frontend" $MAX_WAIT_FRONTEND; then
    echo -e "${RED}❌ Failed to start frontend${NC}"
    echo "   Check logs: /tmp/slowhands-frontend.log"
    exit 1
fi

echo ""

# Note: vite-plugin-electron automatically launches the Electron window
# when `npm run dev` is started, so we don't need to run `npm run start` separately.
# This was causing TWO Electron windows to open!

echo -e "${GREEN}✅ Electron UI launching automatically via Vite${NC}"
echo "   (vite-plugin-electron handles this)"
echo ""

# Summary
echo "================================"
echo -e "${GREEN}🖐️ SlowHands is running!${NC}"
echo ""
echo "   Backend:  $BACKEND_URL"
echo "   Frontend: $FRONTEND_URL (+ Electron UI)"
echo ""
echo "   PIDs:"
echo "     Backend:  $BACKEND_PID"
echo "     Frontend: $FRONTEND_PID (includes Electron)"
echo ""
echo "   Logs:"
echo "     Backend:  /tmp/slowhands-backend.log"
echo "     Frontend: /tmp/slowhands-frontend.log (includes Electron)"
echo ""
echo "================================"
echo ""
echo -e "${YELLOW}💡 Tip: Services will keep running in the background${NC}"
echo -e "${YELLOW}   To stop all services, run: pkill -f 'slowhands|run_server|vite|electron'${NC}"
echo ""

# Exit successfully (don't wait for processes)
exit 0
