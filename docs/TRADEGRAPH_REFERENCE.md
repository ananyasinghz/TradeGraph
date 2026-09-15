# TradeGraph — Master Reference

**Status:** Authoritative project north-star  
**Working title:** Adaptive Knowledge Graph Orchestration for Multi-Agent International Trade Compliance  
**Contract version:** `trade.v1`  
**Last updated:** 2026-09-13 (Phase 0)

Prefer this document over chat history when decisions conflict.

---

## 0. One-sentence mission

TradeGraph is a **local-first, evidence-backed trade compliance workspace** that answers import/export questions by **adaptively choosing the cheapest reliable path** (SQLite lookup → graph → vector retrieval → selective LangGraph agents), never inventing duties or legal conclusions with an LLM.

---

## 1. Product framing (not chatbot-only)

**Primary metaphor:** shipment / enquiry workspace  
**Secondary:** natural-language **Ask** co-pilot that opens, fills, or explains that workspace  

A clearing agent should be able to work **without** free-form chat.

### Core surfaces

| Nav | Purpose | LLM? |
|-----|---------|------|
| Dashboard | Watchlist deltas, recent shipments, incomplete checklists | No |
| Shipments | Case list + workspace detail | Optional assist |
| Tariff browser | Exact HS / rate search | No |
| Calculator | Landed cost (deterministic) | No |
| Agreements | FTA matrix | Light assist later |
| Documents | Checklists / templates | Light assist later |
| Sources | Official doc archive | No |
| Ask | NL co-pilot | Yes (LangGraph) |
| Data / Admin | Versions, seed, approve updates | No |

Home screen: **Dashboard or Shipments — never Ask alone.**

---

## 2. Research gap and novelty

**Not novel alone:** Neo4j, vectors, RAG, LangGraph, tariff websites.

**Defensible novelty:**

> TradeGraph proposes an adaptive, cost-aware orchestration framework for international trade compliance that dynamically selects between deterministic database lookup, knowledge graph traversal, vector retrieval, and multi-agent reasoning based on query requirements, while incorporating versioned regulatory knowledge and evidence verification.

**Central hypothesis:** An adaptive orchestrator that selects the minimum sufficient path can reduce LLM token usage, latency, and unnecessary calls vs fixed multi-agent or always-LLM baselines, while preserving answer accuracy and evidence quality on a defined benchmark.

---

## 3. Locked technical stack

| Layer | Choice |
|-------|--------|
| Backend API | **FastAPI** + Pydantic v2 (Python 3.11) |
| Frontend | **React + TypeScript + Vite** |
| Structured DB | **SQLite** + SQLAlchemy 2 + Alembic (Postgres later) |
| Graph MVP | NetworkX over SQLite → Neo4j optional later |
| Vectors MVP | Chroma / local fallback → Qdrant/pgvector later |
| Orchestration (Ask / complex) | **LangGraph** |
| Form/CRUD paths | Direct Python services (same calculators/repos) — **not** LangGraph every click |
| LLM | Ollama local; templates when off |
| Duty / tax math | **Code only — never LLM** |

**Not using:** Flask, MERN (Mongo/Express/Node), Pinecone (v1), paid APIs required.

---

## 4. Non-negotiable principles

1. Deterministic first — duties, dates, eligibility math are code/DB.
2. LLM at the edge — intent, optional planning, grounded explanation only.
3. Query-aware execution — minimal LangGraph path; no always-run-all-agents.
4. Evidence before explanation — cite verified sources / evidence IDs.
5. Explicit scope — origin, destination, HS, as-of date on tool calls.
6. Graceful degradation — templates/SQL when Ollama is off.
7. Honest evaluation — limited corridor; no fake worldwide coverage.
8. Temporal validity — supersede rates; never silent overwrite.
9. No LLM writes to production tariff data.
10. Disclaimer always visible — decision support, not licensed advice.

---

## 5. Prototype scope lock (Phase 0 default)

| Dimension | Lock |
|-----------|------|
| Corridor | **Bangladesh → India**, apparel focus |
| HS set | Chapter **61** (knit apparel), small verified subset |
| Capabilities (Phase 1) | Tariff browser, shipment workspace, landed-cost calculator, checklist, Ask v1 |
| Brand | **TradeGraph** |
| Primary user | Clearing agent / customs consultant |

Illustrative seed data must be badged `illustrative` vs `demo_verified`. Never present sample rates as current legal determinations.

---

## 6. End-to-end query pipeline (Ask)

```text
User NL query (+ optional shipment_id)
  → Intent extraction (rules + optional LLM)
  → Adaptive router
  → LangGraph path (only needed nodes)
        tools → SQLite / graph / retrieval / calculators
  → Evidence verification
  → Explainable answer + audit (route, tools, sources, tokens)
```

### Routes

| Route | When |
|-------|------|
| `direct_lookup` | Known HS + corridor + single tariff fact |
| `single_tool` | One op (cost, checklist) |
| `graph_vector` | Relationship / regulatory text |
| `multi_agent` | Multi-intent / ambiguous classification |

### Intent schema (illustrative)

```json
{
  "intent": ["tariff_lookup", "fta_eligibility", "document_requirements"],
  "product": "cotton T-shirt",
  "origin": "Bangladesh",
  "destination": "India",
  "date": null,
  "hs_code": null,
  "complexity": "multi_step",
  "confidence": 0.0,
  "ambiguities": [],
  "missing_fields": []
}
```

---

## 7. Knowledge model

- **Authoritative rates:** SQLite `tariff_rates` with effective windows and supersession.
- **Graph:** Product → HS → Tariff → CountryPair → Agreement → Certificate (NetworkX MVP).
- **Vectors:** notification / RoO excerpts with metadata — never override structured rates.

---

## 8. Regulatory update pipeline (later phases)

Official sources → fetch/archive → extract → validate → human approve → versioned publish → update SQLite + graph + vectors.

---

## 9. Evaluation baselines

Traditional lookup | Standard RAG | GraphRAG | Fixed multi-agent | **TradeGraph adaptive**

Metrics: accuracy, evidence quality, latency, LLM calls, tokens, routing accuracy, unnecessary escalation rate.

---

## 10. Fraud-platform reuse (historical)

This repo was evolved from an AML fraud detection platform. Phase 0 **removed** fraud ML, alerts, customers/transactions product surfaces. Useful patterns to restore/adapt in Phase 1+ from git history:

- NLU + deterministic router + date normalizer
- Tool registry / envelope / evidence verify
- Execution tracing
- Investigate-style Ask UX

Replace orchestration executor with **LangGraph** (explicit project choice).

---

## 11. Document hierarchy

| Doc | Role |
|------|------|
| **This file** | Always-on north star |
| `docs/IMPLEMENTATION_PLAN.md` | Phased build + delete map |
| Future ARCHITECTURE / CONTRACTS / EVALUATION | Implementation detail |
| Chat history | Ephemeral |

---

## Disclaimer text (ship in UI)

> TradeGraph is a decision-support prototype. Classifications, duties, and preferential claims require verification against official sources and, where appropriate, a licensed customs professional. Illustrative or demo data is not a legal determination.
