"""Fetch game logs for every rostered player and upsert them into SQLite."""

import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

from . import db, rosters
from .config import SPORTS, SPORT_IDS
from .models import GameLogRow
from .resolve import resolve_all
from .statsapi import StatsAPI
from .util import ip_to_outs, slugify


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def split_to_row(split: dict, person_id: int, group: str, season: int, fetched_at: str) -> GameLogRow | None:
    """Flatten one API split into a game_log row.

    game_pk is the identity, not date: the old code merged on date, so the
    second game of a doubleheader silently overwrote the first.
    """
    game = split.get("game") or {}
    game_pk = game.get("gamePk")
    date = split.get("date")
    if not game_pk or not date:
        return None

    stat = split.get("stat") or {}
    sport = split.get("sport") or {}
    league = split.get("league") or {}
    team = split.get("team") or {}
    opp = split.get("opponent") or {}
    sport_id = sport.get("id")

    def num(key, default=0):
        val = stat.get(key, default)
        return val if isinstance(val, (int, float)) else default

    return GameLogRow(
        person_id=person_id, game_pk=game_pk, group_type=group,
        date=date, season=int(split.get("season") or season),
        sport_id=sport_id,
        sport_abbr=SPORTS.get(sport_id, (sport.get("abbreviation"),))[0],
        league_id=league.get("id"), league_name=league.get("name"),
        team_id=team.get("id"), team_name=team.get("name"),
        opponent_id=opp.get("id"), opponent_name=opp.get("name"),
        is_home=int(bool(split.get("isHome"))) if "isHome" in split else None,
        is_win=int(bool(split.get("isWin"))) if "isWin" in split else None,
        game_type=split.get("gameType"), summary=stat.get("summary"),
        pa=num("plateAppearances"), ab=num("atBats"), h=num("hits"),
        r=num("runs"), rbi=num("rbi"), doubles=num("doubles"),
        triples=num("triples"), hr=num("homeRuns"), sb=num("stolenBases"),
        cs=num("caughtStealing"), bb=num("baseOnBalls"), k=num("strikeOuts"),
        hbp=num("hitByPitch"), tb=num("totalBases"), sac_flies=num("sacFlies"),
        outs=ip_to_outs(stat.get("inningsPitched", "0.0")),
        er=num("earnedRuns"), pitches=num("numberOfPitches"),
        # Whole payload preserved: new stats become a backfill, not a re-scrape.
        raw_stat=json.dumps(stat, separators=(",", ":")),
        fetched_at=fetched_at,
    )


def fetch_player(api, person_id: int, group: str, season: int, fetched_at: str, debug=False):
    """Sweep every sportId. A player who changed levels mid-season has real games
    at more than one, and stopping at the first non-empty level strands them."""
    rows: dict[tuple, GameLogRow] = {}
    for sport_id in SPORT_IDS:
        try:
            splits = api.game_log(person_id, group, season, sport_id)
        except Exception as e:
            if debug:
                print(f"[debug] {person_id} sportId={sport_id} gave up: {e}", file=sys.stderr)
            continue
        for split in splits:
            row = split_to_row(split, person_id, group, season, fetched_at)
            if row:
                rows[(row.person_id, row.game_pk, row.group_type)] = row
    return list(rows.values())


def run(season: int, db_path=None, roster_path=None, overrides_path=None,
        workers: int = 6, debug: bool = False, api: StatsAPI | None = None) -> dict:
    """Full ingest: load rosters -> resolve ids -> fetch logs -> upsert."""
    api = api or StatsAPI(debug=debug)
    teams = rosters.load(roster_path)
    overrides = rosters.load_overrides(overrides_path)
    entries = rosters.flatten(teams)

    resolve_all(entries, api, overrides, season=season, debug=debug)
    # Newly discovered ids are written back so the lookup never runs again.
    rosters.save(teams, roster_path)

    conn = db.connect(db_path)
    db.init(conn)
    started = _now()
    run_id = db.start_run(conn, season, started)

    _write_rosters(conn, teams)

    resolved = [e for e in entries if e.person_id]
    errors = {f"{e.fantasy_team}|{e.name}": "could not find player on MLB Stats API"
              for e in entries if not e.person_id}

    # One fetch per distinct (person_id, group) -- a player on two fantasy
    # rosters is still one set of API calls.
    jobs = {(e.person_id, e.group) for e in resolved}
    fetched_at = _now()
    upserted = 0

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(fetch_player, api, pid, grp, season, fetched_at, debug): (pid, grp)
            for pid, grp in jobs
        }
        for fut in as_completed(futures):
            pid, grp = futures[fut]
            try:
                rows = fut.result()
            except Exception as e:
                errors[str(pid)] = f"fetch failed: {e}"
                continue
            upserted += db.upsert_game_logs(conn, rows)
    conn.commit()

    _update_players(conn, api, sorted({e.person_id for e in resolved}))

    db.finish_run(conn, run_id, _now(), len(entries), len(resolved),
                  upserted, api.requests_made, errors,
                  status="ok" if not errors else "partial")
    conn.execute("VACUUM")
    conn.close()

    return {"players": len(entries), "resolved": len(resolved), "rows": upserted,
            "requests": api.requests_made, "errors": errors}


def _write_rosters(conn, teams) -> None:
    """Mirror rosters.json into SQLite so exports can join in one query."""
    conn.execute("DELETE FROM roster_entry")
    conn.execute("DELETE FROM fantasy_team")
    for i, team in enumerate(teams):
        conn.execute(
            "INSERT INTO fantasy_team (name, slug, ord) VALUES (?,?,?)",
            (team.name, team.slug or slugify(team.name), i),
        )
        for j, p in enumerate(team.players):
            if p.person_id:
                # Stub the dimension row so the FK holds; _update_players fills
                # in the details once the fetch is done.
                conn.execute(
                    "INSERT OR IGNORE INTO player (person_id) VALUES (?)", (p.person_id,)
                )
            conn.execute(
                "INSERT INTO roster_entry (fantasy_team, roster_name, org, level, pos, "
                "group_type, person_id, resolution_status, notes, ord) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (team.name, p.name, p.org, p.level, p.pos, p.group,
                 p.person_id, p.resolution_status, p.notes, j),
            )
    conn.commit()


def _update_players(conn, api, person_ids) -> None:
    """Refresh the player dimension. Batched -- 100 ids per request."""
    if not person_ids:
        return
    try:
        people = api.get_people(person_ids)
    except Exception:
        return
    now = _now()
    for p in people:
        team = p.get("currentTeam") or {}
        conn.execute(
            "INSERT INTO player (person_id, full_name, primary_position, birth_date, "
            "mlb_debut_date, last_seen_team, resolved_at) VALUES (?,?,?,?,?,?,?) "
            "ON CONFLICT(person_id) DO UPDATE SET full_name=excluded.full_name, "
            "primary_position=excluded.primary_position, birth_date=excluded.birth_date, "
            "mlb_debut_date=excluded.mlb_debut_date, last_seen_team=excluded.last_seen_team, "
            "resolved_at=excluded.resolved_at",
            (p["id"], p.get("fullName"), (p.get("primaryPosition") or {}).get("abbreviation"),
             p.get("birthDate"), p.get("mlbDebutDate"), team.get("name"), now),
        )
    # Level/org come from the most recent game actually played.
    conn.execute("""
        UPDATE player SET
          last_seen_level = (SELECT sport_abbr FROM game_log g WHERE g.person_id = player.person_id
                             ORDER BY g.date DESC, g.game_pk DESC LIMIT 1),
          last_seen_team  = COALESCE((SELECT team_name FROM game_log g WHERE g.person_id = player.person_id
                             ORDER BY g.date DESC, g.game_pk DESC LIMIT 1), last_seen_team)
    """)
    conn.commit()
