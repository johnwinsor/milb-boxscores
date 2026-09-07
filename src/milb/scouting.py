"""Load and save data/scouting.json -- hand-written scouting grades and notes.

Human-authored, so it lives in git and is written through the same GitHub
Contents API path as rosters.json. It deliberately stays out of SQLite: that
database is owned by the ingest process and rebuilt from the API, and scouting
opinion is neither.

Keyed by MLBAM person_id rather than roster name, so a report follows the real
player across fantasy trades, name spellings, and roster churn.

Grades use the standard 20-80 scale, where 50 is major-league average and each
10 points is a standard deviation. Tools carry an optional present grade
alongside the future one -- the "45/55" a real report would show -- because for
a prospect the gap between the two is most of the information.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from .config import DATA_DIR

SCHEMA = 1
SCOUTING_PATH = DATA_DIR / "scouting.json"

# Tool sets by role. Abbreviations match how reports are conventionally written.
HITTER_TOOLS = {
    "hit": "Hit",
    "game_power": "Game Power",
    "raw_power": "Raw Power",
    "speed": "Run",
    "field": "Field",
    "arm": "Arm",
}
PITCHER_TOOLS = {
    "fastball": "Fastball",
    "slider": "Slider",
    "curveball": "Curveball",
    "changeup": "Changeup",
    "command": "Command",
}
ALL_TOOLS = {**HITTER_TOOLS, **PITCHER_TOOLS}

RISK_LEVELS = ["low", "medium", "high", "extreme"]

GRADE_MIN, GRADE_MAX = 20, 80


class ScoutingError(ValueError):
    """Raised on a malformed scouting.json, so a bad browser write fails the
    Action loudly instead of silently dropping reports."""


def tools_for(group: str) -> dict[str, str]:
    return PITCHER_TOOLS if group == "pitching" else HITTER_TOOLS


def _grade(value, label: str):
    """A tool grade: null, a bare number, or {present, future}."""
    if value is None:
        return None
    if isinstance(value, dict):
        out = {}
        for key in ("present", "future"):
            if value.get(key) is not None:
                out[key] = _check_scale(value[key], f"{label}.{key}")
        return out or None
    return {"future": _check_scale(value, label)}


def _check_scale(value, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ScoutingError(f"{label}: grade must be a number, got {value!r}")
    value = int(value)
    if not GRADE_MIN <= value <= GRADE_MAX:
        raise ScoutingError(f"{label}: grade {value} is outside the 20-80 scale")
    return value


def parse(doc: dict) -> dict[int, dict]:
    if not isinstance(doc, dict):
        raise ScoutingError("scouting document must be a JSON object")
    if doc.get("schema") != SCHEMA:
        raise ScoutingError(f"unsupported scouting schema {doc.get('schema')!r}, expected {SCHEMA}")

    players = doc.get("players")
    if players is None:
        return {}
    if not isinstance(players, dict):
        raise ScoutingError("'players' must be an object keyed by person_id")

    out: dict[int, dict] = {}
    for key, entry in players.items():
        try:
            person_id = int(key)
        except (TypeError, ValueError):
            raise ScoutingError(f"player key {key!r} is not a person_id") from None
        if not isinstance(entry, dict):
            raise ScoutingError(f"{person_id}: report must be an object")

        grades = {}
        for tool, value in (entry.get("grades") or {}).items():
            if tool not in ALL_TOOLS:
                raise ScoutingError(f"{person_id}: unknown tool {tool!r}")
            graded = _grade(value, f"{person_id}.{tool}")
            if graded:
                grades[tool] = graded

        fv = entry.get("fv")
        if fv is not None:
            fv = _check_scale(fv, f"{person_id}.fv")

        risk = entry.get("risk")
        if risk is not None and risk not in RISK_LEVELS:
            raise ScoutingError(
                f"{person_id}: risk must be one of {', '.join(RISK_LEVELS)}, got {risk!r}")

        eta = entry.get("eta")
        if eta is not None:
            if not isinstance(eta, int) or not 1900 < eta < 2200:
                raise ScoutingError(f"{person_id}: eta must be a 4-digit year, got {eta!r}")

        notes = []
        for i, note in enumerate(entry.get("notes") or []):
            if not isinstance(note, dict) or not note.get("text"):
                raise ScoutingError(f"{person_id}: notes[{i}] needs a 'text' field")
            notes.append({
                "date": note.get("date") or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "text": str(note["text"]),
            })
        notes.sort(key=lambda n: n["date"], reverse=True)

        report = {"grades": grades, "fv": fv, "risk": risk, "eta": eta, "notes": notes,
                  "updated_at": entry.get("updated_at")}
        if any((grades, fv, risk, eta, notes)):
            out[person_id] = report
    return out


def load(path: Path | str | None = None) -> dict[int, dict]:
    path = Path(path or SCOUTING_PATH)
    if not path.exists():
        return {}
    try:
        doc = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        raise ScoutingError(f"{path} is not valid JSON: {e}") from e
    return parse(doc)


def to_document(reports: dict[int, dict]) -> dict:
    return {
        "schema": SCHEMA,
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "players": {str(pid): reports[pid] for pid in sorted(reports)},
    }


def save(reports: dict[int, dict], path: Path | str | None = None) -> bool:
    """Write only when a report actually changed, so the daily commit stays
    meaningful -- same reasoning as rosters.save()."""
    path = Path(path or SCOUTING_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = to_document(reports)
    if path.exists():
        try:
            if json.loads(path.read_text()).get("players") == doc["players"]:
                return False
        except json.JSONDecodeError:
            pass
    path.write_text(json.dumps(doc, indent=2) + "\n")
    return True
