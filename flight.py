"""
Flight Module
"""

from config import ICAO
from database import get_connection
from logs import add_log
from utc_time import get_utc_datetime

AIRLINES = {
    "DAH": "AIR ALGERIE", "DTR": "TASSILI", "THY": "TURKISH", "QTR": "QATAR",
    "TAR": "TUNISAIR", "AFR": "AIR FRANCE", "DLH": "LUFTHANSA",
    "UAE": "EMIRATES", "ETD": "ETIHAD",
}


# ------------------------------------------------------------------ queries
def flight_exists(flight_number):
    conn = get_connection()
    try:
        row = conn.execute("SELECT 1 FROM flights WHERE flight_number=?",
                           (flight_number.upper(),)).fetchone()
        return row is not None
    finally:
        conn.close()


def get_flight_by_number(flight_number):
    conn = get_connection()
    try:
        return conn.execute("SELECT * FROM flights WHERE flight_number=?",
                            (flight_number.upper(),)).fetchone()
    finally:
        conn.close()


def update_flight_status(flight_number, status):
    conn = get_connection()
    try:
        conn.execute("UPDATE flights SET status=? WHERE flight_number=?",
                     (status, flight_number.upper()))
        conn.commit()
    finally:
        conn.close()


def get_flight_count():
    conn = get_connection()
    try:
        return conn.execute("SELECT COUNT(*) FROM flights").fetchone()[0]
    finally:
        conn.close()


def get_departure_flights():
    conn = get_connection()
    try:
        return conn.execute("SELECT * FROM flights WHERE departure=?", (ICAO,)).fetchall()
    finally:
        conn.close()


def get_arrival_flights():
    conn = get_connection()
    try:
        return conn.execute("SELECT * FROM flights WHERE destination=?", (ICAO,)).fetchall()
    finally:
        conn.close()


def get_all_flights():
    conn = get_connection()
    try:
        return conn.execute("SELECT * FROM flights ORDER BY etd, flight_number").fetchall()
    finally:
        conn.close()


# ------------------------------------------------------------------ CLI
def add_flight():
    print("\n" + "=" * 42)
    print("          ADD FLIGHT")
    print("=" * 42)
    number = input(" Flight Number : ").strip().upper()
    if len(number) < 3:
        print(" ✗ Invalid flight number.")
        return
    if flight_exists(number):
        print(" ✗ Flight already exists.")
        return
    airline = AIRLINES.get(number[:3], "UNKNOWN")
    reg = input(" Registration : ").strip().upper()
    ac = input(" Aircraft Type : ").strip().upper()
    wake = input(" Wake (L/M/H) [M] : ").strip().upper() or "M"
    dep = input(f" Departure ICAO [{ICAO}] : ").strip().upper() or ICAO
    dest = input(" Destination ICAO : ").strip().upper()
    sid = input(" SID : ").strip().upper()
    star = input(" STAR : ").strip().upper()
    rwy = input(" Runway : ").strip().upper()
    stand = input(" Stand : ").strip().upper()
    etd = input(" ETD (HH:MM) : ").strip()
    eta = input(" ETA (HH:MM) : ").strip()
    fl = input(" Flight Level : ").strip()
    speed = input(" Speed : ").strip()
    squawk = input(" Squawk : ").strip()

    conn = get_connection()
    try:
        conn.execute("""
            INSERT INTO flights (flight_number, airline, registration, aircraft, wake,
                departure, destination, sid, star, runway, stand, etd, eta,
                flight_level, speed, squawk, status, created_utc)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (number, airline, reg, ac, wake, dep, dest, sid, star, rwy, stand,
              etd, eta, fl, speed, squawk, "SCHEDULED", get_utc_datetime()))
        conn.commit()
    finally:
        conn.close()
    add_log(get_utc_datetime(), "Administrator", "FLIGHT ADDED", number)
    print(f"\n ✓ Flight {number} ({airline}) added.")


def show_flights():
    rows = get_all_flights()
    print("\n" + "=" * 70)
    print("          FLIGHTS")
    print("=" * 70)
    if not rows:
        print("  No flights found.")
        return
    print(f"  Total: {len(rows)}")
    for r in rows:
        print("-" * 70)
        print(f"  {r[1]:<8} {r[2] or '':<14} {r[6]} → {r[7]}   RWY {r[10] or '-'}")
        print(f"           ETD {r[12] or '-'}  ETA {r[13] or '-'}  Status {r[17]}")


def search_flight():
    term = input(" Search (flight / airline / airport) : ").strip().upper()
    if not term:
        return
    like = f"%{term}%"
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT * FROM flights WHERE UPPER(flight_number) LIKE ? OR UPPER(airline) LIKE ?
            OR departure LIKE ? OR destination LIKE ?""", (like,) * 4).fetchall()
    finally:
        conn.close()
    if not rows:
        print(" ✗ No flights found.")
        return
    for r in rows:
        print(f"  {r[1]:<8} {r[2] or '':<14} {r[6]} → {r[7]}  {r[17]}")


def delete_flight():
    number = input(" Flight Number to delete : ").strip().upper()
    if not flight_exists(number):
        print(" ✗ Flight not found.")
        return
    if input(f" Delete {number}? (y/n) : ").lower() != "y":
        return
    conn = get_connection()
    try:
        conn.execute("DELETE FROM flights WHERE flight_number=?", (number,))
        conn.commit()
    finally:
        conn.close()
    add_log(get_utc_datetime(), "Administrator", "FLIGHT DELETED", number)
    print(f" ✓ Flight {number} deleted.")
