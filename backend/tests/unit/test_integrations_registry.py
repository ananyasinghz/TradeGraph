"""IF-1 integrations: registry + curated mirror provider."""

from __future__ import annotations

from backend.app.integrations.core.capabilities import Capability
from backend.app.integrations.core.registry import get_registry, reset_registry_for_tests
from backend.app.integrations.providers.curated_mirror import CuratedMirrorProvider


def setup_function() -> None:
    reset_registry_for_tests()


def test_registry_registers_curated_mirror() -> None:
    reg = get_registry()
    assert reg.has("CURATED_MIRROR_CBIC_Q3")
    assert reg.has("cbic_notification_2026_q3")
    provider = reg.get("CBIC_NOTIFICATION_2026_Q3")
    assert isinstance(provider, CuratedMirrorProvider)
    assert Capability.TARIFF_DOCUMENTS in provider.definition.capabilities


def test_curated_mirror_fetch_result() -> None:
    provider = CuratedMirrorProvider()
    result = provider.fetch_result()
    assert result.checksum
    assert result.records
    assert any(r.get("_kind") == "tariff_rate" for r in result.records)
    rates = provider.lookup_tariff("6109.90", "BD", "IN", "2026-09-01")
    assert rates
    assert rates[0]["rate"] == 9.0