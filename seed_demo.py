"""
Demo data for AOMS  (flights, NOTAM, CTOT, METAR) so every screen can be shown.
Run:  python main.py --demo      (or  python seed_demo.py)
Times are generated relative to the current UTC time, so alerts really appear.
"""

from datetime import datetime, timedelta, timezone

from config import ICAO
from database import get_connection, init_database
from notam import add_notam
from atfcm import set_ctot
import metar_parser

DEMO_METAR = "DAAG 281000Z 32008KT 280V350 9999 FEW030 SCT100 24/12 Q1015 NOSIG"


def _t(minutes):
    return (datetime.now(timezone.utc) + timedelta(minutes=minutes)).strftime("%H:%M")


def seed():
    init_database()
    conn = get_connection()
    rows = [
        # number, airline, reg, type, wake, dep, dest, rwy, stand, etd, eta, fl, spd, squawk, status
        ("DAH1001", "AIR ALGERIE", "7T-VJA", "B738", "M", ICAO, "LFPG", "23", "A1", _t(10), _t(190), "FL370", "450", "4411", "BOARDING"),
        ("DAH1002", "AIR ALGERIE", "7T-VKB", "A332", "H", ICAO, "LFML", "23", "A2", _t(18), _t(130), "FL350", "460", "4412", "SCHEDULED"),
        ("DTR2201", "TASSILI", "7T-VCA", "B738", "M", ICAO, "DABC", "23", "B1", _t(25), _t(95), "FL330", "440", "4413", "SCHEDULED"),
        ("THY612", "TURKISH", "TC-JRA", "A321", "M", ICAO, "LTFM", "23", "B2", _t(32), _t(210), "FL360", "450", "4414", "SCHEDULED"),
        ("QTR421", "QATAR", "A7-BHB", "B77W", "H", ICAO, "OTHH", "23", "C1", _t(40), _t(330), "FL380", "480", "4415", "SCHEDULED"),
        ("AFR1255", "AIR FRANCE", "F-GKXA", "A320", "M", "LFPO", ICAO, "23", "A3", _t(-120), _t(8), "FL360", "440", "5521", "ARRIVING"),
        ("DLH3401", "LUFTHANSA", "D-AIZA", "A320", "M", "EDDF", ICAO, "23", "A4", _t(-150), _t(15), "FL370", "440", "5522", "AIRBORNE"),
        ("TAR710", "TUNISAIR", "TS-IMA", "A319", "M", "DTTA", ICAO, "27", "B3", _t(-50), _t(22), "FL300", "420", "5523", "AIRBORNE"),
        ("UAE761", "EMIRATES", "A6-EBA", "A388", "J", "OMDB", ICAO, "27", "C2", _t(-350), _t(35), "FL390", "490", "5524", "AIRBORNE"),
        ("DAH1100", "AIR ALGERIE", "7T-VJC", "B738", "M", "DABC", ICAO, "27", "A5", _t(-70), _t(48), "FL320", "430", "5525", "AIRBORNE"),
        ("ETD601", "ETIHAD", "A6-EYA", "B789", "H", "OMAA", ICAO, "27", "C3", _t(-330), _t(52), "FL390", "490", "5526", "AIRBORNE"),
    ]
    for r in rows:
        conn.execute("""INSERT OR IGNORE INTO flights (flight_number, airline, registration, aircraft, wake,
                        departure, destination, runway, stand, etd, eta, flight_level, speed, squawk, status, created_utc)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                     (r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8], r[9], r[10], r[11], r[12], r[13], r[14],
                      datetime.now(timezone.utc).strftime("%d %b %Y %H:%M UTC")))
    conn.commit()
    conn.close()

    add_notam("A0101/26", "RWY 09/27 CLSD DUE WIP", "", "PERM", "demo")
    add_notam("A0102/26", "ILS RWY 05 U/S", "", "PERM", "demo")
    add_notam("A0103/26", "TWY B CLSD BTN TWY B3 AND B5", "", "PERM", "demo")
    add_notam("A0104/26", "PAPI RWY 23 U/S", "", "PERM", "demo")
    add_notam("A0105/26", "CRANE ERECTED 2.5NM E OF ARP, 350 FT AGL", "", "PERM", "demo")

    set_ctot("DAH1001", _t(22), "LFPGAL12", "ATC capacity LFPG", "demo")
    set_ctot("DAH1002", _t(60), "LFMLB05", "En-route capacity", "demo")
    set_ctot("DTR2201", _t(-20), "DABCW1", "Weather", "demo")

    metar_parser.set_latest(metar_parser.parse_metar(DEMO_METAR))
    print("Demo data loaded: 11 flights, 5 NOTAM, 3 CTOT.")


if __name__ == "__main__":
    seed()
