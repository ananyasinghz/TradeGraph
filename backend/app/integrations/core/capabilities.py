"""Source capability vocabulary (not country flags)."""

from __future__ import annotations

from enum import StrEnum


class Capability(StrEnum):
    TARIFF_LOOKUP = "tariff_lookup"
    TARIFF_DOCUMENTS = "tariff_documents"
    REGULATIONS = "regulations"
    AGREEMENTS = "agreements"
    RULES_OF_ORIGIN = "rules_of_origin"
    IMPORT_RESTRICTIONS = "import_restrictions"
    CLASSIFICATION = "classification"
    TRADE_DOCUMENTS = "trade_documents"
