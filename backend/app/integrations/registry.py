"""Bootstrap integration provider registry."""

from __future__ import annotations

from backend.app.integrations.core.registry import IntegrationRegistry
from backend.app.integrations.providers.bangladesh_customs import BangladeshCustomsProvider
from backend.app.integrations.providers.cbic import CbicDocumentProvider, CbicLegacyQ3Provider
from backend.app.integrations.providers.curated_mirror import CuratedMirrorProvider


def bootstrap_registry(registry: IntegrationRegistry) -> IntegrationRegistry:
    """Register built-in providers. Called once from get_registry()."""
    if not registry.has("CURATED_MIRROR_CBIC_Q3"):
        legacy = CbicLegacyQ3Provider()
        registry.register("CURATED_MIRROR_CBIC_Q3", legacy)
        registry.register("CBIC_NOTIFICATION_2026_Q3", legacy)

    if not registry.has("IN_CBIC"):
        registry.register("IN_CBIC", CbicDocumentProvider())

    if not registry.has("BD_CUSTOMS"):
        registry.register("BD_CUSTOMS", BangladeshCustomsProvider())

    # Keep generic curated mirror available for demos
    if not registry.has("CURATED_MIRROR"):
        registry.register("CURATED_MIRROR", CuratedMirrorProvider())
    return registry
