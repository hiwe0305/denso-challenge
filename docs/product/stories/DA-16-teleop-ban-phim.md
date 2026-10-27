# DA-16 · Teleop bàn phím trong SIMPLE

## Trạng thái

| Trường | Giá trị |
|---|---|
| Trạng thái | Sẵn sàng (PO duyệt 25/10/2026; viết lại 27/10/2026) |
| Người làm | Chờ PO giao |
| Làn | Adapter simulator (`flywheel-simple`) |
| Story PRD | Story của [design 27/10/2026](../../superpowers/specs/2026-10-27-g1-psi0-demo-design.md) mục 5.2 · Epic 9 |
| Nhãn | [Adapter] · `epic:9` · `gate:G0` · `area:sim` |
| Sprint | S1 tuần 2 đến S2 tuần 3; một episode bàn phím ghi được trước 6/11/2026 |
| Ước lượng | 12 giờ (khoảng 10–15, ước lượng) |
| Phụ thuộc | S1-02 (môi trường SIMPLE, entry point `teleop_decoupled_wbc`). Trong lúc chờ: viết ánh xạ phím thuần Python và test bằng chuỗi phím giả |

## Story

Là người thu dữ liệu, tôi muốn điều khiển G1 trong SIMPLE bằng bàn phím trên task hai bàn và ghi episode ra LeRobot, để đội tự thu demo và correction mà không cần kính PICO.

## Tiêu chí chấp nhận

1. Đọc mã `teleop_decoupled_wbc` của SIMPLE, ghi chỗ cắm thiết bị: đầu vào tư thế đầu và cổ tay của PICO, lệnh đi bộ ở chế độ PLANNER, lệnh bàn tay. Ghi kết luận ở `docs/g0/teleop-keyboard.md` trước khi viết mã.
2. Thiết bị bàn phím thay luồng PICO: phím vận tốc tiến, lùi, sang ngang, xoay (vào planner đi bộ của WBC); chọn tay trái hoặc phải, phím dịch cổ tay theo x, y, z và xoay (IK của SIMPLE đổi thành tư thế thân trên); một phím đóng, một phím mở mỗi bàn tay; phím bắt đầu, thành công, thất bại, reset. Bảng phím hiện trên màn hình.
3. Chạy ở `--sim-mode=mujoco` trên task `G1WholebodyLocomotionPickBetweenTablesTeleop-v0`; dữ liệu đi cùng decoupled WBC với dữ liệu teleop của tác giả.
4. Ghi bằng bộ ghi LeRobot của SIMPLE (`--record`), thêm `meta`: `source_detail = teleop_keyboard`, người điều khiển (mã giả danh), hạt giống điều kiện, phiên bản SIMPLE, kết quả do người bấm.
5. Mỗi phiên ghi một mục sổ chi phí (phút người, số episode, số episode đạt `check_success`).
6. Đo giờ người cho 20 demo thử trên Level 0: trung bình và p90 phút mỗi demo đạt.
7. Hướng dẫn người điều khiển ở `docs/g0/teleop-keyboard.md`.

## Nhiệm vụ

- [ ] 1. Đọc mã teleop của SIMPLE, ghi chỗ cắm (AC 1)
- [ ] 2. Ánh xạ phím thuần Python, test bằng chuỗi phím giả (AC 2)
- [ ] 3. Cắm thiết bị vào `teleop_decoupled_wbc`, chạy trên task hai bàn (AC 2, 3)
- [ ] 4. Ghi LeRobot có `meta` (AC 4)
- [ ] 5. Sổ chi phí mỗi phiên (AC 5)
- [ ] 6. 20 demo thử, đo giờ, hướng dẫn (AC 6, 7)

## Phạm vi file

Theo 07 mục 3.1. pr-guard chặn PR sửa file ngoài danh sách này; file story luôn được sửa.

- `packages/flywheel-simple/src/flywheel_simple/teleop/`, `packages/flywheel-simple/tests/teleop/`
- `scripts/g0/teleop_keyboard.sh`
- `docs/g0/teleop-keyboard.md`, `docs/g0/ledger/DA-16.csv`

## Ghi chú cho người làm

- Nguồn: design 27/10 mục 5.2; spec 2.4 Q6, 2.5; 03 §5.4 (dòng TeleopSource).
- Tài liệu SIMPLE chỉ có PICO 4 cùng tracker (XRoboToolkit); không có đường bàn phím. Nếu không cắm được vào luồng tư thế, phương án lui là bàn phím lái trực tiếp lệnh thân trên của WBC (03 §12.2); ghi `Decision`.
- Code thiết bị chạy trong worker của môi trường SIMPLE, không import vào lõi. Trước PR `chore-restructure`, nếu `packages/flywheel-simple/` chưa có, để mã tạm ở `scripts/g0/` và báo Hiếu.
- Chuyển episode thành bundle chung thuộc làn Dữ liệu (DA-03), không thuộc story này.
- Demo bàn phím chậm và kém mượt hơn PICO; báo riêng. Không commit bản ghi; dữ liệu ở `fwdata/`.

## Kiểm thử

- Chuỗi phím giả cho chuỗi lệnh đúng (test không cần SIMPLE).
- Một episode ghi được, đọc lại bằng loader LeRobot của Ψ₀ ra một batch.

## Người phụ trách

- Làm: chờ PO giao
- Duyệt và merge: Dương Đình Hiếu (người duy nhất, 07 mục 3.4)

## Change log

| Ngày | Nội dung | Người |
|---|---|---|
| 25/10/2026 | Tạo story: teleop bàn phím cho robot DENSO trên MuJoCo | PO (Hiếu) theo design 25/10/2026 (đã xóa) |
| 25/10/2026 | Viết lại: teleop qua ROS 2, ra MCAP | PO (Hiếu) theo design chia làn (đã xóa) |
| 27/10/2026 | Viết lại: thiết bị bàn phím cắm vào `teleop_decoupled_wbc` của SIMPLE trên task hai bàn, ghi LeRobot; bỏ ROS 2, MCAP, robot DENSO; người làm chờ PO giao | PO (Hiếu) theo design 27/10/2026 |

## Ghi chép khi làm

- Giờ thực:
- Công cụ AI đã dùng:
- Ghi chú hoàn thành:
- File đã tạo hoặc sửa:
