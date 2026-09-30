"""Envio de homologação local via Mailpit (SMTP sem autenticação).

O Mailpit captura as mensagens numa caixa local (interface em
http://localhost:8025) e **não entrega nada para a internet**. Serve para
validar o funcionamento e a aparência dos alertas enquanto o Microsoft Graph
não está disponível — não substitui a homologação final no Graph.

Recebe exatamente o mesmo `AlertMessage` que o `GraphNotificationAdapter`
(montado por `service.build_message`): o que é homologado aqui é o conteúdo que
o Graph entregará. Nunca é aceito em produção (validação em `Settings`).
"""

from __future__ import annotations

import asyncio
import smtplib
from email.message import EmailMessage
from email.utils import formatdate, make_msgid

from app.core.config import Settings
from app.core.logging import get_logger
from app.modules.contract_alerts.adapter import AlertMessage, NotificationSendError

logger = get_logger("app.contract_alerts.mailpit")


class MailpitNotificationAdapter:
    name = "mailpit"

    def __init__(
        self,
        *,
        host: str,
        port: int,
        sender: str,
        use_tls: bool = False,
        timeout_seconds: float = 10.0,
        redirect_to: str | None = None,
    ) -> None:
        self._host = host
        self._port = port
        self._sender = sender
        self._use_tls = use_tls
        self._timeout = timeout_seconds
        self._redirect_to = redirect_to

    @classmethod
    def from_settings(cls, settings: Settings) -> MailpitNotificationAdapter:
        return cls(
            host=settings.smtp_host,
            port=settings.smtp_port,
            sender=settings.smtp_sender_email,
            use_tls=settings.smtp_use_tls,
            timeout_seconds=settings.smtp_timeout_seconds,
            redirect_to=settings.notification_redirect_to,
        )

    def build_email(self, message: AlertMessage) -> EmailMessage:
        to, cc, subject = message.recipients, message.cc, message.subject
        if self._redirect_to:
            subject = f"[REDIRECIONADO de {', '.join(to + cc)}] {subject}"
            to, cc = [self._redirect_to], []
        email = EmailMessage()
        email["From"] = self._sender
        email["To"] = ", ".join(to)
        if cc:
            email["Cc"] = ", ".join(cc)
        email["Subject"] = subject
        email["Date"] = formatdate(localtime=True)
        email["Message-ID"] = make_msgid(domain="hub.local")
        # Rastreabilidade: permite achar a ContractNotification a partir da mensagem capturada.
        email["X-Hub-Notification-Id"] = message.notification_id
        email["X-Hub-Contract-Number"] = message.contract_number
        email["X-Hub-Alert-Type"] = message.alert_type
        email.set_content(message.body)
        if message.html_body:
            email.add_alternative(message.html_body, subtype="html")
        return email

    def _send_sync(self, email: EmailMessage) -> None:
        with smtplib.SMTP(self._host, self._port, timeout=self._timeout) as smtp:
            if self._use_tls:
                smtp.starttls()
            smtp.send_message(email)

    async def send(self, message: AlertMessage) -> None:
        email = self.build_email(message)
        try:
            await asyncio.to_thread(self._send_sync, email)
        except (OSError, smtplib.SMTPException) as exc:
            raise NotificationSendError(
                f"SMTP de homologação (Mailpit) {self._host}:{self._port} "
                "indisponível ou recusou a mensagem: "
                f"{type(exc).__name__}"
            ) from exc
        logger.info(
            "contract_alert.mailpit_captured",
            notification_id=message.notification_id,
            contract_id=message.contract_id,
            alert_type=message.alert_type,
            recipients=email["To"],
            redirected=bool(self._redirect_to),
        )
