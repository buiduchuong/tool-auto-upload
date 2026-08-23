$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

function Write-Step([string]$Message) {
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Write-Ok([string]$Message) {
    Write-Host "[OK] $Message" -ForegroundColor Green
}

function Write-Warn([string]$Message) {
    Write-Host "[CANH BAO] $Message" -ForegroundColor Yellow
}

function Test-PythonCommand([string]$Command, [string[]]$Args) {
    try {
        $version = & $Command @Args -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" 2>$null
        return $LASTEXITCODE -eq 0
    }
    catch {
        return $false
    }
}

function Find-SystemPython {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        if (Test-PythonCommand "py" @("-3")) {
            return @{ Command = "py"; Args = @("-3") }
        }
    }

    if (Get-Command python -ErrorAction SilentlyContinue) {
        if (Test-PythonCommand "python" @()) {
            return @{ Command = "python"; Args = @() }
        }
    }

    $commonPython = @(
        "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python310\python.exe",
        "$env:ProgramFiles\Python312\python.exe",
        "$env:ProgramFiles\Python311\python.exe",
        "$env:ProgramFiles\Python310\python.exe"
    )

    foreach ($pythonExe in $commonPython) {
        if ($pythonExe -and (Test-Path -LiteralPath $pythonExe)) {
            if (Test-PythonCommand $pythonExe @()) {
                return @{ Command = $pythonExe; Args = @() }
            }
        }
    }

    return $null
}

function Find-Chrome {
    $paths = @(
        "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
        "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
        "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe"
    )

    foreach ($path in $paths) {
        if ($path -and (Test-Path -LiteralPath $path)) {
            return $path
        }
    }

    return $null
}

function Install-WithWinget([string]$PackageId, [string]$Name) {
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        throw "Khong tim thay winget de tu cai $Name. Hay cai App Installer/winget hoac cai $Name thu cong."
    }

    Write-Step "Dang cai $Name bang winget"
    & winget install --id $PackageId --exact --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0) {
        throw "winget cai $Name that bai, ma loi $LASTEXITCODE."
    }
}

Write-Host "Thu muc tool: $Root"

Write-Step "Kiem tra Python 3.10+"
$python = Find-SystemPython
if (-not $python) {
    Install-WithWinget "Python.Python.3.12" "Python 3.12"
    $env:Path = "$env:LOCALAPPDATA\Programs\Python\Python312;$env:LOCALAPPDATA\Programs\Python\Python312\Scripts;$env:LOCALAPPDATA\Microsoft\WindowsApps;$env:Path"
    $python = Find-SystemPython
}
if (-not $python) {
    throw "Khong tim thay Python 3.10+ sau khi cai. Hay mo lai cua so CMD/PowerShell roi chay setup.bat lan nua."
}
Write-Ok "Da co Python 3.10+"

Write-Step "Kiem tra Google Chrome"
$chrome = Find-Chrome
if (-not $chrome) {
    try {
        Install-WithWinget "Google.Chrome" "Google Chrome"
        $chrome = Find-Chrome
    }
    catch {
        Write-Warn $_.Exception.Message
        Write-Warn "Tool van setup tiep, nhung upload bang Selenium can Chrome de chay."
    }
}
if ($chrome) {
    Write-Ok "Da co Chrome: $chrome"
}

Write-Step "Tao moi truong ao .venv"
$venvPython = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $venvPython)) {
    $pythonCommand = $python.Command
    & $pythonCommand @($python.Args + @("-m", "venv", ".venv"))
    if ($LASTEXITCODE -ne 0) {
        throw "Tao .venv that bai."
    }
}
Write-Ok "Da san sang .venv"

Write-Step "Cai/cap nhat thu vien Python"
& $venvPython -m pip install --upgrade pip setuptools wheel
if ($LASTEXITCODE -ne 0) {
    throw "Cap nhat pip/setuptools/wheel that bai."
}

& $venvPython -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) {
    throw "Cai requirements.txt that bai."
}

& $venvPython -m pip install --upgrade yt-dlp
if ($LASTEXITCODE -ne 0) {
    Write-Warn "Khong cai duoc package yt-dlp. Neu co yt-dlp.exe trong thu muc thi van tai video duoc."
}
Write-Ok "Da cai thu vien Python"

Write-Step "Tao cac thu muc can thiet"
$dirs = @(
    "videos",
    "TikTok_Channel",
    "uploaded_success",
    "uploaded_tiktok_success",
    "uploaded_facebook_success",
    "uploaded_instagram_success",
    "deleted_videos",
    "ayrshare_upload_temp",
    "facebook_upload_temp",
    "zernio_upload_temp",
    "instagram_debug",
    "accounts\youtube",
    "accounts\tiktok",
    "accounts\facebook",
    "accounts\instagram"
)
foreach ($dir in $dirs) {
    New-Item -ItemType Directory -Path (Join-Path $Root $dir) -Force | Out-Null
}
Write-Ok "Da tao thu muc"

Write-Step "Kiem tra file cau hinh mac dinh"
$defaultFiles = @{
    "default_description.txt" = ""
    "tiktok_description.txt" = ""
    "facebook_description.txt" = ""
    "instagram_description.txt" = ""
    "title_hashtags.txt" = ""
    "description_hashtags.txt" = ""
    "archive_video.txt" = ""
    "facebook_archive_video.txt" = ""
    "zernio_media_urls.txt" = ""
    "ayrshare_media_urls.txt" = ""
}
foreach ($item in $defaultFiles.GetEnumerator()) {
    $path = Join-Path $Root $item.Key
    if (-not (Test-Path -LiteralPath $path)) {
        [System.IO.File]::WriteAllText($path, $item.Value, (New-Object System.Text.UTF8Encoding($false)))
    }
}
Write-Ok "Da co file cau hinh"

Write-Step "Kiem tra cong cu phu tro"
$toolWarnings = @()
foreach ($tool in @("chromedriver.exe", "ffmpeg.exe", "ffprobe.exe", "yt-dlp.exe")) {
    if (-not (Test-Path -LiteralPath (Join-Path $Root $tool))) {
        $toolWarnings += $tool
    }
}

if ($toolWarnings -contains "ffmpeg.exe" -or $toolWarnings -contains "ffprobe.exe") {
    if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue) -or -not (Get-Command ffprobe -ErrorAction SilentlyContinue)) {
        try {
            Install-WithWinget "Gyan.FFmpeg" "FFmpeg"
            $env:Path = "$env:Path;$env:ProgramFiles\ffmpeg\bin;$env:LOCALAPPDATA\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.0-full_build\bin"
        }
        catch {
            Write-Warn $_.Exception.Message
            Write-Warn "Neu can cat/nen/ghep video, hay cai FFmpeg thu cong hoac dat ffmpeg.exe/ffprobe.exe cung thu muc tool."
        }
    }
}

if ($toolWarnings.Count -gt 0) {
    Write-Warn ("Thieu file: " + ($toolWarnings -join ", "))
    Write-Warn "Rieng yt-dlp da cai them qua Python, Selenium co the tu quan ly ChromeDriver."
}
else {
    Write-Ok "Da co chromedriver/ffmpeg/ffprobe/yt-dlp di kem"
}

Write-Step "Kiem tra import chinh"
& $venvPython -c "import selenium, pyperclip, requests; import web_panel; print('OK')"
if ($LASTEXITCODE -ne 0) {
    throw "Kiem tra import that bai."
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host " SETUP HOAN TAT" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host "Lan sau chi can chay: run_web_panel.bat"
Write-Host "Neu copy source qua may/VPS khac: chay setup.bat truoc."
