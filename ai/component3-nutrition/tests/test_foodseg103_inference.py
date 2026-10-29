from __future__ import annotations

import base64
import io
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from foodseg103_inference import FoodSeg103Inference, FoodSeg103UnavailableError, InvalidFoodImageError


def png_data_url(width=32, height=20, color=(255, 0, 0)):
    Image = pytest.importorskip("PIL.Image")
    image = Image.new("RGB", (width, height), color)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


class FakeSegmentationModel:
    def __init__(self):
        self.calls = 0
        self.input_tensor = None

    def load_state_dict(self, state_dict, strict=True):
        assert strict is True
        assert "test.weight" in state_dict

    def to(self, device):
        self.device = device
        return self

    def eval(self):
        return self

    def __call__(self, tensor):
        import torch

        self.calls += 1
        self.input_tensor = tensor.detach().cpu()
        logits = torch.full((1, 104, 160, 160), -5.0, device=tensor.device)
        logits[:, 0] = 4.0
        logits[:, 1, :, :80] = 8.0
        return {"out": logits}


def configured_service(tmp_path, monkeypatch, model=None):
    torch = pytest.importorskip("torch")
    checkpoint = tmp_path / "foodseg-test.pth"
    labels = {str(i): ("background" if i == 0 else f"class {i}") for i in range(104)}
    labels["1"] = "candy"
    payload = {
        "model_name": "fcn_resnet50",
        "num_classes": 104,
        "image_size": 160,
        "state_dict": {"test.weight": torch.tensor([1.0])},
        "id2label": labels,
        "metrics": {"val_miou_excluding_background": 0.25},
        "dataset_id": "Tubisi/FoodSeg103",
    }
    torch.save(payload, checkpoint)
    service = FoodSeg103Inference(checkpoint)
    fake_model = model or FakeSegmentationModel()
    built = []

    def build(model_name, num_classes):
        built.append((model_name, num_classes))
        return fake_model

    monkeypatch.setattr(service, "_build_model", build)
    return service, fake_model, built


def test_checkpoint_is_loaded_safely_and_cached_with_verified_class_mapping(tmp_path, monkeypatch):
    service, model, built = configured_service(tmp_path, monkeypatch)

    first = service.predict_data_url(png_data_url())
    second = service.predict_data_url(png_data_url())

    assert built == [("fcn_resnet50", 104)]
    assert model.calls == 2
    assert first["method"] == "foodseg103_segmentation"
    assert first["foods"][0]["class_id"] == 1
    assert first["foods"][0]["food_name"] == "candy"
    assert first["foods"][0]["area_pixels"] == 320
    assert first["foods"][0]["area_fraction"] == pytest.approx(0.5)
    assert first["foods"][0]["estimated_quantity_g"] is None
    assert first["foods"][0]["confidence"] is None
    assert second["foods"] == first["foods"]
    assert service.status["status"] == "ready"


def test_preprocessing_matches_training_normalization_and_overlay_is_original_size(tmp_path, monkeypatch):
    Image = pytest.importorskip("PIL.Image")
    service, model, _ = configured_service(tmp_path, monkeypatch)
    result = service.predict_data_url(png_data_url(width=32, height=20))

    assert tuple(model.input_tensor.shape) == (1, 3, 160, 160)
    assert float(model.input_tensor[0, 0, 0, 0]) == pytest.approx((1.0 - 0.485) / 0.229, abs=1e-5)
    assert float(model.input_tensor[0, 1, 0, 0]) == pytest.approx((0.0 - 0.456) / 0.224, abs=1e-5)
    assert result["original_width"] == 32
    assert result["original_height"] == 20
    overlay_bytes = base64.b64decode(result["mask_overlay_data_url"].split(",", 1)[1])
    with Image.open(io.BytesIO(overlay_bytes)) as overlay:
        assert overlay.size == (32, 20)
        assert overlay.mode == "RGBA"


def test_invalid_image_is_rejected_before_checkpoint_loading(tmp_path):
    service = FoodSeg103Inference(tmp_path / "missing.pth")
    with pytest.raises(InvalidFoodImageError):
        service.predict_data_url("data:image/png;base64,not-valid-base64!")


def test_missing_checkpoint_reports_unavailable(tmp_path):
    service = FoodSeg103Inference(tmp_path / "missing.pth")
    assert service.status["status"] == "unavailable"
    with pytest.raises(FoodSeg103UnavailableError, match="Checkpoint not found"):
        service._load()


def test_missing_runtime_dependency_reports_unavailable(tmp_path, monkeypatch):
    service, _, _ = configured_service(tmp_path, monkeypatch)

    def missing_runtime():
        raise ModuleNotFoundError("torch is not installed")

    monkeypatch.setattr(service, "_import_runtime", missing_runtime)
    with pytest.raises(FoodSeg103UnavailableError, match="ModuleNotFoundError"):
        service._load()
    assert service.status["status"] == "unavailable"
    assert "torch is not installed" in service.status["reason"]


def test_checkpoint_rejects_wrong_class_count(tmp_path, monkeypatch):
    torch = pytest.importorskip("torch")
    service, _, _ = configured_service(tmp_path, monkeypatch)
    checkpoint = {
        "model_name": "fcn_resnet50", "num_classes": 103, "image_size": 160,
        "state_dict": {"test.weight": torch.tensor([1.0])},
        "id2label": {str(i): ("background" if i == 0 else f"class {i}") for i in range(104)},
    }
    torch.save(checkpoint, service.checkpoint_path)
    with pytest.raises(FoodSeg103UnavailableError, match="Expected 104 output classes"):
        service._load()
