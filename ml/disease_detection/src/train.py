"""Phase 13: train one model from a YAML config.

    python src/train.py --config configs/efficientnet_b0.yaml

Transfer-learning models train in two stages:
  1. head only (backbone frozen) for `head_epochs`,
  2. fine-tune everything with a 10x smaller learning rate.
Early stopping watches validation loss. Outputs go to results/<run_name>/:
  best.pt, history.json, curves.png, config.yaml, labels.json
"""
import argparse
import json
import random
import shutil
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import torch  # noqa: E402
import yaml  # noqa: E402
from torch import nn  # noqa: E402
from torch.utils.data import DataLoader  # noqa: E402

from dataset import LeafDataset  # noqa: E402
from models import build_model, count_parameters, head_parameters, set_backbone_trainable  # noqa: E402


def seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def run_epoch(model, loader, criterion, device, optimizer=None, scaler=None):
    training = optimizer is not None
    model.train(training)
    total_loss, correct, n = 0.0, 0, 0
    for x, y in loader:
        x, y = x.to(device, non_blocking=True), y.to(device, non_blocking=True)
        with torch.set_grad_enabled(training), torch.autocast(device.type, enabled=device.type == "cuda"):
            logits = model(x)
            loss = criterion(logits, y)
        if training:
            optimizer.zero_grad(set_to_none=True)
            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()
        total_loss += loss.item() * x.size(0)
        correct += (logits.argmax(1) == y).sum().item()
        n += x.size(0)
    return total_loss / n, correct / n


def plot_curves(history: list[dict], path: Path, title: str) -> None:
    ep = [h["epoch"] for h in history]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 4))
    a1.plot(ep, [h["train_loss"] for h in history], label="train")
    a1.plot(ep, [h["val_loss"] for h in history], label="validation")
    a1.set_title("Loss")
    a2.plot(ep, [h["train_acc"] for h in history], label="train")
    a2.plot(ep, [h["val_acc"] for h in history], label="validation")
    a2.set_title("Accuracy")
    for a in (a1, a2):
        a.set_xlabel("epoch")
        a.legend()
        a.grid(alpha=0.3)
    stage2 = next((h["epoch"] for h in history if h["stage"] == "finetune"), None)
    if stage2:
        for a in (a1, a2):
            a.axvline(stage2 - 0.5, color="grey", ls="--", lw=1)
    fig.suptitle(title)
    fig.tight_layout()
    fig.savefig(path, dpi=150)


def train(cfg: dict) -> Path:
    seed_everything(cfg.get("seed", 42))
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    out = Path(cfg.get("results_dir", "results")) / cfg["run_name"]
    out.mkdir(parents=True, exist_ok=True)

    labels = sorted(pd.read_csv(cfg["train_csv"])["label"].unique())
    (out / "labels.json").write_text(json.dumps(labels, indent=2))
    size = cfg.get("image_size", 224)
    train_ds = LeafDataset(cfg["train_csv"], labels, train=True, size=size)
    val_ds = LeafDataset(cfg["val_csv"], labels, train=False, size=size)
    kw = dict(batch_size=cfg["batch_size"], num_workers=cfg.get("num_workers", 2), pin_memory=device.type == "cuda")
    train_dl = DataLoader(train_ds, shuffle=True, drop_last=True, **kw)
    val_dl = DataLoader(val_ds, shuffle=False, **kw)

    name = cfg["model"]
    model = build_model(name, len(labels), pretrained=cfg.get("pretrained", True)).to(device)
    weights = train_ds.class_weights().to(device) if cfg.get("class_weights", False) else None
    criterion = nn.CrossEntropyLoss(weight=weights, label_smoothing=cfg.get("label_smoothing", 0.1))
    scaler = torch.amp.GradScaler(enabled=device.type == "cuda")
    print(f"{name}: {count_parameters(model) / 1e6:.2f} M parameters, {len(labels)} classes, device={device}")

    stages = []
    if name != "baseline_cnn" and cfg.get("head_epochs", 0) > 0:
        stages.append(("head", cfg["head_epochs"], cfg["lr"]))
        stages.append(("finetune", cfg["epochs"], cfg["lr"] * cfg.get("finetune_lr_factor", 0.1)))
    else:
        stages.append(("full", cfg["epochs"], cfg["lr"]))

    history, best_loss, epoch, patience_left = [], float("inf"), 0, cfg.get("patience", 5)
    start = time.time()
    for stage, n_epochs, lr in stages:
        set_backbone_trainable(model, name, stage != "head")
        params = head_parameters(model, name) if stage == "head" else [p for p in model.parameters() if p.requires_grad]
        optimizer = torch.optim.AdamW(params, lr=lr, weight_decay=cfg.get("weight_decay", 1e-4))
        scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=n_epochs)
        patience_left = cfg.get("patience", 5)
        for _ in range(n_epochs):
            epoch += 1
            tl, ta = run_epoch(model, train_dl, criterion, device, optimizer, scaler)
            vl, va = run_epoch(model, val_dl, criterion, device)
            scheduler.step()
            history.append({"epoch": epoch, "stage": stage, "train_loss": tl, "train_acc": ta, "val_loss": vl,
                            "val_acc": va, "lr": optimizer.param_groups[0]["lr"],
                            "elapsed_min": round((time.time() - start) / 60, 2)})
            print(f"[{stage}] epoch {epoch}: train {tl:.4f}/{ta:.4f}  val {vl:.4f}/{va:.4f}")
            if vl < best_loss - 1e-4:
                best_loss, patience_left = vl, cfg.get("patience", 5)
                torch.save({"model": name, "state_dict": model.state_dict(), "labels": labels,
                            "image_size": size, "epoch": epoch, "val_loss": vl, "val_acc": va}, out / "best.pt")
            else:
                patience_left -= 1
                if patience_left == 0:
                    print("Early stopping")
                    break
            (out / "history.json").write_text(json.dumps(history, indent=2))

    plot_curves(history, out / "curves.png", f"{cfg['run_name']} training curves")
    (out / "history.json").write_text(json.dumps(history, indent=2))
    print(f"Best validation loss {best_loss:.4f}; training took {(time.time() - start) / 60:.1f} min -> {out}")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--override", nargs="*", default=[], help="key=value pairs, e.g. lr=0.0005 epochs=5")
    args = ap.parse_args()
    cfg = yaml.safe_load(Path(args.config).read_text())
    for item in args.override:
        k, v = item.split("=", 1)
        cfg[k] = yaml.safe_load(v)
    out = train(cfg)
    shutil.copy(args.config, out / "config.yaml")
    (out / "config_resolved.yaml").write_text(yaml.safe_dump(cfg))


if __name__ == "__main__":
    main()
