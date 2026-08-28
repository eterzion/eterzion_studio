# Benchmark — estimativa de tamanho na compressão de imagem

**Medido em**: 2026-08-21 · tarefa T015 da feature `008-compression-centre`
**Critério**: SC-002 — estimativa dentro de ±20% do resultado real em ≥80% dos casos

A tarefa foi escrita com a possibilidade explícita de reprovar a fórmula. **Ela
reprovou, duas vezes**, e as duas reprovações apontaram defeitos estruturais que
nenhuma revisão de código teria encontrado — porque o código estava correto e a
*ideia* é que estava errada.

## Método

Cinco conteúdos em 1920×1080, escolhidos como adversários e não como amostra
representativa: se a fórmula sobrevive aos extremos, sobrevive ao meio.

| Conteúdo | Por que está aqui |
|---|---|
| `liso_gradiente` | onde o codec brilha e o cabeçalho domina |
| `ceu_suave` | o caso comum de foto com pouca textura |
| `padrao_medio` | conteúdo que **varia entre as regiões** da imagem |
| `detalhado_ruido` | ruído puro — o pior caso para qualquer codec |
| `bordas_duras` | bordas nítidas e áreas chapadas juntas |

Cinco combinações de formato e qualidade cada: JPEG 85, JPEG 50, WebP 80,
AVIF 60, PNG 80. **25 casos.**

O erro é `(estimado − real) / real`, e o real é o arquivo inteiro codificado de
verdade pelo mesmo Pillow que a Central usa.

## Tentativa 1 — reduzir a imagem e extrapolar pela área

Comprimir uma versão reduzida a 320 px de lado e multiplicar pela razão de
pixels.

```
erro médio absoluto : 267.9%
pior erro           : 1479.8%
dentro de ±20%      : 0/25 (0%)                          REPROVA
```

**Zero de vinte e cinco.** E o padrão dos erros é mais informativo que o número:

| Conteúdo | Erro |
|---|---|
| liso / bordas duras | **+97% a +1480%** — superestima |
| ruidoso | **−47% a −75%** — subestima |

Sinais opostos conforme o conteúdo. Isso não é calibração ruim, é a ideia
errada: **reduzir uma imagem muda o seu conteúdo de frequência, que é
exatamente o que decide o tamanho comprimido.** No conteúdo liso a amostra
minúscula fica dominada pelo cabeçalho, e multiplicar o cabeçalho pela razão de
área infla tudo. No ruidoso, a redução *destrói* o ruído — a amostra comprime
lindamente e o original não.

## Tentativa 2 — recorte em resolução nativa, dois pontos

Duas mudanças: recortar em vez de reduzir (a frequência local é preservada), e
medir dois tamanhos de recorte para separar o custo fixo do custo por pixel.

```
bytes_por_pixel = (S_512 − S_256) / (A_512 − A_256)
fixo            = S_256 − bytes_por_pixel × A_256
estimativa      = fixo + bytes_por_pixel × A_saída
```

```
erro médio absoluto : 32.6%    (era 267.9%)
pior erro           : 88.5%    (era 1479.8%)
dentro de ±20%      : 9/25 (36%)                         REPROVA
```

Oito vezes melhor e ainda reprovado. O padrão de novo aponta a causa:

| Conteúdo | Erro |
|---|---|
| ruidoso | **−0.2% a +1%** — praticamente exato |
| uniforme (liso, céu) | +2% a +81% |
| **que varia entre regiões** | **−22% a −71%** |

O ruído é homogêneo, então um recorte central o representa perfeitamente. O
conteúdo que *varia no espaço* não: o centro de `padrao_medio` não se parece com
os cantos, e a estimativa respondia pela imagem inteira tendo olhado um pedaço.

## Tentativa 3 — grade de cinco recortes

Amostrar centro e quatro quadrantes, somar, e dividir o custo fixo pelos cinco
(a medição é de cinco arquivos; o resultado será um).

```
erro médio absoluto : 8.6%     (era 267.9%, depois 32.6%)
pior erro           : 55.0%
dentro de ±20%      : 22/25 (88%)                        PASSA
```

### Resultado por caso

| Conteúdo | JPEG 85 | JPEG 50 | WebP 80 | AVIF 60 | PNG 80 |
|---|---:|---:|---:|---:|---:|
| liso_gradiente | +8.9% | +4.1% | +12.0% | +11.5% | +18.1% |
| ceu_suave | +2.4% | 0.0% | +4.2% | +4.5% | +20.7% |
| padrao_medio | +2.5% | +3.2% | −8.8% | +5.0% | +7.9% |
| detalhado_ruido | 0.0% | 0.0% | +0.9% | 0.0% | −0.3% |
| bordas_duras | +5.1% | +3.3% | **+34.1%** | +2.7% | **+55.0%** |

## Os três casos que ficam fora, e por que ficam

Todos os três são **superestimativas** — a estimativa promete um arquivo maior
que o que sai. A direção importa: quem mira um limite de 8 MB e recebe 6 MB fica
satisfeito; o contrário estoura o limite.

- **`bordas_duras` PNG (+55%)** e **WebP sem perda (+34%)**: compressão sem
  perda explora repetição em *toda* a imagem. Um padrão que se repete pelos
  1920 px é redundância que um recorte de 512 px não enxerga — ele vê o padrão
  uma vez, o arquivo inteiro o vê dezenas. Recortes não capturam redundância de
  longo alcance, e nenhum tamanho de recorte capturaria.
- **`ceu_suave` PNG (+20.7%)**: a mesma coisa, mais fraca.

**Não vale corrigir.** Corrigir exigiria codificar a imagem inteira, que é o
trabalho que a estimativa existe para evitar — e o erro é conservador e restrito
a formatos sem perda, onde a compressão é modesta de qualquer forma.

## Custo

Dez codificações de recorte (cinco posições × dois tamanhos) por estimativa. Em
1920×1080 isso fica na casa das dezenas de milissegundos, o que cabe numa
interface que recalcula a cada movimento de controle.

## Quando refazer

- Ao acrescentar formato de imagem.
- Ao trocar a versão do Pillow — os codificadores mudam entre versões.
- Antes de afrouxar o SC-002: **o critério não deve ser ajustado ao resultado.**
  Foi a fórmula que mudou duas vezes aqui, não o alvo.

## O que isto ensinou, além do número

Duas ideias plausíveis reprovaram, e nenhuma reprovou por bug. A primeira
parecia óbvia — reduzir e extrapolar é o que qualquer um faria. A segunda
corrigiu o defeito real e escondeu outro atrás dele. **A medição não confirmou
uma escolha; ela escolheu.**
