"""
Facebook web auto upload helper.

Chay nhanh:
1) python facebook_upload.py --login
2) Dang nhap Facebook tren Chrome vua mo, GIU NGUYEN cua so Chrome do
3) python facebook_upload.py --attach --all --target-url https://www.facebook.com/your.page --yes

Luu y:
- Tool dieu khien giao dien Facebook bang trinh duyet, khong vuot captcha/checkpoint.
- Neu Facebook doi giao dien, co the can sua selector/nut bam.
"""

from __future__ import annotations

import argparse
import ctypes
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.parse
import uuid
from pathlib import Path
from typing import Optional

import pyperclip
import requests
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

BASE_DIR = Path(__file__).resolve().parent
VIDEOS_DIR = BASE_DIR / "videos"
PROFILE_DIR = BASE_DIR / "chrome-profile-facebook"
LOCAL_CHROMEDRIVER = BASE_DIR / "chromedriver.exe"
LOCAL_FFMPEG_FILE = BASE_DIR / "ffmpeg.exe"
UPLOADED_DIR = BASE_DIR / "uploaded_facebook_success"
DEBUG_DIR = BASE_DIR / "facebook_debug"
TEMP_UPLOAD_DIR = BASE_DIR / "facebook_upload_temp"
DEFAULT_DESCRIPTION_FILE = BASE_DIR / "facebook_description.txt"

VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}
SAFE_FACEBOOK_FILENAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._ -]{0,119}\.[A-Za-z0-9]{2,5}$")
DEBUG_PORT = 9224
DEFAULT_TIMEOUT = 30
UPLOAD_TIMEOUT = 60 * 60
DEFAULT_API_VERSION = "v23.0"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


# Adapted from XavierZambrano/facebook-reels-api (MIT License).
# The implementation is kept local so this tool can run without installing a
# package from GitHub on every machine.
class FacebookReelsAPI:
    def __init__(self, page_id: str, page_access_token: str, api_version: str = DEFAULT_API_VERSION):
        self.page_id = page_id.strip()
        self.page_access_token = page_access_token.strip()
        self.api_version = api_version.strip() or DEFAULT_API_VERSION
        self.json: dict | None = None

    def is_page_access_token_valid(self) -> bool:
        url = f"https://graph.facebook.com/{self.api_version}/{self.page_id}"
        response = requests.get(
            url,
            params={"fields": "id,name", "access_token": self.page_access_token},
            timeout=60,
        )
        self.json = response.json()
        return response.status_code == 200

    def upload_reel(self, file_path: Path, description: str, publish_time: str | None = None) -> str:
        video_id = self._initialize_upload()
        self._process_upload(video_id, file_path)
        self._publish(video_id, description, publish_time)
        return video_id

    def _initialize_upload(self) -> str:
        url = f"https://graph.facebook.com/{self.api_version}/{self.page_id}/video_reels"
        payload = {"upload_phase": "start", "access_token": self.page_access_token}
        response = requests.post(url, data=payload, timeout=60)
        self.json = response.json()
        if response.status_code != 200:
            raise RuntimeError(f"Khoi tao upload Reels loi: {self.json}")
        video_id = self.json.get("video_id")
        if not video_id:
            raise RuntimeError(f"Facebook khong tra ve video_id: {self.json}")
        return str(video_id)

    def _process_upload(self, video_id: str, file_path: Path) -> None:
        url = f"https://rupload.facebook.com/video-upload/{self.api_version}/{video_id}"
        headers = {
            "Authorization": "OAuth " + self.page_access_token,
            "offset": "0",
            "file_size": str(file_path.stat().st_size),
            "Content-Type": "application/octet-stream",
        }
        with file_path.open("rb") as video_file:
            response = requests.post(url, data=video_file, headers=headers, timeout=UPLOAD_TIMEOUT)
        self.json = response.json()
        if response.status_code != 200:
            raise RuntimeError(f"Upload file Reels loi: {self.json}")

    def _publish(self, video_id: str, description: str, publish_time: str | None = None) -> None:
        url = f"https://graph.facebook.com/{self.api_version}/{self.page_id}/video_reels"
        payload = {
            "access_token": self.page_access_token,
            "video_id": video_id,
            "upload_phase": "finish",
            "description": description,
        }
        if publish_time:
            payload["video_state"] = "SCHEDULED"
            payload["scheduled_publish_time"] = publish_time
        else:
            payload["video_state"] = "PUBLISHED"
        response = requests.post(url, data=payload, timeout=60)
        self.json = response.json()
        if response.status_code != 200:
            raise RuntimeError(f"Publish Reels loi: {self.json}")


def read_text_file(path_value: str | None) -> str:
    if not path_value:
        return ""
    path = Path(path_value)
    if not path.is_absolute():
        path = BASE_DIR / path
    if not path.exists():
        print(f"[CANH BAO] Khong thay file mo ta: {path}")
        return ""
    try:
        return path.read_text(encoding="utf-8").strip()
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8-sig").strip()
    except Exception as exc:
        print(f"[CANH BAO] Khong doc duoc file mo ta {path}: {exc}")
        return ""


def resolve_base_path(path_value: str | None, default_path: Path) -> Path:
    if not path_value:
        return default_path
    path = Path(path_value)
    if not path.is_absolute():
        path = BASE_DIR / path
    return path


def get_video_files(video_dir: Path) -> list[Path]:
    video_dir.mkdir(parents=True, exist_ok=True)
    videos = [p for p in video_dir.rglob("*") if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS]
    return sorted(videos, key=lambda p: str(p).lower())


def find_chrome_executable(chrome_binary: Optional[str] = None) -> str:
    if chrome_binary:
        return chrome_binary

    if os.name != "nt":
        for name in ("google-chrome", "google-chrome-stable", "chromium-browser", "chromium", "chrome"):
            if shutil.which(name):
                return name
        return "google-chrome"

    candidates: list[Path] = []
    for base in [os.environ.get("PROGRAMFILES"), os.environ.get("PROGRAMFILES(X86)"), os.environ.get("LOCALAPPDATA")]:
        if not base:
            continue
        candidates.extend(
            [
                Path(base) / "Google" / "Chrome" / "Application" / "chrome.exe",
                Path(base) / "Google" / "Chrome Beta" / "Application" / "chrome.exe",
                Path(base) / "Google" / "Chrome SxS" / "Application" / "chrome.exe",
            ]
        )
    for path in candidates:
        if path.exists():
            return str(path)
    return "chrome"


def facebook_english_url(target_url: str = "https://www.facebook.com") -> str:
    target_url = (target_url or "https://www.facebook.com").strip()
    parsed = urllib.parse.urlparse(target_url)
    if not parsed.scheme:
        parsed = urllib.parse.urlparse("https://" + target_url)
    query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    query = [(key, value) for key, value in query if key.lower() != "locale"]
    query.append(("locale", "en_US"))
    return urllib.parse.urlunparse(parsed._replace(query=urllib.parse.urlencode(query)))


def open_manual_chrome(chrome_binary: Optional[str] = None, target_url: str = "https://www.facebook.com") -> None:
    PROFILE_DIR.mkdir(exist_ok=True)
    chrome = find_chrome_executable(chrome_binary)
    cmd = [
        chrome,
        f"--remote-debugging-port={DEBUG_PORT}",
        f"--user-data-dir={PROFILE_DIR}",
        "--profile-directory=Default",
        "--start-maximized",
        "--lang=en-US",
        facebook_english_url(target_url),
    ]
    subprocess.Popen(cmd)


def build_driver(chrome_binary: Optional[str] = None, attach: bool = False) -> WebDriver:
    PROFILE_DIR.mkdir(exist_ok=True)
    options = Options()
    options.add_argument("--start-maximized")
    options.add_argument("--log-level=3")
    options.add_argument("--disable-notifications")
    options.add_argument("--lang=en-US")
    options.add_experimental_option("prefs", {"intl.accept_languages": "en-US,en"})
    if attach:
        options.add_experimental_option("debuggerAddress", f"127.0.0.1:{DEBUG_PORT}")
    else:
        options.add_argument(f"--user-data-dir={PROFILE_DIR}")
        options.add_argument("--profile-directory=Default")
    if chrome_binary:
        options.binary_location = chrome_binary

    def connect() -> WebDriver:
        try:
            return webdriver.Chrome(options=options)
        except WebDriverException as automatic_driver_error:
            if not LOCAL_CHROMEDRIVER.exists():
                raise
            print(
                "[CANH BAO] Khong tim duoc ChromeDriver tuong thich tu dong; "
                "dang thu chromedriver.exe trong thu muc."
            )
            detail = str(automatic_driver_error).splitlines()[0]
            print(f"Chi tiet tu dong: {detail}")
            return webdriver.Chrome(
                service=Service(executable_path=str(LOCAL_CHROMEDRIVER)),
                options=options,
            )

    try:
        return connect()
    except WebDriverException as exc:
        if attach:
            print("\n[CANH BAO] Chua ket noi duoc Chrome Facebook dang mo, tool se tu mo Chrome roi thu lai...")
            open_manual_chrome(chrome_binary, "https://www.facebook.com")
            time.sleep(5)
            try:
                return connect()
            except WebDriverException as retry_exc:
                exc = retry_exc
        print("\n[LOI] Khong mo/ket noi duoc Chrome.")
        print("- Hay chay: python facebook_upload.py --login")
        print("- Dang nhap Facebook xong phai GIU NGUYEN cua so Chrome do.")
        print(f"- Cong ket noi mac dinh: {DEBUG_PORT}")
        print(f"Chi tiet loi: {exc}")
        raise


def build_caption(video_path: Path, args: argparse.Namespace) -> str:
    title = (args.title or video_path.stem).strip()
    description = (args.description or args.default_description or "").strip()
    if description:
        return f"{title}\n\n{description}"
    return title


def paste_text(element, text: str) -> None:
    pyperclip.copy(text)
    try:
        element.click()
    except Exception:
        element._parent.execute_script(
            """
            arguments[0].scrollIntoView({block: 'center'});
            arguments[0].focus();
            arguments[0].click();
            """,
            element,
        )
    try:
        element.send_keys("\ue009" + "a")
        element.send_keys("\ue009" + "v")
        time.sleep(0.5)
        if text[:30] in (element.text or ""):
            return
    except Exception:
        pass

    element._parent.execute_script(
        """
        const el = arguments[0];
        const value = arguments[1];
        el.focus();
        el.textContent = value;
        el.dispatchEvent(new InputEvent('input', {
            inputType: 'insertText',
            data: value,
            bubbles: true,
            cancelable: true
        }));
        el.dispatchEvent(new Event('change', {bubbles: true}));
        """,
        element,
        text,
    )
    time.sleep(0.5)


def save_debug_artifacts(driver: WebDriver, label: str) -> None:
    if os.environ.get("SAVE_DEBUG_ARTIFACTS", "").strip() != "1":
        print("[DEBUG] Bo qua luu screenshot/HTML loi. Dat SAVE_DEBUG_ARTIFACTS=1 neu muon bat debug file.")
        return
    DEBUG_DIR.mkdir(exist_ok=True)
    safe_label = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in label)[:80]
    stamp = time.strftime("%Y%m%d_%H%M%S")
    base = DEBUG_DIR / f"{stamp}_{safe_label}"
    try:
        driver.save_screenshot(str(base.with_suffix(".png")))
        print(f"[DEBUG] Da luu anh loi: {base.with_suffix('.png')}")
    except Exception as exc:
        print(f"[DEBUG] Khong luu duoc screenshot: {exc}")
    try:
        base.with_suffix(".html").write_text(driver.page_source, encoding="utf-8", errors="replace")
        print(f"[DEBUG] Da luu HTML loi: {base.with_suffix('.html')}")
    except Exception as exc:
        print(f"[DEBUG] Khong luu duoc HTML: {exc}")


def page_text(driver: WebDriver) -> str:
    try:
        return driver.find_element(By.TAG_NAME, "body").text
    except Exception:
        return ""


def current_page_summary(driver: WebDriver) -> str:
    snippet = " ".join(page_text(driver).split())[:700]
    return f"url={driver.current_url} title={driver.title!r} text={snippet!r}"


def wait_facebook_ready(driver: WebDriver, timeout: int = 90) -> None:
    end_time = time.time() + timeout
    while time.time() < end_time:
        text = page_text(driver).lower()
        url = driver.current_url.lower()
        if "checkpoint" in url or "captcha" in text or "security check" in text:
            raise RuntimeError("Facebook dang yeu cau checkpoint/captcha. Hay xu ly thu cong tren Chrome roi chay lai.")
        if "login" in url or "log in" in text or "dang nhap" in text or "đăng nhập" in text:
            print("[CANH BAO] Facebook co ve chua dang nhap. Hay chay --login va dang nhap truoc.")
        if "facebook.com" in url and text:
            return
        time.sleep(1)
    raise TimeoutException(f"Khong mo duoc Facebook. {current_page_summary(driver)}")


def click_first_by_xpath(driver: WebDriver, xpaths: list[str], *, timeout: int, name: str) -> None:
    end_time = time.time() + timeout
    last_error: Exception | None = None
    while time.time() < end_time:
        for xpath in xpaths:
            try:
                element = WebDriverWait(driver, 2).until(EC.element_to_be_clickable((By.XPATH, xpath)))
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
                time.sleep(0.2)
                try:
                    element.click()
                except Exception:
                    driver.execute_script("arguments[0].click();", element)
                return
            except Exception as exc:
                last_error = exc
        time.sleep(0.5)
    raise TimeoutException(f"Khong tim/click duoc {name}. Loi cuoi: {last_error}. {current_page_summary(driver)}")


def open_post_composer(driver: WebDriver) -> None:
    create_post_xpaths = [
        '//*[@role="button" and (contains(., "Bạn đang nghĩ gì") or contains(., "What\'s on your mind"))]',
        '//*[@role="button" and (contains(., "Tạo bài viết") or contains(., "Create post"))]',
        '//*[self::span or self::div][contains(., "Bạn đang nghĩ gì") or contains(., "What\'s on your mind")]/ancestor::*[@role="button"][1]',
        '//*[self::span or self::div][contains(., "Tạo bài viết") or contains(., "Create post")]/ancestor::*[@role="button"][1]',
    ]
    click_first_by_xpath(driver, create_post_xpaths, timeout=DEFAULT_TIMEOUT, name="hop tao bai viet Facebook")


def click_photo_video(driver: WebDriver) -> None:
    photo_video_xpaths = [
        '//*[@role="button" and (contains(., "Ảnh/video") or contains(., "Anh/video") or contains(., "Photo/video"))]',
        '//*[self::span or self::div][contains(., "Ảnh/video") or contains(., "Anh/video") or contains(., "Photo/video")]/ancestor::*[@role="button"][1]',
    ]
    try:
        click_first_by_xpath(driver, photo_video_xpaths, timeout=10, name="nut Anh/video")
    except TimeoutException:
        print("[INFO] Khong thay nut Anh/video rieng, se thu tim input file truc tiep.")


def _press_key(vk_code: int) -> None:
    ctypes.windll.user32.keybd_event(vk_code, 0, 0, 0)
    ctypes.windll.user32.keybd_event(vk_code, 0, 2, 0)


def fill_windows_open_dialog(file_path: Path, timeout: int = 8) -> bool:
    if os.name != "nt":
        return False
    user32 = ctypes.windll.user32
    end_time = time.time() + timeout
    dialog_titles = ["Open", "Mở", "Chọn tệp để tải lên", "Choose File to Upload"]
    hwnd = 0
    while time.time() < end_time:
        for title in dialog_titles:
            hwnd = user32.FindWindowW("#32770", title)
            if hwnd:
                break
        if hwnd:
            break
        time.sleep(0.2)
    if not hwnd:
        return False

    user32.SetForegroundWindow(hwnd)
    time.sleep(0.3)
    pyperclip.copy(str(file_path.resolve()))
    user32.keybd_event(0x11, 0, 0, 0)  # Ctrl
    _press_key(0x56)  # V
    user32.keybd_event(0x11, 0, 2, 0)
    time.sleep(0.3)
    _press_key(0x0D)  # Enter
    return True


def close_windows_open_dialog(timeout: int = 1) -> bool:
    if os.name != "nt":
        return False
    user32 = ctypes.windll.user32
    end_time = time.time() + timeout
    for title in ["Open", "Mở", "Chọn tệp để tải lên", "Choose File to Upload"]:
        while time.time() < end_time:
            hwnd = user32.FindWindowW("#32770", title)
            if hwnd:
                user32.SetForegroundWindow(hwnd)
                time.sleep(0.2)
                _press_key(0x1B)  # Escape
                return True
            time.sleep(0.1)
    return False


def input_accepts_video(element) -> bool:
    accept = (element.get_attribute("accept") or "").lower().replace(" ", "")
    if not accept:
        return True
    video_tokens = ("video", ".mp4", ".mov", ".m4v", ".webm", ".avi", ".mkv")
    return any(token in accept for token in video_tokens)


def describe_file_input(element) -> str:
    accept = element.get_attribute("accept") or "(empty)"
    multiple = element.get_attribute("multiple")
    aria = element.get_attribute("aria-label") or ""
    return f"accept={accept!r} multiple={multiple!r} aria={aria!r}"


def find_file_input(driver: WebDriver, timeout: int = DEFAULT_TIMEOUT):
    end_time = time.time() + timeout
    last_error: Exception | None = None
    skipped_inputs: list[str] = []
    while time.time() < end_time:
        try:
            inputs = driver.find_elements(By.CSS_SELECTOR, 'input[type="file"]')
            for element in inputs:
                input_desc = describe_file_input(element)
                if input_accepts_video(element):
                    driver.execute_script(
                        """
                        arguments[0].style.display = 'block';
                        arguments[0].style.visibility = 'visible';
                        arguments[0].style.opacity = 1;
                        arguments[0].removeAttribute('hidden');
                        """,
                        element,
                    )
                    print(f"[INFO] Chon input video Facebook: {input_desc}")
                    return element
                if input_desc not in skipped_inputs:
                    skipped_inputs.append(input_desc)
        except Exception as exc:
            last_error = exc
        time.sleep(0.5)
    skipped = "; ".join(skipped_inputs[-5:]) if skipped_inputs else "(khong co input file)"
    raise TimeoutException(
        f"Khong tim thay input video Facebook. Da bo qua input anh: {skipped}. "
        f"Loi cuoi: {last_error}. {current_page_summary(driver)}"
    )


def attach_video_file(driver: WebDriver, video_path: Path) -> None:
    close_windows_open_dialog()
    try:
        file_input = find_file_input(driver, timeout=8)
        print("[INFO] Da thay input chon file Facebook, dang gui file truc tiep...")
        file_input.send_keys(str(video_path.resolve()))
        return
    except Exception as exc:
        print(f"[INFO] Chua gan file truc tiep duoc, se bam Anh/video. Chi tiet: {exc}")

    click_photo_video(driver)
    if fill_windows_open_dialog(video_path):
        print("[INFO] Da dien duong dan video vao hop thoai Open cua Windows.")
        return

    file_input = find_file_input(driver, timeout=DEFAULT_TIMEOUT)
    print("[INFO] Da thay input chon file Facebook sau khi bam Anh/video, dang gui file...")
    file_input.send_keys(str(video_path.resolve()))


def set_caption(driver: WebDriver, caption: str) -> None:
    textareas = [
        '//div[@role="dialog"]//*[@role="textbox" and @contenteditable="true"]',
        '//div[@role="dialog"]//*[@contenteditable="true"]',
        '//*[@role="textbox" and @contenteditable="true"]',
        '//*[@contenteditable="true"]',
    ]
    end_time = time.time() + DEFAULT_TIMEOUT
    last_error: Exception | None = None
    while time.time() < end_time:
        for xpath in textareas:
            try:
                boxes = driver.find_elements(By.XPATH, xpath)
                for box in boxes:
                    if box.is_displayed():
                        paste_text(box, caption)
                        return
            except Exception as exc:
                last_error = exc
        time.sleep(0.5)
    raise TimeoutException(f"Khong tim thay o nhap caption. Loi cuoi: {last_error}. {current_page_summary(driver)}")


def wait_upload_ready(driver: WebDriver, timeout: int = UPLOAD_TIMEOUT) -> None:
    end_time = time.time() + timeout
    blocking_words = [
        "uploading",
        "đang tải lên",
        "dang tai len",
        "processing",
        "đang xử lý",
        "dang xu ly",
    ]
    ready_words = [
        "post",
        "đăng",
        "dang",
    ]
    while time.time() < end_time:
        text = page_text(driver).lower()
        if "couldn't upload" in text or "upload failed" in text or "không tải lên được" in text:
            raise RuntimeError("Facebook bao upload video that bai.")
        publish_buttons = driver.find_elements(
            By.XPATH,
            '//div[@role="dialog"]//*[@role="button" and not(@aria-disabled="true") and '
            '(contains(., "Đăng") or contains(., "Dang") or contains(., "Post") or '
            'contains(., "Tiếp") or contains(., "Tiep") or contains(., "Next"))]',
        )
        has_enabled_publish_action = any(btn.is_displayed() and btn.is_enabled() for btn in publish_buttons)
        has_blocking_text = any(word in text for word in blocking_words)
        has_ready_text = any(word in text for word in ready_words)
        if has_enabled_publish_action and (not has_blocking_text or has_ready_text):
            return
        time.sleep(2)
    raise TimeoutException("Facebook upload/processing qua lau, chua san sang dang.")


def click_next_steps(driver: WebDriver, max_steps: int = 3) -> None:
    next_xpaths = [
        '//div[@role="dialog"]//*[@role="button" and not(@aria-disabled="true") and contains(., "Tiếp")]',
        '//div[@role="dialog"]//*[@role="button" and not(@aria-disabled="true") and contains(., "Tiep")]',
        '//div[@role="dialog"]//*[@role="button" and not(@aria-disabled="true") and contains(., "Next")]',
        '//*[@role="button" and not(@aria-disabled="true") and contains(., "Tiếp")]',
        '//*[@role="button" and not(@aria-disabled="true") and contains(., "Next")]',
    ]
    post_xpaths = [
        '//div[@role="dialog"]//*[@role="button" and not(@aria-disabled="true") and .//*[normalize-space(.)="Đăng"]]',
        '//div[@role="dialog"]//*[@role="button" and not(@aria-disabled="true") and .//*[normalize-space(.)="Post"]]',
        '//div[@role="dialog"]//*[@role="button" and not(@aria-disabled="true") and normalize-space(.)="Đăng"]',
        '//div[@role="dialog"]//*[@role="button" and not(@aria-disabled="true") and normalize-space(.)="Dang"]',
        '//div[@role="dialog"]//*[@role="button" and not(@aria-disabled="true") and normalize-space(.)="Post"]',
        '//div[@role="dialog"]//*[@role="button" and not(@aria-disabled="true") and normalize-space(.)="Đăng ngay"]',
        '//div[@role="dialog"]//*[@role="button" and not(@aria-disabled="true") and normalize-space(.)="Post now"]',
    ]
    for _ in range(max_steps):
        if any(
            element.is_displayed() and element.is_enabled()
            for xpath in post_xpaths
            for element in driver.find_elements(By.XPATH, xpath)
        ):
            return
        clicked = False
        for xpath in next_xpaths:
            buttons = driver.find_elements(By.XPATH, xpath)
            for button in buttons:
                if button.is_displayed() and button.is_enabled():
                    print("[INFO] Facebook dang o buoc trung gian, bam Tiep/Next...")
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", button)
                    time.sleep(0.2)
                    try:
                        button.click()
                    except Exception:
                        driver.execute_script("arguments[0].click();", button)
                    time.sleep(3)
                    clicked = True
                    break
            if clicked:
                break
        if not clicked:
            return


def dismiss_schedule_dialog(driver: WebDriver) -> bool:
    schedule_markers = [
        "lựa chọn lịch đăng",
        "lua chon lich dang",
        "schedule post",
        "scheduling options",
    ]
    if not any(marker in page_text(driver).lower() for marker in schedule_markers):
        return False

    back_xpaths = [
        '//div[@role="dialog"]//*[@role="button" and @aria-label="Quay lại"]',
        '//div[@role="dialog"]//*[@role="button" and @aria-label="Quay lai"]',
        '//div[@role="dialog"]//*[@role="button" and @aria-label="Back"]',
        '//div[@role="dialog"]//*[@role="button" and normalize-space(.)="Quay lại"]',
        '//div[@role="dialog"]//*[@role="button" and normalize-space(.)="Back"]',
    ]
    for xpath in back_xpaths:
        for button in driver.find_elements(By.XPATH, xpath):
            if not button.is_displayed() or not button.is_enabled():
                continue
            try:
                button.click()
            except Exception:
                driver.execute_script("arguments[0].click();", button)
            time.sleep(1)
            print("[INFO] Da thoat hop lua chon lich dang Facebook.")
            return True

    driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
    time.sleep(1)
    print("[INFO] Da dong hop lua chon lich dang Facebook bang phim Escape.")
    return True


def click_post(driver: WebDriver) -> None:
    dismiss_schedule_dialog(driver)
    post_xpaths = [
        '//div[@role="dialog"]//*[@role="button" and not(@aria-disabled="true") and .//*[normalize-space(.)="Đăng"]]',
        '//div[@role="dialog"]//*[@role="button" and not(@aria-disabled="true") and .//*[normalize-space(.)="Post"]]',
        '//div[@role="dialog"]//*[@role="button" and not(@aria-disabled="true") and normalize-space(.)="Đăng"]',
        '//div[@role="dialog"]//*[@role="button" and not(@aria-disabled="true") and normalize-space(.)="Dang"]',
        '//div[@role="dialog"]//*[@role="button" and not(@aria-disabled="true") and normalize-space(.)="Post"]',
        '//div[@role="dialog"]//*[@role="button" and not(@aria-disabled="true") and normalize-space(.)="Đăng ngay"]',
        '//div[@role="dialog"]//*[@role="button" and not(@aria-disabled="true") and normalize-space(.)="Post now"]',
        '//*[@role="button" and not(@aria-disabled="true") and normalize-space(.)="Đăng"]',
        '//*[@role="button" and not(@aria-disabled="true") and normalize-space(.)="Post"]',
    ]
    click_first_by_xpath(driver, post_xpaths, timeout=DEFAULT_TIMEOUT, name="nut Dang/Post")


def wait_after_post(driver: WebDriver, timeout: int = 120) -> None:
    end_time = time.time() + timeout
    success_words = [
        "bài viết của bạn đã được đăng",
        "your post has been published",
        "your post is now published",
        "posted",
    ]
    while time.time() < end_time:
        text = page_text(driver).lower()
        if any(word in text for word in success_words):
            return
        try:
            dialogs = [d for d in driver.find_elements(By.XPATH, '//*[@role="dialog"]') if d.is_displayed()]
            if not dialogs:
                return
        except Exception:
            return
        time.sleep(2)


def make_unique_target(directory: Path, source_name: str) -> Path:
    directory.mkdir(exist_ok=True)
    source = Path(source_name)
    target = directory / source.name
    if not target.exists():
        return target
    counter = 1
    while True:
        candidate = directory / f"{source.stem} ({counter}){source.suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def move_successful_video(video_path: Path) -> None:
    if not video_path.exists():
        return
    target = make_unique_target(UPLOADED_DIR, video_path.name)
    shutil.move(str(video_path), str(target))
    print(f"[OK] Da chuyen video Facebook thanh cong sang: {target}")


def needs_safe_facebook_filename(video_path: Path) -> bool:
    if not SAFE_FACEBOOK_FILENAME_RE.match(video_path.name):
        return True
    try:
        str(video_path.resolve()).encode("ascii")
    except UnicodeEncodeError:
        return True
    return len(str(video_path.resolve())) > 210


def make_safe_facebook_upload_copy(video_path: Path) -> Path:
    if not needs_safe_facebook_filename(video_path):
        return video_path
    TEMP_UPLOAD_DIR.mkdir(exist_ok=True)
    suffix = video_path.suffix.lower()
    safe_name = f"facebook_video_{time.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}{suffix}"
    temp_path = TEMP_UPLOAD_DIR / safe_name
    print(f"[INFO] Ten file co ky tu de gay loi Facebook, tao ban copy tam: {temp_path.name}")
    shutil.copy2(str(video_path), str(temp_path))
    return temp_path


def find_ffmpeg_executable() -> str | None:
    if LOCAL_FFMPEG_FILE.exists() and os.name == "nt":
        return str(LOCAL_FFMPEG_FILE)
    return shutil.which("ffmpeg")


def make_facebook_compatible_video(video_path: Path, args: argparse.Namespace) -> Path:
    print("[INFO] Bo qua chuyen doi Facebook, upload noi dung video goc.")
    return make_safe_facebook_upload_copy(video_path)


def cleanup_temp_upload_copy(upload_path: Path, original_path: Path) -> None:
    if upload_path == original_path:
        return
    try:
        upload_path.unlink(missing_ok=True)
        print(f"[INFO] Da xoa ban copy tam Facebook: {upload_path.name}")
    except Exception as exc:
        print(f"[CANH BAO] Khong xoa duoc ban copy tam Facebook {upload_path}: {exc}")


def upload_one_video(driver: WebDriver, video_path: Path, args: argparse.Namespace) -> None:
    print(f"\n[INFO] Dang upload Facebook: {video_path}")
    upload_path = make_facebook_compatible_video(video_path, args)
    try:
        target_url = facebook_english_url(args.target_url)
        print(f"[INFO] Mo Facebook bang ngon ngu English: {target_url}")
        driver.get(target_url)
        wait_facebook_ready(driver)
        open_post_composer(driver)
        attach_video_file(driver, upload_path)
        caption = build_caption(video_path, args)
        print(f"[INFO] Caption Facebook: {caption[:200]}{'...' if len(caption) > 200 else ''}")
        set_caption(driver, caption)
        wait_upload_ready(driver)
        click_next_steps(driver)
        wait_upload_ready(driver)
        click_post(driver)
        wait_after_post(driver)
        time.sleep(args.after_post_wait)
        print(f"[OK] Da bam Dang/Post Facebook: {video_path.name}")
    except Exception:
        save_debug_artifacts(driver, f"upload_failed_{video_path.stem}")
        raise
    finally:
        cleanup_temp_upload_copy(upload_path, video_path)


def upload_one_reel(api: FacebookReelsAPI, video_path: Path, args: argparse.Namespace) -> None:
    print(f"\n[INFO] Dang upload Facebook Reels API: {video_path}")
    upload_path = make_facebook_compatible_video(video_path, args)
    caption = build_caption(video_path, args)
    print(f"[INFO] Caption/Reels description: {caption[:200]}{'...' if len(caption) > 200 else ''}")
    try:
        video_id = api.upload_reel(upload_path, caption, args.publish_time)
        print(f"[OK] Da publish Facebook Reel: {video_path.name} | video_id={video_id}")
    finally:
        cleanup_temp_upload_copy(upload_path, video_path)


def run_api_upload(args: argparse.Namespace, videos: list[Path]) -> tuple[list[Path], list[tuple[Path, str]]]:
    page_id = (args.page_id or os.environ.get("FACEBOOK_PAGE_ID") or "").strip()
    page_token = (args.page_token or os.environ.get("FACEBOOK_PAGE_TOKEN") or "").strip()
    if not page_id or not page_token:
        print("[LOI] Che do reels-api can --page-id va --page-token (hoac bien moi truong FACEBOOK_PAGE_ID/FACEBOOK_PAGE_TOKEN).")
        sys.exit(1)

    api = FacebookReelsAPI(page_id, page_token, args.api_version)
    print(f"[INFO] Dang kiem tra Page Access Token voi Graph API {api.api_version}...")
    if not api.is_page_access_token_valid():
        print(f"[LOI] Page ID/Token khong hop le hoac thieu quyen. Facebook tra ve: {api.json}")
        sys.exit(1)
    print("[OK] Page Access Token hop le.")

    successes: list[Path] = []
    failures: list[tuple[Path, str]] = []
    for index, video in enumerate(videos, start=1):
        print(f"\n[TIEN DO] Facebook Reels API video {index}/{len(videos)}")
        try:
            upload_one_reel(api, video, args)
            successes.append(video)
            if index < len(videos) and args.delay > 0:
                time.sleep(args.delay)
        except KeyboardInterrupt:
            raise
        except Exception as exc:
            message = str(exc) or exc.__class__.__name__
            failures.append((video, message))
            print(f"[LOI] Upload Facebook Reels API loi, bo qua video nay: {video.name}")
            print(f"[LOI] Chi tiet: {message}")
            if args.stop_on_error:
                break
    return successes, failures


def run_browser_upload(args: argparse.Namespace, videos: list[Path]) -> tuple[list[Path], list[tuple[Path, str]]]:
    driver = build_driver(chrome_binary=args.chrome_binary, attach=args.attach)
    successes: list[Path] = []
    failures: list[tuple[Path, str]] = []
    try:
        for index, video in enumerate(videos, start=1):
            print(f"\n[TIEN DO] Facebook browser video {index}/{len(videos)}")
            try:
                upload_one_video(driver, video, args)
                successes.append(video)
                if index < len(videos) and args.delay > 0:
                    time.sleep(args.delay)
            except KeyboardInterrupt:
                raise
            except Exception as exc:
                message = str(exc) or exc.__class__.__name__
                failures.append((video, message))
                print(f"[LOI] Upload Facebook browser loi, bo qua video nay: {video.name}")
                print(f"[LOI] Chi tiet: {message}")
                if args.stop_on_error:
                    break
    finally:
        if args.attach:
            print("[INFO] Dang dung --attach nen tool khong dong Chrome cua ban.")
        else:
            driver.quit()
    return successes, failures


def run_upload(args: argparse.Namespace) -> None:
    if args.video:
        video_path = resolve_base_path(args.video, VIDEOS_DIR)
        if not video_path.exists():
            print(f"[LOI] Khong thay file video: {video_path}")
            sys.exit(1)
        videos = [video_path]
    elif args.all:
        videos = get_video_files(resolve_base_path(args.video_dir, VIDEOS_DIR))
    else:
        print("[LOI] Chon --all hoac --video")
        sys.exit(1)

    if not videos:
        print("[LOI] Khong co video de upload Facebook.")
        sys.exit(1)

    args.default_description = read_text_file(args.description_file)

    print("Danh sach video se upload Facebook:")
    for video in videos:
        print(f"- {video.name}")
    print(f"\nChe do Facebook: {args.mode}")
    if args.mode == "browser":
        print(f"Target URL: {args.target_url}")
    else:
        print(f"Page ID: {args.page_id or os.environ.get('FACEBOOK_PAGE_ID') or '(chua nhap)'}")
        print(f"Graph API version: {args.api_version}")
    print("\nMo ta dung chung:")
    print(args.default_description[:500] + ("..." if len(args.default_description) > 500 else ""))

    if not args.yes:
        confirm = input("Tiep tuc upload Facebook? Nhap YES de xac nhan: ").strip()
        if confirm != "YES":
            print("Da huy.")
            return

    if args.mode == "reels-api":
        successes, failures = run_api_upload(args, videos)
    else:
        successes, failures = run_browser_upload(args, videos)

    print("\n=== Tong ket upload Facebook ===")
    print(f"[OK] Thanh cong: {len(successes)}/{len(videos)}")
    if failures:
        print(f"[LOI] That bai: {len(failures)}")
        for video, message in failures:
            print(f"- {video.name}: {message}")
        sys.exit(1)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Facebook web auto upload")
    parser.add_argument("--login", action="store_true", help="Mo Chrome de dang nhap Facebook")
    parser.add_argument("--mode", choices=["reels-api", "browser"], default="reels-api", help="Kieu upload Facebook")
    parser.add_argument("--attach", action="store_true", help="Ket noi Chrome da mo bang --login")
    parser.add_argument("--all", action="store_true", help="Upload tat ca video trong thu muc")
    parser.add_argument("--video", help="Upload 1 file video cu the")
    parser.add_argument("--video-dir", default="videos", help="Thu muc lay video khi dung --all")
    parser.add_argument("--target-url", default="https://www.facebook.com", help="Trang Facebook/Profile/Page/Group can dang")
    parser.add_argument("--page-id", default="", help="Facebook Page ID dung cho Reels API")
    parser.add_argument("--page-token", default="", help="Page Access Token dung cho Reels API")
    parser.add_argument("--api-version", default=DEFAULT_API_VERSION, help="Graph API version, vi du v23.0")
    parser.add_argument("--publish-time", default=None, help="Len lich publish Reels, dung timestamp/UTC neu Facebook ho tro")
    parser.add_argument("--title", default="", help="Tieu de/caption rieng. Neu bo trong thi tu lay ten file")
    parser.add_argument("--description", default="", help="Mo ta dung chung neu khong dung file .txt")
    parser.add_argument("--description-file", default="facebook_description.txt", help="File mo ta Facebook")
    parser.add_argument("--delay", type=int, default=10, help="So giay nghi giua moi video")
    parser.add_argument("--after-post-wait", type=int, default=20, help="So giay doi sau khi bam Post")
    parser.add_argument("--stop-on-error", action="store_true", help="Dung ngay khi mot video loi")
    parser.add_argument("--yes", action="store_true", help="Bo qua xac nhan YES")
    parser.add_argument("--no-convert", action="store_true", help="Khong chuyen video sang chuan Facebook bang FFmpeg truoc khi upload")
    parser.add_argument("--chrome-binary", help="Duong dan chrome.exe neu can")
    parser.add_argument("--profile-dir", help="Thu muc Chrome profile rieng neu can chay song song")
    parser.add_argument("--debug-port", type=int, default=DEBUG_PORT, help="Cong remote debugging Chrome")
    return parser.parse_args()


def main() -> None:
    global PROFILE_DIR, DEBUG_PORT
    args = parse_args()
    PROFILE_DIR = resolve_base_path(args.profile_dir, PROFILE_DIR)
    DEBUG_PORT = args.debug_port
    if args.login:
        open_manual_chrome(args.chrome_binary, args.target_url)
        print("[OK] Da mo Facebook. Hay dang nhap, vao dung trang/Page/Group neu can, sau do giu nguyen Chrome.")
    else:
        run_upload(args)


if __name__ == "__main__":
    main()
