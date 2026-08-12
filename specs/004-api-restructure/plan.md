# Implementation Plan: Consolidação estrutural de api/ por domínio

**Branch**: `004-api-restructure` | **Date**: 2026-08-12 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/004-api-restructure/spec.md`

## Summary

`api/` acumulou 56 arquivos de produção (excluindo `__init__.py` e testes) fragmentados por
classe/mecanismo em vez de por domínio (18 arquivos em `astros_upscale_api/app/core/` sozinho,
para 5 domínios reais). Esta feature
consolida os três subprojetos de `api/` (`astros_upscale/`, `astros_upscale_api/`,
`astros_licensing_service/`) em módulos coesos por domínio — `processing.py`, `media.py`,
`jobs.py`, `licensing.py`, `security.py`, `routes.py`, `schemas.py`, `packages.py`, `payments.py`,
`database.py` — sem alterar nenhum comportamento observável (contratos HTTP/WebSocket, segurança,
licenciamento, pagamentos). A ordem de consolidação dentro de cada subprojeto é determinada pela
análise de dependência cruzada real registrada em `research.md` (não pela ordem em que os
arquivos aparecem no pedido), para que cada módulo novo só seja escrito depois que tudo do qual
ele importa já exista.

## Technical Context

**Language/Version**: Python 3.10–3.14 (conforme `api/pyproject.toml`); serviços rodam sob
Python 3.11 (Dockerfiles) / 3.13 (CI)

**Primary Dependencies**: FastAPI, Pydantic, PyTorch/spandrel (upscale), OpenCV, python-ffmpeg,
librosa (astros_upscale); FastAPI, cryptography (astros_licensing_service)

**Storage**: SQLite (`astros_licensing_service/storage/licensing.db`, via `db.py`→`database.py`);
sistema de arquivos local para uploads/outputs (`astros_upscale_api/app/storage/`) — inalterado

**Testing**: pytest (as três subpastas já têm suítes próprias — 7, ~29, 6 arquivos de teste
respectivamente)

**Target Platform**: servidor local (desktop do usuário, processo filho do Electron) para
`astros_upscale_api`; serviço remoto separado para `astros_licensing_service`

**Project Type**: reorganização estrutural interna de um backend já existente (não é uma feature
de produto nova) — dois serviços FastAPI + uma biblioteca Python compartilhada

**Performance Goals**: N/A — mudança é de organização de arquivo, não de algoritmo; Constitution
Princípio III (Performance First) não é violado nem precisa ser reavaliado, já que nenhuma lógica
de processamento muda

**Constraints**: zero mudança de comportamento observável (FR-016, FR-017); nenhuma nova camada
arquitetural (FR-024); testes existentes preservados, não removidos (FR-022)

**Scale/Scope**: 56 arquivos de produção (excluindo `__init__.py` e testes) consolidados em 13
módulos novos (2 em `astros_upscale/`, 6 em `astros_upscale_api/app/`, 5 em
`astros_licensing_service/app/` — `main.py`/`config.py`/`optimize.py` permanecem, só com import
atualizado), distribuídos em 3 subprojetos; 42 arquivos de teste com imports a corrigir (7 + 29 +
6)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Princípio | Avaliação |
|---|---|
| II. Reuse First | ✅ Esta feature É a aplicação do princípio — todo código existente é reaproveitado (REFACTOR: move de lugar), nada é reescrito do zero. Nenhuma implementação nova de funcionalidade já existente é criada. |
| III. Performance First | ✅ N/A para esta mudança — nenhuma lógica de processamento, tiling, ou seleção de hardware muda. Nenhuma claim de performance é feita (nem precisa ser medida), já que não há mudança de algoritmo. |
| IV. Commercial License Only | ✅ Nenhuma dependência nova é adicionada; `requirements*.txt` só é revisado para eventuais entradas órfãs (spec FR-021), não para adicionar/trocar pacotes. |
| V. Models Are Internal | ✅ Não afetado — esta é uma reorganização de arquivo-fonte, não muda nenhum contrato de API nem o que é exposto ao usuário final. |
| VIII. Tests Required | ✅ Gate central desta feature: FR-022 proíbe remover teste que quebrou na reorganização (só corrige o import); FR-023 proíbe forçar testes em arquivos gigantes só para espelhar a consolidação de produção. |
| IX. Two-Layer Architecture | ✅ Não afetado — a fronteira `interface/` ↔ `api/` (HTTP/WebSocket) e a separação de processo do serviço de licenciamento são preservadas integralmente; esta feature é interna a `api/`. |
| X. Interface Structure Is Adapted, Not Templated | N/A — esta feature não toca `interface/`. |
| XI. API Structure Is Consolidated By Domain, Not By Class | ✅ Esta feature é a implementação direta do princípio — consolidação por domínio real (confirmado por análise de dependência em `research.md`), preservando divisão onde uma parte é genuinamente separável (FR-020; nenhum caso encontrado nesta análise — todos os grupos-alvo ficam entre 100 e 1100 linhas, um tamanho que ainda se lê como domínio único). |

Nenhuma violação. Gate passa sem necessidade de `Complexity Tracking`.

## Project Structure

### Documentation (this feature)

```text
specs/004-api-restructure/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output — análise de dependência real + ordem de consolidação
├── data-model.md         # Phase 1 output — mapeamento de caminho origem→destino
├── quickstart.md         # Phase 1 output — validação (contagem de arquivo, grep, testes, import)
├── contracts/            # Phase 1 output — contratos HTTP/WebSocket/payments preservados
└── tasks.md              # Phase 2 output (/speckit-tasks — NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
api/
├── pyproject.toml
├── requirements.txt
│
├── astros_upscale/
│   ├── __init__.py
│   ├── processing.py     # era: core.py + audio.py + content_type.py + face_enhance.py +
│   │                      #      hardware.py + legacy_identifiers.py
│   ├── media.py           # era: media_engine/{probe,temporal,transcode}.py +
│   │                      #      utils/{download,image_io,video_io}.py
│   ├── optimize.py         # inalterado (só import atualizado)
│   └── tests/               # 7 arquivos, imports corrigidos
│
├── astros_upscale_api/
│   ├── run.py, Dockerfile, pyinstaller.spec (sem mudança de conteúdo, ver research.md Decisão 5)
│   ├── app/
│   │   ├── main.py, config.py (imports atualizados)
│   │   ├── routes.py       # era: api/routes_{jobs,files,components,identity,license,preview}.py
│   │   │                   #      + api/ws_progress.py
│   │   ├── processing.py    # era: core/{upscaler,video_upscaler,audio_processor,
│   │   │                    #      component_manager,capacity}.py
│   │   ├── jobs.py          # era: core/{job_manager,worker_supervisor,isolated_worker}.py
│   │   ├── licensing.py      # era: core/{license_gate,license_cache,license_registry,
│   │   │                     #      profile_resolver,offline_tolerance}.py
│   │   ├── security.py        # era: core/{protected_loader,secure_tempdir,integrity,dpapi,
│   │   │                      #      install_identity}.py
│   │   └── schemas.py          # era: models/schemas.py (pasta models/ removida)
│   └── tests/                   # ~29 arquivos, imports corrigidos
│
└── astros_licensing_service/
    ├── run.py, Dockerfile, .env.example (sem mudança de conteúdo)
    ├── app/
    │   ├── main.py, config.py (imports atualizados)
    │   ├── database.py    # era: db.py
    │   ├── licensing.py    # era: licensing.py + authorizations.py + service_identity.py
    │   ├── packages.py      # era: packages.py + package_crypto.py
    │   ├── payments.py       # era: payments/{base,stripe_provider,mercadopago_provider}.py
    │   └── routes.py          # era: routes_{activation,authorizations,packages,webhooks}.py
    ├── storage/                 # inalterado
    ├── tools/build_package.py    # imports atualizados (app.db→app.database, app.package_crypto→app.packages)
    └── tests/                     # 6 arquivos, imports corrigidos
```

**Structure Decision**: adota a estrutura-alvo do pedido original quase literalmente — a análise
de dependência (`research.md`) não encontrou nenhum caso em que um grupo-alvo precisasse
permanecer dividido por FR-020 (todos os módulos consolidados ficam entre ~100 e ~1100 linhas,
tamanho que ainda se lê como um domínio coerente). A única divergência do "resultado esperado" do
pedido é que `legacy_identifiers.py` **não** vira um arquivo próprio remanescente — ele é
absorvido em `processing.py` (`astros_upscale/`), pois a investigação (`research.md` Decisão 1)
confirmou que seu único consumidor é interno a `core.py`/`processing.py`, satisfazendo a condição
de FR-019 para incorporação em vez de arquivo autônomo.

## Complexity Tracking

*Não aplicável — o Constitution Check não encontrou violações a justificar.*
