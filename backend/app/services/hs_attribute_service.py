"""Optional Ollama attribute extraction for HS ranking (edge only — never duties)."""

from __future__ import annotations

import json
import re
from typing import Any

import httpx

from backend.app.core.config import Settings, get_settings
from backend.app.services.hs_attributes import ProductAttributes, extract_attributes_rules


def extract_product_attributes(
    product_text: str,
    *,
    settings: Settings | None = None,
    allow_ollama: bool = False,
) -> ProductAttributes:
    """Rules first; optionally enrich via Ollama when enabled and opted in.

    Hot paths (dashboard / readiness / workspace) must pass allow_ollama=False
    so TRADE_OLLAMA_ENABLED does not add multi-second LLM latency per shipment.
    """
    base = extract_attributes_rules(product_text)
    cfg = settings or get_settings()
    if not (allow_ollama and cfg.ollama_enabled):
        return base
    try:
        llm = _ollama_attributes(product_text, cfg)
    except Exception:
        return base
    if not llm:
        return base
    return ProductAttributes(
        material=llm.get("material") or base.material,
        construction=llm.get("construction") or base.construction,
        garment_type=llm.get("garment_type") or base.garment_type,
        gender=llm.get("gender") or base.gender,
    )


def _ollama_attributes(product_text: str, cfg: Settings) -> dict[str, Any] | None:
    prompt = (
        "Extract trade product attributes as JSON with keys "
        "material, construction (knit|woven|unknown), garment_type, gender. "
        "Do not invent HS codes or duty rates. Product: "
        f"{product_text}"
    )
    url = f"{cfg.ollama_base_url.rstrip('/')}/api/generate"
    with httpx.Client(timeout=cfg.ollama_timeout_seconds) as client:
        resp = client.post(
            url,
            json={"model": cfg.ollama_model, "prompt": prompt, "stream": False, "format": "json"},
        )
        resp.raise_for_status()
        raw = resp.json().get("response") or ""
    return _parse_json_blob(str(raw))


def _parse_json_blob(raw: str) -> dict[str, Any] | None:
    raw = raw.strip()
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        m = re.search(r"\{[^{}]+\}", raw)
        if not m:
            return None
        try:
            data = json.loads(m.group(0))
            return data if isinstance(data, dict) else None
        except json.JSONDecodeError:
            return None


def explain_candidates_grounded(
    product_text: str,
    candidates: list[dict[str, Any]],
    *,
    settings: Settings | None = None,
) -> str | None:
    """Optional grounded paraphrase — must only mention provided candidate codes."""
    cfg = settings or get_settings()
    if not cfg.ollama_enabled or not candidates:
        return None
    codes = ", ".join(str(c.get("hs_code")) for c in candidates[:5])
    prompt = (
        f"In 2 short sentences, explain why these HS candidates ({codes}) may fit "
        f"the product '{product_text}'. Only refer to the listed codes. "
        "Do not invent duties or additional HS codes."
    )
    url = f"{cfg.ollama_base_url.rstrip('/')}/api/generate"
    try:
        with httpx.Client(timeout=cfg.ollama_timeout_seconds) as client:
            resp = client.post(
                url,
                json={"model": cfg.ollama_model, "prompt": prompt, "stream": False},
            )
            resp.raise_for_status()
            text = str(resp.json().get("response") or "").strip()
            return text or None
    except Exception:
        return None
