"""The Admin page mirrors rosters.py's rules so a bad edit is caught before it
becomes a failed workflow run. These pin the server-side half of that contract:
if a rule changes here, web/src/lib/roster.ts must change with it."""

import json

import pytest

from milb import rosters
from milb.config import ORGS
from milb.rosters import RosterError

BASE = {"schema": 1, "teams": [{"name": "Zebras", "slug": "zebras", "players": [
    {"name": "Real Player", "org": "SEA", "level": "AA", "pos": "OF",
     "person_id": 829045, "notes": ""}]}]}


def _with_player(**overrides):
    doc = json.loads(json.dumps(BASE))
    doc["teams"][0]["players"][0].update(overrides)
    return doc


@pytest.mark.parametrize("overrides,fragment", [
    ({"name": ""}, "no name"),
    ({"name": "   "}, "no name"),
    ({"org": "XYZ"}, "unknown org"),
    ({"person_id": "829045"}, "integer"),
])
def test_server_rejects_what_the_client_blocks(overrides, fragment):
    with pytest.raises(RosterError, match=fragment):
        rosters.parse(_with_player(**overrides))


def test_empty_team_name_rejected():
    doc = json.loads(json.dumps(BASE))
    doc["teams"][0]["name"] = ""
    with pytest.raises(RosterError, match="no name"):
        rosters.parse(doc)


def test_blank_position_is_accepted_but_means_hitter():
    """The client blocks this even though the server allows it: a blank pos
    silently routes the player to hitting game logs, so a pitcher gets none."""
    teams = rosters.parse(_with_player(pos=""))
    assert teams[0].players[0].group == "hitting"


def test_client_org_list_matches_the_server():
    """web/src/lib/roster.ts hardcodes the org list for its dropdown; drift
    would let the UI offer an org the Action then rejects."""
    from pathlib import Path
    import re

    src = Path("web/src/lib/roster.ts").read_text()
    block = re.search(r"export const ORGS = \[(.*?)\]", src, re.S).group(1)
    client = set(re.findall(r"'([A-Z]+)'", block))
    assert client == set(ORGS), (
        f"client-only: {sorted(client - set(ORGS))}, server-only: {sorted(set(ORGS) - client)}")


def test_client_pitcher_tokens_match_the_server():
    from pathlib import Path
    import re

    from milb.config import PITCHER_POS_TOKENS

    src = Path("web/src/lib/roster.ts").read_text()
    block = re.search(r"export const PITCHER_TOKENS = \[(.*?)\]", src, re.S).group(1)
    assert set(re.findall(r"'([A-Z]+)'", block)) == PITCHER_POS_TOKENS
