import type { Meta, PlayerDetail, TeamsDoc, WindowReport } from './types'

// import.meta.env.BASE_URL is Vite's configured base ('/milb-boxscores/'), so
// these resolve correctly both on Pages and on the dev server at '/'.
const API = `${import.meta.env.BASE_URL}api`

const cache = new Map<string, Promise<unknown>>()

function get<T>(path: string): Promise<T> {
  const url = `${API}/${path}`
  if (!cache.has(url)) {
    cache.set(
      url,
      fetch(url).then((r) => {
        if (!r.ok) throw new Error(`${r.status} ${r.statusText} for ${path}`)
        return r.json()
      }),
    )
  }
  return cache.get(url) as Promise<T>
}

export const fetchMeta = () => get<Meta>('meta.json')
export const fetchTeams = () => get<TeamsDoc>('teams.json')
export const fetchWindow = (days: number) => get<WindowReport>(`windows/${days}d.json`)
export const fetchPlayer = (personId: number) => get<PlayerDetail>(`players/${personId}.json`)
