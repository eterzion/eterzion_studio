import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'

vi.mock('../../../services/api', async (original) => ({
  ...(await original<typeof import('../../../services/api')>()),
  getVideoExportOptions: vi.fn(async () => ({
    containers: [{ value: 'mp4', available: true }]
  }))
}))

import VideoExportPanel from '../VideoExportPanel.vue'
import { i18n, setLocale } from '../../../i18n'

// As acoes ficam abaixo de tudo, fora do painel, como na Imagem: primeiro o
// "Aplicar a todos" (que a tela passa pelo slot), depois o botao de exportar.

describe('VideoExportPanel', () => {
  it('aplicar a todos e exportar ficam abaixo do painel, nesta ordem', () => {
    setLocale('pt-BR')
    const w = mount(VideoExportPanel, {
      props: { state: null, directory: null, sourceName: 'clip.mp4' },
      slots: { 'before-actions': '<button class="aplicar">aplicar</button>' },
      global: { plugins: [i18n] }
    })
    const painel = w.find('section.panel')
    const acoes = w.find('.export-actions')
    expect(painel.exists() && acoes.exists()).toBe(true)
    // Fora do painel, e depois dele.
    expect(painel.element.contains(acoes.element)).toBe(false)
    expect(
      painel.element.compareDocumentPosition(acoes.element) & Node.DOCUMENT_POSITION_FOLLOWING
    ).toBeTruthy()
    const botoes = acoes.findAll('button').map((b) => b.text())
    expect(botoes[0]).toBe('aplicar')
    expect(botoes[1]).toBe(i18n.global.t('videoEditor.export.start'))
    w.unmount()
  })
})
