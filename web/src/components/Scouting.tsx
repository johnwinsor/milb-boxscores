import { useEffect, useState } from 'react'
import { fetchScouting, getToken, saveScouting } from '../lib/github'
import type { Report } from '../lib/github'
import { RISK_CLASS, SCALE, formatGrade, fvLabel, gradeClass } from '../lib/grades'
import type { Group, ScoutingReport } from '../lib/types'
import { useMeta } from '../lib/useData'

const EMPTY: Report = { grades: {}, fv: null, risk: null, eta: null, notes: [] }

const input =
  'rounded border border-neutral-800 bg-neutral-950 px-2 py-1 text-sm text-neutral-200 focus:border-blue-600 focus:outline-none'

/**
 * The editor lives on the player page rather than in the roster admin, so a
 * grade is written while the stat line that motivated it is on screen.
 * Read-only for anyone without a token, which is every public visitor.
 */
export function Scouting({
  personId, name, group, initial,
}: {
  personId: number
  name: string
  group: Group
  initial: ScoutingReport | null
}) {
  const { data: meta } = useMeta()
  const canEdit = !!getToken()
  const [editing, setEditing] = useState(false)
  const [report, setReport] = useState<Report>(initial ? { ...EMPTY, ...initial } : EMPTY)
  const [sha, setSha] = useState('')
  const [draftNote, setDraftNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [status, setStatus] = useState<{ kind: 'ok' | 'err'; text: string } | null>(null)

  useEffect(() => { setReport(initial ? { ...EMPTY, ...initial } : EMPTY) }, [initial, personId])

  const tools = meta?.scouting_tools?.[group] ?? {}
  const hasReport = Object.keys(report.grades).length > 0 || report.fv != null || report.notes.length > 0

  const beginEdit = async () => {
    setBusy(true); setStatus(null)
    try {
      // Load the live file so we hold a current SHA and never clobber a report
      // written from another browser.
      const { players, sha } = await fetchScouting()
      setSha(sha)
      setReport(players[String(personId)] ?? (initial ? { ...EMPTY, ...initial } : EMPTY))
      setEditing(true)
    } catch (e) {
      setStatus({ kind: 'err', text: (e as Error).message })
    } finally { setBusy(false) }
  }

  const commit = async () => {
    setBusy(true); setStatus(null)
    try {
      const { players, sha: fresh } = await fetchScouting()
      const next = { ...players }
      const cleaned: Report = {
        ...report,
        updated_at: new Date().toISOString().slice(0, 10),
      }
      if (hasReport) next[String(personId)] = cleaned
      else delete next[String(personId)]

      const res = await saveScouting(next, fresh || sha, `Scouting report: ${name}`)
      setStatus({ kind: 'ok', text: `Committed ${res.commit.sha.slice(0, 7)}. Live after the next build.` })
      setEditing(false)
    } catch (e) {
      setStatus({ kind: 'err', text: (e as Error).message })
    } finally { setBusy(false) }
  }

  const setGrade = (tool: string, field: 'present' | 'future', value: string) =>
    setReport((r) => {
      const grades = { ...r.grades }
      const g = { ...(grades[tool] ?? {}) }
      if (value === '') delete g[field]
      else g[field] = Number(value)
      if (g.present == null && g.future == null) delete grades[tool]
      else grades[tool] = g
      return { ...r, grades }
    })

  if (!hasReport && !editing) {
    return (
      <section className="rounded-lg border border-neutral-800 bg-neutral-900/40 p-4">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-neutral-300">Scouting</h2>
          {canEdit && (
            <button onClick={beginEdit} disabled={busy} className="text-sm text-blue-400 hover:text-blue-300">
              {busy ? 'Loading…' : '+ Add a report'}
            </button>
          )}
        </div>
        <p className="mt-1 text-sm text-neutral-600">No report yet.</p>
        {status && <p className="mt-2 text-sm text-red-400">{status.text}</p>}
      </section>
    )
  }

  return (
    <section className="rounded-lg border border-neutral-800 bg-neutral-900/40 p-4">
      <div className="mb-3 flex flex-wrap items-center gap-3">
        <h2 className="text-sm font-semibold text-neutral-300">Scouting</h2>
        {report.fv != null && !editing && (
          <span className="flex items-baseline gap-1.5">
            <span className={`text-lg font-semibold ${gradeClass(report.fv)}`}>{report.fv}</span>
            <span className="text-xs text-neutral-500">FV · {fvLabel(report.fv)}</span>
          </span>
        )}
        {report.risk && !editing && (
          <span className={`rounded px-1.5 py-0.5 text-xs ${RISK_CLASS[report.risk] ?? ''}`}>
            {report.risk} risk
          </span>
        )}
        {report.eta && !editing && (
          <span className="text-xs text-neutral-500">ETA {report.eta}</span>
        )}
        {canEdit && (
          <div className="ml-auto flex items-center gap-2">
            {editing ? (
              <>
                <button onClick={() => setEditing(false)} className="text-sm text-neutral-500 hover:text-neutral-300">
                  Cancel
                </button>
                <button
                  onClick={commit}
                  disabled={busy}
                  className="rounded-md bg-blue-600 px-3 py-1 text-sm font-medium text-white hover:bg-blue-500 disabled:opacity-40"
                >
                  {busy ? 'Committing…' : 'Commit report'}
                </button>
              </>
            ) : (
              <button onClick={beginEdit} disabled={busy} className="text-sm text-blue-400 hover:text-blue-300">
                {busy ? 'Loading…' : 'Edit'}
              </button>
            )}
          </div>
        )}
      </div>

      {status && (
        <p className={`mb-3 rounded-md border px-3 py-2 text-sm ${
          status.kind === 'ok'
            ? 'border-emerald-900 bg-emerald-950/40 text-emerald-300'
            : 'border-red-900 bg-red-950/40 text-red-300'
        }`}>{status.text}</p>
      )}

      {editing ? (
        <div className="space-y-4">
          <div className="flex flex-wrap items-end gap-3">
            <Field label="FV">
              <select
                value={report.fv ?? ''}
                onChange={(e) => setReport((r) => ({ ...r, fv: e.target.value ? Number(e.target.value) : null }))}
                className={input}
              >
                <option value="">—</option>
                {SCALE.map((v) => <option key={v} value={v}>{v}</option>)}
              </select>
            </Field>
            <Field label="Risk">
              <select
                value={report.risk ?? ''}
                onChange={(e) => setReport((r) => ({ ...r, risk: e.target.value || null }))}
                className={input}
              >
                <option value="">—</option>
                {(meta?.risk_levels ?? []).map((r) => <option key={r} value={r}>{r}</option>)}
              </select>
            </Field>
            <Field label="ETA">
              <input
                type="number"
                value={report.eta ?? ''}
                placeholder="2029"
                onChange={(e) => setReport((r) => ({ ...r, eta: e.target.value ? Number(e.target.value) : null }))}
                className={`${input} w-24`}
              />
            </Field>
          </div>

          <div>
            <h3 className="mb-2 text-xs uppercase tracking-wide text-neutral-500">
              Tools · present / future on the 20-80 scale
            </h3>
            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {Object.entries(tools).map(([key, label]) => (
                <div key={key} className="flex items-center gap-2">
                  <span className="w-24 shrink-0 text-sm text-neutral-400">{label}</span>
                  {(['present', 'future'] as const).map((f) => (
                    <select
                      key={f}
                      value={report.grades[key]?.[f] ?? ''}
                      onChange={(e) => setGrade(key, f, e.target.value)}
                      className={`${input} w-20`}
                      title={f}
                    >
                      <option value="">{f === 'present' ? 'pres' : 'fut'}</option>
                      {SCALE.map((v) => <option key={v} value={v}>{v}</option>)}
                    </select>
                  ))}
                </div>
              ))}
            </div>
          </div>

          <div>
            <h3 className="mb-2 text-xs uppercase tracking-wide text-neutral-500">Add a note</h3>
            <textarea
              value={draftNote}
              onChange={(e) => setDraftNote(e.target.value)}
              rows={3}
              placeholder="What you saw, and when."
              className={`${input} w-full`}
            />
            <button
              onClick={() => {
                if (!draftNote.trim()) return
                setReport((r) => ({
                  ...r,
                  notes: [{ date: new Date().toISOString().slice(0, 10), text: draftNote.trim() }, ...r.notes],
                }))
                setDraftNote('')
              }}
              disabled={!draftNote.trim()}
              className="mt-1 rounded-md border border-neutral-700 px-3 py-1 text-sm text-neutral-300 hover:bg-neutral-800 disabled:opacity-40"
            >
              Add note
            </button>
          </div>
        </div>
      ) : (
        <div className="space-y-4">
          {Object.keys(report.grades).length > 0 && (
            <dl className="grid grid-cols-3 gap-x-4 gap-y-2 sm:grid-cols-6">
              {Object.entries(tools).map(([key, label]) => (
                <div key={key}>
                  <dt className="text-[11px] uppercase tracking-wide text-neutral-500">{label}</dt>
                  <dd className={`tabular-nums ${gradeClass(report.grades[key]?.future ?? report.grades[key]?.present)}`}>
                    {formatGrade(report.grades[key])}
                  </dd>
                </div>
              ))}
            </dl>
          )}
          {report.notes.length > 0 && (
            <ul className="space-y-2">
              {report.notes.map((n, i) => (
                <li key={`${n.date}-${i}`} className="border-l-2 border-neutral-800 pl-3">
                  <time className="text-xs text-neutral-500">{n.date}</time>
                  <p className="whitespace-pre-wrap text-sm text-neutral-300">{n.text}</p>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </section>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-xs uppercase tracking-wide text-neutral-500">{label}</span>
      {children}
    </label>
  )
}
