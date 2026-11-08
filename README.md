# AOMS — Air Operations Management System

### Developed by Sofia Karkar

**A Python Desktop Application for Airport Operations Management and AI-Assisted Decision Support**

AOMS is a Python-based desktop application designed to support airport operations and air traffic management. It provides an integrated dashboard for monitoring and managing airport activities.

The system brings together flight operations, runway monitoring, weather information, NOTAMs, airport capacity, ATFCM/CTOT, live air traffic monitoring, operational alerts, and AI-assisted analysis.

## Main Features

- Flight Operations Management
- Runway Monitoring
- Weather Information (METAR / TAF)
- NOTAM Management
- Airport Capacity Monitoring
- ATFCM / CTOT Management
- Live Air Traffic Monitoring
- Operational Alerts
- AI-Assisted Analysis and Decision Support
- Statistics and Reports
- User Authentication and Access Control

## Technologies Used

- Python
- CustomTkinter
- SQLite
- REST APIs
- Pillow

## Developer

**Sofia Karkar**
Software Developer | Information Systems

---

*This project is an academic and technical decision-support prototype. It is not certified for real-world air traffic control operations. All operational decisions remain the responsibility of qualified human controllers.*

## Run

Create your environment file before the first launch:

    cp .env.example .env

Edit `.env` and set a strong, unique `ADMIN_PASSWORD`. Add your own API keys only if needed.

    pip install -r requirements.txt
    python main.py            # graphical interface
    python main.py --cli      # console menu
    python main.py --demo     # load demo data (flights, NOTAM, CTOT) then start

Windows: double-click `run_windows.bat`.

On first launch, the application creates `aoms.db` and initializes the administrator account using the `ADMIN_USERNAME` and `ADMIN_PASSWORD` settings.
Before the first launch, create `.env` from `.env.example` and set a strong, unique `ADMIN_PASSWORD`. Keep `.env` private and never upload it to GitHub.
Existing databases are upgraded automatically (new tables are created at start-up).

## What is inside (mapped to the project description)
| Description | Screen / module |
|---|---|
| 2. Flight management | Flights - `flight.py`, `progress.py`, `clearance.py` |
| 3. Runway management | Runways - `runway.py` (AVAILABLE / OCCUPIED / CLOSED / MAINTENANCE) |
| 4. Live traffic (ADS-B / OpenSky) | Live Flights, **Air Map** (radar view, click an aircraft) |
| 5. Weather: METAR + TAF | Weather - `metar_parser.py` decodes Wind / Vis / Clouds / Temp / Dew point / QNH / Weather; paste any raw METAR to decode offline |
| 6. NOTAM | NOTAM - `notam.py` auto-classifies category + priority; a NOTAM that closes a runway reduces the capacity |
| 7. Airport capacity | Capacity - `capacity.py` (next-60-min demand vs hourly capacity, reduced when a runway is closed) |
| 8. ATFCM | ATFCM - `atfcm.py` (CTOT, delay, regulation, window CTOT -5/+10 min) |
| 9. AI decision support | AI Support - `ai_support.py` (congestion forecast, runway suggestion, anomalies, conflict detection) |
| 10. Dashboard | Dashboard (flights, runways, weather, alerts) + alert counter in the header |
| 11. Map | Air Map (runways, range rings, aircraft, conflicts in red, Demo traffic button) |
| 12. Database | SQLite - tables: users, flights, runways, logs, notams, atfcm, alerts + (v3) airports, aip_*, charts |
| 13. Users & permissions | Role based (RBAC) in `auth.py` |
| 14. Statistics & reports | Reports - charts + CSV export |
| **v3** AIP data of DAAG | **Airport Data** - `aip_data.py`, `aip_loader.py`, `data/daag/*.json` |
| **v3** Chart library | **Charts** - `aip_pages.py`, files in `charts/DAAG/` |
| 17. Scenario | Run `python main.py --demo` to see HIGH TRAFFIC LOAD / CAPACITY LIMIT / CTOT alerts |

## v3 - Airport data & chart library (DAAG)
- `data/daag/*.json` = AIP AD 2.DAAG transcribed in structured form (runways, declared distances, navaids, frequencies,
  86 stands, aprons, taxiways, obstacles, ATS airspace and services). Imported into the database at start-up
  (`aip_loader.py`, only when the files change). Source/AIRAC and known discrepancies are listed in the Notes tab.
- **Airport Data** page (read only): Info, Runways, Navaids, Frequencies, Stands (searchable), Taxiways, Obstacles, Notes.
- **Charts** page: library catalogued from AIP AD 2.24 (AD, APDC, AOC, PATC, SID, ATCSMAC, IAC, VAC). Provided so far:
  `AD`, `APDC1`, `APDC-DATA1`, `IAC1`, `IAC3`-`IAC9`, `VAC1`, `VAC2` (dates in `charts/DAAG/charts_meta.json`). To add a chart: copy `<CODE>.pdf` and/or `<CODE>.png` (e.g. `IAC1.pdf`, `SID2.png`)
  into `charts/DAAG/` and press *Rescan*, or use *Import chart...* (Administrator / ATC Supervisor).
  A PNG gives the in-app zoom/pan preview; a PDF alone opens with the system viewer (a preview is generated
  automatically when PyMuPDF or poppler `pdftoppm` is installed).
- `config.py` corrected against the AIP: CTR 6 NM / 450 M, RWY 05/23 width 60 m, TRUE runway bearings
  (053/233/092/272, used with METAR winds) + magnetic bearings, VOR identifier ALR.
- New permissions: `charts` (all roles), `edit_charts` (Administrator, ATC Supervisor). `airport_info` opens Airport Data.
- New dependency: `pillow` (chart preview). Run `pip install -r requirements.txt` again.
- Another airport: create `data/<icao>/` with the same JSON files and `charts/<ICAO>/` (the pages currently use `config.ICAO`).

## v3.4 - Automatic NOTAM + dialogs
- **NOTAM > ⚙ API**: enter a *free* ICAO API Data Service key (https://applications.icao.int/dataservices/), the locations
  (default `DAAG,DAAA` = aerodrome + Algiers FIR), the interval (default 12 h) and a monthly call limit (default 90:
  the free tier is limited). With *Fetch automatically* ticked the program imports NOTAMs in the background;
  **NOTAM > ⟳ Fetch (API)** fetches immediately. NOTAMs that disappear from the feed or are cancelled (NOTAMC) are
  marked CANCELLED. FIR / other-aerodrome NOTAMs are stored but never close DAAG runways.
- **NOTAM > Paste NOTAM**: paste NOTAMs in ICAO format (A0123/26 NOTAMN ... A) B) C) E)) - no key needed.
- Key storage: local database, or the `ICAO_API_KEY` environment variable. It is never logged or shown in errors.
- Flight dialog: Save/Cancel are packed first, so they stay visible on any screen scaling; the form scrolls.
- Credit line changed to `إعداد رحمة بوعلي`.

## v3.5 - Colored sidebar icons
- One colored icon per page (`assets/icons/*.png`, loaded by `icons.py`). To redraw or change them edit `make_icons.py`
  and run `python make_icons.py`. If an icon file or Pillow is missing the old text glyph is shown instead.

## Alerts (alerts.py)
HIGH TRAFFIC LOAD, RUNWAY CAPACITY APPROACHING LIMIT, RWY CLOSED, CTOT APPROACHING / WINDOW / MISSED,
LOW VISIBILITY / LVP, STRONG WIND, THUNDERSTORM, critical NOTAM, emergency squawk (7500/7600/7700),
duplicate squawk, two aircraft on one runway, aircraft assigned to a closed runway, stand conflict.
Alerts are stored, can be acknowledged, and clear themselves when the situation ends.

## AI levels (ai_support.py)
Level 4 is implemented with transparent rules + statistics (no black box), so it can be explained to a committee:
- Congestion prediction: rolling 60-min demand for the next 2 hours.
- Runway suggestion: headwind / crosswind / tailwind limits, ILS needed in IFR, closures.
- Conflict detection: 5 NM / 1000 ft now and at the closest point of approach in the next 5 min.
- Anomaly detection: see alerts above.
A real ML model can replace these functions later without changing the screens.

## Limits you can tune (config.py)
Capacity (`ARRIVAL_CAPACITY`, `DEPARTURE_CAPACITY`), alert ratios, CTOT tolerance, weather minima,
cross/tail-wind limits, conflict separation.

## Roles
Administrator (all), ATC Supervisor, Tower / Ground / Approach Controller, Observer (view only), Maintenance.
New permissions: `notam`, `edit_notam`, `capacity`, `atfcm`, `ctot`, `alerts`, `ack_alerts`, `ai_support`.

## Files
- main.py, aoms_gui.py (CustomTkinter), seed_demo.py, config.py, database.py
- flight.py, runway.py, traffic.py, progress.py, operations.py, airport_statistics.py
- **v3:** aip_loader.py, aip_data.py, aip_pages.py, data/, charts/
- **new:** metar_parser.py, notam.py, capacity.py, atfcm.py, alerts.py, ai_support.py
- auth.py, users.py, login.py, change_password.py, logs.py, backup.py, weather.py, api.py, live_flights.py, clearance.py, dashboard.py
- legacy/  original Tkinter prototypes

## Security
Never publish `.env` or files containing private API keys and passwords. Sensitive configuration values are read from environment variables.
Anyone who has the token can use your AVWX quota - generate a new one if the project was shared.
