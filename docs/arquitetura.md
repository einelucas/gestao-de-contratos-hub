# Arquitetura

O módulo Gestão de Contratos usa a base compartilhada do Hub em duas aplicações no mesmo repositório.

## Frontend
Nuxt 4 + Vue 3 + TypeScript, Pinia e Tailwind. O shell visual do Hub fica em `AppHeader`, `TabsNav`, layout, tokens CSS e `public/brand`. O dashboard e a listagem consomem somente a API FastAPI.

## Backend
FastAPI + SQLAlchemy assíncrono. O domínio vive em `app/modules/contracts/` e os modelos em `app/models/contracts.py`.

## Persistência
PostgreSQL no Neon. A aplicação usa conexão pooled com asyncpg e o Alembic usa conexão direct com psycopg.

## Dados iniciais
A migration `0002_contracts_domain` cria o domínio e `scripts/seed_contracts.py` importa o CSV inicial de forma idempotente.
