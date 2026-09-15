# Phase 0 changelog

**Date:** 2026-09-13

## Done

- Added `docs/TRADEGRAPH_REFERENCE.md` (north star) and `docs/IMPLEMENTATION_PLAN.md`.
- Rebranded project to TradeGraph; env prefix `TRADE_*`; default DB `data/processed/trade.db`.
- Stripped fraud ML, AML product APIs (alerts/customers/transactions/query/investigations), and related packages.
- FastAPI app is health-only until Phase 1 product APIs.
- Frontend shell uses TradeGraph IA placeholders (Dashboard, Shipments, Tariff, Calculator, Documents, Sources, Ask).
- Reduced tests to config + health; CI coverage threshold adjusted for slim tree.
- Locked corridor: Bangladesh → India, HS chapter 61.
- Locked Ask orchestration: LangGraph (to be wired in Phase 1).

## Not in Phase 0

- Trade schema, seed data, LangGraph graph, tariff/shipment APIs (Phase 1).
