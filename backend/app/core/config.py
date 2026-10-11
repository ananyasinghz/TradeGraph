"""Typed application configuration."""

from functools import lru_cache
from pathlib import Path
from typing import Literal, Self

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables and an optional .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="TRADE_",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = Field(default="TradeGraph API", min_length=1)
    app_version: str = Field(default="0.1.0", pattern=r"^\d+\.\d+\.\d+$")
    environment: Literal["development", "test", "production"] = "development"
    debug: bool = False
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    api_prefix: str = "/api/v1"
    contract_version: Literal["trade.v1"] = "trade.v1"
    database_url: str = "sqlite:///./data/processed/trade.db"
    data_dir: Path = Path("data")
    ollama_enabled: bool = False
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "llama3.2"
    ollama_timeout_seconds: float = Field(default=60.0, gt=0)
    # Prototype scope (see docs/TRADEGRAPH_REFERENCE.md)
    default_origin: str = "BD"
    default_destination: str = "IN"
    prototype_hs_chapter: str = "61"
    orchestration_mode: Literal["adaptive", "direct_lookup", "fixed_multi", "always_llm"] = (
        "adaptive"
    )
    # Demonstration vs operational (PRODUCT_USABILITY_PLAN S1). Operational is forced
    # back to demonstration when no approved published corpus is present.
    product_mode: Literal["demonstration", "operational"] = "demonstration"
    # Phase A/B official source feed controls
    live_feed_enabled: bool = False
    live_feed_max_age_hours: int = Field(default=72, ge=1, le=720)
    source_fetch_interval_minutes: int = Field(default=60, ge=1, le=10080)
    # When true, lifespan starts a background loop that POSTs-equivalent source fetch.
    source_fetch_scheduler_enabled: bool = False
    # Local demo only: allow approve/promote when auth is off (anonymous admin).
    # Ignored / forced false when environment=production or product_mode=operational.
    allow_anonymous_publish: bool = False
    # Comma-separated host suffixes for live HTTP fetches (fail closed if empty/mismatch).
    # Example: "cbic.gov.in,icegate.gov.in,localhost,127.0.0.1"
    # Always include courier.cbic.gov.in — matches seeded cbic_ch61_igst_notif_9_2025.
    http_source_allowlist: str = "localhost,127.0.0.1,example.invalid,courier.cbic.gov.in"
    # Optional live tariff JSON URL (used when connection adapter=live_http_api).
    live_tariff_http_url: str | None = None
    # Official India document URLs (HTML/PDF). Seeded only when set; allowlist required.
    cbic_taxinfo_url: str | None = None
    cbic_customs_url: str | None = None
    icegate_public_url: str | None = None
    # Optional pinned notification/document URL when the portal URL is an index page.
    cbic_taxinfo_document_url: str | None = None
    cbic_customs_document_url: str | None = None
    icegate_public_document_url: str | None = None
    # S12 auth (off by default so local demo/tests stay open; production forces on)
    auth_enabled: bool = False
    # token:actor:role pairs, comma-separated
    auth_tokens: str = (
        "demo-admin:admin:admin,demo-operator:operator:operator,"
        "demo-reviewer:reviewer:reviewer,demo-viewer:viewer:viewer"
    )
    # Firebase Auth (ID token JWKS verify)
    firebase_project_id: str | None = None
    firebase_allowed_emails: str = ""
    bootstrap_admin_emails: str = ""
    # Comma-separated browser origins for CORS (empty → Vite defaults in non-prod)
    cors_origins: str = "http://127.0.0.1:5173,http://localhost:5173"
    # Upload limits
    upload_max_bytes: int = Field(default=10 * 1024 * 1024, ge=1024, le=50 * 1024 * 1024)
    upload_allowed_extensions: str = "pdf,png,jpg,jpeg,txt"
    # ClamAV hook (stub when enabled; default off)
    upload_av_enabled: bool = False
    # Email backend: console (print) or smtp
    email_backend: Literal["console", "smtp"] = "console"
    smtp_host: str | None = None
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from: str = "noreply@tradegraph.local"
    smtp_use_tls: bool = True
    # Optional Slack webhook (org setting may override)
    slack_webhook_url: str | None = None
    # Simple API rate limit (requests per window per IP)
    rate_limit_per_minute: int = Field(default=120, ge=10, le=10000)
    # IF-10 IdP (OIDC) — optional; when set, Bearer JWT subjects map to users.idp_subject
    idp_issuer: str | None = None
    idp_audience: str | None = None
    idp_jwks_url: str | None = None
    default_organization_id: str = "org_demo"

    @field_validator("api_prefix")
    @classmethod
    def validate_api_prefix(cls, value: str) -> str:
        """Require one normalized, non-root API prefix."""
        normalized = value.rstrip("/")
        if not normalized.startswith("/") or normalized == "":
            raise ValueError("api_prefix must start with '/' and cannot be root")
        return normalized

    @model_validator(mode="after")
    def force_auth_in_production(self) -> Self:
        if self.environment == "production" and not self.auth_enabled:
            self.auth_enabled = True
        if self.product_mode == "operational" and not self.auth_enabled:
            self.auth_enabled = True
        if self.environment == "production" or self.product_mode == "operational":
            self.allow_anonymous_publish = False
        return self

@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a process-wide immutable-by-convention settings instance."""
    return Settings()
