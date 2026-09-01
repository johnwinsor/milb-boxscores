import json

from milb import db
from milb.ingest import split_to_row

from conftest import split


def test_split_to_row_maps_fields():
    row = split_to_row(split(816524, "2026-08-11", atBats=5, hits=2, doubles=1,
                             plateAppearances=5, rbi=1, strikeOuts=1, runs=1,
                             totalBases=3, avg=".400"),
                       829045, "hitting", 2026, "2026-08-31T00:00:00Z")
    assert (row.person_id, row.game_pk, row.group_type) == (829045, 816524, "hitting")
    assert (row.ab, row.h, row.doubles, row.pa, row.rbi, row.tb) == (5, 2, 1, 5, 1, 3)
    assert row.sport_abbr == "A" and row.league_name == "California League"
    assert row.team_name == "Inland Empire 66ers"
    # The whole payload is preserved so new stats are a backfill, not a re-scrape.
    assert json.loads(row.raw_stat)["avg"] == ".400"


def test_split_to_row_converts_ip_to_outs():
    row = split_to_row(split(1, "2026-08-11", inningsPitched="5.1"),
                       1, "pitching", 2026, "T")
    assert row.outs == 16


def test_split_without_gamepk_is_skipped():
    s = split(1, "2026-08-11")
    del s["game"]["gamePk"]
    assert split_to_row(s, 1, "hitting", 2026, "T") is None


def test_doubleheader_games_both_persist(conn):
    """The original merged splits keyed on date, so the second game of a
    doubleheader silently overwrote the first."""
    rows = [split_to_row(split(pk, "2026-08-30", hits=h), 1, "hitting", 2026, "T")
            for pk, h in [(100, 2), (101, 1)]]
    conn.execute("INSERT INTO player (person_id) VALUES (1)")
    assert db.upsert_game_logs(conn, rows) == 2
    stored = conn.execute("SELECT count(*), sum(h) FROM game_log WHERE date='2026-08-30'").fetchone()
    assert tuple(stored) == (2, 3)


def test_upsert_is_idempotent(conn):
    conn.execute("INSERT INTO player (person_id) VALUES (1)")
    row = split_to_row(split(100, "2026-08-30", hits=2), 1, "hitting", 2026, "T")
    db.upsert_game_logs(conn, [row])
    db.upsert_game_logs(conn, [row])
    assert conn.execute("SELECT count(*) FROM game_log").fetchone()[0] == 1
