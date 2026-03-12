"""Lightweight foreground masking for color extraction."""

from __future__ import annotations

import logging
from typing import Literal, cast

import numpy as np
from PIL import Image, ImageFilter

LOGGER = logging.getLogger("app.ai.segmentation")

MaskMethod = Literal["grabcut", "heuristic"]

try:  # pragma: no cover - optional dependency
    import cv2

    _HAS_CV2 = True
except Exception:  # pragma: no cover - OpenCV is optional
    cv2 = None
    _HAS_CV2 = False


def _resize_for_processing(image: Image.Image, *, max_size: int = 512) -> tuple[Image.Image, float]:
    width, height = image.size
    max_dim = max(width, height)
    if max_dim <= max_size:
        return image, 1.0
    scale = max_size / max_dim
    resized = cast(
        Image.Image,
        image.resize(
            (max(1, int(width * scale)), max(1, int(height * scale))),
            resample=Image.Resampling.LANCZOS,
        ),
    )
    return resized, scale


def _pil_mask_to_bool(mask: Image.Image) -> np.ndarray:
    return np.asarray(mask, dtype=np.uint8) > 0


def _bool_mask_to_pil(mask: np.ndarray, *, size: tuple[int, int]) -> Image.Image:
    pil_mask = cast(Image.Image, Image.fromarray((mask.astype(np.uint8)) * 255))
    if pil_mask.size != size:
        pil_mask = cast(Image.Image, pil_mask.resize(size, resample=Image.Resampling.NEAREST))
    return pil_mask


def _keep_largest_component(mask: np.ndarray) -> np.ndarray:
    binary = (mask > 0).astype(np.uint8)
    if binary.max() == 0:
        return binary

    if _HAS_CV2:
        num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
        if num_labels <= 1:
            return binary
        largest_label = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
        return cast(np.ndarray, (labels == largest_label).astype(np.uint8))

    # Fallback labeling without OpenCV (simple DFS)
    height, width = binary.shape
    visited = np.zeros_like(binary, dtype=bool)
    best_size = 0
    best_coords: list[tuple[int, int]] | None = None
    offsets = ((1, 0), (-1, 0), (0, 1), (0, -1))

    for y in range(height):
        for x in range(width):
            if not binary[y, x] or visited[y, x]:
                continue
            stack = [(y, x)]
            visited[y, x] = True
            coords: list[tuple[int, int]] = []
            while stack:
                cy, cx = stack.pop()
                coords.append((cy, cx))
                for dy, dx in offsets:
                    ny, nx = cy + dy, cx + dx
                    if (
                        0 <= ny < height
                        and 0 <= nx < width
                        and binary[ny, nx]
                        and not visited[ny, nx]
                    ):
                        visited[ny, nx] = True
                        stack.append((ny, nx))
            if len(coords) > best_size:
                best_size = len(coords)
                best_coords = coords

    output = np.zeros_like(binary, dtype=np.uint8)
    if best_coords:
        for y, x in best_coords:
            output[y, x] = 1
    return output


def _smooth_mask(mask: np.ndarray) -> np.ndarray:
    pil_mask = Image.fromarray((mask.astype(np.uint8)) * 255)
    # Close small gaps, smooth jagged edges.
    pil_mask = pil_mask.filter(ImageFilter.MaxFilter(3))
    pil_mask = pil_mask.filter(ImageFilter.MedianFilter(3))
    pil_mask = pil_mask.filter(ImageFilter.MinFilter(3))
    return _pil_mask_to_bool(pil_mask)


def _grabcut_mask(image: Image.Image) -> np.ndarray | None:
    if not _HAS_CV2:
        return None

    processed, scale = _resize_for_processing(image)
    array = np.asarray(processed.convert("RGB"))
    height, width = array.shape[:2]
    if height < 2 or width < 2:
        return None

    rect_margin = int(min(height, width) * 0.15)
    rect_width = max(1, width - (rect_margin * 2))
    rect_height = max(1, height - (rect_margin * 2))
    rect = (rect_margin, rect_margin, rect_width, rect_height)

    mask = np.zeros((height, width), np.uint8)
    bgd_model = np.zeros((1, 65), np.float64)
    fgd_model = np.zeros((1, 65), np.float64)
    try:  # pragma: no cover - depends on OpenCV build
        cv2.setRNGSeed(0)
    except Exception:
        pass

    try:
        cv2.grabCut(array, mask, rect, bgd_model, fgd_model, 4, cv2.GC_INIT_WITH_RECT)
    except Exception as exc:  # pragma: no cover - defensive
        LOGGER.warning("ai.segmentation.grabcut_failed", extra={"error": str(exc)})
        return None

    mask = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 1, 0).astype(np.uint8)
    if mask.max() == 0:
        return None

    mask = _keep_largest_component(mask)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    mask = cv2.medianBlur(mask, 3)

    if scale != 1.0:
        mask = cv2.resize(
            mask,
            image.size,
            interpolation=cv2.INTER_NEAREST,
        )
    return mask.astype(bool)


def _heuristic_mask(image: Image.Image) -> np.ndarray | None:
    processed, scale = _resize_for_processing(image, max_size=384)
    array = np.asarray(processed.convert("RGB"), dtype=np.float32) / 255.0
    height, width = array.shape[:2]
    if height < 2 or width < 2:
        return None

    yy, xx = np.mgrid[0:height, 0:width]
    center_y, center_x = height / 2.0, width / 2.0
    sigma = min(height, width) * 0.35
    center_weights = np.exp(-(((yy - center_y) ** 2 + (xx - center_x) ** 2) / (2 * sigma**2)))

    border = (xx < width * 0.08) | (xx > width * 0.92) | (yy < height * 0.08) | (yy > height * 0.92)
    border_pixels = array[border]
    if border_pixels.size == 0:
        return None

    background_mean = border_pixels.mean(axis=0)
    color_distance = np.linalg.norm(array - background_mean, axis=2)
    border_distance = color_distance[border]
    distance_threshold = max(float(np.quantile(border_distance, 0.95)) * 1.35, 0.08)

    mask = (color_distance > max(distance_threshold * 4.0, 0.12)) & (center_weights > 0.05) & (~border)
    if mask.sum() < max(200, int(height * width * 0.015)):
        mask = (color_distance > max(distance_threshold * 2.5, 0.08)) & (center_weights > 0.08) & (~border)

    mask = mask.astype(np.uint8)
    mask = _keep_largest_component(mask)
    if mask.max() == 0:
        return None
    smoothed = _smooth_mask(mask)

    if scale != 1.0:
        smoothed = _pil_mask_to_bool(
            _bool_mask_to_pil(smoothed, size=image.size),
        )
    return smoothed


def build_foreground_mask(image: Image.Image, *, method: MaskMethod) -> np.ndarray | None:
    """Estimate a foreground mask. Returns None on failure."""

    if method == "grabcut":
        mask = _grabcut_mask(image)
        if mask is not None:
            return mask
        LOGGER.info("ai.segmentation.grabcut_unavailable", extra={"fallback": "heuristic"})
        return _heuristic_mask(image)

    return _heuristic_mask(image)


def has_opencv() -> bool:
    """Expose whether OpenCV is available."""

    return _HAS_CV2
