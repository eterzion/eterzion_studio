import { describe, expect, it } from 'vitest'
import { ref } from 'vue'
import {
  effectiveAdjustments,
  neutralAdjustments,
  neutralEffects,
  neutralTransform,
  hasUnpreviewableEffects,
  neutralEdits,
  useVideoEdits,
  type VideoEditSet
} from '../useVideoEdits'
import { eqLuma } from '../useVideoPreviewPipeline'

// T040 (specs/007-video-editor-player)

describe('useVideoEdits', () => {
  describe('per-video isolation (FR-003)', () => {
    it('keeps each video its own edits', () => {
      const active = ref<string | null>('a')
      const store = useVideoEdits(active)

      store.editsFor('a').adjustments.contrast = 1.5
      active.value = 'b'
      expect(store.current.value.adjustments.contrast).toBe(1)

      active.value = 'a'
      expect(store.current.value.adjustments.contrast).toBe(1.5)
    })

    it('forgets a removed video without touching the others', () => {
      const active = ref<string | null>('a')
      const store = useVideoEdits(active)
      store.editsFor('a').adjustments.gamma = 2
      store.editsFor('b').adjustments.gamma = 3
      store.forget('a')
      active.value = 'b'
      expect(store.current.value.adjustments.gamma).toBe(3)
    })

    it('falls back to a neutral set when nothing is selected', () => {
      const store = useVideoEdits(ref(null))
      expect(store.current.value).toEqual(neutralEdits())
      expect(store.isNeutral.value).toBe(true)
    })
  })

  describe('reset (FR-004)', () => {
    it('discards all five families, not only the image adjustments', () => {
      // The reading FR-004 was disambiguated to forbid: "ajustes" names one
      // family, "edições" names the set. A reset that cleared only the first
      // would satisfy a careless reading and leave a crop and a trim behind.
      const active = ref<string | null>('a')
      const store = useVideoEdits(active)
      const edits = store.editsFor('a')
      edits.adjustments.contrast = 1.8
      edits.effects.denoise_enabled = true
      edits.transform.rotation_degrees = 90
      edits.transform.crop = { x: 0, y: 0, width: 100, height: 100 }
      edits.trim = { start_seconds: 1, end_seconds: 2 }
      edits.audio.mode = 'remove'

      store.reset('a')

      expect(store.current.value).toEqual(neutralEdits())
      expect(store.isNeutral.value).toBe(true)
    })
  })

  describe('FR-015 disclosure', () => {
    function withEffects(overrides: Partial<VideoEditSet['effects']>): VideoEditSet {
      const edits = neutralEdits()
      Object.assign(edits.effects, overrides)
      return edits
    }

    it('says nothing is hidden for a neutral set', () => {
      expect(hasUnpreviewableEffects(neutralEdits())).toBe(false)
    })

    it('says nothing is hidden for adjustments the shader reproduces', () => {
      const edits = neutralEdits()
      edits.adjustments.brightness = 0.3
      edits.adjustments.contrast = 1.4
      edits.adjustments.saturation = 0.6
      edits.adjustments.gamma = 1.2
      edits.adjustments.hue_degrees = 45
      expect(hasUnpreviewableEffects(edits)).toBe(false)
    })

    it.each([
      ['denoise', { denoise_enabled: true, denoise_strength: 40 }],
      ['blur', { blur_enabled: true, blur_strength: 20 }],
      ['grain', { grain_enabled: true, grain_strength: 10 }]
    ])('discloses %s', (_name, overrides) => {
      expect(hasUnpreviewableEffects(withEffects(overrides))).toBe(true)
    })

    it('does not disclose an effect that is enabled at zero strength', () => {
      expect(
        hasUnpreviewableEffects(withEffects({ denoise_enabled: true, denoise_strength: 0 }))
      ).toBe(false)
    })

    it('discloses sharpness even though it sits under adjustments', () => {
      // It maps to unsharp, a 5×5 convolution the shader does not implement.
      // Its position next to brightness is not evidence that it is previewed.
      const edits = neutralEdits()
      edits.adjustments.sharpness = 0.5
      // Ligado explicitamente: cada ajuste tem seu interruptor, e um valor sem
      // interruptor ligado não é aplicado — nem, portanto, divulgado.
      edits.adjustments.sharpness_enabled = true
      expect(hasUnpreviewableEffects(edits)).toBe(true)
    })
  })
})

describe('eq parity with FFmpeg', () => {
  // The renderer half of the parity test_video_edits.py measures against real
  // FFmpeg. Both implement libavfilter/vf_eq.c's luma path -- crucially, on the
  // STORED plane, which video carries in limited range (16..235):
  //   stored = (16 + 219*v)/255
  //   stored' = contrast*(stored - 0.5) + 0.5 + brightness
  //   stored'' = pow(stored', 1/gamma)
  //   v' = (stored''*255 - 16)/219
  //
  // The first version of this omitted the range hop and disagreed with FFmpeg
  // by exactly 255/219. The shader was corrected, not the tolerance.

  const RANGE = 255 / 219

  it('is the identity at neutral values', () => {
    // The range hop must round-trip exactly, or every untouched frame would
    // shift slightly the moment the shader is switched on.
    for (const v of [0, 0.25, 0.5, 0.75, 1]) {
      expect(eqLuma(v, { brightness: 0, contrast: 1, gamma: 1 })).toBeCloseTo(v, 6)
    }
  })

  it('treats brightness as additive, not multiplicative', () => {
    // The fact that ruled CSS filters out: multiplicative brightness leaves
    // black at black, additive lifts it.
    expect(eqLuma(0, { brightness: 0.2, contrast: 1, gamma: 1 })).toBeGreaterThan(0.2)
    // And it lands where limited range says it should, not where a naive
    // full-range reading would put it.
    expect(eqLuma(0, { brightness: 0.2, contrast: 1, gamma: 1 })).toBeCloseTo(0.2 * RANGE, 4)
  })

  it('scales a brightness step by the range factor', () => {
    const step = 0.1
    const a = eqLuma(0.5, { brightness: 0, contrast: 1, gamma: 1 })
    const b = eqLuma(0.5, { brightness: step, contrast: 1, gamma: 1 })
    expect(b - a).toBeCloseTo(step * RANGE, 4)
  })

  it('pivots contrast about the stored midpoint', () => {
    // Stored 0.5 is full-range 0.5137, not 0.5 -- the pivot lives in the plane
    // the filter operates on, not in the one the display shows.
    const pivot = (0.5 * 255 - 16) / 219
    expect(eqLuma(pivot, { brightness: 0, contrast: 2, gamma: 1 })).toBeCloseTo(pivot, 4)
  })

  it('applies gamma as an inverse power in stored space', () => {
    const stored = (16 + 219 * 0.5) / 255
    const expected = (Math.pow(stored, 1 / 2) * 255 - 16) / 219
    expect(eqLuma(0.5, { brightness: 0, contrast: 1, gamma: 2 })).toBeCloseTo(expected, 6)
  })

  it('clamps before the gamma pass, as vf_eq.c does', () => {
    // pow() of a negative is NaN, and a NaN pixel renders as garbage rather
    // than as an obvious error.
    const result = eqLuma(0, { brightness: -0.5, contrast: 1, gamma: 2 })
    expect(Number.isNaN(result)).toBe(false)
    expect(result).toBe(0)
  })

  it('never returns a value outside 0..1', () => {
    // Stored 16 maps back to full-range 0; anything below it is not a colour.
    for (const brightness of [-1, -0.5, 0, 0.5, 1]) {
      for (const v of [0, 0.5, 1]) {
        const result = eqLuma(v, { brightness, contrast: 1, gamma: 1 })
        expect(result).toBeGreaterThanOrEqual(0)
        expect(result).toBeLessThanOrEqual(1)
      }
    }
  })

  it('never divides by zero on gamma', () => {
    expect(Number.isFinite(eqLuma(0.5, { brightness: 0, contrast: 1, gamma: 0 }))).toBe(true)
  })
})

describe('interruptor por ajuste', () => {
  it('lê como neutro o controle desligado, preservando o valor', () => {
    const a = { ...neutralAdjustments(), brightness: 0.5, brightness_enabled: false }
    // O valor continua lá — desligar guarda a escolha em vez de jogá-la fora.
    expect(a.brightness).toBe(0.5)
    expect(effectiveAdjustments(a).brightness).toBe(0)
  })

  it('aplica o valor quando ligado', () => {
    const a = { ...neutralAdjustments(), brightness: 0.5, brightness_enabled: true }
    expect(effectiveAdjustments(a).brightness).toBe(0.5)
  })

  it('cada interruptor governa só o seu controle', () => {
    const a = {
      ...neutralAdjustments(),
      brightness: 0.5,
      brightness_enabled: false,
      contrast: 1.6,
      contrast_enabled: true
    }
    const e = effectiveAdjustments(a)
    expect(e.brightness).toBe(0)
    expect(e.contrast).toBe(1.6)
  })

  it('não avisa sobre nitidez que está desligada', () => {
    // A divulgação do FR-015 anunciaria algo que a exportação não vai fazer.
    const edits = {
      adjustments: { ...neutralAdjustments(), sharpness: 1.2, sharpness_enabled: false },
      effects: neutralEffects(),
      transform: neutralTransform(),
      trim: null,
      audio: { mode: 'keep' as const, volume: 1 }
    }
    expect(hasUnpreviewableEffects(edits)).toBe(false)
    edits.adjustments.sharpness_enabled = true
    expect(hasUnpreviewableEffects(edits)).toBe(true)
  })
})

describe('reset por painel', () => {
  it('zera só os ajustes, deixando os efeitos', () => {
    const store = useVideoEdits(ref('a'))
    const edits = store.editsFor('a')
    edits.adjustments.brightness = 0.4
    edits.adjustments.brightness_enabled = true
    edits.effects.denoise_enabled = true

    store.resetAdjustments('a')
    expect(edits.adjustments).toEqual(neutralAdjustments())
    expect(edits.effects.denoise_enabled).toBe(true)
  })

  it('zera só os efeitos, deixando os ajustes', () => {
    const store = useVideoEdits(ref('a'))
    const edits = store.editsFor('a')
    edits.adjustments.brightness_enabled = true
    edits.effects.blur_enabled = true

    store.resetEffects('a')
    expect(edits.effects).toEqual(neutralEffects())
    expect(edits.adjustments.brightness_enabled).toBe(true)
  })
})
