# CLAUDE.md · website

Website tĩnh trình bày dự án, đăng lên GitHub Pages bằng `.github/workflows/pages.yml`. Chi tiết cấu trúc ở [website/README.md](README.md).

- Nội dung sửa ở `content/*.json` và các file viết tay trong `dist/` (`index.html`, `app.js`, `current-platform.js`, `styles.css`, `current-platform.css`). Không sửa tay file sinh ra: `dist/current-platform-data.js`, `dist/media.js`, `dist/data/current-*.json`, `dist/assets/decks/`.
- File sinh ra trong `dist/` (deck, hình, `current-platform-data.js`, `media.js`, `data/current-*.json`, `data/presentation-sources.json`) không commit; clone mới phải chạy `python3 website/build.py` trước khi xem hoặc kiểm.
- Sau khi sửa: `python3 website/build.py`, rồi `python3 website/verify.py`. `node website/test.js` cần Node; máy không có Node thì để CI chạy và nói rõ là chưa chạy cục bộ.
- Thứ tự trang nằm ở mảng `chapters` trong `dist/app.js`; giữ nguyên route id để link cũ không hỏng.
- Số liệu trên website là mục tiêu hoặc giả định; ghi rõ như vậy.
- Website hiện theo spec v10.1; cập nhật sang v10.2 là việc riêng, có người làm riêng (07 mục 2).
- `dist/progress.html` và `dist/progress.js` là trang Tiến độ độc lập, không thuộc 12 trang; dữ liệu `dist/data/progress.json` do `scripts/daily_report.py` sinh khi build Pages và không commit (docs/product/08-daily-control.md).
- Trình duyệt có thể giữ bản cũ của `dist/index.html`; khi kiểm thì mở kèm tham số mới, ví dụ `?fresh=1`.
