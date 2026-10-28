# Website · Humanoid Data Flywheel

Website tĩnh 12 trang trình bày Humanoid Data Flywheel theo [spec v10.1](../docs/spec-v10-failure-to-data.md), dựng thành một mạch trình bày 5 phần quanh lõi **Failure → Data**. Recipe đầu tiên cắm vào lõi là Ψ₀ + SIMPLE / G1. Mọi con số là mục tiêu hoặc giả định, không phải kết quả đo tại DENSO; chưa chạy PoC Ψ₀ hoặc robot thật. Bản PowerPoint Pitch v10 chưa cập nhật theo spec v10.1.

## Cấu trúc

| Đường dẫn | Vai trò |
|---|---|
| `content/current-platform.json` | Nội dung: 8 bước của vòng flywheel, đội, vai trong kế hoạch, 6 sprint, nguồn và tiền lệ, ví dụ dataset |
| `content/current-cost-model.json` | Giả định chi phí của Pitch v10 (slide 8, 12, 13), dùng cho máy tính kịch bản ở trang 08 |
| `content/media.json` | Video và hình công khai của tác giả dùng ở trang Dữ liệu & nguồn |
| `assets/platform/`, `assets/team/` | Hình gốc có ghi nguồn (`sources.json`) |
| `build.py` | Chép hai deck từ `deliverables/`, hình gốc, sinh `dist/current-platform-data.js`, `dist/media.js` và `dist/data/*.json` |
| `verify.py` | Kiểm offline: file được tham chiếu, route và nhóm 5 phần, media, SHA-256 của deck và hình |
| `test.js` | Kiểm mạch trình bày, nội dung 12 trang, quyết định Failure → Data, phép tính chi phí và tình huống âm (cần Node) |
| `dist/` | Thư mục được phục vụ và đăng lên GitHub Pages. Git chỉ giữ file viết tay; file `build.py` chép hoặc sinh ra (deck, hình, `current-platform-data.js`, `media.js`, `data/current-*.json`, `data/presentation-sources.json`) nằm trong `.gitignore` và được dựng lại bởi Pages CI và `start-website.sh` |

Trong `dist/`, các file viết tay là `index.html`, `app.js` (router, menu nhóm theo phần, inspector dataset), `current-platform.js` (nội dung từng trang và khung mạch truyện), `styles.css`, `current-platform.css` và `vendor/hls.min.js`. Các mẫu số liệu công khai nằm ở `dist/data/` (G1, GR1, HumanEgo, LIBERO) cùng clip `dist/assets/gr1-episode-0.mp4`.

## Mạch trình bày

Thứ tự trang là mảng `chapters` trong `dist/app.js`; nhóm 5 phần là `CP_PARTS` và câu hỏi của từng trang là `CP_PAGE_META` trong `dist/current-platform.js`. Route id giữ nguyên từ bản trước để link cũ không hỏng; `#dreamdojo` chuyển về `#research`.

| # | Route | Trang | Phần | Câu hỏi trang trả lời |
|---|---|---|---|---|
| 01 | `overview` | Vấn đề & ý tưởng | 1 · Vấn đề | DENSO đau ở đâu, sản phẩm là gì trong một câu; mục tiêu 3 cấp của BTC |
| 02 | `product` | Vòng data flywheel | 1 · Vấn đề | Vòng 8 bước, tài sản sau mỗi vòng, lõi và phần cắm |
| 03 | `architecture` | Failure → Data: khác biệt | 2 · Lõi | So với thu thêm teleop, Mulligan, DISEIL; ba khác biệt; ví dụ chạy qua; ranh giới claim |
| 04 | `engine` | Thuật toán 12 bước | 2 · Lõi | Sơ đồ 12 bước, công cụ chọn kịch bản lỗi, bảng quyết định, chọn can thiệp theo chi phí |
| 05 | `sources` | Dữ liệu & nguồn | 3 · Phần cắm | Nguồn dữ liệu, đơn vị đếm demo gốc, gallery dataset, V2D |
| 06 | `learning` | Model Ψ₀ & training | 3 · Phần cắm | Ψ₀ học gì, đội fine-tune gì, WBC `g1_sonic` so với AMO (V3), tuyến T1–T4 |
| 07 | `validation` | PoC & bằng chứng | 4 · Bằng chứng | Nhánh A, A₀.₇, B, B-fail, C, B⁺; HS, HT, HTa, HTb, HD; tiêu chí BTC; D\*, thống kê, F-ACT |
| 08 | `business` | Giá trị & chi phí | 4 · Bằng chứng | Chỉ số giá trị chính, công thức rút gọn và độ nhạy, máy tính kịch bản Pitch v10 |
| 09 | `roadmap` | Lộ trình 12 tuần | 5 · Triển khai | 6 sprint, cổng G0–G6, V3 hạn ngày 5 Sprint 1, Q0, ai làm gì |
| 10 | `outcomes` | Mở rộng L0 → L4 | 5 · Triển khai | Lõi giữ nguyên, adapter đổi theo mức; điều kiện pilot |
| 11 | `team` | Đội thực hiện | 5 · Triển khai | Đội, minh chứng, vai trong kế hoạch 12 tuần |
| 12 | `research` | Nguồn & tiền lệ | Tham khảo | Ψ₀, SIMPLE, tiền lệ Failure → Data, hướng mở rộng V2D và DreamDojo |

`renderCurrentPlatform` bọc mọi trang bằng cùng một khung: thanh mạch truyện 5 phần (bấm để tới trang đầu của phần), câu nối "Trang trước → trang này trả lời", dòng "Nguồn: spec v10.1 mục …" cho phần 2–4 và nút "Tiếp theo" sinh theo `chapters` (trang cuối dẫn về trang 03). Menu bên trái nhóm theo `CP_PARTS`.

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
