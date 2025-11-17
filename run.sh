#!/bin/bash
# run.sh - safely launch backend and frontend for NextFlix project

# --- 1. Kill any old Flask processes on port 5000 ---
echo "Checking for processes on port 5000..."
PIDS=$(lsof -t -i:5000)
if [ ! -z "$PIDS" ]; then
    echo "Killing old Flask processes: $PIDS"
    kill -9 $PIDS
else
    echo "No old Flask processes found."
fi

# --- 2. Run SQLite import script ---
echo "Running SQLite import..."
cd backend/flask
if [ -f "import_sqlite.py" ]; then
    python3 import_sqlite.py
fi

# --- 3. Start Flask server in background ---
echo "Starting Flask server..."
python3 server.py &
BACKEND_PID=$!
echo "Flask PID: $BACKEND_PID"

# --- 4. Start frontend ---
cd ../../frontend

# Install dependencies if needed (npm install will skip if already installed)
echo "Installing frontend dependencies..."
npm install

# Start React frontend
echo "Starting React frontend..."
npm start

# --- 5. Cleanup ---
echo "Frontend exited. Killing Flask server (PID $BACKEND_PID)..."
kill $BACKEND_PID
echo "All done."
