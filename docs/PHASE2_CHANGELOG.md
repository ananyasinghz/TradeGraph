# Phase 2 changelog

**Date:** 2026-09-13

## Delivered

- Schema: `trade_agreements`, `agreement_eligibility`, `regulatory_chunks`, `watchlist_items`
- Alembic `0002_phase2_fta_watchlist`
- Seed fingerprint `trade_seed.bd_in_61.v2` (illustrative SAFTA-style FTA + RoO chunks + default watchlist)
- NetworkX graph builder + FTA check with evidence path
- Keyword `/retrieve` over regulatory chunks
- Watchlist CRUD + `/watchlist/changes` (seeded 12%→10% for 6109.10)
- Ask intents: `fta_check`, `regulation_retrieve` → route `graph_vector`
- UI: Agreements, Watchlist, Dashboard change feed

## Re-seed

```powershell
alembic upgrade head
python scripts/seed_trade_data.py --create-schema --force
```

## Exit criteria

1. FTA question returns preferential vs MFN + graph path + citation  
2. Watchlist changes show seeded rate supersession  
3. Retrieval returns RoO / notification excerpts  
