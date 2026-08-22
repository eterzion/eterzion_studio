# Feature Specification: Central de Compressão de Mídia

**Feature Branch**: `008-compression-centre`

**Created**: 2026-08-21

**Status**: Draft — aguardando revisão (portão do workflow speckit, passo `review-spec`)

**Input**: solicitação do usuário em 76 seções numeradas, pedindo uma Central de Compressão para
imagens, vídeos, áudios e GIFs, com presets, tamanho alvo, modos básico e avançado, fila,
estimativa, comparação e exportação. A aba nova é laranja.

**Constituição aplicável**: v4.0.0. Esta feature é a razão da emenda — a exceção do Princípio V
para parâmetros de codificação controlados pelo usuário foi escrita para ela, e as cinco condições
cumulativas dessa exceção aparecem abaixo como requisitos, não como intenção.

---

## Contexto: o que já existe

Registrado aqui porque o Princípio II (Reuse First) exige que a spec parta do que há, e porque
metade das 76 seções descreve coisas que o produto já faz.

| A solicitação pede | Já existe | Onde |
|---|---|---|
| Compressão e conversão de imagem/vídeo/áudio | **Sim, funcional** | `astros_upscale/optimize.py`, operações `compress`/`convert` |
| Fila com estados, progresso, cancelamento | **Sim** | `app/jobs.py`, `store/jobs.ts`, `store/mediaQueue.ts` |
| Sonda funcional de encoder de vídeo | **Sim** | `media.encoder_works()`, `first_available_encoder()` |
| Sonda funcional de encoder de áudio | **Sim** | `media.audio_encoder_works()` |
| Sonda funcional de formato de imagem | **Sim** | `media.image_format_works()` |
| Disponibilidade por container, para a interface | **Sim** | `GET /video/export-options`, `GET /image/export-options` |
| Player de vídeo com transporte completo | **Sim** | `components/video/VideoPlayer.vue` |
| Comparação antes/depois com slider | **Sim** | `components/CompareSlider.vue` |
| Zoom sincronizado e inspeção de pixel | **Sim** | `composables/useViewportPanZoom.ts` |
| Painéis, sliders com valor e dica, selects, switches | **Sim** | `CollapsiblePanel`, `SliderField`, `AppSelect`, `SettingSwitch` |
| Histórico | **Sim** | `views/HistoryView.vue` |
| Tetos por operação e recusa antes de começar | **Sim** | `app/config.py` `VIDEO_EDIT_CEILINGS`, `video_edits.check_ceilings()` |
| Limpeza de temporários | **Parcial** | existe por job; não há varredura no encerramento |
| Compressão de GIF/animação | **Não** | caminho novo |
| Estimativa de tamanho antes de processar | **Não** | caminho novo |
| Modo tamanho-alvo | **Não** | caminho novo |
| Presets salvos pelo usuário | **Não** | caminho novo |
| Comparação sincronizada de dois vídeos | **Não** | o player existe; a sincronia não |
| Forma de onda de áudio | **Não** | caminho novo |
| Controles técnicos (codec, CRF, encoder) na interface | **Não, e era proibido** | liberado pela emenda v4.0.0 |

**O que isso significa para o escopo:** a Central não é um subsistema novo ao lado do que existe.
É uma **superfície nova sobre o motor de compressão que já roda**, mais cinco capacidades que
faltam (estimativa, tamanho-alvo, presets do usuário, animação, comparação sincronizada).

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Reduzir uma imagem sem pensar em nada (Priority: P1)

Alguém tem um PNG de 8 MB que precisa caber num e-mail. Abre Compressão, arrasta o arquivo,
escolhe "Balanceado", vê que a estimativa diz ~900 KB, clica em Comprimir, compara o antes e o
depois, e salva.

**Why this priority**: é o produto mínimo. Se só isto existir, a Central já resolve o caso mais
comum de compressão, e todas as outras histórias são a mesma jornada com outra mídia ou mais
controle.

**Independent Test**: importar uma imagem, aplicar um preset, comprimir, comparar e exportar —
sem tocar em nenhum controle avançado, sem escolher codec, sem ver um nome técnico.

**Acceptance Scenarios**:

1. **Given** uma imagem de 8 MB importada, **When** o preset "Balanceado" está selecionado,
   **Then** a interface mostra tamanho original, estimativa e economia estimada antes de qualquer
   processamento.
2. **Given** a compressão concluída, **When** o resultado aparece, **Then** mostra tamanho final
   real, economia real e redução percentual — medidos, não estimados.
3. **Given** o resultado pronto, **When** a pessoa compara, **Then** original e comprimido podem
   ser vistos lado a lado e com slider, com zoom sincronizado.
4. **Given** o resultado pronto, **When** a pessoa exporta, **Then** o arquivo original continua
   byte a byte igual (Princípio XV).
5. **Given** a jornada inteira, **When** ela termina, **Then** nenhum nome de codec, encoder ou
   parâmetro técnico apareceu em tela.

---

### User Story 2 — Fazer caber num limite de tamanho (Priority: P1)

Alguém precisa que um vídeo tenha no máximo 8 MB para um upload. Escolhe "Tamanho desejado",
digita 8 MB, e o sistema calcula o que precisa mudar.

**Why this priority**: é a razão pela qual a maioria das pessoas comprime alguma coisa. Um preset
responde "quão bom", e só o tamanho-alvo responde "vai caber?".

**Independent Test**: definir um alvo e verificar que o resultado fica dentro dele, ou que o
sistema recusa antes de começar dizendo que o alvo é inatingível.

**Acceptance Scenarios**:

1. **Given** um vídeo de 24,8 MB, **When** o alvo é 5 MB, **Then** a estimativa mostra as
   configurações derivadas e diz explicitamente que é uma estimativa.
2. **Given** um alvo impossível para a mídia (menor que o mínimo viável), **When** a pessoa o
   define, **Then** o sistema diz isso **antes** de processar e nomeia o motivo — não processa e
   entrega algo fora do alvo.
3. **Given** um alvo atingível, **When** o processamento termina, **Then** o resultado fica dentro
   do alvo, ou o sistema informa por quanto passou e por quê.
4. **Given** unidades, **When** a pessoa escolhe KB, MB ou GB, **Then** o cálculo acompanha.

---

### User Story 3 — Comprimir vídeo com controle real (Priority: P2)

Alguém com um vídeo de 423 MB quer decidir codec, qualidade e resolução — sabe o que é CRF e
quer usá-lo.

**Why this priority**: é o caso que justifica a emenda constitucional. Sem ele, a Central é um
botão de comprimir com nome bonito.

**Independent Test**: abrir o modo Avançado, escolher codec e CRF, e verificar que o arquivo
produzido usou exatamente o que foi pedido.

**Acceptance Scenarios**:

1. **Given** o modo Básico, **When** a pessoa nunca abre Avançado, **Then** ela vê apenas preset,
   qualidade, formato, resolução e tamanho alvo (condição 2 da exceção).
2. **Given** o modo Avançado aberto, **When** todos os controles estão em "Automático", **Then**
   o resultado é idêntico ao do modo Básico com o mesmo preset (condição 4).
3. **Given** um codec que esta máquina não consegue executar, **When** a lista é apresentada,
   **Then** ele aparece desabilitado com motivo — nunca selecionável (condição 3).
4. **Given** H.264 ou H.265 escolhidos, **When** só há encoder GPL disponível, **Then** ficam
   indisponíveis (condição 5) — a licença não é escolha do usuário.
5. **Given** container e codec incompatíveis, **When** a pessoa tenta combiná-los, **Then** a
   combinação não é oferecida; nunca é aceita em silêncio e corrigida por baixo.

---

### User Story 4 — Comprimir áudio (Priority: P2)

Alguém com um WAV de 60 MB quer um MP3 de 128 kbps, ou um FLAC menor.

**Why this priority**: mídia independente, mesma jornada, e o motor já existe (`optimize_audio`).

**Independent Test**: importar um áudio, escolher codec e bitrate, comprimir, ouvir os dois.

**Acceptance Scenarios**:

1. **Given** um formato lossless escolhido (FLAC, WAV), **When** os controles são apresentados,
   **Then** controles de bitrate lossy não aparecem — não ficam presentes e inertes.
2. **Given** sample rate "original", **When** o arquivo é processado, **Then** não há resampling.
3. **Given** um áudio comprimido, **When** a pessoa compara, **Then** pode alternar entre original
   e resultado, com duração, bitrate, codec, tamanho e sample rate visíveis.

---

### User Story 5 — Otimizar GIFs e animações (Priority: P3)

Alguém tem um GIF de 12 MB e quer que ele caia para 2 MB, ou vire um WebP/MP4.

**Why this priority**: é a única mídia sem nenhum caminho no backend hoje. Depende de tudo o que
as histórias anteriores estabelecem.

**Independent Test**: importar um GIF, reduzir cores e FPS, e verificar que a animação continua
animada e menor.

**Acceptance Scenarios**:

1. **Given** um GIF, **When** comprimido, **Then** o resultado continua sendo uma animação com a
   mesma ordem de quadros.
2. **Given** conversão para WebP/MP4/WebM, **When** tecnicamente possível, **Then** é oferecida;
   quando não, não aparece.
3. **Given** quantidade de cores e dithering, **When** ajustados, **Then** afetam o resultado
   visivelmente.

---

### User Story 6 — Processar muitos arquivos de uma vez (Priority: P3)

Alguém arrasta 40 fotos e quer todas comprimidas com a mesma configuração — ou com configurações
individuais.

**Why this priority**: multiplica o valor das histórias anteriores, mas nenhuma delas depende
desta.

**Independent Test**: importar vários arquivos, aplicar uma configuração a todos, processar, e
cancelar no meio.

**Acceptance Scenarios**:

1. **Given** vários arquivos na fila, **When** "aplicar a todos" é usado, **Then** todos recebem
   a mesma configuração compatível com seu tipo de mídia.
2. **Given** a fila processando, **When** a pessoa cancela um item, **Then** só aquele para, e o
   processo de encoding correspondente termina — sem FFmpeg órfão, sem temporário remanescente.
3. **Given** um item com erro, **When** a pessoa tenta novamente, **Then** ele volta para a fila
   sem afetar os demais.

---

### User Story 7 — Guardar o que funcionou (Priority: P3)

Alguém encontrou a configuração certa para o Discord e quer reusá-la sem redescobri-la.

**Why this priority**: só tem valor depois que existe configuração suficiente para valer a pena
guardar.

**Independent Test**: salvar um preset, fechar o app, reabrir, aplicá-lo e obter o mesmo
resultado.

**Acceptance Scenarios**:

1. **Given** uma configuração ajustada, **When** salva como preset, **Then** sobrevive ao
   reinício do aplicativo.
2. **Given** um preset de imagem, **When** a mídia ativa é vídeo, **Then** ele não é oferecido —
   presets guardam só o que faz sentido para seu tipo.
3. **Given** o histórico, **When** a pessoa repete uma compressão anterior, **Then** as
   configurações daquela execução são restauradas.

---

### Edge Cases

- **Arquivo cujo conteúdo não bate com a extensão.** Um `.png` que é JPEG. A detecção não pode
  confiar na extensão (§39): o tipo vem da sondagem real do conteúdo.
- **Mídia corrompida ou parcialmente ilegível.** Recusa antes de começar, nomeando o motivo.
- **Alvo de tamanho menor que o mínimo viável.** Um vídeo de 2 h não cabe em 1 MB com qualidade
  utilizável. O sistema diz isso antes, não entrega lixo depois.
- **Compressão que aumenta o arquivo.** Recomprimir um JPEG já otimizado pode crescer. O
  resultado informa isso em vez de apresentar economia negativa como sucesso.
- **Nenhum encoder disponível para a combinação pedida.** Já acontece hoje com `mp4` em máquina
  sem hardware H.264 — a Central herda esse comportamento, não o contorna.
- **Espaço em disco insuficiente.** Verificado antes, como `video_edits` já faz.
- **Arquivo de saída igual ao de entrada.** Proibido pelo Princípio XV, inclusive quando a pessoa
  pediu sobrescrever.
- **Aplicativo fechado no meio do processamento.** Temporários não podem sobreviver ao
  encerramento.
- **GIF de um quadro só.** É uma imagem; tratar como animação seria inventar um problema.
- **Áudio sem trilha, vídeo sem áudio.** Controles do que não existe não são oferecidos.

---

## Requirements *(mandatory)*

### Navegação e enquadramento

- **FR-001**: O aplicativo MUST oferecer uma entrada de menu principal "Compressão", com acento
  laranja, seguindo o mesmo mecanismo de acento por módulo que `theme.css` já usa
  (`[data-module]`).
- **FR-002**: A tela MUST usar os componentes, espaçamentos, tipografia, bordas e transições
  existentes. Nenhum estilo isolado, nenhuma redefinição do sistema de design.
- **FR-003**: A tela MUST oferecer navegação interna por tipo de mídia: Imagem, Vídeo, Áudio,
  GIF/Animação.
- **FR-004**: A arquitetura MUST permitir acrescentar um novo tipo de mídia sem alterar os
  existentes — tipos registrados, não ramificados por condicional espalhada.

### Importação e detecção

- **FR-005**: MUST aceitar arquivos por arrastar-e-soltar e por seleção via diálogo nativo.
- **FR-006**: MUST aceitar múltiplos arquivos e acrescentar à fila existente sem substituí-la.
- **FR-007**: MUST detectar o tipo de mídia pelo **conteúdo**, não pela extensão.
- **FR-008**: MUST apresentar, antes de processar e quando aplicável a cada mídia: nome, extensão,
  tamanho, resolução, duração, codec, bitrate, FPS, canais e sample rate.
- **FR-009**: MUST permitir remover um arquivo, limpar todos e acrescentar novos.
- **FR-010**: Metadado que a sondagem não conseguir obter MUST ser omitido, nunca preenchido com
  valor inventado ou com um padrão que pareça medido.

### Presets

- **FR-011**: MUST oferecer os presets: Qualidade máxima, Alta qualidade, Balanceado, Arquivo
  pequeno, Compressão máxima, Personalizado.
- **FR-012**: Os valores de cada preset MUST estar centralizados em configuração, nunca embutidos
  na interface (§66).
- **FR-013**: MUST permitir criar, salvar, renomear, duplicar e excluir presets do usuário, e
  restaurar os padrões.
- **FR-014**: Um preset MUST guardar somente configurações compatíveis com seu tipo de mídia, e
  MUST NOT ser oferecido para outro tipo.
- **FR-015**: Presets de plataforma (Discord, WhatsApp, YouTube, Web, e-mail) MUST vir da mesma
  configuração central, não espalhados pela interface.

### Tamanho alvo

- **FR-016**: MUST oferecer modo "Tamanho desejado" com unidades KB, MB e GB.
- **FR-017**: MUST derivar as configurações necessárias a partir de duração, bitrate, resolução e
  overhead de container.
- **FR-018**: MUST recalcular a estimativa sempre que qualquer configuração mudar.
- **FR-019**: MUST declarar explicitamente que o tamanho final é estimativa.
- **FR-020**: MUST recusar, antes de processar, um alvo que não é atingível, nomeando o motivo.

### Estimativa e resultado

- **FR-021**: Antes de processar, MUST mostrar tamanho original, tamanho estimado, economia
  estimada e redução percentual.
- **FR-022**: Depois de processar, MUST mostrar os mesmos números **medidos**, mais o tempo
  decorrido.
- **FR-023**: Quando o resultado ficar maior que o original, MUST dizer isso — não apresentar
  economia negativa como sucesso.

### Controles por mídia

- **FR-024**: Imagem MUST suportar, quando a build fornecer: PNG, JPEG/JPG, WebP, AVIF, TIFF, BMP.
- **FR-025**: Imagem MUST oferecer qualidade 0–100 com descrição dinâmica (Muito baixa … Máxima).
- **FR-026**: Imagem MUST oferecer lossless e lossy, desabilitando o que o formato não suportar,
  com o motivo em tooltip.
- **FR-027**: Imagem MUST oferecer redimensionamento com largura, altura, percentual, preservar
  proporção, impedir upscale e presets (Original, 4K, 1440p, 1080p, 720p, 480p, 50%, 25%).
- **FR-028**: Imagem MUST oferecer controle de metadados: preservar todos, só essenciais, remover
  EXIF, GPS, comentários, perfil ICC, ou todos. O padrão MUST priorizar privacidade sem degradar a
  imagem.
- **FR-029**: A troca de formato MUST atualizar quais controles existem — não desabilitar
  controles inaplicáveis, e sim não os apresentar.
- **FR-030**: Vídeo MUST oferecer codec (H.264, H.265, VP9, AV1, Automático), container (MP4,
  WebM, MKV), qualidade constante (CRF/CQ) ou bitrate (alvo, máximo, CBR, VBR), resolução, FPS e
  preset de velocidade.
- **FR-031**: Vídeo MUST oferecer configuração separada do áudio contido: manter, recomprimir ou
  remover, com codec, bitrate, sample rate e canais.
- **FR-032**: Áudio MUST suportar, quando as bibliotecas fornecerem: MP3, AAC, M4A, OGG, Opus,
  WAV, FLAC, com codec, bitrate (presets de 64 a 320 kbps e personalizado), sample rate e canais.
- **FR-033**: Formato lossless de áudio MUST ocultar controles de bitrate lossy.
- **FR-034**: Sample rate "original" MUST NOT provocar resampling.
- **FR-035**: GIF/animação MUST oferecer qualidade, resolução, FPS, número de cores, dithering e
  otimização de quadros, e conversão para WebP, MP4 ou WebM quando possível.
- **FR-036**: FPS MUST NOT ser alterado por padrão em nenhuma mídia.

### Modo básico e avançado — condições da exceção constitucional

- **FR-037**: O modo Básico MUST mostrar somente preset, qualidade, formato, resolução e tamanho
  desejado. Nenhum nome de codec, encoder ou parâmetro técnico. *(Condição 2 da exceção do
  Princípio V.)*
- **FR-038**: O modo Avançado MUST ser explicitamente opt-in e MUST NOT ser o padrão.
- **FR-039**: Todo controle técnico MUST ter um valor "Automático" funcional, e o modo Avançado
  MUST permanecer inteiramente utilizável com todos eles nesse valor. *(Condição 4.)*
- **FR-040**: Com todos os controles em "Automático", o resultado MUST ser idêntico ao do modo
  Básico com o mesmo preset. *(Condição 4, verificável.)*
- **FR-041**: A exceção MUST NOT se estender ao caminho de IA. Upscale e restauração de áudio
  continuam sem exposição técnica. *(Condição 1.)*
- **FR-042**: Todo parâmetro técnico MUST ter tooltip explicando o que ele faz em linguagem comum.

### Capacidades e licenciamento

- **FR-043**: Toda opção técnica oferecida MUST ser confirmada por sonda funcional do ambiente —
  nunca por lista de permitidos. *(Condição 3; Princípio XIII.)*
- **FR-044**: Opção indisponível MUST aparecer desabilitada com motivo, nunca omitida em silêncio
  e nunca selecionável.
- **FR-045**: Encoder GPL MUST NOT tornar-se disponível por escolha do usuário. H.264 e H.265
  MUST vir de encoder de hardware ou de encoder licenciado comercialmente. *(Condição 5;
  Licensing and Distribution Constraints.)*
- **FR-046**: Combinações incompatíveis de container, codec de vídeo e codec de áudio MUST NOT
  ser oferecidas, e MUST NOT ser aceitas e corrigidas silenciosamente.
- **FR-047**: Aceleração por hardware MUST ser oferecida quando disponível (NVENC, Quick Sync,
  AMF, VAAPI, VideoToolbox) com escolha Automático/CPU/GPU, e MUST ter fallback por CPU.
- **FR-048**: Em "Automático", qualidade e compatibilidade MUST ter prioridade sobre velocidade.

### Fila, progresso e cancelamento

- **FR-049**: Cada item da fila MUST ter estado dentre um conjunto único e padronizado, usado em
  todo o projeto.
- **FR-050**: MUST mostrar progresso individual e geral, percentual, tempo decorrido, velocidade e
  economia obtida.
- **FR-051**: O progresso MUST vir do progresso real do encoder, nunca de temporizador artificial.
- **FR-052**: MUST permitir cancelar um item e a fila inteira; o cancelamento MUST encerrar o
  processo de encoding correspondente.
- **FR-053**: MUST NOT deixar processo FFmpeg, worker ou arquivo temporário órfão após sucesso,
  erro, cancelamento ou encerramento do aplicativo.

### Comparação e preview

- **FR-054**: Imagem MUST permitir comparação lado a lado e por slider, com zoom sincronizado,
  100% e ajustar.
- **FR-055**: Vídeo MUST permitir comparar original e resultado usando o player existente do
  aplicativo.
- **FR-056**: Áudio MUST permitir alternar entre original e resultado, mostrando duração, bitrate,
  codec, tamanho e sample rate.

### Exportação

- **FR-057**: MUST permitir exportar um arquivo ou todos, e escolher a pasta de destino.
- **FR-058**: O arquivo de origem MUST continuar existindo, byte a byte idêntico, ao fim de
  qualquer operação. *(Princípio XV.)*
- **FR-059**: Sobrescrever MUST exigir instrução explícita por operação, nunca padrão e nunca
  recurso para destino ambíguo. Sobrescrever o **próprio arquivo de origem** MUST NOT ser
  possível. *(Princípio XV; resolve o conflito entre §43 e §53 da solicitação.)*
- **FR-060**: MUST permitir padrão de nomenclatura com marcadores (`{filename}`, `{quality}`,
  `{resolution}`, `{codec}`).
- **FR-061**: Em conflito de nome, MUST oferecer substituir, criar cópia, renomear ou ignorar,
  com opção de aplicar a decisão aos conflitos seguintes.

### Histórico

- **FR-062**: MUST registrar nome, data, tamanhos, redução, formato, codec, resolução, preset e
  duração de cada compressão.
- **FR-063**: MUST permitir abrir o resultado, abrir a pasta, repetir a compressão, duplicar as
  configurações, remover do histórico e limpá-lo.

### Erros e validação

- **FR-064**: MUST validar toda configuração antes de iniciar, e MUST NOT iniciar operação
  sabidamente inválida.
- **FR-065**: Mensagens de erro MUST ser compreensíveis e MUST NOT despejar a saída bruta do
  FFmpeg. Detalhe técnico MUST ficar numa área recolhível separada.
- **FR-066**: Logs técnicos estruturados MUST registrar job, arquivo, encoder, codec, parâmetros,
  duração, status e erro, e MUST NOT se misturar à interface comum.

### Qualidade estrutural

- **FR-067**: Comandos de FFmpeg MUST NOT aparecer espalhados por controllers ou componentes.
  Toda invocação passa por uma camada de abstração, estruturalmente e nunca por composição de
  string. *(Princípio XIII.)*
- **FR-068**: Nenhuma opção da interface MUST existir sem implementação funcional correspondente.
  Nenhum botão inerte, nenhum dado fictício, nenhum TODO para item desta especificação.
- **FR-069**: Funcionalidades existentes não relacionadas MUST NOT ser alteradas.
- **FR-070**: Todo texto de interface MUST ser traduzível e presente nos 11 locales. *(Princípio
  XIV.)*
- **FR-071**: Todo controle MUST ter rótulo, estado de foco, navegação por teclado e contraste
  adequado.

### Key Entities

- **MediaFile** — um arquivo importado: caminho interno, nome, tipo de mídia detectado, tamanho e
  os metadados sondados.
- **MediaMetadata** — o que a sondagem obteve: resolução, duração, codec, bitrate, FPS, canais,
  sample rate. Campos ausentes são ausentes, não zerados.
- **CompressionPreset** — um conjunto nomeado de configurações, ligado a um tipo de mídia, de
  origem interna (padrão/plataforma) ou do usuário.
- **CompressionSettings** — as configurações efetivas de um item, por tipo de mídia.
- **CompressionJob** — uma unidade de trabalho na fila: arquivo, configurações, estado, progresso,
  resultado.
- **CompressionEstimate** — tamanho previsto, economia prevista e as premissas usadas.
- **CompressionResult** — tamanhos medidos, redução, duração do processamento e caminho de saída.
- **EncoderCapability** — o que esta máquina consegue de fato executar, por codec/formato, com o
  motivo quando não consegue.
- **ExportConfiguration** — destino, padrão de nome e política de conflito.

---

## Success Criteria *(mandatory)*

- **SC-001**: Uma pessoa reduz uma imagem do tamanho original ao arquivo exportado sem abrir
  nenhum controle avançado e sem encontrar um único termo técnico.
- **SC-002**: A estimativa de tamanho fica dentro de **±20%** do resultado real em pelo menos 80%
  dos casos medidos, para cada tipo de mídia.
- **SC-003**: Quando um tamanho alvo atingível é definido, o resultado fica dentro dele em pelo
  menos 90% dos casos medidos.
- **SC-004**: O arquivo de origem permanece byte a byte idêntico em 100% das operações, incluindo
  as canceladas e as que falharam.
- **SC-005**: Nenhum processo FFmpeg, worker ou arquivo temporário sobrevive a sucesso, erro,
  cancelamento ou encerramento do aplicativo, verificado por inspeção após cada desfecho.
- **SC-006**: Nenhuma resposta de rota da Central expõe nome de codec ou encoder quando o pedido
  veio do modo Básico.
- **SC-007**: Com todos os controles avançados em "Automático", o arquivo produzido é idêntico ao
  do modo Básico com o mesmo preset — verificado por hash.
- **SC-008**: Nenhuma opção selecionável na interface falha por indisponibilidade do ambiente.
- **SC-009**: O progresso exibido corresponde ao progresso real do encoder, verificável contra a
  posição de tempo que o FFmpeg reporta.
- **SC-010**: A interface permanece responsiva durante o processamento de um arquivo de pelo menos
  1 GB.
- **SC-011**: Os 11 locales têm o mesmo conjunto de chaves, verificado pelo teste de paridade
  existente.
- **SC-012**: Toda a área de compressão é operável por teclado.

---

## Assumptions

- **A infraestrutura de compressão existente é a base.** `optimize.py` e o sistema de jobs são
  estendidos, não substituídos. A alternativa — um motor paralelo — violaria o Princípio II e
  criaria dois lugares onde a mesma coisa é feita de formas diferentes.
- **FFmpeg é a ferramenta para vídeo, áudio e animação; OpenCV para imagem.** É o que o projeto já
  usa, e o Princípio VI proíbe modelo onde ferramenta tradicional resolve.
- **A build de FFmpeg é LGPL.** Consequência já medida: `mp4` e `mov` ficam indisponíveis em
  máquina sem encoder H.264 de hardware. A Central herda isso.
- **A estimativa é estimativa.** Bitrate × duração prevê vídeo e áudio razoavelmente; imagem
  depende do conteúdo e a previsão é mais grosseira. O SC-002 fixa ±20% justamente por isso.
- **Presets do usuário e histórico são locais.** Nada de sincronização ou conta.
- **Prioridade desktop.** Notebook e telas menores funcionam; celular não é alvo.
- **"Substituir original" da §43 não será implementado como escrito.** O Princípio XV o proíbe, e
  a §53 da própria solicitação concorda com o Princípio. Fica: salvar como novo arquivo, com
  sobrescrita de **outro** arquivo mediante confirmação explícita.
- **A fatia de entrega é por mídia.** Imagem ponta a ponta primeiro, depois vídeo, áudio e
  GIF — decidido com o solicitante em 2026-08-21.

---

## Out of Scope

Registrado para que a ausência seja decisão e não esquecimento:

- Edição de conteúdo (corte, rotação, filtros) — é o editor, não a Central.
- Upscale ou qualquer processamento por modelo dentro da Central (Princípio VI).
- Sincronização de presets ou histórico entre máquinas.
- Formatos de mídia além dos nomeados, embora a arquitetura os acomode (FR-004).
- Suporte a celular.
