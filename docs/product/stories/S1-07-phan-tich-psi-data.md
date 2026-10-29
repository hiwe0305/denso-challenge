# S1-07 · Phân tích gói psi-data (Q1, V1, V6, V9)

## Trạng thái

| Trường | Giá trị |
|---|---|
| Trạng thái | Sẵn sàng (PO duyệt 22/10/2026; hủy 25/10/2026; mở lại 27/10/2026) |
| Người làm | Thông |
| Story PRD | 1.6 · Epic 1 |
| Nhãn | [Adapter] · `epic:1` · `gate:G0` · `area:data` |
| Sprint | S1, xong trong tuần 1 vì Q1 quyết định điểm cuối của lưới HE |
| Ước lượng | 10 giờ (bản 22/10: 12 giờ; Q6 đã có trả lời) |
| Phụ thuộc | Không. Chặn DA-03, DA-26 (danh sách demo), DA-27 (dữ liệu gốc để cấy lỗi) |

## Story

Là kỹ sư data, tôi muốn biết gói psi-data của task hai bàn có bao nhiêu demo teleop dùng được, định dạng gì và giấy phép ra sao, để viết đúng bộ nhập, chốt lưới demo của HE và biết dữ liệu được dùng tới đâu.

## Tiêu chí chấp nhận

_Mở lại ngày 27/10/2026 theo [design 27/10/2026](../../superpowers/specs/2026-10-27-g1-psi0-demo-design.md) mục 5.1, 7.3: gói này là "bộ dataset có sẵn" của thí nghiệm HE._

1. Tải gói task hai bàn (`G1WholebodyLocomotionPickBetweenTablesTeleop-v0.zip`, 203 MB) và gói F1 (`BendPickTeleop`, `BendPickMP`) ở một revision ghim của `USC-PSI-Lab/psi-data`; tải tập eval tương ứng trong `simple-eval/`; ghi sha256 từng file; dữ liệu nằm ngoài git.
2. Q1: đếm N_teleop đạt QA sơ bộ (timestamp tăng đơn điệu, không NaN hay Inf, độ dài hợp lý, cờ thành công nếu có). Nếu N_teleop < 80, ghi điểm cuối của lưới HE là N_teleop (design mục 7.3); nếu < 40, báo Hiếu ngay.
3. V1: ghi `codebase_version` trong `meta/info.json`, fps, tên và chiều các trường state, action, camera, độ phân giải ảnh; đơn vị nếu suy được; so với `action_layout` 36 chiều của Ψ₀.
4. V6 phần dữ liệu: episode có ghi layout, seed hay tham số ngẫu nhiên hóa không; dải hạt giống của `simple-eval` nếu suy được (để dải dev và holdout của đội rời dải tác giả, spec mục 4.3).
5. V9: bảng trạng thái giấy phép của psi-data, psi-model, SIMPLE, cảnh HSSD, tài sản Objaverse: nguồn, ngày kiểm, kết luận. Soạn sẵn câu hỏi giấy phép cho Hiếu gửi PSI Lab.
6. Thống kê mô tả cho báo cáo dataset (design mục 6.5): độ dài episode, phân bố vị trí vật và bàn nếu có, tỉ lệ episode thành công.
7. Kết quả ở `docs/g0/psi-data.md`, có mục "Đề xuất cho 03 §3.3" với dòng V1, V6 (phần dữ liệu), V9 ([docs/g0/README.md](../../g0/README.md)).

## Nhiệm vụ

- [x] 1. Tải và ghi hash (AC 1)
- [x] 2. Đọc cấu trúc LeRobot, ghi trường, so với `action_layout` (AC 3)
- [x] 3. Đếm N_teleop đạt QA sơ bộ cho task hai bàn và F1 (AC 2)
- [x] 4. Tìm layout, seed, tham số điều kiện; dải hạt giống của `simple-eval` (AC 4)
- [x] 5. Bảng giấy phép, soạn câu hỏi cho tác giả (AC 5)
- [x] 6. Thống kê mô tả (AC 6)
- [x] 7. Viết `docs/g0/psi-data.md` kèm đề xuất cho 03 §3.3 (AC 7)

## Phạm vi file

Theo 07 mục 3.1. pr-guard chặn PR sửa file ngoài danh sách này; file story luôn được sửa.

- `scripts/g0/inspect_psi_data.py`
- `docs/g0/psi-data.md`
- `docs/g0/ledger/S1-07.csv`

## Ghi chú cho người làm

- Nguồn: 02 · 1.6, 2.2, NFR6; spec 2.3, 2.4 Q1, 4.1, 4.2, 4.3, 4.4; 03 §3.2 (dòng "psi-data"), §3.3 V1, V6, V9, §10.3; design 27/10 mục 5.1, 7.3.
- Đã biết (đọc code ngày 25/10/2026): fork lerobot của Ψ₀ là `songlin/lerobot@09929d8`, `CODEBASE_VERSION = "v2.1"`. Story này kiểm lại trên gói thật.
- Q6 đã có trả lời ngày 27/10/2026: không có PICO; đội viết thiết bị bàn phím (DA-16).
- Quyết định của PO (04 mục 1.3): mọi episode từ psi-data mang `license = unknown`, `data_class = restricted` cho tới khi tác giả trả lời. Design 27/10 mục 8.4 đề xuất coi dữ liệu demo là `public` để lên Colab; nếu V9 chưa rõ thì báo Hiếu chốt.
- Script chỉ đọc dữ liệu, không sửa gói gốc. Viết sao cho DA-03 dùng lại được phần đọc LeRobot.
- Token Hugging Face để trong `.env`.

## Kiểm thử

- Chạy lại script trên cùng revision cho cùng N_teleop và cùng hash.
- Người review kiểm ngẫu nhiên 3 episode bằng tay khớp với số liệu script.

## Người phụ trách

- Làm: Dương Tiến Thông
- Duyệt và merge: Dương Đình Hiếu (người duy nhất, 07 mục 3.4)

## Change log

| Ngày | Nội dung | Người |
|---|---|---|
| 22/10/2026 | Tạo story từ 02 · 1.6, thêm V1, V6, V9 theo AC mới | SM (Bob), PO (Sarah) duyệt |
| 22/10/2026 | Sửa mã trích 05 TN13 thành TH13; ghi liên hệ Q6 với S1-11. AC không đổi | SM (Bob) theo 06 |
| 24/10/2026 | Thêm mục Phạm vi file. AC 7: đề xuất dòng V1, V6, V9 ghi trong file kết quả, Hiếu gom vào 03 §3.3 ở review G0 | PO (Hiếu) |
| 25/10/2026 | Hủy: psi-data là dữ liệu của G1; dữ liệu chính chuyển sang dataset BTC | PO (Hiếu) theo design 25/10/2026 (đã xóa) |
| 27/10/2026 | Mở lại cho task hai bàn: gói 203 MB và tập eval, N_teleop quyết định lưới HE, so với `action_layout`, dải hạt giống của `simple-eval`, thống kê cho báo cáo dataset; bỏ AC Q6 (đã trả lời); 12 → 10 giờ | PO (Hiếu) theo design 27/10/2026 |

## Ghi chép khi làm

- Giờ thực: 2.5h
- Công cụ AI đã dùng: Claude
- Ghi chú hoàn thành: Đã viết script inspect_psi_data.py, hoàn thành báo cáo docs/g0/psi-data.md và sổ chi phí docs/g0/ledger/S1-07.csv, trả lời Q1, V1, V6, V9.
- File đã tạo hoặc sửa:
  - scripts/g0/inspect_psi_data.py
  - docs/g0/psi-data.md
  - docs/g0/ledger/S1-07.csv
  - docs/product/stories/S1-07-phan-tich-psi-data.md
