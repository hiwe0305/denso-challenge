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
| Phụ thuộc | DA-18 (bản export stage 1), DA-19 (adapter train trên Colab), DA-09 (probe P1, P2, P4; **3/11/2026:** dời sau demo, lần chạy ngắn trước 13/11 báo loss và closed-loop, probe sau demo) |

## Story

Là kỹ sư robot learning, tôi muốn chạy stage 1 của Ψ₀ trên dữ liệu egocentric do pipeline của đội xuất ra, để chứng minh đường đi từ dữ liệu egocentric tới model trên dữ liệu công bố, rồi đo tác dụng của fine-tune stage 1 trên video đội tự quay.

## Tiêu chí chấp nhận

1. **Lần chạy ngắn trên dữ liệu công bố**: `pretrain-egodex-psi0-fast.sh` khởi tạo từ `pre.*`, vài trăm bước, trên bản export EgoDex của DA-18; loss giảm, không lỗi định dạng; log vào `metrics.jsonl`; mục sổ chi phí. Đây là bằng chứng đường đi, không phải thí nghiệm.
2. Khi có video đội tự quay: RunPlan fine-tune stage 1 từ `pre.*` có tiêu chí chốt trước; đo P1 (hiểu cảnh hai bàn), P2, P4 (quên trên EgoDex gốc); rồi fine-tune stage 3 ở cùng N demo như HE (DA-26) và so closed-loop với VLM gốc.
3. Giữ checkpoint stage 1 mới khi P1 hoặc closed-loop tốt lên mà P4 không tụt quá ngưỡng ghi trong RunPlan; mọi kết quả, kể cả âm, ghi vào `docs/he/stage1.md`.

## Nhiệm vụ

- [ ] 1. Lần chạy stage 1 ngắn trên EgoDex (AC 1)
  - [x] 1.1 Recipe `pretrain-egodex-psi0-fast.sh`, RunPlan, launcher stage 1, dữ liệu thay thế EgoDex, driver Colab, test CPU
  - [x] 1.2 Loader check của Ψ₀ trên dữ liệu thay thế, chỉ CPU ([stage1.md](../../he/stage1.md) mục 1.5)
  - [x] 1.3 Chuẩn bị chạy sau khi Hiếu duyệt CU (4/11/2026): ghi quyết định, bộ canh CU dừng phiên ở trần (dùng chung, PR #108), lệnh `persist` ở trần mềm
  - [ ] 1.4 Chạy trên Colab (Hiếu đã miễn bước che danh tính cho mẫu EgoDex công bố, 4/11/2026); ghi loss, `metrics.jsonl`, dòng `measured` của sổ chi phí
- [ ] 2. RunPlan fine-tune stage 1 trên video tự quay (AC 2): nhánh B của DA-34 (VLM qua stage 1 trên video đội tự quay, rồi stage 3 như nhánh C); Hiếu chốt 4 mặc định ngày 9/11/2026 ([stage1.md](../../he/stage1.md) mục 2)
  - [x] 2.1 Nguồn dữ liệu `export` cho `Stage1Plan`: ghim bản export của DA-18 bằng `export_id` và sha256 của tarball; `setup` lấy tarball từ Google Drive, kiểm sha256, `export_id`, sha256 từng file trong `meta.json` và `layout_problems`, từ chối khi lệch; nguồn này chỉ nhận `identity_masked: true`; lệnh `pack` đóng tarball; `setup` kiểm sha256 của trọng số cha; test CPU (`test_psi0_stage1_export_source.py`, 15 test)
  - [ ] 2.2 `persist` lưu cả checkpoint VLM (trọng số, kèm config và tokenizer của checkpoint cha) lên Drive với sha256, kiểm header safetensors khớp cha; trả lời Q-28C (stage 3 nạp được VLM của stage 1 cùng action header `postpre.*` gốc) bằng dẫn chứng file:dòng ở `cda3fdf`; test CPU
  - [ ] 2.3 RunPlan `tray-ego-b.yaml`: cha là VLM của nhánh C, stats chuẩn hóa, số bước, checkpoint, val, tiêu chí chốt trước, trần 4 CU; `runplan check` qua; `setup` ghi độ phủ stats
  - [ ] 2.4 `stage1.md` mục 2, dòng `estimated` của sổ chi phí, lệnh chạy cho Hiếu
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
| 3/11/2026 | DA-09 dời sau demo: lần chạy ngắn chưa có probe (07 mục 2.4, bản 1.2) | PO (Hiếu) |
| 4/11/2026 | Duyệt CU cho lần chạy ngắn (tier 2: "Approve tier 2"), ước lượng khoảng 2,3 CU, trần 4 CU; chạy từ `master` sau merge, có bộ canh CU | PO (Hiếu) |
| 4/11/2026 | Miễn bước che danh tính ("Waive for EgoDex") chỉ cho mẫu EgoDex công bố (`public`) trong các lần chạy stage 1 của DA-30; video tự quay và mọi nguồn egocentric khác vẫn phải che trước. RunPlan chặn mọi nguồn khác ([stage1.md](../../he/stage1.md) mục 1.4) | PO (Hiếu) |
| 4/11/2026 | Bộ canh CU dùng chung đổi thiết kế (PR #108): mỗi phiên một watcher theo endpoint, cộng một guard cho cả đợt; một đợt một lúc trên tài khoản, DA-30 chạy trước rồi đến DA-26 ([stage1.md](../../he/stage1.md) mục 1.6) | Review PR #108 |
| 4/11/2026 | Lần chạy 1 hỏng ở `accelerator.prepare` (`betas: "auto"` trong `zero3_offload.json` của tác giả). RunPlan dùng file DeepSpeed của repo, khớp recipe và giữ lr riêng của từng nhóm; `setup` chạy pre-flight DeepSpeed trên model nhỏ trước mọi lần tải ([stage1.md](../../he/stage1.md) mục 1.2, 1.6) | Lần chạy 1 |

## Ghi chép khi làm

- Giờ thực:
- Công cụ AI đã dùng:
- Ghi chú hoàn thành:
- File đã tạo hoặc sửa:
