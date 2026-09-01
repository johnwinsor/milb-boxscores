import { Link } from 'react-router-dom'
import { ErrorNote, Loading } from '../components/Status'
import { useTeams } from '../lib/useData'

const STATUS_LABEL: Record<string, string> = {
  roster: 'id on roster', index: 'matched in league index',
  'index-prior': 'matched in prior season', override: 'manually pinned',
  search: 'matched by search', duplicate: 'shared with another team',
  unresolved: 'unresolved', pending: 'pending',
}

export function Teams() {
  const { data, error, loading } = useTeams()
  if (error) return <ErrorNote error={error} />
  if (loading || !data) return <Loading what="rosters" />

  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
      {data.teams.map((team) => (
        <section key={team.slug} className="rounded-lg border border-neutral-800 bg-neutral-900/40">
          <header className="flex items-baseline justify-between border-b border-neutral-800 px-3 py-2">
            <Link
              to={`/?team=${team.slug}`}
              className="font-semibold text-neutral-100 hover:text-blue-400 hover:underline"
            >
              {team.name}
            </Link>
            <span className="text-xs text-neutral-500">{team.players.length} players</span>
          </header>
          <ul className="divide-y divide-neutral-900">
            {team.players.map((p) => (
              <li key={p.name} className="flex items-baseline gap-2 px-3 py-1.5 text-sm">
                {p.person_id ? (
                  <Link
                    to={`/player/${p.person_id}`}
                    className="text-neutral-200 hover:text-blue-400 hover:underline"
                  >
                    {p.name}
                  </Link>
                ) : (
                  <span className="text-amber-500" title={STATUS_LABEL[p.status] ?? p.status}>
                    {p.name}
                  </span>
                )}
                <span className="ml-auto shrink-0 text-xs text-neutral-500">
                  {[p.org, p.pos].filter(Boolean).join(' · ')}
                </span>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  )
}
