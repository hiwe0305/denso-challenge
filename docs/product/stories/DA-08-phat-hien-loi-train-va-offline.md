# DA-08 · Bộ phát hiện lỗi train F-TRAIN và lỗi offline F-OFF

## Trạng thái

| Trường | Giá trị |
|---|---|
| Trạng thái | Sẵn sàng (PO duyệt 28/10/2026, từ nháp của Châu ở issue #6) |
| Người làm | Châu |
| Làn | Đánh giá |
| Story PRD | 9.8 · Epic 9 · FR54; [design 27/10/2026](../../superpowers/specs/2026-10-27-g1-psi0-demo-design.md) mục 8.2, 8.3, 10 |
| Nhãn | [Lõi] · `epic:9` · `gate:G2` · `area:core` |
| Sprint | S2–S3 |
| Ước lượng | 10 giờ (khoảng 8–12, 07 mục 2.2) |
| Phụ thuộc | DA-25 (file mẫu, gồm kết quả probe); schema `metrics.jsonl` (chưa có trong DA-25, xem Ghi chú); DA-19 (log thật, khoảng 6/11); DA-09 (kết quả P3, P4 thật). Trong lúc chờ code trên file mẫu của testkit |

## Story

Là kỹ sư đánh giá, tôi muốn mỗi checkpoint được kiểm động học train (T1–T8) và sai số action offline (O1–O4) từ log và probe, để loại checkpoint hỏng trước khi tốn rollout closed-loop và để chuỗi chẩn đoán có bằng chứng từ phía train.

## Tiêu chí chấp nhận

1. Đọc `metrics.jsonl` của một job qua schema trong `flywheel.contracts`, phát hiện T1–T6 và T8 đúng định nghĩa ở design mục 10. Mỗi phát hiện ghi mã lỗi, bước bắt đầu, nhóm action hoặc chiều liên quan (khi có), giá trị đo và ngưỡng.
2. T7 (quên) đọc kết quả P4 của checkpoint và của checkpoint cha; O1–O4 đọc kết quả P3. O4 dùng giới hạn khớp từ `action_layout` của embodiment, không chép số vào mã.
3. Ngưỡng (k, W, x%, N, M, ε và ngưỡng của O1–O4) nằm trong `configs/eval/diagnosis/train.yaml`, có hash. Giá trị chưa hiệu chỉnh ghi `# giả định` kèm nguồn; ngưỡng hiệu chỉnh được từ log của checkpoint công bố thì ghi cách tính.
4. Kết quả là một artifact có schema gắn vào checkpoint (đánh dấu, không xóa). Chỉ T1 được đánh dấu "dừng job"; việc dừng thật do adapter train làm, ngoài phạm vi story này.
5. Lệnh `fw eval diag-train --job <đường dẫn>` in bảng phát hiện và ghi artifact vào kho.
6. Mỗi mã T1–T8, O1–O4 có ít nhất một test dương (log hoặc probe cấy lỗi bắt được) và một test âm (log sạch không bị đánh dấu), chạy trên CPU với file mẫu.

## Nhiệm vụ

- [ ] 1. Bộ đọc `metrics.jsonl` và kết quả probe qua contracts, chuỗi thời gian theo nhóm action (AC 1, 2)
- [ ] 2. T1–T3: phân kỳ, không học, quá khớp (AC 1)
- [ ] 3. T4–T6, T8: mất cân bằng nhóm, chiều chết, sụp mode, gradient bất thường (AC 1)
- [ ] 4. T7 và O1–O4 từ P3, P4 (AC 2)
- [ ] 5. Cấu hình ngưỡng có hash (AC 3)
- [ ] 6. Artifact kết quả, lệnh `fw` (AC 4, 5)
- [ ] 7. Bộ log cấy lỗi và test dương, âm cho từng mã (AC 6)

## Phạm vi file

Theo 07 mục 3.1. pr-guard chặn PR sửa file ngoài danh sách này; file story luôn được sửa.

- `packages/flywheel-eval/src/flywheel/eval/diagnosis/train/`
- `packages/flywheel-eval/src/flywheel/eval/api.py`, `packages/flywheel-eval/src/flywheel/eval/cli.py`, `packages/flywheel-eval/src/flywheel/eval/config.py`
- `packages/flywheel-eval/tests/unit/diagnosis/train/`, `packages/flywheel-eval/tests/contract/diagnosis/train/`
- `configs/eval/diagnosis/train.yaml`

## Ghi chú cho người làm

- Nguồn: design 27/10 mục 8.2 (trường log), 8.3 (probe), 10 (F-TRAIN, F-OFF); spec mục 6.4.
- **Hợp đồng còn thiếu** [Đề xuất]: DA-25 chưa có schema `metrics.jsonl` (DA-19 AC 3 cần "đúng schema") và chưa có artifact kết quả chẩn đoán train. Đã mở issue #5 "Contract change" cho Long và Hiếu; chờ chốt trước 30/10. Không thêm trường tạm trong code làn.
- Chỉ import nhân (`flywheel.contracts`, `flywheel.store`, `flywheel.testkit`); không import `torch` hay adapter Ψ₀. Tính toán trên số đã ghi trong log, không chạy model.
- `diagnosis/` dùng chung với DA-13: story này chỉ sửa `diagnosis/train/`.

## Kiểm thử

- Mỗi mã lỗi có một log hoặc probe cấy lỗi bị bắt và log sạch không bị đánh dấu; chạy CPU, không cần GPU.
- Khi có log thật của DA-19: chạy trên một job fine-tune, ghi số phát hiện vào ghi chép.

## Người phụ trách

- Làm: Trần Trịnh Hoàng Châu
- Duyệt và merge: Dương Đình Hiếu (người duy nhất, 07 mục 3.4)
- Bình luận: Hiếu (DA-19, lớp bọc log), Long (`decide` đọc kết quả), Hưng (Agent QA/QC đọc log train)

## Change log

| Ngày | Nội dung | Người |
|---|---|---|
| 28/10/2026 | Nháp story theo design 27/10 mục 10 và 07 mục 2.2 | Châu (chờ SM, PO) |
| 28/10/2026 | Đưa nháp của Châu (issue #6) vào repo; nhãn theo 02 bản 0.5 (story 9.8, Epic 9, cổng G2); hợp đồng còn thiếu theo dõi ở issue #5 | PO (Hiếu) |

## Ghi chép khi làm

- Giờ thực:
- Công cụ AI đã dùng:
- Ghi chú hoàn thành:
- File đã tạo hoặc sửa:
