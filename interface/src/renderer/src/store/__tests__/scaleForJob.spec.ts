import { describe, expect, it, vi } from 'vitest'

vi.mock('../../services/native', () => ({
  hasNativeApi: false,
  api: { toFileUrl: (p: string) => p }
}))
vi.mock('../../services/api', () => ({
  detectContentType: () => Promise.resolve('photo'),
  createLocalJob: vi.fn(),
  getJobStatus: vi.fn(),
  exportJob: vi.fn(),
  cancelJob: vi.fn(),
  errorCategoryCopy: () => ({ message: '', action: '' })
}))
vi.mock('../history', () => ({ recordJob: vi.fn(), recordSimpleJob: vi.fn() }))
vi.mock('../settings', () => ({
  settingsState: { defaultScalePreset: 2, defaultLockAspectRatio: true, defaultQuality: 90 }
}))

import { scaleForJob } from '../jobs'
import type { Job } from '../jobs'

// Custom mode used to send whichever preset factor happened to be selected, so
// asking for a 2x-sized output while the preset sat on 4x ran the 4x model and
// threw most of it away in a downscale. The pass now follows the target.

function job(overrides: Record<string, unknown> = {}): Job {
  const scale = {
    mode: 'custom',
    presetFactor: 4,
    customWidth: 128,
    customHeight: 128,
    ...((overrides.scaleConfig as Record<string, unknown>) ?? {})
  }
  return {
    sourceMeta: { width: 64, height: 64, format: 'PNG', sizeBytes: 1 },
    scaleConfig: scale
  } as unknown as Job
}

describe('scaleForJob', () => {
  it('asks for no model at all in Original', () => {
    expect(scaleForJob(job({ scaleConfig: { mode: 'original' } }))).toBe('1x')
  })

  it('asks for no model at all in Pixel art', () => {
    expect(scaleForJob(job({ scaleConfig: { mode: 'pixel' } }))).toBe('1x')
  })

  it('uses the chosen factor in Preset', () => {
    expect(scaleForJob(job({ scaleConfig: { mode: 'preset', presetFactor: 2 } }))).toBe('2x')
    expect(scaleForJob(job({ scaleConfig: { mode: 'preset', presetFactor: 4 } }))).toBe('4x')
  })

  describe('in Custom, the pass follows the target that was typed', () => {
    it('a doubling uses the 2x pass even when the preset says 4x', () => {
      expect(scaleForJob(job({ scaleConfig: { customWidth: 128, customHeight: 128 } }))).toBe('2x')
    })

    it('below a doubling also uses 2x — never less than what is asked for', () => {
      expect(scaleForJob(job({ scaleConfig: { customWidth: 96, customHeight: 96 } }))).toBe('2x')
    })

    it('exactly 2x is still the 2x pass, not the next one up', () => {
      expect(scaleForJob(job({ scaleConfig: { customWidth: 128, customHeight: 128 } }))).toBe('2x')
    })

    it('beyond a doubling moves up to 4x', () => {
      expect(scaleForJob(job({ scaleConfig: { customWidth: 129, customHeight: 129 } }))).toBe('4x')
      expect(scaleForJob(job({ scaleConfig: { customWidth: 256, customHeight: 256 } }))).toBe('4x')
    })

    it('the larger side decides, so neither dimension is under-served', () => {
      // 64 -> 80 wide is 1.25x, but 64 -> 200 tall is 3.1x.
      expect(scaleForJob(job({ scaleConfig: { customWidth: 80, customHeight: 200 } }))).toBe('4x')
    })

    it('falls back to the preset when the source size is unknown', () => {
      const unsized = job({ scaleConfig: { presetFactor: 4 } })
      unsized.sourceMeta.width = null
      unsized.sourceMeta.height = null
      expect(scaleForJob(unsized)).toBe('4x')
    })
  })
})
