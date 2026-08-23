"""
Mstar YouTube Auto Upload Bot - FIXED V4

Ban nay dung dung nhu yeu cau:
- Tieu de YouTube = ten file video, bo phan duoi .mp4/.mov/...
- Mo ta = dung chung noi dung trong default_description.txt cho tat ca video
- Dang cong khai mac dinh neu chay file run_upload_all_public_same_description.bat

Cach dung nhanh:
1) pip install -r requirements.txt
2) python main.py --login
3) Dang nhap YouTube Studio tren Chrome vua mo, GIU NGUYEN cua so Chrome do
4) Copy video vao thu muc videos/
5) Chay: run_upload_all_public_same_description.bat

Luu y: Tool nay dieu khien giao dien YouTube Studio bang trinh duyet.
Neu YouTube doi giao dien, co the can sua lai nut/selector.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import time
import unicodedata
from pathlib import Path
from typing import Iterable, Optional

import pyperclip
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

BASE_DIR = Path(__file__).resolve().parent
VIDEOS_DIR = BASE_DIR / "videos"
UPLOADED_DIR = BASE_DIR / "uploaded_success"
PROFILE_DIR = BASE_DIR / "chrome-profile"
LOCAL_CHROMEDRIVER = BASE_DIR / "chromedriver.exe"
DEFAULT_DESCRIPTION_FILE = BASE_DIR / "default_description.txt"

VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}
DEFAULT_TIMEOUT = 30
UPLOAD_TIMEOUT = 60 * 60
DEBUG_PORT = 9222
DEFAULT_UPLOAD_DELAY = 2
AFTER_FILE_SELECTED_DELAY = 3
AFTER_NEXT_CLICK_DELAY = 1
MAX_FILE_SELECT_RETRIES = 3

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def read_text_file(path_value: str | None) -> str:
    """Doc mo ta tu file .txt, ho tro tieng Viet va nhieu dong."""
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


def get_video_files(video_dir: Path | None = None) -> list[Path]:
    source_dir = video_dir or VIDEOS_DIR
    source_dir.mkdir(parents=True, exist_ok=True)
    videos = [p for p in source_dir.rglob("*") if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS]
    return sorted(videos, key=lambda p: str(p).lower())


def find_chrome_executable(chrome_binary: Optional[str] = None) -> str:
    """Tim Chrome tren Windows/Linux."""
    if chrome_binary:
        return chrome_binary

    if os.name != "nt":
        for name in ("google-chrome", "google-chrome-stable", "chromium-browser", "chromium", "chrome"):
            if shutil.which(name):
                return name
        return "google-chrome"

    candidates = []
    env_paths = [os.environ.get("PROGRAMFILES"), os.environ.get("PROGRAMFILES(X86)"), os.environ.get("LOCALAPPDATA")]
    for base in env_paths:
        if not base:
            continue
        candidates.extend([
            Path(base) / "Google" / "Chrome" / "Application" / "chrome.exe",
            Path(base) / "Google" / "Chrome Beta" / "Application" / "chrome.exe",
            Path(base) / "Google" / "Chrome SxS" / "Application" / "chrome.exe",
        ])

    for path in candidates:
        if path.exists():
            return str(path)
    return "chrome"


def open_manual_chrome(chrome_binary: Optional[str] = None, with_debug: bool = True) -> None:
    """Mo Chrome that, khong qua Selenium, de dang nhap Google/YouTube."""
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    chrome = find_chrome_executable(chrome_binary)

    cmd = [
        chrome,
        f"--user-data-dir={PROFILE_DIR}",
        "--profile-directory=Default",
        "--start-maximized",
    ]
    if with_debug:
        cmd.insert(1, f"--remote-debugging-port={DEBUG_PORT}")
    cmd.append("https://studio.youtube.com")

    try:
        subprocess.Popen(cmd)
    except FileNotFoundError:
        print("[LOI] Khong tim thay Google Chrome.")
        print("Hay cai Google Chrome hoac truyen duong dan bang --chrome-binary")
        raise


def build_driver(chrome_binary: Optional[str] = None, attach: bool = False) -> WebDriver:
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)

    options = Options()
    options.add_argument("--start-maximized")
    options.add_argument("--log-level=3")
    options.add_argument("--disable-notifications")

    if attach:
        options.add_experimental_option("debuggerAddress", f"127.0.0.1:{DEBUG_PORT}")
    else:
        options.add_argument(f"--user-data-dir={PROFILE_DIR}")
        options.add_argument("--profile-directory=Default")

    if chrome_binary:
        options.binary_location = chrome_binary

    try:
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
            service = Service(executable_path=str(LOCAL_CHROMEDRIVER))
            return webdriver.Chrome(service=service, options=options)
    except WebDriverException as exc:
        print("\n[LOI] Khong mo/ket noi duoc Chrome.")
        if attach:
            print("- Hay mo Chrome truoc bang: python main.py --login")
            print("- Dang nhap xong phai GIU NGUYEN cua so Chrome do.")
            print(f"- Cong ket noi mac dinh: {DEBUG_PORT}")
        else:
            print("- Hay cap nhat Google Chrome len ban moi nhat.")
            print("- Hoac tai chromedriver.exe dung phien ban Chrome va dat cung thu muc main.py.")
        print(f"Chi tiet loi: {exc}")
        raise


def wait_click(driver: WebDriver, locators: Iterable[tuple[str, str]], timeout: int = DEFAULT_TIMEOUT, name: str = "element") -> None:
    last_error: Optional[Exception] = None
    end_time = time.time() + timeout

    while time.time() < end_time:
        for by, value in locators:
            try:
                element = WebDriverWait(driver, 3).until(EC.element_to_be_clickable((by, value)))
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
                time.sleep(0.2)
                element.click()
                return
            except Exception as exc:
                last_error = exc
        time.sleep(0.5)

    raise TimeoutException(f"Khong tim/click duoc {name}. Loi cuoi: {last_error}")


def js_click_first(driver: WebDriver, locators: Iterable[tuple[str, str]], timeout: int = DEFAULT_TIMEOUT, name: str = "element") -> None:
    last_error: Optional[Exception] = None
    end_time = time.time() + timeout

    while time.time() < end_time:
        for by, value in locators:
            try:
                element = WebDriverWait(driver, 3).until(EC.presence_of_element_located((by, value)))
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
                time.sleep(0.2)
                driver.execute_script("arguments[0].click();", element)
                return
            except Exception as exc:
                last_error = exc
        time.sleep(0.5)

    raise TimeoutException(f"Khong JS-click duoc {name}. Loi cuoi: {last_error}")


def find_file_input(driver: WebDriver, timeout: int = DEFAULT_TIMEOUT):
    return WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='file']"))
    )


def visible_textboxes(driver: WebDriver) -> list:
    try:
        return [box for box in driver.find_elements(By.CSS_SELECTOR, "#textbox") if box.is_displayed()]
    except Exception:
        return []


def get_body_text(driver: WebDriver) -> str:
    try:
        return driver.find_element(By.TAG_NAME, "body").text
    except Exception:
        return ""


def text_key(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    without_marks = "".join(char for char in normalized if not unicodedata.combining(char))
    return without_marks.lower().replace("đ", "d").replace("Đ", "d")


def element_text_key(element) -> str:
    try:
        text = element.text or element.get_attribute("innerText") or element.get_attribute("aria-label") or ""
    except Exception:
        text = ""
    return text_key(text)


def find_visible_click_target_by_text_key(driver: WebDriver, text_markers: Iterable[str], root=None):
    """Tim nut theo text khong dau de tranh loi encoding/YouTube doi ngon ngu."""
    marker_keys = [text_key(marker) for marker in text_markers if marker]
    search_root = root or driver
    selectors = [
        "button",
        "ytcp-button",
        "[role='button']",
        "tp-yt-paper-button",
        "ytcp-icon-button",
    ]
    for selector in selectors:
        try:
            elements = search_root.find_elements(By.CSS_SELECTOR, selector)
        except Exception:
            continue
        for element in elements:
            try:
                if not element.is_displayed():
                    continue
                key = element_text_key(element)
                if any(marker in key for marker in marker_keys):
                    return element
            except Exception:
                continue
    return None


def get_active_surface_text(driver: WebDriver) -> str:
    """Uu tien text trong hop thoai upload, tranh doc nham loi cua cac video cu phia sau."""
    dialog_texts: list[str] = []
    for selector in ("ytcp-uploads-dialog", "[role='dialog']"):
        try:
            for element in driver.find_elements(By.CSS_SELECTOR, selector):
                if element.is_displayed():
                    text = (element.text or element.get_attribute("innerText") or "").strip()
                    if text and text not in dialog_texts:
                        dialog_texts.append(text)
        except Exception:
            pass
    return "\n".join(dialog_texts) if dialog_texts else get_body_text(driver)


def has_upload_error(driver: WebDriver) -> bool:
    body_key = text_key(get_active_surface_text(driver))
    markers = [
        "không thể tải lên",
        "khong the tai len",
        "không tải lên được",
        "khong tai len duoc",
        "upload failed",
        "couldn't upload",
        "could not upload",
        "processing abandoned",
        "processing failed",
        "unable to process",
        "video failed to process",
        "không thể tải lên",
        "không tải lên được",
    ]
    markers.extend([
        "qua trinh tai len bi gian doan",
        "nhap vao tiep tuc tai len",
        "tiep tuc tai len",
        "upload interrupted",
    ])
    if any(text_key(marker) in body_key for marker in markers):
        return True

    if find_visible_click_target_by_text_key(driver, ("tiep tuc tai", "continue upload", "retry")) is not None:
        return True

    button_locators = [
        (By.XPATH, '//*[self::button or self::ytcp-button][contains(normalize-space(.), "Tiếp tục tải")]'),
        (By.XPATH, '//*[self::button or self::ytcp-button][contains(normalize-space(.), "Tiep tuc tai")]'),
        (By.XPATH, '//*[self::button or self::ytcp-button][contains(normalize-space(.), "Continue upload")]'),
        (By.XPATH, '//*[self::button or self::ytcp-button][contains(normalize-space(.), "Retry")]'),
    ]
    for by, value in button_locators:
        try:
            if any(element.is_displayed() for element in driver.find_elements(by, value)):
                return True
        except Exception:
            pass
    return False


def click_continue_upload(driver: WebDriver) -> bool:
    deadline = time.time() + 15
    while time.time() < deadline:
        target = find_visible_click_target_by_text_key(
            driver,
            ("tiep tuc tai", "continue upload", "retry"),
        )
        if target is not None:
            try:
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", target)
                time.sleep(0.2)
                driver.execute_script("arguments[0].click();", target)
                time.sleep(2)
                return True
            except Exception:
                pass
        time.sleep(0.5)

    locators = [
        (By.XPATH, '//*[self::button or self::ytcp-button][contains(normalize-space(.), "Tiếp tục tải")]'),
        (By.XPATH, '//*[self::button or self::ytcp-button][contains(normalize-space(.), "Tiep tuc tai")]'),
        (By.XPATH, '//*[self::button or self::ytcp-button][contains(normalize-space(.), "Continue upload")]'),
        (By.XPATH, '//*[self::button or self::ytcp-button][contains(normalize-space(.), "Retry")]'),
    ]
    try:
        js_click_first(driver, locators, timeout=15, name='nut "Tiep tuc tai len"')
        time.sleep(2)
        return True
    except Exception:
        return False


def upload_status_text(driver: WebDriver) -> str:
    texts: list[str] = []
    selectors = [
        "#progress-label",
        "#upload-progress",
        "ytcp-video-upload-progress",
        "[class*='progress-label']",
        "[class*='upload-progress']",
    ]
    for selector in selectors:
        try:
            for element in driver.find_elements(By.CSS_SELECTOR, selector):
                if element.is_displayed():
                    text = (element.text or element.get_attribute("innerText") or "").strip()
                    if text and text not in texts:
                        texts.append(text)
        except Exception:
            pass
    body_text = get_active_surface_text(driver)
    if body_text:
        texts.append(body_text)
    return "\n".join(texts)


def wait_for_upload_completion(driver: WebDriver, video_path: Path, timeout: int = UPLOAD_TIMEOUT) -> None:
    """Khong cho chuyen video khi file hien tai chua tai len du 100%."""
    complete_markers = [
        "Đã tải lên 100%",
        "Da tai len 100%",
        "Upload complete",
        "Upload completed",
        "Finished uploading",
        "Đã hoàn tất quá trình tải lên",
        "Da hoan tat qua trinh tai len",
    ]
    percent_100 = re.compile(
        r"(?:tải lên|tai len|upload(?:ing|ed)?)\D{0,30}100\s*%|"
        r"100\s*%\D{0,30}(?:tải lên|tai len|upload)",
        re.I,
    )
    progress_pattern = re.compile(r"(\d{1,3})\s*%")
    deadline = time.time() + timeout
    recovery_count = 0
    last_percent = -1

    print("[INFO] Dang cho YouTube tai file len du 100%...")
    while time.time() < deadline:
        status_text = upload_status_text(driver)

        if has_upload_error(driver):
            if recovery_count >= MAX_FILE_SELECT_RETRIES:
                raise RuntimeError(
                    f"YouTube lien tuc bao tai len bi gian do sau {MAX_FILE_SELECT_RETRIES} lan thu lai"
                )
            recovery_count += 1
            print(
                f"[CANH BAO] Tai len bi gian do. Dang bam Tiep tuc tai len va chon lai file "
                f"({recovery_count}/{MAX_FILE_SELECT_RETRIES})..."
            )
            if not click_continue_upload(driver):
                raise RuntimeError('Khong bam duoc nut "Tiep tuc tai len" sau khi upload bi gian do')
            file_input = find_file_input(driver, timeout=30)
            file_input.send_keys(str(video_path.resolve()))
            time.sleep(3)
            continue

        lowered = status_text.lower()
        if any(marker.lower() in lowered for marker in complete_markers) or percent_100.search(status_text):
            print("[OK] YouTube da nhan du 100% file video.")
            return

        percentages = [int(value) for value in progress_pattern.findall(status_text)]
        current_percent = max((value for value in percentages if 0 <= value <= 100), default=-1)
        if current_percent > last_percent:
            last_percent = current_percent
            print(f"[UPLOAD] Da tai len: {current_percent}%")

        if is_done_button_ready(driver):
            print("[OK] Nut Publish/Done da san sang, coi nhu YouTube da nhan xong file.")
            return
        time.sleep(2)

    raise TimeoutException(f"YouTube chua xac nhan tai len 100%: {video_path.name}")


def select_video_file_with_recovery(driver: WebDriver, video_path: Path) -> None:
    """Chon file va tu bam Tiep tuc tai len + chon lai neu Studio bao loi."""
    resolved_path = str(video_path.resolve())
    last_error = ""

    for attempt in range(1, MAX_FILE_SELECT_RETRIES + 1):
        print(f"[INFO] Chon file upload lan {attempt}/{MAX_FILE_SELECT_RETRIES}: {video_path.name}")
        file_input = find_file_input(driver, timeout=30)
        file_input.send_keys(resolved_path)

        end_time = time.time() + 25
        while time.time() < end_time:
            if len(visible_textboxes(driver)) >= 2 and not has_upload_error(driver):
                return
            if has_upload_error(driver):
                last_error = "YouTube Studio bao khong the tai len"
                print("[CANH BAO] YouTube bao loi tai len. Dang bam Tiep tuc tai len va chon lai dung file...")
                click_continue_upload(driver)
                time.sleep(2)
                break
            time.sleep(1)
        else:
            if len(visible_textboxes(driver)) >= 2:
                return
            last_error = "Qua thoi gian cho man hinh Chi tiet video"

        if attempt < MAX_FILE_SELECT_RETRIES:
            try:
                find_file_input(driver, timeout=8)
            except TimeoutException:
                print("[INFO] Mo lai hop thoai upload de thu chon file lan nua...")
                click_upload_button(driver)

    raise RuntimeError(
        f"Khong the tai file {video_path.name} sau {MAX_FILE_SELECT_RETRIES} lan thu. {last_error}"
    )


def is_upload_wizard_open(driver: WebDriver) -> bool:
    try:
        visible_controls = driver.find_elements(By.CSS_SELECTOR, "#next-button, #done-button")
        if any(control.is_displayed() for control in visible_controls):
            return True
    except Exception:
        pass

    body_text = get_body_text(driver)
    markers = [
        "Chi tiết",
        "Các thành phần của video",
        "Kiểm tra",
        "Chế độ hiển thị",
        "Tiếp",
        "Đối tượng người xem",
    ]
    return any(marker in body_text for marker in markers)


def wait_studio_idle(driver: WebDriver, timeout: int = 120) -> None:
    saving_markers = [
        "Đang lưu",
        "Dang luu",
        "Saving",
        "Processing",
        "Đang xử lý",
        "Dang xu ly",
    ]
    end_time = time.time() + timeout
    while time.time() < end_time:
        body_text = get_body_text(driver)
        if not any(marker in body_text for marker in saving_markers):
            return
        time.sleep(1)
    print("[CANH BAO] YouTube Studio van dang luu/xu ly cham, thu bam tiep.")


def ensure_logged_in(driver: WebDriver) -> None:
    current = driver.current_url.lower()
    if "accounts.google.com" in current or "signin" in current:
        raise RuntimeError(
            "Chua dang nhap YouTube Studio hoac Google dang chan dang nhap.\n"
            "Cach xu ly: chay `python main.py --login`, dang nhap tren Chrome vua mo, GIU NGUYEN Chrome do, "
            "roi upload bang `python main.py --attach --all --visibility public --description-file default_description.txt`."
        )


def studio_content_url(driver: WebDriver) -> str:
    match = re.search(r"studio\.youtube\.com/channel/([^/?#]+)", driver.current_url)
    if match:
        return f"https://studio.youtube.com/channel/{match.group(1)}/videos/upload"
    return "https://studio.youtube.com/videos/upload"


def is_studio_content_page(driver: WebDriver) -> bool:
    current = driver.current_url.lower()
    if "/videos" in current:
        return True
    body_text = get_body_text(driver).lower()
    markers = [
        "channel content",
        "videos",
        "draft",
        "edit draft",
        "noi dung",
        "nội dung",
        "ban nhap",
        "bản nháp",
        "chinh sua ban nhap",
        "chỉnh sửa bản nháp",
    ]
    return any(marker in body_text for marker in markers)


def open_studio_content_page(driver: WebDriver, timeout: int = 45) -> None:
    """Mo trang danh sach video, tranh YouTube Studio tu day ve dashboard."""
    target_url = studio_content_url(driver)
    print(f"[INFO] Dang mo trang Noi dung: {target_url}")
    driver.get(target_url)
    time.sleep(5)
    ensure_logged_in(driver)

    if not is_studio_content_page(driver):
        content_locators = [
            (By.CSS_SELECTOR, 'a[href*="/videos"]'),
            (By.XPATH, '//*[@aria-label="Content" or @title="Content"]'),
            (By.XPATH, '//*[@aria-label="Nội dung" or @title="Nội dung"]'),
            (By.XPATH, '//*[@aria-label="Noi dung" or @title="Noi dung"]'),
            (By.XPATH, '//*[contains(normalize-space(.), "Nội dung")]'),
            (By.XPATH, '//*[contains(normalize-space(.), "Noi dung")]'),
            (By.XPATH, '//*[contains(normalize-space(.), "Content")]'),
        ]
        try:
            js_click_first(driver, content_locators, timeout=10, name="menu Noi dung/Content")
            time.sleep(5)
        except TimeoutException:
            pass

    end_time = time.time() + timeout
    while time.time() < end_time:
        if is_studio_content_page(driver):
            return
        time.sleep(1)

    raise TimeoutException("YouTube Studio van o trang tong quan, chua vao duoc trang Noi dung/Videos.")


def click_upload_button(driver: WebDriver) -> None:
    driver.set_page_load_timeout(15)
    try:
        driver.get("https://studio.youtube.com")
    except TimeoutException:
        print("[CANH BAO] YouTube Studio tai trang cham, tiep tuc voi trang hien tai.")
    time.sleep(5)
    if "studio.youtube.com" not in driver.current_url.lower():
        manage_locators = [
            (By.CSS_SELECTOR, 'a[href*="studio.youtube.com/channel"][href*="/videos"]'),
            (By.CSS_SELECTOR, 'a[href*="studio.youtube.com/channel"]'),
            (By.XPATH, '//*[contains(normalize-space(.), "Quản lý video")]'),
            (By.XPATH, '//*[contains(normalize-space(.), "Quan ly video")]'),
            (By.XPATH, '//*[contains(normalize-space(.), "Manage videos")]'),
        ]
        wait_click(driver, manage_locators, timeout=20, name="nut Quan ly video")
        time.sleep(5)

    ensure_logged_in(driver)

    upload_icon_locators = [
        (By.CSS_SELECTOR, "ytcp-icon-button#upload-icon"),
        (By.CSS_SELECTOR, "#upload-icon"),
        (By.XPATH, '//*[@id="upload-icon"]'),
        (By.XPATH, '//*[contains(@aria-label, "Tải video lên") or contains(@aria-label, "Tai video len")]'),
        (By.XPATH, '//*[contains(@aria-label, "Upload videos") or contains(@aria-label, "Upload video")]'),
        (By.XPATH, '//button[contains(@aria-label, "Create") or contains(@aria-label, "Tạo") or contains(normalize-space(.), "Tạo")]'),
        (By.XPATH, '//ytcp-button[contains(@aria-label, "Create") or contains(@aria-label, "Tạo")]'),
        (By.XPATH, '//*[contains(@aria-label, "Create") or contains(@aria-label, "Tạo")]'),
    ]

    js_click_first(driver, upload_icon_locators, timeout=60, name="nut upload/create")
    time.sleep(1)

    menu_locators = [
        (By.XPATH, '//*[contains(text(), "Upload videos")]'),
        (By.XPATH, '//*[contains(text(), "Tải video lên")]'),
        (By.XPATH, '//*[contains(text(), "Tai video len")]'),
        (By.XPATH, '//*[@test-id="upload-beta"]'),
    ]

    try:
        find_file_input(driver, timeout=5)
        return
    except TimeoutException:
        wait_click(driver, menu_locators, timeout=20, name="menu Upload videos")


def paste_into_textbox(driver: WebDriver, textbox_index: int, text: str) -> None:
    """Dien title/description bang copy-paste de giu tieng Viet, dau va xuong dong."""
    if text is None:
        return
    boxes = WebDriverWait(driver, DEFAULT_TIMEOUT).until(
        lambda current_driver: (
            current_boxes
            if len(current_boxes := visible_textboxes(current_driver)) > textbox_index
            else False
        )
    )
    box = boxes[textbox_index]
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", box)
    time.sleep(0.2)
    box.click()
    box.send_keys("\ue009" + "a")
    pyperclip.copy(text)
    box.send_keys("\ue009" + "v")
    time.sleep(0.5)

    actual_text = (box.get_attribute("innerText") or box.text or "").strip()
    expected_sample = text.strip()[:20]
    if expected_sample and expected_sample not in actual_text:
        # Fallback cho giao dien contenteditable moi cua YouTube Studio.
        driver.execute_script(
            """
            const box = arguments[0];
            const value = arguments[1];
            box.focus();
            box.textContent = value;
            box.dispatchEvent(new InputEvent('input', {
                bubbles: true,
                inputType: 'insertText',
                data: value
            }));
            box.dispatchEvent(new Event('change', {bubbles: true}));
            """,
            box,
            text,
        )
        time.sleep(0.5)
        actual_text = (box.get_attribute("innerText") or box.text or "").strip()
        if expected_sample not in actual_text:
            raise RuntimeError(f"YouTube Studio chua nhan noi dung textbox index {textbox_index}")


def fill_draft_description(driver: WebDriver, args: argparse.Namespace) -> None:
    description = append_hashtags(
        args.description or getattr(args, "default_description", "") or "",
        args.description_hashtags,
        5000,
    )
    if not description.strip():
        print("[INFO] Khong co noi dung mo ta de dien vao ban nhap.")
        return
    WebDriverWait(driver, DEFAULT_TIMEOUT).until(
        lambda current_driver: len(visible_textboxes(current_driver)) >= 2
    )
    paste_into_textbox(driver, 1, description)
    print("[OK] Da dien/cap nhat mo ta cho ban nhap.")


def normalize_hashtags(value: str) -> str:
    tags: list[str] = []
    for raw in (value or "").replace(",", " ").split():
        tag = raw.strip()
        if not tag:
            continue
        if not tag.startswith("#"):
            tag = "#" + tag
        if tag not in tags:
            tags.append(tag)
    return " ".join(tags)


def append_hashtags(text: str, hashtags: str, limit: int) -> str:
    base = (text or "").strip()
    tags = normalize_hashtags(hashtags)
    if not tags:
        return base[:limit]
    combined = f"{base} {tags}".strip()
    if len(combined) <= limit:
        return combined
    room = limit - len(tags) - 1
    if room <= 0:
        return tags[:limit]
    return f"{base[:room].rstrip()} {tags}"


def build_video_title(video_path: Path, args: argparse.Namespace) -> str:
    custom_title = (getattr(args, "title", "") or "").strip()
    base_title = custom_title or video_path.stem
    return append_hashtags(base_title, args.title_hashtags, 100)


def is_audience_option_selected(driver: WebDriver, radio_name: str) -> bool:
    checks = [
        f'return !!document.querySelector("input[name=\\"{radio_name}\\"]:checked");',
        (
            f'const input = document.querySelector("input[name=\\"{radio_name}\\"]");'
            'const radio = input && input.closest("[role=radio]");'
            'return !!(radio && radio.getAttribute("aria-checked") === "true");'
        ),
    ]
    for script in checks:
        try:
            if driver.execute_script(script):
                return True
        except Exception:
            pass
    return False


def set_audience(driver: WebDriver, made_for_kids: str) -> None:
    if made_for_kids == "skip":
        return

    if made_for_kids == "yes":
        radio_name = "VIDEO_MADE_FOR_KIDS_MFK"
        locators = [
            (By.NAME, "VIDEO_MADE_FOR_KIDS_MFK"),
            (By.XPATH, '//*[@name="VIDEO_MADE_FOR_KIDS_MFK"]'),
            (By.XPATH, '//*[@name="VIDEO_MADE_FOR_KIDS_MFK"]/ancestor::*[@role="radio"][1]'),
            (By.XPATH, "//*[contains(text(), \"Yes, it's made for kids\")]/ancestor::*[@role='radio'][1]"),
            (By.XPATH, '//*[contains(text(), "Có, video này dành cho trẻ em")]/ancestor::*[@role="radio"][1]'),
            (By.XPATH, '//*[contains(text(), "Có, nội dung này dành cho trẻ em")]/ancestor::*[@role="radio"][1]'),
            (By.XPATH, '//*[contains(text(), "Có, nội dung này dành cho trẻ em")]'),
        ]
    else:
        radio_name = "VIDEO_MADE_FOR_KIDS_NOT_MFK"
        locators = [
            (By.NAME, "VIDEO_MADE_FOR_KIDS_NOT_MFK"),
            (By.XPATH, '//*[@name="VIDEO_MADE_FOR_KIDS_NOT_MFK"]'),
            (By.XPATH, '//*[@name="VIDEO_MADE_FOR_KIDS_NOT_MFK"]/ancestor::*[@role="radio"][1]'),
            (By.XPATH, "//*[contains(text(), \"No, it's not made for kids\")]/ancestor::*[@role='radio'][1]"),
            (By.XPATH, "//*[contains(text(), \"No, it's not made for children\")]/ancestor::*[@role='radio'][1]"),
            (By.XPATH, '//*[contains(text(), "Không, video này không dành cho trẻ em")]/ancestor::*[@role="radio"][1]'),
            (By.XPATH, '//*[contains(text(), "Không, nội dung này không dành cho trẻ em")]/ancestor::*[@role="radio"][1]'),
            (By.XPATH, '//*[contains(text(), "Không, nội dung này không dành cho trẻ em")]'),
        ]

    try:
        js_click_first(driver, locators, timeout=30, name="lua chon video danh cho tre em")
        time.sleep(0.5)
        if not is_audience_option_selected(driver, radio_name):
            js_click_first(driver, locators, timeout=10, name="lua chon video danh cho tre em lan 2")
            time.sleep(0.5)
        if not is_audience_option_selected(driver, radio_name):
            raise RuntimeError("YouTube chua nhan lua chon muc tre em")
    except Exception as exc:
        body_text = get_body_text(driver)
        if "Bạn cần phải trả lời câu hỏi này" in body_text or "required" in body_text.lower():
            raise RuntimeError(f"Khong chon duoc muc tre em bat buoc: {exc}") from exc
        print(f"[CANH BAO] Khong chon duoc muc tre em, co the kenh da co default setting: {exc}")


def is_post_upload_page(driver: WebDriver) -> bool:
    current_url = driver.current_url.lower()
    wizard_open = is_upload_wizard_open(driver)
    if "/video/" in current_url and "/edit" in current_url and not wizard_open:
        return True
    if wizard_open:
        return False
    try:
        body_text = get_body_text(driver)
    except Exception:
        return False
    markers = [
        "Đã tải lên 100%",
        "Da tai len 100%",
        "Đã hoàn tất quá trình tải lên",
        "Da hoan tat qua trinh tai len",
        "Video đã xuất bản",
        "Video da xuat ban",
        "Đã lưu mọi thay đổi",
        "Da luu moi thay doi",
    ]
    return any(marker in body_text for marker in markers)


def click_next_buttons(driver: WebDriver, times: int = 3) -> bool:
    next_locators = [
        (By.CSS_SELECTOR, "#next-button"),
        (By.XPATH, '//*[@id="next-button"]'),
        (By.XPATH, '//ytcp-button[contains(., "Next") or contains(., "Tiếp")]'),
        (By.XPATH, '//*[contains(text(), "Next") or contains(text(), "Tiếp")]'),
    ]
    for idx in range(times):
        wait_studio_idle(driver)
        try:
            js_click_first(driver, next_locators, timeout=120, name=f"nut Next lan {idx + 1}")
        except TimeoutException:
            if is_post_upload_page(driver):
                print("[INFO] YouTube Studio da sang trang sau upload, khong can bam Next.")
                return False
            raise
        time.sleep(AFTER_NEXT_CLICK_DELAY)
    return True


def set_visibility(driver: WebDriver, visibility: str) -> None:
    visibility = visibility.lower().strip()
    if visibility == "skip":
        return

    name_map = {
        "private": "PRIVATE",
        "unlisted": "UNLISTED",
        "public": "PUBLIC",
    }
    vi_map = {
        "private": "Riêng tư",
        "unlisted": "Không công khai",
        "public": "Công khai",
    }
    en_map = {
        "private": "Private",
        "unlisted": "Unlisted",
        "public": "Public",
    }

    radio_name = name_map.get(visibility, "PRIVATE")
    locators = [
        (By.NAME, radio_name),
        (By.XPATH, f'//*[@name="{radio_name}"]'),
        (By.XPATH, f'//*[contains(text(), "{en_map.get(visibility, "Private")}")]/ancestor::*[@role="radio"][1]'),
        (By.XPATH, f'//*[contains(text(), "{vi_map.get(visibility, "Riêng tư")}")]/ancestor::*[@role="radio"][1]'),
    ]
    wait_click(driver, locators, timeout=60, name=f"chon che do {visibility}")


def is_done_button_ready(driver: WebDriver) -> bool:
    """YouTube co luc an dong 100% o buoc cuoi; nut Done bat la tin hieu an toan de tiep tuc."""
    try:
        return bool(
            driver.execute_script(
                """
                const candidates = [
                    document.querySelector('ytcp-button#done-button'),
                    document.querySelector('#done-button')
                ].filter(Boolean);
                return candidates.some((button) => {
                    const rect = button.getBoundingClientRect();
                    const style = window.getComputedStyle(button);
                    const nativeButton = button.querySelector('button') || button;
                    const ariaDisabled =
                        button.getAttribute('aria-disabled') === 'true' ||
                        nativeButton.getAttribute('aria-disabled') === 'true';
                    return rect.width > 0 &&
                        rect.height > 0 &&
                        style.visibility !== 'hidden' &&
                        style.display !== 'none' &&
                        !button.hasAttribute('disabled') &&
                        !nativeButton.disabled &&
                        !ariaDisabled;
                });
                """
            )
        )
    except Exception:
        return False


def click_done(driver: WebDriver) -> None:
    done_locators = [
        (By.CSS_SELECTOR, "ytcp-button#done-button"),
        (By.CSS_SELECTOR, "#done-button"),
        (By.XPATH, '//*[@id="done-button"]'),
    ]
    wait_click(driver, done_locators, timeout=UPLOAD_TIMEOUT, name="nut Publish/Done/Save")


def wait_after_done(driver: WebDriver, timeout: int = 60) -> None:
    """Xac nhan hop thoai upload da dong va khong xuat hien loi gian do."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if has_upload_error(driver):
            raise RuntimeError("YouTube bao tai len bi gian do sau khi bam Publish/Done")
        try:
            visible_done = any(
                element.is_displayed()
                for element in driver.find_elements(By.CSS_SELECTOR, "#done-button")
            )
        except Exception:
            visible_done = False
        if not visible_done and not is_upload_wizard_open(driver):
            return
        time.sleep(1)
    raise TimeoutException("YouTube chua dong hop thoai upload sau khi bam Publish/Done")


def verify_not_saved_as_draft(driver: WebDriver, timeout: int = 45) -> None:
    """Khong coi la thanh cong neu YouTube van bao video dang o Draft."""
    deadline = time.time() + timeout
    draft_markers = [
        "saved as draft",
        "save or publish",
        "draft",
        "bản nháp",
        "ban nhap",
        "luu duoi dang ban nhap",
    ]
    published_markers = [
        "video published",
        "your video has been published",
        "video is public",
        "public",
        "công khai",
        "cong khai",
        "đã xuất bản",
        "da xuat ban",
    ]
    while time.time() < deadline:
        if has_upload_error(driver):
            raise RuntimeError("YouTube bao loi upload/processing sau khi bam Publish/Done")
        try:
            if not is_upload_wizard_open(driver):
                return
        except Exception:
            return
        body_text = get_body_text(driver).lower()
        if any(marker in body_text for marker in draft_markers):
            raise RuntimeError(
                "YouTube dang luu video o ban nhap/draft. Tool khong chuyen file vao success; "
                "hay mo YouTube Studio kiem tra Visibility/Checks/Copyright roi publish lai."
            )
        if any(marker in body_text for marker in published_markers):
            print("[OK] YouTube khong bao video o ban nhap.")
            return
        time.sleep(1)


def upload_one_video(driver: WebDriver, video_path: Path, args: argparse.Namespace) -> None:
    print(f"\n=== Upload: {video_path.name} ===")

    click_upload_button(driver)
    select_video_file_with_recovery(driver, video_path)

    # DUNG THEO YEU CAU:
    # Tieu de = ten file video, khong lay metadata rieng.
    # Mo ta = dung chung default_description.txt hoac --description.
    title = build_video_title(video_path, args)
    description = append_hashtags(
        args.description or getattr(args, "default_description", "") or "",
        args.description_hashtags,
        5000,
    )

    time.sleep(AFTER_FILE_SELECTED_DELAY)
    paste_into_textbox(driver, 0, title)
    paste_into_textbox(driver, 1, description)
    set_audience(driver, args.made_for_kids)

    wizard_open = click_next_buttons(driver, 3)
    if wizard_open:
        set_visibility(driver, args.visibility)
        wait_for_upload_completion(driver, video_path)
        click_done(driver)
        wait_after_done(driver)
        if args.visibility == "public":
            verify_not_saved_as_draft(driver)
    else:
        raise RuntimeError(
            "YouTube dong trinh upload truoc khi tool xac nhan file da tai len 100%; "
            "khong danh dau video nay la thanh cong"
        )

    print(f"[OK] Da tai len 100% va hoan tat tren YouTube Studio: {video_path.name}")
    time.sleep(args.delay)


def make_unique_target(directory: Path, filename: str) -> Path:
    target = directory / filename
    if not target.exists():
        return target

    source_name = Path(filename)
    stem = source_name.stem
    suffix = source_name.suffix
    counter = 2
    while True:
        target = directory / f"{stem} ({counter}){suffix}"
        if not target.exists():
            return target
        counter += 1


def move_successful_video(video_path: Path) -> Path | None:
    if not video_path.exists():
        print(f"[CANH BAO] Khong thay file de chuyen sau upload: {video_path}")
        return None

    UPLOADED_DIR.mkdir(exist_ok=True)
    target = make_unique_target(UPLOADED_DIR, video_path.name)
    shutil.move(str(video_path), str(target))
    print(f"[OK] Da chuyen video thanh cong sang: {target}")
    return target


def recover_after_upload_error(driver: WebDriver) -> None:
    """Quay ve Studio de lan upload sau khong bi ket trong dialog loi."""
    try:
        print("[INFO] Dang reset trang YouTube Studio de tiep tuc video ke tiep...")
        driver.get("https://studio.youtube.com")
        time.sleep(5)
    except Exception as exc:
        print(f"[CANH BAO] Khong reset duoc Studio sau loi: {exc}")


def file_lookup_by_title(video_dir: Path) -> dict[str, Path]:
    videos = get_video_files(video_dir)
    lookup: dict[str, Path] = {}
    for video in videos:
        lookup[text_key(video.stem)] = video
    return lookup


def find_video_for_failed_row(row_text: str, lookup: dict[str, Path]) -> Path | None:
    row_key = text_key(row_text)
    best_match: tuple[int, Path] | None = None
    for title_key, video in lookup.items():
        if not title_key:
            continue
        if title_key in row_key or row_key in title_key:
            score = len(title_key)
            if best_match is None or score > best_match[0]:
                best_match = (score, video)
    return best_match[1] if best_match else None


def failed_upload_rows(driver: WebDriver) -> list:
    markers = (
        "qua trinh tai len bi gian doan",
        "tiep tuc tai len",
        "continue upload",
        "upload interrupted",
        "upload failed",
        "processing abandoned",
        "khong tai duoc video len",
        "khong the tai len",
    )
    rows = []
    try:
        candidates = driver.find_elements(By.CSS_SELECTOR, "ytcp-video-row")
    except Exception:
        candidates = []
    for row in candidates:
        try:
            row_text = (row.text or row.get_attribute("innerText") or "").strip()
            row_key = text_key(row_text)
            if any(marker in row_key for marker in markers):
                rows.append(row)
        except Exception:
            continue
    return rows


def wait_for_video_rows_text(driver: WebDriver, timeout: int = 60) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            rows = driver.find_elements(By.CSS_SELECTOR, "ytcp-video-row")
            for row in rows:
                row_text = (row.text or row.get_attribute("innerText") or "").strip()
                if row_text:
                    return
        except Exception:
            pass
        time.sleep(1)


def click_row_continue_upload(driver: WebDriver, row) -> None:
    target = find_visible_click_target_by_text_key(
        driver,
        ("tiep tuc tai", "continue upload", "retry"),
        root=row,
    )
    if target is not None:
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", target)
        time.sleep(0.2)
        driver.execute_script("arguments[0].click();", target)
        time.sleep(2)
        return

    locators = [
        './/*[self::button or self::ytcp-button][contains(normalize-space(.), "Tiếp tục tải")]',
        './/*[self::button or self::ytcp-button][contains(normalize-space(.), "Tiep tuc tai")]',
        './/*[self::button or self::ytcp-button][contains(normalize-space(.), "Continue upload")]',
        './/*[self::button or self::ytcp-button][contains(normalize-space(.), "Retry")]',
        './/*[contains(normalize-space(.), "Tiếp tục tải")]/ancestor::*[@role="button"][1]',
        './/*[contains(normalize-space(.), "Continue upload")]/ancestor::*[@role="button"][1]',
    ]
    last_error: Optional[Exception] = None
    for xpath in locators:
        try:
            targets = row.find_elements(By.XPATH, xpath)
            for target in targets:
                if not target.is_displayed():
                    continue
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", target)
                time.sleep(0.2)
                driver.execute_script("arguments[0].click();", target)
                time.sleep(2)
                return
        except Exception as exc:
            last_error = exc
    raise TimeoutException(f'Khong click duoc nut "Tiep tuc tai len" trong dong loi. Loi cuoi: {last_error}')


def finish_resumed_upload_if_needed(driver: WebDriver, video_path: Path, args: argparse.Namespace) -> None:
    wait_for_upload_completion(driver, video_path)
    if is_upload_wizard_open(driver):
        try:
            set_audience(driver, args.made_for_kids)
        except Exception as exc:
            print(f"[CANH BAO] Khong set duoc muc tre em sau khi upload lai: {exc}")
        click_next_buttons(driver, 3)
        set_visibility(driver, args.visibility)
        click_done(driver)
        wait_after_done(driver)
        if args.visibility == "public":
            verify_not_saved_as_draft(driver)


def resume_failed_uploads(args: argparse.Namespace) -> None:
    video_dir = resolve_base_path(args.video_dir, VIDEOS_DIR)
    lookup = file_lookup_by_title(video_dir)
    if not lookup:
        print(f"[LOI] Thu muc {video_dir} chua co video de upload lai.")
        sys.exit(1)

    args.default_description = read_text_file(args.description_file)
    driver = build_driver(chrome_binary=args.chrome_binary, attach=args.attach)
    successes: list[Path] = []
    failures: list[str] = []
    try:
        open_studio_content_page(driver)
        ensure_logged_in(driver)
        for index in range(1, args.max_failed_uploads + 1):
            print(f"\n[TIEN DO] Tim video loi {index}/{args.max_failed_uploads}")
            open_studio_content_page(driver, timeout=30)
            wait_for_video_rows_text(driver, timeout=60)
            rows = failed_upload_rows(driver)
            if not rows:
                print("[INFO] Khong thay dong video loi can upload lai.")
                break

            row = rows[0]
            row_text = (row.text or row.get_attribute("innerText") or "").strip()
            video = find_video_for_failed_row(row_text, lookup)
            if not video:
                message = "Khong tim thay file trong thu muc upload khop voi dong loi: " + row_text.splitlines()[0][:160]
                failures.append(message)
                print(f"[LOI] {message}")
                break

            try:
                print(f"[INFO] Dang upload lai file loi: {video.name}")
                click_row_continue_upload(driver, row)
                file_input = find_file_input(driver, timeout=30)
                file_input.send_keys(str(video.resolve()))
                finish_resumed_upload_if_needed(driver, video, args)
                successes.append(video)
                print(f"[OK] Da upload lai xong: {video.name}")
                time.sleep(args.delay)
            except Exception as exc:
                message = f"{video.name}: {str(exc) or exc.__class__.__name__}"
                failures.append(message)
                print(f"[LOI] Upload lai that bai: {message}")
                recover_after_upload_error(driver)
                if args.stop_on_error:
                    break

        print("\n=== Tong ket upload lai video loi ===")
        print(f"[OK] Thanh cong: {len(successes)}")
        if failures:
            print(f"[LOI] That bai: {len(failures)}")
            for message in failures:
                print(f"- {message}")
            sys.exit(1)
    finally:
        if args.attach:
            print("[INFO] Dang dung --attach nen tool khong dong Chrome cua ban.")
        else:
            driver.quit()


def click_first_edit_draft(driver: WebDriver, timeout: int = 20) -> bool:
    draft_markers = (
        "ban nhap",
        "draft",
        "chinh sua ban nhap",
        "edit draft",
    )
    end_time = time.time() + timeout
    last_error: Optional[Exception] = None
    while time.time() < end_time:
        try:
            rows = driver.find_elements(By.CSS_SELECTOR, "ytcp-video-row")
            for row in rows:
                try:
                    row_text = (row.text or row.get_attribute("innerText") or "").strip()
                    row_key = text_key(row_text)
                    if not any(marker in row_key for marker in draft_markers):
                        continue
                    targets = row.find_elements(
                        By.CSS_SELECTOR,
                        "#video-title, #video-details, ytcp-icon-button#video-details, a[role='button']",
                    )
                    for target in targets:
                        try:
                            if not target.is_displayed():
                                continue
                            target_id = target.get_attribute("id") or ""
                            label = (target.text or target.get_attribute("aria-label") or "").strip()
                            if label or target_id in {"video-title", "video-details"}:
                                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", target)
                                time.sleep(0.2)
                                driver.execute_script("arguments[0].click();", target)
                                return True
                        except Exception as exc:
                            last_error = exc
                except Exception as exc:
                    last_error = exc
        except Exception as exc:
            last_error = exc
        time.sleep(0.5)
    if last_error:
        print(f"[CANH BAO] Co thay bang video nhung chua click duoc ban nhap: {last_error}")

    locators = [
        (By.XPATH, '//*[self::button or self::ytcp-button][contains(normalize-space(.), "Edit draft")]'),
        (By.XPATH, '//*[self::button or self::ytcp-button][contains(normalize-space(.), "Chỉnh sửa bản nháp")]'),
        (By.XPATH, '//*[self::button or self::ytcp-button][contains(normalize-space(.), "Chinh sua ban nhap")]'),
        (By.XPATH, '//*[contains(normalize-space(.), "Edit draft")]/ancestor::*[@role="button"][1]'),
        (By.XPATH, '//*[contains(normalize-space(.), "Chỉnh sửa bản nháp")]/ancestor::*[@role="button"][1]'),
    ]
    try:
        js_click_first(driver, locators, timeout=timeout, name="nut Edit draft/Chinh sua ban nhap")
        return True
    except TimeoutException:
        return False


def publish_one_open_draft(driver: WebDriver, args: argparse.Namespace) -> None:
    print("[INFO] Dang publish mot ban nhap YouTube...")
    time.sleep(2)
    fill_draft_description(driver, args)
    set_audience(driver, args.made_for_kids)
    click_next_buttons(driver, 3)
    set_visibility(driver, args.visibility)
    if has_upload_error(driver):
        raise RuntimeError("YouTube bao loi upload/processing trong ban nhap, khong publish duoc.")
    click_done(driver)
    wait_after_done(driver)
    if args.visibility == "public":
        verify_not_saved_as_draft(driver)
    print("[OK] Da xu ly xong mot ban nhap.")


def publish_drafts(args: argparse.Namespace) -> None:
    args.default_description = read_text_file(args.description_file)
    driver = build_driver(chrome_binary=args.chrome_binary, attach=args.attach)
    successes = 0
    failures: list[str] = []
    try:
        open_studio_content_page(driver)
        ensure_logged_in(driver)
        for index in range(1, args.max_drafts + 1):
            print(f"\n[TIEN DO] Tim ban nhap {index}/{args.max_drafts}")
            open_studio_content_page(driver, timeout=30)
            if not click_first_edit_draft(driver, timeout=15):
                print("[INFO] Khong thay nut Chinh sua ban nhap/Edit draft nao nua.")
                break
            try:
                publish_one_open_draft(driver, args)
                successes += 1
                time.sleep(args.delay)
                open_studio_content_page(driver, timeout=30)
            except Exception as exc:
                message = str(exc) or exc.__class__.__name__
                failures.append(message)
                print(f"[LOI] Khong publish duoc ban nhap: {message}")
                recover_after_upload_error(driver)
                if args.stop_on_error:
                    break
        print("\n=== Tong ket publish ban nhap ===")
        print(f"[OK] Da publish/xu ly: {successes}")
        if failures:
            print(f"[LOI] That bai: {len(failures)}")
            for message in failures:
                print(f"- {message}")
            sys.exit(1)
    finally:
        if args.attach:
            print("[INFO] Dang dung --attach nen tool khong dong Chrome cua ban.")
        else:
            driver.quit()


def run_login(args: argparse.Namespace) -> None:
    print("\nDang mo Google Chrome that, khong mo bang Selenium...")
    print("Viec nay giup tranh loi Google: Couldn't sign you in / This browser or app may not be secure.")
    open_manual_chrome(chrome_binary=args.chrome_binary, with_debug=True)
    print("\nDa mo YouTube Studio trong Chrome profile rieng.")
    print("1) Dang nhap tai khoan YouTube tren cua so Chrome vua mo.")
    print("2) Khi vao duoc YouTube Studio, GIU NGUYEN cua so Chrome do neu muon upload bang --attach.")
    print("3) Mo CMD moi trong thu muc source va chay:")
    print("   python main.py --attach --all --visibility public --description-file default_description.txt")
    if getattr(args, "no_wait_login", False):
        return
    input("\nBam ENTER de thoat man hinh nay. KHONG can dong Chrome... ")


def run_upload(args: argparse.Namespace) -> None:
    if args.video:
        p = Path(args.video)
        if not p.is_absolute():
            p = BASE_DIR / p
        if not p.exists():
            print(f"[LOI] Khong thay file video: {p}")
            sys.exit(1)
        videos = [p]
    elif args.all:
        video_dir = resolve_base_path(args.video_dir, VIDEOS_DIR)
        videos = get_video_files(video_dir)
    else:
        print("[LOI] Chon --all de upload tat ca video trong thu muc videos hoac --video ten_file.mp4")
        sys.exit(1)

    if not videos:
        video_dir = resolve_base_path(args.video_dir, VIDEOS_DIR)
        video_dir.mkdir(exist_ok=True)
        print(f"[LOI] Thu muc {video_dir} chua co video.")
        sys.exit(1)

    args.default_description = read_text_file(args.description_file)

    print("Danh sach video se upload:")
    for v in videos:
        print(f"- File: {v.name}")
        print(f"  Tieu de YouTube: {build_video_title(v, args)}")
    print("\nMo ta dung chung:")
    print(args.default_description[:500] + ("..." if len(args.default_description) > 500 else ""))
    print(f"\nChe do dang: {args.visibility}")

    if not args.yes:
        confirm = input("Tiep tuc upload? Nhap YES de xac nhan: ").strip()
        if confirm != "YES":
            print("Da huy.")
            return

    driver = build_driver(chrome_binary=args.chrome_binary, attach=args.attach)
    successes: list[Path] = []
    failures: list[tuple[Path, str]] = []
    try:
        total = len(videos)
        for index, video in enumerate(videos, start=1):
            print(f"\n[TIEN DO] Video {index}/{total}")
            try:
                upload_one_video(driver, video, args)
                successes.append(video)
            except KeyboardInterrupt:
                raise
            except Exception as exc:
                message = str(exc) or exc.__class__.__name__
                failures.append((video, message))
                print(f"[LOI] Upload loi, bo qua video nay va tiep tuc: {video.name}")
                print(f"[LOI] Chi tiet: {message}")
                recover_after_upload_error(driver)
                if args.stop_on_error:
                    break
    finally:
        if args.attach:
            print("[INFO] Dang dung --attach nen tool khong dong Chrome cua ban.")
        else:
            driver.quit()

    print("\n=== Tong ket upload ===")
    print(f"[OK] Thanh cong: {len(successes)}/{len(videos)}")
    if failures:
        print(f"[LOI] That bai: {len(failures)}")
        for video, message in failures:
            print(f"- {video.name}: {message}")
        sys.exit(1)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="YouTube Studio auto upload bot - title by filename, same description")
    parser.add_argument("--login", action="store_true", help="Mo Chrome that de dang nhap YouTube Studio")
    parser.add_argument("--no-wait-login", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--attach", action="store_true", help="Ket noi vao cua so Chrome da mo bang --login de upload")
    parser.add_argument("--all", action="store_true", help="Upload tat ca video trong thu muc videos/")
    parser.add_argument("--video", help="Upload 1 file video cu the, vi du: videos/vid1.mp4")
    parser.add_argument("--publish-drafts", action="store_true", help="Mo cac ban nhap dang thay trong YouTube Studio va publish")
    parser.add_argument("--resume-failed-uploads", action="store_true", help="Upload lai cac dong YouTube Studio bi loi Tiep tuc tai len")
    parser.add_argument("--max-drafts", type=int, default=20, help="So ban nhap toi da se thu publish")
    parser.add_argument("--max-failed-uploads", type=int, default=20, help="So video loi toi da se thu upload lai")
    parser.add_argument("--video-dir", default="videos", help="Thu muc lay video khi dung --all")
    parser.add_argument("--visibility", choices=["private", "unlisted", "public", "skip"], default="public", help="Che do hien thi")
    parser.add_argument("--made-for-kids", choices=["yes", "no", "skip"], default="no", help="Video co danh cho tre em khong")
    parser.add_argument("--title", default="", help="Tieu de rieng. Neu bo trong thi tu lay theo ten file video")
    parser.add_argument("--description", default="", help="Mo ta dung chung neu khong dung file .txt")
    parser.add_argument("--description-file", default="default_description.txt", help="File mo ta dung chung")
    parser.add_argument("--title-hashtags", default="", help="Hashtag them vao cuoi tieu de")
    parser.add_argument("--description-hashtags", default="", help="Hashtag them vao cuoi mo ta")
    parser.add_argument("--delay", type=int, default=DEFAULT_UPLOAD_DELAY, help="So giay nghi giua moi video")
    parser.add_argument("--stop-on-error", action="store_true", help="Dung ngay khi mot video upload loi")
    parser.add_argument("--yes", action="store_true", help="Bo qua buoc xac nhan YES")
    parser.add_argument("--chrome-binary", help="Duong dan chrome.exe neu may dung Chrome Beta/Canary")
    parser.add_argument("--profile-dir", help="Thu muc Chrome profile rieng neu can chay song song")
    parser.add_argument("--debug-port", type=int, default=DEBUG_PORT, help="Cong remote debugging Chrome")
    return parser.parse_args()


def main() -> None:
    global PROFILE_DIR, DEBUG_PORT
    args = parse_args()
    PROFILE_DIR = resolve_base_path(args.profile_dir, PROFILE_DIR)
    DEBUG_PORT = args.debug_port
    VIDEOS_DIR.mkdir(exist_ok=True)

    if args.login:
        run_login(args)
    elif args.publish_drafts:
        publish_drafts(args)
    elif args.resume_failed_uploads:
        resume_failed_uploads(args)
    else:
        run_upload(args)


if __name__ == "__main__":
    main()
