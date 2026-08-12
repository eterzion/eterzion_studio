# Feature Specification: Reorganização em duas camadas (api/ + interface/)

**Feature Branch**: `002-api-interface-split`

**Created**: 2026-08-12

**Status**: Draft

**Input**: User description: "Reorganize a estrutura completa do projeto, separando claramente backend/API e interface gráfica em apenas duas pastas principais (api/ e interface/), absorvendo a CLI existente como lógica de serviço da API, sem alterar comportamento visual nem regras de negócio."

## User Scenarios & Testing *(mandatory)*

<!--
  This feature has no end-user-facing behavior — its audience is the people who build, ship,
  and maintain Astros Upscale (the desktop app's own team). "User" below means "person who
  works on this codebase or operates its build/deploy pipeline," not the app's end customer.
-->

### User Story 1 - Um desenvolvedor encontra qualquer parte do sistema em um de dois lugares (Priority: P1)

Um desenvolvedor que nunca trabalhou no repositório antes precisa descobrir onde fica a lógica de
licenciamento, ou onde fica uma tela específica do app. Hoje ele precisa saber que existem três
projetos Python irmãos (`astros_upscale/` na raiz, `interface/astros_upscale_api/`,
`interface/astros_licensing_service/`) além do app Electron, cada um com sua própria forma de ser
executado. Depois desta mudança, a resposta é sempre uma das duas: "é lógica de backend, está em
`api/`" ou "é interface visual, está em `interface/`".

**Why this priority**: é o valor central da feature — sem isso, nada mais importa. Toda a
motivação da reorganização é eliminar a ambiguidade sobre onde uma funcionalidade vive.

**Independent Test**: pode ser validado sozinho abrindo a raiz do repositório e verificando que
todo código-fonte da aplicação (excluindo arquivos de configuração globais realmente necessários)
está dentro de `api/` ou `interface/`, sem uma terceira pasta de código-fonte de aplicação na raiz.

**Acceptance Scenarios**:

1. **Given** a raiz do repositório reorganizada, **When** um desenvolvedor lista os diretórios de
   primeiro nível, **Then** o único código-fonte de aplicação presente está em `api/` ou
   `interface/` (arquivos globais como README, LICENSE, CI, `.gitignore` podem permanecer na raiz).
2. **Given** a pasta `api/`, **When** um desenvolvedor procura pela lógica de licenciamento, pela
   API HTTP local, ou pela lógica de processamento de mídia antes exposta só via CLI, **Then**
   encontra as três dentro de `api/`, organizadas de forma correspondente ao código já existente
   (sem pastas artificiais criadas só para bater com um exemplo).

---

### User Story 2 - Toda funcionalidade da CLI continua acessível, sem exigir terminal (Priority: P1)

Uma funcionalidade que hoje só existe como comando de terminal (`astros-upscale image ...`,
`astros-upscale video ...`, `astros-upscale audio ...`, `astros-upscale optimize ...`,
`astros-upscale models download/update ...`) precisa continuar disponível para quem usa o
aplicativo — mas exclusivamente através da API HTTP que a interface já consome, nunca exigindo que
alguém rode um comando manualmente.

**Why this priority**: é o requisito que mais risco de regressão carrega — remover a CLI sem
preservar a lógica de negócio por trás dela quebraria funcionalidade real do produto. É P1 junto
com a User Story 1 porque a reorganização de pastas sozinha, sem isso, deixaria capacidades do
produto inacessíveis.

**Independent Test**: pode ser testado chamando cada rota HTTP correspondente a uma funcionalidade
antes só disponível via CLI (download/atualização de modelo, otimização/conversão sem IA quando
aplicável) e confirmando que o resultado é equivalente ao que o comando de terminal produzia,
sem invocar nenhum script de linha de comando durante o teste.

**Acceptance Scenarios**:

1. **Given** uma funcionalidade antes exposta como subcomando da CLI (ex.: `models download`),
   **When** a mesma operação é solicitada através de uma rota HTTP da API, **Then** o resultado é
   equivalente ao do comando de terminal original, e nenhum processo de linha de comando precisou
   ser executado manualmente para obtê-lo.
2. **Given** o pacote de lógica de negócio antes usado pela CLI (registro de modelos, resolução de
   `content_type`, motor de mídia, utilitários), **When** a API precisa dessa lógica, **Then** ela
   é chamada como uma dependência de serviço dentro de `api/` — nunca via `sys.path` apontando para
   fora de `api/`, nem via `subprocess` invocando um script de CLI.
3. **Given** o antigo parser de argumentos/prompt interativo da CLI (`astros_upscale/cli.py`),
   **When** a migração é concluída e nada mais depende dele, **Then** ele é removido do
   repositório — sem deixar um comando de terminal como forma alternativa de acessar a mesma
   funcionalidade.

---

### User Story 3 - A interface continua funcionando exatamente como antes (Priority: P1)

Um usuário final do aplicativo (ou um desenvolvedor testando o app) abre o Astros Upscale depois da
reorganização e não percebe nenhuma diferença: a aplicação sobe a API automaticamente, todas as
telas carregam, o processamento de imagem/vídeo/áudio funciona, a licença ativa continua sendo
reconhecida, e nenhuma tela muda de aparência ou comportamento.

**Why this priority**: é uma restrição não-negociável explícita do pedido — a reorganização é
puramente estrutural e não pode ser percebida pelo usuário final. Compartilha o P1 porque uma
regressão aqui invalida a mudança inteira, mesmo que a nova estrutura de pastas esteja correta.

**Independent Test**: pode ser testado abrindo o aplicativo Electron do zero (sem nenhuma mudança
manual de configuração) e percorrendo os fluxos principais (licenciamento, importação de arquivo,
processamento, exportação, configurações) comparando com o comportamento anterior à migração.

**Acceptance Scenarios**:

1. **Given** o aplicativo Electron reorganizado sob `interface/`, **When** ele é iniciado,
   **Then** ele localiza e inicia a API local automaticamente a partir do novo caminho, sem
   intervenção manual.
2. **Given** uma tela qualquer da interface, **When** comparada com o comportamento antes da
   migração, **Then** nenhuma diferença visual ou funcional é observável.
3. **Given** o código-fonte da interface, **When** inspecionado, **Then** nenhum arquivo importa ou
   referencia diretamente um módulo interno de `api/` — toda comunicação passa pelos clientes
   HTTP/WebSocket já existentes.

---

### User Story 4 - O serviço de licenciamento continua isolado como processo (Priority: P2)

Um operador que sobe o serviço de licenciamento em produção precisa continuar podendo rodá-lo como
processo separado, com seu próprio banco de dados, suas próprias credenciais e sua própria porta —
mesmo que seu código-fonte agora resida fisicamente dentro de `api/` junto com a API local.

**Why this priority**: é um requisito de segurança pré-existente (não introduzido por esta
feature) que não pode regredir. É P2 porque, embora crítico, é uma preservação de uma restrição já
documentada, não uma capacidade nova — o risco de regressão é real, mas o comportamento a proteger
já está bem definido e testado hoje.

**Independent Test**: pode ser testado subindo o serviço de licenciamento isoladamente (sem subir a
API local) a partir do novo caminho, confirmando que ele inicializa, aceita ativações e emite
autorizações normalmente, e que a API local não falha ao tentar rodar sem ele configurado
(comportamento de licenciamento "não configurado" preservado).

**Acceptance Scenarios**:

1. **Given** o serviço de licenciamento reorganizado dentro de `api/`, **When** ele é iniciado,
   **Then** roda como processo próprio, em sua própria porta, com seu próprio banco de dados
   SQLite — sem compartilhar processo, porta ou segredo com a API local.
2. **Given** o banco de dados SQLite existente do serviço de licenciamento, **When** o serviço é
   reiniciado a partir do novo caminho, **Then** as licenças, instalações e autorizações
   previamente gravadas continuam acessíveis, sem perda de dados.

---

### Edge Cases

- O que acontece se um script externo (CI, ferramenta de desenvolvedor, documentação) ainda
  referenciar um caminho antigo (`interface/astros_upscale_api`, `interface/astros_licensing_service`,
  `astros_upscale.cli`) depois da migração? → Deve ser identificado e atualizado; não deve restar
  nenhuma referência funcional ao caminho antigo (grep por esses caminhos deve retornar vazio, exceto
  em texto histórico como este documento e o changelog).
- O que acontece se a lógica de negócio da CLI (`astros_upscale/core.py`, `audio.py`,
  `content_type.py`, `media_engine/`, `utils/`, etc.) for necessária tanto pela API local quanto,
  potencialmente, por uma ferramenta de manutenção interna (ex.: `scripts/mirror_models.py`,
  `scripts/benchmark_profiles.py`)? → Esses scripts continuam existindo como scripts de manutenção
  de repositório (não são "CLI do produto" na acepção desta feature — não são um canal alternativo
  para o usuário final acessar funcionalidade do produto); eles devem importar a lógica movida a
  partir do novo caminho dentro de `api/`, sem duplicá-la.
- O que acontece com os pesos de modelo ML em `/models` (raiz) e com o diretório `storage/` da API
  (uploads/outputs)? → Não são código-fonte de aplicação; permanecem como dados/artefatos
  referenciados pelo novo caminho da API dentro de `api/`, sem serem movidos para dentro da árvore
  de código-fonte nem duplicados.
- O que acontece se um teste existente depender de um caminho relativo específico (ex.:
  `parents[3]` para achar a raiz do repo)? → O cálculo de caminho relativo deve ser atualizado para
  refletir a nova profundidade de diretórios, e o teste deve continuar passando.
- O que acontece com o `Dockerfile` único hoje existente (só para a API local) e com o CI que tem
  `working-directory` fixo para os três projetos? → Devem ser atualizados para os novos caminhos;
  não deve ser criado um `docker-compose.yml` que não existia antes, apenas para preencher um
  exemplo.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O repositório MUST ter, na raiz, exatamente duas pastas de código-fonte de
  aplicação de primeiro nível: `api/` e `interface/`. Arquivos globais (README, LICENSE,
  `.gitignore`, CI, arquivos de ambiente de exemplo) MAY permanecer na raiz.
- **FR-002**: `api/` MUST conter a API HTTP local (hoje `interface/astros_upscale_api`), o serviço
  de licenciamento completo (hoje `interface/astros_licensing_service`), e a lógica de negócio de
  processamento de mídia hoje só acessível via `astros_upscale` (registro de modelos, `content_type`,
  motor de mídia, utilitários, realce facial, hardware) — exceto a camada de parsing de
  argumentos/prompt interativo (`astros_upscale/cli.py`), que MUST ser removida ao final da
  migração.
- **FR-003**: `interface/` MUST conter a totalidade do aplicativo visual Electron/Vue hoje em
  `interface/astros_upscale_app` (telas, componentes, layouts, assets, estados/stores, i18n,
  clientes HTTP/WebSocket), preservando sua estrutura interna já existente.
- **FR-004**: A estrutura interna de `api/` MUST ser adaptada à organização de código já existente
  (rotas, serviços, licenciamento, banco de dados, modelos/schemas Pydantic, validações,
  utilitários, integrações de pagamento) — novas pastas MUST NOT ser criadas apenas para
  corresponder a um exemplo ilustrativo, quando a estrutura existente já servir ao mesmo propósito.
- **FR-005**: Toda funcionalidade hoje acessível apenas via comando de terminal da CLI
  (`astros-upscale image/video/audio/optimize/models ...`) MUST continuar acessível através de uma
  rota HTTP da API depois da migração. Nenhuma funcionalidade do produto MUST exigir que o usuário
  execute um comando de terminal.
- **FR-006**: A lógica de negócio hoje usada pela CLI MUST ser reutilizada pelos serviços de `api/`
  como dependência de código dentro da mesma árvore — NÃO via manipulação de `sys.path` apontando
  para fora de `api/`, e NÃO via `subprocess` invocando um script de CLI.
- **FR-007**: `interface/` MUST NOT importar, `require`, ou de qualquer outra forma referenciar
  diretamente um módulo interno de `api/`. Toda comunicação entre as duas MUST ocorrer via
  HTTP/WebSocket, através dos contratos de API já existentes (rotas e schemas).
- **FR-008**: `api/` MUST NOT depender de, importar, ou ler qualquer arquivo específico de
  `interface/` (seus componentes, assets, saída de build, ou configuração). `api/` MUST poder ser
  executada e testada com `interface/` ausente.
- **FR-009**: O serviço de licenciamento, embora fisicamente organizado dentro de `api/`, MUST
  continuar sendo iniciado e executado como processo separado, com sua própria porta e seu próprio
  banco de dados SQLite — MUST NOT compartilhar processo, porta ou segredo (chaves de assinatura,
  variáveis de ambiente sensíveis) com a API local.
- **FR-010**: Todos os imports, caminhos relativos, variáveis de ambiente, entrypoints
  (`run.py` de cada serviço), o `Dockerfile` existente, o `pyinstaller.spec`, o CI
  (`.github/workflows/tests.yml`) e o processo de resolução de caminho da API no lado do Electron
  (`src/main/apiProcess.ts`) MUST ser atualizados para refletir a nova localização dos arquivos —
  nenhum caminho antigo MUST permanecer como referência ativa e funcional após a migração.
- **FR-011**: Nenhum arquivo MUST ser duplicado apenas para manter compatibilidade com o caminho
  antigo. Código legado (o antigo `astros_upscale/cli.py` e qualquer módulo que se torne órfão)
  MUST ser removido somente depois de confirmado que nada mais depende dele.
- **FR-012**: A migração MUST preservar o banco de dados SQLite existente do serviço de
  licenciamento, os arquivos de `storage/` (uploads/outputs) da API, e os manifests de integridade
  já gravados — sem perda de dados.
- **FR-013**: A migração MUST preservar todos os testes automatizados já existentes (os da API
  local, os do serviço de licenciamento, e os do pacote `astros_upscale` na raiz), adaptando seus
  caminhos e imports para a nova estrutura, sem apagá-los.
- **FR-014**: A migração MUST NOT alterar nenhuma regra de negócio existente, nem o comportamento
  visual ou funcional já observável da interface, além do necessário para que ela continue
  funcionando a partir do novo caminho.

### Key Entities *(N/A — feature estrutural, sem novas entidades de dados)*

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% do código-fonte de aplicação do repositório está contido em exatamente duas
  pastas de primeiro nível (`api/` e `interface/`), verificável por uma listagem simples da raiz.
- **SC-002**: 100% da suíte de testes automatizados pré-existente (API local, serviço de
  licenciamento, pacote `astros_upscale`) passa, executada a partir da nova estrutura, sem nenhum
  teste removido em relação à contagem anterior à migração.
- **SC-003**: Uma busca por referências textuais aos três caminhos antigos
  (`interface/astros_upscale_api`, `interface/astros_licensing_service`, import ativo de
  `astros_upscale.cli`) no código-fonte funcional (excluindo documentação histórica e este
  documento) retorna zero ocorrências.
- **SC-004**: Todas as operações antes disponíveis via subcomando da CLI continuam disponíveis via
  pelo menos uma rota HTTP, verificável chamando cada rota correspondente e obtendo um resultado
  equivalente ao do comando de terminal original.
- **SC-005**: O aplicativo Electron inicia, localiza e conecta à API local a partir do novo
  caminho sem nenhuma configuração manual adicional, em 100% das tentativas de inicialização
  testadas.
- **SC-006**: Nenhuma tela do aplicativo apresenta diferença visual ou de comportamento observável
  em relação ao estado anterior à migração, verificado por navegação manual pelos fluxos
  principais (licenciamento, importação, processamento, exportação, configurações).
- **SC-007**: O serviço de licenciamento inicializa e opera corretamente como processo
  independente a partir do novo caminho, preservando 100% dos registros já existentes em seu banco
  de dados.

## Assumptions

- "Comandos/CLI" nesta especificação refere-se especificamente ao pacote `astros_upscale` e seu
  entrypoint `astros_upscale.cli:main` (a superfície de comando voltada ao usuário final do
  produto) — não inclui scripts de manutenção interna do repositório (`scripts/mirror_models.py`,
  `scripts/benchmark_profiles.py`, `interface/astros_licensing_service/tools/build_package.py`),
  que continuam existindo como ferramentas de desenvolvedor, não como canal alternativo de acesso a
  funcionalidade do produto para o usuário final.
- Os pesos de modelo ML (`/models` na raiz) e os diretórios de armazenamento em tempo de execução
  (`storage/uploads`, `storage/outputs`) são dados/artefatos, não código-fonte de aplicação — a
  feature MUST relocá-los ou referenciá-los de forma consistente com a nova estrutura, mas eles não
  contam para os critérios de "código-fonte de aplicação" de FR-001/SC-001.
- Não existe hoje um `docker-compose.yml` no repositório; esta feature não introduz um apenas para
  preencher a estrutura final ilustrativa do pedido original — apenas atualiza o único `Dockerfile`
  já existente (da API local) para o novo caminho, e decide, durante o planejamento técnico, se um
  `Dockerfile` equivalente para o serviço de licenciamento é necessário dado que ele hoje não possui
  um.
- "Interface" nesta especificação é sinônimo do aplicativo Electron/Vue já existente
  (`astros_upscale_app`) — não há uma segunda superfície de interface no repositório.
- A reorganização é uma migração estrutural de arquivos e caminhos, não uma reescrita: a lógica de
  negócio movida MUST permanecer funcionalmente idêntica, com adaptações limitadas a imports,
  caminhos relativos e pontos de entrada.
