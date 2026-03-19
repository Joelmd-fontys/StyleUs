"""Curated label sets and prompt phrases for local fashion classification."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LabelSpec:
    label: str
    prompts: tuple[str, ...]


def _labels(specs: Sequence[LabelSpec]) -> tuple[str, ...]:
    return tuple(spec.label for spec in specs)


CATEGORY_SPECS: tuple[LabelSpec, ...] = (
    LabelSpec(
        "top",
        (
            "upper body clothing item like a t-shirt, shirt, polo, hoodie or sweater",
            "topwear garment worn on the torso",
            "fashion top for the upper body",
        ),
    ),
    LabelSpec(
        "bottom",
        (
            "lower body clothing item like jeans, trousers, shorts or skirt",
            "pants or bottoms worn on the waist and legs",
            "fashion bottom for the lower body",
        ),
    ),
    LabelSpec(
        "shoes",
        (
            "fashion footwear like sneakers, boots, loafers, sandals or heels",
            "pair of shoes or other footwear",
            "shoe item worn on the feet",
        ),
    ),
    LabelSpec(
        "outerwear",
        (
            "outer layer like a puffer, fleece, rain jacket or windbreaker",
            "protective outerwear worn over other clothing",
            "fashion outer layer garment",
        ),
    ),
    LabelSpec(
        "accessory",
        (
            "fashion accessory like a bag, belt, cap, scarf, watch or sunglasses",
            "wardrobe accessory rather than a main garment",
            "small fashion accessory item",
        ),
    ),
)

SUBCATEGORY_SPECS: Mapping[str, tuple[LabelSpec, ...]] = {
    "top": (
        LabelSpec("t-shirt", ("short sleeve tee shirt top", "crew neck t-shirt", "casual tee top")),
        LabelSpec("tank top", ("sleeveless tank top", "tank shirt", "athletic tank top")),
        LabelSpec("long sleeve", ("long sleeve tee top", "long sleeve shirt", "long sleeve knit top")),
        LabelSpec("shirt", ("button up shirt", "dress shirt top", "collared woven shirt")),
        LabelSpec("polo", ("polo shirt with collar", "short sleeve polo top", "knit polo shirt")),
        LabelSpec("hoodie", ("hooded sweatshirt", "hoodie top", "casual hooded pullover")),
        LabelSpec("sweatshirt", ("crewneck sweatshirt", "casual sweatshirt top", "pullover sweatshirt")),
        LabelSpec("sweater", ("knit sweater", "pullover sweater top", "soft sweater knitwear")),
        LabelSpec("jacket", ("lightweight jacket top", "zip jacket", "casual jacket topwear")),
        LabelSpec("coat", ("long coat topwear", "tailored coat", "heavy coat top")),
    ),
    "bottom": (
        LabelSpec("jeans", ("denim jeans", "jean pants", "casual denim bottoms")),
        LabelSpec("chinos", ("chino pants", "casual chino trousers", "cotton chinos")),
        LabelSpec("trousers", ("tailored trousers", "dress pants", "formal trousers")),
        LabelSpec("shorts", ("short pants", "casual shorts", "athletic shorts")),
        LabelSpec("skirt", ("skirt bottom", "mini or midi skirt", "fashion skirt")),
    ),
    "shoes": (
        LabelSpec("sneakers", ("sneakers", "trainers shoes", "casual athletic sneakers")),
        LabelSpec("boots", ("boots footwear", "ankle boots", "combat or work boots")),
        LabelSpec("loafers", ("loafers shoes", "slip on loafers", "dress loafers")),
        LabelSpec("sandals", ("sandals footwear", "open toe sandals", "strappy sandals")),
        LabelSpec("heels", ("high heels shoes", "heeled pumps", "dress heels")),
    ),
    "outerwear": (
        LabelSpec("puffer", ("puffer jacket", "quilted padded jacket", "down puffer outerwear")),
        LabelSpec("fleece", ("fleece jacket", "fleece outerwear", "soft fleece zip jacket")),
        LabelSpec("rain jacket", ("rain jacket shell", "waterproof jacket", "rain shell outerwear")),
        LabelSpec("windbreaker", ("windbreaker jacket", "light shell jacket", "sport windbreaker")),
    ),
    "accessory": (
        LabelSpec("cap", ("baseball cap", "cap hat", "casual cap accessory")),
        LabelSpec("beanie", ("beanie hat", "knit beanie", "winter beanie accessory")),
        LabelSpec("belt", ("belt accessory", "leather belt", "waist belt")),
        LabelSpec("bag", ("bag accessory", "handbag", "shoulder or tote bag")),
        LabelSpec("scarf", ("scarf accessory", "knit scarf", "neck scarf")),
        LabelSpec("watch", ("watch accessory", "wrist watch", "analog watch")),
        LabelSpec("sunglasses", ("sunglasses accessory", "dark sunglasses", "fashion eyewear")),
    ),
}

STYLE_SPECS: tuple[LabelSpec, ...] = (
    LabelSpec("casual", ("casual everyday style", "relaxed casual fashion", "easy everyday outfit piece")),
    LabelSpec("streetwear", ("streetwear style", "urban street style", "street fashion piece")),
    LabelSpec("formal", ("formal tailored style", "dressy formal fashion", "smart occasion wear")),
    LabelSpec("sporty", ("sporty athletic style", "activewear inspired fashion", "performance sport style")),
    LabelSpec("outdoor", ("outdoor utility style", "gorpcore outdoor fashion", "technical outdoor piece")),
    LabelSpec("minimal", ("minimal clean style", "simple understated fashion", "minimal wardrobe staple")),
    LabelSpec("vintage", ("vintage style", "aged archival fashion look", "secondhand vintage aesthetic")),
    LabelSpec("retro", ("retro style", "throwback fashion look", "old school retro aesthetic")),
    LabelSpec("heritage", ("heritage style", "classic heritage fashion", "timeless heritage piece")),
)

MATERIAL_SPECS: tuple[LabelSpec, ...] = (
    LabelSpec("cotton", ("cotton fabric", "cotton garment", "soft cotton material")),
    LabelSpec("denim", ("denim fabric", "denim garment", "rigid denim material")),
    LabelSpec("wool", ("wool fabric", "wool garment", "warm wool material")),
    LabelSpec("leather", ("leather material", "leather garment", "smooth leather finish")),
    LabelSpec("nylon", ("nylon fabric", "technical nylon shell", "synthetic nylon material")),
    LabelSpec("knit", ("knit fabric", "ribbed knit material", "knitted garment texture")),
    LabelSpec("fleece", ("fleece material", "soft fleece fabric", "fleece texture")),
    LabelSpec("suede", ("suede material", "brushed suede finish", "soft suede leather")),
    LabelSpec("mesh", ("mesh material", "breathable mesh fabric", "open mesh texture")),
    LabelSpec("canvas", ("canvas material", "canvas fabric", "sturdy canvas texture")),
    LabelSpec("linen", ("linen material", "linen fabric", "lightweight linen texture")),
)

ATTRIBUTE_SPECS: tuple[LabelSpec, ...] = (
    LabelSpec("oversized", ("oversized fit", "boxy oversized silhouette", "roomy loose fitting item")),
    LabelSpec("slim-fit", ("slim fit silhouette", "close fitting garment", "streamlined slim fit")),
    LabelSpec("relaxed", ("relaxed fit", "easy relaxed silhouette", "loose casual fit")),
    LabelSpec("tailored", ("tailored construction", "structured tailored fit", "clean tailored silhouette")),
    LabelSpec("cropped", ("cropped length", "short cropped silhouette", "cropped garment shape")),
    LabelSpec("quilted", ("quilted construction", "padded quilted texture", "stitched quilted finish")),
    LabelSpec("chunky", ("chunky shape", "bulky chunky silhouette", "thick chunky footwear or knit")),
    LabelSpec("boxy", ("boxy silhouette", "square boxy fit", "wide straight boxy shape")),
)

CATEGORY_LABELS: Sequence[str] = _labels(CATEGORY_SPECS)
SUBCATEGORY_LABELS: dict[str, Sequence[str]] = {
    category: _labels(specs) for category, specs in SUBCATEGORY_SPECS.items()
}
STYLE_LABELS: Sequence[str] = _labels(STYLE_SPECS)
MATERIAL_LABELS: Sequence[str] = _labels(MATERIAL_SPECS)
ATTRIBUTE_LABELS: Sequence[str] = _labels(ATTRIBUTE_SPECS)

SUBCATEGORY_TO_CATEGORY: dict[str, str] = {
    spec.label: category for category, specs in SUBCATEGORY_SPECS.items() for spec in specs
}
