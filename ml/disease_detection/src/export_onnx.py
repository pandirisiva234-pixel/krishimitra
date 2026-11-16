"""Phase 14: export the chosen model to ONNX for the backend, and VERIFY it.

    python src/export_onnx.py --run results/efficientnet_b0 --out ../../trained_models --check-csv splits/test.csv

Writes disease_model.onnx and disease_labels.json, then checks on real test images
that ONNX Runtime and PyTorch give the same predictions (agreement must be 100%).
"""
import argparse
import json
from datetime import date
from pathlib import Path

import numpy as np
import onnxruntime as ort
import pandas as pd
import torch

from evaluate import load_run
from preprocess import IMAGENET_MEAN, IMAGENET_STD, preprocess, read_rgb


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True, type=Path)
    ap.add_argument("--out", default="../../trained_models", type=Path)
    ap.add_argument("--check-csv", default="splits/test.csv")
    ap.add_argument("--check-n", type=int, default=200)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    model, ckpt = load_run(args.run, torch.device("cpu"))
    size = ckpt["image_size"]
    onnx_path = args.out / "disease_model.onnx"
    torch.onnx.export(
        model, torch.randn(1, 3, size, size), str(onnx_path),
        input_names=["input"], output_names=["logits"],
        dynamic_axes={"input": {0: "batch"}, "logits": {0: "batch"}}, opset_version=17, dynamo=False,
    )
    meta = {
        "labels": ckpt["labels"], "input_size": size, "mean": IMAGENET_MEAN.tolist(), "std": IMAGENET_STD.tolist(),
        "model_name": ckpt["model"], "version": f"{args.run.name}-{date.today().isoformat()}",
        "val_acc": ckpt.get("val_acc"), "best_epoch": ckpt.get("epoch"),
    }
    metrics_file = args.run / "metrics_test.json"
    if metrics_file.exists():
        meta["test_metrics"] = json.loads(metrics_file.read_text())
    (args.out / "disease_labels.json").write_text(json.dumps(meta, indent=2))

    # Verification on real images
    session = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
    df = pd.read_csv(args.check_csv).sample(frac=1, random_state=0).head(args.check_n)
    agree, max_diff = 0, 0.0
    with torch.no_grad():
        for path in df["path"]:
            x = preprocess(read_rgb(path), size)[None]
            torch_out = model(torch.from_numpy(x)).numpy()
            onnx_out = session.run(None, {"input": x})[0]
            max_diff = max(max_diff, float(np.abs(torch_out - onnx_out).max()))
            agree += int(torch_out.argmax() == onnx_out.argmax())
    print(f"Exported {onnx_path} ({onnx_path.stat().st_size / 1e6:.1f} MB)")
    print(f"PyTorch vs ONNX on {len(df)} test images: top-1 agreement {agree}/{len(df)}, max logit diff {max_diff:.2e}")
    if agree != len(df):
        raise SystemExit("ONNX predictions differ from PyTorch. Do not deploy this export.")


if __name__ == "__main__":
    main()
