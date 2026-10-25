# DA-19 · Code train của tác giả, lớp bọc log 3 stage và train trên Colab

## Trạng thái

| Trường | Giá trị |
|---|---|
| Trạng thái | Sẵn sàng (PO duyệt 25/10/2026 theo design 25/10/2026) |
| Người làm | Hiếu |
| Story PRD | Story mới của [design 25/10/2026](../../superpowers/specs/2026-10-25-denso-mujoco-and-stage-qa-design.md) mục 11.2 · Epic 9 |
| Nhãn | [Adapter] · `epic:9` · `gate:G0` · `area:rl` |
| Sprint | S1–S2 |
| Ước lượng | 24 giờ (khoảng 20–28 (gồm phần DA-07), ước lượng của SM) |
| Phụ thuộc | Không. Code trên `FakeTrainer` của S1-08 trong lúc chưa có job thật |

## Story

Là trưởng nhóm phụ trách Ψ₀, tôi muốn train cả 3 stage bằng code của tác giả và có log đủ để chấm từng stage, để Agent QA/QC và kỹ sư đánh giá được kết quả train.

## Tiêu chí chấp nhận

1. Script đọc code ở commit ghim của repo Ψ₀: liệt kê mọi chỗ trainer gọi `log`, `accelerator.log`, `init_trackers`, `evaluate`, `save_checkpoint` và tên metric; so với bảng log cần có ở design 23/10 mục 6.3; ghi bảng "có sẵn, thiếu, cách lấy" vào `docs/g0/psi0-logging.md`. Chạy lại mỗi khi đổi commit ghim.
2. `Psi0Trainer` gọi script của tác giả cho stage 1 (`pretrain-*`), stage 2 (`posttrain-*`), stage 3 (`finetune-*`) với cấu hình ghi đè từ RunPlan; không sửa repo của tác giả.
3. Lớp bọc log ghi `metrics.jsonl`: loss tổng, LR, chuẩn gradient theo nhóm (có sẵn), cộng phần thiếu tính lại trên batch val: loss theo nhóm action và theo vị trí trong chunk, phương sai action dự đoán, phân bố độ mở gripper; W&B chạy offline song song (gồm phần của DA-07).
4. Job trên Colab tiếp tục được từ checkpoint (`--train.resume_from_checkpoint=latest`), lưu checkpoint ra kho bền định kỳ, ghi compute unit vào sổ chi phí.
5. Mỗi checkpoint trung gian tự chạy P3 và P4 (theo DA-09 khi có).
6. Dữ liệu DENSO không lên Colab khi chưa chọn phương án ở design 25/10 mục 9. Ghi chi phí vào `docs/g0/ledger/DA-19.csv`, cột theo [docs/g0/README.md](../../g0/README.md).
7. Khung package `flywheel-psi0` (nhiệm vụ con 1, mở PR riêng trong 2 ngày đầu): `pyproject.toml`, `src/flywheel_psi0/__init__.py`, README ghi thư mục nào thuộc story nào (`trainer/`, `probe/` của Hiếu; `policy/` của Châu, gồm DA-23); tạo lại `uv.lock` bằng lệnh uv lock; `uv run pytest` chạy được trên package rỗng. Story khác viết vào package này chờ PR khung merge, trong lúc chờ code trong thư mục của mình trên nhánh riêng.

## Nhiệm vụ

- [ ] 1. Khung package `flywheel-psi0`, mở PR riêng (AC 7)
- [ ] 2. Script đọc code và bảng log (AC 1)
- [ ] 3. `Psi0Trainer` gọi script 3 stage (AC 2)
- [ ] 4. Lớp bọc log và `metrics.jsonl` (AC 3)
- [ ] 5. Chạy trên Colab, tiếp tục từ checkpoint, sổ chi phí (AC 4, 6)
- [ ] 6. Checkpoint trung gian chạy probe (AC 5)

## Phạm vi file

Theo 07 mục 3.1. pr-guard chặn PR sửa file ngoài danh sách này; file story luôn được sửa.

- `packages/flywheel-psi0/pyproject.toml`, `packages/flywheel-psi0/README.md`, `packages/flywheel-psi0/src/flywheel_psi0/__init__.py`
- `uv.lock`: chỉ tạo lại bằng lệnh uv lock sau khi rebase (07 mục 3.2 điểm 5)
- `packages/flywheel-psi0/src/flywheel_psi0/trainer/`
- `packages/flywheel-psi0/tests/trainer/`
- `scripts/g0/read_psi0_logging.py`
- `configs/recipes/psi0-stage1.yaml`, `configs/recipes/psi0-stage2.yaml`, `configs/recipes/psi0-stage3.yaml`
- `docs/g0/psi0-logging.md`, `docs/g0/ledger/DA-19.csv`

## Ghi chú cho người làm

- Nguồn: [design 25/10](../../superpowers/specs/2026-10-25-denso-mujoco-and-stage-qa-design.md) mục 6; design 23/10 mục 6.3; 03 mục 5.4 (bản 0.5), mục 8.4.
- Kết quả đọc code ngày 25/10/2026 ở design 25/10 mục 6.2 là điểm bắt đầu.
- DA-07 gộp vào story này (07 bản 0.3); không làm hai lần.
- Ψ₀ dùng fork lerobot `songlin/lerobot@09929d8` (v2.1), `datasets==3.6.0`; giữ đúng phiên bản trong image.

## Kiểm thử

- Test: `FakeTrainer` đi qua lớp bọc log ra `metrics.jsonl` đúng schema.
- Một job ngắn trên Colab bị ngắt giữa chừng rồi tiếp tục, bước và loss nối liền.

## Người phụ trách

- Làm: Dương Đình Hiếu
- Duyệt và merge: Dương Đình Hiếu (người duy nhất, 07 mục 3.4)
- Bình luận: Châu (vận hành Ψ₀), Thông (sổ chi phí, Agent QA/QC)

## Change log

| Ngày | Nội dung | Người |
|---|---|---|
| 25/10/2026 | Tạo story theo design 25/10/2026 mục 11.2 | PO (Hiếu) |
| 25/10/2026 | Thêm AC 7 và nhiệm vụ con 1: story này tạo khung package `flywheel-psi0` vì là story chạy sớm nhất dùng package; các nhiệm vụ con cũ lùi một số | PO (Hiếu) |

## Ghi chép khi làm

- Giờ thực:
- Công cụ AI đã dùng:
- Ghi chú hoàn thành:
- File đã tạo hoặc sửa:
