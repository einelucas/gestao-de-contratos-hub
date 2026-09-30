"""MailpitNotificationAdapter com servidor SMTP simulado (não precisa do Mailpit rodando)."""

from __future__ import annotations

import smtplib
from datetime import date

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.modules.contract_alerts.adapter import AlertMessage, NotificationSendError, get_notification_adapter
from app.modules.contract_alerts.mailpit import MailpitNotificationAdapter


class FakeSMTP:
    """Substitui smtplib.SMTP e guarda as mensagens enviadas."""

    sent: list = []
    fail: bool = False

    def __init__(self, host: str, port: int, timeout: float) -> None:
        if FakeSMTP.fail:
            raise ConnectionRefusedError("sem servidor")
        self.host, self.port = host, port

    def __enter__(self) -> FakeSMTP:
        return self

    def __exit__(self, *exc) -> None:
        return None

    def starttls(self) -> None:
        raise AssertionError("Mailpit local não usa TLS")

    def send_message(self, email) -> None:
        FakeSMTP.sent.append((self.host, self.port, email))


@pytest.fixture(autouse=True)
def fake_smtp(monkeypatch):
    FakeSMTP.sent = []
    FakeSMTP.fail = False
    monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)
    return FakeSMTP


def _message(**overrides) -> AlertMessage:
    values = {
        "notification_id": "n1",
        "alert_type": "ANTECEDENCIA",
        "recipients": ["teste1@hub.local"],
        "subject": "Contrato 100 vence em 45 dias",
        "body": "texto simples",
        "html_body": "<p>html</p>",
        "contract_id": "c1",
        "contract_number": "100",
        "supplier": "Fornecedor",
        "sector": "TESTE",
        "unit": "LEM",
        "end_date": date(2026, 11, 14),
        "days_to_end": 45,
        "auto_renewal": False,
    }
    values.update(overrides)
    return AlertMessage(**values)


def _adapter(**kwargs) -> MailpitNotificationAdapter:
    return MailpitNotificationAdapter(
        host="127.0.0.1", port=1025, sender="gestao.contratos@hub.local", **kwargs
    )


async def test_sends_one_message_with_text_and_html(fake_smtp) -> None:
    await _adapter().send(_message())
    [(host, port, email)] = fake_smtp.sent
    assert (host, port) == ("127.0.0.1", 1025)
    assert email["From"] == "gestao.contratos@hub.local"
    assert email["To"] == "teste1@hub.local"
    assert email["Cc"] is None
    assert email["Subject"] == "Contrato 100 vence em 45 dias"
    assert email["X-Hub-Notification-Id"] == "n1"
    assert email["X-Hub-Contract-Number"] == "100"
    parts = {part.get_content_type(): part.get_content().strip() for part in email.iter_parts()}
    assert parts == {"text/plain": "texto simples", "text/html": "<p>html</p>"}


async def test_redirect_goes_only_to_test_mailbox(fake_smtp) -> None:
    await _adapter(redirect_to="caixa@hub.local").send(_message(cc=["outro@hub.local"]))
    [(_, _, email)] = fake_smtp.sent
    assert email["To"] == "caixa@hub.local"
    assert email["Cc"] is None
    assert "teste1@hub.local" in email["Subject"] and "outro@hub.local" in email["Subject"]


async def test_unavailable_server_becomes_send_error(fake_smtp) -> None:
    fake_smtp.fail = True
    with pytest.raises(NotificationSendError, match="Mailpit"):
        await _adapter().send(_message())


def test_factory_and_settings() -> None:
    settings = Settings(DATABASE_URL="postgresql://x/y_test", NOTIFICATION_PROVIDER="mailpit")
    adapter = get_notification_adapter(settings)
    assert adapter.name == "mailpit"  # sem exigir nenhuma variável do Graph
    assert (settings.smtp_host, settings.smtp_port, settings.smtp_use_tls) == ("127.0.0.1", 1025, False)
    assert settings.smtp_sender_email == "gestao.contratos@hub.local"

    with pytest.raises(ValidationError, match="produção"):
        Settings(DATABASE_URL="postgresql://x/y", APP_ENV="production", NOTIFICATION_PROVIDER="mailpit")


def test_graph_accepts_azure_variable_names() -> None:
    settings = Settings(
        DATABASE_URL="postgresql://x/y_test",
        NOTIFICATION_PROVIDER="graph",
        AZURE_TENANT_ID="t",
        AZURE_CLIENT_ID="c",
        AZURE_CLIENT_SECRET="s",
        GRAPH_SENDER_EMAIL="contratos@empresa.com",
    )
    assert get_notification_adapter(settings).name == "graph"
    assert (settings.graph_tenant_id, settings.graph_sender) == ("t", "contratos@empresa.com")
