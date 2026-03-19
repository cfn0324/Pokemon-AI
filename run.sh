#!/bin/bash

echo "========================================"
echo "Pokemon AI Agent - Quick Start"
echo "========================================"
echo ""

# Check for Python
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 not found. Please install Python 3.9+"
    exit 1
fi

# Check for AI settings
if [ -z "$AI_API_KEY" ]; then
    # Try to load from .env file
    if [ -f ".env" ]; then
        export $(cat .env | grep -v '^#' | xargs)
    fi

    if [ -z "$AI_API_KEY" ]; then
        echo "ERROR: AI_API_KEY environment variable not set"
        echo ""
        echo "Please set it with:"
        echo "  export AI_API_KEY='your-api-key-here'"
        echo ""
        echo "Or create a .env file with:"
        echo "  AI_API_KEY=your-api-key-here"
        echo ""
        exit 1
    fi
fi

if [ -z "$AI_BASE_URL" ]; then
    echo "ERROR: AI_BASE_URL environment variable not set"
    echo ""
    echo "Please set it with:"
    echo "  export AI_BASE_URL='https://api.your-endpoint.com/v1'"
    echo ""
    exit 1
fi

if [ -z "$AI_MODEL" ]; then
    echo "ERROR: AI_MODEL environment variable not set"
    echo ""
    echo "Please set it with:"
    echo "  export AI_MODEL='your-model-id'"
    echo ""
    exit 1
fi

# Check for ROM
if [ ! -f "PokemonRed.gb" ]; then
    echo "ERROR: PokemonRed.gb not found"
    echo "Please place the Pokemon Red ROM in this directory"
    exit 1
fi

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    source venv/bin/activate
    echo "Installing dependencies..."
    pip install -r requirements.txt
else
    source venv/bin/activate
fi

echo ""
echo "Starting Pokemon AI Agent..."
echo ""
python main.py
