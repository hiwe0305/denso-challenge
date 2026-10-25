# DA-21 · Export LeRobot v3 và checklist chuẩn hóa

## Trạng thái

| Trường | Giá trị |
|---|---|
| Trạng thái | Sẵn sàng (PO duyệt 25/10/2026 theo design 25/10/2026) |
| Người làm | Thông |
| Story PRD | Story mới của [design 25/10/2026](../../superpowers/specs/2026-10-25-denso-mujoco-and-stage-qa-design.md) mục 11.2 · Epic 9 |
| Nhãn | [Adapter] · `epic:9` · `area:data` |
| Sprint | S2 |
| Ước lượng | 5 giờ (khoảng 4–6, ước lượng của SM) |
| Phụ thuộc | DA-02 (export v2.1). Code trên dataset v2.1 mẫu trong lúc chờ. Khung package: DA-22 nhiệm vụ con 1 |

## Story

Là kỹ sư dữ liệu, tôi muốn xuất dataset sang LeRobot v3 từ bản v2.1 và có checklist chuẩn hóa tự động, để dùng được công cụ LeRobot mới mà không xử lý lại dữ liệu.

## Tiêu chí chấp nhận

1. Chuyển từ bản v2.1 sang v3 bằng script chuyển đổi chính thức của LeRobot, ghim phiên bản; không xử lý lại từ bundle.
2. Contract test đọc lại bản v3 bằng `lerobot` bản mới và so số episode, số khung, giá trị một batch mẫu với bản v2.1.
3. Checklist 7 mục của design 25/10 mục 5.1 chạy tự động cho cả v2.1 và v3: `info.json`, chỉ số liên tục, timestamp, video, tasks, stats, đọc lại bằng loader.
4. v2.1 vẫn là bản bắt buộc cho Ψ₀ (fork lerobot `v2.1`); v3 là tùy chọn.

## Nhiệm vụ

- [ ] 1. Chuyển v2.1 sang v3 (AC 1)
- [ ] 2. Contract test bản v3 (AC 2)
- [ ] 3. Checklist 7 mục cho cả hai bản (AC 3, 4)

## Phạm vi file

Theo 07 mục 3.1. pr-guard chặn PR sửa file ngoài danh sách này; file story luôn được sửa.

- `packages/flywheel-ingest/src/flywheel_ingest/export/lerobot_v3/`
- `packages/flywheel-ingest/tests/export/`

## Ghi chú cho người làm

- Nguồn: [design 25/10](../../superpowers/specs/2026-10-25-denso-mujoco-and-stage-qa-design.md) mục 5.1; 03 ADR-03 (bundle là nguồn sự thật).

## Kiểm thử

- Checklist bắt được dataset mẫu cố ý sai: timestamp lệch, thiếu task, stats có NaN.

## Người phụ trách

- Làm: Dương Tiến Thông
- Duyệt và merge: Dương Đình Hiếu (người duy nhất, 07 mục 3.4)
- Bình luận: Long (export), Hiếu (loader Ψ₀)

## Change log

| Ngày | Nội dung | Người |
|---|---|---|
| 25/10/2026 | Tạo story theo design 25/10/2026 mục 11.2 | PO (Hiếu) |
| 25/10/2026 | Phụ thuộc thêm khung package từ DA-22 nhiệm vụ con 1 | PO (Hiếu) |

## Ghi chép khi làm

- Giờ thực:
- Công cụ AI đã dùng:
- Ghi chú hoàn thành:
- File đã tạo hoặc sửa:
