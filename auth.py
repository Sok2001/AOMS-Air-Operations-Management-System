"""
Authentication Module
"""

import hashlib
import sqlite3
from datetime import datetime, timedelta
import random
import string
import socket
import re

from database import get_connection
from logs import add_log
from utc_time import get_utc_datetime

# Maximum login attempts
MAX_ATTEMPTS = 5
LOCK_DURATION = 30  # minutes
SESSION_TIMEOUT = 15  # minutes


def hash_password(password):
    """Hash password using SHA256"""
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(password, hashed):
    """Verify password against hash"""
    return hash_password(password) == hashed


def generate_captcha():
    """Generate a 5-character CAPTCHA"""
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choices(chars, k=5))


def is_strong_password(password):
    """Check if password meets strength requirements"""
    if len(password) < 8:
        return False, "Password must be at least 8 characters long."
    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter."
    if not re.search(r"[a-z]", password):
        return False, "Password must contain at least one lowercase letter."
    if not re.search(r"\d", password):
        return False, "Password must contain at least one digit."
    if not re.search(r"[!@#$%^&*()_+\-=\[\]{};:'\"\\|,.<>/?]", password):
        return False, "Password must contain at least one special character."
    return True, "Password is strong."


def secure_input(prompt):
    """Secure input that works on all platforms"""
    try:
        from getpass import getpass
        return getpass(prompt)
    except Exception:
        return input(prompt)


def login():
    """Authenticate user"""
    print("\n" + "=" * 42)
    print(" AIRPORT OPERATIONS MANAGEMENT SYSTEM")
    print("                LOGIN")
    print("=" * 42)

    username = input(" Username : ").strip()
    password = secure_input(" Password : ").strip()

    conn = get_connection()
    cursor = conn.cursor()

    # Get user from database
    cursor.execute("""
        SELECT id, username, password, full_name, role, active,
               login_attempts, locked_until
        FROM users
        WHERE username=?
    """, (username,))

    user = cursor.fetchone()

    if user is None:
        print("\n ✗ Invalid username or password.")
        add_log(get_utc_datetime(), username, "LOGIN FAILED", f"Failed login attempt for {username}")
        conn.close()
        return None

    user_id, db_username, db_password, full_name, role, active, attempts, locked_until = user

    # Check if account is locked
    if locked_until:
        lock_time = datetime.strptime(locked_until, "%Y-%m-%d %H:%M:%S")
        if datetime.now() < lock_time:
            remaining = (lock_time - datetime.now()).seconds // 60
            print(f"\n ✗ Account is locked. Try again in {remaining} minutes.")
            add_log(get_utc_datetime(), db_username, "ACCOUNT LOCKED",
                    f"Account locked for {remaining} minutes")
            conn.close()
            return None
        else:
            # Reset lock if time passed
            cursor.execute("""
                UPDATE users
                SET locked_until=NULL, login_attempts=0
                WHERE id=?
            """, (user_id,))
            conn.commit()

    # Check if account is active
    if active == 0:
        print("\n ✗ Account is deactivated. Contact administrator.")
        conn.close()
        return None

    # Verify password
    if not verify_password(password, db_password):
        attempts += 1
        remaining = MAX_ATTEMPTS - attempts

        # CAPTCHA after 3 attempts
        if attempts >= 3:
            captcha = generate_captcha()
            print(f"\n 🔐 Verification Code : {captcha}")
            user_input = input(" Enter verification code : ").strip()
            if user_input.upper() != captcha:
                print("\n ✗ Invalid verification code.")
                add_log(get_utc_datetime(), db_username, "LOGIN FAILED",
                        "Invalid CAPTCHA")
                conn.close()
                return None

        if attempts >= MAX_ATTEMPTS:
            # Lock account
            lock_time = datetime.now() + timedelta(minutes=LOCK_DURATION)
            cursor.execute("""
                UPDATE users
                SET locked_until=?, login_attempts=?
                WHERE id=?
            """, (lock_time.strftime("%Y-%m-%d %H:%M:%S"), attempts, user_id))
            conn.commit()
            print(f"\n ✗ Account locked for {LOCK_DURATION} minutes.")
            add_log(get_utc_datetime(), db_username, "ACCOUNT LOCKED",
                    f"Account locked after {attempts} failed attempts")
        else:
            cursor.execute("UPDATE users SET login_attempts=? WHERE id=?", (attempts, user_id))
            conn.commit()
            print(f"\n ✗ Invalid password. {remaining} attempts remaining.")
            add_log(get_utc_datetime(), db_username, "LOGIN FAILED",
                    f"Invalid password. {remaining} attempts remaining")

        conn.close()
        return None

    # Reset login attempts on success
    cursor.execute("""
        UPDATE users
        SET login_attempts=0, locked_until=NULL, last_login=?
        WHERE id=?
    """, (get_utc_datetime(), user_id))
    conn.commit()
    conn.close()

    print("\n ✅ Access Granted")
    print(f"    Welcome : {full_name}")
    print(f"    Role    : {role}")
    print(f"    UTC     : {get_utc_datetime()}")

    # Log login with IP and Computer Name
    hostname = socket.gethostname()
    try:
        ip = socket.gethostbyname(hostname)
    except:
        ip = "127.0.0.1"

    add_log(
        get_utc_datetime(),
        db_username,
        "LOGIN",
        f"User {db_username} logged in from {hostname} ({ip})"
    )

    return {
        "id": user_id,
        "username": db_username,
        "full_name": full_name,
        "role": role,
        "last_activity": datetime.now()
    }


def check_session_timeout(current_user):
    """Check if session has timed out"""
    if current_user is None:
        return True

    last_activity = current_user.get("last_activity")
    if last_activity is None:
        return False

    elapsed = (datetime.now() - last_activity).seconds // 60
    if elapsed >= SESSION_TIMEOUT:
        return True

    # Update last activity
    current_user["last_activity"] = datetime.now()
    return False


def create_admin():
    """Create initial administrator account"""
    print("\n" + "=" * 42)
    print("    CREATE ADMINISTRATOR ACCOUNT")
    print("=" * 42)
    print("  First time setup - Create admin account")
    print("=" * 42)

    conn = get_connection()
    cursor = conn.cursor()

    # Check if any admin exists
    cursor.execute("SELECT COUNT(*) FROM users WHERE role='Administrator'")
    if cursor.fetchone()[0] > 0:
        print(" ✅ Administrator account already exists.")
        conn.close()
        return

    print("\n Please create the administrator account:\n")

    while True:
        username = input(" Username : ").strip()
        if not username:
            print(" ✗ Username cannot be empty.")
            continue
        if len(username) < 3:
            print(" ✗ Username must be at least 3 characters.")
            continue
        break

    while True:
        password = secure_input(" Password : ").strip()
        if not password:
            print(" ✗ Password cannot be empty.")
            continue

        # Check password strength
        is_strong, msg = is_strong_password(password)
        if not is_strong:
            print(f" ✗ {msg}")
            continue

        confirm = secure_input(" Confirm Password : ").strip()
        if password != confirm:
            print(" ✗ Passwords do not match.")
            continue
        break

    full_name = input(" Full Name : ").strip() or "Administrator"

    try:
        cursor.execute("""
            INSERT INTO users (username, password, full_name, role, active)
            VALUES (?, ?, ?, ?, ?)
        """, (username, hash_password(password), full_name, "Administrator", 1))

        conn.commit()
        print("\n ✅ Administrator account created successfully!")
        print(f"    Username : {username}")
        print(f"    Role     : Administrator")

        add_log(get_utc_datetime(), username, "USER CREATED",
                f"Administrator account created: {username}")

    except sqlite3.IntegrityError:
        print("\n ✗ Username already exists.")
    finally:
        conn.close()


def require_role(required_role):
    """Decorator to check user role"""
    def decorator(func):
        def wrapper(current_user, *args, **kwargs):
            if current_user is None:
                print("\n ✗ Please login first.")
                return None

            roles = {
                "Administrator": 6,
                "ATC Supervisor": 5,
                "Tower Controller": 4,
                "Ground Controller": 3,
                "Approach Controller": 2,
                "Observer": 1,
                "Maintenance": 0
            }

            if roles.get(current_user["role"], -1) < roles.get(required_role, -1):
                print(f"\n ✗ Access Denied. {required_role} role required.")
                return None

            return func(current_user, *args, **kwargs)
        return wrapper
    return decorator


def check_permission(current_user, action):
    """Check if user has permission for action"""
    if current_user is None:
        return False

    permissions = {
        "Administrator": ["*"],
        "ATC Supervisor": [
            "add_flight", "edit_flight", "delete_flight", "show_flights",
            "search_flight", "occupy_runway", "release_runway", "show_runways",
            "view_logs", "clear_logs", "dashboard", "statistics",
            "issue_clearance", "show_strip", "update_status", "airport_info",
            "metar", "live_flights", "add_user", "show_users", "edit_user",
            "backup", "restore", "ctot",
            "notam", "edit_notam", "capacity", "atfcm", "alerts", "ack_alerts", "ai_support",
            "charts", "edit_charts"
        ],
        "Tower Controller": [
            "show_flights", "search_flight", "show_runways",
            "occupy_runway", "release_runway", "show_strip",
            "update_status", "dashboard", "airport_info", "metar",
            "issue_clearance", "live_flights",
            "notam", "capacity", "atfcm", "alerts", "ack_alerts", "ai_support", "charts"
        ],
        "Ground Controller": [
            "show_flights", "search_flight", "show_runways",
            "show_strip", "update_status", "dashboard",
            "airport_info", "metar",
            "notam", "capacity", "alerts", "ack_alerts", "charts"
        ],
        "Approach Controller": [
            "show_flights", "search_flight", "show_runways",
            "dashboard", "airport_info", "metar", "live_flights",
            "notam", "capacity", "atfcm", "alerts", "ack_alerts", "ai_support", "charts"
        ],
        "Observer": [
            "show_flights", "search_flight", "show_runways",
            "dashboard", "airport_info", "metar",
            "notam", "capacity", "alerts", "charts"
        ],
        "Maintenance": [
            "show_runways", "dashboard", "airport_info",
            "notam", "alerts", "charts"
        ]
    }

    user_permissions = permissions.get(current_user["role"], [])
    return "*" in user_permissions or action in user_permissions


def count_administrators():
    """Count active administrators"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users WHERE role='Administrator' AND active=1")
    count = cursor.fetchone()[0]
    conn.close()
    return count
