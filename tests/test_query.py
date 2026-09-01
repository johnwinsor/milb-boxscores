from datetime import date

from milb import query
from milb.render import CSV_FIELDS


def test_report_includes_doubleheader_and_totals(seeded):
    reps = {r.name: r for r in query.report(seeded, 7, 2026, today=date(2026, 8, 31))}
    hitter = reps["Hitter Guy"]
    assert len(hitter.records) == 3            # both halves of the 8/30 doubleheader
    assert hitter.total["PA"] == 12            # 4 + 3 + 5
    assert hitter.total["H"] == 6
    assert hitter.total["HR"] == 1


def test_pitching_total_sums_ip_in_base_three(seeded):
    reps = {r.name: r for r in query.report(seeded, 7, 2026, today=date(2026, 8, 31))}
    pitcher = reps["Pitcher Guy"]
    # 5.1 (16 outs) + 1.2 (5 outs) = 21 outs = 7.0 innings, NOT 6.3
    assert pitcher.total["IP"] == "7.0"
    assert pitcher.total["K"] == 11


def test_single_game_gets_no_total_row(seeded):
    # days=0 is just today; the window is inclusive on both ends, so days=1
    # would still pull in the 8/30 doubleheader.
    reps = {r.name: r for r in query.report(seeded, 0, 2026, today=date(2026, 8, 31))}
    assert len(reps["Hitter Guy"].records) == 1
    assert reps["Hitter Guy"].total is None


def test_window_is_inclusive_of_both_ends(seeded):
    reps = {r.name: r for r in query.report(seeded, 1, 2026, today=date(2026, 8, 31))}
    assert len(reps["Hitter Guy"].records) == 3   # 8/30 doubleheader + 8/31


def test_unresolved_player_reports_an_error(seeded):
    seeded.execute("INSERT INTO roster_entry (fantasy_team, roster_name, org, level, pos, "
                   "group_type, person_id, resolution_status, ord) "
                   "VALUES ('Zebras','Ghost Player','SEA','TBD','OF','hitting',NULL,"
                   "'unresolved',9)")
    reps = {r.name: r for r in query.report(seeded, 7, 2026, today=date(2026, 8, 31))}
    assert reps["Ghost Player"].error == "could not find player on MLB Stats API"
    assert reps["Ghost Player"].records == []


def test_players_with_no_games_still_appear(seeded):
    """The report is a left join: a quiet player renders a placeholder card."""
    reps = query.report(seeded, 7, 2026, today=date(2026, 9, 30))
    assert len(reps) == 2
    assert all(r.records == [] for r in reps)


def test_flat_records_cover_every_csv_field(seeded):
    records = query.flat_records(query.report(seeded, 7, 2026, today=date(2026, 8, 31)))
    assert records
    for rec in records:
        for field in ["fantasy_team", "date", "player", "org", "level", "pos",
                      "type", "team", "opponent", "is_total"]:
            assert field in rec, f"{field} missing from {rec}"
    assert set(CSV_FIELDS) - set().union(*(r.keys() for r in records)) == set()


def test_level_changes_detects_direction():
    log = [{"date": "2026-04-01", "sport_abbr": "A+"},
           {"date": "2026-06-01", "sport_abbr": "AA"},
           {"date": "2026-08-01", "sport_abbr": "A+"}]
    changes = query.level_changes(log)
    assert [c["direction"] for c in changes] == ["up", "down"]
    assert changes[0]["from"] == "A+" and changes[0]["to"] == "AA"
