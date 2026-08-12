import { resolve } from 'path'
import { defineConfig } from 'electron-vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  main: {},
  preload: {},
  renderer: {
    resolve: {
      alias: {
        '@renderer': resolve('src/renderer/src')
      }
    },
    // Pinned to match astros_upscale_api's cors_origins (app/config.py) — the API only
    // allows this exact dev origin. If 5173 is busy, kill the stray process rather than
    // letting Vite silently pick another port (CORS would then reject every request).
    server: { port: 5173, strictPort: true },
    plugins: [vue()]
  }
})
