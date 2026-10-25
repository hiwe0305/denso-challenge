# DA-25 · Schema và file mẫu cho artifact giữa các làn

## Trạng thái

| Trường | Giá trị |
|---|---|
| Trạng thái | Sẵn sàng (PO duyệt 25/10/2026; sửa theo design chia làn cùng ngày) |
| Người làm | Hiếu |
| Làn | Nhân |
| Story PRD | Story mới của [design MuJoCo 25/10/2026](../../superpowers/specs/2026-10-25-denso-mujoco-and-stage-qa-design.md) và [design chia làn](../../superpowers/specs/2026-10-25-lanes-and-code-structure-design.md) · Epic 9 |
| Nhãn | [Lõi] · `epic:9` · `gate:G0` · `area:core` |
| Sprint | S1, trước 29/10 |
| Ước lượng | 8 giờ (khoảng 6–10, ước lượng của SM) |
| Phụ thuộc | PR `chore-restructure` (hết 27/10). Bảng topic nháp từ DA-24 nhiệm vụ con 5 (nếu chưa có thì dùng bảng ở design chia làn mục 6.4) |

## Story

Là trưởng nhóm giữ nhân, tôi muốn có schema và file mẫu cho mọi artifact mới giữa các làn, để ba làn và Hưng code song song mà không phải hỏi nhau.

## Tiêu chí chấp nhận

1. Schema trong `flywheel.contracts` cho: bảng topic MCAP (tên, kiểu, tần số), `ReplayReport`, log inference RTC, kết quả probe P1–P4, `QAReport`; xuất JSON Schema.
2. File mẫu hợp lệ cho mỗi artifact trong `flywheel.testkit`, kèm một mẫu sai cố ý để test bộ kiểm.
3. `RolloutRequest` thêm `timing` và `latency_profile_ref` (03 bản 0.5).
4. Model giả cho endpoint LLM trong testkit (cho DA-18, DA-20).
5. Test: mọi file mẫu qua validate; mọi schema có trong JSON Schema xuất ra.

## Nhiệm vụ

- [ ] 1. Schema bảng topic, `ReplayReport` (AC 1)
- [ ] 2. Schema log RTC, probe, `QAReport` (AC 1)
- [ ] 3. `RolloutRequest.timing` (AC 3)
- [ ] 4. File mẫu và model giả trong testkit (AC 2, 4)
- [ ] 5. Test và JSON Schema (AC 5)

## Phạm vi file

Theo 07 mục 3.1. pr-guard chặn PR sửa file ngoài danh sách này; file story luôn được sửa.

- `packages/flywheel-contracts/src/flywheel/contracts/`
- `packages/flywheel-contracts/schemas/`, `packages/flywheel-contracts/tests/`
- `packages/flywheel-testkit/src/flywheel/testkit/`
- `packages/flywheel-testkit/tests/`

## Ghi chú cho người làm

- Nguồn: [design chia làn](../../superpowers/specs/2026-10-25-lanes-and-code-structure-design.md) mục 2, 3.2; 03 mục 7.3.
- Đây là việc nối các làn; trễ hạn thì ba làn phải code trên giả định riêng, nên ưu tiên trước mọi story khác của Hiếu trong tuần 1.

## Kiểm thử

- Mọi file mẫu qua validate; mẫu sai bị từ chối với thông báo rõ trường nào sai.

## Người phụ trách

- Làm: Dương Đình Hiếu
- Duyệt và merge: Dương Đình Hiếu (người duy nhất, 07 mục 3.4)
- Bình luận: Long, Thông, Châu, Hưng (mỗi người xem schema mình dùng)

## Change log

| Ngày | Nội dung | Người |
|---|---|---|
| 25/10/2026 | Tạo story theo design chia làn | PO (Hiếu) |

## Ghi chép khi làm

- Giờ thực:
- Công cụ AI đã dùng:
- Ghi chú hoàn thành:
- File đã tạo hoặc sửa:
