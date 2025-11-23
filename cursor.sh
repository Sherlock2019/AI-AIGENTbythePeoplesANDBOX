#!/usr/bin/env bash
set -euo pipefail

# ==========================================
#  CURSOR AGENT INTERACTIVE LAUNCHER
# ==========================================

# Available models
MODELS=(
  "gpt-4o"
  "gpt-4.1"
  "gpt-4o-mini"
  "claude-3.5-sonnet"
  "claude-3.5-opus"
  "gemma-2-9b"
  "mistral-large"
  "llama3.1-70b"
  "ollama:gemma2:9b"
  "ollama:llama3.1:70b"
)

echo "======================================="
echo "       CURSOR AGENT MODEL PICKER"
echo "======================================="
echo

# Display numbered list
i=1
for m in "${MODELS[@]}"; do
  echo "  [$i] $m"
  ((i++))
done

echo
read -rp "Choose a model number: " CHOICE

# Validate
if ! [[ "$CHOICE" =~ ^[0-9]+$ ]]; then
  echo "❌ Invalid choice."
  exit 1
fi

# Convert to index
INDEX=$((CHOICE-1))

if [[ $INDEX -lt 0 || $INDEX -ge ${#MODELS[@]} ]]; then
  echo "❌ Invalid model number."
  exit 1
fi

MODEL="${MODELS[$INDEX]}"

echo
echo "✨ Selected Model: $MODEL"
echo

# Ask for task
read -rp "Enter your Cursor Agent task: " TASK

if [[ -z "$TASK" ]]; then
  echo "❌ No task entered."
  exit 1
fi

echo
echo "🚀 Running Cursor Agent..."
echo "   Model: $MODEL"
echo "   Task:  $TASK"
echo

cursor-agent --model "$MODEL" "$TASK"
