@echo off
title Football Shorts Generator
color 0A
echo.
echo  =============================================
echo    Football Shorts Generator
echo  =============================================
echo.

:: ── Stap 1: Python zoeken (python of py commando) ──────────────────────────
set PYTHON_CMD=

python --version >nul 2>&1
if not errorlevel 1 (
    set PYTHON_CMD=python
    goto :python_found
)

py --version >nul 2>&1
if not errorlevel 1 (
    set PYTHON_CMD=py
    goto :python_found
)

:: Python niet gevonden — probeer via bekende installatie-paden
if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
    set PYTHON_CMD="%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
    goto :python_found
)
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
    set PYTHON_CMD="%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    goto :python_found
)
if exist "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" (
    set PYTHON_CMD="%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
    goto :python_found
)

:: Python echt niet gevonden — installeren via winget
echo  [!] Python is niet gevonden.
echo  [*] Python wordt automatisch geinstalleerd...
echo      (Dit duurt 1-3 minuten, even geduld)
echo.

winget install -e --id Python.Python.3.11 --accept-package-agreements --accept-source-agreements >nul 2>&1

if errorlevel 1 (
    echo.
    echo  [!] Automatisch installeren mislukt.
    echo  [*] Download Python handmatig:
    echo      1. Ga naar https://python.org
    echo      2. Klik op "Download Python"
    echo      3. Vink onderaan "Add Python to PATH" aan
    echo      4. Klik Install
    echo      5. Dubbelklik daarna opnieuw op START_WINDOWS.bat
    echo.
    start https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

echo  [OK] Python geinstalleerd!
echo  [*] Dit venster herstart zichzelf automatisch...
echo.
timeout /t 3 /nobreak >nul

:: PATH vernieuwen en zichzelf herstarten
setlocal
for /f "tokens=*" %%i in ('powershell -Command "[System.Environment]::GetEnvironmentVariable(\"PATH\",\"User\")"') do set "USERPATH=%%i"
set "PATH=%USERPATH%;%PATH%"
endlocal

cmd /c start "" "%~f0"
exit /b

:python_found
echo  [OK] Python gevonden.
echo.

:: ── Stap 2: Packages installeren ──────────────────────────────────────────
echo  [*] Benodigde onderdelen installeren (eenmalig, ~2 min)...
%PYTHON_CMD% -m pip install --upgrade pip --quiet --no-warn-script-location
%PYTHON_CMD% -m pip install flask yt-dlp Pillow numpy imageio imageio-ffmpeg opencv-python-headless python-dotenv pyyaml --quiet --no-warn-script-location

if errorlevel 1 (
    echo.
    echo  [!] Installatie mislukt. Probeer het opnieuw of run als Administrator.
    pause
    exit /b 1
)

echo  [OK] Alles geinstalleerd.
echo.

:: ── Stap 3: App starten ───────────────────────────────────────────────────
echo  [*] App starten...
echo  [*] Browser opent automatisch op http://localhost:5000
echo.
echo  Laat dit venster open zolang je de app gebruikt.
echo  Sluit dit venster om de app te stoppen.
echo.

%PYTHON_CMD% app.py

echo.
echo  App is gestopt.
pause
