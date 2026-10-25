"""Fast offline regression tests for FoodSeg103 training utilities."""
from __future__ import annotations
import sys
import types
import unittest

# The training script only needs `datasets.load_dataset` when its CLI runs.
# Stub that import so these tests work offline without downloading the dataset.
datasets_stub = types.ModuleType("datasets")
datasets_stub.load_dataset = lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("Dataset loading is not used in unit tests"))
sys.modules.setdefault("datasets", datasets_stub)

from pathlib import Path
import numpy as np
import torch
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from train_hf import HFDataset, sample_split_indices, train_epoch
from train_compare import evaluate


class FakeSplit:
    def __init__(self, rows):
        self.rows = rows
    def __len__(self):
        return len(self.rows)
    def __getitem__(self, index):
        return self.rows[index]
    def select(self, indices):
        return FakeSplit([self.rows[i] for i in indices])


class TinySegModel(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.bn = torch.nn.BatchNorm2d(3)
        self.conv = torch.nn.Conv2d(3, 104, kernel_size=1)
    def forward(self, x):
        return self.conv(self.bn(x))


class TrainingUtilityTests(unittest.TestCase):
    def test_sample_indices_are_deterministic_and_bounded(self):
        a = sample_split_indices(100, 12, 42)
        b = sample_split_indices(100, 12, 42)
        self.assertEqual(a, b)
        self.assertEqual(len(a), 12)
        self.assertEqual(a, sorted(set(a)))
        self.assertEqual(sample_split_indices(4, 0, 1), [0, 1, 2, 3])

    def test_hf_dataset_preserves_class_id_mask_values(self):
        image = Image.fromarray(np.zeros((8, 10, 3), dtype=np.uint8), mode="RGB")
        mask_array = np.zeros((8, 10), dtype=np.uint8)
        mask_array[:, 5:] = 84
        mask = Image.fromarray(mask_array, mode="L")
        ds = HFDataset(FakeSplit([{"image": image, "label": mask}]), image_size=16)
        image_tensor, mask_tensor = ds[0]
        self.assertEqual(tuple(image_tensor.shape), (3, 16, 16))
        self.assertEqual(tuple(mask_tensor.shape), (16, 16))
        self.assertEqual(set(torch.unique(mask_tensor).tolist()), {0, 84})

    def test_training_freezes_batchnorm_running_statistics(self):
        torch.manual_seed(7)
        model = TinySegModel()
        optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3)
        loader = [(torch.randn(2, 3, 8, 8), torch.randint(0, 104, (2, 8, 8)))]
        before = model.bn.running_mean.clone()
        loss = train_epoch(model, loader, optimizer, torch.device("cpu"))
        self.assertTrue(np.isfinite(loss))
        self.assertTrue(torch.equal(before, model.bn.running_mean))

    def test_evaluation_returns_finite_metrics(self):
        model = TinySegModel()
        from torch.utils.data import DataLoader, TensorDataset
        loader = DataLoader(TensorDataset(torch.randn(1, 3, 8, 8), torch.randint(0, 104, (1, 8, 8))), batch_size=1)
        metrics = evaluate(model, loader, torch.device("cpu"), 104)
        self.assertTrue(np.isfinite(metrics["val_miou_excluding_background"]))
        self.assertTrue(np.isfinite(metrics["val_pixel_accuracy"]))
        self.assertTrue(np.isfinite(metrics["val_loss"]))
        self.assertEqual(len(metrics["per_class_iou"]), 104)


if __name__ == "__main__":
    unittest.main()
