import { beforeAll, describe, expect, it, vi } from 'vitest'

vi.mock('../../services/native', () => ({
  hasNativeApi: true,
  api: {
    getAppVersion: () => Promise.resolve('9.9.9'),
    selectOutputFolder: () => Promise.resolve(null)
  }
}))
vi.mock('../../services/api', () => ({ listComponents: () => Promise.resolve([]) }))

import { mount, flushPromises } from '@vue/test-utils'
import { i18n, setLocale } from '../../i18n'
import SettingsView from '../SettingsView.vue'

// "Atualizacoes" e "Avancado" eram dois cartoes, e o segundo repetia a versao
// do app ja mostrada no primeiro. Viraram um so', "Versao e atualizacoes". O
// teste olha o que a pessoa ve -- os titulos dos cartoes -- e nao a estrutura
// do template, que pode mudar sem mudar a tela.

beforeAll(() => {
  // As versoes tecnicas so aparecem quando o preload as expoe.
  ;(window as unknown as { electron: unknown }).electron = {
    process: { versions: { electron: '43.4.0', chrome: '140.0', node: '24.0.0' } }
  }
  setLocale('pt-BR')
})

async function montar(): Promise<ReturnType<typeof mount>> {
  const wrapper = mount(SettingsView, { global: { plugins: [i18n] } })
  await flushPromises()
  return wrapper
}

function titulos(wrapper: ReturnType<typeof mount>): string[] {
  return wrapper.findAll('.group-title').map((h) => h.text())
}

describe('Configuracoes — Versao e atualizacoes', () => {
  it('tem um cartao "Versao e atualizacoes", e nenhum "Atualizacoes" ou "Avancado" solto', async () => {
    const w = await montar()
    const t = titulos(w)
    expect(t).toContain('Versão e atualizações')
    expect(t).not.toContain('Atualizações')
    expect(t).not.toContain('Avançado')
    w.unmount()
  })

  it('as versoes do Electron, Chromium e Node ficam dentro desse cartao', async () => {
    const w = await montar()
    const cartao = w
      .findAll('.settings-group')
      .find((s) => s.find('.group-title').text() === 'Versão e atualizações')
    expect(cartao, 'cartao nao encontrado').toBeTruthy()
    expect(cartao!.text()).toContain('Electron 43.4.0')
    expect(cartao!.text()).toContain('Node 24.0.0')
    w.unmount()
  })

  it('a versao do app aparece uma vez so', async () => {
    // Era o motivo de juntar: "Versao instalada 9.9.9" no primeiro cartao e
    // "Versao do aplicativo 9.9.9" no segundo.
    const w = await montar()
    expect(w.text().split('9.9.9').length - 1).toBe(1)
    w.unmount()
  })
})
