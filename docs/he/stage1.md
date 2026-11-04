# Stage 1 của Ψ₀ trên dữ liệu egocentric (DA-30)

_Bắt đầu 4/11/2026. Story [DA-30](../product/stories/DA-30-stage1-egocentric.md); [design 27/10/2026](../superpowers/specs/2026-10-27-g1-psi0-demo-design.md) mục 7.8, 8.1. Mọi kết quả, kể cả âm, ghi ở đây (AC 3)._

## 1. Lần chạy ngắn trên EgoDex (AC 1)

Đây là **bằng chứng đường đi, không phải thí nghiệm**: dữ liệu ở định dạng stage 1 của Ψ₀ tới được model, loss giảm, `metrics.jsonl` được ghi. Ψ₀ đã pretrain stage 1 trên EgoDex, nên lần chạy này không cho thông tin mới về model. Probe P1, P2, P4 (DA-09) dời sau demo.

### 1.1 Trạng thái

| Bước | Trạng thái | Bằng chứng |
|---|---|---|
| Recipe, RunPlan, launcher, test CPU | Xong | `uv run pytest packages/flywheel-psi0/tests/stage1`: 21 test qua |
| Loader của Ψ₀ đọc dữ liệu thay thế (CPU) | Xong, 4/11/2026 | Mục 1.5 |
| Lần chạy trên Colab | **Chờ Hiếu duyệt CU** | Ước lượng 2,3 CU, trần 4 CU ([sổ chi phí](../g0/ledger/DA-30.csv)) |

### 1.2 Recipe

Script `scripts/train/psi0/pretrain-egodex-psi0-fast.sh` **vẫn còn** ở commit ghim `cda3fdf` (khác script stage 3). Recipe [`psi0-stage1-egodex.yaml`](../../configs/runplans/stage1/psi0-stage1-egodex.yaml) chép nguyên các tham số của script đó. Recipe stage 1 của DA-19 ([`psi0-stage1.yaml`](../../configs/models/psi0-stage1.yaml)) lấy từ script HE (`pretrain-he-psi0-fast.sh`: config `pretrain_he_qwen3vl_config`, ảnh 240×320, không tích lũy gradient), nên không dùng cho EgoDex.

Khác với script, kèm lý do:

| Tham số | Script | Lần chạy này | Lý do |
|---|---|---|---|
| `model.model_name_or_path` | không truyền (Qwen3-VL-2B gốc) | `pre.fast.2605160748.ckpt.ego390k` | AC 1: khởi tạo từ `pre.*`. Timestamp `2605160748` trùng `--timestamp` của script: đây là checkpoint do chính recipe này tạo ra (README của Ψ₀: "EgoDex 390K steps") |
| `train.max_training_steps` | 1.000.000 | 200 | "vài trăm bước" |
| `train.checkpointing_steps` | 5000 | 200 | một checkpoint ở cuối |
| `train.validation_steps` | 1000 | 0 | dữ liệu thay thế không có split `test/`; vài trăm bước không đủ để đọc val dạng sinh token |
| `train.deepspeed_config` | `zero3.json` (mặc định của biến `DEEPSPEED_CONFIG` trong script) | `zero3_offload.json` (file của tác giả) | một GPU: ZeRO-3 trên một thiết bị không chia; fine-tune toàn bộ VLM 2,1 tỉ tham số cần khoảng 34 GB (trọng số bf16, master fp32, Adam) trước activation, quá 24 GB của L4. Offload đưa optimizer và trọng số sang RAM (VM L4: 52 GB) |
| `seed`, `exp`, `timestamp`, `train.output_dir`, `data.root-dir` | của tác giả | theo job | `Psi0Trainer` điền |

Giữ nguyên: batch 16 mỗi GPU, tích lũy gradient 2 (batch toàn cục 32 trên một GPU; tác giả chạy nhiều node), lr 1e-4 hằng số, ảnh 270×480, `chunk_size` 1, `upsample_rate` 3, delta action, tokenizer FAST `egodex-rel-50w-1x48-v2048-s100`, stats `egodex_stat_all.json`, train cả LLM, vision và projector.

### 1.3 Lỗi ở commit ghim và cách vá

Commit `e91e1e7` của Ψ₀ (4/9/2026) bỏ dòng `shuffle = True` trong `PretrainTrainer.create_dataloaders` nhưng giữ dòng đọc biến đó. Với dataset không dùng sampler trộn (EgoDex, HE), stage 1 dừng với `UnboundLocalError` trước bước đầu. Ngày 4/11/2026 nhánh `main` của Ψ₀ vẫn là `cda3fdf`, nên lỗi chưa được sửa ở upstream. Loader check (mục 1.5) tái hiện đúng lỗi này trên mã ở `cda3fdf`.

Cách vá [Đề xuất, cần Hiếu duyệt]: launcher stage 1 dịch lại hàm đó từ chính mã nguồn của Ψ₀, đổi đúng một dòng thành `shuffle = True` như trước `e91e1e7`, giữ số dòng trong traceback ([`patches.py`](../../packages/flywheel-psi0/src/flywheel_psi0/stage1/patches.py)). Bản clone Ψ₀ không bị sửa, commit ghim không đổi. Nếu tác giả sửa lỗi (dòng `shuffle = True` trở lại), bản vá tự bỏ qua; nếu hàm đổi khác, launcher dừng thay vì đoán. Đây là lệch khỏi quy tắc "chạy mã của tác giả nguyên vẹn" của DA-19, nên ghi ở đây.

### 1.4 Dữ liệu

Bản export EgoDex của DA-18 (Hưng, hạn 8/11/2026) chưa có. Trong lúc chờ, dùng dữ liệu công bố theo đúng định dạng mà DA-18 AC 1 phải xuất (định dạng do loader của Ψ₀ quy định, nên không phụ thuộc lựa chọn của DA-18):

- Nguồn: tập test của EgoDex (`test.zip`, 17,3 GB, 111 task, 3243 episode; Apple). Lấy 2 episode số nhỏ nhất của mỗi task: **218 episode, 2,17 GB**. Chỉ tải các file đã chọn bằng HTTP range, không tải cả zip ([`egodex_sample.py`](../../packages/flywheel-psi0/src/flywheel_psi0/stage1/egodex_sample.py)); `manifest.json` ghi tên, cỡ và CRC-32 của từng file.
- Đặt dưới `part1/<task>/<i>.hdf5|mp4` (loader của Ψ₀ train trên `part1`–`part5` và `extra`), rồi thêm `actions_48d` bằng script H-RDT của tác giả (`src/h_rdt/datasets/pretrain/precompute_48d_actions.py`).
- Đo trên laptop ngày 4/11/2026: tải 218 episode mất khoảng 12 phút (1–7 MB/s qua Range); lần đầu đứt kết nối ở file 428/436 (`IncompleteRead`), nên mỗi request giờ thử lại tối đa 6 lần, và chạy lại `fetch` giữ các file đã đủ (lần chạy lại lấy nốt 8 file trong 16 s). Script `actions_48d` chạy 34 s với 8 tiến trình; cả 218 file có `actions_48d`, tổng 90.906 khung.
- Đổi sang bản export của DA-18 khi merge: chỉ đổi khối `dataset` của RunPlan.
- Loader của Ψ₀ coi mỗi episode là một mẫu và bốc một khung ngẫu nhiên mỗi lần: 218 episode với batch 16 là 13 batch mỗi epoch; 200 bước × 2 batch là khoảng 31 epoch. Loss giảm phần lớn do học thuộc tập nhỏ; đúng với mục đích chứng minh đường đi, không nói gì về chất lượng model.
- Dữ liệu `public` (design mục 8.4). Giấy phép EgoDex là CC-BY-NC-ND; câu hỏi Q-EGO-LIC (design mục 14) vẫn mở với Hiếu. Lần chạy chỉ dùng để train, không phát hành gì suy ra từ dữ liệu.
- Che danh tính: video EgoDex là góc nhìn Vision Pro xuống mặt bàn, do Apple công bố. Dữ liệu thay thế đi thẳng vào stage 1, chưa qua bước che danh tính của pipeline (DA-04, DA-18). Bản export của DA-18 sẽ có bước đó; cần Hiếu xác nhận dùng mẫu công bố chưa che cho lần chạy ngắn [Đề xuất].

### 1.5 Loader check trên CPU (4/11/2026)

[`loader_check.py`](../../packages/flywheel-psi0/src/flywheel_psi0/stage1/loader_check.py) đọc `launch.json` của job, phân tích argv bằng config và tyro như `scripts/train.py`, dựng `PretrainTrainer` trên CPU, chỉ nạp processor của `pre.*` (không nạp trọng số), rồi gọi `create_datasets` và `create_dataloaders` của chính trainer. Dùng lại được cho bản export của DA-18 trước khi tốn GPU.

Chạy trong image Docker Ψ₀ của tác giả (`psi0@sha256:0d58…80b2`) trên `rtx3060`, `PYTHONPATH` trỏ vào bản clone ở `cda3fdf`, 20 episode đầu của mẫu (đã thêm `actions_48d`), 4 worker, chỉ CPU:

| Mục | Kết quả |
|---|---|
| Hàm gốc ở `cda3fdf` | `UnboundLocalError: cannot access local variable 'shuffle' where it is not associated with a value` |
| Sau bản vá | 1 batch (20 episode, `drop_last`), 1,8 s kể cả khởi động worker |
| `input_ids` | 16 × 183 token |
| Ảnh | lưới 1 × 16 × 30 patch mỗi mẫu (270×480) |
| Token action FAST mỗi mẫu | 19–35, không mẫu nào bằng 0 |
| Action thô | 1 × 48 (delta, `chunk_size` 1) |
| NaN | không có |

`actions_48d`: script của tác giả chạy 3 s cho 20 file trên laptop, mọi file có khóa `actions_48d` kích thước N × 48.

### 1.6 Chạy lại được

RunPlan [`egodex-short.yaml`](../../configs/runplans/stage1/egodex-short.yaml) (`run_plan_id` `rp_9ff69c9f4645`) chốt trước lần chạy:

- **Loss giảm**: trung vị 20 dòng train cuối thấp hơn trung vị 20 dòng đầu (mỗi dòng một batch, nên so trung vị của cửa sổ, không so hai bước).
- **Chạy lại**: chạy lại 3 bước đầu dưới job id khác (`da30-egodex-short-repeat`), cùng seed 7; loss bước đầu lệch không quá 2%. Seed cố định thứ tự dữ liệu (generator của DataLoader và seed của worker lấy từ seed của cấu hình).

Lệnh trên Colab (L4), theo thứ tự, từ bản sao repo ở `/content/da30/fw` với `PYTHONPATH` gồm `packages/flywheel-psi0/src` và `packages/flywheel-contracts/src` như DA-19:

```bash
python3 -m flywheel_psi0.stage1.colab setup --work /content/da30 --plan fw/configs/runplans/stage1/egodex-short.yaml
```

```bash
Psi0/.venv-psi/bin/python -m flywheel_psi0.stage1.colab run --work /content/da30 --plan fw/configs/runplans/stage1/egodex-short.yaml
```

```bash
Psi0/.venv-psi/bin/python -m flywheel_psi0.stage1.colab repeat --work /content/da30 --plan fw/configs/runplans/stage1/egodex-short.yaml
```

```bash
python3 -m flywheel_psi0.stage1.colab persist --work /content/da30 --plan fw/configs/runplans/stage1/egodex-short.yaml
```

### 1.7 Kết quả

Chưa chạy. Ghi ở đây sau lần chạy: loss bước đầu và cuối, kết quả hai tiêu chí, s/bước, VRAM đỉnh, CU thực đo.

### 1.8 Rủi ro đã biết

- `zero3_offload.json` không được script nào của tác giả dùng ở `cda3fdf`; đường DeepSpeed với optimizer trong file cấu hình (`DummyOptim`, `DummyScheduler`) chưa chạy lần nào trong dự án. Nếu hỏng, phương án dự phòng là A100 40 GB với `zero3.json`, có thể hết VRAM (ước lượng ở mục 1.2); cần duyệt CU lại.
- s/bước là giả định (9 s), chưa đo: stage 1 giải mã khung video 1080p trên CPU và chuyển trọng số qua lại RAM mỗi bước.
