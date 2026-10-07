# Gestão de Contratos — Backend

API FastAPI do módulo Gestão de Contratos dentro da base compartilhada do Hub.

## Stack
- Python 3.12+
- FastAPI + Pydantic v2
- SQLAlchemy 2 assíncrono com `asyncpg`
- PostgreSQL / Neon.tech
- Alembic
- pytest / Ruff / mypy

## Domínio inicial
- `Sector`
- `Supplier`
- `Contract`
- `UserSectorPermission` (estrutura preparada para permissões setoriais)

As estruturas compartilhadas de autenticação e auditoria permanecem preservadas.

## Neon
Use `DATABASE_URL` com a conexão pooled e `MIGRATION_DATABASE_URL` com a conexão direct. Copie `.env.example` para `.env` e nunca versione credenciais reais.

## Comandos
```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
alembic upgrade head
python scripts/seed_contracts.py
uvicorn app.main:app --reload --port 8000
```

## Rotas principais
- `GET /api/v1/health/live`
- `GET /api/v1/health/ready`
- `GET /api/v1/auth/me`
- `GET /api/v1/setores`
- `GET /api/v1/contratos`
- `GET /api/v1/contratos/{id}`
- `POST /api/v1/contratos` (Analyst/Admin)
- `PATCH /api/v1/contratos/{id}` (Analyst/Admin)
- `GET /api/v1/auditoria` (Admin)
