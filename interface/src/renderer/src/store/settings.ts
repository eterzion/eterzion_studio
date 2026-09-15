import { reactive, watch } from 'vue'
import { applyTheme, getInitialTheme, watchSystemTheme, type ThemeMode } from '../theme'
import { detectSystemLocale, setLocale, type SupportedLocale } from '../i18n'
import type { Profile } from '../services/api'

const STORAGE_KEY = 'eterzion-studio:settings'

export interface AppSettings {
  theme: ThemeMode
  defaultOutputFolder: string | null
  defaultExportFormat: 'png' | 'jpg' | 'webp'
  defaultScalePreset: 2 | 4
  defaultLockAspectRatio: boolean
  /** A qualidade do JPEG/WebP, em perfil como a do Video e a do Audio. */
  defaultImageProfile: Profile
  autoCheckUpdates: boolean
  historyLimit: number
  historyAutoCleanupDays: number | null
  showModelDescriptions: boolean
  showCommercialBadges: boolean
  thumbnailSize: 'sm' | 'md' | 'lg'
  animationsEnabled: boolean
  density: 'compact' | 'standard' | 'comfortable'
  language: SupportedLocale | 'auto'
}

function defaults(): AppSettings {
  return {
    // theme.ts (not this blob) is the source of truth — it's read at app boot,
    // before Vue even mounts, to paint the right theme with no flash of the
    // wrong one. This just mirrors it so Configurações has something to bind to.
    theme: getInitialTheme(),
    defaultOutputFolder: null,
    defaultExportFormat: 'png',
    defaultScalePreset: 4,
    defaultLockAspectRatio: true,
    defaultImageProfile: 'balanced',
    autoCheckUpdates: true,
    historyLimit: 200,
    historyAutoCleanupDays: null,
    showModelDescriptions: true,
    showCommercialBadges: true,
    thumbnailSize: 'md',
    animationsEnabled: true,
    density: 'standard',
    language: 'auto'
  }
}

export function perfilDaQualidade(qualidade: number): Profile {
  if (qualidade >= 95) return 'quality'
  if (qualidade >= 85) return 'balanced'
  return 'fast'
}

function load(): AppSettings {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return defaults()
    const salvo = JSON.parse(raw)
    // A qualidade era um numero de 1 a 100; virou perfil. Quem tinha escolhido
    // um numero fica com o perfil mais perto dele.
    if (typeof salvo.defaultQuality === 'number' && !salvo.defaultImageProfile) {
      salvo.defaultImageProfile = perfilDaQualidade(salvo.defaultQuality)
    }
    delete salvo.defaultQuality
    return { ...defaults(), ...salvo }
  } catch {
    return defaults()
  }
}

export const settingsState = reactive<AppSettings>(load())

/** Settings that change how the interface itself looks/behaves are applied as
 *  data-attributes on <html>, the same mechanism theme.ts already uses — CSS reads
 *  them, no per-component wiring needed for the purely visual ones. */
function applyToDom(s: AppSettings): void {
  const root = document.documentElement
  root.dataset.density = s.density
  root.dataset.animations = s.animationsEnabled ? 'on' : 'off'
  root.dataset.thumbSize = s.thumbnailSize
}

applyToDom(settingsState)
watchSystemTheme(() => settingsState.theme)

watch(
  settingsState,
  (s) => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(s))
    applyToDom(s)
  },
  { deep: true }
)

export function setTheme(mode: ThemeMode): void {
  settingsState.theme = mode
  applyTheme(mode)
}

export function setLanguage(language: SupportedLocale | 'auto'): void {
  settingsState.language = language
  setLocale(language === 'auto' ? detectSystemLocale() : language)
}
