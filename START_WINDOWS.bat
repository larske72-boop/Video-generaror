@echo off
title Football Shorts Generator
echo.
echo  =============================================
echo   Football Shorts Generator - Opstarten...
echo  =============================================
echo.

:: Controleer Python
python --version >nul 2>&1
if errorlevel 1 (
    echo  [FOUT] Python niet gevonden!
    echo  Download Python via: https://python.org
    echo  Vink "Add Python to PATH" aan tijdens installatie.
    pause
    exit /b
)

:: Installeer dependencies als die er nog niet zijn
echo  Benodigde onderdelen installeren...
pip install flask yt-dlp moviepy Pillow numpy imageio imageio-ffmpeg --quiet

:: Start de app
echo.
echo  App wordt gestart, browser opent automatisch...
echo  Op iPhone: open http://JOUW-IP:5000
echo.
python app.py
pause
