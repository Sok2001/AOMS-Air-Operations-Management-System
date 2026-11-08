"""
Change Password Script
"""

import sqlite3
import hashlib

from database import DATABASE

def hash_password(password):
    """Hash password using SHA256"""
    return hashlib.sha256(password.encode()).hexdigest()

def change_password():
    """Change user password"""
    print("\n" + "=" * 42)
    print("     CHANGE PASSWORD")
    print("=" * 42)

    username = input(" Username : ").strip()
    new_password = input(" New Password : ").strip()
    confirm = input(" Confirm Password : ").strip()

    if new_password != confirm:
        print(" ✗ Passwords do not match.")
        return

    if len(new_password) < 6:
        print(" ✗ Password must be at least 6 characters.")
        return

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    # Check if user exists
    cursor.execute("SELECT id FROM users WHERE username=?", (username,))
    user = cursor.fetchone()

    if user is None:
        print(f" ✗ User '{username}' not found.")
        conn.close()
        return

    # Update password
    hashed = hash_password(new_password)
    cursor.execute("UPDATE users SET password=? WHERE username=?", (hashed, username))
    conn.commit()
    conn.close()

    print(f"\n ✓ Password changed successfully for '{username}'!")

if __name__ == "__main__":
    change_password()
