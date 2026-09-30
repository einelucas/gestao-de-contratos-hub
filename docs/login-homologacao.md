# Login temporário de homologação

Permite hospedar o Gestão de Contratos para a equipe avaliar, com duas contas
fixas de usuário e senha, enquanto o SSO corporativo (Keycloak) não está
disponível. **É temporário**: o Keycloak continua implementado e volta com uma
variável de ambiente.

| Conta | Perfil | Pode |
|---|---|---|
| Visualizador | `VIEWER` | consultar dashboard, contratos, detalhes, filtros, gráficos e o modelo do e-mail |
| Administrador | `ADMIN` | tudo, pelas regras de sempre (não depende de permissões por setor) |

## Como funciona

- `AUTH_PROVIDER=homologation` no backend. O usuário pode ser um nome ou um e-mail
  (qualquer texto; não diferencia maiúsculas).
- `POST /api/v1/auth/login` confere a senha com o hash **Argon2** do ambiente e cria uma
  sessão (tabela `Session`, só o SHA-256 do token) entregue num cookie **HttpOnly**,
  `SameSite=Lax`, `Secure` em HTTPS, válido por `AUTH_SESSION_HOURS` (padrão 8 h).
- Neste modo o backend **ignora** tokens Bearer e o bypass de desenvolvimento
  (`DEV_AUTH_ENABLED`): só a sessão por cookie autentica.
- As duas contas viram usuários normais (`authProvider=HOMOLOGATION`) com perfil
  `VIEWER`/`ADMIN`; todas as permissões e setores continuam valendo como sempre.
- Resposta única para erro: **"Usuário ou senha inválidos."**
- Limite de tentativas: 5 falhas em 15 min por IP+usuário, 10 por usuário (qualquer IP),
  20 por IP → espera de 15 min (HTTP 429). Em memória, por processo.
- `POST /api/v1/auth/logout` apaga a sessão e o cookie. Remover/renomear a conta no
  ambiente derruba as sessões dela.
- O frontend (Nuxt, modo SPA) faz proxy de `/api/**` para o FastAPI, então o cookie é
  de mesma origem. Links com `?contrato=ID` voltam para o contrato depois do login.

## Configurar no ambiente hospedado

1. **Gerar os hashes** (em qualquer máquina com o backend instalado; a senha não é
   gravada nem aparece na tela):

   ```bash
   cd backend
   python scripts/hash_password.py   # uma vez para cada conta (mínimo 12 caracteres)
   ```

2. **Backend** (variáveis/secrets da plataforma; nunca no repositório nem no build):

   ```
   APP_ENV=production
   AUTH_PROVIDER=homologation
   HOMOLOGATION_VIEWER_USERNAME=<usuário do visualizador>
   HOMOLOGATION_VIEWER_PASSWORD_HASH=<hash gerado>
   HOMOLOGATION_ADMIN_USERNAME=<usuário do administrador>
   HOMOLOGATION_ADMIN_PASSWORD_HASH=<hash gerado>
   AUTH_SESSION_HOURS=8
   AUTH_COOKIE_SECURE=true
   TRUST_PROXY_HEADERS=true
   DEV_AUTH_ENABLED=false
   NOTIFICATION_PROVIDER=log          # graph quando a TI liberar; mailpit é recusado em produção
   APP_PUBLIC_URL=https://<url pública do frontend>
   ```

   A aplicação não sobe se faltar alguma variável, se um "hash" não for Argon2
   (senha em texto) ou se `AUTH_COOKIE_SECURE=false` em produção.

3. **Frontend** (Nuxt): nenhuma senha, hash ou segredo.

   ```
   NUXT_PUBLIC_API_BASE_URL=/api/v1
   NUXT_API_PROXY_TARGET=https://<url interna/pública da API>
   ```

4. **HTTPS obrigatório** no endereço público do frontend.
5. **Preparar as contas e liberar a consulta ao Visualizador** (explícito, nunca em migration):

   ```bash
   python scripts/bootstrap_homologation_users.py --viewer-sectors all
   # ou setores específicos: --viewer-sectors projetos-arquitetura
   ```

   O Visualizador recebe só `canView` (nunca `canEdit`). O Administrador não precisa.

O Mailpit **não** vai para a hospedagem: é só ferramenta local; nenhuma rota da aplicação
expõe mensagens capturadas.

## Voltar para o Keycloak (SSO corporativo)

1. Trocar `AUTH_PROVIDER=keycloak` e configurar `KEYCLOAK_ISSUER`, `KEYCLOAK_AUDIENCE`
   (backend) e `NUXT_PUBLIC_OIDC_*` (frontend).
2. Remover as variáveis `HOMOLOGATION_*`. A partir daí `POST /auth/login` responde 404 e
   nenhum cookie de homologação autentica (o backend nem lê esse cookie no modo keycloak).
3. Opcional: apagar as sessões antigas (`DELETE FROM "Session" WHERE ...`) e desativar os
   dois usuários `authProvider='HOMOLOGATION'`.

Frontend e regras de autorização não mudam: a tela de login escolhe o modo pelo
`GET /api/v1/auth/provider`.
