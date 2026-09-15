# Phase 4 changelog

**Date:** 2026-09-13

## Delivered

- Alembic `0003_phase4_ingestion`: `ingestion_batches`, `ingestion_proposals`, `data_versions`
- Archived fixture source: `config/trade/sources/cbic_notification_2026_q3.json`
- Pipeline: extract → validate (corridor/HS/rate) → **human approve/reject** → versioned publish
- Approved rates supersede prior active rows; `data_quality=demo_verified` + checksummed source
- Invalid proposals (unknown HS, wrong origin) stay rejected/skipped and never publish
- APIs: `POST /ingest/run`, batch list/get, approve/reject, `GET /data-versions`
- CLI: `python scripts/run_ingest.py [--approve BATCH_ID]`
- Sources UI: ingest / review / approve + data versions

## Run

```powershell
alembic upgrade head
python scripts/seed_trade_data.py --create-schema --force
python scripts/run_ingest.py --force
# note batch id from output, then:
# python scripts/run_ingest.py --approve <batch_id> --notes "reviewed"
uvicorn backend.app.main:app --reload --port 8000
```

## Exit criteria

1. One archive source ingested into a pending batch with validation errors surfaced  
2. Approve publishes only valid proposals and creates a data version  
3. Published tariff visible in browser with `demo_verified` quality  
