#!/usr/bin/env python3
"""
使い方:
  python3 benchmark.py
  BENCHMARK_MODELS=qwen3:32b,gpt-oss:20b python3 benchmark.py  # モデル上書き
  BENCHMARK_OUT=results.json python3 benchmark.py
"""
import json, subprocess, urllib.request, os

MODELS = os.environ.get("BENCHMARK_MODELS", "qwen3.8:27b,gemma4:27b").split(",")
OUT_FILE = os.environ.get("BENCHMARK_OUT", "results.json")

PROMPTS = [
    {
        "id": "meeting_memo",
        "label": "会議メモ整理",
        "system": "あなたは議事録整理の専門家です。",
        "user": """以下の会議メモを整理してください。
決定事項、未決事項、Action、担当者、期限を表で整理してください。
明記されていない内容は推測しないでください。

【会議メモ】
日時: 2024年11月14日 14:00〜15:30
出席: 田中（PM）、鈴木（開発）、佐藤（QA）、山田（営業）

冒頭、田中より「先月から続いていた認証基盤の移行作業が完了し、本番リリースは11月20日に予定通り実施する」と報告があった。
鈴木から「移行スクリプトの最終確認は今週金曜までに終わらせたい」との発言。
佐藤は「リグレッションテストは18日までに完了させる。ただしテスト環境が17日まで別チームに貸し出し中のため、早くても17日夜以降の開始になる」と説明した。
山田より「既存顧客への移行完了通知メールはいつ送るか」との質問があったが、田中は「リリース後の動作確認が取れてから送りたい。21日以降を想定」と回答。具体的な送信日時は未定。
また、山田から「新規顧客向けの案内ページを更新してほしい」という要望が出たが、鈴木は「リリース直後は対応が難しい、早くても22日以降」と述べた。ページの更新担当者は決まっていない。
最後に田中より「万一リリースが延期になった場合の連絡は当日朝9時までに全員にSlackで連絡する」とのアナウンスがあった。""",
    },
    {
        "id": "incident_investigation",
        "label": "障害調査",
        "system": "あなたはSREエンジニアです。",
        "user": """以下の事実をもとに、原因仮説を可能性順に3つ挙げてください。
各仮説について「確認すべき証拠」と「断定できる条件」を示してください。
情報が不足している場合は断定せず、その旨を明記してください。

【観測された事実】
- Web APIで503エラーが増加（通常の5倍、15分前から）
- Cloud Run自体のインスタンス数・CPU・メモリは正常範囲
- Backend VMの一部（3台中2台）でHealth Check失敗
- 同時刻にFirewallルールの変更が実施された（変更内容の詳細は未確認）""",
    },
    {
        "id": "biz_consult",
        "label": "曖昧な業務相談",
        "system": "あなたは業務改善コンサルタントです。",
        "user": """直近3か月で工数が増えているチームと作業をPower BIで把握したい。
見るべき指標、可視化案、追加確認事項を整理してください。
過剰な機能追加は避けてください。""",
    },
]


def get_vram_mb() -> int:
    r = subprocess.run(
        ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
        capture_output=True, text=True,
    )
    return int(r.stdout.strip())


def ollama_generate(model: str, system: str, prompt: str) -> dict:
    payload = json.dumps({
        "model": model, "system": system, "prompt": prompt, "stream": False,
    }).encode()
    req = urllib.request.Request(
        "http://localhost:11434/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=600) as resp:
        return json.loads(resp.read())


results = []

for model in MODELS:
    print(f"\n=== Pulling {model} ===", flush=True)
    subprocess.run(["ollama", "pull", model], check=True)

    for p in PROMPTS:
        print(f"[{model}] {p['label']} ...", flush=True)
        vram_before = get_vram_mb()
        resp = ollama_generate(model, p["system"], p["user"])
        vram_after = get_vram_mb()

        eval_count = resp.get("eval_count", 0)
        eval_ns = resp.get("eval_duration", 1)
        tok_per_sec = round(eval_count / (eval_ns / 1e9), 1) if eval_ns else 0

        record = {
            "model": model,
            "prompt_id": p["id"],
            "label": p["label"],
            "response": resp.get("response", ""),
            "eval_count": eval_count,
            "total_duration_ms": resp.get("total_duration", 0) // 1_000_000,
            "eval_duration_ms": eval_ns // 1_000_000,
            "tokens_per_sec": tok_per_sec,
            "vram_before_mb": vram_before,
            "vram_peak_mb": vram_after,
        }
        results.append(record)
        print(f"  {eval_count} tok / {tok_per_sec} tok/s / {record['eval_duration_ms']}ms / VRAM {vram_before}→{vram_after}MB")

with open(OUT_FILE, "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print(f"\nSaved → {OUT_FILE}")

print(f"\n{'Model':25} {'Prompt':25} {'Tokens':>7} {'tok/s':>7} {'ms':>8} {'VRAM_MB':>8}")
print("-" * 85)
for r in results:
    print(f"{r['model']:25} {r['prompt_id']:25} {r['eval_count']:>7} {r['tokens_per_sec']:>7.1f} {r['eval_duration_ms']:>8} {r['vram_peak_mb']:>8}")
