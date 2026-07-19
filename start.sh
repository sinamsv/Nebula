#!/bin/bash

# start.sh - Local development script for Nebula
# Starts the FastAPI backend and Next.js frontend concurrently,
# handles dependency installation and builds when needed,
# and cleans up background tasks gracefully.

# Force exit if any setup command fails
set -e

# Load environment variables if .env exists
if [ -f .env ]; then
  echo "Loading environment variables from .env"
  # Read .env safely without breaking on inline comments
  while IFS= read -r line || [ -n "$line" ]; do
    # Skip comments and empty lines
    if [[ ! "$line" =~ ^[[:space:]]*# ]] && [[ ! "$line" =~ ^[[:space:]]*$ ]]; then
      # Strip inline comments (anything after #, unless in quotes) but keeping it simple:
      # If there is a '#' character, strip it and everything after it
      clean_line=$(echo "$line" | cut -d'#' -f1 | xargs)
      if [ -n "$clean_line" ]; then
        export "$clean_line"
      fi
    fi
  done < .env
fi

# 1. Resolve Frontend Configuration
FRONTEND_DIR="web_frontend"
NODE_ENV=${NODE_ENV:-development}
PORT=${PORT:-8080}

if [ ! -d "$FRONTEND_DIR" ]; then
  echo "ERROR: $FRONTEND_DIR directory not found."
  exit 1
fi

# 2. Automatically detect and handle node_modules / dependencies
if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
  echo "web_frontend/node_modules is missing. Running 'npm install' inside $FRONTEND_DIR..."
  (cd "$FRONTEND_DIR" && npm install)
fi

# 3. Automatically detect and handle production build
if [ "$NODE_ENV" != "development" ]; then
  if [ ! -d "$FRONTEND_DIR/.next" ]; then
    echo "web_frontend/.next is missing and NODE_ENV is '$NODE_ENV'. Running 'npm run build' inside $FRONTEND_DIR..."
    (cd "$FRONTEND_DIR" && npm run build)
  fi
fi

# Disable set -e so that we can manage background process execution
set +e

# Setup clean termination of background processes
cleanup() {
  echo "Stopping all processes..."
  # Kill all processes in our process group, or specifically the backgrounded tasks
  if [ -n "$BACKEND_PID" ]; then
    kill "$BACKEND_PID" 2>/dev/null || true
  fi
  if [ -n "$FRONTEND_PID" ]; then
    kill "$FRONTEND_PID" 2>/dev/null || true
  fi
  exit 0
}

# Trap INT and TERM signals to trigger cleanup
trap cleanup INT TERM

# 4. Start Backend
echo "Starting backend (main.py)..."
python main.py &
BACKEND_PID=$!

# 5. Start Frontend
echo "Starting frontend ($NODE_ENV mode on port $PORT)..."
if [ "$NODE_ENV" = "development" ]; then
  (cd "$FRONTEND_DIR" && PORT=$PORT npm run dev) &
  FRONTEND_PID=$!
else
  (cd "$FRONTEND_DIR" && PORT=$PORT npm run start) &
  FRONTEND_PID=$!
fi

# Wait for background processes to finish
wait $BACKEND_PID $FRONTEND_PID
