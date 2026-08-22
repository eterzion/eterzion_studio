# Phase 0 — Pesquisa: Central de Compressão de Mídia

**Feature**: `008-compression-centre` · **Data**: 2026-08-21

Cada decisão abaixo foi **medida nesta máquina, contra a build LGPL que o instalador empacota**
(`interface/resources/ffmpeg/win32`), não lida em documentação. Essa distinção não é cerimônia:
três defeitos desta mesma semana existiram justamente porque o desenvolvimento rodava contra um
FFmpeg diferente do que o usuário recebe.

---

## Decisão 1 — Imagem passa a ser processada por Pillow, não por OpenCV

**Pergunta:** o caminho de imagem atual (`cv2.imencode`, em `optimize.py` e `Upscaler.export`)
atende a FR-024 (PNG, JPEG, WebP, AVIF, TIFF, BMP) e FR-028 (controle de metadados)?

**Não.** Duas paredes:

1. **AVIF.** `cv2` não escreve AVIF. O código atual contorna chamando FFmpeg com `libaom-av1` em
   modo still-picture — um subprocesso inteiro para gravar uma imagem.
2. **Metadados.** `cv2.imencode` **descarta todos os metadados, sempre**. Não há como preservar
   EXIF, ICC ou orientação. FR-028 pede escolher entre preservar tudo, só o essencial, ou remover
   seletivamente EXIF/GPS/comentários/ICC. Com OpenCV, só uma dessas opções é implementável — a de
   remover tudo — e ela seria implementada por acidente, não por escolha.

**Medido:** Pillow **12.3.0**, que já está em `requirements.txt` e já vem instalado, grava os seis
formatos e controla EXIF nos dois sentidos:

```
PNG: 161 B | JPEG: 677 B | WEBP: 92 B | AVIF: 324 B | TIFF: 9356 B | BMP: 9270 B
EXIF preservado quando pedido: AstrosTest
EXIF removido quando não pedido: True
```

AVIF é **nativo** no Pillow 12 — sem plugin, sem subprocesso de FFmpeg.

**Decisão:** o `ImageCompressionService` usa Pillow. `optimize.py` fica como está, servindo o fluxo
que já o usa; não é reescrito (Princípio II — o que funciona não é tocado por gosto).

**O que isso custa:** duas bibliotecas de imagem no processo. É custo real, e vale porque a
alternativa é ou não entregar FR-028, ou reimplementar leitura de EXIF sobre buffers do OpenCV —
que é escrever um Pillow pior.

---

## Decisão 2 — GIF pela cadeia palettegen/paletteuse do próprio FFmpeg

**Pergunta:** dá para comprimir GIF com a build LGPL, sem `gifsicle` nem dependência nova?

**Sim, medido.** A cadeia canônica roda:

```
fps=10,scale=160:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=64[p];[b][p]paletteuse=dither=bayer
→ GIF de 23.692 bytes
```

WebP animado também: `-c:v libwebp_anim` → 24.952 bytes. Os encoders `gif`, `libwebp` e
`libwebp_anim` estão presentes.

**Armadilha de método registrada:** a primeira sondagem reprovou `paletteuse` e `split` como
"ausentes". Estava errada — são filtros de múltiplas entradas/saídas e não funcionam sozinhos num
`-vf`. Sondar filtro assim produz falso negativo. **A sonda de capacidade de filtro tem que usar a
aridade real do filtro**, e isso vale para o código de produção, não só para esta pesquisa.

**Decisão:** `AnimationCompressionService` monta a cadeia com `filter_complex` estruturado.
`max_colors` atende ao controle de cores, `dither` ao de dithering, `fps` ao de quadros.

---

## Decisão 3 — Progresso vem de `-progress pipe:1`, não de temporizador

**Pergunta:** FR-051 proíbe progresso artificial. O FFmpeg empacotado reporta progresso legível?

**Sim, medido:**

```
out_time_ms=200000
progress=end
```

`-progress pipe:1` emite pares `chave=valor` em texto, incluindo `out_time_ms`, `total_size`,
`speed` e `frame`. Dividir `out_time_ms` pela duração sondada dá percentual real; `speed` dá o
multiplicador (§69) e permite estimar o tempo restante.

**Decisão:** o `VideoCompressionService` e o de áudio leem esse fluxo. Nenhum progresso derivado de
relógio.

**Consequência para imagem:** uma imagem não tem duração e o Pillow não reporta progresso. O
progresso de imagem é por **arquivo dentro da fila**, não dentro do arquivo — e a interface deve
dizer isso, em vez de simular uma barra que anda sozinha.

---

## Decisão 4 — Estimativa: fórmula por mídia, com honestidade declarada

**Pergunta:** como prever tamanho antes de processar (FR-021), com ±20% (SC-002)?

**Vídeo e áudio** são tratáveis: tamanho ≈ (bitrate_vídeo + bitrate_áudio) × duração + overhead de
container. Quando o modo é qualidade constante (CRF), não há bitrate declarado — a estimativa parte
de uma tabela bitrate-por-pixel-por-quadro calibrada por codec e CRF, que **precisa ser medida**,
não presumida. Fica como tarefa de benchmark, no mesmo formato da T011a da 007.

**Imagem** é mais difícil: o tamanho depende do conteúdo (uma foto de céu e uma de folhagem, mesmo
tamanho e mesma qualidade, diferem várias vezes). Duas saídas possíveis:

- extrapolar de uma tabela por formato/qualidade — barato e grosseiro;
- **codificar uma amostra reduzida e extrapolar pela razão de área** — mais caro (dezenas de ms) e
  bem mais fiel, porque a amostra carrega o conteúdo real.

**Decisão:** amostra reduzida. O custo cabe no orçamento de uma interface que já recalcula a cada
mudança de controle, e é a única das duas que pode cumprir o SC-002 num caso adversário.

**Registrado como risco:** o SC-002 exige ±20% em 80% dos casos. Isso **tem que ser medido antes
de a spec ser considerada cumprida**, e a medição pode reprovar a fórmula. É a razão de existir a
tarefa de benchmark.

---

## Decisão 5 — Tamanho alvo resolve para bitrate, e recusa quando não cabe

**Pergunta:** como derivar configurações de um alvo (FR-017)?

Para vídeo e áudio a inversão é direta: `bitrate_total = (alvo_bytes × 8) / duração`, menos
overhead, menos o bitrate de áudio escolhido. O que sobra é o bitrate de vídeo.

O caso interessante é o **piso**: abaixo de certo bitrate por pixel, o resultado deixa de ser
utilizável. Um vídeo de 2 h em 1 MB não é compressão, é destruição. FR-020 exige recusar antes.

**Decisão:** o `CompressionEstimatorService` calcula o alvo e o compara com um piso por resolução.
Abaixo do piso, recusa nomeando o motivo — nunca processa e entrega o que der.

**Para imagem**, o alvo é atingido por busca: comprimir com uma qualidade, medir, ajustar. Uma
busca binária em 4–5 iterações sobre uma amostra reduzida converge rápido. É caro demais para
rodar a cada tecla digitada, então roda ao confirmar o alvo, não a cada dígito.

---

## Decisão 6 — Compatibilidade container × codec vem de tabela declarada, validada por sonda

**Pergunta:** FR-046 proíbe oferecer combinação incompatível. De onde vem a compatibilidade?

Existem duas perguntas distintas, e confundi-las é o erro clássico:

1. **É legal?** MP4 não aceita VP9 com Opus de forma amplamente compatível; WebM só aceita
   VP8/VP9/AV1 com Vorbis/Opus. Isso é propriedade do formato, e é **tabela declarada**.
2. **Esta máquina consegue?** É sonda funcional, e já existe: `encoder_works()`,
   `audio_encoder_works()`, `image_format_works()`.

**Decisão:** a matriz de compatibilidade é declarada em configuração (FR-012, §66) e **filtrada**
pela sonda antes de chegar à interface. Uma combinação só é oferecida quando passa nas duas.
`VIDEO_CONTAINER_ALLOWLIST` já faz exatamente isso para o editor de vídeo — a Central estende o
mesmo mecanismo em vez de criar um segundo.

---

## Decisão 7 — Camada de serviços, não um módulo por classe

**Pergunta:** como organizar sem violar o Princípio XI (consolidação por domínio, não por classe)?

A solicitação (§38) lista sete serviços. O Princípio XI exige justificar cada módulo novo por três
condições testáveis, e "cada classe no seu arquivo" não é uma delas.

**Decisão:** um módulo `app/compression/` com submódulos por **domínio de mídia**, não por classe:

```
app/compression/
├── __init__.py        fachada: a única porta que as rotas conhecem
├── capabilities.py    matriz declarada + filtro por sonda (Decisão 6)
├── estimator.py       estimativa e resolução de alvo (Decisões 4 e 5)
├── presets.py         presets internos, de plataforma e do usuário
├── image.py           Pillow (Decisão 1)
├── video.py           FFmpeg + progresso (Decisões 3)
├── audio.py           FFmpeg
└── animation.py       FFmpeg palettegen/paletteuse (Decisão 2)
```

Sete arquivos, não sete classes espalhadas. `MediaMetadataService` não vira arquivo: sondagem já é
`media.probe_streams()` e `media.detect_secondary_elements()`, e duplicá-la seria o oposto de
reuso. `ExportService` também não: exportação já existe em `routes.py` e `jobs.py`.

---

## Decisão 8 — A fila é a que já existe

**Pergunta:** construir fila nova (§34) ou estender `app/jobs.py`?

`jobs.py` já tem estados, progresso, posição na fila, cancelamento, WebSocket de progresso,
supervisão de worker isolado e limpeza por job. A solicitação descreve exatamente isso.

**Decisão:** estender. Uma segunda fila seria dois lugares para um bug de concorrência morar.

**O que falta e será acrescentado:** estados `analyzing` (a sondagem/estimativa antes de
processar) e a padronização de nomes do §68 num único enum compartilhado.

---

## Riscos registrados

| Risco | Consequência | Mitigação |
|---|---|---|
| A fórmula de estimativa não alcançar ±20% | SC-002 reprova | Benchmark antes de fechar; a tarefa existe e pode reprovar a fórmula |
| Duas bibliotecas de imagem no processo | Memória e superfície maiores | Aceito por decisão registrada (Decisão 1) |
| H.264/H.265 indisponíveis sem hardware | Usuário não exporta MP4 | Já é o estado do produto; decidido em `gpl-encoder-default.md` |
| Sonda de filtro com aridade errada | Falso negativo desabilita recurso que funciona | Registrado na Decisão 2; a sonda usa a aridade real |
| Escopo de 71 FRs numa feature só | Entrega longa sem verificação | Fatiamento por mídia, decidido com o solicitante |
