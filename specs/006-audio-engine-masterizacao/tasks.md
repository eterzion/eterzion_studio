# Tasks: Audio Engine — Masterização e Restauração Híbrida (DSP + IA)

**Input**: Design documents from `/specs/006-audio-engine-masterizacao/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/README.md, quickstart.md

**Tests**: incluídos — Princípio VIII (Tests Required) exige testes reais para toda migração/feature
nova; cada tarefa de código tem uma tarefa de teste correspondente, sem mock do processamento real.

**Organization**: agrupadas por user story (P1–P4), na ordem de dependência real estabelecida em
plan.md — Setup corrige o que já está quebrado hoje; Fundação é a infraestrutura de isolamento que
tudo mais depende; US1 é o MVP completo (masterização automática); US2–US4 estendem US1.

## Format: `[ID] [P?] [Story] Description`

## Path Conventions

Todos os caminhos são relativos a `api/`, seguindo `plan.md`'s Project Structure.

---

## Phase 1: Setup — corrigir o que já está quebrado

**Purpose**: dois bugs reais já presentes no código, bloqueadores para qualquer validação de
ponta a ponta desta feature e, no caso de T001, um bug que já afeta o produto hoje
independentemente desta feature.

- [x] T001 Remover a linha `"sonicmaster @ git+https://github.com/AMAAI-Lab/SonicMaster.git"` da
  extra `[audio]` em `api/pyproject.toml` — ela nunca instalou (repositório sem `setup.py`/
  `pyproject.toml`, confirmado na auditoria). A extra passa a listar só `audiosronnx` e
  `astros-audio-enhance`.
- [x] T002 [P] Teste: `pip install -e ".[audio]"` (ou `uv pip install -e ".[audio]"`) completa sem
  erro num venv limpo, e `python -c "import audiosronnx"` funciona depois — confirma que
  "Melhoria de voz" (quebrada hoje pelo mesmo motivo, achado nesta sessão) volta a funcionar como
  efeito colateral direto de T001.
- [x] T003 Corrigir `_enhance_music` em `astros_upscale_api/app/processing.py`: trocar a chamada
  de `inference_fullsong.py` (que não aceita `--input`/`--output`/`--prompt` — confirmado na
  auditoria) pelo script de inferência único vendorizado em T005
  (`vendor/sonicmaster/infer.py`), mantendo a mesma assinatura de função
  `(input_wav, output_wav) -> None` já usada por `_ENGINE_ENHANCERS['sonicmaster']`.
- [x] T004 [P] Teste de `_enhance_music` corrigida em
  `astros_upscale_api/tests/test_audio_processor.py`, usando um stub/fake do script de inferência
  (o worker real com GPU/checkpoint é `slow`, fora do CI padrão) — confirma que a função chama o
  script certo com os argumentos certos, sem exercitar o modelo de verdade.

**Checkpoint**: `pytest -k "audio_processor"` verde; `pip install astros_upscale[audio]` funciona.

---

## Phase 2: Foundational — isolamento do worker de IA (bloqueia US1–US4)

**Purpose**: infraestrutura de isolamento de processo/dependências que qualquer uso real do
SonicMaster depende (Princípio XII, Decisões 3–4 de research.md). Nenhuma user story pode ser
validada de ponta a ponta com IA real sem esta fase.

**⚠️ CRITICAL**: nenhuma tarefa de US1–US4 que envolva o `SonicMasterProvider` de verdade pode
começar antes desta fase estar completa — mas `analyzer.py`/`dsp.py`/`quality.py` (que não
dependem do provider) podem ser feitos em paralelo com esta fase se houver capacidade.

- [x] T005 Vendorizar o subconjunto mínimo de inferência do SonicMaster em
  `astros_upscale_api/vendor/sonicmaster/`: `model.py`, `utils.py`,
  `configs/tangoflux_config.yaml` (adaptados do repositório original), `infer.py` (baseado em
  `infer_single.py`, único script sem caminhos hardcoded), `LICENSE` (Apache-2.0 original
  copiado), `NOTICE.md` (URL de origem `github.com/AMAAI-Lab/SonicMaster`, commit exato usado,
  atribuição aos autores — Princípio IV/XII).
- [x] T006 [P] Criar `astros_upscale_api/audio_worker_requirements.txt` com os pins exatos de
  `requirements_sonic.txt` do SonicMaster — `torch==2.4.0`, `torchaudio==2.4.0`,
  `torchvision==0.19.0`, `transformers==4.44.0`, `diffusers==0.30.0`, `torchlibrosa==0.1.0`,
  `librosa==0.11.0` — excluindo `accelerate`, `datasets`, `wandb` (só treino) e `laion_clap` (só
  avaliação, não importado por `model.py`).
- [x] T007 [P] Estender `astros_upscale_api/app/config.py` com o campo
  `audio_worker_python: str = ''` (variável `ASTROS_AUDIO_WORKER_PYTHON`) — vazio por padrão,
  mesma convenção de "vazio = recurso opcional desligado" já usada por `licensing_service_url`.
- [x] T008 **(corrigida em `/speckit.analyze` — ver research.md Decisão 3)** Estender
  `WorkerSupervisor.__init__`/`_spawn()` em `astros_upscale_api/app/jobs.py` para aceitar um
  caminho de interpretador opcional no construtor (default `sys.executable`, preservando o
  comportamento atual byte a byte quando omitido) — sem tocar no protocolo de IPC (named pipe/
  authkey/ambiente restrito), que continua idêntico. **Não** altera `get_supervisor()` (o
  singleton de imagem/vídeo, que continua sempre com `sys.executable`).
- [x] T008a Adicionar `get_audio_worker_supervisor()` em `astros_upscale_api/app/jobs.py`: um
  segundo singleton global, **instância separada** de `get_supervisor()`, construído com
  `settings.audio_worker_python`. `audio_engine/ai_provider.py` (T018) usa exclusivamente este
  getter — nunca `get_supervisor()`. Depende de T008.
- [x] T009 [P] Teste de regressão: `get_supervisor()` (imagem/vídeo) continua spawnando com
  `sys.executable` exatamente como hoje, independentemente de `ASTROS_AUDIO_WORKER_PYTHON` estar
  setado ou não — confirma que as duas instâncias são genuinamente independentes, não a mesma
  instância com comportamento condicional.
- [x] T010 [P] Teste: `get_audio_worker_supervisor()` spawna com o interpretador de
  `settings.audio_worker_python` (num teste, pode apontar para o próprio `sys.executable` só para
  confirmar que o parâmetro é respeitado) — e que é uma instância distinta de `get_supervisor()`
  (`get_audio_worker_supervisor() is not get_supervisor()`).

**Checkpoint**: `vendor/sonicmaster/` existe com `LICENSE`+`NOTICE.md`; `WorkerSupervisor` aceita
interpretador configurável sem quebrar o comportamento default; testes T009/T010 verdes.

---

## Phase 3: User Story 1 — Masterização automática (Priority: P1) 🎯 MVP

**Goal**: uma pessoa envia uma faixa e recebe uma versão masterizada automaticamente, com IA
acionada só quando a análise indicar necessidade real, e a saída sempre validada antes de virar
resultado final.

**Independent Test**: enviar uma faixa via `POST /jobs/local` com `audio_mode: "auto_master"` e
confirmar loudness/clipping do resultado, conforme quickstart.md Cenário 1.

### Tests for User Story 1 ⚠️

> Escrever estes testes primeiro; devem falhar antes da implementação correspondente existir.

- [x] T011 [P] [US1] Teste de `audio_engine/analyzer.py` em
  `astros_upscale_api/tests/test_audio_engine_analyzer.py`: áudio sintético com clipping severo
  introduzido deliberadamente → `ProblemDetection.clipping_severity` alto e
  `requires_ai_restoration=True`; áudio sintético limpo → todas as severidades baixas e
  `requires_ai_restoration=False`.
- [x] T012 [P] [US1] Teste de `audio_engine/dsp.py` em
  `astros_upscale_api/tests/test_audio_engine_dsp.py`: mede loudness real antes/depois via
  `pyloudnorm` (não confia só no relatório do próprio ffmpeg) e confirma que o resultado está
  dentro do alvo configurado; confirma ausência de clipping na saída para uma entrada com pico
  moderado.
- [x] T013 [P] [US1] Teste de `audio_engine/quality.py` em
  `astros_upscale_api/tests/test_audio_engine_quality.py`: dado um `AudioAnalysisReport` "antes" e
  um "depois" sintético com regressão clara (ex. `true_peak_db` piorou além do limiar), o veredito
  é `rejected` ou `reduced`, nunca `accepted`; dado um par sem regressão, o veredito é `accepted`.

### Implementation for User Story 1

- [x] T014 [P] [US1] Criar `astros_upscale_api/app/audio_engine/__init__.py` (pacote vazio).
- [x] T015 [US1] Implementar `AudioAnalysisReport`, `ProblemDetection` e o Problem Detector em
  `astros_upscale_api/app/audio_engine/analyzer.py` (data-model.md) — medição via `pyloudnorm` +
  DSP básico de análise (correlação estéreo, balanço espectral, DC offset, clipping ratio).
  Depende de T011 existir (falhando) e de T014.
- [x] T016 [US1] Implementar a cadeia DSP determinística completa em
  `astros_upscale_api/app/audio_engine/dsp.py` — estende `apply_dsp_chain` já existente em
  `processing.py` com os filtros ffmpeg que faltam (EQ paramétrica/dinâmica, compressão
  multibanda, limiter, correção estéreo, dithering na saída), reaproveitando `run_ffmpeg` já
  existente. Depende de T012 (falhando) e T014.
- [x] T017 [US1] Implementar o Quality Guard em `astros_upscale_api/app/audio_engine/quality.py`
  (compara dois `AudioAnalysisReport`, retorna `QualityVerdict` — data-model.md). Depende de T013
  (falhando), T015 (usa `AudioAnalysisReport`).
- [x] T018 [US1] Implementar `AudioRestorationProvider` (protocolo) e `SonicMasterProvider` em
  `astros_upscale_api/app/audio_engine/ai_provider.py`: `initialize()`/`shutdown()` gerenciam o
  worker isolado (via `WorkerSupervisor` parametrizado, T008); `restore()` invoca
  `vendor/sonicmaster/infer.py` no processo isolado; geração de prompt a partir de
  `ProblemDetection.dominant_problems` (FR-005) vive aqui. Depende de T005–T008 (Fundação) e T015
  (tipo `ProblemDetection`).
- [x] T019 [P] [US1] Teste de `ai_provider.py` em
  `astros_upscale_api/tests/test_audio_engine_ai_provider.py`, com um fake/stub do worker isolado
  (sem GPU/checkpoint real) — confirma que `restore()` monta a instrução esperada a partir de um
  `ProblemDetection` de teste, e que `is_available()` retorna `False` quando o interpretador
  configurado não existe.
- [x] T018a [US1] (FR-019) Teste de lazy loading/reuso em `test_audio_engine_ai_provider.py`: o
  `SonicMasterProvider` não inicializa o worker no `__init__`, só em `initialize()`/no primeiro
  `restore()` real; duas chamadas de `restore()` seguidas no mesmo provider **não** re-spawnam o
  worker isolado (confirma reuso, não recarregamento a cada operação). Depende de T018.
- [x] T020 [US1] Implementar `MasteringEngine` em `astros_upscale_api/app/audio_engine/mastering.py`
  — modo `auto_master`: Analyze → Detect → (SonicMaster se `requires_ai_restoration`) → Analyze →
  DSP de masterização → Quality Guard → saída. Depende de T015, T016, T017, T018.
- [x] T020a [US1] (FR-013) Implementar o mapeamento `ai_strength` → estratégia de restauração em
  `mastering.py` (tabela de data-model.md: 0=nenhum força DSP-only mesmo com problema detectado;
  1-25 conservador eleva o limiar de acionamento e reduz passos de inferência; 26-50 padrão; 51-75
  reduz o limiar de acionamento e aumenta passos; 76-100 limiar mínimo e máximo de passos) — nunca
  como multiplicador linear sobre o resultado. Depende de T020.
- [x] T021 [US1] Teste de `mastering.py` modo `auto_master` em
  `astros_upscale_api/tests/test_audio_engine_mastering.py`, com `SonicMasterProvider` trocado por
  um fake: entrada sem problema detectável → provider de IA nunca é chamado (confirma FR-002);
  entrada com clipping sintético → provider é chamado e o resultado passa pelo Quality Guard.
  Depende de T020.
- [x] T021a [US1] (FR-013) Teste do mapeamento `ai_strength` → estratégia: `ai_strength=0` nunca
  aciona o provider de IA mesmo com `requires_ai_restoration=True`; `ai_strength=100` aciona com o
  limiar mínimo/máximo de passos; confirma que o resultado não é simplesmente o mesmo áudio com
  ganho diferente aplicado (não é um multiplicador). Depende de T020a.
- [x] T021b [US1] (FR-009/SC-006) Teste de preservação de intenção musical em
  `test_audio_engine_mastering.py`: numa faixa sintética **sem** nenhum problema detectável
  (`requires_ai_restoration=False`), o resultado de `auto_master` não altera perceptivelmente
  balanço espectral/correlação estéreo além de uma tolerância mínima em relação ao original — usa
  os mesmos campos objetivos de `AudioAnalysisReport` (T015) para a comparação, não avaliação
  subjetiva. Depende de T015, T020.
- [x] T022 [US1] Estender `MediaRequest` e `JobStatus` em `astros_upscale_api/app/schemas.py`:
  `audio_mode: Literal['enhance','auto_master','restore','restore_master'] | None = None` e
  `ai_strength: int | None = None` (0–100) em `MediaRequest`; `audio_analysis`/`quality_verdict`
  opcionais em `JobStatus` (contracts/README.md). **Sub-verificação obrigatória**: um payload sem
  `audio_mode` continua validando e serializando exatamente como antes (nenhum campo novo
  obrigatório, nenhum default que mude o payload de resposta quando ausente).
- [x] T023 [P] [US1] Teste de schema em `astros_upscale_api/tests/test_schemas.py` (ou arquivo de
  teste de schema já existente): payload de `MediaRequest` sem `audio_mode`/`ai_strength` continua
  válido e produz o mesmo objeto de antes (regressão); payload com `audio_mode='auto_master'` e
  `ai_strength=75` valida corretamente; valores fora de `0..100` para `ai_strength` são rejeitados.
- [x] T024 [US1] Integrar em `astros_upscale_api/app/processing.py`: quando
  `content_type == 'music'` e `audio_mode` (do request) não é `None`/`'enhance'`, despachar para
  `audio_engine.mastering.MasteringEngine` em vez do caminho `_ENGINE_ENHANCERS['sonicmaster']`
  atual; quando `audio_mode` é `None`/`'enhance'`, o caminho antigo (`process()` já existente,
  agora com T003 corrigido) permanece exatamente como está, byte a byte. Depende de T020, T022.
- [x] T025 [US1] Teste de compatibilidade retroativa (quickstart.md Cenário 4) em
  `astros_upscale_api/tests/test_routes_jobs.py` (ou arquivo equivalente já existente para rotas
  de job): uma requisição `POST /jobs/local` de música **sem** `audio_mode` produz exatamente o
  mesmo `JobStatus` (mesmos campos, sem os novos) que produzia antes desta feature — este teste é
  a validação de regressão mais importante da fase e deve ser escrito e rodado logo depois de
  T024, antes de qualquer teste de caminho novo.
- [x] T026 [US1] Teste de ponta a ponta (quickstart.md Cenário 1) em
  `astros_upscale_api/tests/test_routes_jobs.py`: `POST /jobs/local` com
  `audio_mode='auto_master'`, provider de IA trocado por fake — job completa,
  `audio_analysis`/`quality_verdict` presentes na resposta quando a IA foi acionada, ausentes
  quando não foi.

**Checkpoint**: User Story 1 completa e testável de forma independente — masterização automática
funciona ponta a ponta com um provider fake; T025 (regressão) verde é obrigatório antes de
prosseguir.

---

## Phase 4: User Story 2 — Restaurar / Restaurar + Masterizar (Priority: P2)

**Goal**: modos que priorizam correção de defeitos sobre loudness de masterização, com a opção de
encadear masterização depois.

**Independent Test**: quickstart.md Cenários 2 (parcial) e 3.

### Tests for User Story 2 ⚠️

- [x] T027 [P] [US2] Teste de modo `restore` em `test_audio_engine_mastering.py`: resultado não é
  levado a um alvo de loudness de masterização (compara `integrated_lufs` do resultado contra o
  original, dentro de uma tolerância — não contra o alvo de masterização usado em `auto_master`).
- [x] T028 [P] [US2] Teste de modo `restore_master` (quickstart.md Cenário 2, segunda etapa):
  aplicar `restore` e depois `auto_master` sobre o resultado produz uma saída equivalente a rodar
  `restore_master` diretamente.
- [x] T029 [P] [US2] Teste de rejeição pelo Quality Guard (quickstart.md Cenário 3): com um fake
  de `SonicMasterProvider` configurado para devolver um resultado que regride métricas
  objetivas, o `output_path` final MUST NOT ser a saída bruta do provider — deve refletir o
  fallback/correção DSP em vez disso.

### Implementation for User Story 2

- [x] T030 [US2] Adicionar o modo `restore` em `audio_engine/mastering.py`: Analyze → (SonicMaster
  se necessário) → Corrective DSP → Quality Guard → saída, sem a etapa de masterização
  (loudness-alvo/limiter de masterização) do modo `auto_master`. Depende de T020 (Phase 3).
- [x] T031 [US2] Adicionar o modo `restore_master` em `audio_engine/mastering.py`: reaproveita a
  lógica de `restore` seguida da lógica de masterização de `auto_master` sobre o resultado
  restaurado (sem duplicar a etapa de análise/restauração). Depende de T030.
- [x] T032 [US2] Garantir (código + comentário) que a rejeição do Quality Guard (T017) é aplicada
  igualmente dentro de `restore`/`restore_master`, não só em `auto_master` — mesma função
  `MasteringEngine._apply_quality_guard`, chamada nos três modos.

**Checkpoint**: User Stories 1 e 2 funcionam de forma independente e conjunta.

---

## Phase 5: User Story 3 — Música completa sem junções audíveis (Priority: P3)

**Goal**: processar faixas mais longas que a janela interna de inferência sem descontinuidade
perceptível nas junções.

**Independent Test**: quickstart.md — enviar uma faixa mais longa que a janela e inspecionar as
junções internas.

### Tests for User Story 3 ⚠️

- [x] T033 [P] [US3] Teste objetivo de continuidade em
  `astros_upscale_api/tests/test_audio_engine_ai_provider.py`: gerar um áudio sintético mais longo
  que a janela de chunk, processar via `restore_full_song` com um fake de inferência determinístico,
  e medir energia/fase na região de overlap entre chunks reconstruídos — sem descontinuidade acima
  de um limiar definido (métrica objetiva, não escuta subjetiva).
- [x] T034 [P] [US3] Teste: áudio sintético mais curto que a janela mínima de chunk é processado
  como um único trecho (nenhuma chamada de reconstrução/crossfade é exercitada).

### Implementation for User Story 3

- [x] T035 [US3] Implementar `SonicMasterProvider.restore_full_song` em `ai_provider.py`:
  divisão em janelas com overlap, crossfade linear na reconstrução, e condicionamento encadeado
  (latente re-codificado dos últimos segundos de overlap do chunk anterior já restaurado —
  reproduzindo o mecanismo real encontrado na auditoria do código do SonicMaster). Depende de T018
  (Phase 3) e T033/T034 (falhando).
- [x] T036 [US3] Conectar `restore_full_song` ao `MasteringEngine` (Phase 3/4): quando o áudio de
  entrada excede a duração de um único chunk, os modos que acionam IA usam `restore_full_song` em
  vez de `restore`. Depende de T035.

**Checkpoint**: músicas completas processam sem descontinuidade audível/mensurável nas junções.

---

## Phase 6: User Story 4 — Continuar funcionando sem GPU/IA (Priority: P4)

**Goal**: indisponibilidade do provider de IA (hardware insuficiente, dependência ausente, falha
de carregamento) nunca impede o uso do produto.

**Independent Test**: quickstart.md Cenário 2 (fallback).

### Tests for User Story 4 ⚠️

- [x] T037 [P] [US4] Teste: com `ASTROS_AUDIO_WORKER_PYTHON` apontando para um caminho inválido (ou
  não setado), `SonicMasterProvider.is_available()` retorna `False` sem lançar exceção.
- [x] T038 [P] [US4] Teste de fallback ponta a ponta (quickstart.md Cenário 2): `MasteringEngine`
  com provider indisponível e uma faixa com defeito que normalmente acionaria IA — job completa
  via DSP, `error`/`error_category` vazios, resultado tem o defeito reduzido (não é uma cópia
  inalterada do original).

### Implementation for User Story 4

- [x] T039 [US4] Implementar `SonicMasterProvider.is_available()` em `ai_provider.py`,
  reaproveitando `HardwareCapability`/detecção de hardware já existente em
  `astros_upscale/processing.py` (Princípio VII) — verifica interpretador configurado, VRAM
  mínima estimada, checkpoint acessível. Depende de T018.
- [x] T040 [US4] Implementar o caminho de fallback em `MasteringEngine` (todos os modos): quando
  `is_available()` é `False` e `requires_ai_restoration` seria `True`, seguir só com DSP em vez de
  tentar carregar o provider — nunca travar tentando inicializar. Depende de T020/T030/T031, T039.

**Checkpoint**: todas as 4 user stories funcionam de forma independente e em conjunto.

---

## Phase 7: Validação final e limpeza

**Purpose**: confirmar que nada quebrou e documentar o que só pode ser confirmado com o ambiente
real (medição de desempenho, configuração operacional).

- [x] T041 Rodar a suíte completa de `astros_upscale_api`
  (`pytest -m "not slow" -n auto`) — deve continuar 100% verde, incluindo
  `test_audio_processor.py` já existente antes desta feature.
- [ ] T042 Rodar os 4 cenários de `quickstart.md` manualmente contra um ambiente real (audio-worker
  configurado, `HF_TOKEN` válido, checkpoint baixado) — registrar o resultado de cada um.
- [ ] T043 Medir VRAM e tempo de inferência reais do SonicMaster (um chunk de 30s, GPU disponível)
  e documentar o número medido — nenhuma promessa de desempenho é escrita em UI/documentação antes
  desta medição existir (research.md já sinalizou isso como desconhecido).
- [x] T044 [P] Atualizar `docs/models/MODEL_LICENSES.md` com uma nota sobre o subconjunto
  vendorizado (`vendor/sonicmaster/`): arquivo(s), commit de origem, confirmação de que a licença
  Apache-2.0 e os avisos de atribuição foram preservados.
- [x] T045 [P] Atualizar `api/README.md` com a variável `ASTROS_AUDIO_WORKER_PYTHON` (tabela de
  variáveis de ambiente já existente) e um parágrafo curto sobre como configurar o venv/checkpoint
  do audio-worker, apontando para `quickstart.md` desta feature para o passo a passo completo.

**Checkpoint**: feature completa, documentada, sem regressão na suíte existente.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: sem dependências — começa imediatamente, corrige bugs já presentes hoje.
- **Foundational (Phase 2)**: independente de Setup no código, mas ambos devem estar prontos antes
  de qualquer teste de ponta a ponta com IA real — BLOQUEIA T018 (US1) em diante que dependa do
  provider real.
- **User Story 1 (Phase 3)**: `analyzer.py`/`dsp.py`/`quality.py` (T014–T017) não dependem da
  Fase 2 e podem começar em paralelo com ela; `ai_provider.py` (T018) em diante depende da Fase 2.
- **User Story 2 (Phase 4)**: depende de US1 completa (reaproveita `analyzer`/`dsp`/`quality`/
  `ai_provider`/`mastering`).
- **User Story 3 (Phase 5)**: depende de `ai_provider.py` (T018, US1) existir — pode ser
  desenvolvida em paralelo com US2 depois disso.
- **User Story 4 (Phase 6)**: depende de `ai_provider.py` e `mastering.py` (US1) existirem — pode
  ser desenvolvida em paralelo com US2/US3 depois disso.
- **Validação final (Phase 7)**: depende de todas as user stories desejadas para o release estarem
  completas.

### Parallel Opportunities

- T002 (teste) em paralelo com T003/T004 (Setup).
- T006, T007 em paralelo entre si (Foundational); T009/T010 em paralelo entre si.
- T011, T012, T013 (testes de US1) em paralelo entre si, e em paralelo com T005–T010 (Foundational).
- T014, e depois T015/T016 (analyzer/dsp) em paralelo entre si — ambos bloqueiam T017 (quality).
- T023 em paralelo com T024 (schema vs. integração tocam arquivos diferentes, mas T024 depende do
  resultado de T022, não de T023 diretamente).
- Depois da Fase 2 completa: US3 (Phase 5) e US4 (Phase 6) podem ser feitas em paralelo entre si,
  ambas depois de US1.
- T044, T045 em paralelo entre si (Phase 7).

---

## Parallel Example: User Story 1

```bash
# Testes de US1, em paralelo:
Task: "Teste de audio_engine/analyzer.py em tests/test_audio_engine_analyzer.py"
Task: "Teste de audio_engine/dsp.py em tests/test_audio_engine_dsp.py"
Task: "Teste de audio_engine/quality.py em tests/test_audio_engine_quality.py"

# Depois de T014 (pacote criado), analyzer e dsp em paralelo:
Task: "Implementar analyzer.py"
Task: "Implementar dsp.py"
```

---

## Implementation Strategy

### MVP First (User Story 1)

1. Phase 1 (Setup) — corrige "Melhoria de voz" quebrada como efeito colateral imediato.
2. Phase 2 (Foundational) — isolamento do worker de IA.
3. Phase 3 (US1) — masterização automática ponta a ponta, com T025 (regressão) validado.
4. **Parar e validar** — quickstart.md Cenário 1 e 4 rodando de verdade.

### Entrega incremental

1. Setup + Foundational → base pronta.
2. US1 → masterização automática (MVP) → validar → possível primeiro release.
3. US2 → restaurar/restaurar+masterizar → validar.
4. US3 → música completa sem junções → validar (pode ser paralelo a US2).
5. US4 → fallback sem GPU/IA → validar (pode ser paralelo a US2/US3).
6. Phase 7 → validação final, medição real, documentação.

---

## Notes

- **Estado da implementação (2026-08-13):** 48/50 tarefas concluídas e testadas (335 testes da
  suíte `astros_upscale_api`, zero regressões, incluindo T025 real de 48s). Restam só **T042**
  (rodar `quickstart.md` contra um ambiente real com audio-worker/checkpoint/`HF_TOKEN`
  configurados) e **T043** (medir VRAM/tempo reais) — ambas exigem hardware/GPU e configuração que
  só o operador do projeto pode fazer, documentado em `api/README.md`.
- **Desvios de design encontrados durante a implementação** (todos testados, nenhum contradiz a
  spec): (1) o mapeamento `ai_strength` → estratégia (T020a) acabou implementado em
  `ai_provider.py` (`_strength_profile`), não em `mastering.py` — é onde a profundidade de
  inferência realmente é decidida; `mastering.py` só repassa o valor adiante sem reescalar.
  (2) O parâmetro `full_song` cogitado para `ai_provider.py`'s `restore()`/`restore_full_song()`
  acabou sendo decorativo — `vendor/sonicmaster/infer.py`'s chunking já lida com qualquer duração
  de forma uniforme (um clipe curto vira exatamente 1 chunk, FR-016), então os dois métodos
  convergem para a mesma implementação; mantidos como métodos separados só para satisfazer o
  contrato `AudioRestorationProvider` da spec, não porque o comportamento difere. (3) A lógica de
  chunking/crossfade (T035) foi extraída para `vendor/sonicmaster/stitching.py`, um módulo próprio
  que só depende de `torch` — necessário para tornar T033/T034 testáveis sem `diffusers`/
  `transformers` (dependências só do audio-worker isolado).
- **Correções de `/speckit.analyze`** (2026-08-13): T008/T008a redesenhados — `WorkerSupervisor`
  é hoje um singleton compartilhado por imagem/vídeo; um segundo supervisor dedicado
  (`get_audio_worker_supervisor()`) substitui a parametrização da instância única, que quebraria
  jobs de imagem/vídeo. T018a, T020a, T021a, T021b adicionadas para cobrir FR-013 (estratégia de
  `ai_strength`), FR-019 (lazy load/reuso) e FR-009/SC-006 (preservação de intenção musical), que
  não tinham tarefa própria. `audio_analysis` (não `analysis_final`) é o nome canônico do campo
  HTTP de resumo de análise em todos os documentos. Total após correções: 50 tarefas.
- `[P]` = arquivos diferentes, sem dependência entre si.
- Cada tarefa de teste deve falhar antes da implementação correspondente existir (T011–T013,
  T019, T021, T023, T025–T029, T033–T034, T037–T038).
- T025 (regressão de compatibilidade) é a validação mais importante desta feature — nenhuma
  tarefa de US2–US4 deve ser considerada concluída se T025 parar de passar.
- T001/T003 corrigem bugs já existentes hoje, independentes do resto da feature — podem (e devem)
  ser entregues mesmo se o restante do trabalho for pausado.
