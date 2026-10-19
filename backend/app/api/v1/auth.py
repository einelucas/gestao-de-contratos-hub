"""Rotas de autenticação.

- GET  /auth/provider — modo ativo (público): o login decide qual tela mostrar.
- GET  /auth/me       — identidade do usuário autenticado (qualquer modo).
- POST /auth/login    — só no modo `homologation`: usuário + senha → cookie de sessão HttpOnly.
- POST /auth/logout   — só no modo `homologation`: invalida a sessão e apaga o cookie.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, get_current_user
from app.core.config import Settings, get_settings
from app.core.database import get_session
from app.core.errors import DomainError, NotFoundError, UnauthorizedError
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
from app.core.local_auth import (
    DEFAULT_LOCAL_PASSWORD,
    LOCAL_AUTH_PROVIDER,
    change_local_password,
    verify_local_credentials,
)
from app.core.logging import get_logger
from app.core.permissions import Role as PermissionRole
from app.core.permissions import permissions_for
from app.models.user import User
from app.shared.audit import record_audit
from app.shared.schema import CamelModel

router = APIRouter(prefix="/auth", tags=["auth"])
logger = get_logger("app.auth")


class LoginIn(CamelModel):
    username: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=1, max_length=256)


class ChangePasswordIn(CamelModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def _strong_new_password(cls, value: str) -> str:
        if value == DEFAULT_LOCAL_PASSWORD:
            raise ValueError("A nova senha deve ser diferente da senha inicial")
        if not any(character.islower() for character in value):
            raise ValueError("A nova senha deve conter uma letra minúscula")
        if not any(character.isupper() for character in value):
            raise ValueError("A nova senha deve conter uma letra maiúscula")
        if not any(character.isdigit() for character in value):
            raise ValueError("A nova senha deve conter um número")
        if not any(not character.isalnum() for character in value):
            raise ValueError("A nova senha deve conter um caractere especial")
        return value


def _me(user: CurrentUser) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "username": user.username,
        "role": user.role.value,
        "active": user.active,
        "passwordChangeRequired": user.password_change_required,
        "permissions": [p.value for p in permissions_for(user.role)],
    }


def _require_homologation(settings: Settings) -> None:
    if settings.auth_provider != "homologation":
        raise NotFoundError("Recurso não encontrado")


@router.get("/provider")
async def provider(settings: Settings = Depends(get_settings)) -> dict:
    return {"provider": settings.auth_provider}


@router.get("/me")
async def me(current_user: CurrentUser = Depends(get_current_user)) -> dict:
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
    local_user = (
        None
        if account is not None
        else await verify_local_credentials(session, body.username, body.password)
    )
    if account is None and local_user is None:
        login_rate_limiter.register_failure(ip, body.username)
        # Nunca registra a senha; o usuário digitado ajuda a investigar tentativas.
        logger.warning("auth.login_failed", ip=ip, username=body.username[:120])
        return JSONResponse(status_code=status.HTTP_401_UNAUTHORIZED, content={"error": INVALID_CREDENTIALS})

    login_rate_limiter.register_success(ip, body.username)
    if local_user is not None:
        user = local_user
        role = PermissionRole(user.role.value)
    else:
        assert account is not None
        user = await upsert_user(session, account)
        role = account.role
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
    logger.info("auth.login_succeeded", user_id=user.id, role=role.value, ip=ip)

    current = CurrentUser(
        id=user.id,
        email=user.email,
        name=user.name,
        role=role,
        active=user.active,
        password_change_required=user.passwordChangeRequired,
        username=account.username if account is not None else user.email,
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


@router.post("/change-password")
async def change_password(
    body: ChangePasswordIn,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> dict:
    user = await session.get(User, current_user.id)
    if user is None or user.authProvider != LOCAL_AUTH_PROVIDER:
        raise DomainError("A senha desta conta é gerenciada pelo provedor de identidade")
    changed = await change_local_password(
        session,
        user=user,
        current_password=body.current_password,
        new_password=body.new_password,
    )
    if not changed:
        raise UnauthorizedError("Senha atual incorreta")
    await record_audit(
        session,
        user_id=user.id,
        action="auth.password_change",
        entity="User",
        entity_id=user.id,
        metadata={"provider": LOCAL_AUTH_PROVIDER},
    )
    await session.commit()
    logger.info("auth.password_changed", user_id=user.id)
    return _me(
        CurrentUser(
            id=user.id,
            email=user.email,
            name=user.name,
            role=current_user.role,
            active=user.active,
            password_change_required=False,
            username=user.email,
        )
    )


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
