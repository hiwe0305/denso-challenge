# DA-17 · Phát lại action trên MuJoCo

## Trạng thái

| Trường | Giá trị |
|---|---|
| Trạng thái | Sẵn sàng (PO duyệt 25/10/2026 theo design 25/10/2026) |
| Người làm | Châu |
| Story PRD | Story mới của [design 25/10/2026](../../superpowers/specs/2026-10-25-denso-mujoco-and-stage-qa-design.md) mục 11.2 · Epic 9 |
| Nhãn | [Adapter] · `epic:9` · `gate:G1` · `area:data` |
| Sprint | S1–S2 |
| Ước lượng | 10 giờ (khoảng 8–12, ước lượng của SM) |
| Phụ thuộc | DA-15 nhiệm vụ con 1 (MJCF tối thiểu). Code trên episode mẫu trong lúc chờ teleop thật |

## Story

Là kỹ sư dữ liệu, tôi muốn phát lại action của mọi episode trên MuJoCo, để biết dữ liệu đúng trước khi tốn GPU train.

## Tiêu chí chấp nhận

1. Chế độ động học: đặt `qpos` theo state đã ghi từng khung; bắt sai ánh xạ khớp, sai đơn vị, vượt giới hạn khớp, tự va chạm, ảnh lệch thời gian với state; ra danh sách khung lỗi.
2. Chế độ động lực học: từ state đầu, áp action đã ghi qua bộ điều khiển; đo sai lệch state theo thời gian và theo nhóm action, thời điểm đóng mở gripper, kết quả vị từ thành công khi phát lại.
3. Video ghép cạnh nhau: phát lại so với video gốc của episode.
4. Ngưỡng sai lệch động lực học hiệu chỉnh từ episode thành công (phân vị 99), như spec mục 4.4; episode trượt động học bị đánh dấu loại, trượt động lực học bị đánh dấu cho kỹ sư xem.
5. Đầu ra là tệp JSON theo episode mà `qa` đọc được; phát lại được cả action dự đoán của policy từ cùng state đầu (cho Agent QA/QC, DA-20).
6. Hiện thực `SimulatorAdapter.replay()` của `DensoMujocoSim`.

## Nhiệm vụ

- [ ] 1. Phát lại động học, danh sách khung lỗi (AC 1)
- [ ] 2. Phát lại động lực học, sai lệch theo nhóm (AC 2)
- [ ] 3. Video ghép (AC 3)
- [ ] 4. Hiệu chỉnh ngưỡng trên episode thành công (AC 4)
- [ ] 5. Tệp kết quả cho `qa`, phát lại action dự đoán, `replay()` (AC 5, 6)

## Phạm vi file

Theo 07 mục 3.1. pr-guard chặn PR sửa file ngoài danh sách này; file story luôn được sửa.

- `packages/flywheel-mujoco/src/flywheel_mujoco/replay/`
- `packages/flywheel-mujoco/tests/replay/`
- `docs/g0/replay.md`

## Ghi chú cho người làm

- Nguồn: [design 25/10](../../superpowers/specs/2026-10-25-denso-mujoco-and-stage-qa-design.md) mục 5.4, 7.2; 03 mục 5.2 (`replay()`).
- Cài lỗi cố ý vào episode mẫu (đảo dấu một khớp, sai đơn vị độ và radian, lệch 2 khung ảnh) để chứng minh phép kiểm bắt được.
- Video egocentric chỉ phát lại được sau khi chuyển sang robot; không thuộc story này.

## Kiểm thử

- Ba lỗi cấy ở ghi chú đều bị bắt; episode sạch không bị đánh dấu.
- Phát lại động học một demo DA-16 cho video khớp video gốc.

## Người phụ trách

- Làm: Trần Trịnh Hoàng Châu
- Duyệt và merge: Dương Đình Hiếu (người duy nhất, 07 mục 3.4)
- Bình luận: Hưng (MJCF), Thông (QA)

## Change log

| Ngày | Nội dung | Người |
|---|---|---|
| 25/10/2026 | Tạo story theo design 25/10/2026 mục 11.2 | PO (Hiếu) |

## Ghi chép khi làm

- Giờ thực:
- Công cụ AI đã dùng:
- Ghi chú hoàn thành:
- File đã tạo hoặc sửa:
