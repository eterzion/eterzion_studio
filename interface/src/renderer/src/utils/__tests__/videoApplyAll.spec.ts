import { describe, expect, it } from 'vitest'
import { reactive } from 'vue'
import { copiarConfiguracao, type VideoConfig } from '../videoApplyAll'
import { neutralEdits } from '../../composables/useVideoEdits'
import type { EnhanceSettings } from '../../components/video/VideoEnhancePanel.vue'

// "Aplicar esta configuracao a todos" no Video: vai o que vale para qualquer
// video, fica o que e' de cada arquivo (recorte e trecho).

function melhoria(mudanca: Partial<EnhanceSettings> = {}): EnhanceSettings {
  return {
    scale: '2x',
    lockAspectRatio: true,
    customWidth: null,
    customHeight: null,
    contentType: 'real_video',
    profile: 'balanced',
    device: 'auto',
    ...mudanca
  }
}

// Reativos, como na tela: o primeiro defeito foi exatamente com eles
// (structuredClone recusa proxies do Vue, e o clique falhava em silencio).
function video(width: number, height: number, enhance = melhoria()): VideoConfig {
  return reactive({ edits: neutralEdits(), enhance, width, height }) as VideoConfig
}

describe('copiarConfiguracao', () => {
  it('leva melhoria, ajustes, efeitos, audio, rotacao e espelhamento', () => {
    const origem = video(640, 480, melhoria({ contentType: 'anime_video', profile: 'quality' }))
    origem.edits.adjustments.brightness = 0.2
    origem.edits.adjustments.brightness_enabled = true
    origem.edits.effects.grain_enabled = true
    origem.edits.audio.mode = 'mute'
    origem.edits.transform.rotation_degrees = 90
    origem.edits.transform.flip_horizontal = true
    const destino = video(1280, 720)

    copiarConfiguracao(origem, destino)

    expect(destino.enhance.contentType).toBe('anime_video')
    expect(destino.enhance.profile).toBe('quality')
    expect(destino.edits.adjustments.brightness).toBe(0.2)
    expect(destino.edits.adjustments.brightness_enabled).toBe(true)
    expect(destino.edits.effects.grain_enabled).toBe(true)
    expect(destino.edits.audio.mode).toBe('mute')
    expect(destino.edits.transform.rotation_degrees).toBe(90)
    expect(destino.edits.transform.flip_horizontal).toBe(true)
  })

  it('recorte e trecho continuam os de cada video', () => {
    const origem = video(640, 480)
    origem.edits.trim = { start_seconds: 10, end_seconds: 20 }
    origem.edits.transform.crop = { x: 0, y: 0, width: 320, height: 240 }
    const destino = video(1280, 720)

    copiarConfiguracao(origem, destino)

    expect(destino.edits.trim).toBeNull()
    expect(destino.edits.transform.crop).toBeNull()
  })

  it('o tamanho personalizado vai como fator, recalculado para cada video', () => {
    const origem = video(
      640,
      480,
      melhoria({ scale: 'custom', customWidth: 1280, customHeight: 960 })
    )
    const destino = video(1000, 500)

    copiarConfiguracao(origem, destino)

    expect(destino.enhance.customWidth).toBe(2000)
    expect(destino.enhance.customHeight).toBe(1000)
  })

  it('a copia nao fica ligada a origem', () => {
    const origem = video(640, 480)
    const destino = video(640, 480)
    copiarConfiguracao(origem, destino)
    origem.edits.adjustments.contrast = 0.5
    expect(destino.edits.adjustments.contrast).not.toBe(0.5)
  })
})
