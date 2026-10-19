"""Autenticação das contas locais criadas pela administração do Hub."""

from __future__ import annotations

import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import Account, User

LOCAL_AUTH_PROVIDER = "LOCAL"
LOCAL_ACCOUNT_PROVIDER = "credential"
DEFAULT_LOCAL_PASSWORD = "INP@2026"

_hasher = PasswordHasher()
_DUMMY_HASH = _hasher.hash(secrets.token_urlsafe(16))


def normalize_login(value: str) -> str:
    return value.strip().lower()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def _matches(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


async def create_local_account(session: AsyncSession, user: User) -> Account:
    account = Account(
        userId=user.id,
        accountId=normalize_login(user.email),
        providerId=LOCAL_ACCOUNT_PROVIDER,
        password=hash_password(DEFAULT_LOCAL_PASSWORD),
    )
    session.add(account)
    await session.flush()
    return account


async def verify_local_credentials(
    session: AsyncSession, username: str, password: str
) -> User | None:
    row = (
        await session.execute(
            select(Account, User)
            .join(User, User.id == Account.userId)
            .where(
                Account.providerId == LOCAL_ACCOUNT_PROVIDER,
                Account.accountId == normalize_login(username),
            )
        )
    ).one_or_none()
    account, user = row if row is not None else (None, None)
    password_hash = account.password if account is not None and account.password else _DUMMY_HASH
    if not _matches(password_hash, password) or account is None or user is None or not user.active:
        return None
    if user.authProvider != LOCAL_AUTH_PROVIDER:
        return None
    if _hasher.check_needs_rehash(password_hash):
        account.password = hash_password(password)
        await session.flush()
    return user


async def change_local_password(
    session: AsyncSession,
    *,
    user: User,
    current_password: str,
    new_password: str,
) -> bool:
    account = (
        await session.execute(
            select(Account).where(
                Account.userId == user.id,
                Account.providerId == LOCAL_ACCOUNT_PROVIDER,
            )
        )
    ).scalar_one_or_none()
    password_hash = account.password if account is not None and account.password else _DUMMY_HASH
    if account is None or user.authProvider != LOCAL_AUTH_PROVIDER:
        _matches(password_hash, current_password)
        return False
    if not _matches(password_hash, current_password):
        return False
    account.password = hash_password(new_password)
    user.passwordChangeRequired = False
    await session.flush()
    return True
