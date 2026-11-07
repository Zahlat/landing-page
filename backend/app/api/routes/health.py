import logging
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.errors import AppError

router = APIRouter(tags=["health"])
logger = logging.getLogger("app.health")


@router.get("/health")
async def health(db: Annotated[AsyncSession, Depends(get_db)]) -> dict[str, str]:
    try:
        await db.execute(text("SELECT 1"))
    except Exception as exc:
        logger.warning("health_db_check_failed type=%s", type(exc).__name__)
        raise AppError(503, "db_unavailable", "Database unavailable.") from exc
    return {"status": "ok"}
