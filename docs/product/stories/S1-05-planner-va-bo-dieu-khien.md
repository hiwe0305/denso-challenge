# S1-05 · Sinh tự động cho task hai bàn (Q2)

## Trạng thái

| Trường | Giá trị |
|---|---|
| Trạng thái | Sẵn sàng (PO duyệt 22/10/2026; hủy 25/10/2026; mở lại 27/10/2026) |
| Người làm | Hiếu |
| Story PRD | 1.5, phần Q2 (AC 1 và AC 4 cho cờ `plan`) · Epic 1; phần xây tuyến của 5.5 cho task hai bàn |
| Nhãn | [Adapter] · `epic:1` · `gate:G0` · `area:sim` · `spike` |
| Sprint | S1 tuần 2 đến S2 tuần 3; có ít nhất 50 episode sinh đạt trước 13/11/2026 cho demo |
| Ước lượng | 20 giờ (bản 22/10: 6 giờ, chỉ trả lời Q2) |
| Phụ thuộc | S1-02; tuyến chọn ở S1-11 (bắt đầu trên tuyến B trong lúc chờ, vì `datagen` có sẵn) |

## Story

Là kỹ sư simulation, tôi muốn sinh tự động episode thành công của task hai bàn trong SIMPLE, để đội có dữ liệu robot không cần người điều khiển và có nguồn cho nhánh B, C sau này.

## Tiêu chí chấp nhận

_Mở lại ngày 27/10/2026 theo [design 27/10/2026](../../superpowers/specs/2026-10-27-g1-psi0-demo-design.md) mục 5.3. Task chính là `G1WholebodyLocomotionPickBetweenTablesTeleop-v0`; SIMPLE không có gói MP cho task này._

1. Q2: tuyến do S1-11 chọn chạy được trên task hai bàn ở `--sim-mode=mujoco`: tuyến A (script đi bộ cộng cuRobo trong env WBC) hoặc tuyến B (task `G1WholebodyLocomotionPickBetweenTablesMP-v0` theo mẫu `PickAndBendPlaceMP-v0`, chạy `datagen`). Ghi tỉ lệ sinh đạt trên ít nhất 50 lượt và thời gian mỗi lượt.
2. Điều kiện lấy trong dải hạt giống train (spec mục 4.3); không dùng tham số Level 1, Level 2.
3. Episode xuất LeRobot với `meta`: `source_kind = synthetic`, `synthetic_tier = S1`, `action_quality = planned`, tuyến, phiên bản planner, hạt giống điều kiện. Lượt hỏng vẫn ghi lý do và chi phí, không xóa.
4. Kiểm planner có chạy được từ một trạng thái lưu giữa episode không (cần cho kiểm khả thi và correction do máy sinh; 02 · 5.5 AC 4); đề xuất giá trị `GenCapabilities.plan`.
5. Có ít nhất 50 episode sinh đạt cho demo 17/11 (DA-28) và cho HE-2 (DA-26).
6. Kết quả ở `docs/g0/q2-planner.md`; chi phí vào `docs/g0/ledger/S1-05.csv`.

## Nhiệm vụ

- [ ] 1. Chạy `datagen` trên một task MP có đi bộ để có mốc (AC 1)
- [ ] 2. Dựng tuyến đã chọn cho task hai bàn, chạy 10 lượt (AC 1)
- [ ] 3. Lấy điều kiện trong dải train, xuất LeRobot có `meta` (AC 2, 3)
- [ ] 4. Chạy 50 lượt, đo tỉ lệ sinh đạt và thời gian (AC 1)
- [ ] 5. Kiểm planner từ trạng thái lưu, đề xuất cờ khả năng (AC 4)
- [ ] 6. Sinh đủ 50 episode đạt, ghi đường dẫn cho DA-26, DA-28 (AC 5)
- [ ] 7. Viết `docs/g0/q2-planner.md`, ghi sổ chi phí (AC 6)

## Phạm vi file

Theo 07 mục 3.1. pr-guard chặn PR sửa file ngoài danh sách này; file story luôn được sửa.

- `scripts/g0/datagen_probe.sh`
- `scripts/g0/autogen/`
- `docs/g0/q2-planner.md`
- `docs/g0/ledger/S1-05.csv`

## Ghi chú cho người làm

- Nguồn: 02 · 1.5 (bản 0.3), 5.1, 5.5; spec 2.4 Q2, 2.5, 6.5, 6.6, 10; 03 §3.2 (dòng "Sinh dữ liệu motion planning"), §5.2 (`GenCapabilities`), §5.4; design 27/10 mục 5.3.
- Lệnh của SIMPLE: `uv run datagen simple/<Task>MP-v0 --num-episodes=N`; cuRobo cho hai tay, AMO cho thân dưới, đế đi theo script; generator của tác giả bỏ episode hỏng (`clear_episode_buffer()`), story này phải giữ lại lượt hỏng để đo tỉ lệ sinh đạt.
- Episode tuyến B chạy AMO: không trộn vào release cùng teleop cho tới khi S1-11 kết luận (ADR-08).
- Mã ở `scripts/g0/autogen/` là spike. Story 5.5 chuyển nó thành `GeneratorAdapter` trong `flywheel-simple` sau PR restructure.
- Dữ liệu sinh ra để trong `fwdata/`, không commit.

## Kiểm thử

- Người review chạy lại tuyến đã chọn cho 5 lượt và ra tỉ lệ sinh đạt cùng bậc.
- Episode xuất ra đọc được bằng loader LeRobot của Ψ₀ (một batch).
- Kết quả kiểm từ trạng thái lưu có script chạy lại được.

## Người phụ trách

- Làm: Dương Đình Hiếu
- Duyệt và merge: Dương Đình Hiếu (người duy nhất, 07 mục 3.4)

## Change log

| Ngày | Nội dung | Người |
|---|---|---|
| 22/10/2026 | Tạo story từ 02 · 1.5 (phần Q2) và AC V3 mới; tách khỏi Q3, Q4 (S1-06) | SM (Bob), PO (Sarah) duyệt |
| 22/10/2026 | Theo 02 bản 0.3 (06 mục 1): V3 tách sang story 1.9, file S1-11; story này chỉ còn Q2 và kiểm planner từ trạng thái lưu; bỏ F1 khỏi vai dự phòng cho Q2; ước lượng 12 → 6 giờ | SM (Bob) theo 06 |
| 24/10/2026 | Thêm mục Phạm vi file. Story giữ `datagen_probe.sh`, S1-11 chỉ chạy; sổ chi phí riêng của story | PO (Hiếu) |
| 25/10/2026 | Hủy: teleop, planner và policy chạy cùng bộ điều khiển trên MuJoCo | PO (Hiếu) theo design 25/10/2026 (đã xóa) |
| 27/10/2026 | Mở lại thành sinh tự động cho task hai bàn: dựng tuyến S1-11 chọn, 50 lượt, xuất LeRobot có `meta`, 50 episode đạt cho demo; thêm `scripts/g0/autogen/`; người làm chờ PO giao; 6 → 20 giờ | PO (Hiếu) theo design 27/10/2026 |
| 27/10/2026 | Giao cho Hiếu theo 07 mục 2.0 (bản 0.6) | PO (Hiếu) |

## Ghi chép khi làm

- Giờ thực:
- Công cụ AI đã dùng:
- Ghi chú hoàn thành:
- File đã tạo hoặc sửa:
