from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from app.models.contracts import ContractNotificationStatus, ContractNotificationType
from app.shared.schema import CamelModel

# would_send / would_retry: só no dry-run. already_notified: a chave de
# deduplicação já existe (dry-run) ou o INSERT caiu no conflito (execução real).
AlertAction = Literal["would_send", "would_retry", "already_notified", "sent", "failed", "skipped"]


class AlertItemOut(CamelModel):
    action: AlertAction
    retry: bool = False
    contract_id: str
    contract_number: str
    supplier: str
    sector_name: str
    unit: str
    type: ContractNotificationType
    recipient: str | None
    contract_end_date: date
    reference_date: date
    notice_days: int
    days_to_end: int
    reason: str
    auto_renewal: bool = False
    notification_id: str | None = None
    attempts: int | None = None
    error: str | None = None


class AlertRunOut(CamelModel):
    today: date
    dry_run: bool
    provider: str | None
    contracts_analyzed: int = 0
    eligible: int = 0
    sent: int = 0
    duplicates: int = 0
    retried: int = 0
    failed: int = 0
    skipped: int = 0
    items: list[AlertItemOut] = []


class ContractNotificationOut(CamelModel):
    id: str
    contract_id: str
    contract_number: str
    supplier: str
    type: ContractNotificationType
    recipient: str
    reference_date: date
    notice_days: int
    contract_end_date: date
    status: ContractNotificationStatus
    attempts: int
    # "log" = só registrado (dev); "graph" = e-mail enviado de verdade.
    provider: str | None
    error: str | None
    sent_at: datetime | None
    last_attempt_at: datetime | None
    created_at: datetime
    updated_at: datetime
    can_retry: bool


class LastNotificationOut(CamelModel):
    type: ContractNotificationType
    status: ContractNotificationStatus
    created_at: datetime
    sent_at: datetime | None


class AttentionContractOut(CamelModel):
    """Item do sino: contrato que exige atenção, com a mensagem já calculada no backend."""

    contract_id: str
    contract_number: str
    supplier: str
    sector_name: str
    unit: str
    alert: str
    end_date: date | None
    days_to_end: int | None
    message: str
    notify: bool
    last_notification: LastNotificationOut | None = None


class AttentionListOut(CamelModel):
    items: list[AttentionContractOut]
    total: int
    overdue: int
    attention: int
    without_date: int


class PaginationOut(CamelModel):
    page: int
    page_size: int
    total: int
    total_pages: int


class ContractNotificationListOut(CamelModel):
    items: list[ContractNotificationOut]
    pagination: PaginationOut | None = None


class EmailPreviewOut(CamelModel):
    """E-mail montado com o mesmo template do envio real — nada é enviado nem gravado."""

    contract_id: str
    contract_number: str
    type: ContractNotificationType
    # Marco de antecedência exibido (45/20/1); 0 para vencimento/vencido.
    notice_days: int
    subject: str
    html: str
    text: str
    team_name: str | None
    # Membros ativos da equipe: cada um recebe o próprio e-mail (sem ver os demais).
    recipients: list[str]
    recipients_problem: str | None
    end_date: date
    days_to_end: int
    # True quando o contrato não tem fim de vigência e a data exibida é ilustrativa.
    illustrative_date: bool
    # Dias reais até o vencimento hoje (None sem data); diferem de days_to_end quando o texto é ilustrativo.
    actual_days_to_end: int | None
    notify: bool
