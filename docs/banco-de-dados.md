# Banco de dados

PostgreSQL hospedado na Neon.tech.

## Variáveis
- `DATABASE_URL`: conexão pooled usada pela aplicação.
- `MIGRATION_DATABASE_URL`: conexão direct usada pelo Alembic.

## Migrations
- `0001_shared_base`: usuários, sessões, contas, verificação, auditoria e Role.
- `0002_contracts_domain`: setores, fornecedores, contratos e permissões setoriais.
- `0003_contract_alerts`: campos de alerta em `Contract` (`notify`, `noticeDays`,
  `responsibleUserId`, `responsibleEmail`, `autoRenewal`, `criticality`), enums
  `ContractCriticality`, `ContractNotificationType` e `ContractNotificationStatus`, e a
  tabela `ContractNotification` (histórico dos alertas por e-mail).
- `0004_notification_provider`: coluna `provider` em `ContractNotification` (`log` ou `graph`).

## ContractNotification

Uma linha por alerta gerado. O índice único `ContractNotification_dedup_key`
`(contractId, type, referenceDate, noticeDays, recipient)` impede envio duplicado.

- `referenceDate`: fim de vigência (ANTECEDENCIA/VENCIMENTO) ou data do marco semanal (VENCIDO).
  Uma renovação muda o fim de vigência e abre um novo ciclo de alertas.
- `noticeDays`: antecedência usada; `0` quando não se aplica (VENCIMENTO/VENCIDO).
- `status`: `PENDING`, `SENT`, `FAILED` ou `SKIPPED`, com `attempts`, `error`, `sentAt` e `lastAttemptAt`.

```bash
python -m alembic upgrade head
python scripts/seed_contracts.py
```

O seed inicial contém 98 contratos do arquivo `backend/data/seed/relacao_contratos.csv`.
