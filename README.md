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
| `qwen3:30b-a3b` | ~21GB | 158.5 | MoE（Qwen公式）、2026-09-17再計測 |
| `qwen3.8:27b` | ~20GB | 54 | MoE（Qwen公式）、速度は遅め |
| `gemma4:26b` | ~19GB | 163 | Google製、高速 |
| `gpt-oss:20b` | ~34GB | 160 | |
| `nemotron-3.5-lightning:30b` | ~25GB | 181 | NVIDIA公式MoE、最速 |

## vLLM 並列ベンチマーク（完了、2026-09-17）

### 目的
Ollama逐次結果に対し、vLLM 10並列でのaggregate throughputを比較する。

### 結果

| 条件 | 同時リクエスト数 | Aggregate tok/s | 1件あたりの応答時間 |
|---|---|---|---|
| Ollama 逐次（`qwen3:30b-a3b`） | 1 | 158.5 | - |
| vLLM 単独 | 1 | 160.3 | 6.2秒（avg ~1000 tok） |
| vLLM 10並列 | 10 | 993.6 | 10.2秒（avg ~1012 tok） |

**Speedup: 6.3倍**（vLLM 10並列 aggregate ÷ Ollama逐次）。単独実行時はOllamaとvLLMでほぼ同速で、差が出るのは同時実行時のみ。詳細レポート（入出力サンプル付き）は別途Artifact化済み。

### スクリプト
- `install_vllm.sh` — vLLMセットアップ（uv + venv）、既定モデルは `ELVISIO/Qwen3-30B-A3B-AWQ`
- `benchmark_vllm.py` — 障害調査プロンプト × 10並列、TTFT/E2E/tok/s計測

### 遭遇した問題と真因（2026-09-17解決）

過去のセッションでは「Triton GCCが`libcuda.so.1`のリンクで失敗」という説明で長時間迷走したが、**実際の原因は無関係だった**。新規VMで再現させたところ、真因は以下の2つのみ:

| # | 問題 | 対処 |
|---|---|---|
| 1 | `python3.10-dev`が入っておらず`Python.h`が無い（Tritonが生成するCUDA拡張のコンパイルに必要） | `sudo apt-get install -y python3.10-dev` |
| 2 | `g++`(`cc1plus`)が入っていない（flashinferのJITカーネルビルドに必要） | `sudo apt-get install -y build-essential` |

`libcuda.so.1`のシンボリックリンク云々は、当時の環境固有の事故であり、Deep Learning VMイメージ自体の恒常的な問題ではなかった。**Deep Learning VMイメージにvLLMを新規インストールする際は、先に`python3.10-dev`と`build-essential`を入れておくこと。**

また `benchmark_vllm.py` 自体にもバグがあった。`urllib.request.urlopen`（同期・ブロッキング呼び出し）を`async def`の中でそのまま呼んでいたため、`asyncio.gather`で10並列を投げても実際は逐次実行されていた（Wall time 62.4s = 6.2s×10と一致）。`asyncio.to_thread()`でラップして真の並列実行に修正済み。

### モデル選定の経緯（Gemma4→Qwen3-30B-A3Bへの変更）
当初はOllamaで最速だった `gemma4:26b`（MoE）を対象にする予定だったが、vLLM向けの量子化チェックポイントが個人開発者1名（`cyankiwi`）によるものしか存在せず、重みの命名規則の違いに起因するvLLMの実バグ（[vllm-project/vllm#40591](https://github.com/vllm-project/vllm/issues/40591)、2026年5月修正済み）を踏んだ実績もあるなど、供給が薄く不安定だった。同程度の速度実績があり、複数の独立した量子化提供元・1年以上の実運用実績がある `Qwen3-30B-A3B` に切り替えて計測した。

### モデル情報
- HF model ID: `ELVISIO/Qwen3-30B-A3B-AWQ`（AWQ 4bit、gated不要）
- 対応する Ollama モデル: `qwen3:30b-a3b`
- VRAM: 約16GB（AWQ 4bit）、A100 40GB で余裕あり。GPU KVキャッシュは4,096 tok/リクエスト換算で最大51倍の同時実行に対応（今回実測は10並列まで）

### 未検証（優先度低）
実運用で想定される同時20〜30人規模は未実測。ただしKVキャッシュ上は51倍まで余裕があり、業務上も同時20人規模の同時アクセスは考えにくいため、現時点では追加検証の優先度は低いと判断（必要になれば再検証）。

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
