import { describe, expect, it } from 'vitest'

import { formatBytes } from '../formatBytes'

// The panel used to print MB with two decimals everywhere, so a 1 KB icon read
// "0.00 MB" and its result read "0.00 MB" too — an accurate size comparison
// that told the person nothing. These pin the unit choice, which is the whole
// point of the helper.

describe('formatBytes', () => {
  it('reports a small icon in bytes, not as zero megabytes', () => {
    expect(formatBytes(1024)).toBe('1.0 KB')
    expect(formatBytes(900)).toBe('900 B')
  })

  it('does not collapse small files to the same value', () => {
    expect(formatBytes(1200)).not.toBe(formatBytes(4800))
  })

  it('climbs units as the file grows', () => {
    expect(formatBytes(5 * 1024)).toBe('5.0 KB')
    expect(formatBytes(2 * 1024 * 1024)).toBe('2.0 MB')
    expect(formatBytes(3 * 1024 * 1024 * 1024)).toBe('3.0 GB')
  })

  it('drops the decimal once the number is big enough not to need it', () => {
    expect(formatBytes(847 * 1024 * 1024)).toBe('847 MB')
  })

  it('has a fallback for a size nobody measured', () => {
    expect(formatBytes(null)).toBe('—')
    expect(formatBytes(undefined)).toBe('—')
    expect(formatBytes(null, 'sem dados')).toBe('sem dados')
  })

  it('handles zero without pretending it is unknown', () => {
    expect(formatBytes(0)).toBe('0 B')
  })
})
