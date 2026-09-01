/**
 * Standout-line thresholds, ported from the CLI's Rich renderer so the web view
 * flags the same games the terminal did. Kept in one place so they are tunable.
 */
export type Emphasis = 'good' | 'note' | null

export function emphasis(
  col: string,
  value: unknown,
  row: Record<string, unknown>,
  isPitcher: boolean,
): Emphasis {
  const n = typeof value === 'number' ? value : Number(value)
  if (!Number.isFinite(n)) return null

  if (col === 'HR' && n > 0) return 'good'
  if (col === 'H' && !isPitcher && n >= 3) return 'good'
  if (col === 'K' && isPitcher && n >= 8) return 'note'
  if (col === 'ER' && isPitcher && n === 0 && row.IP !== '0.0' && row.IP != null) return 'good'
  if (col === 'SB' && !isPitcher && n > 0) return 'note'
  return null
}

export const EMPHASIS_CLASS: Record<'good' | 'note', string> = {
  good: 'font-semibold text-emerald-400',
  note: 'font-semibold text-cyan-400',
}
