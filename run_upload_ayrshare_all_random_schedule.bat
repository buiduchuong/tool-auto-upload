@echo off
chcp 65001 >nul
cd /d "%~dp0"
if "%AYRSHARE_API_KEY%"=="" (
  echo Thieu AYRSHARE_API_KEY. Hay set bien moi truong hoac nhap API key trong panel.
  pause
  exit /b 1
)
call "_run_python.bat" ayrshare_upload.py --all --video-dir videos --description-file default_description.txt --platforms facebook,instagram,tiktok,youtube --start-after-minutes 30 --min-gap-minutes 60 --max-gap-minutes 180 --max-videos 3
pause
