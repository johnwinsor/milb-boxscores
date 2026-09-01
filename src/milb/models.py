"""Typed records passed between pipeline stages."""

from dataclasses import dataclass, field


@dataclass
class RosterEntry:
    """One player on one fantasy team, as authored in data/rosters.json."""
    fantasy_team: str
    name: str
    org: str = ""
    level: str = "TBD"
    pos: str = ""
    person_id: int | None = None
    notes: str = ""
    resolution_status: str = "pending"  # override | roster | search | unresolved

    @property
    def group(self) -> str:
        from .util import is_pitcher
        return "pitching" if is_pitcher(self.pos) else "hitting"

    @property
    def key(self) -> tuple[str, str]:
        return (self.fantasy_team, self.name)


@dataclass
class FantasyTeam:
    name: str
    slug: str
    players: list[RosterEntry] = field(default_factory=list)


@dataclass
class GameLogRow:
    """One player-game. Mirrors the game_log table."""
    person_id: int
    game_pk: int
    group_type: str
    date: str
    season: int
    sport_id: int | None = None
    sport_abbr: str | None = None
    league_id: int | None = None
    league_name: str | None = None
    team_id: int | None = None
    team_name: str | None = None
    opponent_id: int | None = None
    opponent_name: str | None = None
    is_home: int | None = None
    is_win: int | None = None
    game_type: str | None = None
    summary: str | None = None
    # hitting
    pa: int = 0; ab: int = 0; h: int = 0; r: int = 0; rbi: int = 0
    doubles: int = 0; triples: int = 0; hr: int = 0
    sb: int = 0; cs: int = 0; bb: int = 0; k: int = 0
    hbp: int = 0; tb: int = 0; sac_flies: int = 0
    # pitching (IP stored as outs; render with outs_to_ip)
    outs: int = 0; er: int = 0; pitches: int = 0
    raw_stat: str = "{}"
    fetched_at: str = ""
