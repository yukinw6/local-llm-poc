# local-llm-poc

GCP GPU VM（T4 / A100 SPOT）上でOllamaを使ってローカルLLMを動かすPoC。

## 前提条件

- GCPプロジェクトがあり、`gcloud` で認証済み
- `GPUS_ALL_REGIONS` クォータが1以上（デフォルト0 → Google Cloud Consoleからリクエスト）
- [uv](https://docs.astral.sh/uv/) インストール済み

## セットアップ

```bash
git clone <this-repo>
cd local-llm-poc
uv sync
```

## 使い方

### 1. GCPプロジェクトとGPUプロファイルを設定

```bash
export GCP_PROJECT=your-project-id
export GCP_GPU_PROFILE=t4        # t4（デフォルト）/ l4 / a100-40
# ゾーンを変えたい場合（デフォルト: us-central1-b）
export GCP_ZONE=us-central1-b
```

| プロファイル | GPU | VRAM | MACHINE_TYPE | デフォルトモデル |
|---|---|---|---|---|
| `t4`（デフォルト） | T4 | 16GB | n1-standard-4 | qwen3:8b |
| `l4` | L4 | 24GB | g2-standard-4 | qwen3:14b |
| `a100-40` | A100 | 40GB | a2-highgpu-1g | qwen3:32b |

### 2. VM作成

```bash
uv run python setup_vm.py
```

起動後に SSH コマンドとモデルのインストール例が表示されます。VM名はプロファイルごとに自動設定されます（例: `local-llm-poc-t4`、`local-llm-poc-a100-40`）。

### 3. Ollamaとモデルをインストール

```bash
VM_NAME=local-llm-poc-${GCP_GPU_PROFILE:-t4}
gcloud compute scp install_ollama.sh ${VM_NAME}:~ --zone=$GCP_ZONE --project=$GCP_PROJECT
gcloud compute ssh ${VM_NAME} --zone=$GCP_ZONE --project=$GCP_PROJECT \
  --command="MODEL=qwen3:32b bash install_ollama.sh"   # プロファイルに合わせてモデルを指定
```

`MODEL` を省略すると `qwen3:8b`（デフォルト）をpullします。

### 4. 推論テスト

```bash
gcloud compute ssh ${VM_NAME} --zone=$GCP_ZONE --project=$GCP_PROJECT \
  --command="ollama run qwen3:32b '日本語で自己紹介してください'"
```

### 5. VM停止・削除

```bash
uv run python teardown_vm.py --action stop
uv run python teardown_vm.py --action delete --yes   # --yes でプロンプトをスキップ
```

`GCP_GPU_PROFILE` を設定したままで実行すれば、対応する VM が対象になります。

## 確認済みモデル

### T4 16GB（us-central1-b）

| モデル | VRAM使用 | tok/s | 備考 |
|---|---|---|---|
| `qwen3:8b` | ~5GB | - | デフォルト、日本語良好 |
| `deepseek-r1:8b` | ~5GB | - | 推論特化、日本語はテンプレ気味 |
| `qwen3:14b` | ~9GB | - | 日本語最良、余裕で収まる |

※ T4 モデルは定性評価のみ（benchmark.py 未実施）

### A100 40GB（asia-northeast1-a）

| モデル | VRAM使用 | tok/s | 備考 |
|---|---|---|---|
| `qwen3:32b` | ~19GB | - | Thinking モード対応 |
| `qwen3:30b-a3b` | ~21GB | 150 | MoE（Qwen公式） |
| `qwen3.8:27b` | ~20GB | 54 | MoE（Qwen公式）、速度は遅め |
| `gemma4:26b` | ~19GB | 163 | Google製、高速 |
| `gpt-oss:20b` | ~34GB | 160 | |
| `nemotron-3.5-lightning:30b` | ~25GB | 181 | NVIDIA公式MoE、最速 |

## vLLM 並列ベンチマーク（作業中・未完了）

### 目的
Ollama逐次結果（gemma4:26b 154 tok/s）に対し、vLLM 10並列でのaggregate throughputを比較する。

### スクリプト
- `install_vllm.sh` — vLLMセットアップ（uv + venv）
- `benchmark_vllm.py` — 障害調査プロンプト × 10並列、TTFT/E2E/tok/s計測

### 既知の問題（2026-09-17 未解決）

| # | 問題 | 解決済み | 備考 |
|---|---|---|---|
| 1 | `--quantization bitsandbytes` が vLLM 0.29.0 で削除済み | ✅ | AWQ quantized model に変更 |
| 2 | `cyankiwi/gemma-4-26B-A4B-it-AWQ-4bit` は compressed-tensors 形式 | ✅ | `--quantization` フラグを外してauto-detect |
| 3 | Triton GCC が `libcuda.so.1` のリンクで失敗（循環シンボリックリンクを誤作成・削除し libcuda.so.1 が消えた） | ✅ | `sudo ln -sf /usr/lib/x86_64-linux-gnu/libcuda.so.580.178.04 /usr/lib/x86_64-linux-gnu/libcuda.so.1` で復元 |
| 4 | EngineCore初期化失敗（Triton GCC自体は手動実行で通るが vLLM では継続して失敗） | ❌ 未解決 | 根本原因未特定。キャッシュクリア後も再現 |

### 次の作戦候補
- vLLM のバージョンを下げる（0.6系など古いものを試す）
- Gemma4以外のモデル（TRITON_ATTNを強制しないもの）で試す
- Docker imageを使う（公式 vLLM Docker は環境が整っている）

### モデル情報
- HF model ID: `cyankiwi/gemma-4-26B-A4B-it-AWQ-4bit`（AWQ 4bit、gated不要）
- 対応する Ollama モデル: `gemma4:26b`
- VRAM: 16GB（AWQ 4bit）、A100 40GB で余裕あり

---

## クォータについて

GPU を使うには GPU 種別ごとにクォータ申請が必要（デフォルト 0）。
申請: Google Cloud Console → IAM と管理 → クォータ → GPU 名で検索 → 値を 1 に変更。

| プロファイル | クォータ名 | 確認済みリージョン |
|---|---|---|
| `t4` | Preemptible NVIDIA T4 GPUs | us-central1 |
| `a100-40` | Preemptible NVIDIA A100 GPUs | asia-northeast1 |

## GPU在庫・ゾーン実績

| GPU | ゾーン | SPOT在庫 | 備考 |
|---|---|---|---|
| T4 | us-central1-b | ✅ 確認済み | ~$0.15/h |
| A100 | asia-northeast1-a | ✅ 確認済み（2026-09） | us-central1 はクォータ上限あり |
| A100 | asia-northeast1-c | ✅ API で存在確認 | 実稼働未確認 |
| L4 | アジア全域 | 通常インスタンスで在庫切れ確認 | SPOT 未検証 |
