@echo off
cd /d "%~dp0"
powershell -ExecutionPolicy Bypass -File "%~dp0make_vps_light_package.ps1"
pause
