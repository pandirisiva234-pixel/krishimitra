"""Phase 13 models: a baseline CNN trained from scratch and three transfer-learning backbones.

    baseline_cnn       4 conv blocks, ~1.2 M parameters, no pretraining (the reference point)
    mobilenet_v2       ImageNet-pretrained, ~3.5 M params, designed for phones
    mobilenet_v3_large ImageNet-pretrained, ~5.4 M params
    efficientnet_b0    ImageNet-pretrained, ~5.3 M params, strong accuracy per FLOP
"""
import torch
from torch import nn
from torchvision import models


class BaselineCNN(nn.Module):
    def __init__(self, num_classes: int):
        super().__init__()

        def block(cin, cout):
            return nn.Sequential(
                nn.Conv2d(cin, cout, 3, padding=1, bias=False), nn.BatchNorm2d(cout), nn.ReLU(inplace=True),
                nn.Conv2d(cout, cout, 3, padding=1, bias=False), nn.BatchNorm2d(cout), nn.ReLU(inplace=True),
                nn.MaxPool2d(2),
            )

        self.features = nn.Sequential(block(3, 32), block(32, 64), block(64, 128), block(128, 256))
        self.head = nn.Sequential(nn.AdaptiveAvgPool2d(1), nn.Flatten(), nn.Dropout(0.3), nn.Linear(256, num_classes))

    def forward(self, x):
        return self.head(self.features(x))


def build_model(name: str, num_classes: int, pretrained: bool = True) -> nn.Module:
    if name == "baseline_cnn":
        return BaselineCNN(num_classes)
    if name == "mobilenet_v2":
        m = models.mobilenet_v2(weights=models.MobileNet_V2_Weights.IMAGENET1K_V2 if pretrained else None)
        m.classifier[1] = nn.Linear(m.classifier[1].in_features, num_classes)
        return m
    if name == "mobilenet_v3_large":
        m = models.mobilenet_v3_large(weights=models.MobileNet_V3_Large_Weights.IMAGENET1K_V2 if pretrained else None)
        m.classifier[3] = nn.Linear(m.classifier[3].in_features, num_classes)
        return m
    if name == "efficientnet_b0":
        m = models.efficientnet_b0(weights=models.EfficientNet_B0_Weights.IMAGENET1K_V1 if pretrained else None)
        m.classifier[1] = nn.Linear(m.classifier[1].in_features, num_classes)
        return m
    raise ValueError(f"Unknown model '{name}'")


def head_parameters(model: nn.Module, name: str):
    """The new classification layer (trained first while the backbone is frozen)."""
    if name == "baseline_cnn":
        return list(model.parameters())
    return list(model.classifier.parameters())


def set_backbone_trainable(model: nn.Module, name: str, trainable: bool) -> None:
    if name == "baseline_cnn":
        return
    for p in model.features.parameters():
        p.requires_grad = trainable


def count_parameters(model: nn.Module) -> int:
    return sum(p.numel() for p in model.parameters())


@torch.no_grad()
def model_size_mb(model: nn.Module) -> float:
    return sum(p.numel() * p.element_size() for p in model.parameters()) / 1e6
