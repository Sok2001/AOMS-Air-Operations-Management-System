"""Dialogs for the automatic NOTAM feature (v3.4). Built with the same theme as the rest of the GUI:
    NotamApiDialog, PasteNotamDialog, run_async = notam_ui.build(sys.modules[__name__])"""

import threading
import webbrowser

import notam_api


def run_async(widget, func, done):
    """Run func() in a thread (the window stays responsive), then call done(ok, result) in the Tk thread."""
    box = {}

    def work():
        try:
            box["r"] = (True, func())
        except Exception as e:                       # noqa
            box["r"] = (False, str(e))

    threading.Thread(target=work, daemon=True).start()

    def poll():
        if "r" in box:
            done(*box["r"])
        else:
            widget.after(300, poll)

    widget.after(300, poll)


def build(G):
    ctk, messagebox, btn = G.ctk, G.messagebox, G.btn
    BG, PANEL, PANEL2, MUTED, GREEN, ACCENT_DARK, TEXT = G.BG, G.PANEL, G.PANEL2, G.MUTED, G.GREEN, G.ACCENT_DARK, G.TEXT

    class NotamApiDialog(ctk.CTkToplevel):
        """API key, locations, interval and monthly call limit of the automatic NOTAM import."""

        def __init__(self, parent, on_close=None, fetch_now=None):
            super().__init__(parent)
            self.title("NOTAM API settings")
            self.geometry("560x600")
            self.minsize(520, 480)
            self.configure(fg_color=BG)
            self.transient(parent)
            self.after(150, self.grab_set)
            self.on_close, self.fetch_now = on_close, fetch_now
            bar = ctk.CTkFrame(self, fg_color="transparent")          # packed first: always visible
            bar.pack(side="bottom", fill="x", padx=16, pady=(0, 14))
            btn(bar, "Save", self.save, GREEN, 100, hover="#15803d").pack(side="right", padx=4)
            btn(bar, "Save && fetch now", self.save_fetch, ACCENT_DARK, 150).pack(side="right", padx=4)
            btn(bar, "Cancel", self.destroy, PANEL2, 90).pack(side="right", padx=4)
            box = ctk.CTkScrollableFrame(self, fg_color=PANEL, corner_radius=14)
            box.pack(fill="both", expand=True, padx=16, pady=16)
            s = notam_api.get_settings()
            ctk.CTkLabel(box, text="Source: ICAO API Data Service - Realtime NOTAMs (free key, limited free calls)",
                         text_color=MUTED, wraplength=470, justify="left").pack(anchor="w", padx=14, pady=(10, 0))
            btn(box, "Get a free API key (opens website)", lambda: webbrowser.open(notam_api.KEY_URL),
                PANEL2, 260).pack(anchor="w", padx=14, pady=6)
            self.enabled = ctk.CTkSwitch(box, text="Fetch automatically in the background")
            (self.enabled.select if s["enabled"] == "1" else self.enabled.deselect)()
            self.enabled.pack(anchor="w", padx=14, pady=8)
            self.fields = {}
            for key, label, show in (("api_key", "API key", "•"),
                                     ("locations", "Locations (ICAO aerodrome / FIR, comma separated, max 10)", None),
                                     ("interval_h", "Fetch every (hours)  -  6, 12, 24 ...", None),
                                     ("monthly_limit", "Stop after N calls per month (free tier is limited)", None)):
                ctk.CTkLabel(box, text=label, text_color=MUTED).pack(anchor="w", padx=14, pady=(8, 0))
                e = ctk.CTkEntry(box, show=show) if show else ctk.CTkEntry(box)
                e.pack(fill="x", padx=14)
                e.insert(0, s[key])
                self.fields[key] = e
            self.status = ctk.CTkLabel(
                box, justify="left", wraplength=470, text_color=MUTED,
                text=f"Calls this month: {notam_api.calls_used(s)} / {s['monthly_limit']}\n"
                     f"Last attempt: {s['last_attempt'] or '-'} UTC\n{s['last_status']}")
            self.status.pack(anchor="w", padx=14, pady=12)
            ctk.CTkLabel(box, text="The key is stored in the local database (or read from the ICAO_API_KEY environment "
                                   "variable). If no key is available use 'Paste NOTAM' - it needs no key.",
                         text_color=MUTED, wraplength=470, justify="left").pack(anchor="w", padx=14, pady=(0, 10))

        def _store(self):
            try:
                interval = max(1, int(self.fields["interval_h"].get()))
                limit = max(1, int(self.fields["monthly_limit"].get()))
            except ValueError:
                messagebox.showerror("NOTAM API", "Interval and monthly limit must be whole numbers.", parent=self)
                return False
            notam_api.save_settings(enabled="1" if self.enabled.get() else "0",
                                    api_key=self.fields["api_key"].get().strip(),
                                    locations=self.fields["locations"].get().strip().upper(),
                                    interval_h=interval, monthly_limit=limit)
            return True

        def save(self):
            if self._store():
                self.close()

        def save_fetch(self):
            if self._store():
                self.close()
                if self.fetch_now:
                    self.fetch_now()

        def close(self):
            cb = self.on_close
            self.destroy()
            if cb:
                cb()

    class PasteNotamDialog(ctk.CTkToplevel):
        """Paste one or several NOTAMs in ICAO format (A1234/26 NOTAMN ... Q) A) B) C) E) ...)."""

        def __init__(self, parent, user, on_done=None):
            super().__init__(parent)
            self.title("Paste NOTAM text")
            self.geometry("640x520")
            self.minsize(520, 400)
            self.configure(fg_color=BG)
            self.transient(parent)
            self.after(150, self.grab_set)
            self.user, self.on_done = user, on_done
            bar = ctk.CTkFrame(self, fg_color="transparent")
            bar.pack(side="bottom", fill="x", padx=16, pady=(0, 14))
            btn(bar, "Import", self.run, GREEN, 110, hover="#15803d").pack(side="right", padx=4)
            btn(bar, "Cancel", self.destroy, PANEL2, 90).pack(side="right", padx=4)
            box = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=14)
            box.pack(fill="both", expand=True, padx=16, pady=16)
            ctk.CTkLabel(box, text="Paste the NOTAM(s) as published, for example:\n"
                                   "A0123/26 NOTAMN\nQ) DAAA/QMRLC/IV/NBO/A/000/999/3641N00313E005\n"
                                   "A) DAAG B) 2611011200 C) 2611011800\nE) RWY 09/27 CLSD DUE WIP",
                         text_color=MUTED, justify="left").pack(anchor="w", padx=14, pady=(12, 6))
            self.text = ctk.CTkTextbox(box, fg_color=PANEL2, font=ctk.CTkFont(family="Consolas", size=12))
            self.text.pack(fill="both", expand=True, padx=14, pady=(0, 14))

        def run(self):
            raw = self.text.get("1.0", "end").strip()
            if not raw:
                return messagebox.showinfo("NOTAM", "Paste some text first.", parent=self)
            stats, found = notam_api.import_text(raw, self.user["username"])
            if not found:
                return messagebox.showwarning("NOTAM", "No NOTAM header found (expected e.g. 'A0123/26 NOTAMN').",
                                              parent=self)
            messagebox.showinfo("NOTAM", f"{found} NOTAM found: {stats['new']} added, "
                                         f"{stats['cancelled']} cancelled.", parent=self)
            cb = self.on_done
            self.destroy()
            if cb:
                cb()

    return NotamApiDialog, PasteNotamDialog, run_async
