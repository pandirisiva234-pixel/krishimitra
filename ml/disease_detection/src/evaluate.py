"""Phase 13: evaluate a trained model on the held-out test set (or an external field dataset).

    python src/evaluate.py --run results/efficientnet_b0 --split splits/test.csv
    python src/evaluate.py --run results/efficientnet_b0 --split splits/plantdoc_test.csv --tag field

Writes results/<run>/metrics_<tag>.json, classification_report_<tag>.csv and
confusion_matrix_<tag>.png. Numbers come only from the images in --split.
"""
import argparse
import json
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import torch  # noqa: E402
from sklearn.metrics import (  # noqa: E402
    accuracy_score,
    classification_report,
    confusion_matrix,
    precision_recall_fscore_support,
    top_k_accuracy_score,
)
from torch.utils.data import DataLoader  # noqa: E402

from dataset import LeafDataset  # noqa: E402
from models import build_model, count_parameters, model_size_mb  # noqa: E402


def load_run(run: Path, device):
    ckpt = torch.load(run / "best.pt", map_location=device)
    model = build_model(ckpt["model"], len(ckpt["labels"]), pretrained=False)
    model.load_state_dict(ckpt["state_dict"])
    return model.to(device).eval(), ckpt


@torch.no_grad()
def predict(model, loader, device):
    probs, targets = [], []
    for x, y in loader:
        probs.append(torch.softmax(model(x.to(device)), 1).cpu())
        targets.append(y)
    return torch.cat(probs).numpy(), torch.cat(targets).numpy()


@torch.no_grad()
def cpu_latency_ms(model, size: int, runs: int = 30) -> float:
    m = model.to("cpu").eval()
    x = torch.randn(1, 3, size, size)
    for _ in range(5):
        m(x)
    start = time.perf_counter()
    for _ in range(runs):
        m(x)
    return (time.perf_counter() - start) / runs * 1000


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True, type=Path)
    ap.add_argument("--split", default="splits/test.csv")
    ap.add_argument("--tag", default="test")
    ap.add_argument("--batch-size", type=int, default=64)
    args = ap.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model, ckpt = load_run(args.run, device)
    labels = ckpt["labels"]
    df = pd.read_csv(args.split)
    df = df[df["label"].isin(labels)]  # external sets may contain classes the model never saw
    tmp_csv = args.run / f"_eval_{args.tag}.csv"
    df.to_csv(tmp_csv, index=False)
    ds = LeafDataset(tmp_csv, labels, train=False, size=ckpt["image_size"])
    probs, y = predict(model, DataLoader(ds, batch_size=args.batch_size, num_workers=2), device)
    tmp_csv.unlink()
    pred = probs.argmax(1)
    present = sorted(set(y) | set(pred))

    p, r, f1, _ = precision_recall_fscore_support(y, pred, labels=present, average="macro", zero_division=0)
    pw, rw, f1w, _ = precision_recall_fscore_support(y, pred, labels=present, average="weighted", zero_division=0)
    metrics = {
        "run": args.run.name, "model": ckpt["model"], "split": args.split, "tag": args.tag, "images": int(len(y)),
        "accuracy": round(accuracy_score(y, pred), 4),
        "top3_accuracy": round(top_k_accuracy_score(y, probs, k=3, labels=list(range(len(labels)))), 4),
        "macro_precision": round(p, 4), "macro_recall": round(r, 4), "macro_f1": round(f1, 4),
        "weighted_precision": round(pw, 4), "weighted_recall": round(rw, 4), "weighted_f1": round(f1w, 4),
        "mean_confidence": round(float(probs.max(1).mean()), 4),
        "share_below_0.6_confidence": round(float((probs.max(1) < 0.6).mean()), 4),
        "parameters_m": round(count_parameters(model) / 1e6, 2),
        "size_mb": round(model_size_mb(model), 1),
        "cpu_latency_ms_batch1": round(cpu_latency_ms(model, ckpt["image_size"]), 1),
        "best_epoch": ckpt["epoch"],
    }
    (args.run / f"metrics_{args.tag}.json").write_text(json.dumps(metrics, indent=2))
    report = classification_report(y, pred, labels=present, target_names=[labels[i] for i in present],
                                   output_dict=True, zero_division=0)
    pd.DataFrame(report).T.round(4).to_csv(args.run / f"classification_report_{args.tag}.csv")

    cm = confusion_matrix(y, pred, labels=present, normalize="true")
    fig, ax = plt.subplots(figsize=(max(8, len(present) * 0.35), max(7, len(present) * 0.33)))
    im = ax.imshow(cm, cmap="Greens", vmin=0, vmax=1)
    short = [labels[i].replace("___", ": ").replace("_", " ")[:28] for i in present]
    ax.set_xticks(range(len(present)), short, rotation=90, fontsize=6)
    ax.set_yticks(range(len(present)), short, fontsize=6)
    ax.set_xlabel("Predicted")
    ax.set_ylabel("True")
    ax.set_title(f"{args.run.name} — normalised confusion matrix ({args.tag}, n={len(y)})")
    fig.colorbar(im, fraction=0.03)
    fig.tight_layout()
    fig.savefig(args.run / f"confusion_matrix_{args.tag}.png", dpi=150)
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
