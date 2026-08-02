@echo off
chcp 65001 >nul
cd /d "%~dp0"
set "PROFILE_URL=%~1"
if "%PROFILE_URL%"=="" set "PROFILE_URL=https://www.tiktok.com/@tamanmoingay2404"

set "YTDLP_CMD="
if exist "yt-dlp.exe" set "YTDLP_CMD=yt-dlp.exe"
if not defined YTDLP_CMD if exist ".venv\Scripts\python.exe" set "YTDLP_CMD=.venv\Scripts\python.exe -m yt_dlp"

if not defined YTDLP_CMD (
    echo [LOI] Khong thay yt-dlp.exe hoac .venv. Hay chay setup.bat truoc.
    pause
    exit /b 1
)

%YTDLP_CMD% --ignore-config "%PROFILE_URL%" ^
-f "bv*+ba/b" ^
--merge-output-format mp4 ^
--remux-video mp4 ^
--match-filter "vcodec!=none" ^
--ffmpeg-location "." ^
-P "TikTok_Channel" ^
-o "%%(uploader)s/%%(upload_date)s_%%(id)s.%%(ext)s" ^
--download-archive "archive_video.txt" ^
--ignore-errors ^
--sleep-interval 3 --max-sleep-interval 8

pause
