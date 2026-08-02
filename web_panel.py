# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import secrets
import shlex
import shutil
import subprocess
import sys
import threading
import time
import urllib.parse
import base64
import hmac
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "web_static"
VIDEOS_DIR = BASE_DIR / "videos"
TIKTOK_DOWNLOAD_DIR = BASE_DIR / "TikTok_Channel"
DESCRIPTION_FILE = BASE_DIR / "default_description.txt"
TIKTOK_DESCRIPTION_FILE = BASE_DIR / "tiktok_description.txt"
FACEBOOK_DESCRIPTION_FILE = BASE_DIR / "facebook_description.txt"
INSTAGRAM_DESCRIPTION_FILE = BASE_DIR / "instagram_description.txt"
TITLE_HASHTAGS_FILE = BASE_DIR / "title_hashtags.txt"
DESCRIPTION_HASHTAGS_FILE = BASE_DIR / "description_hashtags.txt"
PANEL_SETTINGS_FILE = BASE_DIR / "panel_settings.json"
MAIN_FILE = BASE_DIR / "main.py"
TIKTOK_UPLOAD_FILE = BASE_DIR / "tiktok_upload.py"
FACEBOOK_UPLOAD_FILE = BASE_DIR / "facebook_upload.py"
INSTAGRAM_UPLOAD_FILE = BASE_DIR / "instagram_upload.py"
AYRSHARE_UPLOAD_FILE = BASE_DIR / "ayrshare_upload.py"
ZERNIO_UPLOAD_FILE = BASE_DIR / "zernio_upload.py"
YTDLP_FILE = BASE_DIR / "yt-dlp.exe"
LOCAL_FFMPEG_FILE = BASE_DIR / "ffmpeg.exe"
YOUTUBE_PROFILE_DIR = BASE_DIR / "chrome-profile"
TIKTOK_PROFILE_DIR = BASE_DIR / "chrome-profile-tiktok"
FACEBOOK_PROFILE_DIR = BASE_DIR / "chrome-profile-facebook"
INSTAGRAM_PROFILE_DIR = BASE_DIR / "chrome-profile-instagram"
TIKTOK_ARCHIVE_FILE = BASE_DIR / "archive_video.txt"
DELETED_VIDEOS_DIR = BASE_DIR / "deleted_videos"
WEB_PANEL_URL_FILE = BASE_DIR / "web_panel_url.txt"

YOUTUBE_DEBUG_PORT = 9222
TIKTOK_DEBUG_PORT = 9223
FACEBOOK_DEBUG_PORT = 9224
INSTAGRAM_DEBUG_PORT = 9225
VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}
MAX_LOG_LINES = 200
GROUPS = ("youtube", "tiktok", "facebook", "instagram", "ayrshare", "zernio", "download")


def console_log(message: str) -> None:
    try:
        print(message)
    except OSError:
        pass


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8-sig")
    except Exception:
        return path.read_text(encoding="utf-8", errors="replace")


def write_text(path: Path, text: str) -> None:
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def resolve_path(value: str | None, default_path: Path) -> Path:
    if not value:
        return default_path
    path = Path(value)
    if not path.is_absolute():
        path = BASE_DIR / path
    return path


def path_for_command(path: Path) -> str:
    try:
        return str(path.relative_to(BASE_DIR))
    except ValueError:
        return str(path)


def video_rows(directory: Path) -> list[dict[str, Any]]:
    directory.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    for path in sorted(
        (p for p in directory.rglob("*") if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS),
        key=lambda p: str(p).lower(),
    ):
        try:
            stat = path.stat()
        except OSError:
            continue
        rows.append(
            {
                "name": path.name,
                "path": str(path),
                "relative_path": path_for_command(path),
                "size": stat.st_size,
                "modified": stat.st_mtime,
            }
        )
    return rows


def is_relative_to_path(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def unique_deleted_target(source: Path) -> Path:
    day_dir = DELETED_VIDEOS_DIR / time.strftime("%Y%m%d")
    day_dir.mkdir(parents=True, exist_ok=True)
    target = day_dir / source.name
    if not target.exists():
        return target
    counter = 1
    while True:
        candidate = day_dir / f"{source.stem} ({counter}){source.suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def allowed_video_roots(settings: dict[str, Any]) -> list[Path]:
    roots = [
        VIDEOS_DIR,
        TIKTOK_DOWNLOAD_DIR,
        BASE_DIR / "uploaded_success",
        BASE_DIR / "uploaded_facebook_success",
        BASE_DIR / "uploaded_tiktok_success",
        BASE_DIR / "uploaded_instagram_success",
    ]
    for platform in ("youtube", "tiktok", "facebook", "instagram", "ayrshare", "zernio"):
        upload_dir = settings.get(platform, {}).get("upload_dir")
        if upload_dir:
            roots.append(resolve_path(str(upload_dir), VIDEOS_DIR))
        for account in settings.get("accounts", {}).get(platform, {}).get("items", []):
            if isinstance(account, dict) and account.get("upload_dir"):
                roots.append(resolve_path(str(account["upload_dir"]), VIDEOS_DIR))
    resolved: list[Path] = []
    for root in roots:
        try:
            candidate = root.resolve()
        except OSError:
            candidate = root.absolute()
        if candidate not in resolved:
            resolved.append(candidate)
    return resolved


def delete_video_file(path_value: str, *, permanent: bool = False) -> dict[str, Any]:
    if not path_value:
        raise RuntimeError("Chưa truyền đường dẫn video cần xóa.")
    settings = load_settings(include_token=True)
    path = resolve_path(path_value, VIDEOS_DIR).resolve()
    if not path.exists() or not path.is_file():
        raise RuntimeError(f"Không thấy file video: {path}")
    if path.suffix.lower() not in VIDEO_EXTENSIONS:
        raise RuntimeError("Chỉ cho phép xóa file video.")
    if not any(is_relative_to_path(path, root) for root in allowed_video_roots(settings)):
        raise RuntimeError("Đường dẫn không nằm trong thư mục video của tool, từ chối xóa.")
    if permanent:
        path.unlink()
        return {"ok": True, "deleted": str(path), "permanent": True}
    target = unique_deleted_target(path)
    shutil.move(str(path), str(target))
    return {"ok": True, "deleted": str(path), "moved_to": str(target), "permanent": False}


def default_settings() -> dict[str, Any]:
    return {
        "youtube": {
            "upload_dir": str(VIDEOS_DIR),
            "visibility": "public",
            "made_for_kids": "no",
            "delay": "2",
            "attach": True,
            "custom_title": "",
        },
        "tiktok": {
            "upload_dir": str(TIKTOK_DOWNLOAD_DIR),
            "delay": "5",
            "attach": True,
            "custom_title": "",
        },
        "facebook": {
            "upload_dir": str(VIDEOS_DIR),
            "mode": "reels-api",
            "target_url": "https://www.facebook.com",
            "page_id": "",
            "page_token": "",
            "api_version": "v23.0",
            "delay": "10",
            "attach": True,
            "custom_title": "",
        },
        "instagram": {
            "upload_dir": str(VIDEOS_DIR),
            "delay": "5",
            "attach": True,
            "custom_title": "",
        },
        "ayrshare": {
            "upload_dir": str(VIDEOS_DIR),
            "api_key": "",
            "platforms": "facebook,instagram,tiktok,youtube",
            "custom_title": "",
            "start_after_minutes": "30",
            "min_gap_minutes": "60",
            "max_gap_minutes": "180",
            "max_videos": "3",
        },
        "zernio": {
            "upload_dir": str(VIDEOS_DIR),
            "api_key": "",
            "platforms": "facebook,instagram,tiktok,youtube",
            "account_ids": "",
            "profile_id": "",
            "custom_title": "",
            "start_after_minutes": "30",
            "min_gap_minutes": "60",
            "max_gap_minutes": "180",
            "max_videos": "3",
        },
        "download": {
            "download_dir": str(VIDEOS_DIR),
            "format": "full_hd_1080",
            "output_template": "%(title).200s.%(ext)s",
            "allow_playlist": True,
            "extra_args": "",
        },
        "accounts": {
            "youtube": {
                "selected": "youtube_main",
                "items": [
                    {
                        "id": "youtube_main",
                        "name": "YouTube 1",
                        "profile_dir": str(YOUTUBE_PROFILE_DIR),
                        "debug_port": YOUTUBE_DEBUG_PORT,
                        "upload_dir": str(VIDEOS_DIR),
                    }
                ],
            },
            "tiktok": {
                "selected": "tiktok_main",
                "items": [
                    {
                        "id": "tiktok_main",
                        "name": "TikTok 1",
                        "profile_dir": str(TIKTOK_PROFILE_DIR),
                        "debug_port": TIKTOK_DEBUG_PORT,
                        "upload_dir": str(TIKTOK_DOWNLOAD_DIR),
                    }
                ],
            },
            "facebook": {
                "selected": "facebook_main",
                "items": [
                    {
                        "id": "facebook_main",
                        "name": "Facebook 1",
                        "profile_dir": str(FACEBOOK_PROFILE_DIR),
                        "debug_port": FACEBOOK_DEBUG_PORT,
                        "upload_dir": str(VIDEOS_DIR),
                        "mode": "browser",
                        "target_url": "https://www.facebook.com",
                        "page_id": "",
                        "page_token": "",
                        "api_version": "v23.0",
                    }
                ],
            },
            "instagram": {
                "selected": "instagram_main",
                "items": [
                    {
                        "id": "instagram_main",
                        "name": "Instagram 1",
                        "profile_dir": str(INSTAGRAM_PROFILE_DIR),
                        "debug_port": INSTAGRAM_DEBUG_PORT,
                        "upload_dir": str(VIDEOS_DIR),
                    }
                ],
            },
        },
        "api": {
            "token": "",
        },
        "web_auth": {
            "username": "admin",
            "password": "",
        },
    }


def load_settings(include_token: bool = False) -> dict[str, Any]:
    settings = default_settings()
    if PANEL_SETTINGS_FILE.exists():
        try:
            saved = json.loads(PANEL_SETTINGS_FILE.read_text(encoding="utf-8"))
            for section, values in saved.items():
                if isinstance(values, dict) and section in settings:
                    settings[section].update(values)
        except Exception:
            pass
    normalize_accounts(settings)
    facebook_token = settings["facebook"].get("page_token", "")
    settings["facebook"]["page_token_saved"] = bool(facebook_token)
    if not include_token and facebook_token:
        settings["facebook"]["page_token"] = ""
    for account in settings.get("accounts", {}).get("facebook", {}).get("items", []):
        token = account.get("page_token", "")
        account["page_token_saved"] = bool(token)
        if not include_token and token:
            account["page_token"] = ""
    if not include_token and settings.get("api", {}).get("token"):
        settings["api"]["token"] = ""
    ayrshare_key = settings.get("ayrshare", {}).get("api_key", "")
    settings.setdefault("ayrshare", {})["api_key_saved"] = bool(ayrshare_key)
    if not include_token and ayrshare_key:
        settings["ayrshare"]["api_key"] = ""
    zernio_key = settings.get("zernio", {}).get("api_key", "")
    settings.setdefault("zernio", {})["api_key_saved"] = bool(zernio_key)
    if not include_token and zernio_key:
        settings["zernio"]["api_key"] = ""
    if not include_token and settings.get("web_auth", {}).get("password"):
        settings["web_auth"]["password"] = ""
    return settings


def save_settings(new_settings: dict[str, Any]) -> dict[str, Any]:
    current = load_settings(include_token=True)
    for section, values in new_settings.items():
        if section not in current or not isinstance(values, dict):
            continue
        if section == "accounts":
            merge_accounts(current, values)
            continue
        if section == "api":
            if str(values.get("token") or "").strip():
                current["api"]["token"] = str(values["token"]).strip()
            continue
        if section == "web_auth":
            if str(values.get("username") or "").strip():
                current["web_auth"]["username"] = str(values["username"]).strip()
            if str(values.get("password") or "").strip():
                current["web_auth"]["password"] = str(values["password"]).strip()
            continue
        for key, value in values.items():
            if section == "facebook" and key == "page_token" and not str(value).strip():
                continue
            if section == "ayrshare" and key == "api_key" and not str(value).strip():
                continue
            if section == "zernio" and key == "api_key" and not str(value).strip():
                continue
            current[section][key] = value
    current["facebook"].pop("page_token_saved", None)
    current.get("ayrshare", {}).pop("api_key_saved", None)
    current.get("zernio", {}).pop("api_key_saved", None)
    for account in current.get("accounts", {}).get("facebook", {}).get("items", []):
        account.pop("page_token_saved", None)
    PANEL_SETTINGS_FILE.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
    return load_settings()


def ensure_gpt_api_token() -> str:
    env_token = os.environ.get("WEB_PANEL_API_TOKEN", "").strip()
    if env_token:
        return env_token
    current = load_settings(include_token=True)
    token = str(current.get("api", {}).get("token") or "").strip()
    if token:
        return token
    token = secrets.token_urlsafe(32)
    current.setdefault("api", {})["token"] = token
    PANEL_SETTINGS_FILE.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
    return token


def ensure_web_auth() -> tuple[str, str]:
    env_user = os.environ.get("WEB_PANEL_USERNAME", "").strip()
    env_password = os.environ.get("WEB_PANEL_PASSWORD", "").strip()
    if env_password:
        return env_user or "admin", env_password
    current = load_settings(include_token=True)
    auth = current.setdefault("web_auth", {})
    username = str(auth.get("username") or "admin").strip() or "admin"
    password = str(auth.get("password") or "").strip()
    if not password:
        password = secrets.token_urlsafe(18)
        auth["username"] = username
        auth["password"] = password
        PANEL_SETTINGS_FILE.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
    return username, password


def normalize_account_id(value: str, fallback: str) -> str:
    safe = "".join(ch.lower() if ch.isalnum() else "_" for ch in (value or "").strip())
    safe = "_".join(part for part in safe.split("_") if part)
    return safe or fallback


def normalize_accounts(settings: dict[str, Any]) -> None:
    defaults = default_settings()["accounts"]
    accounts = settings.setdefault("accounts", {})
    for platform, default_group in defaults.items():
        group = accounts.setdefault(platform, {})
        items = group.get("items")
        if not isinstance(items, list) or not items:
            group["items"] = [dict(default_group["items"][0])]
        for index, account in enumerate(group["items"], start=1):
            if not isinstance(account, dict):
                continue
            fallback_id = f"{platform}_{index}"
            account["id"] = normalize_account_id(str(account.get("id") or account.get("name") or ""), fallback_id)
            account.setdefault("name", f"{platform.title()} {index}")
            account.setdefault("profile_dir", str(BASE_DIR / "accounts" / platform / account["id"] / "chrome-profile"))
            if platform == "youtube":
                account.setdefault("debug_port", YOUTUBE_DEBUG_PORT + index - 1)
                account.setdefault("upload_dir", settings.get("youtube", {}).get("upload_dir", str(VIDEOS_DIR)))
            elif platform == "tiktok":
                account.setdefault("debug_port", TIKTOK_DEBUG_PORT + index - 1)
                account.setdefault("upload_dir", settings.get("tiktok", {}).get("upload_dir", str(TIKTOK_DOWNLOAD_DIR)))
            elif platform == "facebook":
                account.setdefault("debug_port", FACEBOOK_DEBUG_PORT + index - 1)
                account.setdefault("upload_dir", settings.get("facebook", {}).get("upload_dir", str(VIDEOS_DIR)))
                account.setdefault("mode", settings.get("facebook", {}).get("mode", "browser"))
                account.setdefault("target_url", settings.get("facebook", {}).get("target_url", "https://www.facebook.com"))
                account.setdefault("page_id", settings.get("facebook", {}).get("page_id", ""))
                account.setdefault("page_token", settings.get("facebook", {}).get("page_token", ""))
                account.setdefault("api_version", settings.get("facebook", {}).get("api_version", "v23.0"))
            elif platform == "instagram":
                account.setdefault("debug_port", INSTAGRAM_DEBUG_PORT + index - 1)
                account.setdefault("upload_dir", settings.get("instagram", {}).get("upload_dir", str(VIDEOS_DIR)))
        selected = str(group.get("selected") or "")
        ids = {str(item.get("id")) for item in group["items"] if isinstance(item, dict)}
        if selected not in ids:
            group["selected"] = group["items"][0]["id"]


def merge_accounts(current: dict[str, Any], incoming: dict[str, Any]) -> None:
    current_accounts = current.setdefault("accounts", {})
    old_tokens = {
        account.get("id"): account.get("page_token", "")
        for account in current_accounts.get("facebook", {}).get("items", [])
        if isinstance(account, dict)
    }
    for platform, group in incoming.items():
        if not isinstance(group, dict):
            continue
        target = current_accounts.setdefault(platform, {})
        if "selected" in group:
            target["selected"] = group["selected"]
        if isinstance(group.get("items"), list):
            target["items"] = group["items"]
    normalize_accounts(current)
    for account in current_accounts.get("facebook", {}).get("items", []):
        if not isinstance(account, dict):
            continue
        if not str(account.get("page_token", "")).strip():
            account_id = account.get("id")
            if old_tokens.get(account_id):
                account["page_token"] = old_tokens[account_id]


def selected_account(platform: str, settings: dict[str, Any], account_id: str | None = None) -> dict[str, Any]:
    group = settings.get("accounts", {}).get(platform, {})
    requested = account_id or group.get("selected")
    for account in group.get("items", []):
        if str(account.get("id")) == str(requested):
            return dict(account)
    items = group.get("items", [])
    if items:
        return dict(items[0])
    raise RuntimeError(f"Chưa cấu hình account cho {platform}.")


def account_chrome_args(account: dict[str, Any], default_profile: Path, default_port: int) -> list[str]:
    profile_dir = resolve_path(str(account.get("profile_dir") or ""), default_profile)
    debug_port = int(account.get("debug_port") or default_port)
    return chrome_args(profile_dir, debug_port)


def script_cmd(script_path: Path) -> list[str]:
    if getattr(sys, "frozen", False):
        return [sys.executable, "--run-script", str(script_path)]
    return [sys.executable, "-u", str(script_path)]


def ytdlp_cmd() -> list[str] | None:
    if YTDLP_FILE.exists() and os.name == "nt":
        return [str(YTDLP_FILE)]
    executable = shutil.which("yt-dlp")
    if executable:
        return [executable]
    try:
        subprocess.run(
            [sys.executable, "-m", "yt_dlp", "--version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=10,
            check=True,
        )
        return [sys.executable, "-m", "yt_dlp"]
    except Exception:
        return None


def ffmpeg_location_args() -> list[str]:
    if LOCAL_FFMPEG_FILE.exists() and os.name == "nt":
        return ["--ffmpeg-location", str(BASE_DIR)]
    executable = shutil.which("ffmpeg")
    if executable:
        return ["--ffmpeg-location", str(Path(executable).resolve().parent)]
    return []


def chrome_args(profile_dir: Path, debug_port: int) -> list[str]:
    return ["--profile-dir", str(profile_dir), "--debug-port", str(debug_port)]


def safe_int(value: Any, default: int) -> str:
    try:
        return str(max(0, int(str(value).strip())))
    except Exception:
        return str(default)


class JobManager:
    def __init__(self) -> None:
        self.lock = threading.RLock()
        self.processes: dict[str, subprocess.Popen[str]] = {}
        self.logs: dict[str, list[str]] = {group: [] for group in GROUPS}
        self.status: dict[str, dict[str, Any]] = {
            group: {"running": False, "exit_code": None, "started_at": None, "ended_at": None}
            for group in GROUPS
        }

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            return {
                "groups": self.status,
                "logs": {group: "".join(lines[-MAX_LOG_LINES:]) for group, lines in self.logs.items()},
            }

    def append_log(self, group: str, line: str) -> None:
        with self.lock:
            self.logs.setdefault(group, []).append(line)
            if len(self.logs[group]) > MAX_LOG_LINES:
                self.logs[group] = self.logs[group][-MAX_LOG_LINES:]

    def start(self, group: str, cmd: list[str]) -> None:
        with self.lock:
            process = self.processes.get(group)
            if process and process.poll() is None:
                raise RuntimeError(f"Nhóm {group} đang chạy, hãy dừng hoặc đợi xong.")
            self.logs[group] = []
            self.status[group] = {"running": True, "exit_code": None, "started_at": time.time(), "ended_at": None}
            self.append_log(group, "\n[WEB PANEL] Chạy lệnh:\n" + format_command(cmd) + "\n\n")
        threading.Thread(target=self._worker, args=(group, cmd), daemon=True).start()

    def start_sequence(self, group: str, jobs_to_run: list[tuple[str, list[str]]]) -> None:
        if not jobs_to_run:
            raise RuntimeError("Chưa chọn account để chạy.")
        with self.lock:
            process = self.processes.get(group)
            if process and process.poll() is None:
                raise RuntimeError(f"Nhóm {group} đang chạy, hãy dừng hoặc đợi xong.")
            self.logs[group] = []
            self.status[group] = {"running": True, "exit_code": None, "started_at": time.time(), "ended_at": None}
            self.append_log(group, f"\n[WEB PANEL] Bắt đầu chạy tuần tự {len(jobs_to_run)} account.\n")
        threading.Thread(target=self._sequence_worker, args=(group, jobs_to_run), daemon=True).start()

    def _worker(self, group: str, cmd: list[str]) -> None:
        process: subprocess.Popen[str] | None = None
        code: int | None = None
        try:
            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "utf-8"
            process = subprocess.Popen(
                cmd,
                cwd=str(BASE_DIR),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                env=env,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
            )
            with self.lock:
                self.processes[group] = process
            assert process.stdout is not None
            for line in process.stdout:
                self.append_log(group, line)
            code = process.wait()
            self.append_log(group, f"\n[WEB PANEL] Tiến trình kết thúc với mã {code}.\n")
        except Exception as exc:
            self.append_log(group, f"\n[WEB PANEL] Lỗi khi chạy lệnh: {exc}\n")
        finally:
            with self.lock:
                current = self.processes.get(group)
                if process is not None and current is process:
                    self.processes.pop(group, None)
                self.status[group] = {
                    "running": False,
                    "exit_code": code,
                    "started_at": self.status.get(group, {}).get("started_at"),
                    "ended_at": time.time(),
                }

    def _sequence_worker(self, group: str, jobs_to_run: list[tuple[str, list[str]]]) -> None:
        final_code = 0
        try:
            for index, (label, cmd) in enumerate(jobs_to_run, start=1):
                with self.lock:
                    self.append_log(group, f"\n[WEB PANEL] Account {index}/{len(jobs_to_run)}: {label}\n")
                code = self._run_process_sync(group, cmd)
                if code != 0:
                    final_code = code
                    self.append_log(group, f"\n[WEB PANEL] Dừng chuỗi vì account {label} kết thúc với mã {code}.\n")
                    break
        except Exception as exc:
            final_code = 1
            self.append_log(group, f"\n[WEB PANEL] Lỗi chuỗi account: {exc}\n")
        finally:
            with self.lock:
                self.processes.pop(group, None)
                self.status[group] = {
                    "running": False,
                    "exit_code": final_code,
                    "started_at": self.status.get(group, {}).get("started_at"),
                    "ended_at": time.time(),
                }

    def _run_process_sync(self, group: str, cmd: list[str]) -> int:
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        self.append_log(group, "\n[WEB PANEL] Chạy lệnh:\n" + format_command(cmd) + "\n\n")
        process = subprocess.Popen(
            cmd,
            cwd=str(BASE_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=env,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        with self.lock:
            self.processes[group] = process
        assert process.stdout is not None
        for line in process.stdout:
            self.append_log(group, line)
        code = process.wait()
        self.append_log(group, f"\n[WEB PANEL] Tiến trình kết thúc với mã {code}.\n")
        return code

    def stop(self, group: str | None = None) -> list[str]:
        stopped: list[str] = []
        targets = [group] if group else list(GROUPS)
        with self.lock:
            for name in targets:
                process = self.processes.get(name)
                if process and process.poll() is None:
                    process.terminate()
                    stopped.append(name)
                    self.append_log(name, "\n[WEB PANEL] Đã gửi lệnh dừng tiến trình.\n")
        return stopped


jobs = JobManager()


def format_command(cmd: list[str]) -> str:
    return subprocess.list2cmdline(cmd)


def build_ytdlp_command(download: dict[str, Any], urls: list[str]) -> list[str]:
    output_dir = resolve_path(str(download.get("download_dir") or ""), VIDEOS_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)
    fmt = str(download.get("format") or "full_hd_1080")
    base_cmd = ytdlp_cmd()
    if not base_cmd:
        raise RuntimeError("Không thấy yt-dlp. Hãy cài yt-dlp hoặc đặt yt-dlp.exe trong thư mục tool.")
    cmd = base_cmd + ["--newline", "--ignore-errors", "-P", str(output_dir), "-o", str(download.get("output_template") or "%(title).200s.%(ext)s")]
    if fmt == "tiktok_profile":
        cmd.append("--ignore-config")
        cmd.append("--yes-playlist")
    elif download.get("allow_playlist", True):
        cmd.append("--yes-playlist")
    else:
        cmd.append("--no-playlist")
    cmd.extend(ffmpeg_location_args())
    if fmt == "full_hd_1080":
        cmd.extend(["-f", "bv*[height<=1080]+ba/b[height<=1080]/best[height<=1080]/best", "--merge-output-format", "mp4"])
    elif fmt == "best_mp4":
        cmd.extend(["-f", "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/best", "--merge-output-format", "mp4"])
    elif fmt == "best":
        cmd.extend(["-f", "bestvideo*+bestaudio/best"])
    elif fmt == "audio_m4a":
        cmd.extend(["-f", "ba[ext=m4a]/bestaudio"])
    elif fmt == "tiktok_profile":
        cmd.extend(
            [
                "-f",
                "bv*+ba/b",
                "--merge-output-format",
                "mp4",
                "--remux-video",
                "mp4",
                "--match-filter",
                "vcodec!=none",
                "--download-archive",
                str(TIKTOK_ARCHIVE_FILE),
                "--sleep-interval",
                "3",
                "--max-sleep-interval",
                "8",
            ]
        )
    extra = str(download.get("extra_args") or "").strip()
    if extra:
        cmd.extend(shlex.split(extra, posix=False))
    cmd.extend(urls)
    return cmd


def youtube_command(action: str, payload: dict[str, Any], settings: dict[str, Any], account_id: str | None = None) -> list[str]:
    youtube = settings["youtube"]
    account = selected_account("youtube", settings, account_id)
    account_args = account_chrome_args(account, YOUTUBE_PROFILE_DIR, YOUTUBE_DEBUG_PORT)
    cmd = script_cmd(MAIN_FILE) + account_args
    if action == "login":
        return script_cmd(MAIN_FILE) + ["--login", "--no-wait-login"] + account_args
    if action == "publish_drafts":
        if youtube.get("attach", True):
            cmd.append("--attach")
        cmd.extend([
            "--publish-drafts",
            "--visibility",
            str(youtube.get("visibility") or "public"),
            "--made-for-kids",
            str(youtube.get("made_for_kids") or "no"),
            "--description-file",
            str(DESCRIPTION_FILE),
            "--delay",
            safe_int(youtube.get("delay"), 2),
            "--max-drafts",
            str(int(payload.get("max_drafts") or 20)),
            "--yes",
        ])
        if read_text(DESCRIPTION_HASHTAGS_FILE).strip():
            cmd.extend(["--description-hashtags", read_text(DESCRIPTION_HASHTAGS_FILE).strip()])
        return cmd
    if action == "resume_failed_uploads":
        if youtube.get("attach", True):
            cmd.append("--attach")
        cmd.extend([
            "--resume-failed-uploads",
            "--video-dir",
            str(account.get("upload_dir") or youtube.get("upload_dir") or VIDEOS_DIR),
            "--visibility",
            str(youtube.get("visibility") or "public"),
            "--made-for-kids",
            str(youtube.get("made_for_kids") or "no"),
            "--description-file",
            str(DESCRIPTION_FILE),
            "--delay",
            safe_int(youtube.get("delay"), 2),
            "--max-failed-uploads",
            str(int(payload.get("max_failed_uploads") or 20)),
            "--yes",
        ])
        return cmd
    if youtube.get("attach", True):
        cmd.append("--attach")
    if action == "upload_all":
        cmd.extend(["--all", "--video-dir", str(account.get("upload_dir") or youtube.get("upload_dir") or VIDEOS_DIR)])
    else:
        video = str(payload.get("video") or "")
        if not video:
            raise RuntimeError("Chưa chọn video YouTube.")
        cmd.extend(["--video", video])
    cmd.extend(
        [
            "--visibility",
            str(youtube.get("visibility") or "public"),
            "--made-for-kids",
            str(youtube.get("made_for_kids") or "no"),
            "--description-file",
            str(DESCRIPTION_FILE),
            "--delay",
            safe_int(youtube.get("delay"), 2),
            "--yes",
        ]
    )
    if str(youtube.get("custom_title") or "").strip():
        cmd.extend(["--title", str(youtube["custom_title"]).strip()])
    if read_text(TITLE_HASHTAGS_FILE).strip():
        cmd.extend(["--title-hashtags", read_text(TITLE_HASHTAGS_FILE).strip()])
    if read_text(DESCRIPTION_HASHTAGS_FILE).strip():
        cmd.extend(["--description-hashtags", read_text(DESCRIPTION_HASHTAGS_FILE).strip()])
    return cmd


def tiktok_command(action: str, payload: dict[str, Any], settings: dict[str, Any], account_id: str | None = None) -> list[str]:
    tiktok = settings["tiktok"]
    account = selected_account("tiktok", settings, account_id)
    account_args = account_chrome_args(account, TIKTOK_PROFILE_DIR, TIKTOK_DEBUG_PORT)
    cmd = script_cmd(TIKTOK_UPLOAD_FILE) + account_args
    if action == "login":
        return script_cmd(TIKTOK_UPLOAD_FILE) + ["--login"] + account_args
    if tiktok.get("attach", True):
        cmd.append("--attach")
    if action == "upload_all":
        cmd.extend(["--all", "--video-dir", str(account.get("upload_dir") or tiktok.get("upload_dir") or TIKTOK_DOWNLOAD_DIR)])
    else:
        video = str(payload.get("video") or "")
        if not video:
            raise RuntimeError("Chưa chọn video TikTok.")
        cmd.extend(["--video", video])
    cmd.extend(["--description-file", str(TIKTOK_DESCRIPTION_FILE), "--delay", safe_int(tiktok.get("delay"), 5), "--yes"])
    if str(tiktok.get("custom_title") or "").strip():
        cmd.extend(["--title", str(tiktok["custom_title"]).strip()])
    return cmd


def facebook_command(action: str, payload: dict[str, Any], settings: dict[str, Any], account_id: str | None = None) -> list[str]:
    facebook = settings["facebook"]
    account = selected_account("facebook", settings, account_id)
    account_target_url = str(account.get("target_url") or "").strip()
    shared_target_url = str(facebook.get("target_url") or "").strip()
    if shared_target_url and account_target_url.rstrip("/") == "https://www.facebook.com":
        target_url = shared_target_url
    else:
        target_url = account_target_url or shared_target_url or "https://www.facebook.com"
    account_args = account_chrome_args(account, FACEBOOK_PROFILE_DIR, FACEBOOK_DEBUG_PORT)
    cmd = script_cmd(FACEBOOK_UPLOAD_FILE) + account_args
    if action == "login":
        return script_cmd(FACEBOOK_UPLOAD_FILE) + ["--login", "--target-url", target_url] + account_args
    mode = str(account.get("mode") or facebook.get("mode") or "reels-api")
    cmd.extend(["--mode", mode])
    if mode == "browser":
        if facebook.get("attach", True):
            cmd.append("--attach")
        cmd.extend(["--target-url", target_url])
    else:
        page_id = str(account.get("page_id") or facebook.get("page_id") or "").strip()
        page_token = str(account.get("page_token") or facebook.get("page_token") or "").strip()
        if not page_id or not page_token:
            raise RuntimeError("Facebook reels-api cần Page ID và Page Access Token.")
        cmd.extend(
            [
                "--page-id",
                page_id,
                "--page-token",
                page_token,
                "--api-version",
                str(account.get("api_version") or facebook.get("api_version") or "v23.0"),
            ]
        )
    if action == "upload_all":
        cmd.extend(["--all", "--video-dir", str(account.get("upload_dir") or facebook.get("upload_dir") or VIDEOS_DIR)])
    else:
        video = str(payload.get("video") or "")
        if not video:
            raise RuntimeError("Chưa chọn video Facebook.")
        cmd.extend(["--video", video])
    cmd.extend(
        [
            "--description-file",
            str(FACEBOOK_DESCRIPTION_FILE),
            "--delay",
            safe_int(facebook.get("delay"), 10),
            "--no-convert",
            "--yes",
        ]
    )
    if str(facebook.get("custom_title") or "").strip():
        cmd.extend(["--title", str(facebook["custom_title"]).strip()])
    return cmd


def instagram_command(action: str, payload: dict[str, Any], settings: dict[str, Any], account_id: str | None = None) -> list[str]:
    instagram = settings["instagram"]
    account = selected_account("instagram", settings, account_id)
    account_args = account_chrome_args(account, INSTAGRAM_PROFILE_DIR, INSTAGRAM_DEBUG_PORT)
    cmd = script_cmd(INSTAGRAM_UPLOAD_FILE) + account_args
    if action == "login":
        return script_cmd(INSTAGRAM_UPLOAD_FILE) + ["--login"] + account_args
    if instagram.get("attach", True):
        cmd.append("--attach")
    if action == "upload_all":
        cmd.extend(["--all", "--video-dir", str(account.get("upload_dir") or instagram.get("upload_dir") or VIDEOS_DIR)])
    else:
        video = str(payload.get("video") or "")
        if not video:
            raise RuntimeError("Chưa chọn video Instagram.")
        cmd.extend(["--video", video])
    cmd.extend(["--description-file", str(INSTAGRAM_DESCRIPTION_FILE), "--delay", safe_int(instagram.get("delay"), 5), "--yes"])
    if str(instagram.get("custom_title") or "").strip():
        cmd.extend(["--title", str(instagram["custom_title"]).strip()])
    return cmd


def ayrshare_command(action: str, payload: dict[str, Any], settings: dict[str, Any]) -> list[str]:
    ayrshare = settings["ayrshare"]
    api_key = str(ayrshare.get("api_key") or os.environ.get("AYRSHARE_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("Ayrshare can API key.")
    cmd = script_cmd(AYRSHARE_UPLOAD_FILE)
    if action == "upload_all":
        cmd.extend(["--all", "--video-dir", str(ayrshare.get("upload_dir") or VIDEOS_DIR)])
    else:
        video = str(payload.get("video") or "")
        if not video:
            raise RuntimeError("Chua chon video Ayrshare.")
        cmd.extend(["--video", video])
    cmd.extend(
        [
            "--description-file",
            str(DESCRIPTION_FILE),
            "--api-key",
            api_key,
            "--platforms",
            str(ayrshare.get("platforms") or "facebook,instagram,tiktok,youtube"),
            "--start-after-minutes",
            safe_int(ayrshare.get("start_after_minutes"), 30),
            "--min-gap-minutes",
            safe_int(ayrshare.get("min_gap_minutes"), 60),
            "--max-gap-minutes",
            safe_int(ayrshare.get("max_gap_minutes"), 180),
            "--max-videos",
            safe_int(ayrshare.get("max_videos"), 3),
        ]
    )
    if str(ayrshare.get("custom_title") or "").strip():
        cmd.extend(["--title", str(ayrshare["custom_title"]).strip()])
    return cmd


def zernio_command(action: str, payload: dict[str, Any], settings: dict[str, Any]) -> list[str]:
    zernio = settings["zernio"]
    api_key = str(zernio.get("api_key") or os.environ.get("ZERNIO_API_KEYS") or os.environ.get("ZERNIO_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("Zernio can API key. Co the nhap nhieu key cach nhau bang dau phay.")
    cmd = script_cmd(ZERNIO_UPLOAD_FILE)
    if action == "upload_all":
        cmd.extend(["--all", "--video-dir", str(zernio.get("upload_dir") or VIDEOS_DIR)])
    else:
        video = str(payload.get("video") or "")
        if not video:
            raise RuntimeError("Chua chon video Zernio.")
        cmd.extend(["--video", video])
    cmd.extend(
        [
            "--description-file", str(DESCRIPTION_FILE),
            "--api-key", api_key,
            "--platforms", str(zernio.get("platforms") or "facebook,instagram,tiktok,youtube"),
            "--start-after-minutes", safe_int(zernio.get("start_after_minutes"), 30),
            "--min-gap-minutes", safe_int(zernio.get("min_gap_minutes"), 60),
            "--max-gap-minutes", safe_int(zernio.get("max_gap_minutes"), 180),
            "--max-videos", safe_int(zernio.get("max_videos"), 3),
        ]
    )
    if str(zernio.get("account_ids") or "").strip():
        cmd.extend(["--account-ids", str(zernio["account_ids"]).strip()])
    if str(zernio.get("profile_id") or "").strip():
        cmd.extend(["--profile-id", str(zernio["profile_id"]).strip()])
    if str(zernio.get("custom_title") or "").strip():
        cmd.extend(["--title", str(zernio["custom_title"]).strip()])
    return cmd


class WebPanelHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def log_message(self, format: str, *args: Any) -> None:
        print("[WEB]", format % args)

    def send_json(self, data: Any, status: int = 200) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_basic_auth_required(self) -> None:
        body = b"Authentication required"
        self.send_response(401)
        self.send_header("WWW-Authenticate", 'Basic realm="Mstar Web Panel"')
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def is_local_request(self) -> bool:
        host = self.client_address[0] if self.client_address else ""
        return host in {"127.0.0.1", "::1", "localhost"}

    def require_web_auth(self) -> bool:
        if self.is_local_request():
            return True
        username, password = ensure_web_auth()
        header = self.headers.get("Authorization", "")
        if not header.startswith("Basic "):
            self.send_basic_auth_required()
            return False
        try:
            decoded = base64.b64decode(header.split(" ", 1)[1]).decode("utf-8")
            provided_user, provided_password = decoded.split(":", 1)
        except Exception:
            self.send_basic_auth_required()
            return False
        if hmac.compare_digest(provided_user, username) and hmac.compare_digest(provided_password, password):
            return True
        self.send_basic_auth_required()
        return False

    def read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or "0")
        if not length:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/gpt/openapi.json":
            self.send_json(gpt_openapi_schema(self))
            return
        if parsed.path.startswith("/gpt/"):
            if not self.require_gpt_auth():
                return
            if parsed.path == "/gpt/status":
                self.send_json(gpt_status())
                return
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")
            return
        if not self.require_web_auth():
            return
        if parsed.path == "/api/state":
            self.send_json(api_state())
            return
        if parsed.path == "/api/jobs":
            self.send_json(jobs.snapshot())
            return
        if parsed.path == "/":
            self.path = "/index.html"
        super().do_GET()

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        try:
            payload = self.read_json()
            if parsed.path.startswith("/gpt/"):
                if not self.require_gpt_auth():
                    return
                self.send_json(run_gpt_endpoint(parsed.path, payload))
            elif not self.require_web_auth():
                return
            elif parsed.path == "/api/settings":
                self.send_json({"settings": save_settings(payload.get("settings", {}))})
            elif parsed.path == "/api/descriptions":
                save_descriptions(payload)
                self.send_json({"ok": True, "descriptions": api_descriptions()})
            elif parsed.path == "/api/action":
                result = run_action(payload)
                self.send_json(result)
            elif parsed.path == "/api/stop":
                stopped = jobs.stop(payload.get("group"))
                self.send_json({"ok": True, "stopped": stopped})
            elif parsed.path == "/api/delete-video":
                self.send_json(delete_video_file(str(payload.get("path") or ""), permanent=bool(payload.get("permanent"))))
            else:
                self.send_error(HTTPStatus.NOT_FOUND, "Not found")
        except Exception as exc:
            self.send_json({"ok": False, "error": str(exc)}, status=400)

    def require_gpt_auth(self) -> bool:
        expected = ensure_gpt_api_token()
        header = self.headers.get("Authorization", "")
        if header == f"Bearer {expected}":
            return True
        self.send_json({"ok": False, "error": "Unauthorized"}, status=401)
        return False


def api_descriptions() -> dict[str, str]:
    return {
        "youtube": read_text(DESCRIPTION_FILE),
        "tiktok": read_text(TIKTOK_DESCRIPTION_FILE),
        "facebook": read_text(FACEBOOK_DESCRIPTION_FILE),
        "instagram": read_text(INSTAGRAM_DESCRIPTION_FILE),
        "title_hashtags": read_text(TITLE_HASHTAGS_FILE).strip(),
        "description_hashtags": read_text(DESCRIPTION_HASHTAGS_FILE).strip(),
    }


def save_descriptions(payload: dict[str, Any]) -> None:
    descriptions = payload.get("descriptions", {})
    if "youtube" in descriptions:
        write_text(DESCRIPTION_FILE, str(descriptions["youtube"]))
    if "tiktok" in descriptions:
        write_text(TIKTOK_DESCRIPTION_FILE, str(descriptions["tiktok"]))
    if "facebook" in descriptions:
        write_text(FACEBOOK_DESCRIPTION_FILE, str(descriptions["facebook"]))
    if "instagram" in descriptions:
        write_text(INSTAGRAM_DESCRIPTION_FILE, str(descriptions["instagram"]))
    if "title_hashtags" in descriptions:
        write_text(TITLE_HASHTAGS_FILE, str(descriptions["title_hashtags"]))
    if "description_hashtags" in descriptions:
        write_text(DESCRIPTION_HASHTAGS_FILE, str(descriptions["description_hashtags"]))


def api_state() -> dict[str, Any]:
    settings = load_settings()
    youtube_account = selected_account("youtube", settings)
    tiktok_account = selected_account("tiktok", settings)
    facebook_account = selected_account("facebook", settings)
    instagram_account = selected_account("instagram", settings)
    return {
        "base_dir": str(BASE_DIR),
        "descriptions": api_descriptions(),
        "settings": settings,
        "videos": {
            "youtube": video_rows(resolve_path(youtube_account.get("upload_dir") or settings["youtube"].get("upload_dir"), VIDEOS_DIR)),
            "tiktok": video_rows(resolve_path(tiktok_account.get("upload_dir") or settings["tiktok"].get("upload_dir"), TIKTOK_DOWNLOAD_DIR)),
            "facebook": video_rows(resolve_path(facebook_account.get("upload_dir") or settings["facebook"].get("upload_dir"), VIDEOS_DIR)),
            "instagram": video_rows(resolve_path(instagram_account.get("upload_dir") or settings["instagram"].get("upload_dir"), VIDEOS_DIR)),
            "zernio": video_rows(resolve_path(settings["zernio"].get("upload_dir"), VIDEOS_DIR)),
        },
        "tools": {
            "yt_dlp": ytdlp_cmd() is not None,
            "ffmpeg": LOCAL_FFMPEG_FILE.exists() or shutil.which("ffmpeg") is not None,
        },
        "jobs": jobs.snapshot(),
    }


def public_base_url(handler: WebPanelHandler) -> str:
    proto = handler.headers.get("X-Forwarded-Proto", "http")
    host = handler.headers.get("X-Forwarded-Host") or handler.headers.get("Host") or "127.0.0.1:8080"
    return f"{proto}://{host}"


def gpt_openapi_schema(handler: WebPanelHandler) -> dict[str, Any]:
    base_url = public_base_url(handler)
    return {
        "openapi": "3.1.0",
        "info": {
            "title": "Mstar Upload Tool API",
            "version": "1.0.0",
            "description": "API cho ChatGPT dieu khien tool tai video va upload YouTube, TikTok, Facebook.",
        },
        "servers": [{"url": base_url}],
        "components": {
            "securitySchemes": {
                "BearerAuth": {"type": "http", "scheme": "bearer"}
            },
            "schemas": {
                "Platform": {"type": "string", "enum": ["youtube", "tiktok", "facebook", "instagram"]},
                "DownloadRequest": {
                    "type": "object",
                    "properties": {
                        "urls": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Danh sach link can tai, moi item la mot URL.",
                        },
                        "format": {
                            "type": "string",
                            "enum": ["full_hd_1080", "auto_with_audio", "best_mp4", "best", "audio_m4a", "tiktok_profile"],
                        },
                        "download_dir": {"type": "string"},
                        "output_template": {"type": "string"},
                        "extra_args": {"type": "string"},
                    },
                    "required": ["urls"],
                },
                "UploadRequest": {
                    "type": "object",
                    "properties": {
                        "platform": {"$ref": "#/components/schemas/Platform"},
                        "account_id": {"type": "string", "description": "ID account de upload mot account."},
                        "account_ids": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Danh sach account de upload lan luot.",
                        },
                        "video": {"type": "string", "description": "Duong dan file video neu chi upload mot video."},
                        "upload_all": {"type": "boolean", "default": True},
                    },
                    "required": ["platform"],
                },
                "PublishDraftsRequest": {
                    "type": "object",
                    "properties": {
                        "account_id": {"type": "string"},
                        "max_drafts": {"type": "integer", "default": 20},
                    },
                },
                "DescriptionRequest": {
                    "type": "object",
                    "properties": {
                        "youtube": {"type": "string"},
                        "tiktok": {"type": "string"},
                        "facebook": {"type": "string"},
                        "instagram": {"type": "string"},
                        "title_hashtags": {"type": "string"},
                        "description_hashtags": {"type": "string"},
                    },
                },
                "DeleteVideoRequest": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Duong dan file video can xoa, lay tu getToolStatus."},
                        "permanent": {
                            "type": "boolean",
                            "default": False,
                            "description": "False se chuyen vao deleted_videos. True se xoa han.",
                        },
                    },
                    "required": ["path"],
                },
            },
        },
        "security": [{"BearerAuth": []}],
        "paths": {
            "/gpt/status": {
                "get": {
                    "operationId": "getToolStatus",
                    "summary": "Xem trang thai tool, jobs, accounts va danh sach video.",
                    "responses": {"200": {"description": "Trang thai hien tai"}},
                }
            },
            "/gpt/download": {
                "post": {
                    "operationId": "downloadVideos",
                    "summary": "Tai video tu link YouTube/TikTok/Facebook bang yt-dlp.",
                    "requestBody": {
                        "required": True,
                        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/DownloadRequest"}}},
                    },
                    "responses": {"200": {"description": "Da bat dau job tai video"}},
                }
            },
            "/gpt/upload": {
                "post": {
                    "operationId": "uploadVideos",
                    "summary": "Dang video len YouTube, TikTok hoac Facebook, co the chay lan luot nhieu account.",
                    "requestBody": {
                        "required": True,
                        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/UploadRequest"}}},
                    },
                    "responses": {"200": {"description": "Da bat dau job upload"}},
                }
            },
            "/gpt/publish-youtube-drafts": {
                "post": {
                    "operationId": "publishYouTubeDrafts",
                    "summary": "Mo cac ban nhap YouTube dang thay trong Studio va publish theo account.",
                    "requestBody": {
                        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/PublishDraftsRequest"}}}
                    },
                    "responses": {"200": {"description": "Da bat dau job publish ban nhap"}},
                }
            },
            "/gpt/description": {
                "post": {
                    "operationId": "setDescriptions",
                    "summary": "Cap nhat mo ta va hashtag dung cho upload.",
                    "requestBody": {
                        "required": True,
                        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/DescriptionRequest"}}},
                    },
                    "responses": {"200": {"description": "Da cap nhat mo ta"}},
                }
            },
            "/gpt/delete-video": {
                "post": {
                    "operationId": "deleteVideo",
                    "summary": "Xoa video khoi tool. Mac dinh chuyen vao deleted_videos de co the khoi phuc.",
                    "requestBody": {
                        "required": True,
                        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/DeleteVideoRequest"}}},
                    },
                    "responses": {"200": {"description": "Da xoa hoac chuyen video vao deleted_videos"}},
                }
            },
            "/gpt/stop": {
                "post": {
                    "operationId": "stopJob",
                    "summary": "Dung mot job hoac tat ca job.",
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {"group": {"type": "string", "enum": ["youtube", "tiktok", "facebook", "instagram", "download"]}},
                                }
                            }
                        }
                    },
                    "responses": {"200": {"description": "Da gui lenh dung"}},
                }
            },
        },
    }


def gpt_status() -> dict[str, Any]:
    state = api_state()
    return {
        "ok": True,
        "accounts": state["settings"].get("accounts", {}),
        "videos": {
            platform: [
                {"name": video["name"], "path": video["path"], "size": video["size"], "modified": video["modified"]}
                for video in videos[:50]
            ]
            for platform, videos in state["videos"].items()
        },
        "video_counts": {platform: len(videos) for platform, videos in state["videos"].items()},
        "jobs": state["jobs"]["groups"],
        "logs": state["jobs"]["logs"],
        "tools": state["tools"],
    }


def run_gpt_endpoint(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    if path == "/gpt/download":
        settings = load_settings(include_token=True)
        download = settings["download"]
        for key in ["format", "download_dir", "output_template", "extra_args"]:
            if payload.get(key):
                download[key] = payload[key]
        urls = payload.get("urls") or []
        if isinstance(urls, str):
            urls = [line.strip() for line in urls.splitlines() if line.strip()]
        return run_action({"platform": "download", "action": "start", "urls": "\n".join(urls), "settings": settings})
    if path == "/gpt/upload":
        platform = str(payload.get("platform") or "")
        action = "upload_selected" if payload.get("video") and not payload.get("upload_all", True) else "upload_all"
        body = {
            "platform": platform,
            "action": action,
            "account_id": payload.get("account_id"),
            "video": payload.get("video"),
        }
        account_ids = payload.get("account_ids") or []
        if account_ids:
            body["action"] = "upload_sequence"
            body["account_ids"] = account_ids
        return run_action(body)
    if path == "/gpt/publish-youtube-drafts":
        return run_action({
            "platform": "youtube",
            "action": "publish_drafts",
            "account_id": payload.get("account_id"),
            "max_drafts": payload.get("max_drafts") or 20,
        })
    if path == "/gpt/description":
        save_descriptions({"descriptions": payload})
        return {"ok": True, "descriptions": api_descriptions()}
    if path == "/gpt/delete-video":
        return delete_video_file(str(payload.get("path") or ""), permanent=bool(payload.get("permanent")))
    if path == "/gpt/stop":
        stopped = jobs.stop(payload.get("group"))
        return {"ok": True, "stopped": stopped}
    raise RuntimeError("GPT endpoint khong hop le.")


def run_action(payload: dict[str, Any]) -> dict[str, Any]:
    platform = str(payload.get("platform") or "")
    action = str(payload.get("action") or "")
    settings = save_settings(payload.get("settings", {})) if payload.get("settings") else load_settings(include_token=True)
    if payload.get("descriptions"):
        save_descriptions(payload)
    if action == "upload_sequence":
        account_ids = [str(item) for item in payload.get("account_ids", []) if str(item).strip()]
        jobs_to_run: list[tuple[str, list[str]]] = []
        for account_id in account_ids:
            account = selected_account(platform, settings, account_id)
            label = str(account.get("name") or account.get("id") or account_id)
            if platform == "youtube":
                cmd = youtube_command("upload_all", payload, settings, account_id)
            elif platform == "tiktok":
                cmd = tiktok_command("upload_all", payload, settings, account_id)
            elif platform == "facebook":
                cmd = facebook_command("upload_all", payload, settings, account_id)
            elif platform == "instagram":
                cmd = instagram_command("upload_all", payload, settings, account_id)
            else:
                raise RuntimeError("Chạy tuần tự chỉ hỗ trợ YouTube, TikTok, Facebook.")
            jobs_to_run.append((label, cmd))
        jobs.start_sequence(platform, jobs_to_run)
        return {"ok": True, "group": platform, "sequence": True}
    if platform == "youtube":
        cmd = youtube_command(action, payload, settings, payload.get("account_id"))
    elif platform == "tiktok":
        cmd = tiktok_command(action, payload, settings, payload.get("account_id"))
    elif platform == "facebook":
        cmd = facebook_command(action, payload, settings, payload.get("account_id"))
    elif platform == "instagram":
        cmd = instagram_command(action, payload, settings, payload.get("account_id"))
    elif platform == "ayrshare":
        cmd = ayrshare_command(action, payload, settings)
    elif platform == "zernio":
        cmd = zernio_command(action, payload, settings)
    elif platform == "download":
        urls = [line.strip() for line in str(payload.get("urls") or "").splitlines() if line.strip()]
        if not urls:
            raise RuntimeError("Chưa nhập link tải video.")
        cmd = build_ytdlp_command(settings["download"], urls)
    else:
        raise RuntimeError("Action không hợp lệ.")
    group = platform
    jobs.start(group, cmd)
    return {"ok": True, "group": group}


def bind_server(host: str, port: int) -> tuple[ThreadingHTTPServer, int]:
    explicit_port = bool(os.environ.get("WEB_PANEL_PORT"))
    ports = [port] if explicit_port else list(range(port, port + 20))
    last_error: OSError | None = None
    for candidate in ports:
        try:
            return ThreadingHTTPServer((host, candidate), WebPanelHandler), candidate
        except OSError as exc:
            last_error = exc
            if explicit_port:
                break
            console_log(f"[CANH BAO] Khong mo duoc cong {candidate}: {exc}. Dang thu cong tiep theo...")
    raise RuntimeError(f"Khong mo duoc web panel tren {host}:{port}. Loi cuoi: {last_error}")


def main() -> None:
    port = int(os.environ.get("WEB_PANEL_PORT", "8080"))
    host = os.environ.get("WEB_PANEL_HOST", "127.0.0.1")
    STATIC_DIR.mkdir(exist_ok=True)
    if WEB_PANEL_URL_FILE.exists():
        WEB_PANEL_URL_FILE.unlink()
    server, actual_port = bind_server(host, port)
    panel_url = f"http://{host}:{actual_port}"
    WEB_PANEL_URL_FILE.write_text(panel_url, encoding="utf-8")
    console_log(f"Web panel dang chay: {panel_url}")
    console_log("Nhan Ctrl+C de dung.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        jobs.stop()
        console_log("\nDa dung web panel.")
    finally:
        if WEB_PANEL_URL_FILE.exists():
            WEB_PANEL_URL_FILE.unlink()


if __name__ == "__main__":
    main()
