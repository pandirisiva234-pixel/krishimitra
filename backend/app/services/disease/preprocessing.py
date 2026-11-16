"""Image preprocessing for the disease model.

IMPORTANT: ml/disease_detection/src/preprocess.py contains the same function.
Training evaluation and the API must preprocess identically, otherwise the
accuracy measured in the notebook will not hold in the app.
"""
import cv2
import numpy as np

IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
IMAGENET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)


def decode_image(data: bytes) -> np.ndarray:
    """Bytes -> RGB uint8 array (H, W, 3). Raises ValueError if not an image."""
    array = np.frombuffer(data, dtype=np.uint8)
    bgr = cv2.imdecode(array, cv2.IMREAD_COLOR)
    if bgr is None:
        raise ValueError("Could not decode image")
    return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)


def blur_score(rgb: np.ndarray) -> float:
    """Variance of the Laplacian: low values mean a blurry photo."""
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def preprocess(rgb: np.ndarray, size: int = 224, mean=IMAGENET_MEAN, std=IMAGENET_STD) -> np.ndarray:
    """RGB uint8 -> float32 tensor (1, 3, size, size), ImageNet-normalised."""
    resized = cv2.resize(rgb, (size, size), interpolation=cv2.INTER_AREA)
    x = resized.astype(np.float32) / 255.0
    x = (x - np.asarray(mean, dtype=np.float32)) / np.asarray(std, dtype=np.float32)
    return np.transpose(x, (2, 0, 1))[np.newaxis, ...].astype(np.float32)
