# DA-16 · Teleop bàn phím trên ROS 2, ghi MCAP

## Trạng thái

| Trường | Giá trị |
|---|---|
| Trạng thái | Sẵn sàng (PO duyệt 25/10/2026; sửa theo design chia làn cùng ngày) |
| Người làm | Hưng |
| Làn | Simulation |
| Story PRD | Story mới của [design MuJoCo 25/10/2026](../../superpowers/specs/2026-10-25-denso-mujoco-and-stage-qa-design.md) và [design chia làn](../../superpowers/specs/2026-10-25-lanes-and-code-structure-design.md) · Epic 9 |
| Nhãn | [Adapter] · `epic:9` · `gate:G0` · `area:data` |
| Sprint | S1 |
| Ước lượng | 12 giờ (khoảng 10–15, ước lượng của SM) |
| Phụ thuộc | DA-15 nhiệm vụ con 1 (MJCF), DA-24 (node sim và bringup), DA-25 (bảng topic). Trong lúc chờ: viết `denso_sim.teleop` thuần Python và test trên MJCF tối thiểu |

## Story

Là người thu dữ liệu, tôi muốn điều khiển robot DENSO trong sim bằng bàn phím và ghi bản ghi MCAP đúng bảng topic, để đội tự thu demo và đường dữ liệu giống robot thật.

## Tiêu chí chấp nhận

1. `denso_sim.teleop`: ánh xạ phím → lệnh đầu tay qua IK; đế bằng vận tốc; cột nâng, gripper, đầu bằng phím riêng; chuyển chế độ theo nhóm action; không phụ thuộc ROS.
2. Node `denso_teleop` (ROS 2) dùng `denso_sim.teleop`, xuất lệnh theo bảng topic (design chia làn mục 6.4); bảng phím hiện trên màn hình.
3. Launch `record.launch.py` ghi rosbag2 dạng MCAP đủ topic trong bảng; mỗi bản ghi kèm hạt giống điều kiện, người điều khiển, phiên bản MJCF, kết quả do người bấm (thành công, thất bại, hủy).
4. Mỗi phiên ghi một mục sổ chi phí (phút người, số episode, số episode đạt vị từ thành công).
5. Đo giờ người cho 20 demo thử trên Level 0: trung bình và p90 phút mỗi demo đạt.
6. Hướng dẫn người điều khiển ở `docs/g0/teleop-keyboard.md`.

## Nhiệm vụ

- [ ] 1. `denso_sim.teleop`: phím, IK đầu tay, chế độ (AC 1)
- [ ] 2. Node `denso_teleop` (AC 2)
- [ ] 3. Ghi MCAP và metadata (AC 3)
- [ ] 4. Sổ chi phí mỗi phiên (AC 4)
- [ ] 5. 20 demo thử, đo giờ, hướng dẫn (AC 5, 6)

## Phạm vi file

Theo 07 mục 3.1. pr-guard chặn PR sửa file ngoài danh sách này; file story luôn được sửa.

- `packages/denso-sim/src/denso_sim/teleop/`, `packages/denso-sim/tests/teleop/`
- `ros2_ws/src/denso_teleop/`
- `ros2_ws/src/denso_bringup/launch/record.launch.py`, `ros2_ws/src/denso_bringup/launch/teleop.launch.py`
- `docs/g0/teleop-keyboard.md`, `docs/g0/ledger/DA-16.csv`

## Ghi chú cho người làm

- Nguồn: [design MuJoCo](../../superpowers/specs/2026-10-25-denso-mujoco-and-stage-qa-design.md) mục 4; [design chia làn](../../superpowers/specs/2026-10-25-lanes-and-code-structure-design.md) mục 6.
- Chuyển MCAP thành episode bundle thuộc làn Dữ liệu (DA-03), không thuộc story này.
- Demo bàn phím chậm và giật hơn teleop thật; báo riêng. Không commit bản ghi; dữ liệu ở `fwdata/`.

## Kiểm thử

- Chuỗi phím giả cho chuỗi lệnh đúng (test không cần ROS).
- `launch_testing`: ghi 5 giây, MCAP có đủ topic trong bảng.

## Người phụ trách

- Làm: Trần Ngọc Hưng
- Duyệt và merge: Dương Đình Hiếu (người duy nhất, 07 mục 3.4)
- Bình luận: Thông (MCAP)

## Change log

| Ngày | Nội dung | Người |
|---|---|---|
| 25/10/2026 | Tạo story theo design MuJoCo 25/10/2026 mục 11.2 | PO (Hiếu) |
| 25/10/2026 | Viết lại theo design chia làn: teleop qua ROS 2, ra MCAP thay cho ghi bundle trực tiếp | PO (Hiếu) |

## Ghi chép khi làm

- Giờ thực:
- Công cụ AI đã dùng:
- Ghi chú hoàn thành:
- File đã tạo hoặc sửa:
