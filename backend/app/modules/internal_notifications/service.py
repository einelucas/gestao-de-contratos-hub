"""Persistência e regras de notificações internas da Gestão de Contratos."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auth import CurrentUser
from app.core.errors import DomainError, NotFoundError
from app.models.common import utcnow
from app.models.contracts import Contract, ContractAuditUpdate, InAppNotification, UserSectorPermission
from app.models.user import Role, User
from app.modules.contracts.access import assert_can_view, restrict_to_viewable, sector_access


def utc_iso(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC)


async def sync_mentions(
    session: AsyncSession, update: ContractAuditUpdate, actor: CurrentUser
) -> None:
    """Notifica apenas usuários ativos que conseguem consultar o contrato.

    Sincroniza em edições; a unicidade impede duplicatas. A exclusão de uma
    atualização remove as notificações correspondentes via CASCADE.
    """
    contract = (await session.execute(
        select(Contract).where(Contract.id == update.contractId)
    )).scalar_one()
    requested = set(update.mentionedUserIds or []) - {actor.id, update.authorId}
    allowed = set()
    if requested:
        users = (await session.execute(
            select(User).where(User.id.in_(requested), User.active.is_(True))
        )).scalars().all()
        permitted = set((await session.execute(
            select(UserSectorPermission.userId).where(
                UserSectorPermission.userId.in_(requested),
                UserSectorPermission.sectorId == contract.sectorId,
                (UserSectorPermission.canView.is_(True) | UserSectorPermission.canEdit.is_(True)),
            )
        )).scalars())
        allowed = {u.id for u in users if u.role == Role.ADMIN or u.id in permitted}

    current = (await session.execute(
        select(InAppNotification).where(InAppNotification.auditUpdateId == update.id)
    )).scalars().all()
    for notification in current:
        if notification.userId not in allowed:
            await session.delete(notification)
        else:
            notification.message = update.text[:500]

    existing = {item.userId for item in current}
    for user_id in allowed - existing:
        session.add(InAppNotification(
            userId=user_id, contractId=update.contractId, actorId=actor.id,
            auditUpdateId=update.id, kind="MENTION", message=update.text[:500],
            scheduledAt=update.createdAt or utcnow(),
        ))


async def inbox(
    session: AsyncSession,
    actor: CurrentUser,
    *,
    contract_id: str | None = None,
    include_scheduled: bool = False,
) -> tuple[list[InAppNotification], int]:
    access = await sector_access(session, actor)
    stmt = select(InAppNotification).join(
        Contract, InAppNotification.contractId == Contract.id
    ).where(InAppNotification.userId == actor.id)
    stmt = restrict_to_viewable(stmt, access, Contract.sectorId)
    if contract_id:
        stmt = stmt.where(InAppNotification.contractId == contract_id)
    if not include_scheduled:
        stmt = stmt.where(InAppNotification.scheduledAt <= utcnow())
    stmt = stmt.options(
        selectinload(InAppNotification.contract).selectinload(Contract.supplier),
        selectinload(InAppNotification.actor)
    ).order_by(InAppNotification.scheduledAt.desc()).limit(150)
    items = list((await session.execute(stmt)).scalars().all())
    # Contagem exata dos itens não lidos visíveis, sem o limite da lista.
    count_query = select(func.count(InAppNotification.id)).select_from(InAppNotification).join(
        Contract, InAppNotification.contractId == Contract.id
    ).where(
        InAppNotification.userId == actor.id,
        InAppNotification.readAt.is_(None),
        InAppNotification.scheduledAt <= utcnow(),
    )
    count_query = restrict_to_viewable(count_query, access, Contract.sectorId)
    unread = (await session.execute(count_query)).scalar_one()
    return items, unread


async def get_own(
    session: AsyncSession, notification_id: str, actor: CurrentUser
) -> InAppNotification:
    item = (await session.execute(
        select(InAppNotification).where(
            InAppNotification.id == notification_id,
            InAppNotification.userId == actor.id,
        )
    )).scalar_one_or_none()
    if item is None:
        raise NotFoundError("Notificação não encontrada")
    contract = (await session.execute(
        select(Contract).where(Contract.id == item.contractId)
    )).scalar_one_or_none()
    if contract is None:
        raise NotFoundError("Notificação não encontrada")
    assert_can_view(await sector_access(session, actor), contract.sectorId)
    return item


async def create_reminder(
    session: AsyncSession,
    actor: CurrentUser,
    contract_id: str,
    message: str,
    scheduled_at: datetime,
) -> InAppNotification:
    contract = (await session.execute(
        select(Contract).where(Contract.id == contract_id)
    )).scalar_one_or_none()
    if contract is None:
        raise NotFoundError("Contrato não encontrado")
    assert_can_view(await sector_access(session, actor), contract.sectorId)
    if scheduled_at.tzinfo is None or scheduled_at.utcoffset() is None:
        raise DomainError("Informe a data com fuso horário.")
    due = scheduled_at.astimezone(UTC).replace(tzinfo=None)
    now = utcnow()
    if due <= now or due > now + timedelta(days=365):
        raise DomainError("Agende para uma data futura, no máximo daqui a um ano.")
    clean_message = message.strip()
    if not clean_message:
        raise DomainError("Escreva o texto do lembrete.")
    item = InAppNotification(
        userId=actor.id,
        actorId=actor.id,
        contractId=contract_id,
        kind="REMINDER",
        message=clean_message[:500],
        scheduledAt=due,
    )
    session.add(item)
    await session.commit()
    await session.refresh(item)
    return item
