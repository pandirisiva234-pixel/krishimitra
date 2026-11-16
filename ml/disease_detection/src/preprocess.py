"""Evaluation/inference preprocessing — IDENTICAL to backend/app/services/disease/preprocessing.py.

Validation, test and the deployed API all use this OpenCV path, so the
accuracy measured here is the accuracy the app delivers. (Training-time
augmentation uses torchvision on top, which is fine: it only affects training.)
"""
import cv2
import numpy as np

IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
IMAGENET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)


def read_rgb(path: str) -> np.ndarray:
    bgr = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if bgr is None:
        raise ValueError(f"Unreadable image: {path}")
    return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)


def preprocess(rgb: np.ndarray, size: int = 224, mean=IMAGENET_MEAN, std=IMAGENET_STD) -> np.ndarray:
    """RGB uint8 (H, W, 3) -> float32 (3, size, size)."""
    resized = cv2.resize(rgb, (size, size), interpolation=cv2.INTER_AREA)
    x = resized.astype(np.float32) / 255.0
    x = (x - np.asarray(mean, dtype=np.float32)) / np.asarray(std, dtype=np.float32)
    return np.transpose(x, (2, 0, 1)).astype(np.float32)
