"""SQLite engine helper tests."""

from sqlalchemy import text

from backend.app.data.database import create_database_engine, session_factory, session_scope


def test_sqlite_memory_engine_enables_foreign_keys() -> None:
    engine = create_database_engine("sqlite:///:memory:")
    factory = session_factory(engine)
    with session_scope(factory) as session:
        enabled = session.execute(text("PRAGMA foreign_keys")).scalar_one()
        assert enabled == 1
