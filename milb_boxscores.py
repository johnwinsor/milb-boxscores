#!/usr/bin/env python3
"""
milb_boxscores.py

Pulls daily box-score lines for a fixed list of players (MLB + all minor
league levels) over the last N days, using the public MLB Stats API
(statsapi.mlb.com) -- the same unauthenticated API that backs MLB.com and
MiLB.com. No API key required.

Usage:
    python milb_boxscores.py 7
    python milb_boxscores.py --days 3 --season 2026
    python milb_boxscores.py 7 --format csv --out lines.csv
    python milb_boxscores.py 7 --format json --out lines.json
    python milb_boxscores.py 7 --no-cache        # ignore/skip the local cache
    python milb_boxscores.py 7 --clear-cache     # wipe the cache file first

Output format (text mode):
    HITTERS:  PA AB H R RBI 2B HR SB CS BB K
    PITCHERS: IP H R ER BB K HR

Caching:
    A local JSON file (default: milb_cache.json, next to this script) stores
    two things so repeated runs don't hammer the API:
      - name/org -> personId lookups (TTL: 30 days, these barely change)
      - personId/group/season -> raw game log splits (TTL: 1 hour, so a
        same-day re-run or a run with a different --days value reuses data
        instead of re-fetching the whole season's game log)
"""

import argparse
import csv
import json
import os
import sys
import time
import unicodedata
from datetime import datetime, timedelta

import requests

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text
    from rich import box as rich_box
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

BASE = "https://statsapi.mlb.com/api/v1"

# sportId values covering MLB + the full minor-league / complex ladder.
# 1=MLB, 11=AAA, 12=AA, 13=High-A, 14=Single-A, 16=Rookie (ACL/FCL),
# 5442=Dominican Summer League
SPORT_IDS = [1, 11, 12, 13, 14, 16, 5442]

FANTASY_TEAMS = {
    "Zebras": [
        {"name": "Yorger Bautista",   "org": "SEA", "level": "CPX",  "pos": "OF"},
        {"name": "Eduardo Quintero",  "org": "LAD", "level": "A+",   "pos": "OF"},
        {"name": "Jonny Farmelo",     "org": "SEA", "level": "AA",   "pos": "OF"},
        {"name": "Tanner McDougal",   "org": "CHW", "level": "AAA",  "pos": "SP/RP"},
        {"name": "Rainiel Rodriguez", "org": "STL", "level": "AA",   "pos": "C"},
        {"name": "Mike Sirota",       "org": "LAD", "level": "AA",   "pos": "OF"},
        {"name": "Jamie Arnold",      "org": "ATH", "level": "AA",   "pos": "SP"},
        {"name": "Steele Hall",       "org": "CIN", "level": "CPX",  "pos": "SS"},
        {"name": "Tyler Bremner",     "org": "LAA", "level": "A+",   "pos": "SP"},
        {"name": "Luis Pena",         "org": "MIL", "level": "A+",   "pos": "2B/SS"},
        {"name": "Owen Murphy",       "org": "ATL", "level": "AAA",  "pos": "SP"},
        {"name": "Devin Taylor",      "org": "ATH", "level": "AA",   "pos": "OF"},
        {"name": "Nathan Flewelling", "org": "TBR", "level": "A+",   "pos": "C"}
    ],

    # Level ("TBD" below) is cosmetic only -- get_game_log() scans every
    # MiLB/MLB level regardless of this field, so it doesn't affect data
    # pulling, only the header text. Org/pos here were cross-referenced from
    # draft-history tabs (most recent draft appearance per player, since org
    # can change via trades); fill in real levels later if you want nicer
    # display text.

    "Ghost Ride the WHIP": [
        {"name": "Kane Kepley",      "org": "CHC", "level": "TBD", "pos": "OF"},
        {"name": "Kevin Defrank",    "org": "MIA", "level": "TBD", "pos": "P"},
        {"name": "Jefferson Rojas",  "org": "CHC", "level": "TBD", "pos": "SS"},
        {"name": "Jace LaViolette",  "org": "CLE", "level": "TBD", "pos": "OF"},
        {"name": "Billy Carlson",    "org": "CHW", "level": "TBD", "pos": "SS"},
        {"name": "Xavier Neyens",    "org": "HOU", "level": "TBD", "pos": "3B"},
        {"name": "Ralphy Velazquez", "org": "CLE", "level": "TBD", "pos": "1B"},
        {"name": "Aiva Arquette",    "org": "MIA", "level": "TBD", "pos": "SS"},
        {"name": "Jaxon Wiggins",    "org": "CHC", "level": "TBD", "pos": "P"},
    ],

    "DC Outlaws": [
        {"name": "Aidan Miller",              "org": "PHI", "level": "TBD", "pos": "3B"},
        {"name": "Lazaro Montes",             "org": "SEA", "level": "TBD", "pos": "OF"},
        {"name": "George Lombard Jr.",         "org": "NYY", "level": "TBD", "pos": "SS"},
        {"name": "Ryan Sloan",                "org": "SEA", "level": "TBD", "pos": "P"},
        {"name": "Josuar De Jesus Gonzalez",  "org": "SFG", "level": "TBD", "pos": "SS"},
        {"name": "Theo Gillen",               "org": "TBR", "level": "TBD", "pos": "OF"},
        {"name": "JoJo Parker",               "org": "TOR", "level": "TBD", "pos": "SS"},
        {"name": "Brody Hopkins",             "org": "TBR", "level": "TBD", "pos": "P"},
        {"name": "Tyson Lewis",               "org": "CIN", "level": "TBD", "pos": "SS"},
        {"name": "Francisco Renteria",        "org": "PHI", "level": "TBD", "pos": "OF"},
        {"name": "Kevin Alvarez",             "org": "HOU", "level": "TBD", "pos": "OF"},
    ],

    "BaseVOLS": [
        {"name": "Marcus Phillips",   "org": "BOS", "level": "TBD", "pos": "P"},
        {"name": "Drew Beam",         "org": "KCR", "level": "TBD", "pos": "P"},
        {"name": "Drue Hackenberg",   "org": "ATL", "level": "TBD", "pos": "P"},
        {"name": "Quinn Mathews",     "org": "STL", "level": "TBD", "pos": "P"},
        {"name": "Ricky Tiedemann",   "org": "TOR", "level": "TBD", "pos": "P"},
        {"name": "James Tibbs III",   "org": "SF",  "level": "TBD", "pos": "OF"},
        {"name": "Seaver King",       "org": "WAS", "level": "TBD", "pos": "SS/OF"},
        {"name": "Cam Caminiti",      "org": "ATL", "level": "TBD", "pos": "P"},
        {"name": "Kendry Rojas",      "org": "MIN", "level": "TBD", "pos": "P"},
        {"name": "Carlos LaGrange",   "org": "NYY", "level": "TBD", "pos": "P"},
    ],

    "Luck Dragons": [
        {"name": "Braylon Payne",      "org": "MIL", "level": "TBD", "pos": "OF"},
        {"name": "Ethan Conrad",       "org": "CHC", "level": "TBD", "pos": "OF"},
        {"name": "Emmanuel Rodriguez", "org": "MIN", "level": "TBD", "pos": "OF"},
        {"name": "Emil Morales",       "org": "LAD", "level": "TBD", "pos": "SS"},
        {"name": "Josue Briceno",      "org": "DET", "level": "TBD", "pos": "1B"},
        {"name": "Alfredo Duno",       "org": "CIN", "level": "TBD", "pos": "C"},
        {"name": "Sebastian Walcott",  "org": "TEX", "level": "TBD", "pos": "SS"},
        {"name": "Thomas White",       "org": "MIA", "level": "TBD", "pos": "P"},
        {"name": "Luis Hernandez",     "org": "SFG", "level": "TBD", "pos": "SS"},
        {"name": "Caden Scarborough",  "org": "TEX", "level": "TBD", "pos": "P"},
        {"name": "Jarlin Susana",      "org": "WAS", "level": "TBD", "pos": "P"},
    ],

    "LawDog": [
        {"name": "Gavin Kilen",         "org": "SFG", "level": "TBD", "pos": "SS"},
        {"name": "Bryce Rainer",        "org": "DET", "level": "TBD", "pos": "SS"},
        {"name": "Arjun Nimmala",       "org": "TOR", "level": "TBD", "pos": "SS"},
        {"name": "Moises Chace",        "org": "PHI", "level": "TBD", "pos": "P"},
        {"name": "Jeferson Quero",      "org": "MIL", "level": "TBD", "pos": "C"},
        {"name": "Michael Arroyo",      "org": "SEA", "level": "TBD", "pos": "2B"},
        {"name": "Jurrangelo Cijntje",  "org": "STL", "level": "TBD", "pos": "P"},
        {"name": "Angel Genao",         "org": "CLE", "level": "TBD", "pos": "SS"},
        {"name": "Ike Irish",           "org": "BAL", "level": "TBD", "pos": "1B/OF"},
        {"name": "Ching-Hsien Ko",      "org": "LAD", "level": "TBD", "pos": "OF"},
    ],

    "Samsung Lions": [
        {"name": "Aidan Smith",      "org": "TBR", "level": "TBD", "pos": "OF"},
        {"name": "George Klassen",   "org": "LAA", "level": "TBD", "pos": "P"},
        {"name": "Luis de Leon",     "org": "BAL", "level": "TBD", "pos": "P"},
        {"name": "Luis Perales",     "org": "WAS", "level": "TBD", "pos": "P"},
        {"name": "Elmer Rodriguez",  "org": "NYY", "level": "TBD", "pos": "P"},
        {"name": "Bo Davidson",      "org": "SFG", "level": "TBD", "pos": "OF"},
    ],

    "Truffle Muts": [
        {"name": "Jacob Reimer",       "org": "NYM", "level": "TBD", "pos": "3B"},
        {"name": "Elian Pena",         "org": "NYM", "level": "TBD", "pos": "SS"},
        {"name": "Josue De Paula",     "org": "LAD", "level": "TBD", "pos": "OF"},
        {"name": "Wandy Asigen",       "org": "NYM", "level": "TBD", "pos": "SS"},
        {"name": "Demetrio Crisantes", "org": "ARI", "level": "TBD", "pos": "2B"},
    ],

    "High N Tight": [
        {"name": "Jhostynxon Garcia", "org": "BOS", "level": "TBD", "pos": "OF"},
        {"name": "Jonathon Long",     "org": "CHC", "level": "TBD", "pos": "1B"},
        {"name": "Jett Williams",     "org": "NYM", "level": "TBD", "pos": "SS"},
        {"name": "Franklin Arias",    "org": "BOS", "level": "TBD", "pos": "SS"},
        {"name": "Andrew Fischer",    "org": "MIL", "level": "TBD", "pos": "1B"},
    ],

    "Austin Waves": [
        {"name": "Ty Johnson",      "org": "TBR", "level": "TBD", "pos": "P"},
        {"name": "Jhonny Level",    "org": "SFG", "level": "TBD", "pos": "SS"},
        {"name": "Robby Snelling",  "org": "SD",  "level": "TBD", "pos": "P"},
        {"name": "Aroon Escobar",   "org": "PHI", "level": "TBD", "pos": "2B"},
        {"name": "Caleb Bonemer",   "org": "CHW", "level": "TBD", "pos": "SS/3B"},
        {"name": "Cam Collier",     "org": "CIN", "level": "TBD", "pos": "3B"},
        {"name": "Zyhir Hope",      "org": "LAD", "level": "TBD", "pos": "OF"},
        {"name": "Ryan Clifford",   "org": "NYM", "level": "TBD", "pos": "1B/OF"},
    ],

    "Seneca Falls Mafia": [
        {"name": "Ethan Salas",       "org": "SD",  "level": "TBD", "pos": "C"},
        {"name": "Blake Mitchell",    "org": "KC",  "level": "TBD", "pos": "C"},
        {"name": "Brayden Taylor",    "org": "TB",  "level": "TBD", "pos": "3B"},
        {"name": "Brock Wilken",      "org": "MIL", "level": "TBD", "pos": "3B"},
        {"name": "Tommy Troy",        "org": "ARI", "level": "TBD", "pos": "SS"},
        {"name": "Jaison Chourio",    "org": "CLE", "level": "TBD", "pos": "OF"},
        {"name": "Nate George",       "org": "BAL", "level": "TBD", "pos": "OF"},
        {"name": "Kendry Chourio",    "org": "KCR", "level": "TBD", "pos": "P"},
        {"name": "Felnin Celesten",   "org": "SEA", "level": "TBD", "pos": "SS"},
    ],

    "Yazoo Yetis": [
        {"name": "Travis Sykora",    "org": "WAS", "level": "TBD", "pos": "P"},
        {"name": "Khal Stephen",     "org": "CLE", "level": "TBD", "pos": "P"},
        {"name": "Trey Gibson",      "org": "BAL", "level": "TBD", "pos": "P"},
        {"name": "Zachary Root",     "org": "LAD", "level": "TBD", "pos": "P"},
        {"name": "Jack Wenninger",   "org": "NYM", "level": "TBD", "pos": "P"},
    ],
    # Add more league rosters here, e.g.:
    # "Rival Squad": [
    #     {"name": "Some Prospect", "org": "TEX", "level": "AA", "pos": "SS"},
    # ],
}


def _build_players():
    """Flatten FANTASY_TEAMS into the list the rest of the script works with,
    tagging each entry with which fantasy roster it belongs to."""
    players = []
    for team_name, roster in FANTASY_TEAMS.items():
        for p in roster:
            entry = dict(p)
            entry["fantasy_team"] = team_name
            players.append(entry)
    return players


PLAYERS = _build_players()

# Manual overrides: if a player can't be found (or the wrong same-name person
# gets matched), look them up with --lookup "Name" to find the right
# personId, then hardcode it here to skip the search step entirely.
# Keyed by "Name|MLB Org" -- NOT affected by which fantasy team they're on,
# since the same real player has the same personId no matter whose roster
# you've got them tagged under.
# e.g. "Luis Pena|MIL": 123456
PERSON_ID_OVERRIDES = {
    "Luis Pena|MIL": 821270,        # confirmed via mlb.com search (434524 was a retired unrelated Luis Pena)
    "Yorger Bautista|SEA": 829045,  # confirmed via mlb.com search (not returned by the people/search endpoint)
    "Hyeseong Kim|LAD": 808975,     # confirmed via mlb.com search
    "Luis Gil|NYY": 661563,         # confirmed via mlb.com search

    # League-wide rollout batch -- confirmed via web search (thebaseballcube.com /
    # milb.com player pages showing MLBAM ID). Several of these fail search
    # because the player's MLB-registered name differs from their common name.
    "Kevin Defrank|MIA": 829074,               # registered as "Kevin DeFrank"
    "Xavier Neyens|HOU": 815832,
    "Aiva Arquette|MIA": 804109,                # full legal name "Aiva John Uakea Arquette"
    "Aidan Miller|PHI": 805795,                 # was matching a game-log-empty namesake
    "JoJo Parker|TOR": 828098,                  # registered as "Joseph Parker"
    "Josuar De Jesus Gonzalez|SFG": 829034,     # registered as just "Josuar Gonzalez"
}

PITCHER_POS_TOKENS = {"SP", "RP", "P", "CP"}


def normalize(s):
    """Lowercase and strip accents so 'Yórger' matches 'yorger'."""
    nfkd = unicodedata.normalize("NFKD", s)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower().strip()

PERSON_ID_TTL = 60 * 60 * 24 * 30   # 30 days
GAME_LOG_TTL = 60 * 60              # 1 hour

CSV_FIELDS = [
    "fantasy_team", "date", "player", "org", "level", "pos", "type", "team", "opponent",
    "PA", "AB", "H", "R", "RBI", "2B", "HR", "SB", "CS", "BB", "K",
    "IP", "ER", "is_total",
]


# --------------------------------------------------------------------------
# Cache
# --------------------------------------------------------------------------

class Cache:
    """Simple TTL-based JSON file cache for person-id lookups and game logs."""

    def __init__(self, path, enabled=True):
        self.path = path
        self.enabled = enabled
        self.data = {"person_id": {}, "game_log": {}}
        if self.enabled and os.path.exists(self.path):
            try:
                with open(self.path, "r") as f:
                    loaded = json.load(f)
                self.data["person_id"] = loaded.get("person_id", {})
                self.data["game_log"] = loaded.get("game_log", {})
            except (json.JSONDecodeError, OSError):
                pass  # corrupt/unreadable cache -> start fresh

    def _get(self, bucket, key, ttl):
        if not self.enabled:
            return None
        entry = self.data.get(bucket, {}).get(key)
        if entry is None:
            return None
        if time.time() - entry.get("_ts", 0) > ttl:
            return None
        return entry.get("value")

    def _set(self, bucket, key, value):
        if not self.enabled:
            return
        self.data.setdefault(bucket, {})[key] = {"_ts": time.time(), "value": value}

    def get_person_id(self, key):
        return self._get("person_id", key, PERSON_ID_TTL)

    def set_person_id(self, key, value):
        self._set("person_id", key, value)

    def get_game_log(self, key):
        return self._get("game_log", key, GAME_LOG_TTL)

    def set_game_log(self, key, value):
        self._set("game_log", key, value)

    def save(self):
        if not self.enabled:
            return
        try:
            with open(self.path, "w") as f:
                json.dump(self.data, f)
        except OSError as e:
            print(f"warning: could not write cache file ({e})", file=sys.stderr)


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def is_pitcher(pos_str):
    tokens = pos_str.split("/")
    return any(t.strip().upper() in PITCHER_POS_TOKENS for t in tokens)


def _get_with_retry(session, url, params=None, timeout=20, retries=3, debug=False):
    """
    GET with retry-on-timeout/transient-error, exponential backoff
    (1s, 2s, 4s...). Raises the last exception if all attempts fail.
    """
    last_exc = None
    for attempt in range(1, retries + 1):
        try:
            resp = session.get(url, params=params, timeout=timeout)
            resp.raise_for_status()
            return resp
        except requests.RequestException as e:
            last_exc = e
            if debug:
                print(f"[debug] request attempt {attempt}/{retries} failed for {url} "
                      f"params={params}: {e}", file=sys.stderr)
            if attempt < retries:
                time.sleep(2 ** (attempt - 1))
    raise last_exc


def _search_people(query, session, debug=False):
    url = f"{BASE}/people/search"
    resp = _get_with_retry(session, url, params={"names": query, "hydrate": "currentTeam"}, debug=debug)
    return resp.json().get("people", [])


def _get_person(person_id, session, debug=False):
    """Fetch a single person's full record (name, position, current team, etc)."""
    url = f"{BASE}/people/{person_id}"
    resp = _get_with_retry(session, url, params={"hydrate": "currentTeam"}, debug=debug)
    people = resp.json().get("people", [])
    return people[0] if people else None


def find_person_id(name, org, session, cache, debug=False):
    """
    Search the Stats API for a person by name, with org-based disambiguation.
    Falls back to a surname-only search (with accent normalization) if the
    full-name search comes back empty -- this catches cases where the API's
    stored name differs slightly (accents, suffixes, nicknames).
    """
    override_key = f"{name}|{org}"
    if override_key in PERSON_ID_OVERRIDES:
        if debug:
            print(f"[debug] {name}: using override personId={PERSON_ID_OVERRIDES[override_key]}", file=sys.stderr)
        return PERSON_ID_OVERRIDES[override_key]

    cache_key = f"{name}|{org}"
    cached = cache.get_person_id(cache_key)
    if cached is not None:
        if debug:
            print(f"[debug] {name}: personId={cached} (from cache)", file=sys.stderr)
        return cached

    people = _search_people(name, session, debug=debug)

    if not people:
        # Fallback: search by surname only, then filter by normalized
        # full-name containment. Catches accent/spelling mismatches.
        surname = name.strip().split()[-1]
        people = _search_people(surname, session, debug=debug)
        target_norm = normalize(name)
        people = [
            p for p in people
            if all(tok in normalize(p.get("fullName", "")) for tok in target_norm.split())
        ]

    if debug:
        listing = ", ".join(
            f"{p.get('fullName')} (id={p['id']}, team={(p.get('currentTeam') or {}).get('name', '?')})"
            for p in people
        ) or "none"
        print(f"[debug] {name}: candidates -> {listing}", file=sys.stderr)

    if not people:
        cache.set_person_id(cache_key, None)
        return None

    exact = [p for p in people if normalize(p.get("fullName", "")) == normalize(name)]
    candidates = exact or people

    person_id = None
    if len(candidates) == 1:
        person_id = candidates[0]["id"]
    else:
        for p in candidates:
            team_name = (p.get("currentTeam") or {}).get("name", "")
            if org.lower() in team_name.lower():
                person_id = p["id"]
                break
        if person_id is None:
            person_id = candidates[0]["id"]

    if debug:
        print(f"[debug] {name}: chose personId={person_id}", file=sys.stderr)

    cache.set_person_id(cache_key, person_id)
    return person_id


def get_game_log(person_id, group, season, session, cache, debug=False):
    """
    Pull game logs from EVERY relevant sportId and merge them, deduped by
    game date -- a player who changed levels mid-season (call-up, demotion,
    rehab assignment) will have real games at more than one level, and
    stopping at the first non-empty sportId would silently strand them on
    whichever level happens to be checked first (see: Kim/Gil, who show
    early-season MLB games but are actually active in the minors right now).
    Cached per (person_id, group, season) for GAME_LOG_TTL seconds.
    """
    cache_key = f"{person_id}|{group}|{season}"
    cached = cache.get_game_log(cache_key)
    if cached is not None:
        if debug:
            print(f"[debug] personId={person_id}: game log from cache ({len(cached)} games)", file=sys.stderr)
        return cached

    merged = {}  # date -> split, last sportId checked wins on a same-date collision
    for sport_id in SPORT_IDS:
        url = f"{BASE}/people/{person_id}/stats"
        params = {
            "stats": "gameLog",
            "group": group,
            "season": season,
            "sportId": sport_id,
        }
        try:
            resp = _get_with_retry(session, url, params=params, debug=debug)
        except requests.RequestException as e:
            if debug:
                print(f"[debug] personId={person_id}: sportId={sport_id} gave up after retries ({e})", file=sys.stderr)
            continue
        found = 0
        for block in resp.json().get("stats", []):
            for split in block.get("splits", []):
                key = split.get("date") or split.get("game", {}).get("gamePk")
                if key is not None:
                    merged[key] = split
                    found += 1
        if debug:
            print(f"[debug] personId={person_id}: sportId={sport_id} -> {found} games", file=sys.stderr)

    splits = list(merged.values())
    cache.set_game_log(cache_key, splits)
    return splits


def within_window(date_str, days):
    game_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    cutoff = datetime.now().date() - timedelta(days=days)
    return game_date >= cutoff


def build_hitting_record(player, stat, date_str, opponent, team):
    return {
        "date": date_str, "player": player["name"], "org": player["org"],
        "level": player["level"], "pos": player["pos"], "type": "hitting",
        "fantasy_team": player.get("fantasy_team", ""),
        "team": team, "opponent": opponent, "is_total": False,
        "PA": stat.get("plateAppearances", 0), "AB": stat.get("atBats", 0),
        "H": stat.get("hits", 0), "R": stat.get("runs", 0),
        "RBI": stat.get("rbi", 0), "2B": stat.get("doubles", 0),
        "HR": stat.get("homeRuns", 0), "SB": stat.get("stolenBases", 0),
        "CS": stat.get("caughtStealing", 0), "BB": stat.get("baseOnBalls", 0),
        "K": stat.get("strikeOuts", 0),
    }


def build_pitching_record(player, stat, date_str, opponent, team):
    return {
        "date": date_str, "player": player["name"], "org": player["org"],
        "level": player["level"], "pos": player["pos"], "type": "pitching",
        "fantasy_team": player.get("fantasy_team", ""),
        "team": team, "opponent": opponent, "is_total": False,
        "IP": stat.get("inningsPitched", "0.0"), "H": stat.get("hits", 0),
        "R": stat.get("runs", 0), "ER": stat.get("earnedRuns", 0),
        "BB": stat.get("baseOnBalls", 0), "K": stat.get("strikeOuts", 0),
        "HR": stat.get("homeRuns", 0),
    }


def ip_to_outs(ip_value):
    """Convert an innings-pitched string like '5.1' (5 innings + 1 out) to a
    total-outs int. The fractional part is outs (0, 1, or 2), NOT decimal."""
    s = str(ip_value)
    whole, _, frac = s.partition(".")
    whole = int(whole) if whole else 0
    frac = int(frac) if frac else 0
    return whole * 3 + frac


def outs_to_ip(outs):
    """Inverse of ip_to_outs: total outs -> '5.1'-style IP string."""
    return f"{outs // 3}.{outs % 3}"


def build_hitting_totals(player, records):
    return {
        "date": "TOTAL", "player": player["name"], "org": player["org"],
        "level": player["level"], "pos": player["pos"], "type": "hitting",
        "fantasy_team": player.get("fantasy_team", ""),
        "team": "", "opponent": "", "is_total": True,
        "PA": sum(r["PA"] for r in records), "AB": sum(r["AB"] for r in records),
        "H": sum(r["H"] for r in records), "R": sum(r["R"] for r in records),
        "RBI": sum(r["RBI"] for r in records), "2B": sum(r["2B"] for r in records),
        "HR": sum(r["HR"] for r in records), "SB": sum(r["SB"] for r in records),
        "CS": sum(r["CS"] for r in records), "BB": sum(r["BB"] for r in records),
        "K": sum(r["K"] for r in records),
    }


def build_pitching_totals(player, records):
    total_outs = sum(ip_to_outs(r["IP"]) for r in records)
    return {
        "date": "TOTAL", "player": player["name"], "org": player["org"],
        "level": player["level"], "pos": player["pos"], "type": "pitching",
        "fantasy_team": player.get("fantasy_team", ""),
        "team": "", "opponent": "", "is_total": True,
        "IP": outs_to_ip(total_outs), "H": sum(r["H"] for r in records),
        "R": sum(r["R"] for r in records), "ER": sum(r["ER"] for r in records),
        "BB": sum(r["BB"] for r in records), "K": sum(r["K"] for r in records),
        "HR": sum(r["HR"] for r in records),
    }


def format_hitting_line(rec):
    if rec.get("is_total"):
        prefix = "TOTAL"
    else:
        prefix = f"{rec['date']}  {rec['team']} vs {rec['opponent']}:"
    return (f"{prefix} "
            f"{rec['PA']} PA {rec['AB']} AB {rec['H']} H {rec['R']} R "
            f"{rec['RBI']} RBI {rec['2B']} 2B {rec['HR']} HR {rec['SB']} SB "
            f"{rec['CS']} CS {rec['BB']} BB {rec['K']} K")


def format_pitching_line(rec):
    if rec.get("is_total"):
        prefix = "TOTAL"
    else:
        prefix = f"{rec['date']}  {rec['team']} vs {rec['opponent']}:"
    return (f"{prefix} "
            f"{rec['IP']} IP {rec['H']} H {rec['R']} R {rec['ER']} ER "
            f"{rec['BB']} BB {rec['K']} K {rec['HR']} HR")


def process_player(player, days, season, session, cache, debug=False):
    """Returns (records, error_message_or_None)."""
    pitcher = is_pitcher(player["pos"])
    group = "pitching" if pitcher else "hitting"

    person_id = find_person_id(player["name"], player["org"], session, cache, debug=debug)
    if person_id is None:
        return [], "could not find player on MLB Stats API"

    splits = get_game_log(person_id, group, season, session, cache, debug=debug)
    if not splits:
        return [], f"no {group} game log found for {season}"

    records = []
    for split in sorted(splits, key=lambda s: s.get("date", "")):
        date_str = split.get("date")
        if not date_str or not within_window(date_str, days):
            continue
        stat = split.get("stat", {})
        team = split.get("team", {}).get("name", player["org"])
        opponent = split.get("opponent", {}).get("name", "?")
        if pitcher:
            records.append(build_pitching_record(player, stat, date_str, opponent, team))
        else:
            records.append(build_hitting_record(player, stat, date_str, opponent, team))

    if len(records) > 1:
        totals = build_pitching_totals(player, records) if pitcher else build_hitting_totals(player, records)
        records.append(totals)

    return records, None


# --------------------------------------------------------------------------
# Output
# --------------------------------------------------------------------------

HITTER_COLUMNS = ["Date", "Team", "Opp", "PA", "AB", "H", "R", "RBI", "2B", "HR", "SB", "CS", "BB", "K"]
PITCHER_COLUMNS = ["Date", "Team", "Opp", "IP", "H", "R", "ER", "BB", "K", "HR"]


def _stat_cell(col, value, rec, pitcher):
    """Return a rich-styled string for one stat cell, highlighting standout lines."""
    text = str(value)
    if col == "HR" and isinstance(value, int) and value > 0:
        return f"[bold green]{text}[/bold green]"
    if col == "H" and not pitcher and isinstance(value, int) and value >= 3:
        return f"[bold green]{text}[/bold green]"
    if col == "K" and pitcher and isinstance(value, int) and value >= 8:
        return f"[bold cyan]{text}[/bold cyan]"
    if col == "ER" and pitcher and rec.get("IP") not in (None, "0.0") and isinstance(value, int) and value == 0:
        return f"[bold green]{text}[/bold green]"
    if col == "SB" and not pitcher and isinstance(value, int) and value > 0:
        return f"[cyan]{text}[/cyan]"
    return text


def write_rich(all_records, errors, days, season, plain_console=False, players=None):
    from rich.rule import Rule

    players = players if players is not None else PLAYERS
    console = Console(no_color=plain_console, width=None)
    if not console.is_terminal:
        console.width = max(console.width, 100)
    console.print(f"\n[bold]Box scores for the last {days} day(s), season {season}[/bold]\n")

    by_player = {}
    for rec in all_records:
        key = (rec.get("fantasy_team", ""), rec["player"])
        by_player.setdefault(key, []).append(rec)

    current_team = object()  # sentinel guarantees the first heading always prints
    for player in players:
        fantasy_team = player.get("fantasy_team", "")
        if fantasy_team != current_team:
            console.print(Rule(f"[bold]{fantasy_team}[/bold]", style="bright_black"))
            current_team = fantasy_team

        name = player["name"]
        key = (fantasy_team, name)
        pitcher = is_pitcher(player["pos"])
        border_color = "red" if pitcher else "blue"
        title = f"{name}  ·  {player['org']} {player['level']} {player['pos']}"

        if key in errors:
            console.print(Panel(f"[dim]{errors[key]}[/dim]", title=title, title_align="left",
                                 border_style="yellow", box=rich_box.ROUNDED))
            continue

        if key not in by_player:
            console.print(Panel(f"[dim]no games played in the last {days} day(s)[/dim]", title=title,
                                 title_align="left", border_style="dim", box=rich_box.ROUNDED))
            continue

        columns = PITCHER_COLUMNS if pitcher else HITTER_COLUMNS
        table = Table(box=rich_box.SIMPLE_HEAVY, show_edge=False, header_style="bold")
        for col in columns:
            justify = "left" if col in ("Date", "Team", "Opp") else "right"
            table.add_column(col, justify=justify, no_wrap=True, overflow="ellipsis")

        for rec in by_player[key]:
            if rec.get("is_total"):
                table.add_section()
                row = ["[bold]TOTAL[/bold]", "", ""]
                for col in columns[3:]:
                    row.append(f"[bold]{rec.get(col, '')}[/bold]")
                table.add_row(*row)
                continue

            row = [rec["date"], rec["team"], rec["opponent"]]
            for col in columns[3:]:
                row.append(_stat_cell(col, rec.get(col, ""), rec, pitcher))
            table.add_row(*row)

        console.print(Panel(table, title=title, title_align="left", border_style=border_color,
                             box=rich_box.ROUNDED, padding=(0, 1)))

    console.print()


def write_text(all_records, errors, days, season, out, players=None):
    players = players if players is not None else PLAYERS
    stream = out or sys.stdout
    print(f"Box scores for the last {days} day(s), season {season}\n", file=stream)
    by_player = {}
    for rec in all_records:
        key = (rec.get("fantasy_team", ""), rec["player"])
        by_player.setdefault(key, []).append(rec)

    current_team = object()  # sentinel guarantees the first heading always prints
    for player in players:
        fantasy_team = player.get("fantasy_team", "")
        if fantasy_team != current_team:
            print(f"=== {fantasy_team} ===\n", file=stream)
            current_team = fantasy_team

        name = player["name"]
        key = (fantasy_team, name)
        header = f"{name} ({player['org']} {player['level']} {player['pos']}):"
        print(header, file=stream)
        if key in errors:
            print(f"  {errors[key]}", file=stream)
        elif key not in by_player:
            print(f"  no games played in the last {days} day(s)", file=stream)
        else:
            for rec in by_player[key]:
                if rec.get("is_total"):
                    print(file=stream)
                line = format_pitching_line(rec) if rec["type"] == "pitching" else format_hitting_line(rec)
                print(f"  {line}", file=stream)
        print(file=stream)


def write_csv(all_records, path):
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for rec in all_records:
            writer.writerow(rec)


def write_json(all_records, path):
    with open(path, "w") as f:
        json.dump(all_records, f, indent=2)


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Scrape daily box-score lines for a fixed list of prospects."
    )
    parser.add_argument(
        "days", type=int, nargs="?", default=7,
        help="number of days to look back (default: 7)",
    )
    parser.add_argument(
        "--season", type=int, default=datetime.now().year,
        help="season year to query (default: current year)",
    )
    parser.add_argument(
        "--format", choices=["text", "csv", "json"], default="text",
        help="output format (default: text)",
    )
    parser.add_argument(
        "--out", default=None,
        help="output file path (required for csv/json; optional for text, "
             "defaults to stdout)",
    )
    parser.add_argument(
        "--cache-file", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "milb_cache.json"),
        help="path to the local cache file (default: milb_cache.json next to the script)",
    )
    parser.add_argument(
        "--no-cache", action="store_true",
        help="disable reading/writing the cache for this run",
    )
    parser.add_argument(
        "--clear-cache", action="store_true",
        help="delete the cache file before running",
    )
    parser.add_argument(
        "--debug", action="store_true",
        help="print search/game-log diagnostics to stderr (candidates found, "
             "sportIds tried, etc.) -- use this to troubleshoot a missing player",
    )
    parser.add_argument(
        "--lookup", default=None, metavar="NAME",
        help="skip the report entirely; just print raw search results for "
             "NAME (id, full name, current team) so you can find the right "
             "personId to hardcode in PERSON_ID_OVERRIDES",
    )
    parser.add_argument(
        "--lookup-id", default=None, type=int, metavar="PERSON_ID",
        help="skip the report entirely; print the full person record for "
             "this personId (name, position, current team) -- use this to "
             "confirm a cached/matched id is actually the right player",
    )
    parser.add_argument(
        "--plain", action="store_true",
        help="disable Rich colorized tables even if Rich is installed; "
             "falls back to the original plain-text output",
    )
    parser.add_argument(
        "--team", default=None, metavar="TEAM",
        help="only run the report for one fantasy roster from FANTASY_TEAMS "
             "(case-insensitive), e.g. --team Zebras",
    )
    args = parser.parse_args()

    if args.lookup_id:
        session = requests.Session()
        session.headers.update({"User-Agent": "prospect-boxscore-script/1.0"})
        person = _get_person(args.lookup_id, session)
        if not person:
            print(f"No person found for id={args.lookup_id}")
            return
        team = (person.get("currentTeam") or {}).get("name", "?")
        pos = (person.get("primaryPosition") or {}).get("abbreviation", "?")
        print(f"id={person['id']}")
        print(f"fullName={person.get('fullName', '?')}")
        print(f"currentTeam={team}")
        print(f"primaryPosition={pos}")
        print(f"birthDate={person.get('birthDate', '?')}")
        print(f"active={person.get('active', '?')}")
        return

    if args.lookup:
        session = requests.Session()
        session.headers.update({"User-Agent": "prospect-boxscore-script/1.0"})
        people = _search_people(args.lookup, session)
        if not people:
            print(f"No matches for '{args.lookup}'")
            return
        for p in people:
            team = (p.get("currentTeam") or {}).get("name", "?")
            print(f"id={p['id']:<8} fullName={p.get('fullName', '?'):<25} currentTeam={team}")
        return

    if args.clear_cache and os.path.exists(args.cache_file):
        os.remove(args.cache_file)
        print(f"Cleared cache file: {args.cache_file}", file=sys.stderr)

    if args.format in ("csv", "json") and not args.out:
        parser.error(f"--out is required when --format={args.format}")

    players = PLAYERS
    if args.team:
        players = [p for p in PLAYERS if p.get("fantasy_team", "").lower() == args.team.lower()]
        if not players:
            known = ", ".join(sorted(FANTASY_TEAMS.keys()))
            parser.error(f"no players found for team '{args.team}'. Known teams: {known}")

    cache = Cache(args.cache_file, enabled=not args.no_cache)
    session = requests.Session()
    session.headers.update({"User-Agent": "prospect-boxscore-script/1.0"})

    all_records = []
    errors = {}

    for player in players:
        error_key = (player.get("fantasy_team", ""), player["name"])
        try:
            records, err = process_player(player, args.days, args.season, session, cache, debug=args.debug)
            if err:
                errors[error_key] = err
            all_records.extend(records)
        except Exception as e:
            errors[error_key] = f"error - {e}"
        time.sleep(0.1 if cache.enabled else 0.25)  # cache hits skip the actual request anyway

    cache.save()

    if args.format == "text":
        if args.out:
            # Writing to a file: always plain text, never ANSI codes.
            with open(args.out, "w") as f:
                write_text(all_records, errors, args.days, args.season, f, players=players)
        elif RICH_AVAILABLE and not args.plain:
            write_rich(all_records, errors, args.days, args.season, players=players)
        else:
            if not RICH_AVAILABLE and not args.plain:
                print("(tip: run 'uv add rich' for colorized table output)\n", file=sys.stderr)
            write_text(all_records, errors, args.days, args.season, None, players=players)
    elif args.format == "csv":
        write_csv(all_records, args.out)
        print(f"Wrote {len(all_records)} rows to {args.out}", file=sys.stderr)
    elif args.format == "json":
        write_json(all_records, args.out)
        print(f"Wrote {len(all_records)} records to {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
