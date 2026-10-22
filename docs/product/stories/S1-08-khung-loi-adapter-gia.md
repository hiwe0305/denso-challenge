# S1-08 · Khung lõi chạy trên adapter giả

## Trạng thái

| Trường | Giá trị |
|---|---|
| Trạng thái | Sẵn sàng (PO duyệt 22/10/2026) |
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

- [ ] 1. Protocol và kiểu dữ liệu (AC 1, 2)
  - [ ] 1.1 Ngày 1–2: thống nhất với Thông ranh giới file trong `contracts` (Long: `protocols.py`, kiểu request, result; Thông: `base.py`, thực thể)
  - [ ] 1.2 Viết 6 Protocol và kiểu capability
  - [ ] 1.3 Viết kiểu v0 tối thiểu, ghi chú sẽ thay ở S2
- [ ] 2. Bộ giả (AC 3)
  - [ ] 2.1 `FakeSim2D`: bài gắp đặt 2D tất định, vector điều kiện nhỏ
  - [ ] 2.2 `FakePolicy`, `FakeTrainer`, `FakeGenerator`, `FakeTeleop`
  - [ ] 2.3 `ToyPickPlace`
- [ ] 3. Vòng rỗng end-to-end và marker `e2e_fake` (AC 4)
- [ ] 4. Contract test v0 (AC 5)
- [ ] 5. Kiểm import-linter (AC 6)

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

## Ghi chép khi làm

- Giờ thực:
- Công cụ AI đã dùng:
- Ghi chú hoàn thành:
- File đã tạo hoặc sửa:
