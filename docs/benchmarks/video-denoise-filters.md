# Benchmark — substituto LGPL para `hqdn3d`

**Medido em**: 2026-08-21 · máquina de desenvolvimento (Windows 11, sem encoder
H.264 de hardware funcional — a mesma da T011a)
**Motivo**: `hqdn3d` é GPL e não existe na build LGPL que o instalador empacota
(ver [gpl-filters-in-video-edits.md](../technical-debt/gpl-filters-in-video-edits.md)).
A Development Workflow exige medir antes de escolher o substituto — reputação
não decide filtro.

## Método

Fonte limpa `testsrc2` codificada em VP9 sem perda perceptível (`crf 10`, `b:v 0`),
depois sujada com `noise=alls=18:allf=t+u`. Cada candidato roda sobre a versão
suja; a qualidade é o **PSNR médio contra a fonte limpa**, medido pelo próprio
filtro `psnr` do FFmpeg.

Duas medidas separadas, porque misturá-las engana:

- **Qualidade** — 854×480, 30 quadros. A saída é codificada, então o relógio
  desta passagem mede filtro **mais** codificação e não serve como custo.
- **Custo** — 1920×1080, 30 quadros, saída para `-f null -`. Sem codificação no
  caminho, o relógio mede o filtro. Três execuções, fica a melhor.

Todos os candidatos foram testados contra a build LGPL de verdade. `hqdn3d`,
`vaguedenoiser`, `owdenoise` e `smartblur` nem aparecem: são GPL e não existem
nela.

## Qualidade — PSNR contra a fonte limpa

| Filtro | PSNR (dB) | Ganho sobre o piso |
|--------|----------:|-------------------:|
| _sem denoise (piso)_ | 34,26 | — |
| `nlmeans=s=3.0` | **43,19** | +8,93 |
| `fftdnoiz=sigma=6` | 40,98 | +6,72 |
| `fftdnoiz=sigma=12` | 40,46 | +6,20 |
| `fftdnoiz=sigma=3` | 39,32 | +5,06 |
| `dctdnoiz=sigma=6` | 35,41 | +1,15 |
| `bm3d=sigma=6` | 35,00 | +0,74 |
| `removegrain=1` | 34,90 | +0,64 |
| `atadenoise` | 34,55 | +0,29 |

## Custo — 1080p, 30 quadros, sem codificação

| Filtro | s / 30 quadros | quadros/s | Sobre o vazio |
|--------|---------------:|----------:|--------------:|
| _`null` (piso de I/O)_ | 0,66 | 45,3 | — |
| `removegrain=1` | 0,67 | 44,7 | +1,5% |
| `atadenoise` | 0,69 | 43,6 | +4,5% |
| **`fftdnoiz=sigma=6`** | **0,74** | **40,6** | **+12%** |
| `dctdnoiz=sigma=6` | 5,50 | 5,5 | 8,3× |
| `bm3d=sigma=6` | 8,23 | 3,6 | 12,5× |
| `nlmeans=s=3.0` | 24,94 | 1,2 | 37,8× |

## Escolha: `fftdnoiz`

`nlmeans` ganha 2,2 dB a mais, e cobra **34× o tempo** de `fftdnoiz` por isso.
Em números do produto: um clipe de um minuto a 30 fps são 1800 quadros, ou
**25 minutos só de denoise** contra 44 segundos. Numa exportação que o usuário
espera, isso não é uma troca — é outro produto.

`dctdnoiz`, `bm3d`, `removegrain` e `atadenoise` estão fora pelo outro lado:
custam de 4% a 12× e entregam menos de 1,2 dB. `atadenoise` é temporal e continua
certo para o que o core já usa (estabilização), mas não substitui um denoise
espacial.

`fftdnoiz` entrega 75% do ganho do `nlmeans` por 12% de custo. É a escolha.

## Mapeamento do controle

O painel expõe um único controle 0–100. `sigma = strength / 100 * 12`:

- **50 → sigma 6**, o pico medido;
- **100 → sigma 12**, onde a medição já mostra a qualidade caindo (40,46 contra
  40,98) porque o filtro começa a comer detalhe junto com o ruído — o teto do
  controle é o ponto onde mais deixa de ser melhor, não um número redondo.

## Quando refazer

Ao trocar a versão do FFmpeg empacotado (`FFMPEG_SOURCE_VERSION` em
`fetch-ffmpeg.mjs`), e antes de aceitar qualquer pedido de "denoise mais forte":
a curva acima já é descendente depois de sigma 6.
