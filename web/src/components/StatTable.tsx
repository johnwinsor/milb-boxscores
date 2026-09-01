import { EMPHASIS_CLASS, emphasis } from '../lib/highlight'

const HITTER_STATS = ['PA', 'AB', 'H', 'R', 'RBI', '2B', 'HR', 'SB', 'CS', 'BB', 'K']
const PITCHER_STATS = ['IP', 'H', 'R', 'ER', 'BB', 'K', 'HR']

export const HITTER_COLUMNS = ['Date', 'Team', 'Opp', ...HITTER_STATS]
export const PITCHER_COLUMNS = ['Date', 'Team', 'Opp', ...PITCHER_STATS]

const LABEL_COLS = new Set(['Date', 'Team', 'Opp', 'Lvl'])

interface Props {
  rows: Record<string, unknown>[]
  total?: Record<string, unknown> | null
  isPitcher: boolean
  /** Drop the Team column -- the caller shows it once in the header instead.
   *  Full minor-league club names are wide, and repeating one down every row
   *  pushes the stat columns off the card. */
  hideTeam?: boolean
  showLevel?: boolean
  onRowClick?: (row: Record<string, unknown>) => void
}

export function StatTable({ rows, total, isPitcher, hideTeam, showLevel, onRowClick }: Props) {
  const columns = [
    'Date',
    ...(showLevel ? ['Lvl'] : []),
    ...(hideTeam ? [] : ['Team']),
    'Opp',
    ...(isPitcher ? PITCHER_STATS : HITTER_STATS),
  ]

  const value = (row: Record<string, unknown>, col: string) => {
    if (col === 'Date') return String(row.date ?? '').slice(5)   // MM-DD; the year is in the header
    if (col === 'Lvl') return row.level
    if (col === 'Team') return row.team
    if (col === 'Opp') return row.opponent ?? row.opp
    return row[col]
  }

  return (
    // Wide tables scroll inside their own container; the page never scrolls sideways.
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-neutral-800 text-neutral-400">
            {columns.map((col) => (
              <th
                key={col}
                className={`px-1.5 py-1.5 font-medium whitespace-nowrap ${
                  LABEL_COLS.has(col) ? 'text-left' : 'text-right'
                }`}
              >
                {col}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr
              key={`${row.date}-${row.game_pk ?? row.gamePk ?? i}`}
              onClick={() => onRowClick?.(row)}
              className={`border-b border-neutral-900 last:border-0 ${
                onRowClick ? 'cursor-pointer hover:bg-neutral-900/60' : ''
              }`}
            >
              {columns.map((col) => {
                const v = value(row, col)
                const emp = LABEL_COLS.has(col) ? null : emphasis(col, v, row, isPitcher)
                return (
                  <td
                    key={col}
                    className={`px-1.5 py-1 ${
                      col === 'Team' || col === 'Opp'
                        ? 'max-w-[10rem] truncate text-left text-neutral-400'
                        : LABEL_COLS.has(col)
                          ? 'whitespace-nowrap text-left text-neutral-400'
                          : 'whitespace-nowrap text-right tabular-nums'
                    } ${emp ? EMPHASIS_CLASS[emp] : ''}`}
                    title={col === 'Team' || col === 'Opp' ? String(v ?? '') : undefined}
                  >
                    {v as string}
                  </td>
                )
              })}
            </tr>
          ))}
          {total && (
            <tr className="border-t-2 border-neutral-700 font-semibold">
              {columns.map((col) => (
                <td
                  key={col}
                  className={`px-1.5 py-1.5 whitespace-nowrap ${
                    LABEL_COLS.has(col) ? 'text-left' : 'text-right tabular-nums'
                  }`}
                >
                  {col === 'Date' ? 'TOTAL' : LABEL_COLS.has(col) ? '' : (total[col] as string)}
                </td>
              ))}
            </tr>
          )}
        </tbody>
      </table>
    </div>
  )
}
