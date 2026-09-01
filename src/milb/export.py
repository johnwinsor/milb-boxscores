"""Render SQLite into the static JSON the web app fetches.

All derivation happens here rather than in the browser, so adding advanced
stats or scouting metrics later means changing Python and re-exporting -- the
frontend's data-fetching layer never moves.
"""

import json
from datetime import date, datetime, timezone
from pathlib import Path

from . import db, query
from .config import LEVEL_ORDER, WEB_API_DIR
from .util import ip_to_outs, outs_to_ip

WINDOWS = [1, 3, 7, 15, 30]

HITTING_TOTAL_KEYS = ["PA", "AB", "H", "R", "RBI", "2B", "HR", "SB", "CS", "BB", "K"]
PITCHING_TOTAL_KEYS = ["H", "R", "ER", "BB", "K", "HR"]


def _write(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, separators=(",", ":"), default=str))


def _rate_stats(t: dict) -> dict:
    """Slash line from counting stats. Single-game rates from the API are not
    reused because they don't aggregate across a window."""
    ab, bb, h = t.get("AB", 0), t.get("BB", 0), t.get("H", 0)
    hr, doubles = t.get("HR", 0), t.get("2B", 0)
    pa = t.get("PA", 0) or (ab + bb)
    singles = max(h - doubles - hr, 0)
    tb = singles + 2 * doubles + 4 * hr  # triples fold into singles here; see note
    avg = h / ab if ab else 0.0
    obp = (h + bb) / pa if pa else 0.0
    slg = tb / ab if ab else 0.0
    return {"AVG": round(avg, 3), "OBP": round(obp, 3),
            "SLG": round(slg, 3), "OPS": round(obp + slg, 3)}


def _pitching_rates(t: dict) -> dict:
    outs = ip_to_outs(t.get("IP", "0.0"))
    innings = outs / 3 if outs else 0.0
    return {
        "ERA": round(t.get("ER", 0) * 9 / innings, 2) if innings else None,
        "WHIP": round((t.get("H", 0) + t.get("BB", 0)) / innings, 2) if innings else None,
        "K9": round(t.get("K", 0) * 9 / innings, 1) if innings else None,
    }


def _aggregate(games: list[dict], is_pitcher: bool) -> dict:
    """Sum a list of season_log games into a totals dict, with rate stats."""
    if is_pitcher:
        outs = sum(g["outs"] or 0 for g in games)
        total = {"G": len(games), "IP": outs_to_ip(outs),
                 "H": sum(g["h"] or 0 for g in games),
                 "R": sum(g["r"] or 0 for g in games),
                 "ER": sum(g["er"] or 0 for g in games),
                 "BB": sum(g["bb"] or 0 for g in games),
                 "K": sum(g["k"] or 0 for g in games),
                 "HR": sum(g["hr"] or 0 for g in games)}
        total.update(_pitching_rates(total))
        return total
    cols = {"PA": "pa", "AB": "ab", "H": "h", "R": "r", "RBI": "rbi",
            "2B": "doubles", "3B": "triples", "HR": "hr", "SB": "sb",
            "CS": "cs", "BB": "bb", "K": "k", "HBP": "hbp", "TB": "tb"}
    total = {"G": len(games)}
    total.update({k: sum(g[c] or 0 for g in games) for k, c in cols.items()})
    total.update(_rate_stats(total))
    # TB comes straight from the API when present; prefer it over the estimate.
    if total.get("TB"):
        ab = total["AB"]
        total["SLG"] = round(total["TB"] / ab, 3) if ab else 0.0
        total["OPS"] = round(total["OBP"] + total["SLG"], 3)
    return total


def _game_row(g: dict, is_pitcher: bool) -> dict:
    """One game, trimmed to what the UI renders."""
    base = {"date": g["date"], "gamePk": g["game_pk"], "level": g["sport_abbr"],
            "team": g["team_name"], "opp": g["opponent_name"],
            "home": bool(g["is_home"]), "win": bool(g["is_win"]),
            "summary": g["summary"]}
    if is_pitcher:
        base.update({k: g[c] for k, c in
                     {"H": "h", "R": "r", "ER": "er", "BB": "bb", "K": "k", "HR": "hr"}.items()})
        base["IP"] = g["IP"]
    else:
        base.update({k: g[c] for k, c in
                     {"PA": "pa", "AB": "ab", "H": "h", "R": "r", "RBI": "rbi",
                      "2B": "doubles", "3B": "triples", "HR": "hr", "SB": "sb",
                      "CS": "cs", "BB": "bb", "K": "k"}.items()})
    return base


def _report_payload(conn, days: int, season: int, today=None) -> dict:
    reports = query.report(conn, days, season, today=today)
    return {
        "days": days, "season": season,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "players": [
            {
                "fantasy_team": r.fantasy_team, "name": r.name, "full_name": r.full_name,
                "org": r.org, "level": r.level, "pos": r.pos, "group": r.group,
                "person_id": r.person_id, "team_slug": r.slug,
                "error": r.error,
                "games": [
                    {k: v for k, v in rec.items()
                     if k not in ("fantasy_team", "player", "org", "pos", "type", "is_total")}
                    for rec in r.records
                ],
                "total": r.total,
            }
            for r in reports
        ],
    }


def run(season: int, db_path=None, out_dir=None, today: date | None = None) -> int:
    out = Path(out_dir or WEB_API_DIR)
    conn = db.connect(db_path, readonly=True)
    written = 0

    roster = query.roster(conn)
    run_row = db.latest_run(conn)
    available = query.seasons(conn)

    teams: dict[str, dict] = {}
    for entry in roster:
        team = teams.setdefault(entry["fantasy_team"], {
            "name": entry["fantasy_team"], "slug": entry["slug"], "players": []})
        team["players"].append({
            "name": entry["roster_name"], "full_name": entry["full_name"] or entry["roster_name"],
            "org": entry["org"], "level": entry["level"], "pos": entry["pos"],
            "group": entry["group_type"], "person_id": entry["person_id"],
            "status": entry["resolution_status"], "notes": entry["notes"],
        })

    _write(out / "meta.json", {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "season": season, "seasons": available, "windows": WINDOWS,
        "levels": LEVEL_ORDER,
        "teams": [{"name": t["name"], "slug": t["slug"], "size": len(t["players"])}
                  for t in teams.values()],
        "players_total": len(roster),
        "players_unresolved": sum(1 for e in roster if not e["person_id"]),
        "last_ingest": dict(run_row) if run_row else None,
    })
    written += 1

    _write(out / "teams.json", {"teams": list(teams.values())})
    written += 1

    for days in WINDOWS:
        _write(out / "windows" / f"{days}d.json", _report_payload(conn, days, season, today))
        written += 1

    # One file per player: full season log, splits, and level moves.
    # Dedupe within this run, not against the filesystem -- checking os.path
    # would skip every player on a re-export and leave stale files behind.
    seen_players: set[int] = set()
    for entry in roster:
        pid = entry["person_id"]
        if not pid or pid in seen_players:
            continue  # a player rostered by two fantasy teams needs one file
        seen_players.add(pid)
        path = out / "players" / f"{pid}.json"
        is_p = entry["group_type"] == "pitching"
        log = query.season_log(conn, pid, season)
        games = [_game_row(g, is_p) for g in log]
        splits = {}
        for days in WINDOWS:
            start = (today or datetime.now().date()).toordinal() - days
            recent = [g for g in log
                      if datetime.strptime(g["date"], "%Y-%m-%d").date().toordinal() >= start]
            splits[f"{days}d"] = _aggregate(recent, is_p)
        _write(path, {
            "person_id": pid, "name": entry["roster_name"],
            "full_name": entry["full_name"] or entry["roster_name"],
            "org": entry["org"], "pos": entry["pos"], "group": entry["group_type"],
            "season": season, "games": games,
            "season_total": _aggregate(log, is_p),
            "splits": splits,
            "level_changes": query.level_changes(log),
            "by_level": {
                lvl: _aggregate([g for g in log if g["sport_abbr"] == lvl], is_p)
                for lvl in {g["sport_abbr"] for g in log if g["sport_abbr"]}
            },
        })
        written += 1

    conn.close()
    return written
