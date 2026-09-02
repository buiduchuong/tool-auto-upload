# Huong dan su dung TikTok Facebook Reuploader

Cong cu nay dung de tai video TikTok va tu dong dang len Facebook Reels bang Puppeteer.

## 1. Chuan bi

Can co:

- Node.js da cai san.
- Google Chrome.
- Tai khoan Facebook da dang nhap.
- File `cookies.json` cua Facebook.
- Internet on dinh.

Thu muc project hien tai:

```text
D:\tool\tiktok-facebook-reuploader-main
```

## 2. Cai dat thu vien

Mo PowerShell tai thu muc project, sau do chay:

```powershell
npm install
```

Neu da cai roi thi khong can chay lai.

## 3. Tao file cookies Facebook

Script can `cookies.json` de Puppeteer mo Facebook ma khong phai dang nhap tay.

Cach lam:

1. Mo Chrome binh thuong.
2. Dang nhap vao Facebook.
3. Cai extension xuat cookie dang JSON cho Puppeteer.
4. Vao `facebook.com`, dung extension de export cookie.
5. Luu file cookie thanh:

```text
D:\tool\tiktok-facebook-reuploader-main\cookies.json
```

Neu cookie het han, script co the bao loi dang nhap hoac mo Facebook nhung khong dang duoc. Khi do hay export lai `cookies.json`.

## 4. Chay dang 1 link TikTok

Trong PowerShell, chay:

```powershell
npm start
```

Khi chuong trinh hoi:

```text
Do you want to enter a single URL or a list of URLs? (single/list):
```

Nhap:

```text
single
```

Sau do dan link TikTok vao:

```text
Enter the TikTok URL:
```

Script se:

1. Lay thong tin video TikTok.
2. Tai file `.mp4` vao thu muc `download`.
3. Luu metadata vao thu muc `download`.
4. Mo Facebook Reels bang Chrome/Puppeteer.
5. Upload video.
6. Bam cac nut `Next` va `Post/Publish`.

## 5. Chay dang nhieu link TikTok

Tao mot file text, moi dong la mot link TikTok. Vi du `links.txt`:

```text
https://www.tiktok.com/@user/video/123
https://www.tiktok.com/@user/video/456
```

Chay:

```powershell
npm start
```

Khi duoc hoi, nhap:

```text
list
```

Sau do nhap duong dan file:

```text
D:\tool\tiktok-facebook-reuploader-main\links.txt
```

Script se xu ly tung link mot.

## 6. Doc log khi chay

Mot lan thanh cong thuong co cac dong gan nhu:

```text
Facebook opened.
Uploaded file to Facebook form: tenvideo.mp4
Clicked button: Next
Clicked button: Next
Caption step finished.
Clicked button: Post
Post clicked, waiting for Facebook to finish...
Upload flow finished.
Video uploaded successfully
```

Neu dung o man hinh `Create footage` va thay nut `Replace video`, nghia la video da duoc dua vao form. Neu khong di tiep, thuong la do script chua bam dung nut `Next`, Facebook dang xu ly video cham, hoac giao dien Facebook thay doi.

## 7. Cac file debug loi

Khi loi, script co the tao cac file anh trong thu muc project:

- `facebook-login-required.png`: cookie het han hoac chua dang nhap.
- `facebook-next-step-1-error.png`: khong tim thay nut `Next` dau tien.
- `facebook-publish-error.png`: khong tim thay nut dang bai.
- `facebook-publish-timeout.png`: da bam dang nhung Facebook chua hien xac nhan.
- `facebook-upload-error.png`: loi khac trong qua trinh upload.

Neu gap loi, hay mo cac anh nay de xem Facebook dang dung o man hinh nao.

## 8. Loi thuong gap

### Bao thanh cong nhung khong thay bai

Co the Facebook chi nhan lenh dang nhung dang xu ly, dang vao nhap, bi chan quyen hien thi, hoac giao dien khong hien thong bao xac nhan. Hay kiem tra tab Reels tren trang ca nhan/Page va file debug neu co.

### Dung o man hinh Create footage

Neu thay `Replace video`, file da upload vao form. Hay xem terminal co dong:

```text
Clicked button: Next
```

Neu khong co, script chua bam duoc nut `Next`.

### Khong tim thay caption

Log:

```text
WARN: Caption field not found, skipping caption.
```

Nghia la video van co the dang, nhung caption TikTok khong duoc dien vao Facebook.

### Cookie het han

Neu Facebook yeu cau dang nhap, export lai `cookies.json`.

### Video da ton tai

Log:

```text
already downloaded! using existing file
```

Nghia la video da co trong thu muc `download`, script se dung lai file do.

## 9. Su dung Telegram bot

Neu muon chay qua Telegram:

1. Tao bot bang BotFather.
2. Mo file `.env`.
3. Dien token va Telegram ID duoc phep su dung:

```env
BOT_TOKEN=token_bot_cua_ban
ALLOWED_TELEGRAM_IDS=123456789
PUPPETEER_HEADLESS=false
PUPPETEER_DEBUG=false
```

Neu co nhieu nguoi duoc phep dung bot, ngan cach ID bang dau phay:

```env
ALLOWED_TELEGRAM_IDS=123456789,987654321
```

De biet Telegram ID, tam thoi de trong `ALLOWED_TELEGRAM_IDS`, chay bot va gui lenh
`/myid`. Sau do dien ID vao `.env` va khoi dong lai bot.

Neu chay tren VPS Linux khong co man hinh, dat:

```env
PUPPETEER_HEADLESS=true
```

Neu Chrome dung hoac khong mo duoc Facebook, bat log chi tiet:

```env
PUPPETEER_DEBUG=true
```

4. Chay bot:

```powershell
npm run bot
```

5. Gui file cookie Facebook dang JSON cho bot, vi du `facebook_shop_1.json`.

Bot se:

- Kiem tra file co cookie `c_user` va `xs`.
- Luu tai khoan voi ten `facebook_shop_1`.
- Tu dong chon tai khoan vua gui.

6. Gui link TikTok. Bot se dang video bang tai khoan dang duoc chon.

Lenh quan ly:

```text
/accounts
/use facebook_shop_1
/remove facebook_shop_1
/videos
/deletevideo 7665006942699425044
/deletevideo all
/stats
/myid
/help
```

Lenh `/videos` hien danh sach ID va dung luong video trong thu muc `download`.
Lenh `/deletevideo <id>` xoa file MP4 va metadata cua video do. Lenh
`/deletevideo all` xoa tat ca video, nhung se bo qua video dang duoc upload.

Moi Telegram user co thu muc tai khoan rieng trong `accounts/<telegram_id>`.
Thu muc nay va file `.env` da duoc them vao `.gitignore`.

Luu y: bot gioi han moi user 5 video moi ngay theo code hien tai.

Cookie Facebook la thong tin dang nhap nhay cam. Chi chay bot tren may chu ban tin
tuong, bat `ALLOWED_TELEGRAM_IDS`, khong gui cookie vao nhom Telegram va khong chia
se file cookie cho nguoi khac. Facebook co the yeu cau xac minh neu nhieu tai khoan
dang nhap tu cung mot IP/VPS.

## 10. Dung chuong trinh

Trong cua so PowerShell dang chay, bam:

```text
Ctrl + C
```

Neu Chrome Puppeteer con mo, co the dong cua so Chrome do bang tay.
