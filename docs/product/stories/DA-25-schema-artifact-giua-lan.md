# DA-25 · Schema và file mẫu cho artifact giữa các làn

## Trạng thái

| Trường | Giá trị |
|---|---|
| Trạng thái | Sẵn sàng (PO duyệt 25/10/2026; sửa 27/10/2026) |
| Người làm | Long |
| Làn | Nhân |
| Story PRD | Story của [design 27/10/2026](../../superpowers/specs/2026-10-27-g1-psi0-demo-design.md) mục 12; 03 mục 7.3 · Epic 9 |
| Nhãn | [Lõi] · `epic:9` · `gate:G0` · `area:core` |
| Sprint | S1, trước 29/10 |
| Ước lượng | 8 giờ (khoảng 6–10, ước lượng của SM) |
| Phụ thuộc | PR `chore-restructure` |

## Story

Là người giữ nhân, tôi muốn có schema và file mẫu cho mọi artifact mới giữa các làn, để ba làn và người làm adapter code song song mà không phải hỏi nhau.

## Tiêu chí chấp nhận

1. Schema trong `flywheel.contracts` cho: `ReplayReport`, `DatasetReport`, `DefectManifest` (đáp án bộ lỗi cấy), log inference RTC, kết quả probe P1–P4, `QAReport`; trường Episode mới `source_detail`, `renderer`, `injected_defect`; xuất JSON Schema. Bỏ bảng topic MCAP (không còn ROS 2).
2. File mẫu hợp lệ cho mỗi artifact trong `flywheel.testkit`, kèm một mẫu sai cố ý để test bộ kiểm.
3. `RolloutRequest` thêm `timing` và `latency_profile_ref` (03 bản 0.5).
4. Model giả cho endpoint LLM trong testkit (cho DA-20).
5. Test: mọi file mẫu qua validate; mọi schema có trong JSON Schema xuất ra.

## Nhiệm vụ

- [ ] 1. Schema `ReplayReport`, `DatasetReport`, `DefectManifest` (AC 1)
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

- Nguồn: design 27/10 mục 6.1, 9.2, 12; 03 mục 7.3 (bảng artifact).
- Đây là việc nối các làn; trễ hạn thì ba làn phải code trên giả định riêng, nên ưu tiên trước mọi story khác của Hiếu trong tuần 1.

## Kiểm thử

- Mọi file mẫu qua validate; mẫu sai bị từ chối với thông báo rõ trường nào sai.

## Người phụ trách

- Làm: Nguyễn Thăng Long
- Duyệt và merge: Dương Đình Hiếu (người duy nhất, 07 mục 3.4)
- Bình luận: Long, Thông, Châu, Hưng (mỗi người xem schema mình dùng)

## Change log

| Ngày | Nội dung | Người |
|---|---|---|
| 25/10/2026 | Tạo story | PO (Hiếu) theo design chia làn (đã xóa) |
| 27/10/2026 | Bỏ bảng topic MCAP; thêm `DatasetReport`, `DefectManifest`, trường Episode mới | PO (Hiếu) theo design 27/10/2026 |
| 27/10/2026 | Giao cho Long theo 07 mục 2.0 (bản 0.6) | PO (Hiếu) |

## Ghi chép khi làm

- Giờ thực:
- Công cụ AI đã dùng:
- Ghi chú hoàn thành:
- File đã tạo hoặc sửa:
