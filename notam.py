"""
NOTAM Management Module
Store NOTAMs, classify them (category + priority) and find which runways they close.
"""

import re
from datetime import datetime, timezone

from config import ICAO
from database import get_connection
from logs import add_log
from utc_time import get_utc_datetime

DT_FORMAT = "%Y-%m-%d %H:%M"          # all times are UTC

# Order matters: equipment (ILS, PAPI...) is tested BEFORE "RWY",
# so "ILS RWY 05 U/S" is a NAVAID notice and does not close the runway.
CATEGORIES = [
    ("NAVAID",   r"\b(ILS|VOR|DME|NDB|LOC|LOCALIZER|GP|GS|GLIDE ?PATH|NAVAID|TACAN)\b"),
    ("LIGHTING", r"\b(LGT|LGTS|LIGHT|LIGHTS|LIGHTING|PAPI|ALS|VASI|REIL|HIAL)\b"),
    ("OBSTACLE", r"\b(CRANE|OBST|OBSTACLE|OBSTRUCTION)\b"),
    ("RUNWAY",   r"\b(RWY|RUNWAY)\b"),
    ("TAXIWAY",  r"\b(TWY|TAXIWAY)\b"),
    ("AIRSPACE", r"\b(AIRSPACE|TSA|RESTRICTED|DANGER AREA|PROHIBITED)\b"),
    ("APRON",    r"\b(APRON|STAND|GATE)\b"),
]
CLOSED_WORDS = ("CLSD", "CLOSED", "U/S", "UNSERVICEABLE", "NOT AVBL", "NOT AVAILABLE", "OUT OF SERVICE")
RUNWAY_NAMES = ("05", "23", "09", "27")
PRIORITY_ORDER = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}


def classify(text):
    """Return (category, priority) from the NOTAM text."""
    t = f" {text.upper()} "
    category = "OTHER"
    for name, pattern in CATEGORIES:
        if re.search(pattern, t):
            category = name
            break
    closed = any(w in t for w in CLOSED_WORDS)
    whole_airport = any(w in t for w in ("AD CLSD", "AERODROME CLSD", "AIRPORT CLOSED", "AD CLOSED"))
    if whole_airport or (category == "RUNWAY" and closed):
        priority = "HIGH"
    elif closed or category in ("NAVAID", "LIGHTING", "AIRSPACE", "OBSTACLE"):
        priority = "MEDIUM"
    else:
        priority = "LOW"
    return category, priority


def affected_runways(text):
    """Runway designators mentioned in a NOTAM text (e.g. 'RWY 05/23 CLSD' -> 05, 23)."""
    t = text.upper()
    return [r for r in RUNWAY_NAMES if re.search(rf"(?<!\d){r}(?!\d)", t)]


def parse_dt(value):
    if not value:
        return None
    value = value.strip().upper()
    if value in ("PERM", "UFN"):
        return None
    for fmt in (DT_FORMAT, "%Y-%m-%d %H%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    raise ValueError("Use format YYYY-MM-DD HH:MM (UTC) or PERM")


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def effective_status(row_status, valid_from, valid_to):
    """CANCELLED stays; otherwise computed from the validity period."""
    if row_status == "CANCELLED":
        return "CANCELLED"
    now = _now()
    try:
        vf, vt = parse_dt(valid_from), parse_dt(valid_to)
    except ValueError:
        return row_status or "ACTIVE"
    if vf and now < vf:
        return "SCHEDULED"
    if vt and now > vt:
        return "EXPIRED"
    return "ACTIVE"


def add_notam(notam_id, text, valid_from="", valid_to="", username="system"):
    """Create a NOTAM. Returns (ok, message)."""
    notam_id, text = notam_id.strip().upper(), text.strip()
    if not notam_id or not text:
        return False, "NOTAM number and text are required."
    try:
        vf, vt = parse_dt(valid_from), parse_dt(valid_to)
    except ValueError as e:
        return False, str(e)
    if vf and vt and vt < vf:
        return False, "End of validity is before its start."
    category, priority = classify(text)
    conn = get_connection()
    try:
        conn.execute("""INSERT INTO notams (notam_id, category, priority, text, valid_from, valid_to,
                        status, created_utc, created_by) VALUES (?,?,?,?,?,?, 'ACTIVE', ?, ?)""",
                     (notam_id, category, priority, text,
                      vf.strftime(DT_FORMAT) if vf else "", vt.strftime(DT_FORMAT) if vt else "PERM",
                      get_utc_datetime(), username))
        conn.commit()
    except Exception as e:      # sqlite3.IntegrityError for duplicates
        conn.close()
        return False, "NOTAM already exists." if "UNIQUE" in str(e) else str(e)
    conn.close()
    add_log(get_utc_datetime(), username, "NOTAM ADDED", f"{notam_id} [{category}/{priority}]")
    return True, f"{notam_id} added ({category}, {priority})."


def list_notams(active_only=False):
    """Rows: dict list sorted by priority then validity."""
    conn = get_connection()
    try:
        rows = conn.execute("""SELECT id, notam_id, category, priority, text, valid_from, valid_to, status,
                               COALESCE(source, 'MANUAL'), COALESCE(location, '')
                               FROM notams""").fetchall()
    finally:
        conn.close()
    out = []
    for r in rows:
        st = effective_status(r[7], r[5], r[6])
        if active_only and st != "ACTIVE":
            continue
        out.append({"id": r[0], "notam_id": r[1], "category": r[2], "priority": r[3], "text": r[4],
                    "valid_from": r[5], "valid_to": r[6], "status": st,
                    "source": r[8], "location": r[9]})
    out.sort(key=lambda n: (PRIORITY_ORDER.get(n["priority"], 3), n["notam_id"]))
    return out


def active_notams():
    return list_notams(active_only=True)


def closed_runways():
    """Runways closed by an active runway NOTAM."""
    closed = set()
    for n in active_notams():
        if n.get("location") not in ("", None, ICAO):      # FIR / other-aerodrome NOTAMs never close our runways
            continue
        if n["category"] == "RUNWAY" and any(w in n["text"].upper() for w in CLOSED_WORDS):
            closed.update(affected_runways(n["text"]))
    return closed


def cancel_notam(notam_id, username="system"):
    conn = get_connection()
    try:
        cur = conn.execute("UPDATE notams SET status='CANCELLED' WHERE notam_id=?", (notam_id.upper(),))
        conn.commit()
        done = cur.rowcount > 0
    finally:
        conn.close()
    if done:
        add_log(get_utc_datetime(), username, "NOTAM CANCELLED", notam_id.upper())
    return done


def delete_notam(notam_id, username="system"):
    conn = get_connection()
    try:
        cur = conn.execute("DELETE FROM notams WHERE notam_id=?", (notam_id.upper(),))
        conn.commit()
        done = cur.rowcount > 0
    finally:
        conn.close()
    if done:
        add_log(get_utc_datetime(), username, "NOTAM DELETED", notam_id.upper())
    return done


# ------------------------------------------------------------------ console
def show_notams():
    rows = list_notams()
    print("\n" + "=" * 70)
    print("          NOTAM")
    print("=" * 70)
    if not rows:
        print("  No NOTAM.")
        return
    for n in rows:
        print(f"  {n['notam_id']:<10} {n['priority']:<7} {n['category']:<9} {n['status']}")
        print(f"      {n['text']}")
        print(f"      Valid: {n['valid_from'] or '-'}  ->  {n['valid_to'] or 'PERM'}")
        print("-" * 70)


def add_notam_cli(user=None):
    nid = input(" NOTAM no. (e.g. A0123/26) : ").strip()
    text = input(" Text (e.g. RWY 09/27 CLSD DUE WIP) : ").strip()
    vf = input(" Valid from (YYYY-MM-DD HH:MM UTC, empty = now) : ").strip()
    vt = input(" Valid to   (YYYY-MM-DD HH:MM UTC or PERM)    : ").strip() or "PERM"
    ok, msg = add_notam(nid, text, vf, vt, user["username"] if user else "system")
    print(("\n ✓ " if ok else "\n ✗ ") + msg)
