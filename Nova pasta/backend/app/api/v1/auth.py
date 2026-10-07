"""Rotas de autenticação.

- GET  /auth/provider — modo ativo (público): o login decide qual tela mostrar.
- GET  /auth/me       — identidade do usuário autenticado (qualquer modo).
- POST /auth/login    — só no modo `homologation`: usuário + senha → cookie de sessão HttpOnly.
- POST /auth/logout   — só no modo `homologation`: invalida a sessão e apaga o cookie.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, require_user
from app.core.config import Settings, get_settings
from app.core.database import get_session
from app.core.errors import NotFoundError
from app.core.homologation_auth import (
    INVALID_CREDENTIALS,
    client_ip,
    create_session,
    delete_expired_sessions,
    delete_session,
    login_rate_limiter,
    upsert_user,
    verify_credentials,
)
from app.core.logging import get_logger
from app.core.permissions import permissions_for
from app.shared.audit import record_audit
from app.shared.schema import CamelModel

router = APIRouter(prefix="/auth", tags=["auth"])
logger = get_logger("app.auth")


class LoginIn(CamelModel):
    username: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=1, max_length=256)


def _me(user: CurrentUser) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "username": user.username,
        "role": user.role.value,
        "active": user.active,
        "permissions": [p.value for p in permissions_for(user.role)],
    }


def _require_homologation(settings: Settings) -> None:
    if settings.auth_provider != "homologation":
        raise NotFoundError("Recurso não encontrado")


@router.get("/provider")
async def provider(settings: Settings = Depends(get_settings)) -> dict:
    return {"provider": settings.auth_provider}


@router.get("/me")
async def me(current_user: CurrentUser = Depends(require_user)) -> dict:
    return _me(current_user)


@router.post("/login")
async def login(
    body: LoginIn,
    request: Request,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> Response:
    _require_homologation(settings)
    ip = client_ip(request, settings)
    wait = login_rate_limiter.retry_after(ip, body.username)
    if wait:
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={"error": "Muitas tentativas. Aguarde alguns minutos e tente novamente."},
            headers={"Retry-After": str(wait)},
        )

    account = verify_credentials(settings, body.username, body.password)
    if account is None:
        login_rate_limiter.register_failure(ip, body.username)
        # Nunca registra a senha; o usuário digitado ajuda a investigar tentativas.
        logger.warning("auth.login_failed", ip=ip, username=body.username[:120])
        return JSONResponse(status_code=status.HTTP_401_UNAUTHORIZED, content={"error": INVALID_CREDENTIALS})

    login_rate_limiter.register_success(ip, body.username)
    user = await upsert_user(session, account)
    token = await create_session(session, user, request, settings)
    await record_audit(
        session,
        user_id=user.id,
        action="auth.login",
        entity="User",
        entity_id=user.id,
        metadata={"provider": "homologation", "ip": ip},
    )
    await session.commit()
    logger.info("auth.login_succeeded", user_id=user.id, role=account.role.value, ip=ip)

    current = CurrentUser(
        id=user.id,
        email=user.email,
        name=user.name,
        role=account.role,
        active=user.active,
        username=account.username,
    )
    response = JSONResponse(content=_me(current))
    response.set_cookie(
        key=settings.auth_cookie_name,
        value=token,
        max_age=settings.auth_session_hours * 3600,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite=settings.auth_cookie_samesite,
        path="/",
    )
    return response


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> Response:
    _require_homologation(settings)
    token = request.cookies.get(settings.auth_cookie_name)
    if token:
        await delete_session(session, token)
    # Limpeza das sessões vencidas fica no logout (não atrasa quem está entrando).
    await delete_expired_sessions(session)
    await session.commit()
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie(
        key=settings.auth_cookie_name,
        path="/",
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite=settings.auth_cookie_samesite,
    )
    return response
