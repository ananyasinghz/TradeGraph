"""Shared product attribute extraction for HS ranking (rules + optional LLM)."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class ProductAttributes:
    material: str | None = None
    construction: str | None = None  # knit | woven | unknown
    garment_type: str | None = None
    gender: str | None = None


def extract_attributes_rules(product_text: str) -> ProductAttributes:
    """Deterministic attribute extract (Ollama may enrich via hs_attribute_service)."""
    t = product_text.lower()
    compact = re.sub(r"[^a-z0-9]+", "", t)
    material = None
    for m in (
        "cotton",
        "linen",
        "wool",
        "silk",
        "polyester",
        "nylon",
        "leather",
        "steel",
        "iron",
        "rubber",
    ):
        if m in t:
            material = m
            break
    construction = None
    if any(x in t for x in ("knit", "knitted", "crocheted")):
        construction = "knit"
    elif any(x in t for x in ("woven", "woven fabric")):
        construction = "woven"
    garment = None
    if "tshirt" in compact or "t-shirt" in t or "tee shirt" in t:
        garment = "tshirt"
    elif "blouse" in t:
        garment = "blouse"
    elif any(x in t for x in ("trouser", "trousers", "slacks")) or (
        "pants" in t and "under" not in t
    ):
        garment = "trousers"
    elif "shirt" in t:
        garment = "shirt"
    elif any(x in t for x in ("jersey", "pullover", "sweater", "cardigan")):
        garment = "knit_top"
    elif any(x in t for x in ("screw", "screws", "bolt", "bolts")):
        garment = "fastener"
    elif any(x in t for x in ("laptop", "computer", "notebook")):
        garment = "computer"
    elif any(x in t for x in ("smartphone", "mobile phone", "cellphone")):
        garment = "phone"
    elif "babies" in t or "baby" in t:
        garment = "babies"
    elif any(x in t for x in ("briefs", "panties", "underwear")):
        garment = "underwear"
    gender = None
    if "women" in t or "ladies" in t:
        gender = "women"
    elif "men" in t or "mens" in t:
        gender = "men"
    return ProductAttributes(
        material=material,
        construction=construction,
        garment_type=garment,
        gender=gender,
    )
