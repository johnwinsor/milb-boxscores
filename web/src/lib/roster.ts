import type { RosterDoc } from './github'

/**
 * Client-side mirror of the rules in src/milb/rosters.py.
 *
 * The Action validates rosters.json on load and fails loudly on a bad document,
 * which is the right server behaviour but a poor way to find out: the site
 * keeps serving the last good build while that night's refresh quietly does not
 * run. Catching the same problems before the commit turns a failed workflow
 * into an inline message.
 *
 * Keep these rules in step with rosters.py -- anything rejected there should be
 * caught here first.
 */

export const ORGS = [
  'ARI', 'ATH', 'ATL', 'BAL', 'BOS', 'CHC', 'CHW', 'CIN', 'CLE', 'COL', 'DET',
  'HOU', 'KC', 'LAA', 'LAD', 'MIA', 'MIL', 'MIN', 'NYM', 'NYY', 'PHI', 'PIT',
  'SD', 'SEA', 'SF', 'STL', 'TB', 'TEX', 'TOR', 'WSH',
]

export const LEVELS = ['TBD', 'DSL', 'CPX', 'A', 'A+', 'AA', 'AAA', 'MLB']

/** Any of these tokens in `pos` makes the pipeline pull pitching logs. */
export const PITCHER_TOKENS = ['SP', 'RP', 'P', 'CP']

export function isPitcher(pos: string): boolean {
  return (pos ?? '').split('/').some((t) => PITCHER_TOKENS.includes(t.trim().toUpperCase()))
}

export interface Issue {
  team: number
  player: number | null
  field: 'name' | 'pos' | 'org' | 'team'
  message: string
}

export function validateRoster(doc: RosterDoc): Issue[] {
  const issues: Issue[] = []
  const seenTeams = new Set<string>()

  doc.teams.forEach((team, ti) => {
    const name = (team.name ?? '').trim()
    if (!name) {
      issues.push({ team: ti, player: null, field: 'team', message: 'Team needs a name' })
    } else if (seenTeams.has(name.toLowerCase())) {
      issues.push({ team: ti, player: null, field: 'team', message: `Duplicate team name "${name}"` })
    } else {
      seenTeams.add(name.toLowerCase())
    }

    const seenPlayers = new Set<string>()
    team.players.forEach((p, pi) => {
      const pname = (p.name ?? '').trim()
      const label = pname || `row ${pi + 1}`

      if (!pname) {
        issues.push({ team: ti, player: pi, field: 'name', message: `${team.name}: an empty row needs a name (or remove it)` })
      } else if (seenPlayers.has(pname.toLowerCase())) {
        issues.push({ team: ti, player: pi, field: 'name', message: `${team.name}: "${pname}" is listed twice` })
      } else {
        seenPlayers.add(pname.toLowerCase())
      }

      // Not rejected by the Action, but a blank position silently makes someone
      // a hitter -- which fetches the wrong game log and yields no data.
      if (!(p.pos ?? '').trim()) {
        issues.push({ team: ti, player: pi, field: 'pos', message: `${team.name}: ${label} needs a position` })
      }

      const org = (p.org ?? '').trim().toUpperCase()
      if (!org) {
        issues.push({ team: ti, player: pi, field: 'org', message: `${team.name}: ${label} needs an org` })
      } else if (!ORGS.includes(org)) {
        issues.push({ team: ti, player: pi, field: 'org', message: `${team.name}: ${label} has an unknown org "${p.org}"` })
      }
    })
  })

  return issues
}

export const hasIssue = (issues: Issue[], team: number, player: number | null, field: Issue['field']) =>
  issues.some((i) => i.team === team && i.player === player && i.field === field)
