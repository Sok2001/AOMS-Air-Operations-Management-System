"""
METAR / TAF Parser
Turns the raw text string into simple, readable fields:
Wind / Visibility / Clouds / Temperature / Dew point / QNH / Weather.
Works offline (you can paste any raw METAR) and is also used on AVWX results.
"""

import re
import time

WX_INTENSITY = {"-": "Light", "+": "Heavy", "VC": "In the vicinity"}
WX_DESCRIPTOR = {"MI": "Shallow", "BC": "Patches of", "PR": "Partial", "DR": "Low drifting",
                 "BL": "Blowing", "SH": "Showers of", "TS": "Thunderstorm with", "FZ": "Freezing"}
WX_PHENOMENA = {"DZ": "Drizzle", "RA": "Rain", "SN": "Snow", "SG": "Snow grains", "IC": "Ice crystals",
                "PL": "Ice pellets", "GR": "Hail", "GS": "Small hail", "UP": "Unknown precipitation",
                "BR": "Mist", "FG": "Fog", "FU": "Smoke", "VA": "Volcanic ash", "DU": "Dust",
                "SA": "Sand", "HZ": "Haze", "PY": "Spray", "PO": "Dust whirls", "SQ": "Squalls",
                "FC": "Funnel cloud", "SS": "Sandstorm", "DS": "Duststorm"}
CLOUD_COVER = {"FEW": "Few", "SCT": "Scattered", "BKN": "Broken", "OVC": "Overcast", "VV": "Vertical visibility"}

_WX_RE = re.compile(r"^(\+|-|VC)?(MI|BC|PR|DR|BL|SH|TS|FZ)?((?:DZ|RA|SN|SG|IC|PL|GR|GS|UP|BR|FG|FU|VA|DU|SA|HZ|PY|PO|SQ|FC|SS|DS)+)$")
_WIND_RE = re.compile(r"^(\d{3}|VRB)(\d{2,3})(?:G(\d{2,3}))?(KT|MPS)$")
_CLOUD_RE = re.compile(r"^(FEW|SCT|BKN|OVC|VV)(\d{3}|///)(CB|TCU)?$")
_TEMP_RE = re.compile(r"^(M?\d{2})/(M?\d{2})?$")

_latest = {"parsed": None, "ts": 0.0}


def set_latest(parsed):
    """Remember the last decoded METAR (used by dashboard / alerts / AI)."""
    _latest["parsed"] = parsed
    _latest["ts"] = time.time()


def get_latest():
    return _latest["parsed"]


def latest_age_seconds():
    return time.time() - _latest["ts"] if _latest["ts"] else None


def _temp(v):
    return None if v is None else -int(v[1:]) if v.startswith("M") else int(v)


def _decode_wx(token):
    m = _WX_RE.match(token)
    if not m:
        return None
    inten, desc, codes = m.groups()
    parts = []
    if inten:
        parts.append(WX_INTENSITY[inten])
    if desc:
        parts.append(WX_DESCRIPTOR[desc])
    parts += [WX_PHENOMENA[codes[i:i + 2]] for i in range(0, len(codes), 2)]
    return " ".join(parts)


def _decode(tokens):
    """Decode the weather tokens shared by METAR and TAF groups."""
    d = {"wind_dir": None, "wind_kt": None, "gust_kt": None, "wind_variable": False,
         "wind_from": None, "wind_to": None,
         "visibility_m": None, "cavok": False, "clouds": [], "ceiling_ft": None,
         "weather": [], "temp_c": None, "dewpoint_c": None, "qnh_hpa": None}
    for t in tokens:
        if t == "CAVOK":
            d["cavok"] = True
            d["visibility_m"] = 9999
            continue
        m = _WIND_RE.match(t)
        if m:
            dr, sp, gu, unit = m.groups()
            k = 1.94384 if unit == "MPS" else 1.0
            d["wind_variable"] = dr == "VRB"
            d["wind_dir"] = None if dr == "VRB" else int(dr)
            d["wind_kt"] = round(int(sp) * k)
            d["gust_kt"] = round(int(gu) * k) if gu else None
            continue
        m = re.match(r"^(\d{3})V(\d{3})$", t)
        if m:
            d["wind_from"], d["wind_to"] = int(m.group(1)), int(m.group(2))
            continue
        if re.match(r"^\d{4}$", t) and d["visibility_m"] is None:
            d["visibility_m"] = int(t)
            continue
        m = re.match(r"^(M?)(\d+)(?:/(\d+))?SM$", t)          # US style (statute miles)
        if m and d["visibility_m"] is None:
            miles = int(m.group(2)) if not m.group(3) else int(m.group(2)) / int(m.group(3))
            d["visibility_m"] = round(miles * 1609)
            continue
        m = _CLOUD_RE.match(t)
        if m:
            cover, h, ext = m.groups()
            ft = None if h == "///" else int(h) * 100
            d["clouds"].append({"cover": cover, "height_ft": ft, "type": ext or ""})
            if cover in ("BKN", "OVC", "VV") and ft is not None:
                d["ceiling_ft"] = ft if d["ceiling_ft"] is None else min(d["ceiling_ft"], ft)
            continue
        if t in ("NSC", "NCD", "SKC", "CLR"):
            continue
        m = _TEMP_RE.match(t)
        if m and "/" in t:
            d["temp_c"] = _temp(m.group(1))
            d["dewpoint_c"] = _temp(m.group(2)) if m.group(2) else None
            continue
        m = re.match(r"^Q(\d{4})$", t)
        if m:
            d["qnh_hpa"] = int(m.group(1))
            continue
        m = re.match(r"^A(\d{4})$", t)
        if m:
            d["qnh_hpa"] = round(int(m.group(1)) / 100 * 33.8639)
            continue
        wx = _decode_wx(t)
        if wx:
            d["weather"].append(wx)
    return d


def flight_rules(vis_m, ceiling_ft):
    """VFR / MVFR / IFR / LIFR from visibility (m) and ceiling (ft)."""
    v = 9999 if vis_m is None else vis_m
    c = 99999 if ceiling_ft is None else ceiling_ft
    if v < 1600 or c < 500:
        return "LIFR"
    if v < 4800 or c < 1000:
        return "IFR"
    if v <= 8000 or c <= 3000:
        return "MVFR"
    return "VFR"


def parse_metar(raw):
    """Decode a raw METAR/SPECI string. Returns a dict or None if empty."""
    if not raw or not raw.strip():
        return None
    raw = " ".join(raw.strip().replace("=", " ").split())
    tokens = raw.upper().split()
    if tokens and tokens[0] in ("METAR", "SPECI"):
        tokens = tokens[1:]
    out = {"raw": raw, "station": None, "time": None, "auto": False}
    if tokens and re.match(r"^[A-Z]{4}$", tokens[0]):
        out["station"] = tokens.pop(0)
    # stop at trend / remarks: they describe future or extra info
    for stop in ("BECMG", "TEMPO", "NOSIG", "RMK"):
        if stop in tokens:
            tokens = tokens[:tokens.index(stop)]
    body = []
    for t in tokens:
        if re.match(r"^\d{6}Z$", t):
            out["time"] = f"{t[:2]}/{t[2:4]}:{t[4:6]}Z"
        elif t in ("AUTO", "COR"):
            out["auto"] = out["auto"] or t == "AUTO"
        else:
            body.append(t)
    out.update(_decode(body))
    out["flight_rules"] = flight_rules(out["visibility_m"], out["ceiling_ft"])
    return out


def parse_taf(raw):
    """Split a raw TAF into its change groups (BASE / BECMG / TEMPO / FM / PROB)."""
    if not raw or not raw.strip():
        return []
    text = " ".join(raw.strip().replace("=", " ").split()).upper()
    parts = re.split(r"\s(?=(?:BECMG|TEMPO|FM\d{6}|PROB\d{2})\b)", text)
    groups = []
    for i, part in enumerate(parts):
        tokens = part.split()
        kind = "BASE"
        if i > 0:
            kind = tokens[0] if not tokens[0].startswith("FM") else "FM"
        if i == 0:
            tokens = [t for t in tokens if t not in ("TAF", "AMD", "COR")]
        d = _decode([t for t in tokens if not re.match(r"^\d{4}/\d{4}$", t)])
        d["flight_rules"] = flight_rules(d["visibility_m"], d["ceiling_ft"])
        d["type"] = kind
        d["text"] = part
        groups.append(d)
    return groups


def describe_wind(d):
    if d.get("wind_kt") is None:
        return "–"
    if d.get("wind_kt") == 0:
        return "Calm"
    direction = "VRB" if d.get("wind_variable") else f"{d['wind_dir']:03d}°"
    s = f"{direction} / {d['wind_kt']} kt"
    if d.get("gust_kt"):
        s += f" G{d['gust_kt']}"
    return s


def describe_visibility(d):
    v = d.get("visibility_m")
    if v is None:
        return "–"
    return "10 km+" if v >= 9999 else (f"{v / 1000:.1f} km" if v >= 1000 else f"{v} m")


def describe_clouds(d):
    if d.get("cavok"):
        return "CAVOK"
    if not d.get("clouds"):
        return "No significant cloud"
    return ", ".join(f"{c['cover']} {c['height_ft'] if c['height_ft'] is not None else '?'} ft{(' ' + c['type']) if c['type'] else ''}"
                     for c in d["clouds"])


def summary_lines(d):
    """Readable dictionary of the decoded METAR for display."""
    return {
        "Wind": describe_wind(d),
        "Visibility": describe_visibility(d),
        "Clouds": describe_clouds(d),
        "Temperature": f"{d['temp_c']} °C" if d.get("temp_c") is not None else "–",
        "Dew point": f"{d['dewpoint_c']} °C" if d.get("dewpoint_c") is not None else "–",
        "QNH": f"{d['qnh_hpa']} hPa" if d.get("qnh_hpa") is not None else "–",
        "Weather": ", ".join(d["weather"]) if d.get("weather") else "None",
        "Flight rules": d.get("flight_rules", "–"),
    }
