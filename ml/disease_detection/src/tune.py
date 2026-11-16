"""Phase 13: small hyperparameter grid search on the validation set (never the test set).

    python src/tune.py --config configs/efficientnet_b0.yaml --epochs 4
Tries each combination for a few epochs and writes results/tuning_<model>.csv.
Put the best values into the config and train it fully with train.py.
"""
import argparse
import itertools
import json
from pathlib import Path

import pandas as pd
import yaml

from train import train

GRID = {"lr": [1e-3, 3e-4], "batch_size": [32, 64], "label_smoothing": [0.0, 0.1]}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--epochs", type=int, default=4)
    args = ap.parse_args()
    base = yaml.safe_load(Path(args.config).read_text())
    rows = []
    keys = list(GRID)
    for values in itertools.product(*GRID.values()):
        cfg = {**base, **dict(zip(keys, values)), "epochs": args.epochs, "head_epochs": min(1, base.get("head_epochs", 0)),
               "run_name": f"tune_{base['model']}_" + "_".join(f"{k}{v}" for k, v in zip(keys, values))}
        out = train(cfg)
        hist = json.loads((out / "history.json").read_text())
        best = min(hist, key=lambda h: h["val_loss"])
        rows.append({**dict(zip(keys, values)), "best_val_loss": best["val_loss"], "best_val_acc": best["val_acc"]})
    df = pd.DataFrame(rows).sort_values("best_val_loss")
    path = Path(base.get("results_dir", "results")) / f"tuning_{base['model']}.csv"
    df.to_csv(path, index=False)
    print(df.to_string(index=False))


if __name__ == "__main__":
    main()
