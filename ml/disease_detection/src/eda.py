"""Phase 12: dataset exploration — image sizes, colour statistics and a sample grid per class.

    python src/eda.py --split splits/train.csv --out results/eda
"""
import argparse
import json
from pathlib import Path

import cv2
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="splits/train.csv")
    ap.add_argument("--out", default="results/eda", type=Path)
    ap.add_argument("--sample", type=int, default=2000, help="images used for size/colour stats")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(args.split)

    sample = df.sample(min(args.sample, len(df)), random_state=0)
    sizes, means, blurs = [], [], []
    for path in sample["path"]:
        img = cv2.imread(path)
        if img is None:
            continue
        h, w = img.shape[:2]
        sizes.append((w, h))
        means.append(img[..., ::-1].reshape(-1, 3).mean(axis=0) / 255)
        blurs.append(cv2.Laplacian(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var())
    sizes = np.array(sizes)
    stats = {
        "images_sampled": len(sizes),
        "unique_sizes": int(len({tuple(s) for s in sizes})),
        "width_min_max": [int(sizes[:, 0].min()), int(sizes[:, 0].max())],
        "height_min_max": [int(sizes[:, 1].min()), int(sizes[:, 1].max())],
        "mean_rgb": np.round(np.mean(means, axis=0), 4).tolist(),
        "blur_laplacian_p5_p50_p95": np.round(np.percentile(blurs, [5, 50, 95]), 1).tolist(),
    }
    (args.out / "image_stats.json").write_text(json.dumps(stats, indent=2))
    print(json.dumps(stats, indent=2))

    labels = sorted(df["label"].unique())
    cols = 4
    fig, axes = plt.subplots(len(labels), cols, figsize=(cols * 2, len(labels) * 2))
    for r, label in enumerate(labels):
        paths = df[df.label == label]["path"].sample(min(cols, (df.label == label).sum()), random_state=1)
        for c in range(cols):
            ax = axes[r, c]
            ax.axis("off")
            if c < len(paths):
                ax.imshow(cv2.imread(paths.iloc[c])[..., ::-1])
            if c == 0:
                ax.set_title(label.replace("___", "\n"), fontsize=6, loc="left")
    fig.tight_layout()
    fig.savefig(args.out / "sample_grid.png", dpi=110)
    print(f"Saved sample grid and stats to {args.out}")


if __name__ == "__main__":
    main()
