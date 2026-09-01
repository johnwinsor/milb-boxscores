import { useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  Bar, BarChart, CartesianGrid, Line, LineChart, ReferenceLine,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { StatTable } from '../components/StatTable'
import { formatStat } from '../lib/format'
import { ErrorNote, Loading } from '../components/Status'
import type { PlayerGame, StatLine } from '../lib/types'
import { usePlayer } from '../lib/useData'

const HIT_CHART = ['H', 'HR', 'RBI', 'K', 'BB', 'PA'] as const
const PIT_CHART = ['K', 'ER', 'H', 'BB'] as const
const HIT_SUMMARY = ['G', 'PA', 'AB', 'H', 'R', 'RBI', '2B', '3B', 'HR', 'SB', 'BB', 'K', 'AVG', 'OBP', 'SLG', 'OPS']
const PIT_SUMMARY = ['G', 'IP', 'H', 'R', 'ER', 'BB', 'K', 'HR', 'ERA', 'WHIP', 'K9']

function StatGrid({ line, keys }: { line: StatLine; keys: string[] }) {
  return (
    <dl className="grid grid-cols-4 gap-x-4 gap-y-2 sm:grid-cols-6 lg:grid-cols-8">
      {keys.map((k) => (
        <div key={k}>
          <dt className="text-[11px] uppercase tracking-wide text-neutral-500">{k}</dt>
          <dd className="tabular-nums text-neutral-100">{formatStat(k, line[k])}</dd>
        </div>
      ))}
    </dl>
  )
}

export function Player() {
  const personId = Number(useParams().personId)
  const { data, error, loading } = usePlayer(personId)
  const [stat, setStat] = useState<string>('H')
  const [rolling, setRolling] = useState(true)

  const isPitcher = data?.group === 'pitching'
  const chartStats = isPitcher ? PIT_CHART : HIT_CHART

  const series = useMemo(() => {
    if (!data) return []
    const pts = data.games.map((g: PlayerGame) => ({
      date: g.date.slice(5),
      value: Number(g[stat] ?? 0),
      level: g.level,
    }))
    if (!rolling) return pts
    // 10-game rolling mean smooths the game-to-game noise into a trend.
    const W = 10
    return pts.map((p, i) => {
      const from = Math.max(0, i - W + 1)
      const slice = pts.slice(from, i + 1)
      return { ...p, value: +(slice.reduce((s, x) => s + x.value, 0) / slice.length).toFixed(2) }
    })
  }, [data, stat, rolling])

  if (error) return <ErrorNote error={error} />
  if (loading || !data) return <Loading what="player" />

  const summaryKeys = isPitcher ? PIT_SUMMARY : HIT_SUMMARY
  const Chart = rolling ? LineChart : BarChart

  return (
    <div className="space-y-6">
      <div>
        <Link to="/" className="text-sm text-neutral-500 hover:text-neutral-300">← Daily report</Link>
        <h1 className="mt-1 text-2xl font-semibold tracking-tight text-neutral-100">
          {data.full_name}
        </h1>
        <p className="text-sm text-neutral-500">
          {[data.org, data.pos, `${data.season} season`].filter(Boolean).join(' · ')}
          {data.name !== data.full_name && ` · rostered as ${data.name}`}
        </p>
      </div>

      <section className="rounded-lg border border-neutral-800 bg-neutral-900/40 p-4">
        <h2 className="mb-3 text-sm font-semibold text-neutral-300">Season</h2>
        <StatGrid line={data.season_total} keys={summaryKeys} />
      </section>

      <section className="grid gap-3 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-5">
        {Object.entries(data.splits).map(([label, line]) => (
          <div key={label} className="rounded-lg border border-neutral-800 bg-neutral-900/40 p-3">
            <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-neutral-400">
              Last {label}
            </h3>
            {line.G ? (
              <StatGrid
                line={line}
                keys={isPitcher ? ['G', 'IP', 'K', 'ER', 'ERA'] : ['G', 'PA', 'H', 'HR', 'OPS']}
              />
            ) : (
              <p className="text-sm text-neutral-600">no games</p>
            )}
          </div>
        ))}
      </section>

      {Object.keys(data.by_level).length > 1 && (
        <section className="rounded-lg border border-neutral-800 bg-neutral-900/40 p-4">
          <h2 className="mb-3 text-sm font-semibold text-neutral-300">
            By level
            {data.level_changes.map((c) => (
              <span
                key={c.date}
                className={`ml-2 rounded px-1.5 py-0.5 text-xs font-normal ${
                  c.direction === 'up'
                    ? 'bg-emerald-950 text-emerald-400'
                    : 'bg-amber-950 text-amber-400'
                }`}
              >
                {c.direction === 'up' ? '↑' : '↓'} {c.from}→{c.to} on {c.date}
              </span>
            ))}
          </h2>
          <div className="space-y-3">
            {Object.entries(data.by_level).map(([lvl, line]) => (
              <div key={lvl}>
                <h3 className="mb-1 text-xs font-semibold text-neutral-400">{lvl}</h3>
                <StatGrid line={line} keys={summaryKeys} />
              </div>
            ))}
          </div>
        </section>
      )}

      <section className="rounded-lg border border-neutral-800 bg-neutral-900/40 p-4">
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <h2 className="mr-2 text-sm font-semibold text-neutral-300">Trend</h2>
          {chartStats.map((s) => (
            <button
              key={s}
              onClick={() => setStat(s)}
              className={`rounded px-2 py-0.5 text-xs ${
                s === stat ? 'bg-neutral-100 text-neutral-900' : 'bg-neutral-800 text-neutral-400'
              }`}
            >
              {s}
            </button>
          ))}
          <label className="ml-auto flex cursor-pointer items-center gap-1.5 text-xs text-neutral-400">
            <input
              type="checkbox"
              checked={rolling}
              onChange={(e) => setRolling(e.target.checked)}
              className="accent-blue-500"
            />
            10-game rolling average
          </label>
        </div>
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <Chart data={series} margin={{ top: 4, right: 8, bottom: 0, left: -20 }}>
              <CartesianGrid stroke="#262626" vertical={false} />
              <XAxis dataKey="date" tick={{ fill: '#737373', fontSize: 11 }} minTickGap={24} />
              <YAxis tick={{ fill: '#737373', fontSize: 11 }} allowDecimals={rolling} />
              <Tooltip
                contentStyle={{
                  background: '#0a0a0a', border: '1px solid #404040',
                  borderRadius: 6, fontSize: 12,
                }}
                labelStyle={{ color: '#a3a3a3' }}
              />
              {data.level_changes.map((c) => (
                <ReferenceLine
                  key={c.date}
                  x={c.date.slice(5)}
                  stroke={c.direction === 'up' ? '#34d399' : '#fbbf24'}
                  strokeDasharray="3 3"
                  label={{ value: c.to, fill: '#a3a3a3', fontSize: 10, position: 'top' }}
                />
              ))}
              {rolling ? (
                <Line type="monotone" dataKey="value" stroke="#60a5fa" strokeWidth={2} dot={false} />
              ) : (
                <Bar dataKey="value" fill="#60a5fa" />
              )}
            </Chart>
          </ResponsiveContainer>
        </div>
      </section>

      <section className="rounded-lg border border-neutral-800 bg-neutral-900/40">
        <h2 className="px-4 py-3 text-sm font-semibold text-neutral-300">
          Game log · {data.games.length} games
        </h2>
        <div className="px-1 pb-1">
          <StatTable
            rows={[...data.games].reverse() as unknown as Record<string, unknown>[]}
            isPitcher={!!isPitcher}
            showLevel
            onRowClick={(row) =>
              window.open(`https://www.mlb.com/gameday/${row.gamePk}`, '_blank', 'noopener')
            }
          />
        </div>
      </section>
    </div>
  )
}
