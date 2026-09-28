@echo off
rem PC-Monitor SDS_110 starten (Windows). Legt beim ersten Aufruf .venv an und installiert die Pakete.
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
    echo Lege virtuelle Umgebung .venv an ...
    py -3 -m venv .venv 2>nul || python -m venv .venv
    if errorlevel 1 (
        echo Python 3 nicht gefunden. Bitte von python.org installieren.
        pause
        exit /b 1
    )
    .venv\Scripts\python.exe -m pip install --upgrade pip
    .venv\Scripts\python.exe -m pip install -r requirements.txt
    if errorlevel 1 (
        echo Installation der Pakete fehlgeschlagen.
        pause
        exit /b 1
    )
)
.venv\Scripts\python.exe -m app.main %*
if errorlevel 1 pause
