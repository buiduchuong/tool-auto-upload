@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================
echo  MSTAR TOOL - CHAY TREN VPS
echo ========================================
echo.

call "%~dp0setup.bat"
if errorlevel 1 (
    echo.
    echo [LOI] Setup that bai. Xem loi phia tren roi chay lai.
    pause
    exit /b 1
)

echo.
echo Dang mo web panel...
call "%~dp0run_web_panel.bat"
