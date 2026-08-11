# Fase 0 — Inventário Técnico dos Repositórios

**Data da auditoria:** 2026-08-08
**Escopo:** `astros_upscale` (repositório atual, tratado como o projeto Astros) e `astros_audio_enhance`.
**Método:** leitura direta de arquivos. Nenhuma afirmação neste documento foi inferida sem
evidência em código. Onde algo não existe, está registrado explicitamente como não existente.

> Este documento é a base factual da especificação (`/speckit.specify`). Ele descreve o que
> **existe hoje**, não o que se pretende construir.

---

## 1. Correções a premissas do briefing

Três premissas do pedido original não correspondem ao estado real dos repositórios. Registradas
aqui porque alteram materialmente o plano de trabalho.

### 1.1 `astros_audio_enhance` já está integrado, não é um repositório a incorporar

`astros_upscale/audio.py:40-65` define `AUDIO_ENGINES` com quatro engines, e uma delas
(`audio-enhance`) consome o `astros_audio_enhance` **como dependência pip**, não como código a
ser copiado. O trabalho pendente é expor áudio na API e no app — não integrar os projetos.

### 1.2 `astros_audio_enhance` é super-resolução, não redução de ruído

O pipeline real é AudioSR (difusão latente + vocoder HiFi-GAN), baseado em Liu et al.,
arXiv:2309.07314. Ele reconstrói banda de frequência ausente. Não faz denoise, não faz correção
de loudness, e não transcodifica para formatos comprimidos (a saída é sempre WAV; o `ffmpeg` é
usado apenas com `-c copy` para recorte, em `astros_audio_enhance/utils.py:264-295`).

**Decisão do dono do projeto (2026-08-08):** "Melhorar Áudio" no Astros = AudioSR. Todas as demais
capacidades de áudio (redução de ruído, melhoria de voz, normalização, correção de volume,
redução de artefatos, inteligibilidade) são **implementação nova**.

### 1.3 Compressão e conversão já existem parcialmente

`astros_upscale/optimize.py` implementa recompressão real de imagem (OpenCV), vídeo (CRF/ffmpeg)
e áudio (bitrate/FLAC/ffmpeg). Limitação atual: `optimize_file:88-103` **exige extensão de saída
igual à de entrada** — portanto faz *comprimir*, mas não *converter*. Conversão é uma extensão
dessa base existente, não um módulo novo.

---

## 2. Inventário: `astros_upscale`

### 2.1 Core de processamento de imagem

| Item | Onde | Estado |
|---|---|---|
| Registro de modelos | `astros_upscale/core.py:22-190` | 19 modelos catalogados |
| Carregamento | `core.py:405` via **spandrel** | Arquitetura auto-detectada do state dict |
| Seleção de device | `core.py:340-346` (`_pick_device`) | CUDA > MPS > CPU |
| Half precision | `core.py:410` | Só em GPU e se o modelo suportar |
| Tile processing | `core.py:463-530` (`tile_process`) | Parametrizado por tile/pad |
| Threshold de tile (API) | `interface/astros_upscale_api/app/core/upscaler.py:57-58` | >1600px → tile 512 |
| Denoise por DNI | `core.py:300-330`, `420-429` | Interpola 2 pesos; só `realesr-general` |
| Face recovery | `astros_upscale/face_restore.py` | GFPGAN v1.4 via spandrel + facexlib |
| Sharpen (pós) | `app/core/upscaler.py:62-70` | Unsharp mask OpenCV |
| Denoise filtro (pós) | `app/core/upscaler.py:78-91` | `fastNlMeansDenoisingColored` |

Arquiteturas presentes: RRDBNet/ESRGAN, SRVGGNetCompact, RealPLKSR, DAT-2, SPAN.
Formatos de peso: `.pth` e `.safetensors`.

### 2.2 Vídeo

Existe processamento real, **exclusivamente na CLI** (`astros_upscale/cli.py:152-199`, `run_video`).

- Leitura/escrita: `astros_upscale/utils/video_io.py`, sobre `cv2.VideoCapture`/`VideoWriter`,
  frame a frame, sequencial.
- **Preserva:** FPS (`video_io.py:41`), áudio via remux ffmpeg (`video_io.py:88-153`),
  ajuste de resolução ímpar para par (`video_io.py:83-85`).
- **Não preserva/não trata:** metadados, timestamps, rotação, HDR, container original (sempre
  reencapsula em `.mp4`), legendas. Sem decode/encode acelerado por GPU. Sem paralelismo.
- **Ausente na API e no app desktop.** `app/core/upscaler.py` só chama `imread`/`imwrite`.

### 2.3 Áudio

`astros_upscale/audio.py:40-65` — quatro engines, todas extras opcionais com fallback
(`MissingAudioDependency`):

| Engine | Pacote | Finalidade | Verificado com pesos reais? |
|---|---|---|---|
| `denoise-voz` | `denoiser` (Meta) | Denoise de voz, CPU | Não (`audio.py:25-30`) |
| `enhance-voz` | `voicefixer` | Denoise + restauração | Não |
| `audio-enhance` | `astros-audio-enhance` | Super-resolução geral → 48kHz | **Sim** |
| `super-voz` | `audiosronnx` | Bandwidth extension de fala, ONNX | Não |

Acionável via `astros-upscale audio` e como flag `--audio` do comando `video`.
**Ausente na API e no app desktop.**

### 2.4 Compressão (`optimize.py`)

| Mídia | Método | Parâmetro |
|---|---|---|
| Imagem | OpenCV `imencode` | quality 0-100 (JPEG/WebP); PNG sempre lossless nível 9 |
| Vídeo | ffmpeg CRF | `_quality_to_crf`: quality 100 → CRF 18, quality 0 → CRF 40; áudio copiado |
| Áudio | ffmpeg bitrate | `_quality_to_audio_bitrate_kbps`: 64–320 kbps; FLAC → compression_level 12 |

Formatos suportados hoje: imagem `.jpg/.jpeg/.png/.webp`; vídeo `.mp4/.mkv/.mov/.avi/.webm`;
áudio lossy `.mp3/.m4a/.aac/.ogg/.opus` + lossless `.flac`.

**Ausente:** AVIF (imagem), seleção de encoder por hardware, conversão entre formatos distintos.

### 2.5 FFmpeg — está espalhado

Três implementações independentes de wrapper, todas via a lib `python-ffmpeg` (não `subprocess` cru):

- `astros_upscale/utils/video_io.py` — `has_ffmpeg`, `extract_audio`, `mux_audio_file`, `copy_audio`
- `astros_upscale/audio.py` — `_run_ffmpeg`, `_to_wav`, `_convert_format`
- `astros_upscale/optimize.py:27-32` — `_run_ffmpeg` própria, duplicada

Não existe módulo central de mídia. Consolidar isso é pré-requisito da camada "Media Engine".

### 2.6 API (`interface/astros_upscale_api`)

Rotas em `app/api/` (não `app/routes/`), registradas em `app/main.py:17-22`:

| Método | Rota | Propósito |
|---|---|---|
| GET | `/health` | Healthcheck |
| GET | `/models` | Lista modelos + status de download + devices |
| POST | `/jobs` | Cria job (upload multipart) |
| POST | `/jobs/local` | Cria job por caminho local (app Electron) |
| GET | `/jobs` | Lista jobs |
| GET | `/jobs/{id}` | Detalhe |
| DELETE | `/jobs/{id}` | Cancela (mata o worker) |
| PATCH | `/jobs/{id}/params` | Atualiza params de job pendente |
| POST | `/jobs/{id}/process` | Enfileira |
| POST | `/jobs/{id}/export` | Reencoda master, sem reinferência |
| GET | `/jobs/{id}/download` | Baixa saída |
| GET | `/identity` | install_id + chaves públicas |
| POST | `/preview/denoise` | Prévia downscaled do denoise |
| WS | `/ws/jobs/{id}` | Progresso em tempo real |

**Estados de job já existentes** (`app/models/schemas.py`):
`pending | queued | processing | done | error | cancelled`
**Categorias de erro:** `out_of_memory | corrupted_input | model_failure | disk_full`

Fila: `asyncio.Queue` single-worker em memória (`app/core/job_manager.py`). O próprio código
recomenda Redis+RQ/Celery se for hospedado multiusuário. Cancelamento é real (mata o processo).
Watchdog detecta worker travado entre jobs (`job_manager.py:279-291`).

**Isolamento de processo:** a inferência roda em processo-filho separado, via named pipe local
autenticado com authkey efêmero, ambiente restrito (`worker_supervisor.py:44-57`).

### 2.7 Hardware detection — insuficiente para o objetivo

Só existe `torch.cuda.is_available()` / `torch.backends.mps.is_available()` (`core.py:340-346`).

**Não existe:** detecção de VRAM, modelo de GPU, memória livre, `nvidia-smi`, `pynvml`, WMI,
enumeração de encoders/decoders disponíveis no ffmpeg.

Isto é uma lacuna direta contra o Princípio VII (Hardware Adaptive) e contra a Seção 21 do
briefing — precisa ser construído.

### 2.8 Frontend (`interface/astros_upscale_app`)

Itens de navegação (`AppSidebar.vue:41-49`): `home`, `imagem`, `video`, `audio`, `otimizar`,
`modelos`, `historico`, `configuracoes`.

| Aba | Tela real? |
|---|---|
| home, imagem, modelos, historico, configuracoes | **Sim** |
| video, audio, otimizar | **Não** — placeholder genérico em `App.vue:60-67` |

**Exposição de modelo ao usuário** (a remover pelo Princípio V):
1. `views/ModelsView.vue` — tela dedicada com busca, filtros por licença, detalhe técnico e
   "Definir como modelo padrão"
2. `views/ImageEditorView.vue` — seleção de modelo e de device por job

### 2.9 Licenciamento de modelos — registro já existe

`interface/astros_upscale_app/src/renderer/src/data/modelLicenses.ts` (frontend, TS) cobre as 19
entradas com: `license`, `developer`, `commercialUse`, `modificationAllowed`,
`redistributionAllowed`, `attributionRequired`, `restrictions[]`, `sourceUrl`, `sourceKind`,
`verifiedAt`.

Classificação atualmente registrada no repositório (**pendente de revalidação independente**):

| Modelos | Licença | Uso comercial |
|---|---|---|
| `ultrasharp`, `animesharp`, `liveaction-span` | CC-BY-NC-SA-4.0 | **Não permitido** |
| `nmkd-superscale` | Não confirmada | **Não verificado** |
| Família Real-ESRGAN (7) | BSD-3-Clause | Permitido |
| Família Phhofm (6) | CC-BY-4.0 | Permitido |
| `nmkd-siax` | WTFPL | Permitido |

O próprio arquivo registra um conflito conhecido: o mirror do UltraSharp
(`huggingface.co/uwg/upscaler`) se declara MIT, contradizendo o CC-BY-NC-SA-4.0 do OpenModelDB.

O backend Python (`core.py`) **não tem nenhum campo de licença** — só `sha256`, `scale`,
`category`, `description`, `architecture`. `models/README.md` não menciona licenças.

### 2.10 Serviço de licenciamento (`interface/astros_licensing_service`)

Serviço FastAPI separado, SQLite próprio, chaves próprias.

**Existe:** criação de licença por webhook (Stripe/Mercado Pago, idempotente por
`payment_reference`); ativação com limite de assentos (`activation_limit`, default 2); release de
instalação; revogação via `set_license_status`; autorizações Ed25519 de curta duração (TTL 300s)
com anti-rollback; entrega de pacote criptografado por instalação (X25519); identidade por
máquina protegida por DPAPI no Windows.

**Não existe:** RBAC; métrica de uso por job (explicitamente por design, `licensing.py:1-5`);
endpoint de renovação dedicado; endpoint admin; Dockerfile.

**Crítico:** todo o enforcement está **desligado por padrão**. `licensing_service_url` vazio
(`app/config.py:25`) faz o worker usar a classe `Upscaler` estática local sem checagem alguma.

### 2.11 Testes

22 arquivos pytest em 3 diretórios:

| Diretório | Arquivos | Cobre |
|---|---|---|
| `tests/` (raiz) | 5 | Registry, core/enhance, video_io, optimize, mirror |
| `interface/astros_upscale_api/tests/` | 13 | HTTP/WS, jobs, isolamento, integridade, identidade |
| `interface/astros_licensing_service/tests/` | 5 | Licenças, autorizações, pagamentos, rotas |

O esforço está concentrado no aparato de proteção. **Vídeo e áudio não têm teste na API**
(coerente com não estarem implementados lá). Sem e2e do Electron.

### 2.12 Build e deploy

- **App:** `electron-builder.yml` — Windows NSIS, macOS dmg, Linux AppImage/snap/deb.
  `publish.url` = `https://example.com/auto-updates` (**placeholder**).
- **API:** roda como processo-filho do Electron (`src/main/apiProcess.ts`), spawn de `python run.py`
  do `.venv`, com reuso se já houver instância viva em `127.0.0.1:8765`.
- **Docker:** só `interface/astros_upscale_api/Dockerfile`. Nada para o licensing service.
- **CI:** `.github/workflows/tests.yml` — 3 jobs (pytest licensing/ubuntu, pytest API/windows por
  causa do DPAPI real, lint+typecheck frontend/ubuntu). Sem job de build de instalador.
- **systemd:** não existe.

---

## 3. Inventário: `astros_audio_enhance`

| Item | Onde | Estado |
|---|---|---|
| Pipeline | `pipeline.py:163-303` | AudioSR: lowpass → difusão latente → HiFi-GAN → normalização |
| Modelo | Checkpoints HF `haoheliu/audiosr_basic` e `_speech` | Baixados em runtime, cache HF |
| Sampler | `latent_diffusion/models/{ddpm,ddim,plms}.py` | DDIM/PLMS |
| Vocoder | `hifigan/models.py` | HiFi-GAN, MIT (Jungil Kong) |
| Device | `pipeline.py:131-137` | CUDA > MPS > CPU automático |
| Interface | `app.py` (Gradio) + `__main__.py` (CLI) | Sem API HTTP estruturada |
| Normalização | `utils.py:182-185`, `app.py:47-67` | Pico/RMS simples |
| FFmpeg | `utils.py:264-295` (único ponto) | Só `-c copy` para recorte |
| Batch | `__main__.py:185-229` | Sequencial, sem paralelismo |
| Testes | `tests/test_package.py` | 7 smoke tests; nenhum de inferência real |

**Não existe:** API HTTP, fila/jobs/workers, WebSocket, denoise, loudness/LUFS, transcodificação
real para MP3/AAC/Opus, logger estruturado, Docker, autenticação.

**Achado de licença:** o `LICENSE` da raiz é boilerplate do GitHub
(`Copyright (c) 2012-2023 Scott Chacon and others`), não o copyright do autor, apesar de
`pyproject.toml:10` declarar MIT/Eric Inacio. Não há declaração de licença dos pesos AudioSR.

---

## 4. Matriz de funcionalidades e destino

Legenda de destino: **REUTILIZAR** (usar como está) · **REFATORAR** (existe, precisa mudar) ·
**EXPOR** (existe no core, falta na API/UI) · **CRIAR** (não existe) · **REMOVER** (deve sair)

| Funcionalidade | astros_upscale | astros_audio_enhance | Destino |
|---|---|---|---|
| **IMAGEM** | | | |
| Upscale 2x/4x (inferência) | Completo (core + API + UI) | — | REUTILIZAR |
| Tile processing | Completo, threshold fixo 1600/512 | — | REFATORAR (adaptar ao hardware) |
| Face recovery (GFPGAN) | Completo | — | REUTILIZAR (verificar licença) |
| Sharpen / denoise pós | Completo (OpenCV) | — | REUTILIZAR |
| Compressão de imagem | `optimize_image`, sem AVIF | — | REFATORAR (+AVIF) |
| Conversão de imagem | Bloqueada (ext igual obrigatória) | — | REFATORAR |
| **VÍDEO** | | | |
| Upscale de vídeo | Completo na CLI, ausente na API/UI | — | EXPOR + REFATORAR |
| Preservação FPS/áudio | Existe (ffmpeg remux) | — | REUTILIZAR |
| Preservação metadados/rotação/HDR | Não trata | — | CRIAR |
| Compressão de vídeo | `optimize_video` (CRF x264) | — | REFATORAR (+HEVC/AV1, +hardware) |
| Conversão de vídeo | Bloqueada | — | REFATORAR |
| Encode/decode por GPU | Não existe | — | CRIAR |
| **ÁUDIO** | | | |
| Super-resolução (AudioSR) | Wrapper em `audio.py` | Implementação | EXPOR (único verificado) |
| Redução de ruído | Wrapper `denoiser` não verificado | Não existe | **CRIAR** (decisão do dono) |
| Melhoria de voz | Wrapper `voicefixer` não verificado | Não existe | **CRIAR** |
| Normalização / loudness | Só pico/RMS | Só pico/RMS | **CRIAR** (LUFS/EBU R128) |
| Redução de artefatos | Não existe | Não existe | **CRIAR** |
| Compressão de áudio | `optimize_audio` (bitrate/FLAC) | Não existe | REUTILIZAR |
| Conversão de áudio | Bloqueada | Não existe | REFATORAR |
| **PLATAFORMA** | | | |
| Jobs (estados/progresso/cancel) | Completo, só para imagem | Não existe | REUTILIZAR + generalizar |
| Fila | asyncio single-worker | Não existe | REUTILIZAR (avaliar limite) |
| Isolamento de processo | Completo | Não existe | REUTILIZAR |
| WebSocket de progresso | Completo | Não existe | REUTILIZAR |
| Camada FFmpeg central | 3 wrappers duplicados | 1 uso pontual | **REFATORAR** (consolidar) |
| Detecção de hardware | Só `cuda.is_available()` | Idem | **CRIAR** (VRAM, encoders) |
| Resolver de perfis Fast/Balanced/Quality | Não existe | Não existe | **CRIAR** |
| Model Manager interno | `mirror_models.py` + download em core | Download HF | REFATORAR (unificar) |
| UI de seleção de modelo | `ModelsView.vue` + editor | — | **REMOVER** |
| Registro de licenças de modelo | `modelLicenses.ts` (frontend) | Não existe | REFATORAR (mover p/ backend) |
| Telas Vídeo/Áudio/Otimizar | Placeholders vazios | — | **CRIAR** |
| Licenciamento de software | Completo, desligado | Não existe | REUTILIZAR (decidir ativação) |

---

## 5. Lacunas críticas identificadas

1. **Detecção de hardware é insuficiente** para cumprir o Princípio VII. Sem VRAM não é possível
   escolher tile size, batch ou precisão de forma adaptativa. É pré-requisito dos perfis.
2. **FFmpeg triplicado** impede a camada Media Engine única.
3. **19 modelos, no máximo 3 perfis por operação/escala.** A redução depende primeiro do
   veredito de licença, depois de benchmark — nesta ordem, porque não adianta medir um modelo
   que não pode ser distribuído.
4. **Licenças de modelo vivem no frontend**, em TypeScript. Precisam ser autoridade do backend,
   já que quem resolve o modelo é o backend.
5. **Registro de licenças é auto-declarado** e contém pelo menos um conflito conhecido
   (UltraSharp). Revalidação independente contra fonte oficial está em curso.
6. **Áudio depende de engines não verificadas** cujas licenças podem inviabilizar uso comercial.
7. **Enforcement de licenciamento está desligado** — decisão de produto pendente sobre ativar.

---

## 6. Pendências desta fase

- [x] Revalidação independente das licenças dos 19 modelos de imagem — concluída. O registro foi
  reduzido de 19 para exatamente 1 implementação por content_type de imagem/vídeo (FR-095, T010/T024),
  com os modelos rejeitados/indeterminados documentados em `astros_upscale/legacy_identifiers.py` e
  as licenças finais rastreadas em `interface/astros_upscale_api/app/core/license_registry.py`
  (`verify_registry_completeness()` garante que todo modelo em `astros_upscale.core.MODELS` tem
  entrada de licença, e vice-versa).
- [x] Verificação das licenças das engines de áudio e das alternativas — concluída. Decisão registrada
  em `docs/models/MODEL_LICENSES.md` §3/§3-bis: fala = `audiosronnx` (Apache-2.0, sem ressalva);
  música = `SonicMaster` (Apache-2.0, **condicional** — depende do VAE do Stable Audio Open, risco
  aceito conscientemente pelo dono do produto). Rastreado em código via
  `profile_resolver._CONTENT_TYPE_IMPLEMENTATIONS`'s `license_status`/`license_condition` (T055).
- [x] Decisão sobre ativar ou não o enforcement de licenciamento no produto final — concluída: **ativado**.
  `astros_licensing_service` (serviço separado) + `license_gate.py`/`routes_license.py` na API local
  aplicam o gate real (`blocked`/`not_activated` recusam o processamento) com tolerância offline de
  30 dias — ver User Story 7 em `specs/001-unified-media-processing/tasks.md`.

### Pendência nova, encontrada durante a entrega (2026-08-11)

- [ ] **O instalador Electron não embute nenhum binário `ffmpeg`** — o backend depende inteiramente de
  um `ffmpeg` já presente no PATH da máquina do usuário final. Na prática, compress/convert (US2),
  vídeo (US3) e áudio (US4) não funcionam numa instalação limpa típica, apesar de implementados e
  testados. Encontrado ao reverificar a licença do FFmpeg (T072); registrado como tarefa de
  acompanhamento separada (empacotar um build LGPL do ffmpeg) — ver
  `docs/models/MODEL_LICENSES.md` §5.
