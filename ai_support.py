"""
AI Decision Support Module  (advisory only)

Rule-based + statistical analysis on the data of the system:
  - congestion prediction (next 2 hours)
  - runway suggestion (wind components, ILS needs, closures)
  - anomaly detection (squawk, runway / stand conflicts, emergencies)
  - conflict detection between live aircraft (5 NM / 1000 ft)

Everything here is a SUGGESTION. The final decision always stays with the
air traffic controller. The functions are written so that a real machine
learning model can replace them later without changing the screens.
"""

import math

from config import (ICAO, ARRIVAL_CAPACITY, DEPARTURE_CAPACITY, LOAD_WARNING_RATIO,
                    LOAD_CRITICAL_RATIO, MAX_CROSSWIND_KT, MAX_TAILWIND_KT,
                    CONFLICT_HORIZONTAL_NM, CONFLICT_VERTICAL_FT, ARP_LAT, ARP_LON,
                    RUNWAY_05, RUNWAY_23, RUNWAY_09, RUNWAY_27)
from database import get_connection
from utc_time import parse_hhmm, now_minutes
import metar_parser

RUNWAY_DATA = {"05": RUNWAY_05, "23": RUNWAY_23, "09": RUNWAY_09, "27": RUNWAY_27}
EMERGENCY_SQUAWK = {"7500": "HIJACK", "7600": "RADIO FAILURE", "7700": "EMERGENCY"}
ACTIVE_STATUSES = ("BOARDING", "PUSHBACK", "STARTUP", "TAXI", "LINE UP", "TAKEOFF",
                   "AIRBORNE", "ARRIVING")


# ------------------------------------------------------------------ wind
def wind_components(wind_dir, wind_kt, runway_heading):
    """(headwind, crosswind) in knots. Headwind < 0 means tailwind. Crosswind is absolute."""
    angle = math.radians(wind_dir - runway_heading)
    return wind_kt * math.cos(angle), abs(wind_kt * math.sin(angle))


# ------------------------------------------------------------------ runway suggestion
def suggest_runway(operation="DEPARTURE", wind_dir=None, wind_kt=None, gust_kt=None, rules="VFR",
                   runway_status=None):
    """
    Rank the runways for ARRIVAL or DEPARTURE.
    Returns a list of dicts sorted from best to worst:
    {runway, score, headwind, crosswind, usable, reasons}
    """
    if runway_status is None:
        from capacity import runway_states
        runway_status = runway_states()
    speed = max(wind_kt or 0, gust_kt or 0)
    calm = wind_dir is None or speed < 3
    results = []
    for rwy, data in RUNWAY_DATA.items():
        reasons, usable = [], True
        status = runway_status.get(rwy, "AVAILABLE")
        if status in ("CLOSED", "MAINTENANCE"):
            usable = False
            reasons.append(f"runway {status.lower()}")
        head = cross = 0.0
        if not calm:
            head, cross = wind_components(wind_dir, speed, data["heading"])
            if head < -MAX_TAILWIND_KT:
                usable = False
                reasons.append(f"tailwind {abs(head):.0f} kt")
            if cross > MAX_CROSSWIND_KT:
                usable = False
                reasons.append(f"crosswind {cross:.0f} kt")
        if operation == "ARRIVAL" and rules in ("IFR", "LIFR") and not data["ils"]:
            usable = False
            reasons.append("no ILS in IFR conditions")
        if status == "OCCUPIED":
            reasons.append("currently occupied")
        score = head - 0.5 * cross + (2 if data["ils"] else 0) - (3 if status == "OCCUPIED" else 0)
        if usable:
            reasons.insert(0, "calm wind" if calm else f"headwind {round(head) + 0:+d} kt, crosswind {round(cross)} kt")
        results.append({"runway": rwy, "score": round(score, 1), "headwind": round(head, 1),
                        "crosswind": round(cross, 1), "usable": usable, "reasons": reasons,
                        "ils": data["ils"]})
    results.sort(key=lambda r: (not r["usable"], -r["score"]))
    return results


def suggest_runway_from_weather(operation="DEPARTURE"):
    """Use the last METAR in memory."""
    w = metar_parser.get_latest() or {}
    return suggest_runway(operation, w.get("wind_dir"), w.get("wind_kt"), w.get("gust_kt"),
                          w.get("flight_rules", "VFR"))


# ------------------------------------------------------------------ congestion prediction
def predict_congestion(horizon_min=120, step=15, now=None):
    """
    Forecast the traffic in the next hours from the ETA / ETD of the flights.
    Returns {"steps": [(label, arrivals_60, departures_60, level)], "peak": ..., "message": ...}
    """
    now = now_minutes() if now is None else now
    conn = get_connection()
    try:
        arr = [e for e, s in conn.execute("SELECT eta, status FROM flights WHERE destination=?", (ICAO,))
               if s not in ("CANCELLED", "LANDED", "PARKED")]
        dep = [e for e, s in conn.execute("SELECT etd, status FROM flights WHERE departure=?", (ICAO,))
               if s not in ("CANCELLED", "DEPARTED", "AIRBORNE", "TAKEOFF", "LANDED", "PARKED")]
    finally:
        conn.close()
    from capacity import compute_capacity          # capacity already reduced by closed runways
    cap = compute_capacity(now)
    arr_cap, dep_cap = cap["arrival_capacity"], cap["departure_capacity"]
    arr_m = [m for m in (parse_hhmm(x) for x in arr) if m is not None]
    dep_m = [m for m in (parse_hhmm(x) for x in dep) if m is not None]

    def count(times, start):
        return sum(1 for t in times if 0 <= (t - start + 720) % 1440 - 720 < 60)

    steps, peak = [], None
    for k in range(0, horizon_min + 1, step):
        t0 = (now + k) % 1440
        a, d = count(arr_m, t0), count(dep_m, t0)
        ratio = max(a / arr_cap if arr_cap else (9.99 if a else 0),
                    d / dep_cap if dep_cap else (9.99 if d else 0))
        level = ("CRITICAL" if ratio >= LOAD_CRITICAL_RATIO else "HIGH" if ratio >= LOAD_WARNING_RATIO
                 else "MODERATE" if ratio >= 0.5 else "LOW")
        label = f"{t0 // 60:02d}:{t0 % 60:02d}"
        steps.append((label, a, d, level))
        if peak is None or ratio > peak[0]:
            peak = (ratio, label, a, d, level)

    if peak and peak[4] in ("HIGH", "CRITICAL"):
        message = (f"⚠ {peak[4]} traffic expected from {peak[1]} UTC "
                   f"({peak[2]} arrivals / {peak[3]} departures in the following 60 min).")
    else:
        message = "No congestion expected in the next 2 hours."
    return {"steps": steps, "peak": peak, "message": message}


# ------------------------------------------------------------------ anomaly detection
def detect_anomalies():
    """Data and operational anomalies. Returns [{level, code, key, message}]."""
    from capacity import runway_states
    conn = get_connection()
    try:
        rows = conn.execute("""SELECT flight_number, runway, stand, squawk, status, departure, destination
                               FROM flights WHERE status NOT IN ('CANCELLED', 'LANDED', 'PARKED')""").fetchall()
    finally:
        conn.close()
    flights = [r[:5] for r in rows]
    out = []
    active = [f for f in flights if f[4] in ACTIVE_STATUSES]

    # emergency squawk
    for fn, rwy, stand, sq, st in flights:
        sq = (sq or "").strip()
        if sq in EMERGENCY_SQUAWK:
            out.append({"level": "CRITICAL", "code": "EMERGENCY_SQUAWK", "key": fn,
                        "message": f"SQUAWK {sq} ({EMERGENCY_SQUAWK[sq]}) - {fn}"})

    # duplicate squawk
    by_sq = {}
    for fn, rwy, stand, sq, st in active:
        sq = (sq or "").strip()
        if sq and sq not in ("2000", "7000", "0000"):
            by_sq.setdefault(sq, []).append(fn)
    for sq, fns in by_sq.items():
        if len(fns) > 1:
            out.append({"level": "WARNING", "code": "DUPLICATE_SQUAWK", "key": sq,
                        "message": f"DUPLICATE SQUAWK {sq}: {', '.join(sorted(fns))}"})

    # two aircraft on the same runway at the same time
    on_rwy = {}
    for fn, rwy, stand, sq, st in flights:
        if st in ("LINE UP", "TAKEOFF") and rwy:
            on_rwy.setdefault(rwy, []).append(fn)
    for rwy, fns in on_rwy.items():
        if len(fns) > 1:
            out.append({"level": "CRITICAL", "code": "RUNWAY_CONFLICT", "key": rwy,
                        "message": f"RWY {rwy}: {len(fns)} aircraft lined up / taking off ({', '.join(sorted(fns))})"})

    # runway assigned but not usable
    states = runway_states()
    for fn, rwy, stand, sq, st, dep, dest in rows:
        still_needs = ((dep == ICAO and st in ("SCHEDULED", "BOARDING", "PUSHBACK", "STARTUP", "TAXI", "LINE UP")) or
                       (dest == ICAO and st in ("SCHEDULED", "AIRBORNE", "ARRIVING")))
        if still_needs and rwy and states.get(rwy) in ("CLOSED", "MAINTENANCE"):
            out.append({"level": "WARNING", "code": "RUNWAY_ASSIGNED_CLOSED", "key": fn,
                        "message": f"{fn} is assigned to RWY {rwy} which is {states[rwy].lower()}"})

    # same stand used twice
    stands = {}
    for fn, rwy, stand, sq, st in flights:
        if stand and st in ("BOARDING", "PUSHBACK", "STARTUP", "PARKED"):
            stands.setdefault(stand, []).append(fn)
    for stand, fns in stands.items():
        if len(fns) > 1:
            out.append({"level": "WARNING", "code": "STAND_CONFLICT", "key": stand,
                        "message": f"STAND {stand} used by {', '.join(sorted(fns))}"})

    # flight moving without a runway
    for fn, rwy, stand, sq, st in flights:
        if st in ("LINE UP", "TAKEOFF", "ARRIVING") and not rwy:
            out.append({"level": "INFO", "code": "NO_RUNWAY", "key": fn,
                        "message": f"{fn} is {st} but has no runway assigned"})
    return out


# ------------------------------------------------------------------ conflict detection
def _to_xy_nm(lat, lon):
    """Flat-earth position in NM relative to the airport (good enough near the airport)."""
    return (lon - ARP_LON) * 60 * math.cos(math.radians(ARP_LAT)), (lat - ARP_LAT) * 60


def distance_nm(lat1, lon1, lat2, lon2):
    """Great-circle distance in nautical miles."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 3440.065 * math.asin(math.sqrt(a))


def detect_conflicts(aircraft, lookahead_min=5):
    """
    aircraft: list of dicts {callsign, lat, lon, alt_ft, track, speed_kt, on_ground, vrate_fpm(optional)}
    Finds pairs that are (or will be within `lookahead_min`) closer than
    5 NM horizontally AND 1000 ft vertically.  ADVISORY ONLY.
    """
    flying = [a for a in aircraft if not a.get("on_ground") and a.get("lat") is not None
              and a.get("lon") is not None and a.get("alt_ft") is not None]
    result = []
    for i in range(len(flying)):
        for j in range(i + 1, len(flying)):
            a, b = flying[i], flying[j]
            ax, ay = _to_xy_nm(a["lat"], a["lon"])
            bx, by = _to_xy_nm(b["lat"], b["lon"])
            dx, dy = bx - ax, by - ay
            vax, vay = _velocity(a)
            vbx, vby = _velocity(b)
            dvx, dvy = vbx - vax, vby - vay
            v2 = dvx * dvx + dvy * dvy
            t = 0.0 if v2 < 1e-9 else max(0.0, min(lookahead_min, -(dx * dvx + dy * dvy) / v2))
            dcpa = math.hypot(dx + dvx * t, dy + dvy * t)
            vert_now = abs(a["alt_ft"] - b["alt_ft"])
            vert_t = abs((a["alt_ft"] + (a.get("vrate_fpm") or 0) * t) - (b["alt_ft"] + (b.get("vrate_fpm") or 0) * t))
            now_dist = math.hypot(dx, dy)
            if now_dist < CONFLICT_HORIZONTAL_NM and vert_now < CONFLICT_VERTICAL_FT:
                severity = "LOSS OF SEPARATION"
            elif dcpa < CONFLICT_HORIZONTAL_NM and vert_t < CONFLICT_VERTICAL_FT:
                severity = "POTENTIAL CONFLICT"
            else:
                continue
            result.append({"a": a["callsign"], "b": b["callsign"], "distance_nm": round(now_dist, 1),
                           "vertical_ft": round(vert_now), "tcpa_min": round(t, 1),
                           "dcpa_nm": round(dcpa, 1), "severity": severity})
    result.sort(key=lambda r: (r["severity"] != "LOSS OF SEPARATION", r["dcpa_nm"]))
    return result


def _velocity(a):
    """NM per minute (east, north) from ground speed and track."""
    spd = (a.get("speed_kt") or 0) / 60.0
    trk = math.radians(a.get("track") or 0)
    return spd * math.sin(trk), spd * math.cos(trk)


# ------------------------------------------------------------------ report
def decision_report():
    """Plain-text summary for the console / AI page."""
    lines = ["AI DECISION SUPPORT  (advisory only - the controller decides)", "=" * 60]
    c = predict_congestion()
    lines.append("Traffic forecast : " + c["message"])
    for op in ("DEPARTURE", "ARRIVAL"):
        best = [r for r in suggest_runway_from_weather(op) if r["usable"]]
        lines.append(f"Runway for {op.lower():<9}: " + (f"RWY {best[0]['runway']}  ({best[0]['reasons'][0]})" if best
                                                      else "no suitable runway - check weather / closures"))
    an = detect_anomalies()
    lines.append(f"Anomalies        : {len(an)}")
    for a in an:
        lines.append(f"   - [{a['level']}] {a['message']}")
    return "\n".join(lines)


def show_ai_report():
    print("\n" + decision_report())
