"""Fixtures de integração com PostgreSQL dedicado a testes.

A suíte carrega `.env.test` antes da aplicação e só permite limpeza em banco
cujo nome termine em `_test`. Nunca aponte `.env.test` para dados reais.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from pathlib import Path

import pytest
import pytest_asyncio
from dotenv import load_dotenv
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

_ENV_TEST_PATH = Path(__file__).resolve().parent.parent / ".env.test"
if not _ENV_TEST_PATH.is_file():
    raise RuntimeError(
        f"'{_ENV_TEST_PATH}' não encontrado. A suíte de testes recusa-se a "
        "rodar sem um banco de dados dedicado a testes — copie "
        "'.env.test.example' para '.env.test' e ajuste DATABASE_URL para um "
        "banco separado do usado por 'backend/.env'. NUNCA aponte os dois "
        "para o mesmo banco: a suíte trunca todas as tabelas a cada teste."
    )
load_dotenv(_ENV_TEST_PATH, override=True)

import app.models  # noqa: E402,F401 — garante que todos os modelos estejam registrados
from app.core.config import get_settings  # noqa: E402
from app.core.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app as fastapi_app  # noqa: E402


def _assert_connected_to_test_database(database_name: str) -> None:
    """Recusa limpeza fora de um banco explicitamente dedicado a testes."""
    settings = get_settings()
    if settings.app_env != "test":
        raise RuntimeError(
            f"Recusando TRUNCATE: APP_ENV='{settings.app_env}' (esperado 'test'). "
            "Verifique backend/.env.test."
        )
    if not database_name.endswith("_test"):
        raise RuntimeError(
            f"Recusando TRUNCATE: banco conectado é '{database_name}', que não "
            "termina em '_test'. A suíte de testes só pode truncar um banco "
            "dedicado a testes. Verifique DATABASE_URL em backend/.env.test."
        )


@pytest_asyncio.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    session = SessionLocal()
    try:
        yield session
        await session.rollback()
    finally:
        await session.close()


@pytest_asyncio.fixture(autouse=True)
async def _clean_database() -> AsyncIterator[None]:
    """Limpa as tabelas compartilhadas após cada teste de integração."""
    yield
    table_names = ", ".join(f'"{t.name}"' for t in reversed(Base.metadata.sorted_tables))
    async with engine.begin() as conn:
        current_db = (await conn.execute(text("SELECT current_database()"))).scalar_one()
        _assert_connected_to_test_database(current_db)
        await conn.execute(text("SET LOCAL lock_timeout = '5s'"))
        await conn.execute(text(f"TRUNCATE TABLE {table_names} RESTART IDENTITY CASCADE"))


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def auth_header() -> Callable[[str], dict[str, str]]:
    """`auth_header("ADMIN")` -> header Bearer do bypass DEV_AUTH_ENABLED.
    Requer `DEV_AUTH_ENABLED=true` no `.env` de teste (já configurado)."""

    def _make(role: str) -> dict[str, str]:
        return {"Authorization": f"Bearer dev-{role.lower()}"}

    return _make
