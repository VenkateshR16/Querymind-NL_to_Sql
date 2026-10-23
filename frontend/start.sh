#!/usr/bin/env bash
# QueryMind Frontend Setup & Launch Script
set -e

cd "$(dirname "$0")"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  🎨 QueryMind Frontend Setup"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if ! command -v node &>/dev/null; then
  echo "❌ Node.js 18+ is required"; exit 1
fi

if [ ! -d "node_modules" ]; then
  echo "📥 Installing npm packages..."
  npm install
fi

echo ""
echo "✅ Starting QueryMind UI on http://localhost:3000"
echo "   Press Ctrl+C to stop"
echo ""

npm run dev
