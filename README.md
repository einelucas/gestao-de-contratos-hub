# Gestão de Contratos — Hub

Primeira versão do módulo Gestão de Contratos construída sobre a base compartilhada do Hub.

## Stack
- Nuxt 4 + Vue 3 + TypeScript
- FastAPI + SQLAlchemy async
- PostgreSQL / Neon.tech
- Alembic

## Entregue nesta versão
- shell/navbar/identidade visual do Hub preservados;
- dashboard de contratos baseado no app de referência de `docs.zip`;
- KPIs clicáveis: Total, Vencidos, Atenção (20 dias), Regulares e Finalizados;
- busca global, filtros por setor/fornecedor/unidade/situação e ordenação;
- grade responsiva 1–5 colunas e modo lista;
- paginação;
- painel lateral de detalhes;
- central de notificações;
- API FastAPI para setores e contratos;
- base de criação/edição via API para Analyst/Admin;
- migration do domínio;
- seed idempotente com `Relação Contratos.csv`;
- variáveis preparadas para Neon pooled/direct connection;
- autenticação e auditoria herdadas do Hub.

Veja `SETUP.md` para executar localmente.
