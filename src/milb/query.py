"""Read player-game data out of SQLite in the shape renderers and exports want.

Record dicts are key-compatible with the original CLI's build_hitting_record /
build_pitching_record output, so CSV and JSON exports stay byte-comparable.
"""

import json
from dataclasses import dataclass, field

from .config import LEVEL_ORDER
from .util import outs_to_ip, window_bounds

HITTING_KEYS = ["PA", "AB", "H", "R", "RBI", "2B", "HR", "SB", "CS", "BB", "K"]
PITCHING_KEYS = ["IP", "H", "R", "ER", "BB", "K", "HR"]


@dataclass
class PlayerReport:
    fantasy_team: str
    name: str
    org: str
    level: str
    pos: str
    group: str
    person_id: int | None
    slug: str = ""
    full_name: str = ""
    records: list[dict] = field(default_factory=list)
    total: dict | None = None
    error: str | None = None

    @property
    def is_pitcher(self) -> bool:
        return self.group == "pitching"


def _record(row, entry, is_pitcher: bool) -> dict:
    """One game line. Identity fields first (CSV order), then stats."""
    rec = {
        "date": row["date"], "player": entry["roster_name"], "org": entry["org"],
        "level": row["sport_abbr"] or entry["level"], "pos": entry["pos"],
        "type": "pitching" if is_pitcher else "hitting",
        "fantasy_team": entry["fantasy_team"],
        "team": row["team_name"] or entry["org"],
        "opponent": row["opponent_name"] or "?",
        "is_total": False,
    }
    if is_pitcher:
        rec.update({
            "IP": outs_to_ip(row["outs"]), "H": row["h"], "R": row["r"],
            "ER": row["er"], "BB": row["bb"], "K": row["k"], "HR": row["hr"],
        })
    else:
        rec.update({
            "PA": row["pa"], "AB": row["ab"], "H": row["h"], "R": row["r"],
            "RBI": row["rbi"], "2B": row["doubles"], "HR": row["hr"],
            "SB": row["sb"], "CS": row["cs"], "BB": row["bb"], "K": row["k"],
        })
    # Extras the terminal never showed but the web app uses.
    rec["game_pk"] = row["game_pk"]
    rec["summary"] = row["summary"]
    rec["is_home"] = row["is_home"]
    rec["is_win"] = row["is_win"]
    return rec


def build_total(records: list[dict], is_pitcher: bool, entry) -> dict:
    """Aggregate a player's window. IP sums through base-3 outs, not decimals."""
    from .util import ip_to_outs
    base = {
        "date": "TOTAL", "player": entry["roster_name"], "org": entry["org"],
        "level": entry["level"], "pos": entry["pos"],
        "type": "pitching" if is_pitcher else "hitting",
        "fantasy_team": entry["fantasy_team"],
        "team": "", "opponent": "", "is_total": True,
    }
    if is_pitcher:
        base["IP"] = outs_to_ip(sum(ip_to_outs(r["IP"]) for r in records))
        for key in ["H", "R", "ER", "BB", "K", "HR"]:
            base[key] = sum(r[key] for r in records)
    else:
        for key in HITTING_KEYS:
            base[key] = sum(r[key] for r in records)
    return base


def roster(conn, team: str | None = None) -> list[dict]:
    sql = ("SELECT r.*, f.slug, p.full_name FROM roster_entry r "
           "JOIN fantasy_team f ON f.name = r.fantasy_team "
           "LEFT JOIN player p ON p.person_id = r.person_id ")
    params = []
    if team:
        sql += "WHERE lower(r.fantasy_team) = lower(?) OR f.slug = lower(?) "
        params = [team, team]
    sql += "ORDER BY f.ord, r.ord"
    return [dict(r) for r in conn.execute(sql, params)]


def report(conn, days: int, season: int, team: str | None = None, today=None) -> list[PlayerReport]:
    """The CLI's report, as data. Players with no games are still returned so
    callers can render a placeholder -- matching the original left-join layout."""
    start, end = window_bounds(days, today)
    entries = roster(conn, team)
    out = []
    for entry in entries:
        rep = PlayerReport(
            fantasy_team=entry["fantasy_team"], name=entry["roster_name"],
            org=entry["org"], level=entry["level"], pos=entry["pos"],
            group=entry["group_type"], person_id=entry["person_id"],
            slug=entry["slug"], full_name=entry["full_name"] or entry["roster_name"],
        )
        if not entry["person_id"]:
            rep.error = "could not find player on MLB Stats API"
            out.append(rep)
            continue

        rows = conn.execute(
            "SELECT * FROM game_log WHERE person_id=? AND group_type=? AND season=? "
            "AND date BETWEEN ? AND ? ORDER BY date, game_pk",
            (entry["person_id"], entry["group_type"], season,
             start.isoformat(), end.isoformat()),
        ).fetchall()

        if not rows:
            has_any = conn.execute(
                "SELECT 1 FROM game_log WHERE person_id=? AND group_type=? AND season=? LIMIT 1",
                (entry["person_id"], entry["group_type"], season),
            ).fetchone()
            if not has_any:
                rep.error = f"no {entry['group_type']} game log found for {season}"
            out.append(rep)
            continue

        is_p = entry["group_type"] == "pitching"
        rep.records = [_record(r, entry, is_p) for r in rows]
        if len(rep.records) > 1:
            rep.total = build_total(rep.records, is_p, entry)
        out.append(rep)
    return out


def flat_records(reports: list[PlayerReport]) -> list[dict]:
    """Flatten to the row list the original CSV/JSON writers consumed."""
    out = []
    for rep in reports:
        out.extend(rep.records)
        if rep.total:
            out.append(rep.total)
    return out


def season_log(conn, person_id: int, season: int) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM game_log WHERE person_id=? AND season=? ORDER BY date, game_pk",
        (person_id, season),
    ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["raw_stat"] = json.loads(r["raw_stat"] or "{}")
        d["IP"] = outs_to_ip(r["outs"])
        out.append(d)
    return out


def level_changes(log: list[dict]) -> list[dict]:
    """Transitions between levels, with direction. The CLI discarded sport_abbr
    entirely, so promotions and demotions were invisible."""
    changes, prev = [], None
    for g in log:
        lvl = g.get("sport_abbr")
        if lvl and lvl != prev:
            if prev is not None:
                a = LEVEL_ORDER.index(prev) if prev in LEVEL_ORDER else -1
                b = LEVEL_ORDER.index(lvl) if lvl in LEVEL_ORDER else -1
                changes.append({"date": g["date"], "from": prev, "to": lvl,
                                "direction": "up" if b > a else "down"})
            prev = lvl
    return changes


def seasons(conn) -> list[int]:
    return [r[0] for r in conn.execute(
        "SELECT DISTINCT season FROM game_log ORDER BY season DESC")]
