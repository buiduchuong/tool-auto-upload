@echo off
cd /d "%~dp0"
echo Dang don cache/debug/temp, khong xoa video goc va profile Chrome...

if exist "__pycache__" rmdir /s /q "__pycache__"
if exist "facebook_debug" rmdir /s /q "facebook_debug"
if exist "tiktok_debug" rmdir /s /q "tiktok_debug"
if exist "facebook_upload_temp" rmdir /s /q "facebook_upload_temp"

mkdir "facebook_upload_temp" >nul 2>nul

echo Da don xong.
pause
