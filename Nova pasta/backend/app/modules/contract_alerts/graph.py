"""Envio real dos alertas pelo Microsoft Graph (`POST /users/{remetente}/sendMail`).

Autenticação: client credentials do Entra ID (permissão de aplicativo
`Mail.Send`). O token é cacheado por processo até ~1 min antes de expirar e
renovado uma vez se o Graph responder 401. Erros viram `NotificationSendError`
com texto seguro (status, código do Graph e `request-id`), nunca com segredo
ou token; o motor grava esse texto em `ContractNotification.error` e cuida do
retry entre execuções.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import httpx
from pydantic import SecretStr

from app.core.config import Settings
from app.core.logging import get_logger
from app.modules.contract_alerts.adapter import AlertMessage, NotificationSendError

logger = get_logger("app.contract_alerts.graph")

GRAPH_AUTHORITY = "https://login.microsoftonline.com"
GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"
GRAPH_SCOPE = "https://graph.microsoft.com/.default"
_TOKEN_SAFETY_MARGIN_SECONDS = 60
_DETAIL_MAX_LENGTH = 300


@dataclass(slots=True)
class _CachedToken:
    value: str
    expires_at: float


# Cache por (tenant, client): a API cria um adapter por requisição e o job um por execução.
_token_cache: dict[tuple[str, str], _CachedToken] = {}


def clear_token_cache() -> None:
    _token_cache.clear()


def _safe_json(response: httpx.Response) -> dict[str, Any]:
    try:
        data = response.json()
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def _describe_graph_error(response: httpx.Response) -> str:
    error = _safe_json(response).get("error") or {}
    code = error.get("code", "desconhecido") if isinstance(error, dict) else "desconhecido"
    detail = (error.get("message", "") if isinstance(error, dict) else "")[:_DETAIL_MAX_LENGTH]
    kind = "temporária" if response.status_code == 429 or response.status_code >= 500 else "permanente"
    parts = [f"Microsoft Graph HTTP {response.status_code} ({kind}) {code}: {detail}".rstrip(": ")]
    if request_id := response.headers.get("request-id"):
        parts.append(f"request-id={request_id}")
    if retry_after := response.headers.get("Retry-After"):
        parts.append(f"retry-after={retry_after}s")
    return " | ".join(parts)


class GraphNotificationAdapter:
    name = "graph"

    def __init__(
        self,
        *,
        tenant_id: str,
        client_id: str,
        client_secret: SecretStr,
        sender: str,
        save_to_sent_items: bool = True,
        timeout_seconds: float = 20.0,
        redirect_to: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._tenant_id = tenant_id
        self._client_id = client_id
        self._client_secret = client_secret
        self._sender = sender
        self._save_to_sent_items = save_to_sent_items
        self._timeout = timeout_seconds
        self._redirect_to = redirect_to
        self._transport = transport

    @classmethod
    def from_settings(cls, settings: Settings) -> GraphNotificationAdapter:
        assert settings.graph_tenant_id and settings.graph_client_id
        assert settings.graph_client_secret and settings.graph_sender
        return cls(
            tenant_id=settings.graph_tenant_id,
            client_id=settings.graph_client_id,
            client_secret=settings.graph_client_secret,
            sender=settings.graph_sender,
            save_to_sent_items=settings.graph_save_to_sent_items,
            timeout_seconds=settings.graph_timeout_seconds,
            redirect_to=settings.notification_redirect_to,
        )

    # ------------------------------------------------------------------ token

    async def _token(self, client: httpx.AsyncClient, *, force_refresh: bool = False) -> str:
        key = (self._tenant_id, self._client_id)
        cached = _token_cache.get(key)
        if cached and not force_refresh and cached.expires_at > time.monotonic():
            return cached.value

        response = await client.post(
            f"{GRAPH_AUTHORITY}/{quote(self._tenant_id)}/oauth2/v2.0/token",
            data={
                "grant_type": "client_credentials",
                "client_id": self._client_id,
                "client_secret": self._client_secret.get_secret_value(),
                "scope": GRAPH_SCOPE,
            },
        )
        body = _safe_json(response)
        if response.status_code != 200 or "access_token" not in body:
            error = body.get("error", "desconhecido")
            description = str(body.get("error_description", "")).splitlines()[0:1]
            raise NotificationSendError(
                f"Falha ao obter token do Microsoft Graph (HTTP {response.status_code}) {error}: "
                f"{(description[0] if description else '')[:_DETAIL_MAX_LENGTH]}".rstrip(": ")
            )
        expires_in = int(body.get("expires_in", 3600))
        token = _CachedToken(
            value=str(body["access_token"]),
            expires_at=time.monotonic() + max(0, expires_in - _TOKEN_SAFETY_MARGIN_SECONDS),
        )
        _token_cache[key] = token
        return token.value

    # ------------------------------------------------------------------ envio

    def _payload(self, message: AlertMessage) -> dict[str, Any]:
        to, cc, subject = message.recipients, message.cc, message.subject
        if self._redirect_to:
            # Homologação: nunca atinge o destinatário real.
            subject = f"[REDIRECIONADO de {', '.join(to + cc)}] {subject}"
            to, cc = [self._redirect_to], []
        return {
            "message": {
                "subject": subject,
                "body": {
                    "contentType": "HTML" if message.html_body else "Text",
                    "content": message.html_body or message.body,
                },
                "toRecipients": [{"emailAddress": {"address": address}} for address in to],
                "ccRecipients": [{"emailAddress": {"address": address}} for address in cc],
            },
            "saveToSentItems": self._save_to_sent_items,
        }

    async def send(self, message: AlertMessage) -> None:
        url = f"{GRAPH_BASE_URL}/users/{quote(self._sender)}/sendMail"
        payload = self._payload(message)
        try:
            async with httpx.AsyncClient(timeout=self._timeout, transport=self._transport) as client:
                token = await self._token(client)
                response = await client.post(url, json=payload, headers={"Authorization": f"Bearer {token}"})
                if response.status_code == 401:
                    # Token revogado/expirado antes do previsto: renova uma única vez.
                    token = await self._token(client, force_refresh=True)
                    response = await client.post(
                        url, json=payload, headers={"Authorization": f"Bearer {token}"}
                    )
        except httpx.TimeoutException as exc:
            raise NotificationSendError(
                f"Tempo esgotado ao falar com o Microsoft Graph (temporária): {type(exc).__name__}"
            ) from exc
        except httpx.HTTPError as exc:
            raise NotificationSendError(
                f"Erro de rede ao falar com o Microsoft Graph (temporária): {type(exc).__name__}"
            ) from exc

        if response.status_code == 202:
            logger.info(
                "contract_alert.graph_accepted",
                notification_id=message.notification_id,
                contract_id=message.contract_id,
                alert_type=message.alert_type,
                recipients=[r["emailAddress"]["address"] for r in payload["message"]["toRecipients"]],
                redirected=bool(self._redirect_to),
                request_id=response.headers.get("request-id"),
            )
            return
        raise NotificationSendError(_describe_graph_error(response))
