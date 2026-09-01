/** Rate stats are conventionally written without a leading zero: .278, not 0.278. */
const THREE_DECIMAL = new Set(['AVG', 'OBP', 'SLG', 'OPS', 'BABIP'])
const TWO_DECIMAL = new Set(['ERA', 'WHIP'])
const ONE_DECIMAL = new Set(['K9', 'BB9', 'HR9'])

export function formatStat(key: string, value: unknown): string {
  if (value === null || value === undefined || value === '') return '—'
  if (typeof value !== 'number') return String(value)

  if (THREE_DECIMAL.has(key)) {
    const s = value.toFixed(3)
    return value < 1 && value >= 0 ? s.slice(1) : s   // .278 / 1.089
  }
  if (TWO_DECIMAL.has(key)) return value.toFixed(2)
  if (ONE_DECIMAL.has(key)) return value.toFixed(1)
  return String(value)
}

/** '2026-09-01T03:58:12Z' or '...+00:00' -> a local, human short form. */
export function formatTimestamp(iso: string | null | undefined): string | null {
  if (!iso) return null
  const withZone = /[Z+]|-\d{2}:\d{2}$/.test(iso) ? iso : `${iso}Z`
  const d = new Date(withZone)
  return Number.isNaN(d.getTime())
    ? null
    : d.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })
}

export function hoursSince(iso: string | null | undefined): number | null {
  if (!iso) return null
  const withZone = /[Z+]|-\d{2}:\d{2}$/.test(iso) ? iso : `${iso}Z`
  const t = Date.parse(withZone)
  return Number.isNaN(t) ? null : (Date.now() - t) / 36e5
}
