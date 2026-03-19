"""CLIP prompts and prediction heads for wardrobe classification."""

from __future__ import annotations

import importlib
import logging
import threading
import warnings
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypedDict, cast

import numpy as np
from PIL import Image

from app.ai.labels import (
    ATTRIBUTE_SPECS,
    CATEGORY_LABELS,
    CATEGORY_SPECS,
    MATERIAL_SPECS,
    STYLE_SPECS,
    SUBCATEGORY_SPECS,
    SUBCATEGORY_TO_CATEGORY,
    LabelSpec,
)
from app.core.config import settings

LOGGER = logging.getLogger("app.ai.clip")

_DEFAULT_MODEL_NAME = "hf-hub:Marqo/marqo-fashionCLIP"
_FALLBACK_MODEL_NAME = "ViT-B-32"
_FALLBACK_PRETRAINED = "laion2b_s34b_b79k"
_LOGIT_SCALE = 100.0
_CATEGORY_BLEND_WEIGHT = 0.65
_PROMPT_PREFIXES: Sequence[str] = (
    "a photo of {}",
    "fashion product photo of {}",
    "wardrobe item showing {}",
)

# Suppress noisy timm deprecation warning emitted by open-clip imports.
warnings.filterwarnings(
    "ignore",
    message="Importing from timm.models.layers is deprecated.*",
    category=FutureWarning,
)


class ClipPrediction(TypedDict):
    category: str
    category_confidence: float
    materials: list[tuple[str, float]]
    style_tags: list[tuple[str, float]]
    attribute_tags: list[tuple[str, float]]
    subcategory: str | None
    subcategory_confidence: float | None
    scores: dict[str, dict[str, float]]
    model_name: str


@dataclass(frozen=True, slots=True)
class TextHead:
    labels: tuple[str, ...]
    embeddings: Any


class ClipPredictor:
    """Multi-head CLIP predictor with optional ONNX image encoding."""

    def __init__(self) -> None:
        self.use_onnx = False
        self.onnx_session: Any | None = None
        self._open_clip, self._torch = self._load_dependencies()
        self.device = self._torch.device(settings.ai_device)
        self.category_index = {label: idx for idx, label in enumerate(CATEGORY_LABELS)}
        self.subcategory_to_category = dict(SUBCATEGORY_TO_CATEGORY)
        self.model_name = ""
        self.model_pretrained = ""
        self.cache_key = ""
        self._load_model()
        self._prepare_text_heads()

    def _load_dependencies(self) -> tuple[Any, Any]:
        try:
            open_clip_module = importlib.import_module("open_clip")
            torch_module = importlib.import_module("torch")
        except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("open-clip-torch is required for local classification") from exc
        if hasattr(torch_module, "set_num_threads"):
            try:
                torch_module.set_num_threads(1)
            except RuntimeError:  # pragma: no cover - torch may already be initialized
                LOGGER.debug("ai.clip.set_num_threads_skipped")
        if hasattr(torch_module, "set_num_interop_threads"):
            try:
                torch_module.set_num_interop_threads(1)
            except RuntimeError:  # pragma: no cover - torch may already be initialized
                LOGGER.debug("ai.clip.set_num_interop_threads_skipped")
        return open_clip_module, torch_module

    def _model_cache_dir(self) -> str | None:
        return str(settings.ai_model_cache_dir_path) if settings.ai_model_cache_dir else None

    def _create_model_and_tokenizer(
        self,
        *,
        model_name: str,
        pretrained: str | None,
    ) -> tuple[Any, Any, Any]:
        open_clip = cast(Any, self._open_clip)
        kwargs: dict[str, Any] = {
            "device": "cpu",
            "precision": "fp32",
        }
        cache_dir = self._model_cache_dir()
        if cache_dir:
            kwargs["cache_dir"] = cache_dir
        if model_name.startswith("hf-hub:"):
            model, _, preprocess = open_clip.create_model_and_transforms(model_name, **kwargs)
        else:
            model, _, preprocess = open_clip.create_model_and_transforms(
                model_name,
                pretrained=pretrained,
                **kwargs,
            )
        tokenizer = open_clip.get_tokenizer(model_name)
        return model, preprocess, tokenizer

    def _load_model(self) -> None:
        requested_name = settings.ai_model_name or _DEFAULT_MODEL_NAME
        requested_pretrained = settings.ai_model_pretrained or None
        try:
            self.model, self.preprocess, self.tokenizer = self._create_model_and_tokenizer(
                model_name=requested_name,
                pretrained=requested_pretrained,
            )
            self.model_name = requested_name
            self.model_pretrained = requested_pretrained or ""
        except Exception as exc:  # pragma: no cover - exercised via fallback
            LOGGER.warning(
                "ai.clip.requested_model_unavailable",
                extra={
                    "model_name": requested_name,
                    "pretrained": requested_pretrained,
                    "error": str(exc),
                    "fallback_model_name": _FALLBACK_MODEL_NAME,
                },
            )
            self.model, self.preprocess, self.tokenizer = self._create_model_and_tokenizer(
                model_name=_FALLBACK_MODEL_NAME,
                pretrained=_FALLBACK_PRETRAINED,
            )
            self.model_name = _FALLBACK_MODEL_NAME
            self.model_pretrained = _FALLBACK_PRETRAINED

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

        self.model = self.model.to(self.device)
        self.model.eval()
        self.cache_key = f"{self.model_name}:{self.model_pretrained or 'default'}"

    def _prepare_text_heads(self) -> None:
        self.category_head = self._build_text_head(CATEGORY_SPECS)
        self.subcategory_head = self._build_text_head(
            tuple(spec for specs in SUBCATEGORY_SPECS.values() for spec in specs)
        )
        self.material_head = self._build_text_head(MATERIAL_SPECS)
        self.style_head = self._build_text_head(STYLE_SPECS)
        self.attribute_head = self._build_text_head(ATTRIBUTE_SPECS)

    def _build_text_head(self, specs: Sequence[LabelSpec]) -> TextHead:
        torch = self._torch
        prompts: list[str] = []
        prompt_counts: list[int] = []
        labels: list[str] = []
        for spec in specs:
            labels.append(spec.label)
            spec_prompts = [
                template.format(phrase)
                for phrase in spec.prompts
                for template in _PROMPT_PREFIXES
            ]
            prompts.extend(spec_prompts)
            prompt_counts.append(len(spec_prompts))

        tokens = self.tokenizer(prompts)
        tokens = tokens.to(self.device)
        with torch.no_grad():
            text_features = self.model.encode_text(tokens)
        text_features = text_features / text_features.norm(dim=-1, keepdim=True)

        merged_features: list[Any] = []
        cursor = 0
        for prompt_count in prompt_counts:
            label_features = text_features[cursor : cursor + prompt_count].mean(dim=0, keepdim=True)
            label_features = label_features / label_features.norm(dim=-1, keepdim=True)
            merged_features.append(label_features)
            cursor += prompt_count

        embeddings = torch.cat(merged_features, dim=0).to(self.device)
        return TextHead(labels=tuple(labels), embeddings=embeddings)

    def _scores_for_head(
        self,
        embedding_tensor: Any,
        head: TextHead,
    ) -> tuple[dict[str, float], Any]:
        torch = self._torch
        logits = (embedding_tensor @ head.embeddings.T) * _LOGIT_SCALE
        probabilities = torch.softmax(logits, dim=-1)[0]
        scores = {
            label: float(probabilities[idx].item()) for idx, label in enumerate(head.labels)
        }
        return scores, probabilities

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

        category_scores, category_probs = self._scores_for_head(
            embedding_tensor,
            self.category_head,
        )
        subcategory_global_scores, subcategory_global_probs = self._scores_for_head(
            embedding_tensor,
            self.subcategory_head,
        )
        material_scores, _material_probs = self._scores_for_head(
            embedding_tensor,
            self.material_head,
        )
        style_scores, _style_probs = self._scores_for_head(
            embedding_tensor,
            self.style_head,
        )
        attribute_scores, _attribute_probs = self._scores_for_head(
            embedding_tensor,
            self.attribute_head,
        )

        subcategory_category_probs = torch.zeros(len(CATEGORY_LABELS), device=self.device)
        for idx, label in enumerate(self.subcategory_head.labels):
            category = self.subcategory_to_category[label]
            category_index = self.category_index[category]
            subcategory_category_probs[category_index] = torch.maximum(
                subcategory_category_probs[category_index],
                subcategory_global_probs[idx],
            )

        blended_category_probs = (
            (category_probs * _CATEGORY_BLEND_WEIGHT)
            + (subcategory_category_probs * (1.0 - _CATEGORY_BLEND_WEIGHT))
        )
        blended_category_probs = blended_category_probs / blended_category_probs.sum()
        category_scores = {
            label: float(blended_category_probs[idx].item())
            for idx, label in enumerate(CATEGORY_LABELS)
        }
        category_idx = int(torch.argmax(blended_category_probs).item())
        category_label = CATEGORY_LABELS[category_idx]
        category_conf = float(blended_category_probs[category_idx].item())

        allowed_indices = [
            idx
            for idx, label in enumerate(self.subcategory_head.labels)
            if self.subcategory_to_category[label] == category_label
        ]
        subcategory_label: str | None = None
        subcategory_conf: float | None = None
        subcategory_scores: dict[str, float] = {}
        if allowed_indices:
            allowed_tensor = torch.tensor(allowed_indices, device=self.device)
            allowed_probs = subcategory_global_probs.index_select(0, allowed_tensor)
            allowed_probs = allowed_probs / allowed_probs.sum()
            for local_index, global_index in enumerate(allowed_indices):
                label = self.subcategory_head.labels[global_index]
                subcategory_scores[label] = float(allowed_probs[local_index].item())
            best_local_index = int(torch.argmax(allowed_probs).item())
            best_global_index = allowed_indices[best_local_index]
            subcategory_label = self.subcategory_head.labels[best_global_index]
            subcategory_conf = float(allowed_probs[best_local_index].item())

        material_ranked = sorted(
            material_scores.items(),
            key=lambda item: item[1],
            reverse=True,
        )
        style_ranked = sorted(
            style_scores.items(),
            key=lambda item: item[1],
            reverse=True,
        )
        attribute_ranked = sorted(
            attribute_scores.items(),
            key=lambda item: item[1],
            reverse=True,
        )

        return ClipPrediction(
            category=category_label,
            category_confidence=category_conf,
            materials=material_ranked,
            style_tags=style_ranked,
            attribute_tags=attribute_ranked,
            subcategory=subcategory_label,
            subcategory_confidence=subcategory_conf,
            scores={
                "category": category_scores,
                "subcategory": subcategory_scores,
                "subcategory_global": subcategory_global_scores,
                "materials": material_scores,
                "style_tags": style_scores,
                "attribute_tags": attribute_scores,
            },
            model_name=self.model_name,
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
