# Live government feed

TradeGraph can refresh an allowlisted HTTP JSON tariff pack, archive the
bytes, normalize into the CBIC ingest envelope, create a **pending**
ingestion batch, and publish only after human approval.

## Controlled test path (required before production)

```bash
python scripts/live_feed_test_server.py
```

```env
TRADE_LIVE_FEED_ENABLED=true
TRADE_LIVE_TARIFF_HTTP_URL=http://127.0.0.1:8765/tariff_pack.json
TRADE_HTTP_SOURCE_ALLOWLIST=localhost,127.0.0.1
```

Then in Admin → Sources: **Refresh** on `live_tariff_http`, review the
diff, **Make rates live**.

Scenarios: `GET /scenario/valid|rate_change|unchanged_whitespace|malformed|404|500`.

## Production scheduler (Phase 4)

Enable the in-process fetch loop only when you intend continuous refresh:

```env
TRADE_SOURCE_FETCH_SCHEDULER_ENABLED=true
TRADE_SOURCE_FETCH_INTERVAL_MINUTES=60
```

Recommended production posture:

1. Keep scheduler **off** until Admin Sources trust + approve workflow is rehearsed.
2. Prefer official document connections (CBIC HTML/PDF) with human approve before rates go live.
3. Impact alerts fire only when the **applicable duty stack signature** changes (e.g. IGST 5→12), not when archive bytes or provenance metadata churn without rate change.
4. Preferential / RoO claims remain case-gated (CoO + FTA eligibility); scheduled refresh never invents preference.

See `backend/app/core/lifespan.py` (`source_fetch_scheduler_enabled`).

## Honesty rules

`live_government_feed=true` only when:

1. A live HTTP adapter connection exists (`live_http_api`).
2. `TRADE_LIVE_FEED_ENABLED=true`.
3. Last **live-adapter** fetch is within `TRADE_LIVE_FEED_MAX_AGE_HOURS`.
4. Approved `source_verified` rates from that live source are published.

Curated fixture refresh never freshen the live timestamp.

## Pipeline stages

`configured` → `fetch_success` → `parsed` → `pending_review` / `quarantined`
→ `approved` / `published`, or `unchanged` / `error` / `stale`.

## First official CBIC / ICEGATE sources

For **HTML/PDF portal documents** (Tax Information Portal, CBIC Customs,
ICEGATE public pages), see [OFFICIAL_INDIA_SOURCES.md](OFFICIAL_INDIA_SOURCES.md).

For the completed **Live Source Verification — CBIC Chapter 61** chain against a
real `courier.cbic.gov.in` document, see
[LIVE_SOURCE_VERIFICATION_CBIC_CH61.md](LIVE_SOURCE_VERIFICATION_CBIC_CH61.md).

For a **JSON pack** that already matches the CBIC envelope, point
`TRADE_LIVE_TARIFF_HTTP_URL` at a verified, permitlisted URL matching
`config/trade/fixtures/cbic/cbic_notification_2026_q3.json`.

Document for each official URL:

- Original URL and retrieval date
- Document type (full pack vs amendment/notice)
- Coverage limits (HS chapters, duty components)
- Checksum of the archived artifact

Do not treat a partial notification as a complete tariff schedule.
Preferential / RoO / exemption applicability still requires case review.

## Security

- Host allowlist (fail closed)
- HTTPS required for non-loopback live URLs
- SSRF blocks private/link-local/metadata addresses
- Redirect targets re-checked against the allowlist
- Timeouts, size limits, content-type checks, bounded 5xx retries
