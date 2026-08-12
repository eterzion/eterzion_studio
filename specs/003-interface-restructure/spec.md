# Feature Specification: Reorganização e simplificação de interface/

**Feature Branch**: `003-interface-restructure`

**Created**: 2026-08-12

**Status**: Draft

**Input**: User description: "Reorganizar e simplificar completamente a estrutura de interface/
(app Electron/Vue), aplicando o espírito de Atomic Design + Clean Architecture + SOLID adaptado
pragmaticamente (Constitution Princípio X — sem camadas domain/application vazias), eliminando
subdivisões desnecessárias, código morto e abstrações sem consumidor real, sem alterar
comportamento visual/funcional."

## User Scenarios & Testing *(mandatory)*

<!--
  Como na feature 002, esta é uma mudança estrutural interna — o "usuário" abaixo é quem
  trabalha no código de interface/, não o usuário final do produto. O usuário final não deve
  perceber nenhuma diferença (isso é, aliás, um requisito explícito).
-->

### User Story 1 - Um desenvolvedor encontra a camada de acesso externo sem ambiguidade (Priority: P1)

Hoje, `api.ts` (a ponte nativa do Electron) e `backend.ts` (o cliente HTTP/WebSocket da API) têm
nomes que invertem a expectativa óbvia — quem procura "o cliente da API" naturalmente abre
`api.ts` primeiro e encontra a ponte do Electron. Um desenvolvedor que chega ao projeto pela
primeira vez precisa conseguir identificar, pelo nome do arquivo, qual dos dois fala com o quê,
sem precisar abrir e ler o conteúdo.

**Why this priority**: é a confusão mais concreta e mensurável encontrada na auditoria — afeta
todo mundo que mexe na camada de rede, é fácil de errar (importar o arquivo errado por engano), e
a correção é isolada (só afeta esses dois arquivos e seus importadores).

**Independent Test**: abrir `interface/src/renderer/src/` e, sem ler o conteúdo dos arquivos,
identificar corretamente pelo nome qual arquivo é a ponte Electron e qual é o cliente HTTP/WS.

**Acceptance Scenarios**:

1. **Given** a árvore reorganizada, **When** um desenvolvedor procura o cliente HTTP/WebSocket da
   API, **Then** o nome do arquivo correspondente deixa isso inequívoco (não é `api.ts`, que hoje
   é a ponte Electron).
2. **Given** a árvore reorganizada, **When** um componente ou view precisa falar com o backend,
   **Then** ele importa da camada de acesso externo isolada — nunca faz `fetch`/chamada IPC direto
   dentro de um componente ou view.

---

### User Story 2 - Nenhum código morto ou não referenciado permanece em interface/ (Priority: P1)

`components/Versions.vue` (boilerplate do template electron-vite, confirmado sem nenhum import em
todo o código) precisa deixar de existir. De forma mais ampla, qualquer arquivo, export, ou
dependência de `package.json` que não tenha mais nenhum consumidor real depois da reorganização
precisa ser removido, não deixado "por segurança".

**Why this priority**: é o requisito mais explícito do pedido original ("remova... arquivos
legados... código morto... duplicados... exports e imports não utilizados") e o mais barato de
verificar objetivamente (grep por uso).

**Independent Test**: rodar uma varredura de import/uso em toda a árvore de `interface/src/`;
zero arquivo, export ou dependência sem pelo menos um consumidor real.

**Acceptance Scenarios**:

1. **Given** a árvore reorganizada, **When** se busca por `Versions.vue` (ou qualquer import dele),
   **Then** o arquivo não existe mais em lugar nenhum do repositório.
2. **Given** a árvore reorganizada, **When** se roda uma checagem de exports/imports não usados
   (lint ou ferramenta equivalente), **Then** zero ocorrência é reportada dentro de
   `interface/src/`.

---

### User Story 3 - Componentes primitivos reutilizáveis ficam separados de blocos de feature (Priority: P2)

Hoje `components/` é uma pasta plana com 19 arquivos misturando primitivos genéricos (um select
customizado, um slider, um switch) com blocos grandes amarrados a uma feature específica (a
sidebar principal, o modal de exportação em lote). Um desenvolvedor procurando "o que já existe
pronto para reusar" precisa ler os 19 nomes um a um.

**Why this priority**: é uma melhoria real de navegabilidade, mas menos urgente que US1/US2 — o
sistema já funciona hoje com a pasta plana; esta é uma melhoria de organização, não uma correção
de um problema ativo. P2 porque só deve ser feita se genuinamente reduzir fragmentação (Constitution
Princípio X), não como exercício de categorização.

**Why this priority**: reforça a mesma razão acima — valor real, mas condicional ao resultado da
análise (pode ser que a separação não compense para 19 arquivos; a decisão final é tomada no plano
técnico, não aqui).

**Independent Test**: abrir `components/`; primitivos genéricos reutilizáveis (usados por 2+ views
ou por natureza claramente independentes de uma feature) estão visualmente separados de blocos
amarrados a uma feature específica.

**Acceptance Scenarios**:

1. **Given** a árvore reorganizada, **When** um desenvolvedor procura um primitivo genérico (ex.:
   um controle de slider), **Then** ele está num local que sinaliza "isto é reutilizável", distinto
   de onde estão os blocos de feature.
2. **Given** a separação foi aplicada, **When** se verifica cada componente movido, **Then** cada
   um tem uma justificativa real de reuso ou de generalidade — nenhum foi movido só para preencher
   a categoria.

---

### User Story 4 - A reorganização não muda nada que o usuário final vê ou como o sistema se comporta (Priority: P1)

Depois de toda a reorganização, alguém que já usava o aplicativo continua vendo exatamente as
mesmas telas, os mesmos fluxos, os mesmos comportamentos — a mudança é inteiramente interna ao
código-fonte.

**Why this priority**: é uma restrição não-negociável explícita do pedido, e compartilha o P1 com
US1/US2 porque uma regressão aqui invalida a reorganização inteira, mesmo que a nova estrutura de
arquivos esteja correta.

**Independent Test**: rodar o app antes e depois da reorganização (build, lint, typecheck, e
percorrer os fluxos principais manualmente) e comparar — zero diferença observável.

**Acceptance Scenarios**:

1. **Given** o app reorganizado, **When** buildado e executado, **Then** typecheck e lint passam
   sem novos erros, e o app abre e funciona normalmente (licenciamento, importação, processamento,
   exportação, configurações).
2. **Given** qualquer arquivo movido ou renomeado, **When** se busca por imports do caminho antigo,
   **Then** nenhuma referência funcional resta (só documentação histórica, se aplicável).

---

### Edge Cases

- O que acontece com o alias `@renderer` (configurado mas nunca usado hoje)? → A especificação não
  exige adotá-lo; a decisão de uso é técnica e cabe ao plano — se a reorganização introduzir
  níveis de aninhamento que produzam imports relativos ruins (`../../`), o alias deve ser adotado
  nesses pontos; caso contrário, não há obrigação de trocar imports relativos que já funcionam bem.
- O que acontece se, durante a análise, `ImageEditorView.vue` (2084 linhas) não tiver
  responsabilidades genuinamente separáveis por trás do tamanho? → Ele permanece como um arquivo
  só, conforme a regra explícita de "não dividir só por tamanho" — documentar essa decisão, não
  dividir por inércia.
- O que acontece com o TODO de URLs placeholder em `AppSidebar.vue`? → Fora de escopo — é conteúdo
  a preencher antes do lançamento, não uma questão estrutural; não deve ser resolvido nem removido
  por esta feature.
- O que acontece se um componente/store/view depender de outro de um jeito que dificulte a
  separação proposta (ex.: um "primitivo" que na prática só é usado por uma feature)? → Ele não é
  primitivo de verdade; permanece junto da feature, não é movido só para bater com uma categoria.
- O que acontece com `interface/src/main/` e `interface/src/preload/` (processo principal do
  Electron)? → Fora de escopo desta feature — a reorganização é sobre `interface/src/renderer/src/`
  (a UI), não sobre o processo principal do Electron.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: A camada de acesso externo (ponte nativa do Electron, cliente HTTP/WebSocket da API)
  MUST ter nomes de arquivo que deixem inequívoco, sem precisar ler o conteúdo, o que cada um é —
  corrigindo a inversão de nomes atual entre `api.ts` (hoje a ponte Electron) e `backend.ts` (hoje
  o cliente HTTP/WS).
- **FR-002**: Nenhum componente ou view MUST fazer chamada de rede (`fetch`) ou IPC do Electron
  diretamente — toda comunicação externa passa pela camada de acesso isolada de FR-001.
- **FR-003**: `interface/src/` MUST NOT conter pastas `domain/`, `application/`, ou `use-cases/`
  (Constitution Princípio X) — a lógica de negócio já vive inteiramente em `api/`.
- **FR-004**: Todo arquivo, export, ou dependência de `package.json` sem nenhum consumidor real
  após a reorganização MUST ser removido — incluindo, no mínimo, `components/Versions.vue`
  (confirmado sem uso).
- **FR-005**: Componentes primitivos genuinamente reutilizáveis (usados por múltiplas
  views/features, ou generalizáveis por natureza) MAY ser organizados separadamente de blocos
  compostos amarrados a uma única feature — essa separação só deve ser aplicada onde reduzir
  fragmentação de verdade, nunca como taxonomia obrigatória para todo componente.
- **FR-006**: Nenhum arquivo MUST ser dividido apenas por contagem de linhas — uma divisão só é
  válida quando há responsabilidades genuinamente distintas, reuso em mais de um lugar, ou ganho
  real e demonstrável de manutenibilidade/testabilidade por trás dela.
- **FR-007**: Nenhuma abstração sem consumidor real MUST ser introduzida — proibido: interface/
  contrato para implementação única, wrapper que só repassa chamada, arquivo `index.ts` que só
  reexporta, camada adicional sem responsabilidade própria.
- **FR-008**: Após qualquer remoção/movimentação, todos os imports afetados MUST ser atualizados;
  nenhuma referência funcional a um caminho antigo MUST restar.
- **FR-009**: A reorganização MUST NOT alterar nenhum comportamento visual ou funcional observável
  pelo usuário final — mudança é estrutural/de limpeza de código-fonte apenas.
- **FR-010**: Ao final, build, lint, typecheck e a suíte de testes/verificações disponíveis para
  `interface/` MUST rodar sem erros novos introduzidos pela reorganização.
- **FR-011**: `interface/src/main/` e `interface/src/preload/` (processo principal do Electron)
  estão fora de escopo desta feature — a reorganização abrange `interface/src/renderer/src/` (a
  UI) apenas, exceto onde uma referência de import externo a ele precisar de atualização por
  consequência direta de um arquivo do renderer ter sido renomeado.

### Key Entities *(N/A — feature estrutural, sem novas entidades de dados)*

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% dos componentes/views que precisam falar com o Electron ou com a API o fazem
  através dos dois arquivos da camada de acesso externo (nomes corrigidos) — zero chamada direta
  de `fetch`/IPC fora dessa camada, verificável por busca no código-fonte.
- **SC-002**: Zero arquivo, export ou dependência sem consumidor real permanece em
  `interface/src/` ao final — verificável por uma checagem de uso (lint de imports não usados ou
  varredura manual equivalente).
- **SC-003**: Build, lint e typecheck de `interface/` terminam com o mesmo número (ou menor) de
  erros/avisos genuínos de antes da reorganização.
- **SC-004**: Navegação manual pelos fluxos principais do app (licenciamento, importação de
  arquivo, processamento, exportação, configurações, cada categoria de mídia) não mostra nenhuma
  diferença visual ou de comportamento em relação ao estado anterior à reorganização.
- **SC-005**: Uma busca por referências aos nomes de arquivo antigos da camada de acesso externo
  (`api.ts`/`backend.ts` pelos nomes específicos, não pelo conceito) no código-fonte funcional
  retorna zero ocorrências fora de documentação histórica.

## Assumptions

- "Interface" nesta especificação significa especificamente `interface/src/renderer/src/` (a UI
  Vue) — o processo principal do Electron (`src/main/`, `src/preload/`) está fora de escopo, salvo
  atualização mecânica de import quando um arquivo do renderer referenciado por eles for renomeado.
- A decisão de separar `components/ui/` de `components/` (US3) é condicional ao resultado da
  análise feita no plano técnico — esta especificação não obriga essa separação a acontecer se a
  análise concluir que não reduz fragmentação real para os 19 componentes existentes.
- Nenhuma dependência nova de `package.json` é introduzida por esta feature — é uma reorganização
  de arquivos já existentes, não uma adição de funcionalidade.
- "Build, lint, typecheck e testes disponíveis" refere-se às ferramentas já configuradas no
  projeto (`npm run build`, `npm run lint`, `npm run typecheck`) — não há suíte de testes
  automatizados de frontend hoje além dessas checagens estáticas; nenhuma suíte nova é criada por
  esta feature.
