"""
core/downloader.py
──────────────────
Shared logic for all frontends (GUI mac, GUI windows, CLI).
NO UI code lives here — only download mechanics.

All frontends import from this module. Bug fixes and new features
go here once and are automatically available everywhere.
"""

import os
import ssl
import sys
from pathlib import Path

import certifi

# ── SSL fix (macOS + Windows) ──────────────────────────────────────────────────
os.environ["SSL_CERT_FILE"]      = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()
ssl._create_default_https_context = ssl.create_default_context

# ── When bundled by PyInstaller, put the bundle dir on PATH so ffmpeg is found ─
if getattr(sys, "frozen", False):
    _bundle_dir = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    os.environ["PATH"] = _bundle_dir + os.pathsep + os.environ.get("PATH", "")

try:
    import yt_dlp
except ImportError:
    sys.exit("yt-dlp not found. Run: pip install yt-dlp")


# ── Path shorthands ────────────────────────────────────────────────────────────

def _win_known_folder(folder_id: str) -> str:
    """Resolve a Windows known folder via PowerShell. Returns '' on failure."""
    try:
        import subprocess
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             f"[Environment]::GetFolderPath('{folder_id}')"],
            capture_output=True, text=True, timeout=5,
        )
        return r.stdout.strip()
    except Exception:
        return ""


def _build_shorthands() -> dict:
    home = str(Path.home())
    if sys.platform == "darwin":
        return {
            "$desktop":   str(Path.home() / "Desktop"),
            "$downloads": str(Path.home() / "Downloads"),
            "$documents": str(Path.home() / "Documents"),
            "$music":     str(Path.home() / "Music"),
            "$videos":    str(Path.home() / "Movies"),
            "$home":      home,
            "~":          home,
        }
    else:  # Windows
        return {
            "$desktop":   _win_known_folder("Desktop")    or str(Path.home() / "Desktop"),
            "$downloads": str(Path.home() / "Downloads"),
            "$documents": _win_known_folder("MyDocuments") or str(Path.home() / "Documents"),
            "$music":     _win_known_folder("MyMusic")    or str(Path.home() / "Music"),
            "$videos":    _win_known_folder("MyVideos")   or str(Path.home() / "Videos"),
            "$home":      home,
            "~":          home,
        }


SHORTHANDS = _build_shorthands()


def resolve_path(raw: str) -> str:
    """
    Turn any user-supplied path into an absolute path.
    Handles shorthands ($desktop etc.), ~, %ENV_VARS%, relative paths,
    and both forward and back slashes.
    """
    raw = raw.strip().replace("/", os.sep)
    low = raw.lower()
    for key, expansion in SHORTHANDS.items():
        if low == key or low.startswith(key + os.sep):
            raw = expansion + raw[len(key):]
            break
    raw = os.path.expandvars(raw)
    raw = os.path.expanduser(raw)
    return str(Path(raw).resolve())


# ── Format / quality constants (used by all frontends for menus) ───────────────

MP3_QUALITIES = [
    ("320", "320 kbps (best)"),
    ("192", "192 kbps"),
    ("128", "128 kbps (smaller)"),
]

MP4_QUALITIES = [
    ("best",  "Best available"),
    ("1080p", "1080p"),
    ("720p",  "720p"),
    ("480p",  "480p"),
]

DEFAULT_MP3_QUALITY = "320"
DEFAULT_MP4_QUALITY = "best"


# ── Playlist fetching ──────────────────────────────────────────────────────────

def fetch_entries(url: str) -> list:
    """
    Fetch metadata for a URL without downloading anything.

    Returns a list of dicts:
        [{"index": int, "title": str, "url": str}, ...]

    Single videos return a one-item list with index=1.
    """
    opts = {
        "quiet":              True,
        "no_warnings":        True,
        "extract_flat":       "in_playlist",
        "skip_download":      True,
        "nocheckcertificate": False,
        "ca_cert":            certifi.where(),
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)

    if not info:
        return []

    # Single video — no playlist wrapper
    if info.get("_type") != "playlist" or "entries" not in info:
        return [{
            "index": 1,
            "title": info.get("title") or info.get("id") or "Unknown",
            "url":   info.get("webpage_url", url),
        }]

    result = []
    for i, e in enumerate(info.get("entries") or [], 1):
        if not e:
            continue
        vid_url = (
            e.get("url")
            or e.get("webpage_url")
            or f"https://www.youtube.com/watch?v={e.get('id', '')}"
        )
        result.append({
            "index": i,
            "title": e.get("title") or e.get("id") or f"Video {i}",
            "url":   vid_url,
        })
    return result


# ── yt-dlp options builder ─────────────────────────────────────────────────────

def build_ydl_opts(fmt: str, quality: str, outtmpl: str,
                   progress_hook, log_hook) -> dict:
    """
    Build a yt_dlp options dict.

    Args:
        fmt:           "mp3" or "mp4"
        quality:       e.g. "320" / "192" / "128" for mp3,
                            "best" / "1080p" / "720p" / "480p" for mp4
        outtmpl:       full output template string (caller builds this)
        progress_hook: callable(d) — yt-dlp progress hook
        log_hook:      callable(msg: str) — receives log lines
    """
    common = {
        "outtmpl":            outtmpl,
        "ignoreerrors":       True,
        "quiet":              True,
        "no_warnings":        True,
        "progress_hooks":     [progress_hook],
        "nocheckcertificate": False,
        "ca_cert":            certifi.where(),
        "logger": type("_Logger", (), {
            "debug":   lambda s, m: log_hook(m) if m and not m.startswith("[debug]") else None,
            "warning": lambda s, m: log_hook(f"⚠ {m}"),
            "error":   lambda s, m: log_hook(f"✘ {m}"),
        })(),
    }

    if fmt == "mp3":
        common.update({
            "format": "bestaudio/best",
            "postprocessors": [
                {
                    "key":              "FFmpegExtractAudio",
                    "preferredcodec":   "mp3",
                    "preferredquality": quality,
                },
                {"key": "FFmpegMetadata"},
                {"key": "EmbedThumbnail"},
            ],
            "writethumbnail": True,
        })
    else:  # mp4 — force H.264 + AAC for QuickTime / Windows Media Player compat
        qmap = {
            "best": (
                "bestvideo[vcodec^=avc1]+bestaudio[acodec^=mp4a]"
                "/bestvideo[vcodec^=avc1]+bestaudio/bestvideo+bestaudio/best"
            ),
            "1080p": (
                "bestvideo[vcodec^=avc1][height<=1080]+bestaudio[acodec^=mp4a]"
                "/bestvideo[height<=1080]+bestaudio/best"
            ),
            "720p": (
                "bestvideo[vcodec^=avc1][height<=720]+bestaudio[acodec^=mp4a]"
                "/bestvideo[height<=720]+bestaudio/best"
            ),
            "480p": (
                "bestvideo[vcodec^=avc1][height<=480]+bestaudio[acodec^=mp4a]"
                "/bestvideo[height<=480]+bestaudio/best"
            ),
        }
        common.update({
            "format":              qmap.get(quality, qmap["best"]),
            "merge_output_format": "mp4",
            "postprocessors": [
                {"key": "FFmpegVideoConvertor", "preferedformat": "mp4"},
                {"key": "FFmpegMetadata"},
            ],
        })

    return common


# ── Output template builder ────────────────────────────────────────────────────

def make_outtmpl(out_dir: str, entry: dict, is_single: bool) -> str:
    """
    Build the yt-dlp output template for a single entry.
    Single videos get no number prefix; playlist entries keep their original index.
    """
    if is_single:
        return os.path.join(out_dir, "%(title)s.%(ext)s")
    return os.path.join(out_dir, f"{entry['index']:02d} - %(title)s.%(ext)s")


# ── ETA formatter (shared across all frontends) ────────────────────────────────

def format_eta(d: dict) -> str:
    """
    Extract a human-readable ETA string from a yt-dlp progress dict.
    Falls back to manual calculation from bytes/speed, then '--:--'.
    """
    eta_sec = d.get("eta")
    if eta_sec is not None:
        try:
            es = int(eta_sec)
            if es > 0:
                m, s = divmod(es, 60)
                return f"{m:02d}:{s:02d}"
        except (TypeError, ValueError):
            pass

    # Manual estimate from bytes
    total      = d.get("total_bytes") or d.get("total_bytes_estimate", 0)
    downloaded = d.get("downloaded_bytes", 0)
    speed      = d.get("speed") or 0
    if total and downloaded and speed and downloaded < total:
        remaining = (total - downloaded) / speed
        m, s = divmod(int(remaining), 60)
        return f"{m:02d}:{s:02d}"

    return "--:--"
