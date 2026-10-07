"""Perfis e permissões compartilhadas pela base do Hub."""

from __future__ import annotations

from enum import Enum


class Role(str, Enum):
    VIEWER = "VIEWER"
    ANALYST = "ANALYST"
    ADMIN = "ADMIN"


class Permission(str, Enum):
    CONTRACTS_VIEW = "contracts:view"
    CONTRACTS_MANAGE = "contracts:manage"
    CONTRACTS_IMPORT = "contracts:import"
    USERS_MANAGE = "users:manage"
    AUDIT_READ = "audit:read"
    ALERTS_MANAGE = "alerts:manage"
    TEAMS_MANAGE = "teams:manage"


_MATRIX: dict[Role, set[Permission]] = {
    Role.VIEWER: {Permission.CONTRACTS_VIEW},
    Role.ANALYST: {Permission.CONTRACTS_VIEW, Permission.CONTRACTS_MANAGE},
    Role.ADMIN: {
        Permission.CONTRACTS_VIEW,
        Permission.CONTRACTS_MANAGE,
        Permission.CONTRACTS_IMPORT,
        Permission.USERS_MANAGE,
        Permission.AUDIT_READ,
        Permission.ALERTS_MANAGE,
        Permission.TEAMS_MANAGE,
    },
}


def can(role: Role, permission: Permission) -> bool:
    return permission in _MATRIX[role]


def permissions_for(role: Role) -> list[Permission]:
    return sorted(_MATRIX[role], key=lambda permission: permission.value)


class ForbiddenError(Exception):
    def __init__(self, permission: Permission, message: str | None = None) -> None:
        self.permission = permission
        super().__init__(message or f"Permissão negada: {permission.value}")


def assert_can(role: Role, permission: Permission) -> None:
    if not can(role, permission):
        raise ForbiddenError(permission)
