"""Equipes de notificação por setor.

Fonte única da regra de destinatários dos alertas: `active_recipients` (equipe
ativa → membros ativos com e-mail válido) é usada pelo motor, pela prévia e
pelas validações do contrato.
"""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auth import CurrentUser
from app.core.errors import ConflictError, DomainError, NotFoundError
from app.core.permissions import Permission, Role, can
from app.models.common import utcnow
from app.models.contracts import Contract, NotificationTeam, NotificationTeamMember, Sector
from app.modules.contracts.access import sector_access
from app.modules.notification_teams.schemas import (
    NotificationTeamCreateIn,
    NotificationTeamOut,
    NotificationTeamUpdateIn,
    TeamMemberIn,
    TeamMemberOut,
)
from app.shared.audit import record_audit
from app.shared.schema import EMAIL_PATTERN

_EMAIL_RE = re.compile(EMAIL_PATTERN)


def active_recipients(team: NotificationTeam | None) -> list[str]:
    """Destinatários efetivos; vazio sem equipe, com equipe inativa ou sem membros ativos válidos."""
    if team is None or not team.active:
        return []
    emails = {
        member.email.strip().lower()
        for member in team.members
        if member.active and member.email and _EMAIL_RE.match(member.email.strip())
    }
    return sorted(emails)


def recipients_problem(team: NotificationTeam | None) -> str | None:
    """Motivo legível de a equipe não ter destinatários (None quando tem)."""
    if team is None:
        return "Contrato sem equipe de notificação"
    if not team.active:
        return f"Equipe '{team.name}' está desativada"
    if not active_recipients(team):
        return f"Equipe '{team.name}' não tem membros ativos com e-mail válido"
    return None


def _team_query() -> Select[tuple[NotificationTeam]]:
    return select(NotificationTeam).options(
        selectinload(NotificationTeam.members), selectinload(NotificationTeam.sector)
    )


async def load_team(session: AsyncSession, team_id: str) -> NotificationTeam:
    stmt = _team_query().where(NotificationTeam.id == team_id).execution_options(populate_existing=True)
    team = (await session.execute(stmt)).scalar_one_or_none()
    if team is None:
        raise NotFoundError("Equipe de notificação não encontrada")
    return team


async def _contract_counts(session: AsyncSession, team_ids: list[str]) -> dict[str, int]:
    if not team_ids:
        return {}
    rows = await session.execute(
        select(Contract.notificationTeamId, func.count(Contract.id))
        .where(Contract.notificationTeamId.in_(team_ids))
        .group_by(Contract.notificationTeamId)
    )
    return {team_id: int(count) for team_id, count in rows.all()}


def to_team_out(team: NotificationTeam, contract_count: int = 0) -> NotificationTeamOut:
    return NotificationTeamOut(
        id=team.id,
        name=team.name,
        sector_id=team.sectorId,
        sector_name=team.sector.name,
        active=team.active,
        members=[
            TeamMemberOut(id=member.id, name=member.name, email=member.email, active=member.active)
            for member in team.members
        ],
        active_member_count=len(active_recipients(team)),
        contract_count=contract_count,
        created_at=team.createdAt,
        updated_at=team.updatedAt,
    )


async def list_teams(
    session: AsyncSession,
    actor: CurrentUser,
    *,
    sector_id: str | None = None,
    only_active: bool = False,
) -> list[NotificationTeamOut]:
    """ADMIN vê todas; quem edita contratos vê só equipes dos setores em que pode editar."""
    stmt = _team_query().order_by(NotificationTeam.name.asc())
    if actor.role != Role.ADMIN:
        access = await sector_access(session, actor)
        editable = access.editable if access.editable is not None else frozenset()
        stmt = stmt.where(NotificationTeam.sectorId.in_(editable))
    if sector_id:
        stmt = stmt.where(NotificationTeam.sectorId == sector_id)
    if only_active:
        stmt = stmt.where(NotificationTeam.active.is_(True))
    teams = (await session.execute(stmt)).scalars().all()
    counts = await _contract_counts(session, [team.id for team in teams])
    return [to_team_out(team, counts.get(team.id, 0)) for team in teams]


async def get_team(session: AsyncSession, team_id: str, actor: CurrentUser) -> NotificationTeamOut:
    team = await load_team(session, team_id)
    if actor.role != Role.ADMIN:
        access = await sector_access(session, actor)
        if not (can(actor.role, Permission.CONTRACTS_MANAGE) and access.can_edit(team.sectorId)):
            raise NotFoundError("Equipe de notificação não encontrada")
    counts = await _contract_counts(session, [team.id])
    return to_team_out(team, counts.get(team.id, 0))


async def _active_sector(session: AsyncSession, sector_id: str) -> Sector:
    sector = await session.get(Sector, sector_id)
    if sector is None or not sector.active:
        raise DomainError("Setor não encontrado ou inativo")
    return sector


async def _assert_unique_name(
    session: AsyncSession, sector_id: str, name: str, exclude_id: str | None = None
) -> None:
    stmt = select(NotificationTeam.id).where(
        NotificationTeam.sectorId == sector_id, func.lower(NotificationTeam.name) == name.lower()
    )
    if exclude_id:
        stmt = stmt.where(NotificationTeam.id != exclude_id)
    if (await session.execute(stmt)).scalar_one_or_none() is not None:
        raise ConflictError("Já existe uma equipe com este nome neste setor")


def _members_snapshot(team: NotificationTeam) -> list[dict[str, Any]]:
    return [{"email": m.email, "name": m.name, "active": m.active} for m in team.members]


def _team_snapshot(team: NotificationTeam) -> dict[str, Any]:
    return {"name": team.name, "sectorId": team.sectorId, "active": team.active}


async def create_team(
    session: AsyncSession, body: NotificationTeamCreateIn, admin: CurrentUser
) -> NotificationTeamOut:
    await _active_sector(session, body.sector_id)
    await _assert_unique_name(session, body.sector_id, body.name)
    team = NotificationTeam(name=body.name, sectorId=body.sector_id, active=body.active)
    team.members = [
        NotificationTeamMember(name=member.name, email=member.email, active=member.active)
        for member in body.members
    ]
    session.add(team)
    await session.flush()
    await record_audit(
        session,
        user_id=admin.id,
        action="notification_team.create",
        entity="NotificationTeam",
        entity_id=team.id,
        new_data={**_team_snapshot(team), "members": _members_snapshot(team)},
    )
    saved_id = team.id
    await session.commit()
    return await get_team(session, saved_id, admin)


async def update_team(
    session: AsyncSession, team_id: str, body: NotificationTeamUpdateIn, admin: CurrentUser
) -> NotificationTeamOut:
    team = await load_team(session, team_id)
    before = _team_snapshot(team)
    changes = body.model_dump(exclude_unset=True, exclude={"members"})

    if "sector_id" in changes and changes["sector_id"] != team.sectorId:
        await _active_sector(session, changes["sector_id"])
        linked = (
            await session.execute(
                select(func.count(Contract.id)).where(
                    Contract.notificationTeamId == team.id, Contract.sectorId != changes["sector_id"]
                )
            )
        ).scalar_one()
        if linked:
            raise ConflictError(
                f"A equipe está vinculada a {linked} contrato(s) de outro setor; "
                "troque a equipe desses contratos antes"
            )
        team.sectorId = changes["sector_id"]
    if "name" in changes:
        await _assert_unique_name(session, changes.get("sector_id", team.sectorId), changes["name"], team.id)
        team.name = changes["name"]
    elif "sector_id" in changes:
        await _assert_unique_name(session, team.sectorId, team.name, team.id)
    if "active" in changes:
        team.active = changes["active"]

    team.updatedAt = utcnow()
    await session.flush()
    after = _team_snapshot(team)
    if after != before:
        await record_audit(
            session,
            user_id=admin.id,
            action="notification_team.update",
            entity="NotificationTeam",
            entity_id=team.id,
            previous_data=before,
            new_data=after,
        )
    if body.members is not None:
        await _apply_members(session, team, body.members, admin)
    saved_id = team.id
    await session.commit()
    return await get_team(session, saved_id, admin)


async def _apply_members(
    session: AsyncSession, team: NotificationTeam, members: list[TeamMemberIn], admin: CurrentUser
) -> None:
    """Substitui a lista de membros (sem commit): atualiza por id, cria os novos e remove os ausentes.

    Remover um membro não mexe no histórico (ContractNotification guarda o e-mail).
    """
    before = _members_snapshot(team)
    existing = {member.id: member for member in team.members}
    unknown = [member.id for member in members if member.id and member.id not in existing]
    if unknown:
        raise DomainError("Membro não pertence a esta equipe")

    # Sem `id`, mas com e-mail já cadastrado na equipe: é o mesmo membro (evita apagar e
    # recriar a linha, que esbarraria no índice único teamId+email).
    by_email = {member.email: member for member in team.members}
    plan: list[tuple[NotificationTeamMember | None, TeamMemberIn]] = []
    reused: set[str] = set()
    for item in members:
        match = existing[item.id] if item.id else by_email.get(item.email)
        if match is not None and match.id in reused:
            match = None
        if match is not None:
            reused.add(match.id)
        plan.append((match, item))

    # Remove primeiro quem saiu da lista, para o e-mail dele poder ser reaproveitado no mesmo save.
    team.members = [member for member in team.members if member.id in reused]
    await session.flush()

    keep: list[NotificationTeamMember] = []
    for match, item in plan:
        if match is not None:
            match.name, match.email, match.active = item.name, item.email, item.active
            match.updatedAt = utcnow()
            keep.append(match)
        else:
            keep.append(NotificationTeamMember(name=item.name, email=item.email, active=item.active))
    team.members = keep
    team.updatedAt = utcnow()
    await session.flush()

    after = _members_snapshot(team)
    before_emails = {m["email"] for m in before}
    after_emails = {m["email"] for m in after}
    await record_audit(
        session,
        user_id=admin.id,
        action="notification_team.members.replace",
        entity="NotificationTeam",
        entity_id=team.id,
        previous_data=before,
        new_data=after,
        metadata={
            "added": sorted(after_emails - before_emails),
            "removed": sorted(before_emails - after_emails),
        },
    )


async def replace_members(
    session: AsyncSession, team_id: str, members: list[TeamMemberIn], admin: CurrentUser
) -> NotificationTeamOut:
    team = await load_team(session, team_id)
    await _apply_members(session, team, members, admin)
    saved_id = team.id
    await session.commit()
    return await get_team(session, saved_id, admin)
