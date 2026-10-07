"""Adapters de envio dos alertas de vencimento.

O motor de alertas só conhece o `NotificationAdapter` Protocol — nunca Graph,
SMTP ou log. Mesmo desenho do módulo de notificações do Painel de
Equipamentos: trocar o provedor é implementar o Protocol e registrar na
fábrica abaixo, escolhida por `NOTIFICATION_PROVIDER`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Protocol

from app.core.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger("app.contract_alerts.adapter")


@dataclass(frozen=True, slots=True)
class AlertMessage:
    """Conteúdo de um alerta: texto simples (`body`), HTML (`html_body`) e os
    campos estruturados usados para montá-los e para os logs."""

    notification_id: str
    alert_type: str
    recipients: list[str]
    subject: str
    body: str
    contract_id: str
    contract_number: str
    supplier: str
    sector: str
    unit: str
    end_date: date
    days_to_end: int
    auto_renewal: bool
    html_body: str = ""
    service_description: str = ""
    criticality: str | None = None
    contract_url: str | None = None
    # Preparado para cópia futura (ex.: gestor do setor); vazio por enquanto.
    cc: list[str] = field(default_factory=list)


class NotificationSendError(Exception):
    """Falha de envio com mensagem segura (sem segredos) para gravar em `error`."""


class NotificationAdapter(Protocol):
    name: str

    async def send(self, message: AlertMessage) -> None:
        """Envia a mensagem. Qualquer exceção é tratada pelo motor como falha de envio."""
        ...


class LogNotificationAdapter:
    """DEV/teste: registra o envio no log estruturado, nunca fala com um provedor real."""

    name = "log"

    async def send(self, message: AlertMessage) -> None:
        logger.info(
            "contract_alert.send",
            provider=self.name,
            notification_id=message.notification_id,
            alert_type=message.alert_type,
            contract_id=message.contract_id,
            contract_number=message.contract_number,
            supplier=message.supplier,
            recipients=message.recipients,
            cc=message.cc,
            end_date=message.end_date.isoformat(),
            days_to_end=message.days_to_end,
            auto_renewal=message.auto_renewal,
            subject=message.subject,
        )


def get_notification_adapter(settings: Settings | None = None) -> NotificationAdapter:
    settings = settings or get_settings()
    if settings.notification_provider == "log":
        return LogNotificationAdapter()
    if settings.notification_provider == "mailpit":
        from app.modules.contract_alerts.mailpit import MailpitNotificationAdapter

        return MailpitNotificationAdapter.from_settings(settings)
    if settings.notification_provider == "graph":
        from app.modules.contract_alerts.graph import GraphNotificationAdapter

        return GraphNotificationAdapter.from_settings(settings)
    raise RuntimeError(f"Provedor de notificação sem adapter: {settings.notification_provider!r}")
