# Implementation Plan: Reorganização em duas camadas (api/ + interface/)

**Branch**: `002-api-interface-split` | **Date**: 2026-08-12 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/002-api-interface-split/spec.md`

## Summary

Consolidar três projetos Python hoje independentes — o pacote raiz `astros_upscale` (que também
expõe uma CLI a ser removida), a API HTTP local `interface/astros_upscale_api`, e o serviço de
licenciamento `interface/astros_licensing_service` — dentro de uma única pasta `api/`, mantendo
cada serviço como processo separado. Mover o app Electron/Vue (`interface/astros_upscale_app`)
para `interface/`, sem alterações internas de comportamento. Substituir os dois hacks de
`sys.path` existentes por um pacote `astros_upscale` instalável de verdade (`api/pyproject.toml`),
eliminando a terceira camada de comandos ao apagar `astros_upscale/cli.py` — cuja auditoria prévia
(ver `research.md`) confirmou que toda capacidade que ele expunha já tem rota HTTP equivalente na
API hoje.

## Technical Context

**Language/Version**: Python 3.11 (dois serviços FastAPI + um pacote de lógica) e TypeScript/Vue 3
(app Electron) — inalterados por esta feature.

**Primary Dependencies**: FastAPI, uvicorn, pydantic-settings, PyTorch/torchaudio, OpenCV,
cryptography (backend); Electron, Vue 3, Vite (frontend) — inalterados.

**Storage**: SQLite (`api/astros_licensing_service/storage/licensing.db`, sem ORM) + filesystem
(`api/astros_upscale_api/app/storage/{uploads,outputs}`, `api/astros_licensing_service/storage/identity`).
Nenhum esquema de dados muda; só o caminho físico dos arquivos.

**Testing**: pytest (backend, ~41 arquivos de teste a preservar), vitest/eslint/vue-tsc (frontend,
inalterado).

**Target Platform**: Windows desktop (app empacotado via Electron + PyInstaller), com CI rodando
os testes da API em `windows-latest` (exigido por `dpapi.py`) e o serviço de licenciamento em
`ubuntu-latest`.

**Project Type**: Aplicativo desktop com backend Python de dois processos separados + frontend
Electron — reorganização estrutural, não uma nova feature de produto.

**Performance Goals**: N/A para esta feature — nenhuma mudança de comportamento de processamento é
esperada; o critério de sucesso é comportamento idêntico ao pré-migração (ver SC-006).

**Constraints**: Zero perda de dados (SQLite, storage, manifests de integridade); zero regressão
visual/funcional na interface; nenhum caminho antigo deve restar como referência ativa; suíte de
testes existente (~41 arquivos) deve continuar passando integralmente.

**Scale/Scope**: ~26 pontos de import cruzado a atualizar (mapeados em `research.md`), 3 projetos
Python + 1 projeto Electron a relocar, 1 Dockerfile a atualizar + 1 a criar, 1 workflow de CI com 3
jobs a atualizar, 1 processo de resolução de caminho no Electron a atualizar.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Princípio | Avaliação | Justificativa |
|---|---|---|
| I. Spec First | ✅ PASS | Esta feature segue o fluxo completo Constitution → Specify → Plan → Tasks → Analyze → Implement, exigido explicitamente pelo pedido do usuário. |
| II. Reuse First | ✅ PASS | A auditoria técnica (research.md) confirmou que nenhum módulo do pacote `astros_upscale` está superado pela API — são a mesma lógica, hoje importada via `sys.path`. A decisão de design é mover o pacote como unidade (preservando seus imports internos relativos) em vez de reescrever, e reaproveitar os módulos, não duplicá-los. `cli.py` é removido, não reescrito, porque tudo que ele fazia (além do parsing de argumentos) já está coberto por rotas HTTP existentes. |
| III. Performance First | ✅ PASS (N/A) | Nenhum código de processamento muda; a migração é puramente de localização de arquivos e mecanismo de import. Nenhuma medição de performance é necessária porque nenhum caminho de execução muda. |
| IV. Commercial License Only | ✅ PASS (N/A) | Nenhum componente/modelo/dependência nova é introduzida. `docs/models/MODEL_LICENSES.md` não muda de conteúdo, só potencialmente de caminho de referência relativo (a verificar em Phase 1). |
| V. Models Are Internal | ✅ PASS — a migração *reforça* este princípio | A auditoria encontrou que `cli.py`'s `run_image`/`run_video`/`run_audio` expõem `--model`/`--audio-engine` diretamente ao usuário, violando este princípio. Removê-los (FR-002) elimina essa violação pré-existente em vez de introduzir uma nova. |
| VI. No AI Without Benefit | ✅ PASS (N/A) | Não aplicável — nenhuma escolha de modelo/algoritmo muda. |
| VII. Hardware Adaptive | ✅ PASS (N/A) | `hardware.py` é movido intacto; nenhuma lógica de detecção de hardware muda. |
| VIII. Tests Required | ✅ PASS — gate central desta feature | FR-013/SC-002 exigem explicitamente que os ~41 arquivos de teste existentes continuem passando, adaptados (não reescritos) para os novos caminhos. Nenhum teste é removido; nenhum é substituído por mock do que já era testado de verdade. |
| IX. Two-Layer Architecture | ✅ PASS — esta feature É a implementação deste princípio | Toda a estrutura de diretórios abaixo, a remoção de `cli.py`, e a preservação do isolamento de processo do serviço de licenciamento implementam diretamente as regras deste princípio (ver Project Structure). |

Nenhuma violação encontrada. Nenhuma linha na tabela de Complexity Tracking é necessária.

## Project Structure

### Documentation (this feature)

```text
specs/002-api-interface-split/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md         # Phase 1 output (/speckit-plan command)
├── quickstart.md         # Phase 1 output (/speckit-plan command)
├── contracts/             # Phase 1 output (/speckit-plan command)
├── checklists/requirements.md   # /speckit-specify output
└── tasks.md              # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

A estrutura interna de cada projeto já movido **não muda** — só a localização do diretório pai.
Nada abaixo é uma pasta nova inventada; cada linha corresponde a um diretório/arquivo já existente,
apenas relocado (ou, onde marcado NOVO/REMOVIDO, a única mudança estrutural real desta feature).

```text
api/                                    # NOVO nível — não existia; concentra tudo que hoje é
│                                        # interface/astros_upscale_api + interface/astros_licensing_service
│                                        # + astros_upscale (raiz)
├── pyproject.toml                      # NOVO caminho — era /pyproject.toml na raiz (mesmo conteúdo,
│                                        # menos o entry point `astros_upscale.cli:main`, que é removido)
├── requirements.txt                    # NOVO caminho — era /requirements.txt na raiz
├── astros_upscale/                     # era /astros_upscale/ (raiz) — movido intacto, MENOS cli.py
│   ├── __init__.py
│   ├── core.py                         # registro/resolução de modelos — usado por component_manager.py,
│   │                                   # upscaler.py, video_upscaler.py, license_registry.py
│   ├── audio.py                        # AUDIO_ENGINES — usado por component_manager.py
│   ├── content_type.py                 # classify_image/classify_audio — usado por routes_jobs.py
│   ├── face_enhance.py                 # FaceEnhancer — usado por upscaler.py
│   ├── hardware.py                     # detect_hardware/HardwareCapability — usado por routes_jobs.py,
│   │                                   # capacity.py, profile_resolver.py
│   ├── optimize.py                     # optimize_file — usado por job_manager.py
│   ├── legacy_identifiers.py           # usado internamente por core.py
│   ├── media_engine/
│   │   ├── probe.py                    # usado por routes_jobs.py, audio_processor.py
│   │   ├── temporal.py                 # usado por video_upscaler.py
│   │   └── transcode.py                # usado por routes_jobs.py, audio_processor.py
│   ├── utils/
│   │   ├── download.py                 # usado internamente por core.py; também por scripts/mirror_models.py
│   │   ├── image_io.py                 # usado por routes_jobs.py, routes_preview.py, job_manager.py, upscaler.py
│   │   └── video_io.py                 # usado por video_upscaler.py
│   │                                    # cli.py — REMOVIDO (ver research.md §Decisão 4; toda capacidade
│   │                                    # já coberta por rota HTTP existente, comando violava Principle V)
│   └── tests/                          # era /tests/ (raiz) — 7 arquivos, testam astros_upscale diretamente,
│                                        # movidos para junto do pacote que testam
│       ├── test_core.py
│       ├── test_media_engine_temporal.py
│       ├── test_mirror_and_video.py
│       ├── test_models_registry.py
│       ├── test_optimize.py
│       ├── test_secondary_elements_probe.py
│       └── test_video_io.py
│
├── astros_upscale_api/                 # era interface/astros_upscale_api/ — estrutura interna intacta
│   ├── run.py                          # inalterado (uvicorn app.main:app, porta 8765)
│   ├── Dockerfile                      # caminhos internos (COPY app/, requirements.txt) inalterados —
│   │                                   # só o caminho de build context no CI/scripts que o invocam muda
│   ├── pyinstaller.spec                # caminhos internos inalterados
│   ├── requirements.txt, requirements-dev.txt, pytest.ini
│   ├── app/
│   │   ├── main.py, config.py          # config.py: models_dir continua `APP_DIR.parent.parent.parent`
│   │   │                               # (mesma profundidade — "interface" e "api" são ambos 1 nível —
│   │   │                               # resolve para a raiz real do repo em ambos os casos; só o
│   │   │                               # comentário que documenta os "3 níveis" precisa ser corrigido)
│   │   ├── api/routes_*.py, ws_progress.py
│   │   ├── core/
│   │   │   ├── upscaler.py, video_upscaler.py, audio_processor.py
│   │   │   ├── component_manager.py    # `_REPO_ROOT` MUDA de significado: de
│   │   │   │                           # `APP_DIR.parent.parent.parent` (raiz do repo, onde ficava
│   │   │   │                           # pyproject.toml) para `APP_DIR.parent.parent` (api/, novo local
│   │   │   │                           # de pyproject.toml) — usado só para a checagem de
│   │   │   │                           # "source checkout presente" e o alvo do pip install `[audio]`
│   │   │   ├── job_manager.py, worker_supervisor.py, isolated_worker.py
│   │   │   ├── license_registry.py, license_gate.py, license_cache.py, offline_tolerance.py
│   │   │   ├── protected_loader.py, dpapi.py, install_identity.py, integrity.py, secure_tempdir.py
│   │   │   └── capacity.py, profile_resolver.py
│   │   ├── models/schemas.py
│   │   └── storage/{uploads,outputs}/  # dados de runtime — preservados, não versionados
│   ├── models/RealESRGAN_x4plus.pth    # cópia local existente — inalterada
│   └── tests/                          # 28 arquivos — conftest.py perde os dois `sys.path.insert`
│                                        # (o de `parents[3]` some porque astros_upscale vira import normal;
│                                        # o de `parent.parent` pode simplificar dependendo de como pytest
│                                        # resolve rootdir — decidido durante Phase 1/tasks)
│
├── astros_licensing_service/           # era interface/astros_licensing_service/ — estrutura interna intacta
│   ├── run.py                          # inalterado (uvicorn app.main:app, porta 8766) — continua processo
│   │                                   # próprio, iniciado separadamente (Principle IX)
│   ├── Dockerfile                      # NOVO — não existia; espelha o padrão do Dockerfile da API local
│   │                                   # (python:3.11-slim, copy requirements+app+run.py, uvicorn porta 8766)
│   │                                   # — necessário para FR-009/SC-007 (deploy independente verificável)
│   ├── requirements.txt, requirements-dev.txt, pytest.ini, .env.example
│   ├── app/
│   │   ├── main.py, config.py, db.py
│   │   ├── licensing.py, authorizations.py, packages.py, package_crypto.py, service_identity.py
│   │   ├── routes_activation.py, routes_authorizations.py, routes_packages.py, routes_webhooks.py
│   │   └── payments/{base,stripe_provider,mercadopago_provider}.py
│   ├── storage/{licensing.db, identity/service_signing_key.raw}   # dados — preservados
│   ├── tools/build_package.py          # inalterado (script standalone; só lê astros_upscale_api/app/core/
│   │                                   # upscaler.py como bytes — caminho relativo interno ao novo local
│   │                                   # de ambos precisa ser atualizado, ver tasks)
│   └── tests/                          # 6 arquivos — inalterados internamente
│
└── (sem docker-compose.yml — não existia antes; não é criado por esta feature, ver Assumptions)

interface/                              # era /interface/astros_upscale_app/ — conteúdo promovido um
│                                        # nível (era o único filho relevante de interface/, agora É
│                                        # interface/ diretamente — sem sub-pasta astros_upscale_app)
├── package.json, pnpm-lock.yaml, pnpm-workspace.yaml, electron-builder.yml, electron.vite.config.ts
├── build/, resources/, scripts/fetch-ffmpeg.mjs
└── src/
    ├── main/
    │   ├── index.ts
    │   └── apiProcess.ts               # `resolveRepoRoot()` MUDA: procurava por `pyproject.toml`
    │                                   # (que não existe mais na raiz do repo) — passa a procurar um
    │                                   # diretório que contenha tanto `api/` quanto `interface/` como
    │                                   # filhos (marcador estável e específico deste monorepo).
    │                                   # `apiDir` passa de `join(repoRoot,'interface','astros_upscale_api')`
    │                                   # para `join(repoRoot,'api','astros_upscale_api')`.
    │                                   # `API_BASE_URL` (http://127.0.0.1:8765) inalterado.
    ├── preload/
    └── renderer/                       # nenhuma mudança — não importa nada de api/ diretamente
                                        # (Principle IX, FR-007) — já fala só via fetch/WebSocket
                                        # para http://127.0.0.1:8765, inalterado

# raiz do repositório após a migração:
/
├── api/
├── interface/
├── models/                             # dados (pesos ML) — permanece na raiz, referenciado por
│                                        # api/astros_upscale_api/app/config.py (caminho inalterado
│                                        # em termos de profundidade, ver acima)
├── docs/                               # inalterado — MODEL_LICENSES.md, arquitetura, benchmarks
├── scripts/
│   ├── mirror_models.py                # import muda de `astros_upscale.core`/`astros_upscale.utils.download`
│   │                                   # (raiz) para o mesmo pacote agora em `api/astros_upscale`
│   └── benchmark_profiles.py           # idem
├── .github/workflows/tests.yml         # os 3 jobs mudam `working-directory` e sparse-checkout paths
│                                       # de `interface/astros_upscale_api` → `api/astros_upscale_api`,
│                                       # `interface/astros_licensing_service` → `api/astros_licensing_service`,
│                                       # `interface/astros_upscale_app` → `interface`
├── .venv/                              # inalterado em localização — só o que é `pip install -e`d nele muda
│                                       # de `-e .` (raiz) para `-e ./api` (o novo pyproject.toml)
├── README.md, LICENSE, .gitignore
└── specs/, .specify/                   # inalterados (metadados de processo, não código de aplicação)
```

**Structure Decision**: consolidar os três projetos Python-backend sob `api/` mantendo cada um como
subdiretório próprio com seu `run.py`/`app/` intactos (em vez de fundir seus namespaces Python em um
único pacote `app`), porque isso preserva o requisito constitucional de que o serviço de
licenciamento continue um processo independente sem risco de colisão acidental de módulos
(`app.config`, `app.main` de cada serviço deixam de existir lado a lado no mesmo namespace
importável). O pacote `astros_upscale` (lógica de mídia pura, hoje na raiz) move para dentro de
`api/` como um pacote instalável de verdade via `api/pyproject.toml`, eliminando os dois hacks de
`sys.path` hoje existentes (`component_manager.py`'s `_REPO_ROOT` insert implícito via import, e
`tests/conftest.py`'s `sys.path.insert(..., parents[3])`). `interface/astros_upscale_app` é
promovido para ser o próprio conteúdo de `interface/` (sem sub-pasta), já que é o único projeto que
resta nesse lado da árvore. Ver `research.md` para o detalhamento de cada decisão e as alternativas
descartadas.

## Complexity Tracking

*Nenhuma violação de princípio identificada no Constitution Check — seção vazia.*
