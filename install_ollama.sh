#!/bin/bash
set -e

echo "=== GPU check ==="
nvidia-smi

echo "=== Installing Ollama ==="
curl -fsSL https://ollama.ai/install.sh | sh

echo "=== Starting Ollama service ==="
ollama serve &
sleep 10

MODEL=${MODEL:-qwen3:8b}

if [ "${MODEL}" != "skip" ]; then
  echo "=== Pulling ${MODEL} ==="
  ollama pull "${MODEL}"
fi

echo "=== Done. Run inference with: ==="
echo "  ollama run ${MODEL} \"日本語で自己紹介してください\""
echo ""
echo "=== Pre-inference GPU state ==="
nvidia-smi
