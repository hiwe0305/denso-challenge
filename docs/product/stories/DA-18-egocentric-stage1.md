# DA-18 · Egocentric sang dữ liệu stage 1 của Ψ₀

## Trạng thái

| Trường | Giá trị |
|---|---|
| Trạng thái | Sẵn sàng (PO duyệt 25/10/2026; xóa và khôi phục với nội dung mới 27/10/2026) |
| Người làm | Hưng |
| Làn | Dữ liệu |
| Story PRD | 9.25 · Epic 9 · [design 27/10/2026](../../superpowers/specs/2026-10-27-g1-psi0-demo-design.md) mục 6.6, 7.8 |
| Nhãn | [Adapter] · `epic:9` · `gate:G1` · `area:rl` |
| Sprint | S2; bản export EgoDex đọc được bằng loader trước 10/11/2026 để DA-30 chạy kịp demo |
| Ước lượng | 8 giờ (khoảng 6–10, ước lượng; phần stage 1 tách sang DA-30) |
| Phụ thuộc | DA-04 (đoạn egocentric đã qua QA). Trong lúc chờ: code export trên đoạn EgoDex mẫu của testkit. Chặn DA-30 |

## Story

Là kỹ sư dữ liệu, tôi muốn dữ liệu egocentric do pipeline của đội xử lý được xuất đúng định dạng stage 1 của Ψ₀, để DA-30 chạy được stage 1 trên đó mà không phải sửa dữ liệu.

## Tiêu chí chấp nhận

1. Export đoạn egocentric đã qua QA sang đúng định dạng mà `src/psi/data/egodex/egodex_dataset.py` của Ψ₀ đọc (biến đổi khớp tay cộng mp4; `chunk_size`, `upsample_rate`, delta action như config gốc; action 48 chiều theo tiền xử lý H-RDT), kèm stats theo `calc_egodex_stats.py`.
2. Contract test: loader stage 1 của Ψ₀ ở commit đã ghim đọc bản export ra đúng một batch mẫu đã lưu.
3. Xuất được cả hai nguồn: mẫu EgoDex (E-B) và video tự quay (E-A, `pseudo`), cùng định dạng; `meta` ghi nguồn và độ tin pose.

## Nhiệm vụ

- [ ] 1. Export định dạng stage 1 và stats (AC 1)
- [ ] 2. Contract test bằng loader của Ψ₀ (AC 2)
- [ ] 3. Export cho video tự quay (AC 3)

## Phạm vi file

Theo 07 mục 3.1. pr-guard chặn PR sửa file ngoài danh sách này; file story luôn được sửa.

- `packages/flywheel-data/src/flywheel/data/export/egodex.py`, `packages/flywheel-data/tests/contract/export_egodex/`
- `docs/g0/ledger/DA-18.csv`

## Ghi chú cho người làm

- Nguồn: design 27/10 mục 5.0, 6.6, 7.8, 8.1, 8.3; spec mục 7.9; 03 mục 5.4.
- Trưởng nhóm chốt ngày 27/10/2026: chứng minh hệ thống trên dữ liệu công bố trước; còn thời gian thì dùng dữ liệu egocentric đội thu.
- Ψ₀ đã pretrain stage 1 trên EgoDex, nên fine-tune lại trên EgoDex không cho thông tin mới; vì vậy AC 3 chỉ là lần chạy ngắn.
- Story này chỉ import nhân; không import `flywheel-psi0`. Contract test đọc lại bằng loader của Ψ₀ chạy trong job có marker riêng; trong CI dùng loader giả cùng schema. Phần chạy stage 1 là DA-30 (Hiếu), nối qua `DatasetRef`.
- Trọng số không commit.

## Kiểm thử

- Contract test ở AC 2 chạy trong CI trên đoạn mẫu của testkit (không cần GPU).

## Người phụ trách

- Làm: Trần Ngọc Hưng
- Duyệt và merge: Dương Đình Hiếu (người duy nhất, 07 mục 3.4)

## Change log

| Ngày | Nội dung | Người |
|---|---|---|
| 25/10/2026 | Tạo story: video egocentric thô của nhà máy DENSO thành dữ liệu fine-tune stage 1 | PO (Hiếu) theo design 25/10/2026 (đã xóa) |
| 27/10/2026 | Xóa cùng robot DENSO, rồi khôi phục cùng ngày với nội dung mới: nguồn là mẫu EgoDex và video đội tự quay; lần chạy ngắn trên EgoDex chứng minh đường đi; fine-tune thật chỉ trên video tự quay | PO (Hiếu) theo design 27/10/2026 |
| 27/10/2026 | Tách phần chạy stage 1 sang DA-30; giao cho Hưng theo 07 mục 2.0 (bản 0.6) | PO (Hiếu) |

## Ghi chép khi làm

- Giờ thực:
- Công cụ AI đã dùng:
- Ghi chú hoàn thành:
- File đã tạo hoặc sửa:
