from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from app.ai.color import get_colors
from app.core.config import settings


@pytest.fixture(autouse=True)
def _reset_settings() -> None:
    snapshot = {
        "ai_color_use_mask": settings.ai_color_use_mask,
        "ai_color_mask_method": settings.ai_color_mask_method,
        "ai_color_min_foreground_pixels": settings.ai_color_min_foreground_pixels,
        "ai_color_topk": settings.ai_color_topk,
    }
    yield
    for key, value in snapshot.items():
        setattr(settings, key, value)


@pytest.mark.parametrize(
    "rgb,expected",
    [
        ((5, 5, 5), "Black"),
        ((240, 240, 240), "White"),
        ((63, 81, 181), "Indigo"),
        ((195, 176, 145), "Khaki"),
    ],
)
def test_get_colors_solid(rgb: tuple[int, int, int], expected: str, tmp_path: Path) -> None:
    image_path = tmp_path / f"sample_{expected.lower()}.png"
    Image.new("RGB", (200, 200), color=rgb).save(image_path)

    result = get_colors(str(image_path))

    fallback = {"Khaki": {"Camel"}}
    if expected in fallback:
        assert result.primary_color in {expected, *fallback[expected]}
    else:
        assert result.primary_color == expected
    assert result.secondary_color is None
    assert result.confidence >= 0.9


def test_mask_ignores_background_primary(tmp_path: Path) -> None:
    image_path = tmp_path / "red_on_blue.png"
    image = Image.new("RGB", (360, 360), color=(0, 102, 204))  # blue background
    draw = ImageDraw.Draw(image)
    draw.rectangle((90, 70, 270, 290), fill=(200, 30, 45))  # red shirt
    image.save(image_path)

    settings.ai_color_use_mask = True
    settings.ai_color_mask_method = "heuristic"
    settings.ai_color_min_foreground_pixels = 1500

    result = get_colors(str(image_path))

    assert result.primary_color == "Red"
    assert result.secondary_color in {None, "Red"}
    assert result.primary_color != "Blue"


def test_mask_keeps_dark_foreground(tmp_path: Path) -> None:
    image_path = tmp_path / "black_on_white.png"
    image = Image.new("RGB", (320, 320), color=(245, 245, 245))
    draw = ImageDraw.Draw(image)
    draw.ellipse((80, 80, 240, 260), fill=(0, 0, 0))  # black shoe silhouette
    image.save(image_path)

    settings.ai_color_use_mask = True
    settings.ai_color_mask_method = "heuristic"
    settings.ai_color_min_foreground_pixels = 1200

    result = get_colors(str(image_path))

    assert result.primary_color == "Black"
    assert result.secondary_color in {None, "Black"}


def test_mask_preserves_secondary_from_garment(tmp_path: Path) -> None:
    image_path = tmp_path / "two_tone_on_gray.png"
    image = Image.new("RGB", (360, 360), color=(120, 135, 150))  # muted background
    draw = ImageDraw.Draw(image)
    draw.rectangle((90, 90, 270, 270), fill=(255, 191, 0))  # amber left
    draw.rectangle((180, 90, 270, 270), fill=(44, 160, 44))  # green right
    image.save(image_path)

    settings.ai_color_use_mask = True
    settings.ai_color_mask_method = "heuristic"
    settings.ai_color_topk = 2
    settings.ai_color_min_foreground_pixels = 2000

    result = get_colors(str(image_path))

    garment_colors = {"Amber", "Green"}
    assert result.primary_color in garment_colors
    assert result.secondary_color in garment_colors
