# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import builtins
import json
import mimetypes
import os
import random
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


BASE_DIR = Path(__file__).resolve().parent
VIDEOS_DIR = BASE_DIR / "videos"
DESCRIPTION_FILE = BASE_DIR / "default_description.txt"
MEDIA_URLS_FILE = BASE_DIR / "zernio_media_urls.txt"
LOG_FILE = BASE_DIR / "zernio_last_run.log"
FFPROBE_FILE = BASE_DIR / "ffprobe.exe"
FFMPEG_FILE = BASE_DIR / "ffmpeg.exe"
TEMP_DIR = BASE_DIR / "zernio_upload_temp"
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".webm", ".mkv", ".m4v"}
API_BASE = "https://zernio.com/api/v1"
MAX_UPLOAD_SIZE = 5 * 1024 * 1024 * 1024
SUPPORTED_PLATFORMS = {"facebook", "instagram", "tiktok", "youtube"}
PLATFORM_DURATION_LIMITS = {
    "facebook": 14400,
}
INSTAGRAM_MAX_DURATION = 90
TIKTOK_MAX_DURATION = 599
YOUTUBE_SHORT_MAX_DURATION = 179
YOUTUBE_SHORT_DELAY_MINUTES = 5


def setup_run_log() -> None:
    original_print = builtins.print
    try:
        LOG_FILE.write_text("", encoding="utf-8")
    except Exception:
        pass

    def tee_print(*args: Any, **kwargs: Any) -> None:
        original_print(*args, **kwargs)
        try:
            text = kwargs.get("sep", " ").join(str(arg) for arg in args)
            with LOG_FILE.open("a", encoding="utf-8") as handle:
                handle.write(text + kwargs.get("end", "\n"))
        except Exception:
            pass

    builtins.print = tee_print


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8-sig", errors="replace").strip()


def collect_videos(video_dir: Path, single_video: str | None) -> list[Path]:
    if single_video:
        path = Path(single_video)
        if not path.is_absolute():
            path = BASE_DIR / path
        if not path.exists() or path.suffix.lower() not in VIDEO_EXTENSIONS:
            raise SystemExit(f"[LOI] Khong thay video hop le: {path}")
        return [path]
    if not video_dir.exists():
        raise SystemExit(f"[LOI] Thu muc video khong ton tai: {video_dir}")
    videos = sorted(
        (path for path in video_dir.rglob("*") if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS),
        key=lambda path: str(path).lower(),
    )
    if not videos:
        raise SystemExit(f"[LOI] Khong co video trong: {video_dir}")
    return videos


def parse_csv(value: str) -> list[str]:
    return list(dict.fromkeys(item.strip().lower() for item in value.replace(";", ",").split(",") if item.strip()))


def parse_values(value: str) -> list[str]:
    return list(dict.fromkeys(item.strip() for item in value.replace(";", ",").split(",") if item.strip()))


def parse_api_keys(value: str) -> list[str]:
    normalized = value.replace(";", ",").replace("\r", "\n").replace("\n", ",")
    return list(dict.fromkeys(item.strip() for item in normalized.split(",") if item.strip()))


def short_key_label(api_key: str, index: int) -> str:
    if len(api_key) >= 12:
        return f"key #{index} ({api_key[:5]}...{api_key[-4:]})"
    return f"key #{index}"


def read_media_url_file(path: Path, videos: list[Path]) -> dict[Path, str]:
    if not path.exists():
        return {}
    by_name = {video.name.lower(): video for video in videos}
    mapping: dict[Path, str] = {}
    sequential: list[str] = []
    for raw_line in read_text(path).splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "|" in line:
            name, url = (part.strip() for part in line.split("|", 1))
            if name.lower() in by_name and url:
                mapping[by_name[name.lower()]] = url
        elif line.lower().startswith(("http://", "https://")):
            sequential.append(line)
    for video, url in zip(videos, sequential):
        mapping.setdefault(video, url)
    return mapping


def request_json(method: str, path: str, *, api_key: str, **kwargs: Any) -> dict[str, Any]:
    headers = dict(kwargs.pop("headers", {}))
    headers["Authorization"] = f"Bearer {api_key}"
    try:
        response = requests.request(method, f"{API_BASE}{path}", headers=headers, timeout=kwargs.pop("timeout", (30, 300)), **kwargs)
    except requests.RequestException as exc:
        raise RuntimeError(f"Loi ket noi Zernio khi goi {path}: {exc}") from exc
    try:
        data = response.json()
    except Exception:
        data = {"raw": response.text[:1000]}
    if response.status_code >= 400:
        raise RuntimeError(f"Zernio HTTP {response.status_code}: {json.dumps(data, ensure_ascii=False)}")
    return data


def validate_api_key(api_key: str, label: str = "") -> None:
    if not re.fullmatch(r"sk_[0-9a-fA-F]{64}", api_key):
        print(f"[CANH BAO] API key Zernio {label or ''} thuong co dang sk_ + 64 ky tu hex.")
    request_json("GET", "/accounts", api_key=api_key, timeout=(15, 30))
    print(f"[ZERNIO] API key hop le: {label or '(1 key)'}")


def get_accounts(api_key: str, platforms: list[str], account_ids: list[str], profile_id: str, label: str = "", require_selected: bool = True) -> list[dict[str, Any]]:
    params: dict[str, str] = {"status": "connected"}
    if profile_id:
        params["profileId"] = profile_id
    data = request_json("GET", "/accounts", api_key=api_key, params=params, timeout=(15, 60))
    accounts = data.get("accounts") or data.get("data") or []
    if not isinstance(accounts, list):
        raise RuntimeError(f"Zernio khong tra ve danh sach accounts: {json.dumps(data, ensure_ascii=False)}")
    requested = set(platforms)
    requested_ids = set(account_ids)
    selected: list[dict[str, Any]] = []
    for account in accounts:
        if not isinstance(account, dict):
            continue
        account_id = str(account.get("_id") or account.get("id") or "")
        platform = str(account.get("platform") or "").lower()
        profile_value = account.get("profileId") or account.get("profile_id") or ""
        account_profile_id = str(profile_value.get("_id") or profile_value.get("id") or "") if isinstance(profile_value, dict) else str(profile_value)
        if platform not in requested:
            continue
        if requested_ids and account_id not in requested_ids:
            continue
        if profile_id and account_profile_id != profile_id:
            continue
        selected.append(account)
    if not selected and require_selected:
        raise RuntimeError(
            "Khong tim thay account Zernio phu hop. Hay ket noi mang xa hoi tren Zernio Dashboard "
            "va kiem tra Platforms / Account IDs / Profile ID trong panel."
        )
    if not selected:
        print(f"[CANH BAO] {label or 'API key nay'} khong co account phu hop voi Platforms dang chon.")
        return []
    found_platforms = {str(account.get("platform") or "").lower() for account in selected}
    missing = sorted(requested - found_platforms)
    if missing:
        print(f"[CANH BAO] Chua co account da ket noi cho: {', '.join(missing)}")
    print(f"[ZERNIO] Account se dung cho {label or 'API key'}:")
    for account in selected:
        print(f"  - {account.get('platform')}: {account.get('displayName') or account.get('name') or account.get('username') or '(khong ten)'} ({account.get('_id') or account.get('id')})")
    return selected


def validate_tiktok_public_access(api_key: str, accounts: list[dict[str, Any]]) -> None:
    for account in accounts:
        if str(account.get("platform") or "").lower() != "tiktok":
            continue
        account_id = str(account.get("_id") or account.get("id") or "")
        info = request_json(
            "GET",
            f"/accounts/{account_id}/tiktok/creator-info",
            api_key=api_key,
            params={"mediaType": "video"},
            timeout=(15, 60),
        )
        raw_levels = info.get("privacyLevels") or []
        levels: set[str] = set()
        for item in raw_levels if isinstance(raw_levels, list) else []:
            if isinstance(item, dict):
                value = item.get("value") or item.get("id") or item.get("privacy_level")
            else:
                value = item
            if value:
                levels.add(str(value))
        if levels and "PUBLIC_TO_EVERYONE" not in levels:
            raise RuntimeError(
                f"TikTok account {account_id} khong cho phep dang public qua API. "
                f"Privacy levels hien co: {', '.join(sorted(levels))}"
            )
        print(f"[ZERNIO] TikTok account {account_id} cho phep dang public.")


def upload_media(path: Path, api_key: str) -> str:
    if path.stat().st_size > MAX_UPLOAD_SIZE:
        raise RuntimeError(f"Video vuot gioi han upload Zernio 5 GB: {path.name}")
    content_type = mimetypes.guess_type(path.name)[0] or "video/mp4"
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", path.name).strip("._") or "video.mp4"
    print(f"[ZERNIO] Tao presigned URL: {path.name} ({path.stat().st_size / 1024 / 1024:.2f} MB)")
    data = request_json(
        "POST",
        "/media/presign",
        api_key=api_key,
        headers={"Content-Type": "application/json"},
        json={"filename": safe_name[:180], "contentType": content_type},
    )
    upload_url = str(data.get("uploadUrl") or "")
    public_url = str(data.get("publicUrl") or "")
    if not upload_url or not public_url:
        raise RuntimeError(f"Zernio thieu uploadUrl/publicUrl: {json.dumps(data, ensure_ascii=False)}")
    print(f"[ZERNIO] Dang upload file: {path.name}")
    try:
        with path.open("rb") as handle:
            response = requests.put(upload_url, data=handle, headers={"Content-Type": content_type}, timeout=(30, 7200))
    except requests.RequestException as exc:
        raise RuntimeError(f"Upload video len Zernio that bai: {exc}") from exc
    if response.status_code >= 400:
        raise RuntimeError(f"Upload signed URL loi HTTP {response.status_code}: {response.text[:500]}")
    print("[ZERNIO] Upload media thanh cong.")
    return public_url


def video_duration_seconds(path: Path) -> float | None:
    command = str(FFPROBE_FILE if FFPROBE_FILE.exists() else "ffprobe")
    try:
        result = subprocess.run(
            [command, "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )
        return float((result.stdout or "").strip()) if result.returncode == 0 else None
    except Exception:
        return None


def make_tiktok_clip(path: Path) -> Path:
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    safe_stem = re.sub(r"[^A-Za-z0-9._-]+", "_", path.stem).strip("._-") or "video"
    output = TEMP_DIR / f"{safe_stem[:90]}_tiktok_9m59s.mp4"
    command = str(FFMPEG_FILE if FFMPEG_FILE.exists() else "ffmpeg")
    print(f"[ZERNIO] Video qua 10 phut; dang tao ban TikTok 9m59s: {output.name}")
    result = subprocess.run(
        [
            command,
            "-y",
            "-i", str(path),
            "-t", str(TIKTOK_MAX_DURATION),
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "23",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "128k",
            "-movflags", "+faststart",
            str(output),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0 or not output.exists():
        raise RuntimeError(f"ffmpeg cat video TikTok loi: {(result.stderr or result.stdout).strip()[-1200:]}")
    print(f"[ZERNIO] Da tao ban TikTok: {output.stat().st_size / 1024 / 1024:.2f} MB")
    return output


def make_instagram_clip(path: Path) -> Path:
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    safe_stem = re.sub(r"[^A-Za-z0-9._-]+", "_", path.stem).strip("._-") or "video"
    output = TEMP_DIR / f"{safe_stem[:90]}_instagram_90s.mp4"
    command = str(FFMPEG_FILE if FFMPEG_FILE.exists() else "ffmpeg")
    print(f"[ZERNIO] Video qua 90 giay; dang tao ban Instagram 90s: {output.name}")
    result = subprocess.run(
        [
            command,
            "-y",
            "-i", str(path),
            "-t", str(INSTAGRAM_MAX_DURATION),
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "23",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "128k",
            "-movflags", "+faststart",
            str(output),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0 or not output.exists():
        raise RuntimeError(f"ffmpeg cat video Instagram loi: {(result.stderr or result.stdout).strip()[-1200:]}")
    print(f"[ZERNIO] Da tao ban Instagram: {output.stat().st_size / 1024 / 1024:.2f} MB")
    return output


def make_youtube_short(path: Path) -> Path:
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    safe_stem = re.sub(r"[^A-Za-z0-9._-]+", "_", path.stem).strip("._-") or "video"
    output = TEMP_DIR / f"{safe_stem[:90]}_youtube_short_2m59s.mp4"
    command = str(FFMPEG_FILE if FFMPEG_FILE.exists() else "ffmpeg")
    video_filter = (
        "[0:v]split=2[bgsrc][fgsrc];"
        "[bgsrc]scale=1080:1920:force_original_aspect_ratio=increase,"
        "crop=1080:1920,boxblur=20:10[bg];"
        "[fgsrc]scale=1080:1920:force_original_aspect_ratio=decrease[fg];"
        "[bg][fg]overlay=(W-w)/2:(H-h)/2,format=yuv420p[v]"
    )
    print(f"[ZERNIO] Dang tao YouTube Short 2m59s khung doc 9:16: {output.name}")
    result = subprocess.run(
        [
            command,
            "-y",
            "-i", str(path),
            "-t", str(YOUTUBE_SHORT_MAX_DURATION),
            "-filter_complex", video_filter,
            "-map", "[v]",
            "-map", "0:a?",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "23",
            "-c:a", "aac",
            "-b:a", "128k",
            "-movflags", "+faststart",
            "-shortest",
            str(output),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0 or not output.exists():
        raise RuntimeError(f"ffmpeg tao YouTube Short loi: {(result.stderr or result.stdout).strip()[-1200:]}")
    print(f"[ZERNIO] Da tao YouTube Short: {output.stat().st_size / 1024 / 1024:.2f} MB")
    return output


def effective_accounts(path: Path, accounts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    duration = video_duration_seconds(path)
    if duration is None:
        print("[CANH BAO] Khong doc duoc thoi luong; giu tat ca platforms.")
        return accounts
    selected: list[dict[str, Any]] = []
    skipped: list[str] = []
    for account in accounts:
        platform = str(account.get("platform") or "").lower()
        limit = PLATFORM_DURATION_LIMITS.get(platform)
        if limit and duration > limit:
            skipped.append(platform)
        else:
            selected.append(account)
    if skipped:
        print(f"[ZERNIO] Bo qua do video qua dai: {', '.join(sorted(set(skipped)))}")
    return selected


def platform_entries(accounts: list[dict[str, Any]], title: str, custom_media_by_platform: dict[str, str] | None = None) -> list[dict[str, Any]]:
    custom_media_by_platform = custom_media_by_platform or {}
    result: list[dict[str, Any]] = []
    for account in accounts:
        account_id = str(account.get("_id") or account.get("id") or "")
        platform = str(account.get("platform") or "").lower()
        entry: dict[str, Any] = {"platform": platform, "accountId": account_id}
        if platform == "youtube":
            entry["platformSpecificData"] = {"title": title[:100], "visibility": "public", "madeForKids": False}
        elif platform == "instagram":
            entry["platformSpecificData"] = {"shareToFeed": True}
        custom_media_url = custom_media_by_platform.get(platform, "")
        if custom_media_url:
            entry["customMedia"] = [{"url": custom_media_url, "type": "video"}]
        result.append(entry)
    return result


def schedule_post(path: Path, media_url: str, schedule_date: datetime, api_key: str, accounts: list[dict[str, Any]], description: str, custom_title: str, custom_media_by_platform: dict[str, str] | None = None) -> dict[str, Any]:
    title = custom_title.strip() or path.stem.strip()
    content = f"{title}\n\n{description}" if description else title
    payload: dict[str, Any] = {
        "content": content,
        "mediaItems": [{"url": media_url, "type": "video"}],
        "platforms": platform_entries(accounts, title, custom_media_by_platform),
        "scheduledFor": schedule_date.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
        "timezone": "UTC",
    }
    if any(str(account.get("platform") or "").lower() == "tiktok" for account in accounts):
        payload["tiktokSettings"] = {
            "privacy_level": "PUBLIC_TO_EVERYONE",
            "allow_comment": True,
            "allow_duet": True,
            "allow_stitch": True,
            "content_preview_confirmed": True,
            "express_consent_given": True,
        }
    print(f"[ZERNIO] Hen lich {path.name}: {payload['scheduledFor']} UTC")
    return request_json("POST", "/posts", api_key=api_key, headers={"Content-Type": "application/json"}, json=payload)


def build_account_groups(api_keys: list[str], platforms: list[str], account_ids: list[str], profile_id: str) -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = []
    found_platforms: set[str] = set()
    for index, api_key in enumerate(api_keys, start=1):
        label = short_key_label(api_key, index)
        validate_api_key(api_key, label)
        accounts = get_accounts(api_key, platforms, account_ids, profile_id, label, require_selected=False)
        if not accounts:
            continue
        validate_tiktok_public_access(api_key, accounts)
        found_platforms.update(str(account.get("platform") or "").lower() for account in accounts)
        groups.append({"api_key": api_key, "label": label, "accounts": accounts})
    if not groups:
        raise RuntimeError(
            "Khong tim thay account Zernio phu hop trong cac API key da nhap. "
            "Hay kiem tra key va cac account connected tren Zernio Dashboard."
        )
    missing = sorted(set(platforms) - found_platforms)
    if missing:
        print(f"[CANH BAO] Tong cac API key van chua co account cho: {', '.join(missing)}")
    return groups


def run(args: argparse.Namespace) -> None:
    api_key_text = (args.api_key or os.environ.get("ZERNIO_API_KEYS") or os.environ.get("ZERNIO_API_KEY") or "").strip()
    api_keys = parse_api_keys(api_key_text)
    if not api_keys and not args.dry_run:
        raise SystemExit("[LOI] Thieu Zernio API key. Nhap trong panel hoac set ZERNIO_API_KEYS/ZERNIO_API_KEY.")
    platforms = parse_csv(args.platforms)
    invalid = sorted(set(platforms) - SUPPORTED_PLATFORMS)
    if invalid:
        raise SystemExit(f"[LOI] Platform Zernio chua ho tro trong tool: {', '.join(invalid)}")
    video_dir = Path(args.video_dir)
    if not video_dir.is_absolute():
        video_dir = BASE_DIR / video_dir
    videos = collect_videos(video_dir, args.video)
    if args.max_videos > 0:
        videos = videos[:args.max_videos]
    media_url_file = Path(args.media_url_file)
    if not media_url_file.is_absolute():
        media_url_file = BASE_DIR / media_url_file
    media_urls = read_media_url_file(media_url_file, videos)
    description = read_text(Path(args.description_file))
    account_groups: list[dict[str, Any]] = []
    if not args.dry_run:
        account_groups = build_account_groups(api_keys, platforms, parse_values(args.account_ids), args.profile_id.strip())
    current_date = datetime.now(timezone.utc) + timedelta(minutes=max(0, args.start_after_minutes))
    random.seed(args.random_seed or None)
    key_count = len(api_keys) if api_keys else 1
    print(f"[ZERNIO] Se len lich {len(videos)} video len: {', '.join(platforms)}")
    if not args.dry_run:
        print(f"[ZERNIO] Dang dung {len(account_groups)} nhom account tu {key_count} API key.")
    for index, video in enumerate(videos, start=1):
        if index > 1:
            current_date += timedelta(minutes=random.randint(args.min_gap_minutes, args.max_gap_minutes))
        print(f"\n[TIEN DO] {index}/{len(videos)}: {video.name}")
        if args.dry_run:
            print(f"[DRY RUN] {current_date.strftime('%Y-%m-%dT%H:%M:%S')} UTC -> {', '.join(platforms)}")
            dry_duration = video_duration_seconds(video)
            if "tiktok" in platforms and dry_duration is not None and dry_duration > 600:
                print("[DRY RUN] Se tao ban TikTok 9m59s.")
            if "instagram" in platforms and dry_duration is not None and dry_duration > INSTAGRAM_MAX_DURATION:
                print("[DRY RUN] Se tao ban Instagram 90s.")
            if "youtube" in platforms and dry_duration is not None and dry_duration > 180:
                print(f"[DRY RUN] Se dang them YouTube Short 2m59s sau {YOUTUBE_SHORT_DELAY_MINUTES} phut.")
            continue
        if current_date > datetime.now(timezone.utc) + timedelta(days=6, hours=23):
            raise RuntimeError(
                "Lich dang vuot qua 7 ngay tinh tu luc upload media. "
                "Hay giam Start after / Random gap / Max videos de URL tam cua Zernio khong het han."
            )
        duration = video_duration_seconds(video)
        clip_path: Path | None = None
        instagram_path: Path | None = None
        short_path: Path | None = None
        upload_cache: dict[tuple[str, str], str] = {}

        def uploaded_url(api_key: str, media_path: Path, *, use_existing_original_url: bool = False) -> str:
            if use_existing_original_url and media_path == video:
                existing_url = media_urls.get(video)
                if existing_url:
                    print(f"[ZERNIO] Dung media URL co san: {existing_url}")
                    return existing_url
            cache_key = (api_key, str(media_path))
            if cache_key not in upload_cache:
                upload_cache[cache_key] = upload_media(media_path, api_key)
            return upload_cache[cache_key]

        try:
            posted_any = False
            for group in account_groups:
                api_key = str(group["api_key"])
                group_label = str(group["label"])
                selected_accounts = effective_accounts(video, list(group["accounts"]))
                if not selected_accounts:
                    print(f"[BO QUA] {group_label}: video khong con account hop le sau khi loc thoi luong.")
                    continue
                has_tiktok = any(str(account.get("platform") or "").lower() == "tiktok" for account in selected_accounts)
                has_instagram = any(str(account.get("platform") or "").lower() == "instagram" for account in selected_accounts)
                has_full_video_platform = any(str(account.get("platform") or "").lower() not in {"tiktok", "instagram"} for account in selected_accounts)
                youtube_accounts = [account for account in selected_accounts if str(account.get("platform") or "").lower() == "youtube"]
                custom_media_by_platform: dict[str, str] = {}
                short_media_url = ""
                print(f"[ZERNIO] Dang xu ly {group_label}.")
                if youtube_accounts and duration is not None and duration > 180:
                    if short_path is None:
                        short_path = make_youtube_short(video)
                    short_media_url = uploaded_url(api_key, short_path)
                if has_instagram and duration is not None and duration > INSTAGRAM_MAX_DURATION:
                    if instagram_path is None:
                        instagram_path = make_instagram_clip(video)
                    instagram_media_url = uploaded_url(api_key, instagram_path)
                    custom_media_by_platform["instagram"] = instagram_media_url
                if has_tiktok and duration is not None and duration > 600:
                    if clip_path is None:
                        clip_path = make_tiktok_clip(video)
                    clip_url = uploaded_url(api_key, clip_path)
                    if has_full_video_platform:
                        custom_media_by_platform["tiktok"] = clip_url
                        media_url = uploaded_url(api_key, video, use_existing_original_url=True)
                    elif custom_media_by_platform:
                        custom_media_by_platform["tiktok"] = clip_url
                        media_url = next(iter(custom_media_by_platform.values()))
                    else:
                        media_url = clip_url
                elif custom_media_by_platform and not has_full_video_platform:
                    media_url = next(iter(custom_media_by_platform.values()))
                else:
                    media_url = uploaded_url(api_key, video, use_existing_original_url=True)
                result = schedule_post(
                    video,
                    media_url,
                    current_date,
                    api_key,
                    selected_accounts,
                    description,
                    args.title,
                    custom_media_by_platform,
                )
                posted_any = True
                print(f"[OK] Zernio video day du response ({group_label}):", json.dumps(result, ensure_ascii=False))
                if short_media_url:
                    base_title = args.title.strip() or video.stem.strip()
                    short_title = f"{base_title[:92]} #Shorts"
                    short_result = schedule_post(
                        video,
                        short_media_url,
                        current_date + timedelta(minutes=YOUTUBE_SHORT_DELAY_MINUTES),
                        api_key,
                        youtube_accounts,
                        description,
                        short_title,
                    )
                    print(
                        f"[OK] YouTube Short hen sau {YOUTUBE_SHORT_DELAY_MINUTES} phut response ({group_label}):",
                        json.dumps(short_result, ensure_ascii=False),
                    )
            if not posted_any:
                print("[BO QUA] Video khong co nhom account nao dang duoc sau khi loc.")
        finally:
            if clip_path and clip_path.exists():
                try:
                    clip_path.unlink()
                    print(f"[ZERNIO] Da xoa file TikTok tam: {clip_path.name}")
                except OSError as exc:
                    print(f"[CANH BAO] Khong xoa duoc file TikTok tam: {exc}")
            if instagram_path and instagram_path.exists():
                try:
                    instagram_path.unlink()
                    print(f"[ZERNIO] Da xoa file Instagram tam: {instagram_path.name}")
                except OSError as exc:
                    print(f"[CANH BAO] Khong xoa duoc file Instagram tam: {exc}")
            if short_path and short_path.exists():
                try:
                    short_path.unlink()
                    print(f"[ZERNIO] Da xoa file YouTube Short tam: {short_path.name}")
                except OSError as exc:
                    print(f"[CANH BAO] Khong xoa duoc file YouTube Short tam: {exc}")
        if args.delay > 0 and index < len(videos):
            time.sleep(args.delay)
    print("\n[ZERNIO] Hoan tat len lich.")


def main() -> None:
    setup_run_log()
    parser = argparse.ArgumentParser(description="Upload video len Zernio va hen lich random")
    parser.add_argument("--all", action="store_true", help="Len lich tat ca video trong thu muc")
    parser.add_argument("--video", help="Len lich mot video cu the")
    parser.add_argument("--video-dir", default=str(VIDEOS_DIR), help="Thu muc video")
    parser.add_argument("--description-file", default=str(DESCRIPTION_FILE), help="File mo ta")
    parser.add_argument("--media-url-file", default=str(MEDIA_URLS_FILE), help="URL public: moi dong URL hoac ten_file|URL")
    parser.add_argument("--api-key", default="", help="Mot hoac nhieu Zernio API key, cach nhau bang dau phay")
    parser.add_argument("--platforms", default="facebook,instagram,tiktok,youtube")
    parser.add_argument("--account-ids", default="", help="Account ID Zernio, cach nhau bang dau phay; trong = tu lay")
    parser.add_argument("--profile-id", default="", help="Chi dung account trong Zernio profile nay")
    parser.add_argument("--title", default="", help="Tieu de rieng; de trong se lay ten file")
    parser.add_argument("--start-after-minutes", type=int, default=30)
    parser.add_argument("--min-gap-minutes", type=int, default=60)
    parser.add_argument("--max-gap-minutes", type=int, default=180)
    parser.add_argument("--delay", type=int, default=2)
    parser.add_argument("--max-videos", type=int, default=0)
    parser.add_argument("--random-seed", type=int, default=0)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if not args.all and not args.video:
        raise SystemExit("[LOI] Chon --all hoac --video.")
    if args.max_gap_minutes < args.min_gap_minutes:
        args.max_gap_minutes = args.min_gap_minutes
    run(args)


if __name__ == "__main__":
    main()
