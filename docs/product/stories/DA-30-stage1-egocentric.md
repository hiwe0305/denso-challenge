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
  - [x] 2.2 `persist` lưu cả checkpoint VLM (trọng số, kèm config và tokenizer của checkpoint cha) lên Drive với sha256, kiểm header safetensors khớp cha; trả lời Q-28C (stage 3 nạp được VLM của stage 1 cùng action header `postpre.*` gốc) bằng dẫn chứng file:dòng ở `cda3fdf` ([stage1.md](../../he/stage1.md) mục 2.3); pha `check-vlm` nạp bản trên Drive như stage 3; thử trên CPU với Qwen3-VL nhỏ; test CPU (`test_psi0_stage1_vlm_checkpoint.py`, 10 test)
  - [x] 2.3 RunPlan `tray-ego-b.yaml`: cha là VLM của nhánh C, stats chuẩn hóa, số bước, checkpoint, val, tiêu chí chốt trước, trần 4 CU; `runplan check` qua (`rp_6a66a6ff082c`, bản nháp tới khi có bản export: `setup` từ chối plan nháp); `setup` ghi độ phủ stats; [stage1.md](../../he/stage1.md) mục 2.4; test CPU (`test_psi0_stage1_tray_ego_b.py`, 7 test)
  - [x] 2.4 `stage1.md` mục 2, dòng `estimated` của sổ chi phí (2,5 CU, giả định), lệnh chạy cho Hiếu ([stage1.md](../../he/stage1.md) mục 2.5, 2.6). Còn lại của nhiệm vụ 2: ghim bản export vào plan khi phiên điều phối giao (bỏ `status: draft`)
  - [x] 2.5 Loader check của Ψ₀ trên bản export thử `egx_fb3d1401dac0bd4c` (132 mẫu, chỉ CPU); `loader_check` báo phần action bị cắt ở [−1, 1] và số mẫu một token; ghi kết quả và đề xuất cho plan ([stage1.md](../../he/stage1.md) mục 2.7); test CPU (`test_psi0_stage1_loader_check.py`, 3 test)
  - [x] 2.6 Đo offline, trên bản export thử, làm sạch tư thế có đưa phần action bị cắt xuống dưới 5 % không (liên tục góc, làm mượt, khung nhảy, camera); bảng và đề xuất cho PR của DA-04 ([stage1.md](../../he/stage1.md) mục 2.8)
  - [x] 2.7 Ghim bản export đã làm sạch `egx_7b43c30dc5d88cd7` (132 mẫu, mã làm sạch đã sửa sau review PR #174; thay lần ghim đầu `egx_b6e974e46e8222e8`) vào `tray-ego-b.yaml` sau loader check (3,6 % bị cắt, ngưỡng 5 %); plan giữ `status: draft` tới khi PR #173 và #174 merge (`rp_64bde22a5dda`); test CPU ([stage1.md](../../he/stage1.md) mục 2.9)
  - [x] 2.8 Bỏ `status: draft` khỏi `tray-ego-b.yaml` sau khi PR #173 và #176 (thay #174, cùng mã `ac3637da`) merge và Hiếu xác nhận sự đồng ý của người trong clip (11/11/2026); `run_plan_id` giữ `rp_64bde22a5dda`; tarball cục bộ khớp sha256 ([stage1.md](../../he/stage1.md) mục 2.4, 2.6)
  - [x] 2.9 Lần 1 của nhánh B trên L4 (11/11/2026) hết bộ nhớ ở forward đầu, chưa có bước train nào; Hiếu quyết "Chạy A100": `tray-ego-b.yaml` đổi sang A100 (40 GB), trần 8 CU, recipe giữ nguyên (`rp_1d7627234111`, trước là `rp_64bde22a5dda`); test CPU
  - [x] 2.10 `colab setup` tự cài CUDA toolkit khớp bản CUDA của torch, cùng `ninja`, khi VM có bản CUDA khác (lần 1: CUDA 13.0, torch cu126); đặt `CUDA_HOME` và `PATH` cho pre-flight và `run`, ghi các bước vào `report.json`; test CPU (`test_psi0_stage1_cuda_toolchain.py`, 9 test)
  - [ ] 2.11 Ghi kết quả lần 1 trên L4, cập nhật ước lượng và runbook cho A100 (trần 8 CU, quy tắc dừng ở 6,73 CU/giờ), dòng `measured` 0,38 CU và dòng `estimated` mới của sổ chi phí ([stage1.md](../../he/stage1.md) mục 2.5, 2.6, 2.10)
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
| 9/11/2026 | "Chốt 4 mặc định" cho nhánh B của DA-34: VLM cha là VLM của C (`ego200k.he30k`), mỗi clip một mẫu với câu mô tả cả task, 153 clip 480p đã làm mờ mặt (`public` theo PR #170, bỏ 8 clip 1080p), khoảng 300 bước, trần 4 CU ([stage1.md](../../he/stage1.md) mục 2.1) | PO (Hiếu) |
| 11/11/2026 | Người trong 153 clip đã đồng ý cho đưa tarball lên Drive và chạy stage 1; PR #173 và #176 (thay #174) đã merge, nên plan nhánh B bỏ `status: draft` (`rp_64bde22a5dda`, [stage1.md](../../he/stage1.md) mục 2.4) | PO (Hiếu) |
| 11/11/2026 | Lần 1 của nhánh B trên L4 hết bộ nhớ ở forward đầu (0,38 CU, chưa có bước train). "Chạy A100": `tray-ego-b.yaml` sang A100 40 GB, trần 8 CU, recipe giữ nguyên (`rp_1d7627234111`, [stage1.md](../../he/stage1.md) mục 2.10) | PO (Hiếu) |

## Ghi chép khi làm

- Giờ thực:
- Công cụ AI đã dùng:
- Ghi chú hoàn thành:
- File đã tạo hoặc sửa:
