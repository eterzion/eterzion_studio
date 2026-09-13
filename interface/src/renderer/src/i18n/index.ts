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

/** O russo tem tres formas -- 1 (21, 31…), 2-4 (22-24…) e o resto, com 11-14
 *  no "resto" --, e a regra padrao do vue-i18n para tres formas e' outra
 *  (zero | um | varios): "1 dia" saia na segunda forma, "0 dias" na primeira.
 *  Com menos de tres formas na mensagem, vale a regra padrao. */
export function russianPlural(choice: number, choicesLength: number): number {
  if (choicesLength < 3) return choice === 1 ? 0 : 1
  const n = Math.abs(choice) % 100
  const unidade = n % 10
  if (n > 10 && n < 20) return 2
  if (unidade === 1) return 0
  if (unidade >= 2 && unidade <= 4) return 1
  return 2
}

export const i18n = createI18n({
  legacy: false,
  locale: 'pt-BR', // App.vue sets the real initial locale before mount, from settingsState
  fallbackLocale: 'pt-BR',
  messages,
  pluralRules: { ru: russianPlural }
})

export function setLocale(locale: SupportedLocale): void {
  i18n.global.locale.value = locale
  document.documentElement.setAttribute('lang', locale)
}
