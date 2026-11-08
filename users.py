"""
User Management Module
"""

import sqlite3

from auth import hash_password, require_role, count_administrators, is_strong_password, secure_input
from database import get_connection
from logs import add_log
from utc_time import get_utc_datetime

# Roles and their display names
ROLES = [
    "Administrator",
    "ATC Supervisor",
    "Tower Controller",
    "Ground Controller",
    "Approach Controller",
    "Observer",
    "Maintenance"
]


def get_roles_display():
    """Get roles for display in menus"""
    return ROLES


@require_role("Administrator")
def add_user(current_user):
    """Add a new user"""
    print("\n" + "=" * 33)
    print("        ADD NEW USER")
    print("=" * 33)

    username = input(" Username : ").strip()
    if not username:
        print(" ✗ Username is required.")
        return

    full_name = input(" Full Name : ").strip()

    # Password with strength check
    while True:
        password = secure_input(" Password : ").strip()
        if len(password) < 6:
            print(" ✗ Password must be at least 6 characters.")
            continue

        is_strong, msg = is_strong_password(password)
        if not is_strong:
            print(f" ✗ {msg}")
            continue

        confirm = secure_input(" Confirm Password : ").strip()
        if password != confirm:
            print(" ✗ Passwords do not match.")
            continue
        break

    # Display available roles
    print("\n Available Roles:")
    for i, role in enumerate(get_roles_display(), 1):
        print(f"   {i}. {role}")

    role_choice = input("\n Select role (1-7) : ").strip()
    try:
        role = get_roles_display()[int(role_choice) - 1]
    except (ValueError, IndexError):
        print(" ✗ Invalid role selection.")
        return

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO users (username, password, full_name, role, active)
            VALUES (?, ?, ?, ?, ?)
        """, (username, hash_password(password), full_name, role, 1))

        conn.commit()
        print(f"\n ✓ User {username} added successfully.")

        add_log(
            get_utc_datetime(),
            current_user["username"],
            "USER CREATED",
            f"Added user {username} ({role})"
        )

    except sqlite3.IntegrityError:
        print(f"\n ✗ Username '{username}' already exists.")
    finally:
        conn.close()


@require_role("ATC Supervisor")
def show_users(current_user):
    """Display all users"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, username, full_name, role, active, last_login
        FROM users
        ORDER BY id
    """)

    rows = cursor.fetchall()
    conn.close()

    print("\n" + "=" * 33)
    print("          USERS LIST")
    print("=" * 33)

    if not rows:
        print("  No users found.")
        return

    print(f"\n  Total Users: {len(rows)}\n")

    for idx, row in enumerate(rows, 1):
        print("-" * 33)
        print(f"  #{idx}")
        print(f"  Username    : {row[1]}")
        print(f"  Full Name   : {row[2]}")
        print(f"  Role        : {row[3]}")
        print(f"  Status      : {'ACTIVE' if row[4] == 1 else 'INACTIVE'}")
        print(f"  Last Login  : {row[5] or 'Never'}")


@require_role("Administrator")
def delete_user(current_user):
    """Delete a user"""
    username = input(" Username to delete : ").strip()

    if username == current_user["username"]:
        print(" ✗ Cannot delete yourself.")
        return

    # Check if this is the last administrator
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT role FROM users WHERE username=?", (username,))
    row = cursor.fetchone()
    conn.close()

    if row and row[0] == "Administrator":
        admin_count = count_administrators()
        if admin_count <= 1:
            print(" ✗ Cannot delete the last administrator.")
            return

    confirm = input(f" Delete user '{username}'? (y/n) : ")
    if confirm.lower() != 'y':
        print(" Deletion cancelled.")
        return

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM users WHERE username=?", (username,))
    conn.commit()
    affected = cursor.rowcount
    conn.close()

    if affected == 0:
        print(" ✗ User not found.")
    else:
        print(f" ✓ User {username} deleted.")
        add_log(
            get_utc_datetime(),
            current_user["username"],
            "USER DELETED",
            f"Deleted user {username}"
        )


@require_role("Administrator")
def edit_user(current_user):
    """Edit a user's details"""
    username = input(" Username to edit : ").strip()

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id, full_name, role, active FROM users WHERE username=?", (username,))
    row = cursor.fetchone()

    if row is None:
        print(" ✗ User not found.")
        conn.close()
        return

    print("\n" + "=" * 33)
    print("          EDIT USER")
    print("=" * 33)
    print(f"  Current Full Name : {row[1]}")
    print(f"  Current Role      : {row[2]}")
    print(f"  Current Status    : {'ACTIVE' if row[3] == 1 else 'INACTIVE'}")
    print("=" * 33)

    full_name = input(f" Full Name [{row[1]}] : ").strip() or row[1]

    print("\n Available Roles:")
    for i, role in enumerate(get_roles_display(), 1):
        print(f"   {i}. {role}")

    role_choice = input(f"\n Select role [1-{len(get_roles_display())}] : ").strip()
    try:
        if role_choice:
            role = get_roles_display()[int(role_choice) - 1]
        else:
            role = row[2]
    except (ValueError, IndexError):
        role = row[2]

    # Prevent demoting last administrator
    if row[2] == "Administrator" and role != "Administrator":
        admin_count = count_administrators()
        if admin_count <= 1:
            print(" ✗ Cannot demote the last administrator.")
            conn.close()
            return

    active_input = input(f" Active (y/n) [{('y' if row[3] == 1 else 'n')}] : ").lower()
    if active_input:
        active = 1 if active_input == 'y' else 0
    else:
        active = row[3]

    cursor.execute("""
        UPDATE users
        SET full_name=?, role=?, active=?
        WHERE username=?
    """, (full_name, role, active, username))

    conn.commit()
    conn.close()

    print(f"\n ✓ User {username} updated.")
    add_log(
        get_utc_datetime(),
        current_user["username"],
        "USER UPDATED",
        f"Updated user {username} to role {role}"
    )
