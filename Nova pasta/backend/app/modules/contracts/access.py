"""Escopo de setores por usuário (UserSectorPermission).

- ADMIN consulta e edita todos os setores.
- VIEWER consulta os setores com `canView` ou `canEdit`; nunca edita.
- ANALYST consulta os mesmos setores e edita apenas os que têm `canEdit`.
- Sem nenhuma linha em UserSectorPermission, o usuário não vê contratos.

Contrato de setor não visível responde 404 (não revela que existe); contrato
visível sem permissão de edição responde 403.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import Select, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser
from app.core.errors import NotFoundError
from app.core.permissions import ForbiddenError, Permission, Role, can
from app.models.contracts import Contract, UserSectorPermission


@dataclass(frozen=True, slots=True)
class SectorAccess:
    """`None` significa "todos os setores" (ADMIN)."""

    viewable: frozenset[str] | None
    editable: frozenset[str] | None

    def can_view(self, sector_id: str) -> bool:
        return self.viewable is None or sector_id in self.viewable

    def can_edit(self, sector_id: str) -> bool:
        return self.editable is None or sector_id in self.editable


async def sector_access(session: AsyncSession, actor: CurrentUser) -> SectorAccess:
    if actor.role == Role.ADMIN:
        return SectorAccess(viewable=None, editable=None)

    rows = (
        await session.execute(
            select(UserSectorPermission.sectorId, UserSectorPermission.canEdit).where(
                UserSectorPermission.userId == actor.id,
                or_(UserSectorPermission.canView.is_(True), UserSectorPermission.canEdit.is_(True)),
            )
        )
    ).all()
    viewable = frozenset(sector_id for sector_id, _ in rows)
    editable = (
        frozenset(sector_id for sector_id, can_edit in rows if can_edit)
        if can(actor.role, Permission.CONTRACTS_MANAGE)
        else frozenset()
    )
    return SectorAccess(viewable=viewable, editable=editable)


def restrict_to_viewable(
    stmt: Select[Any], access: SectorAccess, column: Any = Contract.sectorId
) -> Select[Any]:
    if access.viewable is None:
        return stmt
    return stmt.where(column.in_(access.viewable))


def assert_can_view(access: SectorAccess, sector_id: str, message: str = "Contrato não encontrado") -> None:
    if not access.can_view(sector_id):
        raise NotFoundError(message)


def assert_can_edit(access: SectorAccess, sector_id: str) -> None:
    if not access.can_edit(sector_id):
        raise ForbiddenError(
            Permission.CONTRACTS_MANAGE, "Você não tem permissão para editar contratos deste setor"
        )
