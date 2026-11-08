from datetime import datetime, timezone


def get_utc_time():
    return datetime.now(timezone.utc).strftime("%H:%M UTC")


def get_utc_date():
    return datetime.now(timezone.utc).strftime("%d %b %Y")


def get_utc_datetime():
    return datetime.now(timezone.utc).strftime("%d %b %Y %H:%M UTC")


# ---------------------------------------------------------------- time helpers
def parse_hhmm(value):
    """'HH:MM' or 'HHMM' -> minutes since midnight (0-1439), or None if invalid."""
    if not value:
        return None
    v = str(value).strip().upper().replace("Z", "").replace(":", "")
    if not v.isdigit() or len(v) not in (3, 4):
        return None
    v = v.zfill(4)
    h, m = int(v[:2]), int(v[2:])
    if h > 23 or m > 59:
        return None
    return h * 60 + m


def now_minutes():
    """Current UTC time as minutes since midnight."""
    n = datetime.now(timezone.utc)
    return n.hour * 60 + n.minute


def minutes_until(hhmm, now=None):
    """Signed minutes from now until HH:MM (UTC), wrapped to [-720, +720).
    Positive = in the future, negative = already past. None if invalid."""
    t = parse_hhmm(hhmm)
    if t is None:
        return None
    now = now_minutes() if now is None else now
    return (t - now + 720) % 1440 - 720
