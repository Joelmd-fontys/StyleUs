from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from app.ai.color import get_colors


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
