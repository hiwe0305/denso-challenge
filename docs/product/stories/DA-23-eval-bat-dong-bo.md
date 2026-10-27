# DA-23 · Runner eval đồng bộ và bất đồng bộ

## Trạng thái

| Trường | Giá trị |
|---|---|
| Trạng thái | Sẵn sàng (PO duyệt 25/10/2026; sửa 27/10/2026) |
| Người làm | Long |
| Làn | Vòng quyết định |
| Story PRD | Story của [design 27/10/2026](../../superpowers/specs/2026-10-27-g1-psi0-demo-design.md) mục 8.5 · Epic 9 |
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
4. RunPlan khai chế độ eval; mặc định chỉ số chính của HS, HT ở `async` (03 ADR-20); G0 và HE khai `sync` để so được với tác giả (design mục 8.5).
5. Chạy được qua `SimpleSim` trên task hai bàn với Ψ₀ thật ở cả hai chế độ, ít nhất 5 episode mỗi chế độ.

## Nhiệm vụ

- [ ] 1. Hai chế độ trong runner (AC 1)
- [ ] 2. Gom log RTC (AC 2)
- [ ] 3. Demo với bộ giả có độ trễ (AC 3)
- [ ] 4. Khai chế độ trong RunPlan (AC 4)
- [ ] 5. Chạy với `SimpleSim` và Ψ₀ thật (AC 5)

## Phạm vi file

Theo 07 mục 3.1. pr-guard chặn PR sửa file ngoài danh sách này; file story luôn được sửa.

- `packages/flywheel-loop/src/flywheel/loop/runner/`
- `packages/flywheel-loop/tests/unit/runner/`, `packages/flywheel-loop/tests/contract/runner/`
- `configs/loop/eval.yaml`
- `docs/g0/async-eval.md`

## Ghi chú cho người làm

- Nguồn: design 27/10 mục 8.5; 03 mục 7.3, ADR-20.
- Chỉ import nhân (`flywheel.contracts`, `flywheel.store`, `flywheel.testkit`); không import làn khác hay adapter (03 mục 7.3). Thiếu trường trong schema thì báo Hiếu mở PR hợp đồng, không thêm trường tạm.
- `timing` phía sim (chèn độ trễ khi bước SIMPLE) thuộc story 3.1a (adapter SIMPLE); client RTC thuộc DA-19; dòng thời gian RTC dựng trong DA-20.

## Kiểm thử

- Với độ trễ giả bằng 0, hai chế độ cho cùng kết quả trên cùng seed.

## Người phụ trách

- Làm: Nguyễn Thăng Long
- Duyệt và merge: Dương Đình Hiếu (người duy nhất, 07 mục 3.4)
- Bình luận: người làm story 3.1a (`timing`), Hiếu (client RTC), người làm DA-20 (dòng thời gian)

## Change log

| Ngày | Nội dung | Người |
|---|---|---|
| 25/10/2026 | Tạo story cho MuJoCo của robot DENSO | PO (Hiếu) theo design 25/10/2026 (đã xóa) |
| 25/10/2026 | Chuyển sang làn Vòng; tách `timing` sang DA-15, client RTC sang DA-19 | PO (Hiếu) theo design chia làn (đã xóa) |
| 27/10/2026 | Đổi sang SIMPLE: `timing` thuộc story 3.1a; G0 và HE ở `sync`; thêm AC 5 và nhiệm vụ con 5 chạy với Ψ₀ thật | PO (Hiếu) theo design 27/10/2026 |

## Ghi chép khi làm

- Giờ thực:
- Công cụ AI đã dùng:
- Ghi chú hoàn thành:
- File đã tạo hoặc sửa:
