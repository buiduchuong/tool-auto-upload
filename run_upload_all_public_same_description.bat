@echo off
chcp 65001 >nul
cd /d "%~dp0"
call "_run_python.bat" main.py --attach --all --visibility public --description-file default_description.txt
pause
