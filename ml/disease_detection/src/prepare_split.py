"""Phase 12: data cleaning, class distribution and a fixed stratified train/val/test split.

Expects the PlantVillage "color" folder layout:  <data_dir>/<ClassName>/*.jpg
Download (Kaggle):  "PlantVillage Dataset" by abdallahalidev, use plantvillage dataset/color

    python src/prepare_split.py --data-dir ../../datasets/plantvillage/color --out-dir splits

Outputs:
    splits/train.csv, val.csv, test.csv      (path,label)
    results/eda/class_distribution.csv/.png
    results/eda/cleaning_report.json         (corrupt files, exact duplicates removed)
The split is saved to disk so every model is trained and tested on exactly the same images.
"""
import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

import cv2
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.model_selection import train_test_split  # noqa: E402

EXTS = {".jpg", ".jpeg", ".png"}


def scan(data_dir: Path) -> tuple[pd.DataFrame, dict]:
    rows, corrupt, seen, duplicates = [], [], {}, []
    for class_dir in sorted(p for p in data_dir.iterdir() if p.is_dir()):
        for img in sorted(class_dir.iterdir()):
            if img.suffix.lower() not in EXTS:
                continue
            data = img.read_bytes()
            digest = hashlib.md5(data).hexdigest()
            if digest in seen:
                duplicates.append({"file": str(img), "duplicate_of": seen[digest]})
                continue
            if cv2.imread(str(img)) is None:
                corrupt.append(str(img))
                continue
            seen[digest] = str(img)
            rows.append({"path": str(img.resolve()), "label": class_dir.name})
    report = {"kept": len(rows), "corrupt": corrupt, "exact_duplicates_removed": len(duplicates),
              "duplicate_examples": duplicates[:20]}
    return pd.DataFrame(rows), report


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", required=True, type=Path)
    ap.add_argument("--out-dir", default="splits", type=Path)
    ap.add_argument("--eda-dir", default="results/eda", type=Path)
    ap.add_argument("--val", type=float, default=0.15)
    ap.add_argument("--test", type=float, default=0.15)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    df, report = scan(args.data_dir)
    if df.empty:
        raise SystemExit(f"No images found under {args.data_dir}")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    args.eda_dir.mkdir(parents=True, exist_ok=True)

    train_val, test = train_test_split(df, test_size=args.test, stratify=df["label"], random_state=args.seed)
    val_share = args.val / (1 - args.test)
    train, val = train_test_split(train_val, test_size=val_share, stratify=train_val["label"], random_state=args.seed)
    for name, part in (("train", train), ("val", val), ("test", test)):
        part.sort_values(["label", "path"]).to_csv(args.out_dir / f"{name}.csv", index=False)

    counts = Counter(df["label"])
    dist = pd.DataFrame(
        [{"label": k, "images": v, "train": int((train.label == k).sum()), "val": int((val.label == k).sum()),
          "test": int((test.label == k).sum())} for k, v in sorted(counts.items())]
    )
    dist.to_csv(args.eda_dir / "class_distribution.csv", index=False)
    fig, ax = plt.subplots(figsize=(10, 11))
    dist.sort_values("images").plot.barh(x="label", y="images", ax=ax, legend=False, color="#2e7d32")
    ax.set_xlabel("Images")
    ax.set_ylabel("")
    ax.set_title(f"Class distribution ({len(df)} images, {len(counts)} classes)")
    imbalance = max(counts.values()) / min(counts.values())
    ax.text(0.98, 0.02, f"max/min ratio = {imbalance:.1f}", transform=ax.transAxes, ha="right")
    fig.tight_layout()
    fig.savefig(args.eda_dir / "class_distribution.png", dpi=150)

    report.update({"classes": len(counts), "train": len(train), "val": len(val), "test": len(test),
                   "imbalance_ratio": round(imbalance, 2), "seed": args.seed})
    (args.eda_dir / "cleaning_report.json").write_text(json.dumps(report, indent=2))
    print(json.dumps({k: v for k, v in report.items() if k not in ("corrupt", "duplicate_examples")}, indent=2))


if __name__ == "__main__":
    main()
