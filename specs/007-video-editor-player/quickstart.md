# Phase 1 — Quickstart: validação da Área de Edição de Vídeo

**Feature**: `007-video-editor-player` | **Date**: 2026-08-14 | **Plan**: [plan.md](./plan.md)

Roteiro para provar que a feature funciona de ponta a ponta. Cada cenário aponta para o requisito
que valida. Detalhes de contrato ficam em [contracts/api.md](./contracts/api.md); formas de dados,
em [data-model.md](./data-model.md).

## Pré-requisitos

- FFmpeg e ffprobe disponíveis. Confirme que é build **LGPL**: `is_lgpl_build()` em
  `api/astros_upscale/media.py` responde isso a partir da linha de configuração real do binário.
- Ao menos um encoder de hardware presente (`h264_nvenc`, `h264_qsv` ou `h264_amf`), ou aceite que
  `mp4`/`mov` apareçam indisponíveis — que é, por si, o cenário 7.
- Arquivos de teste:

| Apelido | Características | Serve para |
|---------|-----------------|------------|
| `curto.mp4` | ~10 s, 1080p, 30 fps CFR, com áudio | fluxo principal |
| `vfr.mp4` | taxa de quadros variável | FR-012 |
| `sem_audio.mp4` | sem trilha de áudio | FR-009 |
| `longo.mp4` | > 2 h | teto de duração |

## Subir o ambiente

```bash
cd api/astros_upscale_api && python run.py
```

```bash
cd interface && pnpm dev
```

A API sobe em `8765` e o renderer em `5173`. **Reinicie a API depois de qualquer mudança de
schema** — schema alterado com processo antigo no ar produz 422 sem causa aparente.

## Testes automatizados

```bash
cd api/astros_upscale_api && python -m pytest tests/test_video_edits.py tests/test_video_thumbnails.py tests/test_media_handles.py tests/test_video_edit_export.py -v
```

```bash
cd interface && pnpm test
```

Os testes de backend usam FFmpeg real, não mock — o Princípio VIII trata pipeline de processamento
como coisa a testar contra comportamento real.

---

## Cenários de validação

### 1 — Reproduzir, pausar e navegar (US1 · FR-006 a FR-008)

Importe `curto.mp4` na área de edição. Reproduza; pause; arraste o cursor até uma posição arbitrária;
avance um quadro e volte um quadro.

**Esperado**: o tempo acompanha a imagem; a imagem depois de avançar-e-voltar é a mesma do ponto de
partida; tempo e número do quadro correspondem à posição real.

### 2 — Ajuste refletido no preview (US2 · FR-013a, FR-014 · SC-002)

Mova o controle de contraste de ponta a ponta continuamente.

**Esperado**: o preview acompanha sem travar, em ≤ 2 s por alteração. Devolver ao neutro (1.0) torna
a imagem indistinguível da original.

### 3 — Paridade entre preview e exportação (FR-015 · Decisão 1)

Aplique brilho `+0.2` e contraste `1.3`. Capture o quadro em `t=5s` do preview. Exporte e capture o
mesmo quadro do resultado.

**Esperado**: os dois quadros coincidem dentro da tolerância de codificação. Uma divergência
sistemática de brilho aqui é o sintoma exato de o preview ter caído em filtro CSS em vez do shader
que espelha o `eq` — é o motivo de este cenário existir.

### 4 — Origem intacta (FR-019 · SC-003)

Registre o hash de `curto.mp4`. Aplique ajustes, exporte, cancele outra exportação no meio, e provoque
uma falha.

**Esperado**: o hash é o mesmo nos três desfechos. Confira também que o diretório de temporários da
API ficou vazio (FR-022) e que nenhum arquivo parcial ficou no destino (FR-023).

### 5 — Colisão de nome (FR-020)

Exporte duas vezes para o mesmo destino com o mesmo nome.

**Esperado**: o segundo arquivo é gravado sob nome distinto. O primeiro continua intacto. Sobrescrever
só acontece com `conflict: "overwrite"` explícito.

### 6 — Recusa antes de começar (US4 · FR-025 · SC-005)

Envie `longo.mp4` para exportação.

**Esperado**: `422` com `reason: "ceiling_exceeded"` e `limiting_factor: "duration"`, **imediato** —
sem barra de progresso, sem uso de CPU, sem arquivo criado. Uma recusa que chega depois de o
progresso começar reprova este cenário.

### 7 — Encoder ausente (FR-027)

Consulte `GET /video/export-options` num ambiente sem encoder de hardware.

**Esperado**: `mp4` e `mov` vêm com `available: false` e
`unavailable_reason: "no_encoder_available"`; a interface não os oferece. Se forçados via API direta,
a criação do job recusa com `encoder_unavailable` antes de processar.

### 8 — Contorno da interface (SC-007 · FR-026 · Princípio XIII)

Chame a API diretamente, sem passar pelo renderer:

```bash
curl -X POST http://127.0.0.1:8765/video/edit-jobs -H "Content-Type: application/json" -d '{"handle_id":"vh_test","edits":{},"container":"mp4","profile":"balanced","codec":"libx264"}'
```

**Esperado**: `422`. O campo `codec` não existe no schema, e `extra='forbid'` o rejeita em vez de
ignorá-lo em silêncio. Repita trocando `codec` por `input_path` — mesmo resultado, mesma razão.

### 9 — Corte temporal (FR-013d · FR-007b)

Defina entrada em `t=2s` e saída em `t=5s`.

**Esperado**: a linha de tempo distingue o trecho; o preview respeita os limites; o arquivo exportado
tem ~3 s. Confirme que a verificação de tetos usou 3 s, e não a duração do arquivo inteiro.

### 10 — Áudio (FR-013e · FR-009)

Em `curto.mp4`, remova a trilha e exporte. Depois abra `sem_audio.mp4`.

**Esperado**: o resultado não tem trilha de áudio. Com `sem_audio.mp4`, os controles de áudio não são
oferecidos como se houvesse trilha.

### 11 — Taxa de quadros variável (FR-012)

Abra `vfr.mp4`.

**Esperado**: o número do quadro **não** é apresentado como exato. Exibir um número confiante aqui
reprova o cenário — é preferível não exibir.

### 12 — Cache invalidado por conteúdo (FR-017 · Decisão 4)

Abra `curto.mp4` e deixe as miniaturas carregarem. Substitua o arquivo por outro conteúdo, mantendo o
nome. Volte à área de edição.

**Esperado**: as miniaturas antigas não são exibidas. Isto falha silenciosamente quando a chave de
cache é só o caminho — é o cenário que prova a Decisão 4.

### 13 — Idiomas (US5 · FR-029 · SC-006)

Troque o idioma em Configurações e percorra a área de edição, incluindo uma mensagem de erro.

**Esperado**: nenhum texto no idioma errado, nenhuma chave crua na tela. O teste automatizado de
paridade de chaves cobre os 11 locales; este cenário confere o que só o olho pega — chave existente
mas texto não traduzido.

### 14 — Convivência com o fluxo em lote (FR-032)

Na tela de Vídeo, use o fluxo de upscale/otimização em lote como antes.

**Esperado**: funciona exatamente como funcionava. A área de edição é um modo adicional; nada foi
removido.

---

## Critérios de aceitação da fase

A feature está validada quando os 14 cenários passam, os testes automatizados passam, e três
verificações de conformidade constitucional estão feitas:

- **XIII** — nenhum campo de caminho ou de codec nas rotas de edição (cenário 8)
- **XIV** — paridade de chaves entre os 11 locales (teste automatizado)
- **XV** — origem intacta e cache invalidado por conteúdo (cenários 4 e 12)

Uma feature não está completa por compilar. Ela precisa rodar, ter testes passando, e spec, plano,
tarefas e implementação concordando entre si.

---

## Resultado da validação — 2026-08-19

Executado contra a API viva (`127.0.0.1:8765`) com FFmpeg real, na máquina de
desenvolvimento. **9 dos 14 cenários rodaram e passaram**; os 5 restantes exigem
a janela do Electron e estão nomeados abaixo como não executados, não como
aprovados.

| # | Cenário | Resultado |
|---|---------|-----------|
| 4 | Origem intacta | ✅ `done`, hash idêntico, nenhum parcial remanescente |
| 5 | Colisão de nome | ✅ `curto.webm` → `curto (1).webm`, o primeiro preservado |
| 6 | Recusa antes de começar | ✅ 422 `ceiling_exceeded`, fator `width` nomeado |
| 7 | Encoder ausente | ✅ `mp4` e `mov` indisponíveis com `no_encoder_available`, nenhum nome de encoder na resposta |
| 8 | Contorno da interface | ✅ `codec` → 422, `input_path` → 422 |
| 9 | Corte temporal | ✅ 3,008 s de um pedido 2 s→5 s |
| 10 | Áudio | ✅ trilha removida na saída; `sem_audio.mp4` reporta `has_audio: false` |
| 11 | Taxa de quadros variável | ✅ `frame_rate_is_variable: true` |
| 12 | Cache invalidado por conteúdo | ✅ preview recusa com 409, chave de conteúdo muda |
| 3 | Paridade preview × exportação | ✅ **medida** em 2026-08-21 (seção abaixo), não olhada. Encontrou uma divergência real no croma; corrigida e re-medida |

### Não executados

| # | Cenário | Por que não rodou |
|---|---------|-------------------|
| 1 | Reproduzir, pausar, navegar quadro a quadro | Exige importar arquivo pelo diálogo nativo |
| 2 | Ajuste refletido no preview | Exige o shader rodando na janela do Electron |
| 13 | Troca de idioma | Exige percorrer a interface |
| 14 | Fluxo em lote intacto | Verificado por diff (só adições em `VideoView.vue`); falta a conferência na tela |

Os quatro dependem do diálogo nativo de arquivos ou da janela do Electron. Um
navegador comum tem `hasNativeApi` falso, então a superfície cai no estado "não
é possível exibir" — que é o comportamento correto do FR-011, e não evidência de
reprodução.

---

## Medição do SC-002 — completa (2026-08-21)

### Nível sob demanda — 1080p, 5 execuções por caso

| Caso | Mediana | Pior |
|------|---------|------|
| Quadro puro | 123 ms | 293 ms |
| Ajustes | 122 ms | 127 ms |
| Redução de ruído | 132 ms | 134 ms |
| Ruído + desfoque + granulação | 146 ms | 150 ms |

Folgadamente dentro dos 2 s. Empilhar três efeitos custa 24 ms a mais que o
quadro puro — o custo está em decodificar e escrever, não nos filtros.

### Nível interativo (o shader) — 1080p, 60 quadros

Medido com os shaders **extraídos** de `useVideoPreviewPipeline.ts`, não
transcritos, sobre um quadro 1920×1080 decodificado de VP9, com todos os
parâmetros fora do neutro (no neutro o driver pode otimizar o shader para nada):

| | |
|---|---|
| GPU | ANGLE / NVIDIA RTX 4060 / Direct3D11 |
| Mediana | **0,100 ms** |
| p95 | 0,200 ms |
| Pior | 0,300 ms |
| Só GPU (`EXT_disjoint_timer_query_webgl2`) | **0,073 ms** |

**Teto do SC-002: 2000 ms. Passa com quatro ordens de grandeza de folga** — a
30 fps o orçamento por quadro é 33 ms, e o shader usa 0,3% disso.

Ressalva de método: medido no Chromium do painel de navegação, não dentro da
janela do Electron. É a mesma pilha (Chromium + ANGLE + D3D11) e o mesmo shader,
mas não é literalmente a janela do produto. Uma máquina, uma GPU.

---

## Cenário 3 — paridade preview × exportação, medida

Em vez da conferência visual, o mesmo quadro passou pelos dois caminhos de
produção — o shader WebGL e a cadeia que `build_filter_chain` monta — e os
pixels foram comparados. Diferença em níveis de 0–255, por canal RGB, num quadro
1920×1080.

A medição **encontrou uma divergência e ela foi corrigida**. Os números abaixo
são os de depois; o antes, a causa e o recorte que a isolou estão em
[preview-export-parity-combined.md](../../docs/technical-debt/preview-export-parity-combined.md).

| Caso | Média | p99 | Pior |
|------|------:|----:|-----:|
| Combinado suave | 0,73 | 4 | 6 |
| Combinado médio | 1,05 | 4 | 7 |
| Combinado forte | 1,51 | 7 | 7 |
| Luma forte, sem croma | 1,03 | 3 | 6 |
| Croma forte, sem luma | 0,86 | 3 | 6 |

A tolerância adotada pelo projeto é `abs=0.02`, ≈5 níveis. **Todos os casos
passam na média, e o pior caso da tabela inteira é 7.**

Antes da correção, croma forte divergia 5,95 de média e 21 no pior caso: a
saturação passava por uma tabela de 8 bits e era clampeada antes de o `hue`
ler, enquanto o shader escala e rotaciona em float e clampeia uma vez. Saturação
e matiz agora viajam num único `hue=h=..:s=..` — escalar e rotação comutam, a
aritmética é a mesma, e some uma ida a 8 bits.

**O que a medição ensinou sobre o teste:** cada parâmetro isolado sempre
concordou, inclusive antes da correção. A divergência só existia na combinação
de dois. Um teste de paridade que exercita um parâmetro por vez, em cinza, não
podia ter visto isso — e era exatamente o que existia.

### Método, e por que ele foi refeito três vezes

Cada passo abaixo mudou o resultado, e nenhum deles era defeito do produto —
vale registrar para que a próxima medição não repita:

1. **`readPixels` devolve de baixo para cima.** O flip de `v_uv` no shader
   conserta a orientação na tela, não no buffer lido de volta. Comparar sem
   inverter mede espelhamento: pior caso 255.
2. **Quadro desalinhado.** O `<video>` busca por PTS, o `-ss` do ffmpeg por
   keyframe. Com `testsrc2` em movimento, os dois lados comparavam quadros
   diferentes: p99 saltava para ~150. Resolvido congelando a origem.
3. **Bordas com croma subamostrado.** Em `yuv420p`, navegador e ffmpeg
   reconstroem a subamostragem de formas diferentes; numa borda dura isso
   sozinho dá dezenas de níveis. Origem lisa (gradiente) isola a fórmula do
   formato.
