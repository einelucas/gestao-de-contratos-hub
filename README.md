# Gestão de Contratos — Hub

Módulo de **Gestão de Contratos** construído sobre a base compartilhada do Hub, com frontend em Nuxt/Vue, API FastAPI e persistência em PostgreSQL/Neon.

O sistema centraliza a consulta e o acompanhamento dos contratos, oferece indicadores de vencimento, filtros, controle de acesso por perfil/setor e uma central de notificações para apoiar o acompanhamento das vigências.

## Stack

- **Frontend:** Nuxt 4 + Vue 3 + TypeScript
- **Backend:** FastAPI + SQLAlchemy Async
- **Banco de dados:** PostgreSQL / Neon.tech
- **Migrations:** Alembic
- **Autenticação:** Keycloak/OIDC, modo de homologação e autenticação local de desenvolvimento
- **Notificações:** log, Mailpit para homologação e Microsoft Graph para envio corporativo

## Funcionalidades entregues

- shell, navbar e identidade visual do Hub preservados;
- dashboard executivo de contratos;
- KPIs clicáveis:
  - Total;
  - Vencidos;
  - Atenção — contratos com até 20 dias para o vencimento;
  - Regulares;
  - Finalizados;
- gráfico de acompanhamento no dashboard;
- busca global;
- filtros por setor, fornecedor, unidade e situação;
- ordenação dos contratos;
- visualização em grade responsiva de 1 a 5 colunas;
- modo lista;
- paginação;
- painel lateral com detalhes do contrato;
- central de notificações;
- visualização dos alertas e envios associados ao contrato;
- API FastAPI para setores, fornecedores, contratos e notificações;
- criação e edição de contratos conforme perfil/permissão;
- importação CSV/XLSX por ADMIN com preview e substituição atômica por setor;
- controle de acesso por setor;
- migrations versionadas com Alembic;
- seed idempotente a partir de `Relação Contratos.csv`;
- suporte a conexão Neon pooled para a aplicação e direct connection para migrations;
- autenticação e auditoria integradas à arquitetura do Hub.

## Arquitetura

```text
Navegador
   │
   ▼
Nuxt 4 / Vue 3
   │
   │ /api/v1
   ▼
Proxy do Nuxt
   │
   ▼
FastAPI
   │
   ├── Regras de negócio
   ├── Autenticação e autorização
   ├── Auditoria
   └── Notificações
   │
   ▼
PostgreSQL / Neon
```

O frontend **não acessa o banco diretamente**. Toda leitura ou alteração passa pela API FastAPI.

---

# Executando localmente

## 1. Pré-requisitos

Antes de iniciar, tenha instalado:

- Git;
- Node.js e npm compatíveis com Nuxt 4;
- Python **3.12 ou superior**;
- acesso a um banco PostgreSQL, preferencialmente Neon.tech.

Clone o repositório:

```bash
git clone https://github.com/einelucas/gestao-de-contratos-hub.git
cd gestao-de-contratos-hub
```

## 2. Configurar o banco Neon

No Neon, obtenha duas connection strings:

- **Pooled connection** → usada em `DATABASE_URL`;
- **Direct connection** → usada em `MIGRATION_DATABASE_URL`.

A pooled connection normalmente possui `-pooler` no host. A conexão direta é utilizada principalmente pelo Alembic.

> Nunca versione arquivos `.env` ou credenciais reais.

## 3. Backend

Entre na pasta:

```bash
cd backend
```

Crie o ambiente virtual:

### Windows / PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### Linux / macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Instale as dependências:

```bash
python -m pip install -e ".[dev]"
```

Crie o arquivo de ambiente:

### Windows

```powershell
copy .env.example .env
```

### Linux / macOS

```bash
cp .env.example .env
```

Preencha pelo menos as variáveis necessárias para o banco:

```env
APP_ENV=development
DATABASE_URL=postgresql://...
MIGRATION_DATABASE_URL=postgresql://...
ALLOW_TEST_DB_MIGRATIONS=true
CORS_ORIGINS=http://localhost:3000
DEV_AUTH_ENABLED=true
NOTIFICATION_PROVIDER=log
APP_PUBLIC_URL=http://localhost:3000
```

Aplique todas as migrations:

```bash
alembic upgrade head
```

Importe os contratos iniciais:

```bash
python scripts/seed_contracts.py
```

Inicie a API:

```bash
python -m uvicorn app.main:app --reload --port 8000
```

Endereços locais:

- API: `http://localhost:8000`
- Swagger/OpenAPI: `http://localhost:8000/docs`

> Se o PowerShell bloquear a ativação da venv, utilize o CMD ou execute os binários diretamente de `.venv\Scripts`.

## 4. Frontend

Abra outro terminal e entre na pasta:

```bash
cd frontend
```

Crie o arquivo de ambiente:

### Windows

```powershell
copy .env.example .env
```

### Linux / macOS

```bash
cp .env.example .env
```

Para desenvolvimento local, o arquivo pode utilizar:

```env
NUXT_PUBLIC_API_BASE_URL=/api/v1
NUXT_API_PROXY_TARGET=http://localhost:8000
NUXT_PUBLIC_DEV_AUTH_ENABLED=true
```

Instale as dependências:

```bash
npm install
```

Inicie o frontend:

```bash
npm run dev
```

Abra:

```text
http://localhost:3000
```

O navegador chama o próprio Nuxt em `/api/v1`, e o servidor Nuxt encaminha as requisições ao FastAPI por meio de `NUXT_API_PROXY_TARGET`.

---

# Autenticação e perfis

O projeto suporta três cenários de autenticação:

- **Keycloak/OIDC:** integração corporativa;
- **Homologação:** login temporário controlado por configuração;
- **Dev Auth:** autenticação simplificada para desenvolvimento local.

Quando:

```env
DEV_AUTH_ENABLED=true
NUXT_PUBLIC_DEV_AUTH_ENABLED=true
```

a aplicação disponibiliza os perfis de desenvolvimento:

- **Viewer:** consulta;
- **Analyst:** consulta e manutenção conforme permissões;
- **Admin:** acesso administrativo.

As permissões podem ser limitadas por setor.

Para detalhes, consulte:

- `docs/autenticacao.md`
- `docs/login-homologacao.md`

---

# Regras de situação dos contratos

A situação é determinada pelas regras de negócio:

- contrato marcado como finalizado → **Finalizado**;
- contrato sem data de fim → **Sem data**;
- fim da vigência anterior à data atual → **Vencido**;
- contrato vigente com até 20 dias restantes → **Atenção**;
- demais contratos vigentes → **Regular/Vigente**.

A situação exibida no dashboard é derivada dessas regras, evitando depender apenas de preenchimento manual.

---

# Seed inicial

O script:

```bash
python scripts/seed_contracts.py
```

utiliza o arquivo `Relação Contratos.csv` como base inicial.

O processo é idempotente, permitindo nova execução sem duplicar os registros já importados.

O seed também normaliza os fornecedores e associa os registros ao domínio de contratos do sistema.

---

# Notificações

O backend possui três modos principais de envio:

### Desenvolvimento

```env
NOTIFICATION_PROVIDER=log
```

Os alertas são processados sem envio real.

### Homologação com Mailpit

```env
NOTIFICATION_PROVIDER=mailpit
```

Permite validar o conteúdo dos e-mails sem entregar mensagens reais.

### Produção

```env
NOTIFICATION_PROVIDER=graph
```

Utiliza Microsoft Graph para envio corporativo.

Credenciais do Graph devem ser configuradas somente por variáveis de ambiente e **nunca devem ser versionadas**.

Mais detalhes em:

`docs/alertas-email.md`

---

# Banco de dados e migrations

As alterações de estrutura são controladas pelo Alembic.

Para atualizar o banco para a última versão:

```bash
cd backend
alembic upgrade head
```

Para verificar o estado atual:

```bash
alembic current
```

As migrations existentes cobrem a base compartilhada do Hub, domínio de contratos, alertas e evolução do sistema de notificações.

Documentação complementar:

`docs/banco-de-dados.md`

### Importação de contratos

Em **Contratos → Importar**, o ADMIN escolhe o setor, envia um CSV UTF-8 ou XLSX de até 5 MB e revisa o preview. O botão **Baixar modelo** fornece os cabeçalhos aceitos. Linhas vazias são ignoradas; qualquer erro de coluna, valor, data ou duplicidade impede a confirmação. A planilha é validada novamente na confirmação, que exige digitar `SUBSTITUIR`. O arquivo não fica armazenado no servidor.

A substituição remove apenas contratos do setor escolhido e insere a nova base no mesmo commit. Fornecedores existentes são reutilizados sem distinguir maiúsculas/minúsculas ou espaços repetidos. Os contratos importados ficam com `notify=false`; nenhum e-mail é enviado. O log de auditoria guarda apenas metadados e o hash SHA-256 do arquivo.

O histórico de vencidos é corporativo. Quando o setor importado contém toda a base, a operação reinicia os snapshots e cria uma baseline da nova base no mesmo commit. Com contratos em outros setores e histórico corporativo já existente, o preview bloqueia a substituição para preservar esse histórico; é preciso decidir separadamente como migrar uma base parcial. Quando ainda não há histórico, a primeira baseline inclui todos os setores. Falha em qualquer etapa reverte contratos, fornecedores, histórico e auditoria da importação.

---

# Validação do projeto

## Frontend

Executar todas as validações principais:

```bash
cd frontend
npm run check
```

O comando executa:

- typecheck;
- testes;
- build de produção.

Também podem ser executados separadamente:

```bash
npm run typecheck
npm run test
npm run build
```

## Backend

Com a venv ativa:

```bash
cd backend
pytest
ruff check .
mypy app
```

---

# Estrutura principal

```text
gestao-de-contratos-hub/
├── backend/
│   ├── alembic/
│   ├── app/
│   ├── scripts/
│   ├── tests/
│   ├── .env.example
│   └── pyproject.toml
│
├── frontend/
│   ├── app/
│   ├── components/
│   ├── pages/
│   ├── .env.example
│   └── package.json
│
├── docs/
│   ├── alertas-email.md
│   ├── api.md
│   ├── arquitetura.md
│   ├── autenticacao.md
│   ├── banco-de-dados.md
│   ├── desenvolvimento.md
│   └── login-homologacao.md
│
├── Relação Contratos.csv
├── SETUP.md
└── README.md
```

> A estrutura interna do Nuxt pode evoluir; use esta árvore como visão geral dos principais blocos do projeto.

---

# Documentação

Para informações mais detalhadas:

- `SETUP.md` — configuração local;
- `docs/arquitetura.md` — arquitetura;
- `docs/api.md` — API;
- `docs/autenticacao.md` — autenticação;
- `docs/login-homologacao.md` — ambiente de homologação;
- `docs/banco-de-dados.md` — banco e migrations;
- `docs/alertas-email.md` — alertas e envio de e-mails;
- `docs/desenvolvimento.md` — orientações de desenvolvimento.

## Segurança

- não versionar `.env`;
- não registrar senhas, tokens ou secrets no código;
- utilizar `MIGRATION_DATABASE_URL` apenas para operações que exigem conexão direta;
- manter o frontend sem acesso direto ao PostgreSQL;
- utilizar HTTPS e cookies seguros em produção;
- utilizar o provider corporativo de autenticação e notificações em produção.
