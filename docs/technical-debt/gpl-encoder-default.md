# Dívida técnica — `optimize_video` tem um encoder GPL como padrão

**Registrado em**: 2026-08-16 · tarefa T084 da feature `007-video-editor-player`
**Status**: aberta, fora do escopo da 007
**Bloqueia**: o empacotamento de um instalador distribuível

## O que é

[`optimize_video()`](../../api/astros_upscale/optimize.py) declara:

```python
def optimize_video(input_path, output_path, quality=75, codec='libx264', ...)
```

`libx264` é **GPL**. A seção *Licensing and Distribution Constraints* da
constituição é explícita:

> **GPL encoders MUST NOT be bundled.** `libx264` and `libx265` are GPL. H.264
> and H.265 output MUST therefore come from hardware encoders (NVENC, QSV, AMF)
> or from a commercially licensed encoder — never from a GPL software encoder in
> the shipped build.

Hoje isso é tolerável porque o produto usa o FFmpeg do sistema em
desenvolvimento, e `media.py` já detecta e avisa (`is_lgpl_build()`,
`_warn_once_if_gpl_build()`). Deixa de ser tolerável no momento em que um
instalador for empacotado com FFmpeg embutido.

## Por que não foi corrigido na 007

Está fora do escopo dela. `optimize_video` serve o fluxo de otimização em lote,
que a feature de edição de vídeo não altera.

**A 007 não herda o problema.** A allowlist em
[`config.py`](../../api/astros_upscale_api/app/config.py) não contém encoder
GPL em nenhum container, e `first_available_encoder()` em `media.py` recusa
qualquer um da lista `GPL_ENCODERS` **mesmo quando instalado e mesmo quando
pedido explicitamente** — é propriedade da função, não disciplina de cada
chamador. `test_encoder_availability.py` e `test_video_edits.py` fixam isso.

## O que a 007 descobriu, e que agrava a decisão

Ao medir o benchmark da T011a
([video-encoder-profiles.md](../benchmarks/video-encoder-profiles.md)), os três
encoders H.264 de hardware permitidos — `h264_nvenc`, `h264_qsv`, `h264_amf` —
**falharam ao codificar um único quadro** na máquina de desenvolvimento: driver
NVENC desatualizado, sem sessão MFX da Intel, `amfrt64.dll` ausente.

Consequência: nessa máquina, **`mp4` e `mov` não têm nenhum encoder utilizável**.
Os dois containers mais comuns ficam indisponíveis, e o produto oferece apenas
`webm` e `mkv`.

Isso não é defeito de código. É o encontro de duas regras da constituição
operando juntas numa máquina sem hardware compatível. A feature se comporta
corretamente — recusa antes de começar, com motivo nomeado — mas a experiência
é "o formato que você esperava não está disponível".

## Caminhos possíveis

| Caminho | Custo | Efeito |
|---------|-------|--------|
| Licenciar comercialmente um encoder H.264 | Dinheiro e negociação | `mp4`/`mov` disponíveis em toda máquina |
| Aceitar WebM/MKV onde não há hardware | Zero | Parte dos usuários nunca exporta `mp4` |
| Exigir hardware compatível | Zero técnico | Reduz o público; precisa ser dito na compra |

Antes de decidir, vale **medir em quais máquinas reais os encoders de hardware
funcionam** — a medição da T011a é uma amostra de uma, e uma amostra de uma não
é base para uma decisão de produto.

## Ao resolver

1. Trocar o padrão de `optimize_video` por algo que não seja GPL, ou tornar o
   parâmetro obrigatório para que a escolha seja sempre explícita no chamador.
2. Conferir se `astros_upscale/optimize.py` tem outros padrões GPL.
3. Fechar este arquivo referenciando o commit.
