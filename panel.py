# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import queue
import os
import re
import runpy
import shutil
import subprocess
import sys
import threading
from pathlib import Path
from tkinter import END, BOTH, LEFT, RIGHT, X, Y, BooleanVar, StringVar, Tk, filedialog, messagebox
from tkinter import font as tkfont
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText

from download_formats import full_hd_with_audio_args

if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).resolve().parent
else:
    BASE_DIR = Path(__file__).resolve().parent
VIDEOS_DIR = BASE_DIR / "videos"
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
FACEBOOK_PROFILE_DOWNLOAD_FILE = BASE_DIR / "facebook_profile_download.py"
INSTAGRAM_UPLOAD_FILE = BASE_DIR / "instagram_upload.py"
AYRSHARE_UPLOAD_FILE = BASE_DIR / "ayrshare_upload.py"
AYRSHARE_LOG_FILE = BASE_DIR / "ayrshare_last_run.log"
ZERNIO_UPLOAD_FILE = BASE_DIR / "zernio_upload.py"
ZERNIO_LOG_FILE = BASE_DIR / "zernio_last_run.log"
YTDLP_FILE = BASE_DIR / "yt-dlp.exe"
LOCAL_FFMPEG_FILE = BASE_DIR / "ffmpeg.exe"
YOUTUBE_PROFILE_DIR = BASE_DIR / "chrome-profile"
TIKTOK_PROFILE_DIR = BASE_DIR / "chrome-profile-tiktok"
FACEBOOK_PROFILE_DIR = BASE_DIR / "chrome-profile-facebook"
INSTAGRAM_PROFILE_DIR = BASE_DIR / "chrome-profile-instagram"
YOUTUBE_DEBUG_PORT = 9222
TIKTOK_DEBUG_PORT = 9223
FACEBOOK_DEBUG_PORT = 9224
INSTAGRAM_DEBUG_PORT = 9225
TIKTOK_DOWNLOAD_DIR = BASE_DIR / "TikTok_Channel"
TIKTOK_ARCHIVE_FILE = BASE_DIR / "archive_video.txt"
FACEBOOK_DOWNLOAD_DIR = BASE_DIR / "Facebook_Channel"
FACEBOOK_ARCHIVE_FILE = BASE_DIR / "facebook_archive_video.txt"
YOUTUBE_ARCHIVE_FILE = BASE_DIR / "youtube_archive_video.txt"
VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}
URL_RE = re.compile(r"https?://\S+")


class UploadPanel:
    def __init__(self, root: Tk) -> None:
        self.root = root
        self.root.title("Bảng điều khiển upload Mstar")
        self.root.geometry("1120x720")
        self.root.minsize(980, 620)

        self.output_queue: queue.Queue[tuple[str, str, str | int | None]] = queue.Queue()
        self.processes: dict[str, subprocess.Popen[str]] = {}
        self.workers: dict[str, threading.Thread] = {}
        self.active_groups: set[str] = set()

        self.visibility = StringVar(value="public")
        self.made_for_kids = StringVar(value="no")
        self.delay = StringVar(value="2")
        self.attach = BooleanVar(value=True)
        self.upload_dir = StringVar(value=str(VIDEOS_DIR))
        self.selected_video = StringVar(value="")
        self.custom_title = StringVar(value="")
        self.tiktok_upload_dir = StringVar(value=str(TIKTOK_DOWNLOAD_DIR))
        self.tiktok_selected_video = StringVar(value="")
        self.tiktok_custom_title = StringVar(value="")
        self.tiktok_delay = StringVar(value="5")
        self.tiktok_attach = BooleanVar(value=True)
        self.tiktok_move_success = BooleanVar(value=False)
        self.facebook_upload_dir = StringVar(value=str(VIDEOS_DIR))
        self.facebook_selected_video = StringVar(value="")
        self.facebook_mode = StringVar(value="reels-api")
        self.facebook_target_url = StringVar(value="https://www.facebook.com")
        self.facebook_page_id = StringVar(value="")
        self.facebook_page_token = StringVar(value="")
        self.facebook_api_version = StringVar(value="v23.0")
        self.facebook_custom_title = StringVar(value="")
        self.facebook_delay = StringVar(value="10")
        self.facebook_attach = BooleanVar(value=True)
        self.facebook_move_success = BooleanVar(value=False)
        self.instagram_upload_dir = StringVar(value=str(VIDEOS_DIR))
        self.instagram_selected_video = StringVar(value="")
        self.instagram_custom_title = StringVar(value="")
        self.instagram_delay = StringVar(value="5")
        self.instagram_attach = BooleanVar(value=True)
        self.ayrshare_upload_dir = StringVar(value=str(VIDEOS_DIR))
        self.ayrshare_selected_video = StringVar(value="")
        self.ayrshare_api_key = StringVar(value="")
        self.ayrshare_platforms = StringVar(value="facebook,instagram,tiktok,youtube")
        self.ayrshare_custom_title = StringVar(value="")
        self.ayrshare_start_after = StringVar(value="30")
        self.ayrshare_min_gap = StringVar(value="60")
        self.ayrshare_max_gap = StringVar(value="180")
        self.ayrshare_max_videos = StringVar(value="3")
        self.zernio_upload_dir = StringVar(value=str(VIDEOS_DIR))
        self.zernio_selected_video = StringVar(value="")
        self.zernio_api_key = StringVar(value="")
        self.zernio_platforms = StringVar(value="facebook,instagram,tiktok,youtube")
        self.zernio_account_ids = StringVar(value="")
        self.zernio_profile_id = StringVar(value="")
        self.zernio_custom_title = StringVar(value="")
        self.zernio_start_after = StringVar(value="30")
        self.zernio_min_gap = StringVar(value="60")
        self.zernio_max_gap = StringVar(value="180")
        self.zernio_max_videos = StringVar(value="3")
        self.title_hashtags = StringVar(value="")
        self.description_hashtags = StringVar(value="")
        self.download_dir = StringVar(value=str(VIDEOS_DIR))
        self.download_format = StringVar(value="full_hd_1080")
        self.output_template = StringVar(value="%(title).180s #%(uploader).50s.%(ext)s")
        self.allow_playlist = BooleanVar(value=True)
        self.extra_ytdlp_args = StringVar(value="")
        self.status = StringVar(value="Sẵn sàng")

        self._configure_fonts()
        self._build_style()
        self.load_panel_settings()
        self._build_layout()
        self.refresh_videos()
        self.refresh_tiktok_videos()
        self.refresh_facebook_videos()
        self.refresh_instagram_videos()
        self.refresh_ayrshare_videos()
        self.refresh_zernio_videos()
        self.load_description()
        self.load_tiktok_description()
        self.load_facebook_description()
        self.load_instagram_description()
        self.load_hashtags()
        self.root.after(150, self._drain_output_queue)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _configure_fonts(self) -> None:
        """Ưu tiên font Windows hỗ trợ đầy đủ tiếng Việt có dấu."""
        default_font = tkfont.nametofont("TkDefaultFont")
        text_font = tkfont.nametofont("TkTextFont")
        fixed_font = tkfont.nametofont("TkFixedFont")
        default_font.configure(family="Segoe UI", size=10)
        text_font.configure(family="Segoe UI", size=10)
        fixed_font.configure(family="Segoe UI", size=9)
        self.root.option_add("*Font", default_font)

    def _build_style(self) -> None:
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("TFrame", background="#f6f7f9")
        style.configure("TLabel", background="#f6f7f9", foreground="#172033", font=("Segoe UI", 10))
        style.configure("Header.TLabel", font=("Segoe UI Semibold", 18), foreground="#111827")
        style.configure("Subtle.TLabel", foreground="#667085")
        style.configure("TButton", font=("Segoe UI", 10), padding=(12, 7))
        style.configure("Accent.TButton", font=("Segoe UI Semibold", 10), padding=(14, 8))
        style.configure("TLabelframe", background="#f6f7f9")
        style.configure("TLabelframe.Label", background="#f6f7f9", foreground="#344054", font=("Segoe UI Semibold", 10))
        style.configure("Treeview", font=("Segoe UI", 10), rowheight=24)
        style.configure("Treeview.Heading", font=("Segoe UI Semibold", 10))

    def _build_layout(self) -> None:
        root_frame = ttk.Frame(self.root, padding=18)
        root_frame.pack(fill=BOTH, expand=True)

        header = ttk.Frame(root_frame)
        header.pack(fill=X, pady=(0, 14))
        ttk.Label(header, text="Bảng điều khiển upload Mstar", style="Header.TLabel").pack(side=LEFT)
        ttk.Label(header, textvariable=self.status, style="Subtle.TLabel").pack(side=RIGHT)

        notebook = ttk.Notebook(root_frame)
        notebook.pack(fill=BOTH, expand=True)

        upload_tab = ttk.Frame(notebook, padding=0)
        tiktok_tab = ttk.Frame(notebook, padding=0)
        facebook_tab = ttk.Frame(notebook, padding=0)
        instagram_tab = ttk.Frame(notebook, padding=0)
        ayrshare_tab = ttk.Frame(notebook, padding=0)
        zernio_tab = ttk.Frame(notebook, padding=0)
        download_tab = ttk.Frame(notebook, padding=0)
        notebook.add(upload_tab, text="Upload YouTube")
        notebook.add(tiktok_tab, text="Upload TikTok")
        notebook.add(facebook_tab, text="Upload Facebook")
        notebook.add(instagram_tab, text="Upload Instagram")
        notebook.add(ayrshare_tab, text="Ayrshare")
        notebook.add(zernio_tab, text="Zernio")
        notebook.add(download_tab, text="Tải video")

        body = ttk.PanedWindow(upload_tab, orient="horizontal")
        body.pack(fill=BOTH, expand=True)

        left_panel = ttk.Frame(body, padding=(0, 0, 12, 0))
        right_panel = ttk.Frame(body, padding=(12, 0, 0, 0))
        body.add(left_panel, weight=3)
        body.add(right_panel, weight=2)

        self._build_video_section(left_panel)
        self._build_description_section(left_panel)
        self._build_action_section(right_panel)
        self._build_log_section(right_panel)
        self._build_tiktok_tab(tiktok_tab)
        self._build_facebook_tab(facebook_tab)
        self._build_instagram_tab(instagram_tab)
        self._build_ayrshare_tab(ayrshare_tab)
        self._build_zernio_tab(zernio_tab)
        self._build_download_tab(download_tab)

    def _build_tiktok_tab(self, parent: ttk.Frame) -> None:
        body = ttk.PanedWindow(parent, orient="horizontal")
        body.pack(fill=BOTH, expand=True)

        left_panel = ttk.Frame(body, padding=(0, 0, 12, 0))
        right_panel = ttk.Frame(body, padding=(12, 0, 0, 0))
        body.add(left_panel, weight=3)
        body.add(right_panel, weight=2)

        section = ttk.LabelFrame(left_panel, text="Video upload lên TikTok")
        section.pack(fill=BOTH, expand=True)

        toolbar = ttk.Frame(section, padding=10)
        toolbar.pack(fill=X)
        ttk.Button(toolbar, text="Làm mới", command=self.refresh_tiktok_videos).pack(side=LEFT)
        ttk.Button(toolbar, text="Chọn thư mục TikTok", command=self.choose_tiktok_upload_dir).pack(side=LEFT, padx=(8, 0))
        ttk.Button(toolbar, text="Mở thư mục", command=self.open_tiktok_upload_folder).pack(side=LEFT, padx=(8, 0))

        dir_row = ttk.Frame(section, padding=(10, 0, 10, 8))
        dir_row.pack(fill=X)
        ttk.Label(dir_row, text="Thư mục upload").pack(side=LEFT)
        ttk.Entry(dir_row, textvariable=self.tiktok_upload_dir).pack(side=LEFT, fill=X, expand=True, padx=(12, 0))

        columns = ("name", "size", "modified")
        self.tiktok_video_tree = ttk.Treeview(section, columns=columns, show="headings", selectmode="browse", height=16)
        self.tiktok_video_tree.heading("name", text="Tên file")
        self.tiktok_video_tree.heading("size", text="Dung lượng")
        self.tiktok_video_tree.heading("modified", text="Sửa lần cuối")
        self.tiktok_video_tree.column("name", minwidth=260, width=460, stretch=True)
        self.tiktok_video_tree.column("size", minwidth=90, width=110, anchor="e", stretch=False)
        self.tiktok_video_tree.column("modified", minwidth=140, width=170, stretch=False)
        self.tiktok_video_tree.pack(fill=BOTH, expand=True, padx=10, pady=(0, 10))
        self.tiktok_video_tree.bind("<<TreeviewSelect>>", self._on_tiktok_video_selected)

        desc_section = ttk.LabelFrame(left_panel, text="Mô tả TikTok")
        desc_section.pack(fill=BOTH, expand=True, pady=(14, 0))
        desc_buttons = ttk.Frame(desc_section, padding=10)
        desc_buttons.pack(fill=X)
        ttk.Button(desc_buttons, text="Lưu mô tả TikTok", command=self.save_tiktok_description).pack(side=LEFT)
        ttk.Button(desc_buttons, text="Tải lại", command=self.load_tiktok_description).pack(side=LEFT, padx=(8, 0))
        self.tiktok_description_text = ScrolledText(desc_section, height=7, wrap="word", font=("Segoe UI", 10), undo=True)
        self.tiktok_description_text.pack(fill=BOTH, expand=True, padx=10, pady=(0, 10))

        action_section = ttk.LabelFrame(right_panel, text="Điều khiển TikTok")
        action_section.pack(fill=X)
        form = ttk.Frame(action_section, padding=12)
        form.pack(fill=X)
        ttk.Label(form, text="Tiêu đề riêng").grid(row=0, column=0, sticky="w")
        ttk.Entry(form, textvariable=self.tiktok_custom_title).grid(row=0, column=1, sticky="ew", padx=(12, 0), pady=4)
        ttk.Label(form, text="Nghỉ giữa video").grid(row=1, column=0, sticky="w")
        ttk.Entry(form, textvariable=self.tiktok_delay, width=20).grid(row=1, column=1, sticky="ew", padx=(12, 0), pady=4)
        ttk.Checkbutton(form, text="Kết nối Chrome đã đăng nhập (--attach)", variable=self.tiktok_attach).grid(
            row=2, column=0, columnspan=2, sticky="w", pady=(8, 2)
        )
        form.columnconfigure(1, weight=1)

        actions = ttk.Frame(action_section, padding=(12, 0, 12, 12))
        actions.pack(fill=X)
        ttk.Button(actions, text="Mở TikTok đăng nhập", command=self.run_tiktok_login, style="Accent.TButton").pack(fill=X)
        ttk.Button(actions, text="Upload tất cả lên TikTok", command=self.upload_tiktok_all, style="Accent.TButton").pack(fill=X, pady=(8, 0))
        ttk.Button(actions, text="Upload video đang chọn", command=self.upload_tiktok_selected).pack(fill=X, pady=(8, 0))
        ttk.Button(actions, text="Dừng tiến trình", command=lambda: self.stop_process("tiktok")).pack(fill=X, pady=(8, 0))

        note = ttk.LabelFrame(right_panel, text="Gợi ý")
        note.pack(fill=X, pady=(14, 0))
        ttk.Label(
            note,
            text=(
                "Đăng nhập TikTok trước bằng nút Mở TikTok đăng nhập. "
                "Ô Tiêu đề riêng để trống thì tool tự lấy tên file video làm caption. "
                "Nếu nhập tiêu đề riêng, tất cả video trong lần upload sẽ dùng caption đó."
            ),
            style="Subtle.TLabel",
            wraplength=360,
            justify="left",
        ).pack(fill=X, padx=12, pady=12)

        log_section = ttk.LabelFrame(right_panel, text="Log TikTok")
        log_section.pack(fill=BOTH, expand=True, pady=(14, 0))
        self.tiktok_log_text = ScrolledText(log_section, height=18, wrap="word", font=("Segoe UI", 9), state="disabled")
        self.tiktok_log_text.pack(fill=BOTH, expand=True, padx=10, pady=10)

    def _build_facebook_tab(self, parent: ttk.Frame) -> None:
        body = ttk.PanedWindow(parent, orient="horizontal")
        body.pack(fill=BOTH, expand=True)

        left_panel = ttk.Frame(body, padding=(0, 0, 12, 0))
        right_panel = ttk.Frame(body, padding=(12, 0, 0, 0))
        body.add(left_panel, weight=3)
        body.add(right_panel, weight=2)

        section = ttk.LabelFrame(left_panel, text="Video upload lên Facebook")
        section.pack(fill=BOTH, expand=True)

        toolbar = ttk.Frame(section, padding=10)
        toolbar.pack(fill=X)
        ttk.Button(toolbar, text="Làm mới", command=self.refresh_facebook_videos).pack(side=LEFT)
        ttk.Button(toolbar, text="Chọn thư mục Facebook", command=self.choose_facebook_upload_dir).pack(side=LEFT, padx=(8, 0))
        ttk.Button(toolbar, text="Mở thư mục", command=self.open_facebook_upload_folder).pack(side=LEFT, padx=(8, 0))

        dir_row = ttk.Frame(section, padding=(10, 0, 10, 8))
        dir_row.pack(fill=X)
        ttk.Label(dir_row, text="Thư mục upload").pack(side=LEFT)
        ttk.Entry(dir_row, textvariable=self.facebook_upload_dir).pack(side=LEFT, fill=X, expand=True, padx=(12, 0))

        columns = ("name", "size", "modified")
        self.facebook_video_tree = ttk.Treeview(section, columns=columns, show="headings", selectmode="browse", height=16)
        self.facebook_video_tree.heading("name", text="Tên file")
        self.facebook_video_tree.heading("size", text="Dung lượng")
        self.facebook_video_tree.heading("modified", text="Sửa lần cuối")
        self.facebook_video_tree.column("name", minwidth=260, width=460, stretch=True)
        self.facebook_video_tree.column("size", minwidth=90, width=110, anchor="e", stretch=False)
        self.facebook_video_tree.column("modified", minwidth=140, width=170, stretch=False)
        self.facebook_video_tree.pack(fill=BOTH, expand=True, padx=10, pady=(0, 10))
        self.facebook_video_tree.bind("<<TreeviewSelect>>", self._on_facebook_video_selected)

        desc_section = ttk.LabelFrame(left_panel, text="Mô tả Facebook")
        desc_section.pack(fill=BOTH, expand=True, pady=(14, 0))
        desc_buttons = ttk.Frame(desc_section, padding=10)
        desc_buttons.pack(fill=X)
        ttk.Button(desc_buttons, text="Lưu mô tả Facebook", command=self.save_facebook_description).pack(side=LEFT)
        ttk.Button(desc_buttons, text="Tải lại", command=self.load_facebook_description).pack(side=LEFT, padx=(8, 0))
        self.facebook_description_text = ScrolledText(desc_section, height=7, wrap="word", font=("Segoe UI", 10), undo=True)
        self.facebook_description_text.pack(fill=BOTH, expand=True, padx=10, pady=(0, 10))

        action_section = ttk.LabelFrame(right_panel, text="Điều khiển Facebook")
        action_section.pack(fill=X)
        form = ttk.Frame(action_section, padding=12)
        form.pack(fill=X)
        ttk.Label(form, text="Chế độ").grid(row=0, column=0, sticky="w")
        ttk.Combobox(
            form,
            textvariable=self.facebook_mode,
            values=("reels-api", "browser"),
            state="readonly",
            width=18,
        ).grid(row=0, column=1, sticky="ew", padx=(12, 0), pady=4)
        ttk.Label(form, text="Page ID").grid(row=1, column=0, sticky="w")
        ttk.Entry(form, textvariable=self.facebook_page_id).grid(row=1, column=1, sticky="ew", padx=(12, 0), pady=4)
        ttk.Label(form, text="Page Access Token").grid(row=2, column=0, sticky="w")
        ttk.Entry(form, textvariable=self.facebook_page_token, show="*").grid(row=2, column=1, sticky="ew", padx=(12, 0), pady=4)
        ttk.Label(form, text="API version").grid(row=3, column=0, sticky="w")
        ttk.Entry(form, textvariable=self.facebook_api_version, width=20).grid(row=3, column=1, sticky="ew", padx=(12, 0), pady=4)
        ttk.Label(form, text="Target URL").grid(row=4, column=0, sticky="w")
        ttk.Entry(form, textvariable=self.facebook_target_url).grid(row=4, column=1, sticky="ew", padx=(12, 0), pady=4)
        ttk.Label(form, text="Tiêu đề riêng").grid(row=5, column=0, sticky="w")
        ttk.Entry(form, textvariable=self.facebook_custom_title).grid(row=5, column=1, sticky="ew", padx=(12, 0), pady=4)
        ttk.Label(form, text="Nghỉ giữa video").grid(row=6, column=0, sticky="w")
        ttk.Entry(form, textvariable=self.facebook_delay, width=20).grid(row=6, column=1, sticky="ew", padx=(12, 0), pady=4)
        ttk.Checkbutton(form, text="Kết nối Chrome đã đăng nhập (--attach)", variable=self.facebook_attach).grid(
            row=7, column=0, columnspan=2, sticky="w", pady=(8, 2)
        )
        form.columnconfigure(1, weight=1)

        actions = ttk.Frame(action_section, padding=(12, 0, 12, 12))
        actions.pack(fill=X)
        ttk.Button(actions, text="Mở Facebook đăng nhập", command=self.run_facebook_login, style="Accent.TButton").pack(fill=X)
        ttk.Button(actions, text="Upload tất cả lên Facebook", command=self.upload_facebook_all, style="Accent.TButton").pack(fill=X, pady=(8, 0))
        ttk.Button(actions, text="Upload video đang chọn", command=self.upload_facebook_selected).pack(fill=X, pady=(8, 0))
        ttk.Button(actions, text="Dừng tiến trình", command=lambda: self.stop_process("facebook")).pack(fill=X, pady=(8, 0))

        note = ttk.LabelFrame(right_panel, text="Gợi ý")
        note.pack(fill=X, pady=(14, 0))
        ttk.Label(
            note,
            text=(
                "Nhập Target URL là link Profile/Page/Group cần đăng. "
                "Chế độ reels-api cần Page ID và Page Access Token, dùng để đăng Reels lên Page. "
                "Chế độ browser dùng Target URL và Chrome đã đăng nhập. "
                "Caption sẽ gồm tên file hoặc tiêu đề riêng + nội dung trong default_description.txt."
            ),
            style="Subtle.TLabel",
            wraplength=360,
            justify="left",
        ).pack(fill=X, padx=12, pady=12)

        log_section = ttk.LabelFrame(right_panel, text="Log Facebook")
        log_section.pack(fill=BOTH, expand=True, pady=(14, 0))
        self.facebook_log_text = ScrolledText(log_section, height=18, wrap="word", font=("Segoe UI", 9), state="disabled")
        self.facebook_log_text.pack(fill=BOTH, expand=True, padx=10, pady=10)

    def _build_instagram_tab(self, parent: ttk.Frame) -> None:
        body = ttk.PanedWindow(parent, orient="horizontal")
        body.pack(fill=BOTH, expand=True)

        left_panel = ttk.Frame(body, padding=(0, 0, 12, 0))
        right_panel = ttk.Frame(body, padding=(12, 0, 0, 0))
        body.add(left_panel, weight=3)
        body.add(right_panel, weight=2)

        section = ttk.LabelFrame(left_panel, text="Video upload lên Instagram")
        section.pack(fill=BOTH, expand=True)

        toolbar = ttk.Frame(section, padding=10)
        toolbar.pack(fill=X)
        ttk.Button(toolbar, text="Làm mới", command=self.refresh_instagram_videos).pack(side=LEFT)
        ttk.Button(toolbar, text="Chọn thư mục Instagram", command=self.choose_instagram_upload_dir).pack(side=LEFT, padx=(8, 0))
        ttk.Button(toolbar, text="Mở thư mục", command=self.open_instagram_upload_folder).pack(side=LEFT, padx=(8, 0))

        dir_row = ttk.Frame(section, padding=(10, 0, 10, 8))
        dir_row.pack(fill=X)
        ttk.Label(dir_row, text="Thư mục upload").pack(side=LEFT)
        ttk.Entry(dir_row, textvariable=self.instagram_upload_dir).pack(side=LEFT, fill=X, expand=True, padx=(12, 0))

        columns = ("name", "size", "modified")
        self.instagram_video_tree = ttk.Treeview(section, columns=columns, show="headings", selectmode="browse", height=16)
        self.instagram_video_tree.heading("name", text="Tên file")
        self.instagram_video_tree.heading("size", text="Dung lượng")
        self.instagram_video_tree.heading("modified", text="Sửa lần cuối")
        self.instagram_video_tree.column("name", minwidth=260, width=460, stretch=True)
        self.instagram_video_tree.column("size", minwidth=90, width=110, anchor="e", stretch=False)
        self.instagram_video_tree.column("modified", minwidth=140, width=170, stretch=False)
        self.instagram_video_tree.pack(fill=BOTH, expand=True, padx=10, pady=(0, 10))
        self.instagram_video_tree.bind("<<TreeviewSelect>>", self._on_instagram_video_selected)

        desc_section = ttk.LabelFrame(left_panel, text="Mô tả Instagram")
        desc_section.pack(fill=BOTH, expand=True, pady=(14, 0))
        desc_buttons = ttk.Frame(desc_section, padding=10)
        desc_buttons.pack(fill=X)
        ttk.Button(desc_buttons, text="Lưu mô tả Instagram", command=self.save_instagram_description).pack(side=LEFT)
        ttk.Button(desc_buttons, text="Tải lại", command=self.load_instagram_description).pack(side=LEFT, padx=(8, 0))
        self.instagram_description_text = ScrolledText(desc_section, height=7, wrap="word", font=("Segoe UI", 10), undo=True)
        self.instagram_description_text.pack(fill=BOTH, expand=True, padx=10, pady=(0, 10))

        action_section = ttk.LabelFrame(right_panel, text="Điều khiển Instagram")
        action_section.pack(fill=X)
        form = ttk.Frame(action_section, padding=12)
        form.pack(fill=X)
        ttk.Label(form, text="Tiêu đề riêng").grid(row=0, column=0, sticky="w")
        ttk.Entry(form, textvariable=self.instagram_custom_title).grid(row=0, column=1, sticky="ew", padx=(12, 0), pady=4)
        ttk.Label(form, text="Nghỉ giữa video").grid(row=1, column=0, sticky="w")
        ttk.Entry(form, textvariable=self.instagram_delay, width=20).grid(row=1, column=1, sticky="ew", padx=(12, 0), pady=4)
        ttk.Checkbutton(form, text="Kết nối Chrome đã đăng nhập (--attach)", variable=self.instagram_attach).grid(
            row=2, column=0, columnspan=2, sticky="w", pady=(8, 2)
        )
        form.columnconfigure(1, weight=1)

        actions = ttk.Frame(action_section, padding=(12, 0, 12, 12))
        actions.pack(fill=X)
        ttk.Button(actions, text="Mở Instagram đăng nhập", command=self.run_instagram_login, style="Accent.TButton").pack(fill=X)
        ttk.Button(actions, text="Upload tất cả lên Instagram", command=self.upload_instagram_all, style="Accent.TButton").pack(fill=X, pady=(8, 0))
        ttk.Button(actions, text="Upload video đang chọn", command=self.upload_instagram_selected).pack(fill=X, pady=(8, 0))
        ttk.Button(actions, text="Dừng tiến trình", command=lambda: self.stop_process("instagram")).pack(fill=X, pady=(8, 0))

        note = ttk.LabelFrame(right_panel, text="Gợi ý")
        note.pack(fill=X, pady=(14, 0))
        ttk.Label(
            note,
            text=(
                "Đăng nhập Instagram trước bằng nút Mở Instagram đăng nhập. "
                "Tool dùng Chrome profile riêng, port 9225. "
                "Caption sẽ gồm tên file hoặc tiêu đề riêng + nội dung trong instagram_description.txt. "
                "Instagram web hay đổi giao diện, nếu lỗi hãy bật SAVE_DEBUG_ARTIFACTS=1 để lưu debug."
            ),
            style="Subtle.TLabel",
            wraplength=360,
            justify="left",
        ).pack(fill=X, padx=12, pady=12)

        log_section = ttk.LabelFrame(right_panel, text="Log Instagram")
        log_section.pack(fill=BOTH, expand=True, pady=(14, 0))
        self.instagram_log_text = ScrolledText(log_section, height=18, wrap="word", font=("Segoe UI", 9), state="disabled")
        self.instagram_log_text.pack(fill=BOTH, expand=True, padx=10, pady=10)

    def _build_ayrshare_tab(self, parent: ttk.Frame) -> None:
        body = ttk.PanedWindow(parent, orient="horizontal")
        body.pack(fill=BOTH, expand=True)

        left_panel = ttk.Frame(body, padding=(0, 0, 12, 0))
        right_panel = ttk.Frame(body, padding=(12, 0, 0, 0))
        body.add(left_panel, weight=3)
        body.add(right_panel, weight=2)

        section = ttk.LabelFrame(left_panel, text="Video dang qua Ayrshare")
        section.pack(fill=BOTH, expand=True)

        toolbar = ttk.Frame(section, padding=10)
        toolbar.pack(fill=X)
        ttk.Button(toolbar, text="Lam moi", command=self.refresh_ayrshare_videos).pack(side=LEFT)
        ttk.Button(toolbar, text="Chon thu muc", command=self.choose_ayrshare_upload_dir).pack(side=LEFT, padx=(8, 0))
        ttk.Button(toolbar, text="Mo thu muc", command=self.open_ayrshare_upload_folder).pack(side=LEFT, padx=(8, 0))

        dir_row = ttk.Frame(section, padding=(10, 0, 10, 8))
        dir_row.pack(fill=X)
        ttk.Label(dir_row, text="Thu muc upload").pack(side=LEFT)
        ttk.Entry(dir_row, textvariable=self.ayrshare_upload_dir).pack(side=LEFT, fill=X, expand=True, padx=(12, 0))

        columns = ("name", "size", "modified")
        self.ayrshare_video_tree = ttk.Treeview(section, columns=columns, show="headings", selectmode="browse", height=16)
        self.ayrshare_video_tree.heading("name", text="Ten file")
        self.ayrshare_video_tree.heading("size", text="Dung luong")
        self.ayrshare_video_tree.heading("modified", text="Sua lan cuoi")
        self.ayrshare_video_tree.column("name", minwidth=260, width=460, stretch=True)
        self.ayrshare_video_tree.column("size", minwidth=90, width=110, anchor="e", stretch=False)
        self.ayrshare_video_tree.column("modified", minwidth=140, width=170, stretch=False)
        self.ayrshare_video_tree.pack(fill=BOTH, expand=True, padx=10, pady=(0, 10))
        self.ayrshare_video_tree.bind("<<TreeviewSelect>>", self._on_ayrshare_video_selected)

        desc_section = ttk.LabelFrame(left_panel, text="Mo ta Ayrshare")
        desc_section.pack(fill=X, pady=(14, 0))
        desc_buttons = ttk.Frame(desc_section, padding=10)
        desc_buttons.pack(fill=X)
        ttk.Button(desc_buttons, text="Luu default_description.txt", command=self.save_description).pack(side=LEFT)
        ttk.Button(desc_buttons, text="Tai lai", command=self.load_description).pack(side=LEFT, padx=(8, 0))
        ttk.Label(desc_section, text="Ayrshare dung mo ta trong tab YouTube/default_description.txt.", style="Subtle.TLabel").pack(fill=X, padx=10, pady=(0, 10))

        action_section = ttk.LabelFrame(right_panel, text="Dieu khien Ayrshare")
        action_section.pack(fill=X)
        form = ttk.Frame(action_section, padding=12)
        form.pack(fill=X)
        ttk.Label(form, text="API key").grid(row=0, column=0, sticky="w")
        ttk.Entry(form, textvariable=self.ayrshare_api_key, show="*").grid(row=0, column=1, sticky="ew", padx=(12, 0), pady=4)
        ttk.Label(form, text="Platforms").grid(row=1, column=0, sticky="w")
        ttk.Entry(form, textvariable=self.ayrshare_platforms).grid(row=1, column=1, sticky="ew", padx=(12, 0), pady=4)
        ttk.Label(form, text="Tieu de rieng").grid(row=2, column=0, sticky="w")
        ttk.Entry(form, textvariable=self.ayrshare_custom_title).grid(row=2, column=1, sticky="ew", padx=(12, 0), pady=4)
        ttk.Label(form, text="Bat dau sau phut").grid(row=3, column=0, sticky="w")
        ttk.Entry(form, textvariable=self.ayrshare_start_after, width=20).grid(row=3, column=1, sticky="ew", padx=(12, 0), pady=4)
        ttk.Label(form, text="Random min phut").grid(row=4, column=0, sticky="w")
        ttk.Entry(form, textvariable=self.ayrshare_min_gap, width=20).grid(row=4, column=1, sticky="ew", padx=(12, 0), pady=4)
        ttk.Label(form, text="Random max phut").grid(row=5, column=0, sticky="w")
        ttk.Entry(form, textvariable=self.ayrshare_max_gap, width=20).grid(row=5, column=1, sticky="ew", padx=(12, 0), pady=4)
        ttk.Label(form, text="Toi da video moi lan").grid(row=6, column=0, sticky="w")
        ttk.Entry(form, textvariable=self.ayrshare_max_videos, width=20).grid(row=6, column=1, sticky="ew", padx=(12, 0), pady=4)
        form.columnconfigure(1, weight=1)

        actions = ttk.Frame(action_section, padding=(12, 0, 12, 12))
        actions.pack(fill=X)
        ttk.Button(actions, text="Dang tat ca qua Ayrshare (lich random)", command=self.upload_ayrshare_all, style="Accent.TButton").pack(fill=X)
        ttk.Button(actions, text="Dang video dang chon qua Ayrshare", command=self.upload_ayrshare_selected).pack(fill=X, pady=(8, 0))
        ttk.Button(actions, text="Dung tien trinh", command=lambda: self.stop_process("ayrshare")).pack(fill=X, pady=(8, 0))

        note = ttk.LabelFrame(right_panel, text="Ghi chu")
        note.pack(fill=X, pady=(14, 0))
        ttk.Label(
            note,
            text=(
                "Ket noi cac mang xa hoi trong Ayrshare dashboard truoc. "
                "Tool se upload file local len Ayrshare media roi hen lich post random. "
                "Platforms co the nhap facebook,instagram,tiktok,youtube hoac all."
            ),
            style="Subtle.TLabel",
            wraplength=360,
            justify="left",
        ).pack(fill=X, padx=12, pady=12)

        log_section = ttk.LabelFrame(right_panel, text="Log Ayrshare")
        log_section.pack(fill=BOTH, expand=True, pady=(14, 0))
        self.ayrshare_log_text = ScrolledText(log_section, height=18, wrap="word", font=("Segoe UI", 9), state="disabled")
        self.ayrshare_log_text.pack(fill=BOTH, expand=True, padx=10, pady=10)

    def _build_zernio_tab(self, parent: ttk.Frame) -> None:
        body = ttk.PanedWindow(parent, orient="horizontal")
        body.pack(fill=BOTH, expand=True)
        left_panel = ttk.Frame(body, padding=(0, 0, 12, 0))
        right_panel = ttk.Frame(body, padding=(12, 0, 0, 0))
        body.add(left_panel, weight=3)
        body.add(right_panel, weight=2)

        section = ttk.LabelFrame(left_panel, text="Video dang qua Zernio")
        section.pack(fill=BOTH, expand=True)
        toolbar = ttk.Frame(section, padding=10)
        toolbar.pack(fill=X)
        ttk.Button(toolbar, text="Lam moi", command=self.refresh_zernio_videos).pack(side=LEFT)
        ttk.Button(toolbar, text="Chon thu muc", command=self.choose_zernio_upload_dir).pack(side=LEFT, padx=(8, 0))
        ttk.Button(toolbar, text="Mo thu muc", command=self.open_zernio_upload_folder).pack(side=LEFT, padx=(8, 0))
        dir_row = ttk.Frame(section, padding=(10, 0, 10, 8))
        dir_row.pack(fill=X)
        ttk.Label(dir_row, text="Thu muc upload").pack(side=LEFT)
        ttk.Entry(dir_row, textvariable=self.zernio_upload_dir).pack(side=LEFT, fill=X, expand=True, padx=(12, 0))

        columns = ("name", "size", "modified")
        self.zernio_video_tree = ttk.Treeview(section, columns=columns, show="headings", selectmode="browse", height=16)
        for key, label in (("name", "Ten file"), ("size", "Dung luong"), ("modified", "Sua lan cuoi")):
            self.zernio_video_tree.heading(key, text=label)
        self.zernio_video_tree.column("name", minwidth=260, width=460, stretch=True)
        self.zernio_video_tree.column("size", minwidth=90, width=110, anchor="e", stretch=False)
        self.zernio_video_tree.column("modified", minwidth=140, width=170, stretch=False)
        self.zernio_video_tree.pack(fill=BOTH, expand=True, padx=10, pady=(0, 10))
        self.zernio_video_tree.bind("<<TreeviewSelect>>", self._on_zernio_video_selected)

        desc_section = ttk.LabelFrame(left_panel, text="Mo ta Zernio")
        desc_section.pack(fill=X, pady=(14, 0))
        ttk.Label(desc_section, text="Zernio dung mo ta trong tab YouTube/default_description.txt.", style="Subtle.TLabel").pack(fill=X, padx=10, pady=10)

        action_section = ttk.LabelFrame(right_panel, text="Dieu khien Zernio")
        action_section.pack(fill=X)
        form = ttk.Frame(action_section, padding=12)
        form.pack(fill=X)
        fields = [
            ("API key(s)", self.zernio_api_key, True),
            ("Platforms", self.zernio_platforms, False),
            ("Account IDs (tuy chon)", self.zernio_account_ids, False),
            ("Profile ID (tuy chon)", self.zernio_profile_id, False),
            ("Tieu de rieng", self.zernio_custom_title, False),
            ("Bat dau sau phut", self.zernio_start_after, False),
            ("Random min phut", self.zernio_min_gap, False),
            ("Random max phut", self.zernio_max_gap, False),
            ("Toi da video moi lan", self.zernio_max_videos, False),
        ]
        for row, (label, variable, secret) in enumerate(fields):
            ttk.Label(form, text=label).grid(row=row, column=0, sticky="w")
            ttk.Entry(form, textvariable=variable, show="*" if secret else "").grid(row=row, column=1, sticky="ew", padx=(12, 0), pady=3)
        form.columnconfigure(1, weight=1)
        actions = ttk.Frame(action_section, padding=(12, 0, 12, 12))
        actions.pack(fill=X)
        ttk.Button(actions, text="Dang tat ca qua Zernio (lich random)", command=self.upload_zernio_all, style="Accent.TButton").pack(fill=X)
        ttk.Button(actions, text="Dang video dang chon qua Zernio", command=self.upload_zernio_selected).pack(fill=X, pady=(8, 0))
        ttk.Button(actions, text="Dung tien trinh", command=lambda: self.stop_process("zernio")).pack(fill=X, pady=(8, 0))

        note = ttk.LabelFrame(right_panel, text="Ghi chu")
        note.pack(fill=X, pady=(14, 0))
        ttk.Label(note, text="Ket noi account trong Zernio Dashboard truoc. Co the nhap nhieu API key, cach nhau bang dau phay, de gom account tu nhieu tai khoan Zernio. Video qua 90 giay se tu cat ban Instagram 90s; qua 10 phut se tu cat ban TikTok 9m59s. Video qua 3 phut se dang YouTube ban day du va them Short 2m59s khung doc sau 5 phut.", style="Subtle.TLabel", wraplength=360, justify="left").pack(fill=X, padx=12, pady=12)
        log_section = ttk.LabelFrame(right_panel, text="Log Zernio")
        log_section.pack(fill=BOTH, expand=True, pady=(14, 0))
        self.zernio_log_text = ScrolledText(log_section, height=14, wrap="word", font=("Segoe UI", 9), state="disabled")
        self.zernio_log_text.pack(fill=BOTH, expand=True, padx=10, pady=10)

    def _build_download_tab(self, parent: ttk.Frame) -> None:
        body = ttk.PanedWindow(parent, orient="horizontal")
        body.pack(fill=BOTH, expand=True)

        left_panel = ttk.Frame(body, padding=(0, 0, 12, 0))
        right_panel = ttk.Frame(body, padding=(12, 0, 0, 0))
        body.add(left_panel, weight=3)
        body.add(right_panel, weight=2)

        url_section = ttk.LabelFrame(left_panel, text="Danh sách link YouTube/Facebook/TikTok")
        url_section.pack(fill=BOTH, expand=True)
        self.url_text = ScrolledText(url_section, height=18, wrap="word", font=("Segoe UI", 10), undo=True)
        self.url_text.pack(fill=BOTH, expand=True, padx=10, pady=10)

        option_section = ttk.LabelFrame(left_panel, text="Cấu hình tải")
        option_section.pack(fill=X, pady=(14, 0))
        form = ttk.Frame(option_section, padding=12)
        form.pack(fill=X)

        ttk.Label(form, text="Thư mục lưu").grid(row=0, column=0, sticky="w")
        ttk.Entry(form, textvariable=self.download_dir).grid(row=0, column=1, sticky="ew", padx=(12, 8), pady=4)
        ttk.Button(form, text="Chọn", command=self.choose_download_dir).grid(row=0, column=2, sticky="ew", pady=4)

        ttk.Label(form, text="Định dạng").grid(row=1, column=0, sticky="w")
        ttk.Combobox(
            form,
            textvariable=self.download_format,
            values=("full_hd_1080", "youtube_profile", "tiktok_profile", "facebook_profile", "auto_with_audio", "best_mp4", "best", "audio_m4a"),
            state="readonly",
        ).grid(row=1, column=1, columnspan=2, sticky="ew", padx=(12, 0), pady=4)

        ttk.Label(form, text="Tên file mẫu").grid(row=2, column=0, sticky="w")
        ttk.Entry(form, textvariable=self.output_template).grid(row=2, column=1, columnspan=2, sticky="ew", padx=(12, 0), pady=4)

        ttk.Label(form, text="Lệnh thêm").grid(row=3, column=0, sticky="w")
        ttk.Entry(form, textvariable=self.extra_ytdlp_args).grid(row=3, column=1, columnspan=2, sticky="ew", padx=(12, 0), pady=4)

        ttk.Checkbutton(form, text="Tải cả playlist nếu link là playlist", variable=self.allow_playlist).grid(
            row=4, column=0, columnspan=3, sticky="w", pady=(8, 0)
        )
        form.columnconfigure(1, weight=1)

        action_section = ttk.LabelFrame(right_panel, text="Lệnh yt-dlp")
        action_section.pack(fill=X)
        actions = ttk.Frame(action_section, padding=12)
        actions.pack(fill=X)
        ttk.Button(actions, text="Tải video", command=self.download_urls, style="Accent.TButton").pack(fill=X)
        ttk.Button(actions, text="Mẫu tải profile YouTube", command=self.apply_youtube_profile_preset).pack(fill=X, pady=(8, 0))
        ttk.Button(actions, text="Mẫu tải profile TikTok", command=self.apply_tiktok_profile_preset).pack(fill=X, pady=(8, 0))
        ttk.Button(actions, text="Mẫu tải profile Facebook", command=self.apply_facebook_profile_preset).pack(fill=X, pady=(8, 0))
        ttk.Button(actions, text="Xem lệnh sẽ chạy", command=self.preview_ytdlp_command).pack(fill=X, pady=(8, 0))
        ttk.Button(actions, text="Lệnh cPanel/Linux TikTok", command=self.preview_cpanel_tiktok_command).pack(fill=X, pady=(8, 0))
        ttk.Button(actions, text="Mở thư mục lưu", command=self.open_download_folder).pack(fill=X, pady=(8, 0))
        ttk.Button(actions, text="Dừng tiến trình", command=lambda: self.stop_process("download")).pack(fill=X, pady=(8, 0))

        note = ttk.LabelFrame(right_panel, text="Gợi ý")
        note.pack(fill=X, pady=(14, 0))
        ttk.Label(
            note,
            text=(
                "Mỗi dòng nhập một link. Mặc định panel ưu tiên Full HD 1080p và lưu vào thư mục videos/. "
                "YouTube 1080p thường cần ffmpeg để ghép video với âm thanh. "
                "Với TikTok/Facebook profile, bấm nút mẫu tương ứng rồi dán link profile. Facebook sẽ dùng Chrome Facebook đã đăng nhập, "
                "tự quét tab Reels và Videos, đồng thời bỏ qua video đã tải bằng archive riêng. "
                "Sau khi tải xong, có thể upload tiếp bằng tab Upload YouTube. Với Facebook riêng tư, bạn có thể cần thêm cookies "
                "vào ô Lệnh thêm, ví dụ: --cookies cookies.txt"
            ),
            style="Subtle.TLabel",
            wraplength=360,
            justify="left",
        ).pack(fill=X, padx=12, pady=12)

        log_section = ttk.LabelFrame(right_panel, text="Log tải video")
        log_section.pack(fill=BOTH, expand=True, pady=(14, 0))
        self.download_log_text = ScrolledText(log_section, height=18, wrap="word", font=("Segoe UI", 9), state="disabled")
        self.download_log_text.pack(fill=BOTH, expand=True, padx=10, pady=10)

    def _build_video_section(self, parent: ttk.Frame) -> None:
        section = ttk.LabelFrame(parent, text="Video trong thư mục videos/")
        section.pack(fill=BOTH, expand=True)

        toolbar = ttk.Frame(section, padding=10)
        toolbar.pack(fill=X)
        ttk.Button(toolbar, text="Làm mới", command=self.refresh_videos).pack(side=LEFT)
        ttk.Button(toolbar, text="Thêm video", command=self.add_videos).pack(side=LEFT, padx=(8, 0))
        ttk.Button(toolbar, text="Chọn thư mục upload", command=self.choose_upload_dir).pack(side=LEFT, padx=(8, 0))
        ttk.Button(toolbar, text="Mở thư mục upload", command=self.open_videos_folder).pack(side=LEFT, padx=(8, 0))

        dir_row = ttk.Frame(section, padding=(10, 0, 10, 8))
        dir_row.pack(fill=X)
        ttk.Label(dir_row, text="Thư mục upload").pack(side=LEFT)
        ttk.Entry(dir_row, textvariable=self.upload_dir).pack(side=LEFT, fill=X, expand=True, padx=(12, 0))

        columns = ("name", "size", "modified")
        self.video_tree = ttk.Treeview(section, columns=columns, show="headings", selectmode="browse", height=12)
        self.video_tree.heading("name", text="Tên file")
        self.video_tree.heading("size", text="Dung lượng")
        self.video_tree.heading("modified", text="Sửa lần cuối")
        self.video_tree.column("name", minwidth=260, width=420, stretch=True)
        self.video_tree.column("size", minwidth=90, width=110, anchor="e", stretch=False)
        self.video_tree.column("modified", minwidth=140, width=170, stretch=False)
        self.video_tree.pack(fill=BOTH, expand=True, padx=10, pady=(0, 10))
        self.video_tree.bind("<<TreeviewSelect>>", self._on_video_selected)

    def _build_description_section(self, parent: ttk.Frame) -> None:
        section = ttk.LabelFrame(parent, text="Mô tả YouTube")
        section.pack(fill=BOTH, expand=True, pady=(14, 0))

        buttons = ttk.Frame(section, padding=10)
        buttons.pack(fill=X)
        ttk.Button(buttons, text="Lưu mô tả", command=self.save_description).pack(side=LEFT)
        ttk.Button(buttons, text="Tải lại", command=self.load_description).pack(side=LEFT, padx=(8, 0))

        self.description_text = ScrolledText(section, height=10, wrap="word", font=("Segoe UI", 10), undo=True)
        self.description_text.pack(fill=BOTH, expand=True, padx=10, pady=(0, 10))

        hashtag_form = ttk.Frame(section, padding=(10, 0, 10, 10))
        hashtag_form.pack(fill=X)
        ttk.Label(hashtag_form, text="Hashtag tiêu đề").grid(row=0, column=0, sticky="w")
        ttk.Entry(hashtag_form, textvariable=self.title_hashtags).grid(
            row=0, column=1, sticky="ew", padx=(12, 0), pady=3
        )
        ttk.Label(hashtag_form, text="Hashtag mô tả").grid(row=1, column=0, sticky="w")
        ttk.Entry(hashtag_form, textvariable=self.description_hashtags).grid(
            row=1, column=1, sticky="ew", padx=(12, 0), pady=3
        )
        ttk.Label(
            hashtag_form,
            text="Có thể nhập: nro sourcegame hso hoặc #nro #sourcegame #hso",
            style="Subtle.TLabel",
        ).grid(row=2, column=0, columnspan=2, sticky="w", pady=(3, 0))
        hashtag_form.columnconfigure(1, weight=1)

    def _build_action_section(self, parent: ttk.Frame) -> None:
        section = ttk.LabelFrame(parent, text="Điều khiển upload")
        section.pack(fill=X)

        form = ttk.Frame(section, padding=12)
        form.pack(fill=X)

        ttk.Label(form, text="Chế độ hiển thị").grid(row=0, column=0, sticky="w")
        ttk.Combobox(
            form,
            textvariable=self.visibility,
            values=("public", "unlisted", "private", "skip"),
            state="readonly",
            width=18,
        ).grid(row=0, column=1, sticky="ew", padx=(12, 0), pady=4)

        ttk.Label(form, text="Dành cho trẻ em").grid(row=1, column=0, sticky="w")
        ttk.Combobox(
            form,
            textvariable=self.made_for_kids,
            values=("no", "yes", "skip"),
            state="readonly",
            width=18,
        ).grid(row=1, column=1, sticky="ew", padx=(12, 0), pady=4)

        ttk.Label(form, text="Tiêu đề riêng").grid(row=2, column=0, sticky="w")
        ttk.Entry(form, textvariable=self.custom_title).grid(row=2, column=1, sticky="ew", padx=(12, 0), pady=4)

        ttk.Label(form, text="Nghỉ giữa video").grid(row=3, column=0, sticky="w")
        ttk.Entry(form, textvariable=self.delay, width=20).grid(row=3, column=1, sticky="ew", padx=(12, 0), pady=4)

        ttk.Checkbutton(form, text="Kết nối Chrome đã đăng nhập (--attach)", variable=self.attach).grid(
            row=4, column=0, columnspan=2, sticky="w", pady=(8, 2)
        )
        form.columnconfigure(1, weight=1)

        actions = ttk.Frame(section, padding=(12, 0, 12, 12))
        actions.pack(fill=X)
        ttk.Button(actions, text="Mở Chrome đăng nhập", command=self.run_login, style="Accent.TButton").pack(fill=X)
        ttk.Button(actions, text="Upload tất cả video", command=self.upload_all, style="Accent.TButton").pack(fill=X, pady=(8, 0))
        ttk.Button(actions, text="Upload video đang chọn", command=self.upload_selected).pack(fill=X, pady=(8, 0))
        ttk.Button(actions, text="Dừng tiến trình", command=lambda: self.stop_process("youtube")).pack(fill=X, pady=(8, 0))

    def _build_log_section(self, parent: ttk.Frame) -> None:
        section = ttk.LabelFrame(parent, text="Log")
        section.pack(fill=BOTH, expand=True, pady=(14, 0))
        self.log_text = ScrolledText(section, height=18, wrap="word", font=("Segoe UI", 9), state="disabled")
        self.log_text.pack(fill=BOTH, expand=True, padx=10, pady=10)

    def refresh_videos(self) -> None:
        upload_dir = Path(self.upload_dir.get())
        upload_dir.mkdir(parents=True, exist_ok=True)
        for item in self.video_tree.get_children():
            self.video_tree.delete(item)

        videos = sorted(
            (p for p in upload_dir.rglob("*") if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS),
            key=lambda p: str(p).lower(),
        )
        for video in videos:
            stat = video.stat()
            try:
                display_name = str(video.relative_to(upload_dir))
            except ValueError:
                display_name = video.name
            self.video_tree.insert("", END, iid=str(video), values=(display_name, self._format_size(stat.st_size), self._format_time(stat.st_mtime)))
        self.status.set(f"{len(videos)} video sẵn sàng")

    def add_videos(self) -> None:
        selected = filedialog.askopenfilenames(
            title="Chọn video",
            filetypes=(("Video files", "*.mp4 *.mov *.mkv *.avi *.webm *.m4v"), ("All files", "*.*")),
        )
        if not selected:
            return
        upload_dir = Path(self.upload_dir.get())
        upload_dir.mkdir(parents=True, exist_ok=True)
        copied = 0
        for source_text in selected:
            source = Path(source_text)
            target = upload_dir / source.name
            if source.resolve() == target.resolve():
                continue
            if target.exists():
                if not messagebox.askyesno("File đã tồn tại", f"Ghi đè file này?\n{target.name}"):
                    continue
            shutil.copy2(source, target)
            copied += 1
        self.refresh_videos()
        self._append_log(f"[PANEL] Đã thêm {copied} video vào thư mục upload.\n")

    def open_videos_folder(self) -> None:
        upload_dir = Path(self.upload_dir.get())
        upload_dir.mkdir(parents=True, exist_ok=True)
        subprocess.Popen(["explorer", str(upload_dir)])

    def choose_upload_dir(self) -> None:
        selected = filedialog.askdirectory(title="Chọn thư mục upload", initialdir=self.upload_dir.get())
        if selected:
            self.upload_dir.set(selected)
            self.refresh_videos()

    def refresh_tiktok_videos(self) -> None:
        upload_dir = Path(self.tiktok_upload_dir.get())
        upload_dir.mkdir(parents=True, exist_ok=True)
        for item in self.tiktok_video_tree.get_children():
            self.tiktok_video_tree.delete(item)

        videos = sorted(
            (p for p in upload_dir.rglob("*") if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS),
            key=lambda p: str(p).lower(),
        )
        for video in videos:
            stat = video.stat()
            try:
                display_name = str(video.relative_to(upload_dir))
            except ValueError:
                display_name = video.name
            self.tiktok_video_tree.insert(
                "",
                END,
                iid=str(video),
                values=(display_name, self._format_size(stat.st_size), self._format_time(stat.st_mtime)),
            )
        self.status.set(f"{len(videos)} video TikTok sẵn sàng")

    def open_tiktok_upload_folder(self) -> None:
        upload_dir = Path(self.tiktok_upload_dir.get())
        upload_dir.mkdir(parents=True, exist_ok=True)
        subprocess.Popen(["explorer", str(upload_dir)])

    def choose_tiktok_upload_dir(self) -> None:
        selected = filedialog.askdirectory(title="Chọn thư mục upload TikTok", initialdir=self.tiktok_upload_dir.get())
        if selected:
            self.tiktok_upload_dir.set(selected)
            self.refresh_tiktok_videos()

    def refresh_facebook_videos(self) -> None:
        upload_dir = Path(self.facebook_upload_dir.get())
        upload_dir.mkdir(parents=True, exist_ok=True)
        for item in self.facebook_video_tree.get_children():
            self.facebook_video_tree.delete(item)

        videos = sorted(
            (p for p in upload_dir.rglob("*") if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS),
            key=lambda p: str(p).lower(),
        )
        for video in videos:
            stat = video.stat()
            try:
                display_name = str(video.relative_to(upload_dir))
            except ValueError:
                display_name = video.name
            self.facebook_video_tree.insert(
                "",
                END,
                iid=str(video),
                values=(display_name, self._format_size(stat.st_size), self._format_time(stat.st_mtime)),
            )
        self.status.set(f"{len(videos)} video Facebook sẵn sàng")

    def open_facebook_upload_folder(self) -> None:
        upload_dir = Path(self.facebook_upload_dir.get())
        upload_dir.mkdir(parents=True, exist_ok=True)
        subprocess.Popen(["explorer", str(upload_dir)])

    def choose_facebook_upload_dir(self) -> None:
        selected = filedialog.askdirectory(title="Chọn thư mục upload Facebook", initialdir=self.facebook_upload_dir.get())
        if selected:
            self.facebook_upload_dir.set(selected)
            self.refresh_facebook_videos()

    def refresh_instagram_videos(self) -> None:
        upload_dir = Path(self.instagram_upload_dir.get())
        upload_dir.mkdir(parents=True, exist_ok=True)
        for item in self.instagram_video_tree.get_children():
            self.instagram_video_tree.delete(item)

        videos = sorted(
            (p for p in upload_dir.rglob("*") if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS),
            key=lambda p: str(p).lower(),
        )
        for video in videos:
            stat = video.stat()
            try:
                display_name = str(video.relative_to(upload_dir))
            except ValueError:
                display_name = video.name
            self.instagram_video_tree.insert(
                "",
                END,
                iid=str(video),
                values=(display_name, self._format_size(stat.st_size), self._format_time(stat.st_mtime)),
            )
        self.status.set(f"{len(videos)} video Instagram san sang")

    def open_instagram_upload_folder(self) -> None:
        upload_dir = Path(self.instagram_upload_dir.get())
        upload_dir.mkdir(parents=True, exist_ok=True)
        subprocess.Popen(["explorer", str(upload_dir)])

    def choose_instagram_upload_dir(self) -> None:
        selected = filedialog.askdirectory(title="Chon thu muc upload Instagram", initialdir=self.instagram_upload_dir.get())
        if selected:
            self.instagram_upload_dir.set(selected)
            self.refresh_instagram_videos()

    def refresh_ayrshare_videos(self) -> None:
        if not hasattr(self, "ayrshare_video_tree"):
            return
        upload_dir = Path(self.ayrshare_upload_dir.get())
        upload_dir.mkdir(parents=True, exist_ok=True)
        for item in self.ayrshare_video_tree.get_children():
            self.ayrshare_video_tree.delete(item)

        videos = sorted(
            (p for p in upload_dir.rglob("*") if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS),
            key=lambda p: str(p).lower(),
        )
        for video in videos:
            stat = video.stat()
            try:
                display_name = str(video.relative_to(upload_dir))
            except ValueError:
                display_name = video.name
            self.ayrshare_video_tree.insert(
                "",
                END,
                iid=str(video),
                values=(display_name, self._format_size(stat.st_size), self._format_time(stat.st_mtime)),
            )
        self.status.set(f"{len(videos)} video Ayrshare san sang")

    def open_ayrshare_upload_folder(self) -> None:
        upload_dir = Path(self.ayrshare_upload_dir.get())
        upload_dir.mkdir(parents=True, exist_ok=True)
        subprocess.Popen(["explorer", str(upload_dir)])

    def choose_ayrshare_upload_dir(self) -> None:
        selected = filedialog.askdirectory(title="Chon thu muc upload Ayrshare", initialdir=self.ayrshare_upload_dir.get())
        if selected:
            self.ayrshare_upload_dir.set(selected)
            self.refresh_ayrshare_videos()

    def refresh_zernio_videos(self) -> None:
        if not hasattr(self, "zernio_video_tree"):
            return
        upload_dir = Path(self.zernio_upload_dir.get())
        upload_dir.mkdir(parents=True, exist_ok=True)
        for item in self.zernio_video_tree.get_children():
            self.zernio_video_tree.delete(item)
        videos = sorted(
            (path for path in upload_dir.rglob("*") if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS),
            key=lambda path: str(path).lower(),
        )
        for video in videos:
            stat = video.stat()
            try:
                display_name = str(video.relative_to(upload_dir))
            except ValueError:
                display_name = video.name
            self.zernio_video_tree.insert("", END, iid=str(video), values=(display_name, self._format_size(stat.st_size), self._format_time(stat.st_mtime)))
        self.status.set(f"{len(videos)} video Zernio san sang")

    def open_zernio_upload_folder(self) -> None:
        upload_dir = Path(self.zernio_upload_dir.get())
        upload_dir.mkdir(parents=True, exist_ok=True)
        subprocess.Popen(["explorer", str(upload_dir)])

    def choose_zernio_upload_dir(self) -> None:
        selected = filedialog.askdirectory(title="Chon thu muc upload Zernio", initialdir=self.zernio_upload_dir.get())
        if selected:
            self.zernio_upload_dir.set(selected)
            self.refresh_zernio_videos()

    def choose_download_dir(self) -> None:
        selected = filedialog.askdirectory(title="Chọn thư mục lưu video", initialdir=self.download_dir.get())
        if selected:
            self.download_dir.set(selected)

    def open_download_folder(self) -> None:
        path = Path(self.download_dir.get())
        path.mkdir(parents=True, exist_ok=True)
        subprocess.Popen(["explorer", str(path)])

    def apply_tiktok_profile_preset(self) -> None:
        self.download_format.set("tiktok_profile")
        self.download_dir.set(str(TIKTOK_DOWNLOAD_DIR))
        self.upload_dir.set(str(TIKTOK_DOWNLOAD_DIR))
        self.tiktok_upload_dir.set(str(TIKTOK_DOWNLOAD_DIR))
        self.output_template.set("%(uploader)s/%(upload_date)s_%(id)s.%(ext)s")
        self.allow_playlist.set(True)
        self.extra_ytdlp_args.set("")
        current_text = self.url_text.get("1.0", END).strip()
        if not current_text:
            self.url_text.insert("1.0", "https://www.tiktok.com/@tamanmoingay2404\n")
        self._append_download_log(
            "\n[PANEL] Đã nạp mẫu TikTok profile: lưu vào TikTok_Channel, dùng archive_video.txt, nghỉ 3-8 giây.\n"
        )

    def apply_youtube_profile_preset(self) -> None:
        self.download_format.set("youtube_profile")
        self.download_dir.set(str(VIDEOS_DIR))
        self.upload_dir.set(str(VIDEOS_DIR))
        self.output_template.set("%(title).180s #%(uploader).50s.%(ext)s")
        self.allow_playlist.set(True)
        self.extra_ytdlp_args.set("")
        current_text = self.url_text.get("1.0", END).strip()
        if not current_text:
            self.url_text.insert("1.0", "https://www.youtube.com/@username/videos\n")
        self._append_download_log(
            "\n[PANEL] Đã nạp mẫu YouTube profile: tối đa 1080p có tiếng và dùng archive riêng.\n"
        )

    def apply_facebook_profile_preset(self) -> None:
        self.download_format.set("facebook_profile")
        self.download_dir.set(str(FACEBOOK_DOWNLOAD_DIR))
        self.facebook_upload_dir.set(str(FACEBOOK_DOWNLOAD_DIR))
        self.output_template.set("%(uploader)s/%(upload_date)s_%(id)s.%(ext)s")
        self.allow_playlist.set(True)
        self.extra_ytdlp_args.set("")
        current_text = self.url_text.get("1.0", END).strip()
        if not current_text:
            self.url_text.insert("1.0", "https://www.facebook.com/username\n")
        self._append_download_log(
            "\n[PANEL] Đã nạp mẫu Facebook profile: dùng Chrome Facebook, quét Reels/Videos và archive riêng.\n"
        )

    def load_description(self) -> None:
        DESCRIPTION_FILE.touch(exist_ok=True)
        text = DESCRIPTION_FILE.read_text(encoding="utf-8-sig")
        self.description_text.delete("1.0", END)
        self.description_text.insert("1.0", text)
        self._append_log("[PANEL] Đã tải mô tả YouTube.\n")

    def load_tiktok_description(self) -> None:
        self._ensure_platform_description(TIKTOK_DESCRIPTION_FILE)
        text = TIKTOK_DESCRIPTION_FILE.read_text(encoding="utf-8-sig")
        self.tiktok_description_text.delete("1.0", END)
        self.tiktok_description_text.insert("1.0", text)
        self._append_tiktok_log("[PANEL] Đã tải mô tả TikTok.\n")

    def load_facebook_description(self) -> None:
        self._ensure_platform_description(FACEBOOK_DESCRIPTION_FILE)
        text = FACEBOOK_DESCRIPTION_FILE.read_text(encoding="utf-8-sig")
        self.facebook_description_text.delete("1.0", END)
        self.facebook_description_text.insert("1.0", text)
        self._append_facebook_log("[PANEL] Đã tải mô tả Facebook.\n")

    def load_instagram_description(self) -> None:
        self._ensure_platform_description(INSTAGRAM_DESCRIPTION_FILE)
        text = INSTAGRAM_DESCRIPTION_FILE.read_text(encoding="utf-8-sig")
        self.instagram_description_text.delete("1.0", END)
        self.instagram_description_text.insert("1.0", text)
        self._append_instagram_log("[PANEL] Da tai mo ta Instagram.\n")

    def _ensure_platform_description(self, path: Path) -> None:
        if path.exists():
            return
        fallback = ""
        if DESCRIPTION_FILE.exists():
            fallback = DESCRIPTION_FILE.read_text(encoding="utf-8-sig")
        path.write_text(fallback, encoding="utf-8")

    def load_hashtags(self) -> None:
        TITLE_HASHTAGS_FILE.touch(exist_ok=True)
        DESCRIPTION_HASHTAGS_FILE.touch(exist_ok=True)
        self.title_hashtags.set(TITLE_HASHTAGS_FILE.read_text(encoding="utf-8-sig").strip())
        self.description_hashtags.set(DESCRIPTION_HASHTAGS_FILE.read_text(encoding="utf-8-sig").strip())

    def load_panel_settings(self) -> None:
        if not PANEL_SETTINGS_FILE.exists():
            return
        try:
            data = json.loads(PANEL_SETTINGS_FILE.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"[PANEL] Không đọc được panel_settings.json: {exc}")
            return
        facebook = data.get("facebook", {})
        self.facebook_upload_dir.set(facebook.get("upload_dir", self.facebook_upload_dir.get()))
        self.facebook_mode.set(facebook.get("mode", self.facebook_mode.get()))
        self.facebook_target_url.set(facebook.get("target_url", self.facebook_target_url.get()))
        self.facebook_page_id.set(facebook.get("page_id", self.facebook_page_id.get()))
        self.facebook_page_token.set(facebook.get("page_token", self.facebook_page_token.get()))
        self.facebook_api_version.set(facebook.get("api_version", self.facebook_api_version.get()))
        self.facebook_delay.set(str(facebook.get("delay", self.facebook_delay.get())))
        self.facebook_attach.set(bool(facebook.get("attach", self.facebook_attach.get())))
        self.facebook_custom_title.set(facebook.get("custom_title", self.facebook_custom_title.get()))
        instagram = data.get("instagram", {})
        self.instagram_upload_dir.set(instagram.get("upload_dir", self.instagram_upload_dir.get()))
        self.instagram_delay.set(str(instagram.get("delay", self.instagram_delay.get())))
        self.instagram_attach.set(bool(instagram.get("attach", self.instagram_attach.get())))
        self.instagram_custom_title.set(instagram.get("custom_title", self.instagram_custom_title.get()))
        ayrshare = data.get("ayrshare", {})
        self.ayrshare_upload_dir.set(ayrshare.get("upload_dir", self.ayrshare_upload_dir.get()))
        self.ayrshare_api_key.set(ayrshare.get("api_key", self.ayrshare_api_key.get()))
        self.ayrshare_platforms.set(ayrshare.get("platforms", self.ayrshare_platforms.get()))
        self.ayrshare_custom_title.set(ayrshare.get("custom_title", self.ayrshare_custom_title.get()))
        self.ayrshare_start_after.set(str(ayrshare.get("start_after_minutes", self.ayrshare_start_after.get())))
        self.ayrshare_min_gap.set(str(ayrshare.get("min_gap_minutes", self.ayrshare_min_gap.get())))
        self.ayrshare_max_gap.set(str(ayrshare.get("max_gap_minutes", self.ayrshare_max_gap.get())))
        self.ayrshare_max_videos.set(str(ayrshare.get("max_videos", self.ayrshare_max_videos.get())))
        zernio = data.get("zernio", {})
        self.zernio_upload_dir.set(zernio.get("upload_dir", self.zernio_upload_dir.get()))
        self.zernio_api_key.set(zernio.get("api_key", self.zernio_api_key.get()))
        self.zernio_platforms.set(zernio.get("platforms", self.zernio_platforms.get()))
        self.zernio_account_ids.set(zernio.get("account_ids", self.zernio_account_ids.get()))
        self.zernio_profile_id.set(zernio.get("profile_id", self.zernio_profile_id.get()))
        self.zernio_custom_title.set(zernio.get("custom_title", self.zernio_custom_title.get()))
        self.zernio_start_after.set(str(zernio.get("start_after_minutes", self.zernio_start_after.get())))
        self.zernio_min_gap.set(str(zernio.get("min_gap_minutes", self.zernio_min_gap.get())))
        self.zernio_max_gap.set(str(zernio.get("max_gap_minutes", self.zernio_max_gap.get())))
        self.zernio_max_videos.set(str(zernio.get("max_videos", self.zernio_max_videos.get())))
        download = data.get("download", {})
        self.download_dir.set(download.get("download_dir", self.download_dir.get()))
        self.download_format.set(download.get("format", self.download_format.get()))
        self.output_template.set(download.get("output_template", self.output_template.get()))
        self.allow_playlist.set(bool(download.get("allow_playlist", self.allow_playlist.get())))
        self.extra_ytdlp_args.set(download.get("extra_args", self.extra_ytdlp_args.get()))

    def save_panel_settings(self) -> None:
        data = {}
        if PANEL_SETTINGS_FILE.exists():
            try:
                data = json.loads(PANEL_SETTINGS_FILE.read_text(encoding="utf-8"))
            except Exception:
                data = {}
        data["facebook"] = {
            "upload_dir": self.facebook_upload_dir.get().strip(),
            "mode": self.facebook_mode.get().strip(),
            "target_url": self.facebook_target_url.get().strip(),
            "page_id": self.facebook_page_id.get().strip(),
            "page_token": self.facebook_page_token.get().strip(),
            "api_version": self.facebook_api_version.get().strip(),
            "delay": self.facebook_delay.get().strip(),
            "attach": self.facebook_attach.get(),
            "custom_title": self.facebook_custom_title.get().strip(),
        }
        data["instagram"] = {
            "upload_dir": self.instagram_upload_dir.get().strip(),
            "delay": self.instagram_delay.get().strip(),
            "attach": self.instagram_attach.get(),
            "custom_title": self.instagram_custom_title.get().strip(),
        }
        data["ayrshare"] = {
            "upload_dir": self.ayrshare_upload_dir.get().strip(),
            "api_key": self.ayrshare_api_key.get().strip(),
            "platforms": self.ayrshare_platforms.get().strip(),
            "custom_title": self.ayrshare_custom_title.get().strip(),
            "start_after_minutes": self.ayrshare_start_after.get().strip(),
            "min_gap_minutes": self.ayrshare_min_gap.get().strip(),
            "max_gap_minutes": self.ayrshare_max_gap.get().strip(),
            "max_videos": self.ayrshare_max_videos.get().strip(),
        }
        data["zernio"] = {
            "upload_dir": self.zernio_upload_dir.get().strip(),
            "api_key": self.zernio_api_key.get().strip(),
            "platforms": self.zernio_platforms.get().strip(),
            "account_ids": self.zernio_account_ids.get().strip(),
            "profile_id": self.zernio_profile_id.get().strip(),
            "custom_title": self.zernio_custom_title.get().strip(),
            "start_after_minutes": self.zernio_start_after.get().strip(),
            "min_gap_minutes": self.zernio_min_gap.get().strip(),
            "max_gap_minutes": self.zernio_max_gap.get().strip(),
            "max_videos": self.zernio_max_videos.get().strip(),
        }
        data["download"] = {
            "download_dir": self.download_dir.get().strip(),
            "format": self.download_format.get().strip(),
            "output_template": self.output_template.get().strip(),
            "allow_playlist": self.allow_playlist.get(),
            "extra_args": self.extra_ytdlp_args.get().strip(),
        }
        PANEL_SETTINGS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def save_description(self) -> None:
        text = self.description_text.get("1.0", END).rstrip() + "\n"
        DESCRIPTION_FILE.write_text(text, encoding="utf-8")
        TITLE_HASHTAGS_FILE.write_text(self.title_hashtags.get().strip() + "\n", encoding="utf-8")
        DESCRIPTION_HASHTAGS_FILE.write_text(self.description_hashtags.get().strip() + "\n", encoding="utf-8")
        self._append_log("[PANEL] Đã lưu default_description.txt cho YouTube.\n")

    def save_tiktok_description(self) -> None:
        text = self.tiktok_description_text.get("1.0", END).rstrip() + "\n"
        TIKTOK_DESCRIPTION_FILE.write_text(text, encoding="utf-8")
        self._append_tiktok_log("[PANEL] Đã lưu tiktok_description.txt.\n")

    def save_facebook_description(self) -> None:
        text = self.facebook_description_text.get("1.0", END).rstrip() + "\n"
        FACEBOOK_DESCRIPTION_FILE.write_text(text, encoding="utf-8")
        self._append_facebook_log("[PANEL] Đã lưu facebook_description.txt.\n")

    def save_instagram_description(self) -> None:
        text = self.instagram_description_text.get("1.0", END).rstrip() + "\n"
        INSTAGRAM_DESCRIPTION_FILE.write_text(text, encoding="utf-8")
        self._append_instagram_log("[PANEL] Da luu instagram_description.txt.\n")

    def _append_hashtag_args(self, cmd: list[str]) -> None:
        custom_title = self.custom_title.get().strip()
        title_tags = self.title_hashtags.get().strip()
        description_tags = self.description_hashtags.get().strip()
        if custom_title:
            cmd.extend(["--title", custom_title])
        if title_tags:
            cmd.extend(["--title-hashtags", title_tags])
        if description_tags:
            cmd.extend(["--description-hashtags", description_tags])

    @staticmethod
    def _script_cmd(script_path: Path) -> list[str]:
        if getattr(sys, "frozen", False):
            return [sys.executable, "--run-script", str(script_path)]
        return [sys.executable, "-u", str(script_path)]

    def run_login(self) -> None:
        self.save_description()
        cmd = self._script_cmd(MAIN_FILE) + ["--login", "--no-wait-login"]
        self._append_chrome_profile_args(cmd, YOUTUBE_PROFILE_DIR, YOUTUBE_DEBUG_PORT)
        self._run_command(cmd, "Đang mở Chrome để đăng nhập...", "youtube")

    def upload_all(self) -> None:
        self.save_description()
        cmd = self._script_cmd(MAIN_FILE)
        self._append_chrome_profile_args(cmd, YOUTUBE_PROFILE_DIR, YOUTUBE_DEBUG_PORT)
        if self.attach.get():
            cmd.append("--attach")
        cmd.extend(["--all", "--video-dir", self.upload_dir.get(), "--visibility", self.visibility.get(), "--made-for-kids", self.made_for_kids.get()])
        cmd.extend(["--description-file", str(DESCRIPTION_FILE), "--delay", self._safe_delay(), "--yes"])
        self._append_hashtag_args(cmd)
        self._run_command(cmd, "Đang upload tất cả video...", "youtube")

    def upload_selected(self) -> None:
        selected = self.video_tree.selection()
        if not selected:
            messagebox.showinfo("Chưa chọn video", "Hãy chọn một video trong danh sách trước.")
            return
        self.save_description()
        video_path = selected[0]
        cmd = self._script_cmd(MAIN_FILE)
        self._append_chrome_profile_args(cmd, YOUTUBE_PROFILE_DIR, YOUTUBE_DEBUG_PORT)
        if self.attach.get():
            cmd.append("--attach")
        cmd.extend(["--video", video_path, "--visibility", self.visibility.get(), "--made-for-kids", self.made_for_kids.get()])
        cmd.extend(["--description-file", str(DESCRIPTION_FILE), "--delay", self._safe_delay(), "--yes"])
        self._append_hashtag_args(cmd)
        self._run_command(cmd, f"Đang upload {Path(video_path).name}...", "youtube")

    def run_tiktok_login(self) -> None:
        cmd = self._script_cmd(TIKTOK_UPLOAD_FILE) + ["--login"]
        self._append_chrome_profile_args(cmd, TIKTOK_PROFILE_DIR, TIKTOK_DEBUG_PORT)
        self._run_command(cmd, "Đang mở TikTok để đăng nhập...", "tiktok")

    def upload_tiktok_all(self) -> None:
        self.save_tiktok_description()
        cmd = self._script_cmd(TIKTOK_UPLOAD_FILE)
        self._append_chrome_profile_args(cmd, TIKTOK_PROFILE_DIR, TIKTOK_DEBUG_PORT)
        if self.tiktok_attach.get():
            cmd.append("--attach")
        cmd.extend(
            [
                "--all",
                "--video-dir",
                self.tiktok_upload_dir.get(),
                "--description-file",
                str(TIKTOK_DESCRIPTION_FILE),
                "--delay",
                self._safe_tiktok_delay(),
                "--yes",
            ]
        )
        self._append_tiktok_title_args(cmd)
        self._run_command(cmd, "Đang upload tất cả video lên TikTok...", "tiktok")

    def upload_tiktok_selected(self) -> None:
        selected = self.tiktok_video_tree.selection()
        if not selected:
            messagebox.showinfo("Chưa chọn video", "Hãy chọn một video trong danh sách TikTok trước.")
            return
        self.save_tiktok_description()
        video_path = selected[0]
        cmd = self._script_cmd(TIKTOK_UPLOAD_FILE)
        self._append_chrome_profile_args(cmd, TIKTOK_PROFILE_DIR, TIKTOK_DEBUG_PORT)
        if self.tiktok_attach.get():
            cmd.append("--attach")
        cmd.extend(
            [
                "--video",
                video_path,
                "--description-file",
                str(TIKTOK_DESCRIPTION_FILE),
                "--delay",
                self._safe_tiktok_delay(),
                "--yes",
            ]
        )
        self._append_tiktok_title_args(cmd)
        self._run_command(cmd, f"Đang upload TikTok {Path(video_path).name}...", "tiktok")

    def _append_tiktok_title_args(self, cmd: list[str]) -> None:
        custom_title = self.tiktok_custom_title.get().strip()
        if custom_title:
            cmd.extend(["--title", custom_title])

    def run_instagram_login(self) -> None:
        self.save_panel_settings()
        cmd = self._script_cmd(INSTAGRAM_UPLOAD_FILE) + ["--login"]
        self._append_chrome_profile_args(cmd, INSTAGRAM_PROFILE_DIR, INSTAGRAM_DEBUG_PORT)
        self._run_command(cmd, "Dang mo Instagram de dang nhap...", "instagram")

    def upload_instagram_all(self) -> None:
        self.save_panel_settings()
        self.save_instagram_description()
        cmd = self._script_cmd(INSTAGRAM_UPLOAD_FILE)
        self._append_chrome_profile_args(cmd, INSTAGRAM_PROFILE_DIR, INSTAGRAM_DEBUG_PORT)
        if self.instagram_attach.get():
            cmd.append("--attach")
        cmd.extend(
            [
                "--all",
                "--video-dir",
                self.instagram_upload_dir.get(),
                "--description-file",
                str(INSTAGRAM_DESCRIPTION_FILE),
                "--delay",
                self._safe_instagram_delay(),
                "--yes",
            ]
        )
        self._append_instagram_title_args(cmd)
        self._run_command(cmd, "Dang upload tat ca video len Instagram...", "instagram")

    def upload_instagram_selected(self) -> None:
        selected = self.instagram_video_tree.selection()
        if not selected:
            messagebox.showinfo("Chua chon video", "Hay chon mot video trong danh sach Instagram truoc.")
            return
        self.save_panel_settings()
        self.save_instagram_description()
        video_path = selected[0]
        cmd = self._script_cmd(INSTAGRAM_UPLOAD_FILE)
        self._append_chrome_profile_args(cmd, INSTAGRAM_PROFILE_DIR, INSTAGRAM_DEBUG_PORT)
        if self.instagram_attach.get():
            cmd.append("--attach")
        cmd.extend(
            [
                "--video",
                video_path,
                "--description-file",
                str(INSTAGRAM_DESCRIPTION_FILE),
                "--delay",
                self._safe_instagram_delay(),
                "--yes",
            ]
        )
        self._append_instagram_title_args(cmd)
        self._run_command(cmd, f"Dang upload Instagram {Path(video_path).name}...", "instagram")

    def _append_instagram_title_args(self, cmd: list[str]) -> None:
        custom_title = self.instagram_custom_title.get().strip()
        if custom_title:
            cmd.extend(["--title", custom_title])

    def upload_ayrshare_all(self) -> None:
        if not self._validate_ayrshare_config():
            return
        self.save_panel_settings()
        self.save_description()
        cmd = self._build_ayrshare_command(all_videos=True)
        self._run_command(cmd, "Dang hen lich tat ca video qua Ayrshare...", "ayrshare")

    def upload_ayrshare_selected(self) -> None:
        selected = self.ayrshare_video_tree.selection()
        if not selected:
            messagebox.showinfo("Chua chon video", "Hay chon mot video trong danh sach Ayrshare truoc.")
            return
        if not self._validate_ayrshare_config():
            return
        self.save_panel_settings()
        self.save_description()
        cmd = self._build_ayrshare_command(all_videos=False, video=selected[0])
        self._run_command(cmd, f"Dang hen lich Ayrshare {Path(selected[0]).name}...", "ayrshare")

    def _build_ayrshare_command(self, *, all_videos: bool, video: str | None = None) -> list[str]:
        cmd = self._script_cmd(AYRSHARE_UPLOAD_FILE)
        if all_videos:
            cmd.extend(["--all", "--video-dir", self.ayrshare_upload_dir.get()])
        else:
            cmd.extend(["--video", str(video or "")])
        cmd.extend(
            [
                "--description-file",
                str(DESCRIPTION_FILE),
                "--api-key",
                self.ayrshare_api_key.get().strip(),
                "--platforms",
                self.ayrshare_platforms.get().strip() or "facebook,instagram,tiktok,youtube",
                "--start-after-minutes",
                self._safe_int_text(self.ayrshare_start_after, 30),
                "--min-gap-minutes",
                self._safe_int_text(self.ayrshare_min_gap, 60),
                "--max-gap-minutes",
                self._safe_int_text(self.ayrshare_max_gap, 180),
                "--max-videos",
                self._safe_int_text(self.ayrshare_max_videos, 3),
            ]
        )
        if self.ayrshare_custom_title.get().strip():
            cmd.extend(["--title", self.ayrshare_custom_title.get().strip()])
        return cmd

    def _validate_ayrshare_config(self) -> bool:
        if not self.ayrshare_api_key.get().strip():
            messagebox.showinfo("Thieu Ayrshare API key", "Hay nhap API key lay trong Ayrshare Dashboard.")
            return False
        return True

    def upload_zernio_all(self) -> None:
        if not self._validate_zernio_config():
            return
        self.save_panel_settings()
        self.save_description()
        self._run_command(self._build_zernio_command(all_videos=True), "Dang hen lich tat ca video qua Zernio...", "zernio")

    def upload_zernio_selected(self) -> None:
        selected = self.zernio_video_tree.selection()
        if not selected:
            messagebox.showinfo("Chua chon video", "Hay chon mot video trong danh sach Zernio truoc.")
            return
        if not self._validate_zernio_config():
            return
        self.save_panel_settings()
        self.save_description()
        self._run_command(self._build_zernio_command(all_videos=False, video=selected[0]), f"Dang hen lich Zernio {Path(selected[0]).name}...", "zernio")

    def _build_zernio_command(self, *, all_videos: bool, video: str | None = None) -> list[str]:
        cmd = self._script_cmd(ZERNIO_UPLOAD_FILE)
        if all_videos:
            cmd.extend(["--all", "--video-dir", self.zernio_upload_dir.get()])
        else:
            cmd.extend(["--video", str(video or "")])
        cmd.extend([
            "--description-file", str(DESCRIPTION_FILE),
            "--api-key", self.zernio_api_key.get().strip(),
            "--platforms", self.zernio_platforms.get().strip() or "facebook,instagram,tiktok,youtube",
            "--start-after-minutes", self._safe_int_text(self.zernio_start_after, 30),
            "--min-gap-minutes", self._safe_int_text(self.zernio_min_gap, 60),
            "--max-gap-minutes", self._safe_int_text(self.zernio_max_gap, 180),
            "--max-videos", self._safe_int_text(self.zernio_max_videos, 3),
        ])
        if self.zernio_account_ids.get().strip():
            cmd.extend(["--account-ids", self.zernio_account_ids.get().strip()])
        if self.zernio_profile_id.get().strip():
            cmd.extend(["--profile-id", self.zernio_profile_id.get().strip()])
        if self.zernio_custom_title.get().strip():
            cmd.extend(["--title", self.zernio_custom_title.get().strip()])
        return cmd

    def _validate_zernio_config(self) -> bool:
        if not self.zernio_api_key.get().strip():
            messagebox.showinfo("Thieu Zernio API key", "Hay nhap mot hoac nhieu API key lay trong Zernio Settings > API Keys.")
            return False
        return True

    def run_facebook_login(self) -> None:
        self.save_panel_settings()
        target_url = self.facebook_target_url.get().strip() or "https://www.facebook.com"
        cmd = self._script_cmd(FACEBOOK_UPLOAD_FILE) + ["--login", "--target-url", target_url]
        self._append_chrome_profile_args(cmd, FACEBOOK_PROFILE_DIR, FACEBOOK_DEBUG_PORT)
        self._run_command(cmd, "Đang mở Facebook để đăng nhập...", "facebook")

    def upload_facebook_all(self) -> None:
        if not self._validate_facebook_config():
            return
        self.save_panel_settings()
        self.save_facebook_description()
        cmd = self._script_cmd(FACEBOOK_UPLOAD_FILE)
        self._append_chrome_profile_args(cmd, FACEBOOK_PROFILE_DIR, FACEBOOK_DEBUG_PORT)
        self._append_facebook_mode_args(cmd)
        cmd.extend(
            [
                "--all",
                "--video-dir",
                self.facebook_upload_dir.get(),
                "--description-file",
                str(FACEBOOK_DESCRIPTION_FILE),
                "--delay",
                self._safe_facebook_delay(),
                "--yes",
            ]
        )
        self._append_facebook_title_args(cmd)
        self._run_command(cmd, "Đang upload tất cả video lên Facebook...", "facebook")

    def upload_facebook_selected(self) -> None:
        selected = self.facebook_video_tree.selection()
        if not selected:
            messagebox.showinfo("Chưa chọn video", "Hãy chọn một video trong danh sách Facebook trước.")
            return
        if not self._validate_facebook_config():
            return
        self.save_panel_settings()
        self.save_facebook_description()
        video_path = selected[0]
        cmd = self._script_cmd(FACEBOOK_UPLOAD_FILE)
        self._append_chrome_profile_args(cmd, FACEBOOK_PROFILE_DIR, FACEBOOK_DEBUG_PORT)
        self._append_facebook_mode_args(cmd)
        cmd.extend(
            [
                "--video",
                video_path,
                "--description-file",
                str(FACEBOOK_DESCRIPTION_FILE),
                "--delay",
                self._safe_facebook_delay(),
                "--yes",
            ]
        )
        self._append_facebook_title_args(cmd)
        self._run_command(cmd, f"Đang upload Facebook {Path(video_path).name}...", "facebook")

    def _append_facebook_title_args(self, cmd: list[str]) -> None:
        custom_title = self.facebook_custom_title.get().strip()
        if custom_title:
            cmd.extend(["--title", custom_title])

    @staticmethod
    def _append_chrome_profile_args(cmd: list[str], profile_dir: Path, debug_port: int) -> None:
        cmd.extend(["--profile-dir", str(profile_dir), "--debug-port", str(debug_port)])

    def _append_facebook_mode_args(self, cmd: list[str]) -> None:
        mode = self.facebook_mode.get().strip() or "reels-api"
        cmd.extend(["--mode", mode])
        if mode == "browser":
            if self.facebook_attach.get():
                cmd.append("--attach")
            cmd.extend(["--target-url", self.facebook_target_url.get().strip() or "https://www.facebook.com"])
        else:
            cmd.extend(
                [
                    "--page-id",
                    self.facebook_page_id.get().strip(),
                    "--page-token",
                    self.facebook_page_token.get().strip(),
                    "--api-version",
                    self.facebook_api_version.get().strip() or "v23.0",
                ]
            )

    def _validate_facebook_config(self) -> bool:
        if self.facebook_mode.get() != "reels-api":
            return True
        if not self.facebook_page_id.get().strip() or not self.facebook_page_token.get().strip():
            messagebox.showinfo("Thiếu thông tin Facebook", "Chế độ reels-api cần Page ID và Page Access Token.")
            return False
        return True

    def stop_process(self, group: str | None = None) -> None:
        groups = [group] if group else sorted(self.active_groups | set(self.processes))
        stopped: list[str] = []
        for name in groups:
            process = self.processes.get(name)
            if process and process.poll() is None:
                process.terminate()
                stopped.append(name)
                self._append_group_log(name, "[PANEL] Da gui lenh dung tien trinh.\n")
        if stopped:
            self._update_status()
        else:
            self.status.set("Khong co tien trinh dang chay")
    def download_urls(self) -> None:
        urls = self._get_urls()
        if not urls:
            messagebox.showinfo("Chưa có link", "Hãy nhập mỗi link trên một dòng.")
            return
        if not YTDLP_FILE.exists():
            messagebox.showerror("Thiếu yt-dlp.exe", f"Không thấy file:\n{YTDLP_FILE}")
            return
        self.save_panel_settings()
        if self.download_format.get() in {"full_hd_1080", "youtube_profile", "tiktok_profile", "facebook_profile"} and not self._ffmpeg_available():
            messagebox.showwarning(
                "Thiếu ffmpeg",
                "Chế độ Full HD 1080p cần ffmpeg để ghép hình và tiếng.\n"
                "Hãy đặt ffmpeg.exe cùng thư mục với panel.py hoặc cài ffmpeg vào PATH.\n\n"
                "Panel vẫn sẽ chạy, nhưng nếu thiếu ffmpeg YouTube có thể chỉ tải được 360p/720p có tiếng.",
            )
        cmd = self._build_ytdlp_command(urls)
        self._run_command(cmd, "Đang tải video...", "download")

    def preview_ytdlp_command(self) -> None:
        urls = self._get_urls() or ["https://example.com/video"]
        cmd = self._build_ytdlp_command(urls)
        self._append_download_log("\n[PANEL] Lệnh sẽ chạy:\n" + self._format_command(cmd) + "\n")

    def preview_cpanel_tiktok_command(self) -> None:
        urls = self._get_urls() or ["https://www.tiktok.com/@username"]
        url = urls[0]
        output_template = self.output_template.get().strip() or "%(uploader)s/%(upload_date)s_%(id)s.%(ext)s"
        command = (
            "python3 -m pip install -U yt-dlp\n"
            "mkdir -p TikTok_Channel\n"
            f"python3 -m yt_dlp --ignore-config {self._shell_quote(url)} \\\n"
            "  -f 'bv+ba/b[vcodec!=none][acodec!=none]' \\\n"
            "  -S 'res:1080' \\\n"
            "  --merge-output-format mp4 \\\n"
            "  --remux-video mp4 \\\n"
            "  -P TikTok_Channel \\\n"
            f"  -o {self._shell_quote(output_template)} \\\n"
            "  --download-archive archive_video.txt \\\n"
            "  --ignore-errors \\\n"
            "  --sleep-interval 3 --max-sleep-interval 8\n"
        )
        self._append_download_log(
            "\n[PANEL] Lệnh cPanel/Linux cho TikTok profile:\n"
            + command
            + "\n[PANEL] Gợi ý: chạy trong cPanel Terminal hoặc SSH tại thư mục tool.\n"
        )

    def _get_urls(self) -> list[str]:
        raw = self.url_text.get("1.0", END)
        urls: list[str] = []
        for line in raw.splitlines():
            text = line.strip()
            if not text:
                continue
            if text.startswith("##"):
                continue
            match = URL_RE.search(text)
            if match:
                urls.append(match.group(0).rstrip(".,);]"))
            else:
                urls.append(text)
        return urls

    def _build_ytdlp_command(self, urls: list[str]) -> list[str]:
        output_dir = Path(self.download_dir.get())
        output_dir.mkdir(parents=True, exist_ok=True)

        format_choice = self.download_format.get()

        if format_choice == "facebook_profile":
            cmd = self._script_cmd(FACEBOOK_PROFILE_DOWNLOAD_FILE) + [
                "--output-dir", str(output_dir),
                "--output-template", self.output_template.get().strip() or "%(uploader)s/%(upload_date)s_%(id)s.%(ext)s",
                "--archive-file", str(FACEBOOK_ARCHIVE_FILE),
                "--profile-dir", str(FACEBOOK_PROFILE_DIR),
                "--debug-port", str(FACEBOOK_DEBUG_PORT),
                "--yt-dlp", str(YTDLP_FILE),
                "--ffmpeg-dir", str(BASE_DIR),
            ]
            extra = self.extra_ytdlp_args.get().strip()
            if extra:
                cmd.append(f"--extra-args={extra}")
            cmd.extend(urls)
            return cmd

        cmd = [str(YTDLP_FILE), "--ignore-config", "--newline"]
        cmd.extend(["--ignore-errors", "-P", str(output_dir), "-o", self.output_template.get().strip()])
        if format_choice != "tiktok_profile" and any(
            "youtube.com/" in url.lower() or "youtu.be/" in url.lower() for url in urls
        ):
            cmd.extend(["--replace-in-metadata", "uploader", r"[^\w]", ""])
        if LOCAL_FFMPEG_FILE.exists():
            cmd.extend(["--ffmpeg-location", str(BASE_DIR)])
        if format_choice == "tiktok_profile":
            cmd.append("--yes-playlist")
        elif self.allow_playlist.get():
            cmd.append("--yes-playlist")
        else:
            cmd.append("--no-playlist")

        if format_choice in {"full_hd_1080", "youtube_profile"}:
            cmd.extend(full_hd_with_audio_args())
            if format_choice == "youtube_profile":
                cmd.extend(["--download-archive", str(YOUTUBE_ARCHIVE_FILE)])
        elif format_choice == "auto_with_audio":
            pass
        elif format_choice == "best_mp4":
            cmd.extend(["-f", "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/best", "--merge-output-format", "mp4"])
        elif format_choice == "best":
            cmd.extend(["-f", "bestvideo*+bestaudio/best"])
        elif format_choice == "audio_m4a":
            cmd.extend(["-f", "ba[ext=m4a]/bestaudio"])
        elif format_choice == "tiktok_profile":
            cmd.extend(
                [
                    "--download-archive",
                    str(TIKTOK_ARCHIVE_FILE),
                    "--sleep-interval",
                    "3",
                    "--max-sleep-interval",
                    "8",
                ]
            )
            cmd.extend(full_hd_with_audio_args())

        extra = self.extra_ytdlp_args.get().strip()
        if extra:
            try:
                cmd.extend(self._split_windows_args(extra))
            except ValueError as exc:
                self._append_download_log(f"[PANEL] Không tách được Lệnh thêm, bỏ qua. Lỗi: {exc}\n")
        cmd.extend(urls)
        return cmd

    @staticmethod
    def _ffmpeg_available() -> bool:
        return LOCAL_FFMPEG_FILE.exists() or shutil.which("ffmpeg") is not None

    def _run_command(self, cmd: list[str], status: str, group: str) -> None:
        process = self.processes.get(group)
        if group in self.active_groups or (process and process.poll() is None):
            messagebox.showwarning("Đang chạy", f"Nhóm {group} đang có tiến trình chạy. Hãy dừng hoặc đợi xong trước.")
            return
        command_text = self._format_command(cmd)
        if group == "ayrshare":
            try:
                AYRSHARE_LOG_FILE.write_text("", encoding="utf-8")
            except Exception:
                pass
        if group == "zernio":
            try:
                ZERNIO_LOG_FILE.write_text("", encoding="utf-8")
            except Exception:
                pass
        self._append_group_log(group, "\n[PANEL] Chạy lệnh:\n" + command_text + "\n\n")
        self.status.set(status)
        self.active_groups.add(group)
        self.workers[group] = threading.Thread(target=self._worker_run, args=(group, cmd), daemon=True)
        self.workers[group].start()
        self._update_status()

    def _worker_run(self, group: str, cmd: list[str]) -> None:
        process: subprocess.Popen[str] | None = None
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
            self.processes[group] = process
            assert process.stdout is not None
            for line in process.stdout:
                self.output_queue.put((group, "line", line))
            code = process.wait()
            self.output_queue.put((group, "line", f"\n[PANEL] Tiến trình kết thúc với mã {code}.\n"))
            self.output_queue.put((group, "done", code))
        except Exception as exc:
            self.output_queue.put((group, "line", f"\n[PANEL] Lỗi khi chạy lệnh: {exc}\n"))
            self.output_queue.put((group, "done", None))
        finally:
            current = self.processes.get(group)
            if process is not None and current is process:
                self.processes.pop(group, None)
            self.active_groups.discard(group)

    def _drain_output_queue(self) -> None:
        while True:
            try:
                group, kind, payload = self.output_queue.get_nowait()
            except queue.Empty:
                break
            if kind == "done":
                self.refresh_videos()
                self.refresh_tiktok_videos()
                self.refresh_facebook_videos()
                self.refresh_instagram_videos()
                self.refresh_ayrshare_videos()
                self.refresh_zernio_videos()
                self._update_status()
            else:
                self._append_group_log(group, str(payload))
        self.root.after(150, self._drain_output_queue)

    def _append_group_log(self, group: str, text: str) -> None:
        if group == "youtube":
            self._append_log(text)
        elif group == "tiktok":
            self._append_tiktok_log(text)
        elif group == "facebook":
            self._append_facebook_log(text)
        elif group == "instagram":
            self._append_instagram_log(text)
        elif group == "ayrshare":
            self._append_ayrshare_log(text)
        elif group == "zernio":
            self._append_zernio_log(text)
        elif group == "download":
            self._append_download_log(text)
        else:
            self._append_log(text)

    def _update_status(self) -> None:
        running = set(self.active_groups)
        running.update(name for name, process in self.processes.items() if process.poll() is None)
        if running:
            self.status.set("Đang chạy: " + ", ".join(sorted(running)))
        else:
            self.status.set("Sẵn sàng")
    def _append_log(self, text: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert(END, text)
        self.log_text.see(END)
        self.log_text.configure(state="disabled")

    def _append_download_log(self, text: str) -> None:
        if not hasattr(self, "download_log_text"):
            return
        self.download_log_text.configure(state="normal")
        self.download_log_text.insert(END, text)
        self.download_log_text.see(END)
        self.download_log_text.configure(state="disabled")

    def _append_tiktok_log(self, text: str) -> None:
        if not hasattr(self, "tiktok_log_text"):
            return
        self.tiktok_log_text.configure(state="normal")
        self.tiktok_log_text.insert(END, text)
        self.tiktok_log_text.see(END)
        self.tiktok_log_text.configure(state="disabled")

    def _append_facebook_log(self, text: str) -> None:
        if not hasattr(self, "facebook_log_text"):
            return
        self.facebook_log_text.configure(state="normal")
        self.facebook_log_text.insert(END, text)
        self.facebook_log_text.see(END)
        self.facebook_log_text.configure(state="disabled")

    def _append_instagram_log(self, text: str) -> None:
        if not hasattr(self, "instagram_log_text"):
            return
        self.instagram_log_text.configure(state="normal")
        self.instagram_log_text.insert(END, text)
        self.instagram_log_text.see(END)
        self.instagram_log_text.configure(state="disabled")

    def _append_ayrshare_log(self, text: str) -> None:
        if not hasattr(self, "ayrshare_log_text"):
            return
        self.ayrshare_log_text.configure(state="normal")
        self.ayrshare_log_text.insert(END, text)
        self.ayrshare_log_text.see(END)
        self.ayrshare_log_text.configure(state="disabled")

    def _append_zernio_log(self, text: str) -> None:
        if not hasattr(self, "zernio_log_text"):
            return
        self.zernio_log_text.configure(state="normal")
        self.zernio_log_text.insert(END, text)
        self.zernio_log_text.see(END)
        self.zernio_log_text.configure(state="disabled")

    @staticmethod
    def _format_command(cmd: list[str]) -> str:
        parts = list(cmd)
        for index, part in enumerate(parts[:-1]):
            if part == "--page-token":
                parts[index + 1] = "***"
            if part == "--api-key":
                parts[index + 1] = "***"
        return " ".join(f'"{part}"' if " " in part else part for part in parts)

    @staticmethod
    def _shell_quote(text: str) -> str:
        return "'" + text.replace("'", "'\"'\"'") + "'"

    @staticmethod
    def _split_windows_args(text: str) -> list[str]:
        import ctypes

        argc = ctypes.c_int()
        argv = ctypes.windll.shell32.CommandLineToArgvW(text, ctypes.byref(argc))
        if not argv:
            raise ValueError("CommandLineToArgvW failed")
        try:
            return [argv[index] for index in range(argc.value)]
        finally:
            ctypes.windll.kernel32.LocalFree(argv)

    def _on_video_selected(self, _event: object) -> None:
        selected = self.video_tree.selection()
        if selected:
            self.selected_video.set(selected[0])

    def _on_tiktok_video_selected(self, _event: object) -> None:
        selected = self.tiktok_video_tree.selection()
        if selected:
            self.tiktok_selected_video.set(selected[0])

    def _on_facebook_video_selected(self, _event: object) -> None:
        selected = self.facebook_video_tree.selection()
        if selected:
            self.facebook_selected_video.set(selected[0])

    def _on_instagram_video_selected(self, _event: object) -> None:
        selected = self.instagram_video_tree.selection()
        if selected:
            self.instagram_selected_video.set(selected[0])

    def _on_ayrshare_video_selected(self, _event: object) -> None:
        selected = self.ayrshare_video_tree.selection()
        if selected:
            self.ayrshare_selected_video.set(selected[0])

    def _on_zernio_video_selected(self, _event: object) -> None:
        selected = self.zernio_video_tree.selection()
        if selected:
            self.zernio_selected_video.set(selected[0])

    def _safe_delay(self) -> str:
        try:
            value = int(self.delay.get())
        except ValueError:
            value = 10
        return str(max(0, value))

    def _safe_tiktok_delay(self) -> str:
        try:
            value = int(self.tiktok_delay.get())
        except ValueError:
            value = 5
        return str(max(0, value))

    def _safe_facebook_delay(self) -> str:
        try:
            value = int(self.facebook_delay.get())
        except ValueError:
            value = 10
        return str(max(0, value))

    def _safe_instagram_delay(self) -> str:
        try:
            value = int(self.instagram_delay.get())
        except ValueError:
            value = 5
        return str(max(0, value))

    @staticmethod
    def _safe_int_text(variable: StringVar, fallback: int) -> str:
        try:
            value = int(variable.get())
        except ValueError:
            value = fallback
        return str(max(0, value))

    def _on_close(self) -> None:
        try:
            self.save_panel_settings()
        finally:
            self.root.destroy()

    @staticmethod
    def _format_size(size: int) -> str:
        units = ("B", "KB", "MB", "GB")
        value = float(size)
        for unit in units:
            if value < 1024 or unit == units[-1]:
                return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} {unit}"
            value /= 1024
        return f"{size} B"

    @staticmethod
    def _format_time(timestamp: float) -> str:
        import datetime as _dt

        return _dt.datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M")


def main() -> None:
    root = Tk()
    UploadPanel(root)
    root.mainloop()


def run_script_from_exe() -> None:
    if len(sys.argv) < 3:
        raise SystemExit("Missing script path")
    script_path = Path(sys.argv[2]).resolve()
    allowed_scripts = {
        MAIN_FILE.resolve(),
        TIKTOK_UPLOAD_FILE.resolve(),
        FACEBOOK_UPLOAD_FILE.resolve(),
        INSTAGRAM_UPLOAD_FILE.resolve(),
        AYRSHARE_UPLOAD_FILE.resolve(),
        ZERNIO_UPLOAD_FILE.resolve(),
    }
    if script_path not in allowed_scripts:
        raise SystemExit(f"Script is not allowed: {script_path}")

    sys.argv = [str(script_path)] + sys.argv[3:]
    runpy.run_path(str(script_path), run_name="__main__")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--run-script":
        run_script_from_exe()
    else:
        main()

