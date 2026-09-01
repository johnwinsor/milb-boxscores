export type Group = 'hitting' | 'pitching'

export interface Game {
  date: string
  level: string | null
  team: string
  opponent: string
  game_pk: number
  summary: string | null
  is_home: number | null
  is_win: number | null
  [stat: string]: string | number | null
}

export interface Total {
  date: 'TOTAL'
  is_total: true
  [stat: string]: string | number | boolean
}

export interface ReportPlayer {
  fantasy_team: string
  name: string
  full_name: string
  org: string
  level: string
  pos: string
  group: Group
  person_id: number | null
  team_slug: string
  error: string | null
  games: Game[]
  total: Total | null
}

export interface WindowReport {
  days: number
  season: number
  generated_at: string
  players: ReportPlayer[]
}

export interface Meta {
  generated_at: string
  season: number
  seasons: number[]
  windows: number[]
  levels: string[]
  teams: { name: string; slug: string; size: number }[]
  players_total: number
  players_unresolved: number
  last_ingest: {
    finished_at: string | null
    players_resolved: number
    rows_upserted: number
    status: string
  } | null
}

export interface RosterPlayer {
  name: string
  full_name: string
  org: string
  level: string
  pos: string
  group: Group
  person_id: number | null
  status: string
  notes: string
}

export interface TeamsDoc {
  teams: { name: string; slug: string; players: RosterPlayer[] }[]
}

export interface StatLine {
  G: number
  [key: string]: number | string | null
}

export interface PlayerDetail {
  person_id: number
  name: string
  full_name: string
  org: string
  pos: string
  group: Group
  season: number
  games: PlayerGame[]
  season_total: StatLine
  splits: Record<string, StatLine>
  level_changes: { date: string; from: string; to: string; direction: 'up' | 'down' }[]
  by_level: Record<string, StatLine>
}

export interface PlayerGame {
  date: string
  gamePk: number
  level: string | null
  team: string
  opp: string
  home: boolean
  win: boolean
  summary: string | null
  [stat: string]: string | number | boolean | null
}
