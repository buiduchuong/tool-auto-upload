"""
TikTok web auto upload helper.

Chay nhanh:
1) python tiktok_upload.py --login
2) Dang nhap TikTok tren Chrome vua mo, GIU NGUYEN cua so Chrome do
3) python tiktok_upload.py --attach --all --video-dir TikTok_Channel
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
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

BASE_DIR = Path(__file__).resolve().parent
VIDEOS_DIR = BASE_DIR / "videos"
PROFILE_DIR = BASE_DIR / "chrome-profile"
LOCAL_CHROMEDRIVER = BASE_DIR / "chromedriver.exe"
UPLOADED_DIR = BASE_DIR / "uploaded_tiktok_success"
DEBUG_DIR = BASE_DIR / "tiktok_debug"
DEFAULT_DESCRIPTION_FILE = BASE_DIR / "tiktok_description.txt"
VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}
DEBUG_PORT = 9222
DEFAULT_TIMEOUT = 30

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
    path = Path(path_value)
    if not path.is_absolute():
        path = BASE_DIR / path
    if not path.exists():
        print(f"[CANH BAO] Khong thay file mo ta TikTok: {path}")
        return ""
    try:
        return path.read_text(encoding="utf-8").strip()
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8-sig").strip()
    except Exception as exc:
        print(f"[CANH BAO] Khong doc duoc file mo ta TikTok {path}: {exc}")
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
    PROFILE_DIR.mkdir(exist_ok=True)
    chrome = find_chrome_executable(chrome_binary)
    cmd = [
        chrome,
        f"--remote-debugging-port={DEBUG_PORT}",
        f"--user-data-dir={PROFILE_DIR}",
        "--profile-directory=Default",
        "--start-maximized",
        "https://www.tiktok.com/upload",
    ]
    subprocess.Popen(cmd)


def build_driver(chrome_binary: Optional[str] = None, attach: bool = False) -> WebDriver:
    PROFILE_DIR.mkdir(exist_ok=True)
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
            return webdriver.Chrome(
                service=Service(executable_path=str(LOCAL_CHROMEDRIVER)),
                options=options,
            )
    except WebDriverException as exc:
        print("\n[LOI] Khong mo/ket noi duoc Chrome.")
        print("- Hay chay: python tiktok_upload.py --login")
        print("- Dang nhap TikTok xong phai GIU NGUYEN cua so Chrome do.")
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
    element.send_keys("\ue009" + "a")
    pyperclip.copy(text)
    element.send_keys("\ue009" + "v")
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
        driver.switch_to.default_content()
    except Exception:
        pass
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
        driver.switch_to.default_content()
    except Exception:
        pass
    try:
        body = driver.find_element(By.TAG_NAME, "body").text
    except Exception:
        body = ""
    snippet = " ".join(body.split())[:700]
    return f"url={driver.current_url} title={driver.title!r} text={snippet!r}"


def find_element_across_frames(
    driver: WebDriver,
    by: str,
    value: str,
    *,
    displayed: bool = False,
    timeout: int = DEFAULT_TIMEOUT,
):
    last_error: Exception | None = None
    end_time = time.time() + timeout

    def search_current_context(depth: int = 0):
        nonlocal last_error
        try:
            elements = driver.find_elements(by, value)
            for element in elements:
                if not displayed or element.is_displayed():
                    return element
        except Exception as exc:
            last_error = exc

        if depth >= 4:
            return None

        try:
            frames = driver.find_elements(By.CSS_SELECTOR, "iframe,frame")
        except Exception as exc:
            last_error = exc
            return None

        for index in range(len(frames)):
            try:
                frames = driver.find_elements(By.CSS_SELECTOR, "iframe,frame")
                driver.switch_to.frame(frames[index])
                found = search_current_context(depth + 1)
                if found is not None:
                    return found
                driver.switch_to.parent_frame()
            except Exception as exc:
                last_error = exc
                try:
                    driver.switch_to.parent_frame()
                except Exception:
                    try:
                        driver.switch_to.default_content()
                    except Exception:
                        pass
        return None

    while time.time() < end_time:
        try:
            driver.switch_to.default_content()
        except Exception:
            pass
        found = search_current_context()
        if found is not None:
            return found
        time.sleep(0.5)

    raise TimeoutException(f"Khong tim thay element {by}={value}. Loi cuoi: {last_error}. {current_page_summary(driver)}")


def find_first_across_frames(driver: WebDriver, locators: list[tuple[str, str]], *, displayed: bool, timeout: int):
    last_error: Exception | None = None
    end_time = time.time() + timeout
    while time.time() < end_time:
        for by, value in locators:
            try:
                return find_element_across_frames(driver, by, value, displayed=displayed, timeout=2)
            except Exception as exc:
                last_error = exc
        time.sleep(0.5)
    raise TimeoutException(f"Khong tim thay element phu hop. Loi cuoi: {last_error}. {current_page_summary(driver)}")


def dismiss_tiktok_popups(driver: WebDriver) -> None:
    locators = [
        (By.XPATH, '//button[contains(normalize-space(.), "Đã hiểu")]'),
        (By.XPATH, '//button[contains(normalize-space(.), "Got it")]'),
        (By.XPATH, '//button[contains(normalize-space(.), "OK")]'),
        (By.XPATH, '//button[contains(normalize-space(.), "Ok")]'),
        (By.XPATH, '//button[contains(normalize-space(.), "Skip")]'),
        (By.XPATH, '//button[contains(normalize-space(.), "Bỏ qua")]'),
        (By.CSS_SELECTOR, '[aria-label="Close"]'),
        (By.CSS_SELECTOR, '[aria-label="Đóng"]'),
    ]
    clicked = 0
    for _ in range(4):
        did_click = False
        for by, value in locators:
            try:
                element = find_element_across_frames(driver, by, value, displayed=True, timeout=1)
                if not element.is_enabled():
                    continue
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
                time.sleep(0.1)
                try:
                    element.click()
                except Exception:
                    driver.execute_script("arguments[0].click();", element)
                clicked += 1
                did_click = True
                time.sleep(0.8)
                break
            except Exception:
                pass
        if not did_click:
            break
    if clicked:
        print(f"[INFO] Da dong {clicked} popup/huong dan TikTok.")


def set_caption(driver: WebDriver, caption: str) -> None:
    locators = [
        (By.CSS_SELECTOR, '[data-e2e*="caption"] div[contenteditable="true"]'),
        (By.CSS_SELECTOR, '[data-e2e*="caption"] textarea'),
        (By.CSS_SELECTOR, '[data-e2e*="caption"] [role="textbox"]'),
        (By.CSS_SELECTOR, '[contenteditable="true"][role="textbox"]'),
        (By.CSS_SELECTOR, ".public-DraftEditor-content"),
        (By.CSS_SELECTOR, ".DraftEditor-editorContainer [contenteditable='true']"),
        (By.CSS_SELECTOR, "textarea"),
        (By.CSS_SELECTOR, 'div[contenteditable="true"]'),
    ]
    element = find_first_across_frames(driver, locators, displayed=True, timeout=60)
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
    time.sleep(0.2)
    paste_text(element, caption)


def click_post(driver: WebDriver) -> None:
    locators = [
        (By.CSS_SELECTOR, '[data-e2e="post_video_button"]'),
        (By.CSS_SELECTOR, 'button[type="submit"]'),
        (By.XPATH, '//button[not(@disabled) and not(@aria-disabled="true") and .//*[contains(normalize-space(.), "Post")]]'),
        (By.XPATH, '//button[not(@disabled) and not(@aria-disabled="true") and contains(normalize-space(.), "Post")]'),
        (By.XPATH, '//button[not(@disabled) and not(@aria-disabled="true") and .//*[contains(normalize-space(.), "Đăng")]]'),
        (By.XPATH, '//button[not(@disabled) and not(@aria-disabled="true") and contains(normalize-space(.), "Đăng")]'),
    ]
    last_error: Exception | None = None
    end_time = time.time() + 180
    while time.time() < end_time:
        for by, value in locators:
            try:
                element = find_element_across_frames(driver, by, value, displayed=True, timeout=2)
                if not element.is_enabled() or element.get_attribute("aria-disabled") == "true":
                    continue
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
                time.sleep(0.2)
                element.click()
                return
            except Exception as exc:
                last_error = exc
        time.sleep(1)
    raise TimeoutException(f"Khong bam duoc nut Post/Dang TikTok. Loi cuoi: {last_error}")


def click_confirm_post_now(driver: WebDriver) -> bool:
    locators = [
        (By.XPATH, '//button[not(@disabled) and not(@aria-disabled="true") and contains(normalize-space(.), "ngay")]'),
        (By.XPATH, '//button[not(@disabled) and not(@aria-disabled="true") and .//*[contains(normalize-space(.), "ngay")]]'),
        (By.XPATH, '//button[not(@disabled) and not(@aria-disabled="true") and contains(normalize-space(.), "Đăng ngay")]'),
        (By.XPATH, '//button[not(@disabled) and not(@aria-disabled="true") and .//*[contains(normalize-space(.), "Đăng ngay")]]'),
        (By.XPATH, '//button[not(@disabled) and not(@aria-disabled="true") and contains(normalize-space(.), "Post now")]'),
        (By.XPATH, '//button[not(@disabled) and not(@aria-disabled="true") and .//*[contains(normalize-space(.), "Post now")]]'),
        (By.XPATH, '//button[not(@disabled) and not(@aria-disabled="true") and contains(normalize-space(.), "Continue")]'),
        (By.XPATH, '//button[not(@disabled) and not(@aria-disabled="true") and contains(normalize-space(.), "Tiếp tục")]'),
    ]
    end_time = time.time() + 20
    last_error: Exception | None = None
    while time.time() < end_time:
        for by, value in locators:
            try:
                element = find_element_across_frames(driver, by, value, displayed=True, timeout=1)
                if not element.is_enabled() or element.get_attribute("aria-disabled") == "true":
                    continue
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
                time.sleep(0.2)
                try:
                    element.click()
                except Exception:
                    driver.execute_script("arguments[0].click();", element)
                print("[INFO] Da bam nut xac nhan Dang ngay/Post now.")
                return True
            except Exception as exc:
                last_error = exc
        time.sleep(0.5)
    print(f"[INFO] Khong thay hop xac nhan Dang ngay/Post now, tiep tuc. Loi cuoi: {last_error}")
    return False


def wait_after_post(driver: WebDriver, timeout: int = 90) -> None:
    end_time = time.time() + timeout
    success_words = [
        "đã đăng",
        "đăng thành công",
        "dang thanh cong",
        "posted",
        "your video is being posted",
        "your video has been posted",
    ]
    while time.time() < end_time:
        summary = current_page_summary(driver).lower()
        if "tiếp tục đăng" not in summary and any(word in summary for word in success_words):
            return
        if "tiktokstudio/content" in driver.current_url.lower() or "tiktokstudio/post" in driver.current_url.lower():
            return
        time.sleep(2)


def wait_upload_ready(driver: WebDriver) -> None:
    end_time = time.time() + 180
    while time.time() < end_time:
        page_text = ""
        try:
            driver.switch_to.default_content()
            page_text = driver.find_element(By.TAG_NAME, "body").text.lower()
        except Exception:
            pass
        if any(text in page_text for text in ["uploaded", "ready", "post", "đăng", "tải lên hoàn tất", "your video has been uploaded"]):
            return
        time.sleep(2)


def wait_tiktok_upload_page(driver: WebDriver) -> None:
    end_time = time.time() + 90
    while time.time() < end_time:
        summary = current_page_summary(driver).lower()
        if "login" in driver.current_url.lower() or "log in" in summary or "dang nhap" in summary:
            print("[CANH BAO] TikTok co ve chua dang nhap. Hay bam 'Mo TikTok dang nhap' va dang nhap truoc.")
        try:
            find_element_across_frames(driver, By.CSS_SELECTOR, 'input[type="file"]', timeout=2)
            return
        except Exception:
            time.sleep(1)
    raise TimeoutException(f"Khong vao duoc trang upload TikTok hoac chua thay nut chon file. {current_page_summary(driver)}")


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
    print(f"[OK] Da chuyen video TikTok thanh cong sang: {target}")


def upload_one_video(driver: WebDriver, video_path: Path, args: argparse.Namespace) -> None:
    print(f"\n[INFO] Dang upload TikTok: {video_path}")
    try:
        driver.get("https://www.tiktok.com/upload")
        wait_tiktok_upload_page(driver)
        file_input = find_element_across_frames(driver, By.CSS_SELECTOR, 'input[type="file"]', timeout=30)
        print("[INFO] Da thay input chon file TikTok, dang gui file...")
        file_input.send_keys(str(video_path))
        wait_upload_ready(driver)
        dismiss_tiktok_popups(driver)

        caption = build_caption(video_path, args)
        print(f"[INFO] Tieu de/caption TikTok: {caption}")
        set_caption(driver, caption)
        dismiss_tiktok_popups(driver)
        click_post(driver)
        click_confirm_post_now(driver)
        wait_after_post(driver)
        time.sleep(args.after_post_wait)
        print(f"[OK] Da bam Post/Dang TikTok: {video_path.name}")
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
        print("[LOI] Khong co video de upload TikTok.")
        sys.exit(1)

    args.default_description = read_text_file(args.description_file)

    print("Danh sach video se upload TikTok:")
    for video in videos:
        print(f"- {video.name} -> {build_caption(video, args)[:160]}{'...' if len(build_caption(video, args)) > 160 else ''}")
    print("\nMo ta TikTok:")
    print(args.default_description[:500] + ("..." if len(args.default_description) > 500 else ""))


    if not args.yes:
        confirm = input("Tiep tuc upload TikTok? Nhap YES de xac nhan: ").strip()
        if confirm != "YES":
            print("Da huy.")
            return

    driver = build_driver(chrome_binary=args.chrome_binary, attach=args.attach)
    successes: list[Path] = []
    failures: list[tuple[Path, str]] = []
    try:
        for index, video in enumerate(videos, start=1):
            print(f"\n[TIEN DO] TikTok video {index}/{len(videos)}")
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
                print(f"[LOI] Upload TikTok loi, bo qua video nay: {video.name}")
                print(f"[LOI] Chi tiet: {message}")
                if args.stop_on_error:
                    break
    finally:
        if args.attach:
            print("[INFO] Dang dung --attach nen tool khong dong Chrome cua ban.")
        else:
            driver.quit()

    print("\n=== Tong ket upload TikTok ===")
    print(f"[OK] Thanh cong: {len(successes)}/{len(videos)}")
    if failures:
        print(f"[LOI] That bai: {len(failures)}")
        for video, message in failures:
            print(f"- {video.name}: {message}")
        sys.exit(1)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="TikTok web auto upload")
    parser.add_argument("--login", action="store_true", help="Mo Chrome de dang nhap TikTok")
    parser.add_argument("--attach", action="store_true", help="Ket noi Chrome da mo bang --login")
    parser.add_argument("--all", action="store_true", help="Upload tat ca video trong thu muc")
    parser.add_argument("--video", help="Upload 1 file video cu the")
    parser.add_argument("--video-dir", default="videos", help="Thu muc lay video khi dung --all")
    parser.add_argument("--title", default="", help="Tieu de/caption rieng. Neu bo trong thi tu lay ten file")
    parser.add_argument("--description", default="", help="Mo ta TikTok neu khong dung file .txt")
    parser.add_argument("--description-file", default="tiktok_description.txt", help="File mo ta TikTok")
    parser.add_argument("--delay", type=int, default=5, help="So giay nghi giua moi video")
    parser.add_argument("--after-post-wait", type=int, default=15, help="So giay doi sau khi bam Post")
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
        print("[OK] Da mo TikTok Upload. Hay dang nhap TikTok, sau do giu nguyen Chrome.")
    else:
        run_upload(args)


if __name__ == "__main__":
    main()
