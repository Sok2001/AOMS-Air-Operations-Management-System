"""
Airport Statistics Module
"""

import sqlite3
import os

from flight import get_flight_count, get_departure_flights, get_arrival_flights
from logs import total_logs
from runway import count_available_runways, count_occupied_runways, get_active_runway
from database import DATABASE, get_connection

from database import DATABASE


def connect():
    return sqlite3.connect(DATABASE)


def airport_statistics():
    """Display airport statistics"""

    print("\n" + "=" * 50)
    print("     AIRPORT STATISTICS")
    print("     DAAG - ALGIERS")
    print("=" * 50)

    # Flight statistics
    total = get_flight_count()
    departures = len(get_departure_flights())
    arrivals = len(get_arrival_flights())

    print("\n  FLIGHT STATISTICS")
    print("-" * 50)
    print(f"  Total Flights      : {total}")
    print(f"  Departure Flights  : {departures}")
    print(f"  Arrival Flights    : {arrivals}")

    # Runway statistics
    available = count_available_runways()
    occupied = count_occupied_runways()
    active = get_active_runway()

    print("\n  RUNWAY STATISTICS")
    print("-" * 50)
    print(f"  Available Runways  : {available}")
    print(f"  Occupied Runways   : {occupied}")
    print(f"  Active Runway      : {active if active else 'None'}")

    # Flight status statistics
    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT status, COUNT(*)
        FROM flights
        GROUP BY status
        ORDER BY status
    """)

    status_rows = cursor.fetchall()
    conn.close()

    print("\n  FLIGHT STATUS BREAKDOWN")
    print("-" * 50)

    if status_rows:
        for status, count in status_rows:
            print(f"  {status:<12} : {count}")
    else:
        print("  No flights found.")

    # Log statistics
    log_count = total_logs()

    print("\n  SYSTEM STATISTICS")
    print("-" * 50)
    print(f"  Total Log Entries  : {log_count}")

    print("=" * 50)


def get_flight_status_breakdown():
    """Get breakdown of flights by status"""
    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT status, COUNT(*)
        FROM flights
        GROUP BY status
        ORDER BY status
    """)

    rows = cursor.fetchall()
    conn.close()
    return rows


def get_daily_statistics():
    """Get statistics for today"""
    from utc_time import get_utc_date

    today = get_utc_date()

    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT COUNT(*)
        FROM flights
        WHERE created_utc LIKE ?
    """, (today + '%',))

    today_flights = cursor.fetchone()[0]
    conn.close()

    return {
        'date': today,
        'flights_today': today_flights
    }


def show_detailed_statistics():
    """Show detailed airport statistics with more information"""
    print("\n" + "=" * 60)
    print("     DETAILED AIRPORT STATISTICS")
    print("     DAAG - ALGIERS")
    print("=" * 60)

    # Basic stats
    airport_statistics()

    # Additional stats
    conn = connect()
    cursor = conn.cursor()

    # Busiest routes
    print("\n  BUSIEST ROUTES")
    print("-" * 60)

    cursor.execute("""
        SELECT departure, destination, COUNT(*) as count
        FROM flights
        GROUP BY departure, destination
        ORDER BY count DESC
        LIMIT 5
    """)

    routes = cursor.fetchall()
    if routes:
        for dep, dest, count in routes:
            print(f"  {dep} → {dest} : {count} flights")
    else:
        print("  No routes data available.")

    # Most common airlines
    print("\n  MOST COMMON AIRLINES")
    print("-" * 60)

    cursor.execute("""
        SELECT airline, COUNT(*) as count
        FROM flights
        GROUP BY airline
        ORDER BY count DESC
        LIMIT 5
    """)

    airlines = cursor.fetchall()
    if airlines:
        for airline, count in airlines:
            print(f"  {airline:<6} : {count} flights")
    else:
        print("  No airline data available.")

    conn.close()
    print("=" * 60)


def show_statistics_menu():
    """Show statistics menu"""
    while True:
        print("\n" + "=" * 50)
        print("     STATISTICS MENU")
        print("=" * 50)
        print(" 1. Basic Statistics")
        print(" 2. Detailed Statistics")
        print(" 3. Flight Status Breakdown")
        print(" 4. Today's Statistics")
        print(" 0. Back")
        print("-" * 50)

        choice = input(" Choice : ")

        if choice == "1":
            airport_statistics()

        elif choice == "2":
            show_detailed_statistics()

        elif choice == "3":
            breakdown = get_flight_status_breakdown()
            print("\n  FLIGHT STATUS BREAKDOWN")
            print("-" * 50)
            if breakdown:
                for status, count in breakdown:
                    print(f"  {status:<12} : {count}")
            else:
                print("  No flights found.")

        elif choice == "4":
            daily = get_daily_statistics()
            print("\n  TODAY'S STATISTICS")
            print("-" * 50)
            print(f"  Date            : {daily['date']}")
            print(f"  Flights Today   : {daily['flights_today']}")

        elif choice == "0":
            break

        else:
            print(" Invalid Choice")
