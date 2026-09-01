import { useEffect, useRef, useState } from 'react'
import { searchPlayers } from '../lib/github'
import type { Candidate } from '../lib/github'

/**
 * Live player lookup against statsapi.mlb.com, which allows cross-origin reads.
 * This replaces the CLI's `--lookup NAME` → read the id → hand-edit the source →
 * commit loop.
 *
 * Note the search endpoint does not index a large slice of the minors, so a
 * miss here is expected for some prospects; the direct-id field is the fallback.
 */
export function PlayerSearch({
  initialQuery, onPick, onClose,
}: {
  initialQuery: string
  onPick: (c: Candidate) => void
  onClose: () => void
}) {
  const [query, setQuery] = useState(initialQuery)
  const [results, setResults] = useState<Candidate[] | null>(null)
  const [manualId, setManualId] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => { inputRef.current?.focus() }, [])
  useEffect(() => {
    const esc = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', esc)
    return () => window.removeEventListener('keydown', esc)
  }, [onClose])

  const run = async (q: string) => {
    if (!q.trim()) return
    setBusy(true); setError(null)
    try {
      setResults(await searchPlayers(q.trim()))
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  useEffect(() => { void run(initialQuery) /* eslint-disable-next-line */ }, [])

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center bg-black/70 p-4 pt-20"
      onClick={onClose}
    >
      <div
        className="w-full max-w-2xl rounded-lg border border-neutral-700 bg-neutral-900 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center gap-2 border-b border-neutral-800 p-3">
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && run(query)}
            placeholder="Search MLB Stats API by name"
            className="flex-1 rounded border border-neutral-800 bg-neutral-950 px-2 py-1.5 text-sm text-neutral-200 focus:border-blue-600 focus:outline-none"
          />
          <button
            onClick={() => run(query)}
            className="rounded-md border border-neutral-700 px-3 py-1.5 text-sm text-neutral-300 hover:bg-neutral-800"
          >
            Search
          </button>
          <button onClick={onClose} className="px-1 text-neutral-500 hover:text-neutral-300">✕</button>
        </div>

        <div className="max-h-80 overflow-y-auto">
          {busy && <p className="p-4 text-sm text-neutral-500">Searching…</p>}
          {error && <p className="p-4 text-sm text-red-400">{error}</p>}
          {results?.length === 0 && !busy && (
            <p className="p-4 text-sm text-neutral-500">
              No matches. The search endpoint misses many minor leaguers — find the id on the
              player's MLB.com page (it is in the URL) and paste it below.
            </p>
          )}
          <ul className="divide-y divide-neutral-800">
            {results?.map((c) => (
              <li key={c.id}>
                <button
                  onClick={() => onPick(c)}
                  className="flex w-full items-baseline gap-3 px-3 py-2 text-left text-sm hover:bg-neutral-800"
                >
                  <span className="font-medium text-neutral-200">{c.fullName}</span>
                  <span className="text-xs text-neutral-500">
                    {c.primaryPosition?.abbreviation} · {c.currentTeam?.name ?? 'no team'}
                    {c.birthDate && ` · b. ${c.birthDate}`}
                  </span>
                  <span className="ml-auto font-mono text-xs text-neutral-600">{c.id}</span>
                </button>
              </li>
            ))}
          </ul>
        </div>

        <div className="flex items-center gap-2 border-t border-neutral-800 p-3">
          <label className="text-xs uppercase tracking-wide text-neutral-500">Or paste an id</label>
          <input
            value={manualId}
            onChange={(e) => setManualId(e.target.value.replace(/\D/g, ''))}
            placeholder="829045"
            className="w-32 rounded border border-neutral-800 bg-neutral-950 px-2 py-1 font-mono text-sm text-neutral-200 focus:border-blue-600 focus:outline-none"
          />
          <button
            onClick={() => manualId && onPick({ id: Number(manualId), fullName: '' })}
            disabled={!manualId}
            className="rounded-md border border-neutral-700 px-3 py-1 text-sm text-neutral-300 hover:bg-neutral-800 disabled:opacity-40"
          >
            Use
          </button>
        </div>
      </div>
    </div>
  )
}
