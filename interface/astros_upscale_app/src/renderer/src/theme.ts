export type ThemeMode = 'dark' | 'light'

const STORAGE_KEY = 'astros-upscale:theme'

export function getInitialTheme(): ThemeMode {
  const stored = localStorage.getItem(STORAGE_KEY)
  if (stored === 'dark' || stored === 'light') return stored
  return window.matchMedia?.('(prefers-color-scheme: light)').matches ? 'light' : 'dark'
}

export function applyTheme(mode: ThemeMode): void {
  document.documentElement.setAttribute('data-theme', mode)
  localStorage.setItem(STORAGE_KEY, mode)
}
