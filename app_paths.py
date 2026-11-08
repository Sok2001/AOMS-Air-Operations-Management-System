import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IS_FROZEN = getattr(sys, "frozen", False)

if IS_FROZEN:
    if sys.platform == "darwin":
        APP_DATA_DIR = os.path.expanduser(
            "~/Library/Application Support/AOMS"
        )
    elif os.name == "nt":
        APP_DATA_DIR = os.path.join(
            os.environ.get("APPDATA", os.path.expanduser("~")),
            "AOMS"
        )
    else:
        APP_DATA_DIR = os.path.expanduser(
            "~/.local/share/AOMS"
        )
else:
    APP_DATA_DIR = BASE_DIR

os.makedirs(APP_DATA_DIR, exist_ok=True)

DATABASE_PATH = os.environ.get(
    "AOMS_DB",
    os.path.join(APP_DATA_DIR, "aoms.db")
)

BACKUP_DIR = os.path.join(APP_DATA_DIR, "backup")
FLIGHTS_FILE = os.path.join(APP_DATA_DIR, "flights.json")

# Persistent chart storage: outside the temporary PyInstaller bundle.
CHARTS_DIR = os.path.join(APP_DATA_DIR, "charts")

os.makedirs(BACKUP_DIR, exist_ok=True)
os.makedirs(CHARTS_DIR, exist_ok=True)


def resource_path(*parts):
    """Resolve bundled resources in development and PyInstaller builds."""
    resource_base = getattr(sys, "_MEIPASS", BASE_DIR)
    return os.path.join(resource_base, *parts)
