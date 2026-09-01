/**
 * Roster writes go through the GitHub Contents API: a save is a commit.
 *
 * The site is static, so there is no server to authenticate against. The admin
 * pastes a fine-grained token scoped to this one repo with Contents:read+write;
 * it lives only in this browser's localStorage and is never committed. Visitors
 * without a token see a read-only site.
 */
const TOKEN_KEY = 'milb.github.token'
const REPO_KEY = 'milb.github.repo'
const DEFAULT_REPO = 'johnwinsor/milb-boxscores'
const ROSTER_PATH = 'data/rosters.json'

export const getToken = () => localStorage.getItem(TOKEN_KEY) ?? ''
export const setToken = (t: string) =>
  t ? localStorage.setItem(TOKEN_KEY, t) : localStorage.removeItem(TOKEN_KEY)
export const getRepo = () => localStorage.getItem(REPO_KEY) || DEFAULT_REPO
export const setRepo = (r: string) => localStorage.setItem(REPO_KEY, r || DEFAULT_REPO)

async function gh<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`https://api.github.com${path}`, {
    ...init,
    headers: {
      Accept: 'application/vnd.github+json',
      'X-GitHub-Api-Version': '2022-11-28',
      Authorization: `Bearer ${getToken()}`,
      ...(init.body ? { 'Content-Type': 'application/json' } : {}),
      ...init.headers,
    },
  })
  if (!res.ok) {
    const body = await res.text()
    let message = `${res.status} ${res.statusText}`
    try { message = JSON.parse(body).message ?? message } catch { /* plain text */ }
    if (res.status === 401) message = 'Token rejected. Check it has not expired or been revoked.'
    if (res.status === 404) message = `Not found. Check the repo name and that the token grants access to ${getRepo()}.`
    throw new Error(message)
  }
  return res.status === 204 ? (undefined as T) : ((await res.json()) as T)
}

export interface RosterFile { doc: RosterDoc; sha: string }
export interface RosterDoc {
  schema: number
  updated_at: string
  teams: { name: string; slug: string; players: RosterPlayerDoc[] }[]
}
export interface RosterPlayerDoc {
  name: string
  org: string
  level: string
  pos: string
  person_id: number | null
  notes: string
}

/** Read rosters.json plus its blob SHA, which the next write must supply. */
export async function fetchRoster(): Promise<RosterFile> {
  const res = await gh<{ content: string; sha: string }>(
    `/repos/${getRepo()}/contents/${ROSTER_PATH}`,
  )
  // atob gives latin-1; round-trip through TextDecoder so accented names survive.
  const bytes = Uint8Array.from(atob(res.content.replace(/\n/g, '')), (c) => c.charCodeAt(0))
  return { doc: JSON.parse(new TextDecoder().decode(bytes)), sha: res.sha }
}

export async function saveRoster(doc: RosterDoc, sha: string, message: string) {
  const json = JSON.stringify({ ...doc, updated_at: new Date().toISOString().replace(/\.\d+/, '') }, null, 2) + '\n'
  const content = btoa(String.fromCharCode(...new TextEncoder().encode(json)))
  return gh<{ commit: { sha: string; html_url: string } }>(
    `/repos/${getRepo()}/contents/${ROSTER_PATH}`,
    { method: 'PUT', body: JSON.stringify({ message, content, sha }) },
  )
}

/** Kick the pipeline immediately instead of waiting for the daily cron. */
export async function triggerRefresh() {
  await gh(`/repos/${getRepo()}/dispatches`, {
    method: 'POST',
    body: JSON.stringify({ event_type: 'refresh' }),
  })
}

// -- MLB Stats API ---------------------------------------------------------
// statsapi.mlb.com sends Access-Control-Allow-Origin: *, so player search runs
// straight from the browser with no proxy.

export interface Candidate {
  id: number
  fullName: string
  currentTeam?: { name?: string }
  primaryPosition?: { abbreviation?: string }
  birthDate?: string
  active?: boolean
}

export async function searchPlayers(name: string): Promise<Candidate[]> {
  const url = `https://statsapi.mlb.com/api/v1/people/search?names=${encodeURIComponent(name)}&hydrate=currentTeam`
  const res = await fetch(url)
  if (!res.ok) throw new Error(`MLB search failed: ${res.status}`)
  return (await res.json()).people ?? []
}

export async function lookupPlayer(personId: number): Promise<Candidate | null> {
  const url = `https://statsapi.mlb.com/api/v1/people/${personId}?hydrate=currentTeam`
  const res = await fetch(url)
  if (!res.ok) return null
  return (await res.json()).people?.[0] ?? null
}
