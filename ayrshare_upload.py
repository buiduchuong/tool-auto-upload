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


BASE_DIR = Path(__file__).resolve().parent
VIDEOS_DIR = BASE_DIR / "videos"
DESCRIPTION_FILE = BASE_DIR / "default_description.txt"
MEDIA_URLS_FILE = BASE_DIR / "ayrshare_media_urls.txt"
VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}
AYRSHARE_API_BASE = "https://api.ayrshare.com/api"
SMALL_MEDIA_LIMIT = 30 * 1024 * 1024
AYRSHARE_LOG_FILE = BASE_DIR / "ayrshare_last_run.log"
FFPROBE_FILE = BASE_DIR / "ffprobe.exe"
FFMPEG_FILE = BASE_DIR / "ffmpeg.exe"
AYRSHARE_TEMP_DIR = BASE_DIR / "ayrshare_upload_temp"
PLATFORM_DURATION_LIMITS = {
    "instagram": 900,
    "tiktok": 600,
}


def setup_run_log() -> None:
    original_print = builtins.print
    try:
        AYRSHARE_LOG_FILE.write_text("", encoding="utf-8")
    except Exception:
        pass

    def tee_print(*args: Any, **kwargs: Any) -> None:
        original_print(*args, **kwargs)
        try:
            text = kwargs.get("sep", " ").join(str(arg) for arg in args)
            end = kwargs.get("end", "\n")
            with AYRSHARE_LOG_FILE.open("a", encoding="utf-8") as handle:
                handle.write(text + end)
        except Exception:
            pass

    builtins.print = tee_print


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8-sig", errors="replace").strip()


def read_media_url_file(path: Path, videos: list[Path]) -> dict[Path, str]:
    if not path.exists():
        return {}
    lines = [line.strip() for line in read_text(path).splitlines() if line.strip() and not line.strip().startswith("#")]
    mapping: dict[Path, str] = {}
    by_name = {video.name.lower(): video for video in videos}
    sequential_urls: list[str] = []
    for line in lines:
        if "|" in line:
            name, url = [part.strip() for part in line.split("|", 1)]
            video = by_name.get(name.lower())
            if video and url:
                mapping[video] = url
        elif line.lower().startswith(("http://", "https://")):
            sequential_urls.append(line)
    for video, url in zip(videos, sequential_urls):
        mapping.setdefault(video, url)
    return mapping


def video_title(path: Path, custom_title: str = "") -> str:
    return custom_title.strip() or path.stem.strip()


def build_post_text(path: Path, description: str, custom_title: str = "") -> str:
    title = video_title(path, custom_title)
    if description:
        return f"{title}\n\n{description}"
    return title


def parse_platforms(value: str) -> list[str]:
    platforms = [item.strip().lower() for item in value.replace(";", ",").split(",") if item.strip()]
    return platforms or ["all"]


def format_duration(seconds: float) -> str:
    total = max(0, int(round(seconds)))
    minutes, secs = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h{minutes:02d}m{secs:02d}s"
    return f"{minutes}m{secs:02d}s"


def ffprobe_command() -> str:
    return str(FFPROBE_FILE if FFPROBE_FILE.exists() else "ffprobe")


def ffmpeg_command() -> str:
    return str(FFMPEG_FILE if FFMPEG_FILE.exists() else "ffmpeg")


def video_duration_seconds(path: Path) -> float | None:
    cmd = [
        ffprobe_command(),
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
    except Exception as exc:
        print(f"[CANH BAO] Khong doc duoc thoi luong bang ffprobe: {exc}")
        return None
    if result.returncode != 0:
        print(f"[CANH BAO] ffprobe loi voi {path.name}: {(result.stderr or result.stdout).strip()[:300]}")
        return None
    try:
        return float((result.stdout or "").strip())
    except ValueError:
        print(f"[CANH BAO] ffprobe khong tra ve thoi luong hop le cho {path.name}: {result.stdout!r}")
        return None


def filter_platforms_by_duration(path: Path, platforms: list[str]) -> list[str]:
    if "all" in platforms:
        print("[CANH BAO] Platforms dang la all nen khong tu loc duoc gioi han TikTok/Instagram theo thoi luong.")
        return platforms
    duration = video_duration_seconds(path)
    if duration is None:
        print("[CANH BAO] Khong biet thoi luong video, giu nguyen platforms.")
        return platforms
    print(f"[AYRSHARE] Thoi luong video: {format_duration(duration)} ({duration:.2f}s)")
    allowed: list[str] = []
    skipped: list[str] = []
    for platform in platforms:
        limit = PLATFORM_DURATION_LIMITS.get(platform)
        if limit is not None and duration > limit:
            skipped.append(f"{platform}>{format_duration(limit)}")
            continue
        allowed.append(platform)
    if skipped:
        print(f"[AYRSHARE] Bo platform do video qua dai: {', '.join(skipped)}")
        print(f"[AYRSHARE] Platforms con lai: {', '.join(allowed) if allowed else '(khong con platform nao)'}")
    return allowed


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
        (p for p in video_dir.rglob("*") if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS),
        key=lambda p: str(p).lower(),
    )
    if not videos:
        raise SystemExit(f"[LOI] Khong co video trong: {video_dir}")
    return videos


def request_json(method: str, url: str, *, api_key: str, **kwargs: Any) -> dict[str, Any]:
    headers = kwargs.pop("headers", {})
    headers["Authorization"] = f"Bearer {api_key}"
    timeout = kwargs.pop("timeout", 300)
    try:
        response = requests.request(method, url, headers=headers, timeout=timeout, **kwargs)
    except requests.RequestException as exc:
        raise RuntimeError(f"Loi ket noi Ayrshare khi goi {url}: {exc}") from exc
    try:
        data = response.json()
    except Exception:
        data = {"raw": response.text}
    if response.status_code >= 400:
        if data.get("code") == 169 or "Paid Plan Required" in str(data):
            raise RuntimeError(
                "Ayrshare tu choi goi API nay vi tai khoan chua co quyen Premium/Business "
                f"(HTTP {response.status_code}): {json.dumps(data, ensure_ascii=False)}"
            )
        if data.get("code") == 276 or "suspended" in str(data).lower():
            raise RuntimeError(
                "Da nhan API key, nhung Ayrshare bao tai khoan/profile dang bi suspended "
                "nen khong the upload hoac len lich. "
                "Neu ban dang nhap RefId vao o API key thi hay doi sang API Key that trong trang API Key "
                "cua Ayrshare dashboard. RefId khong phai API key. Neu da dung dung API Key, hay vao "
                "Ayrshare dashboard de reactivate profile, kiem tra billing/quyen tai khoan, "
                f"hoac doi API key/profile khac (HTTP {response.status_code}): "
                f"{json.dumps(data, ensure_ascii=False)}"
            )
        raise RuntimeError(f"HTTP {response.status_code}: {json.dumps(data, ensure_ascii=False)}")
    return data


def looks_like_ayrshare_ref_id(value: str) -> bool:
    return bool(re.fullmatch(r"[a-fA-F0-9]{40}", value.strip()))


def validate_ayrshare_account(api_key: str) -> None:
    print("[AYRSHARE] Kiem tra API key/profile truoc khi xu ly video")
    data = request_json(
        "GET",
        f"{AYRSHARE_API_BASE}/user",
        api_key=api_key,
        timeout=(15, 30),
    )
    status = str(data.get("status") or "").lower()
    if status == "error":
        raise RuntimeError(f"Ayrshare /user bao loi: {json.dumps(data, ensure_ascii=False)}")


def safe_upload_name(path: Path) -> str:
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", path.stem).strip("._-") or "video"
    suffix = path.suffix.lower() or ".mp4"
    return f"{stem[:80]}{suffix}"


def upload_small_media(path: Path, api_key: str) -> str:
    upload_name = safe_upload_name(path)
    size_mb = path.stat().st_size / 1024 / 1024
    print(f"[AYRSHARE] Upload media nho: {path.name} ({size_mb:.2f} MB) -> {upload_name}")
    with path.open("rb") as handle:
        data = request_json(
            "POST",
            f"{AYRSHARE_API_BASE}/media/upload",
            api_key=api_key,
            files={"file": (upload_name, handle, mimetypes.guess_type(upload_name)[0] or "video/mp4")},
            data={"fileName": upload_name, "description": path.stem[:200]},
            timeout=(30, 120),
        )
    print("[AYRSHARE] Upload media nho response:", json.dumps(data, ensure_ascii=False))
    url = str(data.get("url") or data.get("accessUrl") or "").strip()
    if not url:
        raise RuntimeError(f"Ayrshare khong tra ve media URL: {json.dumps(data, ensure_ascii=False)}")
    return url


def upload_large_media(path: Path, api_key: str) -> str:
    content_type = path.suffix.lower().lstrip(".") or "mp4"
    print(f"[AYRSHARE] Tao uploadUrl cho video lon: {path.name}")
    data = request_json(
        "GET",
        f"{AYRSHARE_API_BASE}/media/uploadUrl",
        api_key=api_key,
        params={"fileName": path.name, "contentType": content_type},
    )
    upload_url = str(data.get("uploadUrl") or data.get("uploadURL") or "").strip()
    access_url = str(data.get("accessUrl") or data.get("accessURL") or "").strip()
    signed_content_type = str(data.get("contentType") or mimetypes.guess_type(path.name)[0] or "video/mp4")
    if not upload_url or not access_url:
        raise RuntimeError(f"Thieu uploadUrl/accessUrl: {json.dumps(data, ensure_ascii=False)}")
    print(f"[AYRSHARE] Dang PUT file len signed URL: {path.name}")
    with path.open("rb") as handle:
        response = requests.put(upload_url, data=handle, headers={"Content-Type": signed_content_type}, timeout=3600)
    if response.status_code >= 400:
        raise RuntimeError(f"Upload signed URL loi HTTP {response.status_code}: {response.text[:500]}")
    verify_media_url(access_url, api_key)
    return access_url


def compress_for_small_upload(path: Path) -> Path:
    duration = video_duration_seconds(path)
    if not duration or duration <= 0:
        raise RuntimeError("Khong doc duoc thoi luong video de nen xuong duoi 30 MB.")
    AYRSHARE_TEMP_DIR.mkdir(parents=True, exist_ok=True)
    output = AYRSHARE_TEMP_DIR / f"{path.stem}_ayrshare_30mb.mp4"
    target_size_mb = 9
    audio_bitrate_kbps = 64
    total_bitrate_kbps = max(180, int((target_size_mb * 8192) / duration))
    video_bitrate_kbps = max(120, total_bitrate_kbps - audio_bitrate_kbps)
    print(
        "[AYRSHARE] Tai khoan bi chan upload video lon, "
        f"nen ban tam duoi 30 MB: {output.name}"
    )
    cmd = [
        ffmpeg_command(),
        "-y",
        "-i",
        str(path),
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-b:v",
        f"{video_bitrate_kbps}k",
        "-maxrate",
        f"{video_bitrate_kbps}k",
        "-bufsize",
        f"{video_bitrate_kbps * 2}k",
        "-vf",
        "scale='min(1080,iw)':-2",
        "-c:a",
        "aac",
        "-b:a",
        f"{audio_bitrate_kbps}k",
        "-movflags",
        "+faststart",
        str(output),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg nen video loi: {(result.stderr or result.stdout).strip()[:800]}")
    if output.stat().st_size > SMALL_MEDIA_LIMIT:
        raise RuntimeError(
            f"Video sau khi nen van qua 30 MB ({output.stat().st_size / 1024 / 1024:.2f} MB)."
        )
    print(f"[AYRSHARE] Da nen xong: {output.stat().st_size / 1024 / 1024:.2f} MB")
    return output


def verify_media_url(media_url: str, api_key: str) -> None:
    print("[AYRSHARE] Kiem tra media URL sau khi upload")
    data = request_json(
        "POST",
        f"{AYRSHARE_API_BASE}/media/urlExists",
        api_key=api_key,
        headers={"Content-Type": "application/json"},
        json={"mediaUrl": media_url},
    )
    status_code = int(data.get("statusCode") or data.get("code") or 0)
    if status_code and status_code >= 400:
        raise RuntimeError(f"Media URL chua san sang: {json.dumps(data, ensure_ascii=False)}")


def upload_media(path: Path, api_key: str) -> str:
    if path.stat().st_size <= SMALL_MEDIA_LIMIT:
        return upload_small_media(path, api_key)
    try:
        return upload_large_media(path, api_key)
    except RuntimeError as exc:
        if "Paid Plan Required" not in str(exc) and "chua co quyen Premium/Business" not in str(exc):
            raise
        raise RuntimeError(
            f"{exc}\n[GOI Y] API key nay khong duoc phep upload media len Ayrshare. "
            f"Hay dan URL public truc tiep cua video vao {MEDIA_URLS_FILE.name}, moi dong mot URL "
            "hoac dang theo dang ten_file|URL, roi chay lai. Cach khac la nang goi Ayrshare."
        ) from exc


def schedule_post(
    path: Path,
    media_url: str,
    schedule_date: datetime,
    api_key: str,
    platforms: list[str],
    description: str,
    custom_title: str,
    validate_scheduled: bool,
) -> dict[str, Any]:
    title = video_title(path, custom_title)
    payload: dict[str, Any] = {
        "post": build_post_text(path, description, custom_title),
        "platforms": platforms,
        "mediaUrls": [media_url],
        "isVideo": True,
        "scheduleDate": schedule_date.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "validateScheduled": validate_scheduled,
        "youTubeOptions": {
            "title": title[:100],
            "visibility": "public",
            "madeForKids": False,
        },
    }
    print(f"[AYRSHARE] Hen lich {path.name}: {payload['scheduleDate']} UTC")
    return request_json(
        "POST",
        f"{AYRSHARE_API_BASE}/post",
        api_key=api_key,
        headers={"Content-Type": "application/json"},
        json=payload,
    )


def run(args: argparse.Namespace) -> None:
    api_key = (args.api_key or os.environ.get("AYRSHARE_API_KEY") or "").strip()
    if not api_key and not args.dry_run:
        raise SystemExit("[LOI] Thieu Ayrshare API key. Nhap trong panel hoac set AYRSHARE_API_KEY.")
    if api_key and looks_like_ayrshare_ref_id(api_key):
        print(
            "[CANH BAO] Gia tri API key trong panel giong RefId cua Ayrshare, khong phai API Key. "
            "Hay vao Ayrshare Dashboard > API Key va copy API Key that."
        )
    if api_key and not args.dry_run:
        validate_ayrshare_account(api_key)
    video_dir = Path(args.video_dir)
    if not video_dir.is_absolute():
        video_dir = BASE_DIR / video_dir
    videos = collect_videos(video_dir, args.video)
    if args.max_videos > 0:
        videos = videos[: args.max_videos]
    description = read_text(Path(args.description_file))
    media_url_file = Path(args.media_url_file)
    if not media_url_file.is_absolute():
        media_url_file = BASE_DIR / media_url_file
    media_url_map = read_media_url_file(media_url_file, videos)
    platforms = parse_platforms(args.platforms)
    current_date = datetime.now(timezone.utc) + timedelta(minutes=max(0, args.start_after_minutes))
    random.seed(args.random_seed or None)

    print(f"[AYRSHARE] Se len lich {len(videos)} video len: {', '.join(platforms)}")
    for index, video in enumerate(videos, start=1):
        if index > 1:
            current_date += timedelta(minutes=random.randint(args.min_gap_minutes, args.max_gap_minutes))
        print(f"\n[TIEN DO] {index}/{len(videos)}: {video.name}")
        effective_platforms = filter_platforms_by_duration(video, platforms)
        if not effective_platforms:
            print("[BO QUA] Video khong con platform hop le sau khi loc thoi luong.")
            continue
        if args.dry_run:
            print(f"[DRY RUN] Platforms: {', '.join(effective_platforms)}")
            print(f"[DRY RUN] {current_date.strftime('%Y-%m-%dT%H:%M:%SZ')} UTC")
            continue
        media_url = media_url_map.get(video)
        if media_url:
            print(f"[AYRSHARE] Dung media URL co san cho {video.name}: {media_url}")
        else:
            media_url = upload_media(video, api_key)
        result = schedule_post(
            video,
            media_url,
            current_date,
            api_key,
            effective_platforms,
            description,
            args.title,
            not args.no_validate_scheduled,
        )
        print("[OK] Ayrshare response:", json.dumps(result, ensure_ascii=False))
        if args.delay > 0 and index < len(videos):
            time.sleep(args.delay)
    print("\n[AYRSHARE] Hoan tat len lich.")


def main() -> None:
    setup_run_log()
    parser = argparse.ArgumentParser(description="Upload video len Ayrshare va hen lich random")
    parser.add_argument("--all", action="store_true", help="Len lich tat ca video trong thu muc")
    parser.add_argument("--video", help="Len lich mot video cu the")
    parser.add_argument("--video-dir", default=str(VIDEOS_DIR), help="Thu muc video")
    parser.add_argument("--description-file", default=str(DESCRIPTION_FILE), help="File mo ta")
    parser.add_argument("--media-url-file", default=str(MEDIA_URLS_FILE), help="File URL public video; moi dong URL hoac ten_file|URL")
    parser.add_argument("--api-key", default="", help="Ayrshare API key")
    parser.add_argument("--platforms", default="facebook,instagram,tiktok,youtube", help="VD: facebook,instagram,tiktok,youtube hoac all")
    parser.add_argument("--title", default="", help="Tieu de/caption rieng; de trong se lay ten file")
    parser.add_argument("--start-after-minutes", type=int, default=30, help="Video dau tien dang sau bao nhieu phut")
    parser.add_argument("--min-gap-minutes", type=int, default=60, help="Khoang cach random toi thieu giua 2 video")
    parser.add_argument("--max-gap-minutes", type=int, default=180, help="Khoang cach random toi da giua 2 video")
    parser.add_argument("--delay", type=int, default=2, help="Nghi giua cac lenh API")
    parser.add_argument("--max-videos", type=int, default=0, help="Gioi han so video xu ly moi lan; 0 la khong gioi han")
    parser.add_argument("--random-seed", type=int, default=0, help="Seed de test lich random")
    parser.add_argument("--no-validate-scheduled", action="store_true", help="Tat validateScheduled")
    parser.add_argument("--dry-run", action="store_true", help="Chi xem lich, khong goi API")
    args = parser.parse_args()
    if not args.all and not args.video:
        raise SystemExit("[LOI] Chon --all hoac --video.")
    if args.max_gap_minutes < args.min_gap_minutes:
        args.max_gap_minutes = args.min_gap_minutes
    run(args)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
