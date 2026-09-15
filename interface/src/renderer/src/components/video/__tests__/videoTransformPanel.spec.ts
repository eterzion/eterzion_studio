import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import VideoTransformPanel from '../VideoTransformPanel.vue'
import { neutralEdits } from '../../../composables/useVideoEdits'
import { i18n, setLocale } from '../../../i18n'

// Sem "Tamanho de saida" (ignorava a escala: com upscale 2x continuava
// mostrando o tamanho da origem) e o intervalo so' quando ha' corte ("video
// inteiro" nao dizia nada).

function montar(trim: { start_seconds: number; end_seconds: number } | null) {
  setLocale('pt-BR')
  return mount(VideoTransformPanel, {
    props: {
      transform: neutralEdits().transform,
      trim,
      formatTime: (s: number) => `${s}s`
    },
    global: { plugins: [i18n] }
  })
}

describe('VideoTransformPanel', () => {
  it('sem corte, nao aparece a linha de intervalo', () => {
    const w = montar(null)
    expect(w.text()).not.toContain(i18n.global.t('videoEditor.edits.trim'))
    expect(w.text()).not.toContain(i18n.global.t('videoEditor.edits.clearTrim'))
    w.unmount()
  })

  it('com corte, mostra o intervalo e o botao de remover', async () => {
    const w = montar({ start_seconds: 2, end_seconds: 5 })
    expect(w.text()).toContain('2s')
    expect(w.text()).toContain('5s')
    const remover = w
      .findAll('button')
      .find((b) => b.text() === i18n.global.t('videoEditor.edits.clearTrim'))
    await remover!.trigger('click')
    expect(w.emitted('clearTrim')).toHaveLength(1)
    w.unmount()
  })

  it('nao mostra mais o tamanho de saida', () => {
    const w = montar(null)
    expect(w.text()).not.toMatch(/\d+\s*×\s*\d+/)
    w.unmount()
  })
})
