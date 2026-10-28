# DA-33 · Synthetic S1 cho task bê khay

## Trạng thái

| Trường | Giá trị |
|---|---|
| Trạng thái | Nháp (PO duyệt hướng 28/10/2026); nhiệm vụ con chi tiết viết khi DA-32 xong nhiệm vụ con 4 |
| Người làm | Hiếu |
| Làn | Adapter simulator (`flywheel-simple`) |
| Story PRD | Story của [design 28/10/2026](../../superpowers/specs/2026-10-28-tray-transfer-he-design.md) mục 4, 5, 7 (M2) |
| Nhãn | [Adapter] · `epic:9` · `gate:G1` · `area:sim` |
| Sprint | S2 tuần 1; M2 8/11/2026 |
| Ước lượng | 20 giờ (khoảng 15–30, ước lượng) |
| Phụ thuộc | DA-32 (task, vị từ). Máy có CUDA cho cuRobo (máy 3060 hoặc server thuê) |

## Story

Là trưởng nhóm, tôi muốn sinh tự động episode G1 bê khay bằng hai tay qua đường MP của SIMPLE, để có ít nhất 80 demo robot đạt QA cho thí nghiệm DA-34.

## Tiêu chí chấp nhận

1. Bước con cầm hai tay cùng lúc (hai tay tới hai tay cầm, đóng cả hai, nhấc, mang, hạ, mở cả hai) chạy được trong MP agent của SIMPLE từ package của đội, không fork SIMPLE; nếu bắt buộc fork thì ghim commit và ghi lý do.
2. `decompose()` của task khay cho chuỗi bước theo 7 bước scorer của DA-32.
3. Một episode sinh tự động mang khay thành công theo `check_success()` của DA-32 (mục tiêu 6/11).
4. `datagen` sinh ≥ 100 episode, ≥ 80 đạt QA; release có hash; mỗi episode ghi `source_kind = synthetic`, `synthetic_tier = S1`, `action_quality = planned`, phiên bản planner.
5. Đo thời gian sinh mỗi episode, tỉ lệ đạt, GPU-giờ; ghi sổ chi phí.
6. Ghi `action_layout` và bộ điều khiển của dữ liệu (AMO) để DA-34 khớp với đường eval của Ψ₀.

## Nhiệm vụ

- [ ] 1. Bước con cầm hai tay trong MP agent (AC 1)
- [ ] 2. `decompose()` và một episode thành công (AC 2, 3)
- [ ] 3. Sinh hàng loạt, QA, release (AC 4)
- [ ] 4. Đo, sổ chi phí, ghi `action_layout` (AC 5, 6)

## Phạm vi file

Theo 07 mục 3.1. pr-guard chặn PR sửa file ngoài danh sách này; file story luôn được sửa.

- `packages/flywheel-simple/src/flywheel_simple/tray/`, `packages/flywheel-simple/tests/tray/`
- `scripts/g0/tray/`
- `docs/g0/tray/`, `docs/g0/ledger/DA-33.csv`

## Ghi chú cho người làm

- MP agent của SIMPLE (`simple/agents/mp.py`) lên kế hoạch từng tay một (`switch_arm`) và cầm vật theo grasp dựng sẵn (Bodex). Cầm khay cần bước con mới; tay cầm khay có tư thế cầm cố định theo hình học nên có thể tính trực tiếp thay vì tìm grasp.
- `decompose()` của task hai bàn (`g1_wholebody_locomotion_pick_between_tables_teleop.py`) là mẫu cho Walk, Turn, Lift.
- cuRobo cần CUDA; laptop RTX 3050 4 GB chỉ để thử, chạy hàng loạt trên máy 3060 hoặc server thuê.

## Người phụ trách

- Làm: Dương Đình Hiếu
- Duyệt và merge: Dương Đình Hiếu (người duy nhất, 07 mục 3.4)

## Change log

| Ngày | Nội dung | Người |
|---|---|---|
| 28/10/2026 | Tạo story nháp theo design 28/10/2026 | PO (Hiếu) |

## Ghi chép khi làm
