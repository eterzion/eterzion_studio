# Implementation Plan: Audio Engine — Masterização e Restauração Híbrida (DSP + IA)

**Branch**: `006-audio-engine-masterizacao` | **Date**: 2026-08-13 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/006-audio-engine-masterizacao/spec.md`

## Summary

Estender o pipeline de áudio já existente em `astros_upscale_api` com um subpacote
`app/audio_engine/` que orquestra masterização e restauração de música em três modos
(Masterização Automática, Restaurar, Restaurar + Masterizar), combinando DSP determinístico
(sempre) com o SonicMaster (só quando um Problem Detector indicar necessidade real), isolado atrás
de um provider adapter e de um worker separado, com um Quality Guard que nunca deixa a saída de IA
virar resultado final sem validação objetiva. A extensão reaproveita a rota de job existente
(`POST /jobs/local`), corrige um bug real já presente no código (`_enhance_music` chamando o
script SonicMaster errado) e conserta a extra `[audio]` de `pyproject.toml`, hoje quebrada.

## Technical Context

**Language/Version**: Python 3.13 (ambiente principal, já em uso); audio-worker isolado roda em
Python compatível com os pins de `requirements_sonic.txt` do SonicMaster (mesma major, 3.10+ —
`torch==2.4.0` não exige 3.13 especificamente, apesar do README do SonicMaster recomendar isso;
confirmar durante a implementação com um teste real de import, não assumir).

**Primary Dependencies**: FastAPI/uvicorn/pydantic-settings (já em uso, sem mudança); `ffmpeg-python`
(já em uso, DSP); `pyloudnorm` (novo, MIT, medição LUFS/peak independente); no audio-worker
isolado: `torch==2.4.0`, `torchaudio==2.4.0`, `diffusers==0.30.0`, `transformers==4.44.0`,
`torchlibrosa==0.1.0`, `librosa==0.11.0` (pins exatos do SonicMaster, Decisão 4/research.md).

**Storage**: nenhuma nova — reaproveita o armazenamento de jobs em memória já existente
(`app/jobs.py`) e o diretório de modelos/checkpoints já existente (`models/`, ou um subdiretório
próprio para o checkpoint do SonicMaster, dado seu tamanho — 3,29 GB).

**Testing**: pytest (já em uso) — testes reais contra ffmpeg/pyloudnorm para o DSP e o Analyzer
(sem mock do processamento em si, Princípio VIII); o `SonicMasterProvider` é testado com um
double/fake do worker isolado para os testes rápidos de CI (o worker real, com GPU e checkpoint,
fica na categoria `slow`, fora do CI padrão — mesmo padrão já usado para outros engines pesados).

**Target Platform**: igual ao resto de `astros_upscale_api` — Windows/Linux, GPU NVIDIA opcional
via CUDA, fallback CPU.

**Project Type**: extensão de serviço backend existente (não é um projeto novo).

**Performance Goals**: não quantificados nesta spec além de FR-005/FR-019 (não recarregar o modelo
a cada job) — VRAM/tempo de inferência real do SonicMaster são desconhecidos até serem medidos
(research.md); nenhuma meta numérica de latência é prometida antes dessa medição.

**Constraints**: dependências do audio-worker isoladas do ambiente principal (FR-023); nenhuma
regressão no contrato HTTP/WebSocket existente (Decisão 2); nenhuma regressão de comportamento
para `audio_mode='enhance'`/omitido.

**Scale/Scope**: um subpacote novo (5 arquivos), extensão aditiva de 2 schemas existentes, correção
de 1 bug real existente, correção de 1 arquivo de configuração de dependências, vendorização de um
subconjunto de código de terceiro.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design — ainda válido.*

| Princípio | Como este plano cumpre |
|---|---|
| II. Reuse First | Reaproveita `WorkerSupervisor` (parametrizado, não recriado), a rota `POST /jobs/local` existente, `app/schemas.py`, o padrão de download-com-checksum de modelos, e os filtros ffmpeg já usados em `apply_dsp_chain`. |
| III. Performance First | Nenhuma etapa de IA roda incondicionalmente (FR-002); medição real de VRAM/tempo antes de qualquer promessa de desempenho (research.md). |
| IV. Commercial License Only | SonicMaster (Apache-2.0) e `pyloudnorm` (MIT) verificados; risco condicional do VAE já registrado em `docs/models/MODEL_LICENSES.md` §3-bis e re-referenciado aqui, não reintroduzido como novo risco não documentado. |
| VIII. Tests Required | quickstart.md define cenários reais (não mockados) para os caminhos feliz e de fallback; Cenário 4 é o teste de regressão do contrato existente. |
| IX. Two-Layer Architecture | Tudo dentro de `api/`; `interface/` continua só falando por HTTP/WebSocket — nenhuma mudança de canal. |
| XI. API Structure Is Consolidated By Domain | `audio_engine/` tem 5 arquivos por domínio real (Decisão 1), não uma árvore de subpastas por camada técnica; schemas HTTP ficam em `schemas.py` (Decisão 5). |
| XII. AI Audio Restoration Is Bounded, Provider-Isolated, and Never Auto-Trusted | Todo o plano é a aplicação direta deste princípio: DSP nunca substituído (Decisão 6), saída de IA sempre validada (Quality Guard, data-model.md), provider isolado atrás de `AudioRestorationProvider` (Decisão 3/data-model.md), lazy load + fallback (FR-019/FR-020), worker isolado (Decisão 3), dependências isoladas (Decisão 4), licenciamento condicional rastreado (Decisão 4 item 5). |

Nenhuma violação identificada — nenhuma entrada necessária em Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/006-audio-engine-masterizacao/
├── plan.md              # este arquivo
├── research.md          # Fase 0 — decisões 1-6
├── data-model.md         # Fase 1 — entidades
├── quickstart.md          # Fase 1 — validação ponta a ponta
├── contracts/
│   └── README.md          # Fase 1 — contrato HTTP/WS (extensão aditiva)
└── tasks.md               # Fase 2 (/speckit.tasks — ainda não gerado)
```

### Source Code (repository root)

```text
api/
├── pyproject.toml                          # CORRIGIDO: extra [audio] sem a linha sonicmaster quebrada
└── astros_upscale_api/
    ├── audio_worker_requirements.txt        # NOVO — pins exatos do SonicMaster, ambiente isolado
    ├── app/
    │   ├── schemas.py                       # ESTENDIDO — audio_mode/ai_strength em MediaRequest,
    │   │                                     #   audio_analysis/quality_verdict em JobStatus
    │   ├── processing.py                    # CORRIGIDO — _enhance_music chama o script certo;
    │   │                                     #   dispatch para audio_engine.mastering quando
    │   │                                     #   audio_mode != 'enhance'
    │   ├── jobs.py                          # ESTENDIDO — WorkerSupervisor aceita interpretador
    │   │                                     #   configurável no construtor; novo
    │   │                                     #   get_audio_worker_supervisor(), instância
    │   │                                     #   SEPARADA de get_supervisor() (nunca a mesma —
    │   │                                     #   achado do /speckit.analyze, ver research.md)
    │   ├── config.py                        # ESTENDIDO — nova var ASTROS_AUDIO_WORKER_PYTHON
    │   └── audio_engine/                    # NOVO subpacote (Decisão 1)
    │       ├── __init__.py
    │       ├── analyzer.py                  # AudioAnalysisReport, ProblemDetection
    │       ├── dsp.py                       # DSP determinístico (ffmpeg + pyloudnorm)
    │       ├── mastering.py                  # MasteringEngine — orquestra os 3 modos
    │       ├── quality.py                    # Quality Guard
    │       └── ai_provider.py                # AudioRestorationProvider + SonicMasterProvider + prompts
    └── vendor/
        └── sonicmaster/                      # NOVO — subconjunto vendorizado (Decisão 4)
            ├── LICENSE                        # Apache-2.0 original, preservado
            ├── NOTICE.md                      # origem, commit, atribuição
            ├── model.py                       # de AMAAI-Lab/SonicMaster, adaptado
            ├── utils.py
            ├── configs/tangoflux_config.yaml
            └── infer.py                       # baseado em infer_single.py, adaptado

docs/models/MODEL_LICENSES.md                 # ESTENDIDO — nota sobre o subconjunto vendorizado
```

Nenhuma mudança em `interface/` é necessária para esta feature (fora de escopo — a spec cobre o
backend; expor os novos modos na UI é trabalho de uma feature de interface separada).

**Structure Decision**: extensão in-place de `astros_upscale_api` (Opção "extensão de serviço
existente", não um novo projeto/serviço) — ver Decisões 1-6 de `research.md` para a justificativa
de cada escolha de layout.

## Complexity Tracking

*Nenhuma violação de princípio identificada — seção vazia por design.*
