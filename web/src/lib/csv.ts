import type { ReportPlayer } from './types'

/**
 * Column order and semantics match the CLI's CSV_FIELDS exactly, so a download
 * from the browser is interchangeable with `milb report --format csv`.
 */
export const CSV_FIELDS = [
  'fantasy_team', 'date', 'player', 'org', 'level', 'pos', 'type', 'team', 'opponent',
  'PA', 'AB', 'H', 'R', 'RBI', '2B', 'HR', 'SB', 'CS', 'BB', 'K',
  'IP', 'ER', 'is_total',
] as const

function cell(v: unknown): string {
  if (v === null || v === undefined) return ''
  const s = typeof v === 'boolean' ? (v ? 'True' : 'False') : String(v)
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
}

export function toRows(players: ReportPlayer[]): Record<string, unknown>[] {
  const rows: Record<string, unknown>[] = []
  for (const p of players) {
    const ident = {
      fantasy_team: p.fantasy_team, player: p.name, org: p.org,
      pos: p.pos, type: p.group,
    }
    for (const g of p.games) rows.push({ ...ident, ...g, is_total: false })
    if (p.total) rows.push({ ...ident, ...p.total })
  }
  return rows
}

export function toCsv(players: ReportPlayer[]): string {
  const rows = toRows(players)
  return [
    CSV_FIELDS.join(','),
    ...rows.map((r) => CSV_FIELDS.map((f) => cell(r[f])).join(',')),
  ].join('\r\n') + '\r\n'
}

export function download(filename: string, content: string, type: string) {
  const url = URL.createObjectURL(new Blob([content], { type }))
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}
