#!/bin/bash

# Start FastAPI backend in the background on port 8000
echo "Starting FastAPI backend on port 8000..."
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 &

# Wait a few seconds to let backend initialize
sleep 2

# Start Next.js frontend in the foreground on Hugging Face port (default 7860)
PORT=${PORT:-7860}
echo "Starting Next.js frontend on port $PORT..."
cd /app/frontend
exec npm run start -- -p $PORT
