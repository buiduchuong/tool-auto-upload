@echo off
setlocal EnableExtensions
title TikTok Facebook Reuploader - Setup

cd /d "%~dp0"

echo ============================================================
echo   TikTok Facebook Reuploader - Environment setup
echo ============================================================
echo.

rem Install the current Node.js LTS only when Node/npm is missing.
where node.exe >nul 2>&1
if errorlevel 1 goto install_node
where npm.cmd >nul 2>&1
if errorlevel 1 goto install_node
goto node_ready

:install_node
echo [1/6] Node.js or npm was not found.
echo       Installing the latest Node.js LTS from nodejs.org...

fltmc >nul 2>&1
if errorlevel 1 (
    echo.
    echo ERROR: Administrator permission is required to install Node.js.
    echo Right-click setup.bat, choose "Run as administrator", then try again.
    goto failed
)

set "NODE_MSI=%TEMP%\node-lts-setup.msi"
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; $ProgressPreference='SilentlyContinue'; [Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; $arch = if ([Runtime.InteropServices.RuntimeInformation]::OSArchitecture -eq 'Arm64') {'arm64'} else {'x64'}; $file = 'win-' + $arch + '-msi'; $releases = (Invoke-WebRequest -UseBasicParsing 'https://nodejs.org/dist/index.json').Content | ConvertFrom-Json; $release = $null; foreach ($item in $releases) { if ($item.lts -and $item.files -contains $file) { $release = $item; break } }; if (-not $release) { throw 'No compatible Node.js LTS installer was found.' }; $url = 'https://nodejs.org/dist/' + $release.version + '/node-' + $release.version + '-' + $arch + '.msi'; Write-Host ('Downloading ' + $url); Invoke-WebRequest -UseBasicParsing $url -OutFile $env:NODE_MSI"
if errorlevel 1 (
    echo ERROR: Could not download Node.js LTS.
    goto failed
)

start /wait "" msiexec.exe /i "%NODE_MSI%" /qn /norestart
if errorlevel 1 (
    echo ERROR: Node.js installation failed.
    goto failed
)
del /q "%NODE_MSI%" >nul 2>&1

set "PATH=%ProgramFiles%\nodejs;%ProgramFiles(x86)%\nodejs;%PATH%"

:node_ready
echo [1/6] Checking Node.js and npm...
node --version
if errorlevel 1 goto node_not_available
call npm.cmd --version
if errorlevel 1 goto node_not_available

echo.
echo [2/6] Installing project packages...
set "PUPPETEER_SKIP_DOWNLOAD="
rem This tool launches full Chrome, so the separate headless-shell download is unnecessary.
set "PUPPETEER_SKIP_CHROME_HEADLESS_SHELL_DOWNLOAD=true"
if exist "package-lock.json" (
    call npm.cmd ci
    if errorlevel 1 (
        echo.
        echo package-lock.json is out of sync. Repairing it with npm install...
        call npm.cmd install
    )
) else (
    call npm.cmd install
)
if errorlevel 1 (
    echo ERROR: npm could not install the project packages.
    goto failed
)

echo.
echo [3/6] Checking the Chromium browser used by Puppeteer...
node -e "const fs=require('fs'); import('puppeteer').then(p=>process.exit(fs.existsSync(p.executablePath())?0:1)).catch(()=>process.exit(1))"
if errorlevel 1 (
    echo Chromium is missing. Downloading it now...
    call npx.cmd puppeteer browsers install chrome
    if errorlevel 1 (
        echo ERROR: Chromium download failed.
        goto failed
    )
) else (
    echo Chromium is ready.
)

echo.
echo [4/6] Installing a local FFmpeg binary...
set "FFMPEG_ROOT=%CD%\.tools\ffmpeg"
call npm.cmd install --prefix "%FFMPEG_ROOT%" --no-save --no-package-lock ffmpeg-static@5.2.0
if errorlevel 1 (
    echo WARNING: FFmpeg could not be installed. Video conversion may be skipped.
) else (
    if not exist "node_modules\.bin" mkdir "node_modules\.bin"
    >"node_modules\.bin\ffmpeg.cmd" echo @"%%~dp0..\..\.tools\ffmpeg\node_modules\ffmpeg-static\ffmpeg.exe" %%*
    echo FFmpeg is ready.
)

echo.
echo [5/6] Preparing local configuration and folders...
if not exist ".env" (
    if exist ".env.example" (
        copy /y ".env.example" ".env" >nul
        echo Created .env from .env.example.
    )
) else (
    echo Existing .env was kept unchanged.
)
if not exist "download" mkdir "download"
if not exist "accounts" mkdir "accounts"

echo.
echo [6/6] Verifying JavaScript files...
node --check "index.js"
if errorlevel 1 goto verification_failed
node --check "telebot.js"
if errorlevel 1 goto verification_failed

echo.
echo ============================================================
echo   SETUP COMPLETED SUCCESSFULLY
echo ============================================================
echo.
echo Run the normal tool with:
echo   npm start
echo.
echo Run the Telegram bot with:
echo   npm run bot
echo.
echo Before using the Telegram bot, edit .env and set BOT_TOKEN.
echo Before uploading to Facebook, make sure cookies.json is valid.
echo.
pause
exit /b 0

:node_not_available
echo.
echo ERROR: Node.js was installed but this window cannot find it.
echo Close this window, open a new Command Prompt, and run setup.bat again.
goto failed

:verification_failed
echo ERROR: JavaScript syntax verification failed.

:failed
echo.
echo Setup did not finish. Review the error shown above.
pause
exit /b 1
