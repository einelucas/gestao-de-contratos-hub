# Alertas de vencimento por e-mail

O backend envia alertas de vencimento de contratos para a **equipe de notificação**
do setor do contrato. O processamento roda num job diário fora da API; o frontend
não precisa estar aberto.

```
PostgreSQL → python -m app.jobs.contract_alerts → régua 45/20/1/0 + vencido semanal
          → equipe do contrato → membros ativos → uma ContractNotification por destinatário
          → NotificationAdapter (log | mailpit | graph) → SENT / FAILED → retry (até 3 tentativas)
```

## Régua fixa

| Marco | `type` / `noticeDays` | Janela de recuperação |
|---|---|---|
| 45 dias antes | `ANTECEDENCIA` / 45 | faltam 45…21 dias |
| 20 dias antes | `ANTECEDENCIA` / 20 | faltam 20…2 dias |
| 1 dia antes | `ANTECEDENCIA` / 1 | falta 1 dia |
| No dia | `VENCIMENTO` / 0 | só no dia |
| Vencido | `VENCIDO` / 0 | 7, 14, 21… dias após (sem recuperação) |

- Só contratos com `notify = true`, não finalizados e com fim de vigência.
- "Hoje" é o dia civil em `America/Sao_Paulo`. O status "Atenção" do painel continua em 20 dias,
  independente dos e-mails.
- **Um e-mail por membro ativo** da equipe (sem expor os demais destinatários), com rastreio,
  falha e retry individuais. Deduplicação: `(contrato, tipo, data de referência, noticeDays, destinatário)`.
- **Marco perdido** (job fora do ar): recuperado dentro da janela, uma única vez.
  **Ativação tardia**: marco cuja data é anterior a `notifyEnabledOn` não é enviado
  (ligar os alertas com 15 dias restantes → próximo marco é o de 1 dia).
- Um marco já processado não é reenviado para quem entrou depois na equipe, nem para uma
  nova equipe vinculada ao contrato; eles participam dos próximos marcos.
- Equipe inativa, sem membros ativos ou sem equipe: nada é enviado; o marco fica `SKIPPED`
  (rastreável) e pode ser recuperado dentro da janela quando a equipe for corrigida.
- Renovar o contrato (mudar o fim de vigência) abre um novo ciclo; o histórico fica.
- Contratos com renovação automática recebem os alertas normalmente, com destaque no e-mail.
- Campos legados do contrato (`responsibleUserId`, `responsibleEmail`, `noticeDays`) permanecem
  no banco, mas não definem mais destinatário nem antecedência.

## Providers

`NOTIFICATION_PROVIDER` escolhe o adapter; o motor e o template são os mesmos nos três.

| Provider | Uso | Entrega de verdade? | `provider` no histórico |
|---|---|---|---|
| `log` | simulação (padrão) | não, só registra no log | `log` |
| `mailpit` | homologação local | não, captura numa caixa local | `mailpit` |
| `graph` | produção / homologação corporativa | sim, Microsoft Graph | `graph` |

## Homologação local com Mailpit

O [Mailpit](https://mailpit.axllent.org/) é um servidor SMTP local que **captura** as
mensagens numa caixa própria. Ele **não envia nada para a internet**: serve para validar o
funcionamento, os destinatários e a aparência dos e-mails enquanto o Graph não está
disponível. **Não substitui a homologação final no Microsoft Graph.**

1. Inicie o Mailpit (escolha um):
   - Docker: `docker compose -f backend/docker-compose.mailpit.yml up -d`
   - Binário (sem Docker): baixe `mailpit-windows-amd64.zip` (ou a versão do seu sistema) em
     <https://github.com/axllent/mailpit/releases>, descompacte e rode
     `mailpit --smtp 127.0.0.1:1025 --listen 127.0.0.1:8025`
2. Configure o backend:

   ```
   NOTIFICATION_PROVIDER=mailpit
   SMTP_HOST=127.0.0.1
   SMTP_PORT=1025
   SMTP_USE_TLS=false
   SMTP_SENDER_EMAIL=gestao.contratos@hub.local
   ```

   Nenhuma variável do Graph é exigida nesse modo. `mailpit` é **recusado** com
   `APP_ENV=production` (a aplicação não sobe).
3. Rode o job (`python -m app.jobs.contract_alerts`, ou `--dry-run` antes) e abra
   <http://localhost:8025>. Cada membro da equipe aparece como uma mensagem separada; os
   cabeçalhos `X-Hub-Notification-Id` e `X-Hub-Contract-Number` ligam cada mensagem ao histórico.

Use apenas dados fictícios (ex.: `teste1@hub.local`) num banco de teste. Screenshots da
homologação: `docs/homologacao/mailpit/`.

## Homologação corporativa futura (Graph)

Quando a TI fornecer as credenciais, basta trocar para `NOTIFICATION_PROVIDER=graph` e
preencher as variáveis abaixo; a regra de negócio e o template não mudam.

## Configuração do Microsoft Graph

1. No Entra ID, registre um aplicativo (ex.: "Hub - Gestão de Contratos").
2. Em **Permissões de API**, adicione `Microsoft Graph > Permissões de aplicativo > Mail.Send`
   e conceda consentimento de administrador.
3. Crie um **segredo do cliente** e guarde o valor (só aparece uma vez).
4. Crie ou escolha a caixa remetente (ex.: `contratos@empresa.com.br`).
5. Recomendado: restrinja o aplicativo a essa caixa com uma *Application Access Policy*
   do Exchange Online, para que ele não possa enviar como qualquer usuário:

   ```powershell
   New-ApplicationAccessPolicy -AppId <GRAPH_CLIENT_ID> `
     -PolicyScopeGroupId contratos@empresa.com.br `
     -AccessRight RestrictAccess -Description "Hub - alertas de contratos"
   ```

6. Configure as variáveis no ambiente (nunca no código nem no repositório):

| Variável | Descrição |
|---|---|
| `NOTIFICATION_PROVIDER` | `graph` para envio real (`log` e `mailpit` são só para dev/homologação) |
| `GRAPH_TENANT_ID` (ou `AZURE_TENANT_ID`) | ID do diretório (tenant) |
| `GRAPH_CLIENT_ID` (ou `AZURE_CLIENT_ID`) | ID do aplicativo |
| `GRAPH_CLIENT_SECRET` (ou `AZURE_CLIENT_SECRET`) | segredo do cliente |
| `GRAPH_SENDER` (ou `GRAPH_SENDER_EMAIL`) | caixa remetente |
| `GRAPH_SAVE_TO_SENT_ITEMS` | guarda cópia em Itens Enviados (padrão `true`) |
| `GRAPH_TIMEOUT_SECONDS` | timeout das chamadas (padrão `20`) |
| `APP_PUBLIC_URL` | URL do frontend para o botão "Abrir no Hub" (opcional) |
| `NOTIFICATION_REDIRECT_TO` | homologação: todos os e-mails vão para esta caixa (proibido em produção) |

Com `NOTIFICATION_PROVIDER=graph`, a aplicação não sobe se faltar alguma variável do
Graph; a mensagem cita só o nome da variável, nunca o valor.

## Homologação segura

1. `NOTIFICATION_PROVIDER=graph` + `NOTIFICATION_REDIRECT_TO=sua.caixa@empresa.com.br`.
2. `python -m app.jobs.contract_alerts --dry-run` para conferir o que seria enviado.
3. Execute o job; todos os e-mails chegam só na caixa de teste, com o destinatário
   original no assunto.

## Agendamento

Uma vez por dia, de preferência de manhã (horário de Brasília). Exemplo no Render
(Cron Job, mesmo repositório e variáveis da API):

- **Command:** `python -m app.jobs.contract_alerts`
- **Schedule:** `0 10 * * *` (UTC = 07:00 em Brasília)

Código de saída: `0` quando o job conclui (falhas de envio ficam `FAILED` para retry),
`1` se o job não conseguir executar, `2` para argumentos inválidos.

## Operação

- `GET /api/v1/alertas/previa` — prévia (dry-run) sem efeitos colaterais.
- `POST /api/v1/alertas/executar?dry_run=false` — execução manual (auditada).
- `GET /api/v1/notificacoes-contratos?status=FAILED` — falhas pendentes.
- `POST /api/v1/notificacoes-contratos/{id}/reenviar` — reenvio manual (auditado).
- A coluna `provider` de cada notificação indica se o envio foi real (`graph`) ou só
  registrado (`log`).
- Erros do Graph ficam em `error` com status HTTP, classificação (temporária/permanente),
  código do Graph e `request-id` para abrir chamado na Microsoft.
