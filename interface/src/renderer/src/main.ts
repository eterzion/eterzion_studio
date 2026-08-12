import '@fontsource-variable/inter'
import '@fontsource-variable/jetbrains-mono'
import './assets/main.css'
import './styles/tailwind.css'

import { createApp } from 'vue'
import App from './App.vue'
import { applyTheme, getInitialTheme } from './theme'
import { i18n, setLocale, detectSystemLocale, type SupportedLocale } from './i18n'

applyTheme(getInitialTheme())

const STORAGE_KEY = 'astros-upscale:settings'
function getInitialLocale(): SupportedLocale {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    const stored = raw ? JSON.parse(raw).language : null
    if (stored && stored !== 'auto') return stored as SupportedLocale
  } catch {
    // fall through to detection
  }
  return detectSystemLocale()
}
setLocale(getInitialLocale())

createApp(App).use(i18n).mount('#app')
