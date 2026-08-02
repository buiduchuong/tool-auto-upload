$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Package = Join-Path $Root "vps_light_package"
$Archive = Join-Path $Root "vps_light_package.zip"

$resolvedRoot = (Resolve-Path -LiteralPath $Root).Path
if (Test-Path -LiteralPath $Package) {
    $resolvedPackage = (Resolve-Path -LiteralPath $Package).Path
    if (-not $resolvedPackage.StartsWith($resolvedRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Package path is outside tool folder: $resolvedPackage"
    }
    Remove-Item -LiteralPath $resolvedPackage -Recurse
}
if (Test-Path -LiteralPath $Archive) {
    $resolvedArchive = (Resolve-Path -LiteralPath $Archive).Path
    if (-not $resolvedArchive.StartsWith($resolvedRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Archive path is outside tool folder: $resolvedArchive"
    }
    Remove-Item -LiteralPath $resolvedArchive
}

New-Item -ItemType Directory -Path $Package | Out-Null

$Files = @(
    "main.py",
    "tiktok_upload.py",
    "facebook_upload.py",
    "instagram_upload.py",
    "zernio_upload.py",
    "web_panel.py",
    "show_credentials.py",
    "requirements.txt",
    "README_CHAY_NHANH.txt",
    "HUONG_DAN_COPY_VPS.txt",
    "setup.bat",
    "setup.ps1",
    "CHAY_TREN_VPS.bat",
    "_run_python.bat",
    "run_web_panel.bat",
    "run_download_tiktok_profile.bat",
    "show_credentials.bat",
    "cleanup_vps_light.bat",
    "chromedriver.exe",
    "ffmpeg.exe",
    "ffprobe.exe",
    "yt-dlp.exe",
    "default_description.txt",
    "tiktok_description.txt",
    "facebook_description.txt",
    "instagram_description.txt",
    "title_hashtags.txt",
    "description_hashtags.txt",
    "archive_video.txt",
    "zernio_media_urls.txt",
    "HUONG_DAN_ZERNIO.txt",
    "HUONG_DAN_WEB_PANEL.txt",
    "HUONG_DAN_CHATGPT_API.txt",
    "HUONG_DAN_BAO_MAT_VPS.txt",
    "HUONG_DAN_WINDOWS_2012_VPS.txt",
    "DANH_SACH_DONG_GOI_VPS.txt"
)

foreach ($File in $Files) {
    $Source = Join-Path $Root $File
    if (Test-Path -LiteralPath $Source) {
        Copy-Item -LiteralPath $Source -Destination $Package
    }
}

$Dirs = @(
    "web_static",
    "videos",
    "TikTok_Channel",
    "uploaded_success",
    "uploaded_facebook_success",
    "uploaded_tiktok_success",
    "uploaded_instagram_success",
    "deleted_videos"
)

foreach ($Dir in $Dirs) {
    $Source = Join-Path $Root $Dir
    $Target = Join-Path $Package $Dir
    New-Item -ItemType Directory -Path $Target -Force | Out-Null
    if ($Dir -eq "web_static" -and (Test-Path -LiteralPath $Source)) {
        Copy-Item -Path (Join-Path $Source "*") -Destination $Target -Recurse
    }
}

$SettingsSource = Join-Path $Root "panel_settings.json"
$SettingsTarget = Join-Path $Package "panel_settings.json"
if (Test-Path -LiteralPath $SettingsSource) {
    Push-Location $Root
    try {
        $SettingsJsonRaw = & python -c "import json, web_panel; print(json.dumps(web_panel.load_settings(include_token=True), ensure_ascii=False))"
        if ($LASTEXITCODE -ne 0) {
            throw "Khong doc duoc cau hinh day du bang web_panel.py."
        }
    }
    finally {
        Pop-Location
    }
    $Settings = $SettingsJsonRaw | ConvertFrom-Json
    $Settings.youtube.upload_dir = "videos"
    $Settings.tiktok.upload_dir = "TikTok_Channel"
    $Settings.facebook.upload_dir = "videos"
    $Settings.zernio.upload_dir = "videos"
    $Settings.download.download_dir = "videos"
    $Settings.facebook.page_token = ""
    $Settings.zernio.api_key = ""
    $Settings.api.token = ""
    $Settings.web_auth.password = ""

    foreach ($Platform in @("youtube", "tiktok", "facebook")) {
        $UploadDir = if ($Platform -eq "tiktok") { "TikTok_Channel" } else { "videos" }
        foreach ($Account in $Settings.accounts.$Platform.items) {
            $Account.upload_dir = $UploadDir
            $Account.profile_dir = "accounts\$Platform\$($Account.id)\chrome-profile"
            if ($Platform -eq "facebook") {
                $Account.page_token = ""
            }
        }
    }

    $SettingsJson = $Settings | ConvertTo-Json -Depth 20
    [System.IO.File]::WriteAllText(
        $SettingsTarget,
        $SettingsJson,
        (New-Object System.Text.UTF8Encoding($false))
    )
}

Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.IO.Compression.ZipFile]::CreateFromDirectory(
    $Package,
    $Archive,
    [System.IO.Compression.CompressionLevel]::Optimal,
    $false
)

Write-Output "Da tao goi VPS nhe tai: $Package"
Write-Output "File ZIP: $Archive"
Write-Output "Goi nay khong copy videos, Chrome profiles, debug, cache."
Write-Output "Token va mat khau trong panel_settings.json da duoc xoa."
