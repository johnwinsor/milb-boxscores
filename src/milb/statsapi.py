"""Thin client for the public MLB Stats API (no auth required)."""

import itertools
import sys
import threading
import time

import requests

from .config import BASE, USER_AGENT


class StatsAPI:
    """Session wrapper with retry/backoff and a request counter.

    Thread-safe for concurrent GETs: requests.Session is safe for this usage,
    and the counter is guarded.
    """

    def __init__(self, timeout: int = 20, retries: int = 3, debug: bool = False):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})
        adapter = requests.adapters.HTTPAdapter(pool_connections=16, pool_maxsize=16)
        self.session.mount("https://", adapter)
        self.timeout, self.retries, self.debug = timeout, retries, debug
        self._lock = threading.Lock()
        self.requests_made = 0

    def _log(self, msg: str) -> None:
        if self.debug:
            print(f"[debug] {msg}", file=sys.stderr)

    def get(self, path: str, params: dict | None = None) -> dict:
        """GET with retry on transient errors, exponential backoff (1s, 2s, 4s)."""
        url = f"{BASE}{path}"
        last_exc = None
        for attempt in range(1, self.retries + 1):
            try:
                with self._lock:
                    self.requests_made += 1
                resp = self.session.get(url, params=params, timeout=self.timeout)
                resp.raise_for_status()
                return resp.json()
            except requests.RequestException as e:
                last_exc = e
                self._log(f"attempt {attempt}/{self.retries} failed {url} {params}: {e}")
                if attempt < self.retries:
                    time.sleep(2 ** (attempt - 1))
        raise last_exc

    # -- endpoints ---------------------------------------------------------

    def search_people(self, query: str) -> list[dict]:
        data = self.get("/people/search", {"names": query, "hydrate": "currentTeam"})
        return data.get("people", [])

    def get_person(self, person_id: int) -> dict | None:
        data = self.get(f"/people/{person_id}", {"hydrate": "currentTeam"})
        people = data.get("people", [])
        return people[0] if people else None

    def get_people(self, person_ids) -> list[dict]:
        """Batch person lookup -- the endpoint accepts a comma-separated id list,
        so 100 players cost 1-2 requests instead of 100."""
        ids = [str(i) for i in person_ids if i]
        out = []
        for chunk in _chunks(ids, 100):
            data = self.get("/people", {"personIds": ",".join(chunk), "hydrate": "currentTeam"})
            out.extend(data.get("people", []))
        return out

    def game_log(self, person_id: int, group: str, season: int, sport_id: int) -> list[dict]:
        data = self.get(
            f"/people/{person_id}/stats",
            {"stats": "gameLog", "group": group, "season": season, "sportId": sport_id},
        )
        splits = []
        for block in data.get("stats", []):
            splits.extend(block.get("splits", []))
        return splits


def _chunks(seq, n):
    it = iter(seq)
    while chunk := list(itertools.islice(it, n)):
        yield chunk
