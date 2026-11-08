"""
Airport Capacity Module
Compares the traffic demand with the hourly capacity (config.py) and
reduces the capacity when a runway is closed (status, maintenance or NOTAM).
"""

from config import (ICAO, ARRIVAL_CAPACITY, DEPARTURE_CAPACITY,
                    LOAD_WARNING_RATIO, LOAD_CRITICAL_RATIO)
from database import get_connection
from notam import closed_runways
from utc_time import parse_hhmm, now_minutes

# the 4 runway ends belong to 2 physical runways
PHYSICAL_RUNWAYS = {"05/23": ("05", "23"), "09/27": ("09", "27")}
FINISHED = ("CANCELLED", "LANDED", "PARKED", "DEPARTED", "AIRBORNE", "TAKEOFF")
ARR_DONE = ("CANCELLED", "LANDED", "PARKED")
DEP_DONE = ("CANCELLED", "DEPARTED", "AIRBORNE", "TAKEOFF", "LANDED", "PARKED")


def congestion_level(ratio):
    if ratio >= LOAD_CRITICAL_RATIO:
        return "CRITICAL"
    if ratio >= LOAD_WARNING_RATIO:
        return "HIGH"
    if ratio >= 0.5:
        return "MODERATE"
    return "LOW"


def runway_states():
    """{'05': 'AVAILABLE', ...} including NOTAM closures."""
    conn = get_connection()
    try:
        states = dict(conn.execute("SELECT runway, status FROM runways").fetchall())
    finally:
        conn.close()
    for r in closed_runways():
        states[r] = "CLOSED"
    return states


def operational_runways():
    """Physical runways that still have at least one usable end."""
    states = runway_states()
    out = {}
    for name, ends in PHYSICAL_RUNWAYS.items():
        out[name] = any(states.get(e, "AVAILABLE") not in ("CLOSED", "MAINTENANCE") for e in ends)
    return out


def _window_count(times, now, ahead=60, behind=15):
    n = 0
    for t in times:
        m = parse_hhmm(t)
        if m is None:
            continue
        diff = (m - now + 720) % 1440 - 720
        if -behind <= diff <= ahead:
            n += 1
    return n


def compute_capacity(now=None):
    """Full capacity picture used by dashboard, alerts and the Capacity page."""
    now = now_minutes() if now is None else now
    conn = get_connection()
    try:
        arr = conn.execute("""SELECT eta, status FROM flights WHERE destination=?""", (ICAO,)).fetchall()
        dep = conn.execute("""SELECT etd, status FROM flights WHERE departure=?""", (ICAO,)).fetchall()
    finally:
        conn.close()
    arr_pending = [e for e, s in arr if s not in ARR_DONE]
    dep_pending = [e for e, s in dep if s not in DEP_DONE]

    ops = operational_runways()
    factor = sum(ops.values()) / len(ops) if ops else 1
    arr_cap = ARRIVAL_CAPACITY * factor
    dep_cap = DEPARTURE_CAPACITY * factor

    arr_next = _window_count(arr_pending, now)
    dep_next = _window_count(dep_pending, now)
    ratio_arr = (arr_next / arr_cap) if arr_cap else (9.99 if arr_next else 0)
    ratio_dep = (dep_next / dep_cap) if dep_cap else (9.99 if dep_next else 0)
    total_cap = arr_cap + dep_cap
    ratio_total = ((arr_next + dep_next) / total_cap) if total_cap else (9.99 if arr_next + dep_next else 0)
    worst = max(ratio_arr, ratio_dep)

    return {
        "arrivals_pending": len(arr_pending), "departures_pending": len(dep_pending),
        "arrivals_next_hour": arr_next, "departures_next_hour": dep_next,
        "arrival_capacity": round(arr_cap, 1), "departure_capacity": round(dep_cap, 1),
        "ratio_arrival": ratio_arr, "ratio_departure": ratio_dep, "ratio_total": ratio_total,
        "runways_operational": ops, "capacity_factor": factor,
        "level": congestion_level(worst),
        "aircraft_on_ground": _count_status(("TAXI", "LINE UP", "PUSHBACK", "STARTUP")),
        "runways_occupied": _count_runways("OCCUPIED"),
    }


def _count_status(statuses):
    conn = get_connection()
    try:
        q = ",".join("?" * len(statuses))
        return conn.execute(f"SELECT COUNT(*) FROM flights WHERE status IN ({q})", statuses).fetchone()[0]
    finally:
        conn.close()


def _count_runways(status):
    return sum(1 for s in runway_states().values() if s == status)


def hourly_profile():
    """Movements per UTC hour (0-23): ([arrivals], [departures]) from ETA / ETD."""
    arrivals, departures = [0] * 24, [0] * 24
    conn = get_connection()
    try:
        for eta, in conn.execute("SELECT eta FROM flights WHERE destination=? AND status!='CANCELLED'", (ICAO,)):
            m = parse_hhmm(eta)
            if m is not None:
                arrivals[m // 60] += 1
        for etd, in conn.execute("SELECT etd FROM flights WHERE departure=? AND status!='CANCELLED'", (ICAO,)):
            m = parse_hhmm(etd)
            if m is not None:
                departures[m // 60] += 1
    finally:
        conn.close()
    return arrivals, departures


def show_capacity():
    c = compute_capacity()
    print("\n" + "=" * 50)
    print("      AIRPORT CAPACITY")
    print("=" * 50)
    print(f"  Arrivals   (next 60 min) : {c['arrivals_next_hour']} / {c['arrival_capacity']}")
    print(f"  Departures (next 60 min) : {c['departures_next_hour']} / {c['departure_capacity']}")
    print(f"  Pending  ARR / DEP       : {c['arrivals_pending']} / {c['departures_pending']}")
    print(f"  Operational runways      : " + ", ".join(f"{k} {'OK' if v else 'CLOSED'}" for k, v in c['runways_operational'].items()))
    print(f"  Congestion level         : {c['level']}")
