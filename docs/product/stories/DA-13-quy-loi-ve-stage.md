# DA-13 · Kiểm hệ thống F-SYS và quy lỗi về stage trong `diagnosis`

## Trạng thái

| Trường | Giá trị |
|---|---|
| Trạng thái | Sẵn sàng (PO duyệt 28/10/2026, từ nháp của Châu ở issue #6) |
| Người làm | Châu |
| Làn | Đánh giá |
| Story PRD | 9.13 · Epic 9 · FR55; [design 27/10/2026](../../superpowers/specs/2026-10-27-g1-psi0-demo-design.md) mục 8.3, 10; spec mục 6.4 |
| Nhãn | [Lõi] · `epic:9` · `gate:G4` · `area:core` |
| Sprint | S3 |
| Ước lượng | 9 giờ (khoảng 8–10, 07 mục 2.2) |
| Phụ thuộc | DA-25 (file mẫu probe, log RTC); DA-09 (probe P1–P4 thật); DA-08 (cờ T7); `Trace` từ SIMPLE (khoảng 6/11). Trong lúc chờ code trên file mẫu |

## Story

Là kỹ sư đánh giá, tôi muốn mỗi cụm lỗi closed-loop được kiểm hệ thống trước (R1–R6), rồi gắn giả thuyết về stage của Ψ₀ gây lỗi kèm bằng chứng probe, để evidence card chỉ đề xuất dữ liệu khi lỗi không đến từ hệ thống.

## Tiêu chí chấp nhận

1. Kiểm F-SYS chỉ từ log, đúng thứ tự spec mục 6.4: thiếu tín hiệu → sai số bám lệnh (R3, tách thân trên và thân dưới) → độ trễ (R1, R2) → đồng bộ cảm biến (R4) → camera chuẩn (R5). Thiếu tín hiệu cho ra CHƯA RÕ. R6 (server lỗi) ghi `infra_status`, không tính là lỗi policy.
2. Ngưỡng τ_track, τ_lat, τ_sync và bản tham chiếu camera nằm trong `configs/eval/diagnosis/system.yaml`, có hash; τ lấy phân vị 99 trên episode teleop thành công hoặc lần chạy chuẩn G0, ghi cách tính.
3. Cụm đã qua kiểm hệ thống và kiểm dữ liệu được gắn giả thuyết stage theo bảng quy lỗi (P1, P3, P4, T7, ngoài miền), mỗi giả thuyết kèm bằng chứng: probe nào, trên khung hình hay episode nào, giá trị.
4. Giả thuyết là đề xuất cho kỹ sư xác nhận trên evidence card; không tự chuyển thành can thiệp.
5. Trên bộ lỗi cấy hệ thống: trễ camera ra LỖI ĐỒNG BỘ, lệch calibration ra LỖI CALIBRATION; episode sạch không bị báo lỗi hệ thống (spec mục 7.6).
6. Chạy trên CPU với `Trace` và kết quả probe mẫu của testkit.

## Nhiệm vụ

- [ ] 1. Bộ đọc `Trace`, log RTC, kết quả probe qua contracts (AC 1, 3)
- [ ] 2. Kiểm thiếu tín hiệu và R3 sai số bám lệnh (AC 1)
- [ ] 3. R1, R2 độ trễ và buffer; R4 đồng bộ; R5 camera; R6 hạ tầng (AC 1)
- [ ] 4. Cấu hình ngưỡng có hash (AC 2)
- [ ] 5. Bảng quy lỗi về stage, bằng chứng gắn kèm (AC 3, 4)
- [ ] 6. Test trên lỗi cấy hệ thống và đối chứng sạch (AC 5, 6)

## Phạm vi file

Theo 07 mục 3.1. pr-guard chặn PR sửa file ngoài danh sách này; file story luôn được sửa.

- `packages/flywheel-eval/src/flywheel/eval/diagnosis/system/`, `packages/flywheel-eval/src/flywheel/eval/diagnosis/stage/`
- `packages/flywheel-eval/src/flywheel/eval/api.py`, `packages/flywheel-eval/src/flywheel/eval/cli.py`, `packages/flywheel-eval/src/flywheel/eval/config.py`
- `packages/flywheel-eval/tests/unit/diagnosis/system/`, `packages/flywheel-eval/tests/unit/diagnosis/stage/`
- `configs/eval/diagnosis/system.yaml`, `configs/eval/diagnosis/stage.yaml`

## Ghi chú cho người làm

- Nguồn: spec mục 6.4 (thứ tự kiểm hệ thống, bước 4b), 7.6 (nghiệm thu trên lỗi cấy); design 27/10 mục 8.3, 10.
- **Bảng quy lỗi về stage** [Đã chốt 30/10/2026]: dùng một bảng chung ở spec v10.5 mục 6.4 và design mục 10 (năm dòng: Stage 1, Stage 3 học action, lệch phân phối, quên, ngoài miền). Dòng Stage 1 chỉ ghi nhận và báo cáo, không đề xuất can thiệp dữ liệu. Bảng vẫn để trong `stage.yaml` để đổi không cần sửa mã, nhưng chỉ một bản, không có khóa chọn biến thể.
- Trường "lệnh gửi" và "trạng thái đo" của WBC chốt ở G0 theo agent `psi0_decoupled_wbc` (spec 6.4); trước đó dùng trường của `Trace` mẫu.
- Chỉ import nhân; `diagnosis/` dùng chung với DA-08: story này chỉ sửa `diagnosis/system/` và `diagnosis/stage/`.

## Kiểm thử

- Lỗi cấy hệ thống ra đúng lớp; episode sạch không bị báo; chạy CPU.

## Người phụ trách

- Làm: Trần Trịnh Hoàng Châu
- Duyệt và merge: Dương Đình Hiếu (người duy nhất, 07 mục 3.4)
- Bình luận: Hiếu (DA-09 probe, `Trace`), Long (`decide`, evidence card), Thông (bộ lỗi cấy DA-27)

## Change log

| Ngày | Nội dung | Người |
|---|---|---|
| 28/10/2026 | Nháp story theo spec mục 6.4 và design 27/10 mục 10 | Châu (chờ SM, PO) |
| 28/10/2026 | Đưa nháp của Châu (issue #6) vào repo; nhãn theo 02 bản 0.5 (story 9.13, Epic 9, cổng G4). Bảng quy lỗi về stage (spec 6.4 khác design mục 10) chưa chốt, để trong `stage.yaml` | PO (Hiếu) |
| 30/10/2026 | Chốt bảng quy lỗi về stage theo spec v10.5 mục 6.4 (khớp design mục 10); sửa ghi chú cho người làm | PO (Hiếu) |

## Ghi chép khi làm

- Giờ thực:
- Công cụ AI đã dùng:
- Ghi chú hoàn thành:
- File đã tạo hoặc sửa:
