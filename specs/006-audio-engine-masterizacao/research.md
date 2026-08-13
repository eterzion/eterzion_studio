# Research — Audio Engine (Masterização e Restauração Híbrida)

Base: spec.md, a auditoria técnica do SonicMaster feita nesta sessão, o Princípio XII da
constituição (v2.5.0), e leitura direta do código já existente (`app/processing.py`'s pipeline de
áudio, `app/licensing.py`'s `_CONTENT_TYPE_IMPLEMENTATIONS`, `app/jobs.py`'s `WorkerSupervisor`).

## Achado prévio: já existe um pipeline de áudio parcial, e uma parte está quebrada

Antes de decidir a arquitetura nova, é preciso registrar o que já existe, porque isso muda o
escopo real do trabalho — não é "construir do zero":

- `app/processing.py` já tem `process(input_path, engine_ref, output_path, ...)`: converte para
  WAV, roda uma cadeia DSP fixa via ffmpeg (`afftdn,deesser,acompressor,loudnorm=I=-16:TP=-1.5:LRA=11`),
  depois despacha para `_enhance_speech` (audiosronnx) ou `_enhance_music` (SonicMaster) por
  `engine_ref`.
- `app/licensing.py`'s `_CONTENT_TYPE_IMPLEMENTATIONS['music']` já resolve `content_type='music'`
  para `engine_ref='sonicmaster'`, com `license_status='approved_conditional'` e o texto exato do
  risco do VAE já registrado como dado, não só como comentário.
- **`_enhance_music` chama o script errado.** Ela invoca `inference_fullsong.py` com flags
  `--input`/`--output`/`--prompt`/`--fs` — mas a auditoria confirmou que `inference_fullsong.py`
  **não tem esses argumentos** (é dataset/JSONL-driven, com caminhos absolutos dos autores). O
  script com essa assinatura exata é `infer_single.py`. Isso nunca funcionou como está escrito.
  Corrigir essa chamada é parte obrigatória deste trabalho, não um efeito colateral.

## Decisão 1 — Layout físico: subpacote `app/audio_engine/`, arquivos por domínio (não por subpasta)

**Decision**: criar `api/astros_upscale_api/app/audio_engine/` como subpacote, com arquivos
**flat** dentro dele — um arquivo por domínio real, não uma subpasta por camada da árvore que o
pedido original desenhou:

```
app/audio_engine/
├── __init__.py
├── analyzer.py     # Audio Analyzer + Problem Detector (medição objetiva + detecção de problemas)
├── dsp.py           # todo DSP determinístico: loudness, EQ, dinâmica, estéreo, limiter, dithering
├── mastering.py      # MasteringEngine: orquestra Auto Master / Restore / Restore+Master
├── quality.py         # Quality Guard
└── ai_provider.py     # AudioRestorationProvider (interface) + SonicMasterProvider + geração de prompt
```

**Rationale**: duas forças em tensão, resolvidas a favor do Princípio XI. (1) O volume real de
código de um pipeline de mastering completo — análise, DSP com múltiplos estágios, orquestração de
modos, validação de qualidade, provider de IA — é grande o suficiente para justificar seu próprio
subpacote dentro de `app/` (não cabe razoavelmente dentro de `processing.py`, que já tem 800+
linhas cobrindo imagem/vídeo). (2) Mas a estrutura de 6 subpastas pedida originalmente
(`analyzer/`, `dsp/`, `mastering/`, `quality/`, `encoder/`, `ai/`) reproduziria exatamente o
padrão que o Princípio XI já rejeitou uma vez neste projeto — `app/core/` tinha 18 arquivos, um
por classe/conceito, sem benefício de navegação real. Cada uma dessas 6 "camadas" é, na prática,
um domínio coeso o bastante para ser **um arquivo**, não uma pasta com múltiplos arquivos por
tipo de filtro/métrica. `encoder/` como pasta própria não se justifica: exportar o áudio final é
uma função dentro de `dsp.py` (mesmo padrão de reencode que `processing.py` já usa para
imagem/vídeo), não um domínio separado. `ai/`'s três arquivos (`provider.py`/`sonicmaster.py`/
`prompts.py`) colapsam em um só (`ai_provider.py`) pela mesma razão que `licensing.py` já bundla
gate+cache+registry+resolver+offline-tolerance e `security.py` bundla cinco preocupações — a
geração de prompt é lógica específica de um provider (`SonicMasterProvider`), não um domínio
próprio.

**Alternatives considered**:
- *Um único arquivo `audio_mastering.py` gigante* — rejeitado: análise, DSP, orquestração,
  qualidade e o provider de IA são responsabilidades genuinamente separáveis e testáveis de forma
  independente (a cláusula de exceção do próprio Princípio XI/X), diferente do caso de
  `app/core/` original.
- *A árvore de 6 subpastas exatamente como pedida* — rejeitada pelas razões acima: reproduziria a
  fragmentação que a constituição já corrigiu duas vezes neste projeto.
- *Arquivos soltos direto em `app/` (`audio_analyzer.py`, `audio_dsp.py`, ...) sem subpacote* —
  rejeitada: o número de arquivos (5) mais o código de terceiro vendorizado (decisão 4) justifica
  um namespace próprio para não poluir `app/`'s nível superior, que já tem `processing.py`,
  `jobs.py`, `licensing.py`, `security.py`, `routes.py`, `schemas.py` — mais 5+ arquivos soltos
  tornaria esse nível difícil de escanear visualmente.

## Decisão 2 — Contrato HTTP: estender a rota de job existente, não criar uma nova

**Decision**: os novos modos (Masterização Automática, Restaurar, Restaurar + Masterizar) e o
parâmetro de intensidade de IA entram como campos **opcionais e aditivos** no schema de criação de
job já existente (`LocalJobRequest`/`MediaRequest`), usados apenas quando `media_type='audio'` e
`content_type='music'`. Nenhuma rota nova é criada; `POST /jobs/local`, `GET /jobs/{id}` e o
WebSocket de progresso continuam exatamente como estão hoje para todo o resto (imagem, vídeo,
áudio de fala, e o comportamento padrão atual de áudio de música quando os novos campos não são
enviados).

```
audio_mode: 'enhance' | 'auto_master' | 'restore' | 'restore_master' | None  (default: 'enhance')
ai_strength: int | None  # 0-100, default a definir em data-model.md
```

Quando `audio_mode` é omitido ou `'enhance'`, o comportamento é **idêntico ao pipeline atual**
(DSP fixo + um passe do engine do content_type) — isso preserva o contrato existente por completo,
conforme o Princípio XI exige.

**Rationale**: o job de áudio já existe, já tem `content_type`, já resolve `engine_ref` via
licenciamento, já tem workers/progresso/cancelamento funcionando. Criar uma rota paralela
duplicaria toda essa infraestrutura (validação, gate de licença, WebSocket, histórico) só para
expor o que é, na prática, uma variação de parâmetros do mesmo tipo de job — exatamente o problema
que o Princípio XI e o Princípio II (Reuse First) existem para evitar.

**Alternatives considered**:
- *Nova operação* (`operation='master'` em vez de `'enhance'`) — rejeitada: obrigaria duplicar toda
  a validação/gate de licença/schema de progresso já implementados para `operation='enhance'`, sem
  ganho real — os novos modos são variações de como o `enhance` de música é executado, não uma
  operação HTTP conceitualmente diferente.
- *Rota dedicada* (`POST /jobs/local/audio-master`) — rejeitada pela mesma razão, mais o custo de
  manter dois caminhos de código para o gate de licença.

## Decisão 3 — Worker isolado: reaproveitar o padrão do `WorkerSupervisor`, com interpretador configurável

**Decision**: o `SonicMasterProvider` roda num processo filho isolado, seguindo o mesmo padrão já
implementado em `app/jobs.py` (`WorkerSupervisor`: named pipe local via
`multiprocessing.connection`, authkey efêmero, ambiente restrito) — mas em uma **segunda
instância dedicada**, nunca compartilhando a instância singleton já existente
(`app/jobs.py`'s `get_supervisor()`/`_supervisor`, hoje reusada por todo job de imagem/vídeo).

**Achado durante `/speckit.analyze`**: `WorkerSupervisor` é hoje um singleton de processo único,
reaproveitado entre chamadas (`get_supervisor()` retorna sempre a mesma instância/processo já
vivo). Parametrizar `_spawn()` para escolher o interpretador por job — como uma primeira versão
desta decisão propunha — quebraria esse padrão: o mesmo processo persistente não pode servir, ao
mesmo tempo, o ambiente principal (upscale de imagem/vídeo, `sys.executable`) e o ambiente isolado
do audio-worker (torch==2.4.0 e companhia) — um job de imagem reusaria um processo que só tem as
dependências de áudio, ou vice-versa.

A mudança concreta, corrigida: `WorkerSupervisor` (a classe) MUST aceitar um parâmetro de
interpretador no `__init__`/`_spawn()` (default `sys.executable`, preservando o comportamento
atual), e `app/jobs.py` ganha um **segundo getter/singleton dedicado** —
`get_audio_worker_supervisor()` — que instancia `WorkerSupervisor` com o interpretador do
audio-worker (`ASTROS_AUDIO_WORKER_PYTHON`), como um processo persistente **separado e paralelo**
ao supervisor de imagem/vídeo, nunca a mesma instância. `audio_engine/ai_provider.py` só conhece
`get_audio_worker_supervisor()`, nunca `get_supervisor()`. O resto do mecanismo — listener local,
authkey, ambiente restrito, encerramento/cleanup determinístico — é reaproveitado tal como está,
só instanciado duas vezes com parâmetros diferentes em vez de uma vez com comportamento variável.

**Rationale**: aplicação direta do Princípio II (Reuse First — reusar, não recriar isolamento de
processo do zero) equilibrada com FR-023/Princípio XII (dependências de IA isoladas do ambiente
principal). O `_enhance_music` atual já contorna esse problema de forma ad-hoc (chama
`subprocess.run(['python', script, ...])`, dependendo de qual `python` está no PATH do operador,
sem isolamento real de ambiente nem reuso do mecanismo de worker) — a mudança aqui formaliza e
integra esse isolamento ao mecanismo já testado, em vez de manter dois padrões de subprocess
diferentes no mesmo arquivo.

**Alternatives considered**:
- *Rodar o SonicMaster no mesmo interpretador do worker de upscale já existente* — rejeitada:
  exigiria instalar torch==2.4.0/diffusers==0.30.0/transformers==4.44.0 no ambiente principal,
  colidindo com as versões já usadas por upscale de imagem/vídeo (torch atual do projeto é
  2.13.0) e violando FR-023 diretamente.
- *Mecanismo de IPC totalmente novo (ex. fila HTTP local, gRPC)* — rejeitada: mais complexidade
  para resolver um problema que já tem solução funcionando (named pipe + authkey); o único ajuste
  necessário é o caminho do interpretador, não o protocolo de comunicação.
- *Parametrizar o interpretador na instância singleton já existente (`get_supervisor()`), sem uma
  segunda instância* — rejeitada durante `/speckit.analyze`: `WorkerSupervisor` hoje é reaproveitado
  como um único processo persistente entre chamadas; fazer esse mesmo processo trocar de
  interpretador por job quebraria jobs de imagem/vídeo em andamento ou subsequentes (o processo já
  vivo não tem as dependências do ambiente que não foi usado para spawná-lo). Uma segunda instância
  dedicada evita essa colisão sem abrir mão do reuso dentro de cada categoria de job.

## Decisão 4 — Dependências e código de terceiro: extra quebrada corrigida, código vendorizado, ambiente isolado

**Decision**:

1. **Corrigir `api/pyproject.toml` imediatamente**: remover a linha
   `"sonicmaster @ git+https://github.com/AMAAI-Lab/SonicMaster.git"` da extra `[audio]` — ela
   nunca instalou (confirmado na auditoria: sem `setup.py`/`pyproject.toml` no repositório de
   origem). A extra `[audio]` passa a cobrir só `audiosronnx` e `astros-audio-enhance` (que já
   funcionam), restaurando a instalação de "Melhoria de voz" imediatamente como efeito colateral
   necessário deste trabalho.
2. **Vendorizar um subconjunto mínimo de inferência do SonicMaster** em
   `api/astros_upscale_api/vendor/sonicmaster/` — apenas os arquivos necessários para inferência
   (baseados em `model.py`, `utils.py`, `configs/tangoflux_config.yaml`, e uma versão adaptada de
   `infer_single.py` como ponto de entrada, já que é o único script sem caminhos hardcoded).
   Código de treinamento (`train_ptload_inference.py`, `preencode_latents_acce2.py`) **não** é
   vendorizado — a auditoria já cobriu a arquitetura que eles revelam, não é necessário para rodar
   inferência. O arquivo `LICENSE` (Apache-2.0) original é copiado junto, com um `NOTICE`/`README`
   próprio documentando URL de origem e commit exato, satisfazendo a obrigação de atribuição do
   Princípio IV/XII.
3. **Novo arquivo de dependências isolado**, `api/astros_upscale_api/audio_worker_requirements.txt`
   — as versões exatas pinadas por `requirements_sonic.txt` do SonicMaster (`torch==2.4.0`,
   `torchaudio==2.4.0`, `torchvision==0.19.0`, `transformers==4.44.0`, `diffusers==0.30.0`,
   `torchlibrosa==0.1.0`, `librosa==0.11.0`), **exceto** `accelerate`, `datasets`, `wandb`
   (só treino) e `laion_clap` (só avaliação — não importado por `model.py`, confirmado na
   auditoria). Instalado num venv dedicado, separado do `.venv` raiz do projeto — não entra na
   instalação padrão do backend.
4. **Estratégia de compatibilidade**: não tentar forçar o SonicMaster a rodar contra o
   `torch==2.13.0` já usado pelo resto do projeto. O ambiente do audio-worker usa exatamente as
   versões que o SonicMaster já testa contra (pinadas no próprio `requirements_sonic.txt`),
   eliminando o risco de incompatibilidade em vez de tentar resolvê-lo — consistente com FR-023,
   que já exige esse isolamento independentemente da questão de versão. Testar se uma versão mais
   nova de `torch`/`diffusers` também funciona é um follow-up de otimização (poderia simplificar
   para um único ambiente no futuro), não um bloqueador desta implementação.
5. **Checkpoint (3,29 GB) e VAE do Stable Audio Open**: não vendorizados nem baixados no build —
   baixados sob demanda no primeiro uso real (lazy load, FR-019), reaproveitando o padrão de
   download-com-checksum já usado para modelos de imagem/vídeo (`astros_upscale.processing`'s
   `download_with_fallback`). O VAE exige autenticação (`HF_TOKEN`/aceite dos termos da Stability
   AI) — tratado como parte da configuração inicial do operador (documentado nas Assumptions da
   spec), não resolvido silenciosamente em runtime.

**Rationale**: cada peça isolada resolve exatamente um risco já identificado na auditoria
(instalação quebrada, incompatibilidade de versão, contaminação do ambiente principal, atribuição
de licença) sem introduzir complexidade não pedida.

**Alternatives considered**:
- *`pip install` direto de um fork nosso do SonicMaster com `setup.py` adicionado* — rejeitada por
  ora: manter um fork publicado é mais trabalho de manutenção contínua do que vendorizar o
  subconjunto de inferência já necessário; pode ser revisitado depois se o projeto precisar
  atualizar o SonicMaster com frequência.
- *Ambiente único compartilhado, forçando upgrade do restante do projeto para torch==2.4.0* —
  rejeitada: downgrade do torch usado por upscale de imagem/vídeo para uma versão de 2024 não é
  aceitável (Princípio III — Performance First, e reverteria trabalho de atualização de
  dependências já feito nesta mesma sessão).

## Decisão 5 — Esquemas: request/response no `schemas.py` existente; tipos internos nos próprios módulos

**Decision**: os campos de request/response que cruzam a fronteira HTTP (novos campos em
`LocalJobRequest`, e os dados de análise/veredito expostos no status do job) entram no
`app/schemas.py` já existente, seguindo a regra explícita do Princípio XI de que schemas
pertencem todos a um único arquivo. Tipos que só circulam **dentro** do audio-engine (ex. a
estrutura interna completa do Relatório de Análise antes de ser resumida para o cliente) são
dataclasses simples dentro de `analyzer.py`/`quality.py`, não expostos em `schemas.py`.

**Rationale**: aplicação direta da regra já escrita no Princípio XI — não criar um `schemas.py`
paralelo dentro de `audio_engine/` só porque o domínio é novo.

## Decisão 6 — DSP determinístico: ffmpeg (já em uso) + `pyloudnorm` para medição independente

**Decision**: manter DSP determinístico majoritariamente em filtros ffmpeg (LGPL-safe, já a base
de `apply_dsp_chain` hoje — `afftdn`, `deesser`, `acompressor`, `loudnorm`), estendido com filtros
adicionais LGPL para os requisitos que faltam: `firequalizer`/`equalizer` (EQ paramétrica),
`compand` (compressão/multibanda), `alimiter` (limitação), `stereotools` (correção/análise
estéreo), `dither` (dithering na saída). Para a **medição objetiva independente** que o Analyzer e
o Quality Guard precisam (FR-001, FR-007) — LUFS/True Peak/RMS calculados em Python, não confiando
apenas no que o `loudnorm` do ffmpeg reporta internamente — usar `pyloudnorm` (MIT, implementa
ITU-R BS.1770-4; API confirmada via Context7: `pyln.Meter(rate).integrated_loudness(data)` e
`pyln.normalize.loudness(data, current, target)`), já listado como aprovado em
`docs/models/MODEL_LICENSES.md` §4.

**Rationale**: nenhuma dependência nova pesada é necessária para o DSP determinístico — o projeto
já usa ffmpeg como base LGPL para toda a cadeia de áudio, e `pyloudnorm` já está pré-aprovado por
licença e é leve (sem dependência de ML). Ter a medição em Python, separada da aplicação do
`loudnorm` do ffmpeg, é o que permite ao Quality Guard comparar objetivamente antes/depois de cada
etapa (incluindo a etapa de IA) sem depender de o próprio ffmpeg "se auto-avaliar".

**Alternatives considered**:
- *`ffmpeg-normalize` (wrapper Python de alto nível)* — rejeitada: adiciona uma dependência
  externa para orquestrar exatamente o que `apply_dsp_chain` já faz diretamente com `ffmpeg-python`
  (já em uso no projeto).
- *Biblioteca DSP totalmente em Python (`pedalboard`, `scipy.signal` puro) substituindo ffmpeg* —
  rejeitada: reescreveria uma cadeia já funcional e testada (`test_audio_processor.py`) sem
  benefício claro, contra o Princípio II.

## Resumo de riscos carregados para `data-model.md`/`tasks.md`

- Correção do bug real em `_enhance_music` (script errado) é pré-requisito antes de qualquer modo
  novo funcionar — vira uma tarefa própria, não apenas um efeito colateral.
- VRAM/tempo de inferência do SonicMaster permanecem não medidos até a primeira execução real
  contra o checkpoint publicado — tasks.md deve incluir uma tarefa de medição explícita antes de
  qualquer promessa de desempenho na UI.
- A obrigação de `HF_TOKEN`/aceite de termos para o VAE gated é uma dependência operacional, não
  técnica — deve ser documentada no guia de configuração do audio-worker (quickstart.md/tasks.md),
  não resolvida em código.
