#!/usr/bin/env bash
# QueryMind Backend Setup & Launch Script
set -e

cd "$(dirname "$0")"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ⚡ QueryMind Backend Setup"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Python check
if ! command -v python3 &>/dev/null; then
  echo "❌ Python 3.10+ is required"; exit 1
fi

# Create venv if needed
if [ ! -d "venv" ]; then
  echo "📦 Creating virtual environment..."
  python3 -m venv venv
fi

source venv/bin/activate

echo "📥 Installing dependencies..."
pip install --upgrade pip -q
pip install -r requirements.txt -q

echo ""
echo "✅ Starting QueryMind API on http://localhost:5000"
echo "   Press Ctrl+C to stop"
echo ""

python app.py
