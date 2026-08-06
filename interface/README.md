# Interface gráfica (desktop)

Esta pasta reúne tudo que **não é a CLI** (`astros_upscale/`, na raiz do
repositório): a interface gráfica desktop, em duas partes.

```
interface/
├── astros_upscale_api/   # API local (FastAPI) — expõe o upscaling via HTTP/WebSocket
└── astros_upscale_app/   # app desktop (Electron + Vue 3)
```

Elas rodam como dois processos separados que conversam por HTTP/WebSocket —
o app não tem nenhuma lógica de upscaling embutida, só fala com a API.

```
┌─────────────────────────────┐        HTTP/WebSocket        ┌──────────────────────────────┐
│  astros_upscale_app         │  ───────────────────────────▶ │  astros_upscale_api           │
│  Electron + Vue (renderer)  │  ◀─────────────────────────── │  FastAPI + RealESRGAN/PyTorch │
└─────────────────────────────┘   http://127.0.0.1:8765        └──────────────────────────────┘
```

---

## 1. API (`astros_upscale_api/`)

Reaproveita `astros_upscale.core` diretamente (o mesmo `load_model()`/
`enhance()` que a CLI usa) — nenhuma lógica de upscaling é duplicada aqui,
só exposta como endpoints.

### Instalar e rodar

```bash
# no mesmo ambiente virtual da instalação principal da CLI (veja o README da
# raiz) — torch/realesrgan/pillow/opencv já estão instalados por ela; só
# faltam as libs da própria API:
pip install fastapi "uvicorn[standard]" pydantic-settings python-multipart websockets

cd interface/astros_upscale_api
python run.py
# ou: uvicorn app.main:app --reload --port 8765
```

Confirme que subiu: `http://127.0.0.1:8765/health` deve responder
`{"status":"ok"}`; `http://127.0.0.1:8765/docs` abre o Swagger interativo.
Por padrão ela usa a mesma pasta `models/` da raiz do projeto — nenhum
download extra é necessário se você já rodou a CLI antes.

### Endpoints

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/health` | healthcheck |
| `GET` | `/models` | lista modelos de IA disponíveis e dispositivos (`cpu`/`cuda`/`auto`) |
| `POST` | `/jobs` | cria um job (upload multipart: `file` + `params` JSON) |
| `GET` | `/jobs` | lista todos os jobs |
| `GET` | `/jobs/{job_id}` | detalhe de um job |
| `DELETE` | `/jobs/{job_id}` | cancela um job |
| `PATCH` | `/jobs/{job_id}/params` | atualiza parâmetros de um job ainda `pending` |
| `POST` | `/jobs/{job_id}/process` | dispara o processamento do job |
| `GET` | `/jobs/{job_id}/download` | baixa o arquivo processado |
| `WS` | `/ws/jobs/{job_id}` | stream de progresso em tempo real |

`params` (JSON) aceita: `model`, `device` (`auto`/`cpu`/`cuda`/`mps`),
`scale`, `custom_size` (`{width, height}`, opcional), `adjustments`
(`denoise`/`deblur`/`detail_recovery`/`face_correction`), `export`
(`format`/`quality`) e `output_dir` (opcional — quando a API roda no mesmo
computador que o app desktop, grava direto na pasta escolhida pelo usuário
em vez de `storage/outputs/`).

### Hospedagem remota

O app fala com a API só por `VITE_API_BASE_URL` (veja a seção do App
abaixo) — nada no frontend precisa mudar para apontar para um servidor
remoto. Para isso:

1. **Docker**: `docker build -t astros-upscale-api . && docker run -p 8765:8765 astros-upscale-api` (`Dockerfile` já incluso).
2. **Autenticação**: defina `ASTROS_API_KEY` no `.env` da API; o cliente
   (`src/api/client.js` no app) já injeta `Authorization: Bearer <chave>`
   automaticamente sempre que `VITE_API_BASE_URL` não for `localhost`.
3. **CORS**: ajuste `ASTROS_CORS_ORIGINS` para o domínio real do app em
   produção.
4. **Fila escalável**: a fila atual é local (`asyncio.Queue`, um worker) —
   para múltiplos usuários simultâneos, troque `app/core/job_manager.py`
   por Redis + RQ/Celery; os endpoints não mudam.

---

## 2. App desktop (`astros_upscale_app/`)

Electron + Vue 3 + Vite + Tailwind + Lucide.

Requer [Node.js](https://nodejs.org/) 18+ e a API (seção 1) rodando.

```bash
cd interface/astros_upscale_app
npm install
npm run electron:preview   # builda tudo e abre a janela do Electron
```

Desenvolvimento com hot-reload (abre no navegador, não numa janela
Electron — mais rápido para iterar em componentes Vue; a API continua
precisando estar rodando à parte):

```bash
npm run dev
```

Por padrão o app fala com `http://127.0.0.1:8765` (arquivo `.env`); para
apontar para uma API remota, edite `VITE_API_BASE_URL`/`VITE_API_KEY` em
`.env.production` e rode `npm run build`.

### Empacotar um instalador

Ainda não testado neste repositório. Os arquivos já estão preparados
(`pyinstaller.spec` na API, `electron-builder` no app via
`build.extraResources` em `package.json`), mas os passos completos são:

```bash
cd interface/astros_upscale_api
pip install pyinstaller
pyinstaller pyinstaller.spec        # gera dist/astros-upscale-api(.exe)

cd ../astros_upscale_app
npm run electron:build              # empacota tudo com electron-builder
```
