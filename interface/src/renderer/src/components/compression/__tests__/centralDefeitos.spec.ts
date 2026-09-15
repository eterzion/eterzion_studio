import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { mount } from '@vue/test-utils'
import { i18n, setLocale } from '../../../i18n'
import VideoCompressionSettings from '../VideoCompressionSettings.vue'

// Tres defeitos da Central de Compressao que nada acusava, porque cada um
// "funcionava" no sentido de nao dar erro:
//
// - o motivo de indisponibilidade que o backend manda nao tinha traducao, e a
//   tela esperava dois que ele nunca envia;
// - a dica do padrao de nome sumia com o `{filename}`, que o vue-i18n tratava
//   como parametro -- a dica existia justamente para mostrar esse marcador;
// - o seletor de container aparecia no modo Basico, que por regra nao envia
//   container: a escolha era descartada sem aviso.

const raiz = resolve(process.cwd(), '..')

function motivosDoBackend(): string[] {
  const schemas = readFileSync(resolve(raiz, 'api/eterzion_upscale_api/app/schemas.py'), 'utf8')
  const bloco = /^UnavailableReason = Literal\[([\s\S]*?)\]/m.exec(schemas)?.[1]
  expect(bloco, 'UnavailableReason nao encontrado em schemas.py').toBeTruthy()
  return [...bloco!.matchAll(/'([a-z_]+)'/g)].map((m) => m[1]).sort()
}

function motivosDaTela(): string[] {
  const fonte = readFileSync(
    resolve(process.cwd(), 'src/renderer/src/services/compression.ts'),
    'utf8'
  )
  const bloco = /export type UnavailableReason =([\s\S]*?)\n\n/.exec(fonte)?.[1]
  expect(bloco, 'UnavailableReason nao encontrado em compression.ts').toBeTruthy()
  return [...bloco!.matchAll(/\|\s*'([a-z_]+)'/g)].map((m) => m[1]).sort()
}

describe('motivos de indisponibilidade', () => {
  it('a tela conhece exatamente os motivos que o backend manda', () => {
    expect(motivosDaTela()).toEqual(motivosDoBackend())
  })

  it('cada motivo tem traducao em todos os idiomas', () => {
    const pasta = resolve(process.cwd(), 'src/renderer/src/i18n/locales')
    for (const arquivo of [
      'pt-BR',
      'pt-PT',
      'en',
      'es',
      'fr',
      'de',
      'it',
      'ja',
      'ko',
      'ru',
      'zh-Hans'
    ]) {
      const msgs = JSON.parse(readFileSync(resolve(pasta, `${arquivo}.json`), 'utf8'))
      for (const motivo of motivosDoBackend()) {
        expect(msgs.compression.unavailable[motivo], `${arquivo}: ${motivo}`).toBeTruthy()
      }
    }
  })
})

describe('textos com marcadores de nome', () => {
  it('a dica do padrao mostra o {filename}, e a recusa lista os marcadores validos', () => {
    setLocale('pt-BR')
    const { t } = i18n.global
    expect(t('compression.export.patternHint')).toContain('{filename}')
    const recusa = t('compression.refusal.invalid_naming_pattern')
    for (const m of ['{filename}', '{quality}', '{resolution}', '{codec}']) {
      expect(recusa).toContain(m)
    }
  })
})

describe('seletor de container', () => {
  function rotulos(mode: 'basic' | 'advanced'): string[] {
    setLocale('pt-BR')
    const w = mount(VideoCompressionSettings, {
      props: { settings: {}, target: null, mode, capabilities: null },
      global: { plugins: [i18n] }
    })
    const textos = w.findAll('.setting-row').map((r) => r.text())
    w.unmount()
    return textos
  }

  const container = (): string => i18n.global.t('compression.video.container')

  it('nao aparece no modo Basico, que por regra nao envia container', () => {
    expect(rotulos('basic').some((r) => r.includes(container()))).toBe(false)
  })

  it('aparece no modo Avancado', () => {
    expect(rotulos('advanced').some((r) => r.includes(container()))).toBe(true)
  })
})
