"""Phase E attribute extraction degrades without Ollama."""

from __future__ import annotations

from backend.app.core.config import Settings
from backend.app.services.hs_attribute_service import extract_product_attributes


def test_attributes_without_ollama() -> None:
    settings = Settings.model_validate(
        {"environment": "test", "ollama_enabled": False, "app_name": "t"}
    )
    attrs = extract_product_attributes("100% linen pants", settings=settings)
    assert attrs.garment_type == "trousers"
    assert attrs.material == "linen"
