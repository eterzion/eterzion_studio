# Dívida técnica — H.264 sem encoder GPL: decisão de produto pendente

**Registrado em**: 2026-08-16 · tarefa T084 da feature `007-video-editor-player`
**Parte de código**: **fechada** em 2026-08-21 (ver *O que foi corrigido*)
**Decisão de produto**: **fechada** em 2026-08-21 — aceitar WebM/MKV onde não há hardware
**Bloqueia**: nada

## O que era

[`optimize_video()`](../../api/astros_upscale/optimize.py) declarava:

```python
def optimize_video(input_path, output_path, quality=75, codec='libx264', ...)
```

`libx264` é **GPL**. A seção *Licensing and Distribution Constraints* da
constituição é explícita:

> **GPL encoders MUST NOT be bundled.** `libx264` and `libx265` are GPL. H.264
> and H.265 output MUST therefore come from hardware encoders (NVENC, QSV, AMF)
> or from a commercially licensed encoder — never from a GPL software encoder in
> the shipped build.

O registro original tratava isso como um padrão latente, tolerável até o
empacotamento. **Era pior do que isso.** Duas descobertas ao corrigir:

- `optimize_file()` tinha o **mesmo** `codec='libx264'` — o registro só nomeava
  `optimize_video`.
- `_run_compress_convert()` em [`jobs.py`](../../api/astros_upscale_api/app/jobs.py)
  chama `optimize_file(...)` **sem passar `codec`**. Ou seja: a tela de
  compressão/conversão não tinha um padrão GPL esperando o empacotamento — ela
  já produzia H.264 por libx264, em todo vídeo, hoje.

## O que foi corrigido

`optimize.py` deixou de tomar decisão de licenciamento por default:

1. `codec` agora é `None` por padrão em `optimize_video` e `optimize_file`, e
   `None` significa **resolver um que funcione aqui**, a partir do container de
   saída — via `first_available_encoder()`, que recusa a lista `GPL_ENCODERS`
   incondicionalmente, mesmo instalada e mesmo pedida por nome.
2. `_CONTAINER_VIDEO_ENCODERS` / `_CONTAINER_AUDIO_ENCODERS` espelham a allowlist
   da API. Não são importados de `config.py` de propósito: a dependência corre no
   sentido contrário (a API importa este pacote, nunca o inverso).
3. Cada encoder recebe o quantizador que entende — `cq` no NVENC,
   `global_quality` no QSV, `qp_i` no AMF, `crf` + `b:v 0` no VP9/AV1. O número
   continua vindo de `_quality_to_crf`; só o nome muda. O `preset: medium`
   anterior era vocabulário de libx264 e saiu.
4. Áudio deixou de ser sempre `copy`: copiar só é correto quando o container não
   muda. AAC não entra em WebM, Opus não entra em MP4 — converter com `copy`
   produzia arquivo inválido.
5. Falha antes de começar, com motivo, quando nenhum encoder do container
   funciona (Princípio XIII), e a mensagem **nunca nomeia um encoder** — ela
   chega ao cliente pelo campo de erro do job, e o Princípio V mantém nome de
   encoder fora desse fio.

Fixado por `test_optimize.py`: nenhum container oferece encoder GPL, todo
`VIDEO_EXTENSIONS` tem lista de encoders, codec GPL pedido por nome é recusado,
a mensagem não vaza nome, e cada encoder recebe o quantizador certo.

## A consequência, que é real

Na máquina de desenvolvimento, o benchmark da T011a
([video-encoder-profiles.md](../benchmarks/video-encoder-profiles.md)) mediu os
três encoders H.264 de hardware permitidos — `h264_nvenc`, `h264_qsv`,
`h264_amf` — **falhando ao codificar um único quadro**: driver NVENC
desatualizado, sem sessão MFX da Intel, `amfrt64.dll` ausente.

Antes da correção, comprimir para `mp4` nessa máquina funcionava — por libx264,
que é justamente o que a constituição proíbe. Depois dela, **recusa com motivo
nomeado**. `mp4`, `mov` e `avi` ficam indisponíveis onde não há hardware; sobram
`webm` e `mkv`.

Isso não é defeito. É o encontro de duas regras da constituição numa máquina sem
hardware compatível, e agora a tela de compressão se comporta como a de edição de
vídeo já se comportava. Mas na prática **implementa o segundo caminho da tabela
por omissão** — "aceitar WebM/MKV onde não há hardware" — e isso merece ser uma
escolha, não um efeito colateral.

## A decisão — tomada em 2026-08-21

**Aceitar WebM/MKV onde não há hardware.**

| Caminho | Custo | Efeito | |
|---------|-------|--------|---|
| Licenciar comercialmente um encoder H.264 | Dinheiro e negociação | `mp4`/`mov` disponíveis em toda máquina | recusado |
| **Aceitar WebM/MKV onde não há hardware** | **Zero** | **Parte dos usuários nunca exporta `mp4`** | **escolhido** |
| Exigir hardware compatível | Zero técnico | Reduz o público; precisa ser dito na compra | recusado |
| `libopenh264` (Cisco) | Baixo em código | Licença BSD, mas a isenção de royalties da Cisco só vale para o binário **dela**, baixado em runtime — muda a forma de distribuir, não só a allowlist. Qualidade abaixo de x264 | recusado |

### O que a escolha exige, e por que nada mais precisou ser feito

Aceitar WebM/MKV só é honesto se o usuário **souber por que** o formato que
esperava não está lá. Isso já está implementado no único lugar onde a escolha é
visível:

- `GET /video/export-options` responde container por container com
  `available`, decidido por sonda funcional e não pela allowlist;
- `VideoExportPanel.vue` desabilita o indisponível e mostra
  `videoEditor.limits.noEncoderAvailable` como motivo, em vez de simplesmente
  omitir a opção — omitir faria o usuário procurar o que não existe;
- se **nenhum** container servir, o painel diz isso em vez de oferecer um botão
  que falharia.

O caminho de compressão/conversão (`optimize.py`) recusa antes de transcodificar,
com motivo nomeado. Ele **não** tem seletor de formato na interface: a tela só
emite `operation: 'enhance'`, e compress/convert é superfície de API. Se um dia
ganhar seletor, ele precisa consultar disponibilidade como o editor faz — caso
contrário a recusa chega depois de o usuário esperar, não antes de escolher.

### Se a decisão for revista

1. Adotando `libopenh264` ou um encoder licenciado, acrescentá-lo em
   `VIDEO_CONTAINER_ALLOWLIST` ([`config.py`](../../api/astros_upscale_api/app/config.py))
   **e** em `_CONTAINER_VIDEO_ENCODERS` (`optimize.py`) — as duas listas, ou os
   dois caminhos divergem.
2. Passando a exigir hardware, dizer isso na página de compra e no instalador,
   não só no erro do job.
3. Vale medir em quais máquinas reais os encoders de hardware funcionam antes de
   rever — a medição da T011a é uma amostra de uma.
