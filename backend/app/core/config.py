"""Configuração da aplicação via variáveis de ambiente (Pydantic Settings).

Espelha as variáveis documentadas em `backend/.env.example`. Nenhum valor
padrão sensível é definido aqui — segredos são sempre exigidos via ambiente.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import AliasChoices, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

AppEnv = Literal["production", "test", "development"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # Sempre backend/.env, qualquer que seja o diretório de onde o processo foi iniciado
        # (variáveis de ambiente reais continuam tendo prioridade sobre o arquivo).
        env_file=str(Path(__file__).resolve().parents[2] / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        # Erros de configuração nunca ecoam os valores (URLs com senha, segredo do Graph).
        hide_input_in_errors=True,
    )

    app_env: AppEnv = Field(default="development", alias="APP_ENV")

    # Banco de dados. `database_url` é usada pela aplicação (pool assíncrono).
    # `migration_database_url` é opcional e, quando presente, é a URL usada
    # pelo Alembic — permite apontar migrations para uma conexão direta
    # sem trocar a URL utilizada pela aplicação.
    database_url: str = Field(alias="DATABASE_URL")
    migration_database_url: str | None = Field(default=None, alias="MIGRATION_DATABASE_URL")

    allow_test_db_migrations: bool = Field(default=False, alias="ALLOW_TEST_DB_MIGRATIONS")

    cors_origins: str = Field(default="http://localhost:3000", alias="CORS_ORIGINS")

    # Keycloak / OIDC
    keycloak_issuer: str | None = Field(default=None, alias="KEYCLOAK_ISSUER")
    keycloak_audience: str | None = Field(default=None, alias="KEYCLOAK_AUDIENCE")
    keycloak_jwks_url: str | None = Field(default=None, alias="KEYCLOAK_JWKS_URL")
    keycloak_allowed_algorithms: str = Field(default="RS256", alias="KEYCLOAK_ALLOWED_ALGORITHMS")
    jwks_cache_ttl_seconds: int = Field(default=3600, alias="JWKS_CACHE_TTL_SECONDS")

    # Autenticação de desenvolvimento (bypass controlado, nunca em produção).
    dev_auth_enabled: bool = Field(default=False, alias="DEV_AUTH_ENABLED")
    dev_auth_user_email: str = Field(default="dev@example.com", alias="DEV_AUTH_USER_EMAIL")

    # Autenticação: `keycloak` (SSO corporativo, oficial) ou `homologation` (login
    # temporário usuário/senha com duas contas fixas, para hospedar a homologação).
    # Em `homologation` o backend só aceita a sessão por cookie: Bearer/Keycloak e o
    # bypass de desenvolvimento ficam desligados.
    auth_provider: Literal["keycloak", "homologation"] = Field(default="keycloak", alias="AUTH_PROVIDER")
    homologation_viewer_username: str | None = Field(default=None, alias="HOMOLOGATION_VIEWER_USERNAME")
    homologation_viewer_password_hash: SecretStr | None = Field(
        default=None, alias="HOMOLOGATION_VIEWER_PASSWORD_HASH"
    )
    homologation_viewer_name: str = Field(
        default="Visualizador (homologação)", alias="HOMOLOGATION_VIEWER_NAME"
    )
    homologation_admin_username: str | None = Field(default=None, alias="HOMOLOGATION_ADMIN_USERNAME")
    homologation_admin_password_hash: SecretStr | None = Field(
        default=None, alias="HOMOLOGATION_ADMIN_PASSWORD_HASH"
    )
    homologation_admin_name: str = Field(
        default="Administrador (homologação)", alias="HOMOLOGATION_ADMIN_NAME"
    )
    auth_session_hours: int = Field(default=8, ge=1, le=72, alias="AUTH_SESSION_HOURS")
    auth_cookie_name: str = Field(default="gc_session", alias="AUTH_COOKIE_NAME")
    # Secure=true exige HTTPS; só pode ser false fora de produção (ex.: http://localhost).
    auth_cookie_secure: bool = Field(default=True, alias="AUTH_COOKIE_SECURE")
    auth_cookie_samesite: Literal["lax", "strict"] = Field(default="lax", alias="AUTH_COOKIE_SAMESITE")
    # Atrás de proxy confiável (ex.: o próprio Nuxt), usa X-Forwarded-For para o limite de tentativas.
    trust_proxy_headers: bool = Field(default=False, alias="TRUST_PROXY_HEADERS")

    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # Provedor dos alertas de vencimento por e-mail:
    #   log     — só registra (simulação; dev/teste);
    #   mailpit — SMTP local sem autenticação (homologação; captura as mensagens, não entrega);
    #   graph   — Microsoft Graph (envio corporativo real; único provider de produção).
    notification_provider: Literal["log", "mailpit", "graph"] = Field(
        default="log", alias="NOTIFICATION_PROVIDER"
    )
    # Dev/homologação: se definido, TODOS os alertas vão para este e-mail (o
    # destinatário original aparece no assunto). Proibido em produção.
    notification_redirect_to: str | None = Field(default=None, alias="NOTIFICATION_REDIRECT_TO")
    # URL pública do frontend, usada no link "Abrir no Hub" do e-mail (opcional).
    app_public_url: str | None = Field(default=None, alias="APP_PUBLIC_URL")

    # Microsoft Graph — registro de aplicativo no Entra ID com permissão de
    # aplicativo `Mail.Send` (idealmente restrita à caixa remetente por
    # Application Access Policy). O segredo nunca é logado.
    # Os nomes AZURE_* / GRAPH_SENDER_EMAIL também são aceitos.
    graph_tenant_id: str | None = Field(
        default=None, validation_alias=AliasChoices("GRAPH_TENANT_ID", "AZURE_TENANT_ID")
    )
    graph_client_id: str | None = Field(
        default=None, validation_alias=AliasChoices("GRAPH_CLIENT_ID", "AZURE_CLIENT_ID")
    )
    graph_client_secret: SecretStr | None = Field(
        default=None, validation_alias=AliasChoices("GRAPH_CLIENT_SECRET", "AZURE_CLIENT_SECRET")
    )
    # Caixa remetente (UPN ou e-mail), ex.: contratos@empresa.com.br.
    graph_sender: str | None = Field(
        default=None, validation_alias=AliasChoices("GRAPH_SENDER", "GRAPH_SENDER_EMAIL")
    )
    graph_save_to_sent_items: bool = Field(default=True, alias="GRAPH_SAVE_TO_SENT_ITEMS")
    graph_timeout_seconds: float = Field(default=20.0, alias="GRAPH_TIMEOUT_SECONDS")

    # SMTP local do Mailpit (homologação). Sem autenticação; não é usado pelo Graph.
    smtp_host: str = Field(default="127.0.0.1", alias="SMTP_HOST")
    smtp_port: int = Field(default=1025, alias="SMTP_PORT")
    smtp_use_tls: bool = Field(default=False, alias="SMTP_USE_TLS")
    smtp_sender_email: str = Field(default="gestao.contratos@hub.local", alias="SMTP_SENDER_EMAIL")
    smtp_timeout_seconds: float = Field(default=10.0, alias="SMTP_TIMEOUT_SECONDS")

    @model_validator(mode="after")
    def _validate_notifications(self) -> Settings:
        if self.notification_provider == "graph":
            required = {
                "GRAPH_TENANT_ID (ou AZURE_TENANT_ID)": self.graph_tenant_id,
                "GRAPH_CLIENT_ID (ou AZURE_CLIENT_ID)": self.graph_client_id,
                # SecretStr é sempre "truthy"; o que importa é o valor.
                "GRAPH_CLIENT_SECRET (ou AZURE_CLIENT_SECRET)": (
                    self.graph_client_secret.get_secret_value().strip() if self.graph_client_secret else ""
                ),
                "GRAPH_SENDER (ou GRAPH_SENDER_EMAIL)": self.graph_sender,
            }
            missing = [name for name, value in required.items() if not value]
            if missing:
                raise ValueError("NOTIFICATION_PROVIDER=graph exige as variáveis: " + ", ".join(missing))
        if self.notification_provider == "mailpit" and self.app_env == "production":
            raise ValueError(
                "NOTIFICATION_PROVIDER=mailpit é só para homologação local e não pode ser usado em produção"
            )
        if self.notification_redirect_to and self.app_env == "production":
            raise ValueError("NOTIFICATION_REDIRECT_TO não pode ser usado em produção")
        return self

    @model_validator(mode="after")
    def _validate_auth(self) -> Settings:
        if self.auth_provider == "homologation":

            def secret(value: SecretStr | None) -> str:
                return value.get_secret_value().strip() if value else ""

            required = {
                "HOMOLOGATION_VIEWER_USERNAME": (self.homologation_viewer_username or "").strip(),
                "HOMOLOGATION_VIEWER_PASSWORD_HASH": secret(self.homologation_viewer_password_hash),
                "HOMOLOGATION_ADMIN_USERNAME": (self.homologation_admin_username or "").strip(),
                "HOMOLOGATION_ADMIN_PASSWORD_HASH": secret(self.homologation_admin_password_hash),
            }
            missing = [name for name, value in required.items() if not value]
            if missing:
                raise ValueError("AUTH_PROVIDER=homologation exige as variáveis: " + ", ".join(missing))
            bad_hash = [
                name
                for name in ("HOMOLOGATION_VIEWER_PASSWORD_HASH", "HOMOLOGATION_ADMIN_PASSWORD_HASH")
                if not required[name].startswith("$argon2")
            ]
            if bad_hash:
                raise ValueError(
                    "Use hashes Argon2 (python scripts/hash_password.py), nunca a senha em texto: "
                    + ", ".join(bad_hash)
                )
            if (
                required["HOMOLOGATION_VIEWER_USERNAME"].lower()
                == required["HOMOLOGATION_ADMIN_USERNAME"].lower()
            ):
                raise ValueError("Os usuários de homologação VIEWER e ADMIN precisam ser diferentes")
        if self.app_env == "production" and not self.auth_cookie_secure:
            raise ValueError("AUTH_COOKIE_SECURE=false não é permitido em produção (o cookie exige HTTPS)")
        return self

    @field_validator("database_url", "migration_database_url")
    @classmethod
    def _require_asyncpg_scheme_for_app_url(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if value.startswith("postgres://"):
            value = "postgresql://" + value[len("postgres://") :]
        return value

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def keycloak_allowed_algorithms_list(self) -> list[str]:
        return [alg.strip() for alg in self.keycloak_allowed_algorithms.split(",") if alg.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def sqlalchemy_database_url(self) -> str:
        """URL assíncrona (asyncpg) usada pelo engine da aplicação."""
        return _to_asyncpg_url(self.database_url)

    @property
    def alembic_database_url(self) -> str:
        """URL síncrona (psycopg) usada pelas migrations Alembic."""
        url = self.migration_database_url or self.database_url
        return _to_sync_url(url)


def _asyncpg_compatible_query(query: str) -> str:
    """asyncpg aceita `ssl=<disable|allow|prefer|require|verify-ca|verify-full>`
    (mesmos valores de libpq), mas seu `connect()` não reconhece `sslmode`
    nem `channel_binding` como kwargs — provedores como Neon devolvem a
    `DATABASE_URL` no formato libpq (`sslmode=require&channel_binding=require`),
    que quebra a conexão assíncrona com `TypeError: unexpected keyword
    argument 'sslmode'`. Traduz `sslmode` -> `ssl` e descarta
    `channel_binding` (recurso de libpq, sem equivalente no asyncpg). A URL
    síncrona usada pelo Alembic (`_to_sync_url`, via psycopg) não passa por
    aqui e continua aceitando os parâmetros originais sem tradução."""
    pairs = parse_qsl(query, keep_blank_values=True)
    translated = [
        ("ssl", value) if key == "sslmode" else (key, value)
        for key, value in pairs
        if key != "channel_binding"
    ]
    return urlencode(translated)


def _to_asyncpg_url(url: str) -> str:
    if url.startswith("postgresql+asyncpg://") or url.startswith("sqlite+aiosqlite://"):
        return url
    if url.startswith("postgresql://"):
        async_url = "postgresql+asyncpg://" + url[len("postgresql://") :]
        parts = urlsplit(async_url)
        return urlunsplit(parts._replace(query=_asyncpg_compatible_query(parts.query)))
    if url.startswith("sqlite://"):
        return "sqlite+aiosqlite://" + url[len("sqlite://") :]
    return url


def _to_sync_url(url: str) -> str:
    if url.startswith("postgresql+asyncpg://"):
        return "postgresql+psycopg://" + url[len("postgresql+asyncpg://") :]
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://") :]
    return url


@lru_cache
def get_settings() -> Settings:
    return Settings()
