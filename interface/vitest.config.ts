import { resolve } from 'path'
import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'

// The renderer had no test runner at all until 007-video-editor-player needed one
// (Constitution Princípio VIII: every new feature MUST have tests). Deliberately a
// separate config from electron.vite.config.ts: that one describes how the three
// Electron bundles are built, this one only describes how renderer sources are
// exercised in isolation. Merging them would make the build config carry test-only
// concerns for no gain.
export default defineConfig({
  plugins: [vue()],
  // Mirrors electron.vite.config.ts's define. Without it, importing
  // services/api.ts here fails on an undeclared global — the tests would be
  // exercising a different module than the app does.
  define: { __ASTROS_API_PORT__: JSON.stringify(process.env.ASTROS_API_PORT || '8765') },
  resolve: {
    alias: { '@renderer': resolve('src/renderer/src') }
  },
  test: {
    // happy-dom rather than jsdom: composables here touch HTMLVideoElement and
    // requestVideoFrameCallback, and happy-dom is the faster of the two for the
    // narrow DOM surface these tests need.
    environment: 'happy-dom',
    include: ['src/renderer/src/**/*.spec.ts'],
    // The main and preload bundles are Node-side and are not covered here.
    exclude: ['node_modules/**', 'out/**', 'dist/**']
  }
})
