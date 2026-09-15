# TradeGraph — Product Usability Plan

**Status:** Locked / authoritative for product evolution after V1.1  
**Aligned with:** `docs/TRADEGRAPH_REFERENCE.md`, `docs/IMPLEMENTATION_PLAN.md` (Phases 0–4 complete)  
**Locked:** 2026-09-13  

---

## North-star rule

> TradeGraph must never present an illustrative, incomplete, or outdated result as if it were a real compliance decision.

Evolve the existing FastAPI + React + SQLite foundation. Do **not** rebuild from scratch. Keep research (adaptive routing, benchmarks) behind Admin / Research Lab.

### Three foundations

1. Versioned, reviewable, cited sources  
2. Complete shipment / line-item / document / evidence model  
3. Safe answers (uncertainty, assumptions, dates, citations)

---

## Dual product modes

| Mode | When | UI must show |
|------|------|----------------|
| **Demonstration** | Seeded / synthetic / research / no approved published corpus | Demo data · Illustrative rule · Not an official customs determination · No live government feed |
| **Operational** | Official sources archived, reviewed, published; every result has evidence | Curated / approved labels; still never invent rates via LLM |

Do not silently switch modes. Effective mode is exposed by `GET /api/v1/system/status`. Operational is allowed only when approved published coverage exists; otherwise the API **forces Demonstration** and reports why.

Until a live scheduler exists, never claim “live data.” Prefer:

- *Official-source-backed, manually refreshed data*, or  
- *Curated regulatory dataset*

---

## Reuse (do not discard)

- Shipment-centered workspace  
- Deterministic duty math (`cost_service`)  
- Seed + Alembic + `data_quality` badges  
- Ingest validate → approve → publish  
- LangGraph Ask + adaptive baselines  
- Watchlist ↔ shipment linkage  
- V1.1 docs statuses, drafts, formula narrative, honesty tips  

**Do not expand countries** until BD→IN chapter 61 is operationally honest.

---

## Release overview

| Release | Goal | Est. |
|---------|------|------|
| **R1** | Honest & safe (trust before features) | 1–2 weeks |
| **R2** | One corridor operationally useful (BD→IN) | 4–8 weeks |
| **R3** | Collaboration & monitoring (auth, jobs, Postgres) | 4–6 weeks |
| **R4** | Research contribution on a trustworthy base | ongoing |

---

## Release 1 — Honest & safe

1. Dual mode + global status banner (`/system/status`) — **S1**  
2. Coverage-miss / fail-safe empty states — **S2**  
3. Ask answer contract + FTA rename + estimate labeling — **S3**  
4. Nav split: user vs Research Lab — **S4**  
5. Honesty badges on every compliance surface (extends S1–S3)  

### R1 exit criteria

- Demo / mode banner unavoidable  
- Unsupported HS/corridor never looks like a silent bug (S2)  
- FTA never claims bare “eligible” without evidence (S3)  
- Research modes not in main nav (S4)  

---

## Release 2 — BD→IN operationally useful

Schema: Party, Shipment enrichment, LineItem, TariffRule (regime + supersession), Regulation/Source enrichment, Evidence, Document/Version, CalculationSnapshot.

Source lifecycle:

```
Discover → Fetch → Archive → Checksum → Parse → Extract
  → Validate → Review → Approve → Publish → Index → Notify
```

Statuses: `unverified | fetched | parsed | validation_failed | awaiting_review | approved | published | superseded | rejected | expired`

Also: HS classification assistance; valuation estimate vs customs modes; FTA condition engine; document forms + PDF + uploads; shipment tabs + readiness score.

**Happy path:** create shipment → describe product → HS candidates → confirm → approved tariff → FTA needs_evidence → upload docs → estimate cost → missing evidence → export pack — with citations.

---

## Release 3 — Collaboration & monitoring

Auth (Viewer / Operator / Reviewer / Admin), audit trail, background ingest/diff jobs, watchlist impact notifications, PostgreSQL + Docker Compose, backups, readiness, rate limits.

---

## Release 4 — Research

Measure evidence completeness, unsupported-claim rate, effective-date accuracy, false-confidence rate, human-review reduction, classification quality, latency/tokens/cost. Keep Research Lab separate from operator UI.

---

## Implementation slices (PR order)

| Slice | Release | Outcome | Status |
|-------|---------|---------|--------|
| **S1** | R1 | `/system/status` + global Demo/Operational banner + coverage fields | Done |
| **S2** | R1 | CoverageMiss on tariff/calc/FTA/Ask | Done |
| **S3** | R1 | Ask contract + FTA rename + estimate labeling | Done |
| **S4** | R1 | Nav split user vs Research Lab | Done |
| **S5** | R2 | Migration: Party, LineItem, Evidence, richer Source/TariffRule | Done |
| **S6** | R2 | Source archive + checksum + status machine | Done |
| **S7** | R2 | Classification candidates API + shipment tab | Done |
| **S8** | R2 | Calculation snapshots + estimate vs customs modes | Done |
| **S9** | R2 | FTA condition engine + needs_evidence | Done |
| **S10** | R2 | Document forms + PDF + uploads | Done |
| **S11** | R2 | Readiness score + shipment tab IA | Done |
| **S12** | R3 | Auth / roles / audit | Done |
| **S13** | R3 | Watchlist impact + jobs + Postgres/Compose | Done |

---

## Explicit non-goals (until R2 exit)

- Worldwide corridors / all HS chapters  
- Claiming “live government feed” without scheduler + approve + sync timestamp  
- LLM inventing rates or duties  
- Many decorative agents  
- Mixing research metrics into operator Home  

---

## Bottom line

Evolve from *seeded compliance demo with AI features* into an *evidence-backed trade workflow system* with deterministic rules, human review, versioned sources, document management, and optional local AI for explanations only.
