"""
Alerts Module
Builds the list of operational alerts from the whole system
(capacity, runways, weather, NOTAM, CTOT, anomalies), stores them in the
database and lets users acknowledge them.
The alerts are only help messages: the decision always stays with the controller.
"""

from config import (LOW_VIS_M, LVP_VIS_M, LVP_CEILING_FT, STRONG_WIND_KT,
                    LOAD_WARNING_RATIO, LOAD_CRITICAL_RATIO)
from database import get_connection
from utc_time import get_utc_datetime
import metar_parser

ORDER = {"CRITICAL": 0, "WARNING": 1, "INFO": 2}


def _alert(level, code, key, message):
    return {"level": level, "code": code, "key": key, "message": message}


def generate_alerts():
    """Compute the alerts that apply right now (not stored yet)."""
    from capacity import compute_capacity, runway_states
    from atfcm import list_ctot
    from notam import active_notams
    import ai_support

    out = []

    # ---- traffic load / capacity
    c = compute_capacity()
    for kind, ratio, n, cap in (("ARRIVAL", c["ratio_arrival"], c["arrivals_next_hour"], c["arrival_capacity"]),
                                ("DEPARTURE", c["ratio_departure"], c["departures_next_hour"], c["departure_capacity"])):
        if ratio >= LOAD_CRITICAL_RATIO:
            out.append(_alert("CRITICAL", "TRAFFIC_LOAD", kind,
                              f"HIGH TRAFFIC LOAD - {kind.lower()}s {n} in next 60 min (capacity {cap:g})"))
        elif ratio >= LOAD_WARNING_RATIO:
            out.append(_alert("WARNING", "CAPACITY_LIMIT", kind,
                              f"RUNWAY CAPACITY APPROACHING LIMIT - {kind.lower()}s {n} / {cap:g}"))

    # ---- runways
    for rwy, st in sorted(runway_states().items()):
        if st == "CLOSED":
            out.append(_alert("WARNING", "RUNWAY_CLOSED", rwy, f"RWY {rwy} CLOSED"))
        elif st == "MAINTENANCE":
            out.append(_alert("INFO", "RUNWAY_MAINT", rwy, f"RWY {rwy} under maintenance"))

    # ---- CTOT
    for x in list_ctot():
        m = x["minutes_to_ctot"]
        if x["state"] == "APPROACHING":
            out.append(_alert("WARNING", "CTOT_APPROACHING", x["flight_number"],
                              f"CTOT APPROACHING - {x['flight_number']} CTOT {x['ctot']} in {m} min"))
        elif x["state"] == "IN WINDOW":
            out.append(_alert("WARNING", "CTOT_WINDOW", x["flight_number"],
                              f"CTOT WINDOW OPEN - {x['flight_number']} must depart by CTOT+10 ({x['ctot']})"))
        elif x["state"] == "MISSED":
            out.append(_alert("CRITICAL", "CTOT_MISSED", x["flight_number"],
                              f"CTOT MISSED - {x['flight_number']} (CTOT {x['ctot']}) needs a new slot"))

    # ---- weather
    w = metar_parser.get_latest()
    if w:
        vis, ceil = w.get("visibility_m"), w.get("ceiling_ft")
        if (vis is not None and vis < LVP_VIS_M) or (ceil is not None and ceil < LVP_CEILING_FT):
            out.append(_alert("CRITICAL", "LVP", "wx", "LOW VISIBILITY PROCEDURES conditions (vis/ceiling below minima)"))
        elif vis is not None and vis < LOW_VIS_M:
            out.append(_alert("WARNING", "LOW_VIS", "wx", f"LOW VISIBILITY - {vis} m (IFR)"))
        gust = max(w.get("wind_kt") or 0, w.get("gust_kt") or 0)
        if gust >= STRONG_WIND_KT:
            out.append(_alert("WARNING", "STRONG_WIND", "wx", f"STRONG WIND - {gust} kt"))
        if any("Thunderstorm" in x for x in w.get("weather", [])):
            out.append(_alert("WARNING", "THUNDERSTORM", "wx", "THUNDERSTORM reported at the airport"))

    # ---- NOTAM
    for n in active_notams():
        if n["priority"] == "HIGH":
            out.append(_alert("WARNING", "NOTAM_HIGH", n["notam_id"], f"NOTAM {n['notam_id']}: {n['text'][:70]}"))

    # ---- anomalies
    for a in ai_support.detect_anomalies():
        out.append(_alert(a["level"], a["code"], a["key"], a["message"]))

    out.sort(key=lambda a: (ORDER.get(a["level"], 3), a["code"], a["key"]))
    return out


def sync_alerts():
    """Store new alerts, update messages, and mark alerts that no longer apply as CLEARED."""
    current = {(a["code"], a["key"]): a for a in generate_alerts()}
    conn = get_connection()
    try:
        rows = conn.execute("SELECT id, code, key, status FROM alerts WHERE status IN ('ACTIVE','ACKNOWLEDGED')").fetchall()
        seen = set()
        for rid, code, key, status in rows:
            if (code, key) in current:
                seen.add((code, key))
                a = current[(code, key)]
                conn.execute("UPDATE alerts SET message=?, level=? WHERE id=?", (a["message"], a["level"], rid))
            else:
                conn.execute("UPDATE alerts SET status='CLEARED' WHERE id=?", (rid,))
        for k, a in current.items():
            if k not in seen:
                conn.execute("INSERT INTO alerts (utc_time, level, code, key, message, status) VALUES (?,?,?,?,?, 'ACTIVE')",
                             (get_utc_datetime(), a["level"], a["code"], a["key"], a["message"]))
        conn.commit()
    finally:
        conn.close()


def list_alerts(history=False, limit=200):
    """Rows (id, utc_time, level, code, message, status, ack_by)."""
    conn = get_connection()
    try:
        where = "" if history else "WHERE status IN ('ACTIVE','ACKNOWLEDGED')"
        rows = conn.execute(f"""SELECT id, utc_time, level, code, message, status, ack_by FROM alerts
                                {where} ORDER BY id DESC LIMIT ?""", (limit,)).fetchall()
    finally:
        conn.close()
    if not history:
        rows.sort(key=lambda r: (r[5] == "ACKNOWLEDGED", ORDER.get(r[2], 3), -r[0]))
    return rows


def count_active():
    """Number of alerts that nobody acknowledged yet, as (total, critical)."""
    conn = get_connection()
    try:
        t = conn.execute("SELECT COUNT(*) FROM alerts WHERE status='ACTIVE'").fetchone()[0]
        c = conn.execute("SELECT COUNT(*) FROM alerts WHERE status='ACTIVE' AND level='CRITICAL'").fetchone()[0]
    finally:
        conn.close()
    return t, c


def acknowledge(alert_id, username):
    conn = get_connection()
    try:
        conn.execute("UPDATE alerts SET status='ACKNOWLEDGED', ack_by=? WHERE id=? AND status='ACTIVE'",
                     (username, alert_id))
        conn.commit()
    finally:
        conn.close()


def show_alerts():
    sync_alerts()
    rows = list_alerts()
    print("\n" + "=" * 70)
    print("          ALERTS")
    print("=" * 70)
    if not rows:
        print("  ✓ No active alerts.")
        return
    icons = {"CRITICAL": "🔴", "WARNING": "⚠ ", "INFO": "ℹ "}
    for r in rows:
        print(f"  {icons.get(r[2], '')} [{r[2]:<8}] {r[4]}  ({r[5].lower()})")
