import json
import os

from app_paths import FLIGHTS_FILE

FILE_NAME = FLIGHTS_FILE


def load_flights():
    if not os.path.exists(FILE_NAME):
        return []

    try:
        with open(FILE_NAME, "r", encoding="utf-8") as file:
            return json.load(file)
    except:
        return []


def save_flights(flights):
    with open(FILE_NAME, "w", encoding="utf-8") as file:
        json.dump(flights, file, indent=4)
