# Tasks: Central de Compressão de Mídia

**Feature**: `008-compression-centre` · **Input**: [spec.md](./spec.md), [plan.md](./plan.md),
[research.md](./research.md), [data-model.md](./data-model.md), [contracts/api.md](./contracts/api.md)

**Convenções**: `[P]` = paralelizável (arquivos distintos, sem dependência). `[USn]` = pertence à
história n. Toda tarefa tem resultado verificável.

**Fatiamento**: por mídia, decidido com o solicitante. A Fase 3 entrega **Imagem ponta a ponta** e
é utilizável sozinha. Vídeo, Áudio e GIF vêm depois, cada um sobre a fundação já pronta.

---

## Fase 1 — Setup

- [X] T001 Criar `api/astros_upscale_api/app/compression/__init__.py` como fachada vazia, e
      confirmar que `pytest` continua verde — o esqueleto não pode quebrar nada
- [X] T002 [P] Criar `interface/src/renderer/src/constants/compression.ts` com os tipos de mídia e
      os modos, sem valores ainda
- [X] T003 [P] Registrar o acento laranja do módulo em `theme.css` (`[data-module='compression']`),
      seguindo o mecanismo que image/video/audio já usam
- [X] T004 [P] Acrescentar a entrada "Compressão" em `AppSidebar.vue` e a rota correspondente, com
      a chave `nav.compression` nos 11 locales
- [X] T005 Escrever o teste de paridade de chaves rodando (já existe) e confirmar que os 11
      locales continuam iguais depois da T004

**Checkpoint**: ✅ **cumprido em 2026-08-21.** A aba aparece, é laranja, abre a tela com as quatro
abas de mídia, e nada mais mudou: 580 testes da API, 95 do renderer, lint e typecheck zerados.

---

## Fase 2 — Fundação (BLOQUEIA todas as histórias)

### Status e fila

- [X] T006 Acrescentar `analyzing` ao conjunto de status em `app/jobs.py` e no tipo do renderer,
      **sem renomear** os existentes — a justificativa está em data-model.md e renomear tocaria
      histórico, API, WebSocket e renderer sem ganho
- [X] T007 Escrever `test_status_enum_is_single_source.py`: nenhuma string de status literal fora
      do enum, em toda a base

### Capacidades

- [X] T008 Escrever `app/compression/config.py` com a matriz declarada container × codec de vídeo
      × codec de áudio, os presets internos, os presets de plataforma e os pisos de bitrate por
      resolução — **nenhum valor mágico fora daqui** (FR-012, §66)
- [X] T009 Escrever `app/compression/capabilities.py`: cruza a matriz declarada com as sondas
      funcionais. **Correção durante a implementação:** a sonda de imagem usava `image_format_works`
      (OpenCV) e reprovava AVIF, que o Pillow grava — a Decisão 1 leva a imagem para o Pillow, e
      uma sonda que não interroga quem faz o trabalho responde sobre outra coisa. Passou a usar
      `pillow_format_works`
- [X] T010 Acrescentar sonda de **filtro** em `media.py`, respeitando a aridade real do filtro —
      a pesquisa registrou que sondar `paletteuse` como filtro de uma entrada dá falso negativo
- [X] T011 [P] Escrever `test_compression_capabilities.py`: toda opção reportada como disponível é
      confirmada por sonda; motivo é chave, nunca nome de biblioteca; nenhum encoder GPL aparece
      disponível em nenhuma circunstância
- [X] T012 `GET /compression/capabilities` em `routes.py` + schemas, conforme contracts/api.md
- [X] T013 [P] Escrever `test_no_codec_leak_compression.py`: resposta a pedido do modo Básico não
      contém nome de codec ou encoder (SC-006), espelhando o teste que já existe para vídeo

### Estimativa

- [X] T014 Escrever `app/compression/estimator.py` — estimativa por mídia e resolução de
      tamanho-alvo, com `confidence` e `assumptions` (data-model.md)
- [X] T015 **Benchmark da estimativa** — registrado em `docs/benchmarks/compression-estimate.md`.
      **Reprovou a fórmula duas vezes.** A primeira (reduzir e extrapolar): 0/25 dentro de ±20%,
      erro médio 268%. A segunda (recorte nativo, dois pontos): 9/25, erro médio 32,6%. A terceira
      (grade de cinco recortes): **22/25, erro médio 8,6% — SC-002 passa**. As duas reprovações
      apontaram defeitos estruturais, não de calibração
- [X] T016 [P] Escrever `test_compression_estimator.py`: alvo abaixo do piso responde
      `below_floor` e **não** cria job; estimativa recalcula ao mudar configuração; unidades
      KB/MB/GB
- [X] T017 `POST /compression/estimate` — idempotente, sem efeito colateral, sem temporário

### Presets

- [X] T018 Escrever `app/compression/presets.py`: internos e de plataforma da config, do usuário em
      armazenamento local
- [X] T019 [P] Escrever `test_compression_presets.py`: preset de um tipo de mídia não é oferecido
      para outro (FR-014); `builtin`/`platform` são somente leitura (409 `readonly_preset`);
      `settings` incompatível com `media_kind` é 422
- [X] T020 `GET/POST/PATCH/DELETE /compression/presets`

### Job e ciclo de vida

- [X] T021 `POST /compression/jobs` com **todas** as recusas da tabela de contracts/api.md,
      verificadas antes de qualquer processamento (FR-064)
- [X] T022 Validação da condição 2 da exceção constitucional no backend: `advanced: false` com
      campo técnico em `settings` → 422 `invalid_settings`
- [X] T023 [P] Escrever `test_compression_job_refusals.py` cobrindo as sete linhas da tabela de
      recusas, uma a uma
- [X] T024 Gerenciamento de temporários: contexto que limpa em sucesso, erro, cancelamento **e**
      no encerramento da aplicação (FR-053)
- [X] T025 [P] Escrever `test_compression_no_orphans.py`: depois de sucesso, erro e cancelamento,
      nenhum temporário e nenhum processo filho vivo (SC-005)

### Importação e detecção

Bloco acrescentado pelo `/speckit.analyze`: a primeira versão destas tarefas não tinha nenhuma
para importar arquivo. A §3 e a §39 inteiras — arrastar, múltiplos, detecção por conteúdo,
metadados antes de processar — não teriam sido implementadas, e a falta só apareceria ao tentar
usar a tela.

- [X] T025a Detecção de tipo de mídia **pelo conteúdo**, não pela extensão (FR-007). Reusa
      `probe_streams`/`detect_secondary_elements`; acrescenta o que falta para distinguir
      `animation` de `image` (contagem de quadros)
- [X] T025b [P] Escrever `test_media_kind_detection.py`: um `.png` que é JPEG é detectado como
      JPEG; GIF de um quadro é `image`; extensão errada nunca decide
- [X] T025c Sondagem de metadados por tipo (FR-008), com **campo ausente ausente** e nunca zerado
      (FR-010)
- [X] T025d [P] Escrever `test_metadata_absent_is_none.py`: bitrate não sondado é `None`, não `0` —
      a diferença entre uma afirmação sobre a mídia e uma sobre a sondagem
- [X] T025e `MediaDropzone` na Central reusando `UploadZone`: arrastar-e-soltar, clicar para
      selecionar, múltiplos arquivos, acrescentar à fila sem substituí-la (FR-005, FR-006)
- [X] T025f Painel de informações do arquivo antes de processar: nome, extensão, tamanho,
      resolução, duração, codec, bitrate, FPS, canais, sample rate — cada um só quando aplicável
      e só quando sondado (FR-008, FR-010)
- [X] T025g Gerenciamento da fila de entrada: remover arquivo, limpar todos, acrescentar novos
      (FR-009)
- [X] T025h [P] i18n do bloco de importação nos 11 locales

### Casca da interface

- [X] T026 `CompressionView.vue` — layout de duas colunas conforme §75, usando `MediaEditorShell`
- [X] T027 [P] `CompressionMediaTabs.vue` — Imagem · Vídeo · Áudio · GIF, com registro extensível
      (FR-004): acrescentar um tipo não toca os existentes
- [X] T028 [P] `CompressionModeToggle.vue` — Básico ⇄ Avançado, **Básico é o padrão** (FR-038)
- [X] T029 [P] `useCompressionSettings.ts` — estado por tipo de mídia, com `auto`/`original` como
      padrão de todo campo técnico (FR-039)
- [X] T030 [P] `useCompressionEstimate.ts` — chama a estimativa com supressão de rajada, para
      digitar num campo não disparar uma chamada por tecla

**Checkpoint**: as rotas respondem, a tela abre com as abas e o alternador de modo, nada comprime
ainda. Nenhuma história começa antes daqui.

---

## Fase 3 — US1 + US2: Imagem ponta a ponta (P1) 🎯 MVP

**Meta**: importar, ajustar, estimar, comprimir, comparar e exportar uma imagem — inclusive por
tamanho alvo.

**Teste independente**: percorrer a jornada inteira sem abrir o modo Avançado e sem ver um único
termo técnico.

### Backend

- [X] T031 [US1] Escrever `app/compression/image.py` sobre **Pillow** (Decisão 1 da pesquisa):
      PNG, JPEG, WebP, AVIF, TIFF, BMP; qualidade; lossless; e as opções por formato (nível PNG,
      chroma e progressivo JPEG, effort WebP, speed/chroma AVIF)
- [X] T032 [US1] Implementar as sete políticas de metadados, com `essential_only` como padrão —
      preserva orientação e ICC, remove GPS e o resto (FR-028)
- [X] T033 [P] [US1] Escrever `test_image_metadata_policy.py`: cada política verificada **lendo os
      metadados do arquivo produzido**, nunca pela aparência
- [X] T034 [US1] Redimensionamento: largura, altura, percentual, proporção, impedir upscale
      (padrão ligado) e os presets de resolução (FR-027)
- [X] T035 [P] [US1] Escrever `test_image_resize.py`, incluindo que impedir-upscale de fato impede
- [X] T036 [US2] Resolução de tamanho-alvo para imagem por busca sobre amostra reduzida
      (Decisão 5), disparada ao confirmar o alvo e não a cada dígito
- [X] T037 [P] [US2] Escrever `test_image_target_size.py`: alvo atingível é atingido; alvo abaixo
      do piso é recusado antes

### Interface

- [X] T038 [US1] `ImageCompressionSettings.vue` — Básico: preset, qualidade com descrição dinâmica
      (FR-025), formato, resolução, tamanho alvo
- [X] T039 [US1] Modo Avançado da imagem: os controles por formato, **que mudam** conforme o
      formato escolhido em vez de ficarem presentes e desabilitados (FR-029)
- [X] T040 [P] [US1] `CompressionPresetSelector.vue`
- [X] T041 [P] [US2] `TargetSizeControl.vue` com KB/MB/GB
- [X] T042 [P] [US1] `CompressionEstimate.vue` — original, estimativa, economia, redução, e a
      declaração de que é estimativa (FR-019), com a `confidence` visível
- [X] T043 [P] [US1] `CompressionSummary.vue` — o resumo lateral do §61
- [ ] T044 [US1] `CompressionQueue.vue` + item, sobre a fila existente
- [X] T045 [US1] `CompressionComparison.vue` para imagem: lado a lado, slider, zoom sincronizado —
      reusando `CompareSlider` e `useViewportPanZoom`
- [X] T046 [US1] Resultado: tamanhos medidos, economia, redução, tempo, e `grew` quando o arquivo
      cresceu (FR-023)
- [X] T047 [US1] Exportação com destino, padrão de nome e política de conflito
- [X] T048 [P] [US1] Chaves de i18n de tudo acima nos 11 locales

### Verificação da fatia

- [ ] T049 [US1] Rodar os cenários 1, 10, 13, 14 e 18 do quickstart
- [ ] T050 [US2] Rodar os cenários 2, 3 e 4 do quickstart — o **2 pode reprovar a fórmula**
- [ ] T051 [US1] Confirmar SC-001: a jornada inteira sem um termo técnico

**Checkpoint**: 🎯 **Imagem é utilizável de ponta a ponta.** Se o trabalho parar aqui, a Central
já resolve o caso mais comum.

---

## Fase 4 — US3: Vídeo (P2)

- [ ] T052 [US3] `app/compression/video.py`: codec, container, CRF/CQ ou bitrate, resolução, FPS,
      preset de velocidade, preferência de encoder — argumentos **estruturados**, todo número por
      validador (Princípio XIII)
- [ ] T053 [US3] Progresso real por `-progress pipe:1`, com `speed` e tempo restante (FR-051)
- [ ] T054 [P] [US3] Escrever `test_video_progress_is_real.py`: o percentual acompanha a posição
      de tempo que o FFmpeg reporta, não um relógio
- [ ] T055 [US3] Áudio contido no vídeo: manter, recomprimir ou remover, com codec, bitrate,
      sample rate e canais (FR-031)
- [ ] T056 [US3] Aceleração por hardware com Automático/CPU/GPU e fallback por CPU (FR-047),
      com qualidade e compatibilidade acima de velocidade (FR-048)
- [ ] T057 [P] [US3] Escrever `test_video_compatibility_matrix.py`: combinação incompatível nunca
      é oferecida e nunca é aceita silenciosamente (FR-046)
- [ ] T058 [US3] `VideoCompressionSettings.vue` — Básico e Avançado, com o CRF mostrando a
      interpretação visual do §16
- [ ] T059 [US3] Comparação de vídeo com o player existente, sincronizando os dois (FR-055)
- [ ] T060 [P] [US3] Tooltips de todo parâmetro técnico (FR-042)
- [ ] T061 [P] [US3] i18n nos 11 locales
- [ ] T062 [US3] Rodar os cenários 5, 6, 7, 8, 9, 11 e 12 do quickstart — **o 5 é o que verifica a
      condição 4 da exceção constitucional, por hash**

**Checkpoint**: vídeo utilizável, e a exceção constitucional verificada na prática.

---

## Fase 5 — US4: Áudio (P2)

- [ ] T063 [US4] `app/compression/audio.py`: MP3, AAC, M4A, OGG, Opus, WAV, FLAC; codec, bitrate
      CBR/VBR, sample rate, canais
- [ ] T064 [US4] Formato lossless **oculta** controles de bitrate lossy (FR-033); sample rate
      `original` não faz resampling (FR-034)
- [ ] T065 [P] [US4] Escrever `test_audio_lossless_controls.py` e `test_audio_no_resampling.py`
- [ ] T066 [US4] `AudioCompressionSettings.vue`
- [ ] T067 [US4] Comparação de áudio: alternar original ⇄ resultado com duração, bitrate, codec,
      tamanho e sample rate (FR-056)
- [ ] T068 [P] [US4] i18n nos 11 locales
- [ ] T069 [US4] Rodar o cenário 15 do quickstart

---

## Fase 6 — US5: GIF e animação (P3)

- [ ] T070 [US5] `app/compression/animation.py` com a cadeia `palettegen`/`paletteuse` medida na
      Decisão 2, mais `libwebp_anim` para WebP animado
- [ ] T071 [US5] Detecção: GIF de um quadro é `image`, não `animation` (caso de borda registrado)
- [ ] T072 [P] [US5] Escrever `test_animation_compression.py`: resultado continua animado, ordem
      de quadros preservada, um-quadro classificado como imagem
- [ ] T073 [US5] Conversão GIF → WebP/MP4/WebM quando suportada, e ausente quando não
- [ ] T074 [US5] `AnimationCompressionSettings.vue`: qualidade, resolução, FPS, cores, dithering,
      otimização de quadros
- [ ] T075 [P] [US5] i18n nos 11 locales
- [ ] T076 [US5] Rodar os cenários 16 e 17 do quickstart

---

## Fase 7 — US6: Lote e fila (P3)

- [ ] T077 [US6] "Aplicar a todos" no cliente — N pedidos com as mesmas configurações, e não uma
      rota em lote que esconderia qual arquivo falhou (registrado em contracts/api.md)
- [ ] T078 [US6] Configuração individual por arquivo
- [ ] T079 [US6] Cancelar item e cancelar fila; tentar novamente item com erro
- [ ] T080 [P] [US6] Escrever `test_compression_queue.py`: cancelar um não afeta os outros; erro
      não para a fila
- [ ] T081 [US6] Progresso individual e geral, com velocidade e economia obtida
- [ ] T082 [US6] Rodar os cenários 11 e 19 do quickstart

---

## Fase 8 — US7: Presets do usuário e histórico (P3)

- [ ] T083 [US7] Persistência local dos presets do usuário, sobrevivendo ao reinício
- [ ] T084 [US7] Criar, salvar, renomear, duplicar, excluir; restaurar padrões
- [ ] T085 [US7] Histórico com `settings_snapshot`, e "repetir compressão" usando o snapshot e não
      o preset atual (FR-063)
- [ ] T086 [P] [US7] Escrever `test_compression_history.py` incluindo o caso do preset alterado
      depois da execução
- [ ] T087 [US7] Rodar os cenários 20 e 21 do quickstart

---

## Fase 9 — Transversais e acabamento

- [ ] T088 Erros compreensíveis, com a saída bruta do FFmpeg numa área recolhível (FR-065)
- [ ] T089 [P] Logs técnicos estruturados: job, arquivo, encoder, codec, parâmetros, duração,
      status, erro — fora da interface comum (FR-066)
- [ ] T090 [P] Acessibilidade: rótulo, foco, teclado, contraste em todo controle (FR-071)
- [ ] T091 [P] Responsividade desktop/notebook/telas menores (§57)
- [ ] T092 Verificar SC-010: interface responsiva com arquivo de ≥1 GB
- [ ] T093 [P] Rodar os cenários 22, 23 e 24 do quickstart
- [ ] T093a Confirmar o SC-008 exaustivamente: **percorrer toda opção selecionável** das quatro
      mídias, nos dois modos, e verificar que nenhuma falha por indisponibilidade do ambiente.
      Acrescentado pelo `/speckit.analyze` — o SC-008 era o único critério de sucesso sem nenhuma
      tarefa que o verificasse
- [ ] T094 Confirmar que nenhuma opção da interface existe sem implementação (FR-068) — varredura
      por controle, não por amostragem
- [ ] T095 Confirmar que nada fora da Central mudou (FR-069): `git diff` contra o estado inicial,
      arquivo por arquivo
- [ ] T096 Rodar lint, typecheck, vitest, pytest do core e pytest da API, **contra a build LGPL
      empacotada** e com o PATH limpo

---

## Dependências

- **Fase 1** → **Fase 2** → todas as histórias
- **Fase 3** (Imagem) não depende de 4, 5, 6
- **Fase 4** (Vídeo) e **Fase 5** (Áudio) são independentes entre si
- **Fase 6** (GIF) depende da Fase 4 — reusa o caminho de FFmpeg e progresso
- **Fase 7** (Lote) depende de ao menos uma mídia entregue
- **Fase 8** (Presets/histórico) depende de haver configuração que valha guardar
- **Fase 9** depende de tudo

## Paralelização

Dentro da Fase 2, T008–T013 (capacidades), T014–T017 (estimativa) e T018–T020 (presets) são três
frentes independentes. Na Fase 3, backend (T031–T037) e interface (T038–T048) avançam em paralelo
depois que os schemas da Fase 2 existem.

## Contagem

105 tarefas (96 + 9 acrescentadas pelo `/speckit.analyze`).
**Fases 1–3 entregam o MVP utilizável**: 59 tarefas.
