# Stage 1 của Ψ₀ trên dữ liệu egocentric (DA-30)

_Bắt đầu 4/11/2026. Story [DA-30](../product/stories/DA-30-stage1-egocentric.md); [design 27/10/2026](../superpowers/specs/2026-10-27-g1-psi0-demo-design.md) mục 7.8, 8.1. Mọi kết quả, kể cả âm, ghi ở đây (AC 3)._

## 1. Lần chạy ngắn trên EgoDex (AC 1)

Đây là **bằng chứng đường đi, không phải thí nghiệm**: dữ liệu ở định dạng stage 1 của Ψ₀ tới được model, loss giảm, `metrics.jsonl` được ghi. Ψ₀ đã pretrain stage 1 trên EgoDex, nên lần chạy này không cho thông tin mới về model. Probe P1, P2, P4 (DA-09) dời sau demo.

### 1.1 Trạng thái

| Bước | Trạng thái | Bằng chứng |
|---|---|---|
| Recipe, RunPlan, launcher, driver Colab, test CPU | Xong | `uv run pytest packages/flywheel-psi0/tests/stage1`: 28 test qua (driver Colab chạy `run`, `repeat`, `persist` trên Ψ₀ giả). Bộ canh CU nằm ở script dùng chung (mục 1.6), test của nó ở PR #108 |
| Loader của Ψ₀ đọc dữ liệu thay thế (CPU) | Xong, 4/11/2026: 20 episode, rồi cả 218 | Mục 1.5 |
| Lần chạy trên Colab | **Đã duyệt CU, 4/11/2026** (tier 2). Hiếu miễn bước che danh tính cho mẫu EgoDex công bố ("Waive for EgoDex", 4/11/2026, mục 1.4). Chạy từ `master` sau khi PR merge, với bộ canh CU dùng chung (mục 1.6) | Ước lượng 2,3 CU trên một L4, trần 4 CU ([sổ chi phí](../g0/ledger/DA-30.csv)) |

**Quyết định [Đã chốt 4/11/2026, Hiếu]:** "Approve tier 2". Tier 2 gồm lần chạy ngắn này, ước lượng khoảng 2,3 CU, trần 4 CU. Trước đó cùng ngày Hiếu đã dừng mọi job Colab (số dư khoảng 101,8 CU). Lần chạy dùng code ở `master` sau khi PR của DA-30 được merge, không chạy từ nhánh.

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
- Che danh tính: video EgoDex là góc nhìn Vision Pro xuống mặt bàn, do Apple công bố. Dữ liệu thay thế đi thẳng vào stage 1, chưa qua bước che danh tính của pipeline (DA-04, DA-18). CLAUDE.md ghi bước che danh tính là bất biến ("trước mọi bước xử lý khác"), nên lần chạy cần Hiếu miễn rõ ràng.

**Quyết định [Đã chốt 4/11/2026, Hiếu]:** "Waive for EgoDex", trả lời câu hỏi có miễn bước che danh tính cho mẫu EgoDex công bố trong lần chạy ngắn của DA-30 không. Phạm vi hẹp:

- Chỉ áp cho mẫu EgoDex công bố (`data_class` `public`) trong các lần chạy stage 1 của DA-30.
- Không áp cho video egocentric đội tự quay: video đó vẫn phải qua bước che danh tính trước mọi bước khác, như CLAUDE.md yêu cầu. Mọi nguồn egocentric khác cũng vậy.
- Chốt trong mã: khối `dataset` của RunPlan ghi `source.name`, `data_class` và `identity_masked`. Một RunPlan có `identity_masked: false` chỉ nạp được khi nguồn là `egodex` và `data_class` là `public` (`masking_waived` trong `stage1/egodex_sample.py`). Nguồn khác, hoặc EgoDex với `data_class` khác, bị từ chối khi nạp plan, khi `setup` của driver và khi chạy `egodex_sample fetch`. Test: `test_the_egodex_waiver_covers_only_public_egodex`, `test_the_sample_fetch_refuses_an_unwaived_source`.

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

Lần 2, cùng ngày, **cả 218 episode**, 12 worker như run thật, container giới hạn 12 CPU (như VM Colab), 12 GB RAM và `--shm-size 4g`. Lần đầu với `/dev/shm` mặc định 64 MB của Docker, worker chết vì `Bus error`; đó là giới hạn của container, VM Colab không có giới hạn này.

| Mục | Kết quả |
|---|---|
| Một epoch | 13 batch × 16 = 208 mẫu (`drop_last`), `problems` rỗng |
| `input_ids` | 189–220 token mỗi batch |
| Token action FAST mỗi mẫu | 1–43; không mẫu nào bằng 0 (một mẫu chỉ có 1 token, chắc là action gần đứng yên) |
| Ảnh, action | lưới 16 × 30 mọi batch; action 1 × 48 |
| Thời gian | batch đầu 5,8 s (12 worker khởi động và nạp song song), cả epoch khoảng 7,2 s, tức khoảng 30 mẫu/s **dù máy đang tải nặng** (load 67 trên 64 CPU) |

Ở tốc độ đó, nạp dữ liệu tốn khoảng 1 s cho mỗi bước 32 mẫu, nhỏ so với giả định 9 s/bước (mục 1.8). Phần chưa biết vẫn là GPU và offload.

### 1.6 Chạy lại được

RunPlan [`egodex-short.yaml`](../../configs/runplans/stage1/egodex-short.yaml) (`run_plan_id` `rp_45304b9931c3`) chốt trước lần chạy:

- **Loss giảm**: trung vị 20 dòng train cuối thấp hơn trung vị 20 dòng đầu (mỗi dòng một batch, nên so trung vị của cửa sổ, không so hai bước).
- **Chạy lại**: chạy lại 3 bước đầu dưới job id khác (`da30-egodex-short-repeat`), cùng seed 7; loss bước đầu lệch không quá 2%. Seed cố định thứ tự dữ liệu (generator của DataLoader và seed của worker lấy từ seed của cấu hình).

**Bộ canh CU** là script dùng chung `scripts/colab/cu_watch.py` (PR #108, phải merge trước PR này). Mỗi phiên Colab có một tiến trình `session`, theo dõi phiên theo endpoint chứ không theo tên. Cả đợt có thêm một tiến trình `guard` làm lưới an toàn: dừng mọi phiên ở sàn, và dừng mọi assignment không có watcher sống đăng ký. Cách đo, biên và các đường fail closed ghi trong docstring của script. Với DA-30:

- **Chạy một mình.** Quy tắc vận hành từ review PR #108 (4/11/2026): DA-26 và DA-30 không chạy cùng lúc, và lần chạy 4 CU của DA-30 đi trước, một mình. `colab sessions` phải trống trước khi bắt đầu, vì guard dừng mọi assignment không đăng ký trên tài khoản.
- Watcher tự mở phiên (`session --new --name da30-stage1 --gpu L4 --cap 4`), nên số dư và mốc thời gian được ghi đúng lúc phiên bắt đầu. Không mở phiên bằng tay.
- Trần cứng 4 CU (`compute.max_compute_units` của RunPlan). Sàn `--floor 14` theo số dư thật của cả tài khoản (101,8 − 88 của tier 2), đặt ở cả guard lẫn watcher.
- Khi chi tiêu tới khoảng 3,45 CU, watcher chạy `persist` của driver trong kernel của phiên ([`persist_cell.py`](../../configs/runplans/stage1/persist_cell.py)), để log và `metrics.jsonl` còn lại sau khi phiên bị dừng ở trần. Mốc này sớm hơn 90% trần để `persist` có đủ 600 s trước khi dừng. Vì vậy:
  - lệnh train phải chạy trong shell SSH, không qua `colab exec`, để kernel rảnh;
  - Drive phải được mount (`colab drivemount -s da30-stage1 /content/drive`) ngay sau `setup`.
- Chỉ bắt đầu train khi đã có file `fwdata/colab/da30/da30-stage1.ready`, nghĩa là phiên đã chạy đúng L4.
- Dòng `exit` cuối của `da30-stage1.jsonl` có `balance_drop` của tài khoản, cùng `spent`, `wall_cu` và `balance_cu` của phiên. Đây là số liệu cho dòng `measured` của sổ chi phí.
- Mã thoát:
  - 0: phiên tự kết thúc;
  - 3: đã dừng ở trần hoặc ở sàn;
  - 4: sai loại GPU;
  - 5: `STOP_FAILED`, phiên có thể vẫn tính tiền. Guard tiếp tục dừng nó, nhưng vẫn phải xem `colab sessions` ngay;
  - 6: crash, tín hiệu hoặc `new` lỗi; mọi assignment nó tạo đã dừng.

```bash
export PATH=~/project/wm-wam-review/.venv-colab-cli/bin:$PATH
R=fwdata/colab/da30; mkdir -p $R; rm -f $R/da30-stage1.ready
nohup setsid bash -c 'trap "" TERM HUP INT; python3 scripts/colab/cu_watch.py guard --registry "$0" --floor 14 --log "$0/guard.jsonl"; echo "exit $?"' $R < /dev/null > $R/guard.out 2>&1 &
nohup setsid bash -c 'trap "" TERM HUP INT; python3 scripts/colab/cu_watch.py session --registry "$0" --new --name da30-stage1 --gpu L4 --cap 4 --floor 14 --persist "colab exec -s da30-stage1 -f configs/runplans/stage1/persist_cell.py" --log "$0/da30-stage1.jsonl"; echo "exit $?"' $R < /dev/null > $R/da30-stage1.out 2>&1 &
until [ -f $R/da30-stage1.ready ]; do grep -q '^exit ' $R/da30-stage1.out && exit 1; sleep 5; done
```

Lệnh trên Colab (L4, phiên `da30-stage1` do bộ canh mở), theo thứ tự, từ bản sao repo ở `/content/da30/fw` với `PYTHONPATH` gồm `packages/flywheel-psi0/src` và `packages/flywheel-contracts/src` như DA-19:

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
- s/bước là giả định (9 s), chưa đo. Phần nạp dữ liệu đã đo khoảng 1 s (mục 1.5); phần còn lại là GPU, chuyển trọng số qua lại RAM và Adam trên CPU của offload.

### 1.9 Ước lượng CU

Giả định, chưa đo. Một VM L4 ở 1,94 CU/giờ (S1-04). **Hơn một nửa của 2,3 CU là phần cố định** (38 trong 68 phút, khoảng 1,2 CU), không phụ thuộc số bước. Phần train dùng 9 s/bước, cũng là giả định cho fine-tune toàn bộ VLM với ZeRO-3 offload trên một L4, chưa đo trong dự án; recipe ghi cùng số này (`estimate.seconds_per_step`). Phần cố định khoảng 38 phút: setup môi trường của DA-19 khoảng 10 phút; tải `pre.*` 4,3 GB và mẫu EgoDex 2,17 GB khoảng 8 phút; `actions_48d` và loader check khoảng 5 phút (đo trên laptop và `rtx3060`: 34 s và dưới 1 phút); nạp model khoảng 3 phút; checkpoint cuối khoảng 4 phút; chạy lại 3 bước khoảng 7 phút; persist khoảng 1 phút. Cộng 200 bước train:

| s/bước | Train | Tổng | CU |
|---|---|---|---|
| 5 | 17 phút | 55 phút | 1,8 |
| 9 (giả định chính) | 30 phút | 68 phút | 2,2–2,3 |
| 15 | 50 phút | 88 phút | 2,8 |
| 26 | 86 phút | 124 phút | 4,0 (trần của RunPlan) |

Quy tắc dừng [Đề xuất]: đọc s/bước trong `train.log` sau 20 bước; quá 20 s thì dừng VM và báo Hiếu trước khi chạy tiếp, trước khi bộ canh tự dừng ở khoảng 24 s (dưới đây). Bộ canh CU (mục 1.6) là chốt chặn cuối: phiên tự dừng trước 4 CU dù không ai đọc log. Biên của bộ canh là 430 s, khoảng 0,23 CU ở L4, nên phiên dừng ở khoảng 3,77 CU, tức khoảng 117 phút. Trừ 38 phút cố định, còn khoảng 79 phút train, tức khi s/bước vượt khoảng 24 s.
