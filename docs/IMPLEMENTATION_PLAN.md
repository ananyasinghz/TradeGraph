# TradeGraph — Implementation Plan

**Status:** Authoritative phased plan (Phases 0–4)  
**Aligned with:** `docs/TRADEGRAPH_REFERENCE.md`  
**Product evolution (post V1.1):** `docs/PRODUCT_USABILITY_PLAN.md`  
**Last updated:** 2026-09-13

---

## Locked decisions

| ID | Decision | Choice |
|----|----------|--------|
| D1 | Repo strategy | Evolve current root → TradeGraph |
| D2 | API | **FastAPI** (not Flask, not Express) |
| D3 | Frontend | **React + Vite + TypeScript** (not MERN) |
| D4 | DB | **SQLite** now; Postgres later |
| D5 | Ask orchestration | **LangGraph** |
| D6 | Form/CRUD | Direct services (same repos/calculators) |
| D7 | Graph MVP | NetworkX; Neo4j later if needed |
| D8 | Vectors MVP | Existing Chroma/fallback pattern; Qdrant later |
| D9 | LLM | Ollama optional; templates when off |
| D10 | Duty math | Never LLM |
| D11 | Corridor v1 | Bangladesh → India, HS ch. 61 |
| D12 | Env prefix | `TRADE_*` |
| D13 | Fraud ML/AML product | Deleted in Phase 0 |
| D14 | Schema | New Alembic chain in Phase 1 (no fraud table migration) |

---

## Phase overview

| Phase | Goal | Exit criteria |
|-------|------|----------------|
| **0** | Align, docs, strip fraud surfaces, health-only app | Docs present; `/health` works; CI green; no ML on default path |
| **1** | Product MVP | Tariff browser + shipments + calculator + checklist + Ask v1 (direct/single_tool) |
| **2** | Graph, FTA, retrieval, watchlist | FTA/graph answers + watchlist change feed |
| **3** | Adaptive LangGraph + baselines | Benchmark table: adaptive vs fixed vs lookup |
| **4** | Ingestion + harden | One real source ingested with approve step |

---

## Phase 0 checklist

- [x] `docs/TRADEGRAPH_REFERENCE.md`
- [x] `docs/IMPLEMENTATION_PLAN.md`
- [x] README → TradeGraph
- [x] `TRADE_*` settings; DB path `trade.db`
- [x] Remove fraud ML, alerts, customers/transactions APIs & UI
- [x] Health-only FastAPI boots
- [x] Frontend shell: TradeGraph nav placeholders
- [x] Reduced test suite + CI-capable config
- [x] Corridor lock documented (BD→IN, ch. 61)

## Phase 1 checklist

- [x] Alembic trade schema + SQLAlchemy models
- [x] BD→IN ch.61 illustrative seed catalog + `scripts/seed_trade_data.py`
- [x] Services: tariff, cost, checklist, shipment
- [x] REST: tariffs, hs-codes, shipments, calculate, sources, ask
- [x] LangGraph Ask: intent → tools → verify (no LLM required)
- [x] UI: Tariff browser, Shipments, Calculator, Sources, Ask
- [x] Same `cost_service` for Calculator UI and Ask

## Phase 2 checklist

- [x] Agreements + eligibility schema; regulatory chunks; watchlist
- [x] NetworkX trade graph + FTA check with graph path
- [x] Keyword retrieval over RoO / notification chunks
- [x] Watchlist + rate-change feed (6109.10 12%→10%)
- [x] Ask routes: `graph_vector` for FTA / regulation
- [x] UI: Agreements, Watchlist, Dashboard changes

## Phase 3 checklist

- [x] Complexity estimator + adaptive route policy
- [x] Baseline modes: `adaptive` / `direct_lookup` / `fixed_multi` / `always_llm`
- [x] Ask metrics: tools, tokens, latency, evidence_score, complexity
- [x] `TRADE_ORCHESTRATION_MODE` + per-request `orchestration_mode`
- [x] Benchmark fixture + `POST /api/v1/eval/run` + `scripts/run_benchmark.py`
- [x] Tests + Ask UI mode selector
- [x] `docs/PHASE3_CHANGELOG.md`

## Phase 4 checklist

- [x] Ingestion schema + Alembic `0003_phase4_ingestion`
- [x] One archived source fixture (CBIC-style Q3 2026)
- [x] Extract → validate → pending review
- [x] Human approve / reject → versioned publish (tariffs + chunks + data_versions)
- [x] Harden: checksum, corridor/HS locks, skip invalid proposals
- [x] Sources UI review workflow + CLI
- [x] `docs/PHASE4_CHANGELOG.md`

---

## Delete map (Phase 0)

### Removed from product path

| Area | Examples |
|------|----------|
| Card-fraud ML | `backend/app/ml/**`, ML scripts, `config/ml/**` |
| AML anomaly/features/EDA | `tools/anomaly`, `tools/features`, `tools/eda`, `tools/statistics` |
| Fraud risk/SAR | `backend/app/risk/**` |
| Alerts product | alerts routes/services + `AlertsView` |
| Customers/transactions | related routes/repos/UI |
| Scoring | `services/scoring.py`, `feature_ref.py`, `provisional_risk.py` |
| Heavy fraud workflow stack | nlu/planning/workflow/tools/evidence/… removed for clean Phase 0; **reintroduce via LangGraph in Phase 1** using patterns from git history |
| Fraud-only tests/scripts/eval | AML/ULB suites |

### Kept / adapted in Phase 0

| Area | Role |
|------|------|
| `backend/app/core/**` | Settings (`TRADE_*`), logging, errors, request ID |
| `backend/app/data/database.py` | SQLite engine helpers |
| `backend/app/domain/base.py` | Strict Pydantic contracts |
| `backend/app/api/routes/health.py` | Health |
| Frontend shell | Nav placeholders for product IA |
| Docs | Reference + this plan |

Git history retains the old investigation graph, NLU, evidence, and tool-registry code as a **pattern reference** for Phase 1 LangGraph + tools — do not re-import AML semantics.

---

## API target (Phase 1+)

Keep: `GET /api/v1/health`

Add: shipments, tariffs, hs-codes, calculate, watchlist, sources, ask, admin data-version.

Remove (done): customers, transactions, alerts, AML investigations/query.

---

## Frontend IA target

```text
Dashboard | Shipments | Tariff browser | Calculator | Documents | Sources | Ask | (Admin later)
```

Delete done: Alerts, Customers.

---

## Dead-end avoidances

| Risk | Mitigation |
|------|------------|
| Chatbot-only product | Phase 1 exit requires browser + calc + shipments |
| Duplicate calc logic | Single `cost_service` |
| LangGraph on every click | Forms call services directly |
| Postgres/Neo4j/Qdrant too early | SQLite + NetworkX + Chroma-pattern first |
| Worldwide data | BD→IN ch. 61 lock |
| LLM duties | Banned + tested |
| Fraud code confusing CI | Stripped in Phase 0 |
| Half rename FRAUD→TRADE | Phase 0 uses `TRADE_*` only |

---

## Open items (optional later)

- Exact checklist doc types beyond COO / commercial invoice / packing list
- Next.js migration (not required; Vite stays)
- When to introduce Neo4j (only after NetworkX pain)

---

## Definition of “on track”

Each week answer:

1. What can a user do **without chat**?
2. Which table is authoritative for rates?
3. Which function computes money?
4. Which corridor/HS are in scope?
5. Was fraud-only code reintroduced by mistake?
