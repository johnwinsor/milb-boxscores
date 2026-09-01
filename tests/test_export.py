import json
from datetime import date

from milb import export


def test_export_writes_every_file_on_every_run(seeded, db_path, tmp_path):
    """The dedupe guard must be per-run, not a filesystem check -- an exists()
    test would silently skip every player on the second export and leave the
    site serving stale data."""
    first = export.run(2026, db_path=db_path, out_dir=tmp_path, today=date(2026, 8, 31))
    second = export.run(2026, db_path=db_path, out_dir=tmp_path, today=date(2026, 8, 31))
    assert first == second
    assert len(list((tmp_path / "players").glob("*.json"))) == 2


def test_player_export_shape(seeded, db_path, tmp_path):
    export.run(2026, db_path=db_path, out_dir=tmp_path, today=date(2026, 8, 31))
    hitter = json.loads((tmp_path / "players" / "1.json").read_text())
    assert hitter["season_total"]["G"] == 3          # both doubleheader games count
    assert hitter["season_total"]["H"] == 6
    assert hitter["season_total"]["AVG"] == round(6 / 12, 3)
    assert hitter["splits"]["7d"]["G"] == 3
    assert len(hitter["games"]) == 3
    assert hitter["games"][0]["gamePk"]              # links to MLB Gameday

    pitcher = json.loads((tmp_path / "players" / "2.json").read_text())
    assert pitcher["season_total"]["IP"] == "7.0"    # 5.1 + 1.2, base-3
    assert pitcher["season_total"]["ERA"] == round(2 * 9 / 7, 2)


def test_meta_and_windows(seeded, db_path, tmp_path):
    export.run(2026, db_path=db_path, out_dir=tmp_path, today=date(2026, 8, 31))
    meta = json.loads((tmp_path / "meta.json").read_text())
    assert meta["players_total"] == 2 and meta["players_unresolved"] == 0
    assert meta["teams"][0]["name"] == "Zebras"
    for days in export.WINDOWS:
        w = json.loads((tmp_path / "windows" / f"{days}d.json").read_text())
        assert len(w["players"]) == 2
