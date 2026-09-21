import enum
from datetime import datetime, date


class QuarterType(str, enum.Enum):
    Q1 = "Q1"
    Q2 = "Q2"
    Q3 = "Q3"
    Q4 = "Q4"


def quarter_type_for_date(d: date) -> QuarterType:
    """Map a calendar date to its quarter: Jan-Mar=Q1, Apr-Jun=Q2, Jul-Sep=Q3, Oct-Dec=Q4."""
    return {
        1: QuarterType.Q1, 2: QuarterType.Q1, 3: QuarterType.Q1,
        4: QuarterType.Q2, 5: QuarterType.Q2, 6: QuarterType.Q2,
        7: QuarterType.Q3, 8: QuarterType.Q3, 9: QuarterType.Q3,
        10: QuarterType.Q4, 11: QuarterType.Q4, 12: QuarterType.Q4,
    }[d.month]


def club_today() -> date:
    """Today's date in the clubs' timezone (settings.CLUB_TIMEZONE), not UTC."""
    from zoneinfo import ZoneInfo

    from app.core.config import settings

    return datetime.now(ZoneInfo(settings.CLUB_TIMEZONE)).date()


def parse_date(v):
    """Parse a date from a datetime string like '2093-06-18T22:00:00.000Z' or a plain date string like '2093-06-18'."""
    if isinstance(v, str) and "T" in v:
        return datetime.fromisoformat(v.replace("Z", "+00:00")).date()
    return v


def parse_datetime(v):
    """Parse a datetime from an ISO string like '2093-06-18T22:00:00.000Z'."""
    if isinstance(v, str):
        return datetime.fromisoformat(v.replace("Z", "+00:00"))
    return v


