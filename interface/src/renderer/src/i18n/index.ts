import { createI18n } from 'vue-i18n'
import ptBR from './locales/pt-BR.json'
import ptPT from './locales/pt-PT.json'
import en from './locales/en.json'
import es from './locales/es.json'
import ru from './locales/ru.json'
import fr from './locales/fr.json'
import de from './locales/de.json'
import it from './locales/it.json'
import ja from './locales/ja.json'
import ko from './locales/ko.json'
import zhHans from './locales/zh-Hans.json'

export const SUPPORTED_LOCALES = [
  { value: 'pt-BR', label: 'Português (Brasil)' },
  { value: 'pt-PT', label: 'Português (Portugal)' },
  { value: 'en', label: 'English' },
  { value: 'es', label: 'Español' },
  { value: 'ru', label: 'Русский' },
  { value: 'fr', label: 'Français' },
  { value: 'de', label: 'Deutsch' },
  { value: 'it', label: 'Italiano' },
  { value: 'ja', label: '日本語' },
  { value: 'ko', label: '한국어' },
  { value: 'zh-Hans', label: '简体中文' }
] as const

export type SupportedLocale = (typeof SUPPORTED_LOCALES)[number]['value']

const messages = {
  'pt-BR': ptBR,
  'pt-PT': ptPT,
  en,
  es,
  ru,
  fr,
  de,
  it,
  ja,
  ko,
  'zh-Hans': zhHans
}

/** navigator.language reflects the OS locale in Electron/Chromium — this is
 * the "detectar automaticamente o idioma do Windows" mechanism; no separate
 * main-process/IPC call needed. Maps to the closest supported locale, always
 * falling back to pt-BR (this app's native language) rather than English. */
export function detectSystemLocale(): SupportedLocale {
  const candidates = navigator.languages?.length ? navigator.languages : [navigator.language]
  for (const raw of candidates) {
    const lower = raw.toLowerCase()
    if (lower.startsWith('pt-br')) return 'pt-BR'
    if (lower.startsWith('pt')) return 'pt-PT'
    if (lower.startsWith('zh')) return 'zh-Hans'
    const exact = SUPPORTED_LOCALES.find((l) => l.value.toLowerCase() === lower)
    if (exact) return exact.value
    const byLanguage = SUPPORTED_LOCALES.find((l) =>
      lower.startsWith(l.value.toLowerCase().split('-')[0])
    )
    if (byLanguage) return byLanguage.value
  }
  return 'pt-BR'
}

export const i18n = createI18n({
  legacy: false,
  locale: 'pt-BR', // App.vue sets the real initial locale before mount, from settingsState
  fallbackLocale: 'pt-BR',
  messages
})

export function setLocale(locale: SupportedLocale): void {
  i18n.global.locale.value = locale
  document.documentElement.setAttribute('lang', locale)
}
