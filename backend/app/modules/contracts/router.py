from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, require_permission, require_user
from app.core.database import get_session
from app.core.permissions import Permission
from app.modules.contracts import overdue_history, service, summary
from app.modules.contracts.schemas import (
    ContractCreateIn,
    ContractListOut,
    ContractOut,
    ContractSummaryOut,
    ContractUpdateIn,
    OverdueHistoryOut,
    ResponsibleListOut,
    SectorListOut,
    UserSectorPermissionsIn,
    UserSectorPermissionsOut,
)

router = APIRouter(tags=["gestao-contratos"])


@router.get("/setores", response_model=SectorListOut)
async def list_setores(
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(require_user),
) -> SectorListOut:
    return SectorListOut(items=await service.list_sectors(session, current_user))


@router.get("/contratos", response_model=ContractListOut)
async def list_contratos(
    sector_id: str | None = Query(default=None, alias="sectorId"),
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(require_user),
) -> ContractListOut:
    items = await service.list_contracts(session, current_user, sector_id=sector_id)
    return ContractListOut(items=items, total=len(items))


# Registrada antes de /contratos/{contract_id} para "resumo" não ser lido como id.
@router.get("/contratos/resumo", response_model=ContractSummaryOut)
async def resumo_contratos(
    sector_id: str | None = Query(default=None, alias="sectorId"),
    unit: str | None = Query(default=None),
    de: date | None = Query(default=None),
    ate: date | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(require_user),
) -> ContractSummaryOut:
    return await summary.build_summary(
        session, current_user, sector_id=sector_id, unit=unit, date_from=de, date_to=ate
    )


# Registrada antes de /contratos/{contract_id} pelo mesmo motivo do /resumo.
@router.get("/contratos/vencidos-historico", response_model=OverdueHistoryOut)
async def historico_vencidos(
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(require_user),
) -> OverdueHistoryOut:
    return await overdue_history.reconcile_and_get_history(session)


@router.get("/contratos/{contract_id}", response_model=ContractOut)
async def get_contrato(
    contract_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(require_user),
) -> ContractOut:
    return await service.get_contract(session, contract_id, current_user)


@router.post("/contratos", response_model=ContractOut, status_code=201)
async def create_contrato(
    body: ContractCreateIn,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(require_permission(Permission.CONTRACTS_MANAGE)),
) -> ContractOut:
    return await service.create_contract(session, body, current_user)


@router.patch("/contratos/{contract_id}", response_model=ContractOut)
async def update_contrato(
    contract_id: str,
    body: ContractUpdateIn,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(require_permission(Permission.CONTRACTS_MANAGE)),
) -> ContractOut:
    return await service.update_contract(session, contract_id, body, current_user)


@router.get("/responsaveis", response_model=ResponsibleListOut)
async def list_responsaveis(
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(require_permission(Permission.CONTRACTS_MANAGE)),
) -> ResponsibleListOut:
    return ResponsibleListOut(items=await service.list_responsibles(session))


@router.get("/usuarios/{user_id}/setores", response_model=UserSectorPermissionsOut)
async def get_usuario_setores(
    user_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(require_permission(Permission.USERS_MANAGE)),
) -> UserSectorPermissionsOut:
    return await service.get_user_sector_permissions(session, user_id)


@router.put("/usuarios/{user_id}/setores", response_model=UserSectorPermissionsOut)
async def replace_usuario_setores(
    user_id: str,
    body: UserSectorPermissionsIn,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(require_permission(Permission.USERS_MANAGE)),
) -> UserSectorPermissionsOut:
    return await service.replace_user_sector_permissions(session, user_id, body, current_user)
