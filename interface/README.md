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
veja o `Dockerfile` em `api/astros_upscale_api/` para como subi-la.

```bash
npm install
npm run build && npm run start   # builda tudo e abre a janela do Electron
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

O app também tem uma tela de ativação/status de licença
(`src/renderer/src/views/LicenseActivationView.vue`, com um indicador
compacto em `components/LicenseWidget.vue`, sobre `store/license.ts`), que
fala com `api/astros_licensing_service` — um segundo processo FastAPI,
separado da API de processamento, na porta `8766` por padrão. Ele **não** é
subido automaticamente pelo Electron como a API de processamento; para testar
o fluxo de ativação em desenvolvimento, rode-o à parte (veja
`api/astros_licensing_service/`).

O app fala com `http://127.0.0.1:8765` — hoje esse endereço é uma constante
fixa em `src/main/apiProcess.ts` e `src/renderer/src/services/api.ts` (não há
`.env`/`VITE_API_BASE_URL` lido em tempo de build); para apontar para uma
API remota é preciso editar essas duas constantes diretamente.

## Estrutura

```
src/
├── main/                    # processo principal do Electron
│   ├── index.ts             # bootstrap: liga janela, IPC e protocolo custom
│   ├── apiProcess.ts        # inicia/encerra api/astros_upscale_api
│   ├── protocols/           # protocolo astros-media:// (serve preview/thumbnails)
│   ├── windows/             # criação da BrowserWindow
│   └── ipc/                 # handlers IPC (diálogos nativos, app info)
│
├── preload/                 # contextBridge — única ponte renderer → main
│
└── renderer/src/
    ├── App.vue, main.ts
    ├── views/                # as 10 telas do app
    ├── components/
    │   ├── atoms/            # AppButton, AppSpinner, AppBadge
    │   ├── molecules/        # JobCard, EmptyState
    │   └── *.vue             # demais componentes, sem tier forçado
    ├── services/
    │   ├── api.ts            # cliente HTTP de api/astros_upscale_api
    │   ├── websocket.ts       # progresso de job em tempo real (WebSocket)
    │   └── native.ts          # wrapper sobre window.api (preload)
    ├── store/                # estado global (jobs, history, settings, license, apiStatus)
    ├── composables/
    ├── i18n/                 # vue-i18n, 11 idiomas
    ├── styles/tailwind.css   # config do Tailwind (tokens mapeados de assets/theme.css)
    └── assets/theme.css      # fonte da verdade dos design tokens (cor, spacing, radius…)
```

Os tiers `atoms/`/`molecules/` só existem para os componentes com duplicação
real confirmada (ver `specs/005-interface-design-system/research.md`) — a
maioria dos componentes continua solta em `components/`, sem taxonomia
forçada (Princípio X da constituição do projeto).

## Empacotar um instalador

```bash
cd ../api/astros_upscale_api
pip install pyinstaller
pyinstaller pyinstaller.spec        # gera dist/astros-upscale-api(.exe)

cd ../../interface
npm run build:win     # ou build:mac / build:linux — empacota tudo com electron-builder
```

`build:win`/`build:linux` também baixam o ffmpeg empacotado automaticamente
(`npm run fetch:ffmpeg:win`/`fetch:ffmpeg:linux`, ver
[docs/models/MODEL_LICENSES.md](../docs/models/MODEL_LICENSES.md)) — não é
preciso rodar esse passo manualmente. Para um build sem instalador (só a
pasta descompactada), use `npm run build:unpack`.
