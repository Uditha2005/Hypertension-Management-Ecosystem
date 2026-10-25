# Component 3 — Food image segmentation model comparison

This folder adds an isolated research experiment for multi-ingredient recognition in meal photos. It does **not** replace the existing Component 3 API or change its current Gemini-based photo workflow.

## What it compares

The script fine-tunes three pretrained semantic-segmentation architectures on the real FoodSeg103 dataset:

1. `fcn_resnet50` — heavier baseline; may be slow or memory-intensive on an 8 GB Mac.
2. `deeplabv3_mobilenet_v3_large` — mobile-backbone DeepLabV3.
3. `lraspp_mobilenet_v3_large` — lightweight segmentation model using MobileNetV3.

FoodSeg103 contains 7,118 real images with pixel-wise ingredient labels (class IDs 0–103). The experiment uses no generated or synthetic images. The code resizes the original images and masks for training; this is normal preprocessing, not synthetic data generation.

## Important status

- This archive includes exploratory pilot checkpoints and logs. They are evidence that the training loop ran, not evidence of a production-ready model.
- The latest 300-train / 200-validation pilot reached 5.92% validation mIoU excluding background at its best epoch. This is low for reliable ingredient segmentation and must not be presented as a final result or deployed to the app.
- The dataset is not bundled with the project; it must be downloaded separately.
- `src/train_hf.py` now records the exact sampled row indices, freezes BatchNorm running statistics for small-batch fine-tuning, uses a lower learning rate for the pretrained backbone than for the new classifier, and blocks accidental deployment from subset/pilot runs.
- Evaluation timing synchronizes MPS/CUDA before recording latency. Existing pilot latency values were generated before this timing fix and should not be used as reliable inference-latency measurements.
- Fast offline regression tests are available in `tests/` and can be run with `python -m unittest discover -s tests -v` after installing the core requirements. The tests use a stub for dataset loading and do not download FoodSeg103.
- This implementation expects official grayscale class-ID masks in `annos/` and images in `Images/` with matching file stems.
- The starter script currently creates a deterministic 70/30 split from paired files. Before reporting final research results, adapt the loader to use the official train/validation lists from the downloaded archive if available. Do not report the pilot metrics as final results.
- FoodSeg103 is not Sri Lankan-specific. It includes a `rice` class, but may not reliably distinguish Sri Lankan dishes/curries that are absent from its label taxonomy.
- Pixel segmentation is not portion-weight estimation and cannot directly reveal sodium or other nutrients.

## 1. Download FoodSeg103

Use the official dataset page/repository and read its licence and terms before use:

- Project repository: https://github.com/ada-yl325/FoodSeg103
- Dataset paper: https://arxiv.org/abs/2105.05409

The official repository describes a password-protected ZIP download. Download it manually from the official link in the repository, then extract it. The expected structure is similar to:

```text
data/FoodSeg103/
├── Images/
└── annos/
```

If the archive includes split files, keep them. The script scans for matching image/mask filenames and attempts to read simple official `train.txt` plus `val.txt`/`test.txt` split lists. If it cannot find usable lists, it falls back to a deterministic 70/30 split and records that caveat in `results/run_manifest.json`. Verify the manifest before reporting final results.

Place the extracted dataset somewhere with at least a few GB of free disk space. Do not commit the dataset or trained checkpoints to Git.

## 2. Create a local environment on Mac M1

Open the repository root in VS Code. In the integrated terminal:

```bash
cd ai/component3-nutrition/research/food_segmentation
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-macos.txt
```

If the PyTorch install fails, follow the current official macOS install selector at https://pytorch.org/get-started/locally/ and choose macOS + Pip. Then install `numpy` and `Pillow` as above. Use a Python version supported by the current PyTorch/torchvision wheels.

Check the installation and MPS availability:

```bash
python -c "import torch, torchvision; print('torch', torch.__version__); print('torchvision', torchvision.__version__); print('MPS available:', torch.backends.mps.is_available())"
```

If MPS is available, the script selects it automatically. The environment variable `PYTORCH_ENABLE_MPS_FALLBACK=1` is set in the script to allow unsupported operations to fall back to CPU where PyTorch permits it.

## 3. Run a small pilot first

From the `food_segmentation` folder, use the actual path to your extracted dataset:

```bash
python src/train_compare.py \
  --data-root /absolute/path/to/data/FoodSeg103 \
  --output-dir results/pilot \
  --epochs 1 \
  --image-size 160 \
  --batch-size 1 \
  --max-train-images 40 \
  --max-val-images 20 \
  --models lraspp_mobilenet_v3_large deeplabv3_mobilenet_v3_large
```

This is only a smoke/pilot run to confirm your Mac can train and evaluate models. It does not produce credible final comparison results. The first run may download pretrained backbone weights, so an internet connection is needed once.

If you hit memory pressure, quit other apps and start with only `lraspp_mobilenet_v3_large`, image size 128 or 160, and batch size 1. Do not start all models simultaneously.

## 4. Run the planned pilot comparison

```bash
python src/train_compare.py \
  --data-root /absolute/path/to/data/FoodSeg103 \
  --output-dir results/pilot \
  --epochs 2 \
  --image-size 224 \
  --batch-size 1 \
  --max-train-images 300 \
  --max-val-images 100
```

This runs all three candidates sequentially. Expect it to take a while on an M1. For the first practical run, FCN-ResNet50 is the most likely candidate to be slow or run into memory pressure; omit it if needed.

## 5. Full experiment after the pilot is stable

Only after confirming the data loader, device and training loop work should you try the full data. The full experiment can take many hours or longer on an M1 with 8 GB RAM. Start with the lightweight models and keep image size at 224 and batch size at 1:

```bash
python src/train_compare.py \
  --data-root /absolute/path/to/data/FoodSeg103 \
  --output-dir results/full_lraspp \
  --epochs 10 \
  --image-size 224 \
  --batch-size 1 \
  --max-train-images 0 \
  --max-val-images 0 \
  --models lraspp_mobilenet_v3_large
```

Then run the other models in separate commands and separate output folders. Do not run multiple trainings in parallel. Check `results/run_manifest.json` to confirm whether official split files were detected. If not, do not report the fallback 70/30 split as an official benchmark; adjust the loader to the exact split-file format in your archive before formal reporting.

## 6. Results and model selection

Each run writes:

- `model_comparison.csv` — ranked candidate comparison.
- `summary.json` — ranked model list and selection rule.
- `run_manifest.json` — dataset counts and run configuration.
- `<model>/best_model.pth` — checkpoint with best observed validation mIoU.
- `<model>/history.json` and `<model>/best_metrics.json` — training history and per-class IoU.

Primary metric: mean Intersection over Union (mIoU) over classes present in validation, excluding background. Secondary metric: pixel accuracy. Inference time is an approximate model-forward measurement and excludes image loading/preprocessing. Select the winner only after a fair full-data comparison using the same official split, class mapping, resolution, epoch policy and seed. For stronger evidence, repeat with multiple seeds and report mean and spread.

## 7. Dataset citation

Wu, X. et al. (2021). *A Large-Scale Benchmark for Food Image Segmentation*. ACM Multimedia. https://arxiv.org/abs/2105.05409

The upstream repository identifies the project as Apache-2.0, but verify the dataset download terms and source-image restrictions yourself before redistribution or publication.


## Direct Hugging Face workflow (recommended for the Tubisi dataset page)

The Hugging Face mirror stores the dataset in Parquet format, not the `Images/` + `annos/` directory layout. Use `src/train_hf.py`; it loads the official `train` and `validation` splits through the `datasets` library and preserves the provided split rather than making a random split.

Install in the project venv:

```bash
python -m pip install -r requirements-macos.txt
```

Run a quick end-to-end smoke/pilot (download/cache occurs automatically; internet required on first run):

```bash
python src/train_hf.py --output-dir results/hf_smoke --epochs 1 --image-size 128 --batch-size 1 --max-train-images 12 --max-val-images 6 --max-train-batches 2 --models lraspp_mobilenet_v3_large
```

After the smoke run completes successfully, run a larger pilot:

```bash
python src/train_hf.py --output-dir results/hf_pilot --epochs 2 --image-size 160 --batch-size 1 --max-train-images 300 --max-val-images 100 --models lraspp_mobilenet_v3_large deeplabv3_mobilenet_v3_large
```

For a formal comparison, use the complete official splits and the same training policy for each candidate. This can take many hours on an 8 GB M1. Keep one model training at a time and check free disk space; Hugging Face cache plus checkpoints require additional space. For example, after the smoke and pilot succeed, a full comparison that automatically deploys the validation-mIoU winner is:

```bash
python src/train_hf.py \
  --output-dir results/full_comparison \
  --epochs 5 --image-size 192 --batch-size 1 \
  --max-train-images 0 --max-val-images 0 \
  --models lraspp_mobilenet_v3_large deeplabv3_mobilenet_v3_large fcn_resnet50 \
  --deploy-best
```

If FCN-ResNet50 exhausts memory, stop and rerun the comparison with the two MobileNet models, using the same image size, split, epoch count and seed. Report that limitation; do not compare runs with materially different budgets as if they were equal. Pilot scores are not final research results.

### Connect the trained model to the app

With `--deploy-best`, the training script automatically copies the highest validation-mIoU checkpoint to `ai/component3-nutrition/models/foodseg103/best_model.pth`, which is the checkpoint path read by the nutrition API. The checkpoint includes its class mapping. Alternatively set `FOODSEG103_CHECKPOINT` to a full checkpoint path. Restart the nutrition API after deployment. If no local checkpoint exists, the existing Gemini photo-recognition path remains available when `GEMINI_API_KEY` is configured. The API `/health` response reports whether the local FoodSeg103 checkpoint is available and which recognition method is active.

The segmentation model predicts ingredient classes and pixel regions only. It does not estimate grams or nutrient values. The UI's 100 g suggestion is explicitly a placeholder that must be reviewed and edited by the user; nutrient totals continue to come from selected USDA food records.
