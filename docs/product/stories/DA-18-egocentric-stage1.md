# DA-18 · Video egocentric thô thành dữ liệu fine-tune stage 1

## Trạng thái

| Trường | Giá trị |
|---|---|
| Trạng thái | Sẵn sàng (PO duyệt 25/10/2026 theo design 25/10/2026) |
| Người làm | Long |
| Story PRD | Story mới của [design 25/10/2026](../../superpowers/specs/2026-10-25-denso-mujoco-and-stage-qa-design.md) mục 11.2 · Epic 9 |
| Nhãn | [Adapter] · `epic:9` · `area:data` |
| Sprint | S2–S3 |
| Ước lượng | 25 giờ (khoảng 20–30, ước lượng của SM) |
| Phụ thuộc | DA-04 (che danh tính, cắt đoạn, pose); DA-01. Code trên đoạn EgoDex mẫu trong lúc chờ |

## Story

Là kỹ sư ML, tôi muốn biến video egocentric thô hợp với task DENSO thành dữ liệu mà code stage 1 của Ψ₀ đọc được, để fine-tune VLM trên cảnh nhà máy.

## Tiêu chí chấp nhận

1. Đầu vào: video thô (trước khi có video DENSO, dùng mẫu EgoDex); che danh tính là bước đầu tiên, `deid_status` bắt buộc trước mọi bước sau (bất biến kiến trúc).
2. Cắt đoạn theo 6 bước của task khay → máy; pose tay 3D và tư thế camera: E-B đọc từ thiết bị, E-A ước lượng, gắn `action_quality = pseudo`.
3. Xuất đúng định dạng mà `src/psi/data/egodex/egodex_dataset.py` của Ψ₀ ở commit ghim đọc được (biến đổi khớp tay và video), khớp `chunk_size`, `upsample_rate`, delta action của config gốc; stats bằng `scripts/data/calc_egodex_stats.py`.
4. Câu lệnh ngôn ngữ mỗi đoạn và bộ hỏi đáp về linh kiện, khay, máy, bước đang làm (dùng cho probe P1).
5. Contract test: loader Ψ₀ đọc ra một batch mẫu, so từng giá trị với batch đã lưu.
6. RunPlan nháp cho fine-tune stage 1 từ `pre.*` theo `pretrain_egodex_qwen3vl_config`, trỏ tới dataset này (chưa chạy); mục tiêu train là token FAST, hỏi đáp chỉ để chấm (design 25/10 mục 5.2).
7. Dataset có `data_class` gộp theo mức chặt nhất; dữ liệu DENSO không lên Colab khi chưa chọn phương án ở design 25/10 mục 9.

## Nhiệm vụ

- [ ] 1. Nối với DA-04: che danh tính, cắt đoạn, pose (AC 1, 2)
- [ ] 2. Xuất định dạng EgoDex và stats (AC 3)
- [ ] 3. Câu lệnh và bộ hỏi đáp (AC 4)
- [ ] 4. Contract test bằng loader Ψ₀ (AC 5)
- [ ] 5. RunPlan nháp stage 1, `data_class` (AC 6, 7)

## Phạm vi file

Theo 07 mục 3.1. pr-guard chặn PR sửa file ngoài danh sách này; file story luôn được sửa.

- `packages/flywheel-ingest/src/flywheel_ingest/egocentric/stage1/`
- `packages/flywheel-ingest/tests/egocentric/`
- `configs/runplans/draft-stage1-egocentric.yaml`
- `docs/g0/egocentric-stage1.md`

## Ghi chú cho người làm

- Nguồn: [design 25/10](../../superpowers/specs/2026-10-25-denso-mujoco-and-stage-qa-design.md) mục 5.2, 6.1; design 23/10 mục 5.3, 6.1 (P1, P2, P4).
- Fine-tune chỉ được giữ khi P1 hoặc P2 trên dữ liệu DENSO tốt lên mà P4 không tụt quá ngưỡng ghi trước trong RunPlan.
- Stage 1 học chuyển động bàn tay người, robot cầm bằng gripper; giá trị chính của video nằm ở hình ảnh và cấu trúc task.

## Kiểm thử

- Contract test ở AC 5 chạy trong CI trên đoạn mẫu nhỏ (không cần GPU).
- Test: đoạn chưa che danh tính bị từ chối ở mọi bước sau.

## Người phụ trách

- Làm: Nguyễn Thăng Long
- Duyệt và merge: Dương Đình Hiếu (người duy nhất, 07 mục 3.4)
- Bình luận: Hiếu (stage 1, RunPlan), Thông (QA)

## Change log

| Ngày | Nội dung | Người |
|---|---|---|
| 25/10/2026 | Tạo story theo design 25/10/2026 mục 11.2 | PO (Hiếu) |

## Ghi chép khi làm

- Giờ thực:
- Công cụ AI đã dùng:
- Ghi chú hoàn thành:
- File đã tạo hoặc sửa:
