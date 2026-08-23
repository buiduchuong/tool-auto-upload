"""
Instagram web auto upload helper.

Chay nhanh:
1) python instagram_upload.py --login
2) Dang nhap Instagram tren Chrome vua mo, GIU NGUYEN cua so Chrome do
3) python instagram_upload.py --attach --all --video-dir videos
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

import pyperclip
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.remote.webdriver import WebDriver

BASE_DIR = Path(__file__).resolve().parent
VIDEOS_DIR = BASE_DIR / "videos"
PROFILE_DIR = BASE_DIR / "chrome-profile-instagram"
LOCAL_CHROMEDRIVER = BASE_DIR / "chromedriver.exe"
DEBUG_DIR = BASE_DIR / "instagram_debug"
DEFAULT_DESCRIPTION_FILE = BASE_DIR / "instagram_description.txt"
VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}
DEBUG_PORT = 9225
DEFAULT_TIMEOUT = 30
INSTAGRAM_URL = "https://www.instagram.com/"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def resolve_base_path(path_value: str | None, default_path: Path) -> Path:
    if not path_value:
        return default_path
    path = Path(path_value)
    if not path.is_absolute():
        path = BASE_DIR / path
    return path


def read_text_file(path_value: str | None) -> str:
    if not path_value:
        return ""
    path = resolve_base_path(path_value, DEFAULT_DESCRIPTION_FILE)
    if not path.exists():
        print(f"[CANH BAO] Khong thay file mo ta Instagram: {path}")
        return ""
    try:
        return path.read_text(encoding="utf-8").strip()
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8-sig").strip()
    except Exception as exc:
        print(f"[CANH BAO] Khong doc duoc file mo ta Instagram {path}: {exc}")
        return ""


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


def open_manual_chrome(chrome_binary: Optional[str] = None) -> None:
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    chrome = find_chrome_executable(chrome_binary)
    cmd = [
        chrome,
        f"--remote-debugging-port={DEBUG_PORT}",
        f"--user-data-dir={PROFILE_DIR}",
        "--profile-directory=Default",
        "--start-maximized",
        INSTAGRAM_URL,
    ]
    subprocess.Popen(cmd)


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
            print("[CANH BAO] Dang thu chromedriver.exe trong thu muc tool.")
            detail = str(automatic_driver_error).splitlines()[0]
            print(f"Chi tiet tu dong: {detail}")
            return webdriver.Chrome(
                service=Service(executable_path=str(LOCAL_CHROMEDRIVER)),
                options=options,
            )
    except WebDriverException as exc:
        print("\n[LOI] Khong mo/ket noi duoc Chrome.")
        print("- Hay chay: python instagram_upload.py --login")
        print("- Dang nhap Instagram xong phai GIU NGUYEN cua so Chrome do.")
        print(f"- Cong ket noi mac dinh: {DEBUG_PORT}")
        print(f"Chi tiet loi: {exc}")
        raise


def build_title(video_path: Path, title: str) -> str:
    custom_title = (title or "").strip()
    return (custom_title or video_path.stem)[:2200]


def build_caption(video_path: Path, args: argparse.Namespace) -> str:
    title = build_title(video_path, args.title)
    description = (args.description or getattr(args, "default_description", "") or "").strip()
    if description:
        return f"{title}\n\n{description}"[:2200]
    return title


def paste_text(element, text: str) -> None:
    element.click()
    element.send_keys(Keys.CONTROL, "a")
    pyperclip.copy(text)
    element.send_keys(Keys.CONTROL, "v")
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


def current_page_summary(driver: WebDriver) -> str:
    try:
        body = driver.find_element(By.TAG_NAME, "body").text
    except Exception:
        body = ""
    snippet = " ".join(body.split())[:900]
    return f"url={driver.current_url} title={driver.title!r} text={snippet!r}"


def full_body_text(driver: WebDriver) -> str:
    try:
        return driver.find_element(By.TAG_NAME, "body").text
    except Exception:
        return ""


def instagram_upload_error_message(driver: WebDriver) -> str | None:
    text = full_body_text(driver).lower()
    checks = [
        ("không thể tải video lên", "Instagram bao: Khong the tai video len."),
        ("không tải lên được một hoặc nhiều video vì quá dài", "Instagram bao video qua dai/khong hop le."),
        ("nếu video dài hơn 1 phút", "Instagram bao video dai hon 1 phut thi moi lan chi duoc dang 1 video."),
        ("couldn't upload video", "Instagram bao couldn't upload video."),
        ("video is too long", "Instagram bao video is too long."),
        ("too long", "Instagram bao video qua dai."),
    ]
    for needle, message in checks:
        if needle in text:
            return message
    return None


def close_instagram_modal(driver: WebDriver) -> bool:
    try:
        candidates = driver.find_elements(By.CSS_SELECTOR, '[aria-label="Đóng"], [aria-label="Close"], svg[aria-label="Đóng"], svg[aria-label="Close"]')
        for element in candidates:
            if not element.is_displayed():
                continue
            target = driver.execute_script("return arguments[0].closest('button,[role=\"button\"],div[tabindex],a') || arguments[0];", element)
            try:
                target.click()
            except Exception:
                driver.execute_script("arguments[0].click();", target)
            time.sleep(1)
            # Some Instagram flows ask for discard confirmation.
            click_by_text(driver, ["discard", "bỏ", "bo", "hủy", "huy"], name="Discard/Close Instagram modal", timeout=2)
            print("[INFO] Da dong modal Instagram hien tai.")
            return True
    except Exception:
        pass
    return False


def find_first(driver: WebDriver, locators: list[tuple[str, str]], *, displayed: bool = True, timeout: int = DEFAULT_TIMEOUT):
    last_error: Exception | None = None
    end_time = time.time() + timeout
    while time.time() < end_time:
        for by, value in locators:
            try:
                elements = driver.find_elements(by, value)
                for element in elements:
                    if not displayed or element.is_displayed():
                        return element
            except Exception as exc:
                last_error = exc
        time.sleep(0.5)
    raise TimeoutException(f"Khong tim thay element phu hop. Loi cuoi: {last_error}. {current_page_summary(driver)}")


def click_first(driver: WebDriver, locators: list[tuple[str, str]], *, name: str, timeout: int = DEFAULT_TIMEOUT) -> None:
    element = find_first(driver, locators, displayed=True, timeout=timeout)
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
    time.sleep(0.2)
    try:
        element.click()
    except Exception:
        driver.execute_script("arguments[0].click();", element)
    print(f"[INFO] Da bam {name}.")


def visible_clickable_elements(driver: WebDriver):
    return driver.execute_script(
        """
        const selectors = 'button,a,[role="button"],div[tabindex],span[role="button"]';
        return Array.from(document.querySelectorAll(selectors)).filter((el) => {
          const rect = el.getBoundingClientRect();
          const style = window.getComputedStyle(el);
          return rect.width > 0 && rect.height > 0 && style.visibility !== 'hidden' && style.display !== 'none';
        });
        """
    )


def element_text_value(driver: WebDriver, element) -> str:
    try:
        return driver.execute_script(
            """
            const el = arguments[0];
            return [el.innerText, el.textContent, el.getAttribute('aria-label'), el.getAttribute('title')]
              .filter(Boolean).join(' ');
            """,
            element,
        ) or ""
    except Exception:
        return ""


def click_by_text(driver: WebDriver, terms: list[str], *, name: str, timeout: int = DEFAULT_TIMEOUT) -> bool:
    normalized_terms = [term.lower() for term in terms if term]
    end_time = time.time() + timeout
    last_seen = ""
    while time.time() < end_time:
        try:
            for element in visible_clickable_elements(driver):
                text = element_text_value(driver, element)
                lowered = text.lower()
                if text:
                    last_seen = text[:180]
                if any(term in lowered for term in normalized_terms):
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
                    time.sleep(0.2)
                    try:
                        element.click()
                    except Exception:
                        driver.execute_script("arguments[0].click();", element)
                    print(f"[INFO] Da bam {name}: {text[:80]!r}")
                    return True
        except Exception:
            pass
        time.sleep(0.5)
    print(f"[INFO] Khong thay nut {name}. Text gan nhat: {last_seen!r}")
    return False


def click_parent_of_labeled_icon(driver: WebDriver, labels: list[str], *, name: str, timeout: int = DEFAULT_TIMEOUT) -> bool:
    lowered_labels = [label.lower() for label in labels if label]
    end_time = time.time() + timeout
    while time.time() < end_time:
        try:
            elements = driver.find_elements(By.CSS_SELECTOR, "[aria-label]")
            for element in elements:
                label = (element.get_attribute("aria-label") or "").strip()
                if not label:
                    continue
                if not any(item in label.lower() for item in lowered_labels):
                    continue
                clicked = driver.execute_script(
                    """
                    const el = arguments[0];
                    const target = el.closest('a,button,[role="button"],div[tabindex]') || el;
                    target.scrollIntoView({block: 'center'});
                    target.click();
                    return [
                      target.tagName,
                      target.getAttribute('role'),
                      target.getAttribute('aria-label'),
                      target.innerText || target.textContent || ''
                    ].filter(Boolean).join(' ');
                    """,
                    element,
                )
                print(f"[INFO] Da bam {name}: {label!r} -> {str(clicked)[:100]!r}")
                return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


def click_instagram_create_button(driver: WebDriver, timeout: int = 30) -> bool:
    end_time = time.time() + timeout
    while time.time() < end_time:
        try:
            for link in driver.find_elements(By.CSS_SELECTOR, "a,button,[role='button']"):
                if not link.is_displayed():
                    continue
                text = (link.text or element_text_value(driver, link) or "").strip().lower()
                href = (link.get_attribute("href") or "").strip()
                if text in {"tạo", "create"} or (href.endswith("#") and text.startswith("tạo")):
                    driver.execute_script("arguments[0].scrollIntoView({block:'center', inline:'center'});", link)
                    time.sleep(0.2)
                    ActionChains(driver).move_to_element(link).pause(0.1).click().perform()
                    print(f"[INFO] Da bam nut Tao/Create tren sidebar: {text!r}")
                    return True
        except Exception:
            pass

        try:
            clicked = driver.execute_script(
                """
                const labels = ['Bài viết mới', 'New post', 'Create'];
                const icon = Array.from(document.querySelectorAll('[aria-label]')).find(el => {
                  const label = el.getAttribute('aria-label') || '';
                  return labels.some(item => label.toLowerCase().includes(item.toLowerCase()));
                });
                if (!icon) return '';
                const target = icon.closest('a,button,[role="button"]') || icon.parentElement || icon;
                const rect = target.getBoundingClientRect();
                target.dispatchEvent(new MouseEvent('mouseover', {bubbles:true, clientX:rect.left+rect.width/2, clientY:rect.top+rect.height/2}));
                target.dispatchEvent(new MouseEvent('mousedown', {bubbles:true, clientX:rect.left+rect.width/2, clientY:rect.top+rect.height/2}));
                target.dispatchEvent(new MouseEvent('mouseup', {bubbles:true, clientX:rect.left+rect.width/2, clientY:rect.top+rect.height/2}));
                target.dispatchEvent(new MouseEvent('click', {bubbles:true, clientX:rect.left+rect.width/2, clientY:rect.top+rect.height/2}));
                return icon.getAttribute('aria-label') || target.innerText || target.textContent || target.tagName;
                """
            )
            if clicked:
                print(f"[INFO] Da bam icon Tao/Create tren sidebar: {str(clicked)[:80]!r}")
                return True
        except Exception:
            pass
        time.sleep(0.75)
    return False


def has_instagram_file_picker(driver: WebDriver, timeout: int = 3) -> bool:
    try:
        find_first(driver, [(By.CSS_SELECTOR, 'input[type="file"]')], displayed=False, timeout=timeout)
        body = ""
        try:
            body = driver.find_element(By.TAG_NAME, "body").text.lower()
        except Exception:
            pass
        if any(term in body for term in ["select from computer", "chọn từ máy tính", "chon tu may tinh", "kéo ảnh", "keo anh"]):
            return True
        # Instagram sometimes keeps the file input hidden but ready inside the create dialog.
        dialog_like = driver.find_elements(By.CSS_SELECTOR, '[role="dialog"], [aria-modal="true"]')
        return any(item.is_displayed() for item in dialog_like)
    except Exception:
        return False


def dismiss_instagram_popups(driver: WebDriver) -> None:
    popup_terms = [
        "not now",
        "lúc khác",
        "luc khac",
        "bỏ qua",
        "bo qua",
        "ok",
        "got it",
        "đã hiểu",
        "da hieu",
        "continue",
        "tiếp tục",
        "tiep tuc",
    ]
    end_time = time.time() + 2
    while time.time() < end_time:
        clicked = False
        try:
            elements = driver.find_elements(By.CSS_SELECTOR, 'button,a,[role="button"]')
            for element in elements:
                if not element.is_displayed():
                    continue
                text = element_text_value(driver, element).strip()
                lowered = text.lower()
                if not text or len(text) > 60:
                    continue
                if any(term in lowered for term in popup_terms):
                    try:
                        element.click()
                    except Exception:
                        driver.execute_script("arguments[0].click();", element)
                    print(f"[INFO] Da dong popup Instagram: {text[:60]!r}")
                    clicked = True
                    time.sleep(0.5)
                    break
        except Exception:
            pass
        if not clicked:
            return


def ensure_logged_in_or_raise(driver: WebDriver) -> None:
    summary = current_page_summary(driver).lower()
    url = driver.current_url.lower()
    if "login" in url or "log in" in summary or "đăng nhập" in summary or "dang nhap" in summary:
        raise RuntimeError("Instagram chua dang nhap. Hay bam 'Mo Instagram dang nhap', dang nhap xong giu nguyen Chrome.")


def open_create_dialog(driver: WebDriver) -> None:
    existing_error = instagram_upload_error_message(driver)
    if existing_error:
        print(f"[CANH BAO] {existing_error} Dang dong modal loi de chon lai file.")
        close_instagram_modal(driver)

    if has_instagram_file_picker(driver, timeout=1):
        print("[INFO] Man hinh tao bai Instagram dang mo san.")
        return

    driver.get(INSTAGRAM_URL)
    time.sleep(3)
    ensure_logged_in_or_raise(driver)
    dismiss_instagram_popups(driver)

    if has_instagram_file_picker(driver, timeout=2):
        print("[INFO] Man hinh tao bai Instagram dang mo san.")
        return

    if not click_instagram_create_button(driver, timeout=30):
        if not click_parent_of_labeled_icon(
            driver,
            ["bài viết mới", "new post", "create", "tạo"],
            name="Create/New post Instagram",
            timeout=8,
        ) and not click_by_text(driver, ["create", "new post", "tạo"], name="Create/New post Instagram", timeout=8):
            raise TimeoutException(f"Khong bam duoc nut Tao/Create Instagram. {current_page_summary(driver)}")
    end_time = time.time() + 30
    while time.time() < end_time:
        dismiss_instagram_popups(driver)
        if has_instagram_file_picker(driver, timeout=1):
            print("[INFO] Da mo hop tao bai Instagram.")
            return
        time.sleep(1)
    raise TimeoutException(f"Da bam Create nhung chua thay hop chon file Instagram. {current_page_summary(driver)}")


def attach_video_file(driver: WebDriver, video_path: Path) -> None:
    existing_error = instagram_upload_error_message(driver)
    if existing_error:
        raise RuntimeError(existing_error)
    try:
        file_input = find_first(driver, [(By.CSS_SELECTOR, 'input[type="file"]')], displayed=False, timeout=8)
    except Exception:
        try:
            click_first(
                driver,
                [
                    (By.XPATH, '//button[contains(normalize-space(.), "Select from computer")]'),
                    (By.XPATH, '//button[contains(normalize-space(.), "Chọn từ máy tính")]'),
                    (By.XPATH, '//*[self::button or @role="button"][contains(normalize-space(.), "Select")]'),
                    (By.XPATH, '//*[self::button or @role="button"][contains(normalize-space(.), "Chọn")]'),
                ],
                name="Select from computer",
                timeout=15,
            )
        except Exception:
            click_by_text(driver, ["select from computer", "chọn từ máy tính", "chon tu may tinh", "select", "chọn"], name="Select from computer", timeout=15)
        file_input = find_first(driver, [(By.CSS_SELECTOR, 'input[type="file"]')], displayed=False, timeout=15)
    file_input.send_keys(str(video_path))
    print("[INFO] Da gui file video cho Instagram.")
    wait_after_file_selected(driver, timeout=90)
    dismiss_instagram_popups(driver)


def has_button_text(driver: WebDriver, terms: list[str]) -> bool:
    lowered_terms = [term.lower() for term in terms]
    try:
        for element in driver.find_elements(By.CSS_SELECTOR, 'button,a,[role="button"]'):
            if not element.is_displayed():
                continue
            text = element_text_value(driver, element).lower()
            if any(term in text for term in lowered_terms):
                return True
    except Exception:
        pass
    return False


def wait_after_file_selected(driver: WebDriver, timeout: int = 90) -> None:
    end_time = time.time() + timeout
    last_summary = ""
    while time.time() < end_time:
        try:
            summary = current_page_summary(driver)
            last_summary = summary
            lowered = summary.lower()
            upload_error = instagram_upload_error_message(driver)
            if upload_error:
                raise RuntimeError(upload_error)
            if any(word in lowered for word in ["couldn't", "failed", "không thể", "khong the", "lỗi", "loi"]):
                raise RuntimeError(f"Instagram bao loi sau khi chon file: {summary}")
            if caption_box_exists(driver, timeout=1) or has_button_text(driver, ["Next", "Tiếp", "Tiep", "OK"]):
                print("[INFO] Instagram da nhan file, san sang sang buoc tiep theo.")
                return
            if any(word in lowered for word in ["crop", "cắt", "cat", "edit", "chỉnh sửa", "chinh sua"]):
                print("[INFO] Instagram da hien man crop/edit.")
                return
        except RuntimeError:
            raise
        except Exception:
            pass
        time.sleep(1)
    raise TimeoutException(f"Instagram chua nhan file/chua hien nut Tiep sau khi gui file. {last_summary}")


def caption_box_exists(driver: WebDriver, timeout: int = 3) -> bool:
    try:
        find_first(
            driver,
            [
                (By.CSS_SELECTOR, '[aria-label*="caption" i]'),
                (By.CSS_SELECTOR, 'textarea[aria-label*="caption" i]'),
                (By.CSS_SELECTOR, 'textarea[placeholder*="caption" i]'),
                (By.CSS_SELECTOR, 'div[contenteditable="true"][role="textbox"]'),
                (By.CSS_SELECTOR, 'textarea'),
            ],
            displayed=True,
            timeout=timeout,
        )
        return True
    except Exception:
        return False


def click_next_until_caption(driver: WebDriver) -> None:
    for step in range(1, 5):
        time.sleep(2)
        dismiss_instagram_popups(driver)
        if caption_box_exists(driver, timeout=2):
            return
        try:
            click_first(
                driver,
                [
                    (By.XPATH, '//*[self::button or @role="button"][contains(normalize-space(.), "Next")]'),
                    (By.XPATH, '//*[self::button or @role="button"][contains(normalize-space(.), "Tiếp")]'),
                    (By.XPATH, '//*[self::button or @role="button"][contains(normalize-space(.), "Tiếp theo")]'),
                ],
                name=f"Next Instagram buoc {step}",
                timeout=8,
            )
            continue
        except Exception:
            pass
        if click_by_text(driver, ["next", "tiếp", "tiep"], name=f"Next Instagram buoc {step}", timeout=8):
            continue
        if step >= 2:
            raise TimeoutException(f"Khong toi duoc man hinh caption Instagram. {current_page_summary(driver)}")


def set_caption(driver: WebDriver, caption: str) -> None:
    locators = [
        (By.CSS_SELECTOR, '[aria-label*="caption" i]'),
        (By.CSS_SELECTOR, 'textarea[aria-label*="caption" i]'),
        (By.CSS_SELECTOR, 'textarea[placeholder*="caption" i]'),
        (By.CSS_SELECTOR, 'div[contenteditable="true"][role="textbox"]'),
        (By.CSS_SELECTOR, 'textarea'),
        (By.CSS_SELECTOR, 'div[contenteditable="true"]'),
    ]
    element = find_first(driver, locators, displayed=True, timeout=60)
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
    time.sleep(0.2)
    paste_text(element, caption)


def click_share(driver: WebDriver) -> None:
    dismiss_instagram_popups(driver)
    if click_exact_text_element(driver, ["Chia sẻ", "Share", "Đăng", "Post"], name="Share/Dang Instagram", timeout=60):
        return
    try:
        click_first(
            driver,
            [
                (By.XPATH, '//*[self::button or @role="button"][contains(normalize-space(.), "Share")]'),
                (By.XPATH, '//*[self::button or @role="button"][contains(normalize-space(.), "Chia sẻ")]'),
                (By.XPATH, '//*[self::button or @role="button"][contains(normalize-space(.), "Đăng")]'),
            ],
            name="Share/Dang Instagram",
            timeout=60,
        )
    except Exception:
        if click_modal_top_right(driver, name="Share/Dang Instagram"):
            return
        if not click_by_text(driver, ["share", "chia sẻ", "chia se", "đăng", "dang"], name="Share/Dang Instagram", timeout=60):
            raise


def click_modal_top_right(driver: WebDriver, *, name: str) -> bool:
    try:
        target = driver.execute_script(
            """
            const dialogs = Array.from(document.querySelectorAll('[role="dialog"], [aria-modal="true"]'))
              .filter(el => {
                const r = el.getBoundingClientRect();
                const s = getComputedStyle(el);
                return r.width > 300 && r.height > 200 && s.display !== 'none' && s.visibility !== 'hidden';
              })
              .sort((a, b) => (b.getBoundingClientRect().width * b.getBoundingClientRect().height) - (a.getBoundingClientRect().width * a.getBoundingClientRect().height));
            const dialog = dialogs[0];
            if (!dialog) return null;
            const dr = dialog.getBoundingClientRect();
            const candidates = Array.from(dialog.querySelectorAll('div,span,a,button,[role="button"]'))
              .map(el => {
                const r = el.getBoundingClientRect();
                const s = getComputedStyle(el);
                const text = (el.innerText || el.textContent || '').trim();
                return {el, text, x:r.left, y:r.top, w:r.width, h:r.height, visible:r.width>0 && r.height>0 && s.display !== 'none' && s.visibility !== 'hidden'};
              })
              .filter(item => item.visible && item.y <= dr.top + 70 && item.x >= dr.right - 180 && item.w <= 180 && item.h <= 80)
              .sort((a, b) => (b.x - a.x) || (a.y - b.y));
            if (candidates.length) return candidates[0].el;
            return dialog;
            """
        )
        if target is None:
            return False
        try:
            ActionChains(driver).move_to_element(target).pause(0.1).click().perform()
        except Exception:
            driver.execute_script(
                """
                const el = arguments[0];
                const r = el.getBoundingClientRect();
                const x = r.right - 45;
                const y = r.top + 22;
                const hit = document.elementFromPoint(x, y) || el;
                for (const type of ['mouseover','mousedown','mouseup','click']) {
                  hit.dispatchEvent(new MouseEvent(type, {bubbles:true, cancelable:true, clientX:x, clientY:y}));
                }
                """,
                target,
            )
        print(f"[INFO] Da bam {name} bang vi tri goc phai modal.")
        return True
    except Exception as exc:
        print(f"[INFO] Khong bam duoc {name} bang vi tri goc phai modal: {exc}")
        return False


def click_exact_text_element(driver: WebDriver, texts: list[str], *, name: str, timeout: int = DEFAULT_TIMEOUT) -> bool:
    wanted = {text.lower() for text in texts}
    end_time = time.time() + timeout
    last_seen = ""
    while time.time() < end_time:
        try:
            candidates = driver.execute_script(
                """
                const wanted = new Set(arguments[0].map(x => x.toLowerCase()));
                return Array.from(document.querySelectorAll('div,span,a,button,[role="button"]')).map((el) => {
                  const rect = el.getBoundingClientRect();
                  const style = window.getComputedStyle(el);
                  const text = (el.innerText || el.textContent || '').trim();
                  return {
                    el,
                    text,
                    visible: rect.width > 0 && rect.height > 0 && style.display !== 'none' && style.visibility !== 'hidden',
                    x: rect.left,
                    y: rect.top,
                    w: rect.width,
                    h: rect.height
                  };
                }).filter(item => item.visible && wanted.has(item.text.toLowerCase()) && item.w <= 160 && item.h <= 80)
                  .sort((a, b) => (b.x - a.x) || (a.y - b.y));
                """,
                list(wanted),
            )
            for item in candidates:
                element = item.get("el")
                text = item.get("text") or ""
                last_seen = text
                if element is None:
                    continue
                driver.execute_script("arguments[0].scrollIntoView({block:'center', inline:'center'});", element)
                time.sleep(0.2)
                try:
                    ActionChains(driver).move_to_element(element).pause(0.1).click().perform()
                except Exception:
                    driver.execute_script(
                        """
                        const el = arguments[0];
                        const rect = el.getBoundingClientRect();
                        const x = rect.left + rect.width / 2;
                        const y = rect.top + rect.height / 2;
                        for (const type of ['mouseover','mousedown','mouseup','click']) {
                          el.dispatchEvent(new MouseEvent(type, {bubbles:true, cancelable:true, clientX:x, clientY:y}));
                        }
                        """,
                        element,
                    )
                print(f"[INFO] Da bam {name} dung text: {text!r}")
                return True
        except Exception:
            pass
        time.sleep(0.5)
    print(f"[INFO] Khong thay nut {name} dung text. Gan nhat: {last_seen!r}")
    return False


def wait_after_share(driver: WebDriver, timeout: int = 900) -> None:
    end_time = time.time() + timeout
    last_progress_log = 0.0
    success_words = [
        "your reel has been shared",
        "your post has been shared",
        "your reel was shared",
        "your post was shared",
        "post shared",
        "reel shared",
        "shared",
        "đã chia sẻ",
        "bài viết của bạn đã được chia sẻ",
        "bai viet cua ban da duoc chia se",
        "da chia se",
        "đã đăng",
        "dang thanh cong",
    ]
    sharing_words = ["đang chia sẻ", "dang chia se", "sharing"]
    while time.time() < end_time:
        try:
            body_text = driver.find_element(By.TAG_NAME, "body").text.lower()
        except Exception:
            body_text = ""
        summary = current_page_summary(driver).lower()
        combined = f"{body_text}\n{summary}"
        if any(word in combined for word in success_words):
            print("[INFO] Instagram bao da chia se/dang thanh cong.")
            return
        if "/p/" in driver.current_url.lower() or "/reel/" in driver.current_url.lower():
            return
        visible_dialogs = []
        try:
            visible_dialogs = [
                item
                for item in driver.find_elements(By.CSS_SELECTOR, '[role="dialog"], [aria-modal="true"]')
                if item.is_displayed()
            ]
        except Exception:
            pass
        if not visible_dialogs and "instagram.com" in driver.current_url.lower():
            print("[INFO] Hop tao bai Instagram da dong, xem nhu da dang xong.")
            return
        if any(word in combined for word in sharing_words) and time.time() - last_progress_log >= 15:
            print("[INFO] Instagram dang chia se, tiep tuc doi...")
            last_progress_log = time.time()
        time.sleep(2)
    raise TimeoutException("Het thoi gian doi Instagram dang bai; modal van chua dong. Co the video qua lon/cham xu ly hoac Instagram bi ket.")


def upload_one_video(driver: WebDriver, video_path: Path, args: argparse.Namespace) -> None:
    print(f"\n[INFO] Dang upload Instagram: {video_path}")
    try:
        open_create_dialog(driver)
        attach_video_file(driver, video_path)
        click_next_until_caption(driver)
        caption = build_caption(video_path, args)
        print(f"[INFO] Caption Instagram: {caption}")
        set_caption(driver, caption)
        dismiss_instagram_popups(driver)
        click_share(driver)
        wait_after_share(driver)
        time.sleep(args.after_post_wait)
        print(f"[OK] Da bam Share/Dang Instagram: {video_path.name}")
    except Exception:
        save_debug_artifacts(driver, f"upload_failed_{video_path.stem}")
        raise


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
        print("[LOI] Khong co video de upload Instagram.")
        sys.exit(1)

    args.default_description = read_text_file(args.description_file)
    print("Danh sach video se upload Instagram:")
    for video in videos:
        caption = build_caption(video, args)
        print(f"- {video.name} -> {caption[:160]}{'...' if len(caption) > 160 else ''}")
    print("\nMo ta Instagram:")
    print(args.default_description[:500] + ("..." if len(args.default_description) > 500 else ""))

    if not args.yes:
        confirm = input("Tiep tuc upload Instagram? Nhap YES de xac nhan: ").strip()
        if confirm != "YES":
            print("Da huy.")
            return

    driver = build_driver(chrome_binary=args.chrome_binary, attach=args.attach)
    successes: list[Path] = []
    failures: list[tuple[Path, str]] = []
    try:
        for index, video in enumerate(videos, start=1):
            print(f"\n[TIEN DO] Instagram video {index}/{len(videos)}")
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
                print(f"[LOI] Upload Instagram loi, bo qua video nay: {video.name}")
                print(f"[LOI] Chi tiet: {message}")
                if args.stop_on_error:
                    break
    finally:
        if args.attach:
            print("[INFO] Dang dung --attach nen tool khong dong Chrome cua ban.")
        else:
            driver.quit()

    print("\n=== Tong ket upload Instagram ===")
    print(f"[OK] Thanh cong: {len(successes)}/{len(videos)}")
    if failures:
        print(f"[LOI] That bai: {len(failures)}")
        for video, message in failures:
            print(f"- {video.name}: {message}")
        sys.exit(1)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Instagram web auto upload")
    parser.add_argument("--login", action="store_true", help="Mo Chrome de dang nhap Instagram")
    parser.add_argument("--attach", action="store_true", help="Ket noi Chrome da mo bang --login")
    parser.add_argument("--all", action="store_true", help="Upload tat ca video trong thu muc")
    parser.add_argument("--video", help="Upload 1 file video cu the")
    parser.add_argument("--video-dir", default="videos", help="Thu muc lay video khi dung --all")
    parser.add_argument("--title", default="", help="Tieu de/caption rieng. Neu bo trong thi tu lay ten file")
    parser.add_argument("--description", default="", help="Mo ta Instagram neu khong dung file .txt")
    parser.add_argument("--description-file", default="instagram_description.txt", help="File mo ta Instagram")
    parser.add_argument("--delay", type=int, default=5, help="So giay nghi giua moi video")
    parser.add_argument("--after-post-wait", type=int, default=15, help="So giay doi sau khi bam Share")
    parser.add_argument("--stop-on-error", action="store_true", help="Dung ngay khi mot video loi")
    parser.add_argument("--yes", action="store_true", help="Bo qua xac nhan YES")
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
        open_manual_chrome(args.chrome_binary)
        print("[OK] Da mo Instagram. Hay dang nhap Instagram, sau do giu nguyen Chrome.")
    else:
        run_upload(args)


if __name__ == "__main__":
    main()
