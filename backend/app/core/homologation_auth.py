"""Login temporário de homologação (AUTH_PROVIDER=homologation).

Duas contas fixas, definidas só por variáveis de ambiente (usuário + hash Argon2):
uma VIEWER e uma ADMIN. Cada conta é espelhada numa linha de `User`
(authProvider="HOMOLOGATION"), então o resto do sistema — perfis, permissões
por setor, auditoria — funciona exatamente como com o Keycloak.

Sessão: token aleatório entregue em cookie HttpOnly; no banco (tabela `Session`)
fica apenas o SHA-256 do token. Nada disso se aplica com AUTH_PROVIDER=keycloak.
"""

from __future__ import annotations

import hashlib
import secrets
import time
from collections import deque
from dataclasses import dataclass
from datetime import timedelta

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from fastapi import Request
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.permissions import Role
from app.models.common import utcnow
from app.models.user import Role as UserRole
from app.models.user import Session as UserSession
from app.models.user import User

HOMOLOGATION_AUTH_PROVIDER = "HOMOLOGATION"
INVALID_CREDENTIALS = "Usuário ou senha inválidos."

_hasher = PasswordHasher()
# Hash de referência para gastar o mesmo tempo quando o usuário não existe.
_DUMMY_HASH = _hasher.hash(secrets.token_urlsafe(16))


@dataclass(frozen=True, slots=True)
class HomologationAccount:
    username: str
    name: str
    role: Role
    password_hash: str


def accounts(settings: Settings) -> dict[str, HomologationAccount]:
    """Contas configuradas, indexadas pelo usuário em minúsculas."""
    configured = [
        (
            settings.homologation_viewer_username,
            settings.homologation_viewer_name,
            Role.VIEWER,
            settings.homologation_viewer_password_hash,
        ),
        (
            settings.homologation_admin_username,
            settings.homologation_admin_name,
            Role.ADMIN,
            settings.homologation_admin_password_hash,
        ),
    ]
    result: dict[str, HomologationAccount] = {}
    for username, name, role, password_hash in configured:
        if username and password_hash:
            clean = username.strip()
            result[clean.lower()] = HomologationAccount(
                clean, name, role, password_hash.get_secret_value().strip()
            )
    return result


def verify_credentials(settings: Settings, username: str, password: str) -> HomologationAccount | None:
    """Confere usuário + senha. Sempre executa uma verificação Argon2 (tempo constante)."""
    account = accounts(settings).get(username.strip().lower())
    try:
        _hasher.verify(account.password_hash if account else _DUMMY_HASH, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return None
    return account


# ---------------------------------------------------------------------- limite de tentativas


class LoginRateLimiter:
    """Limite simples em memória (por processo): falhas repetidas geram um intervalo de espera.

    - até `max_failures` falhas por (IP, usuário) dentro de `window`;
    - até `max_ip_failures` falhas por IP (qualquer usuário) dentro de `window`;
    - até `max_user_failures` falhas por usuário (qualquer IP) — protege contra IPs
      trocados/forjados, ao custo de bloquear a conta temporariamente sob ataque;
    - estourado o limite, novas tentativas são recusadas por `lockout`.
    """

    def __init__(
        self,
        *,
        max_failures: int = 5,
        max_ip_failures: int = 20,
        max_user_failures: int = 10,
        window_seconds: float = 15 * 60,
        lockout_seconds: float = 15 * 60,
    ) -> None:
        self.max_failures = max_failures
        self.max_ip_failures = max_ip_failures
        self.max_user_failures = max_user_failures
        self.window = window_seconds
        self.lockout = lockout_seconds
        self._failures: dict[str, deque[float]] = {}
        self._locked_until: dict[str, float] = {}

    @staticmethod
    def _keys(ip: str, username: str) -> tuple[str, str, str]:
        name = username.strip().lower()
        return f"ip:{ip}", f"user:{ip}:{name}", f"name:{name}"

    def retry_after(self, ip: str, username: str) -> int:
        """Segundos até poder tentar de novo (0 = liberado)."""
        now = time.monotonic()
        waits = [
            until - now for key in self._keys(ip, username) if (until := self._locked_until.get(key, 0)) > now
        ]
        return int(max(waits)) + 1 if waits else 0

    def register_failure(self, ip: str, username: str) -> None:
        now = time.monotonic()
        for key, limit in zip(
            self._keys(ip, username),
            (self.max_ip_failures, self.max_failures, self.max_user_failures),
            strict=True,
        ):
            bucket = self._failures.setdefault(key, deque())
            bucket.append(now)
            while bucket and now - bucket[0] > self.window:
                bucket.popleft()
            if len(bucket) >= limit:
                self._locked_until[key] = now + self.lockout
                bucket.clear()

    def register_success(self, ip: str, username: str) -> None:
        _, user_key, _ = self._keys(ip, username)
        self._failures.pop(user_key, None)
        self._locked_until.pop(user_key, None)

    def reset(self) -> None:
        self._failures.clear()
        self._locked_until.clear()


login_rate_limiter = LoginRateLimiter()


def client_ip(request: Request, settings: Settings) -> str:
    if settings.trust_proxy_headers:
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "desconhecido"


# ---------------------------------------------------------------------- usuário e sessão


async def upsert_user(session: AsyncSession, account: HomologationAccount) -> User:
    """Espelha a conta num `User` (perfil e nome sempre vêm da configuração)."""
    user = (
        await session.execute(
            select(User).where(
                User.authProvider == HOMOLOGATION_AUTH_PROVIDER, User.externalUserId == account.username
            )
        )
    ).scalar_one_or_none()
    if user is None:
        user = User(
            name=account.name,
            email=f"{account.username.lower()}@homologacao.hub",
            emailVerified=False,
            role=UserRole(account.role.value),
            active=True,
            authProvider=HOMOLOGATION_AUTH_PROVIDER,
            externalUserId=account.username,
        )
        session.add(user)
    else:
        user.name = account.name
        user.role = UserRole(account.role.value)
    await session.flush()
    return user


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


async def create_session(session: AsyncSession, user: User, request: Request, settings: Settings) -> str:
    """Cria a sessão e devolve o token em claro (só vai para o cookie; no banco fica o hash)."""
    token = secrets.token_urlsafe(32)
    session.add(
        UserSession(
            userId=user.id,
            token=_token_hash(token),
            expiresAt=utcnow() + timedelta(hours=settings.auth_session_hours),
            ipAddress=client_ip(request, settings),
            userAgent=(request.headers.get("user-agent") or "")[:500] or None,
        )
    )
    await session.flush()
    return token


async def user_from_session(session: AsyncSession, token: str) -> User | None:
    """Usuário da sessão válida (não expirada, conta de homologação ativa)."""
    row = (
        await session.execute(
            select(UserSession, User)
            .join(User, User.id == UserSession.userId)
            .where(UserSession.token == _token_hash(token), UserSession.expiresAt > utcnow())
        )
    ).one_or_none()
    if row is None:
        return None
    _, user = row
    if user.authProvider != HOMOLOGATION_AUTH_PROVIDER or not user.active:
        return None
    return user


async def delete_session(session: AsyncSession, token: str) -> None:
    await session.execute(delete(UserSession).where(UserSession.token == _token_hash(token)))


async def delete_expired_sessions(session: AsyncSession) -> None:
    await session.execute(delete(UserSession).where(UserSession.expiresAt <= utcnow()))
