"""Central interna: menções, lembretes pessoais e leitura de notificações."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query, Response
from pydantic import Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, require_user
from app.core.database import get_session
from app.core.errors import DomainError
from app.models.common import utcnow
from app.modules.internal_notifications import service
from app.shared.schema import CamelModel

router = APIRouter(tags=["notificacoes-internas"])


class ReminderIn(CamelModel):
    message: str = Field(min_length=1, max_length=500)
    scheduled_at: datetime


class InternalNotificationOut(CamelModel):
    id: str
    kind: str
    contract_id: str
    contract_number: str
    supplier: str
    actor_name: str | None
    message: str
    scheduled_at: datetime
    read_at: datetime | None
    created_at: datetime


class InternalNotificationListOut(CamelModel):
    items: list[InternalNotificationOut]
    unread_count: int


def to_out(item) -> InternalNotificationOut:
    return InternalNotificationOut(
        id=item.id,
        kind=item.kind,
        contract_id=item.contractId,
        contract_number=item.contract.contractNumber,
        supplier=item.contract.supplier.name,
        actor_name=item.actor.name if item.actor else None,
        message=item.message,
        scheduled_at=service.utc_iso(item.scheduledAt),
        read_at=service.utc_iso(item.readAt) if item.readAt else None,
        created_at=service.utc_iso(item.createdAt),
    )


@router.get("/notificacoes-internas", response_model=InternalNotificationListOut)
async def list_internal_notifications(
    contract_id: str | None = Query(default=None, alias="contractId"),
    include_scheduled: bool = Query(default=False, alias="includeScheduled"),
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(require_user),
) -> InternalNotificationListOut:
    items, unread_count = await service.inbox(
        session, actor, contract_id=contract_id, include_scheduled=include_scheduled and bool(contract_id)
    )
    return InternalNotificationListOut(items=[to_out(item) for item in items], unread_count=unread_count)


@router.post("/contratos/{contract_id}/lembretes", response_model=InternalNotificationOut, status_code=201)
async def create_reminder(
    contract_id: str,
    body: ReminderIn,
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(require_user),
) -> InternalNotificationOut:
    item = await service.create_reminder(session, actor, contract_id, body.message, body.scheduled_at)
    # Também carrega o contrato/fornecedor/autor após o commit.
    items, _ = await service.inbox(session, actor, contract_id=contract_id, include_scheduled=True)
    reminder = next((entry for entry in items if entry.id == item.id), None)
    if reminder is None:
        raise DomainError("Não foi possível consultar o lembrete criado.")
    return to_out(reminder)


@router.patch("/notificacoes-internas/{notification_id}/lida", response_model=InternalNotificationListOut)
async def mark_read(
    notification_id: str,
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(require_user),
) -> InternalNotificationListOut:
    item = await service.get_own(session, notification_id, actor)
    if item.scheduledAt > utcnow():
        raise DomainError("Lembretes futuros ainda não podem ser marcados como lidos.")
    if item.readAt is None:
        item.readAt = utcnow()
        await session.commit()
    items, unread_count = await service.inbox(session, actor)
    return InternalNotificationListOut(items=[to_out(entry) for entry in items], unread_count=unread_count)


@router.delete("/notificacoes-internas/{notification_id}", status_code=204)
async def cancel_reminder(
    notification_id: str,
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(require_user),
) -> Response:
    item = await service.get_own(session, notification_id, actor)
    if item.kind != "REMINDER":
        raise DomainError("Apenas lembretes podem ser excluídos.")
    await session.delete(item)
    await session.commit()
    return Response(status_code=204)
