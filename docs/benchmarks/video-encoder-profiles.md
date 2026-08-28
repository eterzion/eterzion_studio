# Benchmark — encoders de vídeo por perfil

**Feature**: `007-video-editor-player` · tarefa T011a
**Data**: 2026-08-16
**Motivo**: o fluxo de desenvolvimento da constituição exige que *"Benchmarks MUST precede the final
choice of what backs each of the three profiles"*, e o Princípio III proíbe registrar afirmação de
desempenho sem medição. Este documento existe para que o mapeamento perfil → encoder da
`video_edits.py` não seja escolhido por reputação.

## Máquina

Windows 10 Pro. FFmpeg do PATH. Entrada: `curto.mp4` (1920×1080, 30 fps CFR, H.264, 10 s), os
3 primeiros segundos, saída descartada (`-f null`).

## Resultado

| Encoder | Container | Resultado | Tempo (3 s de 1080p) |
|---------|-----------|-----------|----------------------|
| `h264_nvenc` | mp4, mov, mkv | ❌ **falha** | — |
| `h264_qsv` | mp4, mov, mkv | ❌ **falha** | — |
| `h264_amf` | mp4, mov, mkv | ❌ **falha** | — |
| `libvpx-vp9` | mkv, webm | ✅ | **2,35 s** |
| `libaom-av1` | webm | ✅ | **50,63 s** |

Erros exatos das três falhas:

```
h264_nvenc  Driver does not support the required nvenc API version. Required: 13.1 Found: 13.0
h264_qsv    Error creating a MFX session: -9 — the current mfx implementation is not supported
h264_amf    DLL amfrt64.dll failed to open — failed to create hardware device
```

## O que a medição decidiu

**1. `libaom-av1` não respalda `fast` nem `balanced`, em nenhum container.** É **21,5× mais lento**
que `libvpx-vp9` na mesma entrada — 50,6 s para 3 s de vídeo, ou seja ~17× o tempo real. O
Princípio III diz que quando duas implementações corretas diferem, a mais rápida vence, e que ganho
de qualidade que multiplica o tempo de processamento precisa ser justificado por ganho medido e
perceptível. Nada aqui justifica 21×.

Mapeamento resultante para `webm`:

| Perfil | Encoder | Razão |
|--------|---------|-------|
| `fast` | `libvpx-vp9` | único viável |
| `balanced` | `libvpx-vp9` | único viável |
| `quality` | `libvpx-vp9` | ver nota abaixo |

`libaom-av1` **permanece na allowlist** — é o único caminho para AV1, é LGPL-compatível, e uma
máquina com mais CPU pode mudar a conta. Mas não é escolhido por padrão em nenhum perfil enquanto a
medição for esta. Revisar quando houver medição em hardware diferente.

**2. A checagem de disponibilidade tinha de ser funcional, não uma listagem.** `ffmpeg -encoders`
lista os três encoders H.264 de hardware nesta máquina, e os três falham no primeiro quadro. Uma
verificação baseada em listagem teria oferecido `mp4` e `mov` e deixado toda exportação morrer no
meio — exatamente o que o Princípio XIII proíbe. Daí `encoder_works()` em `media.py`, que codifica
um quadro 64×64 e observa o resultado. Custo medido: ~120 ms por encoder, cacheado por processo.

## Consequência de produto, ainda não resolvida

**Nesta máquina, `mp4` e `mov` não têm nenhum encoder utilizável.** Os dois containers mais comuns
ficam indisponíveis, e o produto oferece apenas `webm` e `mkv`.

Isso não é defeito desta feature — é a consequência direta de duas regras da constituição operando
juntas:

- encoders GPL (`libx264`, `libx265`) não podem ser empacotados;
- H.264/H.265 precisa portanto vir de encoder de hardware ou comercialmente licenciado.

Numa máquina sem encoder de hardware funcional, não sobra caminho para H.264. A feature se comporta
corretamente — recusa antes de começar, com motivo — mas a experiência é "o formato que você
esperava não está disponível".

**Decisão de produto pendente**, fora do escopo desta feature: licenciar comercialmente um encoder
H.264, ou aceitar que máquinas sem hardware compatível exportem apenas WebM/MKV. Vale medir em quais
máquinas reais os encoders de hardware funcionam antes de decidir — esta é uma amostra de uma.

## Como reproduzir

```bash
cd api/astros_upscale_api/tests/fixtures && python -m tests.fixtures.make_video_fixtures
```

```bash
ffmpeg -y -v error -i curto.mp4 -c:v libvpx-vp9 -t 3 -f null -
```
