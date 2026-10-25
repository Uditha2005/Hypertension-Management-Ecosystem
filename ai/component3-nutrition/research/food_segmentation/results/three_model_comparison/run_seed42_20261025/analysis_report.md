# FoodSeg103 Three-Model Pilot Analysis

## Scope and source files

This report was calculated from this run's `run_manifest.json`, `model_comparison.csv`, `summary.json`, and the three model-specific `best_metrics.json` files. I also checked the three `history.json` files and the metric implementation in `src/train_compare.py` to verify indexing and epoch selection. No training code, checkpoints, or experiment outputs were changed; this report is the only new file.

The run used the official `Tubisi/FoodSeg103` train and validation splits: 300 of 4,983 training images and 200 of 2,135 validation images, at 160 × 160 pixels, batch size 1, 15 epochs, seed 42, pretrained ImageNet backbones, and Apple MPS. It is a small-subset pilot, not a full-dataset evaluation.

## Class-ID and IoU indexing audit

The manifest contains 104 `id2label` entries, IDs 0 through 103. ID 0 is `background`; IDs 1 through 103 are food labels. The per-class IoU array has 104 entries and uses the same direct index: array element `i` is the IoU for class ID `i`, which maps to `id2label[str(i)]`. The evaluator builds the confusion matrix using those class IDs and emits `iou[i]` at array position `i`; no offset is applied. Background is omitted from the reported mean IoU and from the food rankings below.

`val_classes_present` is the number of foreground classes with non-zero confusion-matrix union (`union > 0`). A `null` per-class IoU means union is zero: the class appeared neither in the validation ground truth nor in predictions, so it is unevaluable for that model on this subset. A value of `0.0` is different: the class had a non-zero union but no intersection, so it is evaluated and scored as zero. The reported present-class counts equal the number of non-null foreground IoUs in each JSON.

Manifest labels for IDs 62 (` hanamaki baozi`) and 91 (` cabbage`) contain leading spaces. They are trimmed only for readability in this report; their IDs are unchanged.

Here is the direct ID audit for several food names that are easy to misalign when an array is shifted:

| Class ID | Manifest label | LRASPP IoU | FCN-ResNet-50 IoU | DeepLabV3 IoU |
|---:|---|---:|---:|---:|
| 4 | chocolate | 0.00% | 0.00% | 0.03% |
| 13 | coffee | 4.88% | 13.13% | 17.88% |
| 29 | banana | 22.23% | 24.42% | 13.43% |
| 66 | rice | 16.29% | 33.82% | 20.90% |
| 73 | tomato | 20.84% | 42.42% | 23.70% |
| 84 | carrot | 37.57% | 48.02% | 31.93% |

These values are taken from array positions 4, 13, 29, 66, 73, and 84 respectively. Any prior interpretation that assigned an entry to a different food because of a shifted index is incorrect; for example, chocolate is ID 4, while banana is ID 29.

## Model comparison

Percentages below are the saved metric fractions multiplied by 100. Validation loss is the saved cross-entropy loss per valid pixel with ignore index 255. Training time is the recorded sum of training-epoch time; inference latency is the recorded mean per image.

| Model | Best epoch | Best val mIoU, foreground | Pixel accuracy | Val loss | Present foreground classes | Inference (ms/image) | Training time | Key strengths and limitations |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| FCN-ResNet-50 | 12 | **13.53%** | **62.79%** | **1.8935** | 86 / 103 | 54.63 | 1,273.74 s (21.23 min) | Highest mIoU and pixel accuracy, and lowest validation loss. Much slower inference and training; 34 evaluable food classes scored zero and 17 were unevaluable. |
| DeepLabV3-MobileNetV3-Large | 15 | 5.97% | 52.71% | 2.2622 | 85 / 103 | 22.68 | 602.24 s (10.04 min) | Strongest on corn, with good carrot and broccoli IoUs; much faster than FCN. Its average IoU is close to LRASPP; 41 evaluable classes scored zero and 18 were unevaluable. Best mIoU occurred at the final epoch. |
| LRASPP-MobileNetV3-Large | 11 | 5.92% | 53.30% | 2.3422 | 90 / 103 | **19.30** | **493.04 s (8.22 min)** | Fastest inference and training, and the most foreground classes with non-zero union. Its mean IoU is low; 40 evaluable classes scored zero and 13 were unevaluable. |

FCN exceeds LRASPP by 7.61 percentage points of mIoU and DeepLabV3 by 7.57 points. Its pixel accuracy is higher by 9.48 points versus LRASPP and 10.08 points versus DeepLabV3. The trade-off is about 2.83× LRASPP's and 2.41× DeepLabV3's measured per-image inference latency. DeepLabV3's mIoU exceeds LRASPP's by only 0.045 percentage points, a negligible separation in this single pilot.

The CSV and summary rank the models identically and their summary metrics agree. Each CSV best epoch agrees with its model's `best_metrics.json` and the maximum-mIoU epoch in its history. Recomputing mIoU as the arithmetic mean of the non-null foreground IoUs agrees with the saved result to within approximately 0.000000005, consistent with float32 rounding. Training seconds also agree with the sum of per-epoch training times.

## Per-class rankings

Rankings exclude background and `null` values. IoUs are percentages. Many classes tie at exactly 0%; to make the requested bottom-ten lists reproducible, ties are ordered by ascending class ID. The lists therefore show ten examples among the tied worst classes, not ten distinct levels of performance.

### FCN-ResNet-50

| Rank | Best class (ID) | IoU | Worst class (ID) | IoU |
|---:|---|---:|---|---:|
| 1 | green beans (95) | 62.48% | candy (1) | 0.00% |
| 2 | french fries (3) | 59.10% | chocolate (4) | 0.00% |
| 3 | corn (59) | 58.83% | cheese butter (9) | 0.00% |
| 4 | broccoli (87) | 53.00% | wine (11) | 0.00% |
| 5 | carrot (84) | 48.02% | milk (15) | 0.00% |
| 6 | strawberry (30) | 45.76% | tea (16) | 0.00% |
| 7 | apple (25) | 43.53% | almond (17) | 0.00% |
| 8 | tomato (73) | 42.42% | cashew (19) | 0.00% |
| 9 | milkshake (12) | 40.37% | dried cranberries (20) | 0.00% |
| 10 | biscuit (5) | 35.79% | soy (21) | 0.00% |

### DeepLabV3-MobileNetV3-Large

| Rank | Best class (ID) | IoU | Worst class (ID) | IoU |
|---:|---|---:|---|---:|
| 1 | corn (59) | 41.27% | candy (1) | 0.00% |
| 2 | carrot (84) | 31.93% | popcorn (6) | 0.00% |
| 3 | broccoli (87) | 31.25% | wine (11) | 0.00% |
| 4 | french fries (3) | 28.92% | milk (15) | 0.00% |
| 5 | bread (58) | 23.78% | tea (16) | 0.00% |
| 6 | tomato (73) | 23.70% | almond (17) | 0.00% |
| 7 | rice (66) | 20.90% | red beans (18) | 0.00% |
| 8 | green beans (95) | 20.79% | cashew (19) | 0.00% |
| 9 | coffee (13) | 17.88% | dried cranberries (20) | 0.00% |
| 10 | steak (46) | 17.60% | soy (21) | 0.00% |

### LRASPP-MobileNetV3-Large

| Rank | Best class (ID) | IoU | Worst class (ID) | IoU |
|---:|---|---:|---|---:|
| 1 | corn (59) | 38.62% | candy (1) | 0.00% |
| 2 | carrot (84) | 37.57% | chocolate (4) | 0.00% |
| 3 | green beans (95) | 34.79% | popcorn (6) | 0.00% |
| 4 | broccoli (87) | 33.00% | milk (15) | 0.00% |
| 5 | apple (25) | 26.35% | tea (16) | 0.00% |
| 6 | banana (29) | 22.23% | almond (17) | 0.00% |
| 7 | french fries (3) | 21.59% | red beans (18) | 0.00% |
| 8 | bread (58) | 20.94% | cashew (19) | 0.00% |
| 9 | tomato (73) | 20.84% | dried cranberries (20) | 0.00% |
| 10 | ice cream (8) | 17.47% | soy (21) | 0.00% |

## Interpretation and limitations

**Measured:** FCN-ResNet-50 led this pilot on foreground mIoU, pixel accuracy, and validation loss. LRASPP was the fastest, while FCN's inference was substantially slower. Corn and carrot were among the strongest classes for all three; many food classes scored zero, and a further 13–18 classes per model were unevaluable on the selected validation subset.

**Potential overfitting, not a proven diagnosis:** training loss fell from epoch 1 to epoch 15 for every model. Validation loss was lowest at epoch 1 in all three histories, while mIoU peaked later: epoch 12 for FCN, epoch 15 for DeepLabV3, and epoch 11 for LRASPP. LRASPP's mIoU declined after epoch 11. The divergence between falling training loss and validation loss that does not improve is a warning sign, but the changing mIoU shows that the metrics do not move together; one small validation subset cannot establish the cause.

This run uses only about 6.0% of the official training split and 9.4% of the validation split. At 160 × 160, small or thin ingredients may lose detail. The pilot does not report ground-truth pixel support counts per class, so the zero IoUs cannot be separated into rare-class failures versus classes that were predicted but absent from ground truth. Pixel accuracy can also be dominated by background and common pixels, so it should not replace foreground mIoU. The per-image latency is measured during validation and should not be treated as a full application latency benchmark including image decoding, resizing, device transfer, and downstream nutrition logic.

The model-selection winner is also chosen using this same 200-image validation subset; its best score therefore has selection bias. These measurements do not establish that FCN is generally superior, or that any model is ready for the hypertension nutrition component.

## Recommended follow-up

1. Reproduce the three-model comparison with the complete official 4,983-image training split and 2,135-image validation split, keeping architectures, pretrained initialization, preprocessing, loss, optimizer groups, frozen BatchNorm, and metric definitions identical. Keep official train and validation examples disjoint.
2. Run at least three fixed, documented seeds. Save the seed-specific training indices/order, histories, per-class IoU, and ground-truth class pixel/image support. Report mean and spread across seeds instead of selecting a model from one run.
3. Benchmark inference after warm-up with repeated runs on the same MPS hardware and batch/image size. Report model-only latency separately from end-to-end image preprocessing and nutrition-pipeline latency.
4. Keep the validation set for selection, then evaluate the chosen candidate on a separate held-out set of real meal images with reviewed ingredient masks. Before using it in the hypertension component, assess ingredient errors and downstream food/portion/nutrition outputs with domain review. Treat class weighting, sampling changes, and tuning as separate, pre-specified experiments applied consistently across models.

## Artifact paths

- `run_manifest.json`
- `model_comparison.csv`
- `summary.json`
- `lraspp_mobilenet_v3_large/best_metrics.json`
- `fcn_resnet50/best_metrics.json`
- `deeplabv3_mobilenet_v3_large/best_metrics.json`
- `analysis_report.md` (this report)
