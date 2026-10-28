# DA-17 · Kiểm dữ liệu bằng phát lại action trên MuJoCo của SIMPLE

## Trạng thái

| Trường | Giá trị |
|---|---|
| Trạng thái | Sẵn sàng (PO duyệt 25/10/2026; sửa 27/10/2026) |
| Người làm | Thông |
| Làn | Dữ liệu |
| Story PRD | Story của [design 27/10/2026](../../superpowers/specs/2026-10-27-g1-psi0-demo-design.md) mục 6.3 · Epic 9 |
| Nhãn | [Lõi] · `epic:9` · `gate:G1` · `area:data` |
| Sprint | S1–S2 |
| Ước lượng | 9 giờ (khoảng 7–11, ước lượng của SM) |
| Phụ thuộc | DA-25 (schema `ReplayReport`). Gọi `SimulatorAdapter.replay()` qua Protocol; hàm `replay()` của `SimpleSim` thuộc story 3.1a (adapter SIMPLE, S2); trong lúc chờ dùng simulator giả của testkit. PR `chore-restructure` (07 mục 3.6; mở PR 28/10, merge 29/10/2026) tạo khung package `flywheel-data` |

## Story

Là kỹ sư dữ liệu, tôi muốn mọi episode có action robot (psi-data, bàn phím, sinh tự động) được phát lại trên MuJoCo của SIMPLE và so với state đã ghi, để loại dữ liệu sai trước khi tốn GPU train.

## Tiêu chí chấp nhận

1. Gọi `replay()` chế độ động học: liệt kê khung sai ánh xạ khớp, sai đơn vị, vượt giới hạn khớp, tự va chạm, ảnh lệch thời gian với state.
2. Gọi `replay()` chế độ động lực học qua decoupled WBC: sai lệch state theo thời gian và theo nhóm action, thời điểm đóng mở bàn tay, `check_success` khi phát lại.
3. Ngưỡng hiệu chỉnh từ episode thành công (phân vị 99) trong `configs/data/replay.yaml`; trượt động học thì loại, trượt động lực học thì đánh dấu cho kỹ sư.
4. Ra `ReplayReport` đúng schema; bước QA của release đọc report này.
5. Phát lại được action dự đoán của policy từ cùng state đầu (đầu vào cho Agent QA/QC); video ghép cạnh nhau ngoài git.

## Nhiệm vụ

- [ ] 1. Động học và danh sách khung lỗi (AC 1)
- [ ] 2. Động lực học và sai lệch theo nhóm (AC 2)
- [ ] 3. Ngưỡng hiệu chỉnh và cấu hình (AC 3)
- [ ] 4. `ReplayReport` và nối vào QA (AC 4)
- [ ] 5. Phát lại action dự đoán, video (AC 5)

## Phạm vi file

Theo 07 mục 3.1. pr-guard chặn PR sửa file ngoài danh sách này; file story luôn được sửa.

- `packages/flywheel-data/src/flywheel/data/replay_check/`
- `packages/flywheel-data/tests/unit/replay_check/`, `packages/flywheel-data/tests/contract/replay_check/`
- `configs/data/replay.yaml`
- `docs/g0/replay.md`

## Ghi chú cho người làm

- Nguồn: design 27/10 mục 6.3, 10 (D7); 03 mục 7.3 (artifact `ReplayReport`).
- Dữ liệu tuyến B của sinh tự động chạy AMO: phát lại qua bộ điều khiển AMO, không qua WBC (S1-11).
- Chỉ import nhân (`flywheel.contracts`, `flywheel.store`, `flywheel.testkit`); không import làn khác hay adapter (03 mục 7.3). Thiếu trường trong schema thì báo Hiếu mở PR hợp đồng, không thêm trường tạm.
- Cấy lỗi vào episode mẫu (đảo dấu một khớp, sai đơn vị độ và radian, lệch 2 khung ảnh) để chứng minh phép kiểm bắt được.

## Kiểm thử

- Ba lỗi cấy đều bị bắt; episode sạch không bị đánh dấu (chạy với simulator giả, không cần MuJoCo).

## Người phụ trách

- Làm: Dương Tiến Thông
- Duyệt và merge: Dương Đình Hiếu (người duy nhất, 07 mục 3.4)
- Bình luận: người làm story 3.1a (`replay()`), người làm DA-20 (Agent QA/QC đọc report)

## Change log

| Ngày | Nội dung | Người |
|---|---|---|
| 25/10/2026 | Tạo story cho robot DENSO trên MuJoCo | PO (Hiếu) theo design 25/10/2026 (đã xóa) |
| 25/10/2026 | Chuyển sang làn Dữ liệu; hàm `replay()` thuộc DA-15 | PO (Hiếu) theo design chia làn (đã xóa) |
| 27/10/2026 | Đổi sang MuJoCo của SIMPLE trên task hai bàn; `replay()` thuộc story 3.1a; thêm nguồn AMO | PO (Hiếu) theo design 27/10/2026 |
| 28/10/2026 | Sửa hạn PR `chore-restructure` theo 07 mục 3.6 bản 0.6: mở 28/10, merge 29/10 | PO (Hiếu) |

## Ghi chép khi làm

- Giờ thực:
- Công cụ AI đã dùng:
- Ghi chú hoàn thành:
- File đã tạo hoặc sửa:
