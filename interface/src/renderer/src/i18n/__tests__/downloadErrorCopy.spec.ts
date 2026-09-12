import { describe, expect, it } from 'vitest'

/**
 * Cada motivo de falha de download que o backend classifica
 * (`_DOWNLOAD_MESSAGES` em api/eterzion_upscale/media.py) precisa de frase em
 * todas as línguas. Sem ela o vue-i18n devolve a própria chave e a tela
 * mostraria "errors.download.rateLimited.message" — trocar um texto técnico
 * por outro. A mesma lista está fixada do lado Python
 * (test_download_messages.py), então um motivo novo quebra um dos dois.
 */
const MOTIVOS = [
  'rateLimited',
  'serverUnavailable',
  'notFound',
  'network',
  'corrupted',
  'diskFull',
  'unknown'
]

type Frase = { message?: string; action?: string }
type Locale = {
  errors: {
    category: { downloadFailed: Frase }
    download?: Record<string, Frase>
  }
}

const locales = import.meta.glob<{ default: Locale }>('../locales/*.json', {
  eager: true
})

describe('frases de falha de download', () => {
  for (const [arquivo, mod] of Object.entries(locales)) {
    it(`${arquivo} tem frase para cada motivo, sem link`, () => {
      const erros = mod.default.errors
      expect(erros.category.downloadFailed.message).toBeTruthy()
      expect(erros.category.downloadFailed.action).toBeTruthy()
      for (const motivo of MOTIVOS) {
        const frase = erros.download?.[motivo]
        expect(frase?.message, `${arquivo}: errors.download.${motivo}.message`).toBeTruthy()
        expect(frase?.action, `${arquivo}: errors.download.${motivo}.action`).toBeTruthy()
        expect(`${frase?.message} ${frase?.action}`).not.toMatch(
          /https?:|:\/\/|\.safetensors|\.pth/
        )
      }
    })
  }
})
