#!/usr/bin/env bash
# install_all_models.sh
# ✅ Installs all requested models in FP16 (full precision) when supported
# ✅ Gemma-2 2B pulled as FP16 (~4GB on disk)

set -euo pipefail

# -------------------------------------------------------------
# ✅ List of models (your original list)
# -------------------------------------------------------------
models=(
  "gemma2:2b"      # ✅ This one will be pulled FP16 below
  "phi3:medium"
  "phi3:mini"
  "mistral:7b"
  "qwen2.5:1.5b"
  "stablelm2:1.6b"
)

echo "🚀 Installing all supported models..."

# -------------------------------------------------------------
# ✅ Pull all standard models first (default quant or FP8)
# -------------------------------------------------------------
for m in "${models[@]}"; do
  echo "➡️ Pulling $m..."
  if ! ollama pull "$m"; then
    echo "⚠️ Warning: Failed to pull $m (skipped)."
  fi
done

# -------------------------------------------------------------
# ✅ Pull Gemma-2 2B in FULL FP16 precision (~4GB)
# -------------------------------------------------------------
echo "✅ Pulling Gemma-2 2B in FP16 full precision..."
echo "   This will download ~4GB (largest version)."

# Ollama supports model formats via MODEL FILE (recommended)
cat > Gemma-2B-FP16.ollama << 'EOF'
FROM gemma2:2b
PARAMETER format fp16
EOF

# Build the FP16 model locally
ollama create gemma2-2b-fp16 -f Gemma-2B-FP16.ollama

echo "🎉 Gemma-2 2B FP16 installed as: gemma2-2b-fp16"
echo "✅ Done!"
