"""
ATFCM Module  (Air Traffic Flow & Capacity Management)
CTOT = Calculated Take-Off Time. A flight with a CTOT must take off inside the
slot window [CTOT - 5 min, CTOT + 10 min].
"""

from config import (CTOT_TOLERANCE_BEFORE, CTOT_TOLERANCE_AFTER, CTOT_WARNING_MIN)
from database import get_connection
from logs import add_log
from utc_time import get_utc_datetime, parse_hhmm, minutes_until

DEPARTED = ("TAKEOFF", "AIRBORNE", "ARRIVING", "LANDED", "PARKED", "CANCELLED")


def ctot_state(minutes_to_ctot, flight_status=""):
    """PENDING / APPROACHING / IN WINDOW / MISSED / DEPARTED."""
    if flight_status in DEPARTED:
        return "DEPARTED"
    m = minutes_to_ctot
    if m is None:
        return "PENDING"
    if m > CTOT_WARNING_MIN:
        return "PENDING"
    if m > CTOT_TOLERANCE_BEFORE:
        return "APPROACHING"
    if m >= -CTOT_TOLERANCE_AFTER:
        return "IN WINDOW"
    return "MISSED"


def set_ctot(flight_number, ctot, regulation="", reason="", username="system"):
    """Create or update the CTOT of a flight. Returns (ok, message)."""
    fn = flight_number.strip().upper()
    if parse_hhmm(ctot) is None:
        return False, "CTOT must be HH:MM (UTC)."
    t = parse_hhmm(ctot)
    ctot = f"{t // 60:02d}:{t % 60:02d}"
    conn = get_connection()
    try:
        if not conn.execute("SELECT 1 FROM flights WHERE flight_number=?", (fn,)).fetchone():
            return False, f"Flight {fn} not found."
        conn.execute("""INSERT INTO atfcm (flight_number, ctot, regulation, reason, created_utc)
                        VALUES (?,?,?,?,?)
                        ON CONFLICT(flight_number) DO UPDATE SET ctot=excluded.ctot,
                        regulation=excluded.regulation, reason=excluded.reason""",
                     (fn, ctot, regulation.strip().upper(), reason.strip(), get_utc_datetime()))
        conn.commit()
    finally:
        conn.close()
    add_log(get_utc_datetime(), username, "CTOT SET", f"{fn} CTOT {ctot} {regulation}".strip())
    return True, f"CTOT {ctot} set for {fn}."


def remove_ctot(flight_number, username="system"):
    conn = get_connection()
    try:
        cur = conn.execute("DELETE FROM atfcm WHERE flight_number=?", (flight_number.strip().upper(),))
        conn.commit()
        done = cur.rowcount > 0
    finally:
        conn.close()
    if done:
        add_log(get_utc_datetime(), username, "CTOT REMOVED", flight_number.upper())
    return done


def list_ctot(now=None):
    """All regulated flights sorted by CTOT time (nearest first)."""
    conn = get_connection()
    try:
        rows = conn.execute("""SELECT a.flight_number, f.etd, a.ctot, a.regulation, a.reason,
                                      f.runway, f.status, f.destination
                               FROM atfcm a LEFT JOIN flights f ON f.flight_number = a.flight_number""").fetchall()
    finally:
        conn.close()
    out = []
    for fn, etd, ctot, reg, reason, rwy, status, dest in rows:
        e, c = parse_hhmm(etd), parse_hhmm(ctot)
        delay = None if e is None or c is None else (c - e + 720) % 1440 - 720
        m = minutes_until(ctot, now)
        out.append({"flight_number": fn, "etd": etd or "", "ctot": ctot, "delay_min": delay,
                    "regulation": reg or "", "reason": reason or "", "runway": rwy or "",
                    "status": status or "", "destination": dest or "",
                    "minutes_to_ctot": m, "state": ctot_state(m, status or "")})
    out.sort(key=lambda x: (x["state"] == "DEPARTED", 9999 if x["minutes_to_ctot"] is None
                            else abs(x["minutes_to_ctot"])))
    return out


def delay_statistics():
    """Average / maximum / total ATFCM delay (minutes) over regulated flights."""
    delays = [x["delay_min"] for x in list_ctot() if x["delay_min"] is not None and x["delay_min"] > 0]
    if not delays:
        return {"count": 0, "average": 0, "maximum": 0, "total": 0}
    return {"count": len(delays), "average": round(sum(delays) / len(delays), 1),
            "maximum": max(delays), "total": sum(delays)}


# ------------------------------------------------------------------ console
def show_ctot():
    rows = list_ctot()
    print("\n" + "=" * 70)
    print("          ATFCM / CTOT")
    print("=" * 70)
    if not rows:
        print("  No regulated flights.")
        return
    print(f"  {'FLIGHT':<9}{'ETD':<7}{'CTOT':<7}{'DELAY':<8}{'REG':<10}{'IN':<8}STATE")
    for x in rows:
        d = "-" if x["delay_min"] is None else f"{x['delay_min']:+d}m"
        m = "-" if x["minutes_to_ctot"] is None else f"{x['minutes_to_ctot']:+d}m"
        print(f"  {x['flight_number']:<9}{x['etd'] or '-':<7}{x['ctot']:<7}{d:<8}{x['regulation'] or '-':<10}{m:<8}{x['state']}")


def set_ctot_cli(user=None):
    fn = input(" Flight number : ").strip()
    ctot = input(" CTOT (HH:MM UTC) : ").strip()
    reg = input(" Regulation (optional) : ").strip()
    reason = input(" Reason (optional) : ").strip()
    ok, msg = set_ctot(fn, ctot, reg, reason, user["username"] if user else "system")
    print(("\n ✓ " if ok else "\n ✗ ") + msg)
