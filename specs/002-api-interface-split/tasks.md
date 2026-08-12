---

description: "Task list for feature 002-api-interface-split"

---

# Tasks: Reorganização em duas camadas (api/ + interface/)

**Input**: Design documents from `/specs/002-api-interface-split/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/README.md, quickstart.md

**Tests**: Não são criados testes novos — esta feature preserva os ~41 arquivos de teste já
existentes, adaptando seus caminhos/imports. Cada fase de história de usuário termina rodando a
suíte relevante para confirmar zero regressão (Principle VIII).

**Organization**: Tarefas agrupadas por história de usuário de `spec.md`. US1/US2/US3 são P1
(devem ser concluídas juntas para uma migração minimamente completa e segura); US4 é P2.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Pode rodar em paralelo (arquivos/subárvores diferentes, sem dependência de tarefa incompleta)
- **[Story]**: US1, US2, US3, US4 — mapeiam para spec.md
- Caminhos de arquivo exatos em cada descrição

## Path Conventions

Ver `plan.md` → Project Structure para a árvore final completa. Resumo:
`api/astros_upscale/`, `api/astros_upscale_api/`, `api/astros_licensing_service/`, `interface/`
(promovido de `interface/astros_upscale_app/`).

---

## Phase 1: Setup

**Purpose**: preparar uma linha de base segura e reversível antes de qualquer movimentação de
arquivo.

- [x] T001 Confirmar árvore de trabalho git limpa (`git status` sem alterações pendentes) antes de
  iniciar; se houver algo, parar e reportar em vez de prosseguir sobre estado sujo.
- [x] T002 Capturar contagem de testes baseline: rodar `pytest` em `interface/astros_upscale_api`,
  `interface/astros_licensing_service` e na raiz (pacote `astros_upscale`), registrar
  quantidade de testes coletados/passando de cada um, para comparar depois da migração (SC-002).
- [x] T003 Tirar um backup de `interface/astros_licensing_service/storage/licensing.db` (cópia de
  arquivo, ex. `licensing.db.pre-migration.bak`, fora da árvore versionada) e registrar a
  contagem de linhas de cada tabela (`licenses`, `installations`, `authorizations`, `packages`)
  via `sqlite3`, para comparar depois da migração (SC-007).
- [x] T004 Criar o diretório `api/` na raiz do repositório (vazio, só a pasta).

**Checkpoint**: linha de base capturada, seguro prosseguir.

---

## Phase 2: Foundational (movimentações de diretório — bloqueia todas as histórias)

**Purpose**: mover fisicamente os quatro projetos para seus novos locais usando `git mv` (preserva
histórico de cada arquivo). Nenhuma história de usuário pode ser validada antes desta fase.

**⚠️ CRITICAL**: nenhuma tarefa de US1–US4 pode começar antes desta fase estar completa.

- [x] T005 [P] `git mv interface/astros_upscale_api api/astros_upscale_api`
- [x] T006 [P] `git mv interface/astros_licensing_service api/astros_licensing_service`
- [x] T007 [P] `git mv astros_upscale api/astros_upscale`
- [x] T008 [P] `git mv tests api/astros_upscale/tests` (os 7 arquivos de teste da raiz, que testam
  `astros_upscale` diretamente — ver `research.md` Decisão 5)
- [x] T009 [P] `git mv pyproject.toml api/pyproject.toml`
- [x] T010 [P] `git mv requirements.txt api/requirements.txt` (se distinto do
  `requirements.txt` de cada serviço — confirmar que não há colisão de nome antes de mover;
  renomear para `api/requirements-root.txt` se houver conflito de conteúdo com um já existente
  em `api/astros_upscale_api/` ou `api/astros_licensing_service/`)
- [x] T011 Mover o conteúdo de `interface/astros_upscale_app/` um nível acima, para que ele passe
  a SER `interface/` diretamente (ex.: `git mv interface/astros_upscale_app/* interface/` a
  partir de um diretório temporário, ou renomear `interface` → `interface_old`, criar `interface`
  novo, mover o conteúdo — usar a sequência que preserva melhor a detecção de rename do git;
  confirmar ao final que `interface/astros_upscale_app/` não existe mais e `interface/package.json`
  existe diretamente).
- [x] T012 Verificar que `astros_upscale.egg-info/` (artefato de build, não versionado ou
  versionado por engano) na raiz é removido/ignorado — não deve ser movido, é regenerado por
  `pip install -e`.
- [x] T013 Rodar `git status` e conferir visualmente que o git detectou as movimentações acima
  como renames (não como delete+add não relacionados) — se não detectar, considerar isso um
  sinal de alerta antes de prosseguir (histórico de arquivo se perderia).

**Checkpoint**: `api/` e `interface/` existem com o conteúdo movido; nada foi editado ainda, só
relocado. Nenhum serviço funciona ainda (imports/caminhos ainda apontam para os locais antigos) —
isso é esperado e corrigido nas próximas fases.

---

## Phase 3: User Story 1 - Um desenvolvedor encontra qualquer parte do sistema em um de dois lugares (Priority: P1)

**Goal**: a raiz do repositório expõe só `api/` e `interface/` como pastas de código-fonte de
aplicação, com estrutura interna correspondendo 1:1 ao que já existia (Phase 2 já fez o trabalho
físico — esta fase valida e corrige detalhes de organização).

**Independent Test**: listar a raiz do repo; confirmar que todo código-fonte de aplicação está em
`api/` ou `interface/`.

### Implementation for User Story 1

- [x] T014 [US1] Confirmar que a raiz do repositório contém apenas: `api/`, `interface/`,
  `models/`, `docs/`, `scripts/`, `specs/`, `.specify/`, `.github/`, `.venv/`, `README.md`,
  `LICENSE`, `.gitignore` — nenhuma outra pasta de código-fonte de aplicação. Registrar qualquer
  arquivo/pasta fora dessa lista para decisão (mover para dentro de `api/`/`interface/`, ou
  confirmar que é um arquivo global legítimo).
- [x] T015 [US1] Revisar `api/astros_upscale_api/`, `api/astros_licensing_service/`,
  `api/astros_upscale/` e confirmar que nenhuma pasta nova artificial foi criada além do que
  `plan.md` especifica — cada uma deve refletir 1:1 sua estrutura interna pré-migração.
- [x] T016 [US1] Atualizar `README.md` (se ele documentar a estrutura de pastas antiga) para
  refletir `api/`/`interface/`.

**Checkpoint**: estrutura de diretórios validada e documentada. (Os serviços ainda não rodam —
isso é validado em US2/US3.)

---

## Phase 4: User Story 2 - Toda funcionalidade da CLI continua acessível, sem exigir terminal (Priority: P1)

**Goal**: `astros_upscale/cli.py` é removido; a lógica de negócio que ele usava vira dependência
real de `api/astros_upscale_api` (pacote instalado, não `sys.path`); toda capacidade antes exposta
via terminal continua acessível por rota HTTP.

**Independent Test**: chamar cada rota HTTP mapeada em `research.md` (equivalente a
`image`/`video`/`audio`/`optimize`/`models download`/`models update`) e confirmar resultado
equivalente, sem invocar nenhum comando de terminal.

### Implementation for User Story 2

- [x] T017 [US2] Remover `astros_upscale.cli:main` (e a seção `[project.scripts]`
  correspondente, se existir só por causa dele) de `api/pyproject.toml`.
- [x] T018 [US2] Apagar `api/astros_upscale/cli.py`.
- [x] T019 [P] [US2] Reinstalar o pacote em modo editável a partir do novo local:
  `pip install -e ./api` (ou equivalente) no `.venv` da raiz, substituindo a instalação antiga
  feita a partir de `/pyproject.toml`. Confirmar `python -c "import astros_upscale; print(astros_upscale.__file__)"`
  resolve para `api/astros_upscale/__init__.py`.
- [x] T020 [US2] Editar `api/astros_upscale_api/app/core/component_manager.py`:
  `_REPO_ROOT = APP_DIR.parent.parent.parent` → `APP_DIR.parent.parent` (agora aponta para
  `api/`, onde vive `pyproject.toml` — ver `research.md` Decisão 6). Atualizar também o
  comentário na linha anterior e a mensagem de erro em `_pip_install_audio_extra` que menciona
  "astros_upscale ao lado" para refletir o novo caminho relativo.
- [x] T021 [US2] Corrigir o comentário sobre "3 níveis" em
  `api/astros_upscale_api/app/config.py` (o valor computado de `models_dir` não muda, só o
  comentário que documenta o caminho `interface/astros_upscale_api/app` → atualizar para
  `api/astros_upscale_api/app`).
- [x] T022 [P] [US2] Editar `api/astros_upscale_api/tests/conftest.py`: remover
  `sys.path.insert(0, str(Path(__file__).resolve().parents[3]))` (desnecessário — `astros_upscale`
  agora é importado como pacote instalado); reavaliar se o `sys.path.insert(0, str(Path(__file__).resolve().parent.parent))`
  restante ainda é necessário dado como pytest resolve `rootdir`/`sys.path` a partir do novo local
  — remover também se supérfluo.
- [x] T023 [P] [US2] Editar `scripts/mirror_models.py` e `scripts/benchmark_profiles.py`:
  confirmar que `from astros_upscale.core import ...` / `from astros_upscale.utils.download import ...`
  continuam resolvendo corretamente contra o pacote agora instalado a partir de `api/` (nenhuma
  mudança de linha de import deve ser necessária se T019 foi feito corretamente — só validar).
- [x] T024 [US2] Rodar `pytest api/astros_upscale/tests/` e confirmar que os 7 arquivos passam a
  partir do novo local, sem `sys.path` manual.
- [x] T025 [US2] Rodar `pytest api/astros_upscale_api -m "not slow"` e confirmar que os 28
  arquivos passam a partir do novo local.
- [x] T026 [US2] Validar manualmente (ou via script) cada linha da tabela "cli.py command
  handlers vs API routes" de `research.md`: subir `api/astros_upscale_api` (`python run.py`) e
  chamar `POST /jobs` (image/video/audio via `media_type`), `POST /jobs` com
  `operation=compress|convert`, e `POST /components/{id}/install`/`.../update`, confirmando
  resposta 2xx equivalente ao que o comando de terminal correspondente produzia (SC-004).
- [x] T027 [US2] Grep final: `grep -rn "astros_upscale\.cli" .` deve retornar vazio em todo o
  repositório (fora de `specs/`/documentação histórica).

**Checkpoint**: nenhuma funcionalidade exige mais um comando de terminal; a API local roda a
partir do novo caminho com o pacote `astros_upscale` importado de verdade (sem `sys.path`).

---

## Phase 5: User Story 3 - A interface continua funcionando exatamente como antes (Priority: P1)

**Goal**: o app Electron localiza e inicia a API automaticamente a partir do novo caminho; nenhuma
tela muda; nenhum arquivo de `interface/` importa módulo interno de `api/`.

**Independent Test**: abrir o app Electron do zero e percorrer os fluxos principais.

### Implementation for User Story 3

- [x] T028 [US3] Editar `interface/src/main/apiProcess.ts`: `resolveRepoRoot()` deixa de procurar
  `pyproject.toml` subindo diretórios e passa a procurar um diretório que contenha, ao mesmo
  tempo, uma subpasta `api` e uma subpasta `interface` (ver `research.md` Decisão 7).
- [x] T029 [US3] No mesmo arquivo, atualizar `apiDir` de
  `join(repoRoot, 'interface', 'astros_upscale_api')` para
  `join(repoRoot, 'api', 'astros_upscale_api')`. Confirmar que `API_BASE_URL`
  (`http://127.0.0.1:8765`) permanece inalterado (a porta não muda).
- [x] T030 [P] [US3] Grep em `interface/`: `grep -rn "^from app\|require(.*api/astros" interface/src`
  deve retornar vazio — nenhum arquivo de interface importa módulo Python de `api/` diretamente
  (FR-007).
- [x] T031 [US3] Rodar `cd interface && pnpm install && pnpm lint && pnpm typecheck` e confirmar
  zero erros novos introduzidos pela movimentação (os mesmos warnings pré-existentes são
  aceitáveis, conforme padrão já estabelecido neste projeto).
- [x] T032 [US3] Rodar `cd interface && pnpm dev` (ou o comando de desenvolvimento do Electron) e
  confirmar que a API local sobe automaticamente a partir do novo caminho, sem configuração
  manual (SC-005).
- [x] T033 [US3] Percorrer manualmente, no app aberto: ativação de licença, importação de um
  arquivo, processamento via fila, exportação, tela de Configurações/Créditos — confirmar
  nenhuma diferença visual/funcional perceptível em relação ao estado pré-migração (SC-006).
- [x] T034 [US3] Grep final: `grep -rn "interface/astros_upscale_api\|interface/astros_licensing_service" .`
  deve retornar vazio em todo o repositório (fora de `specs/`/documentação histórica) (SC-003).

**Checkpoint**: a interface funciona ponta a ponta a partir do novo caminho, sem regressão
observável e sem import cruzado indevido.

---

## Phase 6: User Story 4 - O serviço de licenciamento continua isolado como processo (Priority: P2)

**Goal**: o serviço de licenciamento roda como processo independente a partir do novo caminho,
preservando 100% dos dados do SQLite existente, e ganha um `Dockerfile` próprio para deploy
independente verificável.

**Independent Test**: subir só `api/astros_licensing_service` (sem a API local) e confirmar que
ativações/autorizações funcionam e os dados pré-existentes estão intactos.

### Implementation for User Story 4

- [x] T035 [US4] Criar `api/astros_licensing_service/Dockerfile`, espelhando o padrão de
  `api/astros_upscale_api/Dockerfile` (base `python:3.11-slim`, copia `requirements.txt` + `app/`
  + `run.py`, roda `uvicorn app.main:app --host 0.0.0.0 --port 8766`) — ver `research.md` Decisão 8.
- [x] T036 [US4] Editar `api/astros_licensing_service/tools/build_package.py`: corrigir o caminho
  hardcoded para `astros_upscale_api/app/core/upscaler.py`, hoje relativo a partir de
  `interface/astros_licensing_service/tools/`, para refletir a nova posição relativa (ambos os
  serviços agora são irmãos dentro de `api/`).
- [x] T037 [US4] Rodar `pytest api/astros_licensing_service` (6 arquivos) e confirmar que passam
  a partir do novo local.
- [x] T038 [US4] Subir `api/astros_licensing_service` sozinho (`python run.py`, sem a API local
  rodando) e confirmar `GET /health` responde e que o SQLite em
  `api/astros_licensing_service/storage/licensing.db` contém a mesma contagem de linhas por
  tabela capturada em T003 (zero perda de dados, SC-007).
- [x] T039 [P] [US4] Confirmar (grep) que `api/astros_licensing_service/app/` não é importado por
  nenhum arquivo Python dentro de `api/astros_upscale_api/app/` — a comunicação continua
  exclusivamente via `licensing_service_url` (HTTP), nunca por import direto.
- [x] T040 [US4] Confirmar que `api/astros_licensing_service/app/config.py` e
  `api/astros_upscale_api/app/config.py` continuam com portas/segredos/bancos de dados
  independentes — nenhum valor de configuração foi acidentalmente compartilhado ou fundido
  durante a movimentação.

**Checkpoint**: o serviço de licenciamento é implantável e testável de forma totalmente
independente da API local, com seus dados preservados.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: pontos de configuração/build que nenhuma história individual cobre sozinha, e a
varredura final de limpeza.

- [x] T041 [P] Atualizar `.github/workflows/tests.yml`: os 3 jobs mudam `working-directory` e
  `sparse-checkout` de `interface/astros_upscale_api` → `api/astros_upscale_api`,
  `interface/astros_licensing_service` → `api/astros_licensing_service`,
  `interface/astros_upscale_app` → `interface` (o job de sparse-checkout do Windows passa a
  incluir `api` como um todo, ou especificamente `api/astros_upscale`, `models`,
  `api/astros_upscale_api`).
- [x] T042 [P] Revisar `api/astros_upscale_api/pyinstaller.spec` linha a linha por caminhos
  relativos que dependiam da antiga profundidade `interface/astros_upscale_api` (ex.: referências
  a `../../` para alcançar `astros_upscale` ou `/models`) e corrigir conforme a nova estrutura.
- [x] T043 [P] Atualizar `docs/processing-protection-architecture.md` e
  `docs/audit/phase0-inventory.md` (se citarem os caminhos antigos como referência de arquitetura
  ativa, não como histórico) para os novos caminhos.
- [x] T044 Remover `astros_upscale.egg-info/` da raiz (artefato de build do local antigo, se ainda
  presente) e confirmar que o novo `pip install -e ./api` gera seu próprio artefato de build
  dentro de `api/` (git-ignorado).
- [x] T045 Varredura final: `grep -rln "interface/astros_upscale_api\|interface/astros_licensing_service\|interface/astros_upscale_app" .`
  em todo o repositório (código, configuração, CI, docs versionados) — zero ocorrências fora de
  `specs/002-api-interface-split/` (que documenta o histórico da migração) e do `CHANGELOG`/
  histórico de commits.
- [x] T046 Rodar a suíte completa mais uma vez (`api/astros_upscale`, `api/astros_upscale_api`,
  `api/astros_licensing_service`) e comparar a contagem de testes com a linha de base capturada
  em T002 — nenhum teste deve ter sido perdido (SC-002).
- [x] T047 Executar `quickstart.md` do início ao fim, item por item, e marcar cada critério de
  sucesso (SC-001 a SC-007) como validado.
- [x] T049 Validar FR-008 (api/ não depende de interface/): rodar
  `grep -rln "interface/" api/ --include="*.py"` (deve retornar vazio, fora de comentários
  puramente descritivos que não afetam import/execução) e, em seguida, renomear temporariamente
  `interface/` (ex. para `interface_disabled/`) e confirmar que `pytest api/astros_upscale`,
  `pytest api/astros_upscale_api -m "not slow"` e `pytest api/astros_licensing_service` continuam
  passando com `interface/` ausente — depois desfazer o rename.
- [x] T050 Validar que `models/` (raiz) e os diretórios `storage/` de cada serviço
  (`api/astros_upscale_api/app/storage/`, `api/astros_licensing_service/storage/`) permanecem no
  mesmo local e com o mesmo conteúdo de antes da Fase 2 — nenhum arquivo de dados foi movido,
  duplicado ou versionado por engano durante os `git mv` de código.
- [x] T048 Apagar os backups temporários criados em T003 (`licensing.db.pre-migration.bak`) depois
  que T038 confirmar integridade dos dados.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: sem dependências — pode começar imediatamente.
- **Foundational (Phase 2)**: depende da conclusão do Setup — BLOQUEIA todas as histórias de usuário.
- **User Stories (Phase 3–6)**: todas dependem da conclusão da Fase 2.
  - US1, US2, US3 são todas P1 — recomendado concluir as três antes de considerar a migração
    minimamente funcional (US1 é validação estrutural pura e rápida; US2 e US3 têm dependência
    lógica fraca entre si — US2 valida o backend, US3 valida que o frontend ainda alcança esse
    backend — por isso US3 deve rodar DEPOIS de US2 estar concluída, já que T032/T033 exigem a API
    local já funcional a partir do novo caminho).
  - US4 (P2) pode rodar em paralelo com US2/US3 depois da Fase 2, já que trata de um serviço
    independente — mas T038 é mais fácil de validar depois que T003 (backup) já existe (Fase 1).
- **Polish (Phase 7)**: depende de todas as histórias P1 (US1–US3) estarem concluídas; T041–T043
  também dependem de US4 estar concluída (para saber o caminho final do Dockerfile do licensing
  service a referenciar no CI, se aplicável).

### User Story Dependencies

- **US1 (P1)**: depende só da Fase 2 (movimentação física). Sem dependência de US2/US3/US4.
- **US2 (P1)**: depende da Fase 2. Sem dependência de US1/US3/US4, mas deve completar antes de US3
  (a interface precisa de uma API funcional para ser validada ponta a ponta).
- **US3 (P1)**: depende da Fase 2 e, na prática, de US2 estar concluída (T032 sobe a API local que
  só funciona depois dos ajustes de US2).
- **US4 (P2)**: depende só da Fase 2. Independente de US1/US2/US3.

### Within Each User Story

- Movimentação de arquivo (Fase 2) antes de qualquer ajuste de import/configuração.
- Ajustes de import/configuração antes de rodar testes.
- Testes passando antes do checkpoint da história ser considerado concluído.

### Parallel Opportunities

- T005–T010 (Fase 2) são movimentações de subárvores disjuntas — podem ser feitas em paralelo.
- Dentro de US2: T019, T022, T023 tocam arquivos diferentes e independentes entre si — paralelizáveis.
- Dentro de US3: T030 (grep) é independente de T028/T029 (edição) — paralelizável.
- Dentro de US4: T039 (grep) é independente de T035/T036 — paralelizável.
- US4 inteira pode rodar em paralelo com US2+US3, já que trata de um serviço independente.
- T041, T042, T043 (Fase 7) tocam arquivos diferentes — paralelizáveis entre si.

---

## Parallel Example: Phase 2 (Foundational)

```bash
# As quatro movimentações de subárvore são independentes entre si:
git mv interface/astros_upscale_api api/astros_upscale_api
git mv interface/astros_licensing_service api/astros_licensing_service
git mv astros_upscale api/astros_upscale
git mv tests api/astros_upscale/tests
```

## Parallel Example: User Story 2

```bash
# Depois de T017/T018 (remoção do entry point + cli.py):
Task: "Reinstalar pacote editável a partir de api/ (T019)"
Task: "Remover sys.path.insert de conftest.py (T022)"
Task: "Validar imports de scripts/mirror_models.py e benchmark_profiles.py (T023)"
```

---

## Implementation Strategy

### MVP First (US1 + US2 + US3 — as três P1 juntas)

Diferente do padrão usual de "US1 sozinha já é um MVP entregável", aqui as três histórias P1 são
facetas da MESMA mudança estrutural mínima viável: mover os arquivos sem validar que tudo ainda
funciona (só US1) não é seguro entregar; validar que a API funciona sem validar que a interface
ainda a alcança (só US2) deixa o produto inutilizável. Por isso, a estratégia recomendada é:

1. Completar Fase 1 (Setup) e Fase 2 (Foundational — movimentação física).
2. Completar US1 (validação estrutural) — rápida, confirma que a Fase 2 não deixou nada para trás.
3. Completar US2 (backend funcional, CLI removida, testes passando).
4. Completar US3 (frontend funcional ponta a ponta) — só possível depois de US2.
5. **PARAR e VALIDAR**: neste ponto, o produto está funcionalmente equivalente ao pré-migração.
6. Completar US4 (isolamento do serviço de licenciamento como processo/deploy) — pode ser feita a
   qualquer momento depois da Fase 2, inclusive em paralelo com os passos 2–4 acima.
7. Completar Fase 7 (Polish — CI, PyInstaller, docs, varredura final, `quickstart.md` completo).

### Incremental Delivery

Não há entrega parcial "segura para produção" antes de US1+US2+US3 estarem todas completas — a
migração é atômica do ponto de vista do usuário final (o app precisa continuar funcionando do
início ao fim). US4 e a Fase 7 são as únicas partes verdadeiramente incrementais/paralelizáveis
sem risco ao produto.

---

## Notes

- [P] tasks = arquivos/subárvores diferentes, sem dependência entre si.
- Cada tarefa de grep listada é também um critério de aceitação — se retornar algo, a tarefa não
  está concluída.
- Fazer commit após cada fase concluída (não após cada tarefa individual), dado que a Fase 2
  sozinha já é uma unidade atômica de `git mv` que não faz sentido dividir em commits menores.
- Evitar: mover arquivos fora da sequência da Fase 2 (movimentações espalhadas por várias fases
  tornam o diff de rename do git mais difícil de revisar corretamente).
