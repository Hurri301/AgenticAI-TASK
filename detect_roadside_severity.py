#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Any, Tuple

import numpy as np
from PIL import Image
import cv2
from tqdm import tqdm

import torch
from torchvision.ops import box_convert

import groundingdino.datasets.transforms as T
from groundingdino.models import build_model
from groundingdino.util.misc import clean_state_dict
from groundingdino.util.slconfig import SLConfig
from groundingdino.util.utils import get_phrases_from_posmap

from transformers import AutoProcessor, AutoModelForZeroShotObjectDetection

# SAM (segment-anything). We'll use the Meta SAM v1 in transformers for simplicity.
from transformers import SamModel, SamProcessor


# ---------------------------
# Config
# ---------------------------
@dataclass
class Det:
    label: str
    score: float
    box_xyxy: Tuple[int, int, int, int]  # x1,y1,x2,y2
    mask: np.ndarray | None = None


DEFAULT_PROMPTS = [
    # roadside objects
    "tree",
    "traffic sign",
    "pole",
    "utility pole",
    "post",
    "guardrail",
    "metal guardrail",
    "concrete barrier",
    "wire rope barrier",
    "building",
    "structure",
    "ditch",
    "drainage ditch",
    # NOTE: slope/cliff are *not* reliably detectable in 2D; still can propose:
    "cliff",
    "steep slope",
]

GROUNDINGDINO_TRANSFORM = T.Compose(
    [
        T.RandomResize([800], max_size=1333),
        T.ToTensor(),
        T.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    ]
)


def load_image_rgb(path: str) -> np.ndarray:
    img = Image.open(path).convert("RGB")
    return np.array(img)


def ensure_dir(p: Path) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)


def find_repo_root() -> Path:
    starts = [Path.cwd().resolve(), Path(__file__).resolve()]
    for start in starts:
        for item in [start] + list(start.parents):
            if (item / "GroundingDINO").is_dir():
                return item
    return Path(__file__).resolve().parent


def default_groundingdino_config(repo_root: Path) -> Path:
    return repo_root / "GroundingDINO" / "groundingdino" / "config" / "GroundingDINO_SwinT_OGC.py"


def default_groundingdino_checkpoint(repo_root: Path) -> Path:
    return repo_root / "GroundingDINO" / "weights" / "groundingdino_swint_ogc.pth"


def preprocess_caption(caption: str) -> str:
    text = caption.lower().strip()
    return text if text.endswith(".") else f"{text}."


def load_local_groundingdino_model(config_file: Path, checkpoint_file: Path, device: str):
    args = SLConfig.fromfile(str(config_file))
    args.device = device
    model = build_model(args)

    checkpoint = torch.load(str(checkpoint_file), map_location="cpu")
    state = checkpoint["model"] if isinstance(checkpoint, dict) and "model" in checkpoint else checkpoint
    model.load_state_dict(clean_state_dict(state), strict=False)
    model.eval()
    return model.to(device)


# ---------------------------
# GroundingDINO detector
# ---------------------------
class GroundingDINODetector:
    """
    Open-vocabulary detection.

    Prefer the local GroundingDINO repo/checkpoint already used by the Codex skill:
    - GroundingDINO/groundingdino/config/GroundingDINO_SwinT_OGC.py
    - GroundingDINO/weights/groundingdino_swint_ogc.pth

    Fall back to the Hugging Face model only if the local files are unavailable.
    """
    def __init__(self, device: str = "cuda"):
        self.device = device
        repo_root = find_repo_root()
        config_file = default_groundingdino_config(repo_root)
        checkpoint_file = default_groundingdino_checkpoint(repo_root)

        self.backend = "hf"
        self.processor = None
        if config_file.is_file() and checkpoint_file.is_file():
            if str(repo_root / "GroundingDINO") not in sys.path:
                sys.path.insert(0, str(repo_root / "GroundingDINO"))
            self.model = load_local_groundingdino_model(config_file, checkpoint_file, device)
            self.backend = "local"
        else:
            self.processor = AutoProcessor.from_pretrained("IDEA-Research/grounding-dino-base")
            self.model = AutoModelForZeroShotObjectDetection.from_pretrained(
                "IDEA-Research/grounding-dino-base"
            ).to(device)
        self.model.eval()

    @torch.no_grad()
    def detect(
        self,
        image_rgb: np.ndarray,
        prompts: List[str],
        box_threshold: float = 0.25,
        text_threshold: float = 0.25,
        max_dets: int = 100,
    ) -> List[Det]:
        if self.backend == "local":
            return self._detect_local(
                image_rgb=image_rgb,
                prompts=prompts,
                box_threshold=box_threshold,
                text_threshold=text_threshold,
                max_dets=max_dets,
            )
        return self._detect_hf(
            image_rgb=image_rgb,
            prompts=prompts,
            box_threshold=box_threshold,
            text_threshold=text_threshold,
            max_dets=max_dets,
        )

    def _detect_hf(
        self,
        image_rgb: np.ndarray,
        prompts: List[str],
        box_threshold: float,
        text_threshold: float,
        max_dets: int,
    ) -> List[Det]:
        pil = Image.fromarray(image_rgb)

        # join prompts into a single query text; groundingDINO works well with period-separated phrases
        text = ". ".join(prompts) + "."

        inputs = self.processor(images=pil, text=text, return_tensors="pt").to(self.device)
        outputs = self.model(**inputs)

        # Post-process to boxes in absolute pixel coords
        target_sizes = torch.tensor([pil.size[::-1]]).to(self.device)  # (h,w)
        # results = self.processor.post_process_grounded_object_detection(
        #     outputs,
        #     inputs.input_ids,
        #     box_threshold=box_threshold,
        #     text_threshold=text_threshold,
        #     target_sizes=target_sizes,
        # )[0]
        # transformers versions differ: some expect positional thresholds
        # signature in many builds: (outputs, input_ids, box_threshold, text_threshold, target_sizes)
        results = self.processor.post_process_grounded_object_detection(
            outputs,
            inputs.input_ids,
            box_threshold,
            text_threshold,
            target_sizes=target_sizes,
        )[0]

        boxes = results["boxes"].detach().cpu().numpy()  # xyxy
        scores = results["scores"].detach().cpu().numpy()
        labels = results["labels"]

        dets: List[Det] = []
        for box, score, lbl in zip(boxes, scores, labels):
            if len(dets) >= max_dets:
                break
            x1, y1, x2, y2 = box.tolist()
            dets.append(
                Det(
                    label=str(lbl),
                    score=float(score),
                    box_xyxy=(int(x1), int(y1), int(x2), int(y2)),
                )
            )
        return dets

    def _detect_local(
        self,
        image_rgb: np.ndarray,
        prompts: List[str],
        box_threshold: float,
        text_threshold: float,
        max_dets: int,
    ) -> List[Det]:
        pil = Image.fromarray(image_rgb)
        _, image_tensor = GROUNDINGDINO_TRANSFORM(pil, None)
        caption = preprocess_caption(". ".join(prompts))

        with torch.no_grad():
            outputs = self.model(image_tensor[None].to(self.device), captions=[caption])

        prediction_logits = outputs["pred_logits"].cpu().sigmoid()[0]
        prediction_boxes = outputs["pred_boxes"].cpu()[0]

        keep_mask = prediction_logits.max(dim=1)[0] > box_threshold
        logits = prediction_logits[keep_mask]
        boxes = prediction_boxes[keep_mask]

        if boxes.numel() == 0:
            return []

        tokenizer = self.model.tokenizer
        tokenized = tokenizer(caption)
        phrases = [
            get_phrases_from_posmap(logit > text_threshold, tokenized, tokenizer).replace(".", "")
            for logit in logits
        ]
        scores = logits.max(dim=1)[0]

        width, height = pil.size
        scale = torch.tensor([width, height, width, height], dtype=boxes.dtype)
        xyxy = box_convert(boxes * scale, in_fmt="cxcywh", out_fmt="xyxy")
        xyxy[:, 0::2] = xyxy[:, 0::2].clamp(0, max(width - 1, 0))
        xyxy[:, 1::2] = xyxy[:, 1::2].clamp(0, max(height - 1, 0))
        xyxy = xyxy.round().to(dtype=torch.int64)

        dets: List[Det] = []
        ranked = sorted(
            zip(xyxy.tolist(), scores.tolist(), phrases),
            key=lambda item: item[1],
            reverse=True,
        )
        for box, score, phrase in ranked[:max_dets]:
            x1, y1, x2, y2 = box
            dets.append(
                Det(
                    label=str(phrase),
                    score=float(score),
                    box_xyxy=(int(x1), int(y1), int(x2), int(y2)),
                )
            )
        return dets


# ---------------------------
# SAM segmenter (boxes -> masks)
# ---------------------------
class SAMSegmenter:
    """
    Segment Anything via transformers:
    - model: facebook/sam-vit-base
    """
    def __init__(self, device: str = "cuda"):
        self.device = device
        self.processor = SamProcessor.from_pretrained("facebook/sam-vit-base")
        self.model = SamModel.from_pretrained("facebook/sam-vit-base").to(device)
        self.model.eval()

    @torch.no_grad()
    def segment_boxes(self, image_rgb: np.ndarray, dets: List[Det]) -> List[Det]:
        if not dets:
            return dets

        pil = Image.fromarray(image_rgb)

        # SAM expects boxes as (x1, y1, x2, y2) in pixel coords
        input_boxes = [list(d.box_xyxy) for d in dets]

        inputs = self.processor(
            pil,
            input_boxes=[input_boxes],  # batch=1
            return_tensors="pt"
        ).to(self.device)

        outputs = self.model(**inputs)
        # masks: (batch, num_boxes, 1, H, W) in model output resolution; processor will postprocess
        masks = self.processor.post_process_masks(
            outputs.pred_masks.cpu(),
            inputs["original_sizes"].cpu(),
            inputs["reshaped_input_sizes"].cpu(),
        )[0]  # (num_boxes, 1, H, W)

        masks_np = masks.squeeze(1).numpy().astype(bool)  # (num_boxes, H, W)

        for i, d in enumerate(dets):
            d.mask = masks_np[i]
        return dets


# ---------------------------
# Utilities: visualize and COCO export
# ---------------------------
def draw_dets(image_rgb: np.ndarray, dets: List[Det]) -> np.ndarray:
    img = image_rgb.copy()
    h, w = img.shape[:2]

    for d in dets:
        x1, y1, x2, y2 = d.box_xyxy
        x1 = max(0, min(w - 1, x1))
        x2 = max(0, min(w - 1, x2))
        y1 = max(0, min(h - 1, y1))
        y2 = max(0, min(h - 1, y2))

        cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.putText(
            img,
            f"{d.label}:{d.score:.2f}",
            (x1, max(0, y1 - 6)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 255, 0),
            1,
            cv2.LINE_AA,
        )

        if d.mask is not None:
            # overlay mask lightly
            mask = d.mask.astype(np.uint8) * 255
            colored = np.zeros_like(img)
            colored[:, :, 1] = mask  # green channel
            img = cv2.addWeighted(img, 1.0, colored, 0.25, 0)

    return img


def coco_rle_from_mask(mask: np.ndarray) -> Dict[str, Any]:
    """
    COCO RLE encoding requires pycocotools. We avoid dependency here by exporting polygons later if needed.
    For now: store binary mask as PNG path; it's simpler for training YOLOv8-seg.
    """
    raise NotImplementedError


def save_mask_png(mask: np.ndarray, out_path: Path) -> None:
    ensure_dir(out_path)
    m = (mask.astype(np.uint8) * 255)
    Image.fromarray(m).save(out_path)


def run_single_image(
    img_path: str,
    out_dir: str,
    prompts: List[str],
    box_th: float,
    text_th: float,
    do_sam: bool,
    device: str,
) -> None:
    image_rgb = load_image_rgb(img_path)
    det_model = GroundingDINODetector(device=device)
    dets = det_model.detect(
        image_rgb=image_rgb,
        prompts=prompts,
        box_threshold=box_th,
        text_threshold=text_th,
    )

    seg_model = None
    if do_sam:
        seg_model = SAMSegmenter(device=device)
        dets = seg_model.segment_boxes(image_rgb, dets)

    out_dir_p = Path(out_dir)
    out_dir_p.mkdir(parents=True, exist_ok=True)

    # Save visualization
    vis = draw_dets(image_rgb, dets)
    vis_path = out_dir_p / (Path(img_path).stem + "_overlay.png")
    Image.fromarray(vis).save(vis_path)

    # Save masks if available
    masks_dir = out_dir_p / "masks" / Path(img_path).stem
    ann = []
    for i, d in enumerate(dets):
        rec = {
            "label": d.label,
            "score": d.score,
            "box_xyxy": list(d.box_xyxy),
        }
        if d.mask is not None:
            mask_path = masks_dir / f"{i:04d}_{d.label}.png"
            save_mask_png(d.mask, mask_path)
            rec["mask_png"] = str(mask_path)
        ann.append(rec)

    json_path = out_dir_p / (Path(img_path).stem + "_pred.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({"image": img_path, "predictions": ann}, f, indent=2)

    print(f"Saved overlay: {vis_path}")
    print(f"Saved json:    {json_path}")
    if do_sam:
        print(f"Saved masks:   {masks_dir}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", required=True, help="Path to panorama (png/jpg)")
    ap.add_argument("--out-dir", default="artifacts/dets", help="Output directory")
    ap.add_argument("--device", default=None, help="cuda | mps | cpu (auto if omitted)")
    ap.add_argument("--box-th", type=float, default=0.25)
    ap.add_argument("--text-th", type=float, default=0.25)
    ap.add_argument("--no-sam", action="store_true", help="Disable SAM masks (boxes only)")
    ap.add_argument("--prompts", default=None, help="Comma-separated prompts; default is roadside set")
    args = ap.parse_args()

    if args.device:
        device = args.device
    else:
        if torch.cuda.is_available():
            device = "cuda"
        elif getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
            device = "mps"
        else:
            device = "cpu"

    prompts = DEFAULT_PROMPTS if args.prompts is None else [p.strip() for p in args.prompts.split(",") if p.strip()]
    run_single_image(
        img_path=args.image,
        out_dir=args.out_dir,
        prompts=prompts,
        box_th=args.box_th,
        text_th=args.text_th,
        do_sam=(not args.no_sam),
        device=device,
    )


if __name__ == "__main__":
    main()
