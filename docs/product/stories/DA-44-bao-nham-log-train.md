# DA-44 · Bỏ báo nhầm của bộ phát hiện log train trên job thật

## Trạng thái

| Trường | Giá trị |
|---|---|
| Trạng thái | Đang làm (PO duyệt 19/11/2026) |
| Người làm | Hiếu, làm cùng Claude (làn Đánh giá; chủ làn là Châu) |
| Làn | Đánh giá (`flywheel-eval`) |
| Story PRD | Sửa DA-08 (F-TRAIN T1–T8); [design 27/10/2026](../../superpowers/specs/2026-10-27-g1-psi0-demo-design.md) mục 10 |
| Nhãn | [Lõi] · `area:core` · `hotfix` của DA-08 |
| Sprint | Sau demo 17/11/2026 |
| Ước lượng | 5 giờ (ước lượng) |
| Phụ thuộc | DA-08 (bộ phát hiện), DA-27 (bộ log cấy), log thật của DA-26 và DA-34 trong `fwdata/` (không commit) |

## Story

Là người đọc chẩn đoán train (kỹ sư và Agent QA/QC), tôi muốn bộ phát hiện F-TRAIN im lặng trên job Ψ₀ khỏe và vẫn bắt lỗi cấy, để mỗi phát hiện T1, T2, T8 là một fact đáng tin chứ không phải báo nhầm mà agent phải diễn giải.

Bối cảnh: [agent-qa mục 3.3](../../g0/agent-qa.md) ghi rằng ngày 6–7/11/2026 T1, T2, T8 báo trên cả ba job fine-tune 40k step khỏe. Trên `origin/master` ngày 19/11/2026 chưa có commit nào sửa (lần cuối các file `diagnosis/train/` đổi là DA-08/6).

## Tiêu chí chấp nhận

1. **T2** chấm một lần đo val nằm sau cửa sổ baseline: khi val đo mỗi 2000 step, điểm chấm không trùng một lần đo đã vào baseline. Test với val mỗi 2000 step: job khỏe không báo, job phẳng vẫn báo.
2. **T5** không cho `start_step` âm (hay trước bản ghi đầu) khi job ngắn hơn `t5.window_steps`; có test.
3. **T1 và T8** có ngưỡng lấy từ dữ liệu theo một luật ghi trên dòng config. Lệnh hiệu chỉnh đọc log train, in ngưỡng đề xuất kèm luật; có unit test trên log tổng hợp. Ngưỡng nào chưa hiệu chỉnh trên log thật thì ghi `giả định`.
4. Test hồi quy: log khỏe có hình như log thật (loss 46 → 0,1; val mỗi 2000 step; grad norm trung vị 7–8, p99 khoảng 50, đỉnh khởi động vài trăm) không cho T1, T2, T8.
5. Lỗi cấy của bộ log DA-27 vẫn bị bắt 3/3 mỗi loại; ghi output của lần chạy.
6. [agent-qa mục 3.3](../../g0/agent-qa.md) ghi điều đã sửa và điều chưa kiểm trên log thật.

## Nhiệm vụ

- [ ] 1. T2 chấm sau cửa sổ baseline, test val mỗi 2000 step (AC 1)
- [ ] 2. T5 không cho `start_step` trước bản ghi đầu, test job ngắn (AC 2)
- [ ] 3. T1 và T8 theo dữ liệu (AC 3)
  - [ ] 3.1 T1 so loss đã làm mượt theo trung vị trượt (`t1.smooth_steps`), không so từng batch
  - [ ] 3.2 Lệnh `fw eval calibrate-train` đọc log khỏe, in ngưỡng đề xuất và luật; unit test trên log tổng hợp
  - [ ] 3.3 Chạy lệnh trên log thật trong `fwdata/`, ghi ngưỡng vào `train.yaml` kèm luật và số job
- [ ] 4. Test hồi quy log khỏe hình thật; chạy bộ log cấy DA-27 với lớp code, ghi output (AC 4, 5)
- [ ] 5. Cập nhật agent-qa mục 3.3 (AC 6)

## Phạm vi file

Theo 07 mục 3.1. pr-guard chặn PR sửa file ngoài danh sách này; file story luôn được sửa.

- `packages/flywheel-eval/src/flywheel/eval/diagnosis/train/`
- `packages/flywheel-eval/src/flywheel/eval/config.py`, `packages/flywheel-eval/src/flywheel/eval/api.py`, `packages/flywheel-eval/src/flywheel/eval/cli.py`
- `packages/flywheel-eval/tests/unit/diagnosis/train/`
- `configs/eval/diagnosis/train.yaml`
- `docs/g0/agent-qa.md`

Ngoài phạm vi, đề xuất PR riêng cho chủ file: bản sạch của bộ log cấy (`packages/flywheel-data/src/flywheel/data/inject/log_defects.py`, `config.py`, `configs/data/inject.yaml`; chủ là Hiếu, DA-27) nên có grad norm và nhịp đo val giống log Ψ₀ thật.

## Chỗ cần quyết hoặc chờ người khác

1. **Đổi nghĩa T1 nhánh spike [Đề xuất].** Design mục 10 nói "tăng quá k lần giá trị nhỏ nhất trong cửa sổ W". Story này so loss đã làm mượt (trung vị trượt) thay vì loss từng batch, vì loss từng batch của job khỏe dao động hơn 100 lần trong 500 step. Nhánh NaN và Inf giữ nguyên. Cần PO (Hiếu) xác nhận; nếu không đồng ý thì chỉ còn cách tăng `k` lên trên 200, và T1 nhánh spike gần như không còn bắt được gì.
2. **Log thật chỉ là job cùng một công thức** (Ψ₀ stage 3, batch và lr như DA-26, DA-34). Ngưỡng hiệu chỉnh đúng cho công thức đó; công thức khác cần chạy lại lệnh hiệu chỉnh.
3. Châu là chủ làn: PR này cần Châu xem phần thay đổi bộ phát hiện.

## Kiểm thử

- `uv run pytest packages/flywheel-eval/tests/unit/diagnosis/train tests/e2e/test_log_defects_detected.py`
- `uv run ruff check`, `uv run mypy`, `uv run lint-imports` theo README gốc; `python3 scripts/repo/check_links.py`.

## Người phụ trách

- Làm: Dương Đình Hiếu, cùng Claude
- Duyệt và merge: Dương Đình Hiếu (07 mục 3.4)
- Bình luận: Châu (chủ làn Đánh giá và DA-08)

## Change log

| Ngày | Nội dung | Người |
|---|---|---|
| 19/11/2026 | Viết story từ agent-qa mục 3.3; PO duyệt làm | Hiếu, Claude |

## Ghi chép khi làm

- Giờ thực: (ghi theo nhiệm vụ con)
- Công cụ AI đã dùng: Claude Code.
