# API

Prefixo: `/api/v1`.

## Saúde

- `GET /health/live`: indica que o processo está ativo.
- `GET /health/ready`: verifica a conectividade com o banco.

## Autenticação

- `GET /auth/me`: retorna o usuário autenticado e suas permissões.

## Usuários

Rotas administrativas:

- `GET /usuarios`
- `POST /usuarios`
- `PATCH /usuarios/{user_id}`
- `GET /usuarios/{user_id}/setores`: setores liberados ao usuário (`canView`/`canEdit`).
- `PUT /usuarios/{user_id}/setores`: substitui a lista completa de setores do usuário.

## Contratos

Todas as rotas respeitam `UserSectorPermission`:

- ADMIN consulta e edita todos os setores.
- VIEWER consulta os setores com `canView` ou `canEdit`, sem editar.
- ANALYST consulta os mesmos setores e cria/edita apenas nos setores com `canEdit`.
- Usuário sem nenhuma permissão setorial não vê contratos.
- Contrato de setor não liberado responde `404`; setor liberado só para consulta responde `403` na edição.

Rotas:

- `GET /setores`: setores visíveis ao usuário, com `canEdit`.
- `GET /contratos?sectorId=`: contratos visíveis ao usuário.
- `GET /contratos/{contract_id}`
- `POST /contratos`
- `PATCH /contratos/{contract_id}`
- `GET /contratos/resumo?sectorId=&unit=&de=&ate=`: indicadores do dashboard (KPIs, % em dia,
  por status/setor/unidade, série mensal, faixas de prazo, atrasos e valores). `de`/`ate`
  filtram pelo fim da vigência.
- `GET /responsaveis` (`contracts:manage`): usuários ativos para o campo "Responsável".

Campos de alerta (entrada e saída): `notify`, `noticeDays` (1–365, padrão 20),
`responsibleUserId`, `responsibleEmail`, `autoRenewal` e `criticality` (`BAIXA`/`MEDIA`/`ALTA`).
Na saída também vêm `responsibleUserName`, `notificationRecipient` (e-mail do usuário
vinculado ou, sem ele, `responsibleEmail`) e `canEdit`. Ativar `notify` exige responsável
ou e-mail do responsável. `noticeDays` define só o disparo do e-mail de antecedência;
o status visual (Atenção) continua usando a janela fixa de 20 dias.

## Alertas de vencimento

Motor em `app/modules/contract_alerts/`. Envio pelo adapter definido em
`NOTIFICATION_PROVIDER` (`log` por enquanto). Execução diária por agendador externo:

```bash
python -m app.jobs.contract_alerts             # execução real
python -m app.jobs.contract_alerts --dry-run   # só mostra o que seria enviado
python -m app.jobs.contract_alerts --dry-run --date 2026-10-20
```

Regras: ANTECEDENCIA quando faltam exatamente `noticeDays` dias; VENCIMENTO no dia;
VENCIDO a cada 7 dias de atraso (7, 14, 21…). Falhas são retentadas na mesma linha
de `ContractNotification` até 3 tentativas.

- `GET /alertas/previa?data=` (ADMIN): dry-run sem efeitos colaterais; `data` simula outro dia.
- `POST /alertas/executar?dry_run=true|false` (ADMIN): padrão `dry_run=true`; `data` só com dry-run.
- `GET /contratos/{contract_id}/notificacoes`: histórico do contrato (respeita setores).
- `GET /alertas/contratos`: contratos que exigem atenção (sino), com mensagem e último alerta.
- `GET /notificacoes-contratos?status=&tipo=&contractId=&destinatario=&de=&ate=&page=&pageSize=` (ADMIN).
- `POST /notificacoes-contratos/{id}/reenviar` (ADMIN): só `FAILED` com menos de 3 tentativas.

## Auditoria

- `GET /auditoria`: lista eventos registrados, com paginação e filtros opcionais por entidade e ação.

A documentação interativa completa é gerada pelo FastAPI em `/docs`.
