# Website · Humanoid Data Flywheel

Website tĩnh 12 trang trình bày Pitch v10 (Ψ₀ + SIMPLE / G1) và deck workflow kỹ thuật. Số liệu hiệu quả là **ước lượng có điều kiện**, không phải kết quả đo tại DENSO. Chưa chạy PoC Ψ₀ hoặc robot thật.

## Cấu trúc

| Đường dẫn | Vai trò |
|---|---|
| `content/current-platform.json` | Nội dung pitch: workflow, đội, mốc, nguồn, ví dụ dataset |
| `content/current-cost-model.json` | Giả định chi phí của Pitch v10 (slide 8, 12, 13) |
| `content/media.json` | Video và hình công khai của tác giả dùng ở trang Dữ liệu & V2D |
| `assets/platform/`, `assets/team/` | Hình gốc có ghi nguồn (`sources.json`) |
| `build.py` | Chép hai deck từ `deliverables/`, hình gốc, sinh `dist/current-platform-data.js`, `dist/media.js` và `dist/data/*.json` |
| `verify.py` | Kiểm offline: file được tham chiếu, route, media, SHA-256 của deck và hình |
| `test.js` | Kiểm nội dung 12 trang, phép tính chi phí và tình huống âm (cần Node) |
| `dist/` | Thư mục được phục vụ và đăng lên GitHub Pages |

Trong `dist/`, các file viết tay là `index.html`, `app.js` (router, menu, inspector dataset), `current-platform.js` (nội dung từng trang), `styles.css`, `current-platform.css` và `vendor/hls.min.js`. Các mẫu số liệu công khai nằm ở `dist/data/` (G1, GR1, HumanEgo, LIBERO) cùng clip `dist/assets/gr1-episode-0.mp4`.

## Sửa và kiểm tra

Sửa nội dung trong `content/` hoặc thay deck trong `deliverables/`, rồi chạy từ thư mục gốc của project:

```bash
python3 website/build.py
```

```bash
python3 website/verify.py
```

```bash
node website/test.js
```

```bash
bash start-website.sh
```

Mở [website cục bộ](http://127.0.0.1:4175/#overview) và giữ máy chủ chạy khi xem. GitHub Actions chạy cùng các bước build và kiểm tra trước khi đăng `website/dist`.

Bản website đầy đủ trước đây (các trang FluxVLA/GR00T/GR1, hồ sơ đọc trong trang, replay MuJoCo) nằm trong tag git `archive/v3` ở thư mục `presentation-site/`.
