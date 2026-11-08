"""
AIP data loader (DAAG and any future airport).

Reads data/<icao>/*.json (transcribed from the AIP) and scans charts/<ICAO>/ for chart files,
then fills the aip_* / charts tables.  Safe to run on every start-up (idempotent):
the JSON import only runs when the files changed (checksum), the chart scan always runs.
"""

import hashlib
import json
import os
import re

from database import get_connection

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
CHARTS_DIR = os.path.join(BASE_DIR, "charts")

DATA_FILES = ["airport", "runways", "navaids", "frequencies", "stands", "aprons",
              "obstacles", "notes", "charts_catalog"]
CHART_EXT = (".png", ".jpg", ".jpeg", ".pdf")


# ------------------------------------------------------------------ helpers
def dms_to_deg(text):
    """'364159.61N' / '0031259.47E' -> decimal degrees (None if empty / invalid)."""
    if not text:
        return None
    m = re.match(r"^\s*(\d{2,3})(\d{2})(\d{2}(?:\.\d+)?)\s*([NSEW])\s*$", str(text))
    if not m:
        return None
    deg = int(m.group(1)) + int(m.group(2)) / 60 + float(m.group(3)) / 3600
    return round(-deg if m.group(4) in "SW" else deg, 6)


def normalize_code(name, icao="DAAG"):
    """'DAAG-IAC1.pdf' / 'AD 2 DAAG-IAC1' / 'iac1' -> 'IAC1'."""
    stem = os.path.splitext(os.path.basename(name))[0].upper().strip()
    stem = re.sub(r"^AD\s*2[\s_-]*", "", stem)
    stem = re.sub(rf"^{icao.upper()}[\s_-]*(?=[A-Z0-9])", "", stem)
    return stem.replace(" ", "").replace("_", "-")


def guess_type(code):
    m = re.match(r"^([A-Z]+)", code)
    return m.group(1) if m else "OTHER"


def _read_json(icao, name):
    path = os.path.join(DATA_DIR, icao.lower(), name + ".json")
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _checksum(icao):
    h = hashlib.sha256()
    for name in DATA_FILES:
        path = os.path.join(DATA_DIR, icao.lower(), name + ".json")
        if os.path.exists(path):
            with open(path, "rb") as f:
                h.update(name.encode() + f.read())
    return h.hexdigest()


# ------------------------------------------------------------------ import
def import_airport(icao="DAAG", force=False):
    """Import data/<icao>/*.json into the database. Returns True if something was imported."""
    icao = icao.upper()
    sig = _checksum(icao)
    conn = get_connection()
    try:
        row = conn.execute("SELECT value FROM aip_meta WHERE key=?", (f"data:{icao}",)).fetchone()
        if row and row[0] == sig and not force:
            return False
        ap = _read_json(icao, "airport")
        if not ap:
            return False
        cur = conn.cursor()
        for t in ("airports", "aip_runways", "aip_navaids", "aip_frequencies", "aip_stands",
                  "aip_aprons", "aip_taxiways", "aip_obstacles", "aip_sections", "aip_notes"):
            cur.execute(f"DELETE FROM {t} WHERE icao=?", (icao,))

        cur.execute("""INSERT INTO airports (icao, iata, name, city, country, arp_lat, arp_lon, elevation_m,
                       ref_temp_c, mag_var, location, traffic, airac, source)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (icao, ap.get("iata"), ap.get("name"), ap.get("city"), ap.get("country"),
                     ap.get("arp_lat"), ap.get("arp_lon"), ap.get("elevation_m"), ap.get("ref_temp_c"),
                     ap.get("mag_var"), ap.get("location"), ap.get("traffic"), ap.get("airac"),
                     ap.get("source")))
        for i, (k, v) in enumerate(ap.get("sections", {}).items()):
            cur.execute("INSERT INTO aip_sections (icao, ord, section, text) VALUES (?,?,?,?)", (icao, i, k, v))

        for r in _read_json(icao, "runways") or []:
            cur.execute("""INSERT INTO aip_runways (icao, rwy, true_brg, mag_brg, length_m, width_m, surface, pcr,
                           thr_lat, thr_lon, thr_elev_m, slope, strip, resa, shoulders, tora, toda, asda, lda,
                           approach_lgt, thr_lgt, papi, tdz_lgt, cl_lgt, edge_lgt, end_lgt, swy_lgt,
                           ils, ils_cat, loc, gp, dme)
                           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (icao, r["rwy"], r["true_brg"], r["mag_brg"], r["length_m"], r["width_m"], r["surface"],
                         r["pcr"], dms_to_deg(r["thr_lat"]), dms_to_deg(r["thr_lon"]), r["thr_elev_m"],
                         r["slope"], r["strip"], r["resa"], r["shoulders"], r["tora"], r["toda"], r["asda"],
                         r["lda"], r["approach_lgt"], r["thr_lgt"], r["papi"], r["tdz_lgt"], r["cl_lgt"],
                         r["edge_lgt"], r["end_lgt"], r["swy_lgt"], r["ils"], r["ils_cat"], r["loc"], r["gp"],
                         r["dme"]))
        for n in _read_json(icao, "navaids") or []:
            cur.execute("""INSERT INTO aip_navaids (icao, type, ident, freq, channel, lat, lon, remarks)
                           VALUES (?,?,?,?,?,?,?,?)""",
                        (icao, n["type"], n["ident"], n["freq"], n["channel"],
                         dms_to_deg(n["lat"]), dms_to_deg(n["lon"]), n["remarks"]))
        for f in _read_json(icao, "frequencies") or []:
            cur.execute("""INSERT INTO aip_frequencies (icao, service, callsign, freq, hours, remarks)
                           VALUES (?,?,?,?,?,?)""",
                        (icao, f["service"], f["callsign"], f["freq"], f["hours"], f["remarks"]))
        for s in _read_json(icao, "stands") or []:
            cur.execute("""INSERT INTO aip_stands (icao, apron, stand, category, strength, lat, lon)
                           VALUES (?,?,?,?,?,?,?)""",
                        (icao, s["apron"], s["stand"], s["category"], s["strength"],
                         dms_to_deg(s["lat"]), dms_to_deg(s["lon"])))
        aprons = _read_json(icao, "aprons") or {}
        for a in aprons.get("aprons", []):
            cur.execute("INSERT INTO aip_aprons (icao, apron, elevation_m, surface_strength) VALUES (?,?,?,?)",
                        (icao, a["apron"], a["elevation_m"], a["surface_strength"]))
        for t in aprons.get("taxiways", []):
            for ident in t["twys"]:
                cur.execute("""INSERT INTO aip_taxiways (icao, twy, width_m, surface, pcr, remarks)
                               VALUES (?,?,?,?,?,?)""",
                            (icao, ident, t["width_m"], t["surface"], t["pcr"], t.get("remarks", "")))
        for o in _read_json(icao, "obstacles") or []:
            cur.execute("""INSERT INTO aip_obstacles (icao, obst_id, type, position, elev_hgt, marking, area, remarks)
                           VALUES (?,?,?,?,?,?,?,?)""",
                        (icao, o["obst_id"], o["type"], o["position"], o["elev_hgt"], o["marking"],
                         o["area"], o.get("remarks", "")))
        for i, n in enumerate(_read_json(icao, "notes") or []):
            cur.execute("INSERT INTO aip_notes (icao, ord, text) VALUES (?,?,?)", (icao, i, n))

        cur.execute("INSERT OR REPLACE INTO aip_meta (key, value) VALUES (?, ?)", (f"data:{icao}", sig))
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ------------------------------------------------------------------ charts
def scan_charts(icao="DAAG"):
    """Catalog (from AIP AD 2.24) + files found in charts/<ICAO>/  ->  `charts` table."""
    icao = icao.upper()
    folder = os.path.join(CHARTS_DIR, icao)
    os.makedirs(folder, exist_ok=True)
    catalog = {c["code"]: c for c in (_read_json(icao, "charts_catalog") or [])}
    files = {}
    for fn in sorted(os.listdir(folder)):
        ext = os.path.splitext(fn)[1].lower()
        if ext in CHART_EXT:
            files.setdefault(normalize_code(fn, icao), {})[ext] = fn
    meta_path = os.path.join(folder, "charts_meta.json")       # optional: {"IAC1": {"date": "18 DEC 23", "airac": ""}}
    dates = {}
    if os.path.exists(meta_path):
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                dates = {normalize_code(k, icao): v for k, v in json.load(f).items()}
        except Exception:
            dates = {}
    conn = get_connection()
    try:
        conn.execute("DELETE FROM charts WHERE icao=? AND source='auto'", (icao,))
        codes = list(catalog) + [c for c in files if c not in catalog]
        for code in codes:
            meta = catalog.get(code, {})
            f = files.get(code, {})
            preview = next((f[e] for e in (".png", ".jpg", ".jpeg") if e in f), None)
            pdf = f.get(".pdf")
            conn.execute("""INSERT INTO charts (icao, code, type, title, rwy, category, airac, file, preview, source)
                            VALUES (?,?,?,?,?,?,?,?,?, 'auto')""",
                         (icao, code, meta.get("type") or guess_type(code), meta.get("title") or code,
                          meta.get("rwy", ""), meta.get("category", ""),
                          (dates.get(code, {}).get("date", "") if (pdf or preview) else ""), pdf, preview))
        conn.commit()
    finally:
        conn.close()


def sync(icao="DAAG"):
    """Import data (if changed) and rescan the chart folder."""
    imported = import_airport(icao)
    scan_charts(icao)
    return imported


def sync_safe(icao="DAAG"):
    """Never raises: the rest of the program must start even if the AIP data is missing."""
    try:
        return sync(icao)
    except Exception as e:  # noqa
        print(f"[aip_loader] warning: {e}")
        return False
