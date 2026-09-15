# Live HS + rates envelope

**Status:** Authoritative for Phase A–E full HS search + live rates  
**Aligned with:** `docs/TRADEGRAPH_REFERENCE.md`, plan Live HS Full Search  
**Locked:** 2026-09-15

## Scope

| Dimension | Lock |
|-----------|------|
| Classification | **Full ITC-HS nomenclature** from ingested packs (`ITC-HS_2022.pdf`, `HS_Code_Mappin.pdf`, optional HTTP refresh) |
| Duty rates corridor | **BD→IN only** until a dedicated rate pack exists for other corridors |
| Authority | Ranked **candidates + mandatory Confirm HS** — never auto-file |
| Ranker | SQLite FTS5 + structured priors + synonyms (LLM attributes optional, edge only) |

## Local PDF inventory

| File | Role |
|------|------|
| `config/trade/source/ITC-HS_2022.pdf` | Primary nomenclature |
| `config/trade/source/HS_Code_Mappin.pdf` | Mapping / crosswalk aid |

Honesty: *Local official-style PDF archive — not a live government API until HTTP refresh succeeds.*

## Seed vs operator path

- `config/trade/demo/seed_catalog.v1.yaml` remains for **CI/tests** and bootstrap.
- Operator default path: ingested HS catalog + published tariff rates (approve → publish).

## Success metrics

| Metric | Target |
|--------|--------|
| Classify top-3 recall | ≥ **70%** on gold set (≥ 100 labeled texts; expand toward 200) |
| Suggest latency p95 | &lt; **2s** local for typical queries |
| `live_government_feed` | `true` only when live HTTP adapter succeeds within `TRADE_LIVE_FEED_MAX_AGE_HOURS` **and** approved published rates exist |

## HTTP fetch

- Hosts must match `TRADE_HTTP_SOURCE_ALLOWLIST` (comma-separated host suffixes). Fail closed if not allowlisted.
- Configure named URLs on `SourceConnection` rows (`adapter=live_http_api`, `fetch_mode=http_get`).
- Curated JSON mirrors **never** set `live_government_feed=true`.

## Disclaimer

TradeGraph is decision-support software. Classifications and duties require verification against official sources and, where appropriate, a licensed customs professional.
