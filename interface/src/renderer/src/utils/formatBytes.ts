/** A file size in the unit that actually says something about it.
 *
 * Three places hardcoded MB with two decimals, which is right for a photo and
 * useless for anything small: a 1 KB icon read "0.00 MB", and so did its
 * result, so the panel showed a size comparison of "0.00 MB → 0.00 MB". The
 * number was accurate and told the person nothing.
 *
 * No locale-aware number formatting: the unit names are the same in every
 * language this app ships, so there is nothing here to translate.
 *
 * **Two bases, deliberately.** The rest of the app has always shown binary units
 * (1 KB = 1024 B), which is what Windows Explorer shows next to the same file.
 * The Compression Centre shows decimal (1 kB = 1000 B) because that is what its
 * backend counts (`target_to_bytes`) and what the sites imposing a limit count:
 * a person asking for "8 MB" so an upload is accepted needs the number to mean
 * what the site means, not something 5% larger. Mixing the two on one screen is
 * the actual defect — hence one file, two named functions, and never a silent
 * default.
 */
const BINARY_UNITS = ['B', 'KB', 'MB', 'GB', 'TB'] as const
const DECIMAL_UNITS = ['B', 'kB', 'MB', 'GB', 'TB'] as const

export function formatBytes(bytes: number | null | undefined, fallback = '—'): string {
  return format(bytes, fallback, 1024, BINARY_UNITS)
}

/** Decimal (1 kB = 1000 B) — the Compression Centre's unit, matching its
 *  backend and the upload limits people are trying to fit under. */
export function formatBytesDecimal(bytes: number | null | undefined, fallback = '—'): string {
  return format(bytes, fallback, 1000, DECIMAL_UNITS)
}

function format(
  bytes: number | null | undefined,
  fallback: string,
  base: number,
  units: readonly string[]
): string {
  if (bytes == null || Number.isNaN(bytes)) return fallback
  const negative = bytes < 0
  const magnitude = Math.abs(bytes)
  if (magnitude < base) return `${negative ? '-' : ''}${Math.round(magnitude)} B`

  let value = magnitude
  let unit = 0
  while (value >= base && unit < units.length - 1) {
    value /= base
    unit += 1
  }
  // One decimal below 10, none above: "1.4 MB" is worth knowing, "847.3 MB"
  // carries a digit nobody reads.
  const texto = value < 10 ? value.toFixed(1) : String(Math.round(value))
  return `${negative ? '-' : ''}${texto} ${units[unit]}`
}
