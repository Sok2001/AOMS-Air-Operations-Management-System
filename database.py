"""
Database Module (SQLite)
Creates the schema on first run and seeds the default administrator.
"""

import hashlib
import os
import sqlite3

from config import ADMIN_USERNAME, ADMIN_PASSWORD, RUNWAYS

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
from app_paths import DATABASE_PATH as DATABASE


def get_connection():
    return sqlite3.connect(DATABASE)


def has_administrator():
    """Check whether an administrator account already exists."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT COUNT(*) FROM users WHERE role='Administrator'"
        ).fetchone()
        return bool(row and row[0])
    except sqlite3.OperationalError:
        return False
    finally:
        conn.close()


def initialize_database(gui=True):
    """Initialize the database and request a password on first GUI launch."""
    if has_administrator():
        return init_database()

    if ADMIN_PASSWORD and ADMIN_PASSWORD.strip():
        return init_database()

    if gui:
        from first_run import request_admin_password
        password = request_admin_password()
    else:
        from getpass import getpass
        from auth import is_strong_password

        password = None
        while not password:
            candidate = getpass("Create administrator password: ")
            valid, reason = is_strong_password(candidate)
            if not valid:
                print(reason)
                continue

            confirmation = getpass("Confirm password: ")
            if candidate != confirmation:
                print("Passwords do not match.")
                continue

            password = candidate

    if not password:
        return None

    return init_database(admin_password=password)


def init_database(admin_password=None):
    """Create tables if missing, seed runways and the default admin."""
    password = ADMIN_PASSWORD if admin_password is None else admin_password
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            full_name TEXT,
            role TEXT NOT NULL,
            active INTEGER DEFAULT 1,
            login_attempts INTEGER DEFAULT 0,
            locked_until TEXT,
            last_login TEXT
        )""")

    # Column order matters: other modules read rows by index
    # (id, flight_number, airline, registration, aircraft, wake, departure,
    #  destination, sid, star, runway, stand, etd, eta, flight_level, speed,
    #  squawk, status, created_utc)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS flights (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            flight_number TEXT UNIQUE NOT NULL,
            airline TEXT,
            registration TEXT,
            aircraft TEXT,
            wake TEXT,
            departure TEXT,
            destination TEXT,
            sid TEXT,
            star TEXT,
            runway TEXT,
            stand TEXT,
            etd TEXT,
            eta TEXT,
            flight_level TEXT,
            speed TEXT,
            squawk TEXT,
            status TEXT DEFAULT 'SCHEDULED',
            created_utc TEXT
        )""")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS runways (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            runway TEXT UNIQUE NOT NULL,
            status TEXT DEFAULT 'AVAILABLE'
        )""")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            utc_time TEXT,
            username TEXT,
            action TEXT,
            details TEXT
        )""")


    # ---- NOTAM
    cur.execute("""
        CREATE TABLE IF NOT EXISTS notams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            notam_id TEXT UNIQUE NOT NULL,
            category TEXT,
            priority TEXT,
            text TEXT NOT NULL,
            valid_from TEXT,
            valid_to TEXT,
            status TEXT DEFAULT 'ACTIVE',
            created_utc TEXT,
            created_by TEXT
        )""")

    # ---- v3.4: automatic NOTAM import (settings + origin of each NOTAM)
    cur.execute("CREATE TABLE IF NOT EXISTS app_settings (key TEXT PRIMARY KEY, value TEXT)")
    for col, ddl in (("source", "TEXT DEFAULT 'MANUAL'"), ("location", "TEXT")):
        try:
            cur.execute(f"ALTER TABLE notams ADD COLUMN {col} {ddl}")
        except sqlite3.OperationalError:      # column already exists
            pass

    # ---- ATFCM / CTOT
    cur.execute("""
        CREATE TABLE IF NOT EXISTS atfcm (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            flight_number TEXT UNIQUE NOT NULL,
            ctot TEXT NOT NULL,
            regulation TEXT,
            reason TEXT,
            created_utc TEXT
        )""")

    # ---- Alerts (history + acknowledgement)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            utc_time TEXT,
            level TEXT,
            code TEXT,
            key TEXT,
            message TEXT,
            status TEXT DEFAULT 'ACTIVE',
            ack_by TEXT
        )""")


    # ---- AIP data (airports, runways, navaids, stands, obstacles, charts) - filled by aip_loader.py
    cur.executescript("""
        CREATE TABLE IF NOT EXISTS aip_meta (key TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE IF NOT EXISTS airports (
            icao TEXT PRIMARY KEY, iata TEXT, name TEXT, city TEXT, country TEXT, arp_lat REAL, arp_lon REAL,
            elevation_m REAL, ref_temp_c REAL, mag_var TEXT, location TEXT, traffic TEXT, airac TEXT, source TEXT);
        CREATE TABLE IF NOT EXISTS aip_sections (id INTEGER PRIMARY KEY AUTOINCREMENT, icao TEXT, ord INTEGER,
            section TEXT, text TEXT);
        CREATE TABLE IF NOT EXISTS aip_notes (id INTEGER PRIMARY KEY AUTOINCREMENT, icao TEXT, ord INTEGER, text TEXT);
        CREATE TABLE IF NOT EXISTS aip_runways (
            id INTEGER PRIMARY KEY AUTOINCREMENT, icao TEXT, rwy TEXT, true_brg REAL, mag_brg REAL, length_m REAL,
            width_m REAL, surface TEXT, pcr TEXT, thr_lat REAL, thr_lon REAL, thr_elev_m REAL, slope TEXT, strip TEXT,
            resa TEXT, shoulders TEXT, tora REAL, toda REAL, asda REAL, lda REAL, approach_lgt TEXT, thr_lgt TEXT,
            papi TEXT, tdz_lgt TEXT, cl_lgt TEXT, edge_lgt TEXT, end_lgt TEXT, swy_lgt TEXT, ils TEXT, ils_cat TEXT,
            loc TEXT, gp TEXT, dme TEXT, UNIQUE(icao, rwy));
        CREATE TABLE IF NOT EXISTS aip_navaids (id INTEGER PRIMARY KEY AUTOINCREMENT, icao TEXT, type TEXT,
            ident TEXT, freq TEXT, channel TEXT, lat REAL, lon REAL, remarks TEXT);
        CREATE TABLE IF NOT EXISTS aip_frequencies (id INTEGER PRIMARY KEY AUTOINCREMENT, icao TEXT, service TEXT,
            callsign TEXT, freq TEXT, hours TEXT, remarks TEXT);
        CREATE TABLE IF NOT EXISTS aip_stands (id INTEGER PRIMARY KEY AUTOINCREMENT, icao TEXT, apron TEXT,
            stand TEXT, category TEXT, strength TEXT, lat REAL, lon REAL);
        CREATE TABLE IF NOT EXISTS aip_aprons (id INTEGER PRIMARY KEY AUTOINCREMENT, icao TEXT, apron TEXT,
            elevation_m REAL, surface_strength TEXT);
        CREATE TABLE IF NOT EXISTS aip_taxiways (id INTEGER PRIMARY KEY AUTOINCREMENT, icao TEXT, twy TEXT,
            width_m REAL, surface TEXT, pcr TEXT, remarks TEXT);
        CREATE TABLE IF NOT EXISTS aip_obstacles (id INTEGER PRIMARY KEY AUTOINCREMENT, icao TEXT, obst_id TEXT,
            type TEXT, position TEXT, elev_hgt TEXT, marking TEXT, area TEXT, remarks TEXT);
        CREATE TABLE IF NOT EXISTS charts (id INTEGER PRIMARY KEY AUTOINCREMENT, icao TEXT, code TEXT, type TEXT,
            title TEXT, rwy TEXT, category TEXT, airac TEXT, file TEXT, preview TEXT, source TEXT DEFAULT 'auto',
            UNIQUE(icao, code));
    """)

    # Runways of DAAG
    cur.execute("SELECT COUNT(*) FROM runways")
    if cur.fetchone()[0] == 0:
        cur.executemany("INSERT INTO runways (runway, status) VALUES (?, 'AVAILABLE')",
                        [("05",), ("23",), ("09",), ("27",)])

    # Default administrator (first run only)
    cur.execute("SELECT COUNT(*) FROM users WHERE role='Administrator'")
    created_admin = False
    if cur.fetchone()[0] == 0:
        if not password or not password.strip():
            conn.close()
            raise RuntimeError("Administrator password is missing.")

        pw = hashlib.sha256(password.encode()).hexdigest()
        cur.execute("""INSERT INTO users (username, password, full_name, role, active)
                       VALUES (?, ?, ?, 'Administrator', 1)""",
                    (ADMIN_USERNAME, pw, "System Administrator"))
        created_admin = True

    conn.commit()
    conn.close()
    return created_admin
