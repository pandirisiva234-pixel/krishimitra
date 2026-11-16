"""Phase 13: build the model-comparison table from every results/*/metrics_<tag>.json.

    python src/compare.py --tag test
Outputs results/comparison_<tag>.csv, .md and a chart. Nothing is typed by hand.
"""
import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

COLS = ["run", "model", "images", "accuracy", "macro_precision", "macro_recall", "macro_f1", "top3_accuracy",
        "parameters_m", "size_mb", "cpu_latency_ms_batch1"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default="results", type=Path)
    ap.add_argument("--tag", default="test")
    args = ap.parse_args()
    rows = [json.loads(p.read_text()) for p in sorted(args.results.glob(f"*/metrics_{args.tag}.json"))]
    if not rows:
        raise SystemExit(f"No metrics_{args.tag}.json files found. Run evaluate.py first.")
    df = pd.DataFrame(rows)[COLS].sort_values("macro_f1", ascending=False)
    df.to_csv(args.results / f"comparison_{args.tag}.csv", index=False)
    (args.results / f"comparison_{args.tag}.md").write_text(df.to_markdown(index=False))
    print(df.to_string(index=False))

    fig, ax = plt.subplots(figsize=(7, 4))
    for _, r in df.iterrows():
        ax.scatter(r["cpu_latency_ms_batch1"], r["macro_f1"], s=r["size_mb"] * 8 + 20, alpha=0.7)
        ax.annotate(r["run"], (r["cpu_latency_ms_batch1"], r["macro_f1"]), textcoords="offset points", xytext=(6, 4))
    ax.set_xlabel("CPU latency per image (ms)")
    ax.set_ylabel(f"Macro F1 ({args.tag})")
    ax.set_title("Accuracy vs speed (bubble size = model size)")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(args.results / f"comparison_{args.tag}.png", dpi=150)


if __name__ == "__main__":
    main()
