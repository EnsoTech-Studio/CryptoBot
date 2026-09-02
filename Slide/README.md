# CryptoBot Architecture Presentation Slides

Bộ slide thuyết trình kiến trúc phần mềm đồ án **CryptoBot (Crypto Strategy Lab)** được thiết kế tương thích đa nền tảng, có thể chạy trực tiếp trên bất kỳ máy tính hoặc trình duyệt nào mà không cần cài đặt môi trường hay kết nối internet.

---

## 🚀 Các Tùy Chọn Trình Chiếu

### 1. Slide Độc Lập (Standalone Single File) — **Khuyến nghị mang đi báo cáo**
* **Tập tin:** [`standalone.html`](file:///home/nesfan/Desktop/HCMUS/Nam3/HK3/KTPM/CryptoBot/Slide/standalone.html)
* **Đặc điểm:**
  * **100% Self-Contained:** Tất cả 20 sơ đồ kiến trúc HD được nhúng trực tiếp dưới dạng Base64 Data URI.
  * **Hoạt động Offline 100%:** Thư viện Markdown parser (`marked.js`), CSS và toàn bộ logic điều khiển được nhúng sẵn trong 1 file HTML duy nhất.
  * **Di chuyển dễ dàng:** Chỉ cần copy file `standalone.html` vào USB, gửi qua Email/Zalo/Telegram hoặc mở trực tiếp trên máy của hội đồng chấm điểm bằng cách double-click (giao thức `file://`).

### 2. Slide Dự Án (Local Development)
* **Tập tin:** [`index.html`](file:///home/nesfan/Desktop/HCMUS/Nam3/HK3/KTPM/CryptoBot/Slide/index.html)
* Sử dụng khi làm việc trực tiếp bên trong cấu trúc thư mục repo dự án.

### 3. Xuất Bản In & Lưu PDF
* Mở `standalone.html` trên trình duyệt (Chrome, Brave, Edge, Safari).
* Nhấn `Ctrl + P` (hoặc `Cmd + P`), chọn **Destination: Save as PDF**, khổ ngang (**Landscape**), bỏ chọn Headers and Footers để có bản in PDF từng slide sắc nét.

---

## ⌨️ Phím Tắt & Tính Năng Điều Khiển

| Phím Tắt | Chức Năng |
| :--- | :--- |
| `→` / `Space` / `PageDown` | Chuyển sang slide tiếp theo |
| `←` / `Backspace` / `PageUp` | Quay lại slide trước |
| `Home` / `End` | Về slide đầu tiên / slide cuối cùng |
| `F` | Bật / Tắt chế độ toàn màn hình (**Fullscreen**) |
| `B` hoặc `.` | Màn hình đen (**Blackout**) để tập trung người nghe vào người thuyết trình |
| `T` | Tạm dừng / Tiếp tục đồng hồ bấm giờ thuyết trình |
| `?` hoặc `H` | Mở / Đóng bảng hướng dẫn phím tắt |
| **Click vào sơ đồ** | Phóng to hình ảnh sơ đồ HD dạng Lightbox Modal |
| **Thanh tiến trình (Progress)** | Nhấp chuột vào thanh tiến trình dưới cùng để nhảy đến vị trí slide bất kỳ |
| **Menu thả xuống (Dropdown)** | Chọn trực tiếp slide theo số thứ tự và tiêu đề |

---

## 🛠️ Biên Dịch & Cập Nhật Slide

Khi chỉnh sửa nội dung trong thư mục [`sections/`](file:///home/nesfan/Desktop/HCMUS/Nam3/HK3/KTPM/CryptoBot/Slide/sections), chạy lệnh sau để tự động tạo lại `main.md`, `index.html` và `standalone.html`:

```bash
cd Slide
python3 build_html.py
```

Hoặc chỉ xuất slide standalone:
```bash
python3 export_standalone.py -o standalone.html
```

Kiểm thử tự động toàn bộ 29 slide với Playwright:
```bash
node verify_standalone_playwright.js
```
