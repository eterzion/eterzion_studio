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

Requer Python 3.11+ e um venv na raiz do repositório (`.venv/`).

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

Cada serviço lê seu próprio arquivo `.env` (não commitado) na raiz do seu
respectivo `app/`, via `pydantic-settings`. As mais relevantes para produção:

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
| `ASTROS_FFMPEG_DIR` | *(vazio)* | Diretório do ffmpeg empacotado (setado pelo Electron quando há um bundle) |
| `ASTROS_WORKER_AUTHKEY` | *(vazio)* | Token de autenticação do IPC do worker isolado |

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

Cada serviço tem seu próprio `pyinstaller.spec` e `Dockerfile` —
`astros_upscale_api/pyinstaller.spec` e `astros_licensing_service/` (Docker).
Veja [interface/README.md](../interface/README.md#empacotar-um-instalador)
para o passo a passo completo de empacotar o instalador do app desktop, que
inclui a API de processamento via PyInstaller.
