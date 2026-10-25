from datetime import UTC, datetime
from zoneinfo import ZoneInfo

EAT = ZoneInfo("Africa/Nairobi")

# Pinned "now": Monday 2026-11-02 08:00 Nairobi time.
FIXED_NOW = datetime(2026, 11, 2, 5, 0, tzinfo=UTC)

MON, TUE, WED, SAT = "2026-11-02", "2026-11-03", "2026-11-04", "2026-11-07"


def at(day: str, hhmm: str) -> datetime:
    """Aware datetime in clinic time, e.g. at(TUE, '09:00')."""
    y, m, d = (int(x) for x in day.split("-"))
    h, mi = (int(x) for x in hhmm.split(":"))
    return datetime(y, m, d, h, mi, tzinfo=EAT)


def iso(dt: datetime) -> str:
    return dt.isoformat()
