# Resolvido — preview e exportação divergiam quando os ajustes eram combinados

**Registrado em**: 2026-08-21 · medido ao fechar o cenário 3 da `007-video-editor-player`
**Fechado em**: 2026-08-21
**Feria**: FR-015 (o preview não pode divergir da exportação em silêncio)

## O que era

Cada ajuste de cor, **isolado**, concordava entre o shader do preview e a cadeia
de filtros da exportação. **Combinados, não.** Diferença em níveis de 0–255, por
canal RGB, num quadro 1920×1080:

| Ajuste isolado | Média | p99 | Pior |
|----------------|------:|----:|-----:|
| Brilho 0,2 | 0,54 | 2 | 5 |
| Contraste 1,35 | 0,72 | 3 | 5 |
| Gama 1,4 | 1,14 | 3 | 6 |
| Saturação 1,25 | 0,43 | 3 | 6 |
| Matiz 25° | 0,84 | 3 | 6 |
| **Os cinco juntos** | **5,68** | **22** | **22** |

A tolerância adotada pelo projeto é `abs=0.02`, ≈5 níveis. Isolados, todos
passavam. Juntos, a média sozinha estourava.

## A primeira hipótese estava errada

A suspeita registrada era o clamp intermediário **na luma**: `lutyuv` grava numa
tabela de 8 bits e satura ao sair, enquanto o shader mantém float até o fim. Com
brilho, contraste e gama empurrando a luma contra os limites, pareceu a
explicação óbvia.

Um recorte que separa as explicações concorrentes derrubou a ideia:

| Caso | Média | p99 | Pior |
|------|------:|----:|-----:|
| Combinado suave (0,05 · 1,08 · 1,08 · 1,08 · 5°) | 0,59 | 5 | 9 |
| Combinado médio | 0,92 | 5 | 9 |
| Combinado forte | 2,56 | 22 | 22 |
| **Luma forte, sem croma** | **0,99** | 4 | 6 |
| **Croma forte, sem luma** | **5,95** | 20 | 21 |

**A luma concorda mesmo no forte.** Quem diverge é o **croma** — e nem saturação
nem matiz sozinhos (0,43 e 0,84), só os dois juntos.

## A causa

A cadeia fazia saturação num passo e matiz em outro:

```
lutyuv=u='clip((val-128)*1.25+128,0,255)':v='...'   →   hue=h=25
```

`lutyuv` escreve planos de **8 bits**. A saturação satura o croma e o clampeia
**antes** de o `hue` sequer ler. O shader escala e rotaciona em float e clampeia
uma vez, no fim. Não é a fórmula que difere: é quantas vezes o valor passa por 8
bits.

Isolada, a saturação concordava porque nada lia o resultado clampeado depois.

## A correção

Saturação passa a viajar junto com o matiz num único passo — o filtro `hue`
aceita `s=`:

```
hue=h=25:s=1.25
```

Escalar e rotação **comutam**, então a aritmética é a mesma; some uma ida a 8
bits, e some um filtro da cadeia.

Medido:

| Caso | Antes | Depois |
|------|------:|-------:|
| Croma forte — média | 5,95 | **0,93** |
| Croma forte — pior | 21 | **8** |
| Tudo combinado — média | 2,56 | **1,36** |
| Tudo combinado — pior | 22 | **8** |

Tudo dentro da tolerância do projeto, inclusive no pior caso.

## O que fica fixado

- `test_saturation_never_goes_through_a_chroma_lut` recusa o retorno do passo
  de croma em `lutyuv`, nomeando o motivo.
- `test_adjustments_split_between_luma_and_chroma` fixa a forma: dois passos, e
  só dois.
- O teste de paridade renderiza a cadeia que o produto emite, não um `eq=`
  escrito à mão.

**A lacuna que deixou isto passar:** o teste de paridade original exercitava
cinza com um parâmetro por vez. Nunca croma, nunca dois ao mesmo tempo — e esta
é exatamente uma classe que só aparece na combinação. Medir um parâmetro de cada
vez prova menos do que parece.
