"""
Configuration File
"""

import os
from dotenv import load_dotenv

load_dotenv()

# =====================================================
# AVWX API
# =====================================================

AVWX_TOKEN = os.getenv("AVWX_TOKEN", "")

API_METAR = "https://avwx.rest/api/metar"

# OpenSky Network
OPENSKY_URL = "https://opensky-network.org/api/states/all"

# =====================================================
# DATABASE
# =====================================================

DATABASE_FILE = "aoms.db"

# =====================================================
# AIRPORT INFORMATION
# =====================================================

AIRPORT_NAME = "Houari Boumediene International Airport"

ICAO = "DAAG"
IATA = "ALG"

CITY = "Algiers"
COUNTRY = "Algeria"

ELEVATION = 25                 # metres (AIP AD 2.2: 25 M)
ELEVATION_UNIT = "M"

TIMEZONE = "UTC+1"

ARP = "364140N0031301E"

CTR_RADIUS = "6 NM"            # AIP AD 2.17: circle of 6 NM radius centred on ARP
CTR_UPPER_LIMIT = "450 M GND/MSL"   # AIP AD 2.17
AIRSPACE_CLASS = "D"

TRANSITION_ALTITUDE = 1200       # metres MSL (AIP AD 2.17)
TRANSITION_ALTITUDE_UNIT = "M MSL"
TRANSITION_LEVEL = "Published by ATC"

# =====================================================
# RUNWAYS
# =====================================================

RUNWAYS = [
    "05/23",
    "09/27"
]

# =====================================================
# RUNWAY DATA
# =====================================================

RUNWAY_09 = {
    "heading": 92,          # TRUE bearing (AIP AD 2.12)
    "mag_heading": 90,      # magnetic (variation 2°E)
    "length": 3500,
    "width": 45,
    "surface": "BITUMINOUS CONCRETE",
    "ils": True,
    "papi": True
}

RUNWAY_27 = {
    "heading": 272,          # TRUE bearing (AIP AD 2.12)
    "mag_heading": 270,      # magnetic (variation 2°E)
    "length": 3500,
    "width": 45,
    "surface": "BITUMINOUS CONCRETE",
    "ils": True,
    "papi": True
}

RUNWAY_05 = {
    "heading": 53,          # TRUE bearing (AIP AD 2.12)
    "mag_heading": 51,      # magnetic (variation 2°E)
    "length": 3500,
    "width": 60,
    "surface": "BITUMINOUS CONCRETE",
    "ils": False,
    "papi": True
}

RUNWAY_23 = {
    "heading": 233,          # TRUE bearing (AIP AD 2.12)
    "mag_heading": 231,      # magnetic (variation 2°E)
    "length": 3500,
    "width": 60,
    "surface": "BITUMINOUS CONCRETE",
    "ils": True,
    "papi": True
}

# =====================================================
# CAPACITY
# =====================================================

ARRIVAL_CAPACITY = 12
DEPARTURE_CAPACITY = 12
SEPARATION = 5

# =====================================================
# FREQUENCIES
# =====================================================

TOWER_FREQUENCY = "118.700"
GROUND_FREQUENCY = "121.800"
APPROACH_FREQUENCY = "121.400"
ATIS_FREQUENCY = "128.525"

# =====================================================
# RADIO NAVIGATION
# =====================================================

RADIO_NAVIGATION = {

    "DVOR/DME ALR": {
        "Frequency": "112.500 MHz",
        "Channel": "72X"
    },

    "DVOR/DME ZEM": {
        "Frequency": "116.600 MHz",
        "Channel": "113X"
    },

    "DVOR/DME SDM": {
        "Frequency": "113.900 MHz",
        "Channel": "86X"
    },

    "NDB SMR": {
        "Frequency": "370 kHz"
    },

    "NDB MAR": {
        "Frequency": "416 kHz"
    },

    "LOCATOR OA": {
        "Frequency": "342 kHz"
    },

    "ILS RWY23": {
        "Localizer": "110.300 MHz",
        "GlideSlope": "335.000 MHz"
    },

    "ILS RWY09": {
        "Localizer": "108.500 MHz",
        "GlideSlope": "329.900 MHz"
    },

    "ILS RWY27": {
        "Localizer": "109.500 MHz",
        "GlideSlope": "332.600 MHz"
    }
}

# =====================================================
# DEFAULTS
# =====================================================

DEFAULT_SPEED = 450
DEFAULT_CRUISE_ALTITUDE = 35000

# =====================================================
# ADMIN
# =====================================================

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")


# =====================================================
# OPERATIONAL THRESHOLDS (used by capacity / alerts / AI support)
# =====================================================

# Airport reference point in decimal degrees (from ARP above)
ARP_LAT = 36.6944
ARP_LON = 3.2169

# Traffic load: ratio of demand (next 60 min) to hourly capacity
LOAD_WARNING_RATIO = 0.80
LOAD_CRITICAL_RATIO = 1.00

# ATFCM: a flight must depart in [CTOT - 5 min, CTOT + 10 min]
CTOT_TOLERANCE_BEFORE = 5
CTOT_TOLERANCE_AFTER = 10
CTOT_WARNING_MIN = 30          # alert when CTOT is closer than this

# Weather limits
LOW_VIS_M = 5000               # IFR conditions
LVP_VIS_M = 800                # low visibility procedures
LVP_CEILING_FT = 200
STRONG_WIND_KT = 25
MAX_CROSSWIND_KT = 25
MAX_TAILWIND_KT = 5

# Separation used by the conflict detector (advisory only)
CONFLICT_HORIZONTAL_NM = 5.0
CONFLICT_VERTICAL_FT = 1000
