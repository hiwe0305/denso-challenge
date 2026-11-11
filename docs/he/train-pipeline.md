# Hướng dẫn train toàn pipeline: egocentric → stage 1 → stage 3 → eval

_10/11/2026. Viết cho Hiếu tự chạy nhánh B của [DA-34](../product/stories/DA-34-thi-nghiem-egocentric-khay.md) (VLM Ψ₀ qua stage 1 trên video egocentric của đội, rồi stage 3 như nhánh C). File này gom các runbook đã có thành một đường chạy từ đầu đến cuối. Lệnh gốc và lý do của từng chặn nằm ở các mục được dẫn; khi hai nơi khác nhau, runbook gốc thắng. Số thời gian và CU là ước lượng, trừ chỗ ghi "đo"._

## 0. Code nằm ở đâu

| Bước | Code | Config | Runbook gốc |
|---|---|---|---|
| Dữ liệu egocentric: ingest, che mặt, pose, nhãn, QA, báo cáo | [`flywheel.data.ingest.egocentric`](../../packages/flywheel-data/src/flywheel/data/ingest/egocentric/), CLI [`egocentric_cli.py`](../../packages/flywheel-data/src/flywheel/data/egocentric_cli.py) (`fw egocentric …`); QA ở [`qa/egocentric.py`](../../packages/flywheel-data/src/flywheel/data/qa/egocentric.py) | [`configs/data/egocentric.yaml`](../../configs/data/egocentric.yaml) | [egocentric.md](../g0/egocentric.md) mục 1, 3.1, 6.1, 8 |
| Job pose E-A (MediaPipe) trên `rtx3060` | [`estimate_job.py`](../../packages/flywheel-data/src/flywheel/data/ingest/egocentric/estimate_job.py) | `pose_ea` trong `egocentric.yaml` | [egocentric.md](../g0/egocentric.md) mục 1.1, 10.4 |
| Export sang dạng EgoDex cho stage 1 | `flywheel.data.export.egodex` | — | [stage1.md](stage1.md) mục 2.2, 2.9 |
| Đóng gói, kiểm bản export | [`stage1/export_source.py`](../../packages/flywheel-psi0/src/flywheel_psi0/stage1/export_source.py) (`pack`, `verify`), [`stage1/loader_check.py`](../../packages/flywheel-psi0/src/flywheel_psi0/stage1/loader_check.py) | — | [stage1.md](stage1.md) mục 2.7, 2.9 |
| Stage 1 (VLM) trên Colab | [`stage1/colab.py`](../../packages/flywheel-psi0/src/flywheel_psi0/stage1/colab.py) (`setup`, `run`, `persist`, `check-vlm`, `repeat`), [`stage1/trainer.py`](../../packages/flywheel-psi0/src/flywheel_psi0/stage1/trainer.py), [`stage1/runplan.py`](../../packages/flywheel-psi0/src/flywheel_psi0/stage1/runplan.py) | [`configs/runplans/stage1/tray-ego-b.yaml`](../../configs/runplans/stage1/tray-ego-b.yaml), [`zero3_offload.json`](../../configs/runplans/stage1/zero3_offload.json), [`persist_cell.py`](../../configs/runplans/stage1/persist_cell.py) | [stage1.md](stage1.md) mục 2.6 |
| Bộ canh CU của Colab | [`scripts/colab/cu_watch.py`](../../scripts/colab/cu_watch.py) | — | [stage1.md](stage1.md) mục 1.6 |
| Bản cắt demo robot | [`scripts/he/demo_subset.py`](../../scripts/he/demo_subset.py), [`tray/demo_sets.py`](../../packages/flywheel-psi0/src/flywheel_psi0/tray/demo_sets.py) | [`demo_sets-v2.json`](../../configs/runplans/tray/demo_sets-v2.json) | [tray.md](tray.md) mục 11, 18.4 |
| RunPlan nhánh khay: kiểm, đóng băng | [`tray/runplan.py`](../../packages/flywheel-psi0/src/flywheel_psi0/tray/runplan.py) | [`he-tray-v2.yaml`](../../configs/runplans/tray/he-tray-v2.yaml) (C), [`he-tray-b.yaml`](../../configs/runplans/tray/he-tray-b.yaml) (B) | [tray.md](tray.md) mục 18.3 |
| Stage 3 (fine-tune Ψ₀) trên Colab | [`tray/colab_train.py`](../../packages/flywheel-psi0/src/flywheel_psi0/tray/colab_train.py) (`check`, `setup`, `train`, `manifest`), [`trainer/psi0_trainer.py`](../../packages/flywheel-psi0/src/flywheel_psi0/trainer/psi0_trainer.py), [`trainer/recipe.py`](../../packages/flywheel-psi0/src/flywheel_psi0/trainer/recipe.py) | `psi0-stage3.yaml` của plan | [tray.md](tray.md) mục 12, 17.6, 18.4 |
| Kéo checkpoint từ Colab về | [`scripts/he/he1_fetch.py`](../../scripts/he/he1_fetch.py) (`probe`, `once`, `follow`) | — | [tray.md](tray.md) mục 12, 17.6 |
| Eval trên `rtx3060` | [`tray/eval_batch.py`](../../packages/flywheel-psi0/src/flywheel_psi0/tray/eval_batch.py), [`tray/eval_driver.py`](../../packages/flywheel-psi0/src/flywheel_psi0/tray/eval_driver.py); server `serve-*.sh`, `launch-eval-*.sh` trong `~/denso-da34-t8/` (ngoài repo) | tập điều kiện `rp_a04c14e79dfd-2e57f60` | [tray.md](tray.md) mục 16.2, 17.6, 18.5 |
| Đọc kết quả | [`tray/eval_results.py`](../../packages/flywheel-psi0/src/flywheel_psi0/tray/eval_results.py) (`--baseline` cho so cặp) | luật đọc trong khối `branch-b-rules` | [tray.md](tray.md) mục 18.2, 18.5 |
| Sổ chi phí | `docs/g0/ledger/DA-30.csv` (stage 1), `docs/g0/ledger/DA-34.csv` (stage 3, eval) | — | [08](../product/08-daily-control.md) |

Ψ₀ là mã của tác giả ở commit `cda3fdf`. `setup` tự clone và dựng môi trường trên VM, nên không cần cài Ψ₀ trên laptop.

## 1. Sơ đồ và chi phí

```
video đội (laptop) ─► 30 fps ─► ingest ─► deid ─► pose E-A (rtx3060) ─► nhãn, review, QA ─► export ─► tarball ─► Drive
                                                                                                          │
VLM của C (psi-model) ─────────────────────────────────────────────► stage 1 (Colab L4, ~1,3 giờ, ~2,5 CU) ◄┘
                                                                                │ VLM lên Drive + 4 ghim
demo robot: release tray_s1_f9433b028c52, tập C 160 episode (rtx3060) ─► bản cắt ─► stage 3 (Colab L4, ~8,3 giờ, ~16 CU)
                                                                                │ checkpoint về laptop rồi rtx3060, kiểm sha256
                                                                    eval B (rtx3060, ~4 giờ giai đoạn 1; ~16,5 giờ nếu chạy đủ)
                                                                                │
                                                          eval_results --baseline eval C ─► Decision, sổ chi phí
```

| Bước | Máy | Thời gian | CU | Ai |
|---|---|---|---|---|
| 1. Dữ liệu egocentric | laptop + `rtx3060` | ~1–2 giờ cho 150 clip | 0 | Hiếu hoặc phiên DA-04 |
| 2. Stage 1 | Colab L4 | ~78 phút (giả định) | ~2,5 (trần 4) | Hiếu launch |
| 3. Ghim VLM vào plan B, đóng băng | laptop | vài phút + 1 PR | 0 | phiên DA-34 |
| 4. Stage 3 B | Colab L4 | ~8,3 giờ (C đo 8,27 giờ) | ~16 (cap 18) | Hiếu launch |
| 5. Eval B | `rtx3060` | ~4 giờ giai đoạn 1, ~16,5 giờ nếu chạy đủ 240 | 0 | Hiếu bảo chạy |
| 6. Đọc, ghi `Decision` | laptop | < 1 giờ | 0 | phiên DA-34, Hiếu ký |

**Số dư CU cần trước bước 4:** ít nhất 32 CU (sàn 14 cộng cap 18). Ngày 9/11 số dư là 14,88 CU, nên phải mua thêm trước khi launch stage 3.

## 2. Chuẩn bị một lần

1. **Chạy từ `master`.** Mọi job GPU chạy từ bản checkout `master` sạch, không từ nhánh: `git fetch origin && git checkout --detach origin/master`, trong một thư mục riêng. Không dùng worktree đang có thay đổi.
2. **Colab CLI** trên laptop: `export PATH=~/project/wm-wam-review/.venv-colab-cli/bin:$PATH`, rồi `colab sessions` (phải trống: mỗi tài khoản chỉ chạy một đợt một lúc) và `colab usage` (số dư).
3. **Laptop thức suốt lần chạy.** Lần 1 của C+ mất 7,49 CU vì laptop restart giữa chừng ([tray.md](tray.md) mục 17.8). Bộ canh CU chạy trên laptop; laptop ngủ thì không còn gì dừng phiên ở trần.
4. **`rtx3060`:** SSH alias `rtx3060`. Máy dùng chung: tối đa 14 worker của đội, job nặng chạy trong `systemd-run --user --scope -p MemoryMax=…`, job dài dùng `nohup setsid`.
5. **Hai hàm dùng ở bước 2 và 4.** Dán vào shell sau khi đã đặt `R` (registry của đợt), như [tray.md](tray.md) mục 12:

```bash
ready() { if ( until [ -f $R/$1.ready ]; do grep -q '^exit ' $R/$1.out && exit 1; sleep 5; done
  [ -f $R/guard.beat ] && [ $(( $(date +%s) - $(stat -c %Y $R/guard.beat) )) -lt 120 ] )
  then echo "$1 READY"; else echo "$1 NOT READY: do not start the job"; return 1; fi; }
vm() { grep -q '^exit ' $R/$1.out && { echo "$1: watcher exited, no ssh"; return 1; }
  colab sessions < /dev/null | grep -q "^\[$1\]" || { echo "$1: not listed, no ssh"; return 1; }
  ssh -o ProxyCommand="colab ssh --proxy-mode -s $1" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null root@colab "${@:2}"; }
```

## 3. Bước 1: dữ liệu egocentric → bản export trên Drive

**Với 153 clip quay ngày 9/11 thì bước này đã xong**, chỉ còn việc đưa tarball lên Drive (3.9). Bản export ghim trong plan là `egx_7b43c30dc5d88cd7`: 132 mẫu, 7804 khung, tarball `fwdata/egocentric-export/tarballs/egx_7b43c30dc5d88cd7.tar`, sha256 `666a67fc…f84a`. Các mục 3.1–3.8 dành cho khi quay thêm video. Khi đó phải export, ghim lại vào `tray-ego-b.yaml` và chạy lại loader check, vì `export_id` đổi.

Mã làm sạch pose (PR #176, thay #174) phải có trên `master` trước khi chạy 3.5. Bản export phải được xuất từ đúng mã đó.

### 3.1 Sắp video

Thư mục nguồn có `device.json` (tên thiết bị, `fps`, `width`, `height`, ma trận nội 3 × 3) và `two_table/<i>.mp4` ([egocentric.md](../g0/egocentric.md) mục 8). Mỗi clip là trọn một lần làm task. Không để trong khung hình bảng tên hay giấy tờ có tên người; các clip 1080p ngày 9/11 bị loại vì có bảng tên.

### 3.2 Đưa về đúng 30 fps

Export từ chối khi clip không đúng 30 fps; clip của điện thoại là 30,2–30,5 fps hoặc 50 fps. Script dưới đây ghi lại từng clip ở đúng 30 fps, chạy trên **video gốc, trước `ingest`**. Clip gần 30 fps giữ mọi khung (chỉ đổi nhãn fps). Clip fps cao hơn lấy, với mỗi mốc 1/30 s, khung có thời điểm gần mốc đó nhất. Script nằm ngoài repo; lưu thành `to30fps.py` ở thư mục riêng ngoài `fwdata/`:

```python
"""Rewrite each <src>/two_table/<i>.mp4 (raw, not .deid) at exactly 30 fps into <dst>.
Near-30 fps sources keep every frame (relabelled); higher rates take, for each 1/30 s
tick, the frame whose timestamp is nearest. Prints one JSON line per clip."""
import json, sys
from pathlib import Path
import cv2, numpy as np
src, dst = Path(sys.argv[1]), Path(sys.argv[2]); (dst/"two_table").mkdir(parents=True, exist_ok=True)
for v in sorted((src/"two_table").glob("*.mp4"), key=lambda p: int(p.name.split(".")[0])):
    if v.name.endswith(".deid.mp4"): continue
    cap = cv2.VideoCapture(str(v)); fps_in = cap.get(cv2.CAP_PROP_FPS); frames, ts = [], []
    while True:
        ok, f = cap.read()
        if not ok: break
        ts.append(cap.get(cv2.CAP_PROP_POS_MSEC)/1000.0); frames.append(f)
    cap.release()
    if fps_in < 31:
        keep = list(range(len(frames)))
    else:
        t = np.array(ts) - ts[0]; ticks = np.arange(0, t[-1] + 1e-9, 1/30)
        keep = [int(np.argmin(np.abs(t - k))) for k in ticks]
    h, w = frames[0].shape[:2]
    out = cv2.VideoWriter(str(dst/"two_table"/v.name), cv2.VideoWriter_fourcc(*"mp4v"), 30.0, (w, h))
    for i in keep: out.write(frames[i])
    out.release()
    print(json.dumps({"clip": v.name, "fps_in": round(fps_in, 3), "n_in": len(frames), "n_out": len(keep)}))
d = json.loads((src/"device.json").read_text()); d["fps"] = 30
d["device"] = d["device"] + "; resampled to 30 fps (near-30 relabelled, 50 fps nearest-tick)"
(dst/"device.json").write_text(json.dumps(d, indent=1))
```

```bash
uv run python /path/to/to30fps.py fwdata/egocentric-raw/<video gốc> fwdata/egocentric-raw/<video-30fps> > fwdata/egocentric-raw/to30fps.jsonl
```

### 3.3 Ingest và che mặt (laptop)

`deid` phải chạy trước mọi bước đọc khung hình; cổng của pipeline chặn mọi bước sau nếu thiếu nó ([egocentric.md](../g0/egocentric.md) mục 3.1). Model YuNet nằm ở `fwdata/models/yunet`.

```bash
FW_ROOT=fwdata uv run fw egocentric ingest video --root fwdata/egocentric-raw/<video-30fps>   # in ra thư mục làm việc $W
W=<thư mục in ra>
FW_ROOT=fwdata uv run fw egocentric deid $W
```

### 3.4 Pose E-A trên `rtx3060`

MediaPipe không có trong `uv.lock`, nên job chạy trong venv riêng trên `rtx3060` ([egocentric.md](../g0/egocentric.md) mục 1.1, 10.4):

```bash
FW_ROOT=fwdata uv run fw egocentric pose $W --job ea_jobs.json      # laptop: ghi manifest
# chép manifest, các bản .deid.mp4 trong manifest và estimate_job.py lên ~/denso-da04/<thư mục> (chỉ bản đã che)
ssh rtx3060   # rồi trong ~/denso-da04/<thư mục>:
nohup setsid systemd-run --user --scope -p MemoryMax=8G -p MemorySwapMax=0 \
  ~/denso-da04/venv-ea/bin/python estimate_job.py --manifest ea_jobs.json --root <thư mục video> \
  --out out-ea --model hand_landmarker.task > ea.log 2>&1 < /dev/null &
# xong: chép out-ea/ về laptop, ví dụ fwdata/egocentric-raw/out-ea-<tên>/
FW_ROOT=fwdata uv run fw egocentric pose $W --estimates fwdata/egocentric-raw/out-ea-<tên>   # laptop: đọc E-A, làm sạch, ghi pose.npz
```

`pose --estimates` tự làm sạch E-A (khối `pose_ea.clean` của `egocentric.yaml`): hệ camera, liên tục dấu cổ tay, nội suy khung nhảy, làm mượt Savitzky–Golay cửa sổ 21.

### 3.5 Nhãn, duyệt của người, QA, báo cáo, export (laptop)

```bash
FW_ROOT=fwdata uv run fw egocentric annotate $W            # không có endpoint model thì câu lệnh lấy từ mẫu câu của cấu hình
FW_ROOT=fwdata uv run fw egocentric review $W --apply <phiếu duyệt .jsonl>
FW_ROOT=fwdata uv run fw egocentric qa $W
FW_ROOT=fwdata uv run fw egocentric report $W              # xem $W/report/index.html
FW_ROOT=fwdata uv run python -m flywheel.data.export.egodex --work $W --out fwdata/egocentric-export/<tên mới> \
  --include-flag --run-plan-id <id plan stage 1>
```

- **Phiếu duyệt.** Hiếu chốt ngày 9/11 rằng mỗi clip là một mẫu mang câu của cả task ([egocentric.md](../g0/egocentric.md) mục 6.1). Với mỗi episode, phiếu ghi một dòng: `fix` cho đoạn đầu, đổi đoạn đó thành chuỗi khung dài nhất có pose hữu hạn liên tục và dài ít nhất 30 khung; câu là "carry the tray with both hands from table A to table B and place it on the target zone"; các đoạn khác `reject`. Phiếu của 153 clip ở `fwdata/egocentric-raw/review-whole-clip-480p.jsonl` là mẫu. Mỗi dòng trỏ vào đoạn bằng `match`, không bằng vị trí.
- **`--include-flag`** là bắt buộc: các clip trọn task được QA đánh `flag`, không `pass` (132 `flag`, 21 `reject` trên 153 clip).
- Export bỏ mọi đoạn có một khung pose NaN, và chuẩn hóa bằng `egodex_stat_all.json` của tác giả.

### 3.6 Loader check (`rtx3060`, chỉ CPU, 0 CU)

Kiểm trước khi tốn GPU: phần giá trị action bị cắt ở [−1, 1] (`actions.clipped_value_share`) phải **≤ 5 %**. Bản ghim đo 3,6 %; trước khi làm sạch là 41,6 %. Cách chạy (image Ψ₀, `PYTHONPATH` trỏ bản clone `cda3fdf`, 8 CPU, 4 worker) ở [stage1.md](stage1.md) mục 2.7:

```bash
python -m flywheel_psi0.stage1.loader_check <launch.json của Stage1Trainer> --workers 4
```

Quá 5 % thì dừng: báo phiên DA-04, không train.

### 3.7 Đóng gói và ghim

```bash
uv run python -m flywheel_psi0.stage1.export_source pack --export fwdata/egocentric-export/<tên> \
  --out fwdata/egocentric-export/tarballs/<export_id>.tar
uv run python -m flywheel_psi0.stage1.export_source verify --export fwdata/egocentric-export/<tên> --export-id <export_id>
sha256sum fwdata/egocentric-export/tarballs/<export_id>.tar; stat -c %s fwdata/egocentric-export/tarballs/<export_id>.tar
```

Đóng gói từ thư mục export gốc, không từ bản đã qua loader: loader ghi thêm `filelist_cache.pkl` vào thư mục nó đọc. Cùng một export luôn cho cùng sha256. Ghim `export_id`, `tarball`, `sha256`, `bytes`, `samples` vào `dataset.source` của [`tray-ego-b.yaml`](../../configs/runplans/stage1/tray-ego-b.yaml) bằng một PR (phiên DA-30); `run_plan_id` đổi theo.

### 3.8 Bỏ `draft` khỏi plan stage 1

Một PR nhỏ của phiên DA-30 bỏ `status: draft`. Sau khi merge, `runplan check` phải in `OK rp_64bde22a5dda` mà không còn chữ "draft" (với bản ghim hiện tại). `setup` từ chối plan nháp trước khi cài hay tải bất cứ gì.

### 3.9 Đưa tarball lên Drive

Đưa `fwdata/egocentric-export/tarballs/egx_7b43c30dc5d88cd7.tar` lên `MyDrive/denso/da30/exports/`, đúng tên đó. `setup` so cỡ (`bytes` 48 701 440) trước khi chép và so sha256 sau khi chép sang VM.

**Trước khi qua bước 2:** người có mặt trong video đã đồng ý cho dùng video. `data_class` `public` (PR #170) chỉ cho phép đưa dữ liệu lên Colab; nó không thay cho sự đồng ý.

## 4. Bước 2: stage 1 trên Colab

Lệnh đầy đủ ở [stage1.md](stage1.md) mục 2.6. Tóm tắt, từ bản checkout `master` trên laptop:

```bash
export PATH=~/project/wm-wam-review/.venv-colab-cli/bin:$PATH
colab sessions; colab usage                                   # phải trống; số dư ≥ 18 (sàn 14 + cap 4)
S=da30-stage1-b
R=fwdata/colab/da30b-$(date +%Y%m%d-%H%M%S); mkdir -p fwdata/colab && mkdir $R
nohup setsid bash -c 'trap "" TERM HUP INT; python3 scripts/colab/cu_watch.py guard --registry "$0" --floor 14 --log "$0/guard.jsonl"; echo "exit $?"' $R < /dev/null > $R/guard.out 2>&1 &
nohup setsid bash -c 'trap "" TERM HUP INT; python3 scripts/colab/cu_watch.py session --registry "$0" --new --name da30-stage1-b --gpu L4 --cap 4 --floor 14 --persist "colab exec -s da30-stage1-b -f configs/runplans/stage1/persist_cell.py" --log "$0/da30-stage1-b.jsonl"; echo "exit $?"' $R < /dev/null > $R/da30-stage1-b.out 2>&1 &
ready $S
git archive --format=tar.gz HEAD | vm $S 'mkdir -p /content/da30/fw && tar -xz -C /content/da30/fw'
colab drivemount -s $S /content/drive                          # trước setup: tarball nằm trên Drive
```

Trên VM, trong `/content/da30`, với `PYTHONPATH=fw/packages/flywheel-psi0/src:fw/packages/flywheel-contracts/src`. Lệnh train chạy qua SSH (`vm $S '…'`), không qua `colab exec`, để kernel rảnh cho `persist` của bộ canh. Chạy theo thứ tự, mỗi lệnh chỉ khi lệnh trước xong:

```bash
P=fw/configs/runplans/stage1/tray-ego-b.yaml
python3 -m flywheel_psi0.stage1.colab setup --work /content/da30 --plan $P               # pre-flight DeepSpeed, tải VLM cha, kiểm tarball
Psi0/.venv-psi/bin/python -m flywheel_psi0.stage1.colab run --work /content/da30 --plan $P
python3 -m flywheel_psi0.stage1.colab persist --work /content/da30 --plan $P             # VLM lên Drive sớm nhất
Psi0/.venv-psi/bin/python -m flywheel_psi0.stage1.colab check-vlm --work /content/da30 --plan $P
Psi0/.venv-psi/bin/python -m flywheel_psi0.stage1.colab repeat --work /content/da30 --plan $P
python3 -m flywheel_psi0.stage1.colab persist --work /content/da30 --plan $P
```

- **Quy tắc dừng [Đề xuất]:** đọc s/bước trong `train.log` sau 20 bước; quá 14 s/bước thì dừng VM. Bộ canh dừng phiên ở khoảng 3,77 CU và chạy `persist` sớm hơn 600 s.
- **Kết quả:** VLM ở `MyDrive/denso/da30/da30-tray-ego-b/vlm/`. Mục `persist.vlm` của `report.json` có bốn giá trị cần ghim ở bước 3: `job_id`, `drive_dir`, `weights_sha256`, `manifest_sha256`.
- **Sau khi chạy:** tải `report.json` và log về `fwdata/colab/`. Ghi dòng `measured` vào `docs/g0/ledger/DA-30.csv`, lấy `balance_drop` ở dòng `exit` của `$R/da30-stage1-b.jsonl`, trỏ về dòng ước lượng `job_da30_stage1_tray_ego_b`.

## 5. Bước 3: ghim VLM vào plan B và đóng băng

Đây là nhiệm vụ con 4.7 của DA-34, do phiên DA-34 làm bằng một PR ([tray.md](tray.md) mục 18.3):

1. Điền `parents.psi0-b-ego-stage1.vlm_stage1` của [`he-tray-b.yaml`](../../configs/runplans/tray/he-tray-b.yaml) bằng bốn giá trị ở bước 2.
2. Kiểm `colab_train manifest --folder <thư mục VLM>`: `header_sha256` phải bằng `parent_header_sha256` (`53d000d9…`). Lệch nghĩa là stage 1 lưu sai tensor, và stage 3 sẽ train trên trọng số ngẫu nhiên.
3. Bỏ `draft`, chạy `python -m flywheel_psi0.tray.runplan freeze configs/runplans/tray/he-tray-b.yaml` để có id mới, đặt `B_FROZEN` trong `colab_train.py` bằng id đó, và cập nhật `subject_id` của `he-tray-b.decision.json`.
4. Luật đọc 18.2 (gồm phần eval hai giai đoạn Hiếu chốt 10/11) đã được duyệt.

Trước khi PR này merge, `check`, `setup` và `train` của B đều từ chối, kèm lý do.

## 6. Bước 4: stage 3 B trên Colab

Lệnh đầy đủ ở [tray.md](tray.md) mục 18.4 (khác C+ ở mục 17.6 bốn điều: plan, `--branch B`, bản cắt ở `sets/B/`, VLM lấy từ Drive).

**6.1 `rtx3060`: kiểm lúc khởi chạy và dựng bản cắt** (0 CU, ~1 phút). `D` là bản `git archive` của `master` mới vào `~/denso-da34-master-<sha>`, kèm file `TREE_SHA`:

```bash
cd $D && export PYTHONPATH=$(ls -d $PWD/packages/*/src | paste -sd:)
PY=~/denso-da34-pool/.venv/bin/python
REL_C=~/denso-da34-pool/fwdata/releases/tray_s1_f9433b028c52
CUT=~/denso-da34-pool/fwdata/cut-b-$(cut -c1-7 TREE_SHA)
E=G1WholebodyTrayTransferTeleop-v0
$PY -m flywheel_psi0.tray.runplan check configs/runplans/tray/he-tray-b.yaml --release $REL_C --launch \
  || { echo "runplan check --launch failed: do not launch"; exit 1; }
$PY scripts/he/demo_subset.py --src $REL_C --sets configs/runplans/tray/demo_sets-v2.json --set C --out $CUT/sets/B/$E
$PY -m flywheel_psi0.tray.colab_train check --branch B --work $CUT
```

**6.2 Laptop: kéo bản cắt, guard và watcher.** Số dư phải ≥ 32 CU.

```bash
CUT=denso-da34-pool/fwdata/cut-b-<sha7>
rsync -a --delete --partial-dir=.rsync-partial rtx3060:$CUT/sets/ fwdata/tray/cut-b/sets/
export PATH=~/project/wm-wam-review/.venv-colab-cli/bin:$PATH
colab sessions; colab usage
S=da34-t4-ft-b-s0
R=fwdata/colab/batch-$(date +%Y%m%d-%H%M%S); mkdir -p fwdata/colab && mkdir $R && git rev-parse HEAD > $R/master.sha
nohup setsid bash -c 'trap "" TERM HUP INT; python3 scripts/colab/cu_watch.py guard --registry "$0" --floor 14 --log "$0/guard.jsonl"; echo "exit $?"' $R < /dev/null > $R/guard.out 2>&1 &
nohup setsid bash -c 'trap "" TERM HUP INT; python3 scripts/colab/cu_watch.py session --registry "$0" --new --name "$1" --gpu L4 --cap 18 --floor 14 --persist "python3 scripts/he/he1_fetch.py once --session $1 --registry $0 --dest fwdata/tray/runs --remote-work /content/da34" --log "$0/$1.jsonl"; echo "exit $?"' $R $S < /dev/null > $R/$S.out 2>&1 &
```

**6.3 Phiên B.** Mỗi lệnh chỉ chạy khi lệnh trước đã xong:

```bash
ready $S && python3 scripts/he/he1_fetch.py probe --session $S --registry $R --dest fwdata/tray/runs --remote-work /content/da34 \
  || { colab stop -s $S; echo "$S: not ready or proxy too slow, session stopped"; }
git archive --format=tar.gz HEAD | vm $S 'mkdir -p /content/da34/fw && tar -xz -C /content/da34/fw'
rsync -a --partial-dir=.rsync-partial -e "ssh -o ProxyCommand='colab ssh --proxy-mode -s $S' -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null" \
  fwdata/tray/cut-b/sets/ root@colab:/content/da34/sets/
colab drivemount -s $S /content/drive
VMPP=fw/packages/flywheel-psi0/src:fw/packages/flywheel-contracts/src
vm $S "cd /content/da34 && PYTHONPATH=$VMPP python3 -m flywheel_psi0.tray.colab_train check --branch B" \
  || { colab stop -s $S; echo "$S: cut or plan does not hold on the VM, session stopped"; }
vm $S "cd /content/da34; nohup setsid bash -c 'PYTHONPATH=$VMPP python3 -m flywheel_psi0.tray.colab_train setup --branch B; echo setup exit \$?' > setup.log 2>&1 < /dev/null &"
vm $S 'tail -2 /content/da34/setup.log'   # chờ "setup exit 0"
vm $S "cd /content/da34; nohup setsid bash -c 'PYTHONPATH=$VMPP Psi0/.venv-psi/bin/python -m flywheel_psi0.tray.colab_train train --branch B; echo train exit \$?' > train.log 2>&1 < /dev/null &"
nohup setsid bash -c 'python3 scripts/he/he1_fetch.py follow --session "$1" --registry "$0" --dest fwdata/tray/runs --remote-work /content/da34 --every 600 --stop-when-done; echo "exit $?"' $R $S < /dev/null > $R/$S.fetch.log 2>&1 &
```

`setup` của B kiểm VLM từ Drive trước khi train. Lệch một trong các điều sau thì dừng: sha256 trọng số, header safetensors so với VLM của C, manifest cả thư mục, và mọi file không phải trọng số phải trùng từng byte với VLM của C.

**6.4 Chuyển checkpoint sang `rtx3060`.** Chỉ chuyển khi `fetched.json` báo `final`:

```bash
J=fwdata/tray/runs/da34-t4-ft-b-s0
DST=denso-da34-pool/fwdata/tray/runs/da34-t4-ft-b-s0
python3 -c 'import json, sys; sys.exit(0 if json.load(open(sys.argv[1]))["final"] else 1)' $J/fetched.json \
  || { echo "not final: no hand-off"; exit 1; }
(cd $J && find . -type f -not -path '*/.*' -print0 | sort -z | xargs -0 sha256sum) > $J.sha256
rsync -a --partial-dir=.rsync-partial --exclude='.*' $J/ rtx3060:$DST/
rsync -a $J.sha256 rtx3060:$DST.sha256
ssh rtx3060 "cd $DST && sha256sum -c --quiet" < $J.sha256 && echo "hand-off OK" || echo "hand-off FAILED: do not eval"
```

Sau đó ghi dòng `measured` cho `job_da34_ft_B` vào `docs/g0/ledger/DA-34.csv`, trỏ về dòng ước lượng 16,0 CU. Sau khi hand-off OK và đã kiểm sha256 trên `rtx3060`, bản trên laptop có thể xóa.

## 7. Bước 5: eval B trên `rtx3060`

Cách chạy giống hệt eval C SimReady và eval C+, để ghép cặp được với mốc C (20/240). Chi tiết ở [tray.md](tray.md) mục 18.5:

- Tập `rp_a04c14e79dfd-2e57f60` (270 điều kiện), cây client `~/denso-da34-master-079160d` có SimReady, server B `ckpt_40000`, `Ta` 24, `--rtc`, cổng 22185, **1 worker**, lô 10 episode, scope `MemoryMax=8G`.
- Script vận hành: chép `~/denso-da34-t8/serve-cplus.sh` và `launch-eval-cplus.sh` thành `serve-b.sh` và `launch-eval-b.sh`, thay job thành `da34-t4-ft-b-s0`. Ba chặn giữ nguyên: sha256 của hand-off, đúng một run có `ckpt_40000`, và bounds của `run_config.json` bằng stats của bản cắt B (lệch 0 so với C).
- **Hai giai đoạn (Hiếu chốt 10/11/2026):** chạy trước 6 lô `l1-000`, `l2-000`, `l1-010`, `l2-010`, `l1-020`, `l2-020` (60 điều kiện, khoảng 4 giờ), rồi đọc. Dừng khi B hơn hoặc kém C rất rõ (McNemar p < 0,001 cùng chiều với CI), hoặc khi B không hơn C trên 60 điều kiện đó. Còn lại thì chạy tiếp tới đủ 240 (khoảng 16,5 giờ tổng). Luật chính xác nằm trong khối `branch-b-rules` của [tray.md](tray.md) mục 18.2, sau khi PR luật merge.

```bash
# trên rtx3060, sau "hand-off OK" và khi Hiếu cho chạy; CUT = thư mục bước 6.1 đã ghi
~/denso-da34-t8/serve-b.sh $CUT
systemd-run --user --scope --unit da34-eval-b -p MemoryMax=8G -p MemorySwapMax=0 \
  nohup setsid ~/denso-da34-t8/launch-eval-b.sh > ~/denso-da34-t8/eval-b.out 2>&1 < /dev/null &
```

Không chạy song song với eval khác trên cùng server: client không gửi `session_id`, nên hai client thành một phiên RTC ([tray.md](tray.md) mục 17.7).

## 8. Bước 6: đọc kết quả và ghi lại

```bash
PLAN=configs/runplans/tray/he-tray-b.yaml
SET=~/denso-da34-pool/fwdata/tray/eval-sets/rp_a04c14e79dfd-2e57f60
EV=~/denso-da34-pool/fwdata/tray/eval
$PY -m flywheel_psi0.tray.eval_results $PLAN --set $SET --out $EV/eval-b-simready-<B id> \
    --baseline $EV/eval-c-simready-rp_a04c14e79dfd --json b-vs-c.json
$PY -m flywheel_psi0.tray.eval_results $PLAN --set $SET --out $EV/eval-b-simready-<B id> \
    --baseline $EV/eval-cplus-simready-rp_a04c14e79dfd --json b-vs-cplus.json   # chỉ mô tả
```

- `paired.headline`: hiệu B − C (`diff`), CI bootstrap (`ci`), `ci_vs_0` (`above` / `contains` / `below`, ứng với luật 1 / 2 / 3), số cặp bất đồng, `mcnemar_exact_p`.
- Kết quả và giới hạn đi vào `he-tray-b.decision.json` và [tray.md](tray.md) mục 18, kèm dòng `measured` cho `job_da34_eval_B` (nhiệm vụ con 4.8). Hiếu ký `Decision`.
- Mọi số B − C ghi là **sơ bộ, trên dev**: 1 seed train mỗi nhánh, 1 rollout mỗi điều kiện, chỉ trong sim.

## 9. Bài học từ C và C+

| Chuyện đã xảy ra | Cách tránh |
|---|---|
| Laptop restart giữa lần 1 của C+, mất 7,49 CU | Bật chế độ giữ thức; không cập nhật hệ điều hành trong lúc chạy |
| Export từ chối clip 30,2 fps và 50 fps | Chạy 3.2 trước `ingest` |
| 41,6 % action bị cắt do xoay camera của VO và lật cổ tay | Mã làm sạch của PR #176; loader check ≤ 5 % trước khi tốn GPU |
| QA từ chối mọi clip trọn task (`segment_count` ≥ 2) | PR #173: QA tôn trọng phiếu duyệt của người; export với `--include-flag` |
| Hai eval cùng một server cho kết quả khác một worker | Mỗi lúc một eval, 1 worker |
| Ảnh eval khác ảnh train (cây eval thiếu SimReady) | Dùng `simple-guard.sh` trước mỗi lô; kiểm PSNR frame 0 ([tray.md](tray.md) mục 16.2) |
| `setup` chạy từ nhánh chưa merge | Chỉ chạy từ `master`; plan nháp hoặc thiếu ghim thì bị từ chối trước khi tốn GPU |

## Change log

| Ngày | Sửa | Người |
|---|---|---|
| 10/11/2026 | Bản đầu: gom runbook stage 1 (stage1.md 2.6), stage 3 B (tray.md 18.4), eval B (18.5) và pipeline egocentric (egocentric.md) thành một đường chạy, kèm bản đồ code | Claude (phiên điều phối), theo yêu cầu của Hiếu |
