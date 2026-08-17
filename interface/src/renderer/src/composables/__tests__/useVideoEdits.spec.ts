import { describe, expect, it } from 'vitest'
import { ref } from 'vue'
import {
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
      expect(hasUnpreviewableEffects(edits)).toBe(true)
    })
  })
})

describe('eq parity with FFmpeg', () => {
  // The renderer half of the contract test_video_edits.py pins on the FFmpeg
  // side. Both implement libavfilter/vf_eq.c's luma path:
  //   v = contrast * (v - 0.5) + 0.5 + brightness;  v = pow(v, 1/gamma)

  it('is the identity at neutral values', () => {
    for (const v of [0, 0.25, 0.5, 0.75, 1]) {
      expect(eqLuma(v, { brightness: 0, contrast: 1, gamma: 1 })).toBeCloseTo(v, 6)
    }
  })

  it('treats brightness as additive, not multiplicative', () => {
    // The single fact that ruled out CSS filters. Multiplicative brightness
    // would leave 0 at 0; additive lifts it.
    expect(eqLuma(0, { brightness: 0.2, contrast: 1, gamma: 1 })).toBeCloseTo(0.2, 6)
    expect(eqLuma(0.5, { brightness: 0.2, contrast: 1, gamma: 1 })).toBeCloseTo(0.7, 6)
  })

  it('pivots contrast about the midpoint', () => {
    expect(eqLuma(0.5, { brightness: 0, contrast: 2, gamma: 1 })).toBeCloseTo(0.5, 6)
    expect(eqLuma(0.75, { brightness: 0, contrast: 2, gamma: 1 })).toBeCloseTo(1, 6)
  })

  it('applies gamma as an inverse power', () => {
    expect(eqLuma(0.25, { brightness: 0, contrast: 1, gamma: 2 })).toBeCloseTo(Math.sqrt(0.25), 6)
  })

  it('clamps before the gamma pass, as vf_eq.c does', () => {
    // pow() of a negative number is NaN. Order matters, and getting it wrong
    // renders black pixels rather than an obvious error.
    expect(eqLuma(0, { brightness: -0.5, contrast: 1, gamma: 2 })).toBe(0)
    expect(Number.isNaN(eqLuma(0, { brightness: -0.5, contrast: 1, gamma: 2 }))).toBe(false)
  })

  it('never divides by zero on gamma', () => {
    expect(Number.isFinite(eqLuma(0.5, { brightness: 0, contrast: 1, gamma: 0 }))).toBe(true)
  })
})
