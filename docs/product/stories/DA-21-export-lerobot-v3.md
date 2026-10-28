# DA-21 · Export LeRobot v3 và checklist chuẩn hóa

## Trạng thái

| Trường | Giá trị |
|---|---|
| Trạng thái | Sẵn sàng (PO duyệt 25/10/2026; sửa 27/10/2026) |
| Người làm | Thông |
| Làn | Dữ liệu |
| Story PRD | Story của [design 27/10/2026](../../superpowers/specs/2026-10-27-g1-psi0-demo-design.md) mục 6.4 · Epic 9 |
| Nhãn | [Lõi] · `epic:9` · `area:data` |
| Sprint | S2 |
| Ước lượng | 5 giờ (khoảng 4–6, ước lượng của SM) |
| Phụ thuộc | DA-02 (export v2.1, cùng người làm). Code trên dataset v2.1 mẫu của testkit. PR `chore-restructure` (07 mục 3.6; mở PR 28/10, merge 29/10/2026) tạo khung package `flywheel-data` |

## Story

Là kỹ sư dữ liệu, tôi muốn xuất dataset sang LeRobot v3 từ bản v2.1 và có checklist chuẩn hóa tự động, để dùng công cụ LeRobot mới mà không xử lý lại dữ liệu.

## Tiêu chí chấp nhận

1. Chuyển v2.1 sang v3 bằng script chuyển đổi chính thức của LeRobot, ghim phiên bản; không xử lý lại từ bundle.
2. Contract test đọc lại bản v3 bằng `lerobot` bản mới; so số episode, số khung, một batch mẫu với bản v2.1.
3. Checklist 7 mục (design 27/10 mục 6.4) chạy tự động cho cả v2.1 và v3.
4. v2.1 là bản bắt buộc cho Ψ₀ (fork lerobot `v2.1`); v3 tùy chọn.

## Nhiệm vụ

- [ ] 1. Chuyển v2.1 sang v3 (AC 1)
- [ ] 2. Contract test bản v3 (AC 2)
- [ ] 3. Checklist cho cả hai bản (AC 3, 4)

## Phạm vi file

Theo 07 mục 3.1. pr-guard chặn PR sửa file ngoài danh sách này; file story luôn được sửa.

- `packages/flywheel-data/src/flywheel/data/export/lerobot_v3.py`, `packages/flywheel-data/src/flywheel/data/export/checklist.py`
- `packages/flywheel-data/tests/unit/export/`, `packages/flywheel-data/tests/contract/export/`
- `configs/data/export.yaml`

## Ghi chú cho người làm

- Nguồn: design 27/10 mục 6.4; 03 ADR-03.
- Chỉ import nhân (`flywheel.contracts`, `flywheel.store`, `flywheel.testkit`); không import làn khác hay adapter (03 mục 7.3). Thiếu trường trong schema thì báo Hiếu mở PR hợp đồng, không thêm trường tạm.

## Kiểm thử

- Checklist bắt được dataset mẫu cố ý sai: timestamp lệch, thiếu task, stats có NaN.

## Người phụ trách

- Làm: Dương Tiến Thông
- Duyệt và merge: Dương Đình Hiếu (người duy nhất, 07 mục 3.4)
- Bình luận: Hiếu (loader Ψ₀)

## Change log

| Ngày | Nội dung | Người |
|---|---|---|
| 25/10/2026 | Tạo story | PO (Hiếu) theo design 25/10/2026 (đã xóa) |
| 25/10/2026 | Đường dẫn trong `flywheel-data` | PO (Hiếu) theo design chia làn (đã xóa) |
| 27/10/2026 | Nguồn chuyển sang design 27/10; nội dung không đổi | PO (Hiếu) |
| 28/10/2026 | Sửa hạn PR `chore-restructure` theo 07 mục 3.6 bản 0.6: mở 28/10, merge 29/10 | PO (Hiếu) |

## Ghi chép khi làm

- Giờ thực:
- Công cụ AI đã dùng:
- Ghi chú hoàn thành:
- File đã tạo hoặc sửa:
