@echo off
chcp 65001 >nul
cd /d "%~dp0"
call "_run_python.bat" tiktok_upload.py --login
pause
