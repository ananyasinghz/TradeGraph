# TradeGraph

Local-first international trade compliance workspace (FastAPI + React + SQLite).  
Ask / multi-step flows use **LangGraph**. Forms and calculators call deterministic services directly.

**North star:** [`docs/TRADEGRAPH_REFERENCE.md`](docs/TRADEGRAPH_REFERENCE.md)  
**Build plan (Phases 0–4):** [`docs/IMPLEMENTATION_PLAN.md`](docs/IMPLEMENTATION_PLAN.md)  
**Product usability (R1–R4):** [`docs/PRODUCT_USABILITY_PLAN.md`](docs/PRODUCT_USABILITY_PLAN.md)

## Demo day (copy-paste)

You need two things installed on your machine:

1. **Python 3.11** (not 3.12+)
2. **Node.js** (includes `npm`)

You do **not** need Ollama, Postgres, or cloud API keys for the default demo.

### Full HS catalog (recommended after seed)

Local PDFs live under `config/trade/source/` (`ITC-HS_2022.pdf`, `HS_Code_Mappin.pdf`). After migrations:

```powershell
alembic upgrade head
python scripts/load_hs_nomenclature.py --from-pdf config/trade/source/HS_Code_Mappin.pdf
# optional slower full ITC extract:
# python scripts/extract_hs_pdf.py
# python scripts/run_hs_eval.py
```

Classify then searches the full loaded nomenclature (FTS + rules), not only chapter 61 seed rows. See [`docs/LIVE_HS_ENVELOPE.md`](docs/LIVE_HS_ENVELOPE.md).

### Terminal 1 — backend

Open PowerShell in this project folder:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
Copy-Item .env.example .env

alembic upgrade head
python scripts/seed_trade_data.py --create-schema --force

# If the DB is stuck / missing Alembic version / missing columns, stop uvicorn first:
#   python scripts/reset_demo_db.py --fetch
# Credible demo in 3 commands (after seed + API schema):
#   python scripts/demo_promote_cbic.py
#   # refresh UI → Verified source, approved rules, Customs mode unlocks with freight/insurance
# Or use Admin → Sources → Demo fixture lane → "Make demo fixture rates live".

uvicorn backend.app.main:app --reload --port 8000
```

Leave this running. Quick check: open http://127.0.0.1:8000/api/v1/health

**Honesty — Admin Sources lanes:**

- **Live / official:** always-seeded `cbic_ch61_igst_notif_9_2025` (Notification 9/2025 IGST PDF). Refresh fetches the remote document when allowlisted — not the curated Q3 JSON.
- **Demo fixture:** `cbic_notification_2026_q3` local JSON only (collapsed panel). Never claim it is live CBIC.
- Scheduler defaults to **Manual refresh only**. `live_government_feed` is only true when `TRADE_LIVE_FEED_ENABLED=true` and a successful live/official fetch is within `TRADE_LIVE_FEED_MAX_AGE_HOURS`.
- Publishing requires an authenticated reviewer unless `TRADE_ALLOW_ANONYMOUS_PUBLISH=true` in local development.

### Terminal 2 — frontend

```powershell
cd frontend
npm install
npm run dev
```

Open the URL Vite prints (usually http://127.0.0.1:5173).

### End-to-end tests (Playwright)

From `frontend/` (starts an isolated API + Vite automatically):

```powershell
cd frontend
npm install
npx playwright install chromium
npm run test:e2e:r0
# all tagged rounds:
npm run test:e2e
```

Checkpoint notes live under [`docs/ux-checkpoints/`](docs/ux-checkpoints/).

### Authentication (Firebase)

Default local demo keeps **`TRADE_AUTH_ENABLED=false`** so the API stays open for offline demos and CI.

To require login (Email/Password + Google):

1. Follow [`docs/FIREBASE_AUTH.md`](docs/FIREBASE_AUTH.md).
2. Set backend `TRADE_AUTH_ENABLED=true` and `TRADE_FIREBASE_PROJECT_ID=...`.
3. Set frontend `VITE_FIREBASE_*` values and restart Vite.
4. Sign in from the login screen; the SPA sends `Authorization: Bearer <Firebase ID token>`.

Security inventory: [`docs/SECURITY_AUDIT.md`](docs/SECURITY_AUDIT.md). Production (`TRADE_ENVIRONMENT=production`) forces auth on and rejects demo Bearer tokens.

### What to click first

1. **Tariff browser** — search HS `6109.10` (hover ⓘ if a word is unclear)
2. **Calculator** — run landed cost
3. **Ask** — try a demo question (mode `adaptive` is fine)
4. **Sources** — Ingest CBIC Q3 archive → Approve & publish
5. **Glossary** — every tip definition in one place

New visitors also see a dismissible “New here?” banner at the top.

## Prototype scope

- Corridor: **Bangladesh → India**
- HS focus: chapter **61** (knit apparel)
- Seed rates are **illustrative** unless marked `demo_verified`

## Status

**Phase 4 complete:** archived source ingest with validate → approve → versioned publish.  
**Novice UX:** ⓘ tips, Glossary, Documents catalog, demo-day README.

## Setup (details)

### Backend

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
Copy-Item .env.example .env

# Create schema + seed illustrative BD→IN ch.61 data (v2 includes FTA/watchlist)
alembic upgrade head
python scripts/seed_trade_data.py --create-schema --force

uvicorn backend.app.main:app --reload --port 8000
```

Health: `GET http://127.0.0.1:8000/api/v1/health`

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

## Orchestration modes (Phase 3)

Set default via `TRADE_ORCHESTRATION_MODE` or pass `orchestration_mode` on `POST /api/v1/ask`:

| Mode | Behavior |
|------|----------|
| `adaptive` | Cheapest reliable tool path from complexity |
| `direct_lookup` | Tariff lookup only |
| `fixed_multi` | Full multi-tool fan-out |
| `always_llm` | Fan-out + LLM token proxy (duties still deterministic) |

```powershell
python scripts/run_benchmark.py --ensure-seed
# or POST /api/v1/eval/run
```

## Ingestion (Phase 4)

```powershell
python scripts/run_ingest.py --force
python scripts/run_ingest.py --approve <batch_id> --notes "reviewed"
```

Or use **Sources & ingestion** in the UI / `POST /api/v1/ingest/run` then approve.

## Phase 1–4 APIs

| Method | Path |
|--------|------|
| GET | `/api/v1/health` |
| GET | `/api/v1/hs-codes` |
| GET | `/api/v1/tariffs` |
| GET | `/api/v1/tariffs/{id}/history` |
| POST | `/api/v1/calculate/landed-cost` |
| CRUD-ish | `/api/v1/shipments` (+ `/calculate`, `/checklist`) |
| GET | `/api/v1/sources` |
| GET | `/api/v1/document-requirements` |
| POST | `/api/v1/ask` |
| GET/POST | `/api/v1/agreements`, `/api/v1/fta/check` |
| GET | `/api/v1/retrieve` |
| GET/POST | `/api/v1/watchlist`, `/api/v1/watchlist/changes` |
| POST | `/api/v1/eval/run` |
| POST | `/api/v1/ingest/run` |
| GET | `/api/v1/ingest/batches` |
| POST | `/api/v1/ingest/batches/{id}/approve` · `/reject` |
| GET | `/api/v1/data-versions` |

## Quality

```powershell
ruff check backend scripts
mypy backend
pytest
```

## Disclaimer

TradeGraph is decision-support software, not a substitute for licensed customs advice.
