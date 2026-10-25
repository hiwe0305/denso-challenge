# S1-09 · Tín hiệu từng bước và tập điều kiện đánh giá (V6, V7)

## Trạng thái

| Trường | Giá trị |
|---|---|
| Trạng thái | Sẵn sàng (PO duyệt 22/10/2026; sửa 25/10/2026) |
| Người làm | Châu |
| Story PRD | 1.8 (story mới do PO thêm) · Epic 1 |
| Nhãn | [Adapter] · `epic:1` · `gate:G0` · `area:sim` · `spike` |
| Sprint | S1, tuần 2 |
| Ước lượng | 8 giờ |
| Phụ thuộc | DA-15 nhiệm vụ con 1 (MJCF tối thiểu). Là đầu vào cho DA-12, scorer và tập điều kiện ở S2 |

## Story

Là kỹ sư simulation, tôi muốn biết SIMPLE cho lấy những tín hiệu nào khi rollout và sinh tập điều kiện thế nào, để scorer từng bước và việc chia tập không dựa trên giả định.

## Tiêu chí chấp nhận

_Đổi ngày 25/10/2026 ([design 25/10/2026](../../superpowers/specs/2026-10-25-denso-mujoco-and-stage-qa-design.md) mục 8, 11.1): tín hiệu và tập điều kiện lấy từ env MuJoCo của task khay → máy thay cho task G1 trong SIMPLE._

1. V7: bảng tín hiệu lấy được khi rollout task khay → máy: lệnh gửi và giá trị đo theo nhóm action (`base`, `lift`, `arm_l`, `arm_r`, `gripper_l`, `gripper_r`, `head`), tư thế linh kiện, tiếp xúc gripper–linh kiện, va chạm, lực tại đồ gá, timestamp. Mỗi dòng ghi tần số và cách lấy (trường của `mjData`, sensor trong MJCF).
2. Đối chiếu bảng với tín hiệu scorer cần cho 6 bước và 10 kiểu lỗi (design 23/10 mục 7.1). Tín hiệu thiếu: đề xuất sensor thêm vào MJCF cho DA-15.
3. V6: `reset(seed)` tất định: 10 seed, mỗi seed 2 lần, so layout.
4. V6: sinh tập điều kiện theo vector điều kiện của design 25/10 mục 8 (90 dev, 150 holdout), dải seed rời nhau; đề xuất định nghĩa Level 0, 1, 2 để Hiếu chốt trước khi thu demo đầu tiên.
5. Kết quả ở `docs/g0/signals-conditions.md`, có mục "Đề xuất cho 03 §3.3" ([docs/g0/README.md](../../g0/README.md)).

## Nhiệm vụ

- [ ] 1. Liệt kê tín hiệu trên env MuJoCo (AC 1)
- [ ] 2. Đối chiếu với nhu cầu scorer, đề xuất sensor thiếu (AC 2)
- [ ] 3. Kiểm `reset(seed)` tất định (AC 3)
- [ ] 4. Sinh tập điều kiện, đề xuất Level 0–2 (AC 4)
- [ ] 5. Viết tài liệu kèm đề xuất cho 03 §3.3 (AC 5)

## Phạm vi file

Theo 07 mục 3.1. pr-guard chặn PR sửa file ngoài danh sách này; file story luôn được sửa.

- `scripts/g0/probe_signals.py`, `scripts/g0/probe_reset_determinism.py`
- `docs/g0/signals-conditions.md`
- `docs/g0/ledger/S1-09.csv`

## Ghi chú cho người làm

- Nguồn: 02 · 1.8 (mới), 2.4, 2.5, 3.3, 3.4; spec 4.2, 4.3, 5.1, 5.2, 5.3; 03 §3.2 (dòng "Điều kiện ban đầu", "Ngẫu nhiên hóa"), §3.3 V6, V7, §8.3 (chia tập theo `layout_hash`), §12.2.
- Châu sẽ làm scorer (3.3) và hiệu chỉnh (3.5) ở S2, nên story này là bước chuẩn bị trực tiếp. Hưng dùng bảng tín hiệu để viết hook ghi tín hiệu trong 3.1a.
- Không đoán tín hiệu từ tài liệu; ghi tín hiệu đã thấy thật trong episode chạy thử.
- V11 (timestamp riêng cho state và từng khung ảnh, tham số camera; 03 §3.3) do Hưng chốt trong 3.1a ở S2. Nếu story này thấy được các trường đó thì ghi vào bảng để 3.1a dùng.
- Scorer ở S2 cần thêm lớp lỗi chung cho mỗi kiểu lỗi (02 · 3.3 AC 4); khi đối chiếu 9 kiểu lỗi, ghi bước hỏng tương ứng để gán lớp.
- File sẽ tạo: `scripts/g0/probe_signals.py`, `scripts/g0/probe_reset_determinism.py`, `docs/g0/signals-conditions.md`.

## Kiểm thử

- `probe_reset_determinism.py` trả mã khác 0 khi hai lần reset cùng seed cho layout khác nhau.
- Hưng đọc bảng tín hiệu và xác nhận viết được hook từ đó (review).

## Người phụ trách

- Làm: Trần Trịnh Hoàng Châu
- Review: Trần Ngọc Hưng
- Dự phòng: Trần Ngọc Hưng

## Change log

| Ngày | Nội dung | Người |
|---|---|---|
| 22/10/2026 | Tạo story từ 02 · 1.8 (PO thêm để phủ V6, V7) | SM (Bob), PO (Sarah) duyệt |
| 22/10/2026 | Đồng bộ 03 bản 0.3: tín hiệu lệnh theo giao diện WBC; ghi chú V11 và lớp lỗi chung; sửa mã trích 05 TN13 thành TH13. AC của 02 · 1.8 không đổi | SM (Bob) theo 06 |
| 24/10/2026 | Thêm mục Phạm vi file. AC 6: đề xuất dòng V6, V7 ghi trong file kết quả, Hiếu gom vào 03 §3.3 ở review G0 | PO (Hiếu) |
| 25/10/2026 | Đổi sang task khay → máy trên MuJoCo; phụ thuộc DA-15 thay S1-02; bỏ phần `decompose()` và `simple-eval` | PO (Hiếu) theo design 25/10/2026 |

## Ghi chép khi làm

- Giờ thực:
- Công cụ AI đã dùng:
- Ghi chú hoàn thành:
- File đã tạo hoặc sửa:
