# S1-03 · Tái tạo đánh giá Ψ₀, checkpoint gốc (Q0), độ không tất định

_Kết quả của story [S1-03](../product/stories/S1-03-tai-tao-danh-gia-psi0.md). Quy ước file ở [docs/g0/README.md](README.md). Người làm: Hiếu. Bắt đầu 24/10/2026._

| Mục | Trạng thái |
|---|---|
| 1.1 Liệt kê checkpoint trong `psi0/` | Xong 24/10/2026 |
| 1.2 Chọn checkpoint gốc và task tái tạo | Chưa |
| 1.3 Câu hỏi provenance cho PSI Lab | Chưa |
| 2.1–2.2 Môi trường và script serve | Xong 3/11/2026 trên máy 3060: serve checkpoint task hai bàn, smoke 30 lần `/act` đạt (mục 2.6) |
| 2.3–5 Đo VRAM, độ trễ, đánh giá, độ không tất định | Chưa; cần máy 5090 |
| 6 Task hai bàn ở `mujoco_isaac` (AC 9) | Chưa: server chuyển lên Colab (Hiếu chốt 3/11/2026, không thuê GPU; mục 3.4.1); lượt Isaac Level 0 cũ dừng sau 2/10 (đều hỏng, file task lỗi spawn); chưa chạy lại với file đã sửa |
| 7 Task hai bàn ở `mujoco` (AC 10) | 0/90 cũ (file task `6d10628`, lỗi spawn) bị thay; chạy lại với file `b75c678`: Level 0 0/10 (3/11/2026, mục 3.2). Kết luận Q-27C tạm (mục 3.5) |
| 8 Checkpoint ablation của HE (AC 11) | Liệt kê xong 3/11/2026 (mục 4); câu hỏi Q-27E chờ Hiếu gửi PSI Lab |

> **Cập nhật (3/11/2026, 23:20).** Các lượt `mujoco` 0/90 và hai episode Isaac đầu tiên chạy với file task hai bàn của SIMPLE `6d10628` (image ghim `38a6…`). Bản này spawn robot với cánh tay giơ; ngón chạm bàn 1 lúc WBC ổn định nên robot bị đẩy lùi 0,1–0,28 m. Tác giả sửa ở `b75c678` (PR #29, `77872fe`, 29/10/2026), và Hiếu chuyển pin SIMPLE sang đó (PR #68). Từ nay `eval_psi0.sh run` mount file `b75c678` vào image (mục 3). Kết quả cũ giữ nguyên trong bảng, đánh dấu "bị thay". Chạy lại `mujoco` Level 0 với file đã sửa: **0/10**. Lỗi spawn vì vậy không giải thích được việc `mujoco` hỏng.

## 1. Q0 · Checkpoint trong `psi0/`

### 1.1 Revision ghim

| Trường | Giá trị |
|---|---|
| Repo | `USC-PSI-Lab/psi-model` (Hugging Face, công khai, không gated) |
| Revision ghim | `cb1480f50d9764ab2f6261bc2e651a67ad54da17` |
| Commit cuối của repo | 28/09/2026 |
| Ngày kiểm | 24/10/2026 |
| Model card | Không có `README.md` ở revision này (tải về trả 404) |

Toàn repo có 2 317 file; `psi0/` chiếm 225 file. Các thư mục khác (`act`, `dp`, `gr00t`, `gr00t-n1.6`, `egovla`, `h_rdt`, `intervla-m1`, `openpi`, `openpi-05`) là baseline, không dùng cho Q0.

### 1.2 Danh sách

Ngày trong tên lấy từ dấu thời gian `YYMMDDHHMM` trong tên thư mục, là ngày tác giả chạy. Ngày tải lên là ngày commit cuối của các file trên Hugging Face. Kích thước tính bằng GB thập phân.

| Thư mục | Ngày trong tên | Ngày tải lên | GB | Số file | Nội dung |
|---|---|---|---|---|---|
| `pre.fast.egodex.2512241941.ckpt200k` | 2025-12-24 | 2026-03-12 | 4.28 | 12 | VLM |
| `pre.abl.only.he.2512311516.48k` | 2025-12-31 | 2026-03-12 | 4.28 | 12 | VLM |
| `pre.fast.1by1.2601091803.ckpt.ego200k.he30k` | 2026-01-09 | 2026-03-12 | 4.28 | 12 | VLM |
| `pre.abl.ego.10per.2602021632.46k` | 2026-02-02 | 2026-03-12 | 4.28 | 12 | VLM |
| `pre.fast.2605160748.ckpt.ego390k` | 2026-05-16 | 2026-07-17 | 4.28 | 12 | VLM |
| `postpre.1by1.pad36.2601131206.ckpt.he30k` | 2026-01-13 | 2026-03-12 | 1.99 | 1 | action header |
| `postpre.abl.ego.10per.2602050006` | 2026-02-05 | 2026-03-12 | 1.99 | 1 | action header |
| `postpre.abl.only.he.2602050012` | 2026-02-05 | 2026-03-12 | 1.99 | 1 | action header |
| `postpre.sonic1.0.unifolm.2609092156.40k` | 2026-09-09 | 2026-09-14 | 11.24 | 13 | VLM + action header |
| `postpre.sonic1.1.unifolm.2609181726.40k` | 2026-09-18 | 2026-09-28 | 11.24 | 13 | VLM + action header |
| `simple-checkpoints/` | — | 2026-05-06 → 2026-08-30 | 137.58 | 89 | 22 run fine-tune trên task SIMPLE |
| `sonic-checkpoints/` | — | 2026-09-14 | 11.22 | 6 | 1 run fine-tune đa task trên dữ liệu sonic |
| `real-checkpoints/` | — | 2026-03-23 → 2026-05-15 | 52.62 | 41 | 8 run fine-tune robot thật (`task1`–`task8`) |

Cách đọc tên. `pre.*` có VLM (`model.safetensors` khoảng 4,3 GB, kèm tokenizer và processor) nhưng không có action header. Ba thư mục `postpre.*` đầu chỉ có `action_header.safetensors`, nên phải ghép với một `pre.*`. Hai thư mục `postpre.sonic*` có đủ cả hai phần.

### 1.3 Run fine-tune trên SIMPLE

Mỗi run có `argv.txt`, `run_config.json`, `envs.txt` và một checkpoint `ckpt_40000` (6,25 GB). Tên run có dạng `<task>.simple.flow1000.cosine.lr1.0e-04.b<batch>.gpus<n>.<thời gian>`.

| Task trong tên run | Batch × GPU | Ngày trong tên |
|---|---|---|
| `g1wholebodybendhandoverteleop-v0-lv0` | b128 × 8 | 2026-05-22 |
| `g1wholebodybendhandoverteleop-v0` | b128 × 8 | 2026-05-19 |
| `g1wholebodybendpick-v0` | b256 × 8 | 2026-03-15 |
| `g1wholebodybendpickmixed-v0` | b128 × 8 | 2026-05-23 |
| `g1wholebodybendpicksimtorealteleop-v0` | b128 × 8 | 2026-05-20 |
| `g1wholebodybendpickteleop-v0` | b128 × 8 | 2026-05-23 |
| `g1wholebodyclosedoorteleop-v0` | b128 × 8 | 2026-05-07 |
| `g1wholebodyhandover-v0` | b64 × 4 | 2026-04-07 |
| `g1wholebodylocomotionpickbetweentablesmixed-v0` | b128 × 8 | 2026-05-22 |
| `g1wholebodylocomotionpickbetweentablesteleop-v0` | b64 × 4 | 2026-04-08 |
| `g1wholebodylocomotionpickbetweentablesvariant5-v0-processed` | b128 × 8 | 2026-05-20 |
| `g1wholebodyopenfaucetteleop-v0` | b128 × 8 | 2026-05-08 |
| `g1wholebodyopenoventeleop-v0` | b128 × 8 | 2026-05-12 |
| `g1wholebodyopentrashcanteleop-v0` | b128 × 8 | 2026-05-29 |
| `g1wholebodypickandplaceandhugcontainerteleop-v0` | b128 × 8 | 2026-04-28 |
| `g1wholebodypushofficechairteleop-v0` | b128 × 8 | 2026-05-29 |
| `g1wholebodytabletopgrasp-v0` | b128 × 8 | 2026-03-18 |
| `g1wholebodyxmovebendpickmp-v0` | b128 × 8 | 2026-05-18 |
| `g1wholebodyxmovebendpickteleop-v0-by-10-teleop-trajs` | b128 × 8 | 2026-05-23 |
| `g1wholebodyxmovebendpickteleop-v0` | b112 × 7 | 2026-04-10 |
| `g1wholebodyxmovepick-v0` | b128 × 8 | 2026-03-18 |
| `sonic-wbcbox.neckle` | b256 × 8 | 2026-08-26 |

Không có run nào cho task chính `G1WholebodyBendPickAndPlaceTeleop-v0`. Có run cho task tái tạo ưu tiên (`g1wholebodyxmovebendpickteleop-v0`) và cho task F1 (`g1wholebodybendpickteleop-v0`).

### 1.4 Dữ liệu đầu vào ghi trong cấu hình run

Đây là dữ kiện đọc từ `argv.txt` và `run_config.json` ở revision ghim. Việc chọn checkpoint làm ở nhiệm vụ con 1.2.

| Run | VLM khởi tạo (`model_name_or_path`) | Action header khởi tạo | Dữ liệu train | Ghi chú |
|---|---|---|---|---|
| `simple-checkpoints/g1wholebodyxmovebendpickteleop-v0…2604100422` | `psi0/pre.fast.1by1.2601091803.ckpt.ego200k.he30k` | `psi0/postpre.1by1.pad36.2601131206.ckpt.he30k` | `G1WholebodyXMoveBendPickTeleop-v0` | VLM đóng băng (`no-tune-vlm`); `action-chunk-size` 30, `action-dim` 36, `action-exec-horizon` 30, có `rtc`, `max-delay` 8; ảnh 180 × 320; 40 000 bước, lr 1e-4 |
| `sonic-checkpoints/multi-task.psi-dream.2609092156` | Checkpoint nội bộ `.runs/posttrain/dropout.us…2609012205` | Như cột trước | `g1_sonic_lerobot_0810_merged_train` | Train cả VLM (`tune-vlm`); `action-dim` 80, `odim` 45; ảnh 270 × 480; không `rtc` |

Tên env đúng của task tái tạo trong dữ liệu là `G1WholebodyXMoveBendPickTeleop-v0` (trường `data.train_repo_ids`).

Lặp lại được: liệt kê bằng API cây thư mục của Hugging Face `https://huggingface.co/api/models/USC-PSI-Lab/psi-model/tree/<revision>/psi0?recursive=true&expand=true`, đi hết các trang theo header `Link`. File cấu hình tải ở `https://huggingface.co/USC-PSI-Lab/psi-model/resolve/<revision>/<đường dẫn>`. Không tải trọng số.

## 2. Serve Ψ₀ và smoke test

### 2.1 Script

| Lệnh | Việc |
|---|---|
| `bash scripts/g0/serve_psi0.sh setup [--flash-attn]` | Clone Ψ₀ ở commit ghim `cda3fdfafe47cb6fa75400d013de1bd36e3cea05`, dựng môi trường |
| `bash scripts/g0/serve_psi0.sh fetch [--weights]` | Tải run dir ở revision `cb1480f…` của `psi-model`; không có `--weights` thì chỉ tải `argv.txt`, `run_config.json`, `envs.txt` |
| `bash scripts/g0/serve_psi0.sh check` | Smoke không model: làm mọi bước của `Server.__init__` trong `serve_psi0_simple` trừ nạp trọng số, kiểm `--help` của server, ghi giao thức và phần cứng |
| `bash scripts/g0/serve_psi0.sh serve` | Chạy `serve_psi0_simple --policy psi0 --port 22085 --action-exec-horizon 24 --rtc` |
| `bash scripts/g0/eval_psi0.sh smoke [--calls N]` | Gọi `/health`, `/info` và N lần `/act` với ảnh, state bằng 0; kiểm action có kích thước (24, 36) và hữu hạn |

`PSI0_RUNTIME=venv` (mặc định) dùng env uv trong bản clone; `PSI0_RUNTIME=docker` dùng image của tác giả ghim theo digest qua `docker/psi0/compose.yaml`. Dữ liệu nằm ở `fwdata/psi0/` của checkout chính, ngoài git. Mọi giá trị ghim đổi được bằng biến môi trường cùng tên trong script.

`--action-exec-horizon 24` theo README Ψ₀. Run được train với `action-exec-horizon` 30 bằng `action-chunk-size`, mà server từ chối RTC khi hai số bằng nhau.

### 2.2 Smoke trên máy dev, 24/10/2026

Máy: RTX 3050 Laptop 4 GB, driver 595.99.02, RAM 14 GB, Ubuntu 26.04, Docker chưa có runtime NVIDIA. Không nạp được model ở đây: trọng số `ckpt_40000` 6,25 GB ở bf16, lớn hơn VRAM.

| Kiểm | Kết quả |
|---|---|
| `setup` (venv) | Đạt: `psi 0.0.0`, `torch 2.7.0+cu126`, Python 3.11.17, env 6,8 GB |
| `fetch` không trọng số | Đạt: 3 file cấu hình |
| `check` | Đạt, `problems` rỗng (báo cáo `fwdata/psi0/smoke/check-20261024T194806.json`) |
| `eval_psi0.sh smoke` với server giả cùng route và lớp message của Ψ₀ | Đạt: 2 lần `/act` trả (24, 36) |
| Như trên, server giả trả `{"status": "CUDA out of memory"}` với HTTP 200 | Smoke báo hỏng, mã thoát 1, đúng như cần |

Giao thức `act()` đọc từ cấu hình run, chưa đo trên server thật (nền cho V2):

| Trường | Giá trị |
|---|---|
| Giao thức | HTTP JSON (FastAPI, uvicorn): `GET /health`, `GET /info`, `POST /act` |
| Cổng | 22085 (đặt trong script; client SIMPLE ở README dùng `--port 9000`, cần khớp khi chạy nhiệm vụ con 3) |
| Chiều action, chunk, phần trả về | 36, 30, 24 dòng mỗi lần `/act` |
| State | pad tới 36, dùng 1 khung cuối |
| Ảnh | 180 × 320; run không ghi `image_keys`, server lấy ảnh theo thứ tự trong payload |
| RTC | Có trong lúc train (`rtc`, `max_delay` 8), bật khi serve |
| Lỗi | Server trả HTTP 200 kèm `{"status": "<lỗi>"}` thay cho action; client phải kiểm khóa `action` |

### 2.3 Vấn đề gặp khi dựng môi trường

1. **`uv.lock` của Ψ₀ ở `cda3fdf` hỏng.** File là bản gộp lỗi của hai lock, một trỏ tới `pypi.org`, một trỏ tới mirror `pypi.tuna.tsinghua.edu.cn`: bảng `[package.optional-dependencies]` của `jsonschema` lặp, nhiều gói ghi hai lần. uv báo lỗi parse. Lỗi xuất hiện từ commit `6b4a5cc`; lock ở `47993ee` còn hợp lệ nhưng đi với `pyproject.toml` cũ. `setup` giữ bản gốc là `uv.lock.upstream` (sha256 `c61233d62a0be479…`) và giải lại từ `pyproject.toml` (`fwdata/psi0/uv.lock.relocked`, sha256 `fe5ba26e111fe8ad…`).
2. **Lock giải lại lệch 160 trên 350 gói chung** so với lock của tác giả. Gói được ghim trong `pyproject.toml` vẫn trùng (torch 2.7.0, torchvision 0.22.0, transformers 4.57.1, tyro 0.9.32, pydantic 2.10.6, accelerate 1.7.0). Lệch đáng chú ý: diffusers 0.37.0 → 0.39.0, safetensors 0.6.2 → 0.8.0, huggingface-hub 0.35.3 → 0.36.2, fastapi 0.119.1 → 0.162.0. Vì diffusers nằm trong đường lấy mẫu action, **phép tái tạo trên máy 5090 nên chạy bằng image của tác giả** (`PSI0_RUNTIME=docker`); env venv chỉ dùng cho smoke.
3. **`evdev<1.7` cần trình biên dịch C**, máy dev không có. Gói này chỉ phục vụ thiết bị teleop, không được import ở đâu trong `src/`; `setup` bỏ qua nó.
4. **`hf download` lặp `--include` chỉ giữ lần cuối**; script truyền các mẫu trong một `--include`.
5. `envs.txt` của run có token đã che một phần của tác giả. Không chép file này vào tài liệu hay log.
6. flash-attn chưa cài trên máy dev; Ψ₀ tự dùng SDPA. Trên 5090 image đã có flash-attn; nếu không chạy thì ghi lại (nhiệm vụ con 2.1).

### 2.4 Chạy trên máy 3060, 25/10/2026

Máy: RTX 3060 12 GB, driver 550.163.01 (CUDA 12.4), RAM 94 GB, Ubuntu 22.04, Docker có runtime `nvidia` (NVIDIA Container Toolkit 1.20.1), Docker Compose v5.6.1. Chạy bằng `PSI0_RUNTIME=docker`, `FW_UID`, `FW_GID` = 1000.

| Kiểm | Kết quả |
|---|---|
| `setup` | Đạt: clone Ψ₀ ở `cda3fdf`, image ghim đã có (32,4 GB khi giải nén) |
| `fetch --weights` | Đạt: `ckpt_40000/model.safetensors` 6,25 GB, khoảng 1 phút |
| `check` | Đạt sau ba bản sửa dưới đây: CUDA có, RTX 3060 12,4 GB, flash-attn có, `fits_gpu_bf16: true` (báo cáo `fwdata/psi0/smoke/check-20261025T134246.json` trên máy 3060) |
| `serve` | Chưa: hết VRAM khi đưa model lên GPU vì một container Isaac Sim khác (`phyrc-2027:isaac-6.0.1`) đang giữ 7,6 GB. Lúc lỗi PyTorch mới cấp 2,61 GiB, GPU còn 422 MiB trống. Chạy lại khi GPU trống |

Ba lỗi đã sửa:

1. **Thư mục `fwdata/` thuộc root.** Container chạy trước khi có bản clone Ψ₀, Docker tự tạo nguồn bind mount bằng root, rồi `git clone` không ghi được. Script nay dừng ở chế độ Docker nếu chưa có bản clone.
2. **`assert load_dotenv()` thất bại trong container.** `load_dotenv` tìm `.env` từ `/workspace/src` đi lên; compose nay mount `.env` của bản clone vào `/workspace/.env`, chỉ đọc.
3. **CUDA error 804 ("forward compatibility was attempted on non supported HW").** Image dựng trên CUDA 12.9 (`NVIDIA_REQUIRE_CUDA=cuda>=12.9`), driver máy là 550, nên toolkit đặt `libcuda` forward-compat của image (575.57.08) lên trước; card GeForce không dùng được thư viện này. `nvidia-smi` trong container vẫn chạy, chỉ torch lỗi. Compose nay đặt `LD_LIBRARY_PATH=/usr/lib/x86_64-linux-gnu:/usr/local/cuda/lib64` để nạp `libcuda` của driver máy trước. torch 2.7.0+cu126 chạy được trên driver 550 nhờ tương thích trong dòng CUDA 12; đã thử nhân ma trận bf16 trên GPU. `check` nay báo lỗi khi `DEVICE` là `cuda` mà torch không thấy GPU.

Giới hạn: số đo trên 3060 chỉ để tham khảo cho AC 4. p99 độ trễ làm nền cho τ_lat phải đo trên máy chạy thí nghiệm. SIMPLE và Ψ₀ cùng chạy trên một card 12 GB sẽ thiếu VRAM.

### 2.5 Việc còn lại trên máy 5090

```bash
export FW_UID=$(id -u) FW_GID=$(id -g) PSI0_RUNTIME=docker
bash scripts/g0/serve_psi0.sh setup
bash scripts/g0/serve_psi0.sh fetch --weights
bash scripts/g0/serve_psi0.sh check
bash scripts/g0/serve_psi0.sh serve
bash scripts/g0/eval_psi0.sh smoke --calls 5
```

Lệnh cuối chạy ở terminal khác, sau khi server in `Server listens on 0.0.0.0:22085`. Cần NVIDIA container toolkit trên máy 5090; nếu chưa có thì bỏ `PSI0_RUNTIME=docker` (venv) và ghi lại giới hạn ở mục 2.3 ý 2. Trước khi chạy, kiểm GPU không bị tiến trình khác chiếm (`nvidia-smi`). `check` trên 5090 phải báo `fits_gpu_bf16: true`. Smoke đạt thì mới chạy nhiệm vụ con 2.3 (VRAM, p99 độ trễ) và 3.

### 2.6 Serve checkpoint task hai bàn trên máy 3060, 3/11/2026

Từ 3/11/2026 mọi việc chạy nặng làm trên máy 3060 (quy tắc của Hiếu); mục 2.5 giữ cho trường hợp có máy lớn hơn. Thư mục làm việc riêng `~/denso-s103`, chạy bằng `PSI0_RUNTIME=docker`, image Ψ₀ ghim theo digest như mục 2.1.

```bash
export FW_UID=$(id -u) FW_GID=$(id -g) PSI0_RUNTIME=docker
export RUN=g1wholebodylocomotionpickbetweentablesteleop-v0.simple.flow1000.cosine.lr1.0e-04.b64.gpus4.2604081126
bash scripts/g0/serve_psi0.sh setup
bash scripts/g0/serve_psi0.sh fetch --weights
bash scripts/g0/serve_psi0.sh check
bash scripts/g0/serve_psi0.sh serve            # nền: nohup setsid ... < /dev/null &
bash scripts/g0/eval_psi0.sh smoke --calls 30
```

| Kiểm | Kết quả |
|---|---|
| Trọng số `ckpt_40000/model.safetensors` | 6 253 648 840 byte, sha256 `c69c2ae866cdff4c51aee3aa2948b6400e8f001e73d38cbff2b364e41b4cf07b`, khớp oid LFS ở revision `cb1480f…` |
| `check` | Đạt, `problems` rỗng: `train_repo_ids` = `G1WholebodyLocomotionPickBetweenTablesTeleop-v0`, action 36, chunk 30, phục vụ 24, `rtc` có, flash-attn có (báo cáo `fwdata/psi0/smoke/check-20261103T102841.json` trên máy 3060) |
| `serve` | Đạt: `Server listens on 0.0.0.0:22085` khoảng 1 phút sau khi chạy; server báo RTC `inference_delay` 6, `min_exec_horizon` 24 |
| `smoke --calls 30` | Đạt: 30 lần `/act` trả (24, 36), số hữu hạn (báo cáo `fwdata/psi0/smoke/smoke-20261103T103238.json`) |
| VRAM | 7,2 GB cho tiến trình server (`nvidia-smi`); đỉnh của cả card khi smoke 7,8 GB, gồm khoảng 0,8 GB của màn hình và tiến trình khác |
| RAM | RSS của server khoảng 6 GB; `docker stats` 10,4 GiB (gồm page cache) |
| Độ trễ `/act` (ảnh và state bằng 0, cùng máy) | Lần đầu 2,46 s (khởi động); 29 lần sau: trung vị 0,41 s, lớn nhất 0,52 s |

Độ trễ trên là của smoke, chưa phải chu kỳ thật trong SIMPLE; p99 cho τ_lat lấy từ lượt eval (nhiệm vụ con 2.3). Docker `mem_limit` của server đặt 16 GiB (`PSI0_MEM_LIMIT`): `systemd-run --scope` chỉ giới hạn tiến trình `docker` phía client, không giới hạn container chạy dưới `dockerd`.

## 3. Task hai bàn `G1WholebodyLocomotionPickBetweenTablesTeleop-v0` (AC 9, 10)

Chạy 3/11/2026 trên máy 3060. Server như mục 2.6. Client là `eval-decoupled-wbc` của SIMPLE, agent `psi0_decoupled_wbc`, chạy trong image công bố của SIMPLE ghim theo digest `ghcr.io/physical-superintelligence-lab/simple@sha256:38a674039f413ca171d5f8f841c2b9a9d67771fdaf7bcc73c4777fdfcb7a561f` (tag `latest` ngày 3/11/2026, dựng 30/08/2026). Image có Isaac Sim 4.5; `mujoco` và `mujoco_isaac` dùng cùng một bản SIMPLE. Đã so md5 năm file với SIMPLE (chưa so cả image): `eval_decoupled_wbc.py`, `psi0_decoupled_wbc.py`, `g1_sonic.py`, `sonic_decoupled_wbc_agent.py` giống `6d10628` và `b75c678`; file task hai bàn giống `6d10628` (md5 `e116f9f3…`), tức bản có lỗi spawn.

**File task đã sửa** (từ 3/11/2026, 23:00). `eval_psi0.sh run` mount `src/simple/tasks/g1_wholebody_locomotion_pick_between_tables_teleop.py` của SIMPLE `b75c6786f87b4a7f43b52b0ac5b83a1d9ea62e11` (sha256 `51bce5d6c0311219…`, kiểm trước khi mount) đè lên bản trong image, chỉ đọc. `SIMPLE_TASK_FIX=off` chạy lại đúng image cũ. Trong container đã kiểm: file nạp đúng đường dẫn đó, sha256 khớp. Ở lần gọi `/act` đầu tiên của một episode, state các khớp tay bằng 0 khi có bản sửa, lệch khoảng 0,015–0,018 khi không. Khớp cánh tay chỉ lệch dưới 0,008 rad, vì WBC đã đưa tay về tư thế mặc định trong lúc ổn định. Vị trí thân robot không có trong state, nên phép kiểm này không đo được độ lùi 0,1–0,28 m.

**Bộ eval** được cache theo revision (`evals/simple-eval-<7 ký tự đầu>/`), và zip được kiểm với `lfs.oid` của Hugging Face trước khi giải nén. Client đọc `/info` của server, dừng nếu server không serve đúng task, và ghi `/info` vào `server_info.json` cạnh `summary.json`.

```bash
export FW_UID=$(id -u) FW_GID=$(id -g) RUN=<run hai bàn như mục 2.6>
export SIMPLE_ASSETS=<thư mục data/ của SIMPLE có assets, robots, scenes>
bash scripts/g0/eval_psi0.sh run --level 0 --sim-mode mujoco --episodes 10 --pass 1
```

Mỗi lần chạy ghi `fwdata/simple/s103/runs/simple-<commit file task>/<mode>/level-<L>/pass-<K>/ep<S>-<E>/` (`simple-6d10628` cho các lượt cũ, `simple-b75c678` cho các lượt đã sửa) gồm `summary.json` (kết quả từng episode, revision checkpoint, commit Ψ₀, revision `psi-data`, digest image SIMPLE, exec horizon, RTC), `eval_stats.txt`, `client.log` và video camera đầu.

### 3.1 Điều kiện eval công bố chỉ có 10 mỗi mức

`psi-data` revision `de140d67ba77a541f2a58354f7edf4e2480b7c56`, file `simple-eval/G1WholebodyLocomotionPickBetweenTablesTeleop-v0.zip` (690 kB) có bốn thư mục LeRobot v2.1 `dr-level-0`, `dr-level-1`, `dr-level-2`, `dr-level-hard`, **mỗi thư mục 10 điều kiện**. Số công bố 7/5/6 là trên đúng 10 điều kiện này. **[Đã chốt]** (Hiếu, 3/11/2026): "30 lượt mỗi mức" của AC 9, 10 là **10 điều kiện × 3 lượt lặp** (`--pass 1..3`) trên đúng 10 điều kiện của bộ eval tác giả, không sinh điều kiện mới. Đây **không phải 30 điều kiện độc lập**: policy lấy mẫu flow nên mỗi lượt lặp có thể cho kết quả khác, nhưng ba lượt cùng một điều kiện tương quan với nhau, nên kiểm nhị thức trên n = 30 lạc quan về độ chắc. Ba lượt lặp dùng để báo độ không tất định: với mỗi điều kiện, ghi số lượt thành công trên 3 và tỉ lệ điều kiện mà ba lượt không cùng kết quả.

**Phiên bản bộ eval.** Mọi lượt chạy của S1-03 dùng revision `de140d6` (bản HF `main` lúc 3/11/2026, zip 689 559 byte, sha256 `7d215cf3e9202b39…`, bốn thư mục kể cả `dr-level-hard`, lấy từ đợt "eval-fixed" `38e43f2` ngày 02/11/2026). **[Đã chốt]** (Hiếu, 3/11/2026, PR #68): eval ghim `de140d67ba77a541f2a58354f7edf4e2480b7c56` bằng hash; train giữ `e78fb93` tới sau 13/11. So với train `e78fb93`, đo bằng `scripts/g0/inspect_psi_data.py seeds` của master. Lệnh này so vị trí ban đầu do SpatialDR rút (`dr_state_dict.spatial`) ở cùng chỉ số episode:

| Bộ eval | Mức | Vật và khay trùng train | Robot `g1_sonic` trùng train |
|---|---|---|---|
| `e78fb93` (zip 480 532 byte, sha256 `8a4b0ff7…`) | 0, 1 | 10/10 | 10/10 |
| `e78fb93` | 2 | 0/10 | 10/10 |
| `de140d6` | 0, 1 | 10/10 | **0/10** (theo S1-07: lùi 6,1 cm, lệch 2 mm, xoay 0,17°, như nhau ở mọi episode) |
| `de140d6` | 2, hard | 0/10 | 0/10 |

Ngoài tư thế, hai bản còn khác domain randomization hình ảnh: vật liệu sàn, bàn và vật; loại và vị trí vật gây nhiễu; vị trí đèn. Bản trước của mục này ghi mức 0, 1 "chỉ khác hình ảnh" và vật, khay "khác train ở cả 10 episode". Hai ý đó sai: phép so lúc đó dùng `layout.actors.*.pose`, không phải vị trí SpatialDR rút.

Số công bố 7/5/6 có trước cả hai lần tải bộ eval lên HF (checkpoint train tháng 4/2026), nên không biết tác giả đo trên bản nào. Câu hỏi này đã thêm vào Q-27E (mục 4). Ở Level 0 và 1, vật và khay của bộ eval `de140d6` nằm đúng vị trí của episode train cùng chỉ số; chỉ robot khởi đầu lùi 6,1 cm.

### 3.2 Kết quả `mujoco` (AC 10)

| File task | Mức | Thành công | Wilson 95% | Công bố (`mujoco_isaac`, 10 lượt) | p một phía, H0: p ≥ số công bố | Giờ máy | Trạng thái |
|---|---|---|---|---|---|---|---|
| `b75c678` (đã sửa) | Level 0 | 0/10 (10 điều kiện × 1 lượt) | [0%, 28%] | 7/10 | 6 × 10⁻⁶ | 10 phút | Hiện hành (3/11/2026, 23:18) |
| `6d10628` (lỗi spawn) | Level 0 | 0/30 | [0%, 11%] | 7/10 | 2 × 10⁻¹⁶ | 30 phút | Bị thay: lỗi spawn |
| `6d10628` (lỗi spawn) | Level 1 | 0/30 | [0%, 11%] | 5/10 | 9 × 10⁻¹⁰ | 30 phút | Bị thay: lỗi spawn |
| `6d10628` (lỗi spawn) | Level 2 | 0/30 | [0%, 11%] | 6/10 | 1 × 10⁻¹² | 29 phút | Bị thay: lỗi spawn |

Lượt đã sửa: `runs/simple-b75c678/mujoco/level-0/pass-1/ep0-9/`, client thoát 0, 628 s tường, server Docker cục bộ trên máy 3060 (bind 127.0.0.1). Hai episode kiểm thêm, có và không có bản sửa (mục 3, file task đã sửa), cũng hỏng. Level 1, 2 và lượt lặp 2, 3 chưa chạy lại với bản sửa.

Với các lượt cũ, mỗi mức là 10 điều kiện × 3 lượt lặp (mục 3.1). Wilson tính trên n = 30 nên hẹp hơn thực; tính theo 10 điều kiện (0/10) thì cận trên là 28%, vẫn dưới cả ba số công bố. Kiểm Fisher một phía cho Level 0, 0/30 ở `mujoco` so với 7/10 công bố: p = 6 × 10⁻⁶.

Độ không tất định qua 3 lượt lặp: cả 30 điều kiện (3 mức × 10) đều 0/3, không điều kiện nào đổi kết quả giữa các lượt (tỉ lệ đổi chiều 0%). Con số này không nói gì về độ không tất định ở `mujoco_isaac`, nơi tỉ lệ thành công nằm giữa 0 và 1.

Mỗi episode `mujoco` khoảng 60 s (1 200 bước, 50 lần `/act`); client dùng đỉnh 3,3 GiB RAM. Chạy server và client bên trong `systemd-run --user --scope -p MemoryMax=20G -p MemorySwapMax=0`, nhưng giới hạn RAM thật là giới hạn của Docker: server 16 GiB (`PSI0_MEM_LIMIT`), client `mujoco` 16 GiB (`SIMPLE_MEM_LIMIT=16g`; mặc định của script là 20g; lượt Isaac dùng 32g), vì scope chỉ bọc tiến trình `docker` phía client (mục 2.6).

Hình ảnh: ở `mujoco` cảnh là bàn xám, sàn ô bàn cờ, vật màu trắng không texture, khác xa ảnh Isaac của cảnh HSSD mà checkpoint được train. Trong video, robot vẫn đi giữa hai bàn và đưa tay về phía vật, nhưng không lần nào nắm được vật và mang sang bàn 2.

### 3.3 Kiểm open-loop: phù hợp với server và checkpoint đúng [Đề xuất]

Để tách "renderer khác" khỏi "pipeline hỏng", chạy `psi.deploy.mock_psi0_client_openloop` của Ψ₀ (cùng image, cùng server) trên ba episode train của `psi-data/simple/G1WholebodyLocomotionPickBetweenTablesTeleop-v0` (ảnh Isaac), mỗi 5 khung một lần, so chunk dự đoán với action ghi lại (L1 sau khi bỏ chuẩn hóa, bước đầu của chunk):

| Episode | Khung | Tay | Cánh tay | Thân rpy | vx | vy | vyaw | RTT ấm |
|---|---|---|---|---|---|---|---|---|
| 0 | 117 | 0,080 | 0,096 | 0,042 | 0,070 | 0,036 | 0,274 | 358 ms |
| 1 | 133 | 0,103 | 0,091 | 0,052 | 0,061 | 0,026 | 0,225 | 345 ms |
| 2 | 140 | 0,063 | 0,065 | 0,042 | 0,058 | 0,025 | 0,213 | 345 ms |

Theo thời gian, sai số gần 0 ở phần lớn episode và chỉ vọt lên ở các lúc chuyển pha (bắt đầu nắm, thả, bắt đầu và dừng đi); sai số tay bằng 0 suốt lúc giữ vật. Kết quả này phù hợp với việc server, trọng số, chuẩn hóa và giao thức tái tạo đúng action của dữ liệu train khi ảnh là ảnh Isaac [Đề xuất]; mới 3 episode, chưa có ngưỡng hay mốc so sánh, và L1 của vyaw là 0,21–0,27. Open-loop không kiểm phía client SIMPLE (ghép state, ánh xạ action, WBC); phần đó chỉ được kiểm khi có lượt `mujoco_isaac` đạt gần số công bố. Báo cáo: `fwdata/psi0/openloop/openloop_eps{0,1,2}_train.{json,png}` trên máy 3060.

### 3.4 `mujoco_isaac` (AC 9): chưa chạy được trên card 12 GB

| Thử | Kết quả |
|---|---|
| Client Isaac, container không root, không có thư mục cache của Kit | Treo sau `app ready`: Kit không tạo được cache shader trong venv của image. Sửa: `eval_psi0.sh` mount thư mục cache, data, log của Kit và `HOME` ra máy chủ |
| Client Isaac, giới hạn RAM 20 GiB | Bị kill (mã 137) lúc nạp cảnh, RAM chạm 20 GiB |
| Client Isaac, giới hạn RAM 32 GiB, cùng card với server Ψ₀ | Isaac báo `ERROR_OUT_OF_DEVICE_MEMORY` (Vulkan) khi card đã dùng 11,8 GB: server 7,2 GB, Isaac hơn 4,6 GB. RAM client 21,6 GiB. Không có lần `/act` nào |
| Server Ψ₀ trên CPU để nhường GPU cho Isaac | Không được: `serve_psi0_simple` đòi CUDA, và VLM gọi thẳng `flash_attn` (không có kernel CPU). CPU Xeon E5-2697A v4 cũng không có bf16 |

Kết luận: trên máy 3060, server Ψ₀ và client Isaac không cùng chạy được. Cần một GPU có RT core và ≥ 16 GB (ví dụ 24 GB), hoặc tách server sang máy khác. Hiếu chọn [Đề xuất, theo thứ tự]: (a) máy 5090 của đội nếu còn; (b) thuê một GPU 24 GB có RT core (RTX 4090, L40S; A100 không có RT core nên Isaac không render được) chạy cả hai image; (c) server Ψ₀ trên Colab L4 hoặc A100 qua tunnel, client Isaac trên 3060 (dữ liệu demo là `public`, design mục 8.4). Ước lượng 90 episode × 6–10 phút (README Ψ₀) = 9–15 giờ máy, chưa đo.

### 3.4.1 Server Ψ₀ trên Colab, Isaac trên máy 3060 (3/11/2026)

**[Đã chốt]** (Hiếu, 3/11/2026): không thuê GPU; dùng Colab Pro cho server (dữ liệu demo là `public`), chạy qua Colab CLI trên laptop; sau này đội có thể chuyển sang máy chủ khác. Tunnel công khai (cloudflared) bị kiểm quyền của phiên Claude chặn, nên không dùng: server chỉ nghe trên VM Colab, đi tới máy 3060 bằng hai cổng chuyển tiếp SSH riêng: `colab ssh --proxy-mode` (laptop → Colab) và `ssh -R` (máy 3060 → laptop). Client SIMPLE vẫn gọi `http://127.0.0.1:22085`. Laptop phải bật suốt lúc eval; runtime Colab chỉ nhận một kết nối SSH, nên đọc log server bằng `colab exec`.

```bash
colab new -s s103psi0 --gpu L4                      # 1,94 CU/giờ
# trên VM: PSI0_ROOT=/content/psi0 PSI0_RUNTIME=venv PSI0_ENV=image RUN=<run hai bàn>
#          bash scripts/g0/serve_psi0.sh setup && ... fetch --weights && ... check && ... serve
ssh -N -o ProxyCommand="colab ssh --proxy-mode -s s103psi0" -L 127.0.0.1:22185:127.0.0.1:22085 root@colab
ssh -N -R 127.0.0.1:22085:127.0.0.1:22185 rtx3060
```

Colab không chạy được Docker. `PSI0_ENV=image` cài đúng danh sách gói đọc từ image ghim (`docker/psi0/requirements-image.txt`: torch 2.7.0+cu126, flash-attn 2.7.4.post1 từ wheel chính thức, diffusers 0.37.0, transformers 4.57.0, lerobot ở commit `09929d8`), không giải lại lock hỏng của tác giả (mục 2.3).

| Kiểm | Kết quả |
|---|---|
| `check` trên L4 | Đạt: L4 23 GB, flash-attn có, `problems` rỗng |
| Trọng số | sha256 `c69c2ae8…` như mục 2.6 |
| VRAM server | 6,2 GB |
| Open-loop trên 3 episode train, so với server Docker trên 3060 | L1 overall 0,088 / 0,111 / 0,070 so với 0,105 / 0,123 / 0,072; từng nhóm lệch 0,002–0,017; chưa ước lượng nhiễu lấy mẫu để so. RTT ấm 460 ms qua hai cổng chuyển tiếp (Docker cùng máy: 350 ms) |
| Thử `mujoco_isaac` 1 episode (Level 0, episode 0) | Chạy hết, client thoát 0; 1 715 s tường, gồm khoảng 4 phút khởi động Isaac; RAM client đỉnh 11,5 GiB, VRAM 5,7 GB; 50 lần `/act`. Kết quả: hỏng, robot làm rơi hộp ở bàn 1 rồi đi sang bàn 2 tay không |

**Độ trễ qua đường chuyển tiếp và ảnh hưởng tới kết quả.** RTT ấm mỗi lần `/act`: 460 ± 19 ms (open-loop, 3 × ~130 lần gọi), so với 350 ± 10 ms khi server Docker cùng máy; đường chuyển tiếp thêm khoảng 110 ms. Vòng eval của SIMPLE **chờ server**: `Psi0DecoupledWbcAgent.get_action` gọi `/act` đồng bộ khi hàng action rỗng (mỗi 24 bước), và mô phỏng không chạy trong lúc chờ. Độ trễ vì vậy chỉ thêm giờ tường. Chỗ duy nhất dính thời gian thật là bộ nội suy của WBC: mỗi bước đặt waypoint thân trên ở `t_now + 1/50 s` (`time.monotonic`) và đọc lệnh ở `t_now`. Khi khoảng cách giữa hai bước lớn hơn nhiều so với 20 ms, lệnh gần như bằng waypoint mới nhất. Ở `mujoco_isaac` mỗi bước đã mất khoảng 1 s vì render, nên thêm 0,1–0,5 s ở một bước trong 24 không đổi gì đáng kể. Eval Isaac của tác giả cũng chạy chậm hơn thời gian thật như vậy.

Thời gian thật của `mujoco_isaac` trên máy 3060 là khoảng 25 phút mỗi episode (đo trên 3 episode hỏng: lượt thử 1 715 s và hai episode đầu của lượt 1 khoảng 27 phút mỗi episode; episode thành công có thể ngắn hơn), gấp 2,5–4 lần mức 6–10 phút của README. Ước lượng cho AC 9 đủ 10 × 3 × 3 = 90 episode: khoảng 38 giờ máy 3060 và 74 CU Colab; một lượt 10 episode Level 0: khoảng 4,5 giờ và 9 CU.

### 3.5 Trả lời Q-27C [Đề xuất, tạm]

Không: ở `mujoco`, checkpoint của tác giả không giữ được thành công. Sau khi sửa lỗi spawn, Level 0 vẫn 0/10, so với 7/10 công bố ở `mujoco_isaac` (p = 6 × 10⁻⁶). Các lượt cũ (0/90, lỗi spawn) cùng chiều. Kiểm open-loop (mục 3.3) phù hợp với giả thuyết server đúng [Đề xuất]. Đây chưa phải chứng minh: mới 3 episode train, chưa có ngưỡng, và L1 của vyaw là 0,21–0,27. B4 cho thấy policy dựa vào ảnh. Nên nguyên nhân nhiều khả năng là khác biệt ảnh giữa render MuJoCo và Isaac, hoặc một lỗi phía client chưa tìm ra.

Ở Level 0 của bộ eval `de140d6`, vật và khay nằm đúng vị trí của episode train cùng chỉ số; chỉ robot khởi đầu lùi 6,1 cm (mục 3.1). Vậy 0/10 là trên chính vị trí vật đã thấy lúc train. Điều này nghiêng về lỗi hệ thống (renderer khác, hoặc lỗi phía client) hơn là policy yếu. Đề xuất cho HE: giữ mặc định của design mục 4.2 (ảnh train và ảnh eval đều render Isaac; eval ở `mujoco_isaac`), không chuyển sang `mujoco`. Kết luận còn "tạm" cho tới khi có lượt `mujoco_isaac` của chính đội, với file task đã sửa, đạt gần 7/5/6 (B5, mục 3.6). Nếu lượt đó cũng hỏng thì lỗi ở phía client và kết luận trên phải xét lại.

**[Đã chốt]** (Hiếu, 3/11/2026): không thuê GPU; AC 9 chạy với server Ψ₀ trên Colab và Isaac trên máy 3060 (mục 3.4.1).

**Q8 · chờ chốt** [Đề xuất]: chấp nhận lệch của nhiệm vụ con 2.1 là khác biệt đã biết. Story đòi image Ψ₀ riêng trong `docker/psi0/` và ghi chú flash-attn trên máy 5090. PR này dùng image công bố của tác giả, ghim theo digest, trên máy 3060; trên Colab thì dùng đúng danh sách gói của image đó (`docker/psi0/requirements-image.txt`). Phía SIMPLE dùng image công bố ghim theo digest, cộng một file task của `b75c678` mount đè. Chờ Hiếu chốt; chốt xong thì ghi vào story.

### 3.6 Bộ benchmark chứng minh kết luận [Đề xuất]

Mỗi phép kiểm chỉ đổi một yếu tố, giữ nguyên mọi thứ khác. Tiêu chí đạt ghi ở đây trước khi có kết quả Isaac.

| # | Câu cần chứng minh | Chỉ đổi | Tiêu chí đạt | Kết quả |
|---|---|---|---|---|
| B1 | Server, trọng số, chuẩn hóa đúng | (không đổi; so action dự đoán với action ghi lại) | Sai số gần 0 ngoài lúc chuyển pha | Phù hợp [Đề xuất]: 3 episode, chưa có ngưỡng (mục 3.3) |
| B2 | Server Colab giống server Docker | Máy chạy server | L1 hai bên chênh trong cỡ nhiễu lấy mẫu | Phù hợp: L1 lệch 0,002–0,017 mỗi episode; chưa ước lượng nhiễu lấy mẫu (mục 3.4.1) |
| B3 | Độ trễ `/act` không đổi kết quả | Độ trễ: 0 s, 0 s, +2 s mỗi lần gọi | Lệch quỹ đạo của lượt +2 s không lớn hơn lệch giữa hai lượt 0 s | Chưa chạy (runner `fwdata/logs/b3.sh` trên máy 3060) |
| B4 | Policy dựa vào ảnh | Ảnh: thật, xám, mờ, lệch thời gian | L1 tăng rõ khi ảnh sai | Đạt (dưới đây) |
| B5 | `mujoco` hỏng vì renderer (file task `b75c678`) | Renderer: MuJoCo hay Isaac | Isaac không thấp hơn 7/5/6 có ý nghĩa (nhị thức một phía, α = 0,05) và Fisher `mujoco` so với `mujoco_isaac` có p < 0,05 | `mujoco` Level 0 0/10 (bản sửa); Isaac chưa chạy với bản sửa |

Cách đọc B5: Isaac gần 7/5/6 thì renderer là nguyên nhân và AC 9 đạt; Isaac cũng gần 0 thì lỗi ở phía client SIMPLE (B1 đã loại phía server); ở giữa thì chờ PSI Lab trả lời Q-27E.

**B4 · Policy dựa vào ảnh** (3/11/2026, `eval_psi0.sh openloop`, server thứ hai trên Colab L4 cổng 22086, 3 episode train `e78fb93`, mỗi 5 khung). L1 bước đầu của chunk, trung bình 3 episode:

| Ảnh đưa vào | L1 tổng | Tay | Cánh tay | Thân rpy | vx | vy | vyaw |
|---|---|---|---|---|---|---|---|
| Thật | 0,090 | 0,082 | 0,078 | 0,042 | 0,060 | 0,026 | 0,209 |
| Mờ (Gauss bán kính 8) | 0,149 (×1,7) | 0,075 | 0,090 | 0,040 | 0,108 | 0,024 | 0,417 |
| Xám (128) | 0,179 (×2,0) | 0,074 | 0,122 | 0,050 | 0,119 | 0,023 | 0,338 |
| Lệch thời gian (ảnh thật, cách nửa episode) | 0,231 (×2,6) | 0,130 | 0,126 | 0,045 | 0,234 | 0,033 | 0,534 |

Policy dựa vào ảnh: chỉ làm mờ ảnh (giữ bố cục) đã tăng sai số 1,7 lần, chủ yếu ở lệnh đi (vx, vyaw) và cánh tay. Lệnh tay gần như không đổi khi ảnh xám hoặc mờ, nên đóng mở tay chủ yếu theo state; nó chỉ hỏng khi ảnh cho thấy sai pha (lệch thời gian). Ảnh MuJoCo (bàn xám, vật trắng, sàn ô bàn cờ) còn khác ảnh train nhiều hơn ảnh làm mờ, nên việc policy hỏng ở `mujoco` khớp với kết quả này. B4 chưa chứng minh riêng ảnh MuJoCo gây hỏng; B5 mới chứng minh điều đó.

## 4. Checkpoint ablation của thí nghiệm HE (AC 11, nhiệm vụ con 8)

Kiểm ngày 3/11/2026. `psi-model` đã có revision mới `76febdc998e5d32a1ed978c286018752676fce64` (commit 02/11/2026). Sáu thư mục dưới đây giống hệt nhau ở revision ghim `cb1480f…` và ở `76febdc…`: cùng danh sách file, cùng sha256 của mọi file LFS. Vì vậy giữ revision ghim `cb1480f…` cho DA-26, không cần đổi.

| Vai trò trong HE | VLM (`pre.*`) | sha256 `model.safetensors` | Action header (`postpre.*`) | sha256 `action_header.safetensors` |
|---|---|---|---|---|
| Chỉ HE, không EgoDex | `pre.abl.only.he.2512311516.48k` | `a2ae8c24f83c90dea78282defc6abbbd5475e77ede24e1538c9b3b38ec457f4e` | `postpre.abl.only.he.2602050012` | `9118bc03bebd53cbf3567c9e220618e90f8605a5cf4247aa878747b17de2a7e0` |
| 10% EgoDex | `pre.abl.ego.10per.2602021632.46k` | `e84a51035b517c7729e78dcc5cebc8a7f758adf4cf7c161b515d8a46190c8655` | `postpre.abl.ego.10per.2602050006` | `921de23437374d996c3225e6be0bb7acf12bf3098152a596fea7664d778afdc4` |
| Gốc EgoDex 200k + HE 30k | `pre.fast.1by1.2601091803.ckpt.ego200k.he30k` | `6e63da17bdd22430bc07c40e4b14ebb96c9d124d014c532449142862c186d3f9` | `postpre.1by1.pad36.2601131206.ckpt.he30k` | `238b4d95862b0eb44bffa75a2ae69e120aeda3d159fd6f29802dd9338019e14d` |

Chung cho cả sáu: tải lên ngày 12/03/2026; mỗi `pre.*` có 12 file, 4,279 GB, VLM Qwen3-VL bf16, cùng `tokenizer.json` (sha256 `aeb13307a71acd8f…`); mỗi `postpre.*` chỉ có một file action header 1,991 GB. Không có file nào ghi số bước, dữ liệu hay recipe; các số `48k`, `46k`, `ego200k`, `he30k` chỉ là tên thư mục.

Dữ kiện quan trọng cho DA-26: checkpoint task hai bàn của tác giả (`g1wholebodylocomotionpickbetweentablesteleop-v0…b64.gpus4.2604081126`, mục 3) được fine-tune từ đúng cặp "gốc" ở dòng thứ ba (`argv.txt`: `model_name_or_path` và `pretrained-action-header-path`), VLM đóng băng, 40 000 bước, batch 16 × 4 GPU. Như vậy mốc so ở mục 3 là nhánh "EgoDex + HE" của HE với recipe post-train đã biết; hai nhánh ablation chỉ khác cặp khởi tạo nếu PSI Lab xác nhận cùng recipe ở bước `postpre`.

Câu hỏi Q-27E gửi PSI Lab (Hiếu gửi, chung email giấy phép ở nhiệm vụ con 1.3) [Đề xuất]:

1. Số bước pretrain VLM thật của `pre.abl.only.he…48k` và `pre.abl.ego.10per…46k`: 48k, 46k là số bước hay số mẫu? Batch và dữ liệu (HE đủ, 10% EgoDex chọn thế nào)?
2. Ba `postpre.*` (`abl.only.he`, `abl.ego.10per`, `1by1.pad36…he30k`) có cùng recipe post-train action header không (dữ liệu, số bước, batch, lr)? `he30k` nghĩa là 30k bước trên HE?
3. Sáu checkpoint này có train trên dữ liệu SIMPLE hoặc sonic không (điều kiện `clean_for_main_task` của AC 6)?
4. (thêm 3/11/2026) Số 7/5/6 của `G1WholebodyLocomotionPickBetweenTablesTeleop-v0` đo trên bộ eval nào: bản tải lên 14/09/2026 (`e78fb93`), bản "eval-fixed" 02/11/2026 (`de140d6`), hay một bản trước đó? Checkpoint `…2604081126` train trên bản dữ liệu nào (bản gốc hay "data-fixed")? Ở `mujoco_isaac` có cần cờ hoặc cấu hình gì ngoài README không?

## Tiếp tục từ đây (cập nhật 3/11/2026, 23:20)

1. Xong: mount file task `b75c678`; cache bộ eval theo revision, kèm kiểm sha256; client kiểm `/info` của server; chạy lại `mujoco` Level 0 (0/10).
2. `mujoco_isaac` với file đã sửa (B5, AC 9): server Ψ₀ trên Colab, theo mục 3.4.1 (`colab new -s s103psi0 --gpu L4`, `PSI0_ENV=image`, hai cổng chuyển tiếp SSH). Level 0 trước, 10 episode, khoảng 4,5 giờ. Laptop phải bật suốt thời gian chạy.
3. B3 (độ trễ): runner `fwdata/logs/b3.sh` trên máy 3060; chạy được ngay với server cục bộ.
4. Nếu Isaac cũng hỏng: phát lại action của episode train trên điều kiện eval cùng chỉ số, qua cùng client và WBC, để tìm lỗi phía client.
5. Chờ Hiếu: Q8 (mục 3.5), Q-27E (mục 4).
