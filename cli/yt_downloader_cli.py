#!/usr/bin/env python3
"""
cli/yt_downloader_cli.py
────────────────────────
Terminal frontend for the YouTube Downloader.
All download logic lives in core/downloader.py — do not add logic here.

Usage:
    python yt_downloader_cli.py
    python yt_downloader_cli.py --url <URL> --fmt mp3 --quality 320 --out ~/Downloads

Requirements:
    pip install yt-dlp certifi
    ffmpeg installed and on PATH
"""

import argparse
import os
import sys
from pathlib import Path

# ── Locate core/ regardless of where this script is called from ───────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
for _p in (_HERE, _ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from core.downloader import (   # noqa: E402
    fetch_entries, build_ydl_opts, make_outtmpl, resolve_path,
    format_eta, MP3_QUALITIES, MP4_QUALITIES,
    DEFAULT_MP3_QUALITY, DEFAULT_MP4_QUALITY, SHORTHANDS,
)
import yt_dlp  # noqa: F401


# ── Helpers ────────────────────────────────────────────────────────────────────

def _ask(prompt: str, valid: list = None, default: str = None) -> str:
    """Prompt until a valid answer is given."""
    while True:
        suffix = f" [{default}]" if default is not None else ""
        answer = input(f"{prompt}{suffix}: ").strip()
        if not answer and default is not None:
            return default
        if valid is None or answer.lower() in [v.lower() for v in valid]:
            return answer.lower() if valid else answer
        print(f"   ⚠  Please enter one of: {', '.join(valid)}")


def _banner():
    print()
    print("═" * 56)
    print("      🎵  YouTube Downloader  ·  CLI  🎬")
    print("═" * 56)
    print()


def _progress_hook(d: dict):
    """Print a compact progress line, overwriting in-place."""
    if d["status"] == "downloading":
        title = (d.get("info_dict") or {}).get("title", "…")
        pct   = d.get("_percent_str", "?%").strip()
        speed = d.get("_speed_str",   "N/A").strip()
        eta   = format_eta(d)
        print(f"\r  ⬇  {title[:34]:<34}  {pct:>6}  {speed:>12}  ETA {eta}",
              end="", flush=True)
    elif d["status"] == "finished":
        print()
        print(f"  ✔  Processing: {os.path.basename(d.get('filename', ''))}")
    elif d["status"] == "error":
        print(f"\n  ✘  Error: {d.get('filename', 'unknown')}")


def _log_hook(msg: str):
    if msg and msg.strip() and not msg.startswith("[debug]"):
        print(f"     {msg.strip()}")


def _select_videos_interactive(entries: list) -> list:
    """Let the user pick which playlist entries to download."""
    if len(entries) <= 1:
        return entries

    print(f"\n📋  Found {len(entries)} videos:\n")
    for e in entries:
        print(f"    {e['index']:>3})  {e['title']}")

    print()
    print("    Selection options:")
    print("      all          → everything (default)")
    print("      1,3,5        → comma-separated")
    print("      2-8          → inclusive range")
    print("      1-3,7,10-12  → mix of both")

    while True:
        raw = input("\n    Your selection [all]: ").strip().lower()
        if not raw or raw == "all":
            return entries

        selected = set()
        try:
            for part in raw.split(","):
                part = part.strip()
                if "-" in part:
                    a, b = part.split("-", 1)
                    selected.update(range(int(a), int(b) + 1))
                else:
                    selected.add(int(part))
        except ValueError:
            print("   ⚠  Couldn't parse that. Try: 1,3,5-8")
            continue

        filtered = [e for e in entries if e["index"] in selected]
        if not filtered:
            print("   ⚠  No matching videos. Try again.")
            continue

        print(f"\n   ✔  Selected {len(filtered)} video(s):")
        for e in filtered:
            print(f"       {e['index']:>3})  {e['title']}")

        if _ask("\n   Proceed? (y/n)", valid=["y", "n"], default="y") == "y":
            return filtered


# ── Interactive mode ───────────────────────────────────────────────────────────

def run_interactive():
    _banner()

    # URL
    import re
    while True:
        url = input("🔗  YouTube URL:\n    ").strip()
        if re.search(r"youtube\.com|youtu\.be", url):
            break
        print("   ⚠  That doesn't look like a YouTube URL.\n")

    # Fetch
    print("\n⏳  Fetching info…")
    entries = fetch_entries(url)
    if not entries:
        print("❌  Could not fetch any videos. Check the URL and try again.")
        sys.exit(1)

    # Selection
    entries = _select_videos_interactive(entries)
    print()

    # Format
    print("📦  Format:")
    print("    1) MP3  – audio only")
    print("    2) MP4  – video + audio")
    fmt = "mp3" if _ask("    Enter 1 or 2", valid=["1", "2"], default="1") == "1" else "mp4"
    print()

    # Quality
    if fmt == "mp3":
        print("🎚  Bitrate:")
        for i, (val, lbl) in enumerate(MP3_QUALITIES, 1):
            print(f"    {i}) {lbl}")
        choice  = _ask(f"    Enter 1-{len(MP3_QUALITIES)}",
                       valid=[str(i) for i in range(1, len(MP3_QUALITIES)+1)], default="1")
        quality = MP3_QUALITIES[int(choice) - 1][0]
    else:
        print("🎚  Quality:")
        for i, (val, lbl) in enumerate(MP4_QUALITIES, 1):
            print(f"    {i}) {lbl}")
        choice  = _ask(f"    Enter 1-{len(MP4_QUALITIES)}",
                       valid=[str(i) for i in range(1, len(MP4_QUALITIES)+1)], default="1")
        quality = MP4_QUALITIES[int(choice) - 1][0]
    print()

    # Destination
    default_dir = str(Path.home() / "Downloads" / "YT_Downloads")
    shorthand_hint = "  ".join(SHORTHANDS.keys())
    print(f"📁  Output folder")
    print(f"    Shorthands: {shorthand_hint}")
    raw_dir    = input(f"    [{default_dir}]:\n    ").strip()
    output_dir = resolve_path(raw_dir) if raw_dir else default_dir
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    print()

    # Confirm
    print("─" * 56)
    print(f"  Videos  : {len(entries)}")
    print(f"  Format  : {fmt.upper()}  |  Quality: {quality}")
    print(f"  Folder  : {output_dir}")
    print("─" * 56)
    if _ask("\n▶  Start? (y/n)", valid=["y", "n"], default="y") != "y":
        print("\n👋  Cancelled.\n")
        sys.exit(0)

    run_download(entries, fmt, quality, output_dir)


# ── Download runner (used by both interactive and --flag modes) ────────────────

def run_download(entries: list, fmt: str, quality: str, output_dir: str):
    total     = len(entries)
    is_single = total == 1

    print(f"\n📂  Saving to: {output_dir}\n")
    print("─" * 56)

    for i, entry in enumerate(entries, 1):
        if not is_single:
            print(f"\n  [{i}/{total}]  {entry['title']}")

        outtmpl = make_outtmpl(output_dir, entry, is_single)
        opts    = build_ydl_opts(fmt, quality, outtmpl, _progress_hook, _log_hook)

        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([entry["url"]])

    print("─" * 56)
    print(f"\n✅  Done! Files saved to: {output_dir}\n")


# ── Argument-mode (non-interactive / scripting) ────────────────────────────────

def run_with_args(args):
    import re
    if not re.search(r"youtube\.com|youtu\.be", args.url):
        print("❌  Invalid YouTube URL.")
        sys.exit(1)

    fmt     = args.fmt.lower()
    quality = args.quality
    out_dir = resolve_path(args.out) if args.out else str(Path.home() / "Downloads" / "YT_Downloads")
    Path(out_dir).mkdir(parents=True, exist_ok=True)

    print(f"⏳  Fetching info for: {args.url}")
    entries = fetch_entries(args.url)
    if not entries:
        print("❌  No videos found.")
        sys.exit(1)

    # Apply --indices filter if provided
    if args.indices:
        selected = set()
        for part in args.indices.split(","):
            part = part.strip()
            if "-" in part:
                a, b = part.split("-", 1)
                selected.update(range(int(a), int(b) + 1))
            else:
                selected.add(int(part))
        entries = [e for e in entries if e["index"] in selected]
        if not entries:
            print("❌  No videos matched the provided indices.")
            sys.exit(1)

    print(f"📥  {len(entries)} video(s) → {fmt.upper()} @ {quality}  →  {out_dir}\n")
    run_download(entries, fmt, quality, out_dir)


# ── Entry point ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        prog="yt-downloader",
        description="Download YouTube videos or playlists as MP3 or MP4.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Interactive mode (no flags):
    python yt_downloader_cli.py

  Download a playlist as MP3:
    python yt_downloader_cli.py --url "https://youtube.com/playlist?list=..." --fmt mp3 --quality 320

  Download specific videos from a playlist:
    python yt_downloader_cli.py --url "..." --fmt mp4 --quality 1080p --indices "1,3,5-8"

  Save to a shorthand path:
    python yt_downloader_cli.py --url "..." --out "$music/YouTube"

Shorthands: $desktop  $downloads  $documents  $music  $videos  $home
        """,
    )
    parser.add_argument("--url",      help="YouTube video or playlist URL")
    parser.add_argument("--fmt",      choices=["mp3", "mp4"], default="mp3",
                        help="Output format (default: mp3)")
    parser.add_argument("--quality",  default=None,
                        help="Quality: 320/192/128 for MP3, best/1080p/720p/480p for MP4")
    parser.add_argument("--out",      help="Output folder (supports shorthands)")
    parser.add_argument("--indices",  help='Video selection, e.g. "1,3,5-8" (default: all)')

    args = parser.parse_args()

    # No --url → drop into interactive mode
    if not args.url:
        try:
            run_interactive()
        except KeyboardInterrupt:
            print("\n\n👋  Interrupted.\n")
            sys.exit(0)
        return

    # Set quality defaults if not provided
    if args.quality is None:
        args.quality = DEFAULT_MP3_QUALITY if args.fmt == "mp3" else DEFAULT_MP4_QUALITY

    try:
        run_with_args(args)
    except KeyboardInterrupt:
        print("\n\n👋  Interrupted.\n")
        sys.exit(0)


if __name__ == "__main__":
    main()
