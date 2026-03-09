"""Color extraction utilities."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from PIL import Image
from sklearn.cluster import KMeans

from app.ai.segmentation import MaskMethod, build_foreground_mask, has_opencv
from app.core.config import settings

LOGGER = logging.getLogger("app.ai.color")

_PALETTE_RGB: Sequence[tuple[str, tuple[int, int, int]]] = (
    ("black", (0, 0, 0)),
    ("charcoal", (54, 69, 79)),
    ("gray", (128, 128, 128)),
    ("silver", (192, 192, 192)),
    ("white", (255, 255, 255)),
    ("ivory", (255, 255, 240)),
    ("cream", (245, 245, 220)),
    ("beige", (214, 196, 161)),
    ("khaki", (195, 176, 145)),
    ("tan", (210, 180, 140)),
    ("camel", (193, 154, 107)),
    ("brown", (123, 63, 0)),
    ("burgundy", (128, 0, 32)),
    ("maroon", (128, 0, 0)),
    ("red", (200, 30, 45)),
    ("rose", (255, 80, 110)),
    ("pink", (255, 182, 193)),
    ("peach", (255, 204, 170)),
    ("orange", (255, 140, 0)),
    ("amber", (255, 191, 0)),
    ("gold", (212, 175, 55)),
    ("yellow", (255, 221, 51)),
    ("lime", (191, 255, 0)),
    ("olive", (128, 128, 0)),
    ("green", (44, 160, 44)),
    ("forest", (34, 85, 34)),
    ("teal", (0, 128, 128)),
    ("turquoise", (64, 224, 208)),
    ("aqua", (127, 255, 212)),
    ("sky", (135, 206, 235)),
    ("blue", (0, 102, 204)),
    ("navy", (7, 31, 64)),
    ("indigo", (63, 81, 181)),
    ("violet", (138, 43, 226)),
    ("purple", (128, 0, 128)),
    ("magenta", (255, 0, 144)),
)


def _srgb_to_linear(rgb: np.ndarray) -> np.ndarray:
    mask = rgb <= 0.04045
    out = np.empty_like(rgb)
    out[mask] = rgb[mask] / 12.92
    out[~mask] = ((rgb[~mask] + 0.055) / 1.055) ** 2.4
    return out


def _linear_to_lab(rgb: np.ndarray) -> np.ndarray:
    """Convert an array of sRGB values (0-1) to Lab."""
    # sRGB to XYZ (D65)
    matrix = np.array(
        [
            [0.4124564, 0.3575761, 0.1804375],
            [0.2126729, 0.7151522, 0.0721750],
            [0.0193339, 0.1191920, 0.9503041],
        ]
    )
    xyz = rgb @ matrix.T

    # Normalize by D65 white point
    xyz_ref = np.array([0.95047, 1.0, 1.08883])
    xyz = xyz / xyz_ref

    def f(t: np.ndarray) -> np.ndarray:
        delta = 6 / 29
        return np.where(
            t > delta**3,
            np.cbrt(t),
            (t / (3 * delta**2)) + (4 / 29),
        )

    f_xyz = f(xyz)
    lightness = (116 * f_xyz[:, 1]) - 16
    a_channel = 500 * (f_xyz[:, 0] - f_xyz[:, 1])
    b_channel = 200 * (f_xyz[:, 1] - f_xyz[:, 2])
    return np.stack([lightness, a_channel, b_channel], axis=1)


_PALETTE_LAB = np.stack(
    [
        _linear_to_lab(
            np.array(rgb, dtype=np.float64)[None, :] / 255.0,
        )[0]
        for _, rgb in _PALETTE_RGB
    ],
    axis=0,
)


@dataclass(slots=True)
class ColorResult:
    primary_color: str
    secondary_color: str | None
    confidence: float
    secondary_confidence: float | None


def _center_crop(image: Image.Image) -> Image.Image:
    width, height = image.size
    side = min(width, height)
    left = (width - side) // 2
    top = (height - side) // 2
    return image.crop((left, top, left + side, top + side))


def _prepare_pixels(
    image: Image.Image, *, mask: np.ndarray | None
) -> tuple[np.ndarray, int | None]:
    resized = image.resize((256, 256))
    rgb_array = np.asarray(resized, dtype=np.float64) / 255.0

    masked_pixels: int | None = None
    if mask is not None:
        mask_image = Image.fromarray((mask.astype(np.uint8)) * 255)
        if mask_image.size != image.size:
            mask_image = mask_image.resize(image.size, resample=Image.Resampling.NEAREST)
        mask_image = mask_image.resize(resized.size, resample=Image.Resampling.NEAREST)
        mask_array = np.asarray(mask_image, dtype=bool)
        masked_pixels = int(mask_array.sum())
        if masked_pixels > 0:
            rgb_array = rgb_array[mask_array]
        else:
            rgb_array = rgb_array.reshape(-1, 3)
    else:
        rgb_array = rgb_array.reshape(-1, 3)

    if rgb_array.size == 0:
        return np.empty((0, 3)), masked_pixels

    lab = _linear_to_lab(_srgb_to_linear(rgb_array))
    return lab, masked_pixels


def _map_to_palette(lab_vector: np.ndarray) -> str:
    distances = np.linalg.norm(_PALETTE_LAB - lab_vector[None, :], axis=1)
    index = int(np.argmin(distances))
    return _PALETTE_RGB[index][0]


def get_colors(image_path: str) -> ColorResult:
    """Return primary/secondary colors (human readable) from an image."""

    try:
        with Image.open(image_path) as img:
            image = _center_crop(img.convert("RGB"))
    except Exception as exc:
        LOGGER.warning("ai.color.image_load_failed", extra={"error": str(exc)})
        return ColorResult(
            primary_color="Unknown",
            secondary_color=None,
            confidence=0.0,
            secondary_confidence=None,
        )

    mask_method: MaskMethod = (
        settings.ai_color_mask_method
        if settings.ai_color_mask_method in {"grabcut", "heuristic"}
        else "grabcut"
    )
    if mask_method == "grabcut" and not has_opencv():
        LOGGER.info("ai.color.opencv_missing_fallback", extra={"fallback": "heuristic"})
        mask_method = "heuristic"

    mask: np.ndarray | None = None
    if settings.ai_color_use_mask:
        try:
            mask = build_foreground_mask(image, method=mask_method)
        except Exception as exc:
            LOGGER.warning("ai.color.mask_failed", extra={"error": str(exc)})

    try:
        lab_pixels, masked_pixels = _prepare_pixels(image, mask=mask)
    except Exception as exc:
        LOGGER.warning("ai.color.pixel_prep_failed", extra={"error": str(exc)})
        return ColorResult(
            primary_color="Unknown",
            secondary_color=None,
            confidence=0.0,
            secondary_confidence=None,
        )

    if (
        mask is not None
        and masked_pixels is not None
        and masked_pixels < settings.ai_color_min_foreground_pixels
    ):
        LOGGER.warning(
            "ai.color.mask_too_small",
            extra={
                "foreground_pixels": masked_pixels,
                "threshold": settings.ai_color_min_foreground_pixels,
            },
        )
        lab_pixels, _ = _prepare_pixels(image, mask=None)

    if lab_pixels.size == 0:
        return ColorResult(
            primary_color="Unknown",
            secondary_color=None,
            confidence=0.0,
            secondary_confidence=None,
        )

    kmeans = KMeans(
        n_clusters=min(5, len(lab_pixels)),
        n_init=10,
        random_state=0,
    )
    labels = kmeans.fit_predict(lab_pixels)
    centers = kmeans.cluster_centers_

    counts = np.bincount(labels, minlength=len(centers)).astype(float)
    total = counts.sum()
    if total == 0:
        return ColorResult(
            primary_color="Unknown",
            secondary_color=None,
            confidence=0.0,
            secondary_confidence=None,
        )

    shares = counts / total
    valid_indices = [idx for idx, share in enumerate(shares) if share >= 0.05]
    if not valid_indices:
        valid_indices = [int(np.argmax(shares))]

    ranked = sorted(valid_indices, key=lambda idx: shares[idx], reverse=True)
    topk = min(settings.ai_color_topk, len(ranked))

    chosen = []
    for idx in ranked[:topk]:
        color_name = _map_to_palette(centers[idx])
        chosen.append((color_name, shares[idx]))

    if not chosen:
        return ColorResult(
            primary_color="Unknown",
            secondary_color=None,
            confidence=0.0,
            secondary_confidence=None,
        )

    primary_name, primary_share = chosen[0]
    secondary_name = None
    secondary_share = None
    if len(chosen) > 1:
        secondary_name = chosen[1][0]
        secondary_share = chosen[1][1]

    primary_display = primary_name.title()
    secondary_display = secondary_name.title() if secondary_name else None

    return ColorResult(
        primary_color=primary_display,
        secondary_color=secondary_display,
        confidence=float(primary_share),
        secondary_confidence=float(secondary_share) if secondary_share is not None else None,
    )
