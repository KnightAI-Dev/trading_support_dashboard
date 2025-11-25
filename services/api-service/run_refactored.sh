#!/bin/bash
# Script to run the refactored API service

echo "Starting Refactored API Service..."
echo "Port: 8001"
echo ""

# Check if port is already in use
if lsof -Pi :8001 -sTCP:LISTEN -t >/dev/null ; then
    echo "⚠️  Port 8001 is already in use!"
    echo "   Either stop the existing service or change the port in main_refactored.py"
    exit 1
fi

# Run the refactored API
cd "$(dirname "$0")"
python main_refactored.py

