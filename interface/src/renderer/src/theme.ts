import { ref } from 'vue'

export type ThemeMode = 'dark' | 'light' | 'auto'
export type ResolvedTheme = 'dark' | 'light'
export type AccentColor = 'cyan' | 'blue' | 'purple' | 'green' | 'red' | 'orange' | 'pink' | 'gray'

const THEME_STORAGE_KEY = 'astros-upscale:theme'
const ACCENT_STORAGE_KEY = 'astros-upscale:accent'

export const ACCENT_COLORS: { value: AccentColor; label: string }[] = [
  { value: 'cyan', label: 'Ciano' },
  { value: 'blue', label: 'Azul' },
  { value: 'purple', label: 'Roxo' },
  { value: 'green', label: 'Verde' },
  { value: 'red', label: 'Vermelho' },
  { value: 'orange', label: 'Laranja' },
  { value: 'pink', label: 'Rosa' },
  { value: 'gray', label: 'Cinza' }
]

function systemPrefersLight(): boolean {
  return window.matchMedia?.('(prefers-color-scheme: light)').matches ?? false
}

export function resolveTheme(mode: ThemeMode): ResolvedTheme {
  if (mode === 'auto') return systemPrefersLight() ? 'light' : 'dark'
  return mode
}

export function getInitialTheme(): ThemeMode {
  const stored = localStorage.getItem(THEME_STORAGE_KEY)
  if (stored === 'dark' || stored === 'light' || stored === 'auto') return stored
  return systemPrefersLight() ? 'light' : 'dark'
}

export function getInitialAccent(): AccentColor {
  const stored = localStorage.getItem(ACCENT_STORAGE_KEY) as AccentColor | null
  return stored && ACCENT_COLORS.some((a) => a.value === stored) ? stored : 'cyan'
}

/** Reactive mirror of the currently painted theme (post-'auto'-resolution) —
 * so UI like the sidebar's quick-toggle can reflect the real state, including
 * when it changes because Windows' own light/dark switch changed, not just
 * because the user picked something in Configurações. */
export const currentResolvedTheme = ref<ResolvedTheme>(resolveTheme(getInitialTheme()))

export function applyTheme(mode: ThemeMode): void {
  const resolved = resolveTheme(mode)
  document.documentElement.setAttribute('data-theme', resolved)
  currentResolvedTheme.value = resolved
  localStorage.setItem(THEME_STORAGE_KEY, mode)
}

export function applyAccent(accent: AccentColor): void {
  document.documentElement.setAttribute('data-accent', accent)
  localStorage.setItem(ACCENT_STORAGE_KEY, accent)
}

let systemThemeListenerBound = false

/** When mode is 'auto', the app should keep following Windows' light/dark
 * switch live instead of only reading it once at startup. */
export function watchSystemTheme(getMode: () => ThemeMode): void {
  if (systemThemeListenerBound || !window.matchMedia) return
  systemThemeListenerBound = true
  window.matchMedia('(prefers-color-scheme: light)').addEventListener('change', () => {
    if (getMode() === 'auto') applyTheme('auto')
  })
}
