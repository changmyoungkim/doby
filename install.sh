#!/bin/bash

# doby — Structured Memory for LLM-Driven Development

set -e

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║  doby — Structured Memory for LLM-Driven Development         ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# Check if doby directory exists
DOBY_DIR="$HOME/.claude/skills/doby"
if [ ! -d "$DOBY_DIR" ]; then
  echo "ERROR: doby directory not found at $DOBY_DIR"
  exit 1
fi

echo "✓ Found doby directory at $DOBY_DIR"
echo ""

# Install chromadb
echo "Installing chromadb..."
if command -v pip3 &> /dev/null; then
  pip3 install chromadb 2>&1 || {
    echo "ERROR: Failed to install chromadb with pip3"
    exit 1
  }
elif command -v pip &> /dev/null; then
  pip install chromadb 2>&1 || {
    echo "ERROR: Failed to install chromadb with pip"
    echo "Try: pip3 install chromadb"
    exit 1
  }
else
  echo "ERROR: pip or pip3 not found. Install Python first."
  exit 1
fi
echo "✓ chromadb installed"
echo ""

# Create project directories if they don't exist
PROJECT_ROOT="${PWD}"
mkdir -p "$PROJECT_ROOT/.omc/plans"
mkdir -p "$PROJECT_ROOT/.omc/wiki"
mkdir -p "$PROJECT_ROOT/.omc/state"

echo "✓ Created .omc directories in $PROJECT_ROOT"
echo ""

# Copy .dobyrc.example.json to .dobyrc.json if it doesn't exist
if [ -f "$DOBY_DIR/.dobyrc.example.json" ]; then
  if [ ! -f "$PROJECT_ROOT/.dobyrc.json" ]; then
    cp "$DOBY_DIR/.dobyrc.example.json" "$PROJECT_ROOT/.dobyrc.json"
    echo "✓ Copied .dobyrc.example.json to .dobyrc.json"
  else
    echo "✓ .dobyrc.json already exists"
  fi
else
  echo "⚠ .dobyrc.example.json not found"
fi
echo ""

# Auto-install hooks into ~/.claude/settings.local.json
SETTINGS_FILE="$HOME/.claude/settings.local.json"

install_hooks() {
  local doby_hooks='{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "node ~/.claude/skills/doby/detect-change.mjs"
          }
        ]
      }
    ],
    "Stop": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "node ~/.claude/skills/doby/batch-report.mjs"
          }
        ]
      }
    ]
  }
}'

  if [ ! -f "$SETTINGS_FILE" ] || [ "$(cat "$SETTINGS_FILE" 2>/dev/null)" = "{}" ]; then
    echo "$doby_hooks" > "$SETTINGS_FILE"
    echo "✓ Hooks installed to $SETTINGS_FILE"
  elif grep -q "detect-change.mjs" "$SETTINGS_FILE" 2>/dev/null; then
    echo "✓ Doby hooks already installed in $SETTINGS_FILE"
  else
    echo "⚠ $SETTINGS_FILE already has content. Please merge doby hooks manually:"
    echo ""
    echo '  PostToolUse: node ~/.claude/skills/doby/detect-change.mjs (matcher: Write|Edit)'
    echo '  Stop: node ~/.claude/skills/doby/batch-report.mjs'
  fi
}

install_hooks
echo ""

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                    Setup Complete!                            ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "To use doby:"
echo "  1. cd to your project root"
echo "  2. python ~/.claude/skills/doby/rag.py index"
echo "  3. python ~/.claude/skills/doby/rag.py query \"your question\""
echo ""
