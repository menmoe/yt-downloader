# YT Downloader

A clean, modern desktop app for downloading YouTube videos and playlists as **MP3** or **MP4**. No terminal, no commands — just paste a URL and click download.

> **Pre-built binaries available on the [Releases page](../../releases) — no Python required.**

![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Windows-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Built with](https://img.shields.io/badge/built%20with-yt--dlp-red)

---

## Features

- 🎵 Download as **MP3** (128 / 192 / 320 kbps) or **🎬 MP4** (480p / 720p / 1080p / best)
- 📋 Paste a **playlist URL** and pick exactly which videos to download via checkboxes
- ✅ **Select all / Select none** controls for quick playlist management
- 🔢 Files are numbered by their original playlist order, even when you download a custom selection
- 📁 Flexible output folder — supports full paths, relative paths, and shorthands like `$desktop`, `$downloads`, `$documents`
- 📊 Live progress bar with speed and ETA per video
- 📝 Scrollable log panel showing each completed file
- 🎨 Dark-themed UI that feels native on both platforms
- 🔒 SSL fixed out of the box on macOS (no certificate errors)
- 🖥️ DPI-aware on Windows (sharp on 4K / high-DPI screens)
- 🎞️ MP4 output uses H.264 + AAC — plays natively in QuickTime, Windows Media Player, and VLC with no compatibility warnings

---

## Download (No Python needed)

Head to the **[Releases page](../../releases)** and download the latest version for your platform:

| Platform | File |
|----------|------|
| macOS    | `YT.Downloader.app.zip` |
| Windows  | `YT.Downloader.exe` |

**macOS:** Unzip and double-click. If macOS blocks it ("unidentified developer"), right-click → Open → Open anyway.

**Windows:** Just double-click the `.exe`. If Windows Defender shows a SmartScreen warning, click "More info" → "Run anyway". This happens because the app isn't code-signed — the app itself is safe.

---

## Build it yourself

If you'd rather build from source than trust a pre-built binary, follow the instructions below. Building requires Python — but the output app/exe does not.

### Prerequisites (both platforms)

- [Python 3.10+](https://python.org) — on Windows, check **"Add Python to PATH"** during install
- [ffmpeg](https://ffmpeg.org) — required for MP3 conversion and MP4 re-encoding

**Install ffmpeg:**
- macOS: `brew install ffmpeg`
- Windows: Download from [gyan.dev/ffmpeg/builds](https://www.gyan.dev/ffmpeg/builds/) (grab the "essentials" build), extract, and either add to PATH or place `ffmpeg.exe` + `ffprobe.exe` next to the build script

---

### macOS

```bash
# 1. Clone the repo
git clone https://github.com/YOUR_USERNAME/yt-downloader.git
cd yt-downloader/mac

# 2. Make the build script executable
chmod +x build.sh

# 3. Build
./build.sh
```

The script installs all Python dependencies automatically. When it finishes, Finder will open the `dist/` folder containing `YT Downloader.app`. Double-click it to run, or drag it to your Applications folder.

---

### Windows

```bat
:: 1. Clone the repo (or download the ZIP from GitHub)
git clone https://github.com/YOUR_USERNAME/yt-downloader.git
cd yt-downloader\windows

:: 2. Double-click build_windows.bat
::    (or run it from Command Prompt)
build_windows.bat
```

The script installs all Python dependencies automatically. When it finishes, Explorer will open the `dist\` folder containing `YT Downloader.exe`. Move it anywhere — Desktop, `C:\Apps`, a USB drive. It has no installer and leaves nothing in the registry.

---

## Path shorthands

When choosing a save location, you can type any of these instead of a full path:

| Shorthand | Resolves to |
|-----------|-------------|
| `$desktop` | `~/Desktop` |
| `$downloads` | `~/Downloads` |
| `$documents` | `~/Documents` |
| `$music` | `~/Music` |
| `$videos` | `~/Movies` (macOS) / `~/Videos` (Windows) |
| `$home` | Your home directory |
| `~` | Your home directory |

You can also use relative paths (`../my-folder`), environment variables (`%USERPROFILE%\Music` on Windows), and standard absolute paths.

---

## Repo structure

```
yt-downloader/
├── README.md
├── .gitignore
│
├── core/
│   └── downloader.py          # Shared logic — all frontends import from here
│
├── mac/
│   ├── yt_downloader_gui.py   # macOS GUI (UI only, no download logic)
│   └── build.sh               # Builds YT Downloader.app via PyInstaller
│
├── windows/
│   ├── yt_downloader_gui_windows.py  # Windows GUI (UI only, no download logic)
│   └── build_windows.bat             # Builds YT Downloader.exe via PyInstaller
│
└── cli/
    └── yt_downloader_cli.py   # Terminal frontend — interactive or flag-driven
```

All download logic — fetching playlist metadata, building yt-dlp options, path resolution, ETA calculation — lives exclusively in `core/downloader.py`. The GUI and CLI files contain only UI code. This means bug fixes and new features go in one place and every frontend gets them automatically.

---

## CLI

The CLI works on macOS, Windows, and Linux. No build step needed — just Python.

```bash
# Install dependencies once
pip install yt-dlp certifi

# Interactive mode — walks you through everything (same experience as the terminal version)
python cli/yt_downloader_cli.py

# Non-interactive — pass everything as flags (good for scripting)
python cli/yt_downloader_cli.py --url "https://youtube.com/playlist?list=..." --fmt mp3 --quality 320

# Download specific videos from a playlist (by index)
python cli/yt_downloader_cli.py --url "..." --fmt mp4 --quality 1080p --indices "1,3,5-8"

# Save to a shorthand path
python cli/yt_downloader_cli.py --url "..." --out "$music/YouTube"
```

Run `python cli/yt_downloader_cli.py --help` for the full list of flags.

---

## How it works

The app is built around a shared `core/downloader.py` module that contains all download logic — playlist fetching, yt-dlp configuration, path resolution, and progress calculation. The macOS GUI, Windows GUI, and CLI are thin frontends that only handle user interaction; they import everything from core. This means a bug fixed or feature added in `core/` is instantly available in all three frontends.

The GUIs use Python's built-in [tkinter](https://docs.python.org/3/library/tkinter.html) library (no extra UI dependencies) wrapped around [yt-dlp](https://github.com/yt-dlp/yt-dlp). [PyInstaller](https://pyinstaller.org) bundles Python, yt-dlp, certifi (SSL certificates), and ffmpeg into a single self-contained binary — no runtime dependencies needed to run the built app.

---

## Troubleshooting

**"SSL certificate verify failed" on macOS**
This is fixed automatically by the app. If you see it anyway, run `pip install --upgrade certifi` and rebuild.

**No video in the MP4, only audio**
This happens when the video was downloaded in VP9/AV1 format, which QuickTime doesn't support. The app explicitly requests H.264 + AAC and re-encodes via ffmpeg if needed. Make sure ffmpeg is installed and was bundled during the build.

**ffmpeg not found during build**
- macOS: `brew install ffmpeg`
- Windows: Place `ffmpeg.exe` and `ffprobe.exe` in the same folder as `build_windows.bat`, then re-run the script.

**Windows SmartScreen / Defender warning**
The executable is not code-signed (signing costs ~$200–$400/year). Click "More info" → "Run anyway". If you don't trust the pre-built binary, build it yourself from source — the code is fully visible in this repo.

**macOS "app is damaged" or "unidentified developer"**
Right-click the app → Open → Open. If that doesn't work, run:
```bash
xattr -cr "/Applications/YT Downloader.app"
```

**A playlist video was skipped**
Private, members-only, age-restricted, or region-blocked videos are automatically skipped. The rest of the playlist will still download.

**The ETA shows `--:--`**
This happens briefly at the very start of a download before enough data has been transferred to calculate a reliable speed. It corrects itself within a few seconds.

---

## Dependencies

| Package | Purpose |
|---------|---------|
| [yt-dlp](https://github.com/yt-dlp/yt-dlp) | YouTube extraction and downloading |
| [certifi](https://github.com/certifi/python-certifi) | Up-to-date SSL CA certificates |
| [ffmpeg](https://ffmpeg.org) | Audio extraction, video re-encoding, thumbnail embedding |
| [PyInstaller](https://pyinstaller.org) | Packaging into a standalone binary (build-time only) |
| tkinter | GUI — included with Python, no install needed |

---

## Legal disclaimer

> **This project is intended for personal, educational, and research purposes only.**

- This tool is not affiliated with, endorsed by, or connected to YouTube or Google LLC in any way.
- Downloading YouTube content may violate [YouTube's Terms of Service](https://www.youtube.com/t/terms), specifically section 5.1.K, which prohibits downloading content without explicit permission from YouTube.
- You are solely responsible for how you use this tool and for ensuring your use complies with all applicable laws and platform terms in your jurisdiction.
- Only download content you have the right to download — this includes content you own, content explicitly licensed for download (e.g. Creative Commons), or content where you have obtained permission from the rights holder.
- Downloading copyrighted music, movies, or other media without authorization may infringe on copyright law in your country.
- The author of this project accepts no liability for misuse, copyright infringement, or any damages arising from the use of this software.

**If you are a content creator and would like your content removed from someone's use of this tool, please contact that individual directly.**

---

## License

MIT License — see [LICENSE](LICENSE) for details.

You are free to use, modify, and distribute this software. The MIT license covers the code in this repository only and does not grant any rights with respect to YouTube content or third-party services.

---

<p align="center">
  Built with <a href="https://github.com/yt-dlp/yt-dlp">yt-dlp</a> · 
  Packaged with <a href="https://pyinstaller.org">PyInstaller</a>
</p>
