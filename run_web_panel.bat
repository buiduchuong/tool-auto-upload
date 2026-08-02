@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

set "PYTHONIOENCODING=utf-8"
set "PANEL_URL=http://127.0.0.1:8080"
set "PANEL_URL_FILE=web_panel_url.txt"
set "PYTHON_CMD="

powershell -NoProfile -Command "try { $r = Invoke-WebRequest -UseBasicParsing -Uri '%PANEL_URL%/api/state' -TimeoutSec 2; if ($r.StatusCode -eq 200) { exit 0 } } catch {}; exit 1" >nul 2>nul
if not errorlevel 1 (
    echo Web panel dang chay san tai %PANEL_URL%
    start "" "%PANEL_URL%"
    exit /b 0
)

if exist ".venv\Scripts\python.exe" set "PYTHON_CMD=.venv\Scripts\python.exe"

if not defined PYTHON_CMD (
    where py >nul 2>nul
    if not errorlevel 1 (
        py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
        if not errorlevel 1 set "PYTHON_CMD=py -3"
    )
)

if not defined PYTHON_CMD (
    where python >nul 2>nul
    if not errorlevel 1 (
        python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
        if not errorlevel 1 set "PYTHON_CMD=python"
    )
)

if not defined PYTHON_CMD (
    echo [LOI] Khong tim thay Python 3.10 tro len.
    echo Hay chay setup.bat de tu cai moi truong, sau do chay lai.
    pause
    exit /b 1
)

if not exist "web_panel.py" (
    echo [LOI] Thieu file web_panel.py trong thu muc nay.
    pause
    exit /b 1
)

if not exist "web_static\index.html" (
    echo [LOI] Thieu thu muc web_static hoac file index.html.
    pause
    exit /b 1
)

if exist "%PANEL_URL_FILE%" del "%PANEL_URL_FILE%" >nul 2>nul

echo Dang khoi dong web panel bang %PYTHON_CMD%...
echo Trinh duyet se tu mo khi web panel san sang.
start "" powershell -NoProfile -WindowStyle Hidden -Command "$file = Join-Path '%~dp0' '%PANEL_URL_FILE%'; for ($i = 0; $i -lt 40; $i++) { if (Test-Path -LiteralPath $file) { $url = (Get-Content -LiteralPath $file -Raw).Trim(); if ($url) { Start-Process $url; exit 0 } }; Start-Sleep -Milliseconds 500 }; Start-Process '%PANEL_URL%'"

%PYTHON_CMD% web_panel.py
set "PANEL_EXIT=%ERRORLEVEL%"

echo.
echo Web panel da dung, ma loi: %PANEL_EXIT%
if "%PANEL_EXIT%"=="1" echo Neu thay loi cong web panel, hay dong tien trinh cu hoac khoi dong lai VPS.
pause
exit /b %PANEL_EXIT%
