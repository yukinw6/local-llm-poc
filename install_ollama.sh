#!/bin/bash
set -e

echo "=== GPU check ==="
nvidia-smi

echo "=== Installing Ollama ==="
curl -fsSL https://ollama.ai/install.sh | sh

echo "=== Starting Ollama service ==="
ollama serve &
sleep 5

echo "=== Pulling qwen3:8b (~5.5GB) ==="
ollama pull qwen3:8b

echo "=== Done. Run inference with: ==="
echo "  ollama run qwen3:8b \"日本語で自己紹介してください\""
echo ""
echo "=== Pre-inference GPU state ==="
nvidia-smi
