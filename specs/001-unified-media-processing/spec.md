# Feature Specification: Unified Media Processing

**Feature Branch**: `001-unified-media-processing`

**Created**: 2026-08-08

**Status**: Draft

**Input**: User description: "Evoluir o Astros para plataforma unificada de imagem, vídeo e áudio com três operações (Melhorar, Comprimir, Converter) e três perfis internos (Rápido, Equilibrado, Qualidade), com modelos totalmente ocultos do usuário."

**Factual basis**: `docs/audit/phase0-inventory.md` · `docs/models/MODEL_LICENSES.md`
**Governed by**: `.specify/memory/constitution.md` v2.0.0

---

## Context

Astros hoje é um aplicativo de desktop que faz uma coisa: aumentar a resolução de imagens com IA.
Para usá-lo, a pessoa precisa escolher entre 19 modelos com nomes como `RealESRGAN_x4plus` e
`4x_NMKD-Superscale-SP_178000_G`, decidir um device (`auto`/`cpu`/`cuda`), e ajustar parâmetros
técnicos. As abas de Vídeo, Áudio e Otimizar existem na navegação, mas estão vazias.

Esta especificação define a transformação para uma plataforma de mídia unificada, onde a pessoa
escolhe **o que quer fazer**, não **como o sistema deve fazer**.

---

## Clarifications

### Session 2026-08-08

- Q: A infraestrutura de licenciamento e proteção do processamento deve ser ativada nesta entrega,
  mantida desativada, ou removida? → A: **Ativar nesta entrega.** O produto passa a exigir licença
  válida para processar, e todos os fluxos de falha associados entram no escopo desta
  especificação.

- Q: Os modelos devem vir no instalador ou ser baixados sob demanda? → A: **Baixados e armazenados
  no computador da pessoa**, não embarcados no instalador. Existe uma tela de atualização desses
  componentes. O processamento acontece integralmente na máquina da pessoa. A lógica de execução
  (os scripts que definem como cada processo é realizado) é **entregue ao processo no momento da
  execução e removida em seguida**, nunca persistida em disco.

- Q: Quais são os limites de tamanho e duração que o produto se compromete a processar? → A:
  **Derivados do hardware.** Não há limite fixo declarado. O sistema calcula o máximo viável a
  partir dos recursos detectados na máquina e informa a pessoa antes de começar, incluindo uma
  estimativa de duração. Coerente com o Princípio VII, que proíbe constantes fixas onde a
  especificação exige adaptação real.

- Q: Quantos modelos devem existir por operação? → A: **Um único modelo por tipo de conteúdo**, não
  um por perfil. O que distingue Rápido, Equilibrado e Qualidade passa a ser **parâmetro de
  execução** do mesmo modelo, não um modelo diferente. Os tipos de conteúdo reconhecidos são: foto
  real, anime/desenho, vídeo real, vídeo de animação, fala e música. Consequência registrada: não
  existe modelo aprovado para melhoria de **música**, e o modelo dedicado a **vídeo real** foi
  reprovado por licença — ver Lacunas Conhecidas.

- Q: Como medir objetivamente que um perfil entrega mais qualidade que outro? → A: **Métrica
  perceptual como critério principal, métrica de fidelidade como guarda-corpo, e revisão visual
  humana sobre um conjunto fixo de referência antes de fechar cada perfil.** A fidelidade sozinha
  penalizaria justamente os modelos que produzem melhor resultado visual; a perceptual sozinha não
  detecta invenção de detalhe inexistente.

- Q: Como tratar elementos que o processamento não preserva (faixas de áudio extras, legendas,
  capítulos, metadados)? → A: **Avisar antes e deixar a pessoa decidir.** O sistema lista
  exatamente o que será perdido e pede confirmação antes de começar. Nunca descarta em silêncio,
  nunca recusa sem oferecer a escolha.

- Q: A tela de atualização identifica os componentes por nome de modelo ou por capacidade? → A:
  **Por capacidade, com detalhe técnico opcional.** A apresentação padrão fala em capacidades
  ("Melhoria de imagem — Qualidade"); um "ver detalhes" explícito revela nome, versão, procedência
  e licença — informativo apenas, sem oferecer escolha. Motivou a emenda da Constitution para
  v2.0.0, que também resolveu uma contradição entre os Princípios IV e V.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Melhorar uma imagem sem entender de IA (Priority: P1)

Uma pessoa arrasta uma foto para o Astros, escolhe se quer o dobro ou o quádruplo do tamanho, e
escolhe entre Rápido, Equilibrado ou Qualidade. Ela recebe a imagem melhorada. Em nenhum momento
vê o nome de um modelo, uma arquitetura, ou um parâmetro de inferência.

**Why this priority**: é a funcionalidade que o produto já entrega hoje, e a mudança de "escolher
modelo" para "escolher intenção" é a transformação central desta especificação. Sem ela, nenhuma
outra parte faz sentido — as demais mídias herdarão o mesmo modelo de interação. Entregue
sozinha, já é um produto melhor que o atual.

**Independent Test**: processar uma imagem em cada combinação de escala (2x, 4x) e perfil
(Rápido, Equilibrado, Qualidade) e verificar que as seis produzem resultado válido, que os tempos
são crescentes de Rápido para Qualidade, e que nenhuma tela expõe identificador de modelo.

**Acceptance Scenarios**:

1. **Given** uma imagem carregada, **When** a pessoa escolhe 2x e Rápido, **Then** o sistema
   entrega a imagem com o dobro da dimensão sem nunca exibir qual modelo foi usado.
2. **Given** a mesma imagem, **When** processada em Rápido e depois em Qualidade, **Then**
   Qualidade demora mais e produz resultado perceptivelmente melhor ou igual — nunca pior.
3. **Given** uma imagem já processada, **When** a pessoa pede outro formato de saída, **Then** o
   sistema reaproveita o resultado existente sem reprocessar.
4. **Given** qualquer tela do aplicativo, **When** a pessoa navega por todas elas, **Then** não
   existe nenhuma interface de seleção, listagem ou download manual de modelos.

---

### User Story 2 - Converter e comprimir sem perder tempo com IA (Priority: P1)

Uma pessoa tem um vídeo em MKV que precisa virar MP4, um PNG que precisa virar WebP, e um WAV que
precisa virar MP3. Ela quer isso rápido, e não quer que o sistema aplique processamento pesado
onde não é necessário.

**Why this priority**: é a operação mais frequente e a de menor custo de implementação — boa parte
já existe. Não depende de nenhum modelo, portanto não depende da resolução de nenhuma questão de
licença. É a fatia que entrega valor mais cedo com menor risco.

**Independent Test**: converter e comprimir pelo menos um arquivo de cada tipo de mídia, verificar
que a operação não invoca processamento por IA, e que conversões simples não oferecem perfis.

**Acceptance Scenarios**:

1. **Given** um arquivo PNG, **When** a pessoa converte para WebP, **Then** o sistema entrega o
   arquivo convertido sem apresentar escolha de perfil.
2. **Given** um vídeo, **When** a pessoa comprime, **Then** o arquivo resultante é menor que o
   original mantendo resolução, duração e áudio intactos.
3. **Given** um áudio FLAC, **When** convertido para MP3, **Then** duração e número de canais são
   preservados.
4. **Given** uma operação de compressão, **When** a pessoa escolhe um nível, **Then** níveis
   diferentes produzem tamanhos de arquivo mensuravelmente diferentes.

---

### User Story 3 - Melhorar um vídeo preservando o que importa (Priority: P2)

Uma pessoa tem um vídeo antigo de baixa resolução. Quer aumentá-lo, e espera que áudio, duração,
velocidade e proporção continuem corretos — um vídeo melhorado que dessincroniza o áudio é um
vídeo destruído.

**Why this priority**: a capacidade existe hoje na linha de comando mas é inacessível pelo
aplicativo. Expor o que já funciona tem alta relação valor/esforço. Fica abaixo de P1 porque
depende da infraestrutura de perfis e de jobs estar estabelecida.

**Independent Test**: processar um vídeo curto com áudio e verificar objetivamente que duração,
taxa de quadros, número de canais de áudio e proporção permanecem corretos, e que a saída tem a
dimensão esperada.

**Acceptance Scenarios**:

1. **Given** um vídeo com áudio, **When** melhorado em 2x, **Then** a duração final é igual à
   original e o áudio continua sincronizado.
2. **Given** um vídeo com orientação vertical, **When** processado, **Then** a saída mantém a
   orientação correta.
3. **Given** um vídeo longo em processamento, **When** a pessoa cancela, **Then** o processamento
   para de fato e libera os recursos.
4. **Given** um vídeo em processamento, **When** a pessoa acompanha a tela, **Then** vê progresso
   que avança de forma perceptível e representa trabalho real.

---

### User Story 4 - Melhorar um áudio ruim (Priority: P2)

Uma pessoa tem uma gravação com ruído de fundo, volume irregular e voz abafada. Quer que fique
audível e agradável, escolhendo apenas entre Rápido, Equilibrado e Qualidade.

**Why this priority**: é a maior lacuna do produto atual — a aba existe vazia. Parte das
capacidades precisa ser construída do zero. Fica em P2 porque a infraestrutura de jobs e perfis é
pré-requisito, e porque o valor por unidade de esforço é menor que o de vídeo.

**Independent Test**: processar uma gravação com ruído conhecido e verificar por medição objetiva
que o ruído diminuiu, que o volume foi normalizado a um alvo definido, e que a duração e o número
de canais não mudaram.

**Acceptance Scenarios**:

1. **Given** uma gravação com ruído de fundo constante, **When** melhorada, **Then** o ruído é
   mensuravelmente reduzido sem que a voz fique distorcida.
2. **Given** áudios com volumes muito diferentes, **When** ambos são normalizados, **Then** ambos
   atingem o mesmo alvo de volume percebido.
3. **Given** um áudio estéreo, **When** processado, **Then** a saída continua estéreo e com a
   mesma duração.
4. **Given** uma capacidade de áudio que o sistema não oferece, **When** a pessoa procura por ela,
   **Then** o produto não a promete em lugar nenhum da interface.

---

### User Story 5 - Funcionar bem na máquina que a pessoa tem (Priority: P2)

Duas pessoas instalam o Astros: uma num notebook sem placa de vídeo dedicada, outra numa estação
com GPU potente. Ambas conseguem usar o produto, cada uma no melhor desempenho que seu hardware
permite, sem configurar nada.

**Why this priority**: é o que separa um produto de uma ferramenta de laboratório. Sem isso, ou o
produto falha em máquinas modestas, ou desperdiça máquinas boas. É P2 porque as histórias P1
precisam existir antes de haver o que adaptar.

**Independent Test**: executar a mesma operação em uma máquina com GPU e em uma sem, verificar que
ambas concluem com sucesso, e que a configuração de processamento efetivamente aplicada difere
entre elas.

**Acceptance Scenarios**:

1. **Given** uma máquina sem GPU, **When** a pessoa processa uma imagem, **Then** o processamento
   conclui usando o processador, sem erro e sem exigir configuração.
2. **Given** uma máquina com GPU disponível, **When** a mesma operação roda, **Then** ela usa a
   GPU e conclui mais rápido que na máquina sem GPU.
3. **Given** um arquivo grande demais para a memória disponível, **When** processado, **Then** o
   sistema o divide automaticamente em partes em vez de falhar.
4. **Given** uma operação inviável no hardware presente, **When** a pessoa a solicita, **Then**
   recebe uma explicação clara da limitação, não um erro genérico.

---

### User Story 6 - Acompanhar e controlar o que está rodando (Priority: P3)

Uma pessoa enfileira vários arquivos, sai para o café, e ao voltar quer saber o que terminou, o
que falhou e por quê, e quer poder cancelar o que ainda não começou.

**Why this priority**: a capacidade já existe para imagens e será generalizada. É P3 porque
melhora a experiência mas nenhuma operação depende dela para funcionar.

**Independent Test**: enfileirar múltiplos arquivos, cancelar um em espera e um em execução, e
verificar que os estados refletem a realidade e que o cancelado realmente parou.

**Acceptance Scenarios**:

1. **Given** vários arquivos na fila, **When** a pessoa observa a lista, **Then** vê o estado
   correto de cada um e a posição dos que aguardam.
2. **Given** um item em processamento, **When** cancelado, **Then** o processamento para de fato e
   os recursos são liberados.
3. **Given** um item que falhou, **When** a pessoa o inspeciona, **Then** vê uma explicação
   compreensível da causa, não uma mensagem técnica.

---

### User Story 7 - Comprar, ativar e continuar usando (Priority: P1)

Uma pessoa compra o Astros, instala e ativa com o que recebeu na compra. A partir daí usa o
produto normalmente, inclusive sem internet. Se trocar de computador, consegue transferir a
licença sem precisar falar com o suporte.

**Why this priority**: com o controle de licença ativo, nenhuma outra história funciona sem esta —
ela é o portão de entrada do produto inteiro. É também onde uma falha custa mais caro: um cliente
legítimo bloqueado por engano é um problema pior que uma cópia não autorizada rodando.

**Independent Test**: ativar uma instalação com licença válida, processar um arquivo, desligar a
rede e processar novamente verificando que ambos funcionam; depois liberar a instalação e reativar
em outra máquina.

**Acceptance Scenarios**:

1. **Given** uma licença válida ainda não utilizada, **When** a pessoa ativa a instalação, **Then**
   o produto libera o processamento e confirma a ativação de forma compreensível.
2. **Given** uma instalação já ativada, **When** a pessoa fica sem internet, **Then** continua
   processando normalmente dentro do período de tolerância definido.
3. **Given** uma licença que atingiu o limite de instalações, **When** a pessoa tenta ativar mais
   uma, **Then** recebe explicação clara e instrução de como liberar uma instalação existente.
4. **Given** uma instalação ativa, **When** a pessoa a libera, **Then** aquela vaga volta a ficar
   disponível para outra máquina.
5. **Given** uma licença revogada ou reembolsada, **When** o produto verifica, **Then** bloqueia o
   processamento explicando o motivo, sem apagar nem inutilizar arquivos já produzidos.
6. **Given** uma instalação sem licença, **When** a pessoa abre o produto, **Then** entende o que
   precisa fazer, sem mensagem técnica ou código de erro cru.

---

### Edge Cases

- **Arquivo corrompido ou de formato não suportado**: o sistema deve identificar antes de começar
  a processar e explicar o problema, em vez de falhar no meio.
- **Memória insuficiente durante o processamento**: deve reduzir automaticamente o consumo
  (dividindo o trabalho) e só falhar se não houver configuração viável — informando qual é o
  limite atingido.
- **Espaço em disco insuficiente para a saída**: deve ser detectado antes de processar.
- **Vídeo sem faixa de áudio**: deve processar normalmente, sem tentar preservar áudio inexistente.
- **Vídeo com múltiplas faixas de áudio ou legendas**: o sistema lista o que será perdido e pede
  confirmação antes de começar (FR-081 a FR-085).
- **Arquivo sem nenhum elemento secundário**: não deve exibir aviso algum — confirmar o óbvio
  treina a pessoa a clicar sem ler.
- **Imagem com transparência ou 16 bits por canal**: se o processamento não suportar, deve
  informar em vez de degradar silenciosamente.
- **Áudio já limpo**: melhorar não pode piorar; o resultado deve ser no mínimo equivalente.
- **Conversão para o mesmo formato de origem**: deve ser tratada como recompressão, não como erro.
- **Aplicativo fechado durante um processamento**: ao reabrir, o estado deve ser coerente e não
  deve haver arquivos temporários órfãos.
- **Ausência de dependência externa de mídia**: o produto deve informar claramente o que está
  faltando, não falhar de forma obscura.
- **Trabalho anterior referenciando um modelo removido**: o histórico não pode quebrar.
- **Perda de conexão durante a ativação**: deve ser possível repetir a ativação sem consumir uma
  vaga de instalação indevidamente.
- **Uso prolongado sem internet**: ao fim do período de tolerância, o produto deve avisar com
  antecedência, não bloquear de surpresa no meio de um trabalho.
- **Relógio do sistema alterado**: manipular a data não pode estender indefinidamente o período de
  tolerância offline.
- **Trabalho em execução quando a licença é bloqueada**: o trabalho em andamento deve concluir ou
  parar de forma limpa, sem corromper o arquivo de saída.
- **Reinstalação na mesma máquina**: não deve consumir uma vaga adicional de instalação.

---

## Requirements *(mandatory)*

### Functional Requirements

#### Estrutura da plataforma

- **FR-001**: O sistema MUST oferecer três operações — Melhorar, Comprimir e Converter — para três
  tipos de mídia: imagem, vídeo e áudio.
- **FR-002**: O sistema MUST apresentar cada combinação suportada de operação e mídia como um
  fluxo acessível na interface, e MUST NOT exibir seções vazias ou não implementadas.
- **FR-003**: O sistema MUST aceitar múltiplos arquivos e processá-los sem exigir que a pessoa
  aguarde cada um individualmente.

#### Tipo de conteúdo

- **FR-094**: O sistema MUST reconhecer o tipo de conteúdo do arquivo e usar isso — não uma escolha
  de modelo — para determinar qual implementação aplicar. Os tipos são: foto real, anime/desenho,
  vídeo real, vídeo de animação, fala e música.
- **FR-095**: O sistema MUST usar **exatamente uma** implementação por tipo de conteúdo e operação.
  MUST NOT manter implementações alternativas para o mesmo tipo.
- **FR-096**: O sistema MUST detectar automaticamente o tipo de conteúdo, e MUST permitir que a
  pessoa corrija a detecção quando ela estiver errada.
- **FR-097**: A escolha de tipo de conteúdo apresentada à pessoa MUST ser expressa em termos do
  conteúdo dela ("Foto", "Desenho ou anime", "Fala", "Música"), e MUST NOT revelar qual
  implementação corresponde a cada tipo.
- **FR-098**: Quando não houver implementação aprovada para um tipo de conteúdo, o sistema MUST NOT
  oferecer a operação para aquele tipo, e MUST explicar que ela não está disponível.

#### Perfis

- **FR-004**: O sistema MUST oferecer exatamente três perfis — Rápido, Equilibrado e Qualidade —
  para as operações em que o perfil altera efetivamente qualidade, velocidade ou compressão.
  Os perfis MUST ser obtidos por **parâmetros de execução** da mesma implementação — divisão do
  trabalho, precisão de cálculo, pós-processamento, quantidade de passagens — e MUST NOT ser
  obtidos trocando de modelo.
- **FR-005**: O sistema MUST NOT oferecer perfis para operações em que eles não produzem diferença
  real, como conversão direta entre formatos equivalentes.
- **FR-006**: Rápido MUST priorizar velocidade; Qualidade MUST priorizar resultado; Equilibrado
  MUST entregar melhoria perceptível sobre Rápido sem multiplicar desproporcionalmente o tempo.
- **FR-007**: Para a mesma entrada, Qualidade MUST NOT produzir resultado pior que Rápido.
- **FR-008**: O sistema MUST usar Rápido como padrão quando nenhuma escolha for feita.

#### Avaliação de qualidade dos perfis

- **FR-087**: A escolha da implementação que atende cada perfil MUST ser decidida por medição
  registrada sobre um conjunto fixo de arquivos de referência, e MUST NOT ser decidida por
  reputação, popularidade ou tamanho do modelo.
- **FR-088**: A avaliação MUST usar uma métrica perceptual como critério principal de qualidade.
- **FR-089**: A avaliação MUST usar uma métrica de fidelidade como guarda-corpo, para detectar
  quando a implementação introduz detalhe que não existia no original.
- **FR-090**: Nenhum perfil MUST ser fechado sem uma revisão visual humana sobre o conjunto de
  referência.
- **FR-091**: O conjunto de referência MUST ser fixo e versionado, de modo que medições feitas em
  momentos distintos sejam comparáveis.
- **FR-092**: As medições MUST registrar, além de qualidade: tempo, memória de sistema, memória de
  vídeo e tamanho do resultado.
- **FR-093**: Os resultados das medições MUST ser documentados e MUST permanecer verificáveis após
  a decisão.

#### Componentes com risco de licença aceito conscientemente

- **FR-099**: Quando um componente for incluído apesar de uma restrição de licença condicional (não
  um "não" absoluto, mas uma condição que pode se tornar bloqueante), essa condição MUST ser
  registrada em `docs/models/MODEL_LICENSES.md` com o gatilho exato que a torna bloqueante.
- **FR-100**: O sistema MUST manter esse registro revisável — a condição não pode ser documentada
  uma vez e esquecida; ela precisa ser reavaliável quando a condição de negócio mudar.

#### Ocultação de modelos

- **FR-009**: O sistema MUST NOT expor nome de modelo, identificador de checkpoint, nome de engine,
  arquitetura neural ou parâmetro interno de inferência em nenhuma tela de uso, mensagem, registro
  visível ou nome de arquivo de saída. A única exceção é a visão de detalhes técnicos descrita em
  FR-063.
- **FR-010**: O sistema MUST remover qualquer interface que permita escolher, substituir ou
  comparar modelos para efeito de processamento, ou cuja saída dependa de um modelo selecionado
  pela pessoa.
- **FR-011**: O contrato de processamento MUST aceitar intenção (tipo de mídia, operação, escala,
  perfil) e MUST NOT aceitar identificador de modelo vindo da interface.
- **FR-012**: O sistema MUST resolver internamente qual implementação atende cada combinação de
  operação, tipo de conteúdo, escala, perfil e hardware disponível.

#### Melhoria de imagem

- **FR-013**: O sistema MUST oferecer ampliação em 2x e 4x, cada uma com os três perfis.
- **FR-014**: O sistema MUST processar imagens grandes dividindo o trabalho automaticamente,
  respeitando a memória disponível.
- **FR-015**: O sistema MUST oferecer realce de detalhes em regiões de rosto por método
  determinístico, e MUST NOT descrever essa capacidade como reconstrução facial por IA.

#### Melhoria de vídeo

- **FR-016**: O sistema MUST oferecer ampliação de vídeo em 2x e 4x, cada uma com os três perfis.
- **FR-017**: O sistema MUST preservar, no vídeo processado: taxa de quadros, duração, faixa de
  áudio, sincronização entre áudio e imagem, proporção e orientação.
- **FR-018**: O sistema MUST informar explicitamente qualquer característica do arquivo original
  que não seja preservada.
- **FR-101**: Ao melhorar vídeo, a divisão do trabalho em partes (quando necessária pelo tamanho do
  quadro) MUST usar parâmetros fixos para todo o vídeo — MUST NOT variar entre quadros do mesmo
  trabalho. Parâmetros que mudam quadro a quadro produzem costuras inconsistentes que aparecem
  como cintilação perceptível.
- **FR-102**: O sistema MUST oferecer uma etapa opcional de estabilização temporal para reduzir
  cintilação perceptível entre quadros, aplicada por ferramenta de mídia tradicional, não por
  modelo de IA — nenhuma solução de IA para isso passou na verificação de licença comercial.

#### Preservação de elementos secundários

- **FR-081**: Antes de iniciar, o sistema MUST inspecionar o arquivo e identificar os elementos
  que não conseguirá preservar — faixas de áudio adicionais, legendas embutidas, capítulos,
  metadados de captura e demais elementos secundários.
- **FR-082**: O sistema MUST apresentar essa lista à pessoa e MUST exigir confirmação explícita
  antes de prosseguir.
- **FR-083**: O sistema MUST NOT descartar nenhum elemento do arquivo original sem aviso prévio.
- **FR-084**: O sistema MUST NOT recusar o processamento apenas por não conseguir preservar um
  elemento secundário; a decisão pertence à pessoa.
- **FR-085**: Quando nenhum elemento for perdido, o sistema MUST NOT exibir aviso — a confirmação
  só aparece quando há algo real a perder.
- **FR-086**: O arquivo original MUST permanecer intacto em qualquer operação.

#### Melhoria de áudio

- **FR-019**: O sistema MUST oferecer redução de ruído de fundo.
- **FR-020**: O sistema MUST oferecer normalização de volume a um alvo de intensidade percebida
  reconhecido, e não apenas ajuste de pico.
- **FR-021**: O sistema MUST oferecer melhoria de clareza e inteligibilidade de voz.
- **FR-022**: O sistema MUST oferecer melhoria de definição de áudio para gravações de banda
  limitada.
- **FR-023**: O sistema MUST NOT prometer, na interface ou na documentação, capacidades de áudio
  que não entrega — em particular, remoção de artefatos de compressão.
- **FR-024**: O sistema MUST preservar duração e número de canais do áudio original.

#### Compressão

- **FR-025**: O sistema MUST comprimir imagem, vídeo e áudio mantendo dimensões, duração e
  estrutura originais, reduzindo apenas o tamanho do arquivo.
- **FR-026**: O sistema MUST selecionar automaticamente o método de compressão mais adequado ao
  hardware disponível e à compatibilidade de reprodução esperada.
- **FR-027**: O sistema MUST permitir escolher o equilíbrio entre tamanho e fidelidade, e níveis
  distintos MUST produzir tamanhos mensuravelmente distintos.

#### Conversão

- **FR-028**: O sistema MUST converter entre formatos distintos dentro do mesmo tipo de mídia.
- **FR-029**: O sistema MUST usar ferramentas especializadas de mídia para conversão, compressão,
  transcodificação e remuxagem, e MUST NOT usar modelos de IA para essas operações.
- **FR-030**: O sistema MUST recusar, com explicação clara, conversões entre tipos de mídia
  diferentes ou para formatos incompatíveis com o conteúdo.

#### Adaptação ao hardware

- **FR-031**: O sistema MUST detectar automaticamente processador, memória, presença e capacidade
  de GPU, e os recursos de codificação e decodificação realmente disponíveis.
- **FR-032**: O sistema MUST adaptar, com base no hardware detectado: escolha de implementação,
  divisão do trabalho, uso de memória, precisão de cálculo, método de codificação e grau de
  paralelismo.
- **FR-033**: O sistema MUST usar o processador como alternativa quando não houver GPU, sempre que
  a operação for tecnicamente viável.
- **FR-034**: O sistema MUST explicar de forma compreensível quando uma operação for inviável no
  hardware presente.
- **FR-035**: O sistema MUST NOT usar valores fixos onde a especificação exige adaptação real ao
  hardware.
- **FR-076**: O sistema MUST derivar do hardware detectado o tamanho e a duração máximos que
  consegue processar, e MUST NOT declarar limites fixos independentes da máquina.
- **FR-077**: Antes de iniciar, o sistema MUST avaliar se o arquivo cabe na capacidade calculada e
  MUST informar a pessoa quando estiver perto do limite ou acima dele.
- **FR-078**: O sistema MUST apresentar uma estimativa de duração antes de começar trabalhos
  longos, para que a pessoa decida se quer prosseguir.
- **FR-079**: Quando um arquivo exceder a capacidade da máquina, o sistema MUST explicar qual
  recurso é insuficiente e qual seria a condição para viabilizá-lo, e MUST NOT começar um trabalho
  que sabe que não pode concluir.
- **FR-080**: A capacidade calculada MUST considerar a memória efetivamente disponível no momento,
  não apenas a memória total instalada.

#### Trabalhos e progresso

- **FR-036**: O sistema MUST representar toda operação demorada como um trabalho com estado
  observável: aguardando, na fila, processando, concluído, com erro, ou cancelado.
- **FR-037**: O sistema MUST informar progresso quando for possível estimá-lo, e esse progresso
  MUST refletir trabalho real.
- **FR-038**: Cancelar MUST interromper o processamento de fato e liberar os recursos.
- **FR-039**: O sistema MUST apresentar falhas em linguagem compreensível, indicando a causa e o
  que a pessoa pode fazer.
- **FR-040**: O sistema MUST permitir recuperar o resultado de um trabalho concluído sem
  reprocessá-lo.

#### Gestão interna de modelos

- **FR-041**: O sistema MUST gerenciar automaticamente a obtenção, verificação de integridade,
  armazenamento, carregamento, reuso e liberação das implementações que utiliza.
- **FR-042**: O sistema MUST verificar a integridade de qualquer componente obtido antes de usá-lo.
- **FR-043**: O sistema MUST manter exatamente uma implementação por tipo de conteúdo e operação, e
  MUST NOT manter implementações que nenhum tipo de conteúdo utiliza.
- **FR-063**: O sistema MUST oferecer uma tela de componentes e atualizações que apresente cada
  item **por capacidade** ("Melhoria de imagem — Qualidade"), com tamanho ocupado, estado de
  instalação e disponibilidade de atualização.
- **FR-064**: Essa tela MUST permitir baixar, atualizar e remover componentes, e MUST NOT permitir
  escolher qual componente atende um perfil.
- **FR-065**: Essa tela MUST oferecer uma visão de detalhes técnicos explicitamente opcional,
  exibindo nome, versão, procedência e licença do componente. Essa visão MUST ser informativa
  apenas.
- **FR-066**: As atribuições exigidas por licença MUST estar presentes nessa visão de detalhes.
- **FR-067**: Os componentes MUST ser baixados sob demanda e armazenados no computador da pessoa;
  o instalador MUST NOT embarcá-los.
- **FR-068**: Quando uma operação exigir um componente ainda não instalado, o sistema MUST informar
  antes de começar, indicar o tamanho do download e pedir confirmação.
- **FR-069**: Sem conexão e sem o componente necessário instalado, o sistema MUST explicar a
  situação claramente, e MUST NOT falhar de forma obscura nem iniciar um trabalho que não pode
  concluir.

#### Execução e proteção do processamento

- **FR-070**: Todo o processamento de mídia MUST acontecer no computador da pessoa. O sistema MUST
  NOT enviar o conteúdo dos arquivos para nenhum servidor.
- **FR-071**: A lógica que define como cada processo é executado MUST ser entregue ao processo de
  execução no momento do uso e removida em seguida, sem ser persistida em disco em forma
  utilizável.
- **FR-072**: A entrega dessa lógica MUST ser vinculada à instalação autorizada, de modo que o
  material obtido por uma instalação não seja aproveitável por outra.
- **FR-073**: O sistema MUST verificar a integridade e a autenticidade dessa lógica antes de
  executá-la, e MUST recusar execução se a verificação falhar.
- **FR-074**: O sistema MUST recusar lógica de execução de versão anterior à última conhecida.
- **FR-075**: O tempo de permanência de material sensível em memória MUST ser reduzido ao mínimo
  necessário para a execução.

#### Licenciamento de componentes

- **FR-044**: O sistema MUST incluir apenas componentes cuja licença permita explicitamente uso
  comercial, conforme registrado em `docs/models/MODEL_LICENSES.md`.
- **FR-045**: O sistema MUST exibir os créditos de atribuição exigidos pelas licenças dos
  componentes que utiliza, de forma acessível na interface.
- **FR-046**: A verificação de permissão de uso comercial MUST ser aplicada pelo componente que
  decide qual implementação executar.
- **FR-047**: O sistema MUST NOT distribuir componentes cuja licença exija a abertura do código do
  aplicativo.

#### Controle de licença do produto

- **FR-051**: O sistema MUST exigir uma licença válida para executar operações de processamento.
- **FR-052**: O sistema MUST permitir ativar uma instalação a partir do comprovante de compra, sem
  intervenção de suporte humano.
- **FR-053**: O sistema MUST limitar o número de instalações simultâneas por licença, e MUST
  informar claramente qual é o limite e quantas vagas restam.
- **FR-054**: A pessoa MUST poder liberar uma instalação por conta própria, devolvendo a vaga.
- **FR-055**: Reinstalar na mesma máquina MUST NOT consumir uma vaga adicional.
- **FR-056**: Após ativada, a instalação MUST continuar funcionando sem conexão com a internet
  durante um período de tolerância definido.
- **FR-057**: O sistema MUST avisar com antecedência quando o período de tolerância offline estiver
  perto do fim, e MUST NOT bloquear no meio de um trabalho em andamento.
- **FR-058**: Alterar o relógio do sistema MUST NOT estender o período de tolerância offline.
- **FR-059**: Quando uma licença for revogada ou reembolsada, o sistema MUST bloquear novos
  processamentos, e MUST NOT apagar, invalidar ou tornar inacessível nenhum arquivo já produzido.
- **FR-060**: Toda mensagem relacionada a licença MUST explicar a situação e a ação possível, sem
  jargão técnico nem código de erro cru.
- **FR-061**: Uma falha de comunicação com o serviço de licença MUST NOT ser tratada como licença
  inválida enquanto o período de tolerância estiver vigente.
- **FR-062**: O sistema MUST NOT registrar nem transmitir o conteúdo dos arquivos processados, nem
  contabilizar uso por arquivo, como parte do controle de licença.

#### Migração e continuidade

- **FR-048**: O histórico de trabalhos anteriores MUST continuar acessível após a transição, sem
  expor identificadores de modelos que deixaram de existir.
- **FR-049**: As capacidades hoje disponíveis apenas por linha de comando MUST passar a estar
  acessíveis pela interface do aplicativo.
- **FR-050**: Nenhuma capacidade atualmente funcional e comercialmente permitida MUST ser perdida
  na transição, salvo decisão registrada em contrário.

### Key Entities

- **Solicitação de mídia**: o que a pessoa pediu — tipo de mídia, operação, escala quando
  aplicável, perfil quando aplicável, arquivo de entrada e destino desejado.
- **Trabalho**: uma solicitação em execução ou concluída, com estado, progresso, posição na fila,
  resultado e, em caso de falha, causa e categoria do erro.
- **Perfil**: um dos três níveis de intenção — Rápido, Equilibrado, Qualidade —, sem qualquer
  vínculo visível com implementação.
- **Capacidade de hardware**: o retrato do que a máquina oferece, usado para decidir como executar.
- **Implementação**: o meio interno que atende uma combinação de operação, escala e perfil. Nunca
  visível para a pessoa.
- **Registro de licença**: o que autoriza cada componente a existir no produto — origem, licença
  de código, licença de pesos, permissão comercial, restrições e data de verificação.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Uma pessoa que nunca usou o produto consegue melhorar uma imagem em menos de 60
  segundos desde a abertura, sem consultar documentação.
- **SC-002**: Nenhuma tela, mensagem ou nome de arquivo de saída expõe identificador de modelo,
  arquitetura ou parâmetro interno — verificável por inspeção completa da interface.
- **SC-003**: Toda operação oferecida entrega resultado válido nas nove combinações de mídia e
  operação, ou está ausente da interface — não existe seção não implementada.
- **SC-004**: Para a mesma entrada, o perfil Rápido conclui em menos tempo que Equilibrado, que
  conclui em menos tempo que Qualidade — medido e documentado.
- **SC-005**: O perfil Qualidade nunca pontua pior que Rápido na métrica perceptual sobre o
  conjunto de referência, e não degrada a métrica de fidelidade além do limite documentado.
- **SC-006**: Vídeos processados preservam duração, taxa de quadros, canais de áudio e proporção
  com desvio zero em relação ao original.
- **SC-007**: Áudios processados apresentam redução de ruído mensurável e atingem o alvo de volume
  definido, mantendo duração e canais inalterados.
- **SC-008**: Compressão reduz o tamanho do arquivo em pelo menos 30% para conteúdo típico, sem
  alterar dimensões nem duração.
- **SC-009**: O produto conclui a operação principal de cada mídia tanto em máquina sem GPU quanto
  em máquina com GPU, sem configuração manual.
- **SC-010**: Nenhuma operação falha por memória insuficiente antes de ter tentado a configuração
  de menor consumo disponível.
- **SC-011**: 100% dos componentes distribuídos têm permissão de uso comercial verificada e
  registrada com fonte e data.
- **SC-012**: Todas as atribuições exigidas por licença estão visíveis no produto.
- **SC-013**: Cancelar um trabalho em execução libera os recursos em menos de 5 segundos.
- **SC-014**: Toda falha apresentada indica causa e ação possível — nenhuma mensagem técnica bruta
  chega à pessoa.
- **SC-015**: O histórico anterior à transição permanece acessível e nenhum item quebra.
- **SC-016**: Cada perfil tem uma medição registrada e reproduzível sobre o conjunto de referência
  que justifica a implementação escolhida, incluindo qualidade perceptual, fidelidade, tempo e
  consumo de memória — mais o registro da revisão visual humana.
- **SC-017**: Uma pessoa com licença válida consegue ativar e começar a processar em menos de 2
  minutos, sem contatar suporte.
- **SC-018**: Nenhum cliente com licença válida é bloqueado por falha de rede, indisponibilidade
  do serviço de licença, ou uso offline dentro do período de tolerância.
- **SC-019**: Nenhum arquivo já produzido pela pessoa se torna inacessível em consequência de
  qualquer estado de licença.
- **SC-020**: O conteúdo dos arquivos processados nunca sai do computador da pessoa — verificável
  por inspeção do tráfego de rede durante um processamento completo.
- **SC-021**: Após a conclusão de um trabalho, nenhuma cópia utilizável da lógica de execução
  permanece em disco.
- **SC-022**: A tela de componentes permite instalar, atualizar e remover cada item, e sua
  apresentação padrão não exibe nenhum nome técnico.
- **SC-023**: A capacidade máxima informada pelo produto difere entre máquinas de hardware
  diferente — verificável comparando duas máquinas com memória distinta.
- **SC-024**: Nenhum trabalho é iniciado sabendo-se de antemão que excede a capacidade da máquina;
  a recusa acontece antes de qualquer processamento, com explicação do recurso insuficiente.
- **SC-025**: Nenhum elemento do arquivo original é descartado sem que a pessoa tenha confirmado
  antes — verificável processando um arquivo com múltiplas faixas e legendas.
- **SC-026**: Arquivos sem elementos a perder não geram nenhum aviso de confirmação.
- **SC-027**: O produto distribui no máximo uma implementação por tipo de conteúdo e operação —
  verificável contando os componentes instaláveis.
- **SC-028**: A detecção automática de tipo de conteúdo acerta em pelo menos 90% de um conjunto de
  referência rotulado, e a pessoa consegue corrigir os 10% restantes.
- **SC-029**: Nenhuma operação é oferecida para um tipo de conteúdo que não tem implementação
  aprovada.

---

## Assumptions

- **Produto e distribuição**: o Astros é um aplicativo de desktop comercial, de código fechado,
  instalado localmente. Processamento acontece na máquina da pessoa, não em servidor.
- **Uso individual**: o produto atende uma pessoa por instalação. Não há multiusuário concorrente,
  contas ou papéis de acesso.
- **Operação offline**: após ativada, a instalação processa sem internet durante um período de
  tolerância definido. Acesso à rede é necessário para ativar, para revalidar periodicamente a
  licença, e para obter componentes ainda não instalados.
- **Controle de licença**: ativo neste escopo (decisão de 2026-08-08). A infraestrutura já
  existente — identidade criptográfica por instalação, autorizações assinadas de curta duração e
  entrega de pacote protegido — é reutilizada, não reescrita.
- **Período de tolerância offline**: assumido como **30 dias** desde a última revalidação
  bem-sucedida, com aviso a partir do 23º dia. Valor adotado como padrão razoável de mercado, não
  especificado pelo dono do projeto — confirmar antes do lançamento.
- **Limite de instalações por licença**: assumido como **2**, valor já praticado pela
  infraestrutura existente. Confirmar antes do lançamento.
- **Conjunto de referência para medição**: será montado a partir das imagens já presentes em
  `inputs/`, ampliado com amostras de vídeo e áudio representativas. Precisa cobrir os casos
  difíceis reais — pele, texto, texturas finas, gradientes — e não apenas fotos fáceis.
- **Escalas**: apenas 2x e 4x para melhoria. Outras escalas ficam fora do escopo desta
  especificação.
- **Limites de entrada**: não são declarados em números fixos. O produto calcula sua capacidade a
  partir do hardware e a comunica. Consequência assumida: a detecção de hardware precisa estar
  madura antes das operações pesadas, o que a coloca cedo na ordem de implementação.
- **Reaproveitamento**: a infraestrutura existente de trabalhos, fila, progresso, cancelamento e
  isolamento de processo é reutilizada e generalizada, não reescrita.
- **Ferramentas de mídia**: existe uma ferramenta externa de processamento de mídia disponível, e
  ela deve ser distribuída em configuração compatível com produto comercial de código fechado.
- **Recuperação facial**: a capacidade baseada em IA é removida por incompatibilidade de licença,
  conforme decisão registrada em `docs/models/MODEL_LICENSES.md`, e substituída por realce
  determinístico. Isto é uma redução deliberada e documentada de capacidade.
- **Capacidades de áudio**: apenas melhoria de definição de banda **para fala** tem implementação
  aprovada. Redução de ruído, normalização por intensidade percebida e melhoria de voz são
  construção nova por DSP tradicional, conforme decisão registrada.
- **Uma implementação por tipo de conteúdo**: decisão de 2026-08-08. Reduz o conjunto de 19
  modelos catalogados para no máximo um por tipo de conteúdo e operação. Os perfis passam a ser
  obtidos por parâmetro, não por troca de modelo. As lacunas resultantes estão em Lacunas
  Conhecidas.
- **Reduções de capacidade**: quatro lacunas conhecidas (LC-001 a LC-004) são consequências
  aceitas da exigência de licença comercial. Todas estão registradas em vez de contornadas em
  silêncio.
- **Idioma**: a interface permanece multilíngue, com português como idioma de referência.
- **Plataforma principal**: Windows é a plataforma primária de validação; macOS e Linux são
  secundários.

---

## Lacunas Conhecidas

Consequências diretas de aplicar o Princípio IV (apenas licença comercial) combinado com a decisão
de **uma implementação por tipo de conteúdo**. Registradas aqui porque são reduções reais de
capacidade, não omissões da especificação.

### LC-001 — Melhoria de música usa componente com risco de licença aceito conscientemente

**Resolvida em 2026-08-08, com ressalva registrada.** O tipo de conteúdo música é atendido pelo
**SonicMaster** (Apache-2.0, código e pesos). Diferente dos demais componentes aprovados, este não
é uma aprovação limpa — é uma decisão do dono do produto contra a recomendação padrão da
Constitution, documentada em detalhe em `docs/models/MODEL_LICENSES.md` seção 3-bis.

**O risco aceito**: o SonicMaster depende em tempo de inferência do autoencoder do Stable Audio
Open 1.0, cuja licença (Stability AI Community License) proíbe uso comercial acima de
US$ 1.000.000 de receita anual — não é uma restrição não-comercial simples, é uma licença com
prazo de validade atrelado ao próprio sucesso do produto.

**Isto MUST ser tratado como obrigação recorrente, não como decisão de uma vez**: a receita do
produto MUST ser monitorada, e este componente MUST ser removido, substituído ou relicenciado
antes de o limite ser atingido.

### LC-002 — Resolvida: implementação dedicada a vídeo real encontrada, sem ressalva de licença

**Resolvida em 2026-08-08.** O modelo específico para live action que existia no registro anterior
(`liveaction-span`) era CC-BY-NC-SA-4.0 e permanece rejeitado. Em seu lugar, o tipo de conteúdo
vídeo real é atendido por `2xPublic_realplksr_dysample_layernorm_real_nn` — Apache-2.0 em código e
pesos, dataset inteiramente de domínio público, sem contaminação e sem condição de licença.
Detalhe completo em `docs/models/MODEL_LICENSES.md` seção 3-ter, incluindo a mitigação de
cintilação entre quadros (tiling determinístico + `atadenoise`/`deflicker` do FFmpeg, LGPL).

### LC-003 — Não há remoção de artefatos de compressão de áudio

Nenhuma solução madura e comercialmente licenciável existe. A capacidade não é oferecida.

### LC-004 — Não há reconstrução facial por IA

Toda a categoria é inacessível comercialmente. Substituída por realce determinístico de região de
rosto, que melhora nitidez mas não reconstrói rostos muito degradados.

---

## Open Questions

Estas decisões não têm padrão razoável e afetam o escopo. Devem ser resolvidas em
`/speckit.clarify` antes do planejamento.

- **OQ-001** — ✅ **Resolvida em 2026-08-08.** O controle de licença será **ativado nesta entrega**.
  Ver User Story 7, FR-051 a FR-062, e os casos de borda de licença.

- **OQ-002** — ✅ **Resolvida em 2026-08-08.** Não há limite fixo: a capacidade é **derivada do
  hardware detectado** e comunicada antes de começar. Ver FR-076 a FR-080.

- **OQ-003** — ✅ **Resolvida em 2026-08-08.** O sistema **avisa antes e deixa a pessoa decidir**.
  Ver FR-081 a FR-086.

**Nenhuma questão permanece aberta.** A especificação está pronta para `/speckit.plan`.
