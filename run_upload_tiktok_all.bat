@echo off
chcp 65001 >nul
cd /d "%~dp0"
call "_run_python.bat" tiktok_upload.py --attach --all --video-dir TikTok_Channel --description-file tiktok_description.txt --yes
pause
