from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, Depends, FastAPI

from app.api.deps import require_internal_token
from app.api.routes import health, messages
from app.core.body_limit import BodySizeLimitMiddleware
from app.core.config import Settings, get_settings
from app.core.db import make_engine, make_sessionmaker
from app.core.errors import register_error_handlers
from app.core.logging import configure_logging


def build_v1_router() -> APIRouter:
    """Every route under /v1 inherits the internal-token check from this router."""
    router = APIRouter(prefix="/v1", dependencies=[Depends(require_internal_token)])
    router.include_router(messages.router)
    return router


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = make_engine(settings.database_url)
        app.state.engine = engine
        app.state.sessionmaker = make_sessionmaker(engine)
        try:
            yield
        finally:
            await engine.dispose()

    docs_enabled = not settings.is_prod
    app = FastAPI(
        title="Meraki backend",
        lifespan=lifespan,
        docs_url="/docs" if docs_enabled else None,
        redoc_url="/redoc" if docs_enabled else None,
        openapi_url="/openapi.json" if docs_enabled else None,
    )
    app.state.settings = settings

    # Outermost: rejects oversized bodies before routing or JSON parsing.
    app.add_middleware(BodySizeLimitMiddleware)
    register_error_handlers(app)
    app.include_router(health.router)
    app.include_router(build_v1_router())
    return app


app = create_app()
