# DA-37 · Hiệu chỉnh scorer và ngưỡng τ_track, τ_sync

## Trạng thái

| Trường | Giá trị |
|---|---|
| Trạng thái | Nháp (Châu viết 2/11/2026; PO đặt mã DA-37 ngày 3/11/2026) |
| Người làm | Châu |
| Làn | Đánh giá (`flywheel-eval`) |
| Story PRD | 3.5 · Epic 3 · FR18; [spec v10.5](../../spec-v10-failure-to-data.md) mục 5.3, 6.4 |
| Nhãn | [Lõi] · `epic:3` · `gate:G1` · `area:core` |
| Sprint | **Sau 13/11/2026** (sau demo, 07 mục 2.4) |
| Ước lượng | 12 giờ (04 mục 4.2, ước lượng) |
| Phụ thuộc | DA-36 (khung scorer); 3.2 (runner, Long) và 3.4 (`TaskDefinition` của task chính, Hưng) theo 04 mục 4.2; `Trace` thật của SIMPLE (hợp đồng `TraceStep` 6/11, Long, #31; hook `SimpleSim` 8/11, Hiếu) và 100 episode có cờ `check_success`; Hiếu gán nhãn 20 episode thất bại (04 mục 3.4, 12 giờ ngoài story) |

## Story

Là kỹ sư đánh giá, tôi muốn đối chiếu scorer với cờ thành công của SIMPLE và hiệu chỉnh τ_track, τ_sync từ demo teleop thành công, để tin được bước hỏng mà scorer gán và để kiểm hệ thống của DA-13 có ngưỡng thật thay vì `null`.

## Tiêu chí chấp nhận

1. Trên 100 episode gồm cả thành công và thất bại, kết luận toàn task của scorer trùng cờ `check_success` của SIMPLE **≥ 95%** (điều kiện qua G1, 04 mục 4.2).
2. Báo cáo hiệu chỉnh (FR18) liệt kê **mọi episode lệch** kèm lý do lệch, để kỹ sư xem được; báo cáo lưu qua kho (`flywheel.store`) và có hash của scorer, cấu hình vị từ và release đã dùng.
3. Kỹ sư (Hiếu) xem 20 episode thất bại và xác nhận bước hỏng; kết quả lưu trong catalog, không nằm rời trong một file tạm.
4. **τ_track** (thân trên và thân dưới, tách riêng theo spec mục 6.4) và **τ_sync** hiệu chỉnh từ **phân vị 99** trên episode teleop thành công; τ_lat từ lần chạy chuẩn ở G0. Mỗi giá trị ghi kèm **số mẫu đã dùng** và cách tính, không chỉ con số: với episode dưới 100 mẫu thì p99 gần như là giá trị lớn nhất, nên số mẫu là phần của bằng chứng.
5. Giá trị đã hiệu chỉnh vào `configs/eval/diagnosis/system.yaml` (thay `null` của DA-13) và vào RunPlan; `null` trước đó nghĩa là **chưa hiệu chỉnh** nên bộ kiểm ghi `skipped`, sau khi hiệu chỉnh mới thực sự kiểm.
6. Chạy lại được: cùng bộ episode và cùng cấu hình cho cùng báo cáo và cùng τ, có test trên một bộ nhỏ dựng trong test.

## Nhiệm vụ

- [ ] 1. Lệnh đối chiếu scorer với cờ SIMPLE trên một tập episode, báo cáo lệch (AC 1, 2)
- [ ] 2. Lưu nhãn xác nhận của kỹ sư vào catalog (AC 3)
- [ ] 3. Tính τ_track thân trên và thân dưới theo phân vị 99, kèm số mẫu (AC 4)
- [ ] 4. Tính τ_sync và ghi τ_lat của G0, kèm số mẫu (AC 4)
- [ ] 5. Ghi giá trị vào `system.yaml` và RunPlan, bỏ `null` (AC 5)
- [ ] 6. Test chạy lại cho kết quả trùng trên bộ episode nhỏ (AC 6)

## Phạm vi file

Theo 07 mục 3.1. pr-guard chặn PR sửa file ngoài danh sách này; file story luôn được sửa.

- `packages/flywheel-eval/src/flywheel/eval/scorer/`
- `packages/flywheel-eval/src/flywheel/eval/api.py`, `packages/flywheel-eval/src/flywheel/eval/cli.py`, `packages/flywheel-eval/src/flywheel/eval/config.py`
- `packages/flywheel-eval/tests/unit/scorer/`, `packages/flywheel-eval/tests/contract/scorer/`
- `configs/eval/scorer/`, `configs/eval/diagnosis/system.yaml`
- `docs/g0/ledger/DA-37.csv`

## Chỗ cần quyết hoặc chờ người khác

1. **`configs/eval/diagnosis/system.yaml` là file của DA-13**, cùng người làm (Châu) nên không vướng chủ file, nhưng hai story cùng sửa một file: đề nghị DA-13 tạo file với `null`, DA-37 chỉ thay giá trị, và không story nào đổi cấu trúc khóa của story kia.
2. **100 episode có cờ `check_success`** cần `Trace` thật của SIMPLE (hợp đồng `TraceStep` 6/11, hook `SimpleSim` 8/11) và một lần chạy rollout. Trước đó chỉ làm được nhiệm vụ 1 và 6 trên bộ episode dựng trong test.
3. **20 nhãn của Hiếu** là việc ngoài story của Hiếu (04 mục 3.4). Nếu chậm thì AC 3 chậm theo; AC 1 và AC 4 không chờ nhãn.
4. τ_track cần trường "lệnh gửi" và "trạng thái đo" của WBC — **cùng hợp đồng `Trace` mà DA-13 đang chờ** (issue hợp đồng `Trace` cho R3, R4, R5). Hai story chờ cùng một thứ; nên chốt hợp đồng một lần.

## Ghi chú cho người làm

- Chỉ import nhân; không chạy simulator trong bước tính. Việc chạy rollout để lấy 100 episode thuộc `runner` của Long và adapter của Hưng, không thuộc story này.
- Báo cáo hiệu chỉnh là artifact có hash, append-only như mọi báo cáo khác: chạy lại ghi bản ghi mới, không ghi đè bản cũ.
- Scorer **đóng băng cuối S4** (điều kiện qua G3, 04 mục 4.4). Sau khi đóng băng, mọi thay đổi vị từ hay ngưỡng phải có `Decision` và chạy lại baseline.
- Chỉ số chính ở holdout vẫn là cờ `check_success` của SIMPLE, không phải scorer (03 ADR-14).

## Kiểm thử

- `uv run pytest packages/flywheel-eval/tests/unit/scorer packages/flywheel-eval/tests/contract/scorer`
- `uv run ruff check`, `uv run mypy`, `uv run lint-imports` theo README gốc.

## Người phụ trách

- Làm: Trần Trịnh Hoàng Châu
- Duyệt và merge: Dương Đình Hiếu (người duy nhất, 07 mục 3.4)
- Bình luận: Hiếu (20 nhãn, cờ SIMPLE, τ_lat của G0), Long (`Score`, catalog, RunPlan), Hưng (rollout trên SIMPLE), Thông (mã story)

## Change log

| Ngày | Nội dung | Người |
|---|---|---|
| 3/11/2026 | Đặt mã DA-37; thêm phụ thuộc 3.2 và 3.4; dời sau 13/11 theo 07 mục 2.4; báo cáo hiệu chỉnh lưu qua kho thay `docs/g0/scorer/` | PO (Hiếu) |
| 2/11/2026 | Nháp story theo PRD 3.5, spec mục 5.3, 6.4 và 04 mục 4.2; nêu bốn chỗ chờ | Châu (chờ SM, PO) |

## Ghi chép khi làm

- Giờ thực:
- Công cụ AI đã dùng:
- Ghi chú hoàn thành:
- File đã tạo hoặc sửa:
