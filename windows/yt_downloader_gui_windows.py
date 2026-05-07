#!/usr/bin/env python3
"""
YouTube Downloader — Desktop GUI (Windows)
Requires: yt-dlp, certifi, ffmpeg
Build into a standalone .exe with: build_windows.bat
"""

import os, sys, ssl, re, threading, queue, tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
import subprocess

import certifi

# ── Fix SSL on Windows ─────────────────────────────────────────────────────────
os.environ["SSL_CERT_FILE"]      = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()
ssl._create_default_https_context = ssl.create_default_context

# ── When running as a PyInstaller bundle, add our Contents dir to PATH so
#    the bundled ffmpeg.exe is discoverable by yt-dlp ──────────────────────────
if getattr(sys, "frozen", False):
    _bundle_dir = sys._MEIPASS  # type: ignore[attr-defined]
    os.environ["PATH"] = _bundle_dir + os.pathsep + os.environ.get("PATH", "")

try:
    import yt_dlp
except ImportError:
    sys.exit("yt-dlp not found. Run: pip install yt-dlp")


# ── colours / fonts ────────────────────────────────────────────────────────────
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


# ── Windows path shorthands ────────────────────────────────────────────────────
def _win(folder_id: str) -> str:
    """Resolve a Windows known-folder path via PowerShell (most reliable)."""
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             f"[Environment]::GetFolderPath('{folder_id}')"],
            capture_output=True, text=True, timeout=5
        )
        p = result.stdout.strip()
        if p:
            return p
    except Exception:
        pass
    # Fallback to env vars
    return ""

_HOME     = str(Path.home())
_DESKTOP  = _win("Desktop")    or str(Path.home() / "Desktop")
_DOCS     = _win("MyDocuments") or str(Path.home() / "Documents")
_MUSIC    = _win("MyMusic")    or str(Path.home() / "Music")
_VIDEOS   = _win("MyVideos")   or str(Path.home() / "Videos")
_DOWNLOADS = str(Path.home() / "Downloads")  # no standard known-folder ID

PATH_SHORTHANDS = {
    "$desktop":   _DESKTOP,
    "$downloads": _DOWNLOADS,
    "$documents": _DOCS,
    "$music":     _MUSIC,
    "$videos":    _VIDEOS,
    "$home":      _HOME,
    "~":          _HOME,
}

def resolve_path(raw: str) -> str:
    """
    Expand shorthands, %ENV_VARS%, ~, and relative paths to an absolute path.
    Works with both forward and back slashes.
    """
    raw = raw.strip().replace("/", os.sep)
    low = raw.lower()
    for key, expansion in PATH_SHORTHANDS.items():
        norm_key = key.lower()
        if low == norm_key \
                or low.startswith(norm_key + os.sep) \
                or low.startswith(norm_key + "/"):
            raw = expansion + raw[len(key):]
            break
    raw = os.path.expandvars(raw)   # expand %USERPROFILE% etc.
    raw = os.path.expanduser(raw)   # expand ~
    return str(Path(raw).resolve())


# ── yt-dlp helpers ─────────────────────────────────────────────────────────────
def fetch_entries(url: str) -> list:
    opts = {
        "quiet": True, "no_warnings": True,
        "extract_flat": "in_playlist", "skip_download": True,
        "nocheckcertificate": False, "ca_cert": certifi.where(),
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
    if not info:
        return []
    if info.get("_type") != "playlist" or "entries" not in info:
        return [{"index": 1, "title": info.get("title", "Unknown"),
                 "url": info.get("webpage_url", url)}]
    result = []
    for i, e in enumerate(info.get("entries") or [], 1):
        if not e:
            continue
        vid_url = (e.get("url") or e.get("webpage_url")
                   or f"https://www.youtube.com/watch?v={e.get('id','')}")
        result.append({"index": i,
                        "title": e.get("title") or e.get("id") or f"Video {i}",
                        "url": vid_url})
    return result


def build_ydl_opts(fmt, quality, outtmpl, progress_hook, log_hook):
    common = {
        "outtmpl": outtmpl,
        "ignoreerrors": True, "quiet": True, "no_warnings": True,
        "progress_hooks": [progress_hook],
        "nocheckcertificate": False, "ca_cert": certifi.where(),
        "logger": type("L", (), {
            "debug":   lambda s, m: log_hook(m) if m and not m.startswith("[debug]") else None,
            "warning": lambda s, m: log_hook(f"⚠ {m}"),
            "error":   lambda s, m: log_hook(f"✘ {m}"),
        })(),
    }
    if fmt == "mp3":
        common.update({
            "format": "bestaudio/best",
            "postprocessors": [
                {"key": "FFmpegExtractAudio", "preferredcodec": "mp3",
                 "preferredquality": quality},
                {"key": "FFmpegMetadata"},
                {"key": "EmbedThumbnail"},
            ],
            "writethumbnail": True,
        })
    else:
        qmap = {
            "best":  ("bestvideo[vcodec^=avc1]+bestaudio[acodec^=mp4a]"
                      "/bestvideo[vcodec^=avc1]+bestaudio/bestvideo+bestaudio/best"),
            "1080p": ("bestvideo[vcodec^=avc1][height<=1080]+bestaudio[acodec^=mp4a]"
                      "/bestvideo[height<=1080]+bestaudio/best"),
            "720p":  ("bestvideo[vcodec^=avc1][height<=720]+bestaudio[acodec^=mp4a]"
                      "/bestvideo[height<=720]+bestaudio/best"),
            "480p":  ("bestvideo[vcodec^=avc1][height<=480]+bestaudio[acodec^=mp4a]"
                      "/bestvideo[height<=480]+bestaudio/best"),
        }
        common.update({
            "format": qmap.get(quality, qmap["best"]),
            "merge_output_format": "mp4",
            "postprocessors": [
                {"key": "FFmpegVideoConvertor", "preferedformat": "mp4"},
                {"key": "FFmpegMetadata"},
            ],
        })
    return common


# ── Rounded button ─────────────────────────────────────────────────────────────
class RoundedButton(tk.Canvas):
    def __init__(self, parent, text, command, bg=RED, fg=TEXT,
                 hover=RED_HOVER, radius=10, padx=20, pady=10, font=FONT, **kw):
        super().__init__(parent,
                         bg=parent["bg"] if hasattr(parent, "__getitem__") else BG,
                         highlightthickness=0, **kw)
        self._bg, self._hover, self._fg = bg, hover, fg
        self._cmd, self._radius = command, radius
        self._text, self._font = text, font
        self._padx, self._pady = padx, pady
        self._disabled = False
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
        self.create_arc(0,      0,      2*r,   2*r,   start=90,  extent=90,  fill=c, outline=c)
        self.create_arc(w-2*r,  0,      w,     2*r,   start=0,   extent=90,  fill=c, outline=c)
        self.create_arc(0,      h-2*r,  2*r,   h,     start=180, extent=90,  fill=c, outline=c)
        self.create_arc(w-2*r,  h-2*r,  w,     h,     start=270, extent=90,  fill=c, outline=c)
        self.create_rectangle(r, 0,   w-r, h,   fill=c, outline=c)
        self.create_rectangle(0, r,   w,   h-r, fill=c, outline=c)
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

    def configure_text(self, text):
        self._text = text
        self._draw()


# ── Main App ───────────────────────────────────────────────────────────────────
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("YT Downloader")
        self.configure(bg=BG)
        self.resizable(False, False)

        # Windows DPI awareness — keeps the UI sharp on high-DPI screens
        try:
            from ctypes import windll
            windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass

        # State
        self._entries     = []
        self._selected    = []
        self._downloading = False
        self._cancel_flag = False
        self._queue       = queue.Queue()
        self._fmt         = tk.StringVar(value="mp3")
        self._quality     = tk.StringVar(value="320")
        self._dest        = tk.StringVar(
            value=str(Path.home() / "Downloads" / "YT_Downloads"))

        self._build_ui()
        self.after(100, self._poll_queue)

        # Centre on screen
        self.update_idletasks()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w,  h  = self.winfo_width(), self.winfo_height()
        self.geometry(f"+{(sw-w)//2}+{(sh-h)//2}")

    # ── UI construction ────────────────────────────────────────────────────────
    def _build_ui(self):
        pad = dict(padx=28, pady=0)

        # Header
        hdr = tk.Frame(self, bg=BG)
        hdr.pack(fill="x", padx=28, pady=(28, 4))
        tk.Label(hdr, text="▶", font=("Arial", 20), bg=BG, fg=RED).pack(side="left")
        tk.Label(hdr, text="  YT Downloader", font=FONT_LG, bg=BG, fg=TEXT).pack(side="left")
        tk.Label(self, text="Download any YouTube video or playlist as MP3 or MP4.",
                 font=FONT_SM, bg=BG, fg=TEXT_DIM).pack(anchor="w", **pad)

        self._sep(pady=(14, 0))

        # URL row
        self._section_label("YouTube URL")
        url_row = tk.Frame(self, bg=BORDER, padx=1, pady=1)
        url_row.pack(fill="x", **pad, pady=(6, 0))
        inner_row = tk.Frame(url_row, bg=BG)
        inner_row.pack(fill="x")

        self._url_var = tk.StringVar()
        url_entry = tk.Entry(inner_row, textvariable=self._url_var, font=FONT,
                             bg=SURFACE2, fg=TEXT, insertbackground=TEXT,
                             relief="flat", bd=0)
        url_entry.pack(side="left", fill="x", expand=True, ipady=10, ipadx=12)
        url_entry.bind("<Return>", lambda _: self._fetch())

        self._fetch_btn = RoundedButton(inner_row, "  Fetch  ", self._fetch,
                                        padx=16, pady=10, font=FONT,
                                        width=90, height=38)
        self._fetch_btn.pack(side="left", padx=(8, 0))

        self._sep(pady=(16, 0))

        # Video list
        self._section_label("Videos")
        list_frame = tk.Frame(self, bg=SURFACE)
        list_frame.pack(fill="x", **pad, pady=(6, 0))

        self._list_header = tk.Label(
            list_frame,
            text="Paste a URL above and click Fetch to load videos.",
            font=FONT_SM, bg=SURFACE, fg=TEXT_DIM, anchor="w", pady=10, padx=12)
        self._list_header.pack(fill="x")

        self._check_outer = tk.Frame(list_frame, bg=SURFACE)
        self._check_outer.pack(fill="x")

        self._canvas     = tk.Canvas(self._check_outer, bg=SURFACE,
                                      highlightthickness=0, height=0)
        self._scrollbar  = ttk.Scrollbar(self._check_outer, orient="vertical",
                                          command=self._canvas.yview)
        self._check_inner = tk.Frame(self._canvas, bg=SURFACE)
        self._canvas.create_window((0, 0), window=self._check_inner, anchor="nw")
        self._canvas.configure(yscrollcommand=self._scrollbar.set)
        self._check_inner.bind("<Configure>", self._on_list_configure)

        self._sel_row  = tk.Frame(list_frame, bg=SURFACE)
        self._chk_vars = []

        self._sep(pady=(16, 0))

        # Format & Quality
        fq_row = tk.Frame(self, bg=BG)
        fq_row.pack(fill="x", **pad, pady=(0, 0))

        fmt_col = tk.Frame(fq_row, bg=BG)
        fmt_col.pack(side="left", fill="x", expand=True)
        self._section_label("Format", parent=fmt_col)
        fmt_inner = tk.Frame(fmt_col, bg=BG)
        fmt_inner.pack(fill="x", pady=(6, 0))
        for val, label in [("mp3", "🎵  MP3  (audio only)"),
                            ("mp4", "🎬  MP4  (video + audio)")]:
            self._radio(fmt_inner, label, self._fmt, val, self._on_fmt_change)

        self._q_col = tk.Frame(fq_row, bg=BG)
        self._q_col.pack(side="left", fill="x", expand=True, padx=(28, 0))
        self._build_quality_panel()

        self._sep(pady=(16, 0))

        # Destination
        self._section_label("Save to")
        tk.Label(self,
                 text="Tip: use $desktop  $downloads  $documents  $music  $videos  $home  "
                      "or %USERPROFILE%\\folder",
                 font=FONT_SM, bg=BG, fg=TEXT_DIM).pack(anchor="w", **pad)

        dest_row = tk.Frame(self, bg=BORDER, padx=1, pady=1)
        dest_row.pack(fill="x", **pad, pady=(4, 0))
        dest_inner = tk.Frame(dest_row, bg=BG)
        dest_inner.pack(fill="x")

        dest_entry = tk.Entry(dest_inner, textvariable=self._dest, font=FONT_SM,
                              bg=SURFACE2, fg=TEXT_MID, insertbackground=TEXT,
                              relief="flat", bd=0)
        dest_entry.pack(side="left", fill="x", expand=True, ipady=8, ipadx=10)

        browse_btn = RoundedButton(dest_inner, " Browse ", self._browse,
                                   bg=SURFACE2, hover="#333333",
                                   padx=12, pady=8, font=FONT_SM,
                                   width=80, height=34)
        browse_btn.pack(side="left", padx=(8, 0))

        self._sep(pady=(20, 0))

        # Progress
        prog_frame = tk.Frame(self, bg=BG)
        prog_frame.pack(fill="x", **pad)

        self._status_lbl = tk.Label(prog_frame, text="", font=FONT_SM,
                                     bg=BG, fg=TEXT_DIM, anchor="w")
        self._status_lbl.pack(fill="x")

        self._progress = ttk.Progressbar(prog_frame, mode="determinate", maximum=100)
        self._progress.pack(fill="x", pady=(6, 0))
        self._style_progressbar()

        # Log
        log_outer = tk.Frame(self, bg=SURFACE)
        log_outer.pack(fill="x", **pad, pady=(12, 0))
        self._log = tk.Text(log_outer, height=6, font=FONT_MONO,
                             bg=SURFACE, fg=TEXT_DIM, insertbackground=TEXT,
                             relief="flat", bd=0, padx=10, pady=8,
                             state="disabled", wrap="word")
        log_sb = ttk.Scrollbar(log_outer, command=self._log.yview)
        self._log.configure(yscrollcommand=log_sb.set)
        self._log.pack(side="left", fill="both", expand=True)
        log_sb.pack(side="right", fill="y")

        # Action buttons
        btn_row = tk.Frame(self, bg=BG)
        btn_row.pack(fill="x", **pad, pady=(20, 28))

        self._dl_btn = RoundedButton(btn_row, "  ⬇  Download  ", self._start_download,
                                     padx=24, pady=12, font=FONT,
                                     width=200, height=46)
        self._dl_btn.pack(side="right")

        self._cancel_btn = RoundedButton(btn_row, "  Cancel  ", self._cancel,
                                          bg=SURFACE2, hover="#333333",
                                          padx=16, pady=12, font=FONT,
                                          width=120, height=46)
        self._cancel_btn.pack(side="right", padx=(0, 12))
        self._cancel_btn.set_disabled(True)

        self.geometry("700x840")

    # ── Helpers ────────────────────────────────────────────────────────────────
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
        tk.Radiobutton(row, text=label, variable=var, value=value,
                       font=FONT, bg=BG, fg=TEXT_MID,
                       selectcolor=BG, activebackground=BG,
                       activeforeground=TEXT, command=cmd).pack(side="left")

    def _build_quality_panel(self):
        for w in self._q_col.winfo_children():
            w.destroy()
        self._section_label("Quality", parent=self._q_col)
        q_inner = tk.Frame(self._q_col, bg=BG)
        q_inner.pack(fill="x", pady=(6, 0))
        if self._fmt.get() == "mp3":
            opts    = [("320", "320 kbps (best)"), ("192", "192 kbps"),
                       ("128", "128 kbps (smaller)")]
            default = "320"
        else:
            opts    = [("best", "Best available"), ("1080p", "1080p"),
                       ("720p", "720p"), ("480p", "480p")]
            default = "best"
        self._quality.set(default)
        for val, label in opts:
            self._radio(q_inner, label, self._quality, val)

    def _on_fmt_change(self):
        self._build_quality_panel()

    def _style_progressbar(self):
        s = ttk.Style()
        s.theme_use("default")
        s.configure("TProgressbar", troughcolor=SURFACE2, background=RED,
                    bordercolor=BG, lightcolor=RED, darkcolor=RED_DARK, thickness=6)

    def _on_list_configure(self, _=None):
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    # ── Fetch ──────────────────────────────────────────────────────────────────
    def _fetch(self):
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
            entries = fetch_entries(url)
            self._queue.put(("entries", entries))
        except Exception as e:
            self._queue.put(("error", f"Fetch failed: {e}"))

    def _populate_checklist(self, entries):
        self._entries  = entries
        self._selected = list(entries)
        self._chk_vars = []
        self._clear_checklist()

        n = len(entries)
        self._list_header.configure(
            text=f"{'1 video' if n == 1 else f'{n} videos'} found — select which to download:",
            fg=TEXT_MID)

        if n > 1:
            for w in self._sel_row.winfo_children():
                w.destroy()
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

        visible = min(n, 8)
        row_h   = 30
        if n > 1:
            self._canvas.configure(height=visible * row_h)
            self._canvas.pack(side="left", fill="both", expand=True)
            if n > visible:
                self._scrollbar.pack(side="right", fill="y")

        for e in entries:
            var = tk.BooleanVar(value=True)
            self._chk_vars.append(var)
            row = tk.Frame(self._check_inner, bg=SURFACE)
            row.pack(fill="x")
            tk.Checkbutton(
                row,
                text=f"  {e['index']:02d}  {e['title']}",
                variable=var, font=FONT_SM,
                bg=SURFACE, fg=TEXT_MID, selectcolor=SURFACE2,
                activebackground=SURFACE, activeforeground=TEXT,
                anchor="w", command=self._on_check_change
            ).pack(fill="x", padx=8, ipady=4)

        self._fetch_btn.set_disabled(False)

    def _clear_checklist(self):
        for w in self._check_inner.winfo_children():
            w.destroy()
        self._canvas.pack_forget()
        self._scrollbar.pack_forget()
        for w in self._sel_row.winfo_children():
            w.destroy()
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
        if d:
            self._dest.set(d.replace("/", os.sep))

    # ── Download ───────────────────────────────────────────────────────────────
    def _start_download(self):
        if self._downloading:
            return
        if not self._entries:
            messagebox.showwarning("No videos", "Fetch a URL first.")
            return
        if not self._selected:
            messagebox.showwarning("Nothing selected", "Select at least one video.")
            return

        out = resolve_path(self._dest.get().strip())
        Path(out).mkdir(parents=True, exist_ok=True)

        self._downloading  = True
        self._cancel_flag  = False
        self._dl_btn.set_disabled(True)
        self._cancel_btn.set_disabled(False)
        self._progress["value"] = 0
        self._log_clear()

        threading.Thread(
            target=self._download_thread,
            args=(list(self._selected), self._fmt.get(), self._quality.get(), out),
            daemon=True
        ).start()

    def _cancel(self):
        if self._downloading:
            self._cancel_flag = True
            self._queue.put(("log", "⚠  Cancelling after current video…"))

    def _download_thread(self, entries, fmt, quality, out_dir):
        total     = len(entries)
        is_single = total == 1

        for i, entry in enumerate(entries, 1):
            if self._cancel_flag:
                self._queue.put(("log", "✘  Download cancelled."))
                break

            self._queue.put(("status", f"Downloading {i}/{total}: {entry['title']}"))
            self._queue.put(("overall", int((i - 1) / total * 100)))

            if is_single:
                outtmpl = os.path.join(out_dir, "%(title)s.%(ext)s")
            else:
                outtmpl = os.path.join(out_dir, f"{entry['index']:02d} - %(title)s.%(ext)s")

            def make_hook(idx=i, tot=total):
                def hook(d):
                    if d["status"] == "downloading":
                        pct_s = d.get("_percent_str", "0").strip().replace("%", "")
                        try:    pct = float(pct_s)
                        except: pct = 0.0
                        overall = ((idx - 1) + pct / 100) / tot * 100
                        self._queue.put(("progress", overall, pct,
                                         d.get("_speed_str", "").strip(),
                                         d.get("eta")))
                    elif d["status"] == "finished":
                        fname = os.path.basename(d.get("filename", ""))
                        self._queue.put(("log", f"✔  {fname}"))
                return hook

            def log_hook(msg):
                if msg and msg.strip():
                    self._queue.put(("log", msg.strip()))

            opts = build_ydl_opts(fmt, quality, outtmpl, make_hook(), log_hook)
            with yt_dlp.YoutubeDL(opts) as ydl:
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
                    _, overall, pct, speed, eta_sec = msg
                    self._progress["value"] = overall
                    eta_str = "--:--"
                    if eta_sec is not None:
                        try:
                            es = int(eta_sec)
                            if es > 0:
                                m, s = divmod(es, 60)
                                eta_str = f"{m:02d}:{s:02d}"
                        except Exception:
                            pass
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
                        os.startfile(out_dir)   # Windows Explorer

        except queue.Empty:
            pass
        self.after(80, self._poll_queue)

    # ── Log helpers ────────────────────────────────────────────────────────────
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
