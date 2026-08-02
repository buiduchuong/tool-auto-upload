@echo off
chcp 65001 >nul
cd /d "%~dp0"
call "_run_python.bat" facebook_upload.py --login --profile-dir chrome-profile-facebook --debug-port 9224
pause
