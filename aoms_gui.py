"""
AOMS - Airport Operations Management System
Professional GUI (CustomTkinter)

Run:  python aoms_gui.py
Needs: pip install customtkinter requests
Uses your existing modules: config, database, auth, logs, utc_time, api, backup, users
"""

import csv
import math
import os
import random
import sqlite3
import threading
import time
from datetime import datetime, timedelta
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

import customtkinter as ctk

from config import (AIRPORT_NAME, ICAO, IATA, ARRIVAL_CAPACITY, DEPARTURE_CAPACITY,
                    TOWER_FREQUENCY, GROUND_FREQUENCY, APPROACH_FREQUENCY, ATIS_FREQUENCY)
from database import DATABASE
from auth import (verify_password, hash_password, check_permission, is_strong_password,
                  count_administrators, MAX_ATTEMPTS, LOCK_DURATION, SESSION_TIMEOUT)
from logs import add_log
from utc_time import get_utc_time, get_utc_date, get_utc_datetime
from api import get_metar
from users import ROLES
import backup as backup_mod
import metar_parser
import notam as notam_mod
import atfcm as atfcm_mod
import capacity as capacity_mod
import alerts as alerts_mod
import ai_support
from config import ARP_LAT, ARP_LON, RUNWAY_05, RUNWAY_09
import sys
import aip_loader
import aip_pages
import icons
import notam_api
import notam_ui

# ------------------------------------------------------------------ theme
BG = "#0b1220"
SIDEBAR = "#0f1a2e"
PANEL = "#162238"
PANEL2 = "#1c2b45"
ACCENT = "#38bdf8"
ACCENT_DARK = "#0369a1"
TEXT = "#e2e8f0"
MUTED = "#8aa0bd"
GREEN = "#22c55e"
RED = "#ef4444"
AMBER = "#f59e0b"

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

AIRLINES = {"DAH": "AIR ALGERIE", "DTR": "TASSILI", "THY": "TURKISH", "QTR": "QATAR",
            "TAR": "TUNISAIR", "AFR": "AIR FRANCE", "DLH": "LUFTHANSA",
            "UAE": "EMIRATES", "ETD": "ETIHAD"}

PHASES = ["SCHEDULED", "BOARDING", "PUSHBACK", "STARTUP", "TAXI", "LINE UP", "TAKEOFF",
          "AIRBORNE", "ARRIVING", "LANDED", "PARKED", "CANCELLED", "DELAYED"]

RUNWAY_LIST = ["05", "23", "09", "27"]

FLIGHT_COLS = ["flight_number", "airline", "registration", "aircraft", "wake", "departure",
               "destination", "sid", "star", "runway", "stand", "etd", "eta",
               "flight_level", "speed", "squawk", "status"]
FLIGHT_HEAD = ["Flight", "Airline", "Reg", "Aircraft", "Wake", "From", "To", "SID", "STAR",
               "RWY", "Stand", "ETD", "ETA", "FL", "Speed", "Squawk", "Status"]


# ------------------------------------------------------------------ db helpers
def db_all(sql, params=()):
    conn = sqlite3.connect(DATABASE)
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def db_one(sql, params=()):
    conn = sqlite3.connect(DATABASE)
    try:
        return conn.execute(sql, params).fetchone()
    finally:
        conn.close()


def db_exec(sql, params=()):
    conn = sqlite3.connect(DATABASE)
    try:
        cur = conn.execute(sql, params)
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


def ensure_runways():
    try:
        if db_one("SELECT COUNT(*) FROM runways")[0] == 0:
            for r in RUNWAY_LIST:
                db_exec("INSERT INTO runways (runway, status) VALUES (?, ?)", (r, "AVAILABLE"))
    except sqlite3.Error:
        pass


def log(user, action, details=""):
    try:
        add_log(get_utc_datetime(), user["username"], action, details)
    except Exception:
        pass


# ------------------------------------------------------------------ widgets
def style_tree():
    s = ttk.Style()
    s.theme_use("clam")
    s.configure("Treeview", background=PANEL, fieldbackground=PANEL, foreground=TEXT,
                rowheight=30, borderwidth=0, font=("Segoe UI", 10))
    s.configure("Treeview.Heading", background="#24365a", foreground=TEXT, relief="flat",
                font=("Segoe UI", 10, "bold"), padding=6)
    s.map("Treeview", background=[("selected", ACCENT_DARK)], foreground=[("selected", "white")])
    s.map("Treeview.Heading", background=[("active", "#2f4670")])
    s.configure("Vertical.TScrollbar", background=PANEL2, troughcolor=PANEL, borderwidth=0,
                arrowcolor=MUTED)


class Table(ctk.CTkFrame):
    STATUS_TAGS = ("LANDED", "PARKED", "CANCELLED", "DELAYED", "AIRBORNE", "CRITICAL", "HIGH", "MISSED",
                   "WARNING", "MEDIUM", "APPROACHING", "IN WINDOW", "DEPARTED", "EXPIRED", "ACKNOWLEDGED")

    def __init__(self, master, columns, headings=None, widths=None, height=10, **kw):
        super().__init__(master, fg_color=PANEL, corner_radius=12, **kw)
        self.tree = ttk.Treeview(self, columns=columns, show="headings", height=height)
        for i, c in enumerate(columns):
            self.tree.heading(c, text=(headings or columns)[i])
            self.tree.column(c, width=(widths[i] if widths else 100), anchor="w", minwidth=50)
        sb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=8)
        sb.pack(side="right", fill="y", pady=8, padx=(0, 4))
        self.tree.tag_configure("odd", background="#1a2a45")
        self.tree.tag_configure("LANDED", foreground="#86efac")
        self.tree.tag_configure("PARKED", foreground="#86efac")
        self.tree.tag_configure("CANCELLED", foreground="#fca5a5")
        self.tree.tag_configure("DELAYED", foreground="#fcd34d")
        self.tree.tag_configure("AIRBORNE", foreground="#7dd3fc")
        for name, color in (("CRITICAL", "#fca5a5"), ("HIGH", "#fca5a5"), ("MISSED", "#fca5a5"),
                            ("WARNING", "#fcd34d"), ("MEDIUM", "#fcd34d"), ("APPROACHING", "#fcd34d"),
                            ("IN WINDOW", "#7dd3fc"), ("DEPARTED", "#86efac"), ("EXPIRED", "#64748b"),
                            ("ACKNOWLEDGED", "#64748b")):
            self.tree.tag_configure(name, foreground=color)

    def set(self, rows, status_index=None):
        self.tree.delete(*self.tree.get_children())
        for i, r in enumerate(rows):
            tags = ["odd"] if i % 2 else []
            if status_index is not None and r[status_index] in self.STATUS_TAGS:
                tags = [r[status_index]]
            self.tree.insert("", "end", values=["" if v is None else v for v in r], tags=tags)

    def selected(self):
        sel = self.tree.selection()
        return self.tree.item(sel[0])["values"] if sel else None


def card(master, title, value="0", color=ACCENT):
    f = ctk.CTkFrame(master, fg_color=PANEL, corner_radius=14)
    ctk.CTkLabel(f, text=title.upper(), text_color=MUTED,
                 font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w", padx=16, pady=(14, 0))
    lbl = ctk.CTkLabel(f, text=value, text_color=color, font=ctk.CTkFont(size=30, weight="bold"))
    lbl.pack(anchor="w", padx=16, pady=(0, 14))
    f.value = lbl
    return f


def heading(master, text, sub=None):
    box = ctk.CTkFrame(master, fg_color="transparent")
    ctk.CTkLabel(box, text=text, font=ctk.CTkFont(size=22, weight="bold"),
                 text_color=TEXT).pack(anchor="w")
    if sub:
        ctk.CTkLabel(box, text=sub, text_color=MUTED).pack(anchor="w")
    return box


def btn(master, text, cmd, color=ACCENT_DARK, width=120, **kw):
    return ctk.CTkButton(master, text=text, command=cmd, fg_color=color, width=width,
                         hover_color=kw.pop("hover", "#075985"), corner_radius=8, height=34, **kw)


def mlabel(master, justify="left", **kw):
    """CTkLabel with left-aligned multi-line text (`justify` is not a CTkLabel option)."""
    lbl = ctk.CTkLabel(master, **kw)
    try:
        lbl._label.configure(justify=justify)
    except Exception:
        pass
    return lbl


def run_async(widget, work, done):
    """Run `work` in a thread, call `done(result)` on the Tk thread."""
    def target():
        try:
            res = work()
        except Exception as e:  # noqa
            res = e
        try:
            widget.after(0, lambda: done(res))
        except Exception:
            pass
    threading.Thread(target=target, daemon=True).start()


# ------------------------------------------------------------------ login
class LoginWindow(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("AOMS - Login")
        self.geometry("460x560")
        self.resizable(False, False)
        self.configure(fg_color=BG)
        self.user = None
        style_tree()

        wrap = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=20)
        wrap.pack(fill="both", expand=True, padx=30, pady=30)
        ctk.CTkLabel(wrap, text="✈", font=ctk.CTkFont(size=56), text_color=ACCENT).pack(pady=(30, 0))
        ctk.CTkLabel(wrap, text="AOMS", font=ctk.CTkFont(size=30, weight="bold")).pack()
        ctk.CTkLabel(wrap, text="Airport Operations Management System",
                     text_color=MUTED).pack(pady=(0, 4))
        ctk.CTkLabel(wrap, text=f"{AIRPORT_NAME}  ({ICAO})", text_color=MUTED,
                     font=ctk.CTkFont(size=11)).pack(pady=(0, 24))

        self.u = ctk.CTkEntry(wrap, placeholder_text="Username", width=300, height=42)
        self.u.pack(pady=6)
        self.p = ctk.CTkEntry(wrap, placeholder_text="Password", show="•", width=300, height=42)
        self.p.pack(pady=6)
        self.msg = ctk.CTkLabel(wrap, text="", text_color=RED, wraplength=300)
        self.msg.pack(pady=6)
        ctk.CTkButton(wrap, text="Sign in", width=300, height=44, command=self.attempt,
                      font=ctk.CTkFont(size=14, weight="bold")).pack(pady=6)
        ctk.CTkLabel(wrap, text=f"UTC {get_utc_datetime()}", text_color=MUTED).pack(side="bottom", pady=14)
        self.bind("<Return>", lambda e: self.attempt())
        self.u.focus()

    def attempt(self):
        username, password = self.u.get().strip(), self.p.get().strip()
        if not username or not password:
            self.msg.configure(text="Enter username and password.")
            return
        row = db_one("""SELECT id, username, password, full_name, role, active,
                        login_attempts, locked_until FROM users WHERE username=?""", (username,))
        if row is None:
            self.msg.configure(text="Invalid username or password.")
            add_log(get_utc_datetime(), username, "LOGIN FAILED", "Unknown user")
            return
        uid, uname, pw, full, role, active, attempts, locked = row
        attempts = attempts or 0
        if locked:
            try:
                until = datetime.strptime(locked, "%Y-%m-%d %H:%M:%S")
                if datetime.now() < until:
                    mins = int((until - datetime.now()).total_seconds() // 60) + 1
                    self.msg.configure(text=f"Account locked. Try again in {mins} min.")
                    return
                db_exec("UPDATE users SET locked_until=NULL, login_attempts=0 WHERE id=?", (uid,))
                attempts = 0
            except ValueError:
                pass
        if active == 0:
            self.msg.configure(text="Account deactivated. Contact administrator.")
            return
        if not verify_password(password, pw):
            attempts += 1
            if attempts >= MAX_ATTEMPTS:
                until = (datetime.now() + timedelta(minutes=LOCK_DURATION)).strftime("%Y-%m-%d %H:%M:%S")
                db_exec("UPDATE users SET locked_until=?, login_attempts=? WHERE id=?",
                        (until, attempts, uid))
                self.msg.configure(text=f"Too many attempts. Locked {LOCK_DURATION} min.")
                add_log(get_utc_datetime(), uname, "ACCOUNT LOCKED", f"After {attempts} attempts")
            else:
                db_exec("UPDATE users SET login_attempts=? WHERE id=?", (attempts, uid))
                self.msg.configure(text=f"Invalid password. {MAX_ATTEMPTS - attempts} attempts left.")
                add_log(get_utc_datetime(), uname, "LOGIN FAILED", "Invalid password")
            return
        db_exec("UPDATE users SET login_attempts=0, locked_until=NULL, last_login=? WHERE id=?",
                (get_utc_datetime(), uid))
        add_log(get_utc_datetime(), uname, "LOGIN", "GUI login")
        self.user = {"id": uid, "username": uname, "full_name": full, "role": role}
        self.destroy()


# ------------------------------------------------------------------ pages
class Page(ctk.CTkFrame):
    def __init__(self, app):
        super().__init__(app.content, fg_color="transparent")
        self.app = app
        self.user = app.user

    def refresh(self):
        pass

    def can(self, action):
        return check_permission(self.user, action)


class DashboardPage(Page):
    def __init__(self, app):
        super().__init__(app)
        self._wx_busy, self._wx_next = False, 0.0
        heading(self, "Dashboard", f"{AIRPORT_NAME}").pack(anchor="w", pady=(0, 12))
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x")
        self.cards = {}
        for i, (k, t, c) in enumerate([("total", "Total flights", ACCENT),
                                       ("dep", "Departures", GREEN), ("arr", "Arrivals", AMBER),
                                       ("occ", "Occupied RWY", RED), ("sched", "Scheduled", TEXT),
                                       ("board", "Boarding", ACCENT)]):
            cd = card(row, t, "0", c)
            cd.grid(row=0, column=i, padx=5, sticky="nsew")
            row.columnconfigure(i, weight=1)
            self.cards[k] = cd

        mid = ctk.CTkFrame(self, fg_color="transparent")
        mid.pack(fill="x", pady=12)
        mid.columnconfigure((0, 1), weight=1, uniform="a")
        self.rw = ctk.CTkFrame(mid, fg_color=PANEL, corner_radius=14)
        self.rw.grid(row=0, column=0, padx=5, sticky="nsew")
        ctk.CTkLabel(self.rw, text="RUNWAYS", text_color=MUTED,
                     font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w", padx=16, pady=(12, 4))
        self.rw_labels = {}
        for r in RUNWAY_LIST:
            l = ctk.CTkLabel(self.rw, text=f"RWY {r}", anchor="w")
            l.pack(fill="x", padx=16, pady=2)
            self.rw_labels[r] = l
        ctk.CTkLabel(self.rw, text="").pack(pady=4)

        fr = ctk.CTkFrame(mid, fg_color=PANEL, corner_radius=14)
        fr.grid(row=0, column=1, padx=5, sticky="nsew")
        ctk.CTkLabel(fr, text="AIRPORT INFO", text_color=MUTED,
                     font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w", padx=16, pady=(12, 4))
        for k, v in [("ICAO / IATA", f"{ICAO} / {IATA}"), ("Tower", TOWER_FREQUENCY),
                     ("Ground", GROUND_FREQUENCY), ("Approach", APPROACH_FREQUENCY),
                     ("ATIS", ATIS_FREQUENCY)]:
            ctk.CTkLabel(fr, text=f"{k:<12} {v}", anchor="w",
                         font=ctk.CTkFont(family="Consolas", size=13)).pack(fill="x", padx=16, pady=2)
        ctk.CTkLabel(fr, text="").pack(pady=4)

        low = ctk.CTkFrame(self, fg_color="transparent")
        low.pack(fill="x", pady=(0, 8))
        low.columnconfigure((0, 1), weight=1, uniform="b")
        wx = ctk.CTkFrame(low, fg_color=PANEL, corner_radius=14)
        wx.grid(row=0, column=0, padx=5, sticky="nsew")
        ctk.CTkLabel(wx, text="WEATHER (METAR)", text_color=MUTED,
                     font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w", padx=16, pady=(12, 4))
        self.wx_lbl = mlabel(wx, text="Loading METAR…", anchor="w", justify="left",
                                   font=ctk.CTkFont(family="Consolas", size=13))
        self.wx_lbl.pack(fill="x", padx=16, pady=(0, 12))
        al = ctk.CTkFrame(low, fg_color=PANEL, corner_radius=14)
        al.grid(row=0, column=1, padx=5, sticky="nsew")
        ctk.CTkLabel(al, text="ALERTS", text_color=MUTED,
                     font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w", padx=16, pady=(12, 4))
        self.al_lbls = [mlabel(al, text="", anchor="w", justify="left", wraplength=420) for _ in range(4)]
        for l in self.al_lbls:
            l.pack(fill="x", padx=16, pady=1)
        ctk.CTkLabel(al, text="").pack(pady=2)

        ctk.CTkLabel(self, text="Latest flights", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=6)
        self.table = Table(self, ["f", "from", "to", "st", "rwy", "etd"],
                           ["Flight", "From", "To", "Status", "RWY", "ETD"],
                           [120, 100, 100, 140, 80, 100], height=4)
        self.table.pack(fill="both", expand=True, pady=6)

    def refresh(self):
        try:
            c = lambda sql, p=(): db_one(sql, p)[0]
            self.cards["total"].value.configure(text=c("SELECT COUNT(*) FROM flights"))
            self.cards["dep"].value.configure(text=c("SELECT COUNT(*) FROM flights WHERE departure=?", (ICAO,)))
            self.cards["arr"].value.configure(text=c("SELECT COUNT(*) FROM flights WHERE destination=?", (ICAO,)))
            self.cards["occ"].value.configure(text=c("SELECT COUNT(*) FROM runways WHERE status='OCCUPIED'"))
            self.cards["sched"].value.configure(text=c("SELECT COUNT(*) FROM flights WHERE status='SCHEDULED'"))
            self.cards["board"].value.configure(text=c("SELECT COUNT(*) FROM flights WHERE status='BOARDING'"))
            states = dict(db_all("SELECT runway, status FROM runways"))
            colors = {"AVAILABLE": GREEN, "OCCUPIED": RED, "CLOSED": MUTED, "MAINTENANCE": AMBER}
            for r, l in self.rw_labels.items():
                st = states.get(r, "N/A")
                l.configure(text=f"●  RWY {r}      {st}", text_color=colors.get(st, TEXT))
            self.table.set(db_all("""SELECT flight_number, departure, destination, status, runway, etd
                                     FROM flights ORDER BY id DESC LIMIT 8"""), status_index=3)
        except sqlite3.Error as e:
            messagebox.showerror("Database", str(e))
        self._update_wx()
        self._update_alerts()

    def _update_wx(self):
        if not metar_parser.get_latest() and not self._wx_busy and time.time() >= self._wx_next and self.can("metar"):
            self._wx_busy = True
            run_async(self, lambda: get_metar(ICAO), self._wx_done)
        w = metar_parser.get_latest()
        if w:
            s = metar_parser.summary_lines(w)
            wx = "" if s["Weather"] == "None" else "   " + s["Weather"]
            self.wx_lbl.configure(text=f"WIND   {s['Wind']}\nVIS    {s['Visibility']}\nQNH    {s['QNH']}\n"
                                       f"RULES  {s['Flight rules']}{wx}")

    def _wx_done(self, m):
        self._wx_busy = False
        ok = bool(m) and not isinstance(m, Exception) and m.get("raw")
        if ok:
            metar_parser.set_latest(metar_parser.parse_metar(m["raw"]))
        self._wx_next = time.time() + (600 if ok else 120)
        self._update_wx()

    def _update_alerts(self):
        rows = alerts_mod.list_alerts()[:4]
        for i, l in enumerate(self.al_lbls):
            if i < len(rows):
                r = rows[i]
                l.configure(text=f"●  {r[4]}", text_color=MUTED if r[5] == "ACKNOWLEDGED" else LEVEL_COLORS.get(r[2], TEXT))
            else:
                l.configure(text="✓  No active alerts" if i == 0 and not rows else "")


class FlightDialog(ctk.CTkToplevel):
    def __init__(self, parent, flight=None, on_save=None):
        super().__init__(parent)
        self.title("Edit flight" if flight else "Add flight")
        self.geometry("680x720")
        self.minsize(560, 460)
        self.configure(fg_color=BG)
        self.transient(parent)
        self.after(150, self.grab_set)
        self.on_save, self.flight = on_save, flight
        self.widgets = {}
        bar = ctk.CTkFrame(self, fg_color="transparent")      # packed first: Save/Cancel can never be pushed out
        bar.pack(side="bottom", fill="x", padx=16, pady=(0, 14))
        btn(bar, "Save", self.save, GREEN, hover="#15803d").pack(side="right", padx=4)
        btn(bar, "Cancel", self.destroy, PANEL2).pack(side="right", padx=4)
        form = ctk.CTkScrollableFrame(self, fg_color=PANEL, corner_radius=14)
        form.pack(fill="both", expand=True, padx=16, pady=16)
        fields = [("flight_number", "Flight no."), ("airline", "Airline"), ("registration", "Registration"),
                  ("aircraft", "Aircraft type"), ("wake", "Wake", ["L", "M", "H", "J"]),
                  ("departure", "Departure (ICAO)"), ("destination", "Destination (ICAO)"),
                  ("sid", "SID"), ("star", "STAR"), ("runway", "Runway", [""] + RUNWAY_LIST),
                  ("stand", "Stand"), ("etd", "ETD (HH:MM)"), ("eta", "ETA (HH:MM)"),
                  ("flight_level", "Flight level"), ("speed", "Speed (kt)"), ("squawk", "Squawk"),
                  ("status", "Status", PHASES)]
        for i, f in enumerate(fields):
            key, label = f[0], f[1]
            r, c = divmod(i, 2)
            ctk.CTkLabel(form, text=label, text_color=MUTED, anchor="w").grid(
                row=r * 2, column=c, sticky="w", padx=14, pady=(8, 0))
            if len(f) == 3:
                w = ctk.CTkComboBox(form, values=f[2], width=270)
            else:
                w = ctk.CTkEntry(form, width=270)
            w.grid(row=r * 2 + 1, column=c, padx=14, pady=(0, 2))
            self.widgets[key] = w
        if flight:
            for k in FLIGHT_COLS:
                v = flight.get(k)
                self._set(k, "" if v is None else str(v))
            self.widgets["flight_number"].configure(state="disabled")
        else:
            self._set("status", "SCHEDULED")
            self._set("wake", "M")
            self._set("departure", ICAO)

    def _set(self, k, v):
        w = self.widgets[k]
        if isinstance(w, ctk.CTkComboBox):
            w.set(v)
        else:
            w.delete(0, "end")
            w.insert(0, v)

    def _get(self, k):
        return self.widgets[k].get().strip()

    def save(self):
        d = {k: self._get(k) for k in FLIGHT_COLS}
        d["flight_number"] = d["flight_number"].upper()
        for k in ("departure", "destination", "registration", "aircraft"):
            d[k] = d[k].upper()
        if len(d["flight_number"]) < 3:
            return messagebox.showerror("Flight", "Flight number is required.", parent=self)
        if not d["airline"]:
            d["airline"] = AIRLINES.get(d["flight_number"][:3], "UNKNOWN")
        for k in ("etd", "eta"):
            if d[k]:
                try:
                    datetime.strptime(d[k], "%H:%M")
                except ValueError:
                    return messagebox.showerror("Time", f"{k.upper()} must be HH:MM.", parent=self)
        if d["departure"] != ICAO and d["destination"] != ICAO:
            if not messagebox.askyesno("Check route", f"Neither end of the route is {ICAO}. Save anyway?",
                                       parent=self):
                return
        self.on_save(d, self.flight is None)
        self.destroy()


class FlightsPage(Page):
    def __init__(self, app):
        super().__init__(app)
        heading(self, "Flights", "Flight database").pack(anchor="w", pady=(0, 10))
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x", pady=(0, 8))
        self.search = ctk.CTkEntry(bar, placeholder_text="Search flight, airline, route, status…", width=340)
        self.search.pack(side="left")
        self.search.bind("<KeyRelease>", lambda e: self.refresh())
        self.status_f = ctk.CTkComboBox(bar, values=["ALL"] + PHASES, width=140, command=lambda v: self.refresh())
        self.status_f.set("ALL")
        self.status_f.pack(side="left", padx=8)
        if self.can("delete_flight"):
            btn(bar, "Delete", self.delete, RED, 90, hover="#b91c1c").pack(side="right", padx=3)
        if self.can("update_status"):
            btn(bar, "Next phase", self.next_phase, PANEL2, 110).pack(side="right", padx=3)
        if self.can("edit_flight"):
            btn(bar, "Edit", self.edit, PANEL2, 80).pack(side="right", padx=3)
        if self.can("add_flight"):
            btn(bar, "+ Add flight", self.add, ACCENT_DARK, 120).pack(side="right", padx=3)
        self.table = Table(self, FLIGHT_COLS, FLIGHT_HEAD,
                           [90, 120, 80, 70, 50, 70, 70, 80, 80, 50, 60, 60, 60, 50, 60, 60, 100])
        self.table.pack(fill="both", expand=True)
        self.count = ctk.CTkLabel(self, text="", text_color=MUTED)
        self.count.pack(anchor="w", pady=4)

    def refresh(self):
        q = f"%{self.search.get().strip().upper()}%"
        sql = f"SELECT {', '.join(FLIGHT_COLS)} FROM flights WHERE (UPPER(flight_number) LIKE ? OR UPPER(airline) LIKE ? " \
              f"OR UPPER(departure) LIKE ? OR UPPER(destination) LIKE ? OR UPPER(status) LIKE ?)"
        params = [q] * 5
        if self.status_f.get() != "ALL":
            sql += " AND status=?"
            params.append(self.status_f.get())
        sql += " ORDER BY etd, flight_number"
        rows = db_all(sql, params)
        self.table.set(rows, status_index=FLIGHT_COLS.index("status"))
        self.count.configure(text=f"{len(rows)} flight(s)")

    def _selected_dict(self):
        v = self.table.selected()
        if not v:
            messagebox.showinfo("Select", "Select a flight first.")
            return None
        return dict(zip(FLIGHT_COLS, v))

    def add(self):
        FlightDialog(self, None, self._save)

    def edit(self):
        f = self._selected_dict()
        if f:
            FlightDialog(self, f, self._save)

    def _save(self, d, is_new):
        try:
            if is_new:
                if db_one("SELECT 1 FROM flights WHERE flight_number=?", (d["flight_number"],)):
                    return messagebox.showerror("Duplicate", "Flight already exists.")
                cols = FLIGHT_COLS + ["created_utc"]
                db_exec(f"INSERT INTO flights ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
                        [d[k] for k in FLIGHT_COLS] + [get_utc_datetime()])
                log(self.user, "FLIGHT ADDED", d["flight_number"])
            else:
                keys = [k for k in FLIGHT_COLS if k != "flight_number"]
                db_exec(f"UPDATE flights SET {', '.join(k + '=?' for k in keys)} WHERE flight_number=?",
                        [d[k] for k in keys] + [d["flight_number"]])
                log(self.user, "FLIGHT UPDATED", d["flight_number"])
        except sqlite3.Error as e:
            return messagebox.showerror("Database", str(e))
        self.refresh()

    def next_phase(self):
        f = self._selected_dict()
        if not f:
            return
        cur = f["status"]
        i = PHASES.index(cur) if cur in PHASES else -1
        if i >= PHASES.index("PARKED") or i == -1 and cur not in ("", None):
            return messagebox.showinfo("Phase", "Flight is at a final phase. Use Edit to change status.")
        new = PHASES[i + 1]
        db_exec("UPDATE flights SET status=? WHERE flight_number=?", (new, f["flight_number"]))
        log(self.user, "PROGRESS UPDATE", f"{f['flight_number']} -> {new}")
        self.refresh()

    def delete(self):
        f = self._selected_dict()
        if f and messagebox.askyesno("Delete", f"Delete flight {f['flight_number']}?"):
            db_exec("DELETE FROM flights WHERE flight_number=?", (f["flight_number"],))
            log(self.user, "FLIGHT DELETED", f["flight_number"])
            self.refresh()


class RunwaysPage(Page):
    def __init__(self, app):
        super().__init__(app)
        heading(self, "Runways", f"{ICAO} - RWY 05/23 and 09/27, 3500 m x 45 m").pack(anchor="w", pady=(0, 12))
        grid = ctk.CTkFrame(self, fg_color="transparent")
        grid.pack(fill="x")
        grid.columnconfigure((0, 1), weight=1, uniform="r")
        self.status = {}
        for i, r in enumerate(RUNWAY_LIST):
            f = ctk.CTkFrame(grid, fg_color=PANEL, corner_radius=14)
            f.grid(row=i // 2, column=i % 2, padx=6, pady=6, sticky="nsew")
            ctk.CTkLabel(f, text=f"RWY {r}", font=ctk.CTkFont(size=28, weight="bold")).pack(anchor="w", padx=18, pady=(14, 0))
            lab = ctk.CTkLabel(f, text="…", font=ctk.CTkFont(size=14, weight="bold"))
            lab.pack(anchor="w", padx=18)
            self.status[r] = lab
            if self.can("occupy_runway"):
                b = ctk.CTkFrame(f, fg_color="transparent")
                b.pack(anchor="w", padx=14, pady=12)
                for text, st, col in [("Occupy", "OCCUPIED", RED), ("Release", "AVAILABLE", GREEN),
                                      ("Close", "CLOSED", "#475569"), ("Maintenance", "MAINTENANCE", AMBER)]:
                    ctk.CTkButton(b, text=text, width=84, height=30, fg_color=col, hover_color=col,
                                  command=lambda rr=r, s=st: self.set_status(rr, s)).pack(side="left", padx=3)
            else:
                ctk.CTkLabel(f, text="").pack(pady=8)

    def refresh(self):
        colors = {"AVAILABLE": GREEN, "OCCUPIED": RED, "CLOSED": MUTED, "MAINTENANCE": AMBER}
        states = dict(db_all("SELECT runway, status FROM runways"))
        for r, l in self.status.items():
            st = states.get(r, "N/A")
            l.configure(text=f"●  {st}", text_color=colors.get(st, TEXT))

    def set_status(self, r, st):
        if st in ("CLOSED", "MAINTENANCE") and not messagebox.askyesno("Confirm", f"Set RWY {r} to {st}?"):
            return
        db_exec("UPDATE runways SET status=? WHERE runway=?", (st, r))
        log(self.user, "RUNWAY " + st, r)
        self.refresh()


class TrafficPage(Page):
    def __init__(self, app):
        super().__init__(app)
        heading(self, "Traffic & Congestion", "Arrival / departure queues versus capacity").pack(anchor="w", pady=(0, 10))
        top = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=14)
        top.pack(fill="x", pady=(0, 10))
        self.mode = ctk.CTkSegmentedButton(top, values=["DUAL", "SINGLE"], command=lambda v: self.refresh())
        self.mode.set("DUAL")
        self.mode.pack(anchor="e", padx=14, pady=(10, 0))
        self.bars = {}
        for key in ("ARR", "DEP"):
            l = ctk.CTkLabel(top, text=key, anchor="w")
            l.pack(fill="x", padx=16, pady=(8, 0))
            pb = ctk.CTkProgressBar(top, height=14)
            pb.pack(fill="x", padx=16, pady=(2, 0))
            self.bars[key] = (l, pb)
        self.summary = ctk.CTkLabel(top, text="", text_color=MUTED)
        self.summary.pack(anchor="w", padx=16, pady=(8, 12))

        cols = ctk.CTkFrame(self, fg_color="transparent")
        cols.pack(fill="both", expand=True)
        cols.columnconfigure((0, 1), weight=1, uniform="t")
        cols.rowconfigure(1, weight=1)
        ctk.CTkLabel(cols, text="Arrival queue", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, sticky="w", padx=6)
        ctk.CTkLabel(cols, text="Departure queue", font=ctk.CTkFont(weight="bold")).grid(row=0, column=1, sticky="w", padx=6)
        self.arr = Table(cols, ["f", "air", "from", "rwy", "eta", "st"],
                         ["Flight", "Airline", "From", "RWY", "ETA", "Status"], [80, 110, 70, 50, 60, 90], height=8)
        self.dep = Table(cols, ["f", "air", "to", "rwy", "etd", "st"],
                         ["Flight", "Airline", "To", "RWY", "ETD", "Status"], [80, 110, 70, 50, 60, 90], height=8)
        self.arr.grid(row=1, column=0, sticky="nsew", padx=5, pady=4)
        self.dep.grid(row=1, column=1, sticky="nsew", padx=5, pady=4)

    def refresh(self):
        arr = db_all("""SELECT flight_number, airline, departure, runway, eta, status FROM flights
                        WHERE destination=? AND status NOT IN ('CANCELLED','LANDED','PARKED') ORDER BY eta""", (ICAO,))
        dep = db_all("""SELECT flight_number, airline, destination, runway, etd, status FROM flights
                        WHERE departure=? AND status NOT IN ('CANCELLED','DEPARTED','AIRBORNE') ORDER BY etd""", (ICAO,))
        self.arr.set(arr, status_index=5)
        self.dep.set(dep, status_index=5)
        a, d = len(arr), len(dep)
        if self.mode.get() == "SINGLE":
            cap = ARRIVAL_CAPACITY
            items = {"ARR": (a + d, cap, "Total demand (single runway)"), "DEP": (0, 1, "—")}
            cong = max(0, a + d - cap)
            self.summary.configure(text=f"Single runway | Demand {a + d} / Capacity {cap} | Congestion {cong}")
        else:
            items = {"ARR": (a, ARRIVAL_CAPACITY, "Arrivals"), "DEP": (d, DEPARTURE_CAPACITY, "Departures")}
            self.summary.configure(text=f"Dual runway | ARR congestion {max(0, a - ARRIVAL_CAPACITY)} | "
                                        f"DEP congestion {max(0, d - DEPARTURE_CAPACITY)}")
        for k, (n, cap, name) in items.items():
            l, pb = self.bars[k]
            l.configure(text=f"{name}: {n} / {cap}" if k == "ARR" or self.mode.get() == "DUAL" else "")
            pb.set(min(1, n / cap) if cap else 0)
            pb.configure(progress_color=RED if n > cap else (AMBER if n >= cap * 0.8 else GREEN))


class WeatherPage(Page):
    def __init__(self, app):
        super().__init__(app)
        heading(self, "Weather", "METAR & TAF decoded (AVWX) - or paste any raw METAR").pack(anchor="w", pady=(0, 10))
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x")
        self.icao = ctk.CTkEntry(bar, width=110)
        self.icao.insert(0, ICAO)
        self.icao.pack(side="left")
        btn(bar, "Fetch METAR", self.fetch).pack(side="left", padx=6)
        btn(bar, "Fetch TAF", self.fetch_taf, ACCENT_DARK, 100).pack(side="left", padx=2)
        btn(bar, "Decode pasted METAR", self.decode_manual, PANEL2, 170).pack(side="left", padx=6)
        self.info = ctk.CTkLabel(self, text="", text_color=MUTED)
        self.info.pack(anchor="w", pady=6)
        self.grid_f = ctk.CTkFrame(self, fg_color="transparent")
        self.grid_f.pack(fill="x")
        self.vals = {}
        for i, k in enumerate(["Wind", "Visibility", "Clouds", "Weather", "Temperature", "Dew point", "QNH", "Flight rules"]):
            c = card(self.grid_f, k, "–", TEXT)
            c.value.configure(font=ctk.CTkFont(size=17, weight="bold"), wraplength=230)
            try:
                c.value._label.configure(justify="left")
            except Exception:
                pass
            c.grid(row=i // 4, column=i % 4, padx=5, pady=5, sticky="nsew")
            self.grid_f.columnconfigure(i % 4, weight=1, uniform="w")
            self.vals[k] = c
        self.raw = ctk.CTkTextbox(self, height=64, fg_color=PANEL, font=ctk.CTkFont(family="Consolas", size=13))
        self.raw.pack(fill="x", pady=(8, 4))
        ctk.CTkLabel(self, text="TAF forecast", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=4)
        self.taf = Table(self, ["t", "wind", "vis", "wx", "cld", "fr"],
                         ["Group", "Wind", "Visibility", "Weather", "Clouds", "Rules"],
                         [80, 140, 100, 170, 260, 80], height=5)
        self.taf.pack(fill="both", expand=True, pady=4)

    def refresh(self):
        """Called when the page opens and every 10 s: fetch METAR + TAF automatically (every 10 min)."""
        if getattr(self, "_busy", False) or time.time() < getattr(self, "_next", 0):
            return
        last = metar_parser.get_latest()
        if last and not self.raw.get("1.0", "end").strip():
            self.show_raw(last["raw"])
        self.fetch()

    def fetch(self):
        code = self.icao.get().strip().upper()
        self._busy = True
        self._next = time.time() + 120
        self.info.configure(text=f"Fetching {code}…")
        run_async(self, lambda: get_metar(code), self.show)
        self.fetch_taf()

    def fetch_taf(self):
        from api import get_taf
        code = self.icao.get().strip().upper()
        run_async(self, lambda: get_taf(code), self.show_taf)

    def show(self, m):
        self._busy = False
        if not m or isinstance(m, Exception) or not m.get("raw"):
            import api
            self.info.configure(text="No METAR available (" + (api.last_error or "no connection") +
                                ") - retrying automatically; or paste a raw METAR below.")
            return
        self._next = time.time() + 600
        self.show_raw(m["raw"], m.get("source"))

    def decode_manual(self):
        raw = self.raw.get("1.0", "end").strip()
        if not metar_parser.parse_metar(raw):
            return self.info.configure(text="Paste a raw METAR in the box first.")
        self.show_raw(raw)

    def show_raw(self, raw, source=None):
        d = metar_parser.parse_metar(raw)
        if not d:
            return
        metar_parser.set_latest(d)
        for k, v in metar_parser.summary_lines(d).items():
            self.vals[k].value.configure(text=v)
        self.vals["Flight rules"].value.configure(
            text_color={"VFR": GREEN, "MVFR": ACCENT, "IFR": RED, "LIFR": "#d946ef"}.get(d["flight_rules"], TEXT))
        self.info.configure(text=f"{d.get('station') or ''}   observed {d.get('time') or ''}" +
                            (f"   (source: {source})" if source else ""))
        self.raw.delete("1.0", "end")
        self.raw.insert("1.0", d["raw"])

    def show_taf(self, t):
        if not t or isinstance(t, Exception) or not t.get("raw"):
            import api
            return self.taf.set([]) if False else self.info.configure(
                text=self.info.cget("text") + "   |   No TAF (" + (api.last_error or "none published") + ")")
        groups = metar_parser.parse_taf(t["raw"])
        self.taf.set([(g["type"], metar_parser.describe_wind(g), metar_parser.describe_visibility(g),
                       ", ".join(g["weather"]) or "–", metar_parser.describe_clouds(g), g["flight_rules"])
                      for g in groups])
        self.info.configure(text=self.info.cget("text").split("   |   TAF")[0] + f"   |   TAF {t.get('station', '')}: {len(groups)} group(s)")


class LivePage(Page):
    def __init__(self, app):
        super().__init__(app)
        heading(self, "Live Flights", "OpenSky Network").pack(anchor="w", pady=(0, 10))
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x", pady=(0, 8))
        self.country = ctk.CTkEntry(bar, width=180, placeholder_text="Country filter")
        self.country.insert(0, "Algeria")
        self.country.pack(side="left")
        btn(bar, "Load", self.load).pack(side="left", padx=8)
        self.lbl = ctk.CTkLabel(bar, text="", text_color=MUTED)
        self.lbl.pack(side="left", padx=8)
        self.table = Table(self, ["cs", "co", "alt", "spd", "lat", "lon"],
                           ["Callsign", "Country", "Altitude (ft)", "Speed (kt)", "Lat", "Lon"],
                           [110, 160, 110, 100, 90, 90])
        self.table.pack(fill="both", expand=True)

    def load(self):
        import requests
        self.lbl.configure(text="Downloading…")
        run_async(self, lambda: requests.get("https://opensky-network.org/api/states/all", timeout=20).json(),
                  self.show)

    def show(self, data):
        if isinstance(data, Exception) or not isinstance(data, dict):
            return self.lbl.configure(text="Connection error.")
        flt = self.country.get().strip().lower()
        rows = []
        for s in data.get("states") or []:
            cs = (s[1] or "").strip()
            if not cs or (flt and flt not in (s[2] or "").lower()):
                continue
            alt = round(s[7] * 3.28084) if s[7] is not None else ""
            spd = round(s[9] * 1.94384) if s[9] is not None else ""
            rows.append((cs, s[2], alt, spd, s[6], s[5]))
        self.table.set(rows[:300])
        self.lbl.configure(text=f"{len(rows)} aircraft")


class UserDialog(ctk.CTkToplevel):
    def __init__(self, parent, user=None, on_save=None):
        super().__init__(parent)
        self.title("Edit user" if user else "Add user")
        self.geometry("400x560")
        self.configure(fg_color=BG)
        self.transient(parent)
        self.after(150, self.grab_set)
        self.user, self.on_save = user, on_save
        f = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=14)
        f.pack(fill="both", expand=True, padx=14, pady=14)
        self.e = {}
        for key, label, show in [("username", "Username", None), ("full_name", "Full name", None),
                                 ("password", "Password" if not user else "New password (optional)", "•")]:
            ctk.CTkLabel(f, text=label, text_color=MUTED).pack(anchor="w", padx=18, pady=(10, 0))
            en = ctk.CTkEntry(f, width=300, show=show)
            en.pack(padx=18)
            self.e[key] = en
        ctk.CTkLabel(f, text="Role", text_color=MUTED).pack(anchor="w", padx=18, pady=(10, 0))
        self.role = ctk.CTkComboBox(f, values=ROLES, width=300)
        self.role.pack(padx=18)
        self.active = ctk.CTkSwitch(f, text="Active")
        self.active.select()
        self.active.pack(anchor="w", padx=18, pady=12)
        if user:
            self.e["username"].insert(0, user["username"]); self.e["username"].configure(state="disabled")
            self.e["full_name"].insert(0, user["full_name"] or "")
            self.role.set(user["role"])
            (self.active.select if user["active"] else self.active.deselect)()
        btn(f, "Save", self.save, GREEN, 300, hover="#15803d").pack(pady=6)

    def save(self):
        d = {"username": self.e["username"].get().strip(), "full_name": self.e["full_name"].get().strip(),
             "password": self.e["password"].get(), "role": self.role.get(), "active": int(self.active.get())}
        if len(d["username"]) < 3:
            return messagebox.showerror("User", "Username must be at least 3 characters.", parent=self)
        if d["password"] or not self.user:
            ok, msg = is_strong_password(d["password"])
            if not ok:
                return messagebox.showerror("Password", msg, parent=self)
        self.on_save(d, self.user is None)
        self.destroy()


class UsersPage(Page):
    def __init__(self, app):
        super().__init__(app)
        heading(self, "Users", "Accounts and roles").pack(anchor="w", pady=(0, 10))
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x", pady=(0, 8))
        if self.can("delete_user"):
            btn(bar, "Delete", self.delete, RED, 90, hover="#b91c1c").pack(side="right", padx=3)
        if self.can("edit_user"):
            btn(bar, "Edit", self.edit, PANEL2, 80).pack(side="right", padx=3)
        if self.can("add_user"):
            btn(bar, "+ Add user", self.add).pack(side="right", padx=3)
        self.table = Table(self, ["id", "u", "n", "r", "a", "l"],
                           ["ID", "Username", "Full name", "Role", "Status", "Last login"],
                           [50, 140, 200, 160, 90, 180])
        self.table.pack(fill="both", expand=True)

    def refresh(self):
        rows = db_all("SELECT id, username, full_name, role, active, last_login FROM users ORDER BY id")
        self.table.set([(r[0], r[1], r[2], r[3], "ACTIVE" if r[4] else "INACTIVE", r[5] or "Never") for r in rows])

    def _sel(self):
        v = self.table.selected()
        if not v:
            messagebox.showinfo("Select", "Select a user first.")
            return None
        r = db_one("SELECT id, username, full_name, role, active FROM users WHERE id=?", (v[0],))
        return dict(zip(["id", "username", "full_name", "role", "active"], r))

    def add(self):
        UserDialog(self, None, self._save)

    def edit(self):
        u = self._sel()
        if u:
            UserDialog(self, u, self._save)

    def _save(self, d, is_new):
        try:
            if is_new:
                db_exec("INSERT INTO users (username, password, full_name, role, active) VALUES (?,?,?,?,?)",
                        (d["username"], hash_password(d["password"]), d["full_name"], d["role"], d["active"]))
                log(self.user, "USER CREATED", f"{d['username']} ({d['role']})")
            else:
                old = db_one("SELECT role FROM users WHERE username=?", (d["username"],))[0]
                if old == "Administrator" and (d["role"] != "Administrator" or not d["active"]) \
                        and count_administrators() <= 1:
                    return messagebox.showerror("Users", "Cannot demote or disable the last administrator.")
                db_exec("UPDATE users SET full_name=?, role=?, active=? WHERE username=?",
                        (d["full_name"], d["role"], d["active"], d["username"]))
                if d["password"]:
                    db_exec("UPDATE users SET password=?, login_attempts=0, locked_until=NULL WHERE username=?",
                            (hash_password(d["password"]), d["username"]))
                log(self.user, "USER UPDATED", f"{d['username']} -> {d['role']}")
        except sqlite3.IntegrityError:
            return messagebox.showerror("Users", "Username already exists.")
        self.refresh()

    def delete(self):
        u = self._sel()
        if not u:
            return
        if u["username"] == self.user["username"]:
            return messagebox.showerror("Users", "You cannot delete yourself.")
        if u["role"] == "Administrator" and count_administrators() <= 1:
            return messagebox.showerror("Users", "Cannot delete the last administrator.")
        if messagebox.askyesno("Delete", f"Delete user {u['username']}?"):
            db_exec("DELETE FROM users WHERE id=?", (u["id"],))
            log(self.user, "USER DELETED", u["username"])
            self.refresh()


class LogsPage(Page):
    def __init__(self, app):
        super().__init__(app)
        heading(self, "System Logs", "Latest 500 entries").pack(anchor="w", pady=(0, 10))
        self.holder = ctk.CTkFrame(self, fg_color="transparent")
        self.holder.pack(fill="both", expand=True)
        self.table = None

    def refresh(self):
        conn = sqlite3.connect(DATABASE)
        try:
            cur = conn.execute("SELECT * FROM logs ORDER BY id DESC LIMIT 500")
            cols = [c[0] for c in cur.description]
            rows = cur.fetchall()
        except sqlite3.Error as e:
            return messagebox.showerror("Logs", str(e))
        finally:
            conn.close()
        if self.table:
            self.table.destroy()
        self.table = Table(self.holder, cols, [c.upper() for c in cols], [60 if c == "id" else 170 for c in cols])
        self.table.pack(fill="both", expand=True)
        self.table.set(rows)


class BackupPage(Page):
    def __init__(self, app):
        super().__init__(app)
        heading(self, "Backup", "Database backup and restore").pack(anchor="w", pady=(0, 10))
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x", pady=(0, 8))
        btn(bar, "Create backup now", self.create, GREEN, 160, hover="#15803d").pack(side="left")
        if self.can("restore"):
            btn(bar, "Restore selected", self.restore, AMBER, 150, hover="#b45309").pack(side="left", padx=8)
        self.table = Table(self, ["f", "s", "m"], ["File", "Size (KB)", "Modified"], [260, 100, 180])
        self.table.pack(fill="both", expand=True)

    def refresh(self):
        d = backup_mod.BACKUP_DIR
        rows = []
        if os.path.isdir(d):
            for f in sorted(os.listdir(d), reverse=True):
                if f.endswith(".db"):
                    p = os.path.join(d, f)
                    rows.append((f, f"{os.path.getsize(p) / 1024:.1f}",
                                 datetime.fromtimestamp(os.path.getmtime(p)).strftime("%Y-%m-%d %H:%M")))
        self.table.set(rows)

    def create(self):
        if backup_mod.create_backup():
            log(self.user, "BACKUP", "Database backup created")
            messagebox.showinfo("Backup", "Backup created.")
        else:
            messagebox.showerror("Backup", "Backup failed.")
        self.refresh()

    def restore(self):
        v = self.table.selected()
        if not v:
            return messagebox.showinfo("Select", "Select a backup first.")
        if messagebox.askyesno("Restore", f"Replace the current database with {v[0]}?\nThis cannot be undone."):
            if backup_mod.restore_backup(os.path.join(backup_mod.BACKUP_DIR, v[0])):
                log(self.user, "RESTORE", v[0])
                messagebox.showinfo("Restore", "Database restored.")


# ------------------------------------------------------------------ main window
# ================================================================== v2 : charts
class BarChart(tk.Canvas):
    """Small grouped bar chart drawn on a Tk canvas (no extra library needed)."""

    def __init__(self, master, height=230, **kw):
        super().__init__(master, height=height, bg=PANEL, highlightthickness=0, **kw)
        self._args = None
        self.bind("<Configure>", lambda e: self._draw())

    def plot(self, labels, series, hline=None, title=""):
        """series = [(name, values, color)], hline = (value, color, label) or None"""
        self._args = (labels, series, hline, title)
        self._draw()

    def _draw(self):
        self.delete("all")
        if not self._args:
            return
        labels, series, hline, title = self._args
        w, h = max(self.winfo_width(), 240), max(self.winfo_height(), 140)
        left, right, top, bottom = 40, 14, 30, 26
        pw, ph = w - left - right, h - top - bottom
        vmax = max([1] + [v for _, vals, _ in series for v in vals] + ([hline[0]] if hline else []))
        vmax = math.ceil(vmax * 1.15)
        for i in range(5):
            y = top + ph - ph * i / 4
            self.create_line(left, y, w - right, y, fill="#24365a")
            self.create_text(left - 6, y, text=f"{vmax * i / 4:g}", fill=MUTED, anchor="e", font=("Segoe UI", 8))
        n = max(len(labels), 1)
        slot = pw / n
        bw = max(2, slot * 0.8 / max(len(series), 1))
        for si, (_, vals, color) in enumerate(series):
            for i, v in enumerate(vals):
                x0 = left + i * slot + slot * 0.1 + si * bw
                y1 = top + ph
                self.create_rectangle(x0, y1 - ph * v / vmax, x0 + bw - 1, y1, fill=color, outline="")
        step = max(1, n // 12)
        for i in range(0, n, step):
            self.create_text(left + i * slot + slot / 2, top + ph + 12, text=str(labels[i]),
                             fill=MUTED, font=("Segoe UI", 8))
        if hline:
            y = top + ph - ph * hline[0] / vmax
            self.create_line(left, y, w - right, y, fill=hline[1], dash=(5, 3), width=2)
            self.create_text(w - right - 4, y - 8, text=hline[2], fill=hline[1], anchor="e", font=("Segoe UI", 8))
        self.create_text(left, 12, text=title, fill=TEXT, anchor="w", font=("Segoe UI", 10, "bold"))
        x = w - right
        for name, _, color in reversed(series):
            self.create_text(x, 12, text=name, fill=MUTED, anchor="e", font=("Segoe UI", 9))
            x -= len(name) * 6 + 22
            self.create_rectangle(x + 8, 7, x + 18, 17, fill=color, outline="")
            x -= 10


LEVEL_COLORS = {"CRITICAL": RED, "HIGH": RED, "WARNING": AMBER, "MODERATE": AMBER, "MEDIUM": AMBER,
                "INFO": ACCENT, "LOW": GREEN}


# ================================================================== v2 : NOTAM
class NotamDialog(ctk.CTkToplevel):
    def __init__(self, parent, on_save):
        super().__init__(parent)
        self.title("Add NOTAM")
        self.geometry("580x500")
        self.configure(fg_color=BG)
        self.transient(parent)
        self.after(150, self.grab_set)
        self.on_save = on_save
        box = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=14)
        box.pack(fill="both", expand=True, padx=16, pady=16)
        ctk.CTkLabel(box, text="NOTAM no.  (e.g. A0123/26)", text_color=MUTED).pack(anchor="w", padx=14, pady=(12, 0))
        self.nid = ctk.CTkEntry(box)
        self.nid.pack(fill="x", padx=14)
        ctk.CTkLabel(box, text="Text  (e.g. RWY 09/27 CLSD DUE WIP)", text_color=MUTED).pack(anchor="w", padx=14, pady=(10, 0))
        self.text = ctk.CTkTextbox(box, height=90, fg_color=PANEL2)
        self.text.pack(fill="x", padx=14)
        self.text.bind("<KeyRelease>", self.preview_cls)
        self.cls = ctk.CTkLabel(box, text="Category: –   Priority: –", text_color=ACCENT)
        self.cls.pack(anchor="w", padx=14, pady=4)
        row = ctk.CTkFrame(box, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=4)
        ctk.CTkLabel(row, text="Valid from (UTC)", text_color=MUTED).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(row, text="Valid to (UTC or PERM)", text_color=MUTED).grid(row=0, column=1, sticky="w", padx=10)
        self.vf = ctk.CTkEntry(row, width=230)
        self.vf.insert(0, datetime.utcnow().strftime("%Y-%m-%d %H:%M"))
        self.vf.grid(row=1, column=0)
        self.vt = ctk.CTkEntry(row, width=230)
        self.vt.insert(0, "PERM")
        self.vt.grid(row=1, column=1, padx=10)
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(side="bottom", fill="x", padx=16, pady=(0, 14), before=box)
        btn(bar, "Save", self.save, GREEN, hover="#15803d").pack(side="right", padx=4)
        btn(bar, "Cancel", self.destroy, PANEL2).pack(side="right", padx=4)

    def preview_cls(self, _=None):
        t = self.text.get("1.0", "end").strip()
        if t:
            c, p = notam_mod.classify(t)
            self.cls.configure(text=f"Category: {c}   Priority: {p}", text_color=LEVEL_COLORS.get(p, ACCENT))

    def save(self):
        self.on_save(self.nid.get(), self.text.get("1.0", "end").strip(), self.vf.get(), self.vt.get(), self)


# ================================================================== v3.4 : automatic NOTAM
# NOTE: notam_ui's run_async calls done(ok, result); it must NOT replace the GUI-wide run_async(done(result))
# used by METAR / TAF / live flights (that overwrite was why Weather stayed empty).
NotamApiDialog, PasteNotamDialog, run_async_ok = notam_ui.build(sys.modules[__name__])


class NotamPage(Page):
    def __init__(self, app):
        super().__init__(app)
        heading(self, "NOTAM", "Notices to Air Missions - classified by category and priority").pack(anchor="w", pady=(0, 10))
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x", pady=(0, 8))
        self.add_b = btn(bar, "+ Add NOTAM", self.add, GREEN, 130, hover="#15803d")
        self.cancel_b = btn(bar, "Cancel NOTAM", self.cancel, AMBER, 130, hover="#b45309")
        self.del_b = btn(bar, "Delete", self.delete, RED, 90, hover="#b91c1c")
        if self.can("edit_notam"):
            for b in (self.add_b, self.cancel_b, self.del_b):
                b.pack(side="left", padx=(0, 8))
            self.fetch_b = btn(bar, "⟳ Fetch (API)", self.fetch_api, ACCENT_DARK, 130)
            self.paste_b = btn(bar, "Paste NOTAM", self.paste, PANEL2, 120)
            self.api_b = btn(bar, "⚙ API", self.api_settings, PANEL2, 70)
            for b in (self.fetch_b, self.paste_b, self.api_b):
                b.pack(side="left", padx=(0, 8))
        self.only = ctk.CTkCheckBox(bar, text="Active only", command=self.refresh)
        self.only.pack(side="right", padx=8)
        self.info = ctk.CTkLabel(self, text="", text_color=MUTED)
        self.info.pack(anchor="w")
        self.table = Table(self, ["id", "cat", "prio", "st", "from", "to", "src", "text"],
                           ["NOTAM", "Category", "Priority", "Status", "Valid from", "Valid to", "Source", "Text"],
                           [100, 90, 80, 90, 130, 130, 90, 380])
        self.table.pack(fill="both", expand=True, pady=6)

    def refresh(self):
        rows = notam_mod.list_notams(active_only=bool(self.only.get()))
        self.table.set([(n["notam_id"], n["category"], n["priority"], n["status"], n["valid_from"],
                         n["valid_to"],
                         n["source"] + (f" {n['location']}" if n["location"] not in ("", ICAO) else ""),
                         n["text"]) for n in rows], status_index=2)
        closed = sorted(notam_mod.closed_runways())
        self.info.configure(text=f"{len(rows)} NOTAM shown" + (f"   |   Runways closed by NOTAM: {', '.join(closed)}" if closed else ""))

    def add(self):
        NotamDialog(self.app, self._save)

    # ---- v3.4 automatic NOTAM (ICAO API) / paste
    def api_settings(self):
        NotamApiDialog(self.app, on_close=self.refresh, fetch_now=self.fetch_api)

    def paste(self):
        PasteNotamDialog(self.app, self.user, on_done=self.refresh)

    def fetch_api(self):
        s = notam_api.get_settings()
        used, limit = notam_api.calls_used(s), int(s["monthly_limit"] or 90)
        if s["api_key"] and used >= limit and not messagebox.askyesno(
                "NOTAM API", f"{used}/{limit} API calls already used this month (free tier is limited). Fetch anyway?"):
            return
        self.info.configure(text="Fetching NOTAMs…")
        run_async_ok(self, lambda: notam_api.sync(self.user["username"], force=True), self._fetched)

    def _fetched(self, ok, result):
        self.refresh()
        (messagebox.showinfo if ok else messagebox.showerror)("NOTAM API", result)

    def _save(self, nid, text, vf, vt, dlg):
        ok, msg = notam_mod.add_notam(nid, text, vf, vt, self.user["username"])
        if not ok:
            return messagebox.showerror("NOTAM", msg, parent=dlg)
        dlg.destroy()
        self.refresh()

    def _sel(self):
        s = self.table.selected()
        if not s:
            messagebox.showinfo("NOTAM", "Select a NOTAM first.")
        return s[0] if s else None

    def cancel(self):
        n = self._sel()
        if n and messagebox.askyesno("NOTAM", f"Cancel {n}?"):
            notam_mod.cancel_notam(n, self.user["username"])
            self.refresh()

    def delete(self):
        n = self._sel()
        if n and messagebox.askyesno("NOTAM", f"Delete {n} permanently?"):
            notam_mod.delete_notam(n, self.user["username"])
            self.refresh()


# ================================================================== v2 : capacity
class CapacityPage(Page):
    def __init__(self, app):
        super().__init__(app)
        heading(self, "Airport Capacity", "Demand of the next 60 minutes versus hourly capacity").pack(anchor="w", pady=(0, 10))
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x")
        self.cards = {}
        for i, (k, t, c) in enumerate([("arr", "Arrivals (60 min)", AMBER), ("dep", "Departures (60 min)", GREEN),
                                       ("load", "Traffic load", ACCENT), ("level", "Congestion", GREEN),
                                       ("rwy", "Runways open", TEXT)]):
            cd = card(row, t, "0", c)
            cd.grid(row=0, column=i, padx=5, sticky="nsew")
            row.columnconfigure(i, weight=1)
            self.cards[k] = cd
        box = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=14)
        box.pack(fill="x", pady=10)
        self.bars = {}
        for key in ("ARR", "DEP"):
            l = ctk.CTkLabel(box, text=key, anchor="w")
            l.pack(fill="x", padx=16, pady=(8, 0))
            pb = ctk.CTkProgressBar(box, height=14)
            pb.pack(fill="x", padx=16, pady=(2, 0))
            self.bars[key] = (l, pb)
        self.note = mlabel(box, text="", text_color=MUTED, anchor="w", justify="left")
        self.note.pack(fill="x", padx=16, pady=(8, 12))
        self.chart = BarChart(self, height=250)
        self.chart.pack(fill="both", expand=True, pady=4)

    def refresh(self):
        c = capacity_mod.compute_capacity()
        col = LEVEL_COLORS.get(c["level"], TEXT)
        self.cards["arr"].value.configure(text=f"{c['arrivals_next_hour']} / {c['arrival_capacity']:g}")
        self.cards["dep"].value.configure(text=f"{c['departures_next_hour']} / {c['departure_capacity']:g}")
        self.cards["load"].value.configure(text=f"{min(c['ratio_total'], 9.99) * 100:.0f}%", text_color=col)
        self.cards["level"].value.configure(text=c["level"], text_color=col)
        ops = c["runways_operational"]
        self.cards["rwy"].value.configure(text=f"{sum(ops.values())} / {len(ops)}")
        for key, n, cap, ratio, name in (("ARR", c["arrivals_next_hour"], c["arrival_capacity"], c["ratio_arrival"], "Arrivals"),
                                         ("DEP", c["departures_next_hour"], c["departure_capacity"], c["ratio_departure"], "Departures")):
            l, pb = self.bars[key]
            l.configure(text=f"{name}: {n} / {cap:g} per hour")
            pb.set(min(1, ratio))
            pb.configure(progress_color=RED if ratio >= 1 else (AMBER if ratio >= 0.8 else GREEN))
        closed = [k for k, v in ops.items() if not v]
        self.note.configure(text=(f"⚠ Capacity reduced: runway {', '.join(closed)} not available (closed / maintenance / NOTAM)."
                                  if closed else "All runways operational.") +
                            f"   On ground: {c['aircraft_on_ground']}   |   Pending ARR {c['arrivals_pending']} / DEP {c['departures_pending']}")
        arr, dep = capacity_mod.hourly_profile()
        self.chart.plot([f"{h:02d}" for h in range(24)],
                        [("Arrivals", arr, AMBER), ("Departures", dep, GREEN)],
                        hline=(max(c["arrival_capacity"], c["departure_capacity"]), RED, "capacity / hour"),
                        title="Movements per UTC hour (from ETA / ETD)")


# ================================================================== v2 : ATFCM
class CtotDialog(ctk.CTkToplevel):
    def __init__(self, parent, on_save, flight=""):
        super().__init__(parent)
        self.title("Set CTOT")
        self.geometry("440x480")
        self.configure(fg_color=BG)
        self.transient(parent)
        self.after(150, self.grab_set)
        self.on_save = on_save
        box = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=14)
        box.pack(fill="both", expand=True, padx=16, pady=16)
        flights = [r[0] for r in db_all("SELECT flight_number FROM flights WHERE departure=? ORDER BY etd", (ICAO,))]
        self.w = {}
        for key, label, widget in (("fn", "Flight", ctk.CTkComboBox(box, values=flights or [""])),
                                   ("ctot", "CTOT (HH:MM UTC)", ctk.CTkEntry(box)),
                                   ("reg", "Regulation (e.g. LFPGAL12)", ctk.CTkEntry(box)),
                                   ("reason", "Reason", ctk.CTkEntry(box))):
            ctk.CTkLabel(box, text=label, text_color=MUTED).pack(anchor="w", padx=14, pady=(10, 0))
            widget.pack(fill="x", padx=14)
            self.w[key] = widget
        if flight:
            self.w["fn"].set(flight)
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(side="bottom", fill="x", padx=16, pady=(0, 14), before=box)
        btn(bar, "Save", self.save, GREEN, hover="#15803d").pack(side="right", padx=4)
        btn(bar, "Cancel", self.destroy, PANEL2).pack(side="right", padx=4)

    def save(self):
        self.on_save(self.w["fn"].get(), self.w["ctot"].get(), self.w["reg"].get(), self.w["reason"].get(), self)


class AtfcmPage(Page):
    def __init__(self, app):
        super().__init__(app)
        heading(self, "ATFCM / CTOT", "Slots and regulations - take-off window CTOT -5 / +10 min").pack(anchor="w", pady=(0, 10))
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x")
        self.cards = {}
        for i, (k, t, c) in enumerate([("n", "Regulated flights", ACCENT), ("appr", "Approaching", AMBER),
                                       ("missed", "Missed", RED), ("avg", "Average delay (min)", TEXT)]):
            cd = card(row, t, "0", c)
            cd.grid(row=0, column=i, padx=5, sticky="nsew")
            row.columnconfigure(i, weight=1)
            self.cards[k] = cd
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x", pady=8)
        if self.can("ctot"):
            btn(bar, "+ Set CTOT", self.add, GREEN, 120, hover="#15803d").pack(side="left", padx=(0, 8))
            btn(bar, "Edit", self.edit, ACCENT_DARK, 80).pack(side="left", padx=(0, 8))
            btn(bar, "Remove", self.remove, RED, 90, hover="#b91c1c").pack(side="left")
        self.table = Table(self, ["fn", "dest", "etd", "ctot", "delay", "min", "reg", "rwy", "state"],
                           ["Flight", "To", "ETD", "CTOT", "Delay", "CTOT in (min)", "Regulation", "RWY", "State"],
                           [90, 70, 70, 70, 80, 110, 130, 60, 110])
        self.table.pack(fill="both", expand=True, pady=4)

    def refresh(self):
        rows = atfcm_mod.list_ctot()
        self.table.set([(x["flight_number"], x["destination"], x["etd"], x["ctot"],
                         "" if x["delay_min"] is None else f"{x['delay_min']:+d} min",
                         "" if x["minutes_to_ctot"] is None else f"{x['minutes_to_ctot']:+d}",
                         x["regulation"], x["runway"], x["state"]) for x in rows], status_index=8)
        st = atfcm_mod.delay_statistics()
        self.cards["n"].value.configure(text=str(len(rows)))
        self.cards["appr"].value.configure(text=str(sum(1 for x in rows if x["state"] in ("APPROACHING", "IN WINDOW"))))
        self.cards["missed"].value.configure(text=str(sum(1 for x in rows if x["state"] == "MISSED")))
        self.cards["avg"].value.configure(text=str(st["average"]))

    def add(self, flight=""):
        CtotDialog(self.app, self._save, flight)

    def edit(self):
        s = self.table.selected()
        if not s:
            return messagebox.showinfo("CTOT", "Select a flight first.")
        self.add(str(s[0]))

    def _save(self, fn, ctot, reg, reason, dlg):
        ok, msg = atfcm_mod.set_ctot(fn, ctot, reg, reason, self.user["username"])
        if not ok:
            return messagebox.showerror("CTOT", msg, parent=dlg)
        dlg.destroy()
        self.refresh()

    def remove(self):
        s = self.table.selected()
        if s and messagebox.askyesno("CTOT", f"Remove CTOT of {s[0]}?"):
            atfcm_mod.remove_ctot(str(s[0]), self.user["username"])
            self.refresh()


# ================================================================== v2 : alerts
class AlertsPage(Page):
    def __init__(self, app):
        super().__init__(app)
        heading(self, "Alerts", "Operational alerts - help messages, the controller decides").pack(anchor="w", pady=(0, 10))
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x", pady=(0, 8))
        if self.can("ack_alerts"):
            btn(bar, "Acknowledge", self.ack, GREEN, 130, hover="#15803d").pack(side="left", padx=(0, 8))
        btn(bar, "Refresh", self.refresh, PANEL2, 90).pack(side="left")
        self.hist = ctk.CTkCheckBox(bar, text="Show history", command=self.refresh)
        self.hist.pack(side="right", padx=8)
        self.info = ctk.CTkLabel(self, text="", text_color=MUTED)
        self.info.pack(anchor="w")
        self.table = Table(self, ["id", "time", "level", "code", "msg", "st"],
                           ["#", "UTC time", "Level", "Type", "Message", "State"], [50, 150, 90, 170, 520, 110])
        self.table.pack(fill="both", expand=True, pady=6)

    def refresh(self):
        alerts_mod.sync_alerts()
        rows = alerts_mod.list_alerts(history=bool(self.hist.get()))
        self.table.set([(r[0], r[1], r[2], r[3], r[4], r[5]) for r in rows], status_index=2)
        t, c = alerts_mod.count_active()
        self.info.configure(text=f"{t} new alert(s), {c} critical" if t else "✓ No new alerts")

    def ack(self):
        s = self.table.selected()
        if not s:
            return messagebox.showinfo("Alerts", "Select an alert first.")
        alerts_mod.acknowledge(int(s[0]), self.user["username"])
        log(self.user, "ALERT ACK", f"#{s[0]} {s[3]}")
        self.refresh()


# ================================================================== v2 : map
def _opensky_to_aircraft(data):
    out = []
    for s in data.get("states") or []:
        if s[5] is None or s[6] is None:
            continue
        alt = s[7] if s[7] is not None else s[13]
        out.append({"callsign": (s[1] or s[0] or "").strip() or s[0], "lat": s[6], "lon": s[5],
                    "alt_ft": round(alt * 3.28084) if alt is not None else None,
                    "track": s[10] or 0, "speed_kt": round((s[9] or 0) * 1.94384),
                    "vrate_fpm": round((s[11] or 0) * 196.85), "on_ground": bool(s[8])})
    return out


def demo_traffic():
    """Synthetic traffic around the airport (used for presentations / offline tests)."""
    rnd = random.Random(7)
    out = []
    for i in range(14):
        ang, dist = rnd.uniform(0, 2 * math.pi), rnd.uniform(8, 55)
        out.append({"callsign": rnd.choice(["DAH", "THY", "AFR", "DLH", "TAR", "QTR"]) + str(rnd.randint(100, 999)),
                    "lat": ARP_LAT + dist / 60 * math.cos(ang),
                    "lon": ARP_LON + dist / 60 * math.sin(ang) / math.cos(math.radians(ARP_LAT)),
                    "alt_ft": 9000 + i * 1900,
                    "track": (math.degrees(ang) + 180 + rnd.randint(-25, 25)) % 360,
                    "speed_kt": rnd.randint(180, 450), "vrate_fpm": 0, "on_ground": False})
    # two aircraft on a collision course (to show the conflict detector)
    out.append({"callsign": "DAH701", "lat": ARP_LAT + 0.20, "lon": ARP_LON - 0.30, "alt_ft": 6000,
                "track": 90, "speed_kt": 260, "vrate_fpm": 0, "on_ground": False})
    out.append({"callsign": "AFR2210", "lat": ARP_LAT + 0.20, "lon": ARP_LON + 0.30, "alt_ft": 6300,
                "track": 270, "speed_kt": 260, "vrate_fpm": 0, "on_ground": False})
    return out


class MapPage(Page):
    """Radar-style map centred on the airport: runways, range rings, aircraft, conflicts."""

    RANGES = ["20 NM", "40 NM", "60 NM", "100 NM"]

    def __init__(self, app):
        super().__init__(app)
        heading(self, "Air Map", "Live aircraft around the airport (OpenSky / ADS-B)").pack(anchor="w", pady=(0, 10))
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x", pady=(0, 8))
        btn(bar, "Load live traffic", self.load).pack(side="left", padx=(0, 8))
        btn(bar, "Demo traffic", self.demo, PANEL2, 110).pack(side="left", padx=(0, 8))
        self.range = ctk.CTkSegmentedButton(bar, values=self.RANGES, command=lambda v: self.draw())
        self.range.set("60 NM")
        self.range.pack(side="left", padx=8)
        self.status = ctk.CTkLabel(bar, text="", text_color=MUTED)
        self.status.pack(side="left", padx=8)
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=1)
        body.rowconfigure(0, weight=1)
        self.canvas = tk.Canvas(body, bg="#07101f", highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.canvas.bind("<Configure>", lambda e: self.draw())
        self.canvas.bind("<Button-1>", self.click)
        side = ctk.CTkFrame(body, fg_color=PANEL, corner_radius=14, width=270)
        side.grid(row=0, column=1, sticky="ns", padx=(10, 0))
        side.grid_propagate(False)
        ctk.CTkLabel(side, text="SELECTED", text_color=MUTED, font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w", padx=14, pady=(12, 2))
        self.sel = mlabel(side, text="Click an aircraft", justify="left", anchor="w",
                                font=ctk.CTkFont(family="Consolas", size=12))
        self.sel.pack(fill="x", padx=14)
        ctk.CTkLabel(side, text="CONFLICT ADVISORIES", text_color=MUTED, font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w", padx=14, pady=(16, 2))
        self.conf = mlabel(side, text="–", justify="left", anchor="w", wraplength=240,
                                 font=ctk.CTkFont(family="Consolas", size=11))
        self.conf.pack(fill="x", padx=14)
        self.aircraft, self.conflicts, self.hit = [], [], []

    def load(self):
        import requests
        self.status.configure(text="Downloading…")
        box = 2.2
        params = {"lamin": ARP_LAT - box, "lamax": ARP_LAT + box,
                  "lomin": ARP_LON - box * 1.3, "lomax": ARP_LON + box * 1.3}
        run_async(self, lambda: requests.get("https://opensky-network.org/api/states/all",
                                             params=params, timeout=20).json(), self._loaded)

    def _loaded(self, data):
        if isinstance(data, Exception) or not isinstance(data, dict):
            return self.status.configure(text="Connection error - use Demo traffic.")
        self.set_aircraft(_opensky_to_aircraft(data), "OpenSky")

    def demo(self):
        self.set_aircraft(demo_traffic(), "demo")

    def set_aircraft(self, ac, source):
        self.aircraft = ac
        self.conflicts = ai_support.detect_conflicts(ac)
        self.status.configure(text=f"{len(ac)} aircraft ({source})  |  {len(self.conflicts)} advisory(ies)")
        self.conf.configure(text="\n\n".join(
            f"{c['severity']}\n{c['a']} / {c['b']}\nnow {c['distance_nm']} NM, {c['vertical_ft']} ft\n"
            f"CPA {c['dcpa_nm']} NM in {c['tcpa_min']} min" for c in self.conflicts[:6]) or "No conflict detected")
        self.draw()

    def _xy(self, lat, lon, cx, cy, scale):
        return (cx + (lon - ARP_LON) * 60 * math.cos(math.radians(ARP_LAT)) * scale,
                cy - (lat - ARP_LAT) * 60 * scale)

    def draw(self):
        c = self.canvas
        c.delete("all")
        w, h = max(c.winfo_width(), 300), max(c.winfo_height(), 300)
        cx, cy = w / 2, h / 2
        rng = int(self.range.get().split()[0])
        scale = (min(w, h) / 2 * 0.94) / rng            # pixels per NM
        for r in range(rng // 4, rng + 1, rng // 4):
            c.create_oval(cx - r * scale, cy - r * scale, cx + r * scale, cy + r * scale, outline="#173152")
            c.create_text(cx + 4, cy - r * scale + 8, text=f"{r} NM", fill="#34507a", anchor="w", font=("Segoe UI", 8))
        c.create_line(cx, cy - rng * scale, cx, cy + rng * scale, fill="#10223b")
        c.create_line(cx - rng * scale, cy, cx + rng * scale, cy, fill="#10223b")
        # runways (drawn at least 40 px long so they stay visible)
        for name, hdg in (("05/23", RUNWAY_05["heading"]), ("09/27", RUNWAY_09["heading"])):
            half = max(20, 1.9 * scale / 2)
            dx, dy = math.sin(math.radians(hdg)) * half, -math.cos(math.radians(hdg)) * half
            c.create_line(cx - dx, cy - dy, cx + dx, cy + dy, fill=TEXT, width=4)
            c.create_text(cx + dx + 6, cy + dy - 6, text=name, fill=MUTED, font=("Segoe UI", 8))
        c.create_text(cx + 10, cy + 14, text=ICAO, fill=ACCENT, font=("Segoe UI", 10, "bold"), anchor="w")
        in_conflict = {x for cf in self.conflicts for x in (cf["a"], cf["b"])}
        self.hit = []
        for a in self.aircraft:
            x, y = self._xy(a["lat"], a["lon"], cx, cy, scale)
            if not (0 <= x <= w and 0 <= y <= h):
                continue
            col = RED if a["callsign"] in in_conflict else (MUTED if a["on_ground"] else GREEN)
            # velocity vector (1 minute)
            v = (a.get("speed_kt") or 0) / 60 * scale
            c.create_line(x, y, x + math.sin(math.radians(a.get("track") or 0)) * v,
                          y - math.cos(math.radians(a.get("track") or 0)) * v, fill=col)
            c.create_polygon(x, y - 6, x - 5, y + 5, x + 5, y + 5, fill=col, outline="")
            alt = "" if a["alt_ft"] is None else f"{round(a['alt_ft'] / 100):03d}"
            c.create_text(x + 9, y - 2, text=f"{a['callsign']} {alt}", fill=col, anchor="w", font=("Consolas", 8))
            self.hit.append((x, y, a))
        for cf in self.conflicts:                                       # lines between conflicting aircraft
            pa = next((p for p in self.hit if p[2]["callsign"] == cf["a"]), None)
            pb = next((p for p in self.hit if p[2]["callsign"] == cf["b"]), None)
            if pa and pb:
                c.create_line(pa[0], pa[1], pb[0], pb[1], fill=RED, dash=(4, 3))

    def click(self, ev):
        best = min(self.hit, key=lambda p: (p[0] - ev.x) ** 2 + (p[1] - ev.y) ** 2, default=None)
        if best and (best[0] - ev.x) ** 2 + (best[1] - ev.y) ** 2 < 25 ** 2:
            a = best[2]
            self.sel.configure(text=(f"Callsign : {a['callsign']}\nAltitude : {a['alt_ft']} ft\n"
                                     f"Speed    : {a['speed_kt']} kt\nTrack    : {round(a['track'] or 0)}°\n"
                                     f"V/S      : {a.get('vrate_fpm', 0)} fpm\nLat/Lon  : {a['lat']:.3f} / {a['lon']:.3f}"))

    def refresh(self):
        self.draw()


# ================================================================== v2 : AI decision support
class AIPage(Page):
    def __init__(self, app):
        super().__init__(app)
        heading(self, "AI Decision Support", "Suggestions only - the final decision stays with the controller").pack(anchor="w", pady=(0, 8))
        top = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=14)
        top.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(top, text="RUNWAY ASSIGNMENT", text_color=MUTED,
                     font=ctk.CTkFont(size=11, weight="bold")).grid(row=0, column=0, sticky="w", padx=14, pady=(10, 0))
        row = ctk.CTkFrame(top, fg_color="transparent")
        row.grid(row=1, column=0, sticky="w", padx=10, pady=8)
        self.op = ctk.CTkSegmentedButton(row, values=["DEPARTURE", "ARRIVAL"], command=lambda v: self.analyze())
        self.op.set("DEPARTURE")
        self.op.pack(side="left", padx=4)
        self.wd, self.ws, self.wg = (ctk.CTkEntry(row, width=70, placeholder_text=p) for p in ("Dir °", "Kt", "Gust"))
        for e in (self.wd, self.ws, self.wg):
            e.pack(side="left", padx=4)
        self.rules = ctk.CTkComboBox(row, values=["VFR", "MVFR", "IFR", "LIFR"], width=90)
        self.rules.set("VFR")
        self.rules.pack(side="left", padx=4)
        btn(row, "Analyze", self.analyze, ACCENT_DARK, 90).pack(side="left", padx=8)
        self.src = ctk.CTkLabel(row, text="", text_color=MUTED)
        self.src.pack(side="left", padx=6)
        self.rtable = Table(top, ["rwy", "ok", "score", "head", "cross", "why"],
                            ["RWY", "Usable", "Score", "Headwind", "Crosswind", "Reasons"], [60, 70, 70, 90, 90, 420], height=4)
        self.rtable.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 10))
        top.columnconfigure(0, weight=1)
        self.msg = ctk.CTkLabel(self, text="", anchor="w", font=ctk.CTkFont(size=13, weight="bold"))
        self.msg.pack(fill="x", padx=4)
        self.chart = BarChart(self, height=190)
        self.chart.pack(fill="x", pady=6)
        ctk.CTkLabel(self, text="Anomalies detected", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=4)
        self.atable = Table(self, ["lvl", "code", "msg"], ["Level", "Type", "Message"], [90, 190, 700], height=5)
        self.atable.pack(fill="both", expand=True, pady=4)

    def refresh(self):
        w = metar_parser.get_latest()
        if w and not self.ws.get():                       # first time: take the wind from the last METAR
            if w.get("wind_dir") is not None:
                self.wd.insert(0, str(w["wind_dir"]))
            if w.get("wind_kt") is not None:
                self.ws.insert(0, str(w["wind_kt"]))
            if w.get("gust_kt"):
                self.wg.insert(0, str(w["gust_kt"]))
            self.rules.set(w.get("flight_rules", "VFR"))
            self.src.configure(text="wind from last METAR")
        self.analyze()

    @staticmethod
    def _num(entry):
        try:
            return float(entry.get())
        except ValueError:
            return None

    def analyze(self):
        res = ai_support.suggest_runway(self.op.get(), self._num(self.wd), self._num(self.ws),
                                        self._num(self.wg), self.rules.get())
        self.rtable.set([(r["runway"], "YES" if r["usable"] else "NO", r["score"], f"{r['headwind']:+.0f} kt",
                          f"{r['crosswind']:.0f} kt", "; ".join(r["reasons"])) for r in res])
        fc = ai_support.predict_congestion()
        self.msg.configure(text=fc["message"], text_color=RED if "CRITICAL" in fc["message"] else
                           (AMBER if "HIGH" in fc["message"] else GREEN))
        self.chart.plot([s[0] for s in fc["steps"]],
                        [("Arrivals / 60 min", [s[1] for s in fc["steps"]], AMBER),
                         ("Departures / 60 min", [s[2] for s in fc["steps"]], GREEN)],
                        title="Traffic forecast - next 2 hours (UTC)")
        self.atable.set([(a["level"], a["code"], a["message"]) for a in ai_support.detect_anomalies()], status_index=0)


# ================================================================== v2 : reports
class ReportsPage(Page):
    def __init__(self, app):
        super().__init__(app)
        heading(self, "Reports & Statistics", "Traffic, runways, delays and alerts").pack(anchor="w", pady=(0, 10))
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x")
        self.cards = {}
        for i, (k, t, c) in enumerate([("total", "Flights", ACCENT), ("arr", "Arrivals", AMBER), ("dep", "Departures", GREEN),
                                       ("delay", "Avg ATFCM delay", TEXT), ("alerts", "Alerts (all time)", RED)]):
            cd = card(row, t, "0", c)
            cd.grid(row=0, column=i, padx=5, sticky="nsew")
            row.columnconfigure(i, weight=1)
            self.cards[k] = cd
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x", pady=8)
        btn(bar, "Export flights CSV", self.export, ACCENT_DARK, 160).pack(side="left")
        grid = ctk.CTkFrame(self, fg_color="transparent")
        grid.pack(fill="both", expand=True)
        grid.columnconfigure((0, 1), weight=1, uniform="r")
        grid.rowconfigure((0, 1), weight=1)
        self.c_status, self.c_hour, self.c_rwy, self.c_alert = (BarChart(grid, height=200) for _ in range(4))
        for i, ch in enumerate((self.c_status, self.c_hour, self.c_rwy, self.c_alert)):
            ch.grid(row=i // 2, column=i % 2, sticky="nsew", padx=5, pady=5)

    def refresh(self):
        one = lambda sql, p=(): db_one(sql, p)[0]
        self.cards["total"].value.configure(text=str(one("SELECT COUNT(*) FROM flights")))
        self.cards["arr"].value.configure(text=str(one("SELECT COUNT(*) FROM flights WHERE destination=?", (ICAO,))))
        self.cards["dep"].value.configure(text=str(one("SELECT COUNT(*) FROM flights WHERE departure=?", (ICAO,))))
        self.cards["delay"].value.configure(text=f"{atfcm_mod.delay_statistics()['average']} min")
        self.cards["alerts"].value.configure(text=str(one("SELECT COUNT(*) FROM alerts")))
        st = db_all("SELECT status, COUNT(*) FROM flights GROUP BY status ORDER BY COUNT(*) DESC")
        self.c_status.plot([s[0][:8] for s in st], [("Flights", [s[1] for s in st], ACCENT)], title="Flights by status")
        arr, dep = capacity_mod.hourly_profile()
        self.c_hour.plot([f"{h:02d}" for h in range(24)], [("Arr", arr, AMBER), ("Dep", dep, GREEN)],
                         title="Peak hours (UTC)")
        rw = db_all("SELECT runway, COUNT(*) FROM flights WHERE runway<>'' GROUP BY runway ORDER BY runway")
        self.c_rwy.plot([f"RWY {r[0]}" for r in rw], [("Flights", [r[1] for r in rw], GREEN)], title="Runway usage")
        al = db_all("SELECT code, COUNT(*) FROM alerts GROUP BY code ORDER BY COUNT(*) DESC LIMIT 8")
        self.c_alert.plot([a[0][:9] for a in al], [("Alerts", [a[1] for a in al], RED)], title="Alerts by type")

    def export(self):
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")],
                                            initialfile=f"aoms_flights_{datetime.utcnow():%Y%m%d}.csv")
        if not path:
            return
        rows = db_all(f"SELECT {', '.join(FLIGHT_COLS)} FROM flights ORDER BY etd")
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(FLIGHT_HEAD)
            w.writerows(rows)
        log(self.user, "REPORT EXPORT", path)
        messagebox.showinfo("Export", f"{len(rows)} flights saved.")


# ================================================================== v3 : AIP data + chart library
AirportDataPage, ChartsPage = aip_pages.build(sys.modules[__name__])


class App(ctk.CTk):
    NAV = [("Dashboard", "▦", DashboardPage, "dashboard"),
           ("Flights", "✈", FlightsPage, "show_flights"),
           ("Runways", "▬", RunwaysPage, "show_runways"),
           ("Airport Data", "⌂", AirportDataPage, "airport_info"),
           ("Charts", "▣", ChartsPage, "charts"),
           ("Traffic", "⇅", TrafficPage, "show_flights"),
           ("Capacity", "▤", CapacityPage, "capacity"),
           ("ATFCM", "◷", AtfcmPage, "atfcm"),
           ("Weather", "☁", WeatherPage, "metar"),
           ("NOTAM", "⚑", NotamPage, "notam"),
           ("Alerts", "▲", AlertsPage, "alerts"),
           ("Air Map", "◎", MapPage, "live_flights"),
           ("AI Support", "✦", AIPage, "ai_support"),
           ("Reports", "▥", ReportsPage, "statistics"),
           ("Live Flights", "◉", LivePage, "live_flights"),
           ("Users", "☺", UsersPage, "show_users"),
           ("Logs", "≡", LogsPage, "view_logs"),
           ("Backup", "⬒", BackupPage, "backup")]

    def __init__(self, user):
        super().__init__()
        self.user = user
        self.logged_out = False
        self.title(f"AOMS - {AIRPORT_NAME}")
        self.geometry("1280x780")
        self.minsize(1100, 680)
        self.configure(fg_color=BG)
        style_tree()
        ensure_runways()
        self.last_activity = datetime.now()
        for ev in ("<Key>", "<Button>", "<Motion>"):
            self.bind_all(ev, self._touch, add="+")

        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        side = ctk.CTkFrame(self, fg_color=SIDEBAR, corner_radius=0, width=220)
        side.grid(row=0, column=0, sticky="nsw")
        side.grid_propagate(False)
        ctk.CTkLabel(side, text="✈  AOMS", font=ctk.CTkFont(size=24, weight="bold"),
                     text_color=ACCENT).pack(anchor="w", padx=20, pady=(22, 0))
        ctk.CTkLabel(side, text=f"{ICAO} · {IATA}", text_color=MUTED).pack(anchor="w", padx=22, pady=(0, 10))
        ctk.CTkLabel(side, text="إعداد رحمة بوعلي", text_color=MUTED,
                     font=ctk.CTkFont(size=10), wraplength=200).pack(side="bottom", pady=10)
        nav = ctk.CTkScrollableFrame(side, fg_color="transparent", corner_radius=0)
        nav.pack(fill="both", expand=True)

        right = ctk.CTkFrame(self, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)

        header = ctk.CTkFrame(right, fg_color=SIDEBAR, corner_radius=0, height=60)
        header.grid(row=0, column=0, sticky="ew")
        self.title_lbl = ctk.CTkLabel(header, text="", font=ctk.CTkFont(size=14, weight="bold"))
        self.title_lbl.pack(side="left", padx=22, pady=16)
        btn(header, "Logout", self.logout, PANEL2, 80).pack(side="right", padx=16)
        ctk.CTkLabel(header, text=f"{user['full_name']}  ·  {user['role']}", text_color=MUTED).pack(side="right", padx=8)
        self.clock = ctk.CTkLabel(header, text="", font=ctk.CTkFont(family="Consolas", size=15, weight="bold"),
                                  text_color=ACCENT)
        self.clock.pack(side="right", padx=18)
        self.badge = ctk.CTkLabel(header, text="", font=ctk.CTkFont(size=13, weight="bold"))
        if check_permission(user, "alerts"):
            self.badge.pack(side="right", padx=8)
            self.badge.bind("<Button-1>", lambda e: self.show("Alerts") if "Alerts" in self.pages else None)

        self.content = ctk.CTkFrame(right, fg_color="transparent")
        self.content.grid(row=1, column=0, sticky="nsew", padx=20, pady=16)
        self.content.rowconfigure(0, weight=1)
        self.content.columnconfigure(0, weight=1)

        self.pages, self.buttons, self.current = {}, {}, None
        first = None
        for name, icon, cls, perm in self.NAV:
            if not check_permission(user, perm):
                continue
            ic = icons.load(name, 26)                    # colored PNG icon (assets/icons); text glyph if missing
            b = ctk.CTkButton(nav, text=f"  {name}" if ic else f"  {icon}   {name}", image=ic, compound="left",
                              anchor="w", height=42, corner_radius=10,
                              fg_color="transparent", hover_color=PANEL2, text_color=TEXT,
                              font=ctk.CTkFont(size=14), command=lambda n=name: self.show(n))
            b.pack(fill="x", padx=4, pady=1)
            self.buttons[name] = b
            self.pages[name] = cls(self)
            self.pages[name].grid(row=0, column=0, sticky="nsew")
            first = first or name
        try:
            alerts_mod.sync_alerts()
            self.update_badge()
        except Exception:
            pass
        if first:
            self.show(first)
        self.tick()
        self.auto_refresh()
        self._notam_busy, self._notam_done = False, False
        self.after(20000, self.notam_auto)
        self.after(30000, self.check_timeout)
        self.protocol("WM_DELETE_WINDOW", self.quit_app)

    def _touch(self, _=None):
        self.last_activity = datetime.now()

    def show(self, name):
        self.current = name
        for n, b in self.buttons.items():
            b.configure(fg_color=ACCENT_DARK if n == name else "transparent")
        self.pages[name].tkraise()
        self.title_lbl.configure(text=name.upper())
        try:
            self.pages[name].refresh()
        except sqlite3.Error as e:
            messagebox.showerror("Database", str(e))

    def tick(self):
        self.clock.configure(text=f"{get_utc_date()}  {get_utc_time()}")
        self.after(1000, self.tick)

    def update_badge(self):
        total, critical = alerts_mod.count_active()
        self.badge.configure(text=f"●  {total} alert{'s' if total != 1 else ''}",
                             text_color=RED if critical else (AMBER if total else GREEN))

    def auto_refresh(self):
        try:
            alerts_mod.sync_alerts()
            self.update_badge()
        except Exception:
            pass
        if self.current in ("Dashboard", "Traffic", "Runways", "Capacity", "ATFCM", "Alerts", "Weather"):
            try:
                self.pages[self.current].refresh()
            except Exception:
                pass
        self.after(10000, self.auto_refresh)

    def notam_auto(self):
        """Background NOTAM import (only when enabled in NOTAM > API and the interval elapsed)."""
        try:
            if self._notam_busy and self._notam_done:
                self._notam_busy = self._notam_done = False
                alerts_mod.sync_alerts()
                self.update_badge()
                if self.current == "NOTAM":
                    self.pages["NOTAM"].refresh()
            elif not self._notam_busy and notam_api.due():
                self._notam_busy = True

                def work():
                    try:
                        notam_api.sync("auto")
                    except Exception:                      # error text is already stored in the settings
                        pass
                    self._notam_done = True

                threading.Thread(target=work, daemon=True).start()
        except Exception:
            self._notam_busy = self._notam_done = False
        self.after(15000, self.notam_auto)

    def check_timeout(self):
        if (datetime.now() - self.last_activity).total_seconds() > SESSION_TIMEOUT * 60:
            messagebox.showwarning("Session", "Session expired. Please sign in again.")
            return self.logout()
        self.after(30000, self.check_timeout)

    def logout(self):
        log(self.user, "LOGOUT", "GUI logout")
        self.logged_out = True
        self.destroy()

    def quit_app(self):
        self.destroy()


def main():
    while True:
        login = LoginWindow()
        login.mainloop()
        if not login.user:
            break
        app = App(login.user)
        app.mainloop()
        if not app.logged_out:
            break


if __name__ == "__main__":
    from database import initialize_database
    if initialize_database(gui=True) is not None:
        aip_loader.sync_safe()
        main()
