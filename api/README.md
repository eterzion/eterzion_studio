# Backend (api/)

Três subprojetos Python, cada um com responsabilidade própria:

```
astros_upscale/           # biblioteca de processamento: modelos, upscale, tiling,
                           # detecção foto/anime, recuperação facial, hardware,
                           # áudio/vídeo/imagem, engines de mídia (processing.py, media.py, optimize.py)
astros_upscale_api/       # API FastAPI local que o app desktop consome (porta 8765)
astros_licensing_service/ # serviço de licenciamento — processo FastAPI separado (porta 8766)
```

`astros_upscale_api` importa `astros_upscale` diretamente (mesmo processo).
`astros_licensing_service` é um processo totalmente separado — a API local só
fala com ele por HTTP, nunca importa nada dele. Veja
[docs/processing-protection-architecture.md](../docs/processing-protection-architecture.md)
para o porquê dessa separação (proteção do processamento contra pirataria).

## Rodar cada serviço isoladamente

Requer Python 3.10+ (`pyproject.toml`'s `requires-python`; recomendado usar a
3.13, a mesma versão testada em CI e usada nos `Dockerfile`s de cada serviço)
e um venv na raiz do repositório (`.venv/`).

```bash
cd api
pip install -r astros_upscale_api/requirements-dev.txt
pip install -r astros_licensing_service/requirements-dev.txt
pip install -e .   # instala astros_upscale em modo editável (consumido pelas duas APIs acima)

# API de processamento (porta 8765) — é a que o Electron sobe sozinho em dev
cd astros_upscale_api && python run.py

# serviço de licenciamento (porta 8766) — NÃO é subido automaticamente pelo
# Electron; suba à parte para testar ativação de licença em desenvolvimento
cd astros_licensing_service && python run.py
```

O `interface/` (app desktop) só sobe `astros_upscale_api` automaticamente ao
abrir — veja [interface/README.md](../interface/README.md).

## Testes

**Sempre com `-n auto`** (pytest-xdist) — sem isso a suíte de
`astros_upscale_api` sozinha varia de ~40s a vários minutos dependendo do
ambiente. As três subpastas não podem rodar numa única invocação `pytest`
(`astros_upscale_api` e `astros_licensing_service` definem, cada uma, seu
próprio pacote `app`, e a coleta colide entre os dois `sys.path`):

```bash
cd api
../.venv/Scripts/python.exe -m pytest astros_upscale_api/tests -m "not slow" -n auto --no-cov -q
../.venv/Scripts/python.exe -m pytest astros_upscale/tests astros_licensing_service/tests \
  -m "not slow" -n auto --no-cov -q
```

Testes marcados `slow` ficam de fora do CI (`.github/workflows/tests.yml`) e
devem ser rodados manualmente antes de um release. Veja
[specs/004-api-restructure/quickstart.md](../specs/004-api-restructure/quickstart.md)
para o guia completo de validação.

O CI (`.github/workflows/tests.yml`) roda três jobs: `Upscale API (pytest)`
(em `windows-latest`, já que a proteção de segurança usa DPAPI, exclusivo do
Windows), `Licensing service (pytest)` e `Desktop app — lint + typecheck`
(cobrindo `interface/`).

## Variáveis de ambiente

Cada serviço lê seu próprio arquivo `.env` (não commitado), via
`pydantic-settings` — na raiz de onde o processo é iniciado (ex.:
`api/astros_upscale_api/.env`, não dentro do pacote Python `app/`). As mais
relevantes para produção:

**`astros_upscale_api`** (prefixo `ASTROS_`, ver `app/config.py`):

| Variável | Padrão | Descrição |
|---|---|---|
| `ASTROS_PORT` | `8765` | Porta HTTP |
| `ASTROS_API_KEY` | *(vazio)* | Exigida só quando a API é hospedada remotamente |
| `ASTROS_CORS_ORIGINS` | dev origins | Origens permitidas (CORS) |
| `ASTROS_MODELS_DIR` / `ASTROS_UPLOADS_DIR` / `ASTROS_OUTPUTS_DIR` | pastas locais | Onde ficam modelos, uploads e saídas |
| `ASTROS_MAX_UPLOAD_MB` | `200` | Limite de upload |
| `ASTROS_LICENSING_SERVICE_URL` | *(vazio)* | URL do `astros_licensing_service`; vazio desabilita o carregamento protegido |
| `ASTROS_LICENSING_SERVICE_PUBLIC_KEY_B64` | *(vazio)* | Chave pública do serviço de licenciamento, fixada em build de produção (senão é obtida via TOFU de `/public-key`, aceitável só em dev) |
| `ASTROS_DEV_ALLOW_UNLICENSED` | `true` | **Deve ser `false` em qualquer build de produção** — `true` permite rodar sem licença válida (default pensado para dev/testes) |
| `ASTROS_FFMPEG_DIR` | *(vazio)* | Diretório do ffmpeg empacotado. Lida diretamente do ambiente do processo (`os.environ`, em `astros_upscale/media.py`), não é um campo de `Settings` — **não pode ser setada via `.env`**, só como variável de ambiente real. Normalmente setada pelo processo principal do Electron (`apiProcess.ts`), nunca manualmente |
| `ASTROS_AUDIO_WORKER_PYTHON` | *(vazio)* | Caminho do `python.exe` de um venv **separado**, isolado, com `audio_worker_requirements.txt` instalado — habilita a restauração/masterização de música por IA (SonicMaster). Vazio = os modos `auto_master`/`restore`/`restore_master` caem automaticamente para DSP puro (FR-020) |
| `ASTROS_AUDIO_WORKER_CHECKPOINT` | `models/sonicmaster/model.safetensors` | Caminho do checkpoint do SonicMaster (~3,29 GB, baixado sob demanda, nunca commitado) |

### Configurando o audio-worker (restauração de música por IA, opcional)

Os modos de masterização/restauração assistida por IA (`specs/006-audio-engine-masterizacao`) usam
o SonicMaster, vendorizado em `astros_upscale_api/vendor/sonicmaster/` (ver `NOTICE.md` lá dentro
para atribuição). Ele roda num processo/venv completamente separado do backend principal — nunca
instale `audio_worker_requirements.txt` no `.venv` raiz do projeto:

```bash
cd api/astros_upscale_api
python -m venv .audio_worker_venv
.audio_worker_venv/Scripts/pip install -r audio_worker_requirements.txt
```

`audio_worker_requirements.txt` pina `torch==2.6.0`/`torchaudio==2.6.0`/`torchvision==0.21.0`
(primeira série do PyTorch com wheel para Python 3.13 — os pins originais do SonicMaster,
`torch==2.4.0`, não têm wheel para 3.13) e `transformers==4.46.3` (a versão original 4.44.0 puxa
`tokenizers<0.20`, que também não tem wheel para 3.13 e tenta compilar via Rust). Se o Python do
sistema já for 3.13 (`python --version`), o comando acima funciona sem passo extra — não é
necessário instalar um Python mais antigo. Veja `research.md` Decisão 4 para o detalhe completo.

Depois, aponte `ASTROS_AUDIO_WORKER_PYTHON` para
`api/astros_upscale_api/.audio_worker_venv/Scripts/python.exe`. O checkpoint do modelo
(`model.safetensors`, ~3,29 GB) é baixado sob demanda no caminho configurado em
`ASTROS_AUDIO_WORKER_CHECKPOINT` (default: `models/sonicmaster/model.safetensors`), e o VAE que ele
usa (`stabilityai/stable-audio-open-1.0`) exige uma conta Hugging Face com os termos aceitos e a
variável `HF_TOKEN` configurada no ambiente do audio-worker — sem isso, o provedor fica
indisponível e o app cai para DSP puro automaticamente, sem travar. Veja
`specs/006-audio-engine-masterizacao/quickstart.md` para o passo a passo completo de validação.

`ASTROS_WORKER_AUTHKEY` **não** é uma variável de configuração — é um
token efêmero, gerado aleatoriamente a cada processo pelo próprio
`app/jobs.py` (`WorkerSupervisor`) e passado ao worker isolado só para
autenticar o IPC entre os dois. Setá-la manualmente não tem efeito (é
sobrescrita a cada execução); documentada aqui só para quem for ler os logs
do worker e se deparar com ela no ambiente do subprocesso.

**`astros_licensing_service`** (prefixo `ASTROS_LICENSING_`, ver `app/config.py`):

| Variável | Padrão | Descrição |
|---|---|---|
| `ASTROS_LICENSING_PORT` | `8766` | Porta HTTP |
| `ASTROS_LICENSING_DATABASE_PATH` | `storage/licensing.db` | Banco de licenças/instalações/transações |
| `ASTROS_LICENSING_IDENTITY_DIR` | `storage/identity` | Chave de assinatura do serviço |
| `ASTROS_LICENSING_DEFAULT_ACTIVATION_LIMIT` | `2` | Nº de instalações por licença |
| `ASTROS_LICENSING_AUTHORIZATION_TTL_SECONDS` | `300` | Validade de uma autorização de uso |
| `ASTROS_LICENSING_STRIPE_WEBHOOK_SECRET` | *(vazio)* | Segredo do webhook Stripe — vazio desabilita o provedor |
| `ASTROS_LICENSING_MERCADOPAGO_WEBHOOK_SECRET` / `ASTROS_LICENSING_MERCADOPAGO_ACCESS_TOKEN` | *(vazio)* | Credenciais do Mercado Pago |

## Empacotamento (PyInstaller / Docker)

`astros_upscale_api` tem os dois: `pyinstaller.spec` (para embarcar no
instalador do app desktop — ver
[interface/README.md](../interface/README.md#empacotar-um-instalador)) e um
`Dockerfile` próprio (`python:3.13-slim`, para rodar como serviço standalone,
independente do desktop). `astros_licensing_service` só tem `Dockerfile` —
esse serviço nunca é embarcado no app desktop, sempre roda como um processo
remoto/standalone separado.
