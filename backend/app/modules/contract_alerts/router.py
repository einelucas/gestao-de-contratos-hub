from __future__ import annotations

import math
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, require_permission, require_user
from app.core.database import get_session
from app.core.errors import DomainError
from app.core.permissions import Permission
from app.models.contracts import ContractNotificationStatus, ContractNotificationType
from app.modules.contract_alerts import service
from app.modules.contract_alerts.adapter import NotificationAdapter, get_notification_adapter
from app.modules.contract_alerts.eligibility import ADVANCE_MILESTONES
from app.modules.contract_alerts.schemas import (
    AlertRunOut,
    AttentionListOut,
    ContractNotificationListOut,
    ContractNotificationOut,
    EmailPreviewOut,
    PaginationOut,
)
from app.shared.audit import record_audit

router = APIRouter(tags=["alertas-contratos"])

_MAX_PAGE_SIZE = 100


def alert_adapter() -> NotificationAdapter:
    """Dependência sobrescrevível em testes (app.dependency_overrides)."""
    return get_notification_adapter()


def _summary(result: AlertRunOut) -> dict[str, object]:
    return {
        "today": result.today.isoformat(),
        "provider": result.provider,
        "contractsAnalyzed": result.contracts_analyzed,
        "eligible": result.eligible,
        "sent": result.sent,
        "duplicates": result.duplicates,
        "retried": result.retried,
        "failed": result.failed,
        "skipped": result.skipped,
    }


@router.get("/alertas/previa", response_model=AlertRunOut)
async def preview_alertas(
    data: date | None = Query(default=None, description="Simula outro dia (somente leitura)"),
    current_user: CurrentUser = Depends(require_permission(Permission.ALERTS_MANAGE)),
) -> AlertRunOut:
    return await service.preview_alerts(data)


@router.post("/alertas/executar", response_model=AlertRunOut)
async def execute_alertas(
    dry_run: bool = Query(default=True),
    data: date | None = Query(default=None, description="Só aceita com dry_run=true"),
    session: AsyncSession = Depends(get_session),
    adapter: NotificationAdapter = Depends(alert_adapter),
    current_user: CurrentUser = Depends(require_permission(Permission.ALERTS_MANAGE)),
) -> AlertRunOut:
    if dry_run:
        return await service.preview_alerts(data)
    if data is not None:
        # Envio real sempre usa o dia corrente: simular outra data poderia disparar e-mails indevidos.
        raise DomainError("O parâmetro 'data' só é aceito com dry_run=true")

    result = await service.ContractAlertService(session, adapter).run()
    await record_audit(
        session,
        user_id=current_user.id,
        action="contract_alerts.run",
        entity="ContractNotification",
        metadata={"trigger": "manual", **_summary(result)},
    )
    await session.commit()
    return result


@router.get("/alertas/contratos", response_model=AttentionListOut)
async def list_contratos_em_atencao(
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(require_user),
) -> AttentionListOut:
    return await service.attention_contracts(session, current_user)


@router.get("/alertas/modelo", response_model=EmailPreviewOut)
async def modelo_email(
    contrato: str = Query(...),
    tipo: ContractNotificationType = Query(default=ContractNotificationType.ANTECEDENCIA),
    # `int` + checagem manual: `Literal[45, 20, 1]` em query string rejeita "45" (texto) com 422.
    dias: int | None = Query(default=None, description="Marco de antecedência (45, 20 ou 1)"),
    data: date | None = Query(default=None, description="Dia simulado (opcional)"),
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(require_user),
) -> EmailPreviewOut:
    if dias is not None and dias not in ADVANCE_MILESTONES:
        raise DomainError("Marco de antecedência inválido: use 45, 20 ou 1")
    return await service.email_preview(
        session, current_user, contract_id=contrato, alert_type=tipo, notice_days=dias, day=data
    )


@router.get("/contratos/{contract_id}/notificacoes", response_model=ContractNotificationListOut)
async def list_contrato_notificacoes(
    contract_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(require_user),
) -> ContractNotificationListOut:
    items = await service.list_contract_notifications(session, contract_id, current_user)
    return ContractNotificationListOut(items=items)


@router.get("/notificacoes-contratos", response_model=ContractNotificationListOut)
async def list_notificacoes(
    page: int = Query(default=1),
    page_size: int = Query(default=50, alias="pageSize"),
    status: ContractNotificationStatus | None = Query(default=None),
    tipo: ContractNotificationType | None = Query(default=None),
    contract_id: str | None = Query(default=None, alias="contractId"),
    destinatario: str | None = Query(default=None),
    de: date | None = Query(default=None),
    ate: date | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(require_permission(Permission.ALERTS_MANAGE)),
) -> ContractNotificationListOut:
    page = max(1, page)
    page_size = min(_MAX_PAGE_SIZE, max(1, page_size))
    items, total = await service.list_notifications(
        session,
        page=page,
        page_size=page_size,
        status=status,
        alert_type=tipo,
        contract_id=contract_id,
        recipient=destinatario,
        date_from=de,
        date_to=ate,
    )
    return ContractNotificationListOut(
        items=items,
        pagination=PaginationOut(
            page=page,
            page_size=page_size,
            total=total,
            total_pages=max(1, math.ceil(total / page_size)),
        ),
    )


@router.post("/notificacoes-contratos/{notification_id}/reenviar", response_model=ContractNotificationOut)
async def reenviar_notificacao(
    notification_id: str,
    session: AsyncSession = Depends(get_session),
    adapter: NotificationAdapter = Depends(alert_adapter),
    current_user: CurrentUser = Depends(require_permission(Permission.ALERTS_MANAGE)),
) -> ContractNotificationOut:
    before = await service.get_notification(session, notification_id)
    item = await service.ContractAlertService(session, adapter).resend(notification_id)
    after = await service.get_notification(session, notification_id)
    await record_audit(
        session,
        user_id=current_user.id,
        action="contract_notification.resend",
        entity="ContractNotification",
        entity_id=notification_id,
        previous_data={"status": before.status.value, "attempts": before.attempts, "error": before.error},
        new_data={"status": after.status.value, "attempts": after.attempts, "error": after.error},
        metadata={"contractId": after.contract_id, "result": item.action},
    )
    await session.commit()
    return after
