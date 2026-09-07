import { resolve } from 'path'
import { defineConfig } from 'electron-vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'

// Ports, chosen to stay clear of the defaults other tooling grabs (5173 in
// particular, which another project on this machine uses).
//
//   development   API 8050 · renderer 8055
//   packaged      API 8051 · renderer 8055
//
// Development and the packaged app differ on the API port on purpose: running
// both at once is normal while testing a build, and sharing a port would make
// one of them fail to start for reasons that look unrelated.
//
// Four things read this and must agree — the renderer's BASE_URL (inlined
// below), the main process (which spawns the API with the same value), the CSP
// in index.html (substituted below), and the API's own cors_origins. They were
// four separate literals until they drifted; now there is one source.
const DEV_RENDERER_PORT = Number(process.env.ASTROS_DEV_PORT) || 8055
const DEV_API_PORT = process.env.ASTROS_API_PORT || '8050'

// Read by src/main/apiProcess.ts, which passes it to the spawned API as
// ASTROS_PORT. Assigning here rather than requiring the caller to export it is
// what makes a bare `pnpm dev` land on the right ports.
process.env.ASTROS_API_PORT = DEV_API_PORT

// A porta do app empacotado. Espelha `port` em
// api/eterzion_upscale_api/app/config.py e `API_PORT` em src/main/apiProcess.ts —
// os três precisam concordar, e é por isso que este arquivo os documenta juntos.
const PACKAGED_API_PORT = '8051'

/** Substitutes the API origin into index.html's Content-Security-Policy.
 *
 *  The CSP has to name the exact origin the renderer will call, and that port
 *  differs between the packaged app and development. Hardcoding either one
 *  blocks every request in the other — with an error that reads like a network
 *  failure rather than a policy one, which is how it was found.
 *
 *  **As duas origens entram, e não só a de desenvolvimento.** O build gera um
 *  único index.html que serve os dois modos: `electron-vite build` roda sem
 *  `ASTROS_API_PORT`, então substituía 8050 e o app empacotado — que sobe a API
 *  em 8051 — tinha toda chamada bloqueada pela política. O sintoma seria "não
 *  conecta na API" num app recém-instalado, com o backend rodando perfeitamente
 *  ao lado.
 *
 *  Listar as duas não afrouxa nada de relevante: as duas são loopback, e um
 *  processo que já esteja escutando numa delas na máquina do usuário poderia
 *  igualmente escutar na outra. */
function astrosApiOrigin(): { name: string; transformIndexHtml: (html: string) => string } {
  const origens = [...new Set([DEV_API_PORT, PACKAGED_API_PORT])]
  const http = origens.map((p) => `http://127.0.0.1:${p}`).join(' ')
  const ws = origens.map((p) => `ws://127.0.0.1:${p}`).join(' ')
  return {
    name: 'astros-api-origin',
    transformIndexHtml(html: string): string {
      return html.replace(/%ASTROS_API_ORIGIN%/g, http).replace(/%ASTROS_API_WS_ORIGIN%/g, ws)
    }
  }
}

export default defineConfig(({ command }) => ({
  main: {},
  preload: {},
  renderer: {
    resolve: {
      alias: {
        '@renderer': resolve('src/renderer/src')
      }
    },
    // strictPort stays true: the API's cors_origins is an explicit list, so a
    // port Vite picked on its own would be rejected by CORS on every request.
    // Failing loudly beats a page that loads and cannot talk to anything.
    server: { port: DEV_RENDERER_PORT, strictPort: true },
    // The renderer cannot read process.env at runtime, so the API port is
    // inlined here. services/api.ts builds BASE_URL from it.
    //
    // **Por modo, e não sempre o de desenvolvimento.** Isto inlinava
    // `DEV_API_PORT` incondicionalmente: o app empacotado chamava 8050
    // enquanto o backend subia em 8051, e TODA requisição falhava. O sintoma
    // some a causa por completo — a tela de licença dizia "Could not verify
    // your licence / Check your internet connection", com o backend rodando
    // perfeitamente ao lado e respondendo 200 em 8051. Clicar em "Try again"
    // nunca resolvia, porque a porta chamada estava vazia.
    //
    // É a mesma armadilha que o comentário de `astrosApiOrigin` acima descreve
    // para o CSP, e que já foi corrigida lá. A porta ficou para trás: das
    // quatro coisas que o cabeçalho deste arquivo diz que precisam concordar,
    // esta era a única que ainda discordava.
    define: {
      __ASTROS_API_PORT__: JSON.stringify(command === 'build' ? PACKAGED_API_PORT : DEV_API_PORT)
    },
    plugins: [vue(), tailwindcss(), astrosApiOrigin()]
  }
}))
