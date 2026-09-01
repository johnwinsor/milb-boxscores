"""Pure helpers with no I/O. Everything here is directly unit-testable."""

import re
import unicodedata
from datetime import date, datetime, timedelta

from .config import PITCHER_POS_TOKENS


def normalize(s: str) -> str:
    """Lowercase and strip accents so 'Yorger' matches 'Yorger'."""
    nfkd = unicodedata.normalize("NFKD", s or "")
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower().strip()


def slugify(s: str) -> str:
    """'Ghost Ride the WHIP' -> 'ghost-ride-the-whip'. Used for team URLs."""
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", normalize(s))).strip("-")


def is_pitcher(pos_str: str) -> bool:
    """Positions may be slash-separated ('SP/RP', 'SS/OF'); any pitching token wins."""
    return any(t.strip().upper() in PITCHER_POS_TOKENS for t in (pos_str or "").split("/"))


def ip_to_outs(ip_value) -> int:
    """'5.1' (5 innings + 1 out) -> 16. The fractional part is OUTS, not decimal."""
    whole, _, frac = str(ip_value if ip_value is not None else "0.0").partition(".")
    return (int(whole) if whole.strip("-").isdigit() else 0) * 3 + (int(frac) if frac.isdigit() else 0)


def outs_to_ip(outs: int) -> str:
    """Inverse of ip_to_outs: 16 -> '5.1'."""
    outs = int(outs or 0)
    return f"{outs // 3}.{outs % 3}"


def parse_date(date_str: str) -> date:
    return datetime.strptime(date_str, "%Y-%m-%d").date()


def window_bounds(days: int, today: date | None = None) -> tuple[date, date]:
    """Inclusive [start, end] for a 'last N days' window.

    The old within_window() had no upper bound, so scheduled future games passed
    the filter. Clamping to today fixes that.
    """
    today = today or datetime.now().date()
    return today - timedelta(days=days), today


def within_window(date_str: str, days: int, today: date | None = None) -> bool:
    start, end = window_bounds(days, today)
    return start <= parse_date(date_str) <= end
