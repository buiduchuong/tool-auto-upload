# -*- coding: utf-8 -*-
"""Discover every visible video on Facebook profiles, then download with yt-dlp."""
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
import time
import urllib.parse
from pathlib import Path

import facebook_upload


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_PROFILE_DIR = BASE_DIR / "chrome-profile-facebook"
DEFAULT_ARCHIVE = BASE_DIR / "facebook_archive_video.txt"
DEFAULT_YTDLP = BASE_DIR / ("yt-dlp.exe" if os.name == "nt" else "yt-dlp")
VIDEO_PATH_RE = re.compile(r"/(?:reel|reels|videos)/(?:[^/?#]+/)?(\d+)", re.IGNORECASE)


def profile_sections(url: str) -> list[str]:
    """Turn a Facebook profile URL into its Reels and Videos tabs."""
    value = url.strip()
    if not value:
        return []
    if not urllib.parse.urlparse(value).scheme:
        value = "https://" + value.lstrip("/")
    parsed = urllib.parse.urlparse(value)
    host = parsed.netloc.lower().split(":", 1)[0]
    if host not in {"facebook.com", "www.facebook.com", "m.facebook.com", "web.facebook.com"}:
        raise ValueError(f"Không phải link Facebook: {url}")

    path = re.sub(r"/(?:reels?|videos)(?:/.*)?$", "", parsed.path.rstrip("/"), flags=re.IGNORECASE)
    if path.lower() == "/profile.php":
        query = dict(urllib.parse.parse_qsl(parsed.query, keep_blank_values=True))
        query.pop("sk", None)
        if not query.get("id"):
            raise ValueError(f"Link profile.php thiếu id: {url}")
        root_url = urllib.parse.urlunparse(("https", "www.facebook.com", path, "", urllib.parse.urlencode(query), ""))
        return [root_url] + [
            urllib.parse.urlunparse(("https", "www.facebook.com", path, "", urllib.parse.urlencode({**query, "sk": tab}), ""))
            for tab in ("reels", "videos")
        ]

    if not path or path == "/":
        raise ValueError(f"Hãy nhập link profile/Page Facebook cụ thể: {url}")
    root_url = f"https://www.facebook.com{path}/"
    return [root_url] + [f"https://www.facebook.com{path}/{tab}/" for tab in ("reels", "videos")]


def canonical_video_url(href: str) -> tuple[str, str] | None:
    if not href:
        return None
    absolute = urllib.parse.urljoin("https://www.facebook.com/", href)
    parsed = urllib.parse.urlparse(absolute)
    if not parsed.netloc.lower().endswith("facebook.com"):
        return None
    match = VIDEO_PATH_RE.search(parsed.path)
    if match:
        video_id = match.group(1)
        if "/reel" in parsed.path.lower():
            return video_id, f"https://www.facebook.com/reel/{video_id}"
        return video_id, f"https://www.facebook.com/watch/?v={video_id}"
    query = urllib.parse.parse_qs(parsed.query)
    video_id = (query.get("v") or [""])[0]
    if video_id.isdigit() and parsed.path.lower().rstrip("/") in {"/watch", "/video.php"}:
        return video_id, f"https://www.facebook.com/watch/?v={video_id}"
    return None


def visible_video_urls(driver) -> dict[str, str]:
    hrefs = driver.execute_script(
        "return Array.from(document.querySelectorAll('a[href]'), a => a.href);"
    ) or []
    found: dict[str, str] = {}
    for href in hrefs:
        item = canonical_video_url(str(href))
        if item:
            found[item[0]] = item[1]
    return found


def collect_section(driver, url: str, max_scrolls: int, stagnant_limit: int) -> dict[str, str]:
    print(f"\n[FACEBOOK PROFILE] Đang quét: {url}", flush=True)
    driver.get(url)
    time.sleep(4)
    found: dict[str, str] = {}
    stagnant = 0
    previous_height = 0
    for index in range(max_scrolls):
        before = len(found)
        found.update(visible_video_urls(driver))
        height = int(driver.execute_script("return Math.max(document.body.scrollHeight, document.documentElement.scrollHeight);") or 0)
        if len(found) == before and height == previous_height:
            stagnant += 1
        else:
            stagnant = 0
        if index == 0 or (index + 1) % 5 == 0:
            print(f"[FACEBOOK PROFILE] Lần cuộn {index + 1}: đã thấy {len(found)} video", flush=True)
        if stagnant >= stagnant_limit:
            break
        previous_height = height
        driver.execute_script("window.scrollTo(0, Math.max(document.body.scrollHeight, document.documentElement.scrollHeight));")
        time.sleep(2)
    found.update(visible_video_urls(driver))
    print(f"[FACEBOOK PROFILE] Quét xong tab này: {len(found)} video", flush=True)
    return found


def write_netscape_cookies(driver, path: Path) -> None:
    lines = ["# Netscape HTTP Cookie File", "# Exported temporarily by Mstar Facebook profile downloader", ""]
    for cookie in driver.get_cookies():
        domain = str(cookie.get("domain") or ".facebook.com")
        include_subdomains = "TRUE" if domain.startswith(".") else "FALSE"
        cookie_path = str(cookie.get("path") or "/")
        secure = "TRUE" if cookie.get("secure") else "FALSE"
        expires = int(cookie.get("expiry") or 0)
        name = str(cookie.get("name") or "").replace("\t", "")
        value = str(cookie.get("value") or "").replace("\t", "")
        if name:
            lines.append("\t".join((domain, include_subdomains, cookie_path, secure, str(expires), name, value)))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def split_extra_args(value: str) -> list[str]:
    return shlex.split(value, posix=os.name != "nt") if value.strip() else []


def main() -> int:
    parser = argparse.ArgumentParser(description="Tải toàn bộ video/Reels nhìn thấy trên Facebook profile")
    parser.add_argument("urls", nargs="+", help="Một hoặc nhiều link Facebook profile/Page")
    parser.add_argument("--output-dir", default=str(BASE_DIR / "Facebook_Channel"))
    parser.add_argument("--output-template", default="%(uploader)s/%(upload_date)s_%(id)s.%(ext)s")
    parser.add_argument("--archive-file", default=str(DEFAULT_ARCHIVE))
    parser.add_argument("--profile-dir", default=str(DEFAULT_PROFILE_DIR))
    parser.add_argument("--debug-port", type=int, default=9224)
    parser.add_argument("--yt-dlp", default=str(DEFAULT_YTDLP))
    parser.add_argument("--yt-dlp-command-json", default="")
    parser.add_argument("--ffmpeg-dir", default=str(BASE_DIR))
    parser.add_argument("--extra-args", default="")
    parser.add_argument("--max-scrolls", type=int, default=500)
    parser.add_argument("--stagnant-scrolls", type=int, default=8)
    parser.add_argument("--scan-only", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()

    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    archive_file = Path(args.archive_file).resolve()
    archive_file.parent.mkdir(parents=True, exist_ok=True)

    facebook_upload.PROFILE_DIR = Path(args.profile_dir).resolve()
    facebook_upload.DEBUG_PORT = args.debug_port
    print("[FACEBOOK PROFILE] Đang kết nối Chrome Facebook. Nếu chưa đăng nhập, hãy đăng nhập trong cửa sổ Chrome.", flush=True)
    driver = facebook_upload.build_driver(attach=True)
    cookie_path: Path | None = None
    try:
        all_videos: dict[str, str] = {}
        for profile_url in args.urls:
            for section in profile_sections(profile_url):
                all_videos.update(collect_section(driver, section, max(1, args.max_scrolls), max(2, args.stagnant_scrolls)))
        if not all_videos:
            print("[LỖI] Không tìm thấy video. Hãy kiểm tra đăng nhập, link profile và quyền xem nội dung.", flush=True)
            return 2
        if args.scan_only:
            print(f"[FACEBOOK PROFILE] Kiểm tra quét thành công: {len(all_videos)} video duy nhất.", flush=True)
            for video_url in all_videos.values():
                print(video_url, flush=True)
            return 0
        with tempfile.NamedTemporaryFile(prefix="mstar_facebook_cookies_", suffix=".txt", delete=False) as handle:
            cookie_path = Path(handle.name)
        write_netscape_cookies(driver, cookie_path)
    finally:
        # build_driver(attach=True) connects to the user's persistent Chrome; do not close it.
        try:
            driver.service.stop()
        except Exception:
            pass

    video_urls = list(all_videos.values())
    print(f"\n[FACEBOOK PROFILE] Tổng cộng {len(video_urls)} video duy nhất. Bắt đầu tải...", flush=True)
    ytdlp_command = json.loads(args.yt_dlp_command_json) if args.yt_dlp_command_json else [args.yt_dlp]
    if not isinstance(ytdlp_command, list) or not all(isinstance(item, str) and item for item in ytdlp_command):
        raise ValueError("Lệnh yt-dlp không hợp lệ")
    cmd = ytdlp_command + [
        "--ignore-config",
        "--newline",
        "--ignore-errors",
        "--yes-playlist",
        "--cookies",
        str(cookie_path),
        "-P",
        str(output_dir),
        "-o",
        args.output_template,
        "-f",
        "bv*+ba/b",
        "--merge-output-format",
        "mp4",
        "--remux-video",
        "mp4",
        "--match-filter",
        "vcodec!=none",
        "--download-archive",
        str(archive_file),
        "--sleep-interval",
        "2",
        "--max-sleep-interval",
        "6",
    ]
    if Path(args.ffmpeg_dir).exists():
        cmd.extend(["--ffmpeg-location", args.ffmpeg_dir])
    cmd.extend(split_extra_args(args.extra_args))
    cmd.extend(video_urls)
    try:
        return subprocess.call(cmd)
    finally:
        if cookie_path:
            cookie_path.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
