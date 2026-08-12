# Feature Specification: Consolidação estrutural de api/ por domínio

**Feature Branch**: `004-api-restructure`

**Created**: 2026-08-12

**Status**: Draft

**Input**: User description: "Refatoração estrutural completa da pasta api/ — reduzir
drasticamente a fragmentação de arquivos, consolidando por domínio/responsabilidade, sem alterar
comportamento funcional, contratos HTTP/WebSocket, segurança, licenciamento ou pagamentos.
Consolidar astros_upscale/ em processing.py + media.py + optimize.py; eliminar app/api/,
app/core/, app/models/ dentro de astros_upscale_api/ movendo tudo para app/ direto, consolidando
em routes.py, processing.py, jobs.py, licensing.py, security.py, schemas.py; consolidar
astros_licensing_service/app/ em licensing.py, packages.py, payments.py, routes.py, database.py.
Zero mudança de comportamento; todos os imports/testes/Dockerfiles/PyInstaller/pyproject
atualizados; suíte de testes completa passando ao final." (Constitution Princípio XI — API
Structure Is Consolidated By Domain, Not By Class)

## User Scenarios & Testing *(mandatory)*

<!--
  Como nas features 002 e 003, esta é uma mudança estrutural interna — o "usuário" abaixo é quem
  trabalha no código de api/, não o usuário final do produto. O usuário final não deve perceber
  nenhuma diferença (isso é, aliás, um requisito explícito): mesmos paths HTTP, mesmos schemas,
  mesmo comportamento de WebSocket, mesma segurança, mesma licença, mesmos pagamentos.
-->

### User Story 1 - Um desenvolvedor encontra a lógica de um domínio em um lugar só (Priority: P1)

Hoje, entender "como funciona o licenciamento na API local" exige abrir 5 arquivos
(`license_gate.py`, `license_cache.py`, `license_registry.py`, `profile_resolver.py`,
`offline_tolerance.py`) espalhados em `app/core/`, sem que o nome de nenhum deles diga sozinho
"isto é a lógica de licenciamento". O mesmo vale para segurança (5 arquivos), processamento (5
arquivos) e jobs (3 arquivos) — a granularidade de arquivo é por classe/mecanismo, não por
domínio que um desenvolvedor realmente precisa entender de uma vez. Um desenvolvedor que chega ao
projeto precisa conseguir abrir um único arquivo por domínio (`licensing.py`, `security.py`,
`processing.py`, `jobs.py`) e encontrar toda a lógica relacionada, sem perder o fio ao pular entre
arquivos.

**Why this priority**: é o problema mais concreto e mensurável da estrutura atual (18 arquivos em
`app/core/` para 5 domínios reais), afeta qualquer trabalho de manutenção na API, e a correção é
mecânica o suficiente para ser verificada objetivamente (contagem de arquivos por domínio).

**Independent Test**: abrir `api/astros_upscale_api/app/` e, para cada um dos domínios
(processamento, jobs, licenciamento, segurança, rotas, schemas), encontrar toda a lógica
relacionada em um único arquivo — sem precisar saber de antemão em qual dos 18 arquivos antigos
ela estava.

**Acceptance Scenarios**:

1. **Given** a árvore reorganizada, **When** um desenvolvedor procura a lógica de validação de
   licença (gate, cache, registro, resolução de perfil, tolerância offline), **Then** encontra
   tudo em `app/licensing.py`, sem precisar abrir outro arquivo.
2. **Given** a árvore reorganizada, **When** um desenvolvedor procura a lógica de isolamento e
   segurança (loader protegido, tempdir seguro, integridade, DPAPI, identidade instalada), **Then**
   encontra tudo em `app/security.py`.
3. **Given** a árvore reorganizada, **When** um desenvolvedor lista `app/astros_upscale_api/app/`,
   **Then** não existem mais os diretórios `app/api/`, `app/core/`, `app/models/` como divisão
   técnica obrigatória.

---

### User Story 2 - Zero mudança de comportamento observável (Priority: P1)

A consolidação é puramente uma reorganização de arquivos — nenhum consumidor da API (o app
`interface/`, um teste, um cliente externo) pode observar qualquer diferença. Isso inclui: todo
path HTTP, método, parâmetro, schema de request/response, código de status, comportamento de
WebSocket (`ws_progress`), execução assíncrona de jobs (fila, cancelamento, progresso, tratamento
de falha), validação de licença, criptografia de pacotes, e lógica de provedores de pagamento
(Stripe, Mercado Pago).

**Why this priority**: é a restrição mais explícita e não-negociável do pedido original — sem
ela, a reorganização não é uma refatoração, é uma reescrita, o que o pedido proíbe
explicitamente.

**Independent Test**: rodar a suíte de testes completa das três subpastas antes e depois da
reorganização — mesmo conjunto de testes (nenhum removido), mesmo resultado (verde), sem
nenhuma mudança de asserção que reflita mudança de comportamento (só de import path, quando
necessário).

**Acceptance Scenarios**:

1. **Given** a suíte de testes de `api/astros_upscale`, `api/astros_upscale_api` e
   `api/astros_licensing_service` rodando antes da reorganização, **When** a mesma suíte roda
   depois, **Then** o mesmo número de testes passa, nenhum teste foi removido, e nenhum teste
   precisou mudar sua asserção (só, quando necessário, seu import).
2. **Given** um cliente HTTP que hoje chama `POST /jobs`, `GET /jobs/{id}`, `WS /ws/progress/{id}`
   (ou qualquer outra rota existente), **When** a reorganização é concluída, **Then** a mesma
   chamada, com o mesmo payload, produz a mesma resposta (mesmo path, método, schema, status).

---

### User Story 3 - Nenhum código morto, diretório vazio ou wrapper de compatibilidade permanece (Priority: P2)

Depois de mover o código para os novos módulos consolidados, os arquivos antigos, diretórios que
ficarem vazios (`app/api/`, `app/core/`, `app/models/`, `payments/`), imports não usados, e
qualquer wrapper criado só para redirecionar uma chamada antiga para a nova precisam deixar de
existir. `legacy_identifiers.py` é a única exceção condicional: sua remoção/absorção só acontece
depois de confirmar que nada externo (dados persistidos, um cliente já publicado) ainda depende
dos identificadores antigos de modelo que ele mapeia.

**Why this priority**: é o requisito explícito de "não deixar duas versões coexistindo" do pedido
original, e o mais barato de verificar objetivamente (grep por uso, `find` por diretório vazio) —
mas depende das Histórias 1 e 2 estarem concluídas primeiro (só se remove o antigo depois que o
novo funciona).

**Independent Test**: rodar uma varredura de import/uso em toda a árvore de `api/`; nenhum dos
arquivos antigos (`upscaler.py`, `license_gate.py`, `routes_jobs.py`, etc.) existe mais, e nenhum
diretório vazio permanece.

**Acceptance Scenarios**:

1. **Given** a reorganização concluída, **When** se busca por qualquer um dos nomes de arquivo
   antigos (`upscaler.py`, `job_manager.py`, `license_gate.py`, `routes_jobs.py`,
   `authorizations.py` isolado, `package_crypto.py` isolado, etc.) em `api/`, **Then** a busca não
   encontra nenhuma ocorrência (nem como arquivo, nem como import).
2. **Given** a reorganização concluída, **When** se lista `api/astros_upscale_api/app/` e
   `api/astros_licensing_service/app/`, **Then** nenhum diretório vazio (`app/api/`, `app/core/`,
   `app/models/`, `payments/`) permanece.
3. **Given** `legacy_identifiers.py` ainda for necessário (dados/clientes existentes dependem
   dele), **When** a reorganização é concluída, **Then** sua lógica está incorporada a
   `processing.py`, não mantida como arquivo autônomo separado.

---

### User Story 4 - A build e o empacotamento continuam funcionando (Priority: P1)

Depois de mover os arquivos, todo processo que referencia um caminho antigo — Dockerfiles (das
duas APIs), `pyinstaller.spec`, `pyproject.toml`, `requirements*.txt`, o processo principal do
Electron (`interface/src/main/apiProcess.ts`) e o workflow de CI (`.github/workflows/tests.yml`)
— precisa continuar funcionando sem alteração de comportamento, apontando para os novos caminhos
onde necessário.

**Why this priority**: sem isso, a reorganização quebra silenciosamente o empacotamento e o CI —
um tipo de regressão que só aparece depois, fora do fluxo normal de `pytest`.

**Independent Test**: rodar o build/import básico de cada serviço (`uvicorn`/`python -c "import
app.main"` ou equivalente) e, onde o ambiente disponível permitir, o Dockerfile/PyInstaller.

**Acceptance Scenarios**:

1. **Given** a reorganização concluída, **When** `api/astros_upscale_api` e
   `api/astros_licensing_service` são iniciados (`uvicorn app.main:app`), **Then** ambos sobem sem
   erro de import.
2. **Given** a reorganização concluída, **When** o CI (`.github/workflows/tests.yml`) roda,
   **Then** os três jobs (Upscale API, Licensing service, Desktop app) continuam verdes sem
   alteração de comportamento — apenas de caminho, se necessário.

---

### Edge Cases

- O que acontece se um módulo-alvo de consolidação (ex.: `processing.py` em
  `astros_upscale_api/app/`) ficar grande demais ou reunir responsabilidades genuinamente
  independentes depois da fusão? → Permanece dividido nessa parte (Constitution Princípio XI:
  "genuine technical separation still stands"); a decisão e a justificativa são registradas no
  plano.
- O que acontece com testes que hoje importam diretamente de um módulo específico (ex.:
  `from app.core.license_gate import ...`)? → O import é atualizado para o novo caminho
  consolidado; a asserção do teste não muda.
- O que acontece se `legacy_identifiers.py` for confirmado como ainda necessário? → Sua lógica é
  incorporada a `processing.py` (não removida, não mantida como arquivo separado).
- O que acontece com a pasta `astros_upscale_api/models/` (pesos `.pth` de teste, não o
  `app/models/schemas.py`)? → Fora de escopo — é armazenamento de artefato de teste, não código;
  só `app/models/` (o antigo pacote Python de schemas) é afetado por esta reorganização.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `api/astros_upscale/` MUST consolidar `core.py`, `audio.py`, `content_type.py`,
  `face_enhance.py`, `hardware.py` em `processing.py` (registro/gerenciamento de modelos, upscale,
  tiling, detecção foto/anime, recuperação facial, detecção de hardware, seleção de engines).
- **FR-002**: `api/astros_upscale/` MUST consolidar `media_engine/{probe,temporal,transcode}.py` e
  `utils/{download,image_io,video_io}.py` em `media.py` (áudio, leitura/escrita de imagem e vídeo,
  probe, processamento temporal, transcode, download de recursos).
- **FR-003**: `api/astros_upscale/optimize.py` MUST permanecer como está (já é um domínio próprio
  e coerente).
- **FR-004**: `astros_upscale_api/app/` MUST eliminar os diretórios `app/api/`, `app/core/`,
  `app/models/` como divisão técnica obrigatória, com todo o código movido para módulos
  diretamente dentro de `app/`.
- **FR-005**: `astros_upscale_api/app/` MUST consolidar as 7 rotas (`routes_jobs.py`,
  `routes_files.py`, `routes_components.py`, `routes_identity.py`, `routes_license.py`,
  `routes_preview.py`) e `ws_progress.py` em `routes.py`, preservando internamente organização
  lógica clara por seção/router, sem alterar nenhum path, método, parâmetro, schema, código HTTP
  ou comportamento de WebSocket.
- **FR-006**: `astros_upscale_api/app/` MUST consolidar `upscaler.py`, `video_upscaler.py`,
  `audio_processor.py`, `component_manager.py`, `capacity.py` em `processing.py`.
- **FR-007**: `astros_upscale_api/app/` MUST consolidar `job_manager.py`, `worker_supervisor.py`,
  `isolated_worker.py` em `jobs.py`, preservando execução assíncrona, workers, subprocessos,
  filas, cancelamentos, progresso e tratamento de falhas.
- **FR-008**: `astros_upscale_api/app/` MUST consolidar `license_gate.py`, `license_cache.py`,
  `license_registry.py`, `profile_resolver.py`, `offline_tolerance.py` em `licensing.py`.
- **FR-009**: `astros_upscale_api/app/` MUST consolidar `protected_loader.py`,
  `secure_tempdir.py`, `integrity.py`, `dpapi.py`, `install_identity.py` em `security.py`, sem
  enfraquecer nenhum mecanismo existente.
- **FR-010**: `astros_upscale_api/app/models/schemas.py` MUST mover para `astros_upscale_api/app/
  schemas.py`; a pasta `app/models/` MUST ser removida assim que ficar vazia.
- **FR-011**: `astros_licensing_service/app/` MUST consolidar `licensing.py`,
  `authorizations.py`, `service_identity.py` em `licensing.py`, mantendo separação lógica interna
  clara entre ativação, autorização, identidade do serviço e regras de licença.
- **FR-012**: `astros_licensing_service/app/` MUST consolidar `packages.py`,
  `package_crypto.py` em `packages.py`, sem enfraquecer a criptografia existente.
- **FR-013**: `astros_licensing_service/app/` MUST consolidar `payments/base.py`,
  `payments/stripe_provider.py`, `payments/mercadopago_provider.py` em `payments.py`, preservando
  os contratos `PaymentProvider`, `StripeProvider`, `MercadoPagoProvider`.
- **FR-014**: `astros_licensing_service/app/` MUST consolidar `routes_activation.py`,
  `routes_authorizations.py`, `routes_packages.py`, `routes_webhooks.py` em `routes.py`,
  preservando todos os contratos HTTP existentes.
- **FR-015**: `astros_licensing_service/app/db.py` MAY ser renomeado para `database.py` se
  consistente com a convenção do restante do projeto.
- **FR-016**: O sistema MUST preservar, sem alteração, todo path HTTP, método, parâmetro de
  request, schema de request/response, código de status HTTP e comportamento de WebSocket
  existente nas duas APIs.
- **FR-017**: O sistema MUST preservar, sem alteração, a lógica de execução assíncrona de jobs
  (fila, cancelamento, progresso, tratamento de falha), de validação de licença, de criptografia
  de pacotes, e de processamento de pagamentos.
- **FR-018**: Depois da migração, o sistema MUST remover arquivos antigos não mais referenciados,
  diretórios vazios, imports obsoletos, wrappers que só redirecionam para a nova localização,
  aliases sem uso e duplicações introduzidas pela migração.
- **FR-019**: `legacy_identifiers.py` MUST NOT ser removido sem antes confirmar que nada externo
  (dados persistidos, clientes já publicados) ainda depende dele; se ainda necessário, sua lógica
  é incorporada a `processing.py` em vez de mantida como arquivo autônomo.
- **FR-020**: Um módulo-alvo de consolidação MUST permanecer dividido além do ponto proposto
  quando parte dele tiver responsabilidade genuinamente separável/testável de forma independente,
  ou quando a fusão produzir um arquivo grande demais para ser lido como um domínio coerente.
- **FR-021**: O sistema MUST atualizar todos os imports, testes, mocks, monkeypatches, fixtures,
  entrypoints (`run.py`), Dockerfiles, `pyinstaller.spec`, `pyproject.toml`, `requirements*.txt`,
  scripts de build e documentação técnica que referencie os caminhos antigos.
- **FR-022**: Nenhum teste MUST ser removido apenas por ter quebrado durante a reorganização —
  falhas de import são corrigidas, não os testes descartados.
- **FR-023**: Os testes MUST continuar organizados por domínio em arquivos separados quando isso
  ajudar diagnóstico — não MUST ser forçados em arquivos de teste gigantes só para espelhar a
  consolidação do código de produção.
- **FR-024**: A reorganização MUST NOT introduzir nenhuma abstração nova (wrapper, interface de
  implementação única, re-export) cujo único propósito seja facilitar a fusão dos arquivos.

### Key Entities

- **Módulo consolidado**: um arquivo Python que passa a concentrar a lógica de um domínio
  inteiro (ex.: `processing.py`, `licensing.py`, `security.py`) — substitui múltiplos arquivos de
  granularidade por classe/mecanismo.
- **Domínio**: um agrupamento de responsabilidade real dentro de uma das três subpastas de `api/`
  (processamento de mídia, orquestração de jobs, licenciamento, segurança/isolamento, rotas HTTP,
  schemas, pacotes, pagamentos) — a unidade em torno da qual os arquivos se consolidam.
- **Contrato preservado**: qualquer comportamento observável por um consumidor externo (path
  HTTP, schema, código de status, mensagem WebSocket) que não pode mudar como resultado desta
  reorganização.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: O número de arquivos Python de produção em `api/astros_upscale_api/app/` (excluindo
  testes e `__init__.py`) cai de 28 (6 `routes_*.py` + `ws_progress.py` + 18 em `core/` +
  `main.py` + `config.py` + `models/schemas.py`) para no máximo 8 (`main.py`, `config.py`,
  `routes.py`, `processing.py`, `jobs.py`, `licensing.py`, `security.py`, `schemas.py`, mais
  qualquer arquivo adicional justificado por FR-020).
- **SC-002**: O número de arquivos Python de produção em `api/astros_licensing_service/app/`
  (excluindo testes e `__init__.py`) cai de 15 (`main.py`, `config.py`, `db.py`, `licensing.py`,
  `authorizations.py`, `service_identity.py`, `packages.py`, `package_crypto.py`, 3 em
  `payments/`, 4 `routes_*.py`) para no máximo 7 (`main.py`, `config.py`, `database.py`,
  `licensing.py`, `packages.py`, `payments.py`, `routes.py`).
- **SC-003**: O número de arquivos Python de produção em `api/astros_upscale/` (excluindo testes e
  `__init__.py`) cai de 13 (`core.py`, `audio.py`, `content_type.py`, `face_enhance.py`,
  `hardware.py`, `legacy_identifiers.py`, `optimize.py`, 3 em `media_engine/`, 3 em `utils/`)
  para no máximo 3 (`processing.py`, `media.py`, `optimize.py` — `legacy_identifiers.py` é
  absorvido em `processing.py`, não mantido como arquivo próprio, conforme FR-019/research.md
  Decisão 1, que já confirmou ausência de dependência externa).
- **SC-004**: 100% dos testes que passavam antes da reorganização continuam passando depois, com
  a mesma contagem de testes coletados em cada uma das três subpastas.
- **SC-005**: Zero diferença de contrato observável — toda rota, schema, código de status e
  mensagem WebSocket testados antes da reorganização produzem exatamente o mesmo resultado
  depois.
- **SC-006**: Zero referência residual a um caminho de arquivo antigo em código, testes,
  Dockerfiles, `pyinstaller.spec`, `pyproject.toml`, requirements, CI ou documentação técnica
  viva.

## Assumptions

- O ambiente de execução usado para validar (rodar testes, subir os serviços) é o mesmo já
  configurado no repositório (`.venv` na raiz, `uv`/`pytest` conforme `.github/workflows/
  tests.yml`) — nenhuma ferramenta nova é introduzida.
- "Zero mudança de comportamento" é verificado pela suíte de testes existente mais a inspeção
  direta de rotas/schemas — esta reorganização não introduz uma nova suíte de testes de contrato,
  apenas preserva e adapta a existente (Constitution Princípio VIII).
- A pasta `api/astros_upscale_api/models/` (armazenamento de peso `.pth` de teste) e
  `api/astros_upscale_api/app/storage/` (uploads/outputs em runtime) estão fora de escopo — não
  são código-fonte fragmentado, são artefatos/armazenamento.
- Onde Docker/PyInstaller não puderem ser executados no ambiente disponível (ex.: falta de Docker
  instalado), a validação se limita a conferir que os caminhos referenciados nos arquivos de
  configuração foram atualizados corretamente, registrando essa limitação explicitamente em vez
  de omiti-la (Constitution: reportar limitações técnicas, nunca omitir).
