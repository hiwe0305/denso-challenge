# S1-04 · Chi phí fine-tune Ψ₀ (Q5)

_Story: [S1-04](../product/stories/S1-04-chi-phi-finetune-psi0.md). Mục 1 (nhiệm vụ con 1.2): Châu, 24/10/2026. Mục 2 trở đi (nhiệm vụ con 1.1, nhiệm vụ 6, 8): Hiếu, 3–4/11/2026, theo lịch cắt phạm vi của [07 mục 2.4](../product/07-team-workflow.md). Nhiệm vụ 2–5, 7 để sau 13/11/2026._

## Kết luận

- **Recipe** (mục 1): stage 3 là `scripts/train.py finetune_simple_psi0_config` với tham số của bản cuối `finetune-simple-psi0.sh`: 40.000 bước, batch 16 mỗi GPU, learning rate 1e-4 cosine, warmup 1.000, VLM đóng băng. Checkpoint hai bàn của tác giả chạy trên 4 GPU, nên batch toàn cục của tác giả là 64; trên một GPU recipe chỉ thấy 1/4 số mẫu đó.
- **Số đo** (mục 3, Colab 3–4/11/2026): batch 16 chạy 0,47 s/bước trên A100 và 0,71 s/bước trên L4; VRAM đỉnh 17,7 GB (batch 64: 19,6 GB), vừa L4 24 GB. Job bị chặn ở CPU nạp dữ liệu, không phải GPU. Ngắt rồi chạy lại nối liền đúng loss. H100 không dùng được trên tài khoản.
- **Compute unit** (mục 4): một lần 40.000 bước khoảng 16,6 CU trên L4 (val mỗi 2.000 bước) hoặc 44 CU trên A100; 8 lần của demo khoảng 133 CU trên L4, gần hết 140,8 CU còn lại. **[Đã chốt]** (Hiếu, 4/11/2026): L4, giữ recipe DA-19. Giữ cả chu kỳ val 500 bước của recipe thì 19,2 CU mỗi lần, 153 CU cho 8 lần; còn mở: val mỗi 2.000 bước (133 CU) và cách bù ngân sách.
- **Eval HE** (mục 5): 450 episode tới 12/11. Ở `mujoco` khoảng 7,5 giờ `rtx3060`, 0 CU; ở `mujoco_isaac` khoảng 185 giờ và 358 CU, không vừa. [Đề xuất] eval HE ở `mujoco` nếu lượt chạy lại của S1-03 cho phép, Isaac chỉ cho video demo.
- Đã tiêu cho phiên đo: khoảng 6,2 CU (A100 5,65; L4 0,53), trong trần 14 CU Hiếu duyệt.

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

## 3. Đo stage 3 trên Colab (nhiệm vụ 6)

_Thực đo ngày 3–4/11/2026 bằng `colab_train_probe.sh probe <batch> <bước> <chu kỳ> <bước ngắt>`. Hiếu duyệt trước khi chạy: A100 cộng H100, trần 14 CU; sau đó duyệt thêm L4 khoảng 1 CU thay cho H100. Recipe stage 3 của DA-19, cặp `psi0-baseline-egodex-he`, chỉ đổi batch, số bước, chu kỳ checkpoint và validation; validation giữ 20 batch của recipe._

**H100 không chạy được**: `colab new --gpu H100` bị từ chối ("không có quota hoặc quyền cho accelerator này"). Phần ngân sách đó dùng cho L4.

### 3.1 Số đo

"s/bước" là trung vị khoảng cách giữa hai dòng train liền nhau trong `metrics.jsonl`, bỏ bước có checkpoint hoặc validation. VRAM: đỉnh `torch.cuda.max_memory_allocated` do launcher ghi, và đỉnh `memory.used` của `nvidia-smi` lấy mẫu mỗi giây.

| Máy | Batch | Bước đo | s/bước (p90) | Mẫu/s | VRAM torch / nvidia-smi | GPU bận (trung vị) | Một lần val 20 batch |
|---|---|---|---|---|---|---|---|
| A100-SXM4-40GB | 16 | 445 (hai lần chạy) | 0,470 (0,49) | 34,1 | 16,2 / 17,7 GB | 37% | khoảng 50 s |
| A100 | 32 | 148 | 0,644 (0,73) | 49,7 | 16,2 / 18,0 GB | 41% | khoảng 60 s |
| A100 | 64 | 58 | 0,873 (0,94) | 73,3 | 18,8 / 19,6 GB | 30% | khoảng 75 s |
| A100, môi trường DA-19 | 16 | 148 | 0,477 (0,51) | 33,5 | 16,2 / 17,3 GB | 38% | khoảng 57 s |
| L4 24 GB | 16 | 148 | 0,710 (0,79) | 22,5 | 16,2 / 17,0 GB | 77% | khoảng 85 s |
| L4 | 64 | 58 | 2,308 (2,32) | 27,7 | 18,8 / 19,2 GB | 78% | khoảng 100 s |

Không cấu hình nào hết bộ nhớ. Batch toàn cục = batch mỗi GPU, vì một GPU và `gradient_accumulation_steps=1`.

| Mục khác | Số đo |
|---|---|
| Khởi động tới bước đầu | 42–78 s (nạp checkpoint cha, dựng dataloader) |
| Lưu một checkpoint | thêm khoảng 31 s mỗi lần trên A100 (9,5 GB mỗi `ckpt_<step>` theo DA-19) |
| Ngắt và chạy lại (batch 16, 400 bước, checkpoint mỗi 200, giết ở bước 250) | Lần 1 bắt đầu đúng ở `ckpt_200`, chạy tới 400, `infra_status = ok`. Ở 51 bước trùng (200–250), loss hai lần trùng nhau đúng từng số |
| Giá máy | A100 6,73 CU/giờ, L4 1,94 CU/giờ (độ tăng của `colab usage` khi mở phiên) |

### 3.2 Vì sao chậm hơn số smoke của DA-19

DA-19 đo 0,32 s/bước ở batch 16. Lần này, cùng môi trường DA-19 trên cùng VM, ra 0,477 s. Khác biệt không do môi trường. Trên A100, 12 vCPU chạy khoảng 95% (16 tiến trình `pt_data`, tiến trình chính 100%), GPU chỉ bận 20–60%: **job bị chặn ở khâu nạp dữ liệu** (giải mã video và tăng cường ảnh trên CPU), không phải ở GPU. Lần smoke DA-19 chỉ chạy 60 bước và dừng mỗi 20 bước để lưu checkpoint và val, nên worker kịp nạp sẵn batch trong lúc dừng; đây là giải thích hợp lý nhất, chưa kiểm riêng. Số dùng để ước là số 400 bước liên tục.

Hệ quả: GPU mạnh hơn không giúp nhiều. L4 có cùng 12 vCPU, GPU bận 77%, chậm hơn A100 1,5 lần ở batch 16 nhưng rẻ hơn 3,5 lần mỗi giờ. Batch lớn hơn rẻ hơn theo mẫu (A100: 34 → 73 mẫu/s từ batch 16 lên 64).

### 3.3 Chạy lại từ checkpoint tốn gì

Ψ₀ ở `cda3fdf` khôi phục vị trí dữ liệu bằng cách đọc rồi bỏ từng batch qua dataloader (`scripts/train.py`, vòng `for local_step, batch in enumerate(trainer.train_dataloader)` với `skip_resumed_steps`), số batch bỏ là vị trí trong epoch hiện tại. Đo: bỏ 200 batch batch 16 thêm 74 s, khoảng 43 mẫu/s. Một lần chạy lại vì vậy tốn: dựng VM (8 phút) + kéo checkpoint từ Drive + tới một epoch đọc bỏ (62.764 khung / 43 mẫu/s ≈ 24 phút trên gói 99 episode; với N = 20 hay 80 episode thì ít hơn). Ước lượng, chưa đo trọn.

## 4. Quy ra compute unit (nhiệm vụ 6)

_Ước lượng từ số đo mục 3.1, chưa chạy trọn một lần 40.000 bước._ Mỗi lần fine-tune chạy trên một VM riêng: dựng VM 8 phút, khởi động 60 s, S bước × s/bước, validation ở bước 0 và mỗi chu kỳ, checkpoint mỗi 10.000 bước × 31 s. Không tính thời gian chạy lại (mục 3.3) và eval (mục 5).

| Cấu hình | Mẫu thấy | Máy | Val mỗi 500 bước (recipe) | Val mỗi 2.000 bước |
|---|---|---|---|---|
| R1 · recipe DA-19 trên 1 GPU: batch 16 × 40.000 bước | 640.000 | A100 | 6,5 giờ, **44,0 CU** | 5,7 giờ, 38,3 CU |
| R1 | | L4 | 9,9 giờ, 19,2 CU | **8,5 giờ, 16,6 CU** |
| R2 · batch toàn cục của tác giả: 64 × 40.000 bước | 2.560.000 | A100 | 11,6 giờ, 77,9 CU | 10,3 giờ, 69,5 CU |
| R2 | | L4 | 28,0 giờ, 54,3 CU (quá 24 giờ, phải chạy lại ít nhất một lần) | 26,4 giờ, 51,2 CU |
| R3 · batch 64 × 10.000 bước | 640.000 | A100 | 3,0 giờ, 20,3 CU | 2,7 giờ, 18,2 CU |
| R3 | | L4 | 7,1 giờ, 13,8 CU | 6,7 giờ, 13,1 CU |

**8 lần fine-tune của demo** (DA-26 HE-1: V-EGO, V-NOEGO ở N = 20 và 80; DA-34: A, C, C-NOEGO, C+):

| Cấu hình | A100, val mỗi 500 | L4, val mỗi 2.000 | Giờ máy L4 (tuần tự) |
|---|---|---|---|
| R1 | 352 CU | **133 CU** | 68 giờ |
| R2 | 623 CU | 410 CU | 211 giờ |
| R3 | 163 CU | 105 CU | 54 giờ |

Số dư lúc 00:02 ngày 4/11/2026 là 140,81 CU, và đang giảm vì các phiên khác cùng tài khoản: `wam-audit-l4` (dự án khác, 1,94 CU/giờ, khoảng 47 CU mỗi ngày nếu để chạy) và `s103psi0` (A100 của S1-03, 6,73 CU/giờ). Ước 208 CU trước đây (8 × 26 CU từ smoke DA-19) thấp hơn R1 trên A100 khoảng 40%.

### 4.1 Đề xuất và quyết định

1. **[Đã chốt]** (Hiếu, 4/11/2026) **Máy: L4, không phải A100.** Job bị chặn ở CPU, nên L4 rẻ hơn A100 2,3 lần mỗi lần fine-tune R1. Colab cho chạy nhiều phiên cùng lúc (đã có 3 phiên song song ngày 3/11), nên 8 lần × 8,5 giờ chia 3 phiên song song xong trong khoảng một ngày rưỡi.
2. **[Đã chốt]** (Hiếu, 4/11/2026) **Recipe: R1 (giữ nguyên tham số DA-19).** R1 chỉ khác tác giả ở số GPU. R2 đúng batch của tác giả nhưng 8 lần cần 410 CU, gấp 3 lần số dư. R3 đúng batch toàn cục nhưng đổi số bước và lịch learning rate: là thay đổi recipe, cần Hiếu chốt và phải dùng chung cho mọi nhánh (spec 7.3).
3. **[Đề xuất] Validation mỗi 2.000 bước thay vì 500**, giữ 20 batch. Chưa chốt; tới khi chốt, chu kỳ 500 của recipe vẫn áp, nên 8 lần là 153 CU. Validation không đổi quá trình train, nhưng ít điểm `val` hơn cho bộ kiểm DA-08 (21 điểm thay vì 81 mỗi lần). Tiết kiệm 2,6 CU mỗi lần trên L4.
4. **[Đề xuất] Ngân sách** (còn mở): R1 trên L4 cần khoảng 153 CU cho 8 lần (133 CU nếu val mỗi 2.000 bước), gần hết số dư, chưa tính chạy lại và eval. Hiếu cần chọn một trong: dừng các phiên không cần (`wam-audit-l4` của dự án khác), mua thêm CU (gói 100 CU giá khoảng 9,99 USD, giả định theo DA-19), hoặc giảm số lần fine-tune. R3 (105 CU) bị loại vì Hiếu chọn giữ recipe.
5. **Drive**: mỗi lần R1 để lại 4 checkpoint × 9,5 GB = 38 GB; 8 lần là 304 GB, quá 215 GB còn trống (DA-19). Chỉ giữ checkpoint cuối của mỗi lần trên Drive.

## 5. Giờ máy eval của HE (nhiệm vụ 8)

_Ước lượng ngày 4/11/2026 từ số đo S1-03 (`docs/g0/psi0-eval.md` mục 3 trên nhánh `S1-03-psi0-eval`, PR #66, chưa merge) và design mục 4.3, 7.4. Chưa chạy eval nào cho S1-04._

### 5.1 Số đo đầu vào (S1-03)

| Chế độ | Thời gian một episode | Máy | Ghi chú |
|---|---|---|---|
| `mujoco` | khoảng 60 s (90 episode, 1.200 bước, 50 lần `/act`) | `rtx3060`, server Ψ₀ cùng máy (7,2 GB VRAM) | Client đỉnh 3,3 GiB RAM. Mọi lượt dùng file task của SIMPLE `6d10628` (lỗi spawn); thời gian không phụ thuộc lỗi này |
| `mujoco_isaac` | khoảng 24,6 phút (1 episode: 1.715 s tường, trừ khoảng 4 phút khởi động Isaac) | Client Isaac trên `rtx3060`, server Ψ₀ trên Colab L4 (1,94 CU/giờ) | Server và Isaac không cùng vừa card 12 GB. Chỉ một điểm đo; README Ψ₀ báo 6–10 phút |

Tập eval: `psi-data` `simple-eval` chỉ có **10 điều kiện mỗi mức** (S1-03, S1-07). "30 điều kiện × 3 mức" của design mục 7.3 thực tế là 10 điều kiện × 3 lượt × 3 mức = 90 episode mỗi checkpoint. Gói eval ghim `de140d6` có thêm mức `hard`; HE chỉ dùng Level 0, 1, 2.

### 5.2 Khối lượng tới 12/11/2026

| Việc | Checkpoint | Episode |
|---|---|---|
| DA-26 HE-1 sơ bộ | V-EGO, V-NOEGO ở N = 20 và 80, cộng mốc so của tác giả | 5 × 90 = 450 |
| DA-34 (task khay, `mujoco` cố định ở AC 3) | A, C, C-NOEGO, C+, cộng C+ trên điều kiện C hỏng | 4 × 90 + tối đa 90 = tối đa 450 |

### 5.3 Giờ máy

| Phương án cho HE (450 episode) | Giờ máy | CU | Vừa trước 12/11 không |
|---|---|---|---|
| `mujoco` trên `rtx3060` | khoảng 7,5 giờ, tuần tự | 0 | Có |
| `mujoco_isaac`, số đo S1-03 (24,6 phút) | khoảng 185 giờ `rtx3060` cộng 185 giờ L4 cho server | khoảng 358 | Không: quá cả số dư (140 CU) lẫn 8 ngày còn lại |
| `mujoco_isaac`, theo README (6–10 phút) | 45–75 giờ | 87–146 | Không, nếu cộng 133 CU fine-tune |

Design mục 4.3 ước 144 giờ cho lưới HE đầy đủ (12 điểm, 8 phút mỗi episode). Với số đo S1-03, chỉ phần sơ bộ của HE trên Isaac đã vượt ngân sách. DA-34 ở `mujoco` thêm khoảng 7,5 giờ `rtx3060` nếu episode khay dài như episode hai bàn (giả định; episode khay chưa đo).

### 5.4 Rút gọn khi phải dùng Isaac [Đề xuất]

Theo design mục 7.4 và số đo trên, theo thứ tự:

1. **Eval HE ở `mujoco`** nếu lượt chạy lại của S1-03 với file task `b75c678` cho checkpoint tác giả đạt gần số công bố ở `mujoco` (Q-27C, quyết ở S1-03 AC 10). 7,5 giờ, 0 CU. Đây là phương án chính.
2. **Isaac chỉ cho video demo** (design mục 7.6: cùng điều kiện, ba cột, hai mức N): khoảng 10 episode, 4 giờ, 8 CU.
3. Nếu `mujoco` không dùng được: **Isaac một lượt, chỉ Level 0** (10 episode mỗi checkpoint, 50 episode): khoảng 20 giờ, 40 CU, ghi "sơ bộ". Một lượt cả ba mức (150 episode) là 62 giờ, 119 CU, không vừa nếu giữ 8 lần fine-tune R1.
4. "Giảm còn 20 điều kiện mỗi mức" của design mục 7.4 không áp được, vì tập eval chỉ có 10. Bỏ V-EGO10 và giữ N = 20, 80 đã có trong khối lượng ở mục 5.2.

Mỗi rút gọn ghi một `Decision` (DA-26 AC 8).

### 5.5 Isaac Sim trên Colab (Q-27D)

**Chưa thử** trong phiên này (ngoài phạm vi Hiếu giao cho lịch 3/11). Dữ kiện đã có: A100 không có RT core nên không render được Isaac; L4 có RT core, 24 GB VRAM và 52 GB RAM, đủ cho server Ψ₀ (7,2 GB, khoảng 6 GB RAM) cùng client Isaac (5,7 GB, đỉnh 11,5 GiB RAM) trên một VM. Colab không chạy Docker, nên phải cài Isaac Sim 4.5 bằng pip; chưa biết có chạy được. Nếu được, mỗi episode vẫn tốn khoảng 0,8 CU (24,6 phút × 1,94 CU/giờ): không rẻ hơn, chỉ giải phóng `rtx3060` và cho chạy song song nhiều VM.

## Đề xuất cho 03 §3.3

| Dòng | Câu trả lời đề xuất | Trạng thái | Bằng chứng |
|---|---|---|---|
| V8 phần fine-tune | Stage 3 trên một GPU Colab: recipe DA-19 (batch 16 × 40.000 bước) vừa 24 GB (đỉnh 17,7 GB; batch 64 là 19,6 GB). Job bị chặn ở CPU nạp dữ liệu: A100 0,47 s/bước, L4 0,71 s/bước. Một lần khoảng 8,5 giờ, 16,6 CU trên L4 (44 CU trên A100); 8 lần của demo khoảng 133 CU. Tiếp tục được từ checkpoint, loss nối liền | tạm: số đo từ vài trăm bước, chưa chạy trọn 40.000 bước; recipe và chu kỳ val chờ Hiếu chốt (mục 4.1) | Mục 3, 4; `ledger/S1-04.csv`; `scripts/g0/colab_train_probe.sh` |
