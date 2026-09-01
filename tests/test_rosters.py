import json

import pytest

from milb import rosters
from milb.rosters import RosterError

VALID = {
    "schema": 1,
    "teams": [{"name": "Zebras", "slug": "zebras", "players": [
        {"name": "Yorger Bautista", "org": "SEA", "level": "CPX", "pos": "OF",
         "person_id": 829045},
        {"name": "Jamie Arnold", "org": "ATH", "level": "AA", "pos": "SP"},
    ]}],
}


def test_parse_valid():
    teams = rosters.parse(VALID)
    assert len(teams) == 1 and len(teams[0].players) == 2
    assert teams[0].players[0].resolution_status == "roster"   # has person_id
    assert teams[0].players[1].resolution_status == "pending"
    assert teams[0].players[1].group == "pitching"
    assert teams[0].players[0].group == "hitting"


def test_org_is_canonicalized_on_load():
    doc = json.loads(json.dumps(VALID))
    doc["teams"][0]["players"][0]["org"] = "SFG"
    assert rosters.parse(doc)[0].players[0].org == "SF"


@pytest.mark.parametrize("mutate,message", [
    (lambda d: d.update(schema=99), "schema"),
    (lambda d: d.update(teams=[]), "non-empty"),
    (lambda d: d["teams"][0].update(name=""), "no name"),
    (lambda d: d["teams"][0]["players"][0].update(person_id="829045"), "integer"),
    (lambda d: d["teams"][0]["players"][0].update(org="XYZ"), "unknown org"),
])
def test_malformed_documents_raise(mutate, message):
    # A bad browser write must fail the Action loudly, not silently drop players.
    doc = json.loads(json.dumps(VALID))
    mutate(doc)
    with pytest.raises(RosterError, match=message):
        rosters.parse(doc)


def test_duplicate_player_on_one_team_rejected():
    doc = json.loads(json.dumps(VALID))
    doc["teams"][0]["players"].append(doc["teams"][0]["players"][0])
    with pytest.raises(RosterError, match="twice"):
        rosters.parse(doc)


def test_roundtrip(tmp_path):
    path = tmp_path / "rosters.json"
    rosters.save(rosters.parse(VALID), path)
    again = rosters.load(path)
    assert again[0].name == "Zebras"
    assert again[0].players[0].person_id == 829045


def test_save_skips_write_when_only_the_timestamp_would_change(tmp_path):
    """to_document() stamps a fresh updated_at, so an unconditional write
    dirties rosters.json every ingest and yields an empty daily commit."""
    path = tmp_path / "rosters.json"
    teams = rosters.parse(VALID)
    assert rosters.save(teams, path) is True
    before = path.read_text()

    assert rosters.save(teams, path) is False      # nothing changed
    assert path.read_text() == before

    teams[0].players[1].person_id = 12345          # a real change
    assert rosters.save(teams, path) is True
    assert path.read_text() != before
