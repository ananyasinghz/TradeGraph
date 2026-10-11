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
    # Tee / T-shirt forms (including "t shirts", "tees")
    if (
        "tshirt" in compact
        or "t-shirt" in t
        or "tee shirt" in t
        or re.search(r"\bt[\s-]?shirts?\b", t)
        or re.search(r"\btees?\b", t)
    ):
        garment = "tshirt"
        if construction is None:
            construction = "knit"
    elif "blouse" in t:
        garment = "blouse"
    elif any(x in t for x in ("trouser", "trousers", "slacks")) or (
        "pants" in t and "under" not in t
    ):
        garment = "trousers"
    elif re.search(r"\bshirts?\b", t):
        # "cotton shirts" without woven cue → treat as knit T-shirt style (ch.61)
        # unless explicitly dress/woven/oxford/button.
        woven_shirt = any(
            x in t
            for x in ("woven", "dress shirt", "oxford", "button-down", "button down", "formal")
        )
        if woven_shirt:
            garment = "shirt"
            if construction is None:
                construction = "woven"
        else:
            garment = "tshirt"
            if construction is None:
                construction = "knit"
    elif any(x in t for x in ("jersey", "pullover", "sweater", "cardigan")):
        garment = "knit_top"
        if construction is None:
            construction = "knit"
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
