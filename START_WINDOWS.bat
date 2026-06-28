@echo off
title Football Shorts Generator
color 0A
echo.
echo  =============================================
echo    Football Shorts Generator
echo  =============================================
echo.

:: ── Stap 1: Python zoeken ─────────────────────────────────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo  [!] Python is niet geinstalleerd.
    echo.
    echo  Python wordt nu automatisch geinstalleerd via Windows...
    echo  (Dit duurt ongeveer 2 minuten)
    echo.
    winget install -e --id Python.Python.3.11 --accept-package-agreements --accept-source-agreements
    if errorlevel 1 (
        echo.
        echo  Automatisch installeren mislukt.
        echo  Ga naar https://python.org en klik op "Download Python"
        echo  Vink onderaan het installatiescherm "Add Python to PATH" aan!
        echo.
        start https://www.python.org/downloads/
        pause
        exit /b
    )
    echo.
    echo  Python geinstalleerd! Herstart dit bestand nu opnieuw.
    pause
    exit /b
)

echo  [OK] Python gevonden.
echo.

:: ── Stap 2: Packages installeren ──────────────────────────────────────────
echo  Benodigde onderdelen worden geinstalleerd (eenmalig, ~2 min)...
pip install flask yt-dlp moviepy==1.0.3 Pillow numpy imageio imageio-ffmpeg python-dotenv pyyaml --quiet --no-warn-script-location
echo  [OK] Alles geinstalleerd.
echo.

:: ── Stap 3: App starten ───────────────────────────────────────────────────
echo  App wordt gestart...
echo  Browser opent automatisch op http://localhost:5000
echo.
echo  Laat dit venster open zolang je de app gebruikt.
echo  Sluit het venster om de app te stoppen.
echo.
python app.py
pause
