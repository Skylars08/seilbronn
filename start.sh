#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

echo "🚠 Starting Seilbronn: Urbane Seilbahn Heilbronn Decision & Sentiment Atlas..."

# Check or setup virtualenv in user home to avoid external drive noexec restrictions
VENV_DIR="$HOME/.seilbronn_venv"
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating Python virtual environment in $VENV_DIR..."
    python3 -m venv "$VENV_DIR"
    "$VENV_DIR/bin/pip" install --upgrade pip
    "$VENV_DIR/bin/pip" install -q fastapi uvicorn requests feedparser trafilatura pydantic
fi

# Ensure dataset exists
if [ ! -f "data/heilbronn_seilbahn_dataset.json" ]; then
    echo "Preparing dataset from FSI corpus and YouTube..."
    "$VENV_DIR/bin/python3" prepare_dataset.py
fi

echo "🚀 Launching Seilbronn Atlas at http://localhost:8000"
echo "Open http://localhost:8000 in your browser to explore the dashboard!"
exec "$VENV_DIR/bin/python3" server.py

