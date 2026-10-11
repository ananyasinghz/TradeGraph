"""Shared test DB helpers for Phase 1."""

from __future__ import annotations

from pathlib import Path
from sqlite3 import Connection as SQLiteConnection

from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.core.config import Settings
from backend.app.data.models import Base
from backend.app.data.seeding import load_catalog, seed
from backend.app.main import create_app

ROOT = Path(__file__).resolve().parents[3]
CATALOG = ROOT / "config" / "trade" / "demo" / "seed_catalog.v1.yaml"


def make_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "environment": "test",
        "app_name": "Test TradeGraph API",
        "database_url": "sqlite:///:memory:",
        # Isolate from developer .env live-feed flags
        "live_feed_enabled": False,
        "source_fetch_scheduler_enabled": False,
        "auth_enabled": False,
        # Tests exercise publish paths without Bearer tokens unless overridden.
        "allow_anonymous_publish": True,
        "ollama_enabled": False,
    }
    values.update(overrides)
    return Settings.model_validate(values)


def make_seeded_engine() -> tuple[Engine, sessionmaker[Session]]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def enable_sqlite_foreign_keys(dbapi_connection: object, connection_record: object) -> None:
        del connection_record
        if isinstance(dbapi_connection, SQLiteConnection):
            cursor = dbapi_connection.cursor()
            try:
                cursor.execute("PRAGMA foreign_keys=ON")
            finally:
                cursor.close()

    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    catalog = load_catalog(CATALOG)
    with factory() as session:
        seed(session, catalog, force=True)
        from backend.app.services.corridor_service import ensure_default_corridors

        ensure_default_corridors(session)
        from backend.app.services.org_service import ensure_demo_org

        ensure_demo_org(session)
        from backend.app.services import hs_catalog_service

        hs_catalog_service.load_min_fixture(session)
        session.commit()
    return engine, factory


def make_client(**overrides: object) -> TestClient:
    settings = make_settings(**overrides)
    app = create_app(settings)
    engine, factory = make_seeded_engine()
    app.state.engine = engine
    app.state.session_factory = factory
    return TestClient(app)
