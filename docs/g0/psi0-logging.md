# Log của code train Ψ₀: có sẵn, thiếu, cách lấy

_Ngày 3/11/2026. Story [DA-19](../product/stories/DA-19-code-train-va-log.md) nhiệm vụ con 1 (AC 1). Đọc code Ψ₀ ở commit ghim `cda3fdf` bằng [`scripts/g0/read_psi0_logging.py`](../../scripts/g0/read_psi0_logging.py); phần giữa hai dấu `read_psi0_logging.py` do script sinh, phần còn lại viết tay._

## Kết luận

- **Script stage 3 không còn ở commit ghim.** `scripts/train/psi0/finetune-simple-psi0.sh` bị tác giả xóa ở commit `2830f93` (28/09/2026, "release sonic 1.1 checkpoint"), trước `cda3fdf`. Config `finetune_simple_psi0_config` và `scripts/train.py` vẫn còn. Script thay thế `finetune-sonic-simple-psi0.sh` dùng layout SONIC 78 chiều, không phải layout 36 chiều của task hai bàn. **[Đã chốt]** (Hiếu, 3/11/2026) `Psi0Trainer` gọi thẳng `scripts/train.py finetune_simple_psi0_config` qua `torchrun`, với bộ tham số lấy từ bản cuối của `finetune-simple-psi0.sh` (`git show 2830f93^:scripts/train/psi0/finetune-simple-psi0.sh`), ghi vào `configs/models/psi0-stage3.yaml`. Không sửa repo tác giả, không đổi commit ghim. 03 mục 7 và design còn viết "gọi `finetune-simple-psi0.sh`"; sửa hai tài liệu đó là việc của PO, ngoài phạm vi story này.
- **Log có sẵn chỉ qua `accelerate` tới W&B.** Mọi số đi qua `Trainer.log()` → `accelerator.log(..., step=global_step)`. Không có file log cục bộ nào. Script của tác giả đặt `--log.report_to=wandb`; trên Colab không có khóa W&B thì phải đặt `WANDB_MODE=offline`.
- **Có sẵn:** `train/loss`, `train/epoch`, `train/lr_act` cùng `lr_<nhóm>`, `train/grad_norm_act`, `train/grad_norm_vlm` (khi VLM được train), `eval/loss`, và sai số L1 theo 8 nhóm action trên val (`eval/<dataset>/err_l1_hand_joints`, `err_l1_arm_joints`, `err_l1_torso_rpy`, `err_l1_height`, `err_l1_vx`, `err_l1_vy`, `err_l1_vyaw`, `err_l1_target_yaw`). Phép chia nhóm này cứng cho layout 36 chiều (`src/psi/config/transform.py`, `ActionStateTransform.denormalize_L1_action_err`), khớp layout của design mục 9.
- **Thiếu, lớp bọc phải tính:** `grad_norm_vlm` khi VLM đóng băng (stage 3 dùng `--model.no-tune-vlm`, Ψ₀ khi đó không log trường này nên T8a của DA-08 không kiểm được), loss theo vị trí trong chunk, phương sai và độ lệch chuẩn của action dự đoán, độ lệch chuẩn của action đích, phân bố độ mở bàn tay (DA-07), VRAM, throughput, thời gian chạy, và các mã định danh (`run_plan_id`, `job_id`, `checkpoint_id`, `release_id`, `attempt`).

## Cách lớp bọc lấy phần thiếu mà không sửa code tác giả

**[Đề xuất]** Lớp bọc là một launcher Python trong `flywheel_psi0.trainer`, chạy trong cùng tiến trình với `scripts/train.py` (qua `runpy`). Trước khi chạy, nó bọc các phương thức của `FinetuneTrainer`:

| Phương thức | Bọc để | Ra trường |
|---|---|---|
| `Trainer.log(metrics)` | Chép mỗi dict `train/*`, `eval/*` thành một dòng `TrainingMetric` | `step`, `epoch`, `split`, `loss`, `lr`, `grad_norm_*`, `wall_time_s`, `vram_gb`, `throughput` |
| `FinetuneTrainer.inference(eval_model, batch)` | Giữ action dự đoán `(B, Tp, Da)` và `batch["actions"]` của mỗi batch val | `loss_by_group`, `loss_by_chunk_pos`, `pred_var_by_dim`, `pred_std`, `target_std`, `hand_open_hist` |
| `FinetuneTrainer.training_step(batch)` | Giữ batch train; trong lúc chạy, `LossTap` đứng thay `torch.nn.functional` của module trainer và chép kết quả `mse_loss(..., reduction="none")` | `loss_by_group`, `loss_by_chunk_pos` trên dòng train |
| `Trainer.log` ở bước validation | Trước khi ghi dòng train, chạy `inference()` trên batch train của bước đó (chỉ khi `ddp` hoặc một tiến trình) | `pred_var_by_dim`, `pred_std`, `target_std`, `hand_open_hist` trên dòng train |
| `FinetuneTrainer.clip_grad_norms()` | Gọi sau `backward`, trước `optimizer.step()` và `zero_grad()`. Khi Ψ₀ không có nhóm VLM trong kết quả, cộng bình phương norm gradient của mọi tham số ngoài `action_header.`; VLM đóng băng thì bằng 0. Không bọc `training_step`: lúc nó trả về, gradient đã bị xóa nên số đo luôn bằng 0 | `grad_norm_vlm` |

`evaluate()` đã gọi `inference()` trên `val_num_batches` batch val (20 trong bộ tham số stage 3), nên phần tính thêm không chạy lại model. Phần tính số chỉ dùng mảng, kiểm được trên CPU với `FakeTrainer` (nhiệm vụ con 3).

**Độ mở bàn tay** (DA-07, `flywheel_psi0.trainer.val_stats`). **[Đã chốt]** (Hiếu, 3/11/2026). Mốc mở là tư thế mở của SIMPLE, `init_qpos = 0` cho cả 7 khớp Dex3 mỗi tay (`simple/robots/g1_sonic.py`). Mốc nắm lấy từ dữ liệu: trong `stats_psi0.json` của task hai bàn, mọi khớp tay có một cận bằng 0, cận kia là lần nắm sâu nhất của người teleop, sâu hơn `close_qpos` của SIMPLE (ngón trỏ tới 1,5 rad so với 0,5). Độ mở của một khớp giảm tuyến tính từ 1 ở tư thế mở về 0 ở cận xa nhất; độ mở của một tay là trung bình 7 khớp. `hand_open_hist` là histogram 10 ngăn trên [0, 1], gộp hai tay. Tính trong không gian đã chuẩn hóa nên chỉ cần cận min/max của `stats_psi0.json`, không cần đổi về radian.

**Dòng nào mang số đo nào.** **[Đã chốt]** (Hiếu, 3/11/2026; sửa cùng ngày từ "chỉ dòng val" thành "cả hai dòng"). Dòng `val` mang mọi số đo tính trên action lấy mẫu từ batch val. Dòng `train` mang `loss_by_group` và `loss_by_chunk_pos` ở **mọi bước**: đây là chính loss train của Ψ₀ (MSE vận tốc flow matching) tách theo nhóm và vị trí, lấy từ `F.mse_loss(..., reduction="none")` trước khi Ψ₀ cộng lại, nên không tốn thêm lần chạy model nào. Vì là không gian vận tốc, các giá trị này so được giữa các nhóm trong cùng dòng, không so được với dòng val. Mảng được lấy trước mask RTC; để khớp loss Ψ₀ thật sự train, lớp bọc bỏ `--model.max-delay` vị trí đầu (8 ở stage 3) khỏi cả hai phần tách trên dòng train (Hiếu, 3/11/2026), nên `loss_by_chunk_pos[i]` của dòng train là vị trí `8 + i` của chunk và danh sách dài 22 thay vì 30. Dòng val giữ đủ 30 vị trí. Ở mỗi bước validation, launcher còn lấy mẫu action trên batch train của bước đó (một lần `inference()` của tác giả, thêm khoảng 5% thời gian eval, ước lượng chưa đo), nên dòng train ở bước đó có thêm `pred_var_by_dim`, `pred_std`, `target_std`, `hand_open_hist`. Nhờ vậy reader DA-08 hiện tại chạy được T4, T5, T6 mà không phải sửa (issue #44 hết gấp); dòng val vẫn giữ để so train với val.

Stage 1 và 2 chỉ đọc code (design mục 8): stage 1 log `action_accuracy`, `action_l1_loss` trên token FAST, không có loss flow; stage 2 log giống stage 3 trừ `state_drop_frac`.

## Chạy một stage (nhiệm vụ con 2)

`flywheel_psi0.trainer.Psi0Trainer` đọc recipe `configs/models/psi0-stage{1,2,3}.yaml`, điền phần theo job (dữ liệu, checkpoint cha, seed, thư mục ra) từ `TrainSpec`, rồi chạy `torchrun -m flywheel_psi0.trainer.launch <launch.json>` từ thư mục gốc Ψ₀, bằng Python của `.venv-psi`. Launcher gắn các hook ở bảng trên rồi chạy nguyên `scripts/train.py` của tác giả. Thư mục job `runs/<job_id>/` có `metrics.jsonl`, `launch.json`, `result.json` (thư mục run và checkpoint cuối của Ψ₀, trạng thái) và `psi0/` (`--train.output_dir`).

- Recipe stage 3 giữ đúng mọi cờ của bản cuối `finetune-simple-psi0.sh`, so từng cờ với `git show 2830f93^:…`. Khác duy nhất là cờ theo job, cộng bốn cờ để chạy lại: `--timestamp` (lấy từ `job_id`), `--train.output_dir`, `--train.resume_from_checkpoint=latest`, `--train.skip_resumed_steps`.
- Argv của cả ba stage được kiểm bằng chính `tyro` và `DynamicLaunchConfig` của Ψ₀ ở `cda3fdf` (bước đầu của `scripts/train.py`, không cần GPU): parse đúng.
- Điều kiện của môi trường Ψ₀: có `.env` ở thư mục gốc (`scripts/train.py` chạy `assert load_dotenv()`; `cp .env.sample .env`), và `pyarrow` import được, vì launcher import `flywheel.contracts`. `Psi0Trainer` đặt `WANDB_MODE=offline` và thêm `src/` của `flywheel-psi0`, `flywheel-contracts` vào `PYTHONPATH`. `.venv-psi` trên laptop hiện lệch phiên bản (pyarrow cần NumPy ≥ 2, venv có 1.26.4) vì `uv.lock` của clone bị sửa cục bộ; môi trường cài đúng từ `uv.lock` của tác giả không gặp lỗi này.
- Job GPU thật đầu tiên: xem mục dưới.

## Chạy stage 3 trên Colab, ngắt và chạy lại (nhiệm vụ con 5)

_Thực đo ngày 3/11/2026, một lần chạy trên một A100-SXM4-40GB của Colab Pro, bằng `python -m flywheel_psi0.trainer.colab setup|smoke`. Recipe stage 3, cặp checkpoint `psi0-baseline-egodex-he`, dữ liệu psi-data `G1WholebodyLocomotionPickBetweenTablesTeleop-v0`. Override cho lần chạy thử: 60 bước, checkpoint và validation mỗi 20 bước, 2 batch val, `warmup_steps=0`._

| Mục | Kết quả |
|---|---|
| Ngắt | Lần 0 bị giết khi dòng train của bước 30 xuất hiện; dòng cuối là bước 31; checkpoint cuối `ckpt_20` |
| Chạy lại | Lần 1 bắt đầu ở bước 20, chạy tới bước 59, lưu `ckpt_60`, `infra_status = ok` |
| Nối liền | Ở 12 bước trùng (20–31), loss và lr của hai lần trùng nhau tới 4 chữ số: Ψ₀ khôi phục vị trí dữ liệu (`--train.skip_resumed_steps`) và trạng thái RNG |
| `metrics.jsonl` | 77 dòng, đều đúng `TrainingMetric`; reader DA-08 bỏ 13 dòng trùng của phần nối, còn 60 bước train và 4 lần val. Lưu ở `packages/flywheel-psi0/tests/unit/trainer/fixtures/metrics_colab_smoke.jsonl` |
| Đỉnh VRAM | 16,2 GB (batch 16): không vừa `rtx3060` 12 GB; L4 24 GB vừa (suy ra, chưa chạy) |
| Throughput | Trung vị 49,3 mẫu/s, tức 3,1 bước/s |
| Checkpoint | 9,5 GB mỗi `ckpt_<step>` (`model.safetensors`, `optimizer.bin`, scheduler, RNG) |
| Chi phí | 6,73 CU/giờ (`colab usage`); phiên 68 phút, khoảng 7,6 CU, gồm khoảng 20 phút VM rỗi sau một lần cài flash-attn lỗi. Một lần fine-tune 40000 bước ước khoảng 26 CU (`docs/g0/ledger/DA-19.csv`) |

DA-08 trên log thật: T8 báo `grad_norm_action = 153,7` ở bước 0 (ngưỡng 10), phần lớn do lần chạy thử bỏ 1000 bước warmup của recipe. T6 bỏ qua các chiều 0–6 (tay trái) và 31 (chiều cao thân) vì `target_std = 0` trên batch train: trong task hai bàn hai nhóm này không đổi, nên layout G1 của DA-01 nên ghi điều đó.

**Môi trường Ψ₀ ở commit ghim không dựng được theo README.** Ba chỗ phải sửa trong `colab.py`, đều không đụng repo tác giả:

1. `uv.lock` ở `cda3fdf` là hai lock bị trộn: khóa `[package.optional-dependencies]` lặp, khoảng 30 gói ở hai phiên bản (mirror Tsinghua và PyPI), thiếu mục `xyzservices`; `uv sync` không parse được. `repair_lock` đổi URL mirror sang PyPI (cùng đường dẫn, cùng hash), bỏ bản trùng, giữ bản mới hơn của gói hai phiên bản; rồi `uv pip install -e . --group psi -c <368 ràng buộc từ lock>` giải lại với mọi phiên bản lock có. Kết quả giữ đúng `torch 2.7.0`, `numpy 1.26.4`, `pyarrow 21.0.0`, `datasets 3.6.0`, `transformers 4.57.1`, `lerobot` từ `songlin/lerobot@09929d8`. `.venv-psi` trên laptop lệch NumPy chính vì lần giải lại không có ràng buộc này.
2. Colab đặt `UV_SYSTEM_PYTHON`, nên `uv` cài vào Python 3.13 của hệ thống; phải gỡ biến đó và chỉ định `--python .venv-psi/bin/python`.
3. Qwen3-VL được nạp với `flash_attention_2`: không có flash-attn thì train không chạy (README chỉ nói fallback SDPA cho inference trên XPU). Cài `flash_attn 2.7.4.post1` từ wheel dựng sẵn `cu12torch2.7cxx11abiTRUE-cp311`, với `--no-config` để `uv` không đòi build theo `pyproject` của Ψ₀.

**Kho bền là Google Drive.** **[Đã chốt]** (Hiếu, 3/11/2026). Mỗi VM mới gắn Drive bằng `colab drivemount -s <session> /content/drive`; Hiếu đã cấp quyền một lần ngày 3/11, lần gắn sau trên cùng tài khoản không cần trình duyệt (đã thử: gắn lại không hỏi, ghi được từ cả kernel lẫn shell `colab ssh`; Drive còn 215 GB trống). Thư mục đích mặc định `MyDrive/denso/da19/<job_id>`.

- `persist --watch 600 --pid <PID của job>` chạy song song với job, `rsync` mỗi 10 phút: metrics, kết quả, và chỉ những `ckpt_<step>` đã lưu xong (bước không vượt `checkpoint_step` trong `result.json`, vì launcher chỉ ghi file đó sau khi `save_checkpoint` trả về). Checkpoint đang ghi dở không bao giờ lên Drive, nên lần chạy lại không gặp một "checkpoint mới nhất" hỏng.
- Trên VM mới: `setup`, gắn Drive, `restore` (kéo thư mục job về), rồi chạy lại job như cũ; `Psi0Trainer` tự tìm checkpoint cuối và tăng `attempt`.
- Dung lượng: mỗi checkpoint 9,5 GB; recipe stage 3 lưu mỗi 10000 bước nên một lần 40000 bước để lại 4 checkpoint, khoảng 38 GB trên Drive. 215 GB đủ khoảng 5 lần chạy; lưới của DA-26 cần dọn checkpoint không dùng (Drive không tự xóa, `persist` không dùng `--delete`).

**Còn mở:**
- Probe P3, P4 trên checkpoint trung gian (AC 5) chưa làm.
- `colab exec` qua kernel hay treo sau khi khởi động lại kernel; điều khiển VM qua `colab ssh --proxy-mode` ổn định hơn.

## Bảng sinh từ code

<!-- BEGIN read_psi0_logging.py -->

_Sinh bởi `scripts/g0/read_psi0_logging.py` từ commit `cda3fdfafe47cb6fa75400d013de1bd36e3cea05`. Không sửa tay; chạy lại script khi đổi commit ghim._

### Lời gọi log, đánh giá, checkpoint

| File | Dòng | Trong | Lời gọi |
|---|---|---|---|
| `scripts/train.py` | 138 | `_initialize_accelerator` | `accelerator.init_trackers` |
| `scripts/train.py` | 301 | `train` | `trainer.log` |
| `scripts/train.py` | 310 | `train` | `trainer.save_checkpoint` |
| `scripts/train.py` | 327 | `train` | `trainer.evaluate` |
| `scripts/train.py` | 329 | `train` | `trainer.log` |
| `src/psi/trainers/trainer.py` | 176 | `Trainer.log` | `self.accelerator.log` |
| `src/psi/trainers/trainer.py` | 433 | `Trainer.save_checkpoint` | `self.accelerator.save_state` |
| `src/psi/trainers/trainer.py` | 506 | `Trainer.resume_from_checkpoint` | `self.accelerator.load_state` |
| `src/psi/trainers/pretrain.py` | 311 | `PretrainTrainer.training_step` | `wandb.log` |
| `src/psi/trainers/pretrain.py` | 439 | `PretrainTrainer.log` | `self.accelerator.log` |
| `src/psi/trainers/pretrain.py` | 447 | `PretrainTrainer.save_checkpoint` | `super().save_checkpoint` |
| `src/psi/trainers/posttrain.py` | 751 | `PosttrainTrainer.training_step` | `wandb.log` |
| `src/psi/trainers/posttrain.py` | 814 | `PosttrainTrainer.save_checkpoint` | `super().save_checkpoint` |
| `src/psi/trainers/finetune.py` | 837 | `FinetuneTrainer.training_step` | `wandb.log` |
| `src/psi/trainers/finetune.py` | 904 | `FinetuneTrainer.save_checkpoint` | `super().save_checkpoint` |

### Tên metric theo stage

`scripts/train.py` ghi `flatten({**losses, "epoch": epoch}, parent_key="train")` sau mỗi bước và `flatten(eval_losses, parent_key="eval")` sau `evaluate()`, nên khóa dưới đây có tiền tố `train/` hoặc `eval/` trong W&B. `{…}` là phần tên sinh lúc chạy.

| Stage | Tiền tố | Khóa |
|---|---|---|
| 1 (pretrain) | `train/` | `loss`, `action_accuracy`, `action_l1_loss`, `lr`, `epoch`, `grad_norm_vlm` |
| 1 (pretrain) | `eval/` | `action_l1_loss`, `horizon_abs_error`, `n_items`, `decoding_error_count` |
| 2 (posttrain) | `train/` | `lr_act`, `grad_norm_act`, `grad_norm_vlm`, `loss`, `vlm_feat_norm`, `epoch` |
| 2 (posttrain) | `eval/` | `loss`, `**modality_metrics` |
| 3 (finetune) | `train/` | `lr_act`, `grad_norm_act`, `grad_norm_vlm`, `loss`, `vlm_feat_norm`, `state_drop_frac`, `epoch` |
| 3 (finetune) | `eval/` | `loss`, `**modality_metrics` |

### Trường `TrainingMetric` so với stage 3

Cột "Ψ₀ tự log" chỉ nói code tác giả có sẵn số đó hay không. Mọi trường đều có trong `metrics.jsonl`: phần Ψ₀ không có do lớp bọc `flywheel_psi0.trainer` bù, trên các dòng ghi ở cột "Dòng".

| Trường | Ψ₀ tự log | Nguồn trong Ψ₀ | Dòng | Cách lớp bọc lấy |
|---|---|---|---|---|
| `run_plan_id` | không | — | train, val | Nhận từ RunPlan |
| `job_id` | không | — | train, val | Nhận từ RunPlan |
| `checkpoint_id` | không | — | train, val | Id của checkpoint job sẽ ra, như nhau trên mọi dòng |
| `release_id` | không | — | train, val | Nhận từ RunPlan |
| `attempt` | không | — | train, val | Đếm số lần chạy lại từ checkpoint |
| `step` | có | `step=` | train, val | `accelerator.log(..., step=self.global_step)` |
| `epoch` | có | `train/epoch` | train, val | Từ `train/epoch`; dòng val lấy epoch gần nhất |
| `split` | có | `train/loss` | train, val | Tiền tố `train/` thành `train`, `eval/` thành `val` |
| `loss` | có | `train/loss` | train, val | `train/loss` và `eval/loss`; không hữu hạn ghi `"NaN"` |
| `lr` | có | `train/lr_act` | train, val | LR nhóm action header; dòng val lấy LR gần nhất |
| `vlm_frozen` | không | — | train, val | `model.tune_vlm` trong `run_config.json` (`--model.no-tune-vlm`) |
| `loss_by_group` | một phần | `eval/**modality_metrics` | train, val | Train, mọi bước: tách chính loss flow matching (vận tốc) theo nhóm ActionLayout. Val: MSE action trên batch val. Ψ₀ chỉ có L1 khử chuẩn hóa `eval/<dataset>/err_l1_<nhóm>`, không dùng |
| `loss_by_chunk_pos` | không | — | train, val | Như `loss_by_group`, theo vị trí trong chunk; dòng train bỏ `max-delay` (8) vị trí đầu bị mask RTC |
| `grad_norm_vlm` | có | `train/grad_norm_vlm` | train | Ψ₀ chỉ log khi một nhóm VLM được train; stage 3 đóng băng VLM nên launcher (nhiệm vụ con 2) tự đo trong `clip_grad_norms()`, trước `zero_grad()`, để T8a kiểm được |
| `grad_norm_action` | có | `train/grad_norm_act` | train | Grad norm của action header |
| `pred_var_by_dim` | không | — | train, val | Phương sai action lấy mẫu theo chiều (val: batch val; train: batch train ở bước validation) |
| `pred_std` | không | — | train, val | Độ lệch chuẩn action lấy mẫu theo chiều (val: batch val; train: batch train ở bước validation) |
| `target_std` | không | — | train, val | Độ lệch chuẩn action đích theo chiều (val: batch val; train: batch train ở bước validation) |
| `hand_open_hist` | không | — | train, val | Độ mở mỗi tay (0 nắm hết cỡ, 1 mở) từ 14 chiều bàn tay (0–13), histogram 10 ngăn (DA-07); train: batch train ở bước validation |
| `vram_gb` | không | — | train, val | `torch.cuda.max_memory_allocated()` |
| `throughput` | không | — | train | Batch toàn cục chia thời gian một bước; trống ngay sau eval |
| `wall_time_s` | không | — | train, val | Số giây từ lúc lớp bọc khởi động |

### Script train trong `scripts/train/psi0/`

`finetune-simple-psi0.sh` không có ở commit này. Các script có: `finetune-real-amo-psi0.sh`, `finetune-real-sonic-psi0-2.8B-sonic1.0-robust.sh`, `finetune-real-sonic-psi0-2.8B-sonic1.1-robust.sh`, `finetune-sonic-psi-dream-baseline.sh`, `finetune-sonic-psix-baseline.sh`, `finetune-sonic-simple-psi0.sh`, `posttrain-he-psi0.sh`, `posttrain-mix-psi0.sh`, `posttrain-psix-sonic-v1.sh`, `posttrain-psix-unifolm-g1-novlm.sh`, `posttrain-psix-unifolm-g1-sonic1.0.sh`, `posttrain-psix-unifolm-g1-sonic1.1.sh`, `pretrain-egodex-psi0-fast.sh`, `pretrain-egoverse-psi0-fast.sh`, `pretrain-he-psi0-fast.sh`, `pretrain-mix-psi0-fast.sh`, `slurm-pretrain-egodex-psi0-fast.sh`.

<!-- END read_psi0_logging.py -->

## Chạy lại khi đổi commit ghim

```bash
python3 scripts/g0/read_psi0_logging.py --repo fwdata/psi0/Psi0 --commit <commit mới> --write docs/g0/psi0-logging.md
```

`--check docs/g0/psi0-logging.md` trả mã 1 nếu bảng không còn khớp code. Script chỉ dùng thư viện chuẩn và đọc file qua `git show`, nên clone không cần checkout ở commit ghim. Khi một trường đổi từ "có" sang "thiếu", sửa lớp bọc trước khi chạy job.
