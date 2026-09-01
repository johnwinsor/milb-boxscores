"""One-shot seeding from the legacy milb_cache.json, so the first run of the
new pipeline starts with the game logs the old script already fetched."""

import json
from pathlib import Path

from . import db
from .ingest import _now, split_to_row


def from_json_cache(path: str | Path, db_path=None) -> int:
    doc = json.loads(Path(path).read_text())
    conn = db.connect(db_path)
    db.init(conn)
    fetched_at = _now()
    total = 0
    for key, entry in (doc.get("game_log") or {}).items():
        try:
            person_id, group, season = key.split("|")
            person_id, season = int(person_id), int(season)
        except ValueError:
            continue
        conn.execute("INSERT OR IGNORE INTO player (person_id) VALUES (?)", (person_id,))
        rows = [r for r in (split_to_row(s, person_id, group, season, fetched_at)
                            for s in (entry.get("value") or [])) if r]
        total += db.upsert_game_logs(conn, rows)
    conn.commit()
    conn.close()
    return total
