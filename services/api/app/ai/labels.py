"""Curated label sets for local AI classification."""

from __future__ import annotations

from collections.abc import Sequence

CATEGORY_LABELS: Sequence[str] = (
    "top",
    "bottom",
    "shoes",
    "outerwear",
    "accessory",
)

SUBCATEGORY_LABELS: dict[str, Sequence[str]] = {
    "top": (
        "t-shirt",
        "tank top",
        "long sleeve",
        "shirt",
        "polo",
        "hoodie",
        "sweatshirt",
        "sweater",
        "jacket",
        "coat",
    ),
    "bottom": (
        "jeans",
        "chinos",
        "trousers",
        "shorts",
        "skirt",
    ),
    "shoes": (
        "sneakers",
        "boots",
        "loafers",
        "sandals",
        "heels",
    ),
    "outerwear": (
        "puffer",
        "fleece",
        "rain jacket",
        "windbreaker",
    ),
    "accessory": (
        "cap",
        "beanie",
        "belt",
        "bag",
        "scarf",
        "watch",
        "sunglasses",
    ),
}

STYLE_LABELS: Sequence[str] = (
    "streetwear",
    "sport",
    "minimal",
    "retro",
    "outdoor",
    "formal",
    "grunge",
)

MATERIAL_LABELS: Sequence[str] = (
    "cotton",
    "denim",
    "wool",
    "leather",
    "nylon",
    "knit",
    "fleece",
    "suede",
    "mesh",
)
