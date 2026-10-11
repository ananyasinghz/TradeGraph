"""Cotton shirt / T-shirt attribute + ranking priors."""

from __future__ import annotations

from backend.app.services.classification_service import rank_descriptions
from backend.app.services.hs_attributes import extract_attributes_rules


def test_cotton_shirts_map_to_tshirt_knit() -> None:
    attrs = extract_attributes_rules("100% cotton shirts")
    assert attrs.garment_type == "tshirt"
    assert attrs.construction == "knit"
    assert attrs.material == "cotton"


def test_tshirts_still_tshirt() -> None:
    attrs = extract_attributes_rules("Cotton T-shirts")
    assert attrs.garment_type == "tshirt"


def test_dress_shirt_stays_woven_shirt() -> None:
    attrs = extract_attributes_rules("men's woven oxford dress shirt")
    assert attrs.garment_type == "shirt"
    assert attrs.construction == "woven"


def test_ranking_prefers_6109_over_jackets() -> None:
    ranked = rank_descriptions(
        "100% cotton shirts",
        [
            ("6203.32", "Jackets and blazers : -- Of cotton"),
            ("6109.10", "T-shirts, singlets and other vests, of cotton"),
            ("6203.23", "Ensembles : -- Of synthetic fibres"),
        ],
    )
    assert ranked[0][0] == "6109.10"
