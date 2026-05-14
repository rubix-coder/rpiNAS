"""GPU-accelerated CLIP aesthetic scorer + CPU image quality metrics."""
from __future__ import annotations

import json
import math
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import cv2
import imagehash
import numpy as np
from PIL import Image

_MODEL_LOCK = threading.Lock()

SCENE_LABELS = [
    "beach sunset", "mountain landscape", "forest trail", "city skyline at night",
    "family portrait", "group of friends", "wedding ceremony", "birthday party",
    "baby or toddler", "pet dog", "pet cat", "wildlife animal",
    "food and meal", "coffee and drinks", "travel and tourism",
    "architecture building", "flower garden", "sports and action",
    "snow and winter", "autumn leaves", "night sky with stars",
    "indoor home decor", "graduation ceremony", "holiday christmas",
    "street photography", "concert performance", "nature waterfall",
    "car and vehicle", "bicycle and cycling", "boat and water",
]


@dataclass
class ScoreResult:
    aesthetic: float
    sharpness: float
    exposure: float
    face_count: int
    face_rects: list[list[int]]  # [[x,y,w,h], ...]
    composite: float
    phash: str
    width: int
    height: int
    captured_at: datetime | None
    scene_label: str


class AestheticScorer:
    """Loads CLIP ViT-L-14 + laion-aesthetic linear head. Thread-safe after load()."""

    def __init__(self, device: str, model_name: str, pretrained: str, weights_path: str):
        self.device = device
        self.model_name = model_name
        self.pretrained = pretrained
        self.weights_path = weights_path
        self._model = None
        self._preprocess = None
        self._text_features = None  # cached scene label embeddings

    def load(self) -> None:
        """Load CLIP model and aesthetic linear head. Idempotent."""
        if self._model is not None:
            return
        with _MODEL_LOCK:
            if self._model is not None:
                return
            import open_clip
            import torch
            import torch.nn as nn

            clip_model, _, preprocess = open_clip.create_model_and_transforms(
                self.model_name, pretrained=self.pretrained
            )
            clip_model = clip_model.to(self.device).eval()

            class _AestheticHead(nn.Module):
                def __init__(self, input_dim: int = 768):
                    super().__init__()
                    self.layers = nn.Sequential(
                        nn.Linear(input_dim, 1024),
                        nn.Dropout(0.2),
                        nn.Linear(1024, 128),
                        nn.Dropout(0.2),
                        nn.Linear(128, 64),
                        nn.Dropout(0.1),
                        nn.Linear(64, 16),
                        nn.Linear(16, 1),
                    )

                def forward(self, x):
                    return self.layers(x)

            head = _AestheticHead()
            weights_file = Path(self.weights_path)
            if weights_file.exists():
                import torch
                head.load_state_dict(torch.load(str(weights_file), map_location="cpu"))
            head = head.to(self.device).eval()

            self._clip = clip_model
            self._head = head
            self._preprocess = preprocess
            self._open_clip = open_clip
            self._torch = torch

            # Pre-compute scene label text embeddings once
            tokenizer = open_clip.get_tokenizer(self.model_name)
            tokens = tokenizer(SCENE_LABELS).to(self.device)
            with torch.no_grad():
                text_feats = clip_model.encode_text(tokens)
                text_feats = text_feats / text_feats.norm(dim=-1, keepdim=True)
            self._text_features = text_feats
            self._model = True  # sentinel

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    def score_batch(self, pil_images: list[Image.Image]) -> tuple[list[float], list[str]]:
        """
        GPU batch inference.
        Returns (aesthetic_scores 0–10, scene_label_slugs) — one per image.
        """
        import torch

        tensors = torch.stack([self._preprocess(img) for img in pil_images]).to(self.device)

        with torch.no_grad():
            image_features = self._clip.encode_image(tensors)
            image_features_norm = image_features / image_features.norm(dim=-1, keepdim=True)

            # Aesthetic scores
            aesthetic_raw = self._head(image_features_norm.float()).squeeze(-1)
            aesthetic_scores = aesthetic_raw.clamp(0, 10).cpu().tolist()

            # Scene classification via cosine similarity with pre-computed text features
            similarity = (image_features_norm @ self._text_features.T)
            top_indices = similarity.argmax(dim=-1).cpu().tolist()
            scene_slugs = [SCENE_LABELS[i].replace(" ", "_") for i in top_indices]

        return aesthetic_scores, scene_slugs


def compute_sharpness(gray_cv2: np.ndarray) -> float:
    """Laplacian variance on center 60% crop, normalized to 0–1."""
    h, w = gray_cv2.shape
    cy, cx = h // 2, w // 2
    crop = gray_cv2[
        int(cy * 0.4): int(cy * 1.6),
        int(cx * 0.4): int(cx * 1.6),
    ]
    var = float(cv2.Laplacian(crop, cv2.CV_64F).var())
    # sigmoid-style normalization: 500 raw variance → ~0.73
    return 1.0 / (1.0 + math.exp(-(var - 200) / 150))


def compute_exposure(pil_img: Image.Image) -> float:
    """Histogram-based exposure quality score 0–1."""
    gray = np.array(pil_img.convert("L"))
    hist, _ = np.histogram(gray, bins=256, range=(0, 256))
    total = gray.size
    good = hist[30:226].sum()
    clipped = hist[:10].sum() + hist[246:].sum()
    score = good / total - (clipped / total) * 2.0
    return float(max(0.0, min(1.0, score)))


def detect_faces(cv2_img: np.ndarray) -> tuple[int, list[list[int]]]:
    """OpenCV Haar cascade face detection. Returns (count, [[x,y,w,h], ...])."""
    try:
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        cascade = cv2.CascadeClassifier(cascade_path)
        gray = cv2.cvtColor(cv2_img, cv2.COLOR_RGB2GRAY)
        faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
        if len(faces) == 0:
            return 0, []
        rects = [[int(x), int(y), int(w), int(h)] for x, y, w, h in faces]
        return len(rects), rects
    except Exception:
        return 0, []


def compute_phash(pil_img: Image.Image) -> str:
    return str(imagehash.phash(pil_img, hash_size=8))


def read_exif_date(pil_img: Image.Image) -> datetime | None:
    try:
        exif = pil_img._getexif()
        if exif:
            raw = exif.get(36867) or exif.get(36868)  # DateTimeOriginal / DateTimeDigitized
            if raw:
                return datetime.strptime(raw, "%Y:%m:%d %H:%M:%S")
    except Exception:
        pass
    return None


def composite_score(
    aesthetic: float,
    sharpness: float,
    exposure: float,
    face_count: int,
    weights: dict,
) -> float:
    face_bonus = min(face_count, 3) / 3.0
    return (
        weights["aesthetic"] * (aesthetic / 10.0)
        + weights["sharpness"] * sharpness
        + weights["exposure"] * exposure
        + weights["face_bonus"] * face_bonus
    )


def stars_from_score(composite: float) -> int:
    """Map 0–1 composite score to 1–5 stars."""
    return max(1, min(5, int(composite * 5) + 1))
