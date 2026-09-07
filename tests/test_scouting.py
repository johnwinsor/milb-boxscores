import json

import pytest

from milb import scouting
from milb.scouting import ScoutingError

VALID = {
    "schema": 1,
    "players": {
        "829045": {
            "grades": {"hit": 50, "raw_power": {"present": 45, "future": 60}},
            "fv": 55, "risk": "high", "eta": 2029,
            "notes": [{"date": "2026-09-01", "text": "Plus bat speed."}],
        }
    },
}


def test_parse_normalizes_grades():
    r = scouting.parse(VALID)[829045]
    # A bare number is shorthand for the future grade -- that is the one that
    # matters for a prospect.
    assert r["grades"]["hit"] == {"future": 50}
    assert r["grades"]["raw_power"] == {"present": 45, "future": 60}
    assert (r["fv"], r["risk"], r["eta"]) == (55, "high", 2029)


def test_notes_sort_newest_first():
    doc = json.loads(json.dumps(VALID))
    doc["players"]["829045"]["notes"] = [
        {"date": "2026-04-01", "text": "early"},
        {"date": "2026-08-01", "text": "late"},
    ]
    assert [n["text"] for n in scouting.parse(doc)[829045]["notes"]] == ["late", "early"]


def test_empty_reports_are_dropped():
    doc = {"schema": 1, "players": {"1": {"grades": {}, "notes": []}}}
    assert scouting.parse(doc) == {}


@pytest.mark.parametrize("mutate,message", [
    (lambda d: d.update(schema=99), "schema"),
    (lambda d: d["players"]["829045"].update(fv=95), "20-80"),
    (lambda d: d["players"]["829045"].update(fv=10), "20-80"),
    (lambda d: d["players"]["829045"].update(grades={"zzz": 50}), "unknown tool"),
    (lambda d: d["players"]["829045"].update(risk="ultra"), "risk must be"),
    (lambda d: d["players"]["829045"].update(eta="soon"), "eta"),
    (lambda d: d["players"]["829045"].update(notes=[{"date": "2026-01-01"}]), "text"),
    (lambda d: d.update(players={"not-an-id": {}}), "person_id"),
])
def test_malformed_reports_raise(mutate, message):
    """A bad browser write must fail the Action loudly, not land silently."""
    doc = json.loads(json.dumps(VALID))
    mutate(doc)
    with pytest.raises(ScoutingError, match=message):
        scouting.parse(doc)


def test_grades_are_keyed_to_the_right_role():
    assert "hit" in scouting.tools_for("hitting")
    assert "command" in scouting.tools_for("pitching")
    assert "hit" not in scouting.tools_for("pitching")


def test_save_skips_write_when_nothing_changed(tmp_path):
    path = tmp_path / "scouting.json"
    reports = scouting.parse(VALID)
    assert scouting.save(reports, path) is True
    before = path.read_text()
    assert scouting.save(reports, path) is False       # updated_at alone must not dirty it
    assert path.read_text() == before
    reports[829045]["fv"] = 60
    assert scouting.save(reports, path) is True


def test_roundtrip(tmp_path):
    path = tmp_path / "scouting.json"
    scouting.save(scouting.parse(VALID), path)
    assert scouting.load(path)[829045]["fv"] == 55


def test_missing_file_is_not_an_error(tmp_path):
    assert scouting.load(tmp_path / "nope.json") == {}
