"""Static configuration: API endpoints, sport/level mappings, org abbreviations."""

from pathlib import Path

BASE = "https://statsapi.mlb.com/api/v1"
USER_AGENT = "milb-boxscores/0.2 (+https://github.com/johnwinsor/milb-boxscores)"

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
DB_PATH = DATA_DIR / "milb.sqlite"
ROSTERS_PATH = DATA_DIR / "rosters.json"
OVERRIDES_PATH = DATA_DIR / "overrides.json"
WEB_API_DIR = REPO_ROOT / "web" / "public" / "api"

# sportId -> (abbreviation, display name). Covers MLB plus the full minor-league
# and complex ladder. The ingest sweeps every one of these per player: a player
# who changed levels mid-season (callup, demotion, rehab) has real games at more
# than one level, and stopping at the first non-empty sportId strands them.
SPORTS = {
    1:    ("MLB", "Major League Baseball"),
    11:   ("AAA", "Triple-A"),
    12:   ("AA",  "Double-A"),
    13:   ("A+",  "High-A"),
    14:   ("A",   "Single-A"),
    16:   ("CPX", "Rookie / Complex"),
    5442: ("DSL", "Dominican Summer League"),
}
SPORT_IDS = list(SPORTS)

# Ordered worst -> best, for detecting promotions vs demotions on player pages.
LEVEL_ORDER = ["DSL", "CPX", "A", "A+", "AA", "AAA", "MLB"]

PITCHER_POS_TOKENS = {"SP", "RP", "P", "CP"}

# Canonical org abbreviation -> (MLB team id, full club name).
#
# The old code disambiguated same-name players with
# `org.lower() in currentTeam.name.lower()`, which compares "sfg" against
# "San Francisco Giants" and is therefore False almost every time. That silent
# no-op is why a pile of manual personId overrides had to exist. Matching on
# team id instead actually works.
ORGS = {
    "ARI": (109, "Arizona Diamondbacks"),
    "ATH": (133, "Athletics"),
    "ATL": (144, "Atlanta Braves"),
    "BAL": (110, "Baltimore Orioles"),
    "BOS": (111, "Boston Red Sox"),
    "CHC": (112, "Chicago Cubs"),
    "CHW": (145, "Chicago White Sox"),
    "CIN": (113, "Cincinnati Reds"),
    "CLE": (114, "Cleveland Guardians"),
    "COL": (115, "Colorado Rockies"),
    "DET": (116, "Detroit Tigers"),
    "HOU": (117, "Houston Astros"),
    "KC":  (118, "Kansas City Royals"),
    "LAA": (108, "Los Angeles Angels"),
    "LAD": (119, "Los Angeles Dodgers"),
    "MIA": (146, "Miami Marlins"),
    "MIL": (158, "Milwaukee Brewers"),
    "MIN": (142, "Minnesota Twins"),
    "NYM": (121, "New York Mets"),
    "NYY": (147, "New York Yankees"),
    "PHI": (143, "Philadelphia Phillies"),
    "PIT": (134, "Pittsburgh Pirates"),
    "SD":  (135, "San Diego Padres"),
    "SEA": (136, "Seattle Mariners"),
    "SF":  (137, "San Francisco Giants"),
    "STL": (138, "St. Louis Cardinals"),
    "TB":  (139, "Tampa Bay Rays"),
    "TEX": (140, "Texas Rangers"),
    "TOR": (141, "Toronto Blue Jays"),
    "WSH": (120, "Washington Nationals"),
}

# The rosters were hand-typed over time and drifted: SF/SFG, KC/KCR, TB/TBR,
# WAS/WSH all appear. Normalize on load so one club is one key.
ORG_ALIASES = {
    "SFG": "SF", "KCR": "KC", "TBR": "TB", "WAS": "WSH", "WSN": "WSH",
    "CWS": "CHW", "OAK": "ATH", "LA": "LAD", "NY": "NYY", "SDP": "SD",
    "ANA": "LAA", "FLA": "MIA", "TBD": "TB", "CHA": "CHW", "CHN": "CHC",
}


def canonical_org(org: str) -> str:
    """Fold a roster's org abbreviation to the canonical one. Unknown values
    pass through uppercased so a typo is visible rather than silently dropped."""
    if not org:
        return ""
    key = org.strip().upper()
    return ORG_ALIASES.get(key, key)


def org_team_id(org: str) -> int | None:
    entry = ORGS.get(canonical_org(org))
    return entry[0] if entry else None
