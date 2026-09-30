# Desenvolvimento

## Frontend

```bash
cd frontend
pnpm install
pnpm dev
```

Validação:

```bash
pnpm lint
pnpm typecheck
pnpm test
pnpm build
```

## Backend

```bash
cd backend
python -m venv .venv
python -m pip install -e ".[dev]"
python -m alembic upgrade head
python -m uvicorn app.main:app --reload
```

Validação:

```bash
python -m ruff check app tests scripts
python -m mypy app
python -m pytest
```

Os testes de integração exigem `.env.test` e banco PostgreSQL exclusivo terminado em `_test`.
