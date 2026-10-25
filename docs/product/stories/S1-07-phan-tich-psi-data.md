# S1-07 · Phân tích gói psi-data (Q1, Q6, V1, V6, V9)

## Trạng thái

| Trường | Giá trị |
|---|---|
| Trạng thái | Hủy (25/10/2026) |
| Lý do hủy | Theo [design 25/10/2026](../../superpowers/specs/2026-10-25-denso-mujoco-and-stage-qa-design.md) mục 11.1: psi-data là dữ liệu của G1; phân tích dataset của BTC làm trong DA-22. Q6 đã có trả lời (teleop bàn phím trong MuJoCo); V1 đã có trả lời khi đọc code ngày 25/10/2026 (fork lerobot của Ψ₀ là v2.1) |
| Người làm | Thông |
| Story PRD | 1.6 · Epic 1 |
| Nhãn | [Adapter] · `epic:1` · `gate:G0` · `area:data` |
| Sprint | S1, nên xong trong tuần 1 vì Q1 có thể đổi task |
| Ước lượng | 0 giờ (hủy; trước đó 12 giờ) |
| Phụ thuộc | Không. Chặn story 2.2 ở S2 |

## Story

Là kỹ sư data, tôi muốn biết gói psi-data của task chính có bao nhiêu demo teleop dùng được, định dạng gì và giấy phép ra sao, để chọn đúng task, viết đúng bộ nhập và biết dữ liệu được dùng tới đâu.

## Tiêu chí chấp nhận

1. Tải gói task chính và gói F1 ở một revision ghim của `USC-PSI-Lab/psi-data`; ghi sha256 từng file; dữ liệu nằm ngoài git.
2. Q1: đếm N_teleop đạt QA sơ bộ (timestamp tăng đơn điệu, không NaN hay Inf, độ dài hợp lý, cờ thành công nếu có) cho task chính và F1. Nếu N_teleop < 50, đề xuất chuyển task theo spec 2.4.
3. V1: ghi `codebase_version` trong `meta/info.json`, fps, tên và chiều các trường state, action, camera; đơn vị nếu suy được.
4. V6 phần dữ liệu: episode có ghi layout, seed hay tham số ngẫu nhiên hóa không; nếu không, trường nào dùng để suy vector điều kiện (spec 4.2).
5. V9: bảng trạng thái giấy phép của psi-data, psi-model, SIMPLE, cảnh HSSD, tài sản Objaverse: nguồn, ngày kiểm, kết luận. Soạn sẵn nội dung câu hỏi giấy phép cho Hiếu gửi PSI Lab.
6. Q6: hỏi đội và BTC (qua Hiếu) về thiết bị teleop cho SIMPLE; ghi câu trả lời.
7. Kết quả ở `docs/g0/psi-data.md`, có mục "Đề xuất cho 03 §3.3" với dòng V1, V6 (phần dữ liệu), V9 ([docs/g0/README.md](../../g0/README.md)). Hiếu gom vào 03 §3.3 ở review G0.

## Nhiệm vụ

- ~~1. Tải và ghi hash (AC 1)~~
- ~~2. Đọc cấu trúc LeRobot, ghi trường (AC 3)~~
- ~~3. Đếm N_teleop đạt QA sơ bộ cho task chính và F1 (AC 2)~~
- ~~4. Tìm layout, seed, tham số điều kiện trong dữ liệu (AC 4)~~
- ~~5. Bảng giấy phép, soạn câu hỏi cho tác giả (AC 5)~~
- ~~6. Ghi câu trả lời Q6 (AC 6)~~
- ~~7. Viết `docs/g0/psi-data.md` kèm đề xuất cho 03 §3.3 (AC 7)~~

## Phạm vi file

Theo 07 mục 3.1. pr-guard chặn PR sửa file ngoài danh sách này; file story luôn được sửa.

- `scripts/g0/inspect_psi_data.py`
- `docs/g0/psi-data.md`
- `docs/g0/ledger/S1-07.csv`

## Ghi chú cho người làm

- Nguồn: 02 · 1.6, 2.2, NFR6; spec 2.3, 2.4 Q1, Q6, 4.1, 4.2, 4.4; 03 §3.2 (dòng "psi-data"), §3.3 V1, V6, V9, §10.3; 05 SR3, SR4, TH13, R14.
- Quyết định của PO (04 mục 1.3): mọi episode từ psi-data mang `license = unknown`, `data_class = restricted` cho tới khi tác giả trả lời.
- Script phân tích chỉ đọc dữ liệu, không sửa gói gốc. Viết sao cho story 2.2 dùng lại được phần đọc LeRobot.
- Token Hugging Face để trong `.env`.
- Q6 âm cùng V3 âm là kịch bản ở S1-11 AC 5 (C chỉ còn kiểm demo mâu thuẫn, HT sụp); báo Hưng ngay khi có câu trả lời Q6.
- File sẽ tạo: `scripts/g0/inspect_psi_data.py`, `docs/g0/psi-data.md`.

## Kiểm thử

- Chạy lại script trên cùng revision cho cùng N_teleop và cùng hash.
- Long kiểm ngẫu nhiên 3 episode bằng tay khớp với số liệu script.

## Người phụ trách

- Làm: Dương Tiến Thông
- Review: Nguyễn Thăng Long
- Dự phòng: Nguyễn Thăng Long

## Change log

| Ngày | Nội dung | Người |
|---|---|---|
| 22/10/2026 | Tạo story từ 02 · 1.6, thêm V1, V6, V9 theo AC mới | SM (Bob), PO (Sarah) duyệt |
| 22/10/2026 | Sửa mã trích 05 TN13 thành TH13; ghi liên hệ Q6 với S1-11. AC không đổi | SM (Bob) theo 06 |
| 24/10/2026 | Thêm mục Phạm vi file. AC 7: đề xuất dòng V1, V6, V9 ghi trong file kết quả, Hiếu gom vào 03 §3.3 ở review G0 | PO (Hiếu) |
| 25/10/2026 | Hủy: psi-data là dữ liệu của G1; phân tích dataset của BTC làm trong DA-22. Q6 đã có trả lời (teleop bàn phím trong MuJoCo); V1 đã có trả lời khi đọc code ngày 25/10/2026 (fork lerobot của Ψ₀ là v2.1). Nhiệm vụ con gạch bỏ, không xóa nội dung | PO (Hiếu) theo design 25/10/2026 |

## Ghi chép khi làm

- Giờ thực:
- Công cụ AI đã dùng:
- Ghi chú hoàn thành:
- File đã tạo hoặc sửa:
