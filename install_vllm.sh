#!/bin/bash
# vLLM + Gemma 4 26B (A4B MoE) セットアップ
# 前提: Deep Learning VM (CUDA 12.9), HF_TOKEN 環境変数が設定済み
set -e

if [ -z "${HF_TOKEN}" ]; then
  echo "Error: HF_TOKEN is not set."
  exit 1
fi

MODEL=${MODEL:-cyankiwi/gemma-4-26B-A4B-it-AWQ-4bit}
PORT=${PORT:-8000}

echo "=== GPU check ==="
nvidia-smi

echo "=== Installing uv ==="
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"

echo "=== Installing vLLM (venv) ==="
uv venv ~/.vllm-env
source ~/.vllm-env/bin/activate
uv pip install "vllm>=0.6.0" huggingface_hub

echo "=== HuggingFace login ==="
python3 -c "from huggingface_hub import login; login(token='${HF_TOKEN}')"

echo "=== Starting vLLM server ==="
echo "  model: ${MODEL}"
echo "  port : ${PORT}"

# AWQ 4bit量子化済みモデル（~13GB）→ A100 40GBに余裕で収まる
vllm serve "${MODEL}" \
  --quantization awq \
  --dtype float16 \
  --max-model-len 4096 \
  --gpu-memory-utilization 0.90 \
  --max-num-seqs 32 \
  --port "${PORT}" \
  --trust-remote-code &

SERVER_PID=$!
echo "vLLM PID: ${SERVER_PID}"

echo -n "Waiting for server"
for i in $(seq 1 120); do
  if curl -sf "http://localhost:${PORT}/health" > /dev/null 2>&1; then
    echo " ready."
    break
  fi
  echo -n "."
  sleep 5
done

echo ""
echo "=== GPU state after model load ==="
nvidia-smi --query-gpu=memory.used,memory.total --format=csv

echo ""
echo "Next: VLLM_URL=http://localhost:${PORT} python3 benchmark_vllm.py"
wait "${SERVER_PID}"
