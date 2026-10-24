# S1-04 · Chi phí fine-tune Ψ₀ (Q5)

_Bản nháp ngày 24/10/2026, người làm Châu. Story: [S1-04](../product/stories/S1-04-chi-phi-finetune-psi0.md). Chưa chạy fine-tune; mọi số giờ GPU dưới đây là chưa đo._

## 1. Cấu hình mặc định của script công bố (nhiệm vụ con 1.2)

### 1.1 Nguồn và revision

| Trường | Giá trị |
|---|---|
| Repo | [physical-superintelligence-lab/Psi0](https://github.com/physical-superintelligence-lab/Psi0) |
| Script story nhắc tới | `scripts/train/psi0/finetune-simple-psi0.sh`, **không còn trên `main`** |
| Bản đã đọc | [`5236e63` (30/08/2026)](https://github.com/physical-superintelligence-lab/Psi0/blob/5236e633558c6109452da194d0ff1df17b4a3431/scripts/train/psi0/finetune-simple-psi0.sh), bản cuối cùng có file này |
| Commit gỡ file | `2830f93` (29/09/2026, "release sonic 1.1 checkpoint") |
| Script tương ứng trên `main` | [`finetune-sonic-simple-psi0.sh` tại `cda3fdf`](https://github.com/physical-superintelligence-lab/Psi0/blob/cda3fdfafe47cb6fa75400d013de1bd36e3cea05/scripts/train/psi0/finetune-sonic-simple-psi0.sh) (14/10/2026) |

### 1.2 Tham số chính

Số dưới đây đọc từ script, là cấu hình tác giả công bố, chưa chạy lại.

| Tham số | `finetune-simple-psi0.sh` @ `5236e63` | `finetune-sonic-simple-psi0.sh` @ `cda3fdf` |
|---|---|---|
| Config | `finetune_simple_psi0_config` | `finetune_sonic_psi0_config` |
| S (`max_training_steps`) | 40.000 | 40.000 |
| Batch mỗi GPU (`train_batch_size`) | 16 | 32 |
| Số GPU mặc định | 8 (đếm từ `CUDA_VISIBLE_DEVICES`, mặc định `0,…,7`) | 8 |
| Gradient accumulation | 1 | 1 |
| **Batch toàn cục** | **16 × 8 = 128**, khớp 03 §3.2 | **32 × 8 = 256** |
| Learning rate | 1e-4, cosine, warmup 1.000 bước | như trái |
| Optimizer | weight decay 1e-6, betas 0,95 / 0,999, `max_grad_norm` 1,0 | như trái |
| Precision, song song | bf16, DDP qua `torchrun` | như trái |
| Lưu checkpoint | mỗi 10.000 bước, giữ 5 | mỗi 5.000 bước, giữ 5 |
| Validation | mỗi 500 bước, 20 batch | mỗi 1.000 bước, 20 batch |
| VLM | `--model.no-tune-vlm` (đóng băng) | `--model.no-tune-vlm` |
| Checkpoint gốc | `pre.fast.1by1.2601091803.ckpt.ego200k.he30k` và action header `postpre.1by1.pad36.2601131206.ckpt.he30k` | như trái |
| Dữ liệu | `data/simple/<task>` (theo tham số dòng lệnh) | Cố định `G1WholebodyXMoveBendCarryBoxSonic-v0`, bỏ qua tham số `<task>` |
| Chiều action / state | 36 / 36 | 78 / 43 |
| Ảnh | 180 × 320, có tăng cường ảnh | 240 × 320, có tăng cường ảnh |
| Action chunk, exec horizon | 30, 30 | 30, 30 |
| RTC | `--model.rtc`, `max-delay` 8 | `--model.no-rtc` |
| Log | `wandb` | `wandb` |

### 1.3 Điều cần Hiếu quyết trước khi chạy (nhiệm vụ con 2)

1. **Bản script nào.** `finetune-simple-psi0.sh` đã bị gỡ khỏi `main`. Bản trên `main` hiện ghi cứng một task khác, không nhận task của mình. **[Đề xuất]** Ghim `5236e63` cho S1-04, vì đây là bản khớp batch toàn cục 128 của 03 §3.2. Cần xác nhận bản này khớp image `docker/psi0/` của S1-03.
2. **VLM đã đóng băng sẵn.** AC 1 xếp "toàn phần" trước "đóng băng VLM", nhưng script mặc định đã chạy `--model.no-tune-vlm`. **[Đề xuất]** Gọi cấu hình mặc định là "mặc định (VLM đóng băng)". Chỉ thử mở VLM nếu Hiếu muốn. LoRA chỉ là phương án lùi khi mặc định không vừa bộ nhớ.
3. **Một GPU thay vì 8.** Trên một RTX 5090 hoặc một A100, `CUDA_VISIBLE_DEVICES=0` cho batch toàn cục 16. Muốn giữ 128 thì đặt `gradient_accumulation_steps=8`, khi đó mỗi bước chậm khoảng 8 lần. **[Đề xuất]** Đo giây mỗi bước với batch 16 trước. Giờ GPU cho S bước ở batch 128 tính lại theo số mẫu.
4. **Checkpoint gốc (Q0).** Script dùng `pre.*` và `postpre.*` đúng nhóm spec cho phép. Q0 vẫn chờ PSI Lab xác nhận sạch (S1-03).
5. **wandb.** Script gửi log lên wandb. Chạy probe nên đặt `WANDB_MODE=offline`, để không gửi gì ra ngoài khi chưa có tài khoản đội.

## 2. Kết quả đo (nhiệm vụ con 2)

Chưa đo. Chờ image `docker/psi0/` của S1-03 và máy RTX 5090.

## 3. GPU-giờ và USD (nhiệm vụ con 3)

Chưa tính. Sổ `ledger/S1-04.csv` tạo khi có số đo đầu tiên.

## Đề xuất cho 03 §3.3

| Dòng | Câu trả lời đề xuất | Trạng thái | Bằng chứng |
|---|---|---|---|
| V8 phần fine-tune | Chưa có | tạm: chưa chạy | Mục 1 (đọc script) |
