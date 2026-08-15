# Feature Specification: Área de Edição de Vídeo com Player Customizado

**Feature Branch**: `007-video-editor-player`

**Created**: 2026-08-14

**Status**: Draft

**Input**: User description: "Área de edição de vídeo com player customizado no Astros Upscale. A
aplicação já tem telas de Imagem, Vídeo e Áudio; a de vídeo hoje só dispara upscale/otimização em
lote. Esta feature cria uma área de edição de vídeo equivalente à de imagem (MediaEditorShell com
preview + painel de ajustes) e substitui o elemento de vídeo nativo por um player customizado
próprio, com controles de transporte, timeline/scrubbing, exibição de tempo e frame, e preview das
edições aplicadas antes de exportar. Deve respeitar a constituição v2.6.0: allowlist server-side de
codec/container/preset e arquivo referenciado por ID (XIII), todo texto novo como chave i18n nos
locales (XIV), arquivo de origem nunca sobrescrito e preview descartável com cache invalidado por
conteúdo (XV), tetos declarados de duração/resolução/FPS/tamanho com recusa antes de processar
(VII), decomposição de componentes (X) e justificativa para todo módulo novo (XI). Reaproveita o
sistema de jobs existente (progresso, cancelamento, WebSocket)."

> **Nota de procedência.** Esta descrição foi reconstruída a partir do handoff da sessão anterior,
> não do texto original da solicitação, que não está preservado no repositório. Parte do texto
> original **é recuperável a partir da própria constituição v2.6.0**, que foi escrita a partir dele
> e o descreve em quatro pontos (ver *Escopo recuperado da constituição*, abaixo). O escopo das
> operações de edição foi fixado com base nessa evidência, não por suposição. As duas decisões que
> permanecem sendo escolha minha, e não evidência, estão registradas em *Decisões tomadas no lugar
> de perguntas*, ao final.

### Escopo recuperado da constituição

A emenda v2.6.0 foi redigida a partir da solicitação original e a descreve em quatro lugares. Estes
trechos são a melhor evidência disponível do que foi pedido:

| Origem | Texto | O que fixa |
|--------|-------|------------|
| `constitution.md:27` | "the video adjustments/effects/transform/trim/audio/export subsystem" | As seis famílias de operação: **ajustes, efeitos, transformação, corte temporal, áudio e exportação** |
| `constitution.md:28` | "the FFmpeg-backed processing, job, thumbnail and preview services" | O backend cobre processamento, jobs, **miniaturas** e previews |
| `constitution.md:29` | "the custom video player component tree" | O player é uma **árvore de componentes**, não um componente único |
| `constitution.md:887` | "a frontend surface explicitly specified as ~11 components and 6 composables" | A ordem de grandeza da superfície de interface |
| `constitution.md:595` | cita `video_effects.py` e `video_thumbnails.py` como nomes que se justificariam | Sugere a divisão do backend por responsabilidade |

Duas correções que isso impõe sobre a primeira redação desta spec: **corte temporal está dentro do
escopo** (e muda o que a linha de tempo do player precisa mostrar), e **a trilha de áudio do vídeo
está dentro do escopo** (havia sido listada como fora).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Ver o vídeo com controle real antes de decidir qualquer coisa (Priority: P1)

Uma pessoa importa um vídeo e quer olhar para ele antes de escolher o que fazer: avançar até o
trecho que a incomoda, parar num quadro específico, voltar alguns quadros, ver em que segundo e em
que quadro está. Hoje a tela de Vídeo mostra o arquivo apenas como miniatura na tira lateral e
qualquer inspeção depende de abrir o arquivo em outro programa. Com esta história ela abre o vídeo
na área de edição e o percorre inteiramente dentro do Astros.

**Why this priority**: é a base de tudo o que vem depois — não existe "preview das edições" sem um
lugar onde o vídeo é exibido e navegado. Entregue sozinha, já substitui o ir-e-voltar para um player
externo, que é uma dor real independente de qualquer edição.

**Independent Test**: pode ser testada sozinha importando um vídeo, reproduzindo, pausando,
arrastando a barra de progresso até uma posição arbitrária, avançando e voltando quadro a quadro, e
conferindo que o tempo e o número do quadro exibidos correspondem à posição real do vídeo — sem que
nenhum ajuste ou exportação exista ainda.

**Acceptance Scenarios**:

1. **Given** um vídeo importado na área de edição, **When** a pessoa aciona reproduzir, **Then** o
   vídeo reproduz e o indicador de tempo avança acompanhando a imagem.
2. **Given** um vídeo em reprodução, **When** a pessoa aciona pausar, **Then** a reprodução para no
   quadro exibido e o tempo e o número do quadro correspondentes permanecem visíveis.
3. **Given** um vídeo pausado, **When** a pessoa arrasta o cursor da linha de tempo até uma posição,
   **Then** a imagem exibida passa a ser a daquela posição e os indicadores de tempo e quadro
   refletem a nova posição.
4. **Given** um vídeo pausado, **When** a pessoa avança um quadro e depois volta um quadro,
   **Then** a imagem exibida é a mesma do ponto de partida.
5. **Given** um vídeo cuja duração é conhecida, **When** a pessoa observa a linha de tempo,
   **Then** a posição atual e a duração total estão ambas visíveis e legíveis.
6. **Given** um vídeo com áudio, **When** a pessoa ajusta o volume ou silencia, **Then** o áudio
   responde imediatamente e o estado escolhido persiste ao trocar de posição no vídeo.

---

### User Story 2 - Ajustar o vídeo e ver o efeito antes de gastar tempo processando (Priority: P1)

A pessoa quer alterar como o vídeo se parece — os mesmos tipos de ajuste que a tela de Imagem já
oferece — e ver o resultado aplicado sobre o próprio vídeo antes de aceitar o custo de processar o
arquivo inteiro. Ela mexe num controle, o preview reflete a mudança, e ela decide se vale exportar.

**Why this priority**: é a razão de ser da feature. Sem preview, qualquer ajuste vira tentativa e
erro pagando minutos de processamento por tentativa — exatamente o custo que a constituição
(Princípio III, Performance First) trata como a experiência mais direta do produto.

**Independent Test**: pode ser testada sozinha aplicando um ajuste visível e conferindo que o
preview muda de acordo, que voltar o controle ao valor neutro restaura a imagem original, e que o
arquivo de origem permanece intacto no disco — sem que a exportação exista ainda.

**Acceptance Scenarios**:

1. **Given** um vídeo aberto na área de edição, **When** a pessoa altera um ajuste, **Then** o
   preview passa a mostrar o vídeo com aquele ajuste aplicado.
2. **Given** um ajuste aplicado, **When** a pessoa devolve o controle ao valor neutro, **Then** o
   preview volta a ser indistinguível do vídeo original.
3. **Given** um ou mais ajustes aplicados, **When** a pessoa consulta o arquivo de origem no disco,
   **Then** ele está inalterado, byte a byte.
4. **Given** ajustes aplicados a um vídeo, **When** a pessoa seleciona outro vídeo da tira e volta
   ao primeiro, **Then** os ajustes do primeiro continuam como ela os deixou.
5. **Given** um ajuste que o sistema não consegue previsualizar em tempo real, **When** a pessoa o
   altera, **Then** o sistema informa que aquele ajuste só será visível no resultado exportado, em
   vez de exibir um preview silenciosamente errado.
6. **Given** um vídeo com ajustes, **When** a pessoa aciona descartar ajustes, **Then** todos os
   controles voltam ao neutro e o preview volta ao original.
7. **Given** um vídeo aberto, **When** a pessoa define um ponto de entrada e um ponto de saída,
   **Then** a linha de tempo distingue o trecho selecionado e a reprodução do preview respeita esses
   limites.
8. **Given** um vídeo com trilha de áudio, **When** a pessoa remove a trilha, **Then** o preview
   passa a reproduzir sem áudio e a exportação produz arquivo sem trilha de áudio.
9. **Given** uma transformação geométrica aplicada (recorte ou rotação), **When** a pessoa observa o
   preview, **Then** o enquadramento exibido corresponde ao que será exportado, e as dimensões de
   saída resultantes ficam visíveis.

---

### User Story 3 - Exportar o resultado sem destruir o original (Priority: P1)

Decidido o ajuste, a pessoa exporta. Ela escolhe formato e nível de qualidade em termos que
entende, acompanha o progresso, pode cancelar, e ao final tem um arquivo novo — com o original ainda
onde estava.

**Why this priority**: sem exportação a feature não produz nada que a pessoa possa usar fora do
programa. É P1 junto com as duas anteriores porque as três formam o fluxo mínimo completo:
ver → ajustar → obter o arquivo.

**Independent Test**: pode ser testada sozinha exportando um vídeo com ajustes e verificando que o
arquivo novo existe, que reflete os ajustes, que o original não foi tocado e que um cancelamento no
meio não deixa arquivo parcial para trás.

**Acceptance Scenarios**:

1. **Given** um vídeo com ajustes, **When** a pessoa exporta, **Then** um arquivo novo é criado e o
   arquivo de origem continua existindo inalterado.
2. **Given** uma exportação em andamento, **When** a pessoa acompanha a tela, **Then** ela vê
   progresso que avança e uma estimativa do que está acontecendo.
3. **Given** uma exportação em andamento, **When** a pessoa cancela, **Then** o processamento para,
   nenhum arquivo parcial permanece no destino e nenhum arquivo temporário fica para trás.
4. **Given** um destino onde já existe arquivo de mesmo nome, **When** a exportação termina,
   **Then** o resultado é gravado sob nome distinto, sem sobrescrever o arquivo existente.
5. **Given** uma exportação que falha no meio, **When** a pessoa lê a mensagem, **Then** ela indica
   o que impediu a conclusão, e nenhum arquivo parcial ou temporário permanece.

---

### User Story 4 - Ser avisada antes, não depois, quando o vídeo é grande demais (Priority: P2)

A pessoa importa um vídeo longo, em resolução alta, ou pesado demais para a máquina em que está. O
sistema recusa a operação imediatamente e diz qual limite foi atingido — em vez de começar, ocupar a
máquina por minutos e falhar.

**Why this priority**: não é o fluxo principal, mas é o que separa uma recusa honesta de um
travamento. É P2 porque as histórias P1 são demonstráveis sem ela; é obrigatória antes do release
porque o Princípio VII a exige explicitamente.

**Independent Test**: pode ser testada sozinha submetendo um vídeo que excede um limite declarado e
verificando que a recusa acontece antes de qualquer processamento começar e nomeia o fator
limitante.

**Acceptance Scenarios**:

1. **Given** um vídeo que excede um limite declarado (duração, resolução, taxa de quadros, número
   de quadros ou tamanho), **When** a pessoa tenta a operação, **Then** o sistema recusa antes de
   iniciar o processamento e nomeia qual limite foi excedido.
2. **Given** uma máquina sem recurso suficiente para a operação pedida, **When** a pessoa tenta,
   **Then** a recusa nomeia o recurso limitante em vez de apresentar erro genérico.
3. **Given** um vídeo dentro de todos os limites, **When** a pessoa tenta a operação, **Then**
   nenhuma recusa ocorre.
4. **Given** um formato ou codec permitido pela lista do sistema mas ausente no ambiente,
   **When** a pessoa tenta exportar nele, **Then** o sistema informa a indisponibilidade antes de
   iniciar, em vez de falhar no meio do processamento.

---

### User Story 5 - Trabalhar em outro idioma (Priority: P3)

Uma pessoa que usa o produto em qualquer um dos idiomas suportados encontra a área de edição de
vídeo inteiramente no seu idioma — controles, rótulos, estados e mensagens de erro.

**Why this priority**: não bloqueia o uso em português, mas o Princípio XIV a torna obrigatória por
construção: cada texto nasce como chave de tradução. É P3 porque é verificável separadamente, não
porque possa ser adiada para depois da implementação dos textos.

**Independent Test**: pode ser testada sozinha trocando o idioma da aplicação e percorrendo a área
de edição de vídeo à procura de texto não traduzido ou de chave exibida crua.

**Acceptance Scenarios**:

1. **Given** a aplicação em qualquer idioma suportado, **When** a pessoa abre a área de edição de
   vídeo, **Then** nenhum texto aparece em idioma diferente do escolhido e nenhuma chave de
   tradução aparece crua na tela.
2. **Given** uma operação que falha, **When** a mensagem é exibida no idioma escolhido, **Then** ela
   está traduzida como o resto da tela.

---

### Edge Cases

- **Vídeo sem trilha de áudio** — os controles de volume não devem prometer algo que não existe.
- **Vídeo com taxa de quadros variável** — a correspondência entre tempo e número do quadro deixa de
  ser exata; o sistema não deve exibir um número de quadro que não corresponde à imagem.
- **Vídeo cujo container é legível mas cujo codec não é reproduzível no preview** — a pessoa precisa
  saber que não é possível previsualizar antes de tentar ajustar às cegas.
- **Vídeo removido, renomeado ou substituído no disco depois de importado** — miniaturas e previews
  derivados dele não podem continuar sendo exibidos como se fossem o arquivo atual.
- **Arquivo cujo conteúdo mudou mas cujo caminho permanece o mesmo** — qualquer artefato derivado em
  cache precisa ser reconhecido como obsoleto.
- **Duração declarada no container divergente da duração real** — a linha de tempo não pode
  prometer uma posição que o vídeo não alcança.
- **Vídeo de duração muito curta (poucos quadros)** — navegação quadro a quadro e arrasto na linha
  de tempo precisam continuar utilizáveis.
- **Vídeo muito longo** — a linha de tempo precisa continuar permitindo posicionamento preciso.
- **A pessoa fecha a área de edição, ou fecha o aplicativo, com uma exportação em andamento** —
  resolvido pelo FR-023a: fechar a tela não interrompe; encerrar a aplicação cancela e limpa.
- **Vários vídeos importados de uma vez** — trocar de vídeo não pode misturar os ajustes de um com
  os de outro, nem interromper uma exportação já em curso.
- **Espaço em disco insuficiente para o resultado ou para os artefatos intermediários.**
- **Nome de arquivo com caracteres que o sistema de arquivos de destino não aceita.**

## Requirements *(mandatory)*

### Functional Requirements

#### Área de edição

- **FR-001**: O sistema MUST oferecer uma área de edição de vídeo que apresente, para o vídeo
  selecionado, um preview grande, a lista dos vídeos importados e um painel de ajustes — a mesma
  organização que a área de edição de imagem já estabeleceu.
- **FR-002**: A pessoa MUST conseguir importar um ou mais vídeos para a área de edição, alternar
  entre eles, e remover um deles da sessão sem afetar os demais.
- **FR-003**: O sistema MUST manter os ajustes de cada vídeo separados por vídeo, preservados ao
  alternar a seleção.
- **FR-004**: O sistema MUST permitir descartar **todas as edições** de um vídeo — as cinco
  famílias de FR-013a a FR-013e, não apenas os ajustes de imagem — devolvendo todos os controles ao
  estado neutro e removendo o corte temporal.
- **FR-005**: O sistema MUST indicar, para cada vídeo da lista, seu estado atual (importado, com
  ajustes pendentes, exportando, concluído, com erro).

#### Player

- **FR-006**: O sistema MUST oferecer um player próprio para o preview, com controles de transporte
  visíveis: reproduzir, pausar, e navegação quadro a quadro para frente e para trás.
- **FR-007**: O player MUST exibir uma linha de tempo que mostra a posição atual em relação à
  duração total e permite reposicionar a reprodução arrastando ou clicando.
- **FR-007a**: A linha de tempo MUST exibir miniaturas do vídeo ao longo de sua extensão, para que a
  pessoa localize um trecho visualmente em vez de por tentativa. As miniaturas são artefatos
  derivados e estão sujeitas ao FR-017 (invalidação por conteúdo).
- **FR-007b**: Quando houver corte temporal definido (FR-013d), a linha de tempo MUST exibir os
  pontos de entrada e de saída, MUST permitir movê-los, e MUST distinguir visualmente o trecho que
  será exportado do que ficará de fora.
- **FR-008**: O player MUST exibir a posição atual em tempo e o número do quadro correspondente.
- **FR-009**: O player MUST oferecer controle de volume e silenciamento, e MUST indicar quando o
  vídeo não possui trilha de áudio em vez de oferecer um controle sem efeito.
- **FR-010**: O player MUST permanecer utilizável pelo teclado para as ações de transporte, e cada
  controle MUST ter rótulo acessível.
- **FR-011**: Quando o vídeo não puder ser previsualizado no ambiente atual, o player MUST informá-lo
  explicitamente em vez de apresentar uma área vazia sem explicação.
- **FR-012**: Quando a correspondência entre tempo e quadro não for confiável (taxa de quadros
  variável, duração divergente do declarado), o sistema MUST NOT exibir um número de quadro como se
  fosse exato.

#### Ajustes e preview

- **FR-013**: O sistema MUST oferecer seis famílias de operação sobre o vídeo, todas com efeito
  visível ou audível no preview antes de qualquer exportação:
  - **FR-013a — Ajustes de imagem**: alterações de aparência sobre o quadro inteiro (brilho,
    contraste, saturação, temperatura, nitidez e equivalentes), cada uma com um valor neutro ao qual
    pode ser devolvida. *"Ajustes de imagem" nomeia esta família; **"edições"** nomeia o conjunto das
    cinco. Os dois termos não são intercambiáveis nesta spec.*
  - **FR-013b — Efeitos**: tratamentos nomeados aplicáveis ao vídeo (por exemplo redução de ruído,
    desfoque, granulação), que a pessoa liga, desliga e regula em intensidade.
  - **FR-013c — Transformação**: operações geométricas — recorte, rotação, espelhamento e
    redimensionamento — cujo resultado altera as dimensões ou o enquadramento da saída.
  - **FR-013d — Corte temporal**: definição de um ponto de entrada e um ponto de saída que
    delimitam o trecho a exportar, sem alterar o arquivo de origem.
  - **FR-013e — Áudio**: controle sobre a trilha de áudio do vídeo — no mínimo volume, silenciamento
    e remoção da trilha. Esta feature NÃO inclui masterização nem restauração de áudio, que são
    escopo da feature 006.
  - **FR-013f — Exportação**: materialização das cinco anteriores em um arquivo novo (FR-018 a
    FR-023).
- **FR-014**: O preview MUST refletir os ajustes aplicados dentro de um tempo que permita ajuste
  interativo, e MUST indicar quando está recalculando.
- **FR-015**: Quando um ajuste não puder ser refletido no preview, o sistema MUST informar que ele
  só aparecerá no resultado exportado — nunca exibir um preview que difere silenciosamente do
  resultado.
- **FR-016**: Artefatos de preview MUST ser gravados em armazenamento que a aplicação controla,
  MUST NOT ser apresentados como resultado da operação, e MUST NOT substituir o arquivo de origem
  nem qualquer resultado exportado anteriormente.
- **FR-017**: Artefatos derivados de um arquivo de origem (previews, miniaturas, quadros em cache)
  MUST deixar de ser usados quando o conteúdo daquele arquivo mudar, sendo a identificação da
  mudança baseada no conteúdo do arquivo e não apenas no seu caminho.

#### Exportação

- **FR-018**: A pessoa MUST conseguir exportar o vídeo ajustado, escolhendo formato de saída e nível
  de qualidade descritos em termos de intenção, sem precisar conhecer nomes de codec, preset de
  encoder ou parâmetro interno.
- **FR-019**: A exportação MUST produzir um arquivo novo. O arquivo de origem MUST permanecer
  existente e byte-idêntico ao final da operação.
- **FR-020**: Quando o resultado colidir com um arquivo existente no destino, o sistema MUST gravar
  sob nome distinto por padrão. Sobrescrever MUST exigir instrução explícita da pessoa para aquela
  operação.
- **FR-021**: A exportação MUST reaproveitar o sistema de jobs existente, expondo progresso e
  permitindo cancelamento pelos mesmos meios que as operações de vídeo já existentes.
- **FR-022**: Arquivos temporários criados durante a exportação MUST ser removidos em todos os
  desfechos: sucesso, falha e cancelamento.
- **FR-023**: Um cancelamento MUST NOT deixar arquivo de saída parcial no destino.
- **FR-023a**: Quando a área de edição é fechada com uma exportação em andamento, a exportação MUST
  continuar — fechar uma tela não é cancelar um trabalho, e o histórico é onde a pessoa a
  reencontra. Quando a **aplicação** é encerrada com uma exportação em andamento, a exportação MUST
  ser cancelada e MUST receber o mesmo tratamento de qualquer cancelamento: nenhum arquivo parcial
  no destino, nenhum temporário para trás (FR-022, FR-023). Um processo que sobrevive ao
  encerramento da aplicação, ou um arquivo parcial deixado no disco por ela, são defeitos.

#### Limites e validação

- **FR-024**: Cada operação de vídeo introduzida por esta feature MUST declarar seus limites
  máximos explícitos de duração, resolução, taxa de quadros, número de quadros e tamanho de arquivo.
- **FR-025**: O sistema MUST recusar trabalho que exceda esses limites antes de iniciar o
  processamento, nomeando o fator limitante. Uma recusa que chegue depois de minutos de
  processamento, ou uma falha por exaustão de memória, MUST ser tratada como defeito.
- **FR-026**: Todo valor fornecido pelo cliente que selecione comportamento — container, codec,
  preset de encoder, formato de pixel, nome de filtro, proporção — MUST ser validado contra uma
  lista explícita de valores permitidos no backend. Valores numéricos MUST ser validados por faixa.
  A validação feita na interface MUST NOT ser a única.
- **FR-027**: Antes de iniciar trabalho que dependa de um codec, encoder ou container, o sistema
  MUST confirmar que o ambiente de execução realmente o oferece, e MUST falhar com razão clara caso
  não ofereça.
- **FR-028**: Os arquivos de mídia manipulados por esta feature MUST ser referenciados por um
  identificador emitido pela aplicação. Um nome de arquivo vindo do cliente MUST ser tratado como
  texto de exibição e higienizado antes de participar da construção de qualquer caminho.
- **FR-028a**: A aplicação MUST registrar um arquivo escolhido pela pessoa e receber de volta um
  identificador. Todas as operações desta feature MUST usar apenas esse identificador. O fluxo em
  lote existente permanece como está e não é alterado por esta feature.

#### Idioma

- **FR-029**: Todo texto legível por uma pessoa introduzido por esta feature MUST existir como
  chave de tradução, em todos os idiomas que a aplicação suporta. Uma chave presente em apenas
  parte dos idiomas MUST ser tratada como defeito.
- **FR-030**: Mensagens de erro e de recusa apresentadas por esta feature MUST seguir a mesma regra
  do FR-029.

#### Integração com o resto da aplicação

- **FR-031**: As operações de vídeo desta feature MUST aparecer no histórico da aplicação com o
  mesmo nível de informação que as operações de vídeo já existentes.
- **FR-032**: A área de edição de vídeo MUST coexistir com o fluxo de upscale/otimização em lote já
  existente na tela de Vídeo, como um modo adicional. Nenhuma capacidade existente MUST ser removida
  por esta feature, e MUST ficar claro para a pessoa qual dos dois modos faz o quê.

### Key Entities

- **Vídeo importado**: um arquivo de vídeo trazido para a sessão de edição. Carrega identificador
  próprio, nome para exibição, e as características lidas do arquivo (duração, dimensões, taxa de
  quadros, presença de áudio). Referenciado por identificador, nunca por caminho vindo do cliente.
- **Conjunto de edições**: o estado completo das seis famílias de operação (FR-013) para um vídeo
  importado — ajustes, efeitos, transformação, corte temporal e áudio. Existe apenas na sessão até
  que uma exportação o materialize; tem um estado neutro ao qual pode ser devolvido.
- **Trecho selecionado**: o par ponto-de-entrada/ponto-de-saída do corte temporal. Determina a
  duração da saída e, com ela, o custo da exportação e a avaliação contra os limites declarados.
- **Preview**: representação descartável do vídeo com as edições aplicadas, derivada do vídeo
  importado e do conjunto de edições. Nunca é o resultado da operação; é invalidada quando o
  conteúdo da origem muda.
- **Miniaturas da linha de tempo**: artefatos derivados do vídeo importado, usados para localizar
  trechos visualmente. Descartáveis e invalidados por conteúdo, como o preview.
- **Exportação**: a operação que materializa um conjunto de ajustes em um arquivo novo. Tem
  progresso observável, pode ser cancelada, e nunca escreve sobre a origem.
- **Limites de operação**: os tetos declarados (duração, resolução, taxa de quadros, número de
  quadros, tamanho) contra os quais um vídeo importado é avaliado antes de qualquer processamento.
- **Vocabulário permitido**: o conjunto fechado de containers, codecs e presets que o backend
  aceita, separado da verificação de quais deles o ambiente de execução realmente oferece.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A pessoa consegue importar um vídeo, posicioná-lo em um ponto arbitrário e parar em um
  quadro específico sem sair da aplicação, em menos de 30 segundos a partir da tela inicial.
- **SC-002**: Após alterar um ajuste, o preview reflete a mudança em até 2 segundos em pelo menos
  95% das alterações, para vídeos dentro dos limites declarados.
- **SC-003**: Em 100% das exportações concluídas, canceladas ou falhas, o arquivo de origem
  permanece existente e byte-idêntico ao que era antes da operação.
- **SC-004**: Em 100% das exportações canceladas ou falhas, nenhum arquivo parcial permanece no
  destino e nenhum arquivo temporário permanece no armazenamento da aplicação.
- **SC-005**: 100% das recusas por limite excedido ocorrem antes do início do processamento e
  nomeiam o fator limitante; nenhuma operação desta feita termina em falha por exaustão de memória.
- **SC-006**: 100% dos textos legíveis introduzidos por esta feature estão presentes em todos os
  idiomas suportados — verificável por comparação automática entre os arquivos de idioma.
- **SC-007**: Nenhum valor de container, codec ou preset fora da lista permitida é aceito quando a
  interface é contornada e o backend é chamado diretamente.
- **SC-008**: Uma pessoa que nunca usou a área consegue completar o fluxo ver → ajustar → exportar
  na primeira tentativa, sem consultar documentação.
- **SC-009**: Nenhum nome de modelo, checkpoint, codec interno ou parâmetro de inferência aparece
  nas superfícies padrão desta feature.

## Assumptions

Estas decisões foram tomadas na ausência do texto original da solicitação. Cada uma pode ser
revertida sem reescrever a spec inteira, mas todas afetam o plano.

- **Procedência da descrição.** A descrição de entrada foi reconstruída a partir do handoff da
  sessão anterior; o escopo das operações foi recuperado da constituição v2.6.0 (ver *Escopo
  recuperado da constituição*). Se o texto original da solicitação for recuperado, esta spec deve
  ser conferida contra ele antes do `/speckit.plan`.
- **A área de edição é um modo adicional, não uma substituição** (decisão sobre a antiga Q3). O
  fluxo de upscale/otimização em lote da tela de Vídeo continua existindo. Escolhido por ser a
  opção que não remove capacidade que a pessoa já tem; se a intenção original era um só lugar para
  processar vídeo, isto precisa ser revertido antes do `/speckit.plan`.
- **Arquivos passam a ser referenciados por identificador apenas nas operações desta feature**
  (decisão sobre a antiga Q2). A rota em lote existente, que recebe caminho local, não é alterada.
  Escolhido por cumprir o Princípio XIII na superfície nova sem arrastar o fluxo em lote para o
  escopo. O custo aceito é conviverem dois modelos de referência até que o fluxo antigo migre.
- **O layout compartilhado é reaproveitado.** A área de edição usa o mesmo arranjo de preview +
  tira de arquivos + painel que a área de imagem já estabeleceu, em vez de um layout próprio.
- **O sistema de jobs é reaproveitado, não duplicado.** Progresso, cancelamento e notificação de
  progresso vêm do mecanismo já existente.
- **O player é próprio, e não um player de terceiros.** Isso decorre da solicitação; a alternativa
  (biblioteca externa) traria a verificação de licença comercial do Princípio IV para o caminho
  crítico da feature.
- **A idade das edições é a sessão.** As edições vivem enquanto a pessoa está na área de edição; não
  há requisito de retomá-las depois de fechar a aplicação nesta feature.
- **O áudio desta feature é manipulação de trilha, não tratamento de sinal.** Volume, silenciamento
  e remoção estão dentro do escopo (FR-013e); masterização e restauração são a feature 006.
- **Idiomas suportados: 11.** O repositório contém 11 arquivos de idioma
  (`interface/src/renderer/src/i18n/locales/`), e não 12 como o handoff e a constituição v2.6.0
  afirmam. O FR-029 fala em "todos os idiomas que a aplicação suporta" justamente para não fixar um
  número errado. **Vale corrigir a constituição em um PATCH separado.**

## Dependencies

- **Layout de edição compartilhado** — `interface/src/renderer/src/components/MediaEditorShell.vue`,
  hoje usado pela área de imagem; deliberadamente sem conhecimento de jobs ou processamento.
- **Sistema de jobs** — `api/astros_upscale_api/app/jobs.py` e as rotas de job/progresso/cancelamento
  em `routes.py`, incluindo o canal de progresso por WebSocket.
- **Portão de capacidade** — `_capacity_check_for` em `api/astros_upscale_api/app/routes.py`, que o
  Princípio VII nomeia como a forma estabelecida a ser estendida, não duplicada.
- **Invocação estrutural de FFmpeg** — `run_ffmpeg` em `api/astros_upscale/media.py`, construído via
  `ffmpeg-python`, que o Princípio XIII nomeia como a forma obrigatória.
- **Cadeia de filtros de vídeo existente** — `optimize_video` em `api/astros_upscale/optimize.py`,
  ponto natural de extensão da cadeia de filtros.
- **Precedente de pipeline de vídeo parametrizado** — `VideoUpscaler.process()` em
  `api/astros_upscale/processing.py`, que já aceita dimensão-alvo customizada.
- **Precedente de endpoint de preview** — a rota de preview já existente em `routes.py`.
- **Opções compartilhadas de processamento** — `interface/src/renderer/src/constants/processing.ts`.

## Constraints

- **Codificadores GPL não podem ser distribuídos.** A seção de Licenciamento da constituição proíbe
  empacotar `libx264`/`libx265`; saída H.264/H.265 precisa vir de codificador de hardware ou
  comercialmente licenciado. `optimize_video` hoje tem `codec='libx264'` como valor padrão — isso é
  aceitável enquanto depende do FFmpeg do sistema, mas a lista de codecs permitidos desta feature
  não pode assumir que esse padrão continua válido no produto empacotado. **Ponto a resolver no
  `/speckit.plan`.**
- **Modelos permanecem internos.** Nenhuma superfície padrão desta feature expõe nome de modelo,
  codec interno ou parâmetro de inferência (Princípio V).
- **Decomposição de componentes.** Controles independentes desta feature nascem como componentes ou
  composables próprios quando reutilizados ou quando o arquivo deixa de se ler como uma
  responsabilidade (Princípio X). `ImageEditorView.vue` está explicitamente isento e MUST NOT ser
  dividido como refatoração isolada.
- **Módulos novos precisam de justificativa.** Todo módulo novo no backend precisa satisfazer,
  declaradamente no plano, uma de três condições: ser testado diretamente, ser importado de fora do
  seu domínio, ou isolar uma dependência externa. Nomes de categoria técnica
  (`validation.py`, `types.py`, `models.py`) nunca se justificam por si (Princípio XI).

## Out of Scope

- Masterização e restauração da trilha de áudio — é a feature 006. Esta feature trata a trilha
  apenas como objeto de manipulação (volume, silenciamento, remoção).
- Edição multipista, sobreposição de clipes ou transições entre vídeos.
- Legendas: criação, edição ou queima na imagem.
- Persistência das edições entre execuções da aplicação.
- Remoção ou reescrita do fluxo de upscale/otimização em lote da tela de Vídeo.
- Migração do fluxo em lote existente para referência de arquivo por identificador.
- Correção da fila da tela inicial não listar vídeo e áudio — pendência conhecida
  (`queueState.jobs` só é alimentado por `addFiles()` em `store/jobs.ts`, que rejeita não-imagens),
  registrada no handoff como fora do escopo deste fluxo.

## Decisões tomadas no lugar de perguntas

A primeira redação desta spec levantou três perguntas. Todas foram resolvidas sem consulta, por
instrução de seguir adiante. Cada uma está registrada aqui com sua base, porque reverter qualquer
delas muda o tamanho da feature.

| # | Pergunta | Decisão | Base |
|---|----------|---------|------|
| Q1 | Quais operações de edição entram no escopo? | As seis famílias do FR-013: ajustes, efeitos, transformação, corte temporal, áudio, exportação | **Evidência**, não escolha — recuperada de `constitution.md:27`, que descreve o subsistema a partir do texto original |
| Q2 | Como referenciar arquivos por identificador numa aplicação desktop? | Registro do arquivo devolve identificador; só as operações desta feature o usam; o fluxo em lote não muda (FR-028a) | Escolha. Cumpre o Princípio XIII na superfície nova sem arrastar o fluxo em lote para o escopo |
| Q3 | A área de edição substitui a tela de Vídeo? | Convivem: modo adicional, nada existente é removido (FR-032) | Escolha. Reduzir capacidade existente é decisão do dono do produto, não minha |

Q1 deixou de ser uma escolha assim que a constituição foi lida como fonte: ela foi redigida a
partir da solicitação original e nomeia o subsistema termo a termo. Q2 e Q3 continuam sendo
escolhas minhas, e são os dois pontos a conferir primeiro caso o texto original apareça.
