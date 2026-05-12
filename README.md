# YT Downloader

A desktop app (and self-hosted web interface) for downloading YouTube videos and playlists as MP3 or MP4. No terminal required. Paste a URL, pick your settings, and download.

> **Pre-built binaries are available on the [Releases page](../../releases). No Python required.**

![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Windows-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Built with](https://img.shields.io/badge/built%20with-yt--dlp-red)

---

## Features

* Download as **MP3** (128 / 192 / 320 kbps) or **MP4** (480p / 720p / 1080p / best)
* Paste a playlist URL and choose exactly which videos to download with checkboxes
* Select all / Select none controls for quick playlist management
* Files stay numbered according to the original playlist order, even when downloading only part of a playlist
* Flexible output folder support with full paths, relative paths, and shorthands like `$desktop`, `$downloads`, and `$documents`
* Live progress bar with speed and ETA per video
* Scrollable log panel showing completed downloads
* Dark-themed UI that feels native on both macOS and Windows
* SSL works out of the box on macOS with no certificate issues
* DPI-aware on Windows for sharp rendering on high-DPI displays
* MP4 output uses H.264 + AAC for native playback in QuickTime, Windows Media Player, and VLC

---

## Download (No Python needed)

Go to the **[Releases page](../../releases)** and download the latest version for your platform:

| Platform | File                    |
| -------- | ----------------------- |
| macOS    | `YT.Downloader.app.zip` |
| Windows  | `YT.Downloader.exe`     |

**macOS:** Unzip and double-click. If macOS blocks it as an unidentified developer, right-click the app, choose **Open**, then click **Open** again.

**Windows:** Double-click the `.exe`. If Windows Defender shows a SmartScreen warning, click **More info** → **Run anyway**. This happens because the app is not code-signed.

---

## Build it yourself

If you prefer building from source instead of using a pre-built binary, follow the instructions below. Building requires Python, but the final app/exe does not.

### Prerequisites (both platforms)

* [Python 3.10+](https://python.org) — on Windows, enable **"Add Python to PATH"** during installation
* [ffmpeg](https://ffmpeg.org) — required for MP3 conversion and MP4 re-encoding

**Install ffmpeg:**

* macOS: `brew install ffmpeg`
* Windows: Download from [gyan.dev/ffmpeg/builds](https://www.gyan.dev/ffmpeg/builds/) (use the "essentials" build), extract it, and either add it to PATH or place `ffmpeg.exe` and `ffprobe.exe` next to the build script

---

### macOS

```bash
# 1. Clone the repo
git clone https://github.com/moishy-r/yt-downloader.git
cd yt-downloader/mac

# 2. Make the build script executable
chmod +x build.sh

# 3. Build
./build.sh
```

The script installs all Python dependencies automatically. When it finishes, Finder opens the `dist/` folder containing `YT Downloader.app`.

---

### Windows

```bat
:: 1. Clone the repo (or download the ZIP from GitHub)
git clone https://github.com/moishy-r/yt-downloader.git
cd yt-downloader\windows

:: 2. Double-click build_windows.bat
::    (or run it from Command Prompt)
build_windows.bat
```

The script installs all Python dependencies automatically. When it finishes, Explorer opens the `dist\` folder containing `YT Downloader.exe`. You can move it anywhere — Desktop, `C:\Apps`, or a USB drive. It has no installer and does not modify the registry.

---

## CLI

The CLI works on macOS, Windows, and Linux. No build step needed.

```bash
pip install yt-dlp certifi
```

**Interactive mode** (recommended if you're using it manually):
```bash
python cli/yt_downloader_cli.py
```

**Non-interactive**, for scripting:
```bash
# Download a playlist as MP3
python cli/yt_downloader_cli.py --url "https://youtube.com/playlist?list=..." --fmt mp3 --quality 320

# Download specific videos by index
python cli/yt_downloader_cli.py --url "..." --fmt mp4 --quality 1080p --indices "1,3,5-8"

# Use a path shorthand for the output folder
python cli/yt_downloader_cli.py --url "..." --out "$music/YouTube"
```

Run `python cli/yt_downloader_cli.py --help` for all available flags.

---

## Web interface

A browser-based option for people who prefer not to install an app. Runs a small local server on your machine -- nothing is hosted externally, no data leaves your computer.

```bash
# Run from the repo root
pip install -r web/requirements.txt
python web/app.py
```

Then open [http://localhost:5000](http://localhost:5000). Same features as the desktop app: fetch a URL, pick videos from a checkbox list, choose format and quality, and download. Completed files are served directly to your browser.

See [web/README.md](web/README.md) for more detail.

---

## Path shorthands

Instead of typing out a full path for the output folder, you can use these anywhere the app or CLI asks for a location:

| Shorthand | Resolves to |
|-----------|-------------|
| `$desktop` | `~/Desktop` |
| `$downloads` | `~/Downloads` |
| `$documents` | `~/Documents` |
| `$music` | `~/Music` |
| `$videos` | `~/Movies` (macOS) / `~/Videos` (Windows) |
| `$home` | Your home directory |
| `~` | Your home directory |

Relative paths, `%USERPROFILE%` style env vars on Windows, and standard absolute paths all work too.

---

## How it works

All download logic lives in `core/downloader.py` -- playlist fetching, yt-dlp configuration, path resolution, progress calculation. The macOS GUI, Windows GUI, CLI, and web server are all thin frontends that import from core. Fixes and new features go in one place and every frontend picks them up automatically.

The desktop GUIs are built with Python's built-in [tkinter](https://docs.python.org/3/library/tkinter.html) library and [yt-dlp](https://github.com/yt-dlp/yt-dlp). [PyInstaller](https://pyinstaller.org) bundles everything -- Python, yt-dlp, certifi, and ffmpeg -- into a single binary with no external dependencies. The web interface uses [Flask](https://flask.palletsprojects.com/) and streams progress to the browser in real time via Server-Sent Events.

### Repo structure

```
yt-downloader/
├── core/
│   └── downloader.py                 # All download logic lives here
├── mac/
│   ├── yt_downloader_gui.py          # macOS GUI (UI only)
│   └── build.sh                      # Builds YT Downloader.app
├── windows/
│   ├── yt_downloader_gui_windows.py  # Windows GUI (UI only)
│   └── build_windows.bat             # Builds YT Downloader.exe
├── cli/
│   └── yt_downloader_cli.py          # Terminal frontend
├── web/
│   ├── app.py                        # Flask server
│   ├── requirements.txt
│   ├── README.md
│   └── templates/
│       └── index.html                # Browser UI
├── .gitignore
└── README.md
```

---

## Troubleshooting

### "SSL certificate verify failed" on macOS

This should already be handled automatically. If it still appears, run:

```bash
pip install --upgrade certifi
```

Then rebuild the app.

### MP4 download has audio but no video

This usually happens when a video is downloaded in VP9 or AV1 format, which QuickTime does not support. The app requests H.264 + AAC and re-encodes through ffmpeg when needed. Make sure ffmpeg is installed and bundled during the build.

### ffmpeg not found during build

* macOS: `brew install ffmpeg`
* Windows: Place `ffmpeg.exe` and `ffprobe.exe` in the same folder as `build_windows.bat`, then run the script again

### Windows SmartScreen / Defender warning

The executable is not code-signed. Click **More info** → **Run anyway**. If you prefer, you can build the app yourself from source.

### macOS "app is damaged" or "unidentified developer"

Right-click the app and choose **Open**. If that still fails, run:

```bash
xattr -cr "/Applications/YT Downloader.app"
```

### A playlist video was skipped

Private, members-only, age-restricted, or region-blocked videos are skipped automatically. The rest of the playlist will still download.

### The ETA shows `--:--`

This can happen briefly at the beginning of a download before enough data is available to estimate speed.

---

## Dependencies

| Package                                                   | Purpose                                                  |
| --------------------------------------------------------- | -------------------------------------------------------- |
| [yt-dlp](https://github.com/yt-dlp/yt-dlp)                | YouTube extraction and downloading                       |
| [certifi](https://github.com/certifi/python-certifi)      | SSL CA certificates                                      |
| [ffmpeg](https://ffmpeg.org)                              | Audio extraction, video re-encoding, thumbnail embedding |
| [PyInstaller](https://pyinstaller.org)                    | Packaging into a standalone binary (build-time only)     |
| [tkinter](https://docs.python.org/3/library/tkinter.html) | GUI toolkit included with Python                         |

---

## Legal disclaimer

> **This project is intended for personal, educational, and research purposes only.**

* This tool is not affiliated with or endorsed by YouTube or Google LLC.
* Downloading YouTube content may violate [YouTube's Terms of Service](https://www.youtube.com/t/terms), specifically section 5.1.K, which prohibits downloading content without explicit permission from YouTube.
* You are responsible for ensuring your use complies with applicable laws and platform terms.
* Only download content you have permission to download, including your own content or content explicitly licensed for download.
* Downloading copyrighted media without authorization may violate copyright law.
* The author is not liable for misuse, copyright infringement, or damages arising from use of this software.

**If you are a content creator and want your content removed from someone's use of this tool, contact that individual directly.**

---

## License

MIT License — see [LICENSE](LICENSE) for details.

You are free to use, modify, and distribute this software. The MIT license applies only to the code in this repository and does not grant rights to YouTube content or third-party services.

---

<p align="center">
  Built with <a href="https://github.com/yt-dlp/yt-dlp">yt-dlp</a> ·
  Packaged with <a href="https://pyinstaller.org">PyInstaller</a>
</p>
