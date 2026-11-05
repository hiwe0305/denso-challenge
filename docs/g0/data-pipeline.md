# Pipeline dữ liệu: ingest, QA, release, báo cáo trên psi-data và khay S1

_Ngày 4/11/2026. Story [DA-03](../product/stories/DA-03-pipeline-teleop-synthetic.md) nhiệm vụ 6.3, PR 2. Mọi số trong file này là output của `fw data`, chạy trên máy `rtx3060`: hai nguồn ở commit `e3aad54`, hai bản sao chấm lỗi của DA-27 (mục 3.5) ở commit `82e0752`, sau khi #53 merge. Thời gian chạy và RSS đỉnh đo bằng `/usr/bin/time -v`. Dữ liệu và kết quả nằm ở `rtx3060:~/denso-da03-pr2/fwdata/` và không commit._

## Kết luận

- Bốn lệnh `fw data ingest | qa | release | report` chạy hết trên hai nguồn và trả mã 0. Mỗi lệnh dưới 6 giây và dưới 0,5 GB RAM, chạy một tiến trình.
- **psi-data** (task hai bàn, 99 episode): 95 `pass`, 4 `flag`, không episode nào `reject`. Release `rel_24363158e44e66b4` có 99 episode.
- **Khay S1** (DA-33, 102 episode): cả 102 episode bị `flag` vì `action_jump.arm`, không episode nào `reject`. Release `rel_9f32f33779c904f2` có 102 episode.
- **D4 thật trên cả hai nguồn.** `meta/stats.json` ghi `states.mean` lệch so với frame: 3,63e-4 ở psi-data (chiều 31) và 7,67e-4 ở khay S1 (chiều 6). Phần `action` khớp đến từng bit.
- **Bản sao chấm lỗi bị chặn.** Hai bản sao của DA-27 (#53) đi qua `ingest` và `qa`, nhưng `release` từ chối cả hai bằng `has_injected_defect` và trả mã 2 (mục 3.5).
- Chưa chạy được ba phép kiểm phát lại (`replay_kinematic`, `replay_dynamic`, `replay_success`) vì chưa có `ReplayReport` của DA-17. `qa.yaml` cho phép bỏ qua khi thiếu đầu vào (`when_missing: skip`), và trang báo cáo ghi rõ phép kiểm nào chưa chạy.

Việc phát sinh, Hiếu quyết:

| # | Phát hiện | Ảnh hưởng | Ai |
|---|---|---|---|
| 1 | Cả 102 episode khay S1 có bước nhảy tay vượt p99,9 của psi-data (0,0869 rad), chủ yếu ở chiều 20 và 27 (`wrist_yaw`) quanh bước 205–211; trung vị 23 bước vượt ngưỡng mỗi episode (mục 3.2) | Hoặc planner nội suy cổ tay quá thô, hoặc ngưỡng hiệu chỉnh trên teleop người không hợp với planner | DA-33 xem planner; nếu bước nhảy là chủ ý thì thêm ngưỡng theo nguồn vào `qa.yaml` (PR riêng) |
| 2 | `stats.json` của cả hai gói lệch `states.mean` (D4) | Design mục 10 ghi D4 là "chặn export": export Ψ₀ (DA-02) phải tính lại stats từ release, không chép `stats.json` của nguồn | DA-02 |
| 3 | psi-data không ghi seed (đã biết từ [psi-data.md](psi-data.md) V6), nên 99 item của release có `seed: null` | `build_release` cho episode người (`operator_kind = human`) đi qua khi không có seed, nhưng chặn episode máy sinh khi không có seed. **[Đề xuất]** giữ như vậy | Hiếu |
| 4 | Giấy phép `unknown` nên `combined_license` của release psi-data là `unknown` | Giới hạn của demo, như V9 | Đã chốt 3/11/2026 |

## 1. Lệnh

Code ở `rtx3060:~/denso-da03-pr2` được cài bằng `uv sync --frozen --no-dev --package flywheel-data --package flywheel-cli`. Gốc kho là `FW_ROOT=~/denso-da03-pr2/fwdata`. Dữ liệu vào gồm:

- psi-data `e78fb93`: giải nén từ `rtx3060:~/denso-s107/fwdata/psi-data/e78fb93/simple/G1WholebodyLocomotionPickBetweenTablesTeleop-v0.zip`, sau khi kiểm sha256 `6cdf9022…927586` khớp [psi-data.md](psi-data.md) mục 1.
- Release khay `tray_s1_0d84cc87b1e5` của DA-33: chép vào `fwdata/sources/`, sau khi kiểm cả 217 file khớp `release_manifest` của nó.

Script chạy qua `nohup setsid systemd-run --user --scope -p MemoryMax=8G -p MemorySwapMax=0`. Mỗi nguồn chạy bốn bước sau, `$W` là thư mục làm việc mà `ingest` in ra:

```bash
fw data ingest <dataset> --source-detail <psi_data|planner_wbc> --license unknown --data-class public --split train
fw data qa $W
fw data release $W
fw data report $W
```

Mặc định của các lệnh: `qa` đọc `configs/data/qa.yaml`, `configs/embodiments/g1.yaml` và `configs/splits/default.yaml`. `release` ghi vào `$FW_ROOT/releases/<source_detail>_<source_id>`. `report` ghi `report/dataset_report.json` và `report/index.html` vào `$W`. Mỗi lệnh ghi hai dòng `LedgerEntry` (một ước tính, một thực đo) vào `$FW_ROOT/sites/local/runs/g0-DA-03-20261104/<job_id>/ledger.jsonl`.

## 2. Thời gian và bộ nhớ

Wall và RSS đỉnh lấy từ `/usr/bin/time -v` của cả tiến trình, tính cả khởi động Python. Cột "sổ" là số giây ghi trong dòng thực đo của `LedgerEntry`, chỉ tính phần bên trong job. Cột "ước tính" là dòng ước tính ghi trước khi chạy, theo giả định trong `cli.ESTIMATE`.

| Lệnh | psi-data wall | psi-data RSS | psi-data sổ / ước tính | khay S1 wall | khay S1 RSS | khay S1 sổ / ước tính |
|---|---|---|---|---|---|---|
| `ingest` | 2,96 s | 319 MB | 2,10 / 1,26 s | 5,59 s | 350 MB | 4,79 / 2,96 s |
| `qa` | 2,00 s | 351 MB | 1,18 / 3,14 s | 2,47 s | 473 MB | 1,71 / 7,40 s |
| `release` | 0,84 s | 104 MB | 0,043 / 0,099 s | 0,87 s | 106 MB | 0,053 / 0,102 s |
| `report` | 0,77 s | 107 MB | 0,018 / 0,099 s | 0,90 s | 106 MB | 0,029 / 0,102 s |

Giả định ước tính ingest 2e-5 s mỗi frame là thấp hơn thực tế khoảng 1,6 lần. Giả định QA 5e-5 s mỗi frame thì cao hơn thực tế 2,7 đến 4,3 lần. Hai giả định này ghi trong mã và sửa được trong một PR sau. Tiền là 0 USD vì job chạy trên CPU của máy đội.

## 3. Kết quả

### 3.1 Ingest và QA

| Trường | psi-data | khay S1 |
|---|---|---|
| `source_id` | `src_33e3556ebc9bbaeb` | `src_61905ccdc2df03b6` |
| Episode, frame, file | 99, 62 764, 207 | 102, 148 013, 218 |
| Cột `index` khác LeRobot v2.1, đánh số lại (Q7) | 95 episode | 80 episode |
| Ngưỡng QA | `qa-1@95fbc11570b7` | `qa-1@95fbc11570b7` |
| `pass` / `flag` / `quarantine` / `reject` | 95 / 4 / 0 / 0 | 0 / 102 / 0 / 0 |
| Phép kiểm trượt (số episode) | `action_jump.arm` 1, `action_jump.target_yaw` 1, `action_jump.torso_rpy` 1, `action_jump.turn` 1 | `action_jump.arm` 102 |
| Chưa chạy (thiếu `ReplayReport`, hoặc thiếu seed) | `replay_kinematic`, `replay_dynamic`, `task_success`; `split_seed` (gói không ghi seed) | `replay_kinematic`, `replay_dynamic`, `replay_success` |

Ngưỡng `action_jump` là p99,9 của bước nhảy lớn nhất mỗi episode, hiệu chỉnh trên chính 99 episode psi-data (`fw data qa --calibrate`, ghi trong `qa.yaml`). Vì vậy 4 `flag` ở psi-data là kết quả mong đợi: mỗi nhóm có đúng một episode cao nhất vượt p99,9. Hướng `target_yaw` tính bước nhảy theo đường ngắn trên vòng tròn. Nếu không làm vậy, một lần đi qua ±π cho bước nhảy 6,24 rad giả.

### 3.2 Bước nhảy tay của khay S1

Cả 102 episode vượt ngưỡng nhóm `arm`. Bước nhảy lớn nhất mỗi episode rơi vào các bước 205–211, chủ yếu ở chiều 20 và 27 (`left_wrist_yaw`, `right_wrist_yaw`). Trung vị là 23 bước vượt ngưỡng mỗi episode. QA phát lại của DA-33 vẫn ghi 102/102 đạt ([synthetic-s1.md](tray/synthetic-s1.md)), nên bước nhảy này không làm hỏng rollout. Nhưng nó là phân bố action khác hẳn teleop người, và Ψ₀ sẽ học theo. QA chỉ `flag`, không loại.

### 3.3 Stats của dataset (D4)

QA tính lại `meta/stats.json` và `meta/episodes_stats.jsonl` từ frame. Phép tính dùng float32, giống `stats_block` của SIMPLE. So sánh chỉ ra một kết quả cho mỗi file và mỗi feature. Ngưỡng là 1e-5.

| Phép kiểm | psi-data | khay S1 |
|---|---|---|
| `stats_json.states` | **trượt**, 3,63e-4 ở `states.mean[31]` | **trượt**, 7,67e-4 ở `states.mean[6]` |
| `stats_json.action` | 0 | 0 |
| `episodes_stats.action` | 0 | 0 |
| `episodes_stats.timestamp` | 9,2e-7 (episode 18) | 1,8e-6 (episode 38) |

Không suy được vì sao chỉ `states.mean` lệch còn `action` thì khớp.

### 3.4 Release

| Trường | psi-data | khay S1 |
|---|---|---|
| `Release.id` | `rel_24363158e44e66b4` | `rel_9f32f33779c904f2` |
| `manifest_sha256` (16 ký tự đầu) | `47bbf09004096344` | `7a2b290d7642916f` |
| Episode, gồm, loại | 99, 99, 0 | 102, 102, 0 |
| `kind`, `is_root` | `teleop_demo`, true | `sim_rollout`, false |
| `seed_unknown` | 99 | 0 |
| `embodiment_id` | `g1_sonic_dwbc@1` | `g1_sonic_dwbc@1` |
| `split_plan_cfg_id` | `splits_081a3ee7eba6f748` | `splits_081a3ee7eba6f748` |
| `combined_license` | `unknown` | `unknown` |

`read_release` của cả hai thư mục đã tính lại hash của item và khớp với `manifest_sha256` và file `FROZEN`. Trang HTML nằm ở `fwdata/pipeline/<source_id>/report/index.html`.

### 3.5 Bản sao chấm lỗi của DA-27

Hai bản sao `bench-1e258c0a78ca` và `bench-d19e112835e3` được chép từ `rtx3060:~/denso-da27/fwdata/inject/copies/` vào `fwdata/sources/`. Mỗi bản chạy `ingest`, `qa`, `release` với `--source-detail psi_data`. Đáp án `DefectManifest` không được đọc (chỉ bộ chấm đọc). Bảng dưới chỉ là output QA của đội, không phải điểm recall của bộ lỗi cấy.

| Trường | `bench-1e258c0a78ca` | `bench-d19e112835e3` |
|---|---|---|
| `source_id` | `src_921954c2d2c28a8f` | `src_d13edebf5b2fb3b8` |
| Episode, frame | 99, 62 764 | 99, 62 643 |
| `pass` / `flag` / `quarantine` / `reject` | 95 / 4 / 0 / 0 | 77 / 6 / 0 / 16 |
| Phép kiểm trượt (số episode) | `action_jump` 4, như psi-data gốc | `joint_limits` 7; `finite_values`, `frame_index_contiguous`, `image_state_sync`, `split_seed`, `timestamp_step`, `video_rows_match` mỗi phép 3; `action_jump` 9 |
| D4 (`stats.json`, `episodes_stats.jsonl`) | khớp (0) | khớp (0) |
| `fw data release` | mã 2: 99 episode thuộc bản sao `bench-1e258c0a78ca` | mã 2: 99 episode thuộc bản sao `bench-d19e112835e3`, và 3 episode có seed 2000124, 2000587, 2000692 ngoài dải train (D5) |

Release từ chối liệt kê mọi lý do cùng lúc và không ghi thư mục release nào. Dòng thực đo của job vẫn được ghi, với ghi chú `failed: ReleaseRefused`. Ở cả hai bản sao, `stats.json` khớp frame, vì DA-27 tính lại stats khi ghi bản sao (DA-27 nhiệm vụ 9.7).

## 4. Lần chạy đầu bị thay

Lần chạy đầu (cùng ngày, trước commit `e3aad54`) cho psi-data 28 `reject` và khay S1 102 `reject`, tất cả do `joint_limits`. Mọi vi phạm đều nhỏ hơn hoặc bằng 1,02e-6 rad. Nguyên nhân có hai phần: sai số float, và `g1.yaml` làm tròn giới hạn URDF đến 5 chữ số (1,97222 so với 1,972222). Ngưỡng được đổi thành 1e-5 rad, kèm test `test_a_limit_rounded_in_the_layout_is_no_breach`. Cũng trong lần sửa đó, so sánh stats chuyển sang float32 vì float64 báo nhiễu 1,1e-5.

Kết quả lần đầu đã chuyển sang `fwdata/superseded-1/`, gồm các release `rel_0c48621c43418b7f` và `rel_512c65ecf9d47c2d`. Sổ chi phí chỉ ghi thêm. Vì vậy `g0-DA-03-20261104` có 44 dòng: 16 của lần đầu, 16 của lần cuối và 12 của hai bản sao ở mục 3.5. Dòng chạy thử nằm ở `g0-DA-03-trial`.

## 5. Khoảng trống của hợp đồng

PR này không thêm trường nào vào hợp đồng. Các chỗ thiếu sau ghi lại để Hiếu quyết có mở PR hợp đồng hay không:

| Hợp đồng | Thiếu | Hiện làm |
|---|---|---|
| `DatasetReport` | Độ dài episode, seed so với dải, stats theo nhóm action, kết quả D4 (design mục 6.5) | Nằm trong `DatasetSummary` (kiểu nội bộ của làn, file `qa/summary.json`) và chỉ hiện trên trang HTML |
| `v0.ReleaseManifest` | Chỉ có `release_id`, `frozen` | Thân release là `entities.Release` trong `release.json`, đọc bằng `read_release` |
| `QACheck` | Không có trường mã D | Mã D ghi trong `reasons` và trong `qa.yaml` |
| Design mục 10 | Không có mã cho thiếu lineage | Dùng D6 (nhãn sai), mức gần nhất |
