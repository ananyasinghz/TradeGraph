# Phase 3 changelog

**Date:** 2026-09-13

## Delivered

- Complexity estimator (`orchestration/complexity.py`) + adaptive policy (`orchestration/policy.py`)
- Orchestration modes: `adaptive` | `direct_lookup` | `fixed_multi` | `always_llm`
- Ask graph rewritten: `parse_and_plan` → multi-tool `run_tools` → `verify` with nested results + metrics
- Settings: `TRADE_ORCHESTRATION_MODE` (default `adaptive`)
- Benchmark fixture `config/evaluation/benchmark.v1.json` + `POST /api/v1/eval/run`
- CLI: `python scripts/run_benchmark.py --ensure-seed`
- Ask UI: mode selector + complexity / tools / tokens / evidence metrics

## Baseline semantics

| Mode | Behavior |
|------|----------|
| `adaptive` | Min tools from complexity + intents |
| `direct_lookup` | Always `tariff_lookup` only |
| `fixed_multi` | Always full tool fan-out |
| `always_llm` | Full fan-out + `llm_explain` proxy (inflated tokens); **duty numbers stay deterministic** |

## Run

```powershell
python -m pip install -e ".[dev]"
alembic upgrade head
python scripts/seed_trade_data.py --create-schema --force
python scripts/run_benchmark.py --ensure-seed
uvicorn backend.app.main:app --reload --port 8000
```

## Exit criteria

1. Adaptive uses fewer tools/tokens than `fixed_multi` on simple tariff queries  
2. Duty rates remain correct under all modes (no LLM inventing numbers)  
3. `/eval/run` returns comparable mode summaries (accuracy, latency, tokens, tool_count)  
