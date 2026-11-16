"""Build an INDEPENDENT field test set from PlantDoc (real-world photos).

PlantVillage photos are single leaves on plain backgrounds, so high PlantVillage test
accuracy does not prove the model works on farm photos. PlantDoc contains field
photos; only classes that also exist in PlantVillage are kept (mapping in
configs/plantdoc_map.yaml). Report these results separately as "field accuracy".

PlantDoc (classification version): https://github.com/pratikkayal/PlantDoc-Dataset
    python src/prepare_external.py --plantdoc-dir ../../datasets/PlantDoc-Dataset/test --out splits/plantdoc_test.csv
"""
import argparse
from pathlib import Path

import pandas as pd
import yaml

EXTS = {".jpg", ".jpeg", ".png"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--plantdoc-dir", required=True, type=Path)
    ap.add_argument("--map", default="configs/plantdoc_map.yaml")
    ap.add_argument("--out", default="splits/plantdoc_test.csv")
    args = ap.parse_args()
    mapping = yaml.safe_load(Path(args.map).read_text())
    rows, skipped = [], {}
    for class_dir in sorted(p for p in args.plantdoc_dir.iterdir() if p.is_dir()):
        target = mapping.get(class_dir.name)
        files = [f for f in class_dir.iterdir() if f.suffix.lower() in EXTS]
        if target is None:
            skipped[class_dir.name] = len(files)
            continue
        rows += [{"path": str(f.resolve()), "label": target} for f in files]
    df = pd.DataFrame(rows)
    df.to_csv(args.out, index=False)
    print(f"{len(df)} field images across {df['label'].nunique()} mapped classes -> {args.out}")
    print("Skipped (no PlantVillage equivalent):", skipped)


if __name__ == "__main__":
    main()
