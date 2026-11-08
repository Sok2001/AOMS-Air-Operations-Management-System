"""
Automatic NOTAM import (v3.4).

Source: ICAO API Data Service "Realtime NOTAMs" (notams-realtime-list) - fed by the FAA/DINS bridge.
  * needs a FREE API key (request it at https://applications.icao.int/dataservices/),
  * the free tier is limited (about 100 calls), so the program fetches at most once every N hours
    (default 12 h) and counts the calls itself (monthly limit, default 90).
Fallback that needs no key at all: paste NOTAM text in ICAO format (see parse_icao_text / import_text).

The key is stored in the local database (table app_settings) or read from the ICAO_API_KEY environment variable.
It is never written to the logs or shown in error messages.
"""

import json
import re
from datetime import datetime, timedelta, timezone

import requests

from config import ICAO
from database import get_connection
from logs import add_log
import notam as notam_mod
from utc_time import get_utc_datetime

API_URL = "https://applications.icao.int/dataservices/api/notams-realtime-list"
KEY_URL = "https://applications.icao.int/dataservices/"
DEFAULTS = {"enabled": "1", "api_key": "", "locations": f"{ICAO},DAAA", "interval_h": "12",
            "monthly_limit": "90", "last_attempt": "", "last_ok": "", "calls": "", "last_status": "Never fetched"}


class NotamApiError(Exception):
    pass


# ------------------------------------------------------------------ settings
def get_settings():
    import os
    s = dict(DEFAULTS)
    conn = get_connection()
    try:
        for k, v in conn.execute("SELECT key, value FROM app_settings WHERE key LIKE 'notam_%'").fetchall():
            s[k[6:]] = v
    finally:
        conn.close()
    if os.environ.get("ICAO_API_KEY"):
        s["api_key"] = os.environ["ICAO_API_KEY"].strip()
    return s


def save_settings(**kw):
    conn = get_connection()
    try:
        for k, v in kw.items():
            if k in DEFAULTS:
                conn.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES (?, ?)", (f"notam_{k}", str(v)))
        conn.commit()
    finally:
        conn.close()


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _stamp():
    return _now().strftime("%Y-%m-%d %H:%M")


def _month():
    return _now().strftime("%Y-%m")


def calls_used(s=None):
    """API calls made in the current calendar month (counted locally)."""
    s = s or get_settings()
    m, _, n = (s.get("calls") or "").partition(":")
    return int(n) if m == _month() and n.isdigit() else 0


def _count_call():
    n = calls_used() + 1
    save_settings(calls=f"{_month()}:{n}")


def _scrub(text, key):
    text = str(text)
    return text.replace(key, "***") if key else text


# ------------------------------------------------------------------ NOTAM text (ICAO format) parser
HEADER = re.compile(r"(?m)^\s*\(?\s*([A-Z]\d{4}/\d{2})\s+NOTAM([NRC])(?:\s+([A-Z]\d{4}/\d{2}))?")


def _icao_dt(v):
    v = (v or "").strip().upper().replace("EST", "").strip()
    if v in ("PERM", "UFN", ""):
        return ""
    try:
        return datetime.strptime("20" + v[:10], "%Y%m%d%H%M").strftime(notam_mod.DT_FORMAT)
    except ValueError:
        return ""


def parse_icao_text(text):
    """Split text with one or several NOTAMs in ICAO format -> list of dicts
    {notam_id, kind (N/R/C), ref, location, valid_from, valid_to, text}."""
    text = text or ""
    marks = list(HEADER.finditer(text))
    out = []
    for i, m in enumerate(marks):
        block = text[m.start(): marks[i + 1].start() if i + 1 < len(marks) else len(text)]
        a = re.search(r"A\)\s*([A-Z]{4}(?:\s+[A-Z]{4})*)", block)
        b = re.search(r"B\)\s*(\d{10})", block)
        c = re.search(r"C\)\s*(\d{10}\s*(?:EST)?|PERM|UFN)", block)
        e = re.search(r"E\)\s*(.*?)(?=\n\s*[FG]\)|\Z)", block, re.S)
        body = re.sub(r"\s+", " ", e.group(1)).strip().rstrip(")") if e else ""
        out.append({"notam_id": m.group(1), "kind": m.group(2), "ref": m.group(3) or "",
                    "location": (a.group(1).split()[0] if a else ""),
                    "valid_from": _icao_dt(b.group(1)) if b else "",
                    "valid_to": _icao_dt(c.group(1)) if c else "", "text": body})
    return out


# ------------------------------------------------------------------ API response -> NOTAM dicts
def _g(item, *names):
    for n in names:
        for k in (n, n.lower(), n.upper()):
            v = item.get(k)
            if v not in (None, ""):
                return v
    return ""


def _iso_dt(v):
    v = str(v or "").strip()
    if not v:
        return None
    try:
        return datetime.fromisoformat(v.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(v[:19], fmt)
            except ValueError:
                pass
    return None


def normalize(item):
    """One ICAO API record -> {notam_id, kind, ref, location, valid_from, valid_to, text} (None if unusable)."""
    if not isinstance(item, dict):
        return None
    full = str(_g(item, "all"))
    parsed = parse_icao_text(full)
    p = parsed[0] if parsed else {}
    key = str(_g(item, "key"))
    nid = p.get("notam_id") or (key.rsplit("-", 1)[0] if "-" in key else key) or str(_g(item, "id"))
    if not nid:
        return None
    loc = str(_g(item, "location") or p.get("location") or "").upper()
    vf, vt = p.get("valid_from", ""), p.get("valid_to", "")
    if not vf:
        d = _iso_dt(_g(item, "startdate"))
        vf = d.strftime(notam_mod.DT_FORMAT) if d else ""
    if not vt:
        d, d0 = _iso_dt(_g(item, "enddate")), _iso_dt(_g(item, "startdate"))
        vt = "PERM" if (not d or (d0 and d.year - d0.year >= 50)) else d.strftime(notam_mod.DT_FORMAT)
    text = p.get("text") or re.sub(r"\s+", " ", str(_g(item, "message", "all"))).strip()
    return {"notam_id": nid.upper(), "kind": p.get("kind", "N"), "ref": p.get("ref", ""), "location": loc,
            "valid_from": vf, "valid_to": vt or "PERM", "text": text}


# ------------------------------------------------------------------ network
def fetch(settings=None):
    """Call the ICAO API once. Returns the list of raw records. Raises NotamApiError."""
    s = settings or get_settings()
    key = (s.get("api_key") or "").strip()
    if not key:
        raise NotamApiError("No API key. Get a free key at applications.icao.int/dataservices and enter it in API settings.")
    locs = ",".join(x.strip().upper() for x in s["locations"].replace(";", ",").split(",") if x.strip())[:60]
    try:
        r = requests.get(API_URL, params={"api_key": key, "format": "json", "criticality": "", "locations": locs},
                         timeout=25)
    except requests.RequestException as e:
        raise NotamApiError("Network error: " + _scrub(e, key)[:160])
    _count_call()
    if r.status_code != 200:
        raise NotamApiError(f"HTTP {r.status_code}: " + _scrub(r.text, key)[:160].replace("\n", " "))
    try:
        data = r.json()
    except ValueError:
        raise NotamApiError("The server did not return JSON: " + _scrub(r.text, key)[:120].replace("\n", " "))
    if isinstance(data, dict):
        for k in ("data", "notams", "results", "Data"):
            if isinstance(data.get(k), list):
                return data[k]
        raise NotamApiError("API message: " + _scrub(json.dumps(data), key)[:160])
    if not isinstance(data, list):
        raise NotamApiError("Unexpected response format.")
    return data


FAA_URL = "https://notams.aim.faa.gov/notamSearch/search"


def fetch_faa(settings=None):
    """Key-free source: FAA NOTAM Search (ICAO format, worldwide). Returns raw records for normalize()."""
    s = settings or get_settings()
    locs = [x.strip().upper() for x in s["locations"].replace(";", ",").split(",") if x.strip()][:10]
    out = []
    sess = requests.Session()
    sess.headers.update({"User-Agent": "Mozilla/5.0 (AOMS)", "Accept": "application/json",
                         "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"})
    for loc in locs:
        offset = 0
        while offset < 300:
            form = {"searchType": "0", "designatorsForLocation": loc, "formatType": "ICAO", "notamsOnly": "false",
                    "radius": "10", "sortColumns": "5-false", "sortDirection": "true", "offset": str(offset),
                    "flightPathBuffer": "4", "flightPathIncludeNavaids": "true", "flightPathIncludeArtcc": "false",
                    "flightPathResultsType": "All NOTAMs", "latMinutes": "0", "latSeconds": "0", "longMinutes": "0",
                    "longSeconds": "0", "radiusSearchOnDesignator": "false", "latDegrees": "0", "longDegrees": "0"}
            try:
                r = sess.post(FAA_URL, data=form, timeout=25)
            except requests.RequestException as e:
                raise NotamApiError("Network error: " + type(e).__name__)
            if r.status_code != 200:
                raise NotamApiError(f"FAA HTTP {r.status_code}")
            try:
                data = r.json()
            except ValueError:
                raise NotamApiError("FAA did not return JSON")
            lst = data.get("notamList") or []
            for n in lst:
                msg = n.get("icaoMessage") or n.get("traditionalMessage") or ""
                out.append({"all": msg, "location": n.get("icaoId") or loc,
                            "key": n.get("notamNumber") or "", "startdate": n.get("startDate") or "",
                            "enddate": n.get("endDate") or ""})
            offset += 30
            if len(lst) < 30:
                break
    return out


# ------------------------------------------------------------------ database
def import_records(records, username="auto", source="API", cancel_missing=None):
    """Insert / update NOTAMs. records = list of normalize() dicts.
    cancel_missing = set of locations: API NOTAMs of those locations that are no longer returned get CANCELLED.
    Returns dict(new, updated, cancelled)."""
    stats = {"new": 0, "updated": 0, "cancelled": 0}
    seen = set()
    conn = get_connection()
    try:
        for r in records:
            if not r or not r["text"] and r["kind"] != "C":
                continue
            loc = r["location"]
            nid = r["notam_id"] if loc in ("", ICAO) else f"{r['notam_id']}@{loc}"
            if r["kind"] == "C":                         # NOTAMC cancels the referenced NOTAM
                ref = r["ref"] if loc in ("", ICAO) else f"{r['ref']}@{loc}"
                if ref:
                    cur = conn.execute("UPDATE notams SET status='CANCELLED' WHERE notam_id=? AND status!='CANCELLED'",
                                       (ref.upper(),))
                    stats["cancelled"] += cur.rowcount
                continue
            seen.add(nid)
            cat, prio = notam_mod.classify(r["text"])
            row = conn.execute("SELECT id, status, source FROM notams WHERE notam_id=?", (nid,)).fetchone()
            if row is None:
                conn.execute("""INSERT INTO notams (notam_id, category, priority, text, valid_from, valid_to, status,
                                created_utc, created_by, source, location) VALUES (?,?,?,?,?,?, 'ACTIVE', ?, ?, ?, ?)""",
                             (nid, cat, prio, r["text"], r["valid_from"], r["valid_to"] or "PERM",
                              get_utc_datetime(), username, source, loc))
                stats["new"] += 1
            elif row[2] == source and row[1] != "CANCELLED":
                conn.execute("UPDATE notams SET category=?, priority=?, text=?, valid_from=?, valid_to=? WHERE id=?",
                             (cat, prio, r["text"], r["valid_from"], r["valid_to"] or "PERM", row[0]))
                stats["updated"] += 1
        if cancel_missing is not None:
            cur = conn.execute("SELECT id, notam_id, COALESCE(location,'') FROM notams "
                               "WHERE source=? AND status!='CANCELLED'", (source,))
            for rid, nid, loc in cur.fetchall():
                if (loc or ICAO) in cancel_missing and nid not in seen:
                    conn.execute("UPDATE notams SET status='CANCELLED' WHERE id=?", (rid,))
                    stats["cancelled"] += 1
        conn.commit()
    finally:
        conn.close()
    return stats


def import_text(text, username="manual"):
    """Paste NOTAM text in ICAO format (no API key needed). Returns (stats, number_of_notams_found)."""
    recs = parse_icao_text(text)
    for r in recs:
        if not r["location"]:
            r["location"] = ICAO
    return import_records(recs, username, source="MANUAL"), len(recs)


def sync(username="auto", force=False):
    """Fetch from the API and update the database. Returns a one-line summary (raises NotamApiError)."""
    s = get_settings()
    use_key = bool((s.get("api_key") or "").strip())
    if use_key and not force and calls_used(s) >= int(s["monthly_limit"] or 90):
        msg = f"Monthly API call limit reached ({calls_used(s)}/{s['monthly_limit']}). Raise it in API settings or paste NOTAMs."
        save_settings(last_attempt=_stamp(), last_status=msg)
        raise NotamApiError(msg)
    try:
        try:
            raw = fetch(s) if use_key else fetch_faa(s)
        except NotamApiError:
            if not use_key:
                raise
            raw = fetch_faa(s)                       # key failed / quota - try the key-free source
    except NotamApiError as e:
        save_settings(last_attempt=_stamp(), last_status="Error: " + str(e))
        raise
    recs = [normalize(i) for i in raw]
    locs = {x.strip().upper() for x in s["locations"].replace(";", ",").split(",") if x.strip()}
    st = import_records([r for r in recs if r], username, source="API", cancel_missing=locs)
    msg = (f"OK - {len(raw)} received: {st['new']} new, {st['updated']} updated, {st['cancelled']} cancelled "
           + (f"({calls_used()}/{s['monthly_limit']} calls this month)" if use_key else "(source: FAA, no key)"))
    save_settings(last_attempt=_stamp(), last_ok=_stamp(), last_status=msg)
    add_log(get_utc_datetime(), username, "NOTAM API", msg)
    return msg


def due():
    """True when automatic fetching is enabled, a key exists, the interval elapsed and the quota allows it."""
    s = get_settings()
    if s["enabled"] != "1":
        return False
    if s["api_key"] and calls_used(s) >= int(s["monthly_limit"] or 90):
        return False
    last = s.get("last_attempt")
    if not last:
        return True
    try:
        t = datetime.strptime(last[:16], "%Y-%m-%d %H:%M")
    except ValueError:
        return True
    hours = max(1, int(s["interval_h"] or 12)) if s["api_key"] else 1      # no quota without a key -> hourly
    return _now() - t >= timedelta(hours=hours)
