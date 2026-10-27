# DA-18 · Egocentric sang dữ liệu stage 1 của Ψ₀

## Trạng thái

| Trường | Giá trị |
|---|---|
| Trạng thái | Sẵn sàng (PO duyệt 25/10/2026; xóa và khôi phục với nội dung mới 27/10/2026) |
| Người làm | Chờ PO giao (lần chạy GPU do Hiếu chạy) |
| Làn | Dữ liệu (export) và adapter `flywheel-psi0` (stage 1) |
| Story PRD | 9.25 · Epic 9 · [design 27/10/2026](../../superpowers/specs/2026-10-27-g1-psi0-demo-design.md) mục 6.6, 7.8 |
| Nhãn | [Adapter] · `epic:9` · `gate:G1` · `area:rl` |
| Sprint | S2–S3; xuất EgoDex và lần chạy ngắn trước 13/11/2026 cho demo; fine-tune trên video tự quay khi còn thời gian |
| Ước lượng | 20 giờ (khoảng 15–25, ước lượng); GPU-giờ ghi trong sổ |
| Phụ thuộc | DA-04 (đoạn egocentric đã qua QA), DA-19 (adapter train trên Colab). Trong lúc chờ: code export trên đoạn EgoDex mẫu của testkit |

## Story

Là kỹ sư robot learning, tôi muốn dữ liệu egocentric do pipeline của đội xử lý vào được stage 1 của Ψ₀, để chứng minh đường đi từ dữ liệu egocentric tới model trên dữ liệu công bố, rồi fine-tune stage 1 trên video đội tự quay khi còn thời gian.

## Tiêu chí chấp nhận

1. Export đoạn egocentric đã qua QA sang đúng định dạng mà `src/psi/data/egodex/egodex_dataset.py` của Ψ₀ đọc (biến đổi khớp tay cộng mp4; `chunk_size`, `upsample_rate`, delta action như config gốc; action 48 chiều theo tiền xử lý H-RDT), kèm stats theo `calc_egodex_stats.py`.
2. Contract test: loader stage 1 của Ψ₀ ở commit đã ghim đọc bản export ra đúng một batch mẫu đã lưu.
3. **Lần chạy ngắn trên dữ liệu công bố**: chạy `pretrain-egodex-psi0-fast.sh` khởi tạo từ `pre.*`, vài trăm bước, trên bản export EgoDex; loss giảm, không lỗi định dạng; log vào `metrics.jsonl`; mục sổ chi phí. Đây là bằng chứng đường đi, không phải thí nghiệm.
4. Khi có video đội tự quay (DA-04 AC 6): fine-tune stage 1 từ `pre.*` theo RunPlan có tiêu chí chốt trước; đo P1 (hiểu cảnh hai bàn), P2, P4 (quên trên EgoDex gốc); rồi fine-tune stage 3 ở cùng N demo như HE (DA-26) và so closed-loop với VLM gốc.
5. Giữ checkpoint stage 1 mới khi P1 hoặc closed-loop tốt lên mà P4 không tụt quá ngưỡng ghi trong RunPlan; mọi kết quả, kể cả âm, ghi vào `docs/he/stage1.md`.

## Nhiệm vụ

- [ ] 1. Export định dạng stage 1 và stats (AC 1)
- [ ] 2. Contract test bằng loader của Ψ₀ (AC 2)
- [ ] 3. Lần chạy stage 1 ngắn trên EgoDex (AC 3)
- [ ] 4. RunPlan fine-tune stage 1 trên video tự quay (AC 4)
- [ ] 5. Fine-tune, probe, closed-loop, báo cáo (AC 4, 5)

## Phạm vi file

Theo 07 mục 3.1. pr-guard chặn PR sửa file ngoài danh sách này; file story luôn được sửa.

- `packages/flywheel-data/src/flywheel/data/export/egodex.py`, `packages/flywheel-data/tests/contract/export_egodex/`
- `packages/flywheel-psi0/src/flywheel_psi0/stage1/`, `packages/flywheel-psi0/tests/stage1/`
- `configs/runplans/stage1/`
- `docs/he/stage1.md`, `docs/g0/ledger/DA-18.csv`

## Ghi chú cho người làm

- Nguồn: design 27/10 mục 5.0, 6.6, 7.8, 8.1, 8.3; spec mục 7.9; 03 mục 5.4.
- Trưởng nhóm chốt ngày 27/10/2026: chứng minh hệ thống trên dữ liệu công bố trước; còn thời gian thì dùng dữ liệu egocentric đội thu.
- Ψ₀ đã pretrain stage 1 trên EgoDex, nên fine-tune lại trên EgoDex không cho thông tin mới; vì vậy AC 3 chỉ là lần chạy ngắn.
- Phần export nằm trong làn Dữ liệu và chỉ import nhân; phần stage 1 nằm trong adapter `flywheel-psi0`. Hai phần nối qua `DatasetRef` trong `flywheel.contracts`.
- Trọng số không commit.

## Kiểm thử

- Contract test ở AC 2 chạy trong CI trên đoạn mẫu của testkit (không cần GPU).
- Lần chạy ngắn chạy lại được từ RunPlan cho cùng loss bước đầu trong dung sai.

## Người phụ trách

- Làm: chờ PO giao
- Duyệt và merge: Dương Đình Hiếu (người duy nhất, 07 mục 3.4)

## Change log

| Ngày | Nội dung | Người |
|---|---|---|
| 25/10/2026 | Tạo story: video egocentric thô của nhà máy DENSO thành dữ liệu fine-tune stage 1 | PO (Hiếu) theo design 25/10/2026 (đã xóa) |
| 27/10/2026 | Xóa cùng robot DENSO, rồi khôi phục cùng ngày với nội dung mới: nguồn là mẫu EgoDex và video đội tự quay; lần chạy ngắn trên EgoDex chứng minh đường đi; fine-tune thật chỉ trên video tự quay | PO (Hiếu) theo design 27/10/2026 |

## Ghi chép khi làm

- Giờ thực:
- Công cụ AI đã dùng:
- Ghi chú hoàn thành:
- File đã tạo hoặc sửa:
