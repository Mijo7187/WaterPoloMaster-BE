from datetime import datetime


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


