"""
API Module - live METAR / TAF.
Source 1: AVWX (needs a valid token in config.py).
Source 2 (automatic fallback, no key needed): NOAA Aviation Weather Center.
Both return a dict {"raw": ..., "station": ..., "source": ...}; metar_parser decodes the raw text.
"""

import requests
from config import API_METAR, AVWX_TOKEN

NOAA_URL = "https://aviationweather.gov/api/data/{kind}"

last_error = ""          # last problem text, shown in the Weather page when nothing could be fetched


def _avwx(kind, icao):
    global last_error
    if not AVWX_TOKEN:
        return None
    url = f"{API_METAR}/{icao}" if kind == "metar" else f"https://avwx.rest/api/taf/{icao}"
    try:
        r = requests.get(url, headers={"Authorization": AVWX_TOKEN, "Accept": "application/json"}, timeout=15)
    except requests.RequestException as e:
        last_error = f"AVWX: {type(e).__name__}"
        return None
    if r.status_code != 200:
        last_error = f"AVWX: HTTP {r.status_code}" + (" (invalid token)" if r.status_code in (401, 403) else "")
        return None
    try:
        d = r.json()
    except ValueError:
        last_error = "AVWX: bad response"
        return None
    if isinstance(d, dict) and d.get("raw"):
        d["source"] = "AVWX"
        return d
    return None


def _noaa(kind, icao):
    global last_error
    try:
        r = requests.get(NOAA_URL.format(kind=kind), params={"ids": icao, "format": "raw"},
                         headers={"User-Agent": "AOMS/3.5"}, timeout=15)
    except requests.RequestException as e:
        last_error = (last_error + " | " if last_error else "") + f"NOAA: {type(e).__name__}"
        return None
    raw = r.text.strip() if r.status_code == 200 else ""
    if not raw:
        last_error = (last_error + " | " if last_error else "") + f"NOAA: HTTP {r.status_code}" if r.status_code != 200 \
            else (last_error + " | " if last_error else "") + f"NOAA: no {kind.upper()} for {icao}"
        return None
    lines = [l.strip() for l in raw.splitlines() if l.strip()]
    if kind == "metar":
        raw = lines[0]                                   # newest report
    else:
        raw = " ".join(lines)                            # TAF may span several lines
    for p in ("METAR ", "SPECI ", "TAF "):
        if raw.startswith(p):
            raw = raw[len(p):]
    return {"raw": raw, "station": icao, "source": "NOAA"}


def _get(kind, icao):
    global last_error
    icao = (icao or "").strip().upper()
    last_error = ""
    return _avwx(kind, icao) or _noaa(kind, icao)


def get_metar(icao):
    """Live METAR (AVWX, then NOAA fallback). None if both fail - see last_error."""
    return _get("metar", icao)


def get_taf(icao):
    """Live TAF (AVWX, then NOAA fallback). None if both fail - see last_error."""
    return _get("taf", icao)
