#!/bin/bash
# MIRI WatchEye - Local Development Runner

echo "🔍 MIRI WatchEye - Starting local development environment..."

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check for required commands
command -v python3 >/dev/null 2>&1 || { echo "Python 3 required but not installed."; exit 1; }
command -v npm >/dev/null 2>&1 || { echo "npm required but not installed."; exit 1; }

# Start backend
echo -e "${BLUE}Starting backend server...${NC}"
cd backend

# Install dependencies if needed
if [ ! -d "venv" ]; then
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
else
    source venv/bin/activate
fi

# Start uvicorn in background
uvicorn api_server:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!
echo -e "${GREEN}Backend started (PID: $BACKEND_PID)${NC}"

cd ..

# Start frontend
echo -e "${BLUE}Starting frontend dev server...${NC}"
cd frontend

# Install dependencies if needed
if [ ! -d "node_modules" ]; then
    npm install
fi

# Start vite dev server
npm run dev &
FRONTEND_PID=$!
echo -e "${GREEN}Frontend started (PID: $FRONTEND_PID)${NC}"

cd ..

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}MIRI WatchEye is running!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Frontend: http://localhost:5173"
echo "Backend API: http://localhost:8000"
echo "API Docs: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop all services"

# Trap to cleanup on exit
cleanup() {
    echo ""
    echo "Shutting down..."
    kill $BACKEND_PID 2>/dev/null
    kill $FRONTEND_PID 2>/dev/null
    exit 0
}
trap cleanup INT

# Wait
wait
