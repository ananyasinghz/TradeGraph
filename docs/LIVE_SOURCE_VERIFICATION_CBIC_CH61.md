# Live Source Verification — CBIC, Chapter 61

Milestone: prove one **real** official CBIC document path (no local fixture server)
for the narrow slice **BD → IN, Chapter 61**, through fetch → archive → parse →
approve → tariff lookup → shipment recalculation → refresh/outage safety.

## Locked official source

| Field | Value |
|-------|--------|
| Connection key | `cbic_ch61_igst_notif_9_2025` (always seeded; legacy alias `cbic_customs_docs` when env URLs set) |
| Portal / index URL | `https://courier.cbic.gov.in/notification.jsp` |
| **Pinned document URL** | `https://courier.cbic.gov.in/advisory/2025/NOTIFICATION%20NO.%209_2025-INTEGRATED%20TAX%20(RATE)%20-1759486719.pdf` |
| Host allowlist required | `courier.cbic.gov.in` |
| Document identity | Notification No. 9/2025-Integrated Tax (Rate), dated 17-9-2025 (ICAI-formatted reprint hosted on CBIC Courier portal) |
| Why relevant | Schedule I explicitly lists **chapter 61** “Articles of apparel and clothing accessories, knitted or crocheted” (sale value not exceeding Rs 2500/piece) at **IGST 5%** |
| Fixture server used? | **No** |
| Example artifact SHA-256 (2026-10-11 verify run) | `22943574e66ff2d6c14114ebd68c521457d1fa8437801804e92e6356209e9134` |
| Example archive | `data/processed/source_archives/cbic_customs_docs_22943574e66f.bin` |
| Parser | `official_india_doc.v2` (IGST Schedule I chapter 61 → HS 6109.10 exemplar) |

### Coverage limits (honesty)

- This is an **IGST (Rate)** schedule notification, **not** a complete Customs Tariff BCD pack.
- Preferential / SAFTA / RoO eligibility is **not** established by this document.
- Extractor maps the chapter-61 knitted apparel schedule line to exemplar HS **6109.10** for the product’s Chapter 61 BD→IN slice (`parser_version=official_india_doc.v2`).
- BCD is **not** stated in this notification. Approve merges **IGST-only** into the stack (`_partial_components`) and must **not** zero curated BCD/SWS. Published rows keep separate per-component provenance.
- Does **not** claim live coverage of all HS chapters, ICEGATE calculator, or all duty components.

### Human validation table (Gate 3)

| Field | Official document text | Extracted / published |
|-------|------------------------|------------------------|
| Notice | Notification No. 9/2025-Integrated Tax (Rate) dated 17-9-2025 | `notice_id` ≈ `9/2025-INTEGRATEDTAX(RATE)` |
| Effective | 17 September 2025 | `effective_from=2025-09-17` |
| Chapter | “61 Articles of apparel… knitted… sale value not exceeding Rs 2500” (Schedule I) | Mapped exemplar **6109.10** |
| Duty | Schedule I = **5 per cent.** IGST | `igst_pct=5.0` (partial); curated BCD/SWS retained on merge |
| Corridor | Import into India (IGST on supplies/imports under IGST Act) | Origin **BD**, destination **IN** (product corridor filter) |

## How to re-run

```env
TRADE_LIVE_FEED_ENABLED=true
TRADE_HTTP_SOURCE_ALLOWLIST=localhost,127.0.0.1,courier.cbic.gov.in
TRADE_CBIC_CUSTOMS_URL=https://courier.cbic.gov.in/notification.jsp
TRADE_CBIC_CUSTOMS_DOCUMENT_URL=https://courier.cbic.gov.in/advisory/2025/NOTIFICATION%20NO.%209_2025-INTEGRATED%20TAX%20(RATE)%20-1759486719.pdf
TRADE_LIVE_OFFICIAL_VERIFY=1
```

```bash
python scripts/verify_live_cbic_ch61.py
```

Opt-in pytest (skipped in default CI):

```bash
set TRADE_LIVE_OFFICIAL_VERIFY=1
pytest backend/tests/integration/test_live_official_cbic_ch61.py -q --no-cov
```

## Acceptance gates

1. **Connect** — successful HTTPS fetch from `courier.cbic.gov.in` without fixture server.
2. **Prove content** — archive path + SHA-256 + final URL recorded (script prints PROVENANCE).
3. **Validate** — at least one publishable Chapter 61 proposal; ambiguous rows quarantine.
4. **Operate** — approve → `GET /tariffs` for 6109.10 BD→IN → shipment calculate cites published path.
5. **Refresh / outage** — second refresh `unchanged` (no false churn); failed fetch sets `last_error` while prior published rates remain resolvable.

## Related docs

- [OFFICIAL_INDIA_SOURCES.md](OFFICIAL_INDIA_SOURCES.md)
- [LIVE_GOVERNMENT_FEED.md](LIVE_GOVERNMENT_FEED.md)
