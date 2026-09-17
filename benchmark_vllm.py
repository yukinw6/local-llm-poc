#!/usr/bin/env python3
"""
vLLM 並列スループットベンチマーク（障害調査プロンプト固定）
Ollama逐次結果（qwen3:30b-a3b 158.5 tok/s）との比較用

使い方:
  python benchmark_vllm.py
  CONCURRENCY=10 VLLM_URL=http://<IP>:8000 python benchmark_vllm.py
"""
import asyncio, json, os, time, urllib.request

VLLM_URL    = os.environ.get("VLLM_URL", "http://localhost:8000")
CONCURRENCY = int(os.environ.get("CONCURRENCY", "10"))
OUT_FILE    = os.environ.get("BENCHMARK_OUT", "results_vllm.json")

# Ollama逐次ベースライン（qwen3:30b-a3b、障害調査プロンプト、2026-09-17実測）
OLLAMA_BASELINE_TPS = 158.5

SYSTEM = "あなたはSREエンジニアです。"
USER = """以下の事実をもとに、原因仮説を可能性順に3つ挙げてください。
各仮説について「確認すべき証拠」と「断定できる条件」を示してください。
情報が不足している場合は断定せず、その旨を明記してください。

【観測された事実】
- Web APIで503エラーが増加（通常の5倍、15分前から）
- Cloud Run自体のインスタンス数・CPU・メモリは正常範囲
- Backend VMの一部（3台中2台）でHealth Check失敗
- 同時刻にFirewallルールの変更が実施された（変更内容の詳細は未確認）"""


async def send_one(idx: int, model: str) -> dict:
    return await asyncio.to_thread(_send_one_sync, idx, model)


def _send_one_sync(idx: int, model: str) -> dict:
    payload = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": USER},
        ],
        "max_tokens": 1024,
        "stream": True,
    }).encode()
    req = urllib.request.Request(
        f"{VLLM_URL}/v1/chat/completions",
        data=payload,
        headers={"Content-Type": "application/json"},
    )

    t_start = time.perf_counter()
    ttft = None
    tokens = 0

    with urllib.request.urlopen(req, timeout=120) as resp:
        for raw in resp:
            line = raw.decode().strip()
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            try:
                delta = json.loads(data)["choices"][0]["delta"].get("content", "")
            except Exception:
                continue
            if delta:
                if ttft is None:
                    ttft = time.perf_counter() - t_start
                tokens += 1

    e2e = time.perf_counter() - t_start
    return {
        "idx": idx,
        "ttft_ms": round((ttft or 0) * 1000, 1),
        "e2e_ms":  round(e2e * 1000, 1),
        "tokens":  tokens,
        "tok_per_sec": round(tokens / e2e, 1) if e2e > 0 else 0,
    }


def get_model() -> str:
    try:
        with urllib.request.urlopen(f"{VLLM_URL}/v1/models", timeout=5) as r:
            return json.loads(r.read())["data"][0]["id"]
    except Exception:
        return "unknown"


def main():
    try:
        urllib.request.urlopen(f"{VLLM_URL}/health", timeout=5)
    except Exception as e:
        raise SystemExit(f"vLLM not reachable: {e}")

    model = get_model()
    print(f"Model      : {model}")
    print(f"Concurrency: {CONCURRENCY}")
    print(f"Prompt     : 障害調査（Ollama逐次ベースライン: {OLLAMA_BASELINE_TPS} tok/s）")
    print()

    async def _run_all():
        return await asyncio.gather(
            *[send_one(i, model) for i in range(CONCURRENCY)],
            return_exceptions=True,
        )

    wall_start = time.perf_counter()
    raw = asyncio.run(_run_all())
    wall_sec = time.perf_counter() - wall_start

    results = [r for r in raw if isinstance(r, dict)]
    errors  = len(raw) - len(results)
    total_tokens = sum(r["tokens"] for r in results)
    agg_tps = round(total_tokens / wall_sec, 1)

    print(f"{'#':>3} {'TTFT(ms)':>10} {'E2E(ms)':>10} {'Tokens':>7} {'tok/s':>8}")
    print("-" * 44)
    for r in sorted(results, key=lambda x: x["idx"]):
        print(f"{r['idx']:>3} {r['ttft_ms']:>10.0f} {r['e2e_ms']:>10.0f} {r['tokens']:>7} {r['tok_per_sec']:>8.1f}")

    print()
    print(f"Wall time          : {wall_sec:.1f}s")
    print(f"Total tokens       : {total_tokens}")
    print(f"Aggregate tok/s    : {agg_tps}  ← vLLM {CONCURRENCY}並列")
    print(f"Baseline tok/s     : {OLLAMA_BASELINE_TPS}  ← qwen3:30b-a3b Ollama逐次")
    print(f"Speedup (aggregate): {round(agg_tps / OLLAMA_BASELINE_TPS, 1)}x")
    if errors:
        print(f"Errors: {errors}")

    with open(OUT_FILE, "w") as f:
        json.dump({
            "model": model, "concurrency": CONCURRENCY,
            "wall_sec": round(wall_sec, 2),
            "total_tokens": total_tokens,
            "aggregate_tok_per_sec": agg_tps,
            "ollama_baseline_tok_per_sec": OLLAMA_BASELINE_TPS,
            "speedup": round(agg_tps / OLLAMA_BASELINE_TPS, 1),
            "errors": errors, "per_request": results,
        }, f, indent=2)
    print(f"Saved → {OUT_FILE}")


if __name__ == "__main__":
    main()
