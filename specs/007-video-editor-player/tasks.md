---

description: "Task list for 007-video-editor-player"
---

# Tasks: Área de Edição de Vídeo com Player Customizado

**Input**: Design documents from `/specs/007-video-editor-player/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/api.md](./contracts/api.md), [quickstart.md](./quickstart.md)

**Tests**: **incluídos e obrigatórios.** O template os trata como opcionais, mas o Princípio VIII da
constituição diz que toda feature nova precisa de testes, e que pipelines de processamento são
testados contra comportamento real — mock só em fronteira externa genuína. FFmpeg roda de verdade
nos testes de backend.

**Organization**: agrupadas por história de usuário, para que cada uma seja implementável e testável
sozinha.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: pode rodar em paralelo (arquivos diferentes, sem dependência pendente)
- **[Story]**: a qual história pertence (US1–US5)
- Caminho de arquivo exato em toda tarefa

## Path Conventions

- Backend: `api/astros_upscale_api/app/`, `api/astros_upscale/`, testes em `api/astros_upscale_api/tests/`
- Renderer: `interface/src/renderer/src/`
- Processo principal do Electron: `interface/src/main/`, `interface/src/preload/`

---

## Phase 1: Setup

**Purpose**: o que precisa existir antes de qualquer código de feature.

- [X] T000 Adicionar um runner de testes ao renderer — `vitest`, `@vue/test-utils`, `happy-dom`, `interface/vitest.config.ts` e os scripts `test`/`test:watch`. **Não estava no plano**: o renderer não tinha runner algum, e T004/T021/T022/T040 e o `pnpm test` do quickstart o pressupunham. Descoberto ao executar, não na análise
- [X] T001 [P] Declarar os tetos por operação (duração, resolução, FPS, número de quadros, tamanho) como configuração em `api/astros_upscale_api/app/config.py`, com os valores da tabela de research.md Decisão 6
- [X] T002 [P] Declarar a allowlist container → encoders → áudio em `api/astros_upscale_api/app/config.py`, conforme data-model.md *Vocabulário permitido* — sem `libx264` nem `libx265`
- [X] T003 [P] Criar o namespace `videoEditor.*` vazio nos 11 arquivos de `interface/src/renderer/src/i18n/locales/`
- [X] T004 [P] Escrever o teste de paridade de chaves entre os 11 locales em `interface/src/renderer/src/i18n/__tests__/localeParity.spec.ts` — falha quando um locale tem chave que outro não tem
- [X] T005 [P] Preparar os arquivos de teste (`curto.mp4`, `vfr.mp4`, `sem_audio.mp4`, `longo.mp4`) descritos em quickstart.md, gerados por script em `api/astros_upscale_api/tests/fixtures/make_video_fixtures.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: infraestrutura que mais de uma história precisa. **Nenhuma história começa antes desta
fase terminar.**

**Nota sobre `video_edits.py`**: o construtor de grafo de filtros entra aqui, e não na primeira
história que o usa, embora a US1 não precise dele. US2 (preview sob demanda) e US3 (exportação)
dependem do mesmo módulo; deixá-lo em US2 criaria dependência cruzada entre histórias e quebraria a
independência que a organização por história existe para garantir.

### Identificação de arquivos e metadados

- [X] T006 [P] Implementar a chave de conteúdo (tamanho + mtime + hash parcial) em `api/astros_upscale/media.py`, ao lado do uso de `hashlib` que já existe — research.md Decisão 4
- [X] T007 [P] Estender `probe_streams()` em `api/astros_upscale/media.py` para devolver também taxa de quadros, se é VFR, e dimensões — preservando as chaves atuais, que o fluxo de elementos secundários já consome
- [X] T008 Escrever `api/astros_upscale_api/tests/test_media_handles.py` cobrindo emissão de identificador, resolução para caminho, higienização de nome e detecção de origem alterada
- [X] T009 Implementar `api/astros_upscale_api/app/media_handles.py` — registro identificador → caminho, com os metadados de `MediaHandle` (data-model.md). O caminho nunca sai em resposta

### Disponibilidade real de encoders

- [X] T010 [P] Implementar a consulta aos encoders que o binário FFmpeg realmente expõe em `api/astros_upscale/media.py`, ao lado de `is_lgpl_build()` — research.md Decisão 5
- [X] T011 [P] Escrever `api/astros_upscale_api/tests/test_encoder_availability.py` — allowlist ≠ disponibilidade; um encoder permitido e ausente precisa ser reportado como ausente

### Grafo de filtros, allowlist e tetos

- [X] T011a **Medir** encoder e preset candidatos por perfil (`fast`/`balanced`/`quality`) em vídeo real, registrando tempo de codificação e tamanho de saída em `docs/benchmarks/video-encoder-profiles.md`, **antes** de fixar o mapeamento da T013. A constituição exige que benchmarks precedam a escolha do que respalda cada perfil, e o Princípio III proíbe registrar afirmação de desempenho sem medição — reputação e intuição não bastam
- [X] T012 Escrever `api/astros_upscale_api/tests/test_video_edits.py` — construção do grafo via `ffmpeg-python` (nunca string), ordem `crop → rotation → flip → scale`, arredondamento para dimensão par, rejeição de valor fora de faixa, rejeição de container fora da allowlist
- [X] T013 Implementar `api/astros_upscale_api/app/video_edits.py`: construção do grafo com `run_ffmpeg`, resolução perfil → encoder → preset **conforme medido em T011a**, e verificação de tetos que **nomeia o fator limitante**
- [X] T014 [P] Escrever teste em `api/astros_upscale_api/tests/test_video_edits.py` provando que a verificação de tetos usa a duração **do trecho cortado**, não a do arquivo

### Contratos e schemas

- [X] T015 Adicionar em `api/astros_upscale_api/app/schemas.py` os schemas de `MediaHandle`, `VideoEditSet` (ajustes, efeitos, transformação, corte, áudio), `ExportRequest` e as respostas — todos com `extra='forbid'`, faixas de data-model.md
- [X] T016 Escrever `api/astros_upscale_api/tests/test_video_contract_surface.py` — um `codec`, `preset`, `crf` ou `input_path` no corpo é 422, não campo ignorado (SC-007, cenário 8 do quickstart)
- [X] T017 Implementar `POST /media/handles` e `GET /media/handles/{handle_id}` em `api/astros_upscale_api/app/routes.py`, conforme contracts/api.md

### Ponte com o renderer

- [X] T018 [P] Adicionar em `interface/src/renderer/src/services/api.ts` as chamadas de registro e consulta de handle, com os tipos correspondentes
- [X] T019 [P] ~~Ligar o registro de handle em `usePickFiles.ts`~~ — **desvio deliberado, não feito ali.** `usePickFiles.ts` é compartilhado por Vídeo, Áudio e as telas de lote; registrar handle dentro dele imporia a mudança a fluxos fora do escopo desta feature e custaria uma ida à API em cada importação que não precisa de handle. O `addFile` que o composable recebe já é o ponto de extensão por tela, e é onde o registro pertence: `registerMediaHandle()` está em `services/api.ts` (T018) e será chamado pelo `addFile` de `VideoEditorView.vue` na T031. O requisito (FR-028a) é cumprido; o local muda
- [X] T020 [P] Adicionar as opções de container em `interface/src/renderer/src/constants/processing.ts`, ao lado de perfil e dispositivo

**Checkpoint**: identificadores funcionam, o grafo de filtros é construído estruturalmente, a
allowlist e os tetos existem. As histórias podem começar.

---

## Phase 3: User Story 1 — Ver o vídeo com controle real (Priority: P1) 🎯 MVP

**Goal**: abrir um vídeo na área de edição e percorrê-lo inteiramente dentro da aplicação —
reproduzir, pausar, arrastar, andar quadro a quadro, ver tempo e quadro.

**Independent Test**: importar um vídeo, reproduzir, pausar, arrastar até uma posição arbitrária,
avançar e voltar um quadro, e conferir que tempo e número do quadro correspondem à posição real —
sem que ajuste ou exportação existam.

### Tests for User Story 1

- [X] T021 [P] [US1] Escrever `interface/src/renderer/src/composables/__tests__/useVideoPlayback.spec.ts` — reproduzir/pausar, passo por quadro, e a regra de que avançar e voltar retorna ao mesmo quadro
- [X] T022 [P] [US1] Escrever `interface/src/renderer/src/composables/__tests__/useVideoTimeline.spec.ts` — conversões tempo ↔ quadro ↔ pixel, o caso VFR em que o número do quadro não é exibido como exato (FR-012), e os extremos de duração: vídeo de poucos quadros e vídeo de horas continuam posicionáveis

### Implementation for User Story 1

- [X] T023 [P] [US1] Implementar `interface/src/renderer/src/composables/useVideoPlayback.ts` — estado de reprodução e passo por quadro via `requestVideoFrameCallback` (research.md Decisão 3)
- [X] T024 [P] [US1] Implementar `interface/src/renderer/src/composables/useVideoTimeline.ts` — conversões e a supressão do número de quadro em VFR
- [X] T025 [US1] Implementar `interface/src/renderer/src/components/video/VideoPlayerSurface.vue` — o `<video>` servido por `astros-media://` (Decisão 8), sem alteração no handler do processo principal
- [X] T026 [P] [US1] Implementar `interface/src/renderer/src/components/video/VideoTransportControls.vue` — reproduzir, pausar, quadro a quadro, operável por teclado com rótulo acessível (FR-010)
- [X] T027 [P] [US1] Implementar `interface/src/renderer/src/components/video/VideoTimeline.vue` — barra, cursor, clique e arrasto
- [X] T028 [P] [US1] Implementar `interface/src/renderer/src/components/video/VideoTimeDisplay.vue` — posição, duração e número do quadro
- [X] T029 [P] [US1] Implementar `interface/src/renderer/src/components/video/VideoVolumeControl.vue` — volume e silenciar, ausente quando `has_audio` é falso (FR-009)
- [X] T030 [US1] Implementar `interface/src/renderer/src/components/video/VideoPlayer.vue` — compõe superfície, transporte, linha de tempo, tempo e volume
- [X] T031 [US1] Implementar `interface/src/renderer/src/views/VideoEditorView.vue` usando `MediaEditorShell.vue` pelos seus dois slots, com importar/alternar/remover vídeos (FR-002, FR-005)
- [X] T032 [US1] Adicionar o ponto de entrada para a área de edição em `interface/src/renderer/src/views/VideoView.vue`, sem remover o fluxo em lote (FR-032)
- [X] T033 [US1] Tratar o caso de vídeo não previsualizável com aviso explícito em `VideoPlayerSurface.vue` (FR-011)
- [X] T034 [P] [US1] Escrever as chaves `videoEditor.player.*` nos 11 locales de `interface/src/renderer/src/i18n/locales/`

### Miniaturas da linha de tempo (FR-007a)

> Completam o player. Podem ser adiadas sem quebrar o teste independente da US1 — o corte natural se
> o objetivo for o MVP mais enxuto.

- [X] T035 [US1] Escrever `api/astros_upscale_api/tests/test_video_thumbnails.py` — geração do sprite e descarte quando a chave de conteúdo muda (cenário 12 do quickstart)
- [X] T036 [US1] Implementar `api/astros_upscale_api/app/video_thumbnails.py` — sprites em armazenamento da API, cache com chave de conteúdo (FR-016, FR-017)
- [X] T037 [US1] Implementar `GET /media/handles/{handle_id}/thumbnails` em `api/astros_upscale_api/app/routes.py`
- [X] T038 [P] [US1] Implementar `interface/src/renderer/src/composables/useTimelineThumbnails.ts`
- [X] T039 [US1] Implementar `interface/src/renderer/src/components/video/VideoTimelineThumbnails.vue`

**Checkpoint**: US1 funciona sozinha. Já substitui o ir-e-voltar para um player externo.

---

## Phase 4: User Story 2 — Ajustar e ver o efeito antes de processar (Priority: P1)

**Goal**: aplicar as cinco famílias de edição e ver o resultado no preview, com o arquivo de origem
intacto.

**Independent Test**: aplicar um ajuste visível e conferir que o preview muda, que voltar ao neutro
restaura a imagem, e que o arquivo de origem segue intacto — sem que a exportação exista.

### Tests for User Story 2

- [X] T040 [P] [US2] Escrever `interface/src/renderer/src/composables/__tests__/useVideoEdits.spec.ts` — estado neutro, reset (FR-004) e isolamento entre vídeos (FR-003)
- [X] T041 [P] [US2] Escrever `api/astros_upscale_api/tests/test_preview_frame.py` — o quadro renderizado reflete as edições e nunca escreve na origem
- [X] T042 [US2] Escrever o teste de paridade preview × exportação em `api/astros_upscale_api/tests/test_video_edits.py`: mesma entrada de ajuste produz o mesmo resultado pela fórmula do shader e pelo filtro `eq` (cenário 3 do quickstart)

### Implementation for User Story 2

- [X] T043 [P] [US2] Implementar `interface/src/renderer/src/composables/useVideoEdits.ts` — as cinco famílias, estado neutro e reset por vídeo
- [X] T044 [US2] Implementar `interface/src/renderer/src/composables/useVideoPreviewPipeline.ts` — shader WebGL2 com a fórmula do `eq` (research.md Decisão 1); **não usar filtro CSS**, pelo motivo registrado ali
- [X] T045 [US2] Ligar o canvas do shader ao `<video>` em `interface/src/renderer/src/components/video/VideoPlayerSurface.vue`
- [X] T046 [P] [US2] Implementar `interface/src/renderer/src/components/video/VideoAdjustmentsPanel.vue` — ajustes e efeitos, com faixas de data-model.md
- [X] T047 [P] [US2] Implementar `interface/src/renderer/src/components/video/VideoTransformPanel.vue` — recorte, rotação, espelho, tamanho de saída
- [X] T048 [P] [US2] Implementar `interface/src/renderer/src/components/video/VideoTrimHandles.vue` — pontos de entrada e saída, com o trecho selecionado distinguível (FR-007b)
- [X] T049 [US2] Integrar os controles de áudio (manter/silenciar/remover, volume) ao painel de ajustes (FR-013e)
- [X] T050 [US2] Implementar `POST /media/handles/{handle_id}/preview-frame` em `api/astros_upscale_api/app/routes.py`, reaproveitando a forma da rota de preview de imagem
- [X] T051 [US2] Implementar o preview sob demanda no renderer, espelhando debounce, guarda de corrida e invalidação ao trocar de arquivo de `useDenoisePreview.ts` (research.md Decisão 2)
- [X] T052 [US2] Exibir o aviso do FR-015 quando um efeito ativo não estiver no preview em movimento
- [X] T052a [US2] Exibir o indicador de recálculo enquanto o preview está sendo atualizado, em `VideoPlayerSurface.vue` — cláusula do FR-014 que faltava tarefa
- [X] T052b [US2] Implementar o descarte de **todas as cinco famílias** no reset de `useVideoEdits.ts`, não apenas dos ajustes de imagem (FR-004, desambiguado)
- [X] T053 [P] [US2] Escrever as chaves `videoEditor.edits.*` nos 11 locales

**Checkpoint**: US1 e US2 funcionam independentemente. A pessoa vê o resultado antes de gastar tempo.

---

## Phase 5: User Story 3 — Exportar sem destruir o original (Priority: P1)

**Goal**: materializar as edições em um arquivo novo, com progresso, cancelamento e origem intacta.

**Independent Test**: exportar com ajustes e verificar que o arquivo novo existe e reflete as
edições, que o original não foi tocado, e que cancelar no meio não deixa arquivo parcial nem
temporário.

### Tests for User Story 3

- [X] T054 [P] [US3] Escrever `api/astros_upscale_api/tests/test_video_edit_export.py` — ponta a ponta com FFmpeg real: arquivo novo criado, edições aplicadas, origem byte-idêntica (SC-003)
- [X] T055 [P] [US3] Escrever teste de cancelamento e de falha no mesmo arquivo — nenhum arquivo parcial no destino, nenhum temporário remanescente (FR-022, FR-023, SC-004)
- [X] T056 [P] [US3] Escrever teste de colisão de nome — grava sob nome distinto por padrão; `overwrite` só com instrução explícita (FR-020)

### Implementation for User Story 3

- [X] T057 [US3] Implementar o tipo de job de exportação de vídeo editado em `api/astros_upscale_api/app/jobs.py`, reaproveitando progresso, cancelamento e WebSocket existentes (FR-021)
- [X] T058 [US3] ~~Orquestração da exportação em `processing.py`~~ — **desvio: ficou em `jobs.py`.** O plano previa `processing.py`, mas a orquestração de uma exportação é o ciclo de vida de um job — caminho de saída, arquivo parcial, limpeza, cancelamento — e `jobs.py` já é o dono disso para `enhance`, `compress` e `convert`. Pôr um quarto tipo de operação em outro módulo teria criado dois lugares onde procurar "como um job roda". `_run_video_edit` fica ao lado de `_run_compress_convert`, e `video_edits.py` continua sendo quem monta o grafo
- [X] T059 [US3] Implementar a limpeza de temporários como **ponto único de saída** do job, cobrindo sucesso, falha e cancelamento (FR-022) — não espalhada por ramo de erro
- [X] T060 [US3] Implementar a resolução de colisão com renomeação por padrão em `api/astros_upscale_api/app/processing.py` (FR-020)
- [X] T061 [US3] Implementar `POST /video/edit-jobs` em `api/astros_upscale_api/app/routes.py`, com as quatro razões de recusa de contracts/api.md
- [X] T062 [US3] Implementar `GET /video/export-options` em `api/astros_upscale_api/app/routes.py` — disponibilidade real por container, tetos, e **nenhum nome de encoder na resposta** (Princípio V)
- [X] T063 [P] [US3] Implementar `interface/src/renderer/src/composables/useVideoExport.ts` — criação do job, progresso por WebSocket, cancelamento
- [X] T064 [US3] Implementar `interface/src/renderer/src/components/video/VideoExportPanel.vue` — container, perfil, destino, progresso e cancelar
- [X] T065 [P] [US3] Adicionar as chamadas de exportação e de opções em `interface/src/renderer/src/services/api.ts`
- [X] T066 [US3] Registrar as exportações no histórico em `interface/src/renderer/src/store/history.ts`, no mesmo nível das operações de vídeo existentes (FR-031)
- [X] T066a [US3] Garantir em `useVideoExport.ts` que trocar de vídeo ou fechar a área de edição **não** interrompe exportação em curso (FR-023a, primeira metade) — com teste
- [X] T066b [US3] Implementar o cancelamento das exportações em andamento no encerramento da aplicação, em `interface/src/main/`, com a mesma limpeza de qualquer cancelamento (FR-023a, segunda metade)
- [X] T066c [P] [US3] Verificar espaço em disco antes de iniciar e recusar com `disk_full`, reaproveitando a categoria que `ERROR_CATEGORY_COPY` já define — edge case sem tarefa até aqui
- [X] T067 [P] [US3] Escrever as chaves `videoEditor.export.*` nos 11 locales

**Checkpoint**: o fluxo mínimo completo — ver → ajustar → exportar — está entregue.

---

## Phase 6: User Story 4 — Recusa antes, não depois (Priority: P2)

**Goal**: recusar trabalho grande demais antes de começar, nomeando o fator limitante.

**Independent Test**: submeter um vídeo que excede um teto declarado e verificar que a recusa ocorre
antes de qualquer processamento e nomeia o limite.

### Tests for User Story 4

- [X] T068 [P] [US4] Escrever `api/astros_upscale_api/tests/test_video_ceilings.py` — cada fator (duração, resolução, FPS, quadros, tamanho) recusa com o seu nome, **sem que nenhum arquivo seja criado** (SC-005)
- [X] T069 [P] [US4] Escrever teste de encoder ausente — recusa com `encoder_unavailable` antes de processar (FR-027, cenário 7 do quickstart)

### Implementation for User Story 4

- [X] T070 [US4] Ligar a verificação de tetos ao caminho de criação do job em `api/astros_upscale_api/app/routes.py`, **antes** do `check_capacity` existente, que continua inalterado (plan.md, *Complexity Tracking*)
- [X] T071 [US4] Implementar a queda para a próxima opção permitida do mesmo container quando o encoder preferido está ausente, em `api/astros_upscale_api/app/video_edits.py`
- [X] T072 [US4] Exibir os tetos e a indisponibilidade na interface a partir de `GET /video/export-options`, desabilitando o que não está disponível em `VideoExportPanel.vue`
- [X] T073 [US4] Tratar `source_changed` — arquivo alterado desde o registro do handle — nas rotas de edição
- [X] T074 [P] [US4] Escrever as chaves `videoEditor.limits.*` e as mensagens de recusa nos 11 locales (FR-030)

**Checkpoint**: recusas honestas e imediatas, com o motivo nomeado.

---

## Phase 7: User Story 5 — Trabalhar em outro idioma (Priority: P3)

**Goal**: a área de edição inteira em qualquer um dos idiomas suportados.

**Independent Test**: trocar o idioma e percorrer a área de edição à procura de texto não traduzido
ou chave crua.

- [X] T075 [US5] Rodar o teste de paridade de chaves (T004) e corrigir toda divergência entre os 11 locales
- [X] T076 [US5] Revisar as traduções de `videoEditor.*` nos 11 idiomas — **feito por varredura + inspeção.** Checado: valor idêntico ao inglês num locale não-inglês, placeholder `{factor}` perdido na tradução, e texto de outro idioma vazando. Nenhum problema real: as 12 marcações de "igual ao inglês" são cognatos legítimos (Gamma em de/es/fr/it; Pause, Format, Rotation, Saturation, Destination em fr). Zero placeholders perdidos, zero idiomas trocados, os 5 grupos presentes nos 11 locales. **Falta ainda revisão humana nativa** para naturalidade — a varredura pega erro mecânico, não tom
- [X] T077 [US5] Conferir que nenhum literal em português restou nos 11 componentes de `interface/src/renderer/src/components/video/` nem em `VideoEditorView.vue`
- [X] T078 [US5] ~~Extrair literais de componentes existentes retrabalhados~~ — **no-op, e essa é a resposta certa.** Nenhum componente existente foi substancialmente retrabalhado: `UploadZone` e `RangeSlider` receberam props novas (aditivas), `MediaEditorShell` foi usado como está, `VideoView` ganhou um botão. Nada disso dispara o gatilho do Princípio XIV, que é explícito em proibir a extração como varredura isolada. O único literal novo que eu mesmo introduzi — o rótulo do botão Editor — virou chave (commit 218a4ae)

**Checkpoint**: todas as histórias entregues.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [X] T079 [P] Medir o tempo de resposta do preview contra os 2 s do SC-002 — **completa.** O nível sob demanda: 123–146 ms de mediana em 1080p. O nível interativo, o shader: **0,100 ms de mediana, 0,073 ms só de GPU** em 1080p (RTX 4060 / ANGLE / D3D11), medido com os shaders extraídos do `.ts` e todos os parâmetros fora do neutro. Passa com quatro ordens de grandeza de folga. Ressalva registrada em quickstart.md: medido no Chromium do painel de navegação — mesma pilha e mesmo shader, mas não a janela do Electron
- [X] T080 [P] Verificar acessibilidade por teclado em toda a árvore do player (FR-010) — **auditoria feita, três defeitos corrigidos** (commit 218a4ae): atalhos de transporte eram código morto (handler exposto, nada o ligava); todo slider dos painéis era controle sem nome para leitor de tela; e o grupo de transporte se anunciava com o rótulo da linha de tempo
- [ ] T081 Rodar os 14 cenários de [quickstart.md](./quickstart.md) — **10 de 14.** O cenário 3 saiu do limbo: foi **medido** em vez de olhado, comparando pixel a pixel o shader contra a cadeia de produção. Resultado em quickstart.md — cada ajuste isolado concorda dentro da tolerância do projeto, os cinco combinados divergem até 22 níveis, e **isso fica aberto** (FR-015). Os 4 restantes (1, 2, 13, 14) exigem o diálogo nativo ou a janela do Electron
- [X] T082 [P] Confirmar que `interface/src/renderer/src/views/ImageEditorView.vue` não foi modificado — a isenção da v2.6.0 proíbe dividi-lo como refatoração isolada
- [X] T083 [P] Confirmar que o fluxo em lote de `VideoView.vue` funciona como antes (FR-032, cenário 14) — **verificado por diff**: o arquivo ganhou um import de ícone, um emit e um botão; nada foi removido. Confirmação na tela continua pendente junto do T081
- [X] T084 Registrar em `docs/` a dívida do `codec='libx264'` em `api/astros_upscale/optimize.py` — não corrigida aqui, não herdada pela allowlist desta feature
- [X] T085 ~~Correção da contagem de locales na constituição~~ — **feito na emenda v3.0.0**, junto com a exceção do Princípio XIII. Nada a fazer; mantido para rastreabilidade
- [X] T086 [P] Escrever `api/astros_upscale_api/tests/test_no_codec_leak.py` — nenhuma resposta das rotas de vídeo expõe nome de modelo, encoder ou codec, espelhando `test_no_model_leak.py` (SC-009, Princípio V)
- [X] T087 [P] Conferir que `POST /media/handles` satisfaz as quatro condições da exceção do Princípio XIII (v3.0.0): caminho só do diálogo nativo, validação antes de tudo, caminho nunca devolvido, identificador não reversível
- [X] T088 [P] Conferir que nenhuma rota além de `POST /media/handles` aceita caminho — a terceira condição da exceção é a que se perde primeiro quando a superfície cresce

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Fase 1)**: sem dependências
- **Foundational (Fase 2)**: depende da Fase 1 — **bloqueia todas as histórias**
- **US1, US2, US3 (Fases 3–5)**: dependem da Fase 2. Independentes entre si depois dela
- **US4 (Fase 6)**: depende da Fase 2; integra-se ao caminho de job criado na US3
- **US5 (Fase 7)**: depende de as chaves das outras histórias existirem
- **Polish (Fase 8)**: depende das histórias desejadas

### Por que `video_edits.py` está na Fase 2

US2 e US3 precisam do mesmo construtor de grafo. Colocá-lo na primeira história que o usa criaria
dependência de US3 sobre US2 e quebraria a independência entre elas. A US1 não o usa — o custo de
antecipá-lo é menor do que o de acoplar duas histórias.

### Parallel Opportunities

- Fase 1: T001–T005 inteiramente em paralelo
- Fase 2: T006, T007, T010, T011 em paralelo; depois T008→T009; T012→T013; T018–T020 em paralelo
- US1: T021/T022 em paralelo; T026–T029 em paralelo (componentes distintos); T023/T024 em paralelo
- US2: T040/T041 em paralelo; T046–T048 em paralelo
- US3: T054–T056 em paralelo; T063/T065/T067 em paralelo
- Backend e renderer avançam em paralelo dentro de cada história, uma vez fixados os contratos na Fase 2

### Ordem dentro de cada história

- Testes escritos antes da implementação, e falhando antes dela
- Composables antes dos componentes que os consomem
- Módulo de domínio antes da rota que o expõe
- Chaves de tradução junto com o componente, nunca depois (Princípio XIV)

---

## Parallel Example: User Story 1

```bash
# Testes da US1, juntos:
Task: "useVideoPlayback.spec.ts — reproduzir/pausar e passo por quadro"
Task: "useVideoTimeline.spec.ts — conversões e o caso VFR"

# Componentes folha da US1, juntos:
Task: "VideoTransportControls.vue"
Task: "VideoTimeline.vue"
Task: "VideoTimeDisplay.vue"
Task: "VideoVolumeControl.vue"
```

---

## Implementation Strategy

### MVP (User Story 1)

1. Fase 1 → Fase 2 → Fase 3
2. **Parar e validar**: cenário 1 do quickstart
3. T035–T039 (miniaturas) podem ficar para depois sem quebrar o teste independente da US1

### Entrega incremental

1. Setup + Foundational → base pronta
2. + US1 → player funcionando (**MVP**)
3. + US2 → edição com preview
4. + US3 → fluxo completo ver → ajustar → exportar
5. + US4 → recusas honestas
6. + US5 → todos os idiomas

Cada etapa entrega valor sem quebrar a anterior. O Princípio III do fluxo de desenvolvimento exige
justamente isso: implementar → testar → validar → seguir, nunca uma reescrita grande de uma vez.

---

## Notes

- **`/speckit.analyze` é obrigatório antes de `/speckit.implement`** — a constituição condiciona a
  implementação a nenhuma violação crítica pendente
- Reiniciar a API depois de qualquer mudança em `schemas.py`: schema novo com processo antigo no ar
  produz 422 sem causa aparente
- Testes de backend usam FFmpeg real; mock só em fronteira externa genuína (Princípio VIII)
- Nenhuma tarefa toca `ImageEditorView.vue`
- Nenhuma tarefa adiciona encoder GPL à allowlist
