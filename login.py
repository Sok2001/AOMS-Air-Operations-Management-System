"""
Login Module
"""

import sqlite3
import os
from datetime import datetime, timezone

from auth import check_session_timeout
from logs import add_log
from utc_time import get_utc_datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, "aoms.db")

# Global current user
CURRENT_USER = None


def login():
    """Authenticate user"""
    global CURRENT_USER

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    print("\n" + "=" * 62)
    print("            AIRPORT OPERATIONS MANAGEMENT SYSTEM")
    print("                      LOGIN")
    print("=" * 62)

    username = input("\n👤 Username : ").strip()
    password = input("🔑 Password : ").strip()

    # Get user from database with hashed password
    cursor.execute("""
        SELECT full_name, role, username, password
        FROM users
        WHERE username=?
    """, (username,))

    user = cursor.fetchone()

    if user:
        # Verify password using auth.py
        from auth import verify_password
        if verify_password(password, user[3]):
            utc = get_utc_datetime()

            cursor.execute("""
                UPDATE users
                SET last_login=?
                WHERE username=?
            """, (utc, username))

            conn.commit()
            conn.close()

            # Store current user
            CURRENT_USER = {
                'full_name': user[0],
                'role': user[1],
                'username': user[2],
                'last_activity': datetime.now()
            }

            print("\n" + "=" * 62)
            print(" ✅ ACCESS GRANTED")
            print("=" * 62)
            print(f" 👤 User : {user[0]}")
            print(f" 🔑 Role : {user[1]}")
            print(f" 🕐 UTC  : {utc}")
            print("=" * 62 + "\n")

            # Log login
            add_log(utc, user[2], "LOGIN", f"User {user[2]} logged in")

            return True
        else:
            conn.close()
            print("\n" + "=" * 62)
            print(" ❌ ACCESS DENIED - Invalid username or password")
            print("=" * 62 + "\n")
            return False
    else:
        conn.close()
        print("\n" + "=" * 62)
        print(" ❌ ACCESS DENIED - Invalid username or password")
        print("=" * 62 + "\n")
        return False


def get_current_user():
    """Get current logged in user"""
    global CURRENT_USER

    # Check session timeout
    if CURRENT_USER and check_session_timeout(CURRENT_USER):
        print("\n ⚠️ Session expired. Please login again.")
        logout()
        return None

    return CURRENT_USER


def is_logged_in():
    """Check if user is logged in"""
    return CURRENT_USER is not None


def logout():
    """Logout current user"""
    global CURRENT_USER

    if CURRENT_USER:
        add_log(
            get_utc_datetime(),
            CURRENT_USER["username"],
            "LOGOUT",
            f"User {CURRENT_USER['username']} logged out"
        )

    CURRENT_USER = None
    print("\n👋 Logged out successfully\n")
