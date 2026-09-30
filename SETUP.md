# Gestão de Contratos no Hub — setup local

## 1. Banco Neon
Crie um projeto PostgreSQL no Neon e obtenha duas strings:
- **pooled connection** → `DATABASE_URL` (host com `-pooler`);
- **direct connection** → `MIGRATION_DATABASE_URL` (host direto, sem `-pooler`).

Copie `backend/.env.example` para `backend/.env` e substitua os placeholders.

> Nunca versione o `backend/.env` com senha real.

## 2. Backend
No terminal, a partir de `backend`:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
alembic upgrade head
python scripts/seed_contracts.py
uvicorn app.main:app --reload --port 8000
```

Se o PowerShell bloquear a ativação da venv, use o CMD ou execute os binários diretamente de `.venv\Scripts`.

API: `http://localhost:8000`  
Swagger: `http://localhost:8000/docs`

## 3. Frontend
Em outro terminal, a partir de `frontend`:

```powershell
copy .env.example .env
npm install
npm run dev
```

Abra `http://localhost:3000`.

Com `DEV_AUTH_ENABLED=true` no backend e `NUXT_PUBLIC_DEV_AUTH_ENABLED=true` no frontend, a tela de login oferece Viewer, Analyst e Admin para desenvolvimento local.

## 4. O que a migration cria
A migration `0002_contracts_domain` cria:
- `Sector`
- `Supplier`
- `Contract`
- `UserSectorPermission`

O seed cria o setor **Projetos e Arquitetura**, normaliza os fornecedores e importa os 98 contratos do CSV de forma idempotente.

## 5. Regra de situação
- marcado como finalizado → `Finalizado`;
- sem fim de vigência → `Sem data`;
- fim anterior a hoje → `Vencido`;
- demais → `Vigente`;
- vigentes com até 20 dias → alerta `Atenção`.
