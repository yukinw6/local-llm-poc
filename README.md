# local-llm-poc

GCP GPU VM（T4 SPOT）上でOllamaを使ってローカルLLMを動かすPoC。

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

### 1. GCPプロジェクトを設定

```bash
export GCP_PROJECT=your-project-id
# ゾーンを変えたい場合（デフォルト: us-central1-b）
export GCP_ZONE=us-central1-b
```

### 2. VM作成

```bash
uv run python setup_vm.py
```

起動後に SSH コマンドが表示されます。

### 3. Ollamaとモデルをインストール

```bash
gcloud compute scp install_ollama.sh local-llm-poc-vm:~ --zone=$GCP_ZONE --project=$GCP_PROJECT
gcloud compute ssh local-llm-poc-vm --zone=$GCP_ZONE --project=$GCP_PROJECT --command="bash install_ollama.sh"
```

デフォルトで `qwen3:8b`（約5.2GB）をpullします。

### 4. 推論テスト

```bash
gcloud compute ssh local-llm-poc-vm --zone=$GCP_ZONE --project=$GCP_PROJECT \
  --command="ollama run qwen3:8b '日本語で自己紹介してください'"
```

### 5. VM削除

```bash
uv run python teardown_vm.py --action stop
uv run python teardown_vm.py --action delete
```

## 確認済みモデル（T4 16GB）

| モデル | サイズ | 日本語品質 | 備考 |
|---|---|---|---|
| `qwen3:8b` | 5.2GB | ✅ 良好 | デフォルト |
| `deepseek-r1:8b` | 5.2GB | △ テンプレ気味 | 推論特化 |
| `qwen3:14b` | 9.3GB | ✅ 最良 | 余裕で収まる |

## GPUオプション

`config.py` の `MACHINE_TYPE` / `GPU_TYPE` をコメントを参考に切り替えてください。

| GPU | VRAM | MACHINE_TYPE | GPU_TYPE | SPOT概算 |
|---|---|---|---|---|
| T4 | 16GB | n1-standard-4 | nvidia-tesla-t4 | ~$0.15/h |
| L4 | 24GB | g2-standard-4 | nvidia-l4 | ~$0.25/h |
| A100 | 40GB | a2-highgpu-1g | nvidia-tesla-a100 | ~$1.00/h |

## GPU在庫について

アジアリージョン（東京・シンガポール・ジャカルタ）はGPU在庫が枯渇しがちです。
`us-central1-b` の **T4 SPOTインスタンスは取得確認済み**（約$0.15/h）。

L4は通常インスタンスでアジア全域在庫切れを確認。SPOT在庫は未検証。
A100は未検証です。
