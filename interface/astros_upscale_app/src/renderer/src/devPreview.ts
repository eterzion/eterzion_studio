// TEMPORARY dev-only harness to visually inspect views in a plain browser (no real
// Electron/IPC). localStorage is seeded by devPreview.html's inline script (must run
// before this module — see comment there). Not part of the app — remove
// devPreview.html/.ts + the window.api stub usage after use.
import './assets/main.css'
import { createApp, h } from 'vue'
import HistoryView from './views/HistoryView.vue'
import ModelsView from './views/ModelsView.vue'
import ImageEditorView from './views/ImageEditorView.vue'
import HomeView from './views/HomeView.vue'
import { applyTheme } from './theme'
import { queueState } from './store/jobs'

applyTheme('dark')

// Mock the astros_upscale_api fetch calls the app makes.
const MOCK_MODELS = {
  models: [
    { name: 'realesrgan-x4', category: 'Fotos', scale: 4, description: 'Padrão para fotos reais, equilíbrio nitidez/naturalidade' },
    { name: 'realesrgan-x2', category: 'Fotos', scale: 2, description: 'Quando 4x é exagero; só dobra a resolução' },
    { name: 'realesr-general', category: 'Fotos', scale: 4, description: 'Leve e rápido, bom default geral (suporta --denoise)' },
    { name: 'ultrasharp', category: 'Fotos', scale: 4, description: 'Muito nítido; ótimo em JPEG comprimido' },
    { name: 'nomos2-dat2', category: 'Fotos', scale: 4, description: 'DAT-2 (transformer), muito nítido — pesado, evite p/ vídeo/lote grande' },
    { name: 'realesrgan-anime', category: 'Anime', scale: 4, description: 'Modelo leve otimizado para anime/ilustração' },
    { name: 'animesharp', category: 'Anime', scale: 4, description: 'Linhas limpas em ilustrações e texto' },
    { name: 'hfa2k-span', category: 'Anime', scale: 2, description: 'SPAN — qualidade parecida ao realesrgan-anime, muito mais rápido' },
    { name: 'nmkd-siax', category: 'Restauração', scale: 4, description: 'Universal p/ imagens limpas ou pouco comprimidas' },
    { name: 'nmkd-superscale', category: 'Restauração', scale: 4, description: 'Fotos reais com ruído e artefatos' }
  ],
  devices: ['auto', 'cpu', 'cuda', 'mps'],
  default_image_model: 'realesrgan-x4',
  default_video_model: 'realesr-animevideo'
}

const originalFetch = window.fetch.bind(window)
window.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
  const url = typeof input === 'string' ? input : input.toString()
  if (url.includes('/models') && (!init || init.method === undefined || init.method === 'GET')) {
    return new Response(JSON.stringify(MOCK_MODELS), { status: 200, headers: { 'Content-Type': 'application/json' } })
  }
  return originalFetch(input, init)
}) as typeof fetch

const which = new URLSearchParams(location.search).get('view') || 'history'

if (which === 'editor') {
  queueState.jobs.push({
    id: 'preview-job',
    backendJobId: null,
    sourcePath: 'C:/fake/preview.png',
    fileName: 'preview-image.png',
    sourceMeta: { width: 1024, height: 768, format: 'PNG', sizeBytes: 2_500_000 },
    scaleConfig: {
      mode: 'preset', presetFactor: 4, customWidth: null, customHeight: null, lockAspectRatio: true,
      model: 'realesrgan-x4', device: 'auto', denoise: 50, sharpen: 0, faceRecovery: false, faceRecoveryStrength: 50
    },
    status: 'configuring',
    progress: 0,
    queuePosition: null,
    exportState: 'idle',
    createdAt: Date.now()
  })
  queueState.activeJobId = 'preview-job'
}

const App = {
  render() {
    if (which === 'models') return h(ModelsView)
    if (which === 'editor') return h(ImageEditorView)
    if (which === 'home') return h(HomeView, { onOpenImage: () => {} })
    return h(HistoryView)
  }
}

createApp(App).mount('#app')
