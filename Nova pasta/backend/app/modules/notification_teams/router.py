from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, require_permission
from app.core.database import get_session
from app.core.permissions import Permission
from app.modules.notification_teams import service
from app.modules.notification_teams.schemas import (
    NotificationTeamCreateIn,
    NotificationTeamListOut,
    NotificationTeamOut,
    NotificationTeamUpdateIn,
    TeamMembersIn,
)

router = APIRouter(tags=["equipes-notificacao"])


@router.get("/equipes-notificacao", response_model=NotificationTeamListOut)
async def list_equipes(
    sector_id: str | None = Query(default=None, alias="setorId"),
    ativas: bool = Query(default=False),
    session: AsyncSession = Depends(get_session),
    # ANALYST consulta para o formulário do contrato (só setores em que edita); VIEWER não.
    current_user: CurrentUser = Depends(require_permission(Permission.CONTRACTS_MANAGE)),
) -> NotificationTeamListOut:
    items = await service.list_teams(session, current_user, sector_id=sector_id, only_active=ativas)
    return NotificationTeamListOut(items=items)


@router.get("/equipes-notificacao/{team_id}", response_model=NotificationTeamOut)
async def get_equipe(
    team_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(require_permission(Permission.CONTRACTS_MANAGE)),
) -> NotificationTeamOut:
    return await service.get_team(session, team_id, current_user)


@router.post("/equipes-notificacao", response_model=NotificationTeamOut, status_code=201)
async def create_equipe(
    body: NotificationTeamCreateIn,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(require_permission(Permission.TEAMS_MANAGE)),
) -> NotificationTeamOut:
    return await service.create_team(session, body, current_user)


@router.patch("/equipes-notificacao/{team_id}", response_model=NotificationTeamOut)
async def update_equipe(
    team_id: str,
    body: NotificationTeamUpdateIn,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(require_permission(Permission.TEAMS_MANAGE)),
) -> NotificationTeamOut:
    return await service.update_team(session, team_id, body, current_user)


@router.put("/equipes-notificacao/{team_id}/membros", response_model=NotificationTeamOut)
async def replace_membros(
    team_id: str,
    body: TeamMembersIn,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(require_permission(Permission.TEAMS_MANAGE)),
) -> NotificationTeamOut:
    return await service.replace_members(session, team_id, body.members, current_user)
