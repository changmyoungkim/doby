#!/bin/bash

# stmemory — Structured Memory for LLM-Driven Development

set -e

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║  stmemory — Structured Memory for LLM-Driven Development     ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# Check if stmemory directory exists
STMEMORY_DIR="$HOME/.claude/skills/stmemory"
if [ ! -d "$STMEMORY_DIR" ]; then
  echo "ERROR: stmemory directory not found at $STMEMORY_DIR"
  exit 1
fi

echo "✓ Found stmemory directory at $STMEMORY_DIR"
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

# Copy .stmemoryrc.example.json to .stmemoryrc.json if it doesn't exist
if [ -f "$STMEMORY_DIR/.stmemoryrc.example.json" ]; then
  if [ ! -f "$PROJECT_ROOT/.stmemoryrc.json" ]; then
    cp "$STMEMORY_DIR/.stmemoryrc.example.json" "$PROJECT_ROOT/.stmemoryrc.json"
    echo "✓ Copied .stmemoryrc.example.json to .stmemoryrc.json"
  else
    echo "✓ .stmemoryrc.json already exists"
  fi
else
  echo "⚠ .stmemoryrc.example.json not found"
fi
echo ""

# Print hook installation instructions
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                  NEXT STEPS: Add Hooks                        ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "Add the following to ~/.claude/settings.local.json:"
echo ""
echo '  "hooks": {'
echo '    "PostToolUse": [{'
echo '      "matcher": "Write|Edit",'
echo '      "hooks": [{"type": "command", "command": "node ~/.claude/skills/stmemory/detect-change.mjs"}]'
echo '    }],'
echo '    "Stop": [{'
echo '      "matcher": "",'
echo '      "hooks": [{"type": "command", "command": "node ~/.claude/skills/stmemory/batch-report.mjs"}]'
echo '    }]'
echo '  }'
echo ""
echo "These hooks will:"
echo "  - Detect changes after Write/Edit operations (PostToolUse)"
echo "  - Generate a batch report when the session ends (Stop)"
echo ""

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                    Setup Complete!                            ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "To use stmemory:"
echo "  1. cd to your project root"
echo "  2. python ~/.claude/skills/stmemory/rag.py index"
echo "  3. python ~/.claude/skills/stmemory/rag.py query \"your question\""
echo ""
