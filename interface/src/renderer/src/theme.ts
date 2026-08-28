import { ref } from 'vue'

export type ThemeMode = 'dark' | 'light' | 'auto'
export type ResolvedTheme = 'dark' | 'light'

const THEME_STORAGE_KEY = 'eterzion-studio:theme'

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
