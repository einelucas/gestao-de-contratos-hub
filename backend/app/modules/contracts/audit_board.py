"""Consultas e operações do workspace colaborativo de auditoria."""

from __future__ import annotations

from collections.abc import Sequence
from typing import cast

from fastapi import UploadFile
from sqlalchemy import Text, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auth import CurrentUser
from app.core.errors import DomainError, NotFoundError
from app.core.permissions import ForbiddenError, Permission, Role
from app.models.common import utcnow
from app.models.contracts import (
    Contract,
    ContractAuditActivity,
    ContractAuditAttachment,
    ContractAuditUpdate,
)
from app.models.user import User
from app.modules.contracts import service
from app.modules.contracts.access import assert_can_edit, assert_can_view, sector_access
from app.modules.contracts.audit_workflow import FINALIZED, sync_contract_audit_stage
from app.modules.contracts.schemas import (
    AuditActivityOut,
    AuditAttachmentOut,
    AuditBoardOut,
    AuditStage,
    AuditUpdateEditIn,
    AuditUpdateOut,
    AuditUserOut,
    AuditWorkspaceOut,
    ContractOut,
)
from app.modules.internal_notifications.service import sync_mentions
from app.shared.audit import record_audit

MAX_ATTACHMENT_BYTES = 5 * 1024 * 1024
MAX_ATTACHMENTS_PER_UPDATE = 5


async def _contract_with_access(
    session: AsyncSession, contract_id: str, actor: CurrentUser, *, edit: bool = False
) -> Contract:
    access = await sector_access(session, actor)
    item = (await session.execute(select(Contract).where(Contract.id == contract_id))).scalar_one_or_none()
    if item is None:
        raise NotFoundError("Contrato não encontrado")
    assert_can_view(access, item.sectorId)
    if edit:
        assert_can_edit(access, item.sectorId)
    return item


def _attachment_out(item: ContractAuditAttachment) -> AuditAttachmentOut:
    return AuditAttachmentOut(
        id=item.id,
        name=item.name,
        size=item.size,
        type=item.contentType,
        url=f"/contratos/auditoria/anexos/{item.id}",
    )


def _can_edit_update(item: ContractAuditUpdate, actor: CurrentUser) -> bool:
    return item.authorId == actor.id or actor.role == Role.ADMIN


def _update_out(item: ContractAuditUpdate, actor: CurrentUser) -> AuditUpdateOut:
    return AuditUpdateOut(
        id=item.id,
        contract_id=item.contractId,
        text=item.text,
        author=item.author.name if item.author else "Usuário removido",
        author_id=item.authorId,
        mentioned_user_ids=item.mentionedUserIds or [],
        created_at=item.createdAt,
        updated_at=item.updatedAt,
        can_edit=_can_edit_update(item, actor),
        attachments=[_attachment_out(attachment) for attachment in item.attachments],
    )


def _activity_out(item: ContractAuditActivity) -> AuditActivityOut:
    return AuditActivityOut(
        id=item.id,
        contract_id=item.contractId,
        type=item.type,
        message=item.message,
        user_id=item.actorId,
        user_name=item.actor.name if item.actor else "Usuário removido",
        from_stage=cast(AuditStage | None, item.fromStage),
        to_stage=cast(AuditStage | None, item.toStage),
        created_at=item.createdAt,
    )


async def get_board(session: AsyncSession, actor: CurrentUser) -> AuditBoardOut:
    # O backlog "Não iniciado" também faz parte do quadro; list_contracts
    # mantém a restrição de visibilidade por setor.
    contracts = (await session.execute(select(Contract))).scalars().all()
    changed = False
    for contract in contracts:
        before = (contract.auditStage, contract.auditStageEnteredAt)
        sync_contract_audit_stage(contract)
        changed = changed or before != (contract.auditStage, contract.auditStageEnteredAt)
    if changed:
        await session.commit()
    items = await service.list_contracts(session, actor)
    users = (
        (await session.execute(select(User).where(User.active.is_(True)).order_by(User.name))).scalars().all()
    )
    units = sorted({item.unit for item in items if item.unit}, key=str.casefold)
    visible_ids = {item.id for item in items}
    mention_rows = (
        await session.execute(
            select(ContractAuditUpdate.contractId, func.count(ContractAuditUpdate.id))
            .where(
                ContractAuditUpdate.authorId != actor.id,
                func.cast(ContractAuditUpdate.mentionedUserIds, Text).like(f'%"{actor.id}"%'),
            )
            .group_by(ContractAuditUpdate.contractId)
        )
    ).all()
    mention_counts = {contract_id: count for contract_id, count in mention_rows if contract_id in visible_ids}
    return AuditBoardOut(
        items=items,
        units=units,
        users=[
            AuditUserOut(
                id=user.id,
                name=user.name,
                email=user.email,
                role=user.role.value,
                active=user.active,
                image=user.image,
            )
            for user in users
        ],
        current_user_id=actor.id,
        mention_counts=mention_counts,
    )


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

    regularization_before = {
        "regularizationStage": item.regularizationStage,
        "regularizationResponsible": item.regularizationResponsible,
        "regularizationDeadline": service._json_safe(item.regularizationDeadline),
        "regularizationNotes": item.regularizationNotes,
    }
    previous_stage = item.auditStage
    previous_finalized = item.finalized
    if previous_stage == stage:
        return await service.get_contract(session, item.id, actor)

    item.auditStage = stage
    item.auditStageEnteredAt = utcnow()
    item.finalized = stage == FINALIZED
    service.record_regularization_history(item, regularization_before, actor)
    session.add(
        ContractAuditActivity(
            contractId=item.id,
            actorId=actor.id,
            type="STAGE",
            message="iniciou a auditoria" if previous_stage is None else "moveu o contrato entre etapas",
            fromStage=previous_stage,
            toStage=stage,
        )
    )
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


async def get_workspace(session: AsyncSession, contract_id: str, actor: CurrentUser) -> AuditWorkspaceOut:
    await _contract_with_access(session, contract_id, actor)
    updates = (
        (
            await session.execute(
                select(ContractAuditUpdate)
                .where(ContractAuditUpdate.contractId == contract_id)
                .options(
                    selectinload(ContractAuditUpdate.author),
                    selectinload(ContractAuditUpdate.attachments),
                )
                .order_by(ContractAuditUpdate.createdAt.desc())
            )
        )
        .scalars()
        .all()
    )
    activities = (
        (
            await session.execute(
                select(ContractAuditActivity)
                .where(ContractAuditActivity.contractId == contract_id)
                .options(selectinload(ContractAuditActivity.actor))
                .order_by(ContractAuditActivity.createdAt.desc())
            )
        )
        .scalars()
        .all()
    )
    return AuditWorkspaceOut(
        updates=[_update_out(item, actor) for item in updates],
        activity=[_activity_out(item) for item in activities],
    )


async def create_update(
    session: AsyncSession,
    contract_id: str,
    actor: CurrentUser,
    text: str,
    mentioned_user_ids: Sequence[str],
    files: Sequence[UploadFile],
) -> AuditUpdateOut:
    await _contract_with_access(session, contract_id, actor, edit=True)
    clean_text = text.strip()
    if not clean_text and not files:
        raise DomainError("Escreva uma atualização ou adicione um anexo")
    if len(clean_text) > 10000:
        raise DomainError("A atualização deve ter no máximo 10.000 caracteres")
    if len(files) > MAX_ATTACHMENTS_PER_UPDATE:
        raise DomainError(f"Envie no máximo {MAX_ATTACHMENTS_PER_UPDATE} anexos por atualização")

    valid_mentions = (
        set(
            (
                await session.execute(
                    select(User.id).where(User.id.in_(set(mentioned_user_ids)), User.active.is_(True))
                )
            ).scalars()
        )
        if mentioned_user_ids
        else set()
    )
    update = ContractAuditUpdate(
        contractId=contract_id,
        authorId=actor.id,
        text=clean_text,
        mentionedUserIds=sorted(valid_mentions),
    )
    session.add(update)
    await session.flush()

    for upload in files:
        data = await upload.read(MAX_ATTACHMENT_BYTES + 1)
        if len(data) > MAX_ATTACHMENT_BYTES:
            raise DomainError(f"O arquivo {upload.filename or 'anexo'} excede o limite de 5 MB")
        if not data:
            raise DomainError(f"O arquivo {upload.filename or 'anexo'} está vazio")
        session.add(
            ContractAuditAttachment(
                updateId=update.id,
                name=(upload.filename or "anexo")[:255],
                contentType=(upload.content_type or "application/octet-stream")[:160],
                size=len(data),
                data=data,
            )
        )

    session.add(
        ContractAuditActivity(
            contractId=contract_id,
            actorId=actor.id,
            type="FILE" if files else "COMMENT",
            message=(
                f"publicou uma atualização com {len(files)} anexo(s)" if files else "publicou uma atualização"
            ),
        )
    )
    await sync_mentions(session, update, actor)
    await session.commit()
    refreshed = (
        await session.execute(
            select(ContractAuditUpdate)
            .where(ContractAuditUpdate.id == update.id)
            .options(
                selectinload(ContractAuditUpdate.author),
                selectinload(ContractAuditUpdate.attachments),
            )
        )
    ).scalar_one()
    return _update_out(refreshed, actor)


async def edit_update(
    session: AsyncSession, update_id: str, body: AuditUpdateEditIn, actor: CurrentUser
) -> AuditUpdateOut:
    item = (
        await session.execute(
            select(ContractAuditUpdate)
            .where(ContractAuditUpdate.id == update_id)
            .options(
                selectinload(ContractAuditUpdate.author),
                selectinload(ContractAuditUpdate.attachments),
            )
        )
    ).scalar_one_or_none()
    if item is None:
        raise NotFoundError("Atualização não encontrada")
    await _contract_with_access(session, item.contractId, actor, edit=True)
    if not _can_edit_update(item, actor):
        raise ForbiddenError(
            Permission.CONTRACTS_MANAGE,
            "Somente o autor ou um administrador pode editar esta atualização",
        )
    item.text = body.text.strip()
    item.mentionedUserIds = list(dict.fromkeys(body.mentioned_user_ids))
    await sync_mentions(session, item, actor)
    session.add(
        ContractAuditActivity(
            contractId=item.contractId,
            actorId=actor.id,
            type="COMMENT",
            message="editou uma atualização",
        )
    )
    await session.commit()
    return _update_out(item, actor)


async def delete_update(session: AsyncSession, update_id: str, actor: CurrentUser) -> None:
    item = (
        await session.execute(select(ContractAuditUpdate).where(ContractAuditUpdate.id == update_id))
    ).scalar_one_or_none()
    if item is None:
        raise NotFoundError("Atualização não encontrada")
    await _contract_with_access(session, item.contractId, actor, edit=True)
    if not _can_edit_update(item, actor):
        raise ForbiddenError(
            Permission.CONTRACTS_MANAGE,
            "Somente o autor ou um administrador pode excluir esta atualização",
        )
    session.add(
        ContractAuditActivity(
            contractId=item.contractId,
            actorId=actor.id,
            type="COMMENT",
            message="excluiu uma atualização",
        )
    )
    await session.delete(item)
    await session.commit()


async def get_attachment(
    session: AsyncSession, attachment_id: str, actor: CurrentUser
) -> ContractAuditAttachment:
    item = (
        await session.execute(
            select(ContractAuditAttachment)
            .where(ContractAuditAttachment.id == attachment_id)
            .options(selectinload(ContractAuditAttachment.update))
        )
    ).scalar_one_or_none()
    if item is None:
        raise NotFoundError("Anexo não encontrado")
    await _contract_with_access(session, item.update.contractId, actor)
    return item
