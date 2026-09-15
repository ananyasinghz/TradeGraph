# Phase 1 changelog

**Date:** 2026-09-13

## Delivered

- SQLite trade schema (Alembic `0001_phase1_trade_schema` + ORM models)
- Illustrative BD→IN chapter 61 seed (`config/trade/seed_catalog.v1.yaml`)
- Services: tariff lookup (as-of + history), landed-cost calculator, checklist, shipments
- REST APIs: `/hs-codes`, `/tariffs`, `/calculate/landed-cost`, `/shipments`, `/sources`, `/ask`
- LangGraph Ask graph: parse intent → deterministic tools → verify (Ollama not required)
- Frontend: Tariff browser, Shipments workspace, Calculator, Sources, Ask
- Calculator and Ask share `cost_service.calculate`

## Verify locally

```powershell
alembic upgrade head
python scripts/seed_trade_data.py --create-schema --force
uvicorn backend.app.main:app --reload --port 8000
cd frontend; npm install; npm run dev
```

## Exit criteria covered

1. Browse HS → rate + source + as-of  
2. Create shipment → calculate landed cost  
3. Build checklist  
4. Ask duty question → same tariff id/rate as browser  
5. As-of 2025 vs 2026 for HS 6109.10 → 12% vs 10%

## Next (Phase 2)

Graph/FTA, watchlist, richer retrieval corpus.
