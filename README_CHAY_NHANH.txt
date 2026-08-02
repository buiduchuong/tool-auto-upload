HUONG DAN CHAY NHANH

Ban nay da cau hinh dung theo yeu cau:
- Tieu de video YouTube se tu lay theo ten file video.
  Vi du: videos/Tour Sam Son 2N1D.mp4 -> Tieu de: Tour Sam Son 2N1D
- Mo ta dung chung cho tat ca video trong file: default_description.txt
- Che do dang mac dinh: Cong khai / Public

SETUP KHI COPY SANG MAY KHAC / VPS
- Giai nen source/tool vao mot thu muc rieng.
- Bam chay setup.bat.
- Setup se tu kiem tra Python 3.10+, Chrome, tao .venv, cai thu vien, tao cac thu muc can thiet.
- Sau khi setup xong, chay run_web_panel.bat de mo web panel.
- Cac file run_*.bat se tu uu tien dung Python trong .venv sau khi setup.

CACH DE NHAT: MO PANEL QUAN LY
Chay file run_panel.bat
Trong panel ban co the:
- Them video vao thu muc videos/
- Tai video hang loat bang yt-dlp.exe tu YouTube/Facebook/TikTok
- Chon thu muc upload rieng, vi du TikTok_Channel
- Nhap tieu de rieng khi upload, hoac de trong de tu lay ten file video
- Upload video len TikTok trong tab rieng
- Sua va luu mo ta chung
- Mo Chrome dang nhap YouTube
- Upload tat ca video hoac video dang chon
- Xem log upload ngay trong cua so panel

TAI HANG LOAT VIDEO TIKTOK BANG LINK PROFILE
Cach 1: Chay run_panel.bat -> tab Tai video -> bam "Mau tai profile TikTok" -> dan link profile TikTok -> bam "Tai video".
Cach 1b: Neu muon chay tren cPanel/Linux, bam nut "Lenh cPanel/Linux TikTok" trong tab Tai video de lay lenh dan vao cPanel Terminal.
Cach 2: Chay nhanh file run_download_tiktok_profile.bat.
Mac dinh file nay tai profile:
https://www.tiktok.com/@tamanmoingay2404

Neu muon tai profile khac bang lenh:
run_download_tiktok_profile.bat "https://www.tiktok.com/@username"

Video TikTok se luu vao thu muc TikTok_Channel/ theo dang:
TikTok_Channel/uploader/upload_date_id.mp4
File archive_video.txt dung de bo qua video da tai roi.

Neu log bao "does not pass filter (vcodec!=none), skipping", bai do chi co audio trong du lieu yt-dlp lay duoc, thuong la bai anh/slideshow hoac TikTok dang chan video. Tool se bo qua bai do de tranh tai nham file audio.

Neu dung cPanel/SSH:
- Upload tool len hosting.
- Doc file HUONG_DAN_CPANEL_TIKTOK.txt.
- Chay:
  chmod +x run_download_tiktok_profile.sh
  ./run_download_tiktok_profile.sh "https://www.tiktok.com/@username"

UPLOAD VIDEO LEN YOUTUBE
Trong run_panel.bat -> tab Upload YouTube:
- Thu muc upload mac dinh la videos/
- Neu vua tai TikTok, bam "Chon thu muc upload" va chon TikTok_Channel, hoac bam "Mau tai profile TikTok" trong tab Tai video de panel tu set san
- O "Tieu de rieng": nhap tieu de muon dung cho video dang upload
- Neu de trong "Tieu de rieng", tool tu lay ten file video lam tieu de YouTube

UPLOAD VIDEO LEN TIKTOK
Trong run_panel.bat -> tab Upload TikTok:
- Bam "Mo TikTok dang nhap" de dang nhap tai khoan TikTok
- Sau khi dang nhap xong, giu nguyen cua so Chrome
- Thu muc upload mac dinh la TikTok_Channel
- O "Tieu de rieng": nhap caption/tieu de muon dung
- Neu de trong "Tieu de rieng", tool tu lay ten file video lam caption TikTok
- Bam "Upload tat ca len TikTok" hoac "Upload video dang chon"

Chay nhanh bang file:
run_tiktok_login.bat
run_upload_tiktok_all.bat

BUOC 1: Cai thu vien
Chay file setup.bat

BUOC 2: Dang nhap YouTube
Chay file run_login.bat
Dang nhap YouTube Studio tren Chrome vua mo.
Sau khi dang nhap xong, KHONG tat Chrome.

BUOC 3: Sua mo ta chung
Mo file default_description.txt va sua noi dung mo ta ban muon.
Tat ca video se dung chung mo ta nay.

BUOC 4: Them video
Copy video vao thu muc videos/
Dat ten file theo tieu de ban muon tren YouTube.

Vi du:
videos/Tour Sam Son 2N1D gia chi tu 1519000.mp4
videos/Du lich Phu Quoc he 2026.mp4

BUOC 5: Dang tat ca video cong khai
Chay file run_upload_all_public_same_description.bat

Lenh tuong duong:
python main.py --attach --all --visibility public --description-file default_description.txt

LUU Y:
- Neu Google bao loi khong dang nhap duoc, hay dang nhap bang run_login.bat truoc.
- Khi upload phai giu nguyen cua so Chrome da dang nhap.
- Khong nen upload lap lai mot video qua nhieu lan de tranh bi danh dau spam.
