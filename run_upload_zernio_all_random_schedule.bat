@echo off
chcp 65001 >nul
cd /d "%~dp0"
set "PYTHONIOENCODING=utf-8"
if "%ZERNIO_API_KEYS%%ZERNIO_API_KEY%"=="" (
  echo Thieu ZERNIO_API_KEYS hoac ZERNIO_API_KEY. Co the nhap API key trong panel.
  pause
  exit /b 1
)
call "_run_python.bat" zernio_upload.py --all --video-dir videos --platforms facebook,instagram,tiktok,youtube --start-after-minutes 30 --min-gap-minutes 60 --max-gap-minutes 180 --max-videos 3
pause
