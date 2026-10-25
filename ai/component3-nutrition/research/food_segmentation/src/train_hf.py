#!/usr/bin/env python3
"""Fine-tune and compare torchvision segmentation models on Hugging Face FoodSeg103.

Loads the real dataset's official train/validation splits directly through `datasets`.
No synthetic images or labels are created. Designed for Apple Silicon with a small batch.
"""
from __future__ import annotations
import argparse, csv, json, os, random, shutil, sys, time
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
import numpy as np
from PIL import Image
os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
import torch
from torch import nn
from torch.utils.data import DataLoader, Dataset
from datasets import load_dataset
try:
    from huggingface_hub import hf_hub_download
except ImportError:
    hf_hub_download = None
from train_compare import (NUM_CLASSES, MODEL_NAMES, build_model, choose_device, seed_everything, extract_logits, evaluate)

MEAN = torch.tensor([0.485, 0.456, 0.406], dtype=torch.float32)[:, None, None]
STD = torch.tensor([0.229, 0.224, 0.225], dtype=torch.float32)[:, None, None]

def load_id2label(repo_id: str) -> dict[str, str]:
    if hf_hub_download:
        try:
            p = hf_hub_download(repo_id=repo_id, filename="id2label.json", repo_type="dataset")
            raw = json.loads(Path(p).read_text(encoding="utf-8"))
            return {str(k): str(v) for k, v in raw.items()}
        except Exception as exc:
            print(f"Warning: could not download id2label.json ({type(exc).__name__}); using known FoodSeg103 labels.")
    return {str(i): name for i, name in enumerate([
        "background", "candy", "egg tart", "french fries", "chocolate", "biscuit", "popcorn", "pudding", "ice cream", "cheese butter", "cake", "wine", "milkshake", "coffee", "juice", "milk", "tea", "almond", "red beans", "cashew", "dried cranberries", "soy", "walnut", "peanut", "egg", "apple", "date", "apricot", "avocado", "banana", "strawberry", "cherry", "blueberry", "raspberry", "mango", "olives", "peach", "lemon", "pear", "fig", "pineapple", "grape", "kiwi", "melon", "orange", "watermelon", "steak", "pork", "chicken duck", "sausage", "fried meat", "lamb", "sauce", "crab", "fish", "shellfish", "shrimp", "soup", "bread", "corn", "hamburg", "pizza", "hanamaki baozi", "wonton dumplings", "pasta", "noodles", "rice", "pie", "tofu", "eggplant", "potato", "garlic", "cauliflower", "tomato", "kelp", "seaweed", "spring onion", "rape", "ginger", "okra", "lettuce", "pumpkin", "cucumber", "white radish", "carrot", "asparagus", "bamboo shoots", "broccoli", "celery stick", "cilantro mint", "snow peas", "cabbage", "bean sprouts", "onion", "pepper", "green beans", "French beans", "king oyster mushroom", "shiitake", "enoki mushroom", "oyster mushroom", "white button mushroom", "salad", "other ingredients"])}

class HFDataset(Dataset):
    def __init__(self, hf_split, image_size: int):
        self.data = hf_split
        self.image_size = image_size
    def __len__(self): return len(self.data)
    def __getitem__(self, index):
        row = self.data[index]
        image = row["image"]
        mask = row["label"]
        if not isinstance(image, Image.Image): image = Image.open(image["path"] if isinstance(image, dict) else image)
        if not isinstance(mask, Image.Image): mask = Image.open(mask["path"] if isinstance(mask, dict) else mask)
        image = image.convert("RGB").resize((self.image_size, self.image_size), Image.Resampling.BILINEAR)
        # Preserve integer class IDs. P-mode masks carry IDs in their pixel indices;
        # converting P to RGB would destroy the segmentation labels.
        mask_arr = np.asarray(mask)
        if mask_arr.ndim == 3:
            mask_arr = mask_arr[:, :, 0]
        if mask_arr.dtype != np.uint8:
            mask_arr = mask_arr.astype(np.uint8)
        mask = Image.fromarray(mask_arr, mode="L").resize((self.image_size, self.image_size), Image.Resampling.NEAREST)
        image_tensor = torch.from_numpy(np.asarray(image, dtype=np.float32).copy()).permute(2,0,1).contiguous() / 255.0
        image_tensor = (image_tensor - MEAN) / STD
        mask_array = np.asarray(mask, dtype=np.int64).copy()
        valid = (mask_array == 255) | ((mask_array >= 0) & (mask_array < NUM_CLASSES))
        if not valid.all():
            raise ValueError(f"Unexpected mask class IDs {np.unique(mask_array[~valid])[:10].tolist()} in row {index}; expected 0..103 or 255.")
        return image_tensor, torch.from_numpy(mask_array).long()


def sample_split_indices(total: int, limit: int, seed: int) -> list[int]:
    """Return deterministic indices into an official split; limit<=0 means all rows."""
    if total < 0:
        raise ValueError("total must be non-negative")
    if limit <= 0 or limit >= total:
        return list(range(total))
    return sorted(random.Random(seed).sample(range(total), limit))

def package_version(name: str) -> str | None:
    try:
        return version(name)
    except PackageNotFoundError:
        return None


def train_epoch(model, loader, optimizer, device, max_batches=0):
    model.train()

    # Keep BatchNorm running statistics fixed while training.
    # This is useful for small batches and a small diagnostic dataset.
    for module in model.modules():
        if isinstance(module, nn.modules.batchnorm._BatchNorm):
            module.eval()

    losses = []

    for batch_idx, (images, masks) in enumerate(loader):
        if max_batches and batch_idx >= max_batches:
            break

        images, masks = images.to(device), masks.to(device)
        optimizer.zero_grad(set_to_none=True)

        logits = extract_logits(model(images))

        if logits.shape[-2:] != masks.shape[-2:]:
            logits = nn.functional.interpolate(
                logits,
                size=masks.shape[-2:],
                mode="bilinear",
                align_corners=False,
            )

        loss = nn.functional.cross_entropy(
            logits, masks, ignore_index=255
        )

        if not torch.isfinite(loss):
            raise RuntimeError(f"Non-finite loss: {loss.item()}")

        loss.backward()
        optimizer.step()
        losses.append(float(loss.detach().cpu()))

    if not losses:
        raise RuntimeError(
            "No training batches ran; check the selected dataset and batch limit."
        )

    return float(np.mean(losses))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--dataset-id', default='Tubisi/FoodSeg103')
    p.add_argument('--output-dir', type=Path, default=Path('results/hf_pilot'))
    p.add_argument('--models', nargs='+', choices=MODEL_NAMES, default=['lraspp_mobilenet_v3_large','deeplabv3_mobilenet_v3_large'])
    p.add_argument('--epochs', type=int, default=2)
    p.add_argument('--image-size', type=int, default=160)
    p.add_argument('--batch-size', type=int, default=1)
    p.add_argument('--max-train-images', type=int, default=300, help='0 uses full official training split')
    p.add_argument('--max-val-images', type=int, default=100, help='0 uses full official validation split')
    p.add_argument('--max-train-batches', type=int, default=0, help='Fast smoke test; 0 uses all selected training batches')
    p.add_argument('--device', choices=('auto','mps','cpu','cuda'), default='auto')
    p.add_argument('--learning-rate', type=float, default=1e-4)
    p.add_argument('--no-pretrained-backbone', action='store_true')
    p.add_argument('--seed', type=int, default=42)
    p.add_argument('--deploy-best', action='store_true', help='After all selected models finish, copy the highest-validation-mIoU checkpoint to the live Component 3 model path. Use only after a fair comparison.')
    p.add_argument('--deploy-path', type=Path, default=Path(__file__).resolve().parents[3] / 'models' / 'foodseg103' / 'best_model.pth', help='Destination checkpoint used by the nutrition API')
    args=p.parse_args()
    if args.epochs<1 or args.image_size<64 or args.batch_size<1: p.error('epochs and batch-size must be positive; image-size must be >= 64')
    seed_everything(args.seed); device=choose_device(args.device)
    print(f"Loading {args.dataset_id}; device={device}; image_size={args.image_size}; batch_size={args.batch_size}", flush=True)
    ds=load_dataset(args.dataset_id)
    if 'train' not in ds or 'validation' not in ds: raise RuntimeError(f"Expected official train/validation splits; got {list(ds.keys())}")
    for split in ('train','validation'):
        if len(ds[split]) and not {'image','label'}.issubset(set(ds[split].column_names)):
            raise RuntimeError(f"Unexpected columns in {split}: {ds[split].column_names}; expected image and label")
    train_split, val_split=ds['train'], ds['validation']
    train_indices = sample_split_indices(len(train_split), args.max_train_images, args.seed)
    val_indices = sample_split_indices(len(val_split), args.max_val_images, args.seed + 1)
    train_split = train_split.select(train_indices)
    val_split = val_split.select(val_indices)

    # A pilot checkpoint must not accidentally replace the app's live model.
    # Deployment is allowed only after using both complete official splits and
    # all selected training batches.
    full_official_splits = (
        len(train_split) == len(ds['train'])
        and len(val_split) == len(ds['validation'])
        and args.max_train_batches == 0
    )
    if args.deploy_best and not full_official_splits:
        raise ValueError(
            "Refusing to deploy a pilot checkpoint. Use the complete official "
            "train/validation splits (--max-train-images 0 --max-val-images 0) "
            "and no --max-train-batches before passing --deploy-best."
        )
    labels=load_id2label(args.dataset_id)
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise FileExistsError(
            f"Refusing to overwrite non-empty output directory: {args.output_dir}. "
            "Choose a new run-specific output directory."
        )
    args.output_dir.mkdir(parents=True,exist_ok=True)
    manifest={'dataset':args.dataset_id,'dataset_format':'Hugging Face datasets image segmentation','official_split_used':True,
      'train_available':len(ds['train']),'validation_available':len(ds['validation']),'train_images_used':len(train_split),'validation_images_used':len(val_split),
      'num_classes_including_background':NUM_CLASSES,'id2label':labels,'device':str(device),'image_size':args.image_size,'batch_size':args.batch_size,
      'epochs':args.epochs,'seed':args.seed,'pretrained_backbone':not args.no_pretrained_backbone,'no_synthetic_data':True,
      'train_selected_indices':train_indices,'validation_selected_indices':val_indices,
      'ignore_index':255,
      'preprocessing': {'image_mode':'RGB','image_resize':'bilinear','mask_resize':'nearest',
        'normalization_mean':[0.485,0.456,0.406],'normalization_std':[0.229,0.224,0.225]},
      'max_train_batches':args.max_train_batches,'learning_rate_classifier':args.learning_rate,
      'learning_rate_backbone':args.learning_rate * 0.1,'optimizer':'AdamW','weight_decay':1e-4,
      'batch_norm_running_stats_frozen':True,
      'software': {'python': sys.version, 'platform': sys.platform, 'torch': torch.__version__,
        'torchvision': package_version('torchvision'), 'numpy': np.__version__, 'Pillow': package_version('Pillow'),
        'datasets': package_version('datasets'), 'huggingface_hub': package_version('huggingface_hub'),
        'device_name': ('Apple MPS' if device.type == 'mps' else torch.cuda.get_device_name(0) if device.type == 'cuda' else 'CPU')},
      'model_configurations': {name: {'architecture': name, 'pretrained_backbone': not args.no_pretrained_backbone,
        'backbone_lr': args.learning_rate * 0.1, 'head_lr': args.learning_rate,
        'architecture_note': ('LRASPP has low- and high-resolution classifier branches.' if name == 'lraspp_mobilenet_v3_large' else 'Torchvision FCN/DeepLabV3 classifier head.')}
        for name in args.models}}
    (args.output_dir/'run_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    train_loader=DataLoader(HFDataset(train_split,args.image_size),batch_size=args.batch_size,shuffle=True,num_workers=0,pin_memory=False)
    val_loader=DataLoader(HFDataset(val_split,args.image_size),batch_size=1,shuffle=False,num_workers=0,pin_memory=False)
    rows=[]
    for model_name in args.models:
        print(f'\n=== {model_name} ===',flush=True); seed_everything(args.seed)
        model=build_model(model_name,pretrained_backbone=not args.no_pretrained_backbone).to(device)
        optimizer = torch.optim.AdamW(
            [
                {
                    "params": model.backbone.parameters(),
                    "lr": args.learning_rate * 0.1,
                },
                {
                    "params": model.classifier.parameters(),
                    "lr": args.learning_rate,
                },
            ],
            weight_decay=1e-4,
        )
        model_dir=args.output_dir/model_name; model_dir.mkdir(parents=True,exist_ok=True)
        best=-1.0; history=[]; model_training_seconds=0.0; best_epoch=None
        for epoch in range(1,args.epochs+1):
            started=time.perf_counter(); loss=train_epoch(model,train_loader,optimizer,device,args.max_train_batches)
            if device.type == 'mps': torch.mps.synchronize()
            train_seconds=time.perf_counter()-started
            eval_started=time.perf_counter(); metrics=evaluate(model,val_loader,device,NUM_CLASSES)
            if device.type == 'mps': torch.mps.synchronize()
            eval_seconds=time.perf_counter()-eval_started
            model_training_seconds += train_seconds
            record={'epoch':epoch,'train_loss':loss,**{k:v for k,v in metrics.items() if k!='per_class_iou'},'training_seconds':train_seconds,'evaluation_seconds':eval_seconds,'epoch_seconds':train_seconds+eval_seconds}; history.append(record)
            print(f"epoch {epoch}/{args.epochs} loss={loss:.4f} val_loss={metrics['val_loss']:.4f} val_mIoU={metrics['val_miou_excluding_background']:.4f} pixel_acc={metrics['val_pixel_accuracy']:.4f} train={train_seconds:.1f}s eval={eval_seconds:.1f}s",flush=True)
            score=metrics['val_miou_excluding_background']
            if score>best:
                best=score
                best_epoch=epoch
                best_metrics={**metrics,'best_epoch':epoch}
                torch.save({'model_name':model_name,'num_classes':NUM_CLASSES,'image_size':args.image_size,'best_epoch':epoch,'state_dict':model.state_dict(),'metrics':best_metrics,'id2label':labels,'dataset_id':args.dataset_id},model_dir/'best_model.pth')
                (model_dir/'best_metrics.json').write_text(json.dumps(best_metrics,indent=2),encoding='utf-8')
        (model_dir/'history.json').write_text(json.dumps(history,indent=2),encoding='utf-8')
        best_record=history[best_epoch-1]
        rows.append({'model':model_name,'best_epoch':best_epoch,'best_val_miou_excluding_background':best,'best_val_pixel_accuracy':best_record['val_pixel_accuracy'],'best_val_loss':best_record['val_loss'],'val_classes_present':best_record['val_classes_present'],'mean_inference_ms_per_image':best_record['mean_inference_ms_per_image'],'training_time_seconds':model_training_seconds,'epochs_completed':len(history),'train_images':len(train_split),'validation_images':len(val_split),'image_size':args.image_size,'batch_size':args.batch_size,'device':str(device),'checkpoint':str((model_dir/'best_model.pth').resolve())})
        del model,optimizer
        if device.type=='mps':
            try: torch.mps.empty_cache()
            except Exception: pass
    rows.sort(key=lambda x:x['best_val_miou_excluding_background'],reverse=True)
    with (args.output_dir/'model_comparison.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0].keys()));w.writeheader();w.writerows(rows)
    (args.output_dir/'summary.json').write_text(json.dumps({'selection_rule':'highest validation mIoU excluding background; pilot results are exploratory','ranked_models':rows},indent=2),encoding='utf-8')
    print('\nRanked models by validation mIoU:')
    for i,r in enumerate(rows,1): print(f"{i}. {r['model']}: {r['best_val_miou_excluding_background']:.4f}")
    print(f"Results: {(args.output_dir/'model_comparison.csv').resolve()}")
    if args.deploy_best:
        winner=rows[0]
        source=Path(winner['checkpoint'])
        args.deploy_path.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source,args.deploy_path)
        print(f"\nDeployed {winner['model']} checkpoint to {args.deploy_path.resolve()}")
        print('Verify that this comparison used the intended dataset split and training budget before reporting it as a final research result.')
if __name__=='__main__': main()
