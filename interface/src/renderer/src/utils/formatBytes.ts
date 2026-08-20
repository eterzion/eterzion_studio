/** A file size in the unit that actually says something about it.
 *
 * Three places hardcoded MB with two decimals, which is right for a photo and
 * useless for anything small: a 1 KB icon read "0.00 MB", and so did its
 * result, so the panel showed a size comparison of "0.00 MB → 0.00 MB". The
 * number was accurate and told the person nothing.
 *
 * Kept deliberately simple — binary units, one shared rule, no locale-aware
 * number formatting. The unit names are the same in every language this app
 * ships, so there is nothing here to translate.
 */
const UNITS = ['B', 'KB', 'MB', 'GB', 'TB'] as const

export function formatBytes(bytes: number | null | undefined, fallback = '—'): string {
  if (bytes == null || Number.isNaN(bytes)) return fallback
  if (bytes < 1024) return `${Math.round(bytes)} B`

  let value = bytes
  let unit = 0
  while (value >= 1024 && unit < UNITS.length - 1) {
    value /= 1024
    unit += 1
  }
  // One decimal below 10, none above: "1.4 MB" is worth knowing, "847.3 MB"
  // carries a digit nobody reads.
  return `${value < 10 ? value.toFixed(1) : Math.round(value)} ${UNITS[unit]}`
}
