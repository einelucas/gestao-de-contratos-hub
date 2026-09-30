# Autenticação

A aplicação suporta OIDC/Keycloak em ambientes integrados e um bypass controlado para desenvolvimento local.

O backend valida o token, resolve o usuário local e aplica permissões de servidor. O frontend armazena o access token em cookie e consulta `/api/v1/auth/me` para carregar a sessão.

## Desenvolvimento

Com `DEV_AUTH_ENABLED=true` e `APP_ENV` diferente de `production`, são aceitos os tokens:

- `dev-viewer`
- `dev-analyst`
- `dev-admin`

O bypass não desativa a matriz de permissões.

## Permissões iniciais

Somente o perfil `ADMIN` possui `users:manage` e `audit:read`. Não existem permissões de negócio de equipamentos nesta etapa.
