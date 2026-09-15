# Exportação

## O estado atual

Uma regra só nos quatro modos (Imagem, Vídeo, Áudio, Compressão), desde
2026-09-15 (PRs #144 a #147). O destino vai **no próprio pedido do job**, e o
job entrega o resultado nele antes de chegar a `done` — não existe mais uma
segunda etapa de exportação. `job.output_path` é o arquivo final.

O núcleo é `api/eterzion_upscale_api/app/destino.py`. Cada modo só decide o
formato e a codificação:

| Modo | Formatos | Qualidade | Código |
|---|---|---|---|
| Imagem | mesmo do original, PNG, JPG, WebP (TIFF pela API) | perfil → JPEG/WebP 80 / 90 / 97 | `app/exportacao_de_imagem.py` |
| Vídeo (edição) | MP4, MOV, MKV, WebM — os que a máquina grava | perfil de codificação | `app/video_edits.py` |
| Vídeo (upscale) | MP4 | — | `jobs._entregar_video` |
| Áudio | mesmo do original, WAV, FLAC, MP3, M4A, OGG, Opus | perfil → 192 / 256 / 320 kbps | `app/exportacao_de_audio.py` |
| Compressão | os da Central, com padrão de nome | presets, alvo de tamanho, modo Avançado | `app/compression/` |

A qualidade só aparece na tela em formato com perda: em PNG, WAV e FLAC não
há o que escolher, e um controle que não faz nada é pior que a sua ausência.

## As regras de destino

- **Pasta**: a escolhida; sem escolha, a pasta padrão das Configurações; sem
  ela, a do original.
- **Nome**: o do original (ou o digitado), com a extensão do formato de saída.
  A Compressão usa o padrão de nome (`{filename}_compressed`).
- **O original nunca é o destino** (Princípio XV): se o destino cair no
  próprio original, ganha o sufixo do modo — `_upscaled`, `_edited`,
  `_enhanced`, `_compressed` — inclusive com "Substituir".
- **Se já existir**:
  - *Manter os dois* (`rename`): o sufixo e depois `(1)`, `(2)`…;
  - *Substituir* (`overwrite`): grava por cima, com gravação segura;
  - *Perguntar* (`ask`): a rota responde **409** `{reason: "conflict", path}`
    **antes de criar o job**, e a tela abre a mesma caixa em todos os modos
    (`ConflictDialog.vue`, `usePerguntaDeConflito.ts`). Cancelar não é erro:
    nada foi processado.
- **Fila**: o job revê o destino ao começar. Dois pedidos para o mesmo
  arquivo não gravam um por cima do outro, e um nome já numerado só é
  renumerado.

## Recusas antes do job

Tudo o que pode recusar recusa na criação do job, nunca depois de minutos de
processamento: conflito em "Perguntar" (409), formato que não existe
(`format_unavailable`), formato que esta máquina não grava
(`encoder_unavailable`) e falta de espaço no destino (`insufficient_disk`,
com uma estimativa pelo formato e pelo tamanho ou duração). A tela escreve a
recusa na língua do app a partir do `reason`.

## Gravação segura

`destino.gravacao_segura()` dá um temporário **na pasta do destino**
(`nome.a1b2c3.partial.ext` — o marcador antes da extensão, porque o FFmpeg
deduz o formato por ela) e troca pelo destino com `os.replace` só no sucesso.
Uma falha ou um cancelamento não tocam no arquivo que já existia. Na mesma
pasta, e não no temporário do sistema: em outro disco a troca vira cópia e
deixa de ser atômica.

O parcial fica registrado no job, e o encerramento do app o apaga
(`jobs.shutdown`).

Imagem e Áudio processam primeiro num **intermediário sem perda** na pasta
interna (PNG, WAV) e codificam uma vez só, no formato pedido, direto no
temporário do destino; o intermediário é apagado depois. O upscale de Vídeo
grava o MP4 na pasta interna e só o muda de lugar para o destino.
Sem `output_target` no pedido, o resultado fica na pasta interna — é o que
clientes antigos recebem.

## Ajustes da Imagem

Ajustes de cor, efeitos e girar/espelhar da Imagem usam os mesmos filtros do
Vídeo (`video_edits.build_filter_chain`), aplicados ao intermediário depois do
modelo. A conversão para YUV é explícita em BT.709 e faixa limitada — a mesma
do shader da prévia (`useVideoPreviewPipeline.ts`). No padrão do FFmpeg para
PNG (BT.601), o arquivo divergia da prévia em até 15 níveis; um teste de
paridade mede isso. A transparência passa à parte: a cor e os efeitos só no
RGB, o alfa só pelas etapas geométricas.

## Na interface

- As escolhas de cada modo (formato, qualidade, pasta, conflito) ficam em
  `store/exportChoices.ts` e sobrevivem à troca de tela durante a sessão. Cada
  abertura do app começa pelo padrão das Configurações. O nome do arquivo vale
  só para o arquivo ativo.
- O resultado aparece no cartão "Arquivo salvo" (`SavedResultCard.vue`), igual
  em Imagem, Vídeo e Áudio: o nome, a pasta, "Abrir" e "Mostrar na pasta".
