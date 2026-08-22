# Phase 1 — Quickstart: validação da Central de Compressão

**Feature**: `008-compression-centre` · **Data**: 2026-08-21 · **Plan**: [plan.md](./plan.md)

Roteiro para provar que a feature funciona de ponta a ponta. Cada cenário aponta o requisito que
valida.

## Pré-requisitos

- FFmpeg **empacotado** disponível: `pnpm --dir interface fetch:ffmpeg:win` e
  `ASTROS_FFMPEG_DIR` apontando para `interface/resources/ffmpeg/win32`.
  **Não validar contra o FFmpeg do PATH.** Rodar contra um binário diferente do que o usuário
  recebe é exatamente a assimetria em que três defeitos desta semana viveram sem ficar vermelhos.
- Pillow 12.3+ (já em `requirements.txt`).
- Arquivos de teste:

| Apelido | O que é | Serve para |
|---|---|---|
| `foto.png` | 3840×2160, com EXIF e GPS | imagem, metadados, redimensionamento |
| `foto_ceu.jpg` | conteúdo liso | limite superior da estimativa |
| `foto_folhagem.jpg` | conteúdo detalhado | limite inferior da estimativa |
| `clipe.mp4` | ~30 s, 1080p, com áudio | vídeo, tamanho-alvo |
| `musica.wav` | ~3 min, 48 kHz estéreo | áudio |
| `anima.gif` | ~3 s, várias cores | animação |
| `um_quadro.gif` | GIF de 1 quadro | caso de borda |

## Subir o ambiente

```bash
cd interface && pnpm dev
```

---

## Cenários

### 1 — Reduzir uma imagem sem ver nada técnico (US1 · SC-001)

Arraste `foto.png`, escolha "Balanceado", comprima, compare, exporte.

**Esperado**: a jornada inteira sem um único nome de codec, encoder ou parâmetro em tela. Antes de
comprimir, tamanho original, estimativa e economia estimada aparecem. Depois, os mesmos números
medidos, mais o tempo.

### 2 — A estimativa se sustenta (SC-002)

Comprima `foto_ceu.jpg` e `foto_folhagem.jpg` no mesmo preset. Anote estimativa e resultado.

**Esperado**: ambos dentro de ±20%. **Este é o cenário que pode reprovar a fórmula** — é para isso
que ele existe. Conteúdo liso e conteúdo detalhado são os dois extremos que uma tabela estática
erra e a amostra codificada deveria acertar.

### 3 — Tamanho alvo atingido (US2 · SC-003)

`clipe.mp4` com alvo de 5 MB.

**Esperado**: a estimativa mostra as configurações derivadas e diz que é estimativa. O resultado
fica em 5 MB ou abaixo. Se passar, a interface diz por quanto e por quê.

### 4 — Alvo impossível recusado antes (FR-020)

`clipe.mp4` com alvo de 100 KB.

**Esperado**: `feasibility: below_floor`, dito **antes** de processar, com motivo. Nenhum job
criado, nenhum arquivo escrito. Um resultado ilegível entregue "com sucesso" reprova o cenário.

### 5 — Básico e Avançado produzem o mesmo (SC-007 · condição 4 da exceção)

Comprima `clipe.mp4` no Básico com "Balanceado". Repita no Avançado, mesmo preset, **todos os
controles em Automático**. Compare os hashes.

**Esperado**: idênticos. Este cenário é o que dá dente à condição 4 — sem ele, "Automático
funciona" é promessa.

### 6 — O modo Básico não conhece codec (SC-006 · condição 2)

Percorra o Básico inteiro, nas quatro mídias, e inspecione as respostas da API.

**Esperado**: nenhum nome de codec ou encoder em tela nem no corpo das respostas. O mesmo teste que
`test_no_codec_leak.py` faz para o editor.

### 7 — Contorno da interface (FR-064)

```bash
curl -X POST http://127.0.0.1:8050/compression/jobs -H "Content-Type: application/json" \
  -d '{"handle_id":"vh_x","media_kind":"video","advanced":false,"settings":{"video_codec":"h264"}}'
```

**Esperado**: **422** `invalid_settings`. Modo Básico mandando codec não é tolerado — tolerar seria
a porta pela qual a condição 2 deixa de valer.

### 8 — Indisponível é indisponível (FR-044/FR-045 · condição 5)

Numa máquina sem encoder H.264 de hardware, abra os codecs de vídeo.

**Esperado**: H.264 e H.265 desabilitados, com motivo, **sem nomear encoder**. Forçados via API →
422 `encoder_unavailable`. Nenhum encoder GPL aparece porque alguém pediu.

### 9 — Combinação incompatível não é oferecida (FR-046)

Escolha WebM e abra os codecs de vídeo.

**Esperado**: só VP9 e AV1. H.264 não aparece como opção silenciosamente "corrigida" depois.

### 10 — Origem intacta (FR-058 · SC-004)

Registre o hash de `foto.png`. Comprima, exporte, cancele outra no meio, provoque um erro.

**Esperado**: hash idêntico nos quatro desfechos. Diretório de temporários vazio.

### 11 — Nada órfão (FR-053 · SC-005)

Inicie a compressão de `clipe.mp4`, cancele no meio. Depois feche o aplicativo durante outra.

**Esperado**: nenhum processo FFmpeg vivo, nenhum temporário. Verificar com o gerenciador de
tarefas e listando o diretório de temporários — não confiar na ausência de mensagem de erro.

### 12 — Progresso é real (FR-051 · SC-009)

Comprima `clipe.mp4` e acompanhe.

**Esperado**: o percentual corresponde à posição de tempo que o FFmpeg reporta. `speed` e tempo
restante aparecem. Numa imagem, **não** aparecem — e a ausência é correta.

### 13 — Metadados sob controle (FR-028)

`foto.png` (com EXIF e GPS) em cada política de metadados.

**Esperado**: `preserve_all` mantém tudo; `essential_only` mantém orientação e ICC e remove GPS;
`strip_all` não deixa nada. Verificar com `exiftool` ou Pillow — não pela aparência.

### 14 — Formato muda os controles (FR-029)

Alterne o formato de saída de imagem entre PNG, JPEG, WebP e AVIF.

**Esperado**: os controles **mudam**, não ficam presentes e desabilitados. PNG mostra nível de
compressão; JPEG mostra chroma e progressivo; WebP mostra effort; AVIF mostra speed.

### 15 — Áudio lossless esconde bitrate lossy (FR-033)

`musica.wav` → FLAC.

**Esperado**: nenhum controle de bitrate lossy. Sample rate em "original" não faz resampling.

### 16 — Animação continua animada (US5)

`anima.gif` com menos cores e menor FPS.

**Esperado**: o resultado é menor e continua animado, com a mesma ordem de quadros. Conversão para
WebP/MP4/WebM disponível quando possível.

### 17 — GIF de um quadro é imagem (caso de borda)

Importe `um_quadro.gif`.

**Esperado**: classificado como `image`, não como `animation`. Controles de FPS e otimização de
quadros não aparecem.

### 18 — Compressão que aumenta (FR-023)

Comprima um JPEG já otimizado em qualidade máxima.

**Esperado**: a interface diz que o resultado ficou maior. Economia negativa apresentada como
sucesso reprova.

### 19 — Lote com configuração única (US6)

20 imagens, "aplicar a todos", processar, cancelar um item no meio.

**Esperado**: progresso individual e geral. Cancelar um não afeta os outros. Um erro não para a
fila.

### 20 — Preset sobrevive ao reinício (US7)

Salve um preset, feche o aplicativo, reabra, aplique.

**Esperado**: mesma configuração, mesmo resultado. Um preset de imagem não é oferecido em vídeo.

### 21 — Repetir do histórico (FR-063)

Comprima, altere o preset usado, e repita a compressão pelo histórico.

**Esperado**: usa o `settings_snapshot` daquela execução, não o preset alterado.

### 22 — Idiomas (FR-070 · SC-011)

Troque o idioma e percorra a Central inteira, incluindo uma mensagem de erro e um tooltip.

**Esperado**: nenhum texto no idioma errado, nenhuma chave crua.

### 23 — Teclado (FR-071 · SC-012)

Percorra a Central inteira só com teclado.

**Esperado**: todo controle alcançável, foco visível, sliders operáveis por seta.

### 24 — Erro compreensível (FR-065)

Force um erro de encoder.

**Esperado**: mensagem em linguagem comum. A saída bruta do FFmpeg fica numa área recolhível,
disponível mas não despejada.

---

## Critérios de aceitação da fase

A feature está validada quando os 24 cenários passam, os testes automatizados passam, e as
verificações constitucionais estão feitas:

- **V (exceção v4.0.0)** — cenários 5, 6, 7, 8: Básico sem vocabulário técnico, Automático
  equivalente ao Básico, indisponível não selecionável, licença fora do alcance do usuário
- **XIII** — cenário 8 e a sonda de todas as listas
- **XIV** — cenário 22
- **XV** — cenário 10
- **FR-053** — cenário 11

**O cenário 2 pode reprovar a fórmula de estimativa, e isso é um desfecho válido** — melhor
descobrir aqui do que descobrir que o SC-002 nunca foi verdade.
