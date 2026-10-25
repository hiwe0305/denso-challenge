# DA-21 · Export LeRobot v3 và checklist chuẩn hóa

## Trạng thái

| Trường | Giá trị |
|---|---|
| Trạng thái | Sẵn sàng (PO duyệt 25/10/2026; sửa theo design chia làn cùng ngày) |
| Người làm | Thông |
| Làn | Dữ liệu |
| Story PRD | Story mới của [design MuJoCo 25/10/2026](../../superpowers/specs/2026-10-25-denso-mujoco-and-stage-qa-design.md) và [design chia làn](../../superpowers/specs/2026-10-25-lanes-and-code-structure-design.md) · Epic 9 |
| Nhãn | [Lõi] · `epic:9` · `area:data` |
| Sprint | S2 |
| Ước lượng | 5 giờ (khoảng 4–6, ước lượng của SM) |
| Phụ thuộc | DA-02 (export v2.1, cùng người làm). Code trên dataset v2.1 mẫu của testkit. PR `chore-restructure` (07 mục 3.6, hết 27/10) tạo khung package `flywheel-data` |

## Story

Là kỹ sư dữ liệu, tôi muốn xuất dataset sang LeRobot v3 từ bản v2.1 và có checklist chuẩn hóa tự động, để dùng công cụ LeRobot mới mà không xử lý lại dữ liệu.

## Tiêu chí chấp nhận

1. Chuyển v2.1 sang v3 bằng script chuyển đổi chính thức của LeRobot, ghim phiên bản; không xử lý lại từ bundle.
2. Contract test đọc lại bản v3 bằng `lerobot` bản mới; so số episode, số khung, một batch mẫu với bản v2.1.
3. Checklist 7 mục (design MuJoCo mục 5.1) chạy tự động cho cả v2.1 và v3.
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

- Nguồn: [design MuJoCo](../../superpowers/specs/2026-10-25-denso-mujoco-and-stage-qa-design.md) mục 5.1; 03 ADR-03.
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
| 25/10/2026 | Tạo story theo design MuJoCo 25/10/2026 mục 11.2 | PO (Hiếu) |
| 25/10/2026 | Viết lại theo design chia làn: đường dẫn trong `flywheel-data` | PO (Hiếu) |

## Ghi chép khi làm

- Giờ thực:
- Công cụ AI đã dùng:
- Ghi chú hoàn thành:
- File đã tạo hoặc sửa:
