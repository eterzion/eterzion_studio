# Feature Specification: Audio Engine — Masterização e Restauração Híbrida (DSP + IA)

**Feature Branch**: `006-audio-engine-masterizacao`

**Created**: 2026-08-13

**Status**: Draft

**Input**: User description: "Criar um novo módulo audio-engine no backend para masterização e
restauração de áudio, combinando DSP tradicional determinístico com restauração assistida por IA
(via SonicMaster como primeiro provider), seguindo o Princípio XII da constituição (v2.5.0) e a
auditoria técnica do SonicMaster já realizada nesta sessão."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Masterização automática de uma faixa (Priority: P1)

Uma pessoa tem uma música (mixada, mas não masterizada, ou com pequenos problemas de qualidade) e
quer um resultado pronto para ouvir/publicar sem entender nada de engenharia de áudio. Ela escolhe
o modo "Masterização automática", envia o arquivo, e recebe de volta uma versão com loudness
adequado, dinâmica controlada e problemas de qualidade comuns corrigidos — sem escolher modelo,
parâmetro técnico, ou saber que existe uma etapa de IA envolvida.

**Why this priority**: é o caso de uso central do módulo e o que a maioria das pessoas vai usar
primeiro — sem ele não há produto.

**Independent Test**: pode ser testado sozinho enviando uma faixa de música completa em modo
automático e verificando que a saída tem loudness dentro do alvo, sem clipping, e sem regressão
perceptível em relação ao original — sem depender de nenhum outro modo implementado.

**Acceptance Scenarios**:

1. **Given** uma faixa de música estéreo de qualidade razoável, **When** a pessoa aciona
   masterização automática sem ajustar nenhum parâmetro, **Then** ela recebe uma saída com loudness
   dentro do alvo configurado, sem clipping, e sem alteração perceptível de timbre/instrumentação
   em relação ao original.
2. **Given** uma faixa que não apresenta nenhum problema que justifique restauração por IA (ex.:
   já bem gravada, só precisa de loudness/EQ leve), **When** a masterização automática roda,
   **Then** o sistema resolve tudo via DSP determinístico e não invoca nenhum provedor de IA.
3. **Given** uma faixa com um problema real de qualidade (ex.: reverb excessivo), **When** a
   masterização automática roda, **Then** o sistema detecta o problema, aciona a restauração por
   IA antes das etapas de masterização, e o resultado final passa pela validação de qualidade antes
   de ser entregue.

---

### User Story 2 - Restaurar uma gravação de baixa qualidade sem masterizar (Priority: P2)

Uma pessoa tem uma gravação antiga, distorcida, ou de fonte ruim (ex.: uma fita, um MP3 muito
comprimido, uma gravação amadora com reverb excessivo) e quer só melhorar a qualidade técnica —
sem que o sistema mude o volume/dinâmica para um padrão de "música pronta para lançamento". Ela usa
o modo "Restaurar", que prioriza corrigir os defeitos sem aplicar a cadeia completa de
masterização, e pode opcionalmente rodar "Masterizar" depois, como um segundo passo separado.

**Why this priority**: é o segundo caso de uso mais valioso e o que mais se beneficia da parte de
IA do sistema — mas depende da mesma infraestrutura de análise/DSP da User Story 1, por isso vem
depois.

**Independent Test**: pode ser testado enviando uma gravação com defeito conhecido (ex. clipping
severo introduzido artificialmente) em modo "Restaurar" e confirmando que o defeito é reduzido sem
que o volume final seja normalizado para um alvo de loudness de masterização.

**Acceptance Scenarios**:

1. **Given** uma gravação com clipping severo, **When** a pessoa aciona "Restaurar", **Then** o
   sistema aplica a etapa de restauração adequada (DSP e/ou IA, conforme a severidade detectada) e
   entrega uma versão restaurada sem levar a faixa a um alvo de loudness de masterização.
2. **Given** uma faixa já restaurada, **When** a pessoa aciona "Masterizar" sobre o resultado
   restaurado, **Then** o sistema aplica a cadeia de masterização automática sobre a versão
   restaurada (fluxo "Restaurar + Masterizar" em duas etapas ou uma etapa combinada).
3. **Given** uma gravação que, na análise, não apresenta nenhum problema que justifique IA, **When**
   a pessoa aciona "Restaurar", **Then** o sistema aplica só a correção DSP correspondente,
   sem acionar o provedor de IA.

---

### User Story 3 - Processar uma música inteira sem ouvir junções (Priority: P3)

Uma pessoa envia uma música completa (não um trecho curto de teste) para restauração ou
masterização automática. O resultado final não deve ter nenhum ponto perceptível onde o
processamento "muda de trecho" — sem cliques, sem saltos de volume, sem mudança perceptível de
tom entre uma parte e outra da música.

**Why this priority**: é um requisito de qualidade transversal às User Stories 1 e 2 (ambas podem
envolver músicas completas), mas só se torna observável — e testável — depois que o pipeline básico
de restauração/masterização (US1/US2) já processa pelo menos um trecho corretamente.

**Independent Test**: pode ser testado enviando uma faixa mais longa que a janela de processamento
interna do sistema e conferindo, por inspeção de forma de onda e escuta, que não há descontinuidade
audível nos pontos de junção internos.

**Acceptance Scenarios**:

1. **Given** uma música com duração maior que a janela de processamento interna, **When** ela passa
   por restauração e/ou masterização automática, **Then** a saída final tem a mesma duração (dentro
   de uma tolerância desprezível) do original e não apresenta clique, salto de volume ou mudança de
   tonalidade perceptível nos pontos internos de junção.
2. **Given** uma música muito curta (menor que a janela mínima de processamento por IA), **When**
   restauração por IA é necessária, **Then** o sistema processa a faixa inteira como um único
   trecho, sem tentar dividir em pedaços menores que a janela mínima.

---

### User Story 4 - Continuar funcionando sem GPU ou sem o provedor de IA (Priority: P4)

Uma pessoa usa um computador sem GPU dedicada, ou o provedor de restauração por IA está
indisponível por qualquer motivo (dependência não instalada, falha ao carregar, sem VRAM
suficiente). Mesmo assim, ela consegue usar masterização automática e restauração — só que
usando exclusivamente DSP, com uma explicação honesta de que a etapa de IA não está disponível
no momento, nunca um erro genérico ou uma trava.

**Why this priority**: não é o caminho mais usado, mas é o que garante que o produto nunca fica
inutilizável — prioridade mais baixa porque só é observável quando as User Stories 1-3 já
funcionam no caminho feliz.

**Independent Test**: pode ser testado desligando/removendo o provedor de IA (ou simulando GPU
insuficiente) e confirmando que masterização automática e restauração ainda produzem um resultado
via DSP, com uma mensagem clara sobre a limitação.

**Acceptance Scenarios**:

1. **Given** o provedor de restauração por IA está indisponível, **When** a pessoa aciona
   masterização automática ou restauração numa faixa que teria se beneficiado de IA, **Then** o
   sistema entrega um resultado processado só por DSP, sem travar e sem erro genérico.
2. **Given** o hardware não tem GPU e a inferência em CPU é inviável para o provedor configurado,
   **When** restauração por IA seria necessária, **Then** o sistema informa essa limitação de forma
   clara ao invés de tentar carregar o modelo e travar ou demorar indefinidamente.

### Edge Cases

- **Provedor de IA falha durante o processamento** (crash do worker, erro de inferência): o job não
  trava o servidor principal; o usuário recebe o resultado processado só por DSP ou um erro claro,
  nunca um travamento silencioso.
- **VRAM insuficiente para o provedor de IA**: detectado antes de tentar carregar o modelo, com
  fallback para DSP e explicação honesta — não uma tentativa que falha a meio caminho.
- **Dependência do provedor de IA ausente ou com versão incompatível no ambiente**: o sistema
  detecta isso na inicialização/primeiro uso do provedor (não em produção silenciosamente) e cai
  para DSP, registrando a causa para diagnóstico.
- **Áudio de entrada mais curto que a menor janela de processamento por IA**: processado como um
  único trecho, sem chunking artificial.
- **Restauração por IA piora métricas objetivas em relação ao original** (regressão técnica real):
  o resultado da IA é rejeitado ou reduzido antes de virar saída — o usuário nunca recebe um
  resultado objetivamente pior que o original por causa da etapa de IA.
- **Faixa sem nenhum problema detectável**: nenhuma chamada ao provedor de IA é feita; só a cadeia
  de DSP roda (evita custo de GPU/tempo desnecessário).
- **Usuário aciona "Restaurar" numa faixa já em boas condições**: o sistema não força uma alteração
  perceptível só para "ter feito algo" — o resultado pode ser essencialmente igual ao original nos
  aspectos que já estavam corretos.
- **Áudio mono na entrada**: convertido para o formato interno de processamento sem perda adicional
  de qualidade evitável.
- **Falha ao obter/baixar um componente necessário do provedor de IA** (ex. checkpoint ou
  dependência de terceiro protegida por autenticação): tratada como indisponibilidade do provedor
  (fallback para DSP), com mensagem que distingue "não instalado" de "falhou ao processar".

## Requirements *(mandatory)*

### Functional Requirements

**Pipeline e decisão DSP vs. IA**

- **FR-001**: O sistema MUST analisar objetivamente o áudio de entrada (loudness, picos, clipping,
  cauda de reverberação, balanço espectral, correlação estéreo, indicadores de distorção) antes de
  decidir qual processamento aplicar.
- **FR-002**: O sistema MUST decidir, a partir dessa análise, se a restauração por IA é necessária
  — nunca enviar o áudio para o provedor de IA de forma incondicional ou por padrão.
- **FR-003**: Operações determinísticas (medição de loudness/LUFS/True Peak/RMS, detecção de pico,
  correção de DC offset, filtragem high-pass/notch, equalização paramétrica e dinâmica, compressão
  e compressão multibanda, limitação, ajuste de ganho, análise estéreo/fase, normalização,
  dithering) MUST sempre ser executadas por processamento determinístico, nunca delegadas ao
  provedor de IA.
- **FR-004**: Restauração por IA MUST ser considerada apenas para as classes de problema que o DSP
  tradicional não resolve adequadamente sozinho: reverberação excessiva, clipping severo,
  distorção complexa, desequilíbrio tonal complexo, e restauração geral de gravação de baixa
  qualidade.
- **FR-005**: Quando a restauração por IA é usada, a instrução enviada ao provedor MUST ser gerada
  a partir dos problemas objetivamente detectados na análise (FR-001) — nunca uma instrução
  aleatória, fixa por tipo de operação, ou fornecida sem relação com o áudio real.

**Qualidade e não-confiança automática na IA**

- **FR-006**: A saída de qualquer provedor de restauração por IA MUST sempre passar por uma etapa
  de correção DSP e por uma validação de qualidade antes de se tornar a saída entregue ao usuário
  — nunca é entregue diretamente como resultado final.
- **FR-007**: A validação de qualidade MUST comparar métricas objetivas do áudio antes e depois de
  cada etapa de restauração (loudness, pico, pico real, faixa dinâmica, correlação estéreo,
  balanço espectral, indicadores de clipping/distorção/fase).
- **FR-008**: Quando a validação de qualidade identifica uma regressão técnica grave introduzida
  pela restauração por IA, o sistema MUST rejeitar ou reduzir esse processamento antes de produzir
  a saída final — o usuário nunca recebe um resultado objetivamente pior que o original nesses
  aspectos por causa da etapa de IA.
- **FR-009**: Restauração por IA MUST preservar a intenção musical original — MUST NOT alterar
  desnecessariamente timbre, instrumentação, características vocais, posicionamento estéreo,
  transientes ou ambiência artística da gravação. Isso é um critério de aceitação verificável
  (por comparação objetiva antes/depois), não apenas uma diretriz.

**Modos de operação**

- **FR-010**: O sistema MUST oferecer um modo de masterização automática: análise → restauração
  (se necessária) → nova análise → correção/masterização (EQ, dinâmica, correção estéreo,
  saturação/realce quando aplicável, limitação, normalização de loudness ao alvo) → validação de
  qualidade → saída.
- **FR-011**: O sistema MUST oferecer um modo de restauração que prioriza corrigir defeitos técnicos
  sobre atingir um alvo de loudness de masterização — indicado para gravações antigas, distorcidas,
  reverberantes ou de fonte de baixa qualidade — sem aplicar a cadeia completa de masterização
  automaticamente.
- **FR-012**: O sistema MUST permitir que o usuário aplique masterização sobre um resultado já
  restaurado, como uma etapa opcional separada ("Restaurar + Masterizar").
- **FR-013**: O sistema MUST oferecer um parâmetro conceitual de intensidade da restauração por IA
  (com pelo menos os níveis nenhum/conservador/moderado/forte/máximo) que MUST alterar a estratégia
  de restauração usada — MUST NOT ser implementado como um simples multiplicador linear aplicado ao
  resultado do processamento.

**Música completa e reconstrução**

- **FR-014**: O sistema MUST suportar o processamento de músicas completas, não apenas trechos
  curtos, incluindo faixas mais longas que a janela interna de processamento de qualquer etapa do
  pipeline.
- **FR-015**: Quando um áudio precisa ser dividido internamente para processamento (por qualquer
  etapa, incluindo a de IA), a reconstrução final MUST NOT introduzir cliques, saltos de volume, ou
  mudanças de tonalidade perceptíveis nos pontos de junção.
- **FR-016**: Um áudio mais curto que a janela mínima de processamento por IA MUST ser processado
  como um único trecho, sem divisão artificial.

**Disponibilidade e isolamento**

- **FR-017**: O sistema MUST detectar automaticamente se há GPU compatível disponível e adaptar a
  execução da etapa de IA de acordo — reaproveitando a detecção de hardware já existente no
  projeto, sem duplicar essa lógica.
- **FR-018**: Quando o processamento por IA é inviável no hardware disponível, o sistema MUST
  informar essa limitação de forma clara à camada que solicitou o processamento, em vez de tentar
  carregar o modelo indefinidamente ou falhar de forma genérica.
- **FR-019**: O provedor de restauração por IA MUST carregar seus recursos (modelo/pesos) apenas no
  primeiro uso efetivo, nunca na inicialização da aplicação — e MUST permanecer disponível para
  reutilização em operações subsequentes na mesma sessão de uso, evitando recarregar a cada
  operação.
- **FR-020**: Quando o provedor de IA está indisponível por qualquer motivo (falha de carregamento,
  hardware insuficiente, dependência ausente), o sistema MUST cair automaticamente para
  processamento só por DSP — a indisponibilidade do provedor de IA MUST NOT impedir o uso das
  funcionalidades de restauração/masterização do produto.
- **FR-021**: O processamento pesado do provedor de IA MUST rodar isolado do processo principal da
  API (processo/worker separado) — uma falha durante essa inferência MUST NOT derrubar o processo
  principal nem outros jobs em andamento.
- **FR-022**: O restante da aplicação (orquestração de masterização, rotas, jobs) MUST acessar
  qualquer provedor de restauração por IA exclusivamente através de uma interface própria e
  isolada — nunca através de uma chamada direta à biblioteca/API de um modelo específico. Trocar ou
  adicionar um provedor de IA MUST NOT exigir mudanças na lógica de orquestração que o invoca.

**Dependências e distribuição**

- **FR-023**: As dependências de biblioteca/runtime específicas do provedor de IA de áudio MUST
  ser isoladas do conjunto de dependências principal do backend — MUST NOT ser instaladas
  automaticamente junto com a instalação padrão do backend.
- **FR-024**: As versões de dependências do provedor de IA de áudio MUST ser fixadas
  explicitamente (não "mais recente"/"latest" implícito), documentando as versões de linguagem,
  runtime de IA e bibliotecas de áudio necessárias.
- **FR-025**: Avisos e atribuições de licença exigidos pelas dependências do provedor de IA de
  áudio (incluindo do próprio modelo) MUST ser preservados e, quando aplicável, exibidos ao usuário
  final conforme já exigido para outros componentes do produto.
- **FR-026**: Qualquer dependência do provedor de IA de áudio cuja licença seja condicional (por
  exemplo, permissiva apenas abaixo de um limite de receita) MUST ser registrada explicitamente
  como um risco aceito e monitorado na documentação de licenças do projeto — nunca tratada
  silenciosamente como equivalente a uma licença permissiva incondicional.

### Key Entities *(include if feature involves data)*

- **Relatório de Análise de Áudio**: conjunto de métricas objetivas medidas sobre um arquivo de
  áudio em um dado momento (loudness, pico, pico real, faixa dinâmica, correlação estéreo, balanço
  espectral, indicadores de clipping/distorção/reverberação/fase). Produzido antes e depois de
  cada etapa relevante do pipeline, para permitir comparação.
- **Detecção de Problemas**: resultado da análise que indica, para uma lista conhecida de
  categorias de degradação (reverberação excessiva, clipping, distorção, desequilíbrio tonal,
  imagem estéreo deficiente, ruído, hum de rede elétrica, entre outras), se e o quão severamente
  cada uma está presente — usado para decidir se a restauração por IA é necessária e para gerar a
  instrução enviada a ela.
- **Job de Masterização/Restauração**: uma execução do pipeline sobre um arquivo de áudio, com um
  modo de operação (Masterização Automática, Restaurar, Restaurar + Masterizar), um nível de
  intensidade de IA, e resultados intermediários (original, restaurado, masterizado) quando
  aplicável, para permitir comparação A/B.
- **Veredito de Qualidade**: o resultado da validação que compara o áudio antes e depois de uma
  etapa de restauração por IA, indicando se o resultado foi aceito, reduzido ou rejeitado, e por
  qual motivo objetivo.
- **Provedor de Restauração por IA**: uma capacidade de restauração assistida por IA acessível
  através de uma interface comum, independente de qual modelo a implementa por trás — a primeira
  implementação usa o SonicMaster.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Uma pessoa consegue obter uma versão masterizada de uma faixa completa sem escolher
  nenhum parâmetro técnico (modo de masterização automática, ponta a ponta).
- **SC-002**: Faixas processadas em qualquer modo que envolva divisão interna em trechos não
  apresentam clique, salto de volume, ou mudança de tonalidade perceptível nos pontos de junção,
  em toda a amostra de faixas usada para validar esta funcionalidade.
- **SC-003**: Quando a restauração por IA introduziria uma regressão técnica objetiva mensurável, o
  resultado entregue ao usuário não reflete essa regressão, em toda a amostra usada para validar
  esta funcionalidade.
- **SC-004**: A indisponibilidade do provedor de restauração por IA (por qualquer motivo) nunca
  impede a pessoa de obter um resultado processado — o fluxo de masterização/restauração continua
  funcional via DSP em 100% desses casos.
- **SC-005**: Áudio é enviado para restauração por IA somente quando a análise objetiva indica
  necessidade — faixas sem problemas detectáveis são processadas inteiramente por DSP, sem custo
  adicional de tempo/hardware de uma etapa de IA desnecessária.
- **SC-006**: Em nenhum caso testado a restauração por IA altera perceptivelmente o timbre, a
  instrumentação, a voz, o posicionamento estéreo, os transientes ou a ambiência artística de uma
  gravação que não apresentava esses problemas antes do processamento.

## Assumptions

- **Escopo do provedor de IA nesta feature**: o SonicMaster é o único provedor de restauração por
  IA implementado por esta feature. A capacidade de adicionar outros provedores no futuro é uma
  propriedade arquitetural garantida pela interface isolada (FR-022, Princípio XII da
  constituição), não um requisito funcional concreto desta especificação.
- **Relação com a funcionalidade de áudio já existente**: o produto já distingue conteúdo de fala
  e de música e já oferece uma operação de melhoria de áudio. Esta feature estende essa capacidade
  existente para música, adicionando os novos modos de operação (Masterização Automática,
  Restaurar, Restaurar + Masterizar) e o parâmetro de intensidade de IA sobre a mesma base, em vez
  de criar um fluxo de produto paralelo e desconectado. A decisão de layout exato de código para
  essa extensão é responsabilidade do `/speckit.plan` seguinte, não desta especificação.
- **Alvo de loudness de masterização**: assume-se um alvo de loudness dentro dos padrões de
  distribuição musical comumente aceitos hoje, configurável, e não fixado nesta especificação como
  um valor único imutável — o valor exato é uma decisão de implementação/configuração, não uma
  decisão de produto que muda o comportamento observável descrito aqui.
- **Amostra de validação de SC-002/SC-003/SC-006**: assume-se que a validação usa um conjunto de
  faixas de teste representativo (variedade de gêneros, durações e defeitos conhecidos
  introduzidos deliberadamente), definido durante o planejamento/tarefas, não durante esta
  especificação.
- **Ambiente de execução do provedor de IA**: assume-se que o ambiente onde o produto roda pode ou
  não ter GPU compatível — ambos os casos são caminhos suportados e válidos, não uma limitação
  temporária.
- **Exibição de atribuição de licença na UI (FR-025)**: esta especificação cobre só o backend
  (`api/`) — os avisos/atribuições exigidos pela licença do SonicMaster são preservados no código
  vendorizado e registrados na documentação de licenças (obrigação já cumprida por esta feature),
  mas a exibição visível ao usuário final dentro do app desktop é trabalho de uma feature de
  `interface/` separada (a mesma visão técnica opcional já prevista pelo Princípio V da
  constituição), não desta especificação.
- **Autenticação para dependências de terceiro do provedor de IA**: quando o provedor de IA depende
  de um recurso de terceiro que exige autenticação/aceite de termos antes do primeiro uso (como
  observado na auditoria técnica do SonicMaster), esse passo é tratado como parte da configuração
  inicial do provedor pelo operador do produto, não como algo resolvido em tempo de execução sem
  intervenção alguma.
