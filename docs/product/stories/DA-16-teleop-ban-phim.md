# DA-16 · Teleop bàn phím trên MuJoCo

## Trạng thái

| Trường | Giá trị |
|---|---|
| Trạng thái | Sẵn sàng (PO duyệt 25/10/2026 theo design 25/10/2026) |
| Người làm | Hưng |
| Story PRD | Story mới của [design 25/10/2026](../../superpowers/specs/2026-10-25-denso-mujoco-and-stage-qa-design.md) mục 11.2 · Epic 9 |
| Nhãn | [Adapter] · `epic:9` · `gate:G0` · `area:data` |
| Sprint | S1 |
| Ước lượng | 12 giờ (khoảng 10–15, ước lượng của SM) |
| Phụ thuộc | DA-15 nhiệm vụ con 1 (MJCF tối thiểu); DA-01 cho định dạng episode, trong lúc chờ dùng episode mẫu của S1-08 |

## Story

Là người thu dữ liệu, tôi muốn điều khiển robot DENSO trong MuJoCo bằng bàn phím và ghi ra episode đúng định dạng chung, để đội tự thu demo teleop cho các nhánh thí nghiệm.

## Tiêu chí chấp nhận

1. Điều khiển theo đầu tay (EEF) qua IK; đế bằng vận tốc; cột nâng, gripper, đầu bằng phím riêng; chuyển chế độ theo nhóm action; bảng phím hiện trên màn hình.
2. Ghi ở tần số điều khiển của `control_spec`; ảnh theo fps camera, mỗi khung có `t_image`; ghi ra episode bundle (03 mục 4) với `source = teleop_keyboard`, người điều khiển, hạt giống điều kiện, phiên bản MJCF.
3. Phím kết thúc thành công hoặc thất bại; phím reset về trạng thái đầu của hạt giống; episode bị hủy giữa chừng vẫn ghi với lý do.
4. Mỗi phiên ghi một mục sổ chi phí: phút người, số episode, số episode đạt vị từ thành công.
5. Đo giờ người cho 20 demo thử trên Level 0 (design 25/10 mục 4.3); ghi trung bình và p90 phút mỗi demo đạt, đầu vào cho kế hoạch thu.
6. Hướng dẫn cho người điều khiển trong `docs/g0/teleop-keyboard.md`.

## Nhiệm vụ

- [ ] 1. Bảng phím, IK đầu tay, chuyển chế độ (AC 1)
- [ ] 2. Ghi episode bundle (AC 2, 3)
- [ ] 3. Mục sổ chi phí mỗi phiên (AC 4)
- [ ] 4. Thu 20 demo thử, đo giờ (AC 5)
- [ ] 5. Hướng dẫn người điều khiển (AC 6)

## Phạm vi file

Theo 07 mục 3.1. pr-guard chặn PR sửa file ngoài danh sách này; file story luôn được sửa.

- `packages/flywheel-mujoco/src/flywheel_mujoco/teleop/`
- `packages/flywheel-mujoco/tests/teleop/`
- `docs/g0/teleop-keyboard.md`, `docs/g0/ledger/DA-16.csv`

## Ghi chú cho người làm

- Nguồn: [design 25/10](../../superpowers/specs/2026-10-25-denso-mujoco-and-stage-qa-design.md) mục 4; 03 mục 4 (bundle); spec mục 4.1 (demo teleop là demo gốc).
- Demo bàn phím chậm và giật hơn teleop thật; báo riêng, không dùng để nói số tuyệt đối về dữ liệu nhà máy.
- Thiết bị khác (gamepad, SpaceMouse) cắm vào cùng giao diện sau; giữ lớp đọc thiết bị tách khỏi lớp ghi.
- Không commit demo; dữ liệu nằm trong `fwdata/`.

## Kiểm thử

- Unit test: chuỗi phím giả cho ra chuỗi lệnh đúng; bundle ghi ra qua validate của `contracts`.
- Phát lại động học (DA-17) một demo thử cho ra video khớp video gốc.

## Người phụ trách

- Làm: Trần Ngọc Hưng
- Duyệt và merge: Dương Đình Hiếu (người duy nhất, 07 mục 3.4)
- Bình luận: Châu (phát lại), Thông (QA teleop)

## Change log

| Ngày | Nội dung | Người |
|---|---|---|
| 25/10/2026 | Tạo story theo design 25/10/2026 mục 11.2 | PO (Hiếu) |

## Ghi chép khi làm

- Giờ thực:
- Công cụ AI đã dùng:
- Ghi chú hoàn thành:
- File đã tạo hoặc sửa:
