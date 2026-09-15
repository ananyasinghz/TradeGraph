"""Bangladesh Customs / NBR Level 1-2 document provider (IF-8)."""

from __future__ import annotations

from backend.app.integrations.core.capabilities import Capability
from backend.app.integrations.core.models import SourceDefinition
from backend.app.integrations.providers.curated_mirror import CuratedMirrorProvider

BD_DEFINITION = SourceDefinition(
    code="BD_CUSTOMS",
    provider="bangladesh_customs",
    country="BD",
    capabilities=frozenset(
        {
            Capability.TARIFF_DOCUMENTS,
            Capability.REGULATIONS,
            Capability.IMPORT_RESTRICTIONS,
        }
    ),
    supported_formats=frozenset({"json"}),
    requires_auth=False,
    access_method="document",
    honesty_label="Official-source-backed BD Customs document archive (Level 1/2, not live API)",
)

BD_FIXTURE = "config/trade/fixtures/bd_customs/chapter61_operative_v1.json"


class BangladeshCustomsProvider(CuratedMirrorProvider):
    """Level 1/2: curated operative-tariff JSON (manual upload / scheduled document)."""

    def __init__(self, *, local_path: str = BD_FIXTURE) -> None:
        super().__init__(
            definition=BD_DEFINITION,
            local_path=local_path,
            source_url="https://example.invalid/tradegraph/archives/bd-customs-ch61",
        )
