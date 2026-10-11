"""Unit tests for grounded Ask Ollama explanations."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from backend.app.core.config import Settings
from backend.app.orchestration.complexity import is_conceptual_query
from backend.app.services import ask_llm_service


def test_is_conceptual_preferential() -> None:
    assert is_conceptual_query("what is preferential??")
    assert is_conceptual_query("Explain FTA eligibility")
    assert not is_conceptual_query("Calculate landed cost for HS 6109.10")


def test_grounded_explain_disabled() -> None:
    settings = Settings.model_validate(
        {"environment": "test", "ollama_enabled": False, "app_name": "t"}
    )
    assert (
        ask_llm_service.grounded_explain(
            query="what is preferential?",
            tool_facts="FTA check needs HS",
            settings=settings,
        )
        is None
    )


def test_grounded_explain_calls_ollama() -> None:
    settings = Settings.model_validate(
        {
            "environment": "test",
            "ollama_enabled": True,
            "ollama_base_url": "http://127.0.0.1:11434",
            "ollama_model": "llama3.2",
            "app_name": "t",
        }
    )
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {
        "response": "Preferential duty is a lower FTA rate when origin rules are met."
    }
    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.__exit__.return_value = False
    mock_client.post.return_value = mock_resp

    with patch("backend.app.services.ask_llm_service.httpx.Client", return_value=mock_client):
        text = ask_llm_service.grounded_explain(
            query="what is preferential?",
            tool_facts="No HS provided for FTA check.",
            case_context="title=Demo cotton tees\nhs_working=6109.10",
            settings=settings,
        )
    assert text is not None
    assert "Preferential" in text
    assert mock_client.post.called
    body = mock_client.post.call_args.kwargs["json"]
    assert "Do NOT invent" in body["prompt"]
    assert "6109.10" in body["prompt"]


def test_pending_hs_template() -> None:
    text = ask_llm_service.pending_hs_template(
        product_text="Cotton T-shirts",
        query="what is the preferential for my case?",
    )
    assert "6109.10" in text or "HS" in text
    assert "Cotton T-shirts" in text


def test_sanitize_product_drift() -> None:
    out = ask_llm_service._sanitize_product_drift(
        "We need the HS for 100% linen pants before FTA.",
        "Cotton T-shirts",
    )
    assert "linen pants" not in out.lower()
    assert "Cotton T-shirts" in out


def test_format_case_context() -> None:
    ship = MagicMock()
    ship.id = "abc"
    ship.title = "Tees"
    ship.product_text = "cotton t-shirts"
    ship.origin = "BD"
    ship.destination = "IN"
    ship.hs_code_working = "6109.10"
    ship.as_of_date = "2026-06-01"
    ship.invoice_value = "1000"
    ship.currency = "USD"
    ship.incoterm = "CIF"
    ship.regime = "mfn"
    ship.status = "open"
    ship.hs_confirmed_at = None
    text = ask_llm_service.format_case_context(ship, extras={"gaps": "COO missing"})
    assert "hs_working=6109.10" in text
    assert "gaps=COO missing" in text
