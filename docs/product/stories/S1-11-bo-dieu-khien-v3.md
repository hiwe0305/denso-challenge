# S1-11 · Bộ điều khiển teleop và motion planning (V3)

## Trạng thái

| Trường | Giá trị |
|---|---|
| Trạng thái | Sẵn sàng (PO duyệt 22/10/2026; hủy 25/10/2026; mở lại 27/10/2026) |
| Người làm | Chờ PO giao |
| Story PRD | 1.9 · Epic 1 (story mới ở 02 bản 0.3, tách từ AC 5 cũ của 1.5) |
| Nhãn | [Adapter] · `epic:1` · `gate:G0` · `area:sim` · `spike` |
| Sprint | S1. **Bảng đối chiếu xong trước thứ Sáu 30/10/2026.** Chốt tuyến sinh tự động cuối tuần 2 ở review G0 |
| Ước lượng | 8 giờ (bản 22/10: 18 giờ gồm thử T1, T2; phần xây tuyến nay thuộc S1-05) |
| Phụ thuộc | Bước 1 không cần S1-02 (đọc cấu hình, mã SIMPLE và metadata checkpoint). Bước 3 cần S1-02. Chặn S1-05 phần chọn tuyến, DA-03 phần trộn nguồn |

## Story

Là kỹ sư simulation, tôi muốn biết dữ liệu sinh tự động của task hai bàn có cùng bộ điều khiển với demo teleop không, để chọn đúng tuyến sinh tự động và biết dữ liệu nào được trộn trong một release.

## Tiêu chí chấp nhận

_Mở lại ngày 27/10/2026 theo [design 27/10/2026](../../superpowers/specs/2026-10-27-g1-psi0-demo-design.md) mục 5.3: task chính là `G1WholebodyLocomotionPickBetweenTablesTeleop-v0`; dữ liệu bàn phím chạy cùng decoupled WBC với teleop, nhưng dữ liệu sinh bằng `datagen` của SIMPLE chạy AMO._

1. Bảng đối chiếu task hai bàn (`G1WholebodyLocomotionPickBetweenTablesTeleop-v0`) với một task MP gần nhất có đi bộ (ví dụ `G1WholebodyPickAndBendPlaceMP-v0`): env, robot, bộ điều khiển, không gian state, không gian action, tần số điều khiển, camera. Mỗi ô có nguồn là file cấu hình hoặc mã SIMPLE.
2. Đọc `run_config.json` và `argv.txt` của ba checkpoint task hai bàn của tác giả (`…teleop-v0`, `…mixed-v0`, `…variant5-v0-processed`): `mixed` trộn nguồn gì, qua bộ điều khiển nào, dataset nào; ghi vào bảng.
3. Thử nhanh mỗi tuyến 10 lượt trên một điều kiện: tuyến A (script đi bộ cộng cuRobo trong env WBC của task hai bàn) và tuyến B (task MP chạy `datagen`, AMO). Ghi tỉ lệ thành công và ước công sức xây đến mức chạy được (đầu vào cho S1-05).
4. Kết luận: tuyến được chọn; nếu chọn B thì ghi ánh xạ không gian lệnh AMO sang `action_layout` của WBC hoặc ghi rõ hai `embodiment_id` không trộn trong một release (ADR-08).
5. Cùng bảng cho cặp F1 (`BendPickTeleop`, `BendPickMP`) như bản 22/10, chỉ để kiểm khả năng tổng quát của lõi.
6. Kết luận ở `docs/g0/v3-planner-controller.md`, có mục "Đề xuất cho 03 §3.3" với dòng V3 và giá trị cờ `GenCapabilities.plan` ([docs/g0/README.md](../../g0/README.md)); nháp `configs/embodiments/g1_sonic_dwbc.yaml` và `g1_wholebody_amo.yaml`.

## Nhiệm vụ

- [ ] 1. Bảng đối chiếu (AC 1, 2), xong trước 30/10/2026
  - [ ] 1.1 Đọc cấu hình env, robot, bộ điều khiển của task hai bàn và task MP gần nhất; ghi bảng có nguồn
  - [ ] 1.2 Đọc metadata ba checkpoint task hai bàn của tác giả
  - [ ] 1.3 Báo kết luận sơ bộ trong check-in thứ Sáu 30/10/2026
- [ ] 2. Thử tuyến A và tuyến B, 10 lượt mỗi tuyến (AC 3)
- [ ] 3. Kết luận tuyến, ánh xạ hoặc tách `embodiment_id` (AC 4)
- [ ] 4. Bảng cho cặp F1 (AC 5)
- [ ] 5. Viết kết luận, đề xuất cho 03 §3.3, nháp `configs/embodiments/` (AC 6)

## Phạm vi file

Theo 07 mục 3.1. pr-guard chặn PR sửa file ngoài danh sách này; file story luôn được sửa.

- `scripts/g0/v3_route_probe.py`
- `docs/g0/v3-planner-controller.md`
- `configs/embodiments/g1_sonic_dwbc.yaml`, `configs/embodiments/g1_wholebody_amo.yaml`
- `docs/g0/ledger/S1-11.csv`

## Ghi chú cho người làm

- Nguồn: spec 2.1, 2.3, 2.4 (V3), 2.5, 10 (bảng T1–T4); 03 §3.2, §3.3 V3, §5.2 (`control_spec`), §5.4, ADR-08, ADR-15, ADR-25; design 27/10 mục 5.3.
- Tuyến A tương ứng T3 của spec mục 10; tuyến B tương ứng T4 nhưng chỉ cho phần dữ liệu sinh, không đổi task chính.
- Theo 03 §3.2, mọi task `*Teleop-v0` dùng `g1_sonic` còn `*MP-v0` dùng AMO. Cần xác nhận, không giả định.
- Checkpoint nằm ở `USC-PSI-Lab/psi-model`, thư mục `psi0/simple-checkpoints/`; chỉ tải metadata, không tải trọng số.
- File sẽ tạo: `docs/g0/v3-planner-controller.md`, `scripts/g0/v3_route_probe.py`, hai file nháp trong `configs/embodiments/`.

## Kiểm thử

- Bảng đối chiếu có nguồn cho từng ô; người review đối chiếu ngẫu nhiên 3 ô với mã SIMPLE.
- Người review chạy lại probe của tuyến được chọn cho 5 lượt và ra tỉ lệ thành công cùng bậc.

## Người phụ trách

- Làm: chờ PO giao
- Duyệt và merge: Dương Đình Hiếu (người duy nhất, 07 mục 3.4)

## Change log

| Ngày | Nội dung | Người |
|---|---|---|
| 22/10/2026 | Tạo story từ 02 · 1.9 (bản 0.3), tách V3 khỏi S1-05 theo 06 mục 1; hạn ngày 5, thử T1 và T2 song song, chốt cuối tuần 2 | SM (Bob) theo 06 |
| 24/10/2026 | Thêm mục Phạm vi file. AC 6: đề xuất dòng V3 ghi trong file kết quả, Hiếu gom vào 03 §3.3 ở review G0; chạy `datagen_probe.sh` của S1-05, không sửa | PO (Hiếu) |
| 25/10/2026 | Hủy: không còn V3 vì teleop, planner và policy chạy cùng bộ điều khiển trên MuJoCo | PO (Hiếu) theo design 25/10/2026 (đã xóa) |
| 27/10/2026 | Mở lại cho task hai bàn: bảng đối chiếu với task MP có đi bộ, đọc metadata ba checkpoint của tác giả, thử tuyến A và B, chọn tuyến; phần xây tuyến chuyển sang S1-05; người làm chờ PO giao; 18 → 8 giờ | PO (Hiếu) theo design 27/10/2026 |

## Ghi chép khi làm

- Giờ thực:
- Công cụ AI đã dùng:
- Ghi chú hoàn thành:
- File đã tạo hoặc sửa:
