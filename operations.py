"""
Flight Progress Module
"""

import sqlite3
import os

from flight import flight_exists, update_flight_status, get_flight_by_number
from logs import add_log
from utc_time import get_utc_datetime

from database import DATABASE


# Flight phases in order
FLIGHT_PHASES = [
    "SCHEDULED",
    "BOARDING",
    "PUSHBACK",
    "STARTUP",
    "TAXI",
    "LINE UP",
    "TAKEOFF",
    "AIRBORNE",
    "ARRIVING",
    "LANDED",
    "PARKED",
    "CANCELLED",
    "DELAYED"
]

# Phase display names
PHASE_DISPLAY = {
    "SCHEDULED": "Flight Plan Filed",
    "BOARDING": "Boarding",
    "PUSHBACK": "Pushback",
    "STARTUP": "Startup Approved",
    "TAXI": "Taxi",
    "LINE UP": "Line Up",
    "TAKEOFF": "Takeoff",
    "AIRBORNE": "Airborne",
    "ARRIVING": "Approach",
    "LANDED": "Landed",
    "PARKED": "On Block - Flight Completed",
    "CANCELLED": "Cancelled",
    "DELAYED": "Delayed"
}


def connect():
    return sqlite3.connect(DATABASE)


def initialize_flight(flight_number):
    """Initialize flight with SCHEDULED status"""
    if flight_exists(flight_number):
        current = get_flight_by_number(flight_number)
        if current:
            status = current[16] if len(current) > 16 else None
            if not status or status == "":
                update_flight_status(flight_number, "SCHEDULED")
                return True
    return False


def show_status(flight_number):
    """Show current status of a flight"""
    if not flight_exists(flight_number):
        print("✗ Flight Not Found")
        return

    flight = get_flight_by_number(flight_number)
    if not flight:
        print("✗ Error retrieving flight data")
        return

    # flight structure: (id, flight_number, airline, registration, aircraft,
    # wake, departure, destination, sid, star, runway, stand, etd, eta,
    # flight_level, speed, squawk, status, created_utc)

    status = flight[17] if len(flight) > 17 else "UNKNOWN"

    print("\n" + "=" * 42)
    print("      FLIGHT PROGRESS")
    print("=" * 42)
    print(f"  Flight      : {flight[1]}")
    print(f"  Airline     : {flight[2]}")
    print(f"  Aircraft    : {flight[4]}")
    print(f"  Departure   : {flight[6]}")
    print(f"  Destination : {flight[7]}")
    print(f"  ETD         : {flight[12]}")
    print(f"  ETA         : {flight[13]}")
    print(f"  Runway      : {flight[10]}")
    print("-" * 42)
    print(f"  Status      : {PHASE_DISPLAY.get(status, status)}")
    print("=" * 42)


def next_phase(flight_number):
    """Move flight to next phase"""
    if not flight_exists(flight_number):
        print("✗ Flight Not Found")
        return

    flight = get_flight_by_number(flight_number)
    if not flight:
        print("✗ Error retrieving flight data")
        return

    current_status = flight[17] if len(flight) > 17 else "SCHEDULED"

    # Find current index
    try:
        current_index = FLIGHT_PHASES.index(current_status)
    except ValueError:
        current_index = 0

    # Move to next phase if not at the end
    if current_index < len(FLIGHT_PHASES) - 1:
        next_status = FLIGHT_PHASES[current_index + 1]
        update_flight_status(flight_number, next_status)
        print(f"\n✓ Phase Updated")
        print(f"   {PHASE_DISPLAY.get(current_status, current_status)} → {PHASE_DISPLAY.get(next_status, next_status)}")

        # Add to logs
        add_log(
            get_utc_datetime(),
            "Administrator",
            "PROGRESS UPDATE",
            f"{flight_number} → {next_status}"
        )
    else:
        print(f"\n✓ Flight {flight_number} has reached final phase: {PHASE_DISPLAY.get(current_status, current_status)}")


def previous_phase(flight_number):
    """Move flight to previous phase"""
    if not flight_exists(flight_number):
        print("✗ Flight Not Found")
        return

    flight = get_flight_by_number(flight_number)
    if not flight:
        print("✗ Error retrieving flight data")
        return

    current_status = flight[17] if len(flight) > 17 else "SCHEDULED"

    # Find current index
    try:
        current_index = FLIGHT_PHASES.index(current_status)
    except ValueError:
        current_index = 0

    # Move to previous phase if not at the beginning
    if current_index > 0:
        prev_status = FLIGHT_PHASES[current_index - 1]
        update_flight_status(flight_number, prev_status)
        print(f"\n✓ Phase Reverted")
        print(f"   {PHASE_DISPLAY.get(current_status, current_status)} → {PHASE_DISPLAY.get(prev_status, prev_status)}")

        # Add to logs
        add_log(
            get_utc_datetime(),
            "Administrator",
            "PROGRESS REVERT",
            f"{flight_number} → {prev_status}"
        )
    else:
        print(f"\n✗ Flight {flight_number} is at the first phase: {PHASE_DISPLAY.get(current_status, current_status)}")


def get_all_flights_progress():
    """Get progress status for all flights"""
    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT flight_number, status, etd, departure, destination
        FROM flights
        ORDER BY etd
    """)

    rows = cursor.fetchall()
    conn.close()

    print("\n" + "=" * 50)
    print("      ALL FLIGHTS PROGRESS")
    print("=" * 50)

    if not rows:
        print("  No flights found.")
        return

    print(f"\n  Total Flights: {len(rows)}\n")

    for idx, row in enumerate(rows, 1):
        print("-" * 50)
        print(f"  #{idx}")
        print(f"  Flight      : {row[0]}")
        print(f"  Status      : {PHASE_DISPLAY.get(row[1], row[1])}")
        print(f"  ETD         : {row[2]}")
        print(f"  Route       : {row[3]} → {row[4]}")


def update_status():
    """Main function to update flight progress - called from main menu"""
    print("\n" + "=" * 42)
    print("     FLIGHT PROGRESS UPDATE")
    print("=" * 42)

    while True:
        print("\n 1. Show Flight Status")
        print(" 2. Next Phase")
        print(" 3. Previous Phase")
        print(" 4. Show All Flights")
        print(" 0. Back")
        print("-" * 42)

        choice = input(" Choice : ")

        if choice == "1":
            flight = input(" Flight Number : ").upper()
            show_status(flight)

        elif choice == "2":
            flight = input(" Flight Number : ").upper()
            next_phase(flight)

        elif choice == "3":
            flight = input(" Flight Number : ").upper()
            previous_phase(flight)

        elif choice == "4":
            get_all_flights_progress()

        elif choice == "0":
            break

        else:
            print(" Invalid Choice")


# =============================================
# FLIGHT PHASE HELPERS
# =============================================

def get_phase_display(status):
    """Get display name for a status"""
    return PHASE_DISPLAY.get(status, status)


def get_next_status(current_status):
    """Get next status in the sequence"""
    try:
        current_index = FLIGHT_PHASES.index(current_status)
        if current_index < len(FLIGHT_PHASES) - 1:
            return FLIGHT_PHASES[current_index + 1]
        return current_status
    except ValueError:
        return "SCHEDULED"


def get_previous_status(current_status):
    """Get previous status in the sequence"""
    try:
        current_index = FLIGHT_PHASES.index(current_status)
        if current_index > 0:
            return FLIGHT_PHASES[current_index - 1]
        return current_status
    except ValueError:
        return "SCHEDULED"
