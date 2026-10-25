# DA-23 · Eval bất đồng bộ trên MuJoCo và log inference RTC

## Trạng thái

| Trường | Giá trị |
|---|---|
| Trạng thái | Sẵn sàng (PO duyệt 25/10/2026 theo design 25/10/2026) |
| Người làm | Châu |
| Story PRD | Story mới của [design 25/10/2026](../../superpowers/specs/2026-10-25-denso-mujoco-and-stage-qa-design.md) mục 11.2 · Epic 9 |
| Nhãn | [Adapter] · `epic:9` · `area:sim` |
| Sprint | S2 |
| Ước lượng | 12 giờ (khoảng 10–15, ước lượng của SM) |
| Phụ thuộc | DA-15 (env), S1-04 AC 8 (độ trễ trên 3060). Code trên `FakePolicy` có độ trễ giả trong lúc chờ. Khung package: DA-19 nhiệm vụ con 1 |

## Story

Là kỹ sư đánh giá, tôi muốn eval closed-loop chạy cả đồng bộ và bất đồng bộ và ghi log inference RTC, để thấy lỗi do trễ của action chunking trước khi coi nó là lỗi dữ liệu.

## Tiêu chí chấp nhận

1. Hai chế độ của `RolloutRequest.timing`: đồng bộ (sim dừng chờ policy) và bất đồng bộ (sim chạy theo đồng hồ thật, hoặc chèn độ trễ lấy mẫu từ log inference thật).
2. Client RTC ghi mỗi lần suy luận: lúc gửi quan sát, lúc nhận chunk, độ trễ, số action đã tiêu trong lúc chờ (delay d), mức buffer, chỉ số chunk, bước nhảy action ở ranh giới chunk so với trong chunk, lúc buffer cạn.
3. Dòng thời gian RTC dựng thành hình cho DA-20.
4. Demo bằng `FakePolicy` có độ trễ giả: chế độ đồng bộ đạt, chế độ bất đồng bộ lộ lỗi; kiểm hệ thống ghi LỖI RUNTIME.
5. Chạy Ψ₀ trên 3060 nếu S1-04 cho thấy đủ VRAM; nếu không, ghi rõ chỉ số bất đồng bộ đo với độ trễ của phần cứng nào.

## Nhiệm vụ

- [ ] 1. Hai chế độ timing trong runner của env (AC 1)
- [ ] 2. Log RTC phía client (AC 2)
- [ ] 3. Dòng thời gian RTC (AC 3)
- [ ] 4. Demo `FakePolicy` có trễ (AC 4)
- [ ] 5. Chạy với Ψ₀ hoặc ghi giới hạn phần cứng (AC 5)

## Phạm vi file

Theo 07 mục 3.1. pr-guard chặn PR sửa file ngoài danh sách này; file story luôn được sửa.

- `packages/flywheel-mujoco/src/flywheel_mujoco/eval/`
- `packages/flywheel-mujoco/tests/eval/`
- `packages/flywheel-psi0/src/flywheel_psi0/policy/`
- `docs/g0/async-eval.md`

## Ghi chú cho người làm

- Nguồn: [design 25/10](../../superpowers/specs/2026-10-25-denso-mujoco-and-stage-qa-design.md) mục 7.2, 7.3; 03 ADR-20; code RTC của Ψ₀: `real/deploy/psi-inference_rtc.py`, `scripts/deploy/serve_psi0-rtc-*.sh`.
- `RolloutRequest.timing` là thay đổi `contracts`: Long làm PR contract nhỏ trước (07 mục 3.2); trong lúc chờ dùng tham số cục bộ của env.
- Ψ₀ cần khoảng 160 ms mỗi lần suy luận (số tác giả báo); đo lại trên phần cứng của đội.

## Kiểm thử

- Test: với độ trễ giả bằng 0, hai chế độ cho cùng kết quả trên cùng seed.
- Log RTC của demo `FakePolicy` dựng lại đúng dòng thời gian.

## Người phụ trách

- Làm: Trần Trịnh Hoàng Châu
- Duyệt và merge: Dương Đình Hiếu (người duy nhất, 07 mục 3.4)
- Bình luận: Hưng (env), Thông (Agent QA/QC)

## Change log

| Ngày | Nội dung | Người |
|---|---|---|
| 25/10/2026 | Tạo story theo design 25/10/2026 mục 11.2 | PO (Hiếu) |
| 25/10/2026 | Phụ thuộc thêm khung package từ DA-19 nhiệm vụ con 1 | PO (Hiếu) |

## Ghi chép khi làm

- Giờ thực:
- Công cụ AI đã dùng:
- Ghi chú hoàn thành:
- File đã tạo hoặc sửa:
