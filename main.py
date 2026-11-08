"""
AOMS - Airport Operations Management System
Entry point.

    python main.py          -> graphical interface (default)
    python main.py --cli    -> console menu
    python main.py --demo   -> load demo data (flights, NOTAM, CTOT), then start
"""

import sys

from database import init_database


def run_cli():
    from auth import login, check_session_timeout, check_permission
    from dashboard import dashboard
    from flight import add_flight, show_flights, search_flight, delete_flight
    from runway import show_runways, occupy_runway, release_runway
    from traffic import show_traffic_menu
    from progress import show_progress_menu
    from airport_statistics import show_statistics_menu
    from clearance import issue_clearance
    from weather import show_metar, show_taf
    from live_flights import live_flights
    from users import add_user, show_users, edit_user, delete_user
    from logs import show_logs
    from backup import create_backup, list_backups
    from config import ICAO
    from notam import show_notams, add_notam_cli
    from capacity import show_capacity
    from atfcm import show_ctot, set_ctot_cli
    from alerts import show_alerts
    from ai_support import show_ai_report

    user = None
    while user is None:
        user = login()
        if user is None and input("\n Try again? (y/n) : ").lower() != "y":
            return

    # (label, permission, action)
    items = [
        ("Dashboard", "dashboard", lambda: dashboard()),
        ("Add Flight", "add_flight", lambda: add_flight()),
        ("Show Flights", "show_flights", lambda: show_flights()),
        ("Search Flight", "search_flight", lambda: search_flight()),
        ("Delete Flight", "delete_flight", lambda: delete_flight()),
        ("Flight Progress", "update_status", lambda: show_progress_menu()),
        ("Show Runways", "show_runways", lambda: show_runways()),
        ("Occupy Runway", "occupy_runway", lambda: occupy_runway()),
        ("Release Runway", "release_runway", lambda: release_runway()),
        ("Traffic Management", "show_flights", lambda: show_traffic_menu()),
        ("ATC Clearance", "issue_clearance", lambda: issue_clearance()),
        ("Statistics", "statistics", lambda: show_statistics_menu()),
        ("METAR", "metar", lambda: show_metar(ICAO)),
        ("TAF", "metar", lambda: show_taf(ICAO)),
        ("Live Flights", "live_flights", lambda: live_flights()),
        ("Airport Capacity", "capacity", lambda: show_capacity()),
        ("ATFCM / CTOT", "atfcm", lambda: show_ctot()),
        ("Set CTOT", "ctot", lambda: set_ctot_cli(user)),
        ("NOTAM", "notam", lambda: show_notams()),
        ("Add NOTAM", "edit_notam", lambda: add_notam_cli(user)),
        ("Alerts", "alerts", lambda: show_alerts()),
        ("AI Decision Support", "ai_support", lambda: show_ai_report()),
        ("Add User", "add_user", lambda: add_user(user)),
        ("Show Users", "show_users", lambda: show_users(user)),
        ("Edit User", "edit_user", lambda: edit_user(user)),
        ("Delete User", "delete_user", lambda: delete_user(user)),
        ("System Logs", "view_logs", lambda: show_logs()),
        ("Create Backup", "backup", lambda: create_backup()),
        ("List Backups", "backup", lambda: list_backups()),
    ]
    items = [i for i in items if check_permission(user, i[1])]

    while True:
        if check_session_timeout(user):
            print("\n ⚠ Session expired. Please login again.")
            return
        print("\n" + "=" * 42)
        print(" AOMS - MAIN MENU")
        print(f" {user['full_name']}  [{user['role']}]")
        print("=" * 42)
        for n, (label, _, _) in enumerate(items, 1):
            print(f" {n:>2}. {label}")
        print("  0. Exit")
        print("-" * 42)
        choice = input(" Choice : ").strip()
        if choice == "0":
            return
        if choice.isdigit() and 1 <= int(choice) <= len(items):
            items[int(choice) - 1][2]()
        else:
            print(" Invalid choice")


def main():
    created = init_database()
    import aip_loader
    aip_loader.sync_safe()          # AIP data (DAAG) + chart library; idempotent
    if created:
        print("[first run] Default administrator account created. Change its password after login.")

    if "--demo" in sys.argv:
        from seed_demo import seed
        seed()

    if "--cli" in sys.argv:
        run_cli()
    else:
        import aoms_gui
        aoms_gui.main()


if __name__ == "__main__":
    main()
