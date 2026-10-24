# S1-08 · Khung lõi chạy trên adapter giả

## Trạng thái

| Trường | Giá trị |
|---|---|
| Trạng thái | Sẵn sàng (PO duyệt 22/10/2026) |
| Người làm | Long |
| Story PRD | 1.7 · Epic 1 |
| Nhãn | [Lõi] · `epic:1` · `gate:G0` · `area:data` |
| Sprint | S1 (tuần 1–2) |
| Ước lượng | 18 giờ |
| Phụ thuộc | S1-01. Dùng chung `contracts` với S1-10 |

## Story

Là kỹ sư data xây lõi, tôi muốn một vòng rỗng chạy → chấm → chẩn đoán → quyết định → thu → train → cổng trên adapter giả, để các module lõi phát triển song song với G0 mà không chờ SIMPLE và Ψ₀.

## Tiêu chí chấp nhận

1. `flywheel.contracts` có 6 Protocol v0 theo 03 §5.2 bản 0.3 (SimulatorAdapter, PolicyAdapter, TrainerAdapter, GeneratorAdapter, TeleopSource, TaskDefinition), gắn `@runtime_checkable`, có `AdapterInfo`, `SimCapabilities` (gồm `restore_state`, `visual_override`, `fault_injection`, `camera_params`, `replay`, `max_parallel`, `levels`), `GenCapabilities` (gồm `sim_rollout`, `variant`, `recovery_from_state`, `plan`, `controller`). SimulatorAdapter có `control_spec()` trả `ControlSpec` (ADR-15); TaskDefinition có `family`, mỗi kiểu lỗi có `failure_class`.
2. Có kiểu v0 tối thiểu cho `RolloutRequest`, `RolloutResult`, `TraceRef`, `StateRef`, `Condition`, đủ cho vòng rỗng. Khi S1-10 có model thực thể, dùng model đó thay kiểu v0.
3. `packages/flywheel-fakes` có `FakeSim2D` (tất định theo seed), `FakePolicy`, `FakeTrainer`, `FakeGenerator`, `FakeTeleop`, `ToyPickPlace` (TaskDefinition 2–3 bước); chạy trên CPU.
4. Một lệnh (`uv run pytest -m e2e_fake`) chạy vòng rỗng end-to-end; mỗi bước để lại bản ghi JSON trong thư mục tạm; xong dưới 10 phút trong CI, mục tiêu dưới 2 phút.
5. Bộ contract test dùng chung v0 trong `flywheel.testing`: khai năng lực trung thực, idempotent theo `job_id`, lỗi hạ tầng nằm ở `infra_status`. Chạy với bộ giả trong CI.
6. Lõi không import adapter thật; import-linter xanh.

## Nhiệm vụ

- [x] 1. Protocol và kiểu dữ liệu (AC 1, 2)
  - [x] 1.1 Ngày 1–2: thống nhất với Thông ranh giới file trong `contracts` (Long: `protocols.py`, kiểu request, result; Thông: `base.py`, thực thể)
  - [x] 1.2 Viết 6 Protocol và kiểu capability
  - [x] 1.3 Viết kiểu v0 tối thiểu, ghi chú sẽ thay ở S2
- [x] 2. Bộ giả (AC 3)
  - [x] 2.1 `FakeSim2D`: bài gắp đặt 2D tất định, vector điều kiện nhỏ
  - [x] 2.2 `FakePolicy`, `FakeTrainer`, `FakeGenerator`, `FakeTeleop`
  - [x] 2.3 `ToyPickPlace`
- [x] 3. Vòng rỗng end-to-end và marker `e2e_fake` (AC 4)
- [x] 4. Contract test v0 (AC 5)
- [ ] 5. Kiểm import-linter (AC 6)

## Phạm vi file

Theo 07 mục 3.1. pr-guard chặn PR sửa file ngoài danh sách này; file story luôn được sửa.

- `packages/flywheel/src/flywheel/contracts/protocols.py`, `packages/flywheel/src/flywheel/contracts/v0.py`
- `packages/flywheel/src/flywheel/contracts/__init__.py`: story này giữ file export; S1-10 không sửa, mã khác import thực thể từ module base
- `packages/flywheel/src/flywheel/testing/`
- `packages/flywheel/tests/e2e/`
- `packages/flywheel-fakes/`

## Ghi chú cho người làm

- Nguồn: 02 · 1.7, NFR2, mục 4 (chiến lược test); 03 §2.2, §2.3 (luồng một vòng), §5.2, §5.3 (11 điều hợp đồng), §5.4 (bộ giả), §11; 05 mục 3 (bộ giả cần nhưng chưa đủ).
- Phụ thuộc vòng 1.7 ↔ 2.1 đã gỡ (04 P17): story này không chờ S1-10; dùng kiểu v0 và chuyển sang model của S1-10 khi có.
- Chẩn đoán, quyết định ở vòng rỗng chỉ là hàm giả trả kết quả cố định; logic thật làm từ S3. Không làm sớm cấy lỗi trong bộ giả; bộ lỗi cấy chuẩn do Thông dựng ở S3 để tránh tự kiểm chính mình.
- Pydantic v2; chưa cần xuất JSON Schema ở story này.
- `FakeSim2D` ở story này chỉ cần trả `ControlSpec` và tham số camera giả cho đủ hợp đồng; cấy lỗi đồng bộ, camera, ngoài miền làm ở S3–S4 theo bộ lỗi cấy chuẩn của Thông (03 §11).
- File sẽ tạo: `packages/flywheel/src/flywheel/contracts/protocols.py`, `contracts/v0.py`, `packages/flywheel/src/flywheel/testing/contract_suite.py`, `packages/flywheel-fakes/src/flywheel_fakes/*.py`, `packages/flywheel/tests/e2e/test_fake_loop.py`, `packages/flywheel-fakes/tests/test_contracts.py`.

## Kiểm thử

- Unit test cho từng adapter giả: cùng seed cho cùng kết quả.
- Contract suite chạy với bộ giả; thử một adapter giả cố ý khai sai năng lực và suite phải bắt được.
- E2E: vòng rỗng xanh trong CI; đo thời gian và ghi vào Ghi chép khi làm.

## Người phụ trách

- Làm: Nguyễn Thăng Long
- Review: Dương Tiến Thông; Trần Trịnh Hoàng Châu xem phần TaskDefinition
- Dự phòng: Dương Tiến Thông

## Change log

| Ngày | Nội dung | Người |
|---|---|---|
| 22/10/2026 | Tạo story từ 02 · 1.7; ghi cách gỡ phụ thuộc với S1-10 | SM (Bob), PO (Sarah) duyệt |
| 22/10/2026 | Đồng bộ Protocol với 03 §5.2 bản 0.3: `control_spec`, cờ `camera_params`, `controller`, `family`, `failure_class`. AC của 02 · 1.7 không đổi; ước lượng giữ 18 giờ | SM (Bob) theo 06 |
| 24/10/2026 | Thêm mục Phạm vi file; story giữ file export của `contracts`. AC không đổi | PO (Hiếu) |

## Ghi chép khi làm

- Giờ thực:
- Công cụ AI đã dùng:
- Ghi chú hoàn thành:
- Bằng chứng 1.1: đối chiếu phạm vi S1-08 và S1-10 bằng script; S1-08 giữ `protocols.py`, `v0.py`, S1-10 giữ `base.py`, `entities`; 6/6 kiểm tra ranh giới đạt.
- Bằng chứng 1.2: `pytest packages/flywheel/tests/e2e/test_protocols.py -q` đạt 9 test; Ruff đạt; mypy đạt trên 19 file nguồn.
- Bằng chứng 1.3: test Protocol và model v0 đạt 14 test; Ruff đạt; mypy đạt trên 20 file nguồn. `v0.py` ghi rõ model tạm sẽ được thay bằng model chuẩn của S1-10 ở S2.
- Bằng chứng 2.1: unit test `FakeSim2D` đạt 5 test, gồm cùng seed cho condition giống nhau, trace trùng từng byte và idempotent theo `job_id`; Ruff và mypy đạt.
- Bằng chứng 2.2: toàn bộ unit test package fakes đạt 12 test; bốn adapter đạt kiểm tra runtime Protocol và kiểm tra cùng seed/đầu vào cho cùng kết quả; Ruff và mypy đạt.
- Bằng chứng 2.3: toàn bộ unit test package fakes đạt 17 test trong 80,67 giây; `ToyPickPlace` đạt runtime Protocol, ba bước/ba kiểu lỗi có `failure_class`, đánh giá thuần và tất định; Ruff và mypy đạt.
- Bằng chứng 3: `pytest -m e2e_fake -q` đạt 1 test, 19 test không chọn, trong 0,79 giây; đủ 7 bản ghi JSON cho run, score, diagnose, decide, acquire, train, gate; Ruff và mypy đạt.
- Bằng chứng 4: contract suite dùng chung đạt 5 test; kiểm capability, idempotent theo `job_id`, tách lỗi hạ tầng khỏi kết quả task; suite bắt đúng `LyingCameraSimulator` khai `camera_params=True` nhưng không trả hash; Ruff và mypy đạt.
- File đã tạo hoặc sửa:
