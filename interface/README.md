# Interface gráfica (desktop)

Esta pasta contém **só** o app desktop (Electron + Vue 3 + Vite + Tailwind +
Lucide). Toda a lógica de backend — API local, serviço de licenciamento e a
lógica de processamento de mídia — vive em `api/`, na raiz do repositório.

```
api/         # backend: API HTTP local, serviço de licenciamento, lógica de mídia
interface/   # este diretório: telas, componentes, assets, stores, i18n
```

Os dois falam entre si só por HTTP/WebSocket — `interface/` nunca importa
módulo interno de `api/` diretamente.

```
┌─────────────────────────────┐        HTTP/WebSocket        ┌──────────────────────────────┐
│  interface/                 │  ───────────────────────────▶ │  api/astros_upscale_api       │
│  Electron + Vue (renderer)  │  ◀─────────────────────────── │  FastAPI + RealESRGAN/PyTorch │
└─────────────────────────────┘   http://127.0.0.1:8765        └──────────────────────────────┘
```

## Rodar em desenvolvimento

Requer [Node.js](https://nodejs.org/) 18+ e a API local (`api/astros_upscale_api`) rodando —
veja `api/astros_upscale_api/README` ou o `Dockerfile` lá para como subi-la.

```bash
npm install
npm run electron:preview   # builda tudo e abre a janela do Electron
```

Desenvolvimento com hot-reload (abre no navegador, não numa janela Electron —
mais rápido para iterar em componentes Vue; a API continua precisando estar
rodando à parte):

```bash
npm run dev
```

O processo principal do Electron (`src/main/apiProcess.ts`) resolve
automaticamente a raiz do repositório (o diretório que contém tanto `api/`
quanto `interface/`) e sobe `api/astros_upscale_api` sozinho se ela ainda não
estiver rodando — nenhuma configuração manual é necessária no dia a dia.

Por padrão o app fala com `http://127.0.0.1:8765` (arquivo `.env`); para
apontar para uma API remota, edite `VITE_API_BASE_URL`/`VITE_API_KEY` em
`.env.production` e rode `npm run build`.

## Empacotar um instalador

```bash
cd ../api/astros_upscale_api
pip install pyinstaller
pyinstaller pyinstaller.spec        # gera dist/astros-upscale-api(.exe)

cd ../../interface
npm run electron:build              # empacota tudo com electron-builder
```
