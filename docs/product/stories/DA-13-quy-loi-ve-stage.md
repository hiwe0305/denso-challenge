# DA-13 · Kiểm hệ thống F-SYS và quy lỗi về stage trong `diagnosis`

## Trạng thái

| Trường | Giá trị |
|---|---|
| Trạng thái | Sẵn sàng (PO duyệt 28/10/2026, từ nháp của Châu ở issue #6) |
| Người làm | Châu |
| Làn | Đánh giá |
| Story PRD | 9.13 · Epic 9 · FR55; [design 27/10/2026](../../superpowers/specs/2026-10-27-g1-psi0-demo-design.md) mục 8.3, 10; spec mục 6.4 |
| Nhãn | [Lõi] · `epic:9` · `gate:G4` · `area:core` |
| Sprint | S3 · **Lịch 3/11/2026:** kéo lên S2: merge trước **10/11/2026** cho phần 6 của demo (thay S3) |
| Ước lượng | 9 giờ (khoảng 8–10, 07 mục 2.2) |
| Phụ thuộc | DA-25 (file mẫu probe, log RTC); DA-09 (probe P1–P4 thật; **3/11/2026:** dời sau demo, phần quy lỗi theo probe của demo chạy trên file mẫu probe của DA-25); DA-08 (cờ T7); `Trace` từ SIMPLE (khoảng 6/11). **3/11/2026:** hợp đồng `TraceStep`, `CameraParams` và 4 file mẫu (issue #31, Long, 6/11); hook `SimpleSim` ghi trace thật (Hiếu, 8/11). Trên psi-data chỉ R3 thân trên tính được; R3 thân dưới, R4, R5 ra CHƯA RÕ vì gói không ghi tín hiệu đo. Trong lúc chờ code trên file mẫu |

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

- [x] 1. Bộ đọc `Trace`, log RTC, kết quả probe qua contracts (AC 1, 3)
- [x] 2. Kiểm thiếu tín hiệu và R3 sai số bám lệnh (AC 1)
- [x] 3. R1, R2 độ trễ và buffer; R4 đồng bộ; R5 camera; R6 hạ tầng (AC 1)
- [x] 4. Cấu hình ngưỡng có hash (AC 2)
- [x] 5. Bảng quy lỗi về stage, bằng chứng gắn kèm (AC 3, 4)
- [x] 6. Test trên lỗi cấy hệ thống và đối chứng sạch (AC 5, 6)
- [x] 7. `api.py`, lệnh `fw eval diag-system` và artifact kết quả của hai bước (AC 1-4). Phạm vi file đã có `api.py`, `cli.py` nhưng không nhiệm vụ con nào dùng tới; phần 6 của demo cần một điểm vào
- [x] 8. Issue Contract change cho bản ghi kết quả (**issue #70**): `DiagnosisFinding.code` của `flywheel.contracts.training` là `Literal` trên T1-T8, O1-O4 nên mã R không vào được `TrainDiagnosis`; 03 mục 4.3 để `CheckResult` trong `meta` của Cluster (Long giữ). Trong lúc chờ, bản ghi nằm trong làn như `ScoreRecord` của DA-36

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
| 3/11/2026 | Hạn mới theo lịch hoàn thiện 13/11/2026 (07 mục 2.4) | PO (Hiếu) |
| 3/11/2026 | Phụ thuộc: hợp đồng `TraceStep`, `CameraParams` (issue #31) và hook `SimpleSim`; nguồn tín hiệu R3–R5 trên psi-data | PO (Hiếu) theo issue #31 |
| 3/11/2026 | DA-09 dời sau demo: probe của demo dùng file mẫu (07 mục 2.4, bản 1.2) | PO (Hiếu) |
| 3/11/2026 | Thêm nhiệm vụ con 7 (`api.py`, `fw eval diag-system`, artifact) và 8 (issue Contract change cho bản ghi kết quả). Nhiệm vụ 1-6 không phủ `api.py`, `cli.py` dù hai file nằm trong phạm vi, và phần 6 của demo cần điểm vào. `TraceStep`, `CameraParams` (issue #31, PR #48) chưa merge nên bộ đọc giữ đúng tên trường của đề xuất, đổi sang contract khi #48 merge | Châu |

## Ghi chép khi làm

- Giờ thực: 15h (nhiệm vụ 1-7; ước lượng story là 9h, vượt vì hai bộ ngưỡng và bảng quy lỗi đều phải có test đối chứng)
- Công cụ AI đã dùng: Claude Code (Opus 5)
- Ghi chú hoàn thành: AC 1-6 đạt trên trace tổng hợp và file mẫu probe của testkit. Chưa chạy trên `Trace` thật của SIMPLE (hook của Hiếu, 8/11) và chưa chạy trên probe thật (DA-09 dời sau demo). R5 ra CHƯA RÕ tới khi G0 ghim bản tham chiếu camera; `reference_sha256` trong `system.yaml` còn `null`. Mọi ngưỡng trong hai file config là giả định, cách hiệu chỉnh ghi ngay trên dòng.
- File đã tạo hoặc sửa:
  - `packages/flywheel-eval/src/flywheel/eval/diagnosis/system/`: `reader.py`, `verdict.py`, `signals.py`, `tracking.py`, `runtime.py`, `check.py`, `artifact.py`
  - `packages/flywheel-eval/src/flywheel/eval/diagnosis/stage/`: `attribute.py`, `artifact.py`
  - `packages/flywheel-eval/src/flywheel/eval/`: `config.py`, `api.py`, `cli.py`
  - `configs/eval/diagnosis/system.yaml`, `configs/eval/diagnosis/stage.yaml`
  - `packages/flywheel-eval/tests/unit/diagnosis/system/`, `packages/flywheel-eval/tests/unit/diagnosis/stage/`, `packages/flywheel-eval/tests/contract/diagnosis/system/`
