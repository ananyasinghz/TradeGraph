# Official India sources (CBIC + ICEGATE)

TradeGraph can refresh **allowlisted** CBIC and ICEGATE **document URLs**
(HTML/PDF), archive the exact bytes, extract Chapter 61 BD→IN rate lines when
patterns are unambiguous, create a **pending** ingest batch, and publish only
after human approval.

There is **no** public CBIC/ICEGATE tariff REST API used by this product. Portals
are open document sites; acquisition is document fetch + deterministic parse.

## Portals in scope

| Connection key | Env URL | Role |
|----------------|---------|------|
| `cbic_taxinfo_docs` | `TRADE_CBIC_TAXINFO_URL` | CBIC Tax Information Portal documents |
| `cbic_customs_docs` | `TRADE_CBIC_CUSTOMS_URL` | CBIC Customs tariff / notification resources |
| `icegate_public_docs` | `TRADE_ICEGATE_PUBLIC_URL` | ICEGATE **public** reference pages only |

Optional pinned document when the portal URL is an index listing:

- `TRADE_CBIC_TAXINFO_DOCUMENT_URL`
- `TRADE_CBIC_CUSTOMS_DOCUMENT_URL`
- `TRADE_ICEGATE_PUBLIC_DOCUMENT_URL`

Hosts must appear in `TRADE_HTTP_SOURCE_ALLOWLIST` (fail closed).

Example production allowlist (enable deliberately):

```env
TRADE_HTTP_SOURCE_ALLOWLIST=taxinformation.cbic.gov.in,cbic.gov.in,www.cbic.gov.in,icegate.gov.in,www.icegate.gov.in
TRADE_LIVE_FEED_ENABLED=true
TRADE_CBIC_TAXINFO_URL=https://taxinformation.cbic.gov.in/
TRADE_CBIC_TAXINFO_DOCUMENT_URL=https://taxinformation.cbic.gov.in/.../your-pinned-notification
```

## Live Source Verification (Chapter 61)

To prove a real CBIC document (not fixtures), use the locked Courier-hosted
Notification No. 9/2025-Integrated Tax (Rate) URL and run:

`python scripts/verify_live_cbic_ch61.py` with `TRADE_LIVE_OFFICIAL_VERIFY=1`.

See [LIVE_SOURCE_VERIFICATION_CBIC_CH61.md](LIVE_SOURCE_VERIFICATION_CBIC_CH61.md).

## Local fixture path (CI / development)

Fixtures live under `config/trade/fixtures/cbic/official_samples/`.

```env
TRADE_LIVE_FEED_ENABLED=true
TRADE_HTTP_SOURCE_ALLOWLIST=localhost,127.0.0.1
TRADE_CBIC_TAXINFO_URL=http://127.0.0.1:8766/index.html
TRADE_CBIC_TAXINFO_DOCUMENT_URL=http://127.0.0.1:8766/notification.html
```

Serve fixtures with any static HTTP server on port 8766, or use the helpers in
`backend/tests/integration/test_official_india_sources.py`.

## Coverage limits (v1)

- Corridor: **BD → IN**
- HS chapter extract: **61** when clearly stated; other HS may be proposed and
  quarantined by validators
- Document types: labeled `amendment` / `unsupported` — never treated as a
  complete Customs Tariff schedule
- Duty components: BCD-style ad valorem when the pattern matches; SWS/IGST
  defaults are illustrative until review
- Preferential / RoO / ICEGATE duty calculator: **not automated**
- Authenticated ICEGATE / ECCS APIs: **out of scope**

## Honesty

`live_government_feed=true` only when:

1. An official-document or live-JSON adapter connection exists
2. `TRADE_LIVE_FEED_ENABLED=true`
3. Last successful fetch on that adapter is within `TRADE_LIVE_FEED_MAX_AGE_HOURS`
4. Approved `source_verified` rates from that source are published

Curated fixture refresh never counts. A failed refresh sets `last_error` and
pipeline `error` but **does not** supersede previously published rates.

## Operator flow

1. Configure URL + allowlist (+ optional pinned document)
2. Admin → Sources → **Refresh**
3. Inspect archived evidence (URL, checksum, archive path)
4. Review old vs new + quarantined rows
5. **Make rates live** (reviewer/admin)
6. Impacts appear on affected cases when rates actually change

Scheduler uses the same path when `TRADE_SOURCE_FETCH_SCHEDULER_ENABLED=true`.

## Parser

`backend/app/services/official_doc_normalize.py` — `PARSER_VERSION=official_india_doc.v1`.

Uncertain or empty extracts quarantine / archive-as-evidence; no LLM fills rates.
