"""
Airport Data + Charts pages (added in v3).

Kept in a separate module so the existing GUI file is not rewritten: aoms_gui.py calls
    AirportDataPage, ChartsPage = aip_pages.build(sys.modules[__name__])
and receives page classes that use the same theme, Table, heading, btn helpers as every other page.
"""

import os
import shutil
import subprocess
import sys

import aip_data
import aip_loader


def fmt(v):
    if isinstance(v, float) and v.is_integer():
        return int(v)
    return "" if v is None else v


def dms(value, is_lat):
    """Decimal degrees -> 36°41'59.61"N (empty string when value is None)."""
    if value is None:
        return ""
    hemi = ("N" if value >= 0 else "S") if is_lat else ("E" if value >= 0 else "W")
    v = abs(value)
    d = int(v)
    m = int((v - d) * 60)
    s = round((v - d - m / 60) * 3600, 2)
    if s >= 60:
        s, m = 0.0, m + 1
    return f"{d}°{m:02d}'{s:05.2f}\"{hemi}"


def open_external(path):
    """Open a file with the system viewer (Windows / macOS / Linux)."""
    if sys.platform.startswith("win"):
        os.startfile(path)                      # noqa
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])


def render_pdf_preview(pdf_path, png_base, dpi=150):
    """Render page 1 of a PDF to <png_base>.png with PyMuPDF or pdftoppm. Returns the png path or None."""
    out = png_base + ".png"
    try:
        import fitz                              # PyMuPDF (optional)
        doc = fitz.open(pdf_path)
        doc[0].get_pixmap(dpi=dpi).save(out)
        return out
    except Exception:
        pass
    try:
        subprocess.run(["pdftoppm", "-r", str(dpi), "-f", "1", "-l", "1", "-singlefile", "-png",
                        pdf_path, png_base], check=True, capture_output=True, timeout=120)
        return out if os.path.exists(out) else None
    except Exception:
        return None


def build(G):
    ctk, tk, messagebox, filedialog = G.ctk, G.tk, G.messagebox, G.filedialog
    Page, Table, heading, btn = G.Page, G.Table, G.heading, G.btn
    PANEL, PANEL2, MUTED, TEXT, ACCENT, ICAO = G.PANEL, G.PANEL2, G.MUTED, G.TEXT, G.ACCENT, G.ICAO

    try:
        from PIL import Image, ImageTk
        PIL_OK = True
    except Exception:                            # Pillow not installed
        PIL_OK = False

    # ================================================================== Airport data
    class AirportDataPage(Page):
        """Read-only AIP data of the aerodrome (AD 2.x) stored in the database."""

        def __init__(self, app):
            super().__init__(app)
            heading(self, "Airport Data", f"{ICAO} · AIP AD 2 (transcribed) · charts AIRAC AMDT 01/26"
                    ).pack(anchor="w", pady=(0, 10))
            self.tabs = ctk.CTkTabview(self, fg_color=PANEL, corner_radius=12)
            self.tabs.pack(fill="both", expand=True)
            for name in ("Info", "Runways", "Navaids", "Frequencies", "Stands", "Taxiways", "Obstacles", "Notes"):
                self.tabs.add(name)
            self.info = ctk.CTkTextbox(self.tabs.tab("Info"), wrap="word", fg_color=PANEL2,
                                       font=ctk.CTkFont(family="Consolas", size=12))
            self.info.pack(fill="both", expand=True, padx=6, pady=6)
            self.notes = ctk.CTkTextbox(self.tabs.tab("Notes"), wrap="word", fg_color=PANEL2,
                                        font=ctk.CTkFont(size=12))
            self.notes.pack(fill="both", expand=True, padx=6, pady=6)
            self.rwy = Table(self.tabs.tab("Runways"),
                             ["rwy", "true", "mag", "len", "wid", "surface", "pcr", "elev", "tora", "toda", "asda",
                              "lda", "ils", "loc", "gp", "dme"],
                             ["RWY", "True°", "Mag°", "Length", "Width", "Surface", "PCR", "THR elev", "TORA",
                              "TODA", "ASDA", "LDA", "ILS", "LOC", "GP", "DME"],
                             [45, 55, 50, 60, 55, 140, 120, 70, 55, 55, 55, 55, 90, 100, 90, 110])
            self.rwy.pack(fill="both", expand=True)
            self.nav = Table(self.tabs.tab("Navaids"),
                             ["type", "id", "freq", "ch", "lat", "lon", "rem"],
                             ["Type", "ID", "Frequency", "Channel", "Latitude", "Longitude", "Remarks"],
                             [90, 55, 100, 70, 120, 120, 330])
            self.nav.pack(fill="both", expand=True)
            self.frq = Table(self.tabs.tab("Frequencies"), ["s", "c", "f", "h", "r"],
                             ["Service", "Call sign", "Frequency (MHz)", "Hours", "Remarks"],
                             [120, 160, 170, 80, 200])
            self.frq.pack(fill="both", expand=True)
            bar = ctk.CTkFrame(self.tabs.tab("Stands"), fg_color="transparent")
            bar.pack(fill="x", padx=6, pady=(6, 0))
            ctk.CTkLabel(bar, text="Search (apron / stand / category):", text_color=MUTED).pack(side="left")
            self.q = ctk.CTkEntry(bar, width=220)
            self.q.pack(side="left", padx=8)
            self.q.bind("<KeyRelease>", lambda e: self._stands())
            self.stands = Table(self.tabs.tab("Stands"), ["a", "s", "c", "st", "lat", "lon"],
                                ["Apron", "Stand", "Aircraft cat/type", "Bearing strength", "Latitude", "Longitude"],
                                [70, 70, 150, 230, 130, 130])
            self.stands.pack(fill="both", expand=True)
            self.twy = Table(self.tabs.tab("Taxiways"), ["t", "w", "s", "p", "r"],
                             ["TWY", "Width (m)", "Surface", "Strength", "Remarks"], [140, 80, 180, 140, 250])
            self.twy.pack(fill="both", expand=True)
            self.obs = Table(self.tabs.tab("Obstacles"), ["i", "t", "p", "e", "m", "a", "r"],
                             ["ID", "Type", "Position", "ELEV / HGT", "Marking", "Area", "Remarks"],
                             [120, 150, 260, 190, 120, 140, 80])
            self.obs.pack(fill="both", expand=True)

        def _stands(self):
            self.stands.set([(a, s, c, st, dms(la, True), dms(lo, False))
                             for a, s, c, st, la, lo in aip_data.stands(ICAO, self.q.get().strip())])

        def _put(self, box, text):
            box.configure(state="normal")
            box.delete("1.0", "end")
            box.insert("1.0", text)
            box.configure(state="disabled")

        def refresh(self):
            ap = aip_data.get_airport(ICAO)
            if not ap:
                self._put(self.info, "No AIP data for this airport.\nRestart the program, or check data/daag/*.json.")
                return
            lines = [f"{ap['icao']} / {ap['iata']}  -  {ap['name']}", "",
                     f"ARP            : {dms(ap['arp_lat'], True)}  {dms(ap['arp_lon'], False)}",
                     f"Elevation      : {fmt(ap['elevation_m'])} M   Ref. temp: {ap['ref_temp_c']} °C",
                     f"Mag variation  : {ap['mag_var']}", f"Location       : {ap['location']}",
                     f"Traffic        : {ap['traffic']}", f"Data           : {ap['airac']}",
                     f"Source         : {ap['source']}", ""]
            for title, text in aip_data.sections(ICAO):
                lines += [f"■ {title}", f"   {text}", ""]
            self._put(self.info, "\n".join(lines))
            self._put(self.notes, "\n\n".join(f"• {n}" for n in aip_data.notes(ICAO)))
            self.rwy.set([(r[0], fmt(r[1]), fmt(r[2]), fmt(r[3]), fmt(r[4]), r[5], r[6], fmt(r[7]), fmt(r[8]),
                           fmt(r[9]), fmt(r[10]), fmt(r[11]), (r[12] + (" " + r[13].split(" (")[0] if r[13] else "")),
                           r[14], r[15], r[16]) for r in aip_data.runways(ICAO)])
            self.nav.set([(t, i, f, c, dms(la, True), dms(lo, False), rem)
                          for t, i, f, c, la, lo, rem in aip_data.navaids(ICAO)])
            self.frq.set(aip_data.frequencies(ICAO))
            self._stands()
            self.twy.set([(t, fmt(w), s, p, r) for t, w, s, p, r in aip_data.taxiways(ICAO)])
            self.obs.set(aip_data.obstacles(ICAO))

    # ================================================================== Charts
    class ChartsPage(Page):
        """Chart library: AD, APDC, SID, STAR, IAC, VAC, AOC, PATC ... (files in charts/<ICAO>/)."""

        def __init__(self, app):
            super().__init__(app)
            self._zfit = True
            heading(self, "Charts", f"{ICAO} chart library - drop <CODE>.pdf / .png in charts/{ICAO}/ or use Import"
                    ).pack(anchor="w", pady=(0, 8))
            bar = ctk.CTkFrame(self, fg_color="transparent")
            bar.pack(fill="x", pady=(0, 8))
            self.seg = ctk.CTkSegmentedButton(bar, values=["ALL"], command=lambda v: self.refresh())
            self.seg.set("ALL")
            self.seg.pack(side="left", padx=(0, 10))
            self.only = ctk.CTkCheckBox(bar, text="Available only", command=self.refresh)
            self.only.pack(side="left", padx=6)
            if self.can("edit_charts"):
                btn(bar, "Import chart…", self.import_chart, G.ACCENT_DARK, 120).pack(side="right", padx=3)
            btn(bar, "Rescan", self.rescan, PANEL2, 80).pack(side="right", padx=3)
            btn(bar, "Open in viewer", self.open_viewer, PANEL2, 120).pack(side="right", padx=3)

            body = ctk.CTkFrame(self, fg_color="transparent")
            body.pack(fill="both", expand=True)
            body.columnconfigure(1, weight=1)
            body.rowconfigure(0, weight=1)
            self.table = Table(body, ["code", "type", "title", "rwy", "cat", "date", "st"],
                               ["Code", "Type", "Title", "RWY", "Cat", "Date", "Status"],
                               [95, 65, 230, 55, 65, 80, 80], width=620)
            self.table.grid(row=0, column=0, sticky="ns", padx=(0, 10))
            self.table.tree.bind("<<TreeviewSelect>>", self._on_select)
            right = ctk.CTkFrame(body, fg_color=PANEL, corner_radius=12)
            right.grid(row=0, column=1, sticky="nsew")
            right.rowconfigure(1, weight=1)
            right.columnconfigure(0, weight=1)
            tools = ctk.CTkFrame(right, fg_color="transparent")
            tools.grid(row=0, column=0, columnspan=2, sticky="ew", padx=8, pady=(8, 0))
            btn(tools, "−", lambda: self._zoom(1 / 1.25), PANEL2, 36).pack(side="left", padx=2)
            btn(tools, "+", lambda: self._zoom(1.25), PANEL2, 36).pack(side="left", padx=2)
            btn(tools, "Fit", self._fit, PANEL2, 50).pack(side="left", padx=2)
            self.info = ctk.CTkLabel(tools, text="Select a chart", text_color=MUTED)
            self.info.pack(side="left", padx=10)
            self.canvas = tk.Canvas(right, bg="#07101f", highlightthickness=0)
            self.canvas.grid(row=1, column=0, sticky="nsew", padx=8, pady=8)
            self.canvas.bind("<ButtonPress-1>", lambda e: self.canvas.scan_mark(e.x, e.y))
            self.canvas.bind("<B1-Motion>", lambda e: self.canvas.scan_dragto(e.x, e.y, gain=1))
            self.canvas.bind("<MouseWheel>", lambda e: self._zoom(1.15 if e.delta > 0 else 1 / 1.15))
            self.canvas.bind("<Button-4>", lambda e: self._zoom(1.15))
            self.canvas.bind("<Button-5>", lambda e: self._zoom(1 / 1.15))
            self.canvas.bind("<Configure>", lambda e: self._fit() if self._zfit else None)
            self._img_base = None          # PIL image
            self._img_tk = None            # keep a reference (Tk would garbage-collect it)
            self._zscale = 1.0
            self._zfit = True
            self.current = None        # code of the selected chart

        # ---- list
        def refresh(self):
            types = ["ALL"] + aip_data.chart_types(ICAO)
            self.seg.configure(values=types)
            if self.seg.get() not in types:
                self.seg.set("ALL")
            rows = []
            for r in aip_data.charts(ICAO, self.seg.get()):
                ok = aip_data.is_available(r)
                if self.only.get() and not ok:
                    continue
                rows.append((r[0], r[1], r[2], r[3], r[4], r[5], "Available" if ok else "Missing"))
            self.table.set(rows)

        def rescan(self):
            aip_loader.sync_safe(ICAO)
            self.refresh()

        def _selected_code(self):
            v = self.table.selected()
            return str(v[0]) if v else self.current

        # ---- viewer
        def _on_select(self, _=None):
            v = self.table.selected()
            if not v:
                return
            self.current = str(v[0])
            preview, pdf = aip_data.chart_paths(self.current, ICAO)
            self.canvas.delete("all")
            self._img_base = None
            if not (preview or pdf):
                self.info.configure(text=f"{self.current}: file not provided yet - Import it or copy "
                                         f"{self.current}.pdf into charts/{ICAO}/")
                return
            if preview and PIL_OK:
                try:
                    self._img_base = Image.open(preview)
                    self._img_base.load()
                    self._zfit = True
                    self.info.configure(text=f"{self.current}  ·  {self._img_base.width}×{self._img_base.height}px  ·  "
                                             "wheel = zoom, drag = move")
                    self.after(50, self._fit)
                    return
                except Exception as e:
                    self.info.configure(text=f"Cannot display {self.current}: {e}")
                    return
            self.info.configure(text=f"{self.current}: no image preview ({'install pillow' if not PIL_OK else 'PDF only'})"
                                     " - use 'Open in viewer'")

        def _fit(self):
            if self._img_base is None:
                return
            w, h = max(self.canvas.winfo_width(), 100), max(self.canvas.winfo_height(), 100)
            self._zfit = True
            self._zscale = min(w / self._img_base.width, h / self._img_base.height)
            self._render()

        def _zoom(self, factor):
            if self._img_base is None:
                return
            self._zfit = False
            self._zscale = max(0.05, min(4.0, self._zscale * factor))
            self._render()

        def _render(self):
            w, h = int(self._img_base.width * self._zscale), int(self._img_base.height * self._zscale)
            img = self._img_base.resize((max(w, 1), max(h, 1)), Image.LANCZOS if self._zscale < 1 else Image.BICUBIC)
            self._img_tk = ImageTk.PhotoImage(img)
            self.canvas.delete("all")
            self.canvas.create_image(0, 0, anchor="nw", image=self._img_tk)
            self.canvas.configure(scrollregion=(0, 0, w, h))
            self.canvas.xview_moveto(0)
            self.canvas.yview_moveto(0)

        def open_viewer(self):
            code = self._selected_code()
            if not code:
                return messagebox.showinfo("Charts", "Select a chart first.")
            preview, pdf = aip_data.chart_paths(code, ICAO)
            path = pdf or preview
            if not path or not os.path.exists(path):
                return messagebox.showinfo("Charts", f"No file for {code} yet.")
            try:
                open_external(path)
            except Exception as e:
                messagebox.showerror("Charts", f"Cannot open the file: {e}")

        # ---- import
        def import_chart(self):
            src = filedialog.askopenfilename(title="Choose a chart file",
                                             filetypes=[("Charts", "*.pdf *.png *.jpg *.jpeg"), ("All", "*.*")])
            if not src:
                return
            guess = aip_loader.normalize_code(src, ICAO)
            known = ", ".join(r[0] for r in aip_data.charts(ICAO) if not aip_data.is_available(r))[:160]
            dlg = ctk.CTkInputDialog(text=f"Chart code (e.g. IAC1, SID2, VAC1, STAR1).\nMissing now: {known}",
                                     title=f"Import chart ({guess})")
            code = aip_data.clean_code(dlg.get_input() or "")
            if not code:
                return
            ext = os.path.splitext(src)[1].lower()
            folder = os.path.join(aip_loader.CHARTS_DIR, ICAO)
            os.makedirs(folder, exist_ok=True)
            dest = os.path.join(folder, code + ext)
            if os.path.exists(dest) and not messagebox.askyesno("Charts", f"{code}{ext} already exists. Replace it?"):
                return
            try:
                shutil.copyfile(src, dest)
                note = ""
                if ext == ".pdf" and not any(os.path.exists(os.path.join(folder, code + e))
                                             for e in (".png", ".jpg", ".jpeg")):
                    if not render_pdf_preview(dest, os.path.join(folder, code)):
                        note = "\n(No preview could be generated - install PyMuPDF or poppler, or add a PNG.)"
                aip_loader.scan_charts(ICAO)
                G.log(self.user, "CHART IMPORT", f"{ICAO} {code}{ext}")
            except Exception as e:
                return messagebox.showerror("Charts", f"Import failed: {e}")
            self.refresh()
            messagebox.showinfo("Charts", f"{code} imported.{note}")

    return AirportDataPage, ChartsPage
