"""Load and save data/rosters.json -- the human-authored source of truth.

Rosters live in git, not in SQLite, because the web app's save path is a commit
through the GitHub Contents API. That gives versioning, audit, and rollback for
free, and keeps SQLite single-writer.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from .config import ORGS, OVERRIDES_PATH, ROSTERS_PATH, canonical_org
from .models import FantasyTeam, RosterEntry
from .util import slugify

SCHEMA = 1


class RosterError(ValueError):
    """Raised on a malformed rosters.json, so a bad browser write fails the
    Action loudly instead of silently dropping players."""


def load(path: Path | str | None = None) -> list[FantasyTeam]:
    path = Path(path or ROSTERS_PATH)
    if not path.exists():
        raise RosterError(f"no roster file at {path}")
    try:
        doc = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        raise RosterError(f"{path} is not valid JSON: {e}") from e
    return parse(doc)


def parse(doc: dict) -> list[FantasyTeam]:
    if not isinstance(doc, dict):
        raise RosterError("roster document must be a JSON object")
    if doc.get("schema") != SCHEMA:
        raise RosterError(f"unsupported roster schema {doc.get('schema')!r}, expected {SCHEMA}")
    teams_raw = doc.get("teams")
    if not isinstance(teams_raw, list) or not teams_raw:
        raise RosterError("roster document must contain a non-empty 'teams' array")

    teams, seen_slugs = [], set()
    for i, t in enumerate(teams_raw):
        name = (t.get("name") or "").strip()
        if not name:
            raise RosterError(f"teams[{i}] has no name")
        slug = (t.get("slug") or slugify(name)).strip()
        if slug in seen_slugs:
            raise RosterError(f"duplicate team slug {slug!r}")
        seen_slugs.add(slug)

        players, seen_names = [], set()
        for j, p in enumerate(t.get("players") or []):
            pname = (p.get("name") or "").strip()
            if not pname:
                raise RosterError(f"teams[{i}].players[{j}] has no name")
            if pname in seen_names:
                raise RosterError(f"{name!r} lists {pname!r} twice")
            seen_names.add(pname)

            pid = p.get("person_id")
            if pid is not None and not isinstance(pid, int):
                raise RosterError(f"{pname}: person_id must be an integer, got {pid!r}")

            org = canonical_org(p.get("org", ""))
            if org and org not in ORGS:
                raise RosterError(f"{pname}: unknown org {p.get('org')!r}")

            players.append(RosterEntry(
                fantasy_team=name, name=pname, org=org,
                level=(p.get("level") or "TBD").strip(),
                pos=(p.get("pos") or "").strip(),
                person_id=pid, notes=p.get("notes", "") or "",
                resolution_status="roster" if pid else "pending",
            ))
        teams.append(FantasyTeam(name=name, slug=slug, players=players))
    return teams


def to_document(teams: list[FantasyTeam]) -> dict:
    return {
        "schema": SCHEMA,
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "teams": [
            {
                "name": t.name,
                "slug": t.slug,
                "players": [
                    {"name": p.name, "org": p.org, "level": p.level, "pos": p.pos,
                     "person_id": p.person_id, "notes": p.notes}
                    for p in t.players
                ],
            }
            for t in teams
        ],
    }


def save(teams: list[FantasyTeam], path: Path | str | None = None) -> Path:
    path = Path(path or ROSTERS_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(to_document(teams), indent=2) + "\n")
    return path


def flatten(teams: list[FantasyTeam]) -> list[RosterEntry]:
    return [p for t in teams for p in t.players]


def load_overrides(path: Path | str | None = None) -> dict[tuple[str, str], int]:
    """data/overrides.json -- manual 'Name|ORG' -> personId pins, for players the
    name search cannot resolve (registered under a different legal name, etc)."""
    path = Path(path or OVERRIDES_PATH)
    if not path.exists():
        return {}
    doc = json.loads(path.read_text())
    return {
        (e["name"], canonical_org(e["org"])): int(e["person_id"])
        for e in doc.get("overrides", [])
    }
