from datetime import date

import pytest

from milb.config import canonical_org, org_team_id
from milb.util import (ip_to_outs, is_pitcher, normalize, outs_to_ip, slugify,
                       within_window)


@pytest.mark.parametrize("ip,outs", [
    ("0.0", 0), ("1.0", 3), ("5.1", 16), ("5.2", 17), ("6.0", 18), ("100.2", 302),
])
def test_ip_outs_roundtrip(ip, outs):
    # The fractional part of an IP string is OUTS, not a decimal: 5.1 is 5 innings
    # plus one out (16), not 5.33 innings.
    assert ip_to_outs(ip) == outs
    assert outs_to_ip(outs) == ip


def test_ip_to_outs_tolerates_junk():
    assert ip_to_outs(None) == 0
    assert ip_to_outs("") == 0
    assert ip_to_outs(5) == 15


@pytest.mark.parametrize("pos,expected", [
    ("SP", True), ("RP", True), ("P", True), ("CP", True), ("SP/RP", True),
    ("OF", False), ("SS", False), ("SS/OF", False), ("1B/OF", False),
    ("2B/SS", False), ("SS/3B", False), ("C", False), ("", False),
])
def test_is_pitcher(pos, expected):
    assert is_pitcher(pos) is expected


def test_normalize_strips_accents():
    assert normalize("Yórger Bautista") == "yorger bautista"
    assert normalize("Elian Peña") == "elian pena"
    assert normalize("  MIXED Case  ") == "mixed case"


def test_slugify():
    assert slugify("Ghost Ride the WHIP") == "ghost-ride-the-whip"
    assert slugify("Seneca Falls Mafia") == "seneca-falls-mafia"


def test_within_window_is_inclusive_and_clamped():
    today = date(2026, 8, 31)
    assert within_window("2026-08-31", 7, today)      # today
    assert within_window("2026-08-24", 7, today)      # exactly the cutoff
    assert not within_window("2026-08-23", 7, today)  # one day too old
    # The original had no upper bound, so scheduled future games passed.
    assert not within_window("2026-09-01", 7, today)


def test_org_aliases_fold_to_one_club():
    # Rosters were hand-typed over years and drifted.
    assert canonical_org("SFG") == canonical_org("SF") == "SF"
    assert canonical_org("KCR") == canonical_org("KC") == "KC"
    assert canonical_org("TBR") == canonical_org("TB") == "TB"
    assert canonical_org("WAS") == "WSH"
    assert org_team_id("SFG") == org_team_id("SF") == 137


def test_unknown_org_passes_through_visibly():
    assert canonical_org("zzz") == "ZZZ"
    assert org_team_id("ZZZ") is None
