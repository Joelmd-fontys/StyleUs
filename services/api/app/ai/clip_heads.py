"""CLIP prompts and prediction heads for wardrobe classification."""

from __future__ import annotations

import importlib
import logging
import threading
from collections.abc import Sequence
from pathlib import Path
from typing import Any, TypedDict

import numpy as np
from PIL import Image

from app.core.config import settings

LOGGER = logging.getLogger("app.ai.clip")

PROMPT_TEMPLATES: Sequence[str] = (
    "studio product photo of a {label}",
    "close-up {label} garment",
)

CATEGORIES: Sequence[str] = ("top", "bottom", "outerwear", "shoes", "accessory")

MATERIALS: Sequence[str] = (
    "denim",
    "cotton",
    "wool",
    "cashmere",
    "linen",
    "silk",
    "leather",
    "suede",
    "canvas",
    "synthetic",
    "mesh",
    "rubber",
    "fleece",
    "knit",
)

STYLES: Sequence[str] = (
    "minimal",
    "streetwear",
    "athletic",
    "casual",
    "formal",
    "smart-casual",
    "relaxed",
    "outdoor",
    "vintage",
    "luxury",
    "edgy",
    "preppy",
    "boho",
)


class ClipPrediction(TypedDict):
    category: str
    category_confidence: float
    materials: list[tuple[str, float]]
    styles: list[tuple[str, float]]
    scores: dict[str, dict[str, float]]


class ClipPredictor:
    """Multi-head CLIP predictor with optional ONNX inference."""

    def __init__(self) -> None:
        self.use_onnx = False
        self.onnx_session: Any | None = None
        self._open_clip, self._torch = self._load_dependencies()
        self.device = self._torch.device(settings.ai_device)
        self._load_model()
        self._prepare_text_heads()

    def _load_dependencies(self) -> tuple[Any, Any]:
        try:
            open_clip_module = importlib.import_module("open_clip")
            torch_module = importlib.import_module("torch")
        except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("open-clip-torch is required for local classification") from exc
        return open_clip_module, torch_module

    def _load_model(self) -> None:
        open_clip = self._open_clip
        model_name = "ViT-B-32"
        pretrained = "laion2b_s34b_b79k"

        if settings.ai_onnx:
            model_path = settings.ai_onnx_model_path
            try:
                import onnxruntime as ort  # type: ignore[import]

                if model_path:
                    self.onnx_session = ort.InferenceSession(
                        model_path,
                        providers=["CPUExecutionProvider"],
                    )
                    self.use_onnx = True
                else:
                    LOGGER.warning("ai.clip.onnx_missing_path")
            except Exception as exc:  # pragma: no cover - optional dependency
                LOGGER.warning("ai.clip.onnx_unavailable", extra={"error": str(exc)})

        model, _, preprocess = open_clip.create_model_and_transforms(  # type: ignore[attr-defined]
            model_name,
            pretrained=pretrained,
            device="cpu",
        )
        self.preprocess = preprocess
        self.tokenizer = open_clip.get_tokenizer(model_name)  # type: ignore[attr-defined]

        if self.use_onnx:
            self.model = model.to(self.device)
        else:
            self.model = model.to(self.device)
            self.model.eval()

    def _prepare_text_heads(self) -> None:
        torch = self._torch
        with torch.no_grad():
            self.category_text = self._build_text_embeddings(CATEGORIES)
            self.material_text = self._build_text_embeddings(MATERIALS)
            self.style_text = self._build_text_embeddings(STYLES)

    def _build_text_embeddings(self, labels: Sequence[str]) -> Any:
        torch = self._torch
        prompts: list[str] = []
        for label in labels:
            phrase = label.replace("_", " ")
            for template in PROMPT_TEMPLATES:
                prompts.append(template.format(label=phrase))

        tokens = self.tokenizer(prompts)
        tokens = tokens.to(self.device)
        with torch.no_grad():
            text_features = self.model.encode_text(tokens)
        text_features = text_features / text_features.norm(dim=-1, keepdim=True)

        prompt_count = len(PROMPT_TEMPLATES)
        text_features = text_features.view(len(labels), prompt_count, -1).mean(dim=1)
        text_features = text_features / text_features.norm(dim=-1, keepdim=True)
        return text_features.to(self.device)

    def embed_image(self, image_path: Path) -> np.ndarray:
        torch = self._torch
        with Image.open(image_path) as image:
            pixel_tensor = self.preprocess(image.convert("RGB")).unsqueeze(0)

        if self.use_onnx and self.onnx_session is not None:
            try:
                input_name = self.onnx_session.get_inputs()[0].name  # type: ignore[attr-defined]
                outputs = self.onnx_session.run(  # type: ignore[attr-defined]
                    None,
                    {input_name: pixel_tensor.numpy()},
                )
                embedding = outputs[0][0]
            except Exception as exc:  # pragma: no cover - fallback
                LOGGER.warning("ai.clip.onnx_inference_failed", extra={"error": str(exc)})
                with torch.no_grad():
                    embedding = (
                        self.model.encode_image(pixel_tensor.to(self.device))
                        .cpu()
                        .numpy()[0]
                    )
        else:
            with torch.no_grad():
                embedding = (
                    self.model.encode_image(pixel_tensor.to(self.device))
                    .cpu()
                    .numpy()[0]
                )

        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm
        return embedding.astype(np.float32)

    def predict(self, embedding: np.ndarray) -> ClipPrediction:
        torch = self._torch
        embedding_tensor = torch.from_numpy(embedding).unsqueeze(0)
        embedding_tensor = embedding_tensor.to(self.device)

        category_logits = (embedding_tensor @ self.category_text.T) * 100
        category_probs = torch.softmax(category_logits, dim=-1)[0]
        category_idx = int(torch.argmax(category_probs).item())
        category_label = CATEGORIES[category_idx]
        category_conf = float(category_probs[category_idx].item())

        category_scores = {
            label: float(category_probs[i].item())
            for i, label in enumerate(CATEGORIES)
        }

        material_logits = (embedding_tensor @ self.material_text.T) * 100
        material_probs = torch.softmax(material_logits, dim=-1)[0]
        material_scores = {
            label: float(material_probs[i].item())
            for i, label in enumerate(MATERIALS)
        }
        material_ranked = sorted(
            material_scores.items(), key=lambda item: item[1], reverse=True
        )

        style_logits = (embedding_tensor @ self.style_text.T) * 100
        style_probs = torch.softmax(style_logits, dim=-1)[0]
        style_scores = {
            label: float(style_probs[i].item())
            for i, label in enumerate(STYLES)
        }
        style_ranked = sorted(style_scores.items(), key=lambda item: item[1], reverse=True)

        return ClipPrediction(
            category=category_label,
            category_confidence=category_conf,
            materials=material_ranked,
            styles=style_ranked,
            scores={
                "category": category_scores,
                "materials": material_scores,
                "styles": style_scores,
            },
        )


_PREDICTOR_INSTANCE: ClipPredictor | None = None
_PREDICTOR_LOCK = threading.Lock()


def get_predictor() -> ClipPredictor:
    global _PREDICTOR_INSTANCE
    if _PREDICTOR_INSTANCE is not None:
        return _PREDICTOR_INSTANCE

    with _PREDICTOR_LOCK:
        if _PREDICTOR_INSTANCE is None:
            _PREDICTOR_INSTANCE = ClipPredictor()
    return _PREDICTOR_INSTANCE
