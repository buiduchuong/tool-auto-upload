@echo off
chcp 65001 >nul
cd /d "%~dp0"
call "_run_python.bat" facebook_upload.py --mode browser --attach --all --target-url https://www.facebook.com --description-file facebook_description.txt --profile-dir chrome-profile-facebook --debug-port 9224
pause
