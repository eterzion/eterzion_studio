# Aberto — preview e exportação divergem quando os ajustes são combinados

**Registrado em**: 2026-08-21 · medido ao fechar o cenário 3 da `007-video-editor-player`
**Status**: aberto
**Fere**: FR-015 (o preview não pode divergir da exportação em silêncio)

## O que é

Cada ajuste de cor, **isolado**, concorda entre o shader do preview e a cadeia
de filtros da exportação. **Combinados, não.**

Diferença em níveis de 0–255, por canal RGB, num quadro 1920×1080:

| Ajuste isolado | Média | p99 | Pior |
|----------------|------:|----:|-----:|
| Brilho 0,2 | 0,54 | 2 | 5 |
| Contraste 1,35 | 0,72 | 3 | 5 |
| Gama 1,4 | 1,14 | 3 | 6 |
| Saturação 1,25 | 0,43 | 3 | 6 |
| Matiz 25° | 0,84 | 3 | 6 |
| **Os cinco juntos** | **5,68** | **22** | **22** |

A tolerância que o projeto adotou é `abs=0.02`, ≈5 níveis. Isolados, todos
passam. Juntos, a média sozinha já estoura, e o pior caso é 22 níveis — 8,6% da
faixa.

O salto é maior que a soma das partes, então não é acúmulo de arredondamento.
É diferença de **composição**.

## A suspeita

O ponto onde cada lado satura:

- `lutyuv` grava numa tabela de 8 bits. Cada plano é clampeado para 0..255
  **ao sair do filtro**, antes de o `hue` seguinte rodar.
- O shader mantém luma e croma em float do começo ao fim e clampeia **uma vez**,
  na escrita do fragmento.

Com brilho, contraste e gama empurrando a luma contra os limites e a saturação
empurrando o croma, um satura antes do outro. Isso explica por que a divergência
só aparece quando os parâmetros são combinados: sozinho, nenhum deles leva o
valor até o batente.

**É suspeita, não conclusão.** Confirmar exige instrumentar os dois caminhos com
os valores intermediários, não só comparar a saída.

## O que não dá para afirmar

- **Se o `eq` se comportava igual.** A troca de `eq` por `lutyuv` aconteceu no
  mesmo dia (ver [gpl-filters-in-video-edits.md](./gpl-filters-in-video-edits.md)),
  e a build LGPL empacotada não tem `eq` — não há como medir o comportamento
  anterior nesta máquina. `eq` também constrói LUT de 8 bits, então provavelmente
  clampeava no mesmo ponto e a divergência é anterior à troca. Provável não é
  medido.
- **Se o teste antigo teria pego.** Não teria: `test_ffmpeg_eq_matches_the_formula_the_shader_implements`
  exercitava cinza com brilho e contraste. Nunca croma, nunca dois parâmetros ao
  mesmo tempo. Foi exatamente essa lacuna que deixou isto passar.
- **Se 22 níveis são visíveis** no material do usuário. Num gradiente liso,
  provavelmente sim.

## Ao resolver

1. Instrumentar os dois caminhos e localizar o passo onde divergem, em vez de
   ajustar a fórmula até os números caírem.
2. **Estender o teste de paridade a parâmetros combinados e a croma.** Enquanto
   ele só medir cinza com um parâmetro por vez, esta classe continua invisível —
   e é a segunda vez que uma lacuna assim custa caro nesta feature.
3. Se a causa for o clamp intermediário, decidir qual lado muda: o shader pode
   clampear entre os passos para imitar a tabela, ou a cadeia pode rodar em
   maior profundidade de bits (`format=yuv444p16` antes do `lutyuv`).
