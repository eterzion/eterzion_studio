import { beforeAll, describe, expect, it, vi } from 'vitest'

vi.mock('../../services/native', () => ({
  hasNativeApi: true,
  api: {
    getAppVersion: () => Promise.resolve('1.2.6'),
    selectOutputFolder: () => Promise.resolve(null)
  }
}))
vi.mock('../../services/api', () => ({ listComponents: () => Promise.resolve([]) }))

import { mount, flushPromises } from '@vue/test-utils'
import { i18n, setLocale } from '../../i18n'
import SettingsView from '../SettingsView.vue'
import { updatesState } from '../../store/updates'
import { readFileSync, readdirSync } from 'node:fs'
import { join } from 'node:path'

// Enquanto baixa, a tela dizia so' a porcentagem: "Baixando a versao 1.2.6...
// 49%". Quanto falta em minutos depende do tamanho, e 341 MB numa conexao ruim
// e' uma decisao diferente de 30 MB -- entao o tamanho aparece junto.

const MB = 1024 * 1024

beforeAll(() => setLocale('pt-BR'))

/** A linha de estado, sob "Versao instalada". Olhar so' ela, e nao a tela
 *  inteira, porque o travessao e o "de" aparecem em outros textos da pagina. */
function estado(w: ReturnType<typeof mount>): string {
  const linha = w.findAll('.setting-description').map((s) => s.text())
  return linha.find((texto) => texto.includes('1.2.6')) ?? ''
}

async function montarBaixando(
  transferred: number | null,
  totalBytes: number | null
): Promise<ReturnType<typeof mount>> {
  Object.assign(updatesState, {
    phase: 'downloading',
    version: '1.2.6',
    percent: 49,
    transferred,
    totalBytes
  })
  const w = mount(SettingsView, { global: { plugins: [i18n] } })
  await flushPromises()
  return w
}

describe('progresso do download da atualizacao', () => {
  it('mostra quanto ja esta pronto e o tamanho total', async () => {
    const w = await montarBaixando(168 * MB, 341 * MB)
    expect(estado(w)).toBe('Baixando a versão 1.2.6… 49% — 168 MB de 341 MB')
    w.unmount()
  })

  it('antes do primeiro progresso, mantem a frase sem tamanhos', async () => {
    const w = await montarBaixando(null, null)
    // A frase inteira: um tamanho desconhecido nao pode virar "0 B de —"
    // pendurado no fim.
    expect(estado(w)).toBe('Baixando a versão 1.2.6… 49%')
    w.unmount()
  })

  it('nunca passa do total: o download diferencial as vezes fecha com bytes a mais', async () => {
    const w = await montarBaixando(350 * MB, 341 * MB)
    expect(estado(w)).toContain('341 MB de 341 MB')
    w.unmount()
  })
})

// A paridade de chaves ja' e' testada em i18n/localeParity.spec.ts. O que falta
// e' o campo dentro da frase: uma traducao que esqueca {done} nao quebra, so'
// deixa de dizer o tamanho -- exatamente o que esta mudanca veio fazer.
const LOCALES = join(__dirname, '..', '..', 'i18n', 'locales')

describe('a frase com tamanho, em todos os idiomas', () => {
  for (const arquivo of readdirSync(LOCALES).filter((f) => f.endsWith('.json'))) {
    it(`${arquivo} tem version, percent, done e total`, () => {
      const messages = JSON.parse(readFileSync(join(LOCALES, arquivo), 'utf-8'))
      const frase: string = messages.settings.updates.status.downloadingWithSize
      for (const campo of ['{version}', '{percent}', '{done}', '{total}']) {
        expect(frase, campo).toContain(campo)
      }
    })
  }
})
