@echo off
setlocal enabledelayedexpansion
title YT Downloader - Build Script

echo.
echo =====================================================
echo    YT Downloader - Windows Build Script
echo =====================================================
echo.

:: ── 1. Check Python ─────────────────────────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found.
    echo.
    echo Please install Python from https://python.org
    echo Make sure to check "Add Python to PATH" during install.
    echo.
    pause
    exit /b 1
)
for /f "tokens=*" %%v in ('python --version 2^>^&1') do echo [OK] %%v

:: ── 2. Install dependencies ─────────────────────────────────
echo.
echo [*] Installing/upgrading dependencies...
python -m pip install --upgrade --quiet pip
python -m pip install --quiet yt-dlp certifi pyinstaller
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies.
    pause
    exit /b 1
)
echo [OK] Dependencies installed.

:: ── 3. Find certifi CA bundle ───────────────────────────────
for /f "tokens=*" %%p in ('python -c "import certifi; print(certifi.where())"') do set CERTIFI=%%p
echo [OK] certifi: %CERTIFI%

:: ── 4. Find ffmpeg ──────────────────────────────────────────
set FFMPEG_ARGS=
where ffmpeg >nul 2>&1
if errorlevel 1 (
    echo.
    echo [WARNING] ffmpeg not found on PATH.
    echo    MP3 conversion and MP4 re-encoding won't work without it.
    echo    Download from: https://www.gyan.dev/ffmpeg/builds/
    echo    Extract ffmpeg.exe and ffprobe.exe into the same folder as this script,
    echo    then re-run build_windows.bat
    echo.

    :: Check if ffmpeg.exe is sitting right next to this script
    if exist "%~dp0ffmpeg.exe" (
        echo [OK] Found ffmpeg.exe next to build script - will bundle it.
        set FFMPEG_ARGS=--add-binary "%~dp0ffmpeg.exe;."
    )
    if exist "%~dp0ffprobe.exe" (
        echo [OK] Found ffprobe.exe next to build script - will bundle it.
        set FFMPEG_ARGS=!FFMPEG_ARGS! --add-binary "%~dp0ffprobe.exe;."
    )
) else (
    for /f "tokens=*" %%f in ('where ffmpeg') do set FFMPEG_PATH=%%f
    for /f "tokens=*" %%f in ('where ffprobe 2^>nul') do set FFPROBE_PATH=%%f
    echo [OK] ffmpeg: !FFMPEG_PATH!
    set FFMPEG_ARGS=--add-binary "!FFMPEG_PATH!;."
    if defined FFPROBE_PATH (
        echo [OK] ffprobe: !FFPROBE_PATH!
        set FFMPEG_ARGS=!FFMPEG_ARGS! --add-binary "!FFPROBE_PATH!;."
    )
)

:: ── 5. Clean previous build ─────────────────────────────────
echo.
echo [*] Cleaning previous build...
if exist build   rmdir /s /q build
if exist dist    rmdir /s /q dist
if exist "YT Downloader.spec" del /q "YT Downloader.spec"
echo [OK] Cleaned.

:: ── 6. Run PyInstaller ──────────────────────────────────────
echo.
echo [*] Building executable (this takes ~1-2 minutes)...
echo.

python -m PyInstaller ^
  --noconfirm ^
  --windowed ^
  --onefile ^
  --name "YT Downloader" ^
  --add-data "%CERTIFI%;certifi" ^
  %FFMPEG_ARGS% ^
  --hidden-import yt_dlp ^
  --hidden-import yt_dlp.extractor ^
  --hidden-import yt_dlp.postprocessor ^
  --hidden-import certifi ^
  --collect-all yt_dlp ^
  --collect-all certifi ^
  yt_downloader_gui_windows.py

if errorlevel 1 (
    echo.
    echo [ERROR] Build failed. See output above for details.
    pause
    exit /b 1
)

:: ── 7. Done ─────────────────────────────────────────────────
echo.
echo =====================================================
echo   [OK] Build complete!
echo.
echo   Executable:  %cd%\dist\YT Downloader.exe
echo.
echo   You can move "YT Downloader.exe" anywhere you like.
echo   No Python or installation needed to run it.
echo =====================================================
echo.

:: Open the dist folder in Explorer
explorer dist

pause
