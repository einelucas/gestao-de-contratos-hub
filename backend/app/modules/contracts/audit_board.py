"""Consultas e movimentações do Kanban de auditoria."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser
from app.core.errors import ConflictError, NotFoundError
from app.models.contracts import Contract
from app.modules.contracts import service
from app.modules.contracts.access import assert_can_edit, assert_can_view, sector_access
from app.modules.contracts.audit_workflow import (
    FINALIZED,
    alert_without_finalization,
    sync_contract_audit_stage,
)
from app.modules.contracts.schemas import AuditBoardOut, AuditStage, ContractOut
from app.shared.audit import record_audit


async def get_board(session: AsyncSession, actor: CurrentUser) -> AuditBoardOut:
    contracts = (await session.execute(select(Contract))).scalars().all()
    changed = False
    for item in contracts:
        before = (item.auditStage, item.finalized)
        sync_contract_audit_stage(item)
        changed = changed or before != (item.auditStage, item.finalized)
    if changed:
        await session.commit()

    board_ids = set(
        (
            await session.execute(select(Contract.id).where(Contract.auditStage.is_not(None)))
        ).scalars()
    )
    items = await service.list_contracts(session, actor, contract_ids=board_ids)
    units = sorted({item.unit for item in items if item.unit}, key=str.casefold)
    return AuditBoardOut(items=items, units=units)


async def move_contract(
    session: AsyncSession,
    contract_id: str,
    stage: AuditStage,
    actor: CurrentUser,
) -> ContractOut:
    access = await sector_access(session, actor)
    item = (
        await session.execute(select(Contract).where(Contract.id == contract_id).with_for_update())
    ).scalar_one_or_none()
    if item is None:
        raise NotFoundError("Contrato não encontrado")
    assert_can_view(access, item.sectorId)
    assert_can_edit(access, item.sectorId)

    sync_contract_audit_stage(item)
    if item.auditStage is None:
        raise ConflictError("O contrato não está no fluxo de auditoria")
    if stage != FINALIZED and alert_without_finalization(item) != "Vencido":
        raise ConflictError("O contrato não está mais vencido")

    previous_stage = item.auditStage
    previous_finalized = item.finalized
    item.auditStage = stage
    item.finalized = stage == FINALIZED
    await session.flush()
    await record_audit(
        session,
        user_id=actor.id,
        action="contract.audit-stage.update",
        entity="Contract",
        entity_id=item.id,
        previous_data={"auditStage": previous_stage, "finalized": previous_finalized},
        new_data={"auditStage": item.auditStage, "finalized": item.finalized},
    )
    item_id = item.id
    await session.commit()
    return await service.get_contract(session, item_id, actor)
