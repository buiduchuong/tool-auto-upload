@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================
echo  MSTAR TOOL - SETUP TU DONG
echo ========================================
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1"
set "SETUP_EXIT=%ERRORLEVEL%"

echo.
if "%SETUP_EXIT%"=="0" (
    echo [OK] Setup xong. Ban co the chay run_web_panel.bat
) else (
    echo [LOI] Setup chua hoan tat. Xem loi phia tren roi chay lai setup.bat
)
echo.
pause
exit /b %SETUP_EXIT%
