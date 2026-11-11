"""Motor de alertas de vencimento de contratos.

Fluxo de uma execução real:
    contratos com notify=true e não finalizados
    → marco do dia na régua fixa 45/20/1/0 + VENCIDO semanal (eligibility.evaluate)
    → marco já processado? (qualquer linha não-SKIPPED do contrato/ciclo/marco) → ignora
    → equipe do contrato → membros ativos (um destinatário por linha)
    → para cada membro: INSERT … ON CONFLICT DO NOTHING em ContractNotification
      (a chave única inclui o destinatário; quem insere a linha é quem envia)
    → NotificationAdapter.send (um e-mail por destinatário, sem expor os demais)
    → SENT ou FAILED por destinatário
    → retry das FAILED com attempts < 3, reusando a mesma linha

"Marco processado" impede reenvio retroativo: quem entra na equipe (ou uma nova
equipe) depois do marco só participa dos próximos.

Cada contrato é processado e confirmado (commit) de forma independente: um
erro em um contrato nunca interrompe os demais. O dry-run roda numa sessão
própria, em transação READ ONLY, e nunca chama o adapter.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from urllib.parse import quote

from sqlalchemy import Select, func, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auth import CurrentUser
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.errors import ConflictError, NotFoundError
from app.core.logging import get_logger
from app.models.common import utcnow
from app.models.contracts import (
    Contract,
    ContractNotification,
    ContractNotificationStatus,
    ContractNotificationType,
    NotificationTeam,
    Supplier,
)
from app.modules.contract_alerts.adapter import AlertMessage, NotificationAdapter
from app.modules.contract_alerts.eligibility import (
    ADVANCE_MILESTONES,
    AlertDecision,
    evaluate,
    still_same_cycle,
)
from app.modules.contract_alerts.schemas import (
    AlertItemOut,
    AlertRunOut,
    AttentionContractOut,
    AttentionListOut,
    ContractNotificationOut,
    EmailPreviewOut,
    LastNotificationOut,
)
from app.modules.contract_alerts.templates import render_alert
from app.modules.contracts import service as contracts_service
from app.modules.contracts.access import assert_can_view, sector_access
from app.modules.contracts.rules import contracts_today
from app.modules.notification_teams.service import active_recipients, recipients_problem

logger = get_logger("app.contract_alerts")

MAX_ATTEMPTS = 3
# PENDING sem conclusão depois disso = processo morreu durante o envio.
STALE_PENDING_AFTER = timedelta(minutes=15)
# Valor gravado em `recipient` quando não há destinatário válido (linha SKIPPED).
NO_RECIPIENT = ""
_ERROR_MAX_LENGTH = 2000

_DEDUP_COLUMNS = ["contractId", "type", "referenceDate", "noticeDays", "recipient"]


@dataclass(frozen=True, slots=True)
class ContractView:
    """Retrato do contrato desacoplado da sessão ORM (sobrevive a rollbacks)."""

    id: str
    number: str
    supplier: str
    sector: str
    unit: str
    notify: bool
    finalized: bool
    end_date: date | None
    auto_renewal: bool
    # Membros ativos da equipe do contrato (fonte única: notification_teams.active_recipients).
    recipients: tuple[str, ...] = ()
    recipients_problem: str | None = None
    team_id: str | None = None
    team_name: str | None = None
    notify_enabled_on: date | None = None
    service_description: str = ""
    criticality: str | None = None


def _view(contract: Contract) -> ContractView:
    team = contract.notificationTeam
    return ContractView(
        id=contract.id,
        number=contract.contractNumber,
        supplier=contract.supplier.name,
        sector=contract.sector.name,
        unit=contract.unit,
        notify=contract.notify,
        finalized=contract.finalized,
        end_date=contract.endDate,
        auto_renewal=contract.autoRenewal,
        recipients=tuple(active_recipients(team)),
        recipients_problem=recipients_problem(team),
        team_id=team.id if team else None,
        team_name=team.name if team else None,
        notify_enabled_on=contract.notifyEnabledOn,
        service_description=contract.serviceDescription,
        criticality=contract.criticality.value if contract.criticality else None,
    )


def _contract_loader() -> Select[tuple[Contract]]:
    return select(Contract).options(
        selectinload(Contract.supplier),
        selectinload(Contract.sector),
        selectinload(Contract.notificationTeam).selectinload(NotificationTeam.members),
    )


def _error_text(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {exc}"[:_ERROR_MAX_LENGTH]


def build_message(
    *,
    notification_id: str,
    alert_type: ContractNotificationType,
    view: ContractView,
    end_date: date,
    days: int,
    recipient: str,
) -> AlertMessage:
    contract_url = contract_link(view.id)
    rendered = render_alert(
        alert_type=alert_type.value,
        contract_number=view.number,
        supplier=view.supplier,
        service_description=view.service_description,
        sector=view.sector,
        unit=view.unit,
        end_date=end_date,
        days=days,
        auto_renewal=view.auto_renewal,
        criticality=view.criticality,
        contract_url=contract_url,
    )
    return AlertMessage(
        notification_id=notification_id,
        alert_type=alert_type.value,
        recipients=[recipient],
        subject=rendered.subject,
        body=rendered.text,
        html_body=rendered.html,
        contract_id=view.id,
        contract_number=view.number,
        supplier=view.supplier,
        sector=view.sector,
        unit=view.unit,
        end_date=end_date,
        days_to_end=days,
        auto_renewal=view.auto_renewal,
        service_description=view.service_description,
        criticality=view.criticality,
        contract_url=contract_url,
    )


def contract_link(contract_id: str) -> str | None:
    base = get_settings().app_public_url
    if not base:
        return None
    return f"{base.rstrip('/')}/dashboard/contratos?contrato={quote(contract_id)}"


def _item(
    action: str,
    view: ContractView,
    *,
    alert_type: ContractNotificationType,
    reference_date: date,
    notice_days: int,
    contract_end_date: date,
    days_to_end: int,
    reason: str,
    recipient: str | None,
    retry: bool = False,
    notification_id: str | None = None,
    attempts: int | None = None,
    error: str | None = None,
) -> AlertItemOut:
    return AlertItemOut(
        action=action,
        retry=retry,
        contract_id=view.id,
        contract_number=view.number,
        supplier=view.supplier,
        sector_name=view.sector,
        unit=view.unit,
        type=alert_type,
        recipient=recipient,
        contract_end_date=contract_end_date,
        reference_date=reference_date,
        notice_days=notice_days,
        days_to_end=days_to_end,
        reason=reason,
        auto_renewal=view.auto_renewal,
        notification_id=notification_id,
        attempts=attempts,
        error=error,
    )


def _decision_item(
    action: str, view: ContractView, decision: AlertDecision, *, recipient: str | None, **extra: object
) -> AlertItemOut:
    assert view.end_date is not None
    return _item(
        action,
        view,
        alert_type=decision.type,
        reference_date=decision.reference_date,
        notice_days=decision.notice_days,
        contract_end_date=view.end_date,
        days_to_end=decision.days_to_end,
        reason=decision.reason,
        recipient=recipient,
        **extra,  # type: ignore[arg-type]
    )


def _count(result: AlertRunOut, item: AlertItemOut) -> None:
    """No dry-run, `sent`/`retried` contam o que SERIA enviado/reenviado."""
    if item.retry:
        result.retried += 1
    if item.action in ("sent", "would_send", "would_retry"):
        result.sent += 1
    elif item.action == "failed":
        result.failed += 1
    elif item.action == "skipped":
        result.skipped += 1
    elif item.action == "already_notified":
        result.duplicates += 1


@dataclass(frozen=True, slots=True)
class _RetryCandidate:
    id: str
    type: ContractNotificationType
    recipient: str
    reference_date: date
    notice_days: int
    contract_end_date: date
    attempts: int
    view: ContractView
    # O destinatário ainda é membro ativo da equipe atual do contrato?
    still_member: bool = True


class ContractAlertService:
    def __init__(self, session: AsyncSession, adapter: NotificationAdapter | None = None) -> None:
        self.session = session
        self.adapter = adapter

    async def run(self, *, today: date | None = None, dry_run: bool = False) -> AlertRunOut:
        if not dry_run and self.adapter is None:
            raise RuntimeError("Execução real exige um NotificationAdapter")
        today = today or contracts_today()
        result = AlertRunOut(
            today=today,
            dry_run=dry_run,
            provider=None if dry_run else self.adapter.name,  # type: ignore[union-attr]
        )

        contracts = (
            (
                await self.session.execute(
                    _contract_loader()
                    .where(Contract.notify.is_(True), Contract.finalized.is_(False))
                    .order_by(Contract.endDate.asc().nullslast(), Contract.contractNumber.asc())
                )
            )
            .scalars()
            .all()
        )
        views = [_view(contract) for contract in contracts]
        result.contracts_analyzed = len(views)
        attempted: set[str] = set()

        for view in views:
            decision = evaluate(
                notify=view.notify,
                finalized=view.finalized,
                end_date=view.end_date,
                today=today,
                notify_enabled_on=view.notify_enabled_on,
            )
            if decision is None:
                continue
            result.eligible += 1
            try:
                if dry_run:
                    items = await self._preview_new(view, decision)
                else:
                    items = await self._process_new(view, decision)
            except Exception as exc:  # noqa: BLE001 — um contrato nunca derruba o lote
                await self.session.rollback()
                logger.exception(
                    "contract_alert.process_failed",
                    contract_id=view.id,
                    contract_number=view.number,
                    alert_type=decision.type.value,
                    notice_days=decision.notice_days,
                )
                items = [_decision_item("failed", view, decision, recipient=None, error=_error_text(exc))]
            for item in items:
                # Só o que foi de fato tentado agora fica fora do retry desta execução;
                # uma FAILED antiga que apareceu como duplicada ainda deve ser retentada.
                if item.action in ("sent", "failed") and item.notification_id:
                    attempted.add(item.notification_id)
                _count(result, item)
                result.items.append(item)

        await self._retry_phase(result, today=today, dry_run=dry_run, exclude=attempted)
        return result

    # ------------------------------------------------------------------ novos

    async def _existing_id(self, view: ContractView, decision: AlertDecision, recipient: str) -> str | None:
        return (
            await self.session.execute(
                select(ContractNotification.id).where(
                    ContractNotification.contractId == view.id,
                    ContractNotification.type == decision.type,
                    ContractNotification.referenceDate == decision.reference_date,
                    ContractNotification.noticeDays == decision.notice_days,
                    ContractNotification.recipient == recipient,
                )
            )
        ).scalar_one_or_none()

    async def _milestone_processed(self, view: ContractView, decision: AlertDecision) -> bool:
        """Marco já tratado neste ciclo (algum envio que não seja SKIPPED)."""
        found = (
            await self.session.execute(
                select(ContractNotification.id)
                .where(
                    ContractNotification.contractId == view.id,
                    ContractNotification.type == decision.type,
                    ContractNotification.referenceDate == decision.reference_date,
                    ContractNotification.noticeDays == decision.notice_days,
                    ContractNotification.status != ContractNotificationStatus.SKIPPED,
                )
                .limit(1)
            )
        ).scalar_one_or_none()
        return found is not None

    async def _preview_new(self, view: ContractView, decision: AlertDecision) -> list[AlertItemOut]:
        if await self._milestone_processed(view, decision):
            return [_decision_item("already_notified", view, decision, recipient=None)]
        if not view.recipients:
            return [_decision_item("skipped", view, decision, recipient=None, error=view.recipients_problem)]
        return [_decision_item("would_send", view, decision, recipient=email) for email in view.recipients]

    async def _process_new(self, view: ContractView, decision: AlertDecision) -> list[AlertItemOut]:
        if await self._milestone_processed(view, decision):
            logger.info(
                "contract_alert.milestone_already_processed",
                contract_id=view.id,
                alert_type=decision.type.value,
                notice_days=decision.notice_days,
                reference_date=decision.reference_date.isoformat(),
            )
            return [_decision_item("already_notified", view, decision, recipient=None)]
        if not view.recipients:
            return [await self._skip_without_recipients(view, decision)]

        items: list[AlertItemOut] = []
        for recipient in view.recipients:
            try:
                items.append(await self._process_recipient(view, decision, recipient))
            except Exception as exc:  # noqa: BLE001 — um destinatário nunca impede os demais
                await self.session.rollback()
                logger.exception(
                    "contract_alert.recipient_failed",
                    contract_id=view.id,
                    alert_type=decision.type.value,
                    notice_days=decision.notice_days,
                    recipient=recipient,
                )
                items.append(
                    _decision_item("failed", view, decision, recipient=recipient, error=_error_text(exc))
                )
        return items

    def _row_values(self, view: ContractView, decision: AlertDecision, recipient: str) -> dict[str, object]:
        assert view.end_date is not None
        now = utcnow()
        return {
            "id": str(uuid.uuid4()),
            "contractId": view.id,
            "type": decision.type,
            "recipient": recipient,
            "referenceDate": decision.reference_date,
            "noticeDays": decision.notice_days,
            "contractEndDate": view.end_date,
            "notificationTeamId": view.team_id,
            "createdAt": now,
            "updatedAt": now,
        }

    async def _insert(self, values: dict[str, object]) -> str | None:
        inserted_id = (
            await self.session.execute(
                pg_insert(ContractNotification)
                .values(**values)
                .on_conflict_do_nothing(index_elements=_DEDUP_COLUMNS)
                .returning(ContractNotification.id)
            )
        ).scalar_one_or_none()
        await self.session.commit()
        return inserted_id

    async def _skip_without_recipients(self, view: ContractView, decision: AlertDecision) -> AlertItemOut:
        """Registra (uma vez por marco) que não havia para quem enviar; nada é enviado."""
        error = view.recipients_problem or "Sem destinatários ativos"
        values = self._row_values(view, decision, NO_RECIPIENT)
        values.update(status=ContractNotificationStatus.SKIPPED, attempts=0, error=error)
        inserted_id = await self._insert(values)
        if inserted_id is None:
            existing = await self._existing_id(view, decision, NO_RECIPIENT)
            return _decision_item(
                "already_notified", view, decision, recipient=None, notification_id=existing
            )
        logger.warning(
            "contract_alert.skipped_no_recipient",
            contract_id=view.id,
            contract_number=view.number,
            alert_type=decision.type.value,
            notice_days=decision.notice_days,
            team_id=view.team_id,
            notification_id=inserted_id,
            reason=error,
        )
        return _decision_item(
            "skipped", view, decision, recipient=None, notification_id=inserted_id, attempts=0, error=error
        )

    async def _process_recipient(
        self, view: ContractView, decision: AlertDecision, recipient: str
    ) -> AlertItemOut:
        assert view.end_date is not None
        values = self._row_values(view, decision, recipient)
        values.update(
            status=ContractNotificationStatus.PENDING,
            attempts=1,
            lastAttemptAt=values["createdAt"],
            provider=self.adapter.name if self.adapter else None,
        )
        inserted_id = await self._insert(values)
        if inserted_id is None:
            logger.info(
                "contract_alert.duplicate",
                contract_id=view.id,
                alert_type=decision.type.value,
                notice_days=decision.notice_days,
                reference_date=decision.reference_date.isoformat(),
                recipient=recipient,
            )
            existing = await self._existing_id(view, decision, recipient)
            return _decision_item(
                "already_notified", view, decision, recipient=recipient, notification_id=existing
            )

        status, error = await self._deliver(
            notification_id=inserted_id,
            alert_type=decision.type,
            view=view,
            end_date=view.end_date,
            days=decision.days_to_end,
            recipient=recipient,
            attempt=1,
        )
        return _decision_item(
            "sent" if status == ContractNotificationStatus.SENT else "failed",
            view,
            decision,
            recipient=recipient,
            notification_id=inserted_id,
            attempts=1,
            error=error,
        )

    # ------------------------------------------------------------------ envio

    async def _deliver(
        self,
        *,
        notification_id: str,
        alert_type: ContractNotificationType,
        view: ContractView,
        end_date: date,
        days: int,
        recipient: str,
        attempt: int,
    ) -> tuple[ContractNotificationStatus, str | None]:
        """Chama o adapter para uma linha já reivindicada (PENDING) e grava o resultado."""
        assert self.adapter is not None
        message = build_message(
            notification_id=notification_id,
            alert_type=alert_type,
            view=view,
            end_date=end_date,
            days=days,
            recipient=recipient,
        )
        error: str | None = None
        try:
            await self.adapter.send(message)
            status = ContractNotificationStatus.SENT
        except Exception as exc:  # noqa: BLE001 — falha de envio vira FAILED, nunca propaga
            status = ContractNotificationStatus.FAILED
            error = _error_text(exc)

        now = utcnow()
        await self.session.execute(
            update(ContractNotification)
            .where(
                ContractNotification.id == notification_id,
                ContractNotification.status == ContractNotificationStatus.PENDING,
            )
            .values(
                status=status,
                sentAt=now if status == ContractNotificationStatus.SENT else None,
                error=error,
                updatedAt=now,
            )
        )
        await self.session.commit()

        log = logger.info if status == ContractNotificationStatus.SENT else logger.warning
        log(
            "contract_alert.sent"
            if status == ContractNotificationStatus.SENT
            else "contract_alert.send_failed",
            notification_id=notification_id,
            contract_id=view.id,
            contract_number=view.number,
            alert_type=alert_type.value,
            recipient=recipient,
            attempt=attempt,
            provider=self.adapter.name,
            error=error,
        )
        return status, error

    # ------------------------------------------------------------------ retry

    async def _recover_stale_pending(self) -> None:
        cutoff = utcnow() - STALE_PENDING_AFTER
        recovered = (
            (
                await self.session.execute(
                    update(ContractNotification)
                    .where(
                        ContractNotification.status == ContractNotificationStatus.PENDING,
                        ContractNotification.lastAttemptAt < cutoff,
                    )
                    .values(
                        status=ContractNotificationStatus.FAILED,
                        error="Envio interrompido antes da confirmação do resultado",
                        updatedAt=utcnow(),
                    )
                    .returning(ContractNotification.id)
                )
            )
            .scalars()
            .all()
        )
        await self.session.commit()
        for notification_id in recovered:
            logger.warning("contract_alert.stale_pending_recovered", notification_id=notification_id)

    async def _load_candidate(
        self, notification_id: str
    ) -> tuple[ContractNotification, _RetryCandidate] | None:
        row = (
            await self.session.execute(
                select(ContractNotification)
                .options(
                    selectinload(ContractNotification.contract).selectinload(Contract.supplier),
                    selectinload(ContractNotification.contract).selectinload(Contract.sector),
                    selectinload(ContractNotification.contract)
                    .selectinload(Contract.notificationTeam)
                    .selectinload(NotificationTeam.members),
                )
                .where(ContractNotification.id == notification_id)
            )
        ).scalar_one_or_none()
        if row is None:
            return None
        view = _view(row.contract)
        return row, _RetryCandidate(
            id=row.id,
            type=row.type,
            recipient=row.recipient,
            reference_date=row.referenceDate,
            notice_days=row.noticeDays,
            contract_end_date=row.contractEndDate,
            attempts=row.attempts,
            view=view,
            still_member=row.recipient in view.recipients,
        )

    def _retry_item(
        self, action: str, candidate: _RetryCandidate, today: date, **extra: object
    ) -> AlertItemOut:
        return _item(
            action,
            candidate.view,
            alert_type=candidate.type,
            reference_date=candidate.reference_date,
            notice_days=candidate.notice_days,
            contract_end_date=candidate.contract_end_date,
            days_to_end=(candidate.contract_end_date - today).days,
            reason=f"Reenvio de alerta com falha (tentativas: {candidate.attempts} de {MAX_ATTEMPTS})",
            recipient=candidate.recipient,
            retry=True,
            notification_id=candidate.id,
            **extra,  # type: ignore[arg-type]
        )

    async def _retry_candidate(
        self, candidate: _RetryCandidate, *, today: date, dry_run: bool
    ) -> AlertItemOut:
        view = candidate.view
        if not still_same_cycle(
            notify=view.notify,
            finalized=view.finalized,
            end_date=view.end_date,
            cycle_end_date=candidate.contract_end_date,
        ):
            reason = "Contrato não é mais elegível (finalizado, notificação desativada ou vigência alterada)"
        elif not candidate.still_member:
            reason = "Destinatário não faz mais parte da equipe ativa do contrato"
        else:
            reason = ""
        if reason:
            if not dry_run:
                await self.session.execute(
                    update(ContractNotification)
                    .where(
                        ContractNotification.id == candidate.id,
                        ContractNotification.status == ContractNotificationStatus.FAILED,
                    )
                    .values(status=ContractNotificationStatus.SKIPPED, error=reason, updatedAt=utcnow())
                )
                await self.session.commit()
                logger.info("contract_alert.retry_skipped", notification_id=candidate.id, contract_id=view.id)
            return self._retry_item("skipped", candidate, today, attempts=candidate.attempts, error=reason)

        if dry_run:
            return self._retry_item("would_retry", candidate, today, attempts=candidate.attempts)

        # Reivindicação atômica: só um processo consegue passar FAILED -> PENDING.
        now = utcnow()
        attempt = (
            await self.session.execute(
                update(ContractNotification)
                .where(
                    ContractNotification.id == candidate.id,
                    ContractNotification.status == ContractNotificationStatus.FAILED,
                    ContractNotification.attempts < MAX_ATTEMPTS,
                )
                .values(
                    status=ContractNotificationStatus.PENDING,
                    attempts=ContractNotification.attempts + 1,
                    provider=self.adapter.name if self.adapter else None,
                    lastAttemptAt=now,
                    updatedAt=now,
                )
                .returning(ContractNotification.attempts)
            )
        ).scalar_one_or_none()
        await self.session.commit()
        if attempt is None:
            raise ConflictError("A notificação já foi reenviada por outro processo ou atingiu o limite")

        status, error = await self._deliver(
            notification_id=candidate.id,
            alert_type=candidate.type,
            view=view,
            end_date=candidate.contract_end_date,
            days=(candidate.contract_end_date - today).days,
            recipient=candidate.recipient,
            attempt=attempt,
        )
        return self._retry_item(
            "sent" if status == ContractNotificationStatus.SENT else "failed",
            candidate,
            today,
            attempts=attempt,
            error=error,
        )

    async def _retry_phase(
        self, result: AlertRunOut, *, today: date, dry_run: bool, exclude: set[str]
    ) -> None:
        if not dry_run:
            await self._recover_stale_pending()
        ids = (
            (
                await self.session.execute(
                    select(ContractNotification.id)
                    .where(
                        ContractNotification.status == ContractNotificationStatus.FAILED,
                        ContractNotification.attempts < MAX_ATTEMPTS,
                    )
                    .order_by(ContractNotification.createdAt.asc())
                )
            )
            .scalars()
            .all()
        )
        for notification_id in ids:
            # Falhas desta mesma execução só são retentadas na próxima.
            if notification_id in exclude:
                continue
            loaded = await self._load_candidate(notification_id)
            if loaded is None:
                continue
            _, candidate = loaded
            try:
                item = await self._retry_candidate(candidate, today=today, dry_run=dry_run)
            except ConflictError:
                continue
            except Exception as exc:  # noqa: BLE001
                await self.session.rollback()
                logger.exception("contract_alert.retry_failed", notification_id=notification_id)
                item = self._retry_item("failed", candidate, today, error=_error_text(exc))
            _count(result, item)
            result.items.append(item)

    async def resend(self, notification_id: str, *, today: date | None = None) -> AlertItemOut:
        """Reenvio manual (ADMIN): mesma linha, mesmas regras e limite do retry automático."""
        today = today or contracts_today()
        loaded = await self._load_candidate(notification_id)
        if loaded is None:
            raise NotFoundError("Notificação não encontrada")
        row, candidate = loaded
        if row.status != ContractNotificationStatus.FAILED:
            raise ConflictError("Somente notificações com falha (FAILED) podem ser reenviadas")
        if row.attempts >= MAX_ATTEMPTS:
            raise ConflictError(f"Limite de {MAX_ATTEMPTS} tentativas atingido para esta notificação")
        return await self._retry_candidate(candidate, today=today, dry_run=False)


async def preview_alerts(today: date | None = None) -> AlertRunOut:
    """Dry-run sem efeitos colaterais: sessão própria, transação READ ONLY, sem adapter."""
    async with SessionLocal() as session:
        await session.execute(text("SET TRANSACTION READ ONLY"))
        try:
            return await ContractAlertService(session).run(today=today, dry_run=True)
        finally:
            await session.rollback()


# ---------------------------------------------------------------------- consultas


def notification_out(
    row: ContractNotification, contract_number: str, supplier: str
) -> ContractNotificationOut:
    return ContractNotificationOut(
        id=row.id,
        contract_id=row.contractId,
        contract_number=contract_number,
        supplier=supplier,
        type=row.type,
        recipient=row.recipient,
        reference_date=row.referenceDate,
        notice_days=row.noticeDays,
        contract_end_date=row.contractEndDate,
        status=row.status,
        attempts=row.attempts,
        provider=row.provider,
        error=row.error,
        sent_at=row.sentAt,
        last_attempt_at=row.lastAttemptAt,
        created_at=row.createdAt,
        updated_at=row.updatedAt,
        can_retry=row.status == ContractNotificationStatus.FAILED and row.attempts < MAX_ATTEMPTS,
    )


def _notification_query() -> Select[tuple[ContractNotification, str, str]]:
    return (
        select(ContractNotification, Contract.contractNumber, Supplier.name)
        .join(Contract, Contract.id == ContractNotification.contractId)
        .join(Supplier, Supplier.id == Contract.supplierId)
    )


async def get_notification(session: AsyncSession, notification_id: str) -> ContractNotificationOut:
    row = (
        await session.execute(_notification_query().where(ContractNotification.id == notification_id))
    ).one_or_none()
    if row is None:
        raise NotFoundError("Notificação não encontrada")
    return notification_out(*row)


async def list_contract_notifications(
    session: AsyncSession, contract_id: str, actor: CurrentUser
) -> list[ContractNotificationOut]:
    sector_id = (await session.execute(select(Contract.sectorId).where(Contract.id == contract_id))).scalar()
    if sector_id is None:
        raise NotFoundError("Contrato não encontrado")
    assert_can_view(await sector_access(session, actor), sector_id)
    rows = (
        await session.execute(
            _notification_query()
            .where(ContractNotification.contractId == contract_id)
            .order_by(ContractNotification.createdAt.desc())
        )
    ).all()
    return [notification_out(*row) for row in rows]


async def list_notifications(
    session: AsyncSession,
    *,
    page: int,
    page_size: int,
    status: ContractNotificationStatus | None = None,
    alert_type: ContractNotificationType | None = None,
    contract_id: str | None = None,
    recipient: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> tuple[list[ContractNotificationOut], int]:
    filters = []
    if status is not None:
        filters.append(ContractNotification.status == status)
    if alert_type is not None:
        filters.append(ContractNotification.type == alert_type)
    if contract_id:
        filters.append(ContractNotification.contractId == contract_id)
    if recipient:
        filters.append(func.lower(ContractNotification.recipient).contains(recipient.strip().lower()))
    # Período pela data de criação do alerta (createdAt em UTC, fim inclusivo).
    if date_from is not None:
        filters.append(ContractNotification.createdAt >= datetime.combine(date_from, datetime.min.time()))
    if date_to is not None:
        filters.append(
            ContractNotification.createdAt
            < datetime.combine(date_to + timedelta(days=1), datetime.min.time())
        )

    total = (
        await session.execute(select(func.count()).select_from(ContractNotification).where(*filters))
    ).scalar_one()
    rows = (
        await session.execute(
            _notification_query()
            .where(*filters)
            .order_by(ContractNotification.createdAt.desc(), ContractNotification.id.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()
    return [notification_out(*row) for row in rows], int(total)


# ---------------------------------------------------------------------- sino

_ATTENTION_ORDER = {"Vencido": 0, "Atencao": 1, "SemData": 2}


def attention_message(alert: str, days: int | None) -> str:
    if alert == "Vencido":
        overdue = abs(days or 0)
        return "1 dia em atraso" if overdue == 1 else f"{overdue} dias em atraso"
    if alert == "SemData":
        return "Vigência não informada"
    if days == 0:
        return "Vence hoje"
    if days == 1:
        return "Vence amanhã"
    return f"Vence em {days} dias"


async def attention_contracts(session: AsyncSession, actor: CurrentUser) -> AttentionListOut:
    """Contratos visíveis ao usuário que exigem atenção (fonte de verdade do sino)."""
    contracts = [
        item
        for item in await contracts_service.list_contracts(session, actor)
        if item.alert in _ATTENTION_ORDER
    ]
    contracts.sort(
        key=lambda c: (_ATTENTION_ORDER[c.alert], c.days_to_end if c.days_to_end is not None else 10**6)
    )

    last: dict[str, LastNotificationOut] = {}
    if contracts:
        rows = (
            (
                await session.execute(
                    select(ContractNotification)
                    .where(ContractNotification.contractId.in_([c.id for c in contracts]))
                    .order_by(ContractNotification.createdAt.desc())
                )
            )
            .scalars()
            .all()
        )
        for row in rows:
            last.setdefault(
                row.contractId,
                LastNotificationOut(
                    type=row.type, status=row.status, created_at=row.createdAt, sent_at=row.sentAt
                ),
            )

    items = [
        AttentionContractOut(
            contract_id=c.id,
            contract_number=c.contract_number,
            supplier=c.supplier,
            sector_name=c.sector_name,
            unit=c.unit,
            alert=c.alert,
            end_date=c.end_date,
            days_to_end=c.days_to_end,
            message=attention_message(c.alert, c.days_to_end),
            notify=c.notify,
            last_notification=last.get(c.id),
        )
        for c in contracts
    ]
    return AttentionListOut(
        items=items,
        total=len(items),
        overdue=sum(1 for c in contracts if c.alert == "Vencido"),
        attention=sum(1 for c in contracts if c.alert == "Atencao"),
        without_date=sum(1 for c in contracts if c.alert == "SemData"),
    )


# ---------------------------------------------------------------------- modelo do e-mail


async def email_preview(
    session: AsyncSession,
    actor: CurrentUser,
    *,
    contract_id: str,
    alert_type: ContractNotificationType,
    notice_days: int | None = None,
    day: date | None = None,
) -> EmailPreviewOut:
    """Renderiza o e-mail de um marco para o contrato, sem enviar nem gravar.

    Dias exibidos: com `day` (prévia de um dia simulado), a distância real até o
    vencimento; sem ele, o valor do marco — 45/20/1 para antecedência, 0 no
    vencimento e o atraso atual (mínimo 7) para vencido.
    """
    contract = (
        await session.execute(_contract_loader().where(Contract.id == contract_id))
    ).scalar_one_or_none()
    if contract is None:
        raise NotFoundError("Contrato não encontrado")
    assert_can_view(await sector_access(session, actor), contract.sectorId)

    view = _view(contract)
    today = contracts_today()
    milestone = notice_days if notice_days in ADVANCE_MILESTONES else ADVANCE_MILESTONES[0]
    if day is not None and view.end_date is not None:
        days = (view.end_date - day).days
    elif alert_type == ContractNotificationType.ANTECEDENCIA:
        days = milestone
    elif alert_type == ContractNotificationType.VENCIMENTO:
        days = 0
    else:
        current = (view.end_date - today).days if view.end_date is not None else 0
        days = min(-7, current)
    end_date = view.end_date or (today + timedelta(days=days))

    message = build_message(
        notification_id="preview",
        alert_type=alert_type,
        view=view,
        end_date=end_date,
        days=days,
        recipient=view.recipients[0] if view.recipients else "",
    )
    return EmailPreviewOut(
        contract_id=view.id,
        contract_number=view.number,
        type=alert_type,
        notice_days=milestone if alert_type == ContractNotificationType.ANTECEDENCIA else 0,
        subject=message.subject,
        html=message.html_body,
        text=message.body,
        team_name=view.team_name,
        recipients=list(view.recipients),
        recipients_problem=view.recipients_problem,
        end_date=end_date,
        days_to_end=days,
        illustrative_date=view.end_date is None,
        actual_days_to_end=(view.end_date - today).days if view.end_date is not None else None,
        notify=view.notify,
    )
