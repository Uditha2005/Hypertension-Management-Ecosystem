import sys
from pathlib import Path
from collections import Counter

SRC_DIR = Path(__file__).resolve().parent / "src"
sys.path.insert(0, str(SRC_DIR))

import torch
from datasets import load_dataset
from train_hf import HFDataset
from train_compare import build_model, choose_device, extract_logits

SRC_DIR = Path(__file__).resolve().parent / "src"
sys.path.insert(0, str(SRC_DIR))

device = choose_device("auto")
ds = load_dataset("Tubisi/FoodSeg103")
data = HFDataset(ds["validation"].select(range(20)), 128)

checkpoint = torch.load(
    "results/hf_learning_check/lraspp_mobilenet_v3_large/best_model.pth",
    map_location="cpu",
    weights_only=False,
)

model = build_model(
    checkpoint["model_name"],
    pretrained_backbone=False,
)
model.load_state_dict(checkpoint["state_dict"])
model.to(device).eval()

with torch.no_grad():
    image, mask = data[0]
    logits = extract_logits(model(image.unsqueeze(0).to(device)))
    prediction = logits.argmax(1).cpu().squeeze().numpy()

print("Ground-truth class counts:", Counter(mask.numpy().ravel()).most_common(15))
print("Predicted class counts:", Counter(prediction.ravel()).most_common(15))
print("Checkpoint metrics:", checkpoint["metrics"])
