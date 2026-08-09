# Implementation Plan: Unified Media Processing

**Branch**: `001-unified-media-processing` | **Date**: 2026-08-08 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/001-unified-media-processing/spec.md`

## Summary

Evoluir o `astros_upscale` — hoje um upscaler de imagem que expõe 19 modelos por nome — para uma
plataforma unificada de imagem/vídeo/áudio (Melhorar/Comprimir/Converter) com exatamente uma
implementação por tipo de conteúdo (foto real, anime/desenho, vídeo real, vídeo de animação,
fala, música), três perfis obtidos por parâmetro de execução, controle de licença de software
ativo, e detecção de hardware real substituindo os valores fixos atuais.

Abordagem técnica: **reuso e extensão da infraestrutura existente**, não reescrita. A API FastAPI,
o sistema de jobs/fila/WebSocket, o isolamento de processo do worker, e o serviço de licenciamento
já existem e são funcionais — eles ganham um novo resolvedor de operação/perfil/tipo de conteúdo
na frente, e três novos domínios de processamento (vídeo, áudio, compressão/conversão) atrás.

## Technical Context

**Language/Version**: Python 3.13 (API, core, worker isolado) · TypeScript/Vue 3 (app desktop) ·
PowerShell (scripts do Spec Kit, ambiente de desenvolvimento é Windows)

**Primary Dependencies**:
- Backend: FastAPI, spandrel (carregamento de modelo agnóstico de arquitetura), OpenCV, torch,
  `python-ffmpeg` (wrapper sobre FFmpeg externo)
- Desktop: Electron + Vue 3 + Vite
- Licenciamento: serviço FastAPI separado (`astros_licensing_service`), SQLite, Ed25519/X25519
  (via `cryptography`), DPAPI (Windows, via ctypes)

**Storage**: arquivos no sistema de arquivos local (imagens/vídeos/áudios de entrada e saída,
modelos baixados sob demanda). SQLite no serviço de licenciamento (licenças, instalações,
autorizações). Sem banco de dados no lado do produto/API principal — o job store é em memória.

**Testing**: pytest (todos os serviços Python), com testes reais preferidos a mocks para lógica
central — subprocess real para isolamento de worker, modelo real para inferência, HMAC real para
webhooks. `pnpm run lint`/`typecheck`/`build` para o frontend.

**Target Platform**: Windows (plataforma primária de validação, conforme Assumptions da spec) ·
macOS e Linux secundários. Desktop, não servidor — todo processamento é local à máquina do
usuário (FR-070).

**Project Type**: Aplicativo desktop com API local (Electron spawna a API FastAPI como processo
filho) + serviço de licenciamento remoto separado.

**Performance Goals**: derivados de medição por tipo de conteúdo (FR-087 a FR-093), não de alvo
numérico fixo — a Constitution (Princípio III) proíbe afirmar performance sem medir. Alvo
qualitativo: perfil Rápido prioriza taxa de throughput; vídeo é o caso mais sensível a custo por
quadro (FR-101/FR-102 tratam disso).

**Constraints**: offline-capable dentro do período de tolerância de licença (Assumption: 30 dias) ·
sem limite de entrada fixo, capacidade derivada do hardware (FR-076 a FR-080) · FFmpeg embarcado
MUST ser build LGPL, sem `--enable-gpl`/`--enable-nonfree` (Constitution, Licensing and
Distribution Constraints) · nenhum conteúdo de mídia do usuário sai da máquina (FR-070).

**Scale/Scope**: uso individual por instalação, sem multiusuário concorrente (Assumption). Escopo
desta feature: 3 operações × 3 tipos de mídia × até 6 tipos de conteúdo × 3 perfis, mais o
controle de licença e a tela de componentes.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design — see bottom of section.*

Avaliação contra os 8 princípios da Constitution v2.0.0:

| Princípio | Gate | Status |
|---|---|---|
| I. Spec First | Plano deriva de spec.md aprovada, sem NEEDS CLARIFICATION pendente | ✅ PASS |
| II. Reuse First | Toda decisão de estrutura abaixo cita o que é reaproveitado vs. novo, com justificativa técnica onde novo | ✅ PASS — ver Project Structure |
| III. Performance First | Nenhum alvo de performance é afirmado sem medição; FR-087 a FR-093 exigem benchmark antes de fechar cada perfil | ✅ PASS |
| IV. Commercial License Only | Toda dependência nova deste plano (classificador de conteúdo, métricas de benchmark) MUST passar por verificação de licença antes de ser adotada — ver research.md | ✅ PASS — resolvido em R1/R2/R3/R4 |
| V. Models Are Internal | Nenhum contrato de API deste plano aceita `model` como parâmetro; tela de componentes segue o padrão capacidade-primeiro com detalhe opcional (FR-063/FR-097) | ✅ PASS |
| VI. No AI Without Benefit | Conversão/compressão usam FFmpeg, não modelo; classificação de conteúdo prioriza DSP sobre IA quando suficiente — ver research.md | ✅ PASS — resolvido em R1/R2 |
| VII. Hardware Adaptive | Substitui `_TILE_THRESHOLD`/`_TILE_SIZE` fixos por detecção real (FR-031 a FR-035, FR-076 a FR-080) | ✅ PASS — é o objeto principal de uma nova camada |
| VIII. Tests Required | Testes existentes (33 arquivos) preservados; nova cobertura exigida para cada domínio novo | ✅ PASS — ver Project Structure |

**Re-check pós-Phase 0**: os dois gates pendentes (IV, VI) fecharam com evidência registrada em
`research.md` (R1 a R4). Nenhuma violação da Constitution permanece aberta. Prossegue para Phase 1
sem necessidade de entrada em Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/001-unified-media-processing/
├── plan.md              # Este arquivo
├── research.md          # Phase 0 — decisões técnicas com verificação de licença
├── data-model.md        # Phase 1 — entidades
├── quickstart.md        # Phase 1 — roteiro de validação executável
├── contracts/           # Phase 1 — contrato HTTP/WS da API
└── tasks.md             # Phase 2 — /speckit.tasks (não criado aqui)
```

### Source Code (repository root)

Estrutura real do repositório, com o que é **reutilizado**, **estendido** e **novo** marcado
explicitamente — nenhuma reescrita de árvore existente.

```text
astros_upscale/                          # pacote core Python — REUTILIZADO E ESTENDIDO
├── core.py                              # registro de modelos — REFATORAR: de 19 para ≤6 (1/tipo de conteúdo)
├── audio.py                             # engines de áudio — REFATORAR: trocar denoiser/voicefixer por DSP + audiosronnx + SonicMaster
├── optimize.py                          # compressão — ESTENDER: permitir conversão (hoje exige mesma extensão) + AVIF
├── face_restore.py                      # REMOVER (GFPGAN + facexlib, ver MODEL_LICENSES.md)
├── content_type.py                      # NOVO — classificador foto/anime (imagem) e fala/música (áudio)
├── hardware.py                          # NOVO — detecção de CPU/RAM/GPU/VRAM/encoders reais
├── media_engine/                        # NOVO — camada central de FFmpeg (consolida video_io.py/audio.py/optimize.py)
│   ├── probe.py
│   ├── transcode.py
│   └── temporal.py                      # atadenoise/deflicker, tiling determinístico (FR-101/FR-102)
└── utils/
    └── video_io.py                      # REUTILIZADO, chamadas ffmpeg migram para media_engine/

interface/astros_upscale_api/            # API FastAPI local — REUTILIZADA E ESTENDIDA
├── app/
│   ├── core/
│   │   ├── upscaler.py                  # REUTILIZADO (image path já funciona)
│   │   ├── job_manager.py               # ESTENDER: generalizar de "upscale de imagem" para qualquer operação/mídia
│   │   ├── worker_supervisor.py         # REUTILIZADO (isolamento de processo já existe)
│   │   ├── isolated_worker.py           # REUTILIZADO
│   │   ├── profile_resolver.py          # NOVO — MediaRequest → Operation → Profile → Hardware → Engine (Seção 11 do briefing)
│   │   ├── video_upscaler.py            # NOVO — expõe astros_upscale/cli.py run_video via job, não CLI
│   │   ├── audio_processor.py           # NOVO — expõe astros_upscale/audio.py + DSP via job
│   │   └── component_manager.py         # NOVO — download sob demanda, verificação de integridade, cache (Seção 20 do briefing)
│   ├── api/
│   │   ├── routes_jobs.py               # ESTENDER: aceitar mediaType/operation/profile em vez de model
│   │   ├── routes_components.py         # NOVO — tela de componentes (FR-063 a FR-069)
│   │   └── routes_license.py            # NOVO — ativação, liberação, status (FR-051 a FR-062)
│   └── models/
│       └── schemas.py                   # ESTENDER: novos schemas de MediaRequest, Component, LicenseStatus
└── tests/                               # REUTILIZADOS (13 arquivos) + novos por domínio

interface/astros_licensing_service/      # REUTILIZADO INTEGRALMENTE — já implementa FR-051 a FR-062
├── app/                                 # ativação, limite de instalações, revogação, autorizações — tudo já existe
└── tests/                               # REUTILIZADOS (5 arquivos)
                                          # Trabalho aqui é ATIVAR (mudar config), não construir

interface/astros_upscale_app/            # Electron + Vue — REUTILIZADO E ESTENDIDO
├── src/renderer/src/
│   ├── views/
│   │   ├── ImageEditorView.vue          # REUTILIZADO, remove seletor de modelo/device manual
│   │   ├── VideoView.vue                # NOVO — hoje é placeholder vazio
│   │   ├── AudioView.vue                # NOVO — hoje é placeholder vazio
│   │   ├── CompressConvertView.vue      # NOVO — hoje é placeholder "Otimizar" vazio
│   │   ├── ComponentsView.vue           # NOVO — substitui ModelsView.vue (visão capacidade + detalhe opcional)
│   │   └── LicenseActivationView.vue    # NOVO — ativação/status de licença
│   ├── data/
│   │   └── modelLicenses.ts             # REMOVER — autoridade de licença migra para o backend (FR-046)
│   └── backend.ts                       # ESTENDER — novos endpoints de mídia/componentes/licença
```

**Structure Decision**: monorepo existente mantido — `astros_upscale/` (core), `interface/astros_upscale_api/`
(API), `interface/astros_licensing_service/` (licenciamento), `interface/astros_upscale_app/`
(desktop). Nenhum novo serviço ou repositório é criado. `ModelsView.vue` é substituída, não
mantida em paralelo (Constitution II — três implementações da mesma coisa não coexistem).
`face_restore.py` é removido, não refatorado (nenhuma base para reaproveitar, ver MODEL_LICENSES.md).

## Complexity Tracking

*Nenhuma violação da Constitution exige justificativa nesta fase — os dois gates pendentes são
resolvidos no Phase 0 (research.md), não são violações aceitas.*
