"""
Backup Module
"""

import os
import shutil
from datetime import datetime

from database import DATABASE
from app_paths import BACKUP_DIR



def create_backup():
    """Create a backup of the database"""
    # Create backup directory if it doesn't exist
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)

    # Generate backup filename
    date_str = datetime.now().strftime("%Y_%m_%d")
    backup_file = os.path.join(BACKUP_DIR, f"aoms_{date_str}.db")

    try:
        # Copy database file
        shutil.copy2(DATABASE, backup_file)
        print(f"✓ Backup created: {backup_file}")
        return True
    except Exception as e:
        print(f"✗ Backup failed: {e}")
        return False


def restore_backup(backup_file):
    """Restore a backup"""
    if not os.path.exists(backup_file):
        print("✗ Backup file not found.")
        return False

    try:
        shutil.copy2(backup_file, DATABASE)
        print(f"✓ Backup restored: {backup_file}")
        return True
    except Exception as e:
        print(f"✗ Restore failed: {e}")
        return False


def list_backups():
    """List all available backups"""
    if not os.path.exists(BACKUP_DIR):
        print("No backups found.")
        return []

    backups = [f for f in os.listdir(BACKUP_DIR) if f.endswith('.db')]
    backups.sort(reverse=True)

    print("\n" + "=" * 33)
    print("      AVAILABLE BACKUPS")
    print("=" * 33)

    if not backups:
        print("  No backups found.")
        return []

    for idx, backup in enumerate(backups, 1):
        backup_path = os.path.join(BACKUP_DIR, backup)
        size = os.path.getsize(backup_path) / 1024  # KB
        modified = datetime.fromtimestamp(os.path.getmtime(backup_path))
        print(f"  {idx}. {backup} ({size:.1f} KB) - {modified.strftime('%Y-%m-%d %H:%M')}")

    return backups
