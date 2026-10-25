#!/usr/bin/env python3
"""FoodSeg103 model helpers and CLI backed by the Hugging Face trainer.

The command line delegates to :mod:`train_hf`, which loads Tubisi/FoodSeg103's
official train/validation splits and provides the shared preprocessing,
deterministic sampling, frozen-BatchNorm training, and checkpoint handling.
"""
from __future__ import annotations

import os
import random
import time

# MPS may not implement every operation used by every torchvision model.
os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader

NUM_CLASSES = 104  # background (0) + FoodSeg103 ingredient IDs 1..103
MODEL_NAMES = (
    "lraspp_mobilenet_v3_large",
    "fcn_resnet50",
    "deeplabv3_mobilenet_v3_large",
)


def seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def choose_device(requested: str) -> torch.device:
    if requested == "auto":
        if torch.backends.mps.is_available():
            return torch.device("mps")
        if torch.cuda.is_available():
            return torch.device("cuda")
        return torch.device("cpu")
    if requested == "mps" and not torch.backends.mps.is_available():
        raise RuntimeError("MPS was requested but PyTorch reports MPS unavailable. Check the setup instructions.")
    if requested == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA was requested but no CUDA GPU is available.")
    return torch.device(requested)


def build_model(name: str, num_classes: int = NUM_CLASSES, pretrained_backbone: bool = True) -> nn.Module:
    from torchvision.models import MobileNet_V3_Large_Weights, ResNet50_Weights
    from torchvision.models.segmentation import (
        deeplabv3_mobilenet_v3_large,
        fcn_resnet50,
        lraspp_mobilenet_v3_large,
    )

    resnet_weights = ResNet50_Weights.DEFAULT if pretrained_backbone else None
    mobilenet_weights = MobileNet_V3_Large_Weights.DEFAULT if pretrained_backbone else None
    if name == "lraspp_mobilenet_v3_large":
        model = lraspp_mobilenet_v3_large(weights=None, weights_backbone=mobilenet_weights)
        model.classifier.low_classifier = nn.Conv2d(
            model.classifier.low_classifier.in_channels, num_classes, kernel_size=1
        )
        model.classifier.high_classifier = nn.Conv2d(
            model.classifier.high_classifier.in_channels, num_classes, kernel_size=1
        )
    elif name == "fcn_resnet50":
        model = fcn_resnet50(weights=None, weights_backbone=resnet_weights, aux_loss=False)
        model.classifier[4] = nn.Conv2d(model.classifier[4].in_channels, num_classes, kernel_size=1)
    elif name == "deeplabv3_mobilenet_v3_large":
        model = deeplabv3_mobilenet_v3_large(
            weights=None, weights_backbone=mobilenet_weights, aux_loss=False
        )
        model.classifier[4] = nn.Conv2d(model.classifier[4].in_channels, num_classes, kernel_size=1)
    else:
        raise ValueError(f"Unknown model {name!r}; choose from {MODEL_NAMES}")
    return model


def extract_logits(output):
    return output["out"] if isinstance(output, dict) else output


@torch.no_grad()
def evaluate(model: nn.Module, loader: DataLoader, device: torch.device, num_classes: int) -> dict:
    """Evaluate pixel-weighted loss, pixel accuracy, and foreground-class mIoU."""
    model.eval()
    confusion = torch.zeros((num_classes, num_classes), dtype=torch.int64, device="cpu")
    total_seconds = 0.0
    loss_sum = 0.0
    valid_pixels = 0
    for images, masks in loader:
        images = images.to(device)
        masks = masks.to(device)
        if device.type == "mps":
            torch.mps.synchronize()
        elif device.type == "cuda":
            torch.cuda.synchronize(device)
        started = time.perf_counter()
        logits = extract_logits(model(images))
        if logits.shape[-2:] != masks.shape[-2:]:
            logits = nn.functional.interpolate(
                logits, size=masks.shape[-2:], mode="bilinear", align_corners=False
            )
        if device.type == "mps":
            torch.mps.synchronize()
        elif device.type == "cuda":
            torch.cuda.synchronize(device)
        total_seconds += time.perf_counter() - started

        valid = masks != 255
        loss_sum += float(
            nn.functional.cross_entropy(logits, masks, ignore_index=255, reduction="sum").cpu()
        )
        valid_pixels += int(valid.sum().cpu())
        predictions = logits.argmax(1)
        encoded = num_classes * masks[valid].reshape(-1) + predictions[valid].reshape(-1)
        batch_confusion = torch.bincount(
            encoded.cpu(), minlength=num_classes * num_classes
        ).reshape(num_classes, num_classes)
        confusion += batch_confusion

    intersection = confusion.diag().float()
    union = confusion.sum(0).float() + confusion.sum(1).float() - intersection
    iou = intersection / union.clamp_min(1)
    present = union > 0
    foreground_present = present.clone()
    foreground_present[0] = False
    mean_iou = float(iou[foreground_present].mean()) if foreground_present.any() else 0.0
    pixel_accuracy = float(intersection.sum() / confusion.sum().clamp_min(1))
    return {
        "val_miou_excluding_background": mean_iou,
        "val_pixel_accuracy": pixel_accuracy,
        "val_loss": loss_sum / max(1, valid_pixels),
        "val_classes_present": int(foreground_present.sum()),
        "mean_inference_ms_per_image": total_seconds / max(1, len(loader.dataset)) * 1000.0,
        "per_class_iou": [None if not present[i] else float(iou[i]) for i in range(num_classes)],
    }


def main() -> int:
    """Run the Hugging Face FoodSeg103 pipeline and use its shared data path."""
    from train_hf import main as train_hf_main

    train_hf_main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
