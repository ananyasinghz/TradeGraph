"""FastAPI application factory."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.routes.agreements import router as agreements_router
from backend.app.api.routes.ask import router as ask_router
from backend.app.api.routes.auth import router as auth_router
from backend.app.api.routes.calculate import router as calculate_router
from backend.app.api.routes.calculations import router as calculations_router
from backend.app.api.routes.classification import router as classification_router
from backend.app.api.routes.corridors import router as corridors_router
from backend.app.api.routes.dashboard import router as dashboard_router
from backend.app.api.routes.documents import router as documents_router
from backend.app.api.routes.eval import router as eval_router
from backend.app.api.routes.health import router as health_router
from backend.app.api.routes.impacts import router as impacts_router
from backend.app.api.routes.ingest import router as ingest_router
from backend.app.api.routes.jobs import router as jobs_router
from backend.app.api.routes.retrieval import router as retrieval_router
from backend.app.api.routes.scenarios import router as scenarios_router
from backend.app.api.routes.shipments import router as shipments_router
from backend.app.api.routes.source_connections import router as source_connections_router
from backend.app.api.routes.sources import router as sources_router
from backend.app.api.routes.system import router as system_router
from backend.app.api.routes.tariffs import router as tariffs_router
from backend.app.api.routes.watchlist import router as watchlist_router
from backend.app.core.config import Settings, get_settings
from backend.app.core.errors import register_exception_handlers
from backend.app.core.lifespan import app_lifespan
from backend.app.core.logging import configure_logging
from backend.app.core.rate_limit_middleware import RateLimitMiddleware
from backend.app.core.request_id import RequestIdMiddleware
from backend.app.core.security_headers import SecurityHeadersMiddleware
from backend.app.data.database import engine_from_settings, session_factory

_DEFAULT_CORS = (
    "http://127.0.0.1:5173",
    "http://localhost:5173",
)


def _cors_origins(settings: Settings) -> list[str]:
    raw = (settings.cors_origins or "").strip()
    if not raw:
        if settings.environment == "production":
            return []
        return list(_DEFAULT_CORS)
    return [o.strip() for o in raw.split(",") if o.strip()]


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build an isolated app instance for runtime or tests."""
    resolved = settings or get_settings()
    configure_logging(resolved.log_level)

    application = FastAPI(
        title=resolved.app_name,
        version=resolved.app_version,
        debug=resolved.debug,
        lifespan=app_lifespan,
    )
    application.state.settings = resolved
    application.state.engine = engine_from_settings(resolved)
    application.state.session_factory = session_factory(application.state.engine)
    origins = _cors_origins(resolved)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=origins or list(_DEFAULT_CORS),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Organization-Id", "X-Request-ID"],
    )
    application.add_middleware(SecurityHeadersMiddleware, settings=resolved)
    application.add_middleware(RateLimitMiddleware, settings=resolved)
    application.add_middleware(RequestIdMiddleware)
    register_exception_handlers(application)

    prefix = resolved.api_prefix
    application.include_router(health_router, prefix=prefix)
    application.include_router(system_router, prefix=prefix)
    application.include_router(corridors_router, prefix=prefix)
    application.include_router(auth_router, prefix=prefix)
    application.include_router(dashboard_router, prefix=prefix)
    application.include_router(tariffs_router, prefix=prefix)
    application.include_router(calculate_router, prefix=prefix)
    application.include_router(calculations_router, prefix=prefix)
    application.include_router(shipments_router, prefix=prefix)
    application.include_router(scenarios_router, prefix=prefix)
    application.include_router(impacts_router, prefix=prefix)
    application.include_router(classification_router, prefix=prefix)
    application.include_router(ask_router, prefix=prefix)
    application.include_router(sources_router, prefix=prefix)
    application.include_router(source_connections_router, prefix=prefix)
    application.include_router(documents_router, prefix=prefix)
    application.include_router(agreements_router, prefix=prefix)
    application.include_router(retrieval_router, prefix=prefix)
    application.include_router(watchlist_router, prefix=prefix)
    application.include_router(jobs_router, prefix=prefix)
    application.include_router(eval_router, prefix=prefix)
    application.include_router(ingest_router, prefix=prefix)
    return application


app = create_app()
