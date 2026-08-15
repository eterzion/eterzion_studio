# Phase 0 — Research: Área de Edição de Vídeo com Player Customizado

**Feature**: `007-video-editor-player` | **Date**: 2026-08-14 | **Plan**: [plan.md](./plan.md)

Dez decisões. As três primeiras determinam se a feature é viável; as demais fecham os requisitos que
a constituição impõe.

---

## Decisão 1 — Preview interativo por shader WebGL espelhando o filtro `eq` do FFmpeg

**Decisão**: o preview de ajustes e transformação roda no renderer, num shader de fragmento WebGL2
aplicado sobre o elemento `<video>`. O shader implementa a mesma fórmula do filtro `eq` do FFmpeg
que a exportação usará. O vocabulário de parâmetros (nome, faixa, valor neutro) é definido no
backend e consumido pelos dois lados, de modo que existe uma única definição do que "contraste 1.2"
significa.

**Rationale**:

- O SC-002 exige que o preview reflita a alteração em ≤ 2 s em 95% dos casos. Só processamento local
  entrega isso de forma confiável para arrasto contínuo de um controle.
- O FR-015 proíbe exibir um preview que difere silenciosamente do resultado. Isso obriga paridade
  matemática, não aproximação visual.
- A fórmula do `eq` (contraste, brilho, saturação, gama) é aritmética por pixel e cabe em um shader
  de ~30 linhas. Não há complexidade escondida.
- O Chromium do Electron traz WebGL2 nativo. Nenhuma dependência nova, e portanto nenhuma
  verificação de licença comercial (Princípio IV) entra no caminho crítico.

**Alternatives considered**:

- **Filtros CSS (`filter: brightness() contrast() saturate()`)** — rejeitado. Parece a opção
  simples, e é a armadilha: o `brightness` do CSS é multiplicativo e o do `eq` é aditivo. Nenhum
  mapeamento entre os dois é exato em todo o intervalo, então o preview divergiria da exportação de
  forma sistemática e invisível para quem usa. É exatamente o caso que o FR-015 nomeia.
- **Renderizar um trecho no servidor a cada alteração** — rejeitado para o caminho interativo.
  Fidelidade perfeita, latência de segundos por alteração e escrita em disco a cada movimento de
  slider. Inviável para o SC-002 e hostil ao Princípio III.
- **Reproduzir o vídeo já processado em baixa resolução** — rejeitado. Continua exigindo um passe de
  codificação por alteração, com o mesmo problema de latência.

---

## Decisão 2 — Dois níveis de preview, com a fronteira declarada

**Decisão**: o preview tem dois níveis, e a interface diz em qual está.

| Nível | Cobre | Como | Latência |
|-------|-------|------|----------|
| **Interativo** | ajustes (`eq`), transformação geométrica, corte temporal, áudio | shader WebGL + DOM, no renderer | imediato |
| **Sob demanda** | efeitos que o shader não reproduz fielmente (redução de ruído, nitidez avançada) | quadro atual renderizado pelo backend com o FFmpeg real, devolvido como imagem | segundos |

Quando um efeito do segundo nível está ativo, o player indica que o preview em movimento não o
inclui e oferece o quadro renderizado como comparação antes/depois.

**Rationale**: satisfaz o FR-015 sem fingir que tudo é previsualizável em tempo real e sem desistir
do preview para o que não é. O nível "sob demanda" reaproveita um padrão que já existe e funciona —
a rota de preview de redução de ruído devolve um par antes/depois em base64, e
`useDenoisePreview.ts` já resolve debounce, corrida de requisições e invalidação ao trocar de
arquivo (Princípio II).

**Alternatives considered**:

- **Um nível só, tudo no servidor** — rejeitado pela latência (Decisão 1).
- **Um nível só, tudo no cliente, aproximando os efeitos** — rejeitado: aproximar redução de ruído
  em shader produziria um preview convincente e errado, que é pior do que não ter preview.

---

## Decisão 3 — Passo quadro a quadro por `requestVideoFrameCallback`

**Decisão**: a correspondência entre tempo e número do quadro vem de
`HTMLVideoElement.requestVideoFrameCallback()`, cujo `metadata.mediaTime` e `presentedFrames`
identificam o quadro efetivamente exibido. O passo quadro a quadro posiciona por
`currentTime += 1/fps` com o vídeo pausado, e o número exibido é confirmado pelo callback, não
calculado às cegas.

Quando o ffprobe indica taxa de quadros variável, ou divergência entre a duração declarada no
container e a real, o número do quadro deixa de ser exibido como exato — é o que o FR-012 exige.

**Rationale**: `currentTime` sozinho não é confiável para identificar quadro: o navegador arredonda
para o quadro decodificável mais próximo, e em VFR o cálculo `tempo × fps` simplesmente não vale.
`requestVideoFrameCallback` é a única fonte no Chromium que informa qual quadro foi realmente
apresentado. Está disponível no Chromium do Electron sem flag.

**Alternatives considered**:

- **`tempo × fps` puro** — rejeitado: erra em VFR e em qualquer arquivo cujo `duration` do container
  divirja do conteúdo, ambos listados como edge case na spec.
- **Extrair quadros pelo backend para navegar** — rejeitado: transforma uma interação de milissegundos
  em ida e volta ao disco, e o Princípio III trata latência como a experiência mais direta.

---

## Decisão 4 — Chave de cache derivada do conteúdo, não do caminho

**Decisão**: todo artefato derivado (sprite da linha de tempo, quadro de preview, master em cache) é
indexado por uma chave que combina **tamanho em bytes, mtime e um hash parcial do conteúdo**
(primeiros e últimos blocos do arquivo mais o tamanho). `media.py` já importa `hashlib` e já usa
SHA-256 em outro ponto — a função de chave entra ali, ao lado do que já existe.

Quando a chave muda, o artefato anterior deixa de ser usado e é removido.

**Rationale**: o Princípio XV exige que a chave inclua algo que muda com o conteúdo, não só o
caminho. Hash completo de um arquivo de vários gigabytes a cada abertura violaria o Princípio III;
hash parcial mais tamanho e mtime detecta na prática todos os casos que importam aqui — arquivo
substituído, reexportado ou editado por outro programa.

**Alternatives considered**:

- **Só caminho** — proibido explicitamente pelo Princípio XV.
- **Só mtime + tamanho** — rejeitado: uma cópia com mtime preservado passaria por idêntica.
- **Hash completo** — rejeitado pelo custo em arquivos grandes, que é justamente o caso desta
  feature.

---

## Decisão 5 — O cliente envia intenção; o backend resolve encoder e preset

**Decisão**: o contrato de exportação aceita **container** (`mp4`, `mkv`, `webm`, `mov`) e
**perfil** (`fast`, `balanced`, `quality`). Não aceita nome de codec, nome de encoder, preset, CRF
nem formato de pixel. O backend mantém a allowlist e resolve a combinação, em duas etapas:

1. **Permitido** — a allowlist declara quais encoders podem ser usados para cada container.
   Encoders GPL (`libx264`, `libx265`) **não estão na lista**.
2. **Presente** — antes de iniciar, o backend confirma que o encoder escolhido existe neste
   ambiente (consulta aos encoders que o binário FFmpeg realmente expõe, estendendo `media.py`, que
   já é o dono dessa relação e já sabe detectar build LGPL). Se não existe, cai para a próxima opção
   permitida do mesmo container; se nenhuma existe, recusa com razão clara antes de processar.

**Rationale**: um mesmo mecanismo satisfaz três princípios. O XIII pede vocabulário fechado validado
no servidor e verificação de disponibilidade antes de começar. O V pede que a API aceite intenção e
nunca implementação. A seção de Licenciamento pede que encoder GPL não entre no produto — e o jeito
mais confiável de garantir isso é não existir campo pelo qual pedi-lo.

**Alternatives considered**:

- **Aceitar codec do cliente e validar contra allowlist** — rejeitado. Passaria no XIII, mas
  violaria o V ao expor implementação no contrato, e deixaria a porta aberta para um encoder GPL
  entrar via configuração.
- **Assumir que o encoder existe porque está na allowlist** — proibido pelo XIII: "uma entrada na
  allowlist significa permitido, não presente".

---

## Decisão 6 — Tetos por operação, somados ao piso de máquina

**Decisão**: cada operação declara tetos explícitos, verificados **antes** de iniciar, com o fator
limitante nomeado. Valores iniciais, definidos em configuração e não espalhados pelo código:

| Fator | Exportação com efeitos | Corte/remux sem reprocessamento |
|-------|------------------------|----------------------------------|
| Duração | 2 h | 4 h |
| Resolução | 3840 × 2160 | 7680 × 4320 |
| Taxa de quadros | 120 fps | 240 fps |
| Número de quadros | 500 000 | 1 000 000 |
| Tamanho do arquivo | 32 GB | 64 GB |

Esses tetos **não substituem** `check_capacity`. O piso de memória adaptativo continua funcionando
como está; os tetos são uma verificação adicional, aplicada antes. Um vídeo precisa passar nos dois.

**Rationale**: o Princípio VII (v2.6.0) exige que operações cujo custo escala com o tamanho da
entrada declarem máximos e recusem antes de começar. `check_capacity` responde "esta máquina
aguenta?"; os tetos respondem "este trabalho é razoável?". São perguntas diferentes e as duas
precisam de resposta. Ver a análise da tensão com FR-035 em [plan.md](./plan.md), *Complexity
Tracking*.

**Alternatives considered**:

- **Só `check_capacity`** — rejeitado: não cumpre o VII, que pede tetos por operação, e não impede
  um vídeo de 12 horas de começar numa máquina que tecnicamente cabe.
- **Substituir `check_capacity` por tetos fixos** — rejeitado: quebraria a cláusula de adaptação do
  próprio VII e o FR-035 da spec anterior.

---

## Decisão 7 — Registro de handles de mídia

**Decisão**: o processo Electron registra o arquivo escolhido pela pessoa e recebe um identificador
opaco. Todas as rotas novas aceitam apenas o identificador. `media_handles.py` resolve
identificador → caminho dentro do backend; o caminho nunca é parâmetro de rota. Nome de arquivo
vindo do cliente é tratado como texto de exibição e higienizado antes de participar da construção de
qualquer caminho.

O fluxo em lote existente (`POST /jobs/local`) **não é alterado** por esta feature.

**Rationale**: o Princípio XIII é explícito e não abre exceção para aplicação desktop. O registro é
a menor mudança que o satisfaz nas rotas novas sem arrastar o fluxo antigo para o escopo. O custo
aceito é conviverem dois modelos de referência até que o fluxo antigo migre — registrado na spec
como fora de escopo, não como resolvido.

**Alternatives considered**:

- **Manter caminho nas rotas novas** — rejeitado: viola o XIII e falha o SC-007, que mede o
  comportamento da API chamada diretamente.
- **Migrar todo o fluxo em lote junto** — rejeitado por escopo, não por mérito. É a direção certa
  para trabalho futuro.

---

## Decisão 8 — Entrega da mídia ao player pelo protocolo já existente

**Decisão**: o player consome o vídeo pelo esquema `astros-media://` que o processo principal já
registra, sem mudança no handler.

**Rationale**: o handler já faz exatamente o que um player precisa e o comentário no código mostra
que isso foi aprendido na prática — ele é registrado como esquema *standard* e *secure* (para
funcionar tanto sob o servidor de desenvolvimento quanto no build empacotado), responde a
requisições de **Range** (sem o que a linha de tempo não é navegável e o arquivo inteiro iria para a
memória), transmite em fluxo, e já declara os tipos MIME de vídeo. Reescrever isso seria reintroduzir
bugs já corrigidos — precisamente o que o Princípio II existe para evitar.

O parâmetro de query já usado para invalidar cache serve à Decisão 4 sem alteração.

**Alternatives considered**:

- **`file://` direto** — rejeitado: o Chromium bloqueia subrecurso `file://` a partir de página
  `http:`, que é como o renderer roda em desenvolvimento. O comentário no handler registra esse
  bug.
- **Servir o vídeo pela API HTTP** — rejeitado: acrescentaria um caminho de streaming com suporte a
  Range no backend para resolver um problema que o processo principal já resolveu.

---

## Decisão 9 — Chaves de tradução verificadas por teste, não por disciplina

**Decisão**: todo texto novo entra sob o prefixo `videoEditor.*` nos 11 arquivos de idioma. Um teste
automatizado compara os conjuntos de chaves entre todos os locales e falha quando divergem.

**Rationale**: o Princípio XIV diz que uma chave presente em apenas um idioma é pior do que um
literal, porque falha em execução nos demais em vez de aparecer durante o desenvolvimento. Um teste
converte esse risco em falha de CI, que é onde ele custa menos.

O princípio é explicitamente não retroativo: os ~32 literais que hoje estão em templates
permanecem, e nenhuma varredura é feita nas telas existentes. Se a área de edição reaproveitar um
componente com literal embutido, aquele literal é extraído — porque o componente está sendo
substancialmente retrabalhado, que é o gatilho que o próprio princípio define.

**Nota factual**: são **11** idiomas, não 12. `constitution.md` afirma 12 em dois lugares
(Princípio XIV e o log da emenda); `SUPPORTED_LOCALES` e o diretório de locales têm 11. Merece
correção PATCH na constituição, fora desta feature.

**Alternatives considered**:

- **Confiar na revisão de código** — rejeitado: é o mecanismo que já falhou; a cobertura de tradução
  vem encolhendo em relação à aplicação desde que os locales foram criados.

---

## Decisão 10 — O que é reaproveitado, e o destino de cada peça

O Princípio II exige que o destino de todo código existente relevante seja declarado como
**KEEP · MIGRATE · REFACTOR · REPLACE · REMOVE**.

| Peça existente | Destino | Observação |
|----------------|---------|------------|
| `components/MediaEditorShell.vue` | **KEEP** | Usado como está. É deliberadamente só layout; a área de edição de vídeo entra pelos seus dois slots. |
| `main/protocols/mediaProtocol.ts` | **KEEP** | Já resolve Range, streaming e MIME de vídeo (Decisão 8). |
| `app/jobs.py` | **KEEP + estender** | A exportação vira mais um tipo de job. Progresso, cancelamento e WebSocket vêm de lá — não são reimplementados. |
| `_capacity_check_for` (`routes.py`) | **KEEP + estender** | O Princípio VII nomeia esta como a forma estabelecida, a ser estendida e não duplicada. |
| `run_ffmpeg` (`media.py`) | **KEEP** | Forma obrigatória de invocação segundo o Princípio XIII. |
| `is_lgpl_build()` / `_warn_once_if_gpl_build()` | **KEEP** | Já detectam build GPL; a Decisão 5 se apoia neles. |
| `probe_streams` (`media.py`) | **KEEP + estender** | Já devolve duração e contagem de trilhas; ganha taxa de quadros e dimensões, que a linha de tempo precisa. |
| `useDenoisePreview.ts` | **KEEP** | Modelo do preview sob demanda (Decisão 2): debounce, guarda de corrida, invalidação ao trocar de arquivo. |
| `constants/processing.ts` | **KEEP + estender** | Já compartilha perfil e dispositivo entre as três telas; ganha as opções de container. |
| `views/VideoView.vue` | **KEEP** | O fluxo em lote continua. Ganha o ponto de entrada para a área de edição (FR-032). |
| `views/ImageEditorView.vue` | **KEEP** | Explicitamente isento pela v2.6.0. Não é tocado, nem dividido. |
| `optimize_video` (`optimize.py`) | **KEEP** | Fora do escopo desta feature. Seu padrão `libx264` fica registrado como dívida, não é herdado (Decisão 5). |

Nada é marcado REPLACE ou REMOVE: esta feature acrescenta uma superfície, não substitui nenhuma.
