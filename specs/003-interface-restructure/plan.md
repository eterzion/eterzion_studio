# Implementation Plan: Reorganização e simplificação de interface/

**Branch**: `003-interface-restructure` | **Date**: 2026-08-12 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/003-interface-restructure/spec.md`

## Summary

Corrigir a nomenclatura invertida da camada de acesso externo (`api.ts`↔`backend.ts`), remover o
único arquivo morto confirmado (`components/Versions.vue`), e extrair 4 composables de lógica
genuinamente separável/duplicada — sem introduzir `components/ui/` (evidência de reuso não
justifica) nem qualquer pasta `domain/`/`application/`. Tudo baseado em análise factual de reuso
e estrutura feita antes deste plano (ver `research.md`), não em aplicação literal do template
genérico proposto originalmente.

## Technical Context

**Language/Version**: TypeScript 5.9 (Vue 3.5 `<script setup>`), Node 18+/24 (Electron 39).

**Primary Dependencies**: Vue 3, Vite 7, Electron, vue-i18n, `@lucide/vue`. Inalterado — nenhuma
dependência nova.

**Storage**: N/A (frontend não persiste dados fora de `localStorage`, já coberto pelas stores
existentes — sem mudança).

**Testing**: `npm run lint` (ESLint), `npm run typecheck` (vue-tsc + tsc). Não há suíte de testes
automatizados de frontend hoje além dessas checagens estáticas — nenhuma é criada por esta feature
(fora de escopo, per spec Assumptions).

**Target Platform**: Desktop (Windows/Linux/macOS via Electron) — inalterado.

**Project Type**: Reorganização estrutural interna de um app desktop já existente, não uma nova
feature de produto.

**Performance Goals**: N/A — nenhuma mudança de comportamento de execução é esperada; sucesso é
"idêntico ao antes", não uma melhoria de performance.

**Constraints**: Zero regressão visual/funcional (spec US4/SC-004); build/lint/typecheck devem
terminar com o mesmo número ou menos de erros/avisos genuínos de antes (SC-003).

**Scale/Scope**: 19 componentes, 9 views, 5 stores, 2 arquivos de camada de acesso externo, 1
composable, ~28 arquivos `.vue`/`.ts` tocados no total (contando os que só precisam de import
atualizado).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Princípio | Avaliação | Justificativa |
|---|---|---|
| I. Spec First | ✅ PASS | Fluxo completo Constitution → Specify → Plan → Tasks → Analyze → Implement seguido. |
| II. Reuse First | ✅ PASS | Nenhum componente/lógica é reescrito — só movido/renomeado/extraído do próprio código existente. A extração de `useFileIntake` consolida 5 implementações quase idênticas já existentes (VideoView, AudioView, CompressConvertView, ConverterView, ImageEditorView) em uma só, exatamente o que este princípio pede. |
| III. Performance First | ✅ PASS (N/A) | Nenhum caminho de execução muda de comportamento; é reorganização de arquivo-fonte, não de lógica de runtime. |
| IV. Commercial License Only | ✅ PASS (N/A) | Nenhuma dependência nova. |
| V. Models Are Internal | ✅ PASS (N/A) | Não aplicável — feature não toca em seleção de modelo. |
| VI. No AI Without Benefit | ✅ PASS (N/A) | Não aplicável. |
| VII. Hardware Adaptive | ✅ PASS (N/A) | Não aplicável — frontend não detecta hardware. |
| VIII. Tests Required | ✅ PASS | `npm run lint`/`npm run typecheck` rodados antes e depois, comparados (SC-003); nenhum teste existente é removido (não há suíte de testes de frontend além dessas checagens hoje). |
| IX. Two-Layer Architecture | ✅ PASS | Reforçado, não violado: a camada de acesso externo renomeada (`nativeBridge.ts`/`apiClient.ts`) continua sendo o único ponto de contato com `api/` — nenhum componente/view passa a falar direto com IPC/HTTP. |
| X. Interface Structure Is Adapted, Not Templated | ✅ PASS — esta feature É a implementação deste princípio | A decisão de NÃO criar `components/ui/` (ver research.md) é uma aplicação direta da regra "só separar quando reduzir fragmentação real": a evidência de reuso (só 3 de 19 componentes reusados em múltiplas views) não sustenta a divisão. A extração de composables é justificada por responsabilidade genuinamente distinta e/ou duplicação real, nunca por tamanho isolado. |

Nenhuma violação encontrada. Nenhuma linha na tabela de Complexity Tracking é necessária.

## Project Structure

### Documentation (this feature)

```text
specs/003-interface-restructure/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md         # Phase 1 output (/speckit-plan command)
├── quickstart.md         # Phase 1 output (/speckit-plan command)
├── contracts/             # Phase 1 output (/speckit-plan command)
├── checklists/requirements.md   # /speckit-specify output
└── tasks.md              # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

Nada abaixo é uma pasta nova inventada além do que a análise de evidência (research.md) justifica
explicitamente. `components/`, `views/`, `store/`, `i18n/`, `assets/` permanecem exatamente onde
estão — só os itens marcados NOVO/RENOMEADO/REMOVIDO mudam.

```text
interface/src/renderer/src/
├── App.vue, main.ts, theme.ts, types.ts, env.d.ts     # inalterados
├── nativeBridge.ts        # RENOMEADO de api.ts — ponte Electron (window.api), conteúdo idêntico
├── apiClient.ts            # RENOMEADO de backend.ts — cliente HTTP/WS de astros_upscale_api, conteúdo idêntico
│                            # (ambos ficam soltos em src/, não numa pasta clients/ — só 2 arquivos,
│                            # uma pasta para 2 arquivos não reduz fragmentação, Constitution X)
├── assets/                 # inalterado
├── i18n/                   # inalterado
├── store/                  # inalterado (apiStatus, settings, license, history, jobs — só imports internos atualizados para os novos nomes de arquivo)
├── composables/
│   ├── useTruncated.ts     # inalterado
│   ├── useFileIntake.ts    # NOVO — consolida a lógica de seleção/drop/paste de arquivo hoje
│   │                        # duplicada quase palavra-por-palavra em ImageEditorView, VideoView,
│   │                        # AudioView, CompressConvertView, ConverterView (5 implementações → 1)
│   ├── useViewportPanZoom.ts   # NOVO — extraído de ImageEditorView.vue linhas 72-131: estado de
│   │                            # zoom/pan/toggle de espaço, responsabilidade autocontida e
│   │                            # independente do resto do arquivo
│   ├── useDenoisePreview.ts    # NOVO — extraído de ImageEditorView.vue linhas 198-262: presets +
│   │                            # preview assíncrono com debounce/race-guard, autocontido
│   └── useExportPanel.ts       # NOVO — extraído de ImageEditorView.vue linhas 359-401: máquina de
│                                # estado do painel de exportação (formato/qualidade/destino/
│                                # conflito), autocontida
├── components/              # PERMANECE FLAT — sem components/ui/ (ver research.md: só 3/19
│   │                          # componentes têm reuso real em múltiplas views; a divisão não
│   │                          # reduziria fragmentação de verdade, Constitution X)
│   ├── (18 arquivos existentes, inalterados)
│   └── Versions.vue           # REMOVIDO — boilerplate do electron-vite, zero import confirmado
└── views/
    ├── ImageEditorView.vue     # reduzido (~450-550 linhas de script extraídas para os 4 composables acima),
    │                            # comportamento idêntico, agora compõe os composables em vez de
    │                            # inline
    ├── VideoView.vue, AudioView.vue, CompressConvertView.vue, ConverterView.vue
    │                            # cada um passa a usar useFileIntake() em vez de reimplementar
    │                            # pickFiles/handleFilesDropped/handlePaste localmente
    └── (demais views inalteradas)
```

**Structure Decision**: manter a árvore majoritariamente como está — a auditoria (ver
`research.md`) mostrou que a estrutura atual já é enxuta (flat, sem imports profundos, sem
fragmentação real fora dos 2 pontos identificados). As únicas mudanças estruturais reais são: (1)
renomear os 2 arquivos de acesso externo para eliminar a inversão de nomes; (2) remover o único
arquivo morto confirmado; (3) extrair 4 composables com justificativa concreta (1 por duplicação
real de 5 vias, 3 por responsabilidade genuinamente distinta dentro do maior outlier do projeto).
Nenhuma pasta nova de "camada" (`domain/`, `application/`, `ui/`, `clients/`) é criada — cada uma
foi avaliada e rejeitada com uma razão específica documentada em `research.md`.

## Complexity Tracking

*Nenhuma violação de princípio identificada no Constitution Check — seção vazia.*
