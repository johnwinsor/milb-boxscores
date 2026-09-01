import { useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { PlayerCard } from '../components/PlayerCard'
import { ErrorNote, Loading } from '../components/Status'
import { download, toCsv, toRows } from '../lib/csv'
import type { ReportPlayer } from '../lib/types'
import { useMeta, useWindow } from '../lib/useData'

type Kind = 'all' | 'hitting' | 'pitching'

const chip = (active: boolean) =>
  `rounded-md px-2.5 py-1 text-sm transition-colors ${
    active ? 'bg-neutral-100 text-neutral-900' : 'bg-neutral-900 text-neutral-400 hover:text-neutral-200'
  }`

export function Daily() {
  const [params, setParams] = useSearchParams()
  const days = Number(params.get('days') ?? 7)
  const team = params.get('team') ?? ''
  const kind = (params.get('kind') ?? 'all') as Kind
  const [hideQuiet, setHideQuiet] = useState(false)

  const { data: meta } = useMeta()
  const { data, error, loading } = useWindow(days)

  const set = (key: string, value: string) => {
    const next = new URLSearchParams(params)
    value ? next.set(key, value) : next.delete(key)
    setParams(next, { replace: true })
  }

  const visible = useMemo(() => {
    let players: ReportPlayer[] = data?.players ?? []
    if (team) players = players.filter((p) => p.team_slug === team)
    if (kind !== 'all') players = players.filter((p) => p.group === kind)
    if (hideQuiet) players = players.filter((p) => p.games.length > 0)
    return players
  }, [data, team, kind, hideQuiet])

  const grouped = useMemo(() => {
    const out: { team: string; players: ReportPlayer[] }[] = []
    for (const p of visible) {
      const last = out[out.length - 1]
      if (last && last.team === p.fantasy_team) last.players.push(p)
      else out.push({ team: p.fantasy_team, players: [p] })
    }
    return out
  }, [visible])

  const played = visible.reduce((n, p) => n + p.games.length, 0)

  if (error) return <ErrorNote error={error} />
  if (loading || !data) return <Loading what="box scores" />

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-3">
        <div className="flex items-center gap-1">
          <span className="mr-1 text-xs uppercase tracking-wide text-neutral-500">Window</span>
          {(meta?.windows ?? [1, 3, 7, 15, 30]).map((d) => (
            <button key={d} onClick={() => set('days', String(d))} className={chip(d === days)}>
              {d}d
            </button>
          ))}
        </div>

        <div className="flex items-center gap-1">
          {(['all', 'hitting', 'pitching'] as Kind[]).map((k) => (
            <button
              key={k}
              onClick={() => set('kind', k === 'all' ? '' : k)}
              className={chip(k === kind)}
            >
              {k === 'all' ? 'All' : k === 'hitting' ? 'Hitters' : 'Pitchers'}
            </button>
          ))}
        </div>

        <select
          value={team}
          onChange={(e) => set('team', e.target.value)}
          className="rounded-md border border-neutral-800 bg-neutral-900 px-2 py-1 text-sm text-neutral-200"
        >
          <option value="">All teams</option>
          {meta?.teams.map((t) => (
            <option key={t.slug} value={t.slug}>{t.name}</option>
          ))}
        </select>

        <label className="flex cursor-pointer items-center gap-1.5 text-sm text-neutral-400">
          <input
            type="checkbox"
            checked={hideQuiet}
            onChange={(e) => setHideQuiet(e.target.checked)}
            className="accent-blue-500"
          />
          Only players who appeared
        </label>

        <div className="ml-auto flex items-center gap-2">
          <button
            onClick={() => download(`boxscores-${days}d.csv`, toCsv(visible), 'text/csv')}
            className="rounded-md border border-neutral-800 px-2.5 py-1 text-sm text-neutral-400 hover:text-neutral-200"
          >
            CSV
          </button>
          <button
            onClick={() =>
              download(
                `boxscores-${days}d.json`,
                JSON.stringify(toRows(visible), null, 2),
                'application/json',
              )
            }
            className="rounded-md border border-neutral-800 px-2.5 py-1 text-sm text-neutral-400 hover:text-neutral-200"
          >
            JSON
          </button>
        </div>
      </div>

      <p className="text-sm text-neutral-500">
        {played} game line{played === 1 ? '' : 's'} from {visible.length} player
        {visible.length === 1 ? '' : 's'} over the last {days} day{days === 1 ? '' : 's'},
        season {data.season}
      </p>

      {grouped.map(({ team: name, players }) => (
        <section key={name} className="space-y-3">
          <h2 className="flex items-center gap-3 text-sm font-semibold uppercase tracking-wide text-neutral-400">
            {name}
            <span className="h-px flex-1 bg-neutral-800" />
          </h2>
          <div className="grid gap-3 lg:grid-cols-2">
            {players.map((p) => (
              <PlayerCard key={`${p.fantasy_team}-${p.name}`} player={p} days={days} />
            ))}
          </div>
        </section>
      ))}

      {grouped.length === 0 && (
        <p className="py-12 text-center text-neutral-500">No players match these filters.</p>
      )}
    </div>
  )
}
