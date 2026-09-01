import { useCallback, useEffect, useState } from 'react'
import {
  fetchRoster, getRepo, getToken, lookupPlayer, saveRoster,
  setRepo as persistRepo, setToken as persistToken, triggerRefresh,
} from '../lib/github'
import type { Candidate, RosterDoc, RosterPlayerDoc } from '../lib/github'
import { PlayerSearch } from '../components/PlayerSearch'

const ORGS = [
  'ARI', 'ATH', 'ATL', 'BAL', 'BOS', 'CHC', 'CHW', 'CIN', 'CLE', 'COL', 'DET',
  'HOU', 'KC', 'LAA', 'LAD', 'MIA', 'MIL', 'MIN', 'NYM', 'NYY', 'PHI', 'PIT',
  'SD', 'SEA', 'SF', 'STL', 'TB', 'TEX', 'TOR', 'WSH',
]
const LEVELS = ['TBD', 'DSL', 'CPX', 'A', 'A+', 'AA', 'AAA', 'MLB']

const input =
  'rounded border border-neutral-800 bg-neutral-950 px-2 py-1 text-sm text-neutral-200 focus:border-blue-600 focus:outline-none'
const button =
  'rounded-md border border-neutral-700 px-3 py-1.5 text-sm text-neutral-300 hover:bg-neutral-800 disabled:opacity-40 disabled:hover:bg-transparent'

export function Admin() {
  const [token, setTokenState] = useState(getToken())
  const [repo, setRepoState] = useState(getRepo())
  const [doc, setDoc] = useState<RosterDoc | null>(null)
  const [sha, setSha] = useState('')
  const [dirty, setDirty] = useState(false)
  const [busy, setBusy] = useState(false)
  const [status, setStatus] = useState<{ kind: 'ok' | 'err'; text: string } | null>(null)
  const [searchFor, setSearchFor] = useState<{ team: number; player: number } | null>(null)

  const load = useCallback(async () => {
    if (!getToken()) return
    setBusy(true)
    try {
      const { doc, sha } = await fetchRoster()
      setDoc(doc); setSha(sha); setDirty(false)
      setStatus({ kind: 'ok', text: 'Loaded rosters from GitHub.' })
    } catch (e) {
      setStatus({ kind: 'err', text: (e as Error).message })
    } finally {
      setBusy(false)
    }
  }, [])

  useEffect(() => { if (token) void load() }, [token, load])

  // Guard against losing edits to a stray navigation or tab close.
  useEffect(() => {
    if (!dirty) return
    const warn = (e: BeforeUnloadEvent) => { e.preventDefault() }
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [dirty])

  const mutate = (fn: (d: RosterDoc) => void) => {
    if (!doc) return
    const next: RosterDoc = JSON.parse(JSON.stringify(doc))
    fn(next)
    setDoc(next); setDirty(true)
  }

  const save = async () => {
    if (!doc) return
    setBusy(true)
    try {
      const res = await saveRoster(doc, sha, 'Update rosters from web app')
      setStatus({ kind: 'ok', text: `Committed ${res.commit.sha.slice(0, 7)}. The pipeline will refresh on push.` })
      setDirty(false)
      await load()
    } catch (e) {
      const msg = (e as Error).message
      setStatus({
        kind: 'err',
        // A 409 means someone (or the Action) committed since we loaded.
        text: /sha|conflict|409/i.test(msg)
          ? 'Someone else changed rosters.json since you loaded it. Reload to get the latest, then re-apply your edits.'
          : msg,
      })
    } finally {
      setBusy(false)
    }
  }

  const refresh = async () => {
    setBusy(true)
    try {
      await triggerRefresh()
      setStatus({ kind: 'ok', text: 'Refresh dispatched. The Action will rebuild and redeploy in a few minutes.' })
    } catch (e) {
      setStatus({ kind: 'err', text: (e as Error).message })
    } finally {
      setBusy(false)
    }
  }

  const applyCandidate = (teamIdx: number, playerIdx: number, c: Candidate) =>
    mutate((d) => { d.teams[teamIdx].players[playerIdx].person_id = c.id })

  if (!token) {
    return <TokenSetup repo={repo} onRepo={(r) => { persistRepo(r); setRepoState(r) }}
                       onToken={(t) => { persistToken(t); setTokenState(t) }} />
  }

  const unresolved = doc?.teams.flatMap((t, ti) =>
    t.players.map((p, pi) => ({ ...p, ti, pi, team: t.name })).filter((p) => !p.person_id)) ?? []

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-2">
        <h1 className="text-xl font-semibold text-neutral-100">Roster admin</h1>
        <span className="text-xs text-neutral-500">{repo}</span>
        <div className="ml-auto flex flex-wrap items-center gap-2">
          <button onClick={load} disabled={busy} className={button}>Reload</button>
          <button onClick={refresh} disabled={busy} className={button}>Refresh data now</button>
          <button
            onClick={save}
            disabled={busy || !dirty}
            className="rounded-md bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-500 disabled:opacity-40"
          >
            {dirty ? 'Commit changes' : 'No changes'}
          </button>
          <button
            onClick={() => { persistToken(''); setTokenState(''); setDoc(null) }}
            className="text-sm text-neutral-500 hover:text-neutral-300"
          >
            Sign out
          </button>
        </div>
      </div>

      {status && (
        <p className={`rounded-md border px-3 py-2 text-sm ${
          status.kind === 'ok'
            ? 'border-emerald-900 bg-emerald-950/40 text-emerald-300'
            : 'border-red-900 bg-red-950/40 text-red-300'
        }`}>
          {status.text}
        </p>
      )}

      {unresolved.length > 0 && (
        <section className="rounded-lg border border-amber-900/60 bg-amber-950/20 p-3">
          <h2 className="mb-2 text-sm font-semibold text-amber-400">
            {unresolved.length} player{unresolved.length === 1 ? '' : 's'} without an MLB id
          </h2>
          <p className="mb-2 text-xs text-amber-600/80">
            These are skipped by the pipeline. Search for the right person below to pin their id.
          </p>
          <ul className="flex flex-wrap gap-2">
            {unresolved.map((p) => (
              <li key={`${p.ti}-${p.pi}`}>
                <button
                  onClick={() => setSearchFor({ team: p.ti, player: p.pi })}
                  className="rounded bg-amber-950/60 px-2 py-1 text-xs text-amber-300 hover:bg-amber-900/60"
                >
                  {p.name} <span className="text-amber-600">({p.team})</span>
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}

      {doc?.teams.map((team, ti) => (
        <section key={team.slug} className="rounded-lg border border-neutral-800 bg-neutral-900/40">
          <header className="flex items-center gap-2 border-b border-neutral-800 px-3 py-2">
            <input
              value={team.name}
              onChange={(e) => mutate((d) => { d.teams[ti].name = e.target.value })}
              className={`${input} font-semibold`}
            />
            <span className="text-xs text-neutral-500">{team.players.length}</span>
            <button
              onClick={() => mutate((d) => {
                d.teams[ti].players.push({
                  name: '', org: 'ARI', level: 'TBD', pos: 'OF', person_id: null, notes: '',
                })
              })}
              className="ml-auto text-sm text-blue-400 hover:text-blue-300"
            >
              + Add player
            </button>
          </header>

          <div className="divide-y divide-neutral-900">
            {team.players.map((p, pi) => (
              <PlayerRow
                key={pi}
                player={p}
                teams={doc.teams.map((t) => t.name)}
                currentTeam={ti}
                onChange={(patch) =>
                  mutate((d) => Object.assign(d.teams[ti].players[pi], patch))}
                onSearch={() => setSearchFor({ team: ti, player: pi })}
                onRemove={() => mutate((d) => { d.teams[ti].players.splice(pi, 1) })}
                onMove={(dest) => mutate((d) => {
                  const [moved] = d.teams[ti].players.splice(pi, 1)
                  d.teams[dest].players.push(moved)
                })}
              />
            ))}
          </div>
        </section>
      ))}

      {searchFor && doc && (
        <PlayerSearch
          initialQuery={doc.teams[searchFor.team].players[searchFor.player].name}
          onPick={(c) => { applyCandidate(searchFor.team, searchFor.player, c); setSearchFor(null) }}
          onClose={() => setSearchFor(null)}
        />
      )}
    </div>
  )
}

function PlayerRow({
  player, teams, currentTeam, onChange, onSearch, onRemove, onMove,
}: {
  player: RosterPlayerDoc
  teams: string[]
  currentTeam: number
  onChange: (patch: Partial<RosterPlayerDoc>) => void
  onSearch: () => void
  onRemove: () => void
  onMove: (dest: number) => void
}) {
  const [resolved, setResolved] = useState<string | null>(null)
  useEffect(() => {
    let ok = true
    if (player.person_id) {
      void lookupPlayer(player.person_id).then((c) => ok && setResolved(c?.fullName ?? null))
    } else setResolved(null)
    return () => { ok = false }
  }, [player.person_id])

  return (
    <div className="flex flex-wrap items-center gap-2 px-3 py-2">
      <input
        value={player.name}
        placeholder="Player name"
        onChange={(e) => onChange({ name: e.target.value })}
        className={`${input} w-48`}
      />
      <select value={player.org} onChange={(e) => onChange({ org: e.target.value })} className={input}>
        {ORGS.map((o) => <option key={o}>{o}</option>)}
      </select>
      <select value={player.level} onChange={(e) => onChange({ level: e.target.value })} className={input}>
        {LEVELS.map((l) => <option key={l}>{l}</option>)}
      </select>
      <input
        value={player.pos}
        placeholder="POS"
        onChange={(e) => onChange({ pos: e.target.value })}
        className={`${input} w-20`}
      />

      <button onClick={onSearch} className="text-xs text-blue-400 hover:text-blue-300">
        {player.person_id ? `id ${player.person_id}` : 'find id'}
      </button>
      {resolved && resolved !== player.name && (
        <span className="text-xs text-neutral-500" title="MLB-registered name">
          = {resolved}
        </span>
      )}
      {!player.person_id && <span className="text-xs text-amber-500">unresolved</span>}

      <select
        value={currentTeam}
        onChange={(e) => onMove(Number(e.target.value))}
        className={`${input} ml-auto`}
        title="Move to another fantasy team"
      >
        {teams.map((t, i) => <option key={t} value={i}>{t}</option>)}
      </select>
      <button onClick={onRemove} className="text-sm text-neutral-600 hover:text-red-400" title="Remove">
        ✕
      </button>
    </div>
  )
}

function TokenSetup({
  repo, onRepo, onToken,
}: { repo: string; onRepo: (r: string) => void; onToken: (t: string) => void }) {
  const [value, setValue] = useState('')
  return (
    <div className="mx-auto max-w-xl space-y-4">
      <h1 className="text-xl font-semibold text-neutral-100">Roster admin</h1>
      <p className="text-sm text-neutral-400">
        Editing rosters commits to <code className="text-neutral-300">data/rosters.json</code> in
        your repo, which triggers the pipeline to refresh. This site is static, so the write goes
        directly from your browser to the GitHub API.
      </p>
      <ol className="list-decimal space-y-1.5 pl-5 text-sm text-neutral-400">
        <li>
          Create a{' '}
          <a
            href="https://github.com/settings/personal-access-tokens/new"
            target="_blank" rel="noreferrer"
            className="text-blue-400 hover:underline"
          >
            fine-grained personal access token
          </a>
        </li>
        <li>Scope it to <strong className="text-neutral-300">only</strong> this repository</li>
        <li>Grant <strong className="text-neutral-300">Repository permissions → Contents → Read and write</strong></li>
      </ol>
      <p className="rounded-md border border-neutral-800 bg-neutral-900/60 p-3 text-xs text-neutral-500">
        The token is stored in this browser's localStorage only — it is never committed and never
        leaves your machine except in requests to api.github.com. Anyone viewing the public site
        without a token gets a read-only view. Revoke it any time from GitHub settings.
      </p>
      <div className="space-y-2">
        <label className="block text-xs uppercase tracking-wide text-neutral-500">Repository</label>
        <input
          defaultValue={repo}
          onBlur={(e) => onRepo(e.target.value.trim())}
          className={`${input} w-full`}
        />
        <label className="block text-xs uppercase tracking-wide text-neutral-500">Token</label>
        <input
          type="password"
          value={value}
          placeholder="github_pat_..."
          onChange={(e) => setValue(e.target.value)}
          className={`${input} w-full font-mono`}
        />
        <button
          onClick={() => onToken(value.trim())}
          disabled={!value.trim()}
          className="rounded-md bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-500 disabled:opacity-40"
        >
          Save token
        </button>
      </div>
    </div>
  )
}
