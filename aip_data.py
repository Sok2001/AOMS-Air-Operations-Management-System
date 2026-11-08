"""Read-only access to the AIP data stored in the database (see aip_loader.py)."""

import os
import re

from database import get_connection
from aip_loader import CHARTS_DIR


def _all(sql, params=()):
    conn = get_connection()
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def _one(sql, params=()):
    conn = get_connection()
    try:
        return conn.execute(sql, params).fetchone()
    finally:
        conn.close()


def get_airport(icao="DAAG"):
    conn = get_connection()
    try:
        conn.row_factory = __import__("sqlite3").Row
        r = conn.execute("SELECT * FROM airports WHERE icao=?", (icao.upper(),)).fetchone()
        return dict(r) if r else None
    finally:
        conn.close()


def sections(icao="DAAG"):
    return _all("SELECT section, text FROM aip_sections WHERE icao=? ORDER BY ord", (icao.upper(),))


def notes(icao="DAAG"):
    return [r[0] for r in _all("SELECT text FROM aip_notes WHERE icao=? ORDER BY ord", (icao.upper(),))]


def runways(icao="DAAG"):
    return _all("""SELECT rwy, true_brg, mag_brg, length_m, width_m, surface, pcr, thr_elev_m, tora, toda, asda,
                   lda, ils, ils_cat, loc, gp, dme, strip, resa, slope, papi, approach_lgt
                   FROM aip_runways WHERE icao=? ORDER BY rwy""", (icao.upper(),))


def runway_true_heading(rwy, icao="DAAG"):
    r = _one("SELECT true_brg FROM aip_runways WHERE icao=? AND rwy=?", (icao.upper(), str(rwy)))
    return r[0] if r else None


def navaids(icao="DAAG"):
    return _all("SELECT type, ident, freq, channel, lat, lon, remarks FROM aip_navaids WHERE icao=? ORDER BY id",
                (icao.upper(),))


def frequencies(icao="DAAG"):
    return _all("SELECT service, callsign, freq, hours, remarks FROM aip_frequencies WHERE icao=? ORDER BY id",
                (icao.upper(),))


def stands(icao="DAAG", text=""):
    q = f"%{text.upper()}%"
    return _all("""SELECT apron, stand, category, strength, lat, lon FROM aip_stands
                   WHERE icao=? AND (UPPER(apron) LIKE ? OR UPPER(stand) LIKE ? OR UPPER(category) LIKE ?)
                   ORDER BY id""", (icao.upper(), q, q, q))


def aprons(icao="DAAG"):
    return _all("SELECT apron, elevation_m, surface_strength FROM aip_aprons WHERE icao=? ORDER BY id",
                (icao.upper(),))


def taxiways(icao="DAAG"):
    return _all("SELECT twy, width_m, surface, pcr, remarks FROM aip_taxiways WHERE icao=? ORDER BY id",
                (icao.upper(),))


def obstacles(icao="DAAG"):
    return _all("SELECT obst_id, type, position, elev_hgt, marking, area, remarks FROM aip_obstacles "
                "WHERE icao=? ORDER BY id", (icao.upper(),))


def charts(icao="DAAG", chart_type=None):
    sql = "SELECT code, type, title, rwy, category, airac, file, preview FROM charts WHERE icao=?"
    params = [icao.upper()]
    if chart_type and chart_type != "ALL":
        sql += " AND type=?"
        params.append(chart_type)
    return _all(sql + " ORDER BY type, code", params)


def chart_types(icao="DAAG"):
    return [r[0] for r in _all("SELECT DISTINCT type FROM charts WHERE icao=? ORDER BY type", (icao.upper(),))]


def chart_paths(code, icao="DAAG"):
    """(preview_png_or_None, pdf_or_None) as absolute paths, or (None, None) if not available."""
    r = _one("SELECT preview, file FROM charts WHERE icao=? AND code=?", (icao.upper(), code))
    if not r:
        return None, None
    base = os.path.join(CHARTS_DIR, icao.upper())
    return tuple(os.path.join(base, x) if x else None for x in r)


def is_available(row):
    """row = a tuple from charts(): available when a file or preview exists."""
    return bool(row[6] or row[7])


def clean_code(text):
    code = re.sub(r"[^A-Z0-9-]", "", str(text).upper().replace(" ", ""))
    return code
