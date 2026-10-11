"""Grounded Ollama explanations for Ask (never invent duty rates)."""

from __future__ import annotations

import logging
import re
from typing import Any

import httpx

from backend.app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)


def grounded_explain(
    *,
    query: str,
    tool_facts: str,
    case_context: str | None = None,
    settings: Settings | None = None,
    product_text: str | None = None,
) -> str | None:
    """Short natural-language answer grounded only in provided facts + case context.

    Returns None when Ollama is disabled or the call fails (caller keeps tool text).
    """
    cfg = settings or get_settings()
    if not cfg.ollama_enabled:
        logger.info("ask_llm skipped: ollama_enabled=false")
        return None

    case_block = (case_context or "").strip() or "(no open shipment/case)"
    facts_block = (tool_facts or "").strip() or "(no structured tool facts yet)"
    product_line = (product_text or "").strip()
    product_rule = (
        f"- The case product is exactly: \"{product_line}\". Never substitute a different "
        "product (e.g. do not say linen pants if the case is cotton T-shirts).\n"
        if product_line
        else ""
    )
    prompt = (
        "You are TradeGraph's trade co-pilot. Answer the operator question in 2–5 short "
        "sentences using ONLY the verified facts and case context below.\n"
        "Rules:\n"
        "- Do NOT invent HS codes, duty rates, FTA percentages, or legal citations.\n"
        "- If a number is not in the facts, say it is not available and what to provide next.\n"
        "- If HS is pending/missing, say preferential duty cannot be quoted until HS is confirmed.\n"
        "- If the question is conceptual (e.g. what preferential means), explain in plain "
        "language and tie it to the case/facts when present.\n"
        f"{product_rule}"
        "- Prefer actionable next steps over fluff.\n\n"
        f"Case context:\n{case_block}\n\n"
        f"Verified tool facts:\n{facts_block}\n\n"
        f"Operator question:\n{query.strip()}\n\n"
        "Grounded answer:"
    )
    url = f"{cfg.ollama_base_url.rstrip('/')}/api/generate"
    last_err: str | None = None
    for attempt in range(2):
        try:
            with httpx.Client(timeout=cfg.ollama_timeout_seconds) as client:
                resp = client.post(
                    url,
                    json={
                        "model": cfg.ollama_model,
                        "prompt": prompt,
                        "stream": False,
                        "options": {"temperature": 0.1, "num_predict": 280},
                    },
                )
                resp.raise_for_status()
                text = str(resp.json().get("response") or "").strip()
                if not text:
                    last_err = "empty_response"
                    logger.warning(
                        "ask_llm empty response attempt=%s model=%s",
                        attempt + 1,
                        cfg.ollama_model,
                    )
                    continue
                return _sanitize_product_drift(text, product_line)
        except httpx.TimeoutException as exc:
            last_err = f"timeout:{type(exc).__name__}"
            logger.warning(
                "ask_llm timeout attempt=%s timeout_s=%s: %s",
                attempt + 1,
                cfg.ollama_timeout_seconds,
                exc,
            )
        except httpx.HTTPError as exc:
            last_err = f"http:{type(exc).__name__}"
            logger.warning("ask_llm http error attempt=%s: %s", attempt + 1, exc)
            break
        except Exception as exc:  # noqa: BLE001
            last_err = f"error:{type(exc).__name__}"
            logger.warning("ask_llm failed attempt=%s: %s", attempt + 1, exc)
            break
    logger.info("ask_llm unavailable after retries last_err=%s", last_err)
    return None


_OTHER_PRODUCTS = re.compile(
    r"\b(linen\s+pants|linen\s+trousers|wool\s+coats?|silk\s+dresses?)\b",
    re.IGNORECASE,
)


def _sanitize_product_drift(text: str, product_text: str) -> str:
    """Drop answers that invent a different product than the open case."""
    if not product_text:
        return text
    if _OTHER_PRODUCTS.search(text):
        # Keep only if the invented phrase also appears in the real product text.
        for m in _OTHER_PRODUCTS.finditer(text):
            phrase = m.group(0).lower()
            if phrase not in product_text.lower():
                logger.warning("ask_llm product drift blocked phrase=%s", phrase)
                return (
                    f"For this case (“{product_text}”), confirm the working HS code first, "
                    "then re-ask preferential / FTA. I will not invent a different product."
                )
    return text


def format_case_context(shipment: Any | None, *, extras: dict[str, Any] | None = None) -> str:
    """Compact case summary for the LLM prompt (no secrets)."""
    if shipment is None:
        return ""
    lines = [
        f"shipment_id={getattr(shipment, 'id', '')}",
        f"title={getattr(shipment, 'title', '')}",
        f"product={getattr(shipment, 'product_text', '')}",
        f"corridor={getattr(shipment, 'origin', '')}->{getattr(shipment, 'destination', '')}",
        f"hs_working={getattr(shipment, 'hs_code_working', None) or 'pending'}",
        f"as_of={getattr(shipment, 'as_of_date', '')}",
        f"invoice={getattr(shipment, 'invoice_value', '')} {getattr(shipment, 'currency', '')}",
        f"incoterm={getattr(shipment, 'incoterm', '')}",
        f"regime={getattr(shipment, 'regime', '')}",
        f"status={getattr(shipment, 'status', '')}",
        f"hs_confirmed={'yes' if getattr(shipment, 'hs_confirmed_at', None) else 'no'}",
    ]
    if extras:
        for key, value in extras.items():
            if value is not None and value != "":
                lines.append(f"{key}={value}")
    return "\n".join(lines)


def pending_hs_template(*, product_text: str, query: str) -> str:
    """Deterministic answer when preferential/FTA is asked without a working HS."""
    product = product_text.strip() or "this product"
    q = query.lower()
    if any(k in q for k in ("preferential", "fta", "safta", "duty")):
        return (
            f"Preferential / FTA duty for “{product}” cannot be quoted until a working HS code "
            "is confirmed on the case. Open Classify, confirm an HS (knit cotton T-shirts are "
            "often 6109.10 in this prototype), then ask again or use the Preferential tab."
        )
    return (
        f"Confirm the working HS code for “{product}” first, then re-ask so tools can attach "
        "tariff / FTA evidence."
    )
