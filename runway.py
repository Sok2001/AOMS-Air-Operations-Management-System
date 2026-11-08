"""
Runway Management Module
DAAG - Algiers International Airport
"""

import sqlite3
import os

from database import get_connection
from logs import add_log
from utc_time import get_utc_datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, "aoms.db")


# =============================================
# CONSTANTS
# =============================================

# DAAG Runways (المدارج الصحيحة لمطار هواري بومدين)
VALID_RUNWAYS = ["05", "23", "09", "27"]

# Runway statuses
RUNWAY_STATUSES = ["AVAILABLE", "OCCUPIED", "CLOSED", "MAINTENANCE"]


def connect():
    """Create a database connection"""
    return sqlite3.connect(DATABASE)


def init_runways():
    """Initialize runways table if empty"""
    conn = connect()
    cursor = conn.cursor()

    # Check if runways exist
    cursor.execute("SELECT COUNT(*) FROM runways")
    count = cursor.fetchone()[0]

    if count == 0:
        # Insert DAAG runways
        runways = [
            ("05", "AVAILABLE"),
            ("23", "AVAILABLE"),
            ("09", "AVAILABLE"),
            ("27", "AVAILABLE")
        ]
        cursor.executemany("INSERT INTO runways (runway, status) VALUES (?, ?)", runways)
        conn.commit()
        print("✓ Runways initialized for DAAG")

    conn.close()


def show_runways():
    """Display all runways with their status"""
    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT runway, status
        FROM runways
        ORDER BY runway
    """)

    rows = cursor.fetchall()
    conn.close()

    print("\n" + "=" * 33)
    print("   RUNWAY MANAGEMENT")
    print("   DAAG - ALGIERS")
    print("=" * 33)
    print("  RWY 05/23 : 3500m x 60m (BITUMINOUS CONCRETE)")
    print("  RWY 09/27 : 3500m x 45m (BITUMINOUS CONCRETE)")
    print("-" * 33)
    print("  STATUS:")

    if not rows:
        print("  No runways found.")
        return

    for row in rows:
        if row[1] == "AVAILABLE":
            status_display = "✅ AVAILABLE"
        elif row[1] == "OCCUPIED":
            status_display = "🔴 OCCUPIED"
        elif row[1] == "CLOSED":
            status_display = "🚫 CLOSED"
        elif row[1] == "MAINTENANCE":
            status_display = "🛠️ MAINTENANCE"
        else:
            status_display = f"❓ {row[1]}"

        print(f"  RWY {row[0]} : {status_display}")

    print("=" * 33)


def occupy_runway():
    """Occupy a runway"""
    print("\n" + "=" * 33)
    print("   OCCUPY RUNWAY")
    print("   DAAG - ALGIERS")
    print("=" * 33)
    print(" Valid Runways: 05, 23, 09, 27")

    runway = input(" Runway : ").upper()

    if runway not in VALID_RUNWAYS:
        print(" ✗ Invalid Runway for DAAG.")
        print("   Please enter: 05, 23, 09, or 27")
        return

    conn = connect()
    cursor = conn.cursor()

    # Check if runway exists
    cursor.execute("SELECT status FROM runways WHERE runway=?", (runway,))
    row = cursor.fetchone()

    if row is None:
        print(" ✗ Runway not found in database.")
        conn.close()
        return

    if row[0] == "OCCUPIED":
        print(f" ✗ Runway {runway} is already OCCUPIED.")
        conn.close()
        return

    # Update status
    cursor.execute("UPDATE runways SET status='OCCUPIED' WHERE runway=?", (runway,))
    conn.commit()
    conn.close()

    print(f"\n ✓ Runway {runway} is now OCCUPIED.")

    # Add to logs
    add_log(
        get_utc_datetime(),
        "Administrator",
        "OCCUPY RUNWAY",
        runway
    )


def release_runway():
    """Release a runway"""
    print("\n" + "=" * 33)
    print("   RELEASE RUNWAY")
    print("   DAAG - ALGIERS")
    print("=" * 33)
    print(" Valid Runways: 05, 23, 09, 27")

    runway = input(" Runway : ").upper()

    if runway not in VALID_RUNWAYS:
        print(" ✗ Invalid Runway for DAAG.")
        print("   Please enter: 05, 23, 09, or 27")
        return

    conn = connect()
    cursor = conn.cursor()

    # Check if runway exists
    cursor.execute("SELECT status FROM runways WHERE runway=?", (runway,))
    row = cursor.fetchone()

    if row is None:
        print(" ✗ Runway not found in database.")
        conn.close()
        return

    if row[0] == "AVAILABLE":
        print(f" ✗ Runway {runway} is already AVAILABLE.")
        conn.close()
        return

    # Update status
    cursor.execute("UPDATE runways SET status='AVAILABLE' WHERE runway=?", (runway,))
    conn.commit()
    conn.close()

    print(f"\n ✓ Runway {runway} is now AVAILABLE.")

    # Add to logs
    add_log(
        get_utc_datetime(),
        "Administrator",
        "RELEASE RUNWAY",
        runway
    )


# =============================================
# دوال إضافية للاستخدام مع قاعدة البيانات
# =============================================

def get_runway_status(runway):
    """Get status of a specific runway"""
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("SELECT status FROM runways WHERE runway=?", (runway.upper(),))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None


def get_available_runways():
    """Get all available runways"""
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT runway
        FROM runways
        WHERE status='AVAILABLE'
        ORDER BY runway
    """)
    rows = cursor.fetchall()
    conn.close()
    return [row[0] for row in rows]


def get_occupied_runways():
    """Get all occupied runways"""
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT runway
        FROM runways
        WHERE status='OCCUPIED'
        ORDER BY runway
    """)
    rows = cursor.fetchall()
    conn.close()
    return [row[0] for row in rows]


def count_available_runways():
    """Count available runways"""
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM runways WHERE status='AVAILABLE'")
    count = cursor.fetchone()[0]
    conn.close()
    return count


def count_occupied_runways():
    """Count occupied runways"""
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM runways WHERE status='OCCUPIED'")
    count = cursor.fetchone()[0]
    conn.close()
    return count


def get_active_runway():
    """Get the currently active (occupied) runway"""
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT runway
        FROM runways
        WHERE status='OCCUPIED'
        LIMIT 1
    """)
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None


def close_runway(runway):
    """Close a runway (maintenance)"""
    if runway not in VALID_RUNWAYS:
        return False, "Invalid runway"

    conn = connect()
    cursor = conn.cursor()
    cursor.execute("UPDATE runways SET status='CLOSED' WHERE runway=?", (runway,))
    conn.commit()
    conn.close()

    add_log(get_utc_datetime(), "Administrator", "CLOSE RUNWAY", runway)
    return True, f"Runway {runway} closed for maintenance"


def open_runway(runway):
    """Open a closed runway"""
    if runway not in VALID_RUNWAYS:
        return False, "Invalid runway"

    conn = connect()
    cursor = conn.cursor()
    cursor.execute("UPDATE runways SET status='AVAILABLE' WHERE runway=?", (runway,))
    conn.commit()
    conn.close()

    add_log(get_utc_datetime(), "Administrator", "OPEN RUNWAY", runway)
    return True, f"Runway {runway} is now available"
