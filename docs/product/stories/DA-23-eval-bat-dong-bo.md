# DA-23 · Runner eval đồng bộ và bất đồng bộ

## Trạng thái

| Trường | Giá trị |
|---|---|
| Trạng thái | Sẵn sàng (PO duyệt 25/10/2026; sửa theo design chia làn cùng ngày) |
| Người làm | Long |
| Làn | Vòng quyết định |
| Story PRD | Story mới của [design MuJoCo 25/10/2026](../../superpowers/specs/2026-10-25-denso-mujoco-and-stage-qa-design.md) và [design chia làn](../../superpowers/specs/2026-10-25-lanes-and-code-structure-design.md) · Epic 9 |
| Nhãn | [Lõi] · `epic:9` · `area:core` |
| Sprint | S2 |
| Ước lượng | 10 giờ (khoảng 8–12, ước lượng của SM) |
| Phụ thuộc | Schema `RolloutRequest.timing`, log RTC (DA-25). Code trên simulator và policy giả của testkit có độ trễ giả. PR `chore-restructure` (07 mục 3.6, hết 27/10) tạo khung package `flywheel-loop` |

## Story

Là người vận hành vòng, tôi muốn runner chạy closed-loop eval ở cả hai chế độ và gom log inference, để chỉ số chính của mọi nhánh lấy ở chế độ bất đồng bộ và lỗi do trễ đi vào kiểm hệ thống.

## Tiêu chí chấp nhận

1. Runner phát `RolloutRequest` với `timing = sync` hoặc `async`; `async` kèm `latency_profile_ref` lấy từ log inference thật.
2. Gom log RTC của mỗi rollout vào thư mục job, đúng schema; gắn với `Trace`.
3. Demo với simulator và policy giả có độ trễ: `sync` đạt, `async` lộ lỗi; với độ trễ bằng 0 hai chế độ cho cùng kết quả trên cùng seed.
4. RunPlan khai chế độ eval; mặc định chỉ số chính ở `async` (03 ADR-20).

## Nhiệm vụ

- [ ] 1. Hai chế độ trong runner (AC 1)
- [ ] 2. Gom log RTC (AC 2)
- [ ] 3. Demo với bộ giả có độ trễ (AC 3)
- [ ] 4. Khai chế độ trong RunPlan (AC 4)

## Phạm vi file

Theo 07 mục 3.1. pr-guard chặn PR sửa file ngoài danh sách này; file story luôn được sửa.

- `packages/flywheel-loop/src/flywheel/loop/runner/`
- `packages/flywheel-loop/tests/unit/runner/`, `packages/flywheel-loop/tests/contract/runner/`
- `configs/loop/eval.yaml`
- `docs/g0/async-eval.md`

## Ghi chú cho người làm

- Nguồn: [design MuJoCo](../../superpowers/specs/2026-10-25-denso-mujoco-and-stage-qa-design.md) mục 7.3; [design chia làn](../../superpowers/specs/2026-10-25-lanes-and-code-structure-design.md) mục 3.2; 03 ADR-20.
- Chỉ import nhân (`flywheel.contracts`, `flywheel.store`, `flywheel.testkit`); không import làn khác hay adapter (03 mục 7.3). Thiếu trường trong schema thì báo Hiếu mở PR hợp đồng, không thêm trường tạm.
- `timing` của sim thuộc DA-15; client RTC thuộc DA-19; dòng thời gian RTC dựng trong DA-20.

## Kiểm thử

- Với độ trễ giả bằng 0, hai chế độ cho cùng kết quả trên cùng seed.

## Người phụ trách

- Làm: Nguyễn Thăng Long
- Duyệt và merge: Dương Đình Hiếu (người duy nhất, 07 mục 3.4)
- Bình luận: Hưng (`timing`), Hiếu (client RTC), Châu (dòng thời gian)

## Change log

| Ngày | Nội dung | Người |
|---|---|---|
| 25/10/2026 | Tạo story theo design MuJoCo 25/10/2026 mục 11.2 | PO (Hiếu) |
| 25/10/2026 | Viết lại theo design chia làn: chuyển sang làn Vòng; tách `timing` sang DA-15, client RTC sang DA-19 | PO (Hiếu) |

## Ghi chép khi làm

- Giờ thực:
- Công cụ AI đã dùng:
- Ghi chú hoàn thành:
- File đã tạo hoặc sửa:
