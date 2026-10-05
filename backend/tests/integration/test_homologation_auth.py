"""Login temporário de homologação (AUTH_PROVIDER=homologation), contra Postgres real."""

from __future__ import annotations

from datetime import timedelta

import pytest
from argon2 import PasswordHasher
from pydantic import SecretStr, ValidationError
from sqlalchemy import select, update

from app.core.config import Settings, get_settings
from app.core.homologation_auth import login_rate_limiter
from app.main import app as fastapi_app
from app.models.common import utcnow
from app.models.contracts import Sector, Supplier, UserSectorPermission
from app.models.user import Session as UserSession
from app.models.user import User

VIEWER_PASSWORD = "senha-viewer-de-teste-123"
ADMIN_PASSWORD = "senha-admin-de-teste-456"
_hasher = PasswordHasher(time_cost=1, memory_cost=8192, parallelism=1)
VIEWER_HASH = _hasher.hash(VIEWER_PASSWORD)
ADMIN_HASH = _hasher.hash(ADMIN_PASSWORD)


def homologation_settings(**overrides) -> Settings:
    values = {
        "auth_provider": "homologation",
        "homologation_viewer_username": "visualizador",
        "homologation_viewer_password_hash": SecretStr(VIEWER_HASH),
        "homologation_admin_username": "administrador",
        "homologation_admin_password_hash": SecretStr(ADMIN_HASH),
        # O cliente de teste usa http://; Secure=true é verificado à parte.
        "auth_cookie_secure": False,
    }
    values.update(overrides)
    return get_settings().model_copy(update=values)


@pytest.fixture
def homologation():
    settings = homologation_settings()
    fastapi_app.dependency_overrides[get_settings] = lambda: settings
    login_rate_limiter.reset()
    yield settings
    fastapi_app.dependency_overrides.pop(get_settings, None)
    login_rate_limiter.reset()


async def _login(client, username: str, password: str):
    return await client.post("/api/v1/auth/login", json={"username": username, "password": password})


async def test_viewer_login_session_and_me(client, homologation) -> None:
    response = await _login(client, "visualizador", VIEWER_PASSWORD)
    assert response.status_code == 200
    body = response.json()
    assert (body["role"], body["username"], body["name"]) == (
        "VIEWER",
        "visualizador",
        "Visualizador (homologação)",
    )
    assert "passwordHash" not in response.text and VIEWER_HASH not in response.text

    cookie = response.headers["set-cookie"]
    assert cookie.startswith("gc_session=")
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie
    assert "Max-Age=28800" in cookie  # 8 horas
    assert "Path=/" in cookie

    me = await client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert (me.json()["role"], me.json()["username"]) == ("VIEWER", "visualizador")
    assert me.json()["permissions"] == ["contracts:view"]


async def test_admin_login(client, homologation) -> None:
    response = await _login(client, "Administrador", ADMIN_PASSWORD)  # usuário não diferencia maiúsculas
    assert response.status_code == 200
    assert response.json()["role"] == "ADMIN"
    assert (await client.get("/api/v1/usuarios")).status_code == 200
    assert (await client.get("/api/v1/notificacoes-contratos")).status_code == 200
    assert (await client.get("/api/v1/equipes-notificacao")).status_code == 200


async def test_invalid_credentials_are_generic(client, homologation, db_session) -> None:
    wrong_password = await _login(client, "visualizador", "senha-errada-qualquer")
    unknown_user = await _login(client, "nao-existe", VIEWER_PASSWORD)
    assert wrong_password.status_code == unknown_user.status_code == 401
    assert wrong_password.json() == unknown_user.json() == {"error": "Usuário ou senha inválidos."}
    assert "set-cookie" not in wrong_password.headers
    sessions = (await db_session.execute(select(UserSession))).scalars().all()
    assert sessions == []


async def test_bearer_and_dev_bypass_are_ignored_in_homologation(client, homologation) -> None:
    assert (await client.get("/api/v1/auth/me")).status_code == 401
    # O bypass de desenvolvimento e tokens Bearer não autenticam neste modo.
    response = await client.get("/api/v1/auth/me", headers={"Authorization": "Bearer dev-admin"})
    assert response.status_code == 401
    assert (
        await client.get("/api/v1/contratos", headers={"Authorization": "Bearer dev-admin"})
    ).status_code == 401


async def test_expired_session_requires_new_login(client, homologation, db_session) -> None:
    await _login(client, "visualizador", VIEWER_PASSWORD)
    assert (await client.get("/api/v1/auth/me")).status_code == 200
    await db_session.execute(update(UserSession).values(expiresAt=utcnow() - timedelta(minutes=1)))
    await db_session.commit()
    assert (await client.get("/api/v1/auth/me")).status_code == 401


async def test_session_token_is_stored_hashed(client, homologation, db_session) -> None:
    response = await _login(client, "visualizador", VIEWER_PASSWORD)
    token = response.cookies.get("gc_session")
    [stored] = (await db_session.execute(select(UserSession))).scalars().all()
    assert token and stored.token != token and len(stored.token) == 64


async def test_logout_invalidates_session(client, homologation, db_session) -> None:
    response = await _login(client, "administrador", ADMIN_PASSWORD)
    old_token = response.cookies.get("gc_session")
    logout = await client.post("/api/v1/auth/logout")
    assert logout.status_code == 204
    assert 'gc_session=""' in logout.headers["set-cookie"] or "Max-Age=0" in logout.headers["set-cookie"]
    assert (await db_session.execute(select(UserSession))).scalars().all() == []
    # Reusar o token antigo não funciona mais.
    client.cookies.set("gc_session", old_token)
    assert (await client.get("/api/v1/auth/me")).status_code == 401


async def test_viewer_is_blocked_from_admin_actions(client, homologation, db_session) -> None:
    sector = Sector(slug="projetos-arquitetura", name="Projetos e Arquitetura", acronym="P&A")
    db_session.add_all([sector, Supplier(name="Fornecedor X")])
    await db_session.commit()
    await _login(client, "visualizador", VIEWER_PASSWORD)
    viewer = (
        await db_session.execute(select(User).where(User.externalUserId == "visualizador"))
    ).scalar_one()
    db_session.add(UserSectorPermission(userId=viewer.id, sectorId=sector.id, canView=True, canEdit=False))
    await db_session.commit()

    assert (await client.get("/api/v1/contratos")).status_code == 200
    assert (await client.get("/api/v1/contratos/resumo")).status_code == 200
    for method, url, body in (
        ("POST", "/api/v1/contratos", {"sectorId": sector.id, "supplier": "X", "contractNumber": "1"}),
        ("GET", "/api/v1/usuarios", None),
        ("GET", "/api/v1/equipes-notificacao", None),
        ("POST", "/api/v1/equipes-notificacao", {"name": "x", "sectorId": sector.id}),
        ("POST", "/api/v1/alertas/executar?dry_run=false", None),
        ("GET", "/api/v1/alertas/previa", None),
        ("GET", "/api/v1/notificacoes-contratos", None),
        ("PUT", f"/api/v1/usuarios/{viewer.id}/setores", {"items": []}),
        ("GET", "/api/v1/auditoria", None),
    ):
        response = await client.request(method, url, json=body)
        assert response.status_code == 403, (method, url, response.status_code)


async def test_login_rate_limit(client, homologation) -> None:
    for _ in range(5):
        assert (await _login(client, "visualizador", "errada-errada")).status_code == 401
    blocked = await _login(client, "visualizador", VIEWER_PASSWORD)  # nem a senha certa passa
    assert blocked.status_code == 429
    assert int(blocked.headers["retry-after"]) > 0
    # Outro usuário do mesmo IP ainda pode entrar (limite por usuário não derruba todos).
    assert (await _login(client, "administrador", ADMIN_PASSWORD)).status_code == 200


async def test_removed_account_loses_session(client, homologation) -> None:
    await _login(client, "visualizador", VIEWER_PASSWORD)
    renamed = homologation_settings(homologation_viewer_username="outro-visualizador")
    fastapi_app.dependency_overrides[get_settings] = lambda: renamed
    assert (await client.get("/api/v1/auth/me")).status_code == 401


def test_secure_cookie_flag(homologation) -> None:
    assert homologation_settings(auth_cookie_secure=True).auth_cookie_secure is True


async def test_secure_cookie_is_emitted(client) -> None:
    settings = homologation_settings(auth_cookie_secure=True)
    fastapi_app.dependency_overrides[get_settings] = lambda: settings
    login_rate_limiter.reset()
    try:
        response = await _login(client, "visualizador", VIEWER_PASSWORD)
        assert "Secure" in response.headers["set-cookie"]
    finally:
        fastapi_app.dependency_overrides.pop(get_settings, None)


def test_incomplete_or_insecure_configuration_is_rejected() -> None:
    # _env_file=None: o teste valida só o que recebe; sem isso o backend/.env local (que pode
    # usar AUTH_PROVIDER=homologation com as contas preenchidas) completaria a configuração.
    base = {"DATABASE_URL": "postgresql://x/y_test", "AUTH_PROVIDER": "homologation"}
    with pytest.raises(ValidationError) as missing:
        Settings(_env_file=None, **base)
    assert "HOMOLOGATION_VIEWER_PASSWORD_HASH" in str(missing.value)

    complete = {
        **base,
        "HOMOLOGATION_VIEWER_USERNAME": "visualizador",
        "HOMOLOGATION_VIEWER_PASSWORD_HASH": VIEWER_HASH,
        "HOMOLOGATION_ADMIN_USERNAME": "administrador",
        "HOMOLOGATION_ADMIN_PASSWORD_HASH": ADMIN_HASH,
    }
    assert Settings(_env_file=None, **complete).auth_provider == "homologation"
    with pytest.raises(ValidationError, match="Argon2"):
        Settings(_env_file=None, **{**complete, "HOMOLOGATION_ADMIN_PASSWORD_HASH": "senha-em-texto"})
    with pytest.raises(ValidationError, match="diferentes"):
        Settings(_env_file=None, **{**complete, "HOMOLOGATION_ADMIN_USERNAME": "Visualizador"})
    with pytest.raises(ValidationError, match="AUTH_COOKIE_SECURE"):
        Settings(_env_file=None, **{**complete, "APP_ENV": "production", "AUTH_COOKIE_SECURE": False})
    # Nenhum erro ecoa a senha/hash.
    with pytest.raises(ValidationError) as exc:
        Settings(_env_file=None, **{**complete, "HOMOLOGATION_ADMIN_PASSWORD_HASH": "segredo-em-texto"})
    assert "segredo-em-texto" not in str(exc.value)


async def test_keycloak_provider_is_preserved(client, auth_header) -> None:
    # Configuração padrão dos testes: keycloak + bypass de desenvolvimento.
    assert (await client.get("/api/v1/auth/provider")).json() == {"provider": "keycloak"}
    assert (await _login(client, "visualizador", VIEWER_PASSWORD)).status_code == 404
    assert (await client.post("/api/v1/auth/logout")).status_code == 404
    me = await client.get("/api/v1/auth/me", headers=auth_header("ADMIN"))
    assert me.status_code == 200 and me.json()["role"] == "ADMIN"


async def test_bootstrap_grants_viewer_view_only(homologation, db_session, monkeypatch) -> None:
    import scripts.bootstrap_homologation_users as bootstrap

    db_session.add_all(
        [
            Sector(slug="projetos-arquitetura", name="Projetos e Arquitetura", acronym="P&A"),
            Sector(slug="suprimentos", name="Suprimentos", acronym="SUP"),
        ]
    )
    await db_session.commit()
    monkeypatch.setattr(bootstrap, "get_settings", lambda: homologation)

    report = await bootstrap.bootstrap(["all"], dry_run=False)
    assert any("usuário ADMIN: administrador" in line for line in report)
    rows = (
        await db_session.execute(
            select(User.externalUserId, UserSectorPermission.canView, UserSectorPermission.canEdit).join(
                User, User.id == UserSectorPermission.userId
            )
        )
    ).all()
    assert sorted(rows) == [("visualizador", True, False), ("visualizador", True, False)]
    # Idempotente.
    await bootstrap.bootstrap(["all"], dry_run=False)
    assert len((await db_session.execute(select(UserSectorPermission))).scalars().all()) == 2
