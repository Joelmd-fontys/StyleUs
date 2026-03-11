"""CLIP prompts and prediction heads for wardrobe classification."""

from __future__ import annotations

import importlib
import logging
import threading
import warnings
from collections.abc import Sequence
from pathlib import Path
from typing import Any, TypedDict, cast

import numpy as np
from PIL import Image

from app.ai.labels import (
    CATEGORY_LABELS,
    MATERIAL_LABELS,
    STYLE_LABELS,
    SUBCATEGORY_LABELS,
)
from app.core.config import settings

LOGGER = logging.getLogger("app.ai.clip")

# Suppress noisy timm deprecation warning emitted by open-clip imports.
warnings.filterwarnings(
    "ignore",
    message="Importing from timm.models.layers is deprecated.*",
    category=FutureWarning,
)

PROMPT_TEMPLATES: Sequence[str] = (
    "studio photo of a {label}",
    "clean product image of a {label}",
    "clothing item: {label}",
)


class ClipPrediction(TypedDict):
    category: str
    category_confidence: float
    materials: list[tuple[str, float]]
    style_tags: list[tuple[str, float]]
    subcategory: str | None
    subcategory_confidence: float | None
    scores: dict[str, dict[str, float]]


class ClipPredictor:
    """Multi-head CLIP predictor with optional ONNX inference."""

    def __init__(self) -> None:
        self.use_onnx = False
        self.onnx_session: Any | None = None
        self._open_clip, self._torch = self._load_dependencies()
        self.device = self._torch.device(settings.ai_device)
        self.subcategory_text: dict[str, Any] = {}
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
                import onnxruntime as ort

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

        oc = cast(Any, open_clip)
        model, _, preprocess = oc.create_model_and_transforms(
            model_name,
            pretrained=pretrained,
            device="cpu",
        )
        self.preprocess = preprocess
        self.tokenizer = oc.get_tokenizer(model_name)

        if self.use_onnx:
            self.model = model.to(self.device)
        else:
            self.model = model.to(self.device)
            self.model.eval()

    def _prepare_text_heads(self) -> None:
        torch = self._torch
        with torch.no_grad():
            self.category_text = self._build_text_embeddings(CATEGORY_LABELS)
            self.material_text = self._build_text_embeddings(MATERIAL_LABELS)
            self.style_text = self._build_text_embeddings(STYLE_LABELS)
            self.subcategory_text = {
                category: self._build_text_embeddings(labels)
                for category, labels in SUBCATEGORY_LABELS.items()
            }

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
        with Image.open(image_path) as image:
            return self.embed_pil_image(image)

    def embed_pil_image(self, image: Image.Image) -> np.ndarray:
        torch = self._torch
        pixel_tensor = self.preprocess(image.convert("RGB")).unsqueeze(0)

        if self.use_onnx and self.onnx_session is not None:
            try:
                input_name = self.onnx_session.get_inputs()[0].name
                outputs = self.onnx_session.run(
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
        return cast(np.ndarray, np.asarray(embedding, dtype=np.float32))

    def predict(self, embedding: np.ndarray) -> ClipPrediction:
        torch = self._torch
        embedding_tensor = torch.from_numpy(embedding).unsqueeze(0)
        embedding_tensor = embedding_tensor.to(self.device)

        category_logits = (embedding_tensor @ self.category_text.T) * 100
        category_probs = torch.softmax(category_logits, dim=-1)[0]
        category_idx = int(torch.argmax(category_probs).item())
        category_label = CATEGORY_LABELS[category_idx]
        category_conf = float(category_probs[category_idx].item())

        category_scores = {
            label: float(category_probs[i].item())
            for i, label in enumerate(CATEGORY_LABELS)
        }

        subcategory_label: str | None = None
        subcategory_conf: float | None = None
        subcategory_scores: dict[str, float] = {}
        sub_labels = SUBCATEGORY_LABELS.get(category_label, ())
        if sub_labels:
            sub_text = self.subcategory_text.get(category_label)
            if sub_text is not None:
                sub_logits = (embedding_tensor @ sub_text.T) * 100
                sub_probs = torch.softmax(sub_logits, dim=-1)[0]
                subcategory_scores = {
                    label: float(sub_probs[i].item())
                    for i, label in enumerate(sub_labels)
                }
                sub_idx = int(torch.argmax(sub_probs).item())
                subcategory_label = sub_labels[sub_idx]
                subcategory_conf = float(sub_probs[sub_idx].item())

        material_logits = (embedding_tensor @ self.material_text.T) * 100
        material_probs = torch.softmax(material_logits, dim=-1)[0]
        material_scores = {
            label: float(material_probs[i].item())
            for i, label in enumerate(MATERIAL_LABELS)
        }
        material_ranked = sorted(
            material_scores.items(), key=lambda item: item[1], reverse=True
        )

        style_logits = (embedding_tensor @ self.style_text.T) * 100
        style_probs = torch.softmax(style_logits, dim=-1)[0]
        style_tag_scores = {
            label: float(style_probs[i].item())
            for i, label in enumerate(STYLE_LABELS)
        }
        style_ranked = sorted(
            style_tag_scores.items(), key=lambda item: item[1], reverse=True
        )

        return ClipPrediction(
            category=category_label,
            category_confidence=category_conf,
            materials=material_ranked,
            style_tags=style_ranked,
            subcategory=subcategory_label,
            subcategory_confidence=subcategory_conf,
            scores={
                "category": category_scores,
                "materials": material_scores,
                "style_tags": style_tag_scores,
                "subcategory": subcategory_scores,
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
