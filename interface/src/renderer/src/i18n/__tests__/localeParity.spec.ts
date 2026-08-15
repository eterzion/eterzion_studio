import { describe, expect, it } from 'vitest'
import { readFileSync, readdirSync } from 'node:fs'
import { join } from 'node:path'
import { SUPPORTED_LOCALES } from '../index'

// T004 — Constitution Princípio XIV: "A string added in one locale MUST be added
// in all of them. A key that exists only in pt-BR.json is worse than an
// untranslated literal, because it fails at runtime for every other locale
// instead of degrading visibly during development."
//
// Code review is what has been failing at this — translation coverage has been
// shrinking relative to the app since the locale files were created. A test
// turns that risk into a CI failure, which is where it costs least.

const LOCALES_DIR = join(__dirname, '..', 'locales')

/** Every leaf path in a nested message object, as `a.b.c`. Comparing leaves
 *  rather than top-level names is what catches a group that exists everywhere
 *  but is populated in only one locale. */
function leafKeys(value: unknown, prefix = ''): string[] {
  if (value === null || typeof value !== 'object' || Array.isArray(value)) {
    return [prefix]
  }
  const entries = Object.entries(value as Record<string, unknown>)
  // An empty object is itself a leaf for comparison purposes: a group present
  // in one locale and absent in another must still be a difference.
  if (entries.length === 0) return [prefix]
  return entries.flatMap(([k, v]) => leafKeys(v, prefix ? `${prefix}.${k}` : k))
}

function loadLocale(file: string): Record<string, unknown> {
  return JSON.parse(readFileSync(join(LOCALES_DIR, file), 'utf-8'))
}

const localeFiles = readdirSync(LOCALES_DIR)
  .filter((f) => f.endsWith('.json'))
  .sort()

describe('locale parity', () => {
  it('registers every locale file in SUPPORTED_LOCALES', () => {
    // Guards the inverse mistake of the one above: a file added to the folder
    // but never wired into i18n/index.ts is invisible to the app and to the
    // key comparison below.
    const declared = SUPPORTED_LOCALES.map((l) => `${l.value}.json`).sort()
    expect(localeFiles).toEqual(declared)
  })

  it('has the same keys in every locale', () => {
    const reference = localeFiles[0]
    const referenceKeys = leafKeys(loadLocale(reference)).sort()

    for (const file of localeFiles.slice(1)) {
      const keys = leafKeys(loadLocale(file)).sort()
      const missing = referenceKeys.filter((k) => !keys.includes(k))
      const extra = keys.filter((k) => !referenceKeys.includes(k))

      expect({ file, missing, extra }, `${file} diverges from ${reference}`).toEqual({
        file,
        missing: [],
        extra: []
      })
    }
  })
})
