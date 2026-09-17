#!/bin/bash
# vLLM + Qwen3-30B-A3B (MoE) AWQ セットアップ
# 前提: Deep Learning VM (CUDA 12.9)。公開モデルのためHF_TOKENは不要（設定されていれば使う）
set -e

MODEL=${MODEL:-ELVISIO/Qwen3-30B-A3B-AWQ}
PORT=${PORT:-8000}

echo "=== GPU check ==="
nvidia-smi

echo "=== Installing build deps (python3.10-dev, build-essential) ==="
# Deep Learning VMイメージに無いことがある。無いとTritonのCUDA拡張コンパイルが
# 「Python.h: No such file or directory」や「cc1plus: No such file or directory」で失敗する。
sudo apt-get update -qq
sudo apt-get install -y python3.10-dev build-essential

echo "=== Installing uv ==="
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"

echo "=== Installing vLLM (venv) ==="
uv venv ~/.vllm-env
source ~/.vllm-env/bin/activate
uv pip install "vllm>=0.20.0" huggingface_hub

if [ -n "${HF_TOKEN}" ]; then
  echo "=== HuggingFace login ==="
  python3 -c "from huggingface_hub import login; login(token='${HF_TOKEN}')"
fi

echo "=== Starting vLLM server ==="
echo "  model: ${MODEL}"
echo "  port : ${PORT}"

# AWQ 4bit量子化済みモデル（~15GB）→ A100 40GBに余裕で収まる
# --quantizationは明示せずauto-detectに任せる（config.jsonの記載と食い違うと起動失敗するため）
vllm serve "${MODEL}" \
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
