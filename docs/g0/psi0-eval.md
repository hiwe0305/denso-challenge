# S1-03 · Tái tạo đánh giá Ψ₀, checkpoint gốc (Q0), độ không tất định

_Kết quả của story [S1-03](../product/stories/S1-03-tai-tao-danh-gia-psi0.md). Quy ước file ở [docs/g0/README.md](README.md). Người làm: Hiếu. Bắt đầu 24/10/2026._

| Mục | Trạng thái |
|---|---|
| 1.1 Liệt kê checkpoint trong `psi0/` | Xong 24/10/2026 |
| 1.2 Chọn checkpoint gốc và task tái tạo | Chưa |
| 1.3 Câu hỏi provenance cho PSI Lab | Chưa |
| 2.1–2.2 Môi trường và script serve | Smoke không model đạt trên máy dev 24/10/2026; nạp model và `/act` chờ máy 5090 (mục 2) |
| 2.3–5 Đo VRAM, độ trễ, đánh giá, độ không tất định | Chưa; cần máy 5090 |
| 8 Checkpoint ablation của HE (AC 11) | Liệt kê xong 3/11/2026 (mục 4); câu hỏi Q-27E chờ Hiếu gửi PSI Lab |

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
