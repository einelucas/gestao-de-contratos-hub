# Design QA — Layout amplo e Kanban de Auditoria

- Fonte visual principal: página `frontend/pages/equipamentos/kanban.vue` e estilos globais do repositório `hub-painel-de-equipamentos-main (1).zip`, anexado pelo usuário.
- Referência fornecida: captura desktop de 1798 × 853 px.
- Implementação validada: capturas `/tmp/kanban-auditoria-layout.png`, `/tmp/kanban-auditoria-layout-finalizado.png` e `/tmp/kanban-auditoria-layout-mobile.png`.
- Viewports: 1798 × 900 px e 390 × 900 px, device scale factor 1.

## Comparação da página completa

O Hub de Contratos agora usa o mesmo limite útil de 1680 px e margem desktop de 48 px do repositório de referência. Barra de navegação, título, filtros, resumo e quadro compartilham o mesmo alinhamento lateral. Em telas menores, as margens diminuem para 28 px e 20 px, mantendo o comportamento responsivo existente.

## Comparação do quadro

O Kanban reproduz a estrutura do modelo de equipamentos: filtros largos em uma linha, resumo em superfície própria, quadro horizontal com largura intrínseca, colunas de 286 px, cabeçalhos brancos, etapa numerada, contador circular, faixa de cor, altura limitada pela viewport, rolagem interna de cards e barra horizontal discreta. Os cards mantêm os dados próprios de contratos e os controles de drag and drop e movimentação por teclado.

## Superfícies verificadas

- Tipografia: hierarquia compacta e pesos equivalentes ao modelo, usando a fonte já adotada pelo Hub.
- Espaçamento: largura, margens, gaps de 12 px, colunas e preenchimentos seguem as medidas do repositório anexado.
- Cores: superfícies e bordas seguem o modelo; as cores das etapas do fluxo de contratos foram preservadas.
- Conteúdo: número, fornecedor, unidade, setor, vencimento e valor permanecem legíveis nos cards.
- Interação: filtro de unidade, busca, atualização, drag and drop, seletor de etapa e abertura do contrato foram preservados.
- Responsividade: em 390 px os filtros e o resumo empilham, e o quadro mantém colunas de 238 px com rolagem horizontal.
- Console: nenhum erro da aplicação. A única mensagem observada foi a indisponibilidade da fonte externa no túnel isolado de teste.

## Histórico de comparação

- Primeira renderização: identificada contração vertical dos cards quando três itens ocupavam uma coluna.
- Correção: cards passaram a usar `flex: 0 0 auto`, permitindo rolagem interna e mantendo todos os controles visíveis.
- Renderização final: sete colunas, filtro, drag and drop e finalização validados sem erros.

Nenhum achado P0, P1 ou P2 permanece.

final result: passed
