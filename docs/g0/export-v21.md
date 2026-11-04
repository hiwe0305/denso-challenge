# Checklist LeRobot v2.1 cho Ψ₀ trên khay S1 và psi-data

_Ngày 4/11/2026. Story [DA-02](../product/stories/DA-02-export-lerobot-v21.md) nhiệm vụ 3. Checklist là 7 điểm của [design 27/10](../superpowers/specs/2026-10-27-g1-psi0-demo-design.md) mục 6.4: điểm 1–6 do `flywheel.data.export.checklist` chạy trong làn, điểm 7 do contract test `packages/flywheel-psi0/tests/contract/test_loader_roundtrip.py` chạy trong image Ψ₀. Code ở bản cuối của PR #91 (nhánh `DA-02-export-checklist`, rebase lên master `7d73f1e`, đã có PR #89), chạy trên máy `rtx3060`. Dữ liệu, batch mẫu và script chạy nằm ở `rtx3060:~/denso-da02/` và không commit._

## Kết luận

- **psi-data qua 17/18 phép kiểm của điểm 1–6; khay S1 qua 16/18.**
  - `index` (điểm 2) trượt ở cả hai. Lỗi này đã biết: tác giả bắt đầu cột `index` của episode i ở 2 × `dataset_from_index` (Q7 của DA-03). Cả hai dataset cùng đi qua `postprocess_psi0_sonic.py` của SIMPLE.
  - `stats.constant` (điểm 6, D4) trượt ở khay S1, trên 5 chiều `[0, 7, 28, 29, 30]` (`left_hand_thumb_0`, `right_hand_thumb_0`, ba khớp eo). Đây là phát hiện, không điều chỉnh để khay S1 qua (phát hiện 1).
  - **[Đã chốt]** Hiếu chọn phương án A ngày 4/11/2026: theo đúng D4, chiều hằng số không mask và không khai `constant` thì trượt. PR #89 (đã merge) thêm `ActionDimension.constant` và khai chiều 31 trong `g1.yaml`, nên chiều 31 của cả hai dataset qua.
- **Điểm 7 qua trên cả hai dataset** (3/3 test mỗi dataset). Loader Ψ₀ ở `cda3fdf`, fork lerobot `09929d8`, đọc ra đúng giá trị parquet ở cả đầu và cuối episode. Loader tìm dòng theo vị trí và `episode_data_index`, không theo cột `index`, nên lỗi `index` ở trên **không làm sai batch Ψ₀ train**. Batch khớp batch mẫu đã lưu đến từng giá trị.
- **`stats_psi0.json` của psi-data qua điểm 6.** File được tính trên đúng dữ liệu của gói, không NaN. Khoảng lệch DA-27 và DA-03 báo trước đây (`states.mean` lệch 3,63e-4 ở psi-data, 7,67e-4 ở khay S1) **không phải stats sai**. SIMPLE tính `states` bằng float64 và `action` bằng float32. Bản tính lại của làn dùng float32 cho cả hai, nên chính bản tính lại mới cộng dồn sai số. So với bản tính lại float64, `states` lệch 1,2e-7 (psi-data) và 1,8e-7 (khay S1); `action` lệch 0 so với bản float32; min và max lệch 0 (mục 4).
- Chiều hằng số tìm theo đúng luật của Ψ₀ (`ill_mask` trong `ActionStateTransform` ở `cda3fdf`: `|max − min| < 1e-4·(|max| + |min|)`), đối chiếu với bản tính lại; không tìm theo std (mục 4). psi-data có `[31]` (0,74 ở mọi khung); khay S1 có `[0, 7, 28, 29, 30, 31]`. Normalizer `bounds` của Ψ₀ giữ nguyên giá trị các chiều này; test điểm 7 kiểm điều đó trên batch thật.
- Chạy nhẹ: checklist mất 2,5 s (khay S1, 148.013 khung) và 1,4 s (psi-data, 62.764 khung), RSS đỉnh 462 MB cho cả hai trong một tiến trình. Mỗi lần chạy điểm 7 mất 25–35 s, container giới hạn 6 GB, 4 CPU, không GPU, không mạng.

Việc phát sinh, Hiếu quyết:

| # | Phát hiện | Ảnh hưởng | Đề xuất |
|---|---|---|---|
| 1 | Khay S1 có 5 chiều action hằng số mà layout không khai: `[0, 7, 28, 29, 30]` (`left_hand_thumb_0_joint`, `right_hand_thumb_0_joint`, `waist_roll/pitch/yaw_joint`). Ở psi-data, các chiều này có biến thiên | Khay S1 trượt điểm 6 (D4, chặn export). Hoặc planner và IK `upper_body` của DA-33 không bao giờ động tới các khớp này, hoặc đó là ý đồ của planner. Nếu là ý đồ, model fine-tune trên khay sẽ học các chiều này là hằng. DA-33 đang soát action tay của chính release này ([wrist-jump.md](tray/wrist-jump.md), commit `7d73f1e`), cùng đường planner → IK → `action` | DA-33 trả lời các chiều này có thật sự hằng không. Hiếu quyết: khai `constant` cho dữ liệu khay, hoặc sửa planner |
| 2 | D4 trên `states` ở [data-pipeline.md](data-pipeline.md) phát hiện 2 và ở `test_source_stats.py` của DA-27 là dương tính giả do float32 (mục 4) | `dataset_checks` của DA-03 đánh `flag` cho `stats.json` của cả hai nguồn, dù stats đúng | **[Đề xuất]** DA-03 so trong cả float32 và float64 như `checklist.PRECISIONS`; DA-27 sửa lời giải thích "lấy trước khi downsample" |
| 3 | Loader Ψ₀ đòi timestamp khớp trong 1e-4 s (`tolerance_s` của lerobot, dùng ở `check_timestamps_sync` và khi giải mã video). Design 6.4 điểm 3 chỉ đòi nửa chu kỳ (10 ms ở 50 Hz) | Dataset lệch từ 0,1 ms đến 10 ms qua điểm 3 nhưng loader Ψ₀ từ chối. Hai dataset hiện có lệch 2e-13 chu kỳ, không bị ảnh hưởng | **[Đề xuất]** Siết điểm 3 xuống 1e-4 s; việc này cần sửa design |
| 4 | Cả hai `info.json` không khai tên từng chiều action (`shape [-1]`, không có `names`) và để trống `video_info`. Khay S1 có `meta/action_layout.json`; psi-data chỉ có nhóm trong `modality.json` | Điểm 1 kiểm được tên của khay S1, không kiểm được tên của psi-data. Điểm 4 không có codec khai báo để so | Ghi nhận. Checklist báo "không khai" ở chi tiết, không đánh trượt |

## 1. Dữ liệu

| Dataset | Đường dẫn trên `rtx3060` | Kiểm danh tính |
|---|---|---|
| Khay S1 (DA-33) | `~/denso-da33/fwdata/releases/tray_s1_0d84cc87b1e5` | 217/217 file khớp sha256 trong `release_manifest.json` |
| psi-data `e78fb93`, task hai bàn | `~/denso-da03-smoke/fwdata/psi-data/G1WholebodyLocomotionPickBetweenTablesTeleop-v0` | 207/207 file khớp CRC32 trong zip `simple/G1WholebodyLocomotionPickBetweenTablesTeleop-v0.zip` (sha256 `6cdf9022…927586`, [psi-data.md](psi-data.md) mục 1), không thừa file |

Ở cả hai dataset, `meta/stats.json` và `meta/stats_psi0.json` giống hệt nhau.

## 2. Điểm 1–6

Layout lấy từ `configs/embodiments/g1.yaml` (DA-01). Code chạy bằng venv có sẵn `~/denso-da03-smoke/venv` (pyarrow 25.0.1, numpy 2.2.6, pydantic 2.14.2), nạp mã nguồn của nhánh qua `PYTHONPATH`. Chỉ một tiến trình:

```bash
cd ~/denso-da02
PYTHONPATH=packages/flywheel-contracts/src:packages/flywheel-data/src \
  systemd-run --user --scope -q -p MemoryMax=3G -p MemorySwapMax=0 \
  ~/denso-da03-smoke/venv/bin/python run_checklist.py \
  ~/denso-da33/fwdata/releases/tray_s1_0d84cc87b1e5 \
  ~/denso-da03-smoke/fwdata/psi-data/G1WholebodyLocomotionPickBetweenTablesTeleop-v0
```

`run_checklist.py` (ngoài repo):

```python
import resource, sys, time
from pathlib import Path
from flywheel.data.config import load_layout
from flywheel.data.export.checklist import run_checklist

layout = load_layout(Path("configs/embodiments/g1.yaml"))
for root in sys.argv[1:]:
    start = time.monotonic()
    findings = run_checklist(Path(root).expanduser(), layout)
    print(f"== {root}  ({time.monotonic() - start:.1f} s)")
    for f in findings:
        mark = "pass" if f.check.passed else "FAIL"
        print(f"{mark} {f.check.name:28s} {f.code} value={f.check.value:g} "
              f"threshold={f.check.threshold:g}  {f.detail}")
print(f"peak RSS {resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024:.0f} MB")
```

Kết quả. Một phép kiểm trượt khi `value > threshold`. Cột "Chi tiết" là output của lệnh, rút gọn:

| Phép kiểm | Mã | Khay S1 | psi-data | Chi tiết |
|---|---|---|---|---|
| `v21.1.info.codebase_version` | D1 | pass | pass | `v2.1` |
| `v21.1.info.fps` | D1 | pass | pass | 50 |
| `v21.1.info.robot_type` | D1 | pass | pass | `g1` |
| `v21.1.info.action_shape` | D1 | pass | pass | `shape [-1]`; độ rộng 36 được kiểm khi đọc parquet |
| `v21.1.info.action_names` | D1 | pass | pass | Khay: 0/36 tên khác `meta/action_layout.json`. psi-data: không khai tên |
| `v21.1.read` | D1 | pass | pass | Đọc được 102 / 99 episode |
| `v21.2.index.episode_index` | D2 | pass | pass | 0 episode lệch |
| `v21.2.index.index` | D2 | **FAIL** 116.062 | **FAIL** 60.023 | Số dòng lệch, trên 148.013 / 62.764 dòng; episode 1 bắt đầu ở 2846 (cần 1423) / 1162 (cần 581) |
| `v21.2.index.frame_index` | D2 | pass | pass | 0 dòng lệch |
| `v21.3.timestamp` | D2 | pass 2,3e-13 | pass 1,1e-13 | Lệch lớn nhất, tính bằng chu kỳ (ngưỡng 0,5) |
| `v21.4.video.frames` | D2 | pass | pass | Mọi video có số khung bằng số dòng (đọc từ `stsz`) |
| `v21.4.video.codec` | D2 | pass | pass | Tìm thấy `h264`; `video_info` không khai |
| `v21.4.video.resolution` | D2 | pass | pass | (360, 640), khớp `shape` khai báo |
| `v21.5.tasks` | D6 | pass | pass | Mọi episode có câu lệnh |
| `v21.6.stats.file` | D4 | pass | pass | Có `states` và `action` (mean, std, min, max), đúng độ rộng |
| `v21.6.stats.finite` | D4 | pass | pass | 0 NaN hoặc Inf |
| `v21.6.stats.release` | D4 | pass 1,8e-7 | pass 1,2e-7 | Lệch lớn nhất so với bản tính lại gần nhất (float64, ở `states.mean[31]`); ngưỡng 1e-5 |
| `v21.6.stats.constant` | D4 | **FAIL** 5 | pass | Chiều hằng số `[0, 7, 28, 29, 30, 31]` / `[31]`; `g1.yaml` khai `[31]`; lỗi `[0, 7, 28, 29, 30]` / không lỗi |

Trước #89, layout chưa khai chiều nào, nên `stats.constant` trượt ở 6 chiều của khay S1 và chiều 31 của psi-data. Lần chạy thử với contract và `g1.yaml` của nhánh #89 (`139985e`) ra đúng kết quả của bảng trên.

## 3. Điểm 7

Môi trường Ψ₀ là image `ghcr.io/physical-superintelligence-lab/psi0@sha256:0d580125…` (đã ghim ở `docker/psi0/compose.yaml` của S1-03). Trong image có `/workspace/.venv-psi` với lerobot `songlin/lerobot@09929d8` (`CODEBASE_VERSION = "v2.1"`). Package `psi` cài editable từ checkout Ψ₀ `cda3fdf` ở `~/denso-s103/fwdata/psi0/Psi0`. Image không có pytest, nên ba wheel thuần Python được tải từ PyPI bằng `pip download` và giải nén vào `~/denso-da02/fwdata/pytest-py311/site`:

| Wheel | sha256 |
|---|---|
| `pytest-8.3.5-py3-none-any.whl` | `c69214aa…d4d820` |
| `pluggy-1.5.0-py3-none-any.whl` | `44e1ad92…a669` |
| `iniconfig-2.0.0-py3-none-any.whl` | `b6a85871…8374` |

`run_point7.sh <dataset> <batch .npz> [write]` (ngoài repo) chạy test trong image. Lần đầu chạy kèm `write` để ghi batch mẫu; sha256 in ra được ghi vào `REFERENCES` của test:

```bash
docker run --rm --user "$(id -u):$(id -g)" --network none --memory 6g --memory-swap 6g --cpus 4 \
  -e HOME=/tmp -e HF_HUB_OFFLINE=1 -e HF_DATASETS_CACHE=/tmp/hf-datasets \
  -e PYTHONPATH="$REPO/fwdata/pytest-py311/site" -e PYTHONDONTWRITEBYTECODE=1 \
  -e FW_PSI0_ROUNDTRIP_DATASET="$DATASET" -e FW_PSI0_ROUNDTRIP_REFERENCE="$REFERENCE" \
  -e FW_PSI0_ROUNDTRIP_WRITE="${WRITE:-0}" -e FW_PSI0_SRC=/workspace/psi0-pin \
  -v "$REPO:$REPO:ro" -v "$PSI0:/workspace/psi0-pin:ro" -v "$PSI0/src:/workspace/src:ro" \
  -v "$DATASET:$DATASET:ro" -v "$(dirname "$REFERENCE"):$(dirname "$REFERENCE")" \
  -w "$REPO" "$IMAGE" \
  /workspace/.venv-psi/bin/python -m pytest -p no:cacheprovider -q -rs -W default \
  packages/flywheel-psi0/tests/contract/test_loader_roundtrip.py
```

`REPO=~/denso-da02`, `PSI0=~/denso-s103/fwdata/psi0/Psi0`; `IMAGE` là digest ở trên.

Batch gồm 5 mẫu: khung đầu, khung cuối episode 0 (chunk 30 bước bị đệm sau điểm cuối), khung đầu episode 1, khung giữa episode cuối, khung cuối dataset. Mỗi mẫu đi qua `LeRobotDatasetWrapper`, `SimpleRepackTransform` và `ActionStateTransform` với tham số của `configs/models/psi0-stage3.yaml`, không augmentation. Mỗi mẫu gồm ảnh, `states` (1 × 36), `actions` và `raw_actions` (30 × 36), `actions_mask`, câu lệnh.

| Dataset | Batch mẫu (`~/denso-da02/fwdata/psi0-roundtrip/`) | sha256 | Kết quả |
|---|---|---|---|
| Khay S1 | `tray_s1_0d84cc87b1e5.npz`, 1,37 MB | `7aab984b…857e10` | 3 passed, 34 s |
| psi-data | `psi-data-e78fb93-two-table.npz`, 0,88 MB | `f6719f08…d04840` | 3 passed, 25 s |
| Đối chứng: dataset khay với batch mẫu của psi-data | | | 1 failed (`index` của batch khác), như mong đợi |

Ba test kiểm: (1) pin: commit lerobot trong `direct_url.json`, HEAD của checkout Ψ₀, `transform.py` được import giống file của checkout; (2) giá trị loader đọc khớp parquet đọc bằng pyarrow (states, chunk action và cờ đệm, câu lệnh), và chiều hằng số đi qua normalizer nguyên giá trị; (3) batch bằng batch mẫu từng giá trị (`np.array_equal`). Cảnh báo duy nhất là thông báo của torchvision rằng API video sắp bị bỏ.

Ngoài lane CI, module tự bỏ qua khi không import được `psi`: `uv run pytest packages/flywheel-psi0` cho 73 passed, 1 skipped.

## 4. Stats: float32 hay float64

Để biết khoảng lệch của `states` là stats sai hay sai số số học, so stats đã ship với hai bản tính lại trên cùng frame (script `stats_precision.py` ở `~/denso-da02`, đọc bằng `iter_episodes` của DA-03):

| Dataset | Khối | \|ship − tính lại float32\| | \|ship − tính lại float64\| | min, max |
|---|---|---|---|---|
| Khay S1 | `states` mean / std | 7,7e-4 / 4,2e-4 | 1,8e-7 / 1,8e-7 | khớp 0 |
| Khay S1 | `action` mean / std | 0 / 0 | 1,9e-3 / 4,2e-4 | khớp 0 |
| psi-data | `states` mean / std | 3,6e-4 / 3,6e-4 | 1,2e-7 / 1,2e-7 | khớp 0 |
| psi-data | `action` mean / std | 0 / 0 | 3,6e-4 / 3,6e-4 | khớp 0 |

SIMPLE tính mỗi khối theo dtype của nó lúc tính: `states` bằng float64, `action` bằng float32. Cộng dồn float32 qua 10⁵ khung dịch mean đi tới 7,7e-4. Vì thế `stats.release` coi một khối là "tính trên đúng release" khi khối đó khớp một trong hai bản tính lại. Ψ₀ chuẩn hóa bằng min và max (`bounds`), và min, max khớp 0 ở cả hai dataset. Cũng vì float32, std của chiều 31 trong psi-data là 3,6e-4 dù chiều này hằng 0,74. Bản tính lại của làn ra đúng 3,6e-4, nên đây không phải lệch giữa stats ship và release. Do đó checklist tìm chiều hằng số bằng `max − min` (đúng `ill_mask` của Ψ₀), không bằng std.

Dung sai của `stats.release` là 1e-5 (`STATS_TOLERANCE` trong `checklist.py`), bằng ngưỡng `stats_json` của `configs/data/qa.yaml` (DA-03). Lý do chọn 1e-5:
- Lệch thật đo được khi so với bản tính lại cùng dtype là 1,8e-7 trở xuống. Đó là sai số làm tròn float32 của giá trị cỡ 1 (ulp ≈ 6e-8 đến 1,2e-7).
- Một stats tính trên release khác, ví dụ thiếu hoặc thừa một episode, lệch ít nhất cỡ 1e-3 trên mean; test `test_stats_in_either_precision_count_as_computed_on_the_release` kiểm lệch 1e-3.
- 1e-5 nằm giữa hai mức, cách mỗi mức hai bậc độ lớn.

Hàm `check_lerobot_v21(root, layout)` không nhận config, nên dung sai là hằng số trong module. **[Đề xuất]** Nếu cần đưa dung sai vào config, thêm một khóa vào `qa.yaml` qua PR của DA-03.
