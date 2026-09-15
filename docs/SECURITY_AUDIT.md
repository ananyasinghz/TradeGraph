# TradeGraph Security Audit

**Date:** 2026-09-15  
**Scope:** FastAPI + React TradeGraph clearance portal  
**Status:** Findings inventory + remediation map (Firebase Auth program)

## Summary

TradeGraph was built as a local-first demo. Auth exists but is **off by default**, most APIs are open, and the SPA has no login. This document catalogs issues and maps them to remediation phases.

---

## Critical / High

| ID | Finding | Location | Exploit scenario | Remediation |
|----|---------|----------|------------------|-------------|
| H1 | Auth off by default; anonymous principal is **admin** | `backend/app/services/auth_service.py` `resolve_principal` | Anyone who can reach the API acts as admin | Phase 2–3: never anonymous admin when auth on; production forces auth |
| H2 | Most APIs unprotected when auth is on | `backend/app/api/routes/*` (shipments, ask, tariffs, ingest run, eval, …) | Authenticated low-privilege or unauthenticated callers mutate clearance data | Phase 3: RBAC matrix on all portal routes |
| H3 | No login UI; SPA never sends Bearer | `frontend/src/services/api.ts` | Even with backend auth on, UI cannot operate securely | Phase 4: Firebase login + Bearer |
| H4 | UX role in `localStorage` is not security | `WelcomePanel.tsx`, `operatorCopy.ts` | User “picks” clearing agent / student; no server check | Phase 4: server whoami for RBAC; persona = UX only |
| H5 | Uploads: no auth, no size/MIME limits | `shipments.py` upload, `document_service` | Unauthenticated large/malicious file upload | Phase 3 + 5: auth + size/type allowlist |
| H6 | Audit write unused | `write_audit` / `audit_from_request` never called from mutators | No forensic trail for HS confirm / approve / upload | Phase 3: wire audit on mutations |
| H7 | Org tenancy incomplete | Scenarios scoped; shipments/watchlist mostly global | Cross-tenant case access | Phase 3: org filter on shipments/impacts/watchlist |

## Medium

| ID | Finding | Location | Remediation |
|----|---------|----------|-------------|
| M1 | Hardcoded CORS (Vite only) | `backend/app/main.py` | Phase 5: `TRADE_CORS_ORIGINS` |
| M2 | No API rate limits | FastAPI routes | Phase 5: in-memory limiter on Ask/upload/ingest |
| M3 | No security headers | Middleware stack | Phase 5: CSP, XFO, XCTO, Referrer-Policy, HSTS in prod |
| M4 | Demo Bearer tokens if public + `environment=development` | `auth_service` | Phase 2: demo tokens only in development/test; document |
| M5 | Eval / Research CPU burn | `/eval/*` | Phase 3: admin role |
| M6 | Upload artifacts may be committed | `data/uploads/` | Phase 5: gitignore + verify |

## Lower / informational

| ID | Finding | Notes |
|----|---------|-------|
| L1 | FTS raw SQL | Parameterized + token sanitize — low risk |
| L2 | HTTP source allowlist | Fail-closed — keep |
| L3 | No malware scanning for CoO PDFs | Follow-up; size/type gates in Phase 5 |

## Relative strengths

- JWKS validation shape for generic OIDC is reasonable.
- Demo tokens gated to non-production environments.
- `.env` gitignored; illustrative rates honesty banners.
- Scenario org isolation already tested (IF-12).

## Remediation status

| Phase | Outcome | Status |
|-------|---------|--------|
| 0 | This audit | Done |
| 1 | Firebase config contract | In progress |
| 2 | Firebase ID-token verify + user upsert | Pending |
| 3 | RBAC lockdown + org + audit | Pending |
| 4 | Login UI + Bearer | Pending |
| 5 | Headers, CORS, rate limit, uploads | Pending |
| 6 | Tests + docs | Pending |
