"""GraphNotificationAdapter contra um Microsoft Graph simulado (httpx.MockTransport)."""

from __future__ import annotations

import json
from datetime import date

import httpx
import pytest
from pydantic import SecretStr, ValidationError

from app.core.config import Settings
from app.modules.contract_alerts.adapter import AlertMessage, NotificationSendError, get_notification_adapter
from app.modules.contract_alerts.graph import GraphNotificationAdapter, clear_token_cache
from app.modules.contract_alerts.templates import render_alert

SECRET = "super-secreto-nao-vazar"


class FakeGraph:
    """Responde /token e /sendMail; `send_statuses` define as respostas do sendMail em ordem."""

    def __init__(self, send_statuses: list[int], token_status: int = 200) -> None:
        self.send_statuses = list(send_statuses)
        self.token_status = token_status
        self.token_calls = 0
        self.sent: list[dict] = []
        self.auth_headers: list[str] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/oauth2/v2.0/token"):
            self.token_calls += 1
            if self.token_status != 200:
                return httpx.Response(
                    self.token_status,
                    json={
                        "error": "invalid_client",
                        "error_description": "AADSTS7000215: Invalid client secret.",
                    },
                )
            return httpx.Response(200, json={"access_token": f"token-{self.token_calls}", "expires_in": 3600})
        self.auth_headers.append(request.headers["Authorization"])
        status = self.send_statuses.pop(0)
        if status == 202:
            self.sent.append(json.loads(request.content))
            return httpx.Response(202, headers={"request-id": "req-ok"})
        return httpx.Response(
            status,
            headers={"request-id": "req-123", "Retry-After": "30"}
            if status == 429
            else {"request-id": "req-123"},
            json={
                "error": {
                    "code": "ErrorAccessDenied" if status == 403 else "TooManyRequests",
                    "message": "negado",
                }
            },
        )


def _adapter(graph: FakeGraph, **kwargs) -> GraphNotificationAdapter:
    clear_token_cache()
    return GraphNotificationAdapter(
        tenant_id="tenant",
        client_id="client",
        client_secret=SecretStr(SECRET),
        sender="contratos@empresa.com",
        transport=httpx.MockTransport(graph.handler),
        **kwargs,
    )


def _message(**overrides) -> AlertMessage:
    values = {
        "notification_id": "n1",
        "alert_type": "ANTECEDENCIA",
        "recipients": ["resp@empresa.com"],
        "subject": "Assunto",
        "body": "texto",
        "html_body": "<p>html</p>",
        "contract_id": "c1",
        "contract_number": "100",
        "supplier": "Fornecedor",
        "sector": "Obras",
        "unit": "LEM",
        "end_date": date(2026, 10, 21),
        "days_to_end": 20,
        "auto_renewal": False,
    }
    values.update(overrides)
    return AlertMessage(**values)


async def test_send_success_payload() -> None:
    graph = FakeGraph([202])
    await _adapter(graph).send(_message())
    [payload] = graph.sent
    assert payload["message"]["toRecipients"] == [{"emailAddress": {"address": "resp@empresa.com"}}]
    assert payload["message"]["body"] == {"contentType": "HTML", "content": "<p>html</p>"}
    assert payload["saveToSentItems"] is True
    assert graph.auth_headers == ["Bearer token-1"]


async def test_token_is_cached_between_sends() -> None:
    graph = FakeGraph([202, 202])
    adapter = _adapter(graph)
    await adapter.send(_message())
    await adapter.send(_message())
    assert graph.token_calls == 1


async def test_401_refreshes_token_once() -> None:
    graph = FakeGraph([401, 202])
    await _adapter(graph).send(_message())
    assert graph.token_calls == 2
    assert graph.auth_headers == ["Bearer token-1", "Bearer token-2"]


@pytest.mark.parametrize(
    ("status", "expected"),
    [(429, "temporária"), (503, "temporária"), (403, "permanente")],
)
async def test_graph_errors_are_safe_and_traceable(status: int, expected: str) -> None:
    graph = FakeGraph([status])
    with pytest.raises(NotificationSendError) as exc_info:
        await _adapter(graph).send(_message())
    text = str(exc_info.value)
    assert f"HTTP {status} ({expected})" in text
    assert "request-id=req-123" in text
    assert SECRET not in text and "token-1" not in text
    if status == 429:
        assert "retry-after=30s" in text


async def test_token_failure_is_safe() -> None:
    graph = FakeGraph([], token_status=401)
    with pytest.raises(NotificationSendError) as exc_info:
        await _adapter(graph).send(_message())
    assert "invalid_client" in str(exc_info.value)
    assert SECRET not in str(exc_info.value)


async def test_network_error_is_wrapped() -> None:
    def broken(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("sem rede")

    clear_token_cache()
    adapter = GraphNotificationAdapter(
        tenant_id="t",
        client_id="c",
        client_secret=SecretStr(SECRET),
        sender="s@e.com",
        transport=httpx.MockTransport(broken),
    )
    with pytest.raises(NotificationSendError, match="Erro de rede"):
        await adapter.send(_message())


async def test_redirect_never_reaches_real_recipient() -> None:
    graph = FakeGraph([202])
    await _adapter(graph, redirect_to="homolog@empresa.com").send(_message(cc=["gestor@empresa.com"]))
    message = graph.sent[0]["message"]
    assert message["toRecipients"] == [{"emailAddress": {"address": "homolog@empresa.com"}}]
    assert message["ccRecipients"] == []
    assert "resp@empresa.com" in message["subject"] and "gestor@empresa.com" in message["subject"]


def test_settings_require_graph_variables() -> None:
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            DATABASE_URL="postgresql://x/y_test", NOTIFICATION_PROVIDER="graph", GRAPH_CLIENT_SECRET=SECRET
        )
    text = str(exc_info.value)
    assert "GRAPH_TENANT_ID" in text and "GRAPH_SENDER" in text
    assert SECRET not in text


def test_settings_forbid_redirect_in_production() -> None:
    with pytest.raises(ValidationError, match="NOTIFICATION_REDIRECT_TO"):
        Settings(DATABASE_URL="postgresql://x/y", APP_ENV="production", NOTIFICATION_REDIRECT_TO="a@b.com")


def test_factory_builds_graph_adapter() -> None:
    settings = Settings(
        DATABASE_URL="postgresql://x/y_test",
        NOTIFICATION_PROVIDER="graph",
        GRAPH_TENANT_ID="t",
        GRAPH_CLIENT_ID="c",
        GRAPH_CLIENT_SECRET=SECRET,
        GRAPH_SENDER="contratos@empresa.com",
    )
    assert get_notification_adapter(settings).name == "graph"
    assert SECRET not in repr(settings)


def test_template_escapes_and_highlights_auto_renewal() -> None:
    rendered = render_alert(
        alert_type="VENCIDO",
        contract_number="100",
        supplier="<script>alert(1)</script> & Cia",
        service_description="Obra",
        sector="Obras",
        unit="",
        end_date=date(2026, 10, 1),
        days=-14,
        auto_renewal=True,
        criticality="ALTA",
        contract_url="https://hub.example.com/dashboard/contratos?contrato=abc",
    )
    assert "<script>" not in rendered.html
    assert "&lt;script&gt;" in rendered.html
    assert "Este contrato possui renovação automática." in rendered.html
    assert "Este contrato possui renovação automática." in rendered.text
    assert "está vencido há 14 dias" in rendered.subject
    assert "Alta" in rendered.html and "Abrir no Hub" in rendered.html
