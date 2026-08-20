import { describe, expect, it } from 'vitest'

// The video panel used to send '2x' for every exact-size request, whatever the
// size typed: asking for a 4x-sized frame ran the 2x model and interpolated the
// rest of the way up, paying for a model pass and discarding what it was for.
// The rule now matches the Imagem screen's.

function scaleForRequest(
  scale: '2x' | '4x' | 'custom',
  source: { width: number | null; height: number | null },
  custom: { width: number | null; height: number | null }
): '2x' | '4x' {
  if (scale === '2x' || scale === '4x') return scale
  if (!source.width || !source.height || !custom.width || !custom.height) return '2x'
  return Math.max(custom.width / source.width, custom.height / source.height) <= 2 ? '2x' : '4x'
}

const source = { width: 640, height: 480 }

describe('which model pass a video asks for', () => {
  it('an explicit factor is used as-is', () => {
    expect(scaleForRequest('2x', source, { width: null, height: null })).toBe('2x')
    expect(scaleForRequest('4x', source, { width: null, height: null })).toBe('4x')
  })

  it('a doubling uses the 2x pass', () => {
    expect(scaleForRequest('custom', source, { width: 1280, height: 960 })).toBe('2x')
  })

  it('below a doubling also uses 2x — never less than what is asked for', () => {
    expect(scaleForRequest('custom', source, { width: 800, height: 600 })).toBe('2x')
  })

  it('exactly 2x stays on the 2x pass, not the next one up', () => {
    expect(scaleForRequest('custom', source, { width: 1280, height: 960 })).toBe('2x')
  })

  it('beyond a doubling moves up to 4x', () => {
    expect(scaleForRequest('custom', source, { width: 1281, height: 961 })).toBe('4x')
    expect(scaleForRequest('custom', source, { width: 2560, height: 1920 })).toBe('4x')
  })

  it('the larger side decides, so neither dimension is under-served', () => {
    // 640 -> 700 wide is 1.09x, but 480 -> 1600 tall is 3.3x.
    expect(scaleForRequest('custom', source, { width: 700, height: 1600 })).toBe('4x')
  })

  it('falls back to 2x when the source size is unknown', () => {
    expect(
      scaleForRequest('custom', { width: null, height: null }, { width: 4000, height: 3000 })
    ).toBe('2x')
  })
})
