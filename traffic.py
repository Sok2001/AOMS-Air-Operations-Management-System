"""
Traffic Management Module
"""

import sqlite3
import os

from config import ICAO
from flight import flight_exists, get_flight_by_number, update_flight_status
from logs import add_log
from utc_time import get_utc_datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, "aoms.db")


def connect():
    return sqlite3.connect(DATABASE)


def get_departure_queue():
    """Get all departing flights sorted by ETD"""
    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT flight_number, runway, etd, status, airline, destination
        FROM flights
        WHERE departure=? AND status NOT IN ('CANCELLED', 'DEPARTED', 'AIRBORNE')
        ORDER BY etd
    """, (ICAO,))

    rows = cursor.fetchall()
    conn.close()
    return rows


def get_arrival_queue():
    """Get all arriving flights sorted by ETA"""
    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT flight_number, runway, eta, status, airline, departure
        FROM flights
        WHERE destination=? AND status NOT IN ('CANCELLED', 'LANDED', 'PARKED')
        ORDER BY eta
    """, (ICAO,))

    rows = cursor.fetchall()
    conn.close()
    return rows


def show_departure_queue():
    """Display departure queue"""
    from config import ICAO

    print("\n" + "=" * 50)
    print("      DEPARTURE QUEUE")
    print("      DAAG - ALGIERS")
    print("=" * 50)

    flights = get_departure_queue()

    if not flights:
        print("\n  No departure flights.")
        return

    print(f"\n  Total: {len(flights)}\n")
    print("-" * 50)

    for idx, flight in enumerate(flights, 1):
        print(f"  {idx}. {flight[0]}")
        print(f"      Airline   : {flight[4]}")
        print(f"      Destination: {flight[5]}")
        print(f"      Runway    : {flight[1]}")
        print(f"      ETD       : {flight[2]}")
        print(f"      Status    : {flight[3]}")
        print()


def show_arrival_queue():
    """Display arrival queue"""
    from config import ICAO

    print("\n" + "=" * 50)
    print("       ARRIVAL QUEUE")
    print("       DAAG - ALGIERS")
    print("=" * 50)

    flights = get_arrival_queue()

    if not flights:
        print("\n  No arrival flights.")
        return

    print(f"\n  Total: {len(flights)}\n")
    print("-" * 50)

    for idx, flight in enumerate(flights, 1):
        print(f"  {idx}. {flight[0]}")
        print(f"      Airline   : {flight[4]}")
        print(f"      Departure : {flight[5]}")
        print(f"      Runway    : {flight[1]}")
        print(f"      ETA       : {flight[2]}")
        print(f"      Status    : {flight[3]}")
        print()


def add_to_departure_queue(flight_number):
    """Add a flight to departure queue"""
    if not flight_exists(flight_number):
        print("✗ Flight not found.")
        return False

    flight = get_flight_by_number(flight_number)
    if not flight:
        return False

    # flight[6] = departure, flight[7] = destination
    from config import ICAO
    if flight[6] != ICAO:
        print("✗ Flight is not departing from this airport.")
        return False

    update_flight_status(flight_number, "SCHEDULED")

    add_log(
        get_utc_datetime(),
        "Administrator",
        "ADD TO DEPARTURE QUEUE",
        flight_number
    )

    print(f"✓ {flight_number} added to departure queue.")
    return True


def add_to_arrival_queue(flight_number):
    """Add a flight to arrival queue"""
    if not flight_exists(flight_number):
        print("✗ Flight not found.")
        return False

    flight = get_flight_by_number(flight_number)
    if not flight:
        return False

    from config import ICAO
    if flight[7] != ICAO:
        print("✗ Flight is not arriving at this airport.")
        return False

    update_flight_status(flight_number, "ARRIVING")

    add_log(
        get_utc_datetime(),
        "Administrator",
        "ADD TO ARRIVAL QUEUE",
        flight_number
    )

    print(f"✓ {flight_number} added to arrival queue.")
    return True


def remove_from_queue(flight_number):
    """Remove a flight from queue"""
    if not flight_exists(flight_number):
        print("✗ Flight not found.")
        return False

    flight = get_flight_by_number(flight_number)
    if not flight:
        return False

    current_status = flight[17] if len(flight) > 17 else "SCHEDULED"

    if current_status in ["DEPARTED", "AIRBORNE", "LANDED", "PARKED", "CANCELLED"]:
        print(f"✗ Flight {flight_number} has already completed or is in progress.")
        return False

    add_log(
        get_utc_datetime(),
        "Administrator",
        "REMOVE FROM QUEUE",
        flight_number
    )

    print(f"✓ {flight_number} removed from queue.")
    return True


def show_traffic_menu():
    """Show traffic management menu"""
    while True:
        print("\n" + "=" * 50)
        print("     TRAFFIC MANAGEMENT")
        print("     DAAG - ALGIERS")
        print("=" * 50)
        print(" 1. Show Departure Queue")
        print(" 2. Show Arrival Queue")
        print(" 3. Add Flight to Departure Queue")
        print(" 4. Add Flight to Arrival Queue")
        print(" 5. Remove Flight from Queue")
        print(" 0. Back")
        print("-" * 50)

        choice = input(" Choice : ")

        if choice == "1":
            show_departure_queue()

        elif choice == "2":
            show_arrival_queue()

        elif choice == "3":
            flight = input(" Flight Number : ").upper()
            add_to_departure_queue(flight)

        elif choice == "4":
            flight = input(" Flight Number : ").upper()
            add_to_arrival_queue(flight)

        elif choice == "5":
            flight = input(" Flight Number : ").upper()
            remove_from_queue(flight)

        elif choice == "0":
            break

        else:
            print(" Invalid Choice")
