"""Lazy inference for the experimental FoodSeg103 FCN-ResNet-50 checkpoint."""
from __future__ import annotations

import base64
import colorsys
import importlib.util
import io
import os
from pathlib import Path
from typing import Any, Mapping


NUM_CLASSES = 104
EXPECTED_MODEL = "fcn_resnet50"
IMAGE_SIZE = 160
IGNORE_INDEX = 255
DEFAULT_CHECKPOINT = (
    Path(__file__).resolve().parent.parent
    / "research/food_segmentation/results/full_data_experiment/fcn_resnet50_seed42"
    / "fcn_resnet50/best_model.pth"
)
IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)


class InvalidFoodImageError(ValueError):
    """The supplied data URL or encoded image is invalid or unsupported."""


class FoodSeg103UnavailableError(RuntimeError):
    """The checkpoint or its runtime dependencies cannot be used."""


class FoodSeg103Inference:
    """Load once on first use, cache the model, and return mask-based predictions."""

    def __init__(self, checkpoint_path: str | Path | None = None):
        configured_path = checkpoint_path or os.getenv("FOODSEG103_CHECKPOINT")
        self.checkpoint_path = Path(configured_path).expanduser() if configured_path else DEFAULT_CHECKPOINT
        self._model = None
        self._torch = None
        self._numpy = None
        self._image = None
        self._device = None
        self._meta: dict[str, Any] = {}
        self._load_error: str | None = None

    @property
    def available(self) -> bool:
        """Whether a checkpoint file is configured; does not eagerly load it."""
        return self.checkpoint_path.is_file()

    @property
    def status(self) -> dict[str, Any]:
        if not self.available:
            return {"status": "unavailable", "reason": f"Checkpoint not found: {self.checkpoint_path}"}
        if self._load_error:
            return {"status": "unavailable", "reason": self._load_error}
        if self._model is not None:
            return {"status": "ready", "device": str(self._device), "model": self._meta["model_name"]}
        missing = []
        for dependency in ("torch", "torchvision", "numpy", "PIL"):
            try:
                if importlib.util.find_spec(dependency) is None:
                    missing.append(dependency)
            except (ImportError, ValueError):
                missing.append(dependency)
        if missing:
            return {"status": "unavailable", "reason": "Missing inference dependencies: " + ", ".join(missing)}
        return {"status": "not_loaded", "reason": "Checkpoint is present; the model loads on the first photo request."}

    @staticmethod
    def _import_runtime():
        import numpy as np
        import torch
        from PIL import Image

        return torch, np, Image

    @staticmethod
    def _build_model(model_name: str, num_classes: int):
        import importlib.util
        import sys

        research_src = Path(__file__).resolve().parent.parent / "research" / "food_segmentation" / "src"
        script = research_src / "train_compare.py"
        if not script.is_file():
            raise FoodSeg103UnavailableError(f"FoodSeg103 architecture source is missing: {script}")
        module_name = "_component3_foodseg103_model_factory"
        module = sys.modules.get(module_name)
        if module is None:
            spec = importlib.util.spec_from_file_location(module_name, script)
            if spec is None or spec.loader is None:
                raise FoodSeg103UnavailableError("Could not load the FoodSeg103 model factory.")
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
        return module.build_model(model_name, num_classes=num_classes, pretrained_backbone=False)

    def _load(self) -> None:
        if self._model is not None:
            return
        if not self.available:
            raise FoodSeg103UnavailableError(f"Checkpoint not found: {self.checkpoint_path}")
        try:
            torch, np, Image = self._import_runtime()
            # weights_only=True restricts deserialization to tensors and simple
            # built-in containers; never fall back to unrestricted pickle loading.
            payload = torch.load(self.checkpoint_path, map_location="cpu", weights_only=True)
            if not isinstance(payload, Mapping):
                raise ValueError("Checkpoint root must be a dictionary.")
            required = {"model_name", "num_classes", "image_size", "state_dict", "id2label"}
            missing = sorted(required.difference(payload))
            if missing:
                raise ValueError("Checkpoint is missing required fields: " + ", ".join(missing))
            if payload["model_name"] != EXPECTED_MODEL:
                raise ValueError(f"Expected {EXPECTED_MODEL}, found {payload['model_name']!r}.")
            if int(payload["num_classes"]) != NUM_CLASSES:
                raise ValueError(f"Expected {NUM_CLASSES} output classes.")
            if int(payload["image_size"]) != IMAGE_SIZE:
                raise ValueError(f"Expected trained image size {IMAGE_SIZE}.")
            state_dict = payload["state_dict"]
            if not isinstance(state_dict, Mapping) or not state_dict:
                raise ValueError("Checkpoint state_dict must be a non-empty mapping.")

            raw_labels = payload["id2label"]
            if not isinstance(raw_labels, Mapping):
                raise ValueError("Checkpoint id2label must be a mapping.")
            labels = {str(key): str(value).strip() for key, value in raw_labels.items()}
            expected_ids = {str(index) for index in range(NUM_CLASSES)}
            if set(labels) != expected_ids or labels.get("0", "").casefold() != "background":
                raise ValueError("Checkpoint id2label must map IDs 0..103, with ID 0 as background.")
            if any(not label for label in labels.values()):
                raise ValueError("Checkpoint id2label contains an empty class name.")

            model = self._build_model(EXPECTED_MODEL, NUM_CLASSES)
            model.load_state_dict(state_dict, strict=True)
            if torch.backends.mps.is_available():
                device = torch.device("mps")
            elif torch.cuda.is_available():
                device = torch.device("cuda")
            else:
                device = torch.device("cpu")
            model.to(device).eval()
            self._model, self._torch, self._numpy, self._image, self._device = model, torch, np, Image, device
            self._meta = {
                "model_name": EXPECTED_MODEL,
                "num_classes": NUM_CLASSES,
                "image_size": IMAGE_SIZE,
                "id2label": labels,
                "metrics": payload.get("metrics", {}),
                "dataset_id": payload.get("dataset_id", "Tubisi/FoodSeg103"),
            }
            self._load_error = None
        except Exception as exc:
            self._load_error = f"{type(exc).__name__}: {exc}"
            if isinstance(exc, (FileNotFoundError, ValueError, FoodSeg103UnavailableError)):
                raise FoodSeg103UnavailableError(self._load_error) from exc
            raise FoodSeg103UnavailableError("Could not load FoodSeg103 inference dependencies or checkpoint: " + self._load_error) from exc

    @staticmethod
    def _decode_image(data_url: str):
        from PIL import Image, UnidentifiedImageError

        if not isinstance(data_url, str) or "," not in data_url:
            raise InvalidFoodImageError("Expected a base64 image data URL.")
        header, encoded = data_url.split(",", 1)
        mime_to_format = {"data:image/jpeg;base64": "JPEG", "data:image/png;base64": "PNG", "data:image/webp;base64": "WEBP"}
        expected_format = mime_to_format.get(header.lower())
        if expected_format is None:
            raise InvalidFoodImageError("Upload a JPG, PNG, or WEBP image.")
        try:
            raw = base64.b64decode(encoded, validate=True)
        except (ValueError, base64.binascii.Error) as exc:
            raise InvalidFoodImageError("The uploaded image could not be decoded.") from exc
        if not raw or len(raw) > 8 * 1024 * 1024:
            raise InvalidFoodImageError("The image must be non-empty and no larger than 8 MB.")
        try:
            with Image.open(io.BytesIO(raw)) as source:
                if source.format != expected_format:
                    raise InvalidFoodImageError("The image content does not match its declared file type.")
                if source.width < 1 or source.height < 1 or source.width * source.height > 20_000_000:
                    raise InvalidFoodImageError("The image dimensions are invalid or too large.")
                source.load()
                image = source.convert("RGB")
        except InvalidFoodImageError:
            raise
        except (UnidentifiedImageError, OSError, ValueError) as exc:
            raise InvalidFoodImageError("The uploaded file is not a readable image.") from exc
        return image

    @staticmethod
    def _overlay_data_url(mask, Image, np) -> str:
        height, width = mask.shape
        overlay = np.zeros((height, width, 4), dtype=np.uint8)
        for class_id in np.unique(mask):
            class_id = int(class_id)
            if class_id == 0:
                continue
            hue = (class_id * 0.618033988749895) % 1.0
            red, green, blue = colorsys.hsv_to_rgb(hue, 0.72, 0.98)
            selected = mask == class_id
            overlay[selected, :3] = (int(red * 255), int(green * 255), int(blue * 255))
            overlay[selected, 3] = 132
        output = io.BytesIO()
        Image.fromarray(overlay, mode="RGBA").save(output, format="PNG")
        return "data:image/png;base64," + base64.b64encode(output.getvalue()).decode("ascii")

    def predict_data_url(self, image_data_url: str, min_area_fraction: float = 0.006, max_foods: int = 12) -> dict[str, Any]:
        image = self._decode_image(image_data_url)
        self._load()
        torch, np, Image = self._torch, self._numpy, self._image
        original_width, original_height = image.size
        resized = image.resize((IMAGE_SIZE, IMAGE_SIZE), Image.Resampling.BILINEAR)
        array = np.asarray(resized, dtype=np.float32).copy() / 255.0
        tensor = torch.from_numpy(array).permute(2, 0, 1).contiguous()
        mean = torch.tensor(IMAGENET_MEAN, dtype=torch.float32)[:, None, None]
        std = torch.tensor(IMAGENET_STD, dtype=torch.float32)[:, None, None]
        tensor = ((tensor - mean) / std).unsqueeze(0).to(self._device)
        with torch.no_grad():
            output = self._model(tensor)
            logits = output["out"] if isinstance(output, dict) else output
            if logits.ndim != 4 or logits.shape[0] != 1 or logits.shape[1] != NUM_CLASSES:
                raise FoodSeg103UnavailableError(f"Model returned an invalid segmentation shape: {tuple(logits.shape)}.")
            logits = torch.nn.functional.interpolate(logits, size=(IMAGE_SIZE, IMAGE_SIZE), mode="bilinear", align_corners=False)
            if not bool(torch.isfinite(logits).all().item()):
                raise FoodSeg103UnavailableError("Model returned non-finite segmentation logits.")
            mask = logits.argmax(dim=1)[0].detach().to("cpu").numpy().astype(np.uint8)

        original_mask = Image.fromarray(mask, mode="L").resize((original_width, original_height), Image.Resampling.NEAREST)
        original_mask = np.asarray(original_mask, dtype=np.uint8)
        total_pixels = original_width * original_height
        labels = self._meta["id2label"]
        predictions = []
        for class_id in np.unique(original_mask):
            class_id = int(class_id)
            if class_id == 0:
                continue
            area_pixels = int((original_mask == class_id).sum())
            fraction = area_pixels / total_pixels
            if fraction < min_area_fraction:
                continue
            predictions.append({
                "food_name": labels[str(class_id)],
                "estimated_quantity_g": None,
                "confidence": None,
                "class_id": class_id,
                "area_pixels": area_pixels,
                "area_fraction": fraction,
                "notes": f"Predicted FoodSeg103 class {class_id}; mask covers {area_pixels:,} pixels ({fraction * 100:.1f}% of the image). Pixel area does not estimate food weight. Confirm the food and portion.",
            })
        predictions.sort(key=lambda item: (-item["area_pixels"], item["class_id"]))
        predictions = predictions[:max(0, min(int(max_foods), 12))]
        return {
            "foods": predictions,
            "method": "foodseg103_segmentation",
            "model": self._meta["model_name"],
            "dataset": self._meta["dataset_id"],
            "device": str(self._device),
            "image_size": IMAGE_SIZE,
            "original_width": original_width,
            "original_height": original_height,
            "mask_overlay_data_url": self._overlay_data_url(original_mask, Image, np),
            "message": "Segmentation predictions are ready. Review or remove each food, choose its USDA record, and enter the portion before calculating nutrition.",
            "limitation": "This experimental FoodSeg103 model predicts visible ingredient masks. Pixel area is not portion weight; no grams or calibrated confidence are inferred. Confirm each food and portion. It may miss foods outside its 103-class label set.",
        }
