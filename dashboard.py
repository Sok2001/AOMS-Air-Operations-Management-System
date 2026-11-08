import sqlite3
import os

from utc_time import get_utc_time, get_utc_date
from config import ICAO, AIRPORT_NAME

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, "aoms.db")


def dashboard():

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    # =============================================
    # إحصائيات الرحلات الكلية
    # =============================================
    cursor.execute("SELECT COUNT(*) FROM flights")
    total = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM flights WHERE departure=?", (ICAO,))
    departures = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM flights WHERE destination=?", (ICAO,))
    arrivals = cursor.fetchone()[0]

    # =============================================
    # إحصائيات المدارج
    # =============================================
    cursor.execute("""
        SELECT COUNT(*)
        FROM runways
        WHERE status='OCCUPIED'
    """)
    occupied_runways = cursor.fetchone()[0]

    cursor.execute("""
        SELECT runway, status
        FROM runways
        WHERE status='OCCUPIED'
        LIMIT 1
    """)
    runway = cursor.fetchone()

    if runway:
        active_runway = runway[0]
        runway_status = runway[1]
    else:
        active_runway = "NONE"
        runway_status = "AVAILABLE"

    # =============================================
    # إحصائيات الرحلات حسب الحالة
    # =============================================
    cursor.execute("""
        SELECT COUNT(*)
        FROM flights
        WHERE status='SCHEDULED'
    """)
    scheduled = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*)
        FROM flights
        WHERE status='BOARDING'
    """)
    boarding = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*)
        FROM flights
        WHERE status='DEPARTED'
    """)
    departed = cursor.fetchone()[0]

    # =============================================
    # آخر 5 رحلات
    # =============================================
    cursor.execute("""
        SELECT flight_number,
               departure,
               destination,
               status,
               runway,
               etd
        FROM flights
        ORDER BY id DESC
        LIMIT 5
    """)
    flights = cursor.fetchall()

    conn.close()

    # =============================================
    # عرض DASHBOARD
    # =============================================
    print("\n" + "=" * 70)
    print(" " * 20 + "AIRPORT DASHBOARD")
    print("=" * 70)
    print(f" Airport      : {AIRPORT_NAME}")
    print(f" ICAO         : {ICAO}")
    print(f" UTC          : {get_utc_time()}")
    print(f" Date         : {get_utc_date()}")
    print("-" * 70)

    # إحصائيات الرحلات
    print(f" Total Flights : {total}")
    print(f" Departures   : {departures}")
    print(f" Arrivals     : {arrivals}")
    print("-" * 70)

    # إحصائيات المدارج
    print(f" Occupied Runways : {occupied_runways}")
    print(f" Active Runway    : {active_runway}")
    print(f" Runway Status    : {runway_status}")
    print("-" * 70)

    # إحصائيات الحالات
    print(f" Scheduled    : {scheduled}")
    print(f" Boarding     : {boarding}")
    print(f" Departed     : {departed}")
    print("-" * 70)

    # آخر 5 رحلات
    print(" LAST 5 FLIGHTS")
    print("-" * 70)

    if not flights:
        print(" " * 25 + "No Flights")
    else:
        for flight in flights:
            print("-" * 70)
            print(f" Flight : {flight[0]}")
            print(f" Route  : {flight[1]} → {flight[2]}")
            print(f" Status : {flight[3]}")
            print(f" Runway : {flight[4]}")
            print(f" ETD    : {flight[5]}")

    print("-" * 70)
    print(" Airport Status : OPERATIONAL")
    print("=" * 70)
    print()
