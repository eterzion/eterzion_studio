import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

// As escolhas de exportacao sobrevivem a troca de tela: antes viviam dentro de
// cada tela, e sair e voltar as levava de volta ao padrao.

vi.mock('../../services/api', async (original) => ({
  ...(await original<typeof import('../../services/api')>()),
  getVideoExportOptions: vi.fn(async () => ({
    containers: [
      { value: 'mp4', available: true },
      { value: 'webm', available: true },
      { value: 'mkv', available: false }
    ]
  }))
}))

import { resetExportChoices, videoExportChoices } from '../exportChoices'
import { useExportPanel } from '../../composables/useExportPanel'
import VideoExportPanel from '../../components/video/VideoExportPanel.vue'
import { i18n, setLocale } from '../../i18n'

afterEach(() => resetExportChoices())

describe('escolhas de exportacao', () => {
  it('Imagem: a escolha feita numa montagem da tela aparece na proxima', () => {
    const primeira = useExportPanel()
    primeira.exportacao.value.format = 'jpg'
    primeira.exportacao.value.directory = 'C:\\saida'

    const segunda = useExportPanel() // a tela montada de novo
    expect(segunda.exportacao.value.format).toBe('jpg')
    expect(segunda.exportacao.value.directory).toBe('C:\\saida')
  })

  it('Video: voltar para a tela nao troca o formato guardado pelo primeiro disponivel', async () => {
    setLocale('pt-BR')
    videoExportChoices().container = 'webm'
    const w = mount(VideoExportPanel, {
      props: { state: null, directory: null, sourceName: 'clip.mp4' },
      global: { plugins: [i18n] }
    })
    await flushPromises()
    expect(videoExportChoices().container).toBe('webm')
    w.unmount()
  })

  it('Video: um formato guardado que esta maquina nao grava cai no primeiro disponivel', async () => {
    setLocale('pt-BR')
    videoExportChoices().container = 'mkv'
    const w = mount(VideoExportPanel, {
      props: { state: null, directory: null, sourceName: 'clip.mp4' },
      global: { plugins: [i18n] }
    })
    await flushPromises()
    expect(videoExportChoices().container).toBe('mp4')
    w.unmount()
  })
})
