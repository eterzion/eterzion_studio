---

description: "Task list for feature 004-api-restructure"

---

# Tasks: Consolidação estrutural de api/ por domínio

**Input**: Design documents from `/specs/004-api-restructure/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/README.md, quickstart.md

**Tests**: as três subpastas já têm suítes pytest próprias — nenhuma nova é criada; a
verificação é rodar/corrigir a suíte existente (Constitution Princípio VIII), nunca removê-la.

**Organization**: as fases seguem a ordem de dependência real por subprojeto documentada em
`research.md` (Decisões 1–3), não a ordem em que os arquivos foram citados no pedido original —
um módulo consolidado só é escrito depois que tudo do qual ele importa já existe. Cada tarefa de
implementação está rotulada com a(s) história(s) de usuário de `spec.md` que ela serve: US1
(lógica de um domínio em um lugar só), US2 (zero mudança de comportamento), US3 (sem código morto/
diretório vazio/wrapper), US4 (build/empacotamento continuam funcionando).

## Format: `[ID] [P?] [Story] Description`

## Path Conventions

Todos os caminhos abaixo são relativos a `api/`, salvo indicação contrária.

---

## Phase 1: Setup (baseline)

- [x] T001 Confirmar árvore de trabalho git limpa (`git status`) antes de iniciar.
- [x] T002 Capturar baseline de arquivos (excluindo `__init__.py` e testes):
  `find astros_upscale -name "*.py" ! -name "__init__.py" -not -path "*/tests/*" | wc -l` (deve
  dar 13), `find astros_upscale_api/app -name "*.py" ! -name "__init__.py" | wc -l` (deve dar 28),
  `find astros_licensing_service/app -name "*.py" ! -name "__init__.py" | wc -l` (deve dar 15) —
  registrar os três números (para comparar com SC-001/SC-002/SC-003 no final).
- [x] T003 Capturar baseline de testes coletados: rodar `pytest --collect-only -q | tail -1` nas
  três subpastas (`astros_upscale`, `astros_upscale_api`, `astros_licensing_service`) e registrar
  a contagem exata (para comparar com SC-004 no final).

---

## Phase 2: astros_upscale/ — consolidação em processing.py + media.py

**Goal**: `core.py`, `audio.py`, `content_type.py`, `face_enhance.py`, `hardware.py`,
`legacy_identifiers.py` consolidados em `processing.py`; `media_engine/*` + `utils/*`
consolidados em `media.py`; `optimize.py` inalterado exceto import; todo consumidor externo
(dentro de `astros_upscale_api`) e todo teste atualizado.

**Independent Test**: `import astros_upscale.processing` e `import astros_upscale.media`
funcionam sem erro; `pytest astros_upscale/tests -q` passa com a mesma contagem da baseline
(T003).

### Implementation

- [x] T004 [US1] Criar `astros_upscale/media.py` consolidando `media_engine/probe.py`,
  `media_engine/temporal.py`, `media_engine/transcode.py`, `utils/download.py`,
  `utils/image_io.py`, `utils/video_io.py` — sem alterar nenhuma assinatura ou comportamento;
  ajustar os imports internos entre esses seis arquivos (hoje `media_engine/temporal.py` importa
  de `.transcode` e `utils/video_io.py` importa de `..media_engine`) para referência direta dentro
  do mesmo arquivo.
- [x] T005 [US1] Criar `astros_upscale/processing.py` consolidando `core.py`, `audio.py`,
  `content_type.py`, `face_enhance.py`, `hardware.py`, `legacy_identifiers.py` — sem alterar
  nenhuma assinatura ou comportamento; atualizar os imports que hoje apontam para
  `.utils.download` (em `core.py`, `face_enhance.py`) e `.media_engine` (em `audio.py`) para
  `.media` (FR-019: `legacy_identifiers.py` é absorvido diretamente, não mantido como arquivo
  próprio — research.md Decisão 1 confirmou que seu único consumidor é interno a `core.py`).
- [x] T006 [US1] [US3] `git rm` os 9 arquivos originais (`core.py`, `audio.py`,
  `content_type.py`, `face_enhance.py`, `hardware.py`, `legacy_identifiers.py`,
  `media_engine/probe.py`, `media_engine/temporal.py`, `media_engine/transcode.py`) e os 3 de
  `utils/` (`download.py`, `image_io.py`, `video_io.py`); remover `media_engine/` e `utils/`
  assim que ficarem vazios (incluindo seus `__init__.py`, se não tiverem outro conteúdo).
- [x] T007 [US2] Atualizar o import de `optimize.py` (`.media_engine`, `.utils.image_io` →
  `.media`) — nenhuma outra linha muda.
- [x] T008 [US2] Atualizar os 6 pontos de import em `astros_upscale_api/app/` que hoje
  referenciam `astros_upscale.core`, `astros_upscale.audio`, `astros_upscale.content_type`,
  `astros_upscale.face_enhance`, `astros_upscale.hardware`, `astros_upscale.media_engine.*`,
  `astros_upscale.utils.*` diretamente (`app/api/routes_jobs.py`, `app/api/routes_preview.py`,
  `app/core/audio_processor.py`, `app/core/capacity.py`, `app/core/component_manager.py`,
  `app/core/job_manager.py`, `app/core/license_registry.py`, `app/core/profile_resolver.py`,
  `app/core/upscaler.py`, `app/core/video_upscaler.py` — ver lista completa em `research.md`
  Decisão 2) para `astros_upscale.processing`/`astros_upscale.media` conforme o símbolo.
- [x] T009 [US2] Corrigir os imports nos 7 arquivos de teste de `astros_upscale/tests/` para os
  novos caminhos (`processing`/`media`), sem alterar nenhuma asserção.
- [x] T010 [US2] Rodar `pytest astros_upscale/tests -q` — mesma contagem de testes da baseline
  (T003), 100% verde.

**Checkpoint**: `astros_upscale/` consolidado; `astros_upscale_api` ainda não roda (seus próprios
imports internos serão corrigidos na Fase 3) — normal neste ponto.

---

## Phase 3: astros_upscale_api/app/ — consolidação em routes/processing/jobs/licensing/security/schemas

**Goal**: `app/api/`, `app/core/`, `app/models/` deixam de existir como divisão técnica
obrigatória; todo o código movido para `app/routes.py`, `app/processing.py`, `app/jobs.py`,
`app/licensing.py`, `app/security.py`, `app/schemas.py`, sem alterar nenhum contrato HTTP/
WebSocket (FR-016).

**Independent Test**: `python -c "import app.main"` dentro de `astros_upscale_api/` não gera erro
de import; `pytest astros_upscale_api/tests -q` passa com a mesma contagem da baseline (T003).

### Implementation

Ordem por dependência real (`research.md` Decisão 2): `schemas.py` → `security.py` →
`licensing.py` → `processing.py` → `jobs.py` → `routes.py`.

- [x] T011 [P] [US1] Mover `app/models/schemas.py` para `app/schemas.py` (sem alterar nenhum
  campo/tipo/validação de schema — FR-016); remover `app/models/` (incluindo `__init__.py`) assim
  que ficar vazia.
- [x] T012 [US1] Criar `app/security.py` consolidando `app/core/protected_loader.py`,
  `app/core/secure_tempdir.py`, `app/core/integrity.py`, `app/core/dpapi.py`,
  `app/core/install_identity.py` — sem enfraquecer nenhum mecanismo (FR-009); `install_identity.py`
  hoje importa `dpapi`/`secure_tempdir` e `protected_loader.py` importa `install_identity` —
  ambos internos ao mesmo arquivo consolidado, viram referência direta.
- [x] T013 [US1] Criar `app/licensing.py` consolidando `app/core/license_gate.py`,
  `app/core/license_cache.py`, `app/core/license_registry.py`, `app/core/profile_resolver.py`,
  `app/core/offline_tolerance.py` — `license_gate.py` hoje importa `license_cache`/
  `offline_tolerance`, ambos internos ao mesmo arquivo consolidado.
- [x] T014 [US1] Criar `app/processing.py` consolidando `app/core/upscaler.py`,
  `app/core/video_upscaler.py`, `app/core/audio_processor.py`, `app/core/component_manager.py`,
  `app/core/capacity.py` — `component_manager.py` hoje importa `app.core.profile_resolver` e
  `app.core.license_registry.get_model_license`; atualizar para `app.licensing` (criado em T013).
- [x] T015 [US1] Criar `app/jobs.py` consolidando `app/core/job_manager.py`,
  `app/core/worker_supervisor.py`, `app/core/isolated_worker.py` — preservando execução
  assíncrona, workers, subprocessos, filas, cancelamentos, progresso e tratamento de falhas
  (FR-007); `isolated_worker.py`/`job_manager.py` hoje importam `upscaler`/`video_upscaler`/
  `audio_processor` (atualizar para `app.processing`, criado em T014); `worker_supervisor.py`
  hoje importa `secure_tempdir` (atualizar para `app.security`, criado em T012).
- [x] T016 [US1] [US2] Criar `app/routes.py` consolidando `app/api/routes_jobs.py`,
  `app/api/routes_files.py`, `app/api/routes_components.py`, `app/api/routes_identity.py`,
  `app/api/routes_license.py`, `app/api/routes_preview.py`, `app/api/ws_progress.py` —
  preservando internamente organização lógica clara por seção/router, e sem alterar nenhum path,
  método, parâmetro, schema, código HTTP ou comportamento de WebSocket (FR-005, FR-016); atualizar
  os imports que hoje apontam para `app.core.*`/`app.models.schemas` para `app.processing`,
  `app.jobs`, `app.licensing`, `app.security`, `app.schemas` conforme o símbolo.
- [x] T017 [US2] Verificar explicitamente, comparando com o estado anterior (git diff ou lista
  registrada em `contracts/README.md`), que `app/routes.py` preserva cada path, método e schema —
  nenhuma rota omitida ou renomeada durante a consolidação.
- [x] T018 [US1] Atualizar `app/main.py` (imports de `app.api`/`app.core` → `app.routes`,
  `app.jobs`, `app.security`) e `app/config.py` se necessário.
- [x] T019 [US1] [US3] `git rm` os 6 arquivos `routes_*.py` + `ws_progress.py`, os 18 arquivos de
  `app/core/`, e `app/models/schemas.py` (se ainda não removido em T011); remover `app/api/` e
  `app/core/` (incluindo `__init__.py`) assim que ficarem vazios.
- [x] T020 [US2] Corrigir os imports nos ~29 arquivos de teste de `astros_upscale_api/tests/`
  para os novos caminhos (`app.routes`, `app.processing`, `app.jobs`, `app.licensing`,
  `app.security`, `app.schemas`), sem alterar nenhuma asserção.
- [x] T021 [US4] Rodar `python -c "import app.main"` dentro de `astros_upscale_api/` — confirma
  que a ordem de consolidação (T011–T016) não introduziu import circular.
- [x] T022 [US2] Rodar `pytest astros_upscale_api/tests -q` — mesma contagem de testes da
  baseline (T003), 100% verde.

**Checkpoint**: `astros_upscale_api/` consolidado e funcional; `app/api/`, `app/core/`,
`app/models/` não existem mais.

---

## Phase 4: astros_licensing_service/app/ — consolidação em licensing/packages/payments/routes/database

**Goal**: `app/` consolidado em `main.py`, `config.py`, `database.py`, `licensing.py`,
`packages.py`, `payments.py`, `routes.py`, sem alterar nenhum contrato HTTP (FR-017) nem
enfraquecer a criptografia de pacotes (FR-012) ou a lógica de pagamentos (FR-013).

**Independent Test**: `python -c "import app.main"` dentro de `astros_licensing_service/` não
gera erro de import; `pytest astros_licensing_service/tests -q` passa com a mesma contagem da
baseline (T003).

### Implementation

Ordem por dependência real (`research.md` Decisão 3, revisada após `/speckit.analyze` encontrar
um ciclo real entre `licensing.py` e `packages.py`): `database.py` → `payments.py` →
`packages.py` → `licensing.py` → `routes.py`.

- [x] T023 [US1] Renomear `app/db.py` para `app/database.py` (FR-015) — só o nome do arquivo
  muda, conteúdo inalterado.
- [x] T024 [US1] Criar `app/payments.py` consolidando `app/payments/base.py`,
  `app/payments/stripe_provider.py`, `app/payments/mercadopago_provider.py` — preservando
  exatamente os contratos `PaymentProvider`, `StripeProvider`, `MercadoPagoProvider` (FR-013);
  `mercadopago_provider.py`/`stripe_provider.py` hoje importam `payments.base.PaymentEvent`,
  interno ao mesmo arquivo consolidado.
- [x] T025 [US1] Criar `app/packages.py` consolidando `app/packages.py` (original),
  `app/package_crypto.py` — sem enfraquecer a criptografia existente (FR-012). **Ponto crítico**:
  `package_crypto.py` hoje importa `app.service_identity.get_signing_key` no topo do arquivo, e
  `service_identity.py` se funde em `licensing.py` (T026, escrito depois) — importar isso no topo
  de `packages.py` criaria um ciclo real com `licensing.py` (que também precisa de
  `app.packages.latest_version`, ver T026). Esse import MUST ser tornado tardio: mover
  `from app.service_identity import get_signing_key` para dentro do corpo de `build_package()`
  (o único lugar onde é usado), em vez de manter no topo do arquivo — mesmo padrão já usado no
  projeto para quebrar ciclo (`astros_upscale/core.py`'s import tardio de
  `legacy_identifiers.removal_reason` dentro de `resolve_weights()`).
- [x] T026 [US1] Criar `app/licensing.py` consolidando `app/licensing.py` (original),
  `app/authorizations.py`, `app/service_identity.py` — mantendo separação lógica interna clara
  entre ativação, autorização, identidade do serviço e regras de licença (FR-011); `licensing.py`
  original hoje importa `app.payments.base.PaymentEvent` (atualizar para `app.payments`, criado
  em T024); `authorizations.py` hoje importa `app.licensing` (interno ao arquivo consolidado) e
  `app.packages.latest_version` (atualizar para `app.packages`, já criado em T025 — este import
  permanece no topo do arquivo normalmente, sem necessidade de import tardio, já que o ciclo foi
  quebrado do lado de `packages.py` em T025).
- [x] T027 [US1] [US2] Criar `app/routes.py` consolidando `app/routes_activation.py`,
  `app/routes_authorizations.py`, `app/routes_packages.py`, `app/routes_webhooks.py` —
  preservando todos os contratos HTTP existentes (FR-014, FR-017); `routes_webhooks.py` hoje
  importa `app.licensing.create_license_from_payment` e
  `app.payments.{mercadopago_provider,stripe_provider}` (atualizar para os módulos consolidados
  em T024/T026).
- [x] T028 [US2] Verificar explicitamente, comparando com o estado anterior, que `app/routes.py`
  preserva cada path, método e schema das 4 rotas originais — nenhuma omitida ou renomeada.
- [x] T029 [US1] Atualizar `app/main.py` (imports de `app.db`, `app.service_identity` →
  `app.database`, `app.licensing`) e `app/config.py` se necessário.
- [x] T030 [US1] [US3] `git rm` os arquivos originais (`authorizations.py`, `package_crypto.py`,
  `service_identity.py`, `routes_activation.py`, `routes_authorizations.py`,
  `routes_packages.py`, `routes_webhooks.py`, `payments/base.py`, `payments/stripe_provider.py`,
  `payments/mercadopago_provider.py`, `payments/__init__.py`); remover `app/payments/` assim que
  ficar vazio.
- [x] T031 [US4] Atualizar `tools/build_package.py` (`app.db` → `app.database`,
  `app.package_crypto` → `app.packages`).
- [x] T032 [US2] Corrigir os imports nos 6 arquivos de teste de `astros_licensing_service/tests/`
  para os novos caminhos, sem alterar nenhuma asserção.
- [x] T033 [US4] Rodar `python -c "import app.main"` dentro de `astros_licensing_service/` —
  confirma que a ordem de consolidação (T023–T027) não introduziu import circular.
- [x] T034 [US2] Rodar `pytest astros_licensing_service/tests -q` — mesma contagem de testes da
  baseline (T003), 100% verde.

**Checkpoint**: `astros_licensing_service/` consolidado e funcional; `app/payments/` não existe
mais.

---

## Phase 5: Polish & Cross-Cutting Concerns

- [x] T035 [US3] Varredura final de caminho antigo em todo `api/`: rodar os três grep de
  `quickstart.md` §2 (`app.core.`/`app.api.`/`app.models.`, `app.db`/`app.package_crypto`,
  `from astros_upscale.core`/`.audio`/`.content_type`/`.face_enhance`/`.hardware`/
  `.media_engine`/`.utils.`) — todos devem retornar vazio; ao mesmo tempo, revisar os 13 módulos
  novos e confirmar que nenhum deles ganhou uma classe/função wrapper, um `index`-style re-export,
  ou uma interface de implementação única criada só para facilitar a fusão (FR-024) — a
  consolidação move código, não adiciona indireção.
- [x] T036 [US3] Confirmar que nenhum diretório vazio permanece:
  `astros_upscale_api/app/api`, `astros_upscale_api/app/core`, `astros_upscale_api/app/models`,
  `astros_licensing_service/app/payments`, `astros_upscale/media_engine`, `astros_upscale/utils`
  — todos devem reportar "No such file or directory".
- [x] T037 [P] [US4] Revisar `api/pyproject.toml`, `api/requirements.txt`,
  `astros_upscale_api/requirements*.txt`, `astros_licensing_service/requirements*.txt` — confirmar
  que nenhuma dependência ficou órfã (comprovadamente sem uso, FR-021) e que nenhuma referencia
  módulo interno removido; nenhuma versão de pacote é alterada (research.md Decisão 5 já indicava
  zero mudança esperada — esta tarefa confirma no estado final).
- [x] T038 [P] [US4] Revisar `astros_upscale_api/Dockerfile`, `astros_upscale_api/pyinstaller.spec`,
  `astros_licensing_service/Dockerfile` — confirmar que nenhuma referência a caminho removido
  existe (research.md Decisão 5 já indicava zero mudança esperada — esta tarefa confirma no
  estado final).
- [x] T039 [US4] Confirmar que `.github/workflows/tests.yml` e
  `interface/src/main/apiProcess.ts` não referenciam nenhum caminho de arquivo removido
  (ambos referenciam só diretórios/processo, não arquivo individual — confirmar que continua
  assim).
- [x] T040 [US2] Rodar a suíte completa das três subpastas (`astros_upscale`,
  `astros_upscale_api`, `astros_licensing_service`) uma última vez — 100% verde.
  *(rodadas em invocações `pytest` separadas, uma por subpasta, exatamente como
  `.github/workflows/tests.yml` já faz — as duas APIs FastAPI têm pacotes Python
  chamados `app` cada uma; uma única invocação `pytest` cobrindo as três ao mesmo
  tempo colide entre os dois `sys.path`/`app` na coleta, uma limitação
  arquitetural pré-existente e independente desta reorganização, não algo
  introduzido por ela. Resultado: `astros_upscale` 53 passed, `astros_upscale_api`
  273 passed/31 deselected [slow], `astros_licensing_service` 97 passed — 423
  testes, 0 falhas.)*
- [x] T041 [US2] Comparar a contagem de testes coletados (`pytest --collect-only -q`) das três
  subpastas com a baseline capturada em T003 — deve ser idêntica (SC-004).
- [x] T042 [US1] Comparar a contagem de arquivos `.py` de produção das três subpastas (mesmos
  comandos `find` de T002, excluindo `__init__.py` e testes) com a baseline capturada em T002 e
  com as metas de SC-001/SC-002/SC-003 — deve estar dentro do limite (astros_upscale_api/app ≤8,
  astros_licensing_service/app ≤7, astros_upscale ≤3).
- [x] T043 [US4] Se Docker estiver disponível no ambiente de validação, rodar
  `docker build` dos dois Dockerfiles (`quickstart.md` §5); se não estiver disponível, registrar
  essa limitação explicitamente no relatório final em vez de omitir o passo.
  *(Docker não está disponível neste ambiente de validação — `docker: command not found`.
  Limitação registrada explicitamente, não omitida. Mitigação: research.md Decisão 5 já
  confirmou, por inspeção direta do conteúdo, que nenhum dos dois Dockerfiles referencia um
  caminho de arquivo específico — ambos fazem `COPY app ./app` do diretório inteiro — então a
  reorganização não teria como quebrar o build Docker; T038 já revisou os dois Dockerfiles
  quanto a isso.)*
- [x] T044 Executar `quickstart.md` do início ao fim, item por item, e marcar cada critério de
  sucesso (SC-001 a SC-006) como validado.

---

## Dependencies & Execution Order

- **Setup (Phase 1)** → bloqueia todas as demais fases (precisa da baseline antes de qualquer
  mudança).
- **Phase 2 (astros_upscale/)** depende só da Fase 1. Deve terminar antes da Fase 3, porque
  `astros_upscale_api/app/processing.py` (T014) importa símbolos de `astros_upscale.processing`
  (ex.: `load_model`) que só existem depois de T005/T006.
- **Phase 3 (astros_upscale_api/)** depende da Fase 2 completa. Internamente, T011→T012→T013→
  T014→T015→T016 seguem a ordem de dependência de `research.md` Decisão 2 — não paralelizável
  entre si (cada um importa do anterior).
- **Phase 4 (astros_licensing_service/)** é independente de Fase 2 e Fase 3 — é um serviço
  separado, sem import cruzado com os outros dois (confirmado em `research.md`: nenhum import
  `astros_licensing_service` ↔ `astros_upscale_api`). Pode rodar em paralelo com as Fases 2–3 se
  desejado, mas segue sua própria ordem interna T023→T024→T025→T026→T027 (dependência real, ver
  `research.md` Decisão 3).
- **Polish (Phase 5)** depende de Fases 2, 3 e 4 completas.

### Parallel Opportunities

- T011 (mover `schemas.py`) não depende de nenhum outro módulo-alvo — pode rodar em paralelo com
  o início da Fase 3, mas antes de T016 (`routes.py` importa de `schemas.py`).
- Fase 4 inteira pode rodar em paralelo com as Fases 2–3 (subprojeto sem dependência cruzada).
- T037 e T038 (revisão de config/build) tocam arquivos totalmente disjuntos entre si e podem
  rodar em paralelo.

---

## Implementation Strategy

### Ordem recomendada

1. Fase 1 (Setup — baseline).
2. Fase 2 (`astros_upscale/`) — a base da qual `astros_upscale_api` depende.
3. Fase 3 (`astros_upscale_api/`) — o maior volume de consolidação (17→5 arquivos em
   `app/core/` sozinho).
4. Fase 4 (`astros_licensing_service/`) — pode ser feita em paralelo com 2–3 por um segundo
   fluxo de trabalho, já que é totalmente independente; sequencial é igualmente válido e mais
   simples de revisar.
5. Fase 5 (Polish — varredura final, comparação de baseline, quickstart completo).

### Incremental Delivery

Cada fase (2, 3, 4) é internamente **implementar → corrigir import → testar → validar** antes de
passar para a próxima (Development Workflow da Constitution) — nenhuma reescrita única dos 56
arquivos de uma vez. Um checkpoint verde ao final de cada fase é a condição para prosseguir.

---

## Notes

- [P] tasks = arquivos genuinamente independentes, sem dependência entre si.
- Cada tarefa de grep/contagem listada é também um critério de aceitação.
- Fazer commit após cada fase concluída.
- Nenhuma tarefa desta lista deve alterar comportamento funcional, contrato HTTP/WebSocket,
  segurança, licenciamento ou pagamentos — qualquer diferença observada durante T017/T028/T040/
  T044 deve ser tratada como bug a corrigir antes de finalizar, não como mudança aceitável.
- FR-017 (preservar execução assíncrona de jobs, validação de licença, criptografia de pacotes e
  lógica de pagamentos) não tem uma tarefa de grep dedicada — é verificado pela suíte de testes
  existente continuando 100% verde em T010/T022/T034/T040, já que esses comportamentos já são
  exercidos pelos testes atuais de cada domínio.
- Nenhum teste deve ser removido apenas por ter quebrado durante a reorganização — só o import é
  corrigido (FR-022).
