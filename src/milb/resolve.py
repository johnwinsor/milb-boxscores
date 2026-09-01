"""Map a roster entry to an MLBAM personId.

The old approach called /people/search once per player. That endpoint turned out
to simply not index a large slice of the minor leagues -- 13 of 103 rostered
players returned zero results for both their full name and their surname, which
is why a pile of manual overrides had to be hand-maintained.

/sports/{sportId}/players?season=Y returns the *complete* player list for a
level. Seven requests build an index of every player in affiliated ball, which
resolves those same 13 players and costs less than one search per player. The
search endpoint is kept only as a last-resort fallback.

Resolution order, cheapest first:
  1. person_id already on the roster entry     (no request)
  2. data/overrides.json manual pin            (no request)
  3. league index, exact normalized name
  4. league index, surname + first initial     (catches "Zachary" vs "Zach")
  5. prior-season index                        (catches injured / absent players)
  6. /people/search                            (last resort)
"""

import sys

from .config import ORGS, SPORT_IDS, canonical_org, org_team_id
from .models import RosterEntry
from .util import normalize


class LeagueIndex:
    """Every player at every level for a season, indexed by normalized name."""

    def __init__(self, api, debug: bool = False):
        self.api, self.debug = api, debug
        self._by_season: dict[int, dict[str, list[dict]]] = {}

    def _log(self, msg: str) -> None:
        if self.debug:
            print(f"[debug] index: {msg}", file=sys.stderr)

    def for_season(self, season: int) -> dict[str, list[dict]]:
        if season in self._by_season:
            return self._by_season[season]
        index: dict[str, list[dict]] = {}
        seen: set[int] = set()
        for sport_id in SPORT_IDS:
            try:
                people = self.api.get(
                    f"/sports/{sport_id}/players", {"season": season}
                ).get("people", [])
            except Exception as e:
                self._log(f"sportId={sport_id} season={season} failed: {e}")
                continue
            self._log(f"sportId={sport_id} season={season} -> {len(people)} players")
            for person in people:
                if person["id"] in seen:
                    continue
                seen.add(person["id"])
                index.setdefault(normalize(person.get("fullName", "")), []).append(person)
        self._by_season[season] = index
        return index


def _parent_org_id(person: dict) -> int | None:
    """A prospect's currentTeam is their affiliate; the parent club hangs off it
    as parentOrgId (or is the team itself when they're in the majors)."""
    team = person.get("currentTeam") or {}
    mlb_ids = {t[0] for t in ORGS.values()}
    for key in ("parentOrgId", "id"):
        val = team.get(key)
        if isinstance(val, int) and val in mlb_ids:
            return val
    return None


def _pick(candidates: list[dict], entry: RosterEntry) -> dict | None:
    """Break ties by parent-org agreement.

    The old code did `org.lower() in currentTeam.name.lower()` -- comparing
    "sfg" to "San Francisco Giants" -- which is False, so disambiguation never
    fired and collisions silently took the first candidate. Comparing team ids
    actually works.
    """
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]
    want = org_team_id(entry.org)
    if want is not None:
        matched = [c for c in candidates if _parent_org_id(c) == want]
        if matched:
            return matched[0]
    active = [c for c in candidates if c.get("active")]
    return (active or candidates)[0]


def _fuzzy(index: dict[str, list[dict]], name: str) -> list[dict]:
    """Surname plus first initial. 'Zachary Root' -> 'Zach Root'."""
    tokens = normalize(name).split()
    if len(tokens) < 2:
        return []
    surname, initial = tokens[-1], tokens[0][:1]
    out = []
    for key, people in index.items():
        parts = key.split()
        if len(parts) >= 2 and parts[-1] == surname and parts[0][:1] == initial:
            out.extend(people)
    return out


def resolve_entry(entry, api, overrides, index=None, season=None, debug=False) -> RosterEntry:
    """Fill entry.person_id and entry.resolution_status. Never raises."""
    def log(msg):
        if debug:
            print(f"[debug] {entry.name}: {msg}", file=sys.stderr)

    if entry.person_id:
        entry.resolution_status = "roster"
        return entry

    pinned = overrides.get((entry.name, canonical_org(entry.org)))
    if pinned:
        entry.person_id, entry.resolution_status = pinned, "override"
        log(f"personId={pinned} (override)")
        return entry

    if index is not None and season is not None:
        for yr, status in ((season, "index"), (season - 1, "index-prior")):
            table = index.for_season(yr)
            hit = _pick(table.get(normalize(entry.name), []), entry) \
                or _pick(_fuzzy(table, entry.name), entry)
            if hit:
                entry.person_id, entry.resolution_status = hit["id"], status
                log(f"personId={hit['id']} ({hit.get('fullName')}) via {status} {yr}")
                return entry

    try:
        people = api.search_people(entry.name)
        if not people:
            surname = entry.name.strip().split()[-1]
            tokens = normalize(entry.name).split()
            people = [
                p for p in api.search_people(surname)
                if all(t in normalize(p.get("fullName", "")) for t in tokens)
            ]
    except Exception as e:
        entry.resolution_status = "unresolved"
        log(f"search failed: {e}")
        return entry

    exact = [p for p in people if normalize(p.get("fullName", "")) == normalize(entry.name)]
    hit = _pick(exact or people, entry)
    if hit:
        entry.person_id, entry.resolution_status = hit["id"], "search"
        log(f"personId={hit['id']} ({hit.get('fullName')}) via search")
    else:
        entry.resolution_status = "unresolved"
        log("unresolved")
    return entry


def resolve_all(entries, api, overrides, season, debug=False):
    """Resolve a roster in place. The same (name, org) on two fantasy teams is
    one real player with one personId, so it costs one lookup."""
    index = LeagueIndex(api, debug=debug)
    seen: dict[tuple[str, str], int | None] = {}
    for entry in entries:
        key = (entry.name, canonical_org(entry.org))
        if not entry.person_id and seen.get(key):
            entry.person_id, entry.resolution_status = seen[key], "duplicate"
            continue
        resolve_entry(entry, api, overrides, index=index, season=season, debug=debug)
        if entry.person_id:
            seen.setdefault(key, entry.person_id)
    return entries
