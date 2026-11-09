# Stage 1 của Ψ₀ trên dữ liệu egocentric (DA-30)

_Bắt đầu 4/11/2026. Story [DA-30](../product/stories/DA-30-stage1-egocentric.md); [design 27/10/2026](../superpowers/specs/2026-10-27-g1-psi0-demo-design.md) mục 7.8, 8.1. Mọi kết quả, kể cả âm, ghi ở đây (AC 3)._

## 1. Lần chạy ngắn trên EgoDex (AC 1)

Đây là **bằng chứng đường đi, không phải thí nghiệm**: dữ liệu ở định dạng stage 1 của Ψ₀ tới được model, loss giảm, `metrics.jsonl` được ghi. Ψ₀ đã pretrain stage 1 trên EgoDex, nên lần chạy này không cho thông tin mới về model. Probe P1, P2, P4 (DA-09) dời sau demo.

### 1.1 Trạng thái

| Bước | Trạng thái | Bằng chứng |
|---|---|---|
| Recipe, RunPlan, launcher, driver Colab, test CPU | Xong | `uv run pytest packages/flywheel-psi0/tests/stage1`: 28 test qua (driver Colab chạy `run`, `repeat`, `persist` trên Ψ₀ giả). Bộ canh CU nằm ở script dùng chung (mục 1.6), test của nó ở PR #108 |
| Loader của Ψ₀ đọc dữ liệu thay thế (CPU) | Xong, 4/11/2026: 20 episode, rồi cả 218 | Mục 1.5 |
| Lần chạy trên Colab | **Lần 1 hỏng trước bước train đầu, 4/11/2026** (DeepSpeed `betas: "auto"`, mục 1.7); 0,46 CU thực đo. Đã duyệt CU (tier 2). Hiếu miễn bước che danh tính cho mẫu EgoDex công bố ("Waive for EgoDex", 4/11/2026, mục 1.4). Chạy từ `master` sau khi PR merge, với bộ canh CU dùng chung (mục 1.6) | Ước lượng 2,3 CU trên một L4, trần 4 CU ([sổ chi phí](../g0/ledger/DA-30.csv)) |

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
| `train.deepspeed_config` | `zero3.json` (mặc định của biến `DEEPSPEED_CONFIG` trong script) | [`zero3_offload.json`](../../configs/runplans/stage1/zero3_offload.json) của repo này (từ 4/11/2026, sau lần chạy 1), dựa trên file cùng tên của tác giả | một GPU: ZeRO-3 trên một thiết bị không chia; fine-tune toàn bộ VLM 2,1 tỉ tham số cần khoảng 34 GB (trọng số bf16, master fp32, Adam) trước activation, quá 24 GB của L4. Offload đưa optimizer và trọng số sang RAM (VM L4: 52 GB) |
| `seed`, `exp`, `timestamp`, `train.output_dir`, `data.root-dir` | của tác giả | theo job | `Psi0Trainer` điền |

**File DeepSpeed của repo [Đề xuất, 4/11/2026].** File `zero3_offload.json` của tác giả không script nào dùng ở `cda3fdf`, và lần chạy 1 hỏng ở `accelerator.prepare` (mục 1.7). File của repo giữ nguyên phần ZeRO-3 và offload, chỉ đổi hai khối:

| Khối | File của tác giả | File của repo | Lý do |
|---|---|---|---|
| `optimizer.params` | `lr`, `betas`, `eps`, `weight_decay` đều là `"auto"` | 1e-4, [0,9; 0,999], 1e-8, 0,0, đúng giá trị của recipe | `accelerate` 1.7.0 chỉ điền `lr` và `weight_decay` cho `DummyOptim`; `betas` và `eps` để `"auto"` thì dừng (lỗi của lần chạy 1). Ghi đủ cả bốn để file nói rõ optimizer chạy với giá trị nào |
| `scheduler` | `WarmupLR`, mọi tham số `"auto"` | `WarmupCosineLR`, `warmup_min_ratio` và `cos_min_ratio` 1,0, `last_batch_iteration` −1 | Ψ₀ cho vision tower và projector lr riêng 1e-5. `WarmupLR` đặt một lr chung cho mọi nhóm, nên hai nhóm đó lên 1e-4, và hai bước đầu chạy ở lr 0. `WarmupCosineLR` nhân lr riêng của từng nhóm với một tỉ lệ, ở đây luôn là 1,0, nên lr hằng số như recipe (`constant`). Phải dựng ở bước −1: chỉ khi đó DeepSpeed 0.17.1 mới đặt `_last_lr`, mà `PretrainTrainer` đọc `get_last_lr()` sau mỗi micro-step, trước bước scheduler đầu tiên ở ranh giới tích lũy (review PR #112). Giá phải trả: lần cập nhật đầu tiên của nhóm đầu (LLM) chạy ở lr 0, một trên 200 bước |
| `gradient_clipping` | `"auto"` (`accelerate` điền 1,0) | 1,0 | Bằng `max_grad_norm` của recipe. Ψ₀ không tự clip khi chạy DeepSpeed (`pretrain.py:246`), nên đây là lần clip duy nhất; ghi rõ để `runplan check` so được |

`runplan check` so file với recipe: không giá trị nào của `optimizer.params` là `"auto"`; mọi `"auto"` còn lại là khóa mà `accelerate` 1.7.0 điền cho đường này (`FILLED_BY_ACCELERATE`); `lr`, `betas`, `eps`, `weight_decay` và `gradient_clipping` bằng recipe; scheduler hằng số theo nhóm và dựng ở bước −1. Đã thử trên laptop, trong môi trường Ψ₀, chỉ bước điền `"auto"` của `accelerate` (không cần DeepSpeed): file của tác giả báo đúng lỗi của lần chạy 1, file của repo điền hết. Chạy `WarmupCosineLR` của DeepSpeed 0.17.1 trên optimizer hai nhóm: dựng ở bước −1, `get_last_lr()` trả [0; 1e-5] trước bước đầu và [1e-4; 1e-5] từ đó đến hết; dựng ở bước 0, `get_last_lr()` báo lỗi "need to call step() first".

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

RunPlan [`egodex-short.yaml`](../../configs/runplans/stage1/egodex-short.yaml) (`run_plan_id` `rp_6c8cf029703b` từ lần chạy 2; lần chạy 1 là `rp_45304b9931c3`) chốt trước lần chạy:

- **Loss giảm**: trung vị 20 dòng train cuối thấp hơn trung vị 20 dòng đầu (mỗi dòng một batch, nên so trung vị của cửa sổ, không so hai bước).
- **Chạy lại**: chạy lại 3 bước đầu dưới job id khác (`da30-egodex-short-repeat`), cùng seed 7; loss bước đầu lệch không quá 2%. Seed cố định thứ tự dữ liệu (generator của DataLoader và seed của worker lấy từ seed của cấu hình).

**Bộ canh CU** là script dùng chung `scripts/colab/cu_watch.py` (PR #108, phải merge trước PR này). Mỗi phiên Colab có một tiến trình `session`, theo dõi phiên theo endpoint chứ không theo tên. Cả đợt có thêm một tiến trình `guard` làm lưới an toàn: dừng mọi phiên ở sàn, và dừng mọi assignment không có watcher sống đăng ký. Cách đo, biên và các đường fail closed ghi trong docstring của script. Với DA-30:

- **Một đợt một lúc.** Quy tắc vận hành từ review PR #108 (4/11/2026): guard dừng mọi assignment không đăng ký trên tài khoản, nên mỗi lúc tài khoản chỉ chạy một đợt; guard từ chối chạy khi đã có guard khác. Lần chạy ngắn 4 CU của DA-30 đi trước, rồi mới đến đợt của DA-26. `colab sessions` phải trống trước khi bắt đầu.
- Watcher tự mở phiên (`session --new --name da30-stage1 --gpu L4 --cap 4`), nên số dư và mốc thời gian được ghi đúng lúc phiên bắt đầu. Không mở phiên bằng tay.
- Trần cứng 4 CU (`compute.max_compute_units` của RunPlan). Mức duyệt 4 CU tính chung cho mọi lần chạy, nên **lần chạy 2 dùng `--cap 3.5`** (4 trừ 0,46 CU của lần chạy 1, làm tròn xuống), như lệnh dưới **[Đã chốt 4/11/2026]**: chặt hơn mức đã duyệt, nên không cần quyết định mới. Sàn `--floor 14` theo số dư thật của cả tài khoản (101,8 − 88 của tier 2), đặt ở cả guard lẫn watcher.
- Khi chi tiêu tới khoảng 3,45 CU, watcher chạy `persist` của driver trong kernel của phiên ([`persist_cell.py`](../../configs/runplans/stage1/persist_cell.py)), để log và `metrics.jsonl` còn lại sau khi phiên bị dừng ở trần. Mốc này sớm hơn 90% trần để `persist` có đủ 600 s trước khi dừng. Vì vậy:
  - lệnh train phải chạy trong shell SSH, không qua `colab exec`, để kernel rảnh;
  - Drive phải được mount (`colab drivemount -s da30-stage1 /content/drive`) ngay sau `setup`.
- Chỉ bắt đầu train khi lệnh dưới in `READY`. Điều kiện: đã có file `$R/da30-stage1.ready` (phiên đã chạy đúng L4) và heartbeat của guard (`$R/guard.beat`) mới hơn 120 s. Mỗi lần chạy dùng một registry mới `$R`.
- Dòng `exit` cuối của `da30-stage1.jsonl` có `balance_drop` của tài khoản, cùng `spent`, `wall_cu` và `balance_cu` của phiên. Đây là số liệu cho dòng `measured` của sổ chi phí.
- Mã thoát:
  - 0: phiên tự kết thúc;
  - 3: đã dừng ở trần hoặc ở sàn;
  - 4: sai loại GPU;
  - 5: `STOP_FAILED`, phiên có thể vẫn tính tiền. Guard tiếp tục dừng nó, nhưng vẫn phải xem `colab sessions` ngay;
  - 6: crash, tín hiệu hoặc `new` lỗi; mọi assignment nó tạo đã dừng.
  - Khi chính guard dừng phiên, log có `GuardStopped`: mã 3 nếu do sàn, mã 6 nếu guard không thấy watcher sống.

```bash
export PATH=~/project/wm-wam-review/.venv-colab-cli/bin:$PATH
R=fwdata/colab/da30-$(date +%Y%m%d-%H%M%S); mkdir -p fwdata/colab && mkdir $R
nohup setsid bash -c 'trap "" TERM HUP INT; python3 scripts/colab/cu_watch.py guard --registry "$0" --floor 14 --log "$0/guard.jsonl"; echo "exit $?"' $R < /dev/null > $R/guard.out 2>&1 &
nohup setsid bash -c 'trap "" TERM HUP INT; python3 scripts/colab/cu_watch.py session --registry "$0" --new --name da30-stage1 --gpu L4 --cap 3.5 --floor 14 --persist "colab exec -s da30-stage1 -f configs/runplans/stage1/persist_cell.py" --log "$0/da30-stage1.jsonl"; echo "exit $?"' $R < /dev/null > $R/da30-stage1.out 2>&1 &
( until [ -f $R/da30-stage1.ready ]; do grep -q '^exit ' $R/da30-stage1.out && exit 1; sleep 5; done
  [ -f $R/guard.beat ] && [ $(( $(date +%s) - $(stat -c %Y $R/guard.beat) )) -lt 120 ] ) && echo READY || echo "NOT READY: do not start the job"
```

Lệnh trên Colab (L4, phiên `da30-stage1` do bộ canh mở), theo thứ tự, từ bản sao repo ở `/content/da30/fw` với `PYTHONPATH` gồm `packages/flywheel-psi0/src` và `packages/flywheel-contracts/src` như DA-19.

`setup` chạy **pre-flight** (`flywheel_psi0.stage1.preflight`) ngay sau khi dựng môi trường Ψ₀, trước mọi lần tải. Pre-flight build CPU Adam của DeepSpeed, rồi dựng `Accelerator`, `DummyOptim` và `DummyScheduler` như `scripts/train.py` và `PretrainTrainer` của Ψ₀, với file DeepSpeed và các giá trị của recipe. Sau đó nó `prepare` một model nhỏ hai nhóm tham số và chạy hai bước optimizer theo đúng thứ tự micro-step của `PretrainTrainer.training_step`, đọc `get_last_lr()[0]` sau mỗi micro-step như Ψ₀. Nó dừng `setup` nếu `prepare` lỗi, nếu một lần đọc lỗi, hoặc nếu lr của các nhóm khác với lr DeepSpeed 0.17.1 cho: sau `prepare`, nhóm đầu 0 và nhóm sau ở lr riêng; sau bước optimizer đầu, cả hai ở lr riêng. Kết quả ghi vào `report.json`, mục `preflight`. Một lỗi như lần chạy 1 vì thế tốn vài phút setup, không tốn thêm phần tải và nạp model. Thời gian của pre-flight chưa đo; build CPU Adam lần đầu có thể mất một đến hai phút.

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

**Lần 1, 4/11/2026: hỏng trước bước train đầu tiên.** Chạy từ `master` `52bbd45` trên một L4 (`gpu-l4-s-asso1c0-3nx0c41acx7rl`), một mình trên tài khoản, registry mới, guard chạy trước watcher (mục 1.6).

| Giai đoạn | Thời gian | Ghi chú |
|---|---|---|
| Nhận VM đến khi `pipeline.sh` chạy | khoảng 3 phút | Tạo `/content/da30`, upload mã (`git archive` của `52bbd45`) |
| `setup` (môi trường DA-19, `pre.*`) | 185 s | Môi trường 138 s, tải 47 s; Ψ₀ ở `cda3fdf` |
| `setup_stage1` (mẫu EgoDex, `actions_48d`) | 270 s | Tải 208 s, precompute 32 s; 218 episode, 111 task, 2,17 GB, `layout_problems` rỗng |
| `run` | 35 s | Nạp model xong, hỏng ở `accelerator.prepare` |
| Dừng VM | 16:22:54Z | Tải log về trước khi `colab stop`; Drive chưa mount nên `persist` chỉ ghi lên đĩa VM |

Lỗi: `ValueError: optimizer.params.betas not found in kwargs`. `zero3_offload.json` của tác giả có khối `optimizer` với `betas` và `eps` là `"auto"`, nên `PretrainTrainer.create_optimizer` tạo `DummyOptim`. `accelerate` 1.7.0 (bản ghim của Ψ₀) chỉ điền `lr` và `weight_decay` cho `DummyOptim` (`Accelerator._prepare_deepspeed`), còn `betas` và `eps` để nguyên `"auto"` và dừng. Đây là rủi ro đầu tiên của mục 1.8. Script của tác giả dùng `zero3.json`, file này không có khối `optimizer`.

Không có bước train nào: không có loss, `metrics.jsonl`, s/bước hay VRAM đỉnh. Hai tiêu chí chốt trước chưa đánh giá được (`loss_decreased`: "0 train lines, need 40"). `result.json` ghi `policy_error` cho một lỗi cấu hình hạ tầng.

CU thực đo: **0,46 CU**, so với ước lượng 2,3 CU ([sổ chi phí](../g0/ledger/DA-30.csv), dòng `measured`). Số dư giảm từ 101,77 xuống 101,31. Thời gian tính tiền là 14,3 phút × 1,94 CU/giờ = 0,46 CU, khớp với số dư giảm. Watcher thoát mã 0 (`ended`, sau 3 lần poll không thấy phiên), guard thoát mã 0, tài khoản còn 0 phiên.

Phần cố định đo được ngắn hơn giả định của mục 1.9. Từ lúc nhận VM đến lúc nạp model xong mất khoảng 11 phút, giả định là khoảng 26 phút cho các bước tương ứng. Phần train vẫn chưa đo.

Log tải về nằm ở `fwdata/colab/da30-results/`, không commit: `report.json`, `pipeline.log`, `runs/*/train.log`, `launch.json`, `result.json`.

### 1.8 Rủi ro đã biết

- `zero3_offload.json` không được script nào của tác giả dùng ở `cda3fdf`; đường DeepSpeed với optimizer trong file cấu hình (`DummyOptim`, `DummyScheduler`) chưa chạy lần nào trong dự án. **Đã xảy ra ở lần 1, 4/11/2026** (mục 1.7). Nếu hỏng, phương án dự phòng là A100 40 GB với `zero3.json`, có thể hết VRAM (ước lượng ở mục 1.2); cần duyệt CU lại.
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

**Lần chạy 2 [Ước lượng, 4/11/2026].** Khoảng 2,0 CU, khoảng 62 phút ([sổ chi phí](../g0/ledger/DA-30.csv), dòng `job_da30_stage1_short_run2`). Phần cố định dùng số đo của lần chạy 1 (mục 1.7): chuẩn bị VM khoảng 3 phút, môi trường 3,1 phút, mẫu EgoDex 4,5 phút. Phần còn lại là giả định: pre-flight khoảng 2 phút, nạp model và khởi tạo ZeRO-3 offload khoảng 5 phút, 200 bước ở 9 s/bước khoảng 30 phút, checkpoint 4 phút, chạy lại 3 bước 7 phút, persist và tải về 3 phút. Với `--cap 3.5`, watcher dừng ở khoảng 3,27 CU (khoảng 101 phút) và chạy `persist` ở khoảng 2,95 CU (600 s trước mốc dừng, sớm hơn 90% trần). Trừ khoảng 32 phút cố định, còn khoảng 69 phút train, tức phiên tự dừng khi s/bước vượt khoảng 21 s. Quy tắc dừng tay ở 20 s/bước giữ nguyên.

## 2. Nhánh B của DA-34: stage 1 trên video đội tự quay (AC 2)

_Soạn 9/11/2026, chưa chạy._ Nhánh B của thí nghiệm khay ([tray.md](tray.md) mục 4) giống hệt nhánh C, chỉ khác VLM: trước stage 3, VLM của C được fine-tune stage 1 trên video egocentric đội tự quay (người cầm hộp đỏ đi giữa hai bàn). So B với C trả lời câu hỏi "video người + demo robot" có hơn "chỉ demo robot" không. Ở Ψ₀, dữ liệu egocentric chỉ vào stage 1 (48 chiều tay và video), không bao giờ vào stage 3.

Lần chạy này cũng là **lần đầu stage 1 chạy hết đường đi** trong dự án: lần 1 của mục 1 hỏng trước bước train đầu (mục 1.7), lần 2 chưa chạy.

### 2.1 Quyết định

**[Đã chốt 9/11/2026, Hiếu]** "Chốt 4 mặc định":

1. VLM cha là VLM của nhánh C: `psi0/pre.fast.1by1.2601091803.ckpt.ego200k.he30k/model.safetensors` ở revision và sha256 ghim trong [`he-tray-v2.yaml`](../../configs/runplans/tray/he-tray-v2.yaml), không phải `ego390k` của mục 1. Như vậy B khác C đúng một bước stage 1.
2. Mỗi clip là một mẫu, mang câu mô tả cả task (như một episode EgoDex).
3. Dữ liệu: 153 clip của đội (480p, hộp đỏ, hai bàn đặt lưng nhau), 30 fps, mặt đã làm mờ bằng `fw egocentric deid`; `data_class` `public` theo PR #170 (chờ merge). Bỏ 8 clip 1080p vì thấy bảng tên.
4. Khoảng 300 bước train; trần cứng 4 CU (`compute.max_compute_units`), cùng bộ canh CU như mục 1.6.

### 2.2 Dữ liệu: bản export ghim bằng `export_id` và tarball

RunPlan của B không tải mẫu EgoDex mà nhận bản export của DA-18 (`flywheel.data.export.egodex.export_stage1`): `part1/<task>/<i>.hdf5` và `.mp4`, `egodex_stat.json`, `meta.json` có `export_id` và sha256 của từng file. Khối `dataset` có `kind: export` ([`runplan.py`](../../packages/flywheel-psi0/src/flywheel_psi0/stage1/runplan.py), `ExportDataset`):

- Ghim bằng `export_id` (định danh theo nội dung, do export tính từ sha256 các file) và sha256 của **một tarball** do `python -m flywheel_psi0.stage1.export_source pack` ghi. Tarball chỉ phụ thuộc nội dung file (thứ tự cố định, mtime 0, không chủ sở hữu), nên cùng một export luôn cho cùng sha256.
- Tarball nằm trên Google Drive, dưới `/content/drive/MyDrive/<source.tarball>`. Vì vậy với B, **Drive phải mount trước `setup`**, không phải sau như mục 1.6.
- `setup` chép tarball sang đĩa VM, từ chối nếu sha256 khác plan, giải nén chỉ file thường và thư mục (bộ lọc `data` của `tarfile`), rồi từ chối bản export nếu một trong các điều sau sai ([`export_source.py`](../../packages/flywheel-psi0/src/flywheel_psi0/stage1/export_source.py)): `export_id` trong `meta.json` đúng plan và đúng giá trị mà danh sách file băm ra; mỗi file khớp sha256 trong `meta.json`; không có file nào ngoài danh sách (loader của Ψ₀ sẽ train cả file thừa); `data_class` khớp plan; nguồn không có miễn trừ che danh tính; số mẫu khớp plan; `layout_problems` rỗng.
- Giải nén vào `data/egodex.unverified` và chỉ đổi tên thành `data/egodex` khi mọi kiểm tra trên đều đạt; bản bị từ chối bị xóa, nên không bao giờ nằm ở chỗ loader đọc (review PR #171).
- Trước khi cài hay tải bất cứ gì (chưa tốn thời gian GPU), `setup` dừng nếu: plan là bản nháp hoặc còn giá trị giữ chỗ; `data_class` không phải `public` (CLAUDE.md: dữ liệu `internal` và `restricted` không bao giờ lên dịch vụ hosted, kể cả Colab), áp cho cả hai loại dataset; tarball không có trên Drive ở đường dẫn của plan, hoặc khác cỡ `bytes` đã ghim. sha256 kiểm trên bản chép sang VM.
- Bản export đã có `actions_48d` (DA-18 ghi), nên không chạy script `precompute` của tác giả.
- Che danh tính: nguồn `export` chỉ nạp được khi `identity_masked: true`. Miễn trừ ngày 4/11/2026 chỉ áp cho zip EgoDex của Apple (mục 1.4), không áp cho bản export, kể cả export của EgoDex. Test: `test_an_export_must_be_identity_masked`.
- `setup` giờ cũng kiểm sha256 của trọng số cha sau khi tải, cho mọi plan.

Bản export thật chưa có: phiên điều phối dữ liệu sẽ đưa đường dẫn và sha256. Đến lúc đó RunPlan [`tray-ego-b.yaml`](../../configs/runplans/stage1/tray-ego-b.yaml) chưa đóng băng được (mục 2.4).

### 2.3 Checkpoint stage 1 có nạp được vào stage 3 không (Q-28C)

Câu hỏi Q-28C của [design 28/10/2026](../superpowers/specs/2026-10-28-tray-transfer-he-design.md): mã Ψ₀ có cho ghép VLM đã fine-tune stage 1 với action header `postpre.*` gốc không. **Trả lời: có, nhưng thư mục checkpoint của stage 1 phải được đóng gói lại trước.** Dẫn chứng ở `cda3fdf`:

| Điểm | Mã Ψ₀ | Hệ quả |
|---|---|---|
| Stage 1 lưu gì | `trainers/pretrain.py:441-447`: `accelerator.save_model(self.model, ckpt_dir)`, rồi `trainer.py:428-463` gọi `accelerator.save_state(ckpt_dir)` | Thư mục `ckpt_<bước>` có `model.safetensors` (chỉ trọng số Qwen3-VL) và trạng thái DeepSpeed (`pytorch_model/`, optimizer khoảng 25 GB). Không có `config.json`, không có file tokenizer hay processor |
| Trọng số có gom đủ không | `zero3_offload.json` của repo đặt `gather_16bit_weights_on_model_save: true`; `accelerate` 1.7.0 `accelerator.py:3604` đọc cờ này từ engine và chỉ điền khóa này khi là `"auto"` (`utils/dataclasses.py:1275-1290`) | ZeRO-3 gom trọng số bf16 vào một file. `zero3.json` của tác giả cũng bật cờ này, và file `model.safetensors` của các checkpoint `pre.*` công bố có đúng dạng đó (625 tensor, `model.language_model.embed_tokens.weight` 153792 × 2048, không có `lm_head`, metadata `{"format": "pt"}`) |
| Stage 3 đọc VLM thế nào | `trainers/finetune.py:266-288`: `Qwen3VLForConditionalGeneration.from_pretrained(model_name_or_path)` và `AutoProcessor.from_pretrained(model_name_or_path)` | Cần một thư mục có cả trọng số, `config.json` và file processor |
| `vlm_ckpt_step` | Chỉ khai báo ở `config/model_psi0.py:119`; không chỗ nào trong `src/` hay `scripts/` đọc nó | Không dùng được để trỏ vào bước checkpoint; chỉ dùng `model_name_or_path` |
| Action header | `trainers/finetune.py:333-337`: nạp `{pretrained_action_header_path}/action_header.safetensors`, độc lập với VLM | Ghép VLM mới với `postpre.1by1.pad36.2601131206.ckpt.he30k` gốc được, như nhánh C |
| Kích thước vocab | `pretrain.py:63-72` đổi cỡ embedding về `len(tokenizer) + 2048`, làm tròn lên bội của 192. `config.json` của cha đã là 153792 = 151669 + 2048 làm tròn | Trên cha đã đổi cỡ, bước này không đổi gì; `config.json` của cha đúng cho checkpoint mới |
| VLM trong stage 3 | `configs/models/psi0-stage3.yaml`: `model.no-tune-vlm: true` | VLM của B giữ nguyên trong stage 3; chỉ action header học tiếp |

Cách làm ([`vlm_checkpoint.py`](../../packages/flywheel-psi0/src/flywheel_psi0/stage1/vlm_checkpoint.py)): khi RunPlan đặt `persist_vlm: true`, `persist` chép `model.safetensors` của checkpoint cuối, cùng mọi file khác của thư mục cha (`config.json`, `generation_config.json`, tokenizer, processor), vào `<Drive>/denso/da30/<job_id>/vlm/`. Thư mục `vlm/` chỉ chứa đúng các file của thư mục cha, cùng tên và giống từng byte, trừ `model.safetensors`: `colab_train --branch B` của DA-34 từ chối mọi file khác (PR #172, [tray.md](tray.md) mục 18.8 trên nhánh đó). Vì vậy bản ghi `vlm.json` nằm **cạnh** thư mục (`<Drive>/denso/da30/<job_id>/vlm.json`), không nằm trong nó. Bản ghi có sha256 từng file, bước, `run_plan_id`, cha, `drive_dir`, cùng hai giá trị mà plan stage 3 của B ghim: `weights_sha256` và `manifest_sha256`. `manifest_sha256` tính đúng như `tray.colab_train.manifest_sha256` của DA-34; đã so hai hàm trên thư mục của lần thử CPU dưới đây và chúng khớp. `package` cũng so header safetensors với file của cha (cùng tên, cỡ, kiểu tensor), và ghi là vấn đề mọi file lạ trong thư mục. Log và `metrics.jsonl` được chép trước trọng số, nên còn lại nếu phiên dừng giữa lúc chép. Sau đó pha `check-vlm`, trong môi trường Ψ₀, nạp bản trên Drive đúng như stage 3 (`from_pretrained` và `AutoProcessor`) và dừng nếu: sha256 của trọng số hoặc của cả thư mục khác `vlm.json`, transformers báo thiếu hay thừa khóa, embedding nạp vào khác giá trị trong file (tức bị khởi tạo lại), `lm_head` không buộc vào embedding, hoặc 2048 token FAST không vừa vocab. Nhánh B của stage 3 đặt `model_name_or_path` vào thư mục `vlm/` này (sau khi kiểm sha256), giữ `pretrained_action_header_path` của C.

**Thử trên CPU, 9/11/2026** (môi trường Ψ₀ của laptop: transformers 4.57.1, accelerate 1.7.0, `DS_ACCELERATOR=cpu`). Một Qwen3-VL nhỏ dựng từ `config.json` của cha (2 lớp, vocab 153792 như cha), đổi cỡ embedding như `pretrain.py`, lưu bằng `Accelerator.save_model` như `pretrain.py:446`, file tokenizer và processor tải từ thư mục cha trên Hugging Face:

| Bước | Kết quả |
|---|---|
| `save_model` ghi gì | chỉ `model.safetensors`; tên tensor cùng dạng file của cha (`model.language_model.*`, `model.visual.*`, không `lm_head`) |
| `from_pretrained` trên thư mục checkpoint như đã lưu | lỗi (không có `config.json`) |
| `package`, rồi `load_check` | không vấn đề nào: vocab 153792, tokenizer 151669, không thiếu hay thừa khóa, `lm_head` buộc vào embedding |
| Mọi tensor nạp lại so với model đã lưu | bằng nhau |

Phần chưa thử: bước gom ZeRO-3 trên GPU (dựa vào cờ ở trên và dạng file của cha) và nạp model thật 2,1 tỉ tham số. `check-vlm` trên Colab làm phần đó, ngay sau lần chạy.

Một điều cần ghi cạnh kết quả của B: action header `postpre.*` được train (stage 2 của tác giả) trên đặc trưng của VLM cha. Sau 300 bước stage 1, đặc trưng của VLM lệch đi một chút, và stage 3 khởi đầu header từ chỗ lệch đó; stage 3 train header đủ lâu để thích nghi, nhưng đây là khác biệt thứ hai giữa B và C ngoài "VLM đã thấy video". Chạy lại stage 2 thì loại được khác biệt này, nhưng không nằm trong kế hoạch.

### 2.4 RunPlan `tray-ego-b.yaml`

[`tray-ego-b.yaml`](../../configs/runplans/stage1/tray-ego-b.yaml), `run_plan_id` hiện tại `rp_6a66a6ff082c` (bản nháp: id sẽ đổi khi ghim bản export thật). `runplan check` qua và in "draft" kèm lý do.

**Bản nháp cho tới khi có bản export.** Khối `dataset.source` giữ giá trị giữ chỗ (`egx_0000000000000000`, sha256 toàn số 0) và plan có `status: draft`. `colab setup` từ chối plan nháp trước khi làm bất cứ gì (không tốn CU). `runplan check` báo lỗi nếu giá trị giữ chỗ còn mà plan không ghi `draft`, hoặc ngược lại. `status` nằm ngoài `run_plan_id` (như plan của DA-34), nên bỏ nó đi không đổi id. Để đóng băng: chạy `pack` trên bản export, chép `export_id`, `sha256`, `bytes` và đường dẫn tarball trên Drive vào plan, bỏ `status: draft`, chạy lại `runplan check`.

| Khối | Giá trị | Lý do |
|---|---|---|
| `recipe` | [`psi0-stage1-egodex.yaml`](../../configs/runplans/stage1/psi0-stage1-egodex.yaml), không đổi `args` | Bản export có bố cục EgoDex. Cha được train bằng `pretrain-mix-psi0-fast.sh` (HE và EgoDex 1:1, từ `ckpt200k`), với cùng tokenizer FAST `egodex-rel-50w-1x48-v2048-s100`, cùng `egodex_stat_all.json` và ảnh EgoDex 270×480 như script EgoDex. Recipe thêm cha `psi0-pre-egodex-he` vào `parents` |
| `parent` | `pre.fast.1by1.2601091803.ckpt.ego200k.he30k`, sha256 `6e63…d3f9` | VLM của C (quyết định 1). Test so với `he-tray-v2.yaml`; `setup` kiểm sha256 sau khi tải |
| `train.max_training_steps` | 300 | Quyết định 4. 300 bước × 32 mẫu là khoảng 63 lượt qua 153 clip (mỗi lượt một khung ngẫu nhiên mỗi clip). Loss sẽ giảm một phần do học thuộc; B được đánh giá bằng closed-loop của stage 3 so với C (DA-34), không bằng loss này |
| `train.checkpointing_steps` | 300 | Một checkpoint ở cuối (Ψ₀ luôn lưu ở bước cuối: `scripts/train.py:304-310` gọi `should_save_training_checkpoint`, `trainer.py:30-41`). Checkpoint giữa tốn một lần lưu DeepSpeed khoảng 30 GB và vô dụng: phiên đã dừng không chạy tiếp |
| `train.validation_steps` | 0 | Bản export không có split `test/`; val dạng sinh token của Ψ₀ nói ít trong 300 bước. Quên (P4) và hiểu cảnh (P1) là probe của DA-09, dời sau demo |
| `deepspeed_config` | `zero3_offload.json` của mục 1.2 | Một L4; `runplan check` so với recipe; pre-flight của `setup` thử trên model nhỏ. File này bật gom trọng số 16 bit khi lưu, điều kiện của mục 2.3 |
| `persist_vlm` | `true` | Giữ VLM cho stage 3 của B (mục 2.3) |
| `compute.max_compute_units` | 4,0 | Quyết định 4 |

**Stats chuẩn hóa [Đề xuất, 9/11/2026]: dùng file của tác giả `egodex_stat_all.json`, không dùng `egodex_stat.json` của bản export.** Lý do:

- Cha học token action FAST trên action đã chuẩn hóa bằng file của tác giả: cả script EgoDex lẫn script trộn tạo ra cha đều truyền `--data.transform.field.stat-path=assets/stats/egodex_stat_all.json` với khóa `egodex`, và tokenizer FAST được fit trên action ở thang đó. Chuẩn hóa bằng stats khác thì cùng một chuyển động tay cho ra chuỗi token khác, tức là đổi nghĩa của token mà cha đã học, và B sẽ khác C ở hai chỗ thay vì một.
- Stats của 153 clip tư thế giả (MediaPipe) có q01 và q99 nhiễu hơn nhiều so với stats của EgoDex.
- Docstring của export cũng ghi lần chạy của tác giả chuẩn hóa bằng file của họ; file của export dùng để so sánh.

Giá phải trả: Ψ₀ cắt action đã chuẩn hóa về [−1, 1] (`config/transform.py:682`), nên phần đuôi của những chiều mà video của đội vượt khoảng q01–q99 của EgoDex bị cắt. `setup` đo việc này và ghi vào `report.json`, mục `setup_stage1.stats_coverage`: các chiều có q01 hoặc q99 của export nằm ngoài khoảng của tác giả, và tỉ lệ độ rộng khoảng (trung vị, lớn nhất). Chỉ ghi lại, không chặn. Số này đọc được ngay khi có bản export, trước khi tốn GPU (`export_source.stats_coverage` trên CPU). Đo trên bản export thử: phần bị cắt rất lớn (mục 2.7).

**Tiêu chí chốt trước** (như mục 1.6, chỉ khác độ dài):

- **Loss giảm**: trung vị loss train của 30 bước cuối thấp hơn trung vị của 30 bước đầu. Ψ₀ ghi một dòng mỗi bước optimizer (`scripts/train.py:298-301`), nên 30 là một phần mười lần chạy ở mỗi đầu.
- **Chạy lại**: chạy lại 3 bước đầu dưới `da30-tray-ego-b-repeat`, cùng seed 7; loss bước đầu lệch không quá 2%.
- **Nạp được ở stage 3**: `check-vlm` không báo vấn đề nào (mục 2.3).

Ba tiêu chí này là bằng chứng đường đi. Chúng không nói gì về việc video của đội có giúp hay không: câu hỏi đó trả lời bằng closed-loop của stage 3 (B so với C), theo quy tắc của DA-34 ([tray.md](tray.md) mục 4).

### 2.5 Ước lượng CU

Giả định, chưa đo; dòng `job_da30_stage1_tray_ego_b` của [sổ chi phí](../g0/ledger/DA-30.csv). Một VM L4 ở 1,94 CU/giờ (S1-04). Phần cố định dùng số đo của lần 1 (mục 1.7): từ lúc nhận VM đến lúc nạp model xong khoảng 11 phút; bản export chép từ Drive thay cho phần tải EgoDex, giả định không lâu hơn. Phần còn lại là giả định: pre-flight khoảng 2 phút, khởi tạo ZeRO-3 offload khoảng 2 phút, checkpoint cuối 4 phút, chạy lại 3 bước 7 phút, `persist` kèm VLM 4,3 GB lên Drive 4 phút, `check-vlm` 3 phút. Cộng khoảng 33 phút cố định với 300 bước train:

| s/bước | Train | Tổng | CU |
|---|---|---|---|
| 5 | 25 phút | 58 phút | 1,9 |
| 9 (giả định chính) | 45 phút | 78 phút | 2,5 |
| 14 | 70 phút | 103 phút | 3,3 |
| 17 | 85 phút | 118 phút | 3,8 (bộ canh dừng ở khoảng 3,77) |

Với `--cap 4`, bộ canh dừng phiên ở khoảng 3,77 CU (biên 430 s, khoảng 117 phút) và chạy `persist` sớm hơn 600 s (khoảng 107 phút). Nếu lúc đó run chưa tới checkpoint cuối, `persist` chỉ giữ được log, không có VLM.

**Quy tắc dừng [Đề xuất]:** đọc s/bước trong `train.log` sau 20 bước; quá 14 s thì dừng VM và báo Hiếu (ở 14 s/bước, run xong khoảng 3,3 CU, còn chỗ cho `persist`). Thứ tự chạy cũng đổi so với mục 1.6 để trọng số lên Drive sớm nhất: `run`, `persist`, `check-vlm`, rồi mới `repeat` và `persist` lần nữa (lần thứ hai không chép lại trọng số đã có).

### 2.6 Việc Hiếu làm để chạy

Chưa chạy. Điều kiện trước:

1. PR này merge vào `master`; chạy từ `master`, không từ nhánh.
2. PR #170 (`data_class` `public` cho video của đội) đã merge.
3. Phiên điều phối dữ liệu giao bản export: chạy `python -m flywheel_psi0.stage1.export_source pack --export <root> --out <export_id>.tar`, đưa tarball lên `MyDrive/denso/da30/exports/`, gửi `export_id`, `sha256`, `bytes`. Một PR nhỏ ghim ba số đó vào `tray-ego-b.yaml`, bỏ `status: draft`; `runplan check` in `OK rp_…` không còn chữ "draft".
4. Đọc `stats_coverage` của bản export trên CPU trước khi tốn GPU (mục 2.4).
5. `colab sessions` trống: một đợt một lúc trên tài khoản (mục 1.6).

Bộ canh CU như mục 1.6, đổi tên phiên và trần:

```bash
export PATH=~/project/wm-wam-review/.venv-colab-cli/bin:$PATH
R=fwdata/colab/da30b-$(date +%Y%m%d-%H%M%S); mkdir -p fwdata/colab && mkdir $R
nohup setsid bash -c 'trap "" TERM HUP INT; python3 scripts/colab/cu_watch.py guard --registry "$0" --floor 14 --log "$0/guard.jsonl"; echo "exit $?"' $R < /dev/null > $R/guard.out 2>&1 &
nohup setsid bash -c 'trap "" TERM HUP INT; python3 scripts/colab/cu_watch.py session --registry "$0" --new --name da30-stage1-b --gpu L4 --cap 4 --floor 14 --persist "colab exec -s da30-stage1-b -f configs/runplans/stage1/persist_cell.py" --log "$0/da30-stage1-b.jsonl"; echo "exit $?"' $R < /dev/null > $R/da30-stage1-b.out 2>&1 &
( until [ -f $R/da30-stage1-b.ready ]; do grep -q '^exit ' $R/da30-stage1-b.out && exit 1; sleep 5; done
  [ -f $R/guard.beat ] && [ $(( $(date +%s) - $(stat -c %Y $R/guard.beat) )) -lt 120 ] ) && echo READY || echo "NOT READY: do not start the job"
```

Sau `READY`: đưa mã ở commit `master` vào `/content/da30/fw` như lần 1, rồi **mount Drive trước `setup`** (tarball nằm trên Drive):

```bash
colab drivemount -s da30-stage1-b /content/drive
```

Trên VM, từ `/content/da30` (lệnh train chạy trong shell SSH, không qua `colab exec`, để kernel rảnh cho `persist` của bộ canh):

```bash
python3 -m flywheel_psi0.stage1.colab setup --work /content/da30 --plan fw/configs/runplans/stage1/tray-ego-b.yaml
```

```bash
Psi0/.venv-psi/bin/python -m flywheel_psi0.stage1.colab run --work /content/da30 --plan fw/configs/runplans/stage1/tray-ego-b.yaml
```

```bash
python3 -m flywheel_psi0.stage1.colab persist --work /content/da30 --plan fw/configs/runplans/stage1/tray-ego-b.yaml
```

```bash
Psi0/.venv-psi/bin/python -m flywheel_psi0.stage1.colab check-vlm --work /content/da30 --plan fw/configs/runplans/stage1/tray-ego-b.yaml
```

```bash
Psi0/.venv-psi/bin/python -m flywheel_psi0.stage1.colab repeat --work /content/da30 --plan fw/configs/runplans/stage1/tray-ego-b.yaml
```

```bash
python3 -m flywheel_psi0.stage1.colab persist --work /content/da30 --plan fw/configs/runplans/stage1/tray-ego-b.yaml
```

Sau lần chạy: tải `report.json` và log về `fwdata/colab/`, ghi dòng `measured` của sổ chi phí (`balance_drop` ở dòng `exit` của `da30-stage1-b.jsonl`), ghi kết quả vào mục 2.9. VLM nằm ở `MyDrive/denso/da30/da30-tray-ego-b/vlm/`, bản ghi ở `…/da30-tray-ego-b/vlm.json`. Bốn giá trị cần ghim vào `he-tray-b.yaml` của DA-34 (`parents.psi0-b-ego-stage1.vlm_stage1`) có sẵn trong mục `persist.vlm` của `report.json`: `job_id` `da30-tray-ego-b`, `drive_dir`, `weights_sha256`, `manifest_sha256`.

### 2.7 Loader check trên bản export thử (9/11/2026)

Bản export **thử**, không để ghim: `egx_fb3d1401dac0bd4c`, 47 MB, 132 mẫu (`part1/two_table/<i>.hdf5` và `.mp4`), 7804 khung ở 30 fps, mỗi clip 30–99 khung (trung vị 59,5), một câu mô tả cho mọi mẫu, không có `test/`, `data_class` `public`, không miễn trừ che danh tính. Phiên điều phối giao bản này để thử loader; bản thật sẽ có `export_id` mới. `export_source verify` qua.

Cách chạy như mục 1.5: image `psi0@sha256:0d58…80b2` trên `rtx3060`, `PYTHONPATH` trỏ vào bản clone ở `cda3fdf` (mã trong image khác commit ghim nên không dùng), chỉ CPU, container 8 CPU, 10 GB RAM, `--shm-size 4g`, 4 worker. Argv là argv của `tray-ego-b.yaml` (bản nháp), chỉ đổi đường dẫn dữ liệu và VLM cha sang chỗ mount; chỉ nạp processor của cha `ego200k.he30k`, không nạp trọng số. Để so sánh, chạy cùng argv trên 218 episode EgoDex của mục 1.4.

| Mục | Bản export thử | EgoDex (218 episode) |
|---|---|---|
| Mẫu train, test | 132, 0 | 218, 0 |
| Một epoch (`drop_last`) | 8 batch × 16 = 128 | 13 batch × 16 = 208 |
| `input_ids` | 16 × 191–195 | như mục 1.5 |
| Ảnh | lưới 1 × 16 × 30 (270×480), `pixel_values` 7680 × 1536 | như mục 1.5 |
| Action thô | 1 × 48 | 1 × 48 |
| Token action FAST mỗi mẫu | 1–44 | 1–43 |
| NaN, `problems` | không có, rỗng | không có, rỗng |
| Hàm gốc ở `cda3fdf` | vẫn `UnboundLocalError`; bản vá còn cần | như trên |
| Thời gian | batch đầu 1,5–1,7 s (4 worker khởi động), sau đó 0,01–0,5 s mỗi batch | |
| **Giá trị action bị cắt ở ±1** | **41,6 %** | **2,2 %** |
| **Mẫu có ít nhất một chiều bị cắt** | **89,8 %** | 21,2 % |
| Mẫu chỉ có 1 token | 9 / 128 (7,0 %) | 2 / 208 (1,0 %) |

Hai dòng cuối là mục mới của `loader_check` (`actions` trong báo cáo, test `test_psi0_stage1_loader_check.py`), để kiểm bản export thật bằng đúng lệnh này. Một lần chạy riêng 5 epoch (640 mẫu) cho cùng kết quả: 41 % giá trị và 90 % mẫu bị cắt, 7,8 % mẫu một token.

**Kết quả 1: action của bản thử phần lớn nằm ngoài stats của EgoDex.** Đường đi chạy được, nhưng 41,6 % giá trị action sau chuẩn hóa bằng `egodex_stat_all.json` nằm ở biên ±1, gấp 19 lần EgoDex. Với dữ liệu khớp stats, mỗi chiều có khoảng 2 % giá trị ngoài q01–q99, đúng như số đo trên EgoDex. Trên CPU, ngoài Ψ₀:

- `stats_coverage`: cả 42 chiều không phải pad có q01 hoặc q99 của export ngoài khoảng của tác giả; tỉ lệ độ rộng khoảng trung vị 11,9, lớn nhất 26,0.
- Delta tính như loader (khung i và i+3, trong hệ camera của khung i; 7408 delta): cổ tay trái theo x có trung vị |d| 0,030 m, gần bằng q99 của tác giả (0,030), nhưng p90 là 0,22 m mỗi 0,1 s. Góc roll cổ tay trái có p90 là 2,22 rad (q99 của tác giả 0,21); có delta gần ±π.
- Thang đo không sai: cổ tay cách camera trung vị 0,54 m. Phần lớn delta có cỡ hợp lý; phần đuôi rất lớn. Đó là dạng của nhiễu tư thế (tư thế tay ước lượng nhảy giữa các khung, góc lật qua ±π), không phải của chuyển động thật.
- Quỹ đạo camera không phải số đo: bước tịnh tiến mỗi khung chỉ có hai giá trị, 0 hoặc 0,005 (70 % số khung là 0,005). Quay của camera trung vị 2,2° mỗi khung, p90 19,6°, có bước gần 180°. Tư thế tay được đưa sang hệ thế giới bằng quỹ đạo này, nên chuyển động của nó đi vào mọi delta; mục 2.8 cho thấy phần quay là nguồn chính của phần bị cắt. (Bản đầu của mục này ghi bước tịnh tiến luôn là 0,005; sửa ngày 9/11/2026.)

**Kết quả 2: mẫu một token là delta bằng 0, do clip ngắn.** Cả 9 mẫu một token có cùng một hàng action, đúng bằng giá trị 0 sau chuẩn hóa (token `<|a_378|>`). Loader bốc khung `index` trong [0, T−2] và cần khung `index + 3`; khi `index` rơi vào ba khung cuối không có khung đó, nó lặp lại `index` (`egodex_dataset.py:470-506` ở `cda3fdf`), nên delta bằng 0. Tỉ lệ kỳ vọng là 3/(T−1) trung bình trên các clip, tức 5,6 % với độ dài của bản thử (EgoDex: clip dài hàng trăm khung, dưới 1 %); đo được 6,6–7,8 %.

**Kết quả 3: loader ghi file vào thư mục export.** Lần đọc đầu, `EgoDexDataset._load_file_list` ghi `part1/filelist_cache.pkl` (`egodex_dataset.py:249-282`); mount chỉ đọc thì dừng với `OSError`. Trên Colab thư mục export ghi được nên không sao. File này không có trong `meta.json`: `verify_export` chỉ chạy trong `setup` trước khi train, và `pack` từ chối thư mục đã bị loader đọc, nên phải đóng tarball từ bản export gốc.

**Đề xuất cho plan [Đề xuất, 9/11/2026], chờ Hiếu duyệt:**

| Câu hỏi | Đề xuất | Lý do |
|---|---|---|
| Stats | Giữ `egodex_stat_all.json` (mục 2.4) | Đổi sang stats của export sẽ giảm phần bị cắt nhưng đổi nghĩa token mà cha đã học. Với đuôi nhiễu thế này, q01–q99 của export phần lớn là nhiễu, nên khoảng chuẩn hóa sẽ rộng gấp khoảng 12 lần và chuyển động thật bị nén vào vài bin |
| Phần bị cắt | **Không ghim bản export khi `actions.clipped_value_share` của `loader_check` trên 5 %** (EgoDex 2,2 %). Sửa ở pipeline egocentric trước bản export thật: làm mượt tư thế cổ tay theo thời gian, nối góc để không lật qua ±π, bỏ hoặc nội suy khung có bước nhảy lớn; ghi rõ quỹ đạo camera là đo hay đặt | Với 90 % mẫu bị cắt, token FAST chủ yếu mã hóa biên ±1; 300 bước sẽ dạy cha một phân bố action méo. B khi đó khác C vì nhiễu, không vì video của đội, và closed-loop của DA-34 không tách được hai thứ này. Ngưỡng 5 % là đề xuất; Hiếu chọn |
| Không có `test/` | Không đổi | `validation_steps` đã là 0; loader đọc 0 file test và `create_dataloaders` chạy được |
| `upsample_rate` 3 với clip ngắn | Giữ 3 | 3 khung ở 30 fps là 0,1 s, thang thời gian mà token của cha đã học. Giá là khoảng 6 % mẫu có đích bằng 0, phần lớn ở cuối clip, khi tay đã đặt khay xuống và gần như đứng yên |
| Số mẫu | Plan ghi `samples` theo kết quả `pack` của bản thật | Bản thử có 132 mẫu, không phải 153 (export bỏ 21 clip); `setup` từ chối khi số mẫu lệch plan. 300 bước × 32 mẫu là khoảng 73 lượt mỗi clip ở 132 clip |

Plan giữ `status: draft`. Không chạy Colab.

### 2.8 Làm sạch tư thế có đưa phần bị cắt xuống dưới 5 % không [Đề xuất, 9/11/2026]

Đo trên CPU, ngoài repo, trên cùng bản export thử (132 clip, 7804 khung). Không sửa bản export hay pipeline; thay đổi pipeline sẽ đi vào một PR của DA-04.

**Cách đo.** Script đọc `transforms/` của 132 file HDF5, dựng lại `actions_48d` như script `precompute` của tác giả (trùng khớp tuyệt đối với `actions_48d` đã lưu), rồi tính delta đúng như loader ở `cda3fdf`. Mọi `index` trong [0, T−2] đều được lấy. Khung i và i+3 (hoặc i và i ở ba khung cuối) đều nằm trong hệ camera của khung i. Delta gồm vị trí, roll/pitch/yaw kiểu `xyz` của `R2 @ R1.T`, và đầu ngón. Sau đó chuẩn hóa bằng `egodex_stat_all.json`, cắt về [−1, 1], và cho mỗi clip trọng số bằng nhau như loader. Bản xuất như hiện có cho 42,7 % giá trị bị cắt; `loader_check` đo 41,6 % (mục 2.7). Bản dựng lại khớp với loader.

Các bước làm sạch, áp cho từng tay:

- **Liên tục của góc:** nếu xoay khung cổ tay π quanh một trục của nó làm khung gần khung trước hơn 30° trở lên, thì xoay.
- **Làm mượt:** Savitzky–Golay bậc 2 trên vị trí cổ tay, đầu ngón, và quaternion của cổ tay (đã giữ dấu liên tục, chuẩn hóa lại). Cửa sổ 9 khung (0,3 s) và 21 khung (0,7 s).
- **Khung nhảy:** khung có bước nhảy của cổ tay (tịnh tiến hoặc quay) lớn hơn trung vị + 5 × MAD của clip thì **nội suy** (tuyến tính cho vị trí, slerp cho quay), không bỏ. Loader đọc HDF5 và video theo cùng chỉ số khung, nên bỏ khung sẽ lệch ảnh với action.
- **Camera:** 4a giữ quay của camera đã làm mượt, đặt tịnh tiến bằng 0. 4a+ làm sạch quay của camera như cổ tay. 4b dùng camera đơn vị: tư thế giữ trong hệ camera, delta không bù chuyển động đầu.

Ngưỡng q01/q99 của tác giả: cổ tay trái x −0,029/0,030 m, roll trái −0,226/0,213 rad. Delta là cho 3 khung (0,1 s); trung vị và p90 tính trên các delta khác 0.

| Biến thể | Cửa sổ | Giá trị bị cắt | Mẫu có chiều bị cắt | \|Δ\| cổ tay trái x, trung vị / p90 (m) | \|Δ\| roll trái, trung vị / p90 (rad) | Khung tay nội suy (trên 15 608) |
|---|---|---|---|---|---|---|
| 0 Như xuất | | 42,7 % | 92,5 % | 0,027 / 0,215 | 0,287 / 2,12 | 0 |
| 1 Liên tục góc (sửa 5802 lần lật) | | 42,6 % | 92,5 % | 0,027 / 0,215 | 0,270 / 1,37 | 0 |
| 2 = 1 + làm mượt | 9 | 41,3 % | 90,9 % | 0,032 / 0,170 | 0,189 / 0,83 | 0 |
| 3 = 2 + khung nhảy | 9 | 40,7 % | 90,9 % | 0,032 / 0,164 | 0,188 / 0,79 | 1819 |
| 4a = 3, quay camera làm mượt, tịnh tiến 0 | 9 | 41,1 % | 91,1 % | 0,038 / 0,195 | 0,215 / 0,94 | 988 |
| 4a+ = 3, quay camera làm sạch như cổ tay | 9 | 39,2 % | 91,0 % | 0,037 / 0,175 | 0,204 / 0,77 | 748 |
| 4b = 3, camera đơn vị | 9 | 10,6 % | 80,0 % | 0,008 / 0,021 | 0,135 / 0,58 | 816 |
| 2 | 21 | 37,4 % | 87,5 % | 0,032 / 0,111 | 0,124 / 0,44 | 0 |
| 3 | 21 | 37,1 % | 87,7 % | 0,031 / 0,111 | 0,125 / 0,43 | 1819 |
| 4a | 21 | 36,8 % | 87,3 % | 0,039 / 0,152 | 0,142 / 0,50 | 679 |
| 4a+ | 21 | 31,9 % | 86,9 % | 0,035 / 0,132 | 0,131 / 0,42 | 663 |
| **4b** | **21** | **3,9 %** | **56,3 %** | **0,005 / 0,014** | **0,082 / 0,29** | **816** |

Đối chứng, chỉ đổi camera, không làm sạch tay: quay làm mượt và tịnh tiến 0 cho 45,9 %; camera đơn vị cho 18,6 %. 4b với cửa sổ 15 cho 6,0 %. Theo nhóm chiều, 4b cửa sổ 21: vị trí cổ tay 5,5 %, góc cổ tay 13,3 %, đầu ngón x/y 1,1 %, đầu ngón z 2,7 %.

**Làm mượt có xóa chuyển động thật không.** Đo cùng cách trên 73 episode EgoDex (một phần ba của mẫu 218 episode, 600 khung đầu mỗi episode, 23 646 khung). Camera của Vision Pro là số đo thật.

| EgoDex | Giá trị bị cắt | Mẫu có chiều bị cắt | p90 \|Δ\| cổ tay trái x | p90 \|Δ\| roll trái |
|---|---|---|---|---|
| Như có | 1,9 % | 19,5 % | 0,0099 m | 0,084 rad |
| Camera đơn vị | 1,8 % | 19,2 % | 0,0105 m | 0,084 rad |
| Làm mượt cửa sổ 21 | 1,0 % | 11,5 % | 0,0095 m | 0,071 rad |
| 4b cửa sổ 21 | 0,7 % | 9,9 % | 0,0098 m | 0,065 rad |

Cửa sổ 21 giữ gần hết chuyển động của EgoDex: p90 giảm 4 % ở vị trí và 15 % ở roll. Bỏ phần bù chuyển động đầu gần như không đổi phần bị cắt trên EgoDex.

**Kết luận.**

- **Nguồn chính là quỹ đạo quay của camera, không phải nhiễu của tay.** Mọi biến thể còn giữ quay của camera đều ở 32–46 %, kể cả khi quay đó đã được làm sạch như cổ tay. Bỏ camera (đơn vị) một mình đưa 42,7 % xuống 18,6 %. Quay trung vị 2,2° mỗi khung, tức khoảng 65°/s, không hợp với người bê khay; ở khoảng cách tay 0,54 m, 3 khung quay như thế dời tay khoảng 6 cm, gấp đôi q99 của tác giả.
- **Làm sạch tay chỉ có tác dụng khi bỏ camera.** Với camera đơn vị: lật góc, khung nhảy và làm mượt cửa sổ 9 đưa 18,6 % xuống 10,6 %; cửa sổ 21 xuống 3,9 %.
- **Khung cổ tay lật rất thường xuyên:** 22 % số bước khung trong hệ camera (37 % trong hệ thế giới) cần xoay π mới liên tục. Đó là dấu hiệu cách dựng trục cổ tay từ landmark có chỗ mơ hồ về dấu; nên sửa ở chỗ dựng, không chỉ vá sau.

**Đề xuất cho PR của DA-04 [Đề xuất]:**

1. Ghi tư thế trong hệ camera (`transforms/camera` là ma trận đơn vị) cho tới khi có quỹ đạo đầu đo được và đã kiểm. Trên EgoDex, bỏ phần bù chuyển động đầu gần như không đổi gì.
2. Dựng trục cổ tay có dấu xác định. Thêm bước giữ liên tục (xoay π khi gần khung trước hơn 30°) làm lưới an toàn.
3. Nội suy khung có bước nhảy của cổ tay lớn hơn trung vị + 5 × MAD của clip; không bỏ khung.
4. Savitzky–Golay bậc 2, cửa sổ 21 khung ở 30 fps, trên vị trí cổ tay, đầu ngón và quaternion cổ tay.
5. Kiểm lại bằng `loader_check` trên bản export thật trước khi ghim, với ngưỡng 5 % của mục 2.7.

Còn lại sau đề xuất: 3,9 % là trên bản thử, không phải bản thật. Góc cổ tay vẫn bị cắt 13 %, và 56 % mẫu có ít nhất một chiều bị cắt (EgoDex 19,5 %). Bản export qua ngưỡng nhưng vẫn nhiễu hơn EgoDex. Cửa sổ 21 có thể làm mờ những lúc tay đổi hướng nhanh (cầm và đặt khay); phần bị cắt không nói gì về chất lượng policy, closed-loop của B so với C mới trả lời.
