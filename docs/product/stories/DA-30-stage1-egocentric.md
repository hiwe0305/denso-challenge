# DA-30 · Stage 1 của Ψ₀ trên dữ liệu egocentric

## Trạng thái

| Trường | Giá trị |
|---|---|
| Trạng thái | Sẵn sàng (PO duyệt 27/10/2026) |
| Người làm | Hiếu |
| Làn | Adapter `flywheel-psi0` |
| Story PRD | 9.25 · Epic 9 · [design 27/10/2026](../../superpowers/specs/2026-10-27-g1-psi0-demo-design.md) mục 7.8, 8.1 |
| Nhãn | [Adapter] · `epic:9` · `gate:G1` · `area:rl` |
| Sprint | S2–S3; lần chạy ngắn trên EgoDex trước 13/11/2026 cho demo; fine-tune trên video tự quay khi còn thời gian |
| Ước lượng | 12 giờ người (khoảng 10–15, ước lượng); GPU-giờ ghi trong sổ |
| Phụ thuộc | DA-18 (bản export stage 1), DA-19 (adapter train trên Colab), DA-09 (probe P1, P2, P4) |

## Story

Là kỹ sư robot learning, tôi muốn chạy stage 1 của Ψ₀ trên dữ liệu egocentric do pipeline của đội xuất ra, để chứng minh đường đi từ dữ liệu egocentric tới model trên dữ liệu công bố, rồi đo tác dụng của fine-tune stage 1 trên video đội tự quay.

## Tiêu chí chấp nhận

1. **Lần chạy ngắn trên dữ liệu công bố**: `pretrain-egodex-psi0-fast.sh` khởi tạo từ `pre.*`, vài trăm bước, trên bản export EgoDex của DA-18; loss giảm, không lỗi định dạng; log vào `metrics.jsonl`; mục sổ chi phí. Đây là bằng chứng đường đi, không phải thí nghiệm.
2. Khi có video đội tự quay: RunPlan fine-tune stage 1 từ `pre.*` có tiêu chí chốt trước; đo P1 (hiểu cảnh hai bàn), P2, P4 (quên trên EgoDex gốc); rồi fine-tune stage 3 ở cùng N demo như HE (DA-26) và so closed-loop với VLM gốc.
3. Giữ checkpoint stage 1 mới khi P1 hoặc closed-loop tốt lên mà P4 không tụt quá ngưỡng ghi trong RunPlan; mọi kết quả, kể cả âm, ghi vào `docs/he/stage1.md`.

## Nhiệm vụ

- [ ] 1. Lần chạy stage 1 ngắn trên EgoDex (AC 1)
- [ ] 2. RunPlan fine-tune stage 1 trên video tự quay (AC 2)
- [ ] 3. Fine-tune, probe, closed-loop, báo cáo (AC 2, 3)

## Phạm vi file

Theo 07 mục 3.1. pr-guard chặn PR sửa file ngoài danh sách này; file story luôn được sửa.

- `packages/flywheel-psi0/src/flywheel_psi0/stage1/`, `packages/flywheel-psi0/tests/stage1/`
- `configs/runplans/stage1/`
- `docs/he/stage1.md`, `docs/g0/ledger/DA-30.csv`

## Ghi chú cho người làm

- Nguồn: design 27/10 mục 7.8, 8.1, 8.3.
- Tách từ DA-18 ngày 27/10/2026 để mỗi story có một người làm: DA-18 (Hưng) xuất dữ liệu, story này (Hiếu) chạy model.
- Ψ₀ đã pretrain stage 1 trên EgoDex, nên fine-tune lại trên EgoDex không cho thông tin mới; vì vậy AC 1 chỉ là lần chạy ngắn.
- Trọng số không commit.

## Kiểm thử

- Lần chạy ngắn chạy lại được từ RunPlan cho cùng loss bước đầu trong dung sai.

## Người phụ trách

- Làm: Dương Đình Hiếu
- Duyệt và merge: Dương Đình Hiếu (người duy nhất, 07 mục 3.4)
- Bình luận: Trần Ngọc Hưng (DA-18)

## Change log

| Ngày | Nội dung | Người |
|---|---|---|
| 27/10/2026 | Tạo story, tách AC 3–5 từ DA-18 | PO (Hiếu) |

## Ghi chép khi làm

- Giờ thực:
- Công cụ AI đã dùng:
- Ghi chú hoàn thành:
- File đã tạo hoặc sửa:
