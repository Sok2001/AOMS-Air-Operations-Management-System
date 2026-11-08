"""
Logs Module
"""

from database import get_connection


def add_log(utc_time, username, action, details=""):
    """Add an entry to the system log"""
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO logs (utc_time, username, action, details) VALUES (?, ?, ?, ?)",
            (utc_time, username, action, details),
        )
        conn.commit()
    finally:
        conn.close()


def total_logs():
    conn = get_connection()
    try:
        return conn.execute("SELECT COUNT(*) FROM logs").fetchone()[0]
    finally:
        conn.close()


def get_logs(limit=100):
    conn = get_connection()
    try:
        return conn.execute(
            "SELECT id, utc_time, username, action, details FROM logs ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    finally:
        conn.close()


def show_logs(limit=50):
    rows = get_logs(limit)
    print("\n" + "=" * 70)
    print("      SYSTEM LOGS")
    print("=" * 70)
    if not rows:
        print("  No logs found.")
        return
    for r in rows:
        print(f"  {r[1]} | {r[2]:<12} | {r[3]:<18} | {r[4]}")
    print("=" * 70)


def clear_logs():
    conn = get_connection()
    try:
        conn.execute("DELETE FROM logs")
        conn.commit()
    finally:
        conn.close()
