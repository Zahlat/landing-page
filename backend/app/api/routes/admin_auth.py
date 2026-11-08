from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import client_info, current_admin, get_db, get_settings_dep
from app.core.config import Settings
from app.schemas.admin import AdminMe, LoginRequest, LoginResponse
from app.services.auth_service import AdminContext, AuthService
from app.services.message_service import ClientInfo

router = APIRouter(prefix="/admin", tags=["admin-auth"])


@router.post("/auth/login", response_model=LoginResponse)
async def login(
    body: LoginRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
    client: Annotated[ClientInfo, Depends(client_info)],
) -> LoginResponse:
    result = await AuthService(db, settings).login(body.email, body.password, client.ip)
    return LoginResponse(token=result.token, expires_at=result.expires_at)


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    ctx: Annotated[AdminContext, Depends(current_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
) -> Response:
    await AuthService(db, settings).logout(ctx)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=AdminMe)
async def me(ctx: Annotated[AdminContext, Depends(current_admin)]) -> AdminMe:
    return AdminMe(email=ctx.user.email)
