# S1-09 · Tín hiệu từng bước và tập điều kiện đánh giá (V6, V7)

## Trạng thái

| Trường | Giá trị |
|---|---|
| Trạng thái | Sẵn sàng (PO duyệt 22/10/2026; sửa 25/10/2026; về lại SIMPLE 27/10/2026) |
| Người làm | Chờ PO giao |
| Story PRD | 1.8 (story mới do PO thêm) · Epic 1 |
| Nhãn | [Adapter] · `epic:1` · `gate:G0` · `area:sim` · `spike` |
| Sprint | S1, tuần 2 |
| Ước lượng | 8 giờ |
| Phụ thuộc | S1-02. Là đầu vào cho scorer của task hai bàn và tập điều kiện ở S2, cho tập eval của HE (DA-26) |

## Story

Là kỹ sư simulation, tôi muốn biết SIMPLE cho lấy những tín hiệu nào khi rollout task hai bàn và sinh tập điều kiện thế nào, để scorer từng bước và việc chia tập không dựa trên giả định.

## Tiêu chí chấp nhận

_Về lại SIMPLE ngày 27/10/2026 ([design 27/10/2026](../../superpowers/specs/2026-10-27-g1-psi0-demo-design.md) mục 3) trên task `G1WholebodyLocomotionPickBetweenTablesTeleop-v0`._

1. V7: bảng tín hiệu lấy được khi rollout task hai bàn: lệnh gửi và giá trị đo theo giao diện decoupled WBC (thân trên, thân dưới, vận tốc đi bộ), tư thế vật, tiếp xúc tay–vật, tư thế thân và chiều cao thân (thăng bằng), vị trí thân so với hai bàn, va chạm, timestamp. Mỗi dòng ghi tần số và cách lấy (trường của SIMPLE, `mjData`).
2. Đối chiếu bảng với tín hiệu scorer cần cho 6 bước và kiểu lỗi của task hai bàn (spec mục 5.1, 5.2, gồm L-WALK) và với `decompose()`, `check_success` của SIMPLE. Tín hiệu thiếu: đề xuất cách lấy (replay, hook).
3. V6: `reset(seed)` tất định: 10 seed, mỗi seed 2 lần, so layout.
4. V6: sinh tập điều kiện theo vector điều kiện của spec mục 4.2 cộng vị trí tương đối của hai bàn nếu S1-06 cho đổi (90 dev, 150 holdout), dải seed rời nhau và rời dải `simple-eval` (S1-07); đối chiếu Level 0, 1, 2 của SIMPLE.
5. Kết quả ở `docs/g0/signals-conditions.md`, có mục "Đề xuất cho 03 §3.3" ([docs/g0/README.md](../../g0/README.md)).

## Nhiệm vụ

- [ ] 1. Liệt kê tín hiệu trên task hai bàn (AC 1)
- [ ] 2. Đối chiếu với nhu cầu scorer và `check_success` (AC 2)
- [ ] 3. Kiểm `reset(seed)` tất định (AC 3)
- [ ] 4. Sinh tập điều kiện, đối chiếu Level 0–2 (AC 4)
- [ ] 5. Viết tài liệu kèm đề xuất cho 03 §3.3 (AC 5)

## Phạm vi file

Theo 07 mục 3.1. pr-guard chặn PR sửa file ngoài danh sách này; file story luôn được sửa.

- `scripts/g0/probe_signals.py`, `scripts/g0/probe_reset_determinism.py`
- `docs/g0/signals-conditions.md`
- `docs/g0/ledger/S1-09.csv`

## Ghi chú cho người làm

- Nguồn: 02 · 1.8 (mới), 2.4, 2.5, 3.3, 3.4; spec 4.2, 4.3, 5.1, 5.2, 5.3; 03 §3.2 (dòng "Điều kiện ban đầu", "Ngẫu nhiên hóa"), §3.3 V6, V7, §8.3 (chia tập theo `layout_hash`), §12.2.
- Bảng tín hiệu là đầu vào cho scorer của làn Đánh giá; bảng chốt thành schema trong `flywheel.contracts` qua Hiếu (DA-25).
- Không đoán tín hiệu từ tài liệu; ghi tín hiệu đã thấy thật trong episode chạy thử.
- V11 (timestamp riêng cho state và từng khung ảnh, tham số camera; 03 §3.3) chốt trong 3.1a ở S2. Nếu story này thấy được các trường đó thì ghi vào bảng.
- Scorer ở S2 cần lớp lỗi chung cho mỗi kiểu lỗi (02 · 3.3 AC 4); khi đối chiếu, ghi bước hỏng tương ứng để gán lớp.
- File sẽ tạo: `scripts/g0/probe_signals.py`, `scripts/g0/probe_reset_determinism.py`, `docs/g0/signals-conditions.md`.

## Kiểm thử

- `probe_reset_determinism.py` trả mã khác 0 khi hai lần reset cùng seed cho layout khác nhau.
- Người viết scorer đọc bảng tín hiệu và xác nhận scorer lấy đủ từ đó (bình luận).

## Người phụ trách

- Làm: chờ PO giao
- Duyệt và merge: Dương Đình Hiếu (người duy nhất, 07 mục 3.4)

## Change log

| Ngày | Nội dung | Người |
|---|---|---|
| 22/10/2026 | Tạo story từ 02 · 1.8 (PO thêm để phủ V6, V7) | SM (Bob), PO (Sarah) duyệt |
| 22/10/2026 | Đồng bộ 03 bản 0.3: tín hiệu lệnh theo giao diện WBC; ghi chú V11 và lớp lỗi chung; sửa mã trích 05 TN13 thành TH13. AC của 02 · 1.8 không đổi | SM (Bob) theo 06 |
| 24/10/2026 | Thêm mục Phạm vi file. AC 6: đề xuất dòng V6, V7 ghi trong file kết quả, Hiếu gom vào 03 §3.3 ở review G0 | PO (Hiếu) |
| 25/10/2026 | Đổi sang task khay → máy trên MuJoCo; chuyển cho Hưng | PO (Hiếu) theo hai design 25/10/2026 (đã xóa) |
| 27/10/2026 | Về lại SIMPLE trên task hai bàn: tín hiệu theo decoupled WBC, thăng bằng, vị trí so với hai bàn; đối chiếu `check_success`, `decompose()`, L-WALK; dải seed rời `simple-eval`; phụ thuộc S1-02; người làm chờ PO giao | PO (Hiếu) theo design 27/10/2026 |

## Ghi chép khi làm

- Giờ thực:
- Công cụ AI đã dùng:
- Ghi chú hoàn thành:
- File đã tạo hoặc sửa:
