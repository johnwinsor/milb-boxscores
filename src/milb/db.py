"""SQLite store for scraped game logs.

Only the ingest process writes this file (locally, or in the GitHub Action), so
there is exactly one writer and none of the concurrency hazards the old
whole-file JSON cache would have hit under a web server.
"""

import json
import sqlite3
from pathlib import Path

from .config import DB_PATH

SCHEMA_VERSION = 1

SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL);

CREATE TABLE IF NOT EXISTS player (
  person_id        INTEGER PRIMARY KEY,
  full_name        TEXT,
  primary_position TEXT,
  birth_date       TEXT,
  mlb_debut_date   TEXT,
  last_seen_org    TEXT,
  last_seen_level  TEXT,
  last_seen_team   TEXT,
  resolved_at      TEXT
);

CREATE TABLE IF NOT EXISTS fantasy_team (
  name TEXT PRIMARY KEY,
  slug TEXT UNIQUE NOT NULL,
  ord  INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS roster_entry (
  fantasy_team      TEXT NOT NULL REFERENCES fantasy_team(name) ON DELETE CASCADE,
  roster_name       TEXT NOT NULL,
  org               TEXT,
  level             TEXT,
  pos               TEXT,
  group_type        TEXT,
  person_id         INTEGER REFERENCES player(person_id),
  resolution_status TEXT,
  notes             TEXT,
  ord               INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (fantasy_team, roster_name)
);

-- person_id + game_pk, NOT person_id + date. The old code merged splits keyed
-- on date, so the second game of a doubleheader silently overwrote the first.
CREATE TABLE IF NOT EXISTS game_log (
  person_id     INTEGER NOT NULL,
  game_pk       INTEGER NOT NULL,
  group_type    TEXT    NOT NULL,
  date          TEXT    NOT NULL,
  season        INTEGER NOT NULL,
  sport_id      INTEGER, sport_abbr    TEXT,
  league_id     INTEGER, league_name   TEXT,
  team_id       INTEGER, team_name     TEXT,
  opponent_id   INTEGER, opponent_name TEXT,
  is_home       INTEGER, is_win        INTEGER,
  game_type     TEXT,    summary       TEXT,
  pa INTEGER, ab INTEGER, h INTEGER, r INTEGER, rbi INTEGER,
  doubles INTEGER, triples INTEGER, hr INTEGER,
  sb INTEGER, cs INTEGER, bb INTEGER, k INTEGER,
  hbp INTEGER, tb INTEGER, sac_flies INTEGER,
  outs INTEGER, er INTEGER, pitches INTEGER,
  -- Full split.stat payload. Adding OPS, BABIP, pitch mix, or any other stat
  -- later becomes a migration plus a backfill from data already on disk,
  -- rather than a re-scrape. This is the extensibility hatch.
  raw_stat      TEXT NOT NULL,
  fetched_at    TEXT NOT NULL,
  PRIMARY KEY (person_id, game_pk, group_type)
);
CREATE INDEX IF NOT EXISTS idx_gl_person_date ON game_log(person_id, date);
CREATE INDEX IF NOT EXISTS idx_gl_date        ON game_log(date);
CREATE INDEX IF NOT EXISTS idx_gl_season      ON game_log(season);

-- Replaces the hardcoded PERSON_ID_OVERRIDES dict.
CREATE TABLE IF NOT EXISTS person_alias (
  roster_name TEXT NOT NULL,
  org         TEXT NOT NULL,
  person_id   INTEGER NOT NULL,
  note        TEXT,
  PRIMARY KEY (roster_name, org)
);

CREATE TABLE IF NOT EXISTS ingest_run (
  id                INTEGER PRIMARY KEY AUTOINCREMENT,
  started_at        TEXT, finished_at TEXT,
  season            INTEGER,
  players_attempted INTEGER, players_resolved INTEGER,
  rows_upserted     INTEGER, requests_made INTEGER,
  status            TEXT,
  errors_json       TEXT
);
"""

GAME_LOG_COLUMNS = [
    "person_id", "game_pk", "group_type", "date", "season",
    "sport_id", "sport_abbr", "league_id", "league_name",
    "team_id", "team_name", "opponent_id", "opponent_name",
    "is_home", "is_win", "game_type", "summary",
    "pa", "ab", "h", "r", "rbi", "doubles", "triples", "hr",
    "sb", "cs", "bb", "k", "hbp", "tb", "sac_flies",
    "outs", "er", "pitches", "raw_stat", "fetched_at",
]


def connect(path: Path | str | None = None, readonly: bool = False) -> sqlite3.Connection:
    path = Path(path or DB_PATH)
    if readonly:
        if not path.exists():
            raise FileNotFoundError(f"no database at {path} -- run `milb ingest` first")
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


def init(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    row = conn.execute("SELECT version FROM schema_version").fetchone()
    if row is None:
        conn.execute("INSERT INTO schema_version (version) VALUES (?)", (SCHEMA_VERSION,))
    conn.commit()


def upsert_game_logs(conn: sqlite3.Connection, rows) -> int:
    """Insert or replace player-games. Returns the number written."""
    from dataclasses import asdict, is_dataclass

    payload = []
    for row in rows:
        d = asdict(row) if is_dataclass(row) else dict(row)
        payload.append(tuple(d.get(c) for c in GAME_LOG_COLUMNS))
    if not payload:
        return 0
    placeholders = ",".join("?" * len(GAME_LOG_COLUMNS))
    conn.executemany(
        f"INSERT OR REPLACE INTO game_log ({','.join(GAME_LOG_COLUMNS)}) "
        f"VALUES ({placeholders})",
        payload,
    )
    return len(payload)


def start_run(conn: sqlite3.Connection, season: int, started_at: str) -> int:
    cur = conn.execute(
        "INSERT INTO ingest_run (started_at, season, status) VALUES (?,?,'running')",
        (started_at, season),
    )
    conn.commit()
    return cur.lastrowid


def finish_run(conn, run_id, finished_at, attempted, resolved, upserted, requests, errors, status="ok"):
    conn.execute(
        "UPDATE ingest_run SET finished_at=?, players_attempted=?, players_resolved=?, "
        "rows_upserted=?, requests_made=?, errors_json=?, status=? WHERE id=?",
        (finished_at, attempted, resolved, upserted, requests,
         json.dumps(errors), status, run_id),
    )
    conn.commit()


def latest_run(conn: sqlite3.Connection) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM ingest_run WHERE status != 'running' ORDER BY id DESC LIMIT 1"
    ).fetchone()
