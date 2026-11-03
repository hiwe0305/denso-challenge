# S1-04 · Chi phí fine-tune Ψ₀ (Q5)

_Story: [S1-04](../product/stories/S1-04-chi-phi-finetune-psi0.md). Mục 1 (nhiệm vụ con 1.2): Châu, 24/10/2026. Mục 2 trở đi (nhiệm vụ con 1.1, nhiệm vụ 6, 8): Hiếu, 3–4/11/2026, theo lịch cắt phạm vi của [07 mục 2.4](../product/07-team-workflow.md). Nhiệm vụ 2–5, 7 để sau 13/11/2026._

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

_Cập nhật 3/11/2026: ý 1 đã chốt ở DA-19 (Hiếu, 3/11/2026): `Psi0Trainer` gọi thẳng `scripts/train.py finetune_simple_psi0_config` ở commit ghim `cda3fdf` với bộ tham số của bản cuối `finetune-simple-psi0.sh` (`git show 2830f93^:…`), ghi trong `configs/models/psi0-stage3.yaml` ([psi0-logging.md](psi0-logging.md)). Bản cuối đó (cha của `2830f93`, `4f3720d`) và bản `5236e63` Châu đọc là cùng một blob git (`ff4841e`, kiểm qua API GitHub ngày 3/11/2026), nên bảng 1.2 đúng cho recipe DA-19. Ý 3 có số đo ở mục 3; ý 5 đã làm (`WANDB_MODE=offline`)._

1. **Bản script nào.** `finetune-simple-psi0.sh` đã bị gỡ khỏi `main`. Bản trên `main` hiện ghi cứng một task khác, không nhận task của mình. **[Đề xuất]** Ghim `5236e63` cho S1-04, vì đây là bản khớp batch toàn cục 128 của 03 §3.2. Cần xác nhận bản này khớp image `docker/psi0/` của S1-03.
2. **VLM đã đóng băng sẵn.** AC 1 xếp "toàn phần" trước "đóng băng VLM", nhưng script mặc định đã chạy `--model.no-tune-vlm`. **[Đề xuất]** Gọi cấu hình mặc định là "mặc định (VLM đóng băng)". Chỉ thử mở VLM nếu Hiếu muốn. LoRA chỉ là phương án lùi khi mặc định không vừa bộ nhớ.
3. **Một GPU thay vì 8.** Trên một RTX 5090 hoặc một A100, `CUDA_VISIBLE_DEVICES=0` cho batch toàn cục 16. Muốn giữ 128 thì đặt `gradient_accumulation_steps=8`, khi đó mỗi bước chậm khoảng 8 lần. **[Đề xuất]** Đo giây mỗi bước với batch 16 trước. Giờ GPU cho S bước ở batch 128 tính lại theo số mẫu.
4. **Checkpoint gốc (Q0).** Script dùng `pre.*` và `postpre.*` đúng nhóm spec cho phép. Q0 vẫn chờ PSI Lab xác nhận sạch (S1-03).
5. **wandb.** Script gửi log lên wandb. Chạy probe nên đặt `WANDB_MODE=offline`, để không gửi gì ra ngoài khi chưa có tài khoản đội.

### 1.4 Tác giả thật sự train checkpoint hai bàn thế nào

Đọc `argv.txt` của run `g1wholebodylocomotionpickbetweentablesteleop-v0.simple.flow1000.cosine.lr1.0e-04.b64.gpus4.2604081126` ở `USC-PSI-Lab/psi-model` revision `cb1480f` (revision S1-03 ghim), ngày 3/11/2026: đúng bộ tham số ở bảng 1.2 (`train_batch_size=16`, `max_training_steps=40000`, `learning_rate=1e-4`, warmup 1.000, validation mỗi 500 bước với 20 batch, `no-tune-vlm`), chạy trên **4 GPU**, nên **batch toàn cục là 64**, không phải 128 như mặc định 8 GPU của script.

Hệ quả: recipe DA-19 trên một GPU có batch toàn cục 16. Với 40.000 bước, mỗi lần fine-tune thấy 640.000 mẫu, bằng 1/4 của tác giả (2,56 triệu mẫu, khoảng 41 epoch trên 62.764 khung của gói hai bàn). Các biến thể HE vẫn so được với nhau vì cùng recipe; so với checkpoint của tác giả (mốc so của DA-26) thì khác cả lượng train. Mục 4 tính chi phí cho cả hai cách.

## 2. Chuẩn bị trên Colab (nhiệm vụ con 1.1)

Colab không chạy Docker, nên "image Ψ₀ của S1-03" được dựng lại trên VM theo cách `serve_psi0.sh setup` của S1-03 làm với `PSI0_ENV=image`: cài đúng danh sách gói đọc từ image ghim `ghcr.io/physical-superintelligence-lab/psi0@sha256:0d58…80b2` (`docker/psi0/requirements-image.txt` trên nhánh S1-03 `f19b1a4`, PR #66 chưa merge; file chỉ được tải lên VM, không chép vào nhánh này), rồi cài `psi` editable từ bản clone Ψ₀ ở `cda3fdf`. Không sửa `docker/psi0/`.

Lệnh: [`scripts/g0/colab_train_probe.sh`](../../scripts/g0/colab_train_probe.sh) `setup`, chạy trên VM từ một bản sao của repo.

| Mục | Giá trị |
|---|---|
| Ψ₀ | `cda3fdfafe47cb6fa75400d013de1bd36e3cea05` |
| Gói Python | `requirements-image.txt` của S1-03: `torch 2.7.0+cu126`, `flash_attn 2.7.4.post1` (wheel dựng sẵn), `transformers 4.57.0`, `accelerate 1.7.0`, `lerobot` `09929d8`, `pyarrow 21.0.0` |
| Checkpoint cha | `psi-model` @ `cb1480f`: `pre.fast.1by1.2601091803.ckpt.ego200k.he30k` (4,0 GB), `postpre.1by1.pad36.2601131206.ckpt.he30k` (1,9 GB) |
| Dữ liệu | `psi-data` @ `e78fb93` (train ghim, [psi-data.md](psi-data.md)): `simple/G1WholebodyLocomotionPickBetweenTablesTeleop-v0.zip`, sha256 `6cdf9022…927586` khớp; 99 episode, 62.764 khung |
| Thời gian | A100: dựng môi trường 428 s, tải 38 s. L4: 63 s và 55 s (cache gói của Colab đã ấm; không coi là số chắc chắn). Dùng **8 phút mỗi VM** để ước |

So với môi trường DA-19 (`flywheel_psi0.trainer.colab setup`, giải lại lock của tác giả): cùng `torch`, `torchcodec`, `lerobot`, `numpy`; chỉ khác `transformers` 4.57.0 và 4.57.1 cùng vài gói serve, viz. Trên cùng VM A100, hai môi trường cho cùng tốc độ (0,470 và 0,477 s mỗi bước ở batch 16, mục 3.1).

## Đề xuất cho 03 §3.3

| Dòng | Câu trả lời đề xuất | Trạng thái | Bằng chứng |
|---|---|---|---|
| V8 phần fine-tune | Chưa có | tạm: chưa chạy | Mục 1 (đọc script) |
