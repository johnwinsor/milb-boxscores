import pytest

from milb import db as db_module


def split(game_pk, date, **stat):
    """A minimal MLB Stats API gameLog split, shaped like the real payload."""
    return {
        "season": "2026", "date": date, "gameType": "R", "isHome": True, "isWin": False,
        "stat": {"summary": "1-4", **stat},
        "team": {"id": 401, "name": "Inland Empire 66ers"},
        "opponent": {"id": 103, "name": "Lake Elsinore Storm"},
        "league": {"id": 110, "name": "California League"},
        "sport": {"id": 14, "abbreviation": "A"},
        "game": {"gamePk": game_pk},
    }


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "test.sqlite"


@pytest.fixture
def conn(db_path):
    # A real file, not :memory:, so export can reopen it read-only.
    c = db_module.connect(db_path)
    db_module.init(c)
    yield c
    c.close()


@pytest.fixture
def seeded(conn):
    """One hitter and one pitcher on one fantasy team, with games."""
    from milb.ingest import split_to_row
    conn.execute("INSERT INTO fantasy_team (name, slug, ord) VALUES ('Zebras','zebras',0)")
    for pid, name, pos, grp in [(1, "Hitter Guy", "OF", "hitting"),
                                (2, "Pitcher Guy", "SP", "pitching")]:
        conn.execute("INSERT INTO player (person_id, full_name) VALUES (?,?)", (pid, name))
        conn.execute(
            "INSERT INTO roster_entry (fantasy_team, roster_name, org, level, pos, "
            "group_type, person_id, resolution_status, ord) "
            "VALUES ('Zebras',?,'SEA','A',?,?,?,'roster',0)", (name, pos, grp, pid))

    rows = [
        # A doubleheader: two games, same date, different gamePk.
        split_to_row(split(100, "2026-08-30", atBats=4, hits=2, homeRuns=1,
                           plateAppearances=4, runs=1, rbi=2), 1, "hitting", 2026, "T"),
        split_to_row(split(101, "2026-08-30", atBats=3, hits=1, homeRuns=0,
                           plateAppearances=3, runs=0, rbi=0), 1, "hitting", 2026, "T"),
        split_to_row(split(102, "2026-08-31", atBats=5, hits=3, homeRuns=0,
                           plateAppearances=5, runs=2, rbi=1), 1, "hitting", 2026, "T"),
        split_to_row(split(200, "2026-08-30", inningsPitched="5.1", hits=4,
                           earnedRuns=2, strikeOuts=8, baseOnBalls=1), 2, "pitching", 2026, "T"),
        split_to_row(split(201, "2026-08-31", inningsPitched="1.2", hits=0,
                           earnedRuns=0, strikeOuts=3, baseOnBalls=0), 2, "pitching", 2026, "T"),
    ]
    db_module.upsert_game_logs(conn, rows)
    conn.commit()
    return conn
