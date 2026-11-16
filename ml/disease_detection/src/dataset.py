"""PyTorch datasets built from the saved split CSVs."""
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from PIL import Image
from torch.utils.data import Dataset
from torchvision import transforms

from preprocess import IMAGENET_MEAN, IMAGENET_STD, preprocess, read_rgb


def train_transform(size: int = 224):
    """Augmentation simulates field photos: different framing, angle, light and focus."""
    return transforms.Compose([
        transforms.RandomResizedCrop(size, scale=(0.6, 1.0)),
        transforms.RandomHorizontalFlip(),
        transforms.RandomVerticalFlip(),
        transforms.RandomRotation(25),
        transforms.ColorJitter(brightness=0.3, contrast=0.3, saturation=0.3, hue=0.03),
        transforms.RandomApply([transforms.GaussianBlur(5, sigma=(0.1, 2.0))], p=0.2),
        transforms.ToTensor(),
        transforms.Normalize(IMAGENET_MEAN.tolist(), IMAGENET_STD.tolist()),
    ])


class LeafDataset(Dataset):
    def __init__(self, csv_path: str | Path, labels: list[str], train: bool, size: int = 224):
        self.df = pd.read_csv(csv_path)
        unknown = set(self.df["label"]) - set(labels)
        if unknown:
            raise ValueError(f"Labels not in the label list: {sorted(unknown)[:5]}")
        self.index = {label: i for i, label in enumerate(labels)}
        self.train = train
        self.size = size
        self.tf = train_transform(size) if train else None

    def __len__(self) -> int:
        return len(self.df)

    def __getitem__(self, i: int):
        row = self.df.iloc[i]
        target = self.index[row["label"]]
        if self.train:
            img = Image.open(row["path"]).convert("RGB")
            return self.tf(img), target
        # Validation/test use the deployed OpenCV preprocessing
        return torch.from_numpy(preprocess(read_rgb(row["path"]), self.size)), target

    def class_weights(self) -> torch.Tensor:
        """Inverse-frequency weights, used to counter class imbalance."""
        counts = self.df["label"].map(self.index).value_counts().sort_index()
        full = np.ones(len(self.index))
        full[counts.index.to_numpy()] = counts.to_numpy()
        w = 1.0 / full
        return torch.tensor(w / w.sum() * len(w), dtype=torch.float32)
