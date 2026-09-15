# TradeGraph frontend

React 19 + TypeScript + Vite 8 shell for the TradeGraph compliance workspace.

Phase 0: navigation placeholders + API health badge.  
Phase 1: Shipments, Tariff browser, Calculator, Ask (LangGraph-backed).

```powershell
npm install
npm run dev
```

Proxies `/api` to FastAPI on `:8000` (see `vite.config.ts`).
