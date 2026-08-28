# Implementation Plan: Central de Compressão de Mídia

**Branch**: `008-compression-centre` | **Date**: 2026-08-21 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/008-compression-centre/spec.md`

## Summary

Uma área nova — Compressão, acento laranja — que dá controle real sobre compressão de imagens,
vídeos, áudios e animações, com modo Básico para quem só quer um arquivo menor e modo Avançado
para quem sabe o que é CRF.

**A abordagem técnica é herdar, não construir.** O produto já comprime as três mídias principais,
já tem fila com estados e cancelamento, já sonda o que a máquina consegue executar, já compara
antes/depois com slider e zoom sincronizado, e já tem player de vídeo. O que falta é uma
superfície que reúna isso e **cinco capacidades novas**: estimativa de tamanho, modo tamanho-alvo,
presets do usuário, compressão de animação, e comparação sincronizada de dois vídeos.

Decisões de fase 0 que moldam o plano ([research.md](./research.md)): imagem passa a ser
processada por **Pillow** (já é dependência, cobre AVIF nativamente e é a única forma de atender
ao controle de metadados); GIF sai da cadeia `palettegen`/`paletteuse` do FFmpeg empacotado
(medido); progresso vem de `-progress pipe:1` (medido), nunca de temporizador; a fila é a que já
existe.

## Technical Context

**Language/Version**: Python 3.13 (API), TypeScript 5 / Vue 3.5 (renderer), Electron 40

**Primary Dependencies**: FastAPI, Pydantic v2, FFmpeg n8.1 **LGPL** (empacotado), Pillow 12.3,
OpenCV, `python-ffmpeg`

**Storage**: sistema de arquivos. Presets do usuário e histórico em armazenamento local do
aplicativo — sem banco, sem rede.

**Testing**: pytest (API e core), Vitest (renderer)

**Target Platform**: aplicativo desktop Windows/Linux (macOS sem FFmpeg empacotado — ver
MODEL_LICENSES.md §5)

**Project Type**: desktop-app com API local (arquitetura de duas camadas, Princípio IX)

**Performance Goals**: interface responsiva com arquivo de 1 GB (SC-010); estimativa recalculada a
cada mudança de controle sem travar a digitação; progresso refletindo o encoder real (SC-009)

**Constraints**: FFmpeg LGPL — sem `libx264`/`libx265`, sem filtro GPL (`eq`, `hqdn3d`);
origem nunca sobrescrita (Princípio XV); nenhum processo ou temporário órfão (SC-005)

**Scale/Scope**: 71 requisitos funcionais, 4 tipos de mídia, 7 histórias. Entrega fatiada por
mídia, Imagem primeiro.

## Constitution Check

*GATE: obrigatório antes da Fase 0 e reverificado depois do desenho da Fase 1.*

Constituição **v4.0.0**. Portões obrigatórios (Governança) avaliados um a um:

| Princípio | Situação | Como o plano responde |
|---|---|---|
| **II. Reuse First** | ✅ | Fila, sondas, comparação, player, painéis e histórico são reusados. Módulos novos justificados na Decisão 7 |
| **III. Performance First** | ✅ | Estimativa por amostra reduzida; progresso por leitura de fluxo; sem carregar arquivo inteiro em memória |
| **IV. Commercial License Only** | ✅ | Pillow (HPND) e FFmpeg LGPL. Nenhuma dependência nova |
| **V. Models Are Internal** | ⚠️ **exceção aplicada** | A exceção da v4.0.0 autoriza controles técnicos. As cinco condições viraram FR-037 a FR-041, FR-043 a FR-045, e o SC-007 as verifica |
| **VI. No AI Without Benefit** | ✅ | Nenhum modelo na Central. Compressão é FFmpeg e Pillow |
| **VII. Hardware Adaptive** | ✅ | Tetos por operação reusados; recusa antes de começar nomeando o fator |
| **VIII. Tests Required** | ✅ | Presets, validação, bitrate, estimativa, compatibilidade, fila, cancelamento e erros têm tarefa de teste |
| **IX. Two-Layer Architecture** | ✅ | Renderer não processa mídia; toda compressão na API |
| **X. Interface Adapted** | ✅ | Componentes decompostos; nenhum arquivo gigante novo |
| **XI. API Consolidated By Domain** | ✅ | `app/compression/` por domínio de mídia, não por classe (Decisão 7) |
| **XII. AI Audio Bounded** | ✅ | Não se aplica: a Central não roda modelo de áudio |
| **XIII. Structural Invocation** | ✅ | Argumentos estruturados; todo número por validador; sonda funcional antes de oferecer |
| **XIV. Translatable By Default** | ✅ | 11 locales, teste de paridade existente |
| **XV. Source Never Overwritten** | ✅ | FR-058/FR-059. A §43 da solicitação foi divergida por isso, com registro |

**Nenhum portão reprovado.** O único ponto de atenção é o Princípio V, e ele está coberto por
emenda explícita, com risco aceito e registrado no log — não por interpretação conveniente.

## Project Structure

### Documentation (this feature)

```text
specs/008-compression-centre/
├── plan.md              # Este arquivo
├── research.md          # Fase 0 — oito decisões, todas medidas
├── data-model.md        # Fase 1
├── quickstart.md        # Fase 1
├── contracts/api.md     # Fase 1
└── tasks.md             # Fase 2 (/speckit.tasks)
```

### Source Code (repository root)

```text
api/astros_upscale_api/app/
├── compression/               # NOVO — Decisão 7
│   ├── __init__.py            fachada; a única porta que routes.py conhece
│   ├── capabilities.py        matriz declarada × sonda funcional
│   ├── config.py              presets, plataformas, pisos, tabelas (FR-012, §66)
│   ├── estimator.py           estimativa e resolução de tamanho-alvo
│   ├── presets.py             presets internos + do usuário (persistência local)
│   ├── image.py               Pillow
│   ├── video.py               FFmpeg + progresso real
│   ├── audio.py               FFmpeg
│   └── animation.py           FFmpeg palettegen/paletteuse
├── routes.py                  + compression_router
├── schemas.py                 + modelos da Central
└── jobs.py                    + estado `analyzing`, enum de status compartilhado

api/astros_upscale/
└── media.py                   + sonda de filtro com aridade correta (Decisão 2)

interface/src/renderer/src/
├── views/CompressionView.vue           # NOVO — a página
├── components/compression/             # NOVO
│   ├── CompressionMediaTabs.vue        Imagem · Vídeo · Áudio · GIF
│   ├── CompressionQueue.vue            fila + item
│   ├── CompressionPresetSelector.vue
│   ├── CompressionModeToggle.vue       Básico ⇄ Avançado
│   ├── ImageCompressionSettings.vue
│   ├── VideoCompressionSettings.vue
│   ├── AudioCompressionSettings.vue
│   ├── AnimationCompressionSettings.vue
│   ├── TargetSizeControl.vue
│   ├── CompressionEstimate.vue
│   ├── CompressionSummary.vue          o resumo lateral (§61)
│   └── CompressionComparison.vue       antes/depois por mídia
├── composables/
│   ├── useCompressionSettings.ts       estado por tipo de mídia
│   ├── useCompressionQueue.ts
│   └── useCompressionEstimate.ts
├── constants/compression.ts            espelho da config do backend
└── i18n/locales/*.json                 11 arquivos
```

**Componentes reusados sem alteração:** `CollapsiblePanel`, `SliderField`, `SettingRow`,
`SettingSwitch`, `AppSelect`, `RangeSlider`, `NumberStepper`, `UploadZone`, `CompareSlider`,
`VideoPlayer`, `ProgressBar`, `MediaEditorShell`, `useViewportPanZoom`.

## Complexity Tracking

| Complexidade introduzida | Por quê | Alternativa rejeitada, e por quê |
|---|---|---|
| Segunda biblioteca de imagem (Pillow ao lado de OpenCV) | Única forma de atender FR-028 (metadados) e AVIF sem subprocesso | Reimplementar EXIF sobre buffers do OpenCV — é escrever um Pillow pior |
| Módulo `app/compression/` com 9 arquivos | Domínios de mídia genuinamente diferentes; Princípio XI justifica por domínio | Um arquivo só — viraria o que o Princípio XI existe para impedir |
| Estimativa por amostra reduzida | Tabela estática não cumpre ±20% em caso adversário | Tabela — mais barata, e reprova o SC-002 |
| Modo Básico/Avançado | Condição 2 da exceção constitucional | Mostrar tudo — esvazia o Princípio V |

**Complexidade recusada:** fila nova, serviço de metadados próprio, serviço de exportação próprio,
motor de compressão paralelo ao `optimize.py`. Todos já existem em alguma forma; duplicá-los seria
criar um segundo lugar para o mesmo defeito morar.
