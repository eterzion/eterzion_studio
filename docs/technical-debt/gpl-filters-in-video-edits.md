# Resolvido — a edição de vídeo usava dois filtros GPL que a build empacotada não tem

**Registrado em**: 2026-08-21 · descoberto ao rodar a suíte contra um FFmpeg LGPL real
**Fechado em**: 2026-08-21
**Impacto enquanto durou**: os ajustes e o denoise da tela de edição de vídeo
**falhavam por completo no aplicativo empacotado**, e funcionavam em desenvolvimento

## O que era

[`video_edits.py`](../../api/astros_upscale_api/app/video_edits.py) montava a
cadeia de filtros com dois nomes que **só existem em builds `--enable-gpl`**:

| Filtro | Servia para |
|--------|-------------|
| `eq=` | Brilho, contraste, saturação e gama — o painel de ajustes inteiro |
| `hqdn3d=` | Redução de ruído |

O aplicativo empacota uma build **LGPL**: [`fetch-ffmpeg.mjs`](../../interface/scripts/fetch-ffmpeg.mjs)
baixa `ffmpeg-n8.1-latest-win64-lgpl-shared` justamente porque a constituição
exige. O erro em produção seria `No such filter: 'eq'` — a exportação morre ao
abrir o filtergraph, antes do primeiro quadro.

O próprio `media.py` já registrava a regra em comentário:

> Never `hqdn3d` (GPL) for the same reason — a GPL filter in the filtergraph
> would GPL-license the resulting ffmpeg invocation the same way a GPL codec does.

A regra estava escrita. **Um comentário não reprova um build.**

## Como foi confirmado

Executando cada filtro que o código emite contra a build LGPL, não lendo
documentação. Dos onze, faltavam **exatamente os dois GPL**; `hue`, `unsharp`,
`gblur`, `noise`, `atadenoise`, `scale`, `crop`, `transpose`, `fps` e `format`
estavam todos presentes.

Isso também explicava as 5 falhas de `test_video_edits.py` em qualquer máquina
com FFmpeg LGPL. Elas passavam em desenvolvimento porque a máquina do
desenvolvedor tem um binário GPL no PATH.

## O que foi feito

1. **`eq` → `lutyuv`.** A aritmética não mudou: contraste pivota no meio-cinza,
   brilho soma, gama por último, e o clamp fica **antes** da potência (base
   negativa com expoente fracionário é NaN, não pixel escuro). `lutyuv` é LGPL,
   opera nos mesmos planos YUV armazenados e resolve para uma tabela de 256
   entradas por plano — exato em 8 bits e mais barato que a conta por pixel do
   `eq`. A paridade com o shader do preview foi **medida**, não presumida: os
   testes renderizam um cinza conhecido e comparam com `eqLuma()`.
2. **`hqdn3d` → `fftdnoiz`.** Escolhido por medição, conforme a Development
   Workflow — +6,7 dB de PSNR por ~12% de custo, contra `nlmeans` que ganha
   2,2 dB a mais e roda 34× mais devagar. Tabela completa em
   [video-denoise-filters.md](../benchmarks/video-denoise-filters.md).
3. **`GPL_FILTERS` + `graph_has_gpl_filter()` em `media.py`**, espelhando
   `GPL_ENCODERS`. A regra deixou de ser comentário e virou coisa que falha.
4. **O teste de paridade passou a renderizar a cadeia que o produto emite.**
   Antes ele escrevia `eq=...` à mão, ou seja, testava o filtro do FFmpeg e não
   o grafo do produto — por isso não podia ter percebido nada disto. Junto veio
   um teste que executa **toda a superfície de controles num único grafo** contra
   o FFmpeg local: um nome inexistente falha ao abrir o grafo, que é exatamente
   como `eq` e `hqdn3d` teriam sido pegos.
5. **O gerador de fixtures parou de usar `libx264`** (`mpeg4`, LGPL, no lugar).
   Ele falhava com `Unknown encoder 'libx264'` em qualquer máquina LGPL, e as
   57 provas que dependem dessas fixtures se puliam sozinhas — no CI inclusive.

## A causa que continua valendo para a próxima

**Desenvolvimento usa o FFmpeg do PATH; o usuário recebe outro binário.** Nenhum
teste rodava contra a build que é entregue. Os três defeitos desta família — o
encoder GPL padrão, estes dois filtros, e o `libx264` no gerador de fixtures —
saíram todos da mesma assimetria.

O item 4 acima fecha o caso do filtro inexistente, mas não a assimetria. Fechá-la
de vez significa rodar a suíte contra o binário que `fetch-ffmpeg.mjs` baixa —
está registrado como o passo seguinte em
[gpl-encoder-default.md](./gpl-encoder-default.md).
