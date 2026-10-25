"""Lazy local inference for a trained FoodSeg103 semantic segmentation checkpoint."""
from __future__ import annotations
import base64, io, os
from pathlib import Path
from typing import Any
import numpy as np
from PIL import Image

class FoodSeg103Inference:
    def __init__(self, checkpoint_path: str | Path | None = None):
        self.checkpoint_path = Path(checkpoint_path or os.getenv('FOODSEG103_CHECKPOINT', '')).expanduser() if (checkpoint_path or os.getenv('FOODSEG103_CHECKPOINT')) else (Path(__file__).resolve().parent.parent / 'models' / 'foodseg103' / 'best_model.pth')
        self._model = None
        self._torch = None
        self._device = None
        self._meta: dict[str, Any] = {}

    @property
    def available(self) -> bool:
        return self.checkpoint_path.is_file()

    def _load(self):
        if self._model is not None: return
        if not self.available: raise FileNotFoundError(f'FoodSeg103 checkpoint not found: {self.checkpoint_path}')
        import torch
        try:
            from train_compare import build_model
        except ModuleNotFoundError:
            import sys
            research_src = Path(__file__).resolve().parent.parent / 'research' / 'food_segmentation' / 'src'
            if str(research_src) not in sys.path: sys.path.insert(0, str(research_src))
            from train_compare import build_model
        payload = torch.load(self.checkpoint_path, map_location='cpu', weights_only=False)
        model_name = payload.get('model_name')
        num_classes = int(payload.get('num_classes', 104))
        if not model_name or 'state_dict' not in payload: raise ValueError('Checkpoint is missing model_name or state_dict.')
        model = build_model(model_name, num_classes=num_classes, pretrained_backbone=False)
        model.load_state_dict(payload['state_dict'])
        if torch.backends.mps.is_available(): device=torch.device('mps')
        elif torch.cuda.is_available(): device=torch.device('cuda')
        else: device=torch.device('cpu')
        model.to(device).eval()
        self._model, self._torch, self._device = model, torch, device
        self._meta = {'model_name':model_name,'num_classes':num_classes,'image_size':int(payload.get('image_size',224)),
                      'id2label':{str(k):str(v) for k,v in payload.get('id2label',{}).items()},'metrics':payload.get('metrics',{}),'dataset_id':payload.get('dataset_id','FoodSeg103')}

    def predict_data_url(self, image_data_url: str, min_area_fraction: float = 0.006, max_foods: int = 12) -> dict[str, Any]:
        self._load()
        if not image_data_url.startswith('data:image/'): raise ValueError('Expected an image data URL.')
        encoded = image_data_url.split(',',1)[1]
        raw = base64.b64decode(encoded, validate=True)
        image = Image.open(io.BytesIO(raw)).convert('RGB')
        size = self._meta['image_size']
        resized = image.resize((size,size),Image.Resampling.BILINEAR)
        arr=np.asarray(resized,dtype=np.float32).copy()/255.0
        torch=self._torch
        tensor=torch.from_numpy(arr).permute(2,0,1).contiguous()
        mean=torch.tensor([0.485,0.456,0.406],dtype=torch.float32)[:,None,None]
        std=torch.tensor([0.229,0.224,0.225],dtype=torch.float32)[:,None,None]
        tensor=((tensor-mean)/std).unsqueeze(0).to(self._device)
        with torch.no_grad():
            output=self._model(tensor)
            logits=output['out'] if isinstance(output,dict) else output
            logits=torch.nn.functional.interpolate(logits,size=(size,size),mode='bilinear',align_corners=False)
            probs=torch.softmax(logits,dim=1)[0]
            pred=probs.argmax(0)
        pred_np=pred.detach().cpu().numpy()
        probs_np=probs.detach().cpu().numpy()
        total=pred_np.size
        labels=self._meta['id2label']
        detections=[]
        for class_id in np.unique(pred_np):
            if int(class_id)==0: continue
            mask=pred_np==class_id
            fraction=float(mask.sum()/total)
            if fraction < min_area_fraction: continue
            confidence=float(probs_np[int(class_id)][mask].mean())
            # Confidence is an uncalibrated model score, not a probability of correctness.
            level='high' if confidence>=0.85 else 'medium' if confidence>=0.65 else 'low'
            name=labels.get(str(int(class_id)), f'Food class {int(class_id)}')
            detections.append({'food_name':name,'estimated_quantity_g':100.0,'confidence':level,
              'notes':f'Local FoodSeg103 model detected this class over {fraction*100:.1f}% of the resized image. The 100 g value is only a placeholder; estimate and confirm the portion manually. Model confidence is not calibrated.'})
        detections.sort(key=lambda x: float(x['notes'].split('over ')[1].split('%')[0]),reverse=True)
        detections=detections[:max_foods]
        return {'foods':detections,'model':self._meta['model_name'],'dataset':self._meta['dataset_id'],
          'device':str(self._device),'image_size':size,'validation_metrics':self._meta.get('metrics',{}),
          'message':'Local FoodSeg103 segmentation results are ready. Review every food name and manually correct each portion before nutrition analysis.',
          'limitation':'This model segments 103 FoodSeg103 ingredient classes and may miss foods outside its label set, especially Sri Lankan dishes. Pixel area is not portion weight; the 100 g values are placeholders. Confidence scores are uncalibrated. Confirm all suggestions before calculating nutrients.'}
