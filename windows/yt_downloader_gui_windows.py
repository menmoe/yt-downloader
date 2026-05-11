#!/usr/bin/env python3
"""
windows/yt_downloader_gui_windows.py
─────────────────────────────────────
Windows GUI frontend.
All download logic lives in core/downloader.py — do not add logic here.

Build into a standalone .exe:
    Double-click build_windows.bat
"""

import os, sys, threading, queue, tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path

# ── Locate core/ whether running from source or a PyInstaller bundle ───────────
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
for _p in (_HERE, _ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from core.downloader import (   # noqa: E402
    fetch_entries, build_ydl_opts, make_outtmpl, resolve_path,
    format_eta, MP3_QUALITIES, MP4_QUALITIES,
    DEFAULT_MP3_QUALITY, DEFAULT_MP4_QUALITY,
)
import yt_dlp  # noqa: F401

# ── Colours / fonts ────────────────────────────────────────────────────────────
BG        = "#0f0f0f"
SURFACE   = "#1a1a1a"
SURFACE2  = "#242424"
BORDER    = "#2e2e2e"
RED       = "#ff0000"
RED_DARK  = "#cc0000"
RED_HOVER = "#e60000"
TEXT      = "#ffffff"
TEXT_DIM  = "#888888"
TEXT_MID  = "#cccccc"
SUCCESS   = "#22c55e"
WARNING   = "#f59e0b"
FONT      = ("Segoe UI", 11)
FONT_SM   = ("Segoe UI", 9)
FONT_LG   = ("Segoe UI", 18, "bold")
FONT_MONO = ("Consolas", 10)


# ── Rounded button ─────────────────────────────────────────────────────────────
class RoundedButton(tk.Canvas):
    def __init__(self, parent, text, command, bg=RED, fg=TEXT,
                 hover=RED_HOVER, radius=10, padx=20, pady=10, font=FONT, **kw):
        super().__init__(parent,
                         bg=parent["bg"] if hasattr(parent, "__getitem__") else BG,
                         highlightthickness=0, **kw)
        self._bg, self._hover, self._fg = bg, hover, fg
        self._cmd, self._radius         = command, radius
        self._text, self._font          = text, font
        self._padx, self._pady          = padx, pady
        self._disabled                  = False
        self._draw()
        self.bind("<Enter>",    self._on_enter)
        self.bind("<Leave>",    self._on_leave)
        self.bind("<Button-1>", self._on_click)

    def _draw(self, color=None):
        self.delete("all")
        c = color or self._bg
        w = self.winfo_reqwidth()  or int(self._padx * 2 + 120)
        h = self.winfo_reqheight() or int(self._pady * 2 + 24)
        r = self._radius
        self.create_arc(0,     0,     2*r,   2*r,   start=90,  extent=90,  fill=c, outline=c)
        self.create_arc(w-2*r, 0,     w,     2*r,   start=0,   extent=90,  fill=c, outline=c)
        self.create_arc(0,     h-2*r, 2*r,   h,     start=180, extent=90,  fill=c, outline=c)
        self.create_arc(w-2*r, h-2*r, w,     h,     start=270, extent=90,  fill=c, outline=c)
        self.create_rectangle(r, 0,   w-r,   h,     fill=c, outline=c)
        self.create_rectangle(0, r,   w,     h-r,   fill=c, outline=c)
        self.create_text(w//2, h//2, text=self._text, fill=self._fg,
                         font=self._font, anchor="center")

    def _on_enter(self, _):
        if not self._disabled: self._draw(self._hover)
    def _on_leave(self, _):
        if not self._disabled: self._draw(self._bg)
    def _on_click(self, _):
        if not self._disabled: self._cmd()

    def set_disabled(self, state: bool):
        self._disabled = state
        self._draw("#444444" if state else self._bg)


# ── Main application ───────────────────────────────────────────────────────────
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("YT Downloader")
        self.configure(bg=BG)
        self.resizable(False, False)

        # Windows DPI awareness
        try:
            from ctypes import windll
            windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass

        self._entries     = []
        self._selected    = []
        self._downloading = False
        self._cancel_flag = False
        self._queue       = queue.Queue()
        self._fmt         = tk.StringVar(value="mp3")
        self._quality     = tk.StringVar(value=DEFAULT_MP3_QUALITY)
        self._dest        = tk.StringVar(
            value=str(Path.home() / "Downloads" / "YT_Downloads"))

        self._build_ui()
        self.after(100, self._poll_queue)
        self.update_idletasks()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w,  h  = self.winfo_width(), self.winfo_height()
        self.geometry(f"+{(sw-w)//2}+{(sh-h)//2}")

    # ── UI ─────────────────────────────────────────────────────────────────────
    def _build_ui(self):
        pad = dict(padx=28, pady=0)

        hdr = tk.Frame(self, bg=BG)
        hdr.pack(fill="x", padx=28, pady=(28, 4))
        tk.Label(hdr, text="▶", font=("Arial", 20), bg=BG, fg=RED).pack(side="left")
        tk.Label(hdr, text="  YT Downloader", font=FONT_LG, bg=BG, fg=TEXT).pack(side="left")
        tk.Label(self, text="Download any YouTube video or playlist as MP3 or MP4.",
                 font=FONT_SM, bg=BG, fg=TEXT_DIM).pack(anchor="w", **pad)

        self._sep(pady=(14, 0))

        # URL
        self._section_label("YouTube URL")
        url_row = tk.Frame(self, bg=BORDER, padx=1, pady=1)
        url_row.pack(fill="x", **pad, pady=(6, 0))
        inner = tk.Frame(url_row, bg=BG)
        inner.pack(fill="x")
        self._url_var = tk.StringVar()
        url_e = tk.Entry(inner, textvariable=self._url_var, font=FONT,
                         bg=SURFACE2, fg=TEXT, insertbackground=TEXT, relief="flat", bd=0)
        url_e.pack(side="left", fill="x", expand=True, ipady=10, ipadx=12)
        url_e.bind("<Return>", lambda _: self._fetch())
        self._fetch_btn = RoundedButton(inner, "  Fetch  ", self._fetch,
                                        padx=16, pady=10, font=FONT, width=90, height=38)
        self._fetch_btn.pack(side="left", padx=(8, 0))

        self._sep(pady=(16, 0))

        # Video list
        self._section_label("Videos")
        lf = tk.Frame(self, bg=SURFACE)
        lf.pack(fill="x", **pad, pady=(6, 0))
        self._list_header = tk.Label(lf,
            text="Paste a URL above and click Fetch to load videos.",
            font=FONT_SM, bg=SURFACE, fg=TEXT_DIM, anchor="w", pady=10, padx=12)
        self._list_header.pack(fill="x")
        self._check_outer = tk.Frame(lf, bg=SURFACE)
        self._check_outer.pack(fill="x")
        self._canvas      = tk.Canvas(self._check_outer, bg=SURFACE,
                                       highlightthickness=0, height=0)
        self._scrollbar   = ttk.Scrollbar(self._check_outer, orient="vertical",
                                           command=self._canvas.yview)
        self._check_inner = tk.Frame(self._canvas, bg=SURFACE)
        self._canvas.create_window((0, 0), window=self._check_inner, anchor="nw")
        self._canvas.configure(yscrollcommand=self._scrollbar.set)
        self._check_inner.bind("<Configure>",
                               lambda _: self._canvas.configure(
                                   scrollregion=self._canvas.bbox("all")))
        self._sel_row  = tk.Frame(lf, bg=SURFACE)
        self._chk_vars = []

        self._sep(pady=(16, 0))

        # Format + Quality
        fq = tk.Frame(self, bg=BG)
        fq.pack(fill="x", **pad)
        fc = tk.Frame(fq, bg=BG)
        fc.pack(side="left", fill="x", expand=True)
        self._section_label("Format", parent=fc)
        fi = tk.Frame(fc, bg=BG)
        fi.pack(fill="x", pady=(6, 0))
        for val, lbl in [("mp3", "🎵  MP3  (audio only)"),
                          ("mp4", "🎬  MP4  (video + audio)")]:
            self._radio(fi, lbl, self._fmt, val, self._on_fmt_change)
        self._q_col = tk.Frame(fq, bg=BG)
        self._q_col.pack(side="left", fill="x", expand=True, padx=(28, 0))
        self._build_quality_panel()

        self._sep(pady=(16, 0))

        # Destination
        self._section_label("Save to")
        tk.Label(self,
                 text="Supports: $desktop  $downloads  $documents  $music  $videos  "
                      "$home  ~  %USERPROFILE%\\folder  relative paths",
                 font=FONT_SM, bg=BG, fg=TEXT_DIM).pack(anchor="w", **pad)
        dr = tk.Frame(self, bg=BORDER, padx=1, pady=1)
        dr.pack(fill="x", **pad, pady=(4, 0))
        di = tk.Frame(dr, bg=BG)
        di.pack(fill="x")
        tk.Entry(di, textvariable=self._dest, font=FONT_SM,
                 bg=SURFACE2, fg=TEXT_MID, insertbackground=TEXT,
                 relief="flat", bd=0).pack(
                     side="left", fill="x", expand=True, ipady=8, ipadx=10)
        RoundedButton(di, " Browse ", self._browse, bg=SURFACE2, hover="#333333",
                      padx=12, pady=8, font=FONT_SM, width=80, height=34).pack(
                          side="left", padx=(8, 0))

        self._sep(pady=(20, 0))

        # Progress
        pf = tk.Frame(self, bg=BG)
        pf.pack(fill="x", **pad)
        self._status_lbl = tk.Label(pf, text="", font=FONT_SM,
                                     bg=BG, fg=TEXT_DIM, anchor="w")
        self._status_lbl.pack(fill="x")
        self._progress = ttk.Progressbar(pf, mode="determinate", maximum=100)
        self._progress.pack(fill="x", pady=(6, 0))
        s = ttk.Style(); s.theme_use("default")
        s.configure("TProgressbar", troughcolor=SURFACE2, background=RED,
                    bordercolor=BG, lightcolor=RED, darkcolor=RED_DARK, thickness=6)

        # Log
        lo = tk.Frame(self, bg=SURFACE)
        lo.pack(fill="x", **pad, pady=(12, 0))
        self._log = tk.Text(lo, height=6, font=FONT_MONO, bg=SURFACE, fg=TEXT_DIM,
                             insertbackground=TEXT, relief="flat", bd=0,
                             padx=10, pady=8, state="disabled", wrap="word")
        lsb = ttk.Scrollbar(lo, command=self._log.yview)
        self._log.configure(yscrollcommand=lsb.set)
        self._log.pack(side="left", fill="both", expand=True)
        lsb.pack(side="right", fill="y")

        # Buttons
        br = tk.Frame(self, bg=BG)
        br.pack(fill="x", **pad, pady=(20, 28))
        self._dl_btn = RoundedButton(br, "  ⬇  Download  ", self._start_download,
                                     padx=24, pady=12, font=FONT, width=200, height=46)
        self._dl_btn.pack(side="right")
        self._cancel_btn = RoundedButton(br, "  Cancel  ", self._cancel,
                                          bg=SURFACE2, hover="#333333",
                                          padx=16, pady=12, font=FONT,
                                          width=120, height=46)
        self._cancel_btn.pack(side="right", padx=(0, 12))
        self._cancel_btn.set_disabled(True)

        self.geometry("700x860")

    def _sep(self, pady=(8, 0)):
        tk.Frame(self, bg=BORDER, height=1).pack(fill="x", padx=28, pady=pady)

    def _section_label(self, text, parent=None):
        p = parent or self
        tk.Label(p, text=text.upper(), font=(FONT[0], 8, "bold"),
                 bg=p["bg"], fg=TEXT_DIM, anchor="w").pack(
                     fill="x", padx=(0 if parent else 28), pady=(14, 0))

    def _radio(self, parent, label, var, value, cmd=None):
        row = tk.Frame(parent, bg=BG)
        row.pack(anchor="w", pady=2)
        tk.Radiobutton(row, text=label, variable=var, value=value, font=FONT,
                       bg=BG, fg=TEXT_MID, selectcolor=BG, activebackground=BG,
                       activeforeground=TEXT, command=cmd).pack(side="left")

    def _build_quality_panel(self):
        for w in self._q_col.winfo_children(): w.destroy()
        self._section_label("Quality", parent=self._q_col)
        qi = tk.Frame(self._q_col, bg=BG)
        qi.pack(fill="x", pady=(6, 0))
        if self._fmt.get() == "mp3":
            opts, default = MP3_QUALITIES, DEFAULT_MP3_QUALITY
        else:
            opts, default = MP4_QUALITIES, DEFAULT_MP4_QUALITY
        self._quality.set(default)
        for val, lbl in opts:
            self._radio(qi, lbl, self._quality, val)

    def _on_fmt_change(self):
        self._build_quality_panel()

    # ── Fetch ──────────────────────────────────────────────────────────────────
    def _fetch(self):
        import re
        url = self._url_var.get().strip()
        if not re.search(r"youtube\.com|youtu\.be", url):
            messagebox.showwarning("Invalid URL", "Please enter a valid YouTube URL.")
            return
        self._fetch_btn.set_disabled(True)
        self._list_header.configure(text="⏳  Fetching playlist info…", fg=TEXT_DIM)
        self._clear_checklist()
        threading.Thread(target=self._fetch_thread, args=(url,), daemon=True).start()

    def _fetch_thread(self, url):
        try:
            self._queue.put(("entries", fetch_entries(url)))
        except Exception as e:
            self._queue.put(("error", f"Fetch failed: {e}"))

    def _populate_checklist(self, entries):
        self._entries  = entries
        self._selected = list(entries)
        self._chk_vars = []
        self._clear_checklist()
        n = len(entries)
        self._list_header.configure(
            text=f"{'1 video' if n == 1 else f'{n} videos'} found "
                 f"— select which to download:", fg=TEXT_MID)
        if n > 1:
            for w in self._sel_row.winfo_children(): w.destroy()
            self._sel_row.pack(fill="x", padx=12, pady=(4, 2))
            tk.Button(self._sel_row, text="Select all", font=FONT_SM,
                      bg=SURFACE, fg=RED, bd=0, cursor="hand2",
                      activebackground=SURFACE, activeforeground=RED_HOVER,
                      command=self._select_all).pack(side="left")
            tk.Label(self._sel_row, text=" · ", font=FONT_SM,
                     bg=SURFACE, fg=TEXT_DIM).pack(side="left")
            tk.Button(self._sel_row, text="Select none", font=FONT_SM,
                      bg=SURFACE, fg=TEXT_DIM, bd=0, cursor="hand2",
                      activebackground=SURFACE, activeforeground=TEXT,
                      command=self._select_none).pack(side="left")
            self._canvas.configure(height=min(n, 8) * 30)
            self._canvas.pack(side="left", fill="both", expand=True)
            if n > 8: self._scrollbar.pack(side="right", fill="y")
        for e in entries:
            var = tk.BooleanVar(value=True)
            self._chk_vars.append(var)
            row = tk.Frame(self._check_inner, bg=SURFACE)
            row.pack(fill="x")
            tk.Checkbutton(row, text=f"  {e['index']:02d}  {e['title']}",
                           variable=var, font=FONT_SM, bg=SURFACE, fg=TEXT_MID,
                           selectcolor=SURFACE2, activebackground=SURFACE,
                           activeforeground=TEXT, anchor="w",
                           command=self._on_check_change).pack(fill="x", padx=8, ipady=4)
        self._fetch_btn.set_disabled(False)

    def _clear_checklist(self):
        for w in self._check_inner.winfo_children(): w.destroy()
        self._canvas.pack_forget()
        self._scrollbar.pack_forget()
        for w in self._sel_row.winfo_children(): w.destroy()
        self._sel_row.pack_forget()

    def _select_all(self):
        for v in self._chk_vars: v.set(True)
        self._on_check_change()

    def _select_none(self):
        for v in self._chk_vars: v.set(False)
        self._on_check_change()

    def _on_check_change(self):
        self._selected = [e for e, v in zip(self._entries, self._chk_vars) if v.get()]

    # ── Browse ─────────────────────────────────────────────────────────────────
    def _browse(self):
        d = filedialog.askdirectory(initialdir=self._dest.get())
        if d: self._dest.set(d.replace("/", os.sep))

    # ── Download ───────────────────────────────────────────────────────────────
    def _start_download(self):
        if self._downloading: return
        if not self._entries:
            messagebox.showwarning("No videos", "Fetch a URL first."); return
        if not self._selected:
            messagebox.showwarning("Nothing selected", "Select at least one video."); return
        out = resolve_path(self._dest.get().strip())
        Path(out).mkdir(parents=True, exist_ok=True)
        self._downloading = True
        self._cancel_flag = False
        self._dl_btn.set_disabled(True)
        self._cancel_btn.set_disabled(False)
        self._progress["value"] = 0
        self._log_clear()
        threading.Thread(
            target=self._download_thread,
            args=(list(self._selected), self._fmt.get(), self._quality.get(), out),
            daemon=True).start()

    def _cancel(self):
        if self._downloading:
            self._cancel_flag = True
            self._queue.put(("log", "⚠  Cancelling after current video…"))

    def _download_thread(self, entries, fmt, quality, out_dir):
        total     = len(entries)
        is_single = total == 1
        for i, entry in enumerate(entries, 1):
            if self._cancel_flag:
                self._queue.put(("log", "✘  Download cancelled.")); break
            self._queue.put(("status", f"Downloading {i}/{total}: {entry['title']}"))
            self._queue.put(("overall", int((i - 1) / total * 100)))
            outtmpl = make_outtmpl(out_dir, entry, is_single)

            def make_hook(idx=i, tot=total):
                def hook(d):
                    if d["status"] == "downloading":
                        try:    pct = float(d.get("_percent_str","0").strip().replace("%",""))
                        except: pct = 0.0
                        overall = ((idx - 1) + pct / 100) / tot * 100
                        self._queue.put(("progress", overall, pct,
                                         d.get("_speed_str", "").strip(), format_eta(d)))
                    elif d["status"] == "finished":
                        self._queue.put(("log",
                            f"✔  {os.path.basename(d.get('filename',''))}"))
                return hook

            def log_hook(msg):
                if msg and msg.strip(): self._queue.put(("log", msg.strip()))

            with yt_dlp.YoutubeDL(
                    build_ydl_opts(fmt, quality, outtmpl, make_hook(), log_hook)) as ydl:
                ydl.download([entry["url"]])
        self._queue.put(("done", out_dir))

    # ── Queue polling ──────────────────────────────────────────────────────────
    def _poll_queue(self):
        try:
            while True:
                msg  = self._queue.get_nowait()
                kind = msg[0]
                if kind == "entries":
                    self._populate_checklist(msg[1])
                elif kind == "error":
                    self._list_header.configure(text=msg[1], fg=WARNING)
                    self._fetch_btn.set_disabled(False)
                elif kind == "status":
                    self._status_lbl.configure(text=msg[1], fg=TEXT_DIM)
                elif kind == "overall":
                    self._progress["value"] = msg[1]
                elif kind == "progress":
                    _, overall, pct, speed, eta_str = msg
                    self._progress["value"] = overall
                    self._status_lbl.configure(
                        text=f"{pct:.1f}%   {speed}   ETA {eta_str}", fg=TEXT_MID)
                elif kind == "log":
                    self._log_append(msg[1])
                elif kind == "done":
                    out_dir = msg[1]
                    self._progress["value"] = 100
                    self._status_lbl.configure(text="✅  All done!", fg=SUCCESS)
                    self._downloading = False
                    self._dl_btn.set_disabled(False)
                    self._cancel_btn.set_disabled(True)
                    self._log_append(f"✅  Saved to: {out_dir}")
                    if messagebox.askyesno("Done!", "Download complete!\n\nOpen folder?"):
                        os.startfile(out_dir)
        except queue.Empty:
            pass
        self.after(80, self._poll_queue)

    def _log_append(self, text):
        self._log.configure(state="normal")
        self._log.insert("end", text + "\n")
        self._log.see("end")
        self._log.configure(state="disabled")

    def _log_clear(self):
        self._log.configure(state="normal")
        self._log.delete("1.0", "end")
        self._log.configure(state="disabled")


if __name__ == "__main__":
    app = App()
    app.mainloop()
