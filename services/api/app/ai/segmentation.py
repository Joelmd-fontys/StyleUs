"""Foreground masking and garment-focused cropping helpers."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Literal, cast

import numpy as np
from PIL import Image, ImageFilter

LOGGER = logging.getLogger("app.ai.segmentation")

MaskMethod = Literal["grabcut", "heuristic"]
BoundingBox = tuple[int, int, int, int]

_DEFAULT_BACKGROUND = (245, 245, 245)
_MIN_FOREGROUND_PIXELS = 768
_MIN_FOREGROUND_RATIO = 0.012
_CROP_PADDING_RATIO = 0.08

cv2: Any | None

try:  # pragma: no cover - optional dependency
    import cv2 as _cv2

    cv2 = _cv2
    _HAS_CV2 = True
except Exception:  # pragma: no cover - OpenCV is optional
    cv2 = None
    _HAS_CV2 = False


@dataclass(frozen=True, slots=True)
class GarmentFocus:
    image: Image.Image
    masked_image: Image.Image
    mask: np.ndarray | None
    crop_box: BoundingBox
    method: MaskMethod | None
    foreground_pixels: int
    foreground_ratio: float


def _get_cv2() -> Any:
    if cv2 is None:  # pragma: no cover - guarded by _HAS_CV2
        raise RuntimeError("OpenCV is not available")
    return cv2


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
        cv2_module = _get_cv2()
        num_labels, labels, stats, _ = cv2_module.connectedComponentsWithStats(
            binary, connectivity=8
        )
        if num_labels <= 1:
            return binary
        largest_label = 1 + int(np.argmax(stats[1:, cv2_module.CC_STAT_AREA]))
        return cast(np.ndarray, (labels == largest_label).astype(np.uint8))

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
    pil_mask = pil_mask.filter(ImageFilter.MaxFilter(3))
    pil_mask = pil_mask.filter(ImageFilter.MedianFilter(3))
    pil_mask = pil_mask.filter(ImageFilter.MinFilter(3))
    return _pil_mask_to_bool(pil_mask)


def _grabcut_mask(image: Image.Image) -> np.ndarray | None:
    if not _HAS_CV2:
        return None
    cv2_module = _get_cv2()

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
        cv2_module.setRNGSeed(0)
    except Exception:
        pass

    try:
        cv2_module.grabCut(
            array,
            mask,
            rect,
            bgd_model,
            fgd_model,
            4,
            cv2_module.GC_INIT_WITH_RECT,
        )
    except Exception as exc:  # pragma: no cover - defensive
        LOGGER.warning("ai.segmentation.grabcut_failed", extra={"error": str(exc)})
        return None

    mask = np.where((mask == cv2_module.GC_FGD) | (mask == cv2_module.GC_PR_FGD), 1, 0).astype(
        np.uint8
    )
    if mask.max() == 0:
        return None

    mask = _keep_largest_component(mask)
    mask = cast(
        np.ndarray,
        cv2_module.morphologyEx(mask, cv2_module.MORPH_CLOSE, np.ones((5, 5), np.uint8)),
    )
    mask = cast(np.ndarray, cv2_module.medianBlur(mask, 3))

    if scale != 1.0:
        mask = cast(
            np.ndarray,
            cv2_module.resize(mask, image.size, interpolation=cv2_module.INTER_NEAREST),
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

    border = (
        (xx < width * 0.08)
        | (xx > width * 0.92)
        | (yy < height * 0.08)
        | (yy > height * 0.92)
    )
    border_pixels = array[border]
    if border_pixels.size == 0:
        return None

    background_mean = border_pixels.mean(axis=0)
    color_distance = np.linalg.norm(array - background_mean, axis=2)
    border_distance = color_distance[border]
    distance_threshold = max(float(np.quantile(border_distance, 0.95)) * 1.35, 0.08)

    mask = (
        (color_distance > max(distance_threshold * 4.0, 0.12)) & (center_weights > 0.05) & (~border)
    )
    if mask.sum() < max(200, int(height * width * 0.015)):
        mask = (
            (color_distance > max(distance_threshold * 2.5, 0.08))
            & (center_weights > 0.08)
            & (~border)
        )

    mask = mask.astype(np.uint8)
    mask = _keep_largest_component(mask)
    if mask.max() == 0:
        return None
    smoothed = _smooth_mask(mask)

    if scale != 1.0:
        smoothed = _pil_mask_to_bool(_bool_mask_to_pil(smoothed, size=image.size))
    return smoothed


def _mask_bounding_box(mask: np.ndarray) -> BoundingBox | None:
    coordinates = np.argwhere(mask)
    if coordinates.size == 0:
        return None
    y0, x0 = coordinates.min(axis=0)
    y1, x1 = coordinates.max(axis=0)
    return int(x0), int(y0), int(x1) + 1, int(y1) + 1


def _expand_box(box: BoundingBox, size: tuple[int, int], *, padding_ratio: float) -> BoundingBox:
    image_width, image_height = size
    left, top, right, bottom = box
    width = max(1, right - left)
    height = max(1, bottom - top)
    padding = max(4, int(round(max(width, height) * padding_ratio)))

    left = max(0, left - padding)
    top = max(0, top - padding)
    right = min(image_width, right + padding)
    bottom = min(image_height, bottom + padding)

    width = max(1, right - left)
    height = max(1, bottom - top)
    side = max(width, height)
    center_x = (left + right) / 2
    center_y = (top + bottom) / 2

    half_side = side / 2
    left = int(round(center_x - half_side))
    top = int(round(center_y - half_side))
    right = left + side
    bottom = top + side

    if left < 0:
        right = min(image_width, right - left)
        left = 0
    if top < 0:
        bottom = min(image_height, bottom - top)
        top = 0
    if right > image_width:
        shift = right - image_width
        left = max(0, left - shift)
        right = image_width
    if bottom > image_height:
        shift = bottom - image_height
        top = max(0, top - shift)
        bottom = image_height

    return left, top, max(left + 1, right), max(top + 1, bottom)


def _crop_mask(mask: np.ndarray, box: BoundingBox) -> np.ndarray | None:
    left, top, right, bottom = box
    cropped = mask[top:bottom, left:right]
    if cropped.size == 0:
        return None
    return np.asarray(cropped, dtype=bool).copy()


def _apply_mask(image: Image.Image, mask: np.ndarray | None) -> Image.Image:
    if mask is None:
        return image.copy()
    if not np.any(mask):
        return image.copy()

    rgb = np.asarray(image.convert("RGB"), dtype=np.uint8)
    output = np.empty_like(rgb)
    output[:, :] = np.asarray(_DEFAULT_BACKGROUND, dtype=np.uint8)
    output[mask] = rgb[mask]
    return cast(Image.Image, Image.fromarray(output))


def build_foreground_mask(image: Image.Image, *, method: MaskMethod) -> np.ndarray | None:
    """Estimate a foreground mask. Returns None on failure."""

    if method == "grabcut":
        mask = _grabcut_mask(image)
        if mask is not None:
            return mask
        LOGGER.info("ai.segmentation.grabcut_unavailable", extra={"fallback": "heuristic"})
        return _heuristic_mask(image)

    return _heuristic_mask(image)


def prepare_garment_focus(
    image: Image.Image,
    *,
    method: MaskMethod,
    padding_ratio: float = _CROP_PADDING_RATIO,
) -> GarmentFocus:
    """Return a tightly cropped garment image plus an aligned mask when possible."""

    source = image.convert("RGB")
    mask = build_foreground_mask(source, method=method)
    foreground_pixels = 0
    foreground_ratio = 0.0
    if mask is not None:
        mask = _keep_largest_component(mask.astype(np.uint8)).astype(bool)
        foreground_pixels = int(mask.sum())
        foreground_ratio = foreground_pixels / max(1, source.size[0] * source.size[1])
        minimum_pixels = max(
            _MIN_FOREGROUND_PIXELS,
            int(round(source.size[0] * source.size[1] * _MIN_FOREGROUND_RATIO)),
        )
        if foreground_pixels < minimum_pixels:
            LOGGER.info(
                "ai.segmentation.mask_too_small",
                extra={
                    "foreground_pixels": foreground_pixels,
                    "minimum_pixels": minimum_pixels,
                    "foreground_ratio": round(foreground_ratio, 4),
                },
            )
            mask = None

    bounding_box = _mask_bounding_box(mask) if mask is not None else None
    crop_box = (
        _expand_box(bounding_box, source.size, padding_ratio=padding_ratio)
        if bounding_box is not None
        else (0, 0, source.size[0], source.size[1])
    )
    cropped_image = source.crop(crop_box)
    cropped_mask = _crop_mask(mask, crop_box) if mask is not None else None
    masked_image = _apply_mask(cropped_image, cropped_mask)

    return GarmentFocus(
        image=cropped_image,
        masked_image=masked_image,
        mask=cropped_mask,
        crop_box=crop_box,
        method=method if cropped_mask is not None else None,
        foreground_pixels=foreground_pixels,
        foreground_ratio=foreground_ratio,
    )


def has_opencv() -> bool:
    """Expose whether OpenCV is available."""

    return _HAS_CV2
