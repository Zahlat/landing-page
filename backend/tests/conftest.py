"""Test fixtures.

- Runs against real Postgres (TEST_DATABASE_URL), never SQLite.
- Migrations are applied once per run with `alembic upgrade head`.
- Each test runs inside a transaction that is rolled back afterwards; code under
  test that calls commit() only releases a SAVEPOINT.
"""

from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.core.config import Settings
from app.core.db import get_db, make_engine
from app.main import create_app

BACKEND_DIR = Path(__file__).resolve().parent.parent


def _load_test_settings() -> Settings:
    base = Settings()
    test_url = base.test_database_url
    if not test_url:
        raise pytest.UsageError("TEST_DATABASE_URL is not set; refusing to run tests.")
    if test_url == base.database_url:
        raise pytest.UsageError("TEST_DATABASE_URL must differ from DATABASE_URL.")
    db_name = make_url(test_url).database or ""
    if not db_name.endswith("_test"):
        raise pytest.UsageError(
            f"Test database name must end in '_test' (got {db_name!r}); refusing to run."
        )
    return base.model_copy(update={"environment": "test", "database_url": test_url})


TEST_SETTINGS = _load_test_settings()
INTERNAL_HEADERS = {"X-Internal-Token": TEST_SETTINGS.internal_token.get_secret_value()}


@pytest.fixture(scope="session")
def test_settings() -> Settings:
    return TEST_SETTINGS


@pytest.fixture(scope="session")
def internal_headers() -> dict[str, str]:
    return dict(INTERNAL_HEADERS)


@pytest.fixture(scope="session", autouse=True)
def _migrate_test_db() -> Iterator[None]:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    # configparser treats % as interpolation; escape it in passwords.
    cfg.set_main_option("sqlalchemy.url", TEST_SETTINGS.database_url.replace("%", "%%"))
    cfg.attributes["configure_logger"] = False
    command.upgrade(cfg, "head")
    yield


@pytest.fixture(scope="session")
async def engine() -> AsyncIterator[AsyncEngine]:
    eng = make_engine(TEST_SETTINGS.database_url)
    yield eng
    await eng.dispose()


@pytest.fixture
async def db_session(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    async with engine.connect() as conn:
        trans = await conn.begin()
        session = AsyncSession(
            bind=conn, join_transaction_mode="create_savepoint", expire_on_commit=False
        )
        try:
            yield session
        finally:
            await session.close()
            await trans.rollback()


@pytest.fixture
def app(db_session: AsyncSession) -> FastAPI:
    application = create_app(TEST_SETTINGS)

    async def _get_test_db() -> AsyncIterator[AsyncSession]:
        yield db_session

    application.dependency_overrides[get_db] = _get_test_db
    return application


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
