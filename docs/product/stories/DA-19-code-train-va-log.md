# DA-19 · Code train của tác giả, log 3 stage, Colab và client RTC

## Trạng thái

| Trường | Giá trị |
|---|---|
| Trạng thái | Sẵn sàng (PO duyệt 25/10/2026; sửa 27/10/2026) |
| Người làm | Hiếu |
| Làn | Model và phần cứng |
| Story PRD | Story của [design 27/10/2026](../../superpowers/specs/2026-10-27-g1-psi0-demo-design.md) mục 8 · Epic 9 |
| Nhãn | [Adapter] · `epic:9` · `gate:G0` · `area:rl` |
| Sprint | S1–S2 |
| Ước lượng | 26 giờ (khoảng 22–30, ước lượng của SM) |
| Phụ thuộc | Không phụ thuộc người khác. PR `chore-restructure` (07 mục 3.6; mở PR 28/10, merge 29/10/2026) tạo khung package `flywheel-psi0`. Code trên `FakeTrainer` của testkit trong lúc chờ job thật |

## Story

Là trưởng nhóm phụ trách Ψ₀, tôi muốn train cả 3 stage bằng code của tác giả, có log đủ để chấm từng stage, và log inference RTC, để làn Đánh giá và Agent QA/QC phân tích được.

## Tiêu chí chấp nhận

1. Script đọc code ở commit ghim của repo Ψ₀: liệt kê lời gọi `log`, `accelerator.log`, `init_trackers`, `evaluate`, `save_checkpoint` và tên metric; bảng "có sẵn, thiếu, cách lấy" ở `docs/g0/psi0-logging.md`; chạy lại khi đổi commit ghim.
2. `Psi0Trainer` gọi script của tác giả cho stage 1, 2, 3 với cấu hình từ RunPlan; không sửa repo tác giả.
3. Lớp bọc log ghi `metrics.jsonl` đúng schema: phần có sẵn cộng loss theo nhóm action và theo vị trí trong chunk, phương sai dự đoán, phân bố độ mở bàn tay tính lại trên batch val (gồm DA-07).
4. Client RTC trong `Psi0Policy` ghi log inference đúng schema của DA-25: lúc gửi quan sát, lúc nhận chunk, độ trễ, delay d, mức buffer, chỉ số chunk, bước nhảy ở ranh giới chunk.
5. Job trên Colab tiếp tục được từ checkpoint, lưu checkpoint ra kho bền, ghi compute unit vào sổ chi phí; checkpoint trung gian chạy P3, P4.
6. Dữ liệu `internal` hoặc `restricted` không lên Colab; dữ liệu của demo là `public` (design mục 8.4). Ghi chi phí vào `docs/g0/ledger/DA-19.csv`, cột theo [docs/g0/README.md](../../g0/README.md).

## Nhiệm vụ

- [ ] 1. Script đọc code, bảng log (AC 1)
- [ ] 2. `Psi0Trainer` 3 stage (AC 2)
- [ ] 3. Lớp bọc log, `metrics.jsonl` (AC 3)
- [ ] 4. Client RTC và log inference (AC 4)
- [ ] 5. Colab, tiếp tục từ checkpoint, probe, sổ chi phí (AC 5, 6)

## Phạm vi file

Theo 07 mục 3.1. pr-guard chặn PR sửa file ngoài danh sách này; file story luôn được sửa.

- `packages/flywheel-psi0/src/flywheel_psi0/trainer/`, `packages/flywheel-psi0/src/flywheel_psi0/policy/`, `packages/flywheel-psi0/src/flywheel_psi0/probe/`
- `packages/flywheel-psi0/pyproject.toml`, `packages/flywheel-psi0/tests/`
- `scripts/g0/read_psi0_logging.py`
- `configs/models/psi0-stage1.yaml`, `configs/models/psi0-stage2.yaml`, `configs/models/psi0-stage3.yaml`
- `uv.lock`: chỉ tạo lại bằng lệnh uv lock sau khi rebase
- `docs/g0/psi0-logging.md`, `docs/g0/ledger/DA-19.csv`

## Ghi chú cho người làm

- Nguồn: design 27/10 mục 8; 03 mục 7.3 (artifact). Ưu tiên của demo: adapter fine-tune stage 3 (`finetune-simple-psi0.sh`) chạy được trên Colab cho thí nghiệm HE (DA-26); stage 1, 2 chỉ đọc code, không train.
- Khung package `flywheel-psi0` do PR restructure tạo; story này không tạo khung.
- Ψ₀ dùng fork lerobot `songlin/lerobot@09929d8` (v2.1), `datasets==3.6.0`; giữ đúng trong image.

## Kiểm thử

- `FakeTrainer` đi qua lớp bọc log ra `metrics.jsonl` đúng schema.
- Một job ngắn trên Colab ngắt giữa chừng rồi tiếp tục, bước và loss nối liền.
- Policy giả có độ trễ ghi log RTC đúng schema.

## Người phụ trách

- Làm: Dương Đình Hiếu
- Duyệt và merge: Dương Đình Hiếu (người duy nhất, 07 mục 3.4)
- Bình luận: Châu (đọc log cho Agent QA/QC), Long (sổ chi phí)

## Change log

| Ngày | Nội dung | Người |
|---|---|---|
| 25/10/2026 | Tạo story | PO (Hiếu) theo design 25/10/2026 (đã xóa) |
| 25/10/2026 | Bỏ khung package (chuyển vào PR restructure); thêm client RTC từ DA-23; recipe ở `configs/models/` | PO (Hiếu) theo design chia làn (đã xóa) |
| 27/10/2026 | Bỏ phần robot DENSO; Colab nhận dữ liệu `public`; ưu tiên fine-tune stage 3 cho HE | PO (Hiếu) theo design 27/10/2026 |
| 28/10/2026 | Sửa hạn PR `chore-restructure` theo 07 mục 3.6 bản 0.6: mở 28/10, merge 29/10 | PO (Hiếu) |

## Ghi chép khi làm

- Giờ thực:
- Công cụ AI đã dùng:
- Ghi chú hoàn thành:
- File đã tạo hoặc sửa:
