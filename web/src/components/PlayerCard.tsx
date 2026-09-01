import { Link } from 'react-router-dom'
import type { ReportPlayer } from '../lib/types'
import { StatTable } from './StatTable'

/** Border colour carries the same meaning the Rich panels did: red pitcher,
 *  blue hitter, amber unresolved, dim no-games. */
function borderFor(p: ReportPlayer) {
  if (p.error) return 'border-amber-700/60'
  if (!p.games.length) return 'border-neutral-800'
  return p.group === 'pitching' ? 'border-red-800/70' : 'border-blue-800/70'
}

export function PlayerCard({ player, days }: { player: ReportPlayer; days: number }) {
  const subtitle = [player.org, player.level, player.pos].filter(Boolean).join(' ')
  // A player usually spends the whole window with one club; showing it once in
  // the header instead of on every row leaves room for the stat columns.
  const clubs = [...new Set(player.games.map((g) => g.team))]
  const oneClub = clubs.length === 1 ? clubs[0] : null
  const levels = [...new Set(player.games.map((g) => g.level).filter(Boolean))]
  return (
    <section className={`rounded-lg border bg-neutral-900/40 ${borderFor(player)}`}>
      <header className="flex flex-wrap items-baseline gap-x-2 gap-y-1 px-3 py-2">
        {player.person_id ? (
          <Link
            to={`/player/${player.person_id}`}
            className="font-semibold text-neutral-100 hover:text-blue-400 hover:underline"
          >
            {player.name}
          </Link>
        ) : (
          <span className="font-semibold text-neutral-100">{player.name}</span>
        )}
        <span className="text-xs text-neutral-500">{subtitle}</span>
        {oneClub && <span className="text-xs text-neutral-600">· {oneClub}</span>}
        {player.full_name !== player.name && (
          <span className="text-xs text-neutral-600">· {player.full_name}</span>
        )}
      </header>

      {player.error ? (
        <p className="px-3 pb-3 text-sm text-amber-600/90">{player.error}</p>
      ) : player.games.length === 0 ? (
        <p className="px-3 pb-3 text-sm text-neutral-600">
          no games played in the last {days} day{days === 1 ? '' : 's'}
        </p>
      ) : (
        <div className="px-1 pb-1">
          <StatTable
            rows={player.games as unknown as Record<string, unknown>[]}
            total={player.total as unknown as Record<string, unknown> | null}
            isPitcher={player.group === 'pitching'}
            hideTeam={!!oneClub}
            showLevel={levels.length > 1}
          />
        </div>
      )}
    </section>
  )
}
