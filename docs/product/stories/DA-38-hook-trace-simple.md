# DA-38 · Hook ghi `TraceStep` và `CameraParams` từ MuJoCo trong rollout SIMPLE

## Trạng thái

| Trường | Giá trị |
|---|---|
| Trạng thái | Sẵn sàng (PO duyệt 3/11/2026) |
| Người làm | Hiếu |
| Làn | Adapter simulator (`flywheel-simple`) |
| Story PRD | Phần hook của story 3.1a (04 mục S2: "`SimpleSimulator`, hook ghi tín hiệu, `t_state`, `t_image`, tham số camera"); issue #31; 07 mục 2.4 (bản 1.1) |
| Nhãn | [Adapter] · `epic:3` · `gate:G1` · `area:sim` |
| Sprint | S2 · hạn merge **8/11/2026** (07 mục 2.4) |
| Ước lượng | 14 giờ (khoảng 10–18, ước lượng) |
| Phụ thuộc | Hợp đồng `TraceStep`, `CameraParams` và file mẫu (DA-25, PR #48, Long, 6/11). Môi trường SIMPLE của S1-02; task khay của DA-32; server Ψ₀ của S1-03. Không chặn ai ngoài DA-13 (R3–R5 trên trace thật) và DA-37 (cờ `check_success` thật) |

## Story

Là người làm làn Đánh giá, tôi muốn mỗi rollout SIMPLE của đội ghi một trace theo chu kỳ điều khiển (lệnh gửi, trạng thái đo, mốc thời gian) và tham số camera của lượt chạy, đọc thẳng từ MuJoCo, để DA-13 chạy được R3, R4, R5 và DA-37 hiệu chỉnh scorer trên dữ liệu thật thay vì file mẫu.

## Tiêu chí chấp nhận

1. Mỗi chu kỳ điều khiển của `eval-decoupled-wbc` (agent `psi0_decoupled_wbc`) ghi một `TraceStep` hợp lệ theo hợp đồng của DA-25, cho cả task hai bàn `simple/G1WholebodyLocomotionPickBetweenTablesTeleop-v0` và task khay `simple/G1WholebodyTrayTransferTeleop-v0`. Không fork SIMPLE.
2. Trường theo quyết định ở issue #31:
   - `t_state` là `data.time` của MuJoCo lúc đọc trạng thái.
   - `t_image` là thời gian mô phỏng của khung được đưa vào policy ở chu kỳ đó; chu kỳ không có khung mới thì `null`.
   - `cmd_upper = action[0:28]`; `meas_upper` là góc khớp đo, cùng thứ tự.
   - `cmd_lower = action[28:34] + action[35]`; `meas_lower` cùng thứ tự: góc hông đo, chiều cao gốc, vận tốc gốc trong hệ thân, yaw của gốc.
3. Mỗi camera mà policy dùng có một `CameraParams`, lấy từ `CameraCfg` của SIMPLE và model MuJoCo đang chạy: `fx`, `fy`, `cx`, `cy` ở đúng độ phân giải render, `pose` so với body gắn camera, quaternion (w, x, y, z). `reference_sha256` trỏ tới bản tham chiếu của commit SIMPLE đã ghim.
4. Mỗi episode ghi cờ `check_success` của SIMPLE (`sim_success`) cạnh trace.
5. Phần tính toán (dựng `TraceStep`, `CameraParams` từ mảng số) không import `simple` hay `mujoco`, và có test CPU với bộ giả chạy trong CI. Phần cài hook import `simple` có test gắn marker `sim`.
6. Trên `rtx3060`, mỗi task có một lượt chạy thật sinh ra tệp trace. Giá trị trong tệp đến từ sim, không hard-code (kiểm bằng phương sai khác 0 và khớp với `env._success`). Mỗi lượt chạy có dòng `LedgerEntry` trong `docs/g0/ledger/DA-38.csv`.

## Nhiệm vụ

- [x] 1. File story và phạm vi file
- [x] 2. Vector lệnh và đo, intrinsics và pose camera từ mảng số, test CPU (AC 2, 3, 5)
- [x] 3. Dựng `TraceStep`, `CameraParams` và bộ ghi trace theo quy ước tệp của hợp đồng, kèm cờ `sim_success` (AC 1, 3, 4)
  - [x] 3.1. Bộ ghi một thư mục `<trace_id>/` mỗi episode (`steps.jsonl`, `camera_params.jsonl`, `RolloutResult`), `trace_id` chung với client RTC, `reference_sha256` chép từ job spec (review PO 3/11/2026, B1; layout theo G1 của PR #48)
  - [x] 3.2. Ghim bản tham chiếu camera G0 của task hai bàn ở SIMPLE `b75c678` (review PO 3/11/2026, B3)
  - [x] 3.3. Entry module cài hook ở cấp module, đọc `job_id`, `run_plan_id`, thư mục job và bản tham chiếu từ job spec
  - [x] 3.4. Đọc lại tệp qua `TraceStep`, `CameraParams` khi PR #48 merge (test đang skip hoặc xfail tới lúc đó)
- [x] 4. Cài hook vào `eval-decoupled-wbc` (bọc env và agent), test `sim` (AC 1, 5)
- [ ] 5. Lượt chạy thật task hai bàn trên `rtx3060`, ghi ledger (AC 6)
- [ ] 6. Lượt chạy thật task khay trên `rtx3060`, ghi ledger (AC 6)
- [ ] 7. Tài liệu `docs/g0/trace.md`: cách chạy, ý nghĩa trường, giới hạn ở sim (AC 1–6)

## Phạm vi file

Theo 07 mục 3.1. pr-guard chặn PR sửa file ngoài danh sách này; file story luôn được sửa.

- `packages/flywheel-simple/src/flywheel_simple/trace/`, `packages/flywheel-simple/tests/trace/`
- `packages/flywheel-simple/pyproject.toml` (thêm phụ thuộc `flywheel-contracts`, `numpy`, `pydantic`), `uv.lock` (PO cho phép 3/11/2026)
- `scripts/g0/trace/`
- `docs/g0/trace.md`, `docs/g0/ledger/DA-38.csv`
- `docs/g0/camera-reference-two-table.yaml`, ghi chú bản tham chiếu camera trong `docs/g0/env-simple.md`, dòng seam của hook trong `tests/e2e/test_demo_seams.py` (PO yêu cầu ở review 3/11/2026, B1.4 và B3)

Ngoài phạm vi, làm PR docs riêng: dòng DA-38 trong 07 mục 2.2 và 2.4; ánh xạ story 3.1a sang DA-38 trong 04.

## Ghi chú cho người làm

- Trên master không có lớp `SimpleSim`. Vòng episode thật là `simple.cli.eval_decoupled_wbc._run_eval_worker` (SIMPLE @ `6d10628`):
  - `gym.make(env_id)` cho ra `SonicLocoManipEnv`, hoặc `TrayTransferEnv` của DA-32 (lớp con của nó).
  - Agent là `simple.baselines.psi0_decoupled_wbc`.
  - Mỗi lần `env.step` là một chu kỳ 50 Hz, và `_get_obs` render camera ngay sau phần vật lý.
- Hook được cài như `flywheel_simple.tray.run` đã thay module `time`: vá `gym.make` và class agent trong module eval, không fork SIMPLE.
- Client RTC của DA-19 không nằm trên đường này. Agent của SIMPLE chỉ gửi ảnh tới server khi hàng đợi action rỗng (mỗi chunk một lần).
- Lệnh `cmd_*` lấy từ dòng action 36 chiều của Ψ₀ mà agent dùng ở chu kỳ đó, không lấy từ `target_q` sau WBC.
- Đo hông: `joint_qpos[[13, 14, 12]]` (roll, pitch, yaw), như agent dựng state.
- Đo vận tốc: `qvel[0:3]` của freejoint là vận tốc trong hệ thế giới, cần xoay sang hệ yaw của thân.
- Ở sim, ảnh và trạng thái chung một đồng hồ, nên `t_image` bằng `t_state` ở các chu kỳ có khung và `dropped_frames` bằng 0. R4 trên sim dùng để nghiệm thu bộ phát hiện bằng ca cấy trễ (issue #31).
- Góp ý hợp đồng (quy ước tệp, `run_plan_id`, mật độ `t_image`, `dropped_frames`, `check_success`) đã đăng ở review của PR #48. Code theo bản hợp đồng được merge.
- Chạy trên `rtx3060` theo rule RAM của đội: tối đa 60 GB và 14 worker cho cả đội; mỗi job bọc trong `systemd-run --user --scope -p MemoryMax=…`. Dùng thư mục `~/denso-da38`.

## Kiểm thử

- `uv run pytest packages/flywheel-simple/tests/trace -m "not sim"` trong workspace.
- `pytest packages/flywheel-simple/tests/trace -m sim` trong môi trường SIMPLE của S1-02 (`fwdata/simple/.venv`).

## Người phụ trách

- Làm: Dương Đình Hiếu
- Duyệt và merge: Dương Đình Hiếu (người duy nhất, 07 mục 3.4)

## Change log

| Ngày | Nội dung | Người |
|---|---|---|
| 3/11/2026 | Tạo story cho phần hook của story 3.1a theo issue #31 và 07 mục 2.4 (bản 1.1) | PO (Hiếu) |
| 3/11/2026 | G1b: `RolloutResult` của episode ghi ở `<job_dir>/<trace_id>/rollout_result.json` | PO (Hiếu) |
| 3/11/2026 | Review PO: tách nhiệm vụ 3 thành 3.1–3.4; thêm bản tham chiếu camera, ghi chú `env-simple.md` và seam e2e vào phạm vi file (B1, B3) | PO (Hiếu) |

## Ghi chép khi làm

### 3/11/2026 · Kiểm hai rủi ro của cách cài hook (trước nhiệm vụ 4)

Probe chạy trên `rtx3060`, `~/denso-da38`, dùng venv SIMPLE của DA-33 (SIMPLE `6d10628`), mỗi lần bọc trong `systemd-run --scope -p MemoryMax=8G`. Script probe để ngoài repo.

**Rủi ro 1 · các tên cần vá hoặc cần đọc có tồn tại ở SIMPLE đã ghim không.** Có, cả 22 tên đều có:
- Trong `simple.cli.eval_decoupled_wbc`: `gym.make`, `_run_eval_worker`, `typer_main`.
- Trong `simple.baselines.psi0_decoupled_wbc`: `Psi0DecoupledWbcAgent` cùng các method `get_action`, `queue_action`, `reset`, và `STATE_SLICES`. `snake_to_pascal("psi0_decoupled_wbc") + "Agent"` cho đúng tên class này.
- Trong `simple.envs.sonic_loco_manip`: `SonicLocoManipEnv.step` và `_get_obs`.
- `CameraCfg.fx`, `CameraCfg.fy`.
- Thuộc tính đặt trong `__init__` (kiểm trong mã nguồn): `self._action_queue`, `self.client`, `self._success`, `self.mujoco`.

Ba file `eval_decoupled_wbc.py`, `psi0_decoupled_wbc.py`, `sonic_loco_manip.py` trong image docker SIMPLE mà S1-03 dùng (`38a674039f41`) có md5 trùng với venv `6d10628`. Trace của DA-38 và eval của S1-03 vì vậy chạy cùng một vòng eval.

Nhiệm vụ 4 sẽ chuyển kiểm này thành test `sim` trong `tests/trace/`, để khi nâng SIMPLE thì test báo lỗi thay vì hook im lặng không ghi.

**Rủi ro 2 · bản vá có sang được worker không.**
- `run_eval` chạy worker ngay trong tiến trình khi `num_workers == 1`.
- Khi `num_workers > 1`, nó tạo tiến trình con bằng `mp.get_context("spawn")`. Tiến trình con import lại module chính dưới tên `__mp_main__`, nên chỉ chạy phần cấp module; không chạy `main()`.

Kết quả đo:

| Vá ở đâu | `num_workers` | Bản vá có chạy trong worker | Env khay có đăng ký trong worker |
|---|---|---|---|
| Cấp module | 2 | Có (2/2 worker, `__name__ == "__mp_main__"`) | **Không** |
| Trong `main()` | 2 | **Không** (worker chạy `_run_eval_worker` gốc) | — |
| Cấp module | 1 | Có (cùng tiến trình) | Có |

Hệ quả:
1. Hook phải cài ở cấp module của entry point, không cài trong `main()`.
2. Tham số `agent_factory` của `run_eval` là tham số chết: nó chỉ được kiểm, không được truyền cho worker. Không dùng nó làm điểm gắn hook.
3. **Lỗi tiềm ẩn ngoài phạm vi DA-38.** `flywheel_simple.tray.run` gọi `register()` trong `main()`, nên `eval-decoupled-wbc` trên task khay với `--num-workers > 1` sẽ không tìm thấy env trong mọi worker. Lỗi này chặn eval song song của DA-34. Entry point của DA-38 sẽ đăng ký task khay ở cấp module. Sửa `tray/run.py` cần PR riêng, trong phạm vi DA-32.

### 3/11/2026 · Nhiệm vụ 2

- Phần dựng lớp `TraceStep`, `CameraParams` chuyển sang nhiệm vụ 3, vì phải chờ PR #48 merge. PO chốt Long sửa G1, G2 trong #48 trước khi merge. Nhiệm vụ 2 chỉ gồm phần tính toán thuần (`trace/signals.py`, `trace/camera.py`), không import `flywheel.contracts.trace`.
- Intrinsics đọc từ model MuJoCo đã dựng (`cam_fovy`, `cam_sensorsize`, `cam_intrinsic`) cộng kích thước render, không chép từ `CameraCfg`.
  - Lý do: khi `CameraCfg` không có `intrinsics` (cả hai task), SIMPLE đặt `fovy = 2·atan(H / 2fy)`. Ảnh render vì vậy có fx = fy = (H/2)/tan(fovy/2) và tâm ảnh ở giữa.
  - `CameraCfg.fx` lại tính từ chiều rộng, nên hai số chỉ trùng nhau qua cách SIMPLE dựng camera.
- Nhánh camera có `sensor_size` là phép nghịch đảo đúng cách SIMPLE ghi `focal_pixel` và `principal_pixel`. Dấu của điểm chính theo trục y trong MuJoCo chưa kiểm bằng ảnh render. Cả hai task không dùng nhánh này. **[Đề xuất]**
- `reference_sha256` là sha256 của tập camera đã chuẩn hóa: sắp theo `uid`, làm tròn 1e-9, JSON có khóa sắp xếp. Bản tham chiếu tính từ cấu hình của commit SIMPLE đã ghim ở nhiệm vụ 3. **[Đề xuất]** → **[Đã chốt 3/11/2026, PO, Q3]** hàm này chỉ dùng để ghim bản tham chiếu; `CameraParams.reference_sha256` của episode là hash đã ghim, chép từ job spec, không phải hash của bộ camera của chính episode.
- `STATE_SLICES` chép từ SIMPLE `6d10628`. Nhiệm vụ 4 có test `sim` so bản chép này với SIMPLE.

### 3/11/2026 · Nhiệm vụ 4: hook và test `sim`

- Ba điểm gắn, đều là tên cấp module mà worker eval của SIMPLE tra lúc chạy:
  - `eval_module.gym`, thay bằng proxy có `make` bọc env. Mỗi lần `reset` mở một episode và đọc camera.
  - `Psi0DecoupledWbcAgent`, thay bằng lớp con. Mỗi lần `get_action` ghi một chu kỳ, kèm dòng action Ψ₀ mà agent lấy ra khỏi hàng đợi.
  - `_append_eval_stats_line`. Dòng `episode_<i>: <bool>` của SIMPLE kết thúc episode và cho cờ `check_success`.
- Các bước ổn định đầu episode gọi env gốc, không qua env đã bọc, nên không được ghi.
- `t_state` và trạng thái đo được đọc ở đầu chu kỳ: `mjData` chưa đổi kể từ lần `step` trước, nên đây đúng là trạng thái policy dùng để ra quyết định.
  - `cmd` của chu kỳ k so với `meas` của chu kỳ k là lệnh so với trạng thái lúc ra lệnh.
  - Độ trễ bám lệnh, nếu cần, do DA-13 dịch trục khi đọc trace. **[Đề xuất]**
- Test `sim` chạy vòng eval thật của SIMPLE: env, WBC và MuJoCo thật; server Ψ₀ được thay bằng stub trả chunk giữ nguyên tư thế (16 dòng), nên không cần GPU. Điều kiện chạy:
  - Hai bàn: tập `simple-eval` dr-level-0 của psi-data (S1-03 đã tải, chỉ đọc).
  - Khay: episode cha của DA-35 `parents-1103b/shard-00`.
- **Phát hiện ngoài phạm vi (DA-34): eval khay chưa đọc được tập điều kiện LeRobot.**
  - `simple/datasets/lerobot.py:get_episode_lerobot` (SIMPLE `6d10628`) có một dòng FIXME đòi `environment_config["dr_state_dict"]["scene"]["uid"]`.
  - Dataset khay của DA-33 và DA-35 không có khóa này, nên `eval-decoupled-wbc --data-format lerobot` lỗi `KeyError` trên mọi episode khay.
  - Test `sim` dùng một shim chỉ trong test: đọc episode như SIMPLE nhưng bỏ dòng đó. Env khay vốn dựng lại episode từ `seed` và `level`.
  - Lượt chạy thật trên task khay (nhiệm vụ 6) cần PO chốt cách xử lý.
  - **[Đã chốt 3/11/2026, PO]** Vá trong `tray/run.py`: thay `get_episode_lerobot` bằng bản bỏ qua dòng FIXME khi thiếu `dr_state_dict`, cài ở cấp module để có hiệu lực trong worker spawn. Làm bằng hotfix riêng sau PR #65. Nhiệm vụ 6 chạy sau khi hotfix đó merge; khi đó bỏ shim trong test `sim`.
- Kết quả test `sim` trên `rtx3060` (3/11/2026): **4 passed** trong 637 s.
  - Episode hai bàn mất 27 s. Episode khay mất 605 s, phần lớn do `get_episode_lerobot` của SIMPLE giải mã toàn bộ khung video của episode điều kiện (khoảng 1600 khung).
  - Mỗi task kiểm:
    - 40 chu kỳ, `t_state` tăng đúng 0,02 s mỗi chu kỳ;
    - `t_image` chỉ có ở chu kỳ 0, 16, 32 và bằng `t_state` ở đó;
    - `cmd_upper` của chu kỳ 0 bằng `meas_upper` (stub giữ tư thế), tức thứ tự hai bên khớp nhau;
    - trạng thái đo có thay đổi, chiều cao gốc trong khoảng 0,5–0,9 m;
    - camera `head_stereo_left` 640×360 có fy khớp `CameraCfg` tới 1e-6, quaternion chuẩn hóa;
    - `episode_0` và cờ `sim_success` khớp dòng trong `eval_stats.txt`.
- Entry point cài hook ở cấp module (cho worker spawn) đi cùng bộ ghi hợp đồng ở nhiệm vụ 3 và lượt chạy thật ở nhiệm vụ 5.
- 3/11/2026, sau khi PR #67 merge: test `sim` bỏ shim, gọi `flywheel_simple.tray.run.prepare()` (đăng ký env khay và thay bộ đọc điều kiện của SIMPLE). Kết quả chạy lại trên `rtx3060`: 4 passed trong 495 s.

### 3/11/2026 · Nhiệm vụ 3.1, 3.2: tệp của episode và bản tham chiếu camera (review PO, B1 và B3)

**Layout tệp** (`flywheel_simple/trace/files.py`). Một lượt `eval-decoupled-wbc` là một job; mỗi episode là một trace, nằm trong thư mục mang tên `trace_id` của nó. **[Đã chốt 3/11/2026, PO, G1 trên PR #48]**: `TraceRef.uri` trỏ thư mục `<trace_id>/` gồm `steps.jsonl` và `camera_params.jsonl`; `CameraParams` có thêm `trace_id`.

| Tệp | Nội dung | Ai đọc |
|---|---|---|
| `<job_dir>/<trace_id>/steps.jsonl` | Một `TraceStep` mỗi chu kỳ, có `trace_id` | DA-13 (R3, R4, thiếu tín hiệu) |
| `<job_dir>/<trace_id>/camera_params.jsonl` | Một `CameraParams` mỗi dòng, mỗi camera policy thấy một dòng, có `trace_id` | DA-13 (R5) |
| `<job_dir>/<trace_id>/rollout_result.json` | Một `RolloutResult` (`flywheel.contracts.v0`): `sim_success`, `infra_status`, `trace_ref` (`trace_id`, `uri` là thư mục `<trace_id>/`, sha256 của `steps.jsonl`), `camera_params_hash`. Tên tệp **Đã chốt 3/11/2026 [Hiếu]** (G1b, chuyển qua phiên Orchetration), giữ sau hằng `RESULT_NAME` | DA-13 (R6 đọc `infra_status`), scorer |
| `<job_dir>/rtc.jsonl` | `RTCInferenceRecord` của client RTC (DA-19), một tệp mỗi job, nối với trace qua `trace_id`. Hook không ghi tệp này | DA-13 (R1, R2) |

- `infra_status` lấy theo `RolloutResult.infra_status`: `ok` khi SIMPLE ghi dòng `episode_<i>: <bool>` cho episode; `simulator_error` khi episode bị cắt trước dòng đó (tiến trình sim chết, env đóng giữa chừng). **[Đề xuất]**
- **Việc cho DA-13:** reader của #71 đang tìm `trace.jsonl`, `camera_params.json`, `episode.json` và `rtc.jsonl` trong cùng một thư mục. Theo G1 nó phải đọc `steps.jsonl`, `camera_params.jsonl` (JSONL) và tệp `RolloutResult` trong `<trace_id>/`, và đọc `<job_dir>/rtc.jsonl` (thư mục cha) lọc theo `trace_id`.
- **`trace_id`** là `<job_id>-<12 ký tự hex ngẫu nhiên>`, sinh lúc env `reset`, nên không trùng giữa các worker spawn của cùng job. SIMPLE reset env trước rồi mới reset agent, nên agent đã bọc có `fw_trace_id` của episode ngay lúc `reset`. Client RTC chạy trong agent (DA-23) phải gọi `RTCClient.reset(agent.fw_trace_id)`; khi đó `rtc.jsonl`, `steps.jsonl` và `camera_params.jsonl` cùng một `trace_id`. Hiện agent của SIMPLE chưa dùng client RTC, nên lượt chạy của nhiệm vụ 5, 6 chưa có `rtc.jsonl`.
- **`reference_sha256`** (Q3): bộ ghi nhận hash đã ghim từ job spec và chép vào mọi `CameraParams` của episode, và vào `camera_params_hash` của `RolloutResult`. Không có hash thì không ghi `camera_params.jsonl`, và R5 ra CHƯA RÕ. Bộ ghi từ chối chuỗi không phải sha256.
- Tệp ghi bằng JSON thuần: venv SIMPLE không có gói `flywheel`. Test CPU đọc lại tệp `RolloutResult` qua hợp đồng v0. Test cho `TraceStep` và `CameraParams` skip cho tới khi #48 merge. Chạy với `flywheel.contracts` của #48 (`5b373e2`) thêm trường `trace_id` của G1 vào `CameraParams` qua `PYTHONPATH`: `test_files.py` và test seam e2e của hook 10 passed. Với `5b373e2` chưa sửa, test `CameraParams` lỗi vì thừa `trace_id`, tức test sẽ báo nếu #48 merge thiếu G1.

**Bản tham chiếu camera task hai bàn** (`docs/g0/camera-reference-two-table.yaml`, B3):
- `scripts/g0/trace/pin_camera_reference.py` chạy vòng eval thật của SIMPLE `b75c678` một episode 2 bước, với server Ψ₀ thay bằng stub giữ tư thế. Script đọc camera bằng `camera_values` của hook và ghi YAML có dạng khối `r5` của `configs/eval/diagnosis/system.yaml`: `reference_sha256` và `cameras` theo `uid`.
- Chạy trên `rtx3060` ngày 3/11/2026, 23:14–23:16, trong `~/denso-da38` (bản sao SIMPLE checkout ở `b75c678`, venv của DA-33), `systemd-run MemoryMax=12G`, không dùng GPU cho policy. Kết quả: 2 camera (`head_stereo_left`, `head_stereo_right`), 640×360, fx = fy = 224,0664, tâm (320, 180), gắn `eye_in_head`.
- `reference_sha256 = fc7f9c90ebbf8c4662fd70e58de5aed668c0fbc5ccfbbd951dce705729cdeea2`. Test CPU tính lại hash từ file YAML và so với giá trị này.
- Chạy lại sau khi thêm `trace_id` vào hook (23:20): script ghim ra đúng các giá trị cũ; test `sim` hai bàn ở `b75c678` 3 passed trong 49 s (task khay không chạy lại lần này).
- Task khay chưa có bản tham chiếu; lượt chạy khay không có `camera_params.jsonl` cho tới khi ghim.
- Không sửa `system.yaml`; phiên DA-13 chép khối này vào.
- **Rủi ro cho khung 5/11:** CycloneDDS của SIMPLE dùng domain 0. Lượt ghim báo `Failed to find a free participant index for domain 0`, tức đang có tiến trình khác cùng máy giữ domain này. Hai lượt eval chạy cùng lúc trên `rtx3060` có thể nhận nhầm topic của nhau. Trước khi chạy nhiệm vụ 5, 6 cần kiểm xem lượt chạy có độc chiếm máy không, hoặc đặt `DOMAIN_ID` riêng. **[Đề xuất]**

### 4/11/2026 · Nhiệm vụ 3.4: đọc lại qua hợp đồng trên master

- PR #48 merge thành #79 (master `3f02b1a`) với G1, G1b, `CameraParams.trace_id` và tên 28/7 chiều. Nhánh merge `origin/master` (không rebase, không force-push).
- Hợp đồng trên master bắt `run_plan_id` bắt đầu bằng `g0-` theo G2 (`g0-<story>-<yyyymmdd>`). Hai id trong test (`g0-DA-38-test`, `g0-DA-38-seams`) bị từ chối; đổi sang `g0-DA-38-20261104`.
- Kết quả: `test_files.py` không còn skip (mọi dòng `steps.jsonl` là `TraceStep`, mọi dòng `camera_params.jsonl` là `CameraParams`, `rollout_result.json` là `RolloutResult`); test seam của hook qua thay vì xfail.

### 4/11/2026 · Nhiệm vụ 3.3: entry module

- `python -m flywheel_simple.trace.run <env_id> psi0_decoupled_wbc [tham số của eval-decoupled-wbc]`. Job spec đi qua biến môi trường vì worker spawn kế thừa môi trường, không nhận tham số: `FW_TRACE_JOB_DIR`, `FW_JOB_ID`, `FW_RUN_PLAN_ID` (bắt buộc; `g0-…` phải theo G2), `FW_CAMERA_REFERENCE_SHA256` (không có thì không ghi `camera_params.jsonl`).
- Hook cài khi import, dưới cả `__main__` và `__mp_main__` (rủi ro 2 ở trên). Module gọi `prepare()` của `tray/run.py` cho task khay. `adapter_info.version` là `simple@<HEAD của checkout SIMPLE>`.
- Venv SIMPLE không có gói `flywheel`, nên `signals`, `files`, `run` giữ bản chép của tên trong hợp đồng: `UPPER_BODY`, `LOWER_BODY`, ba tên tệp, mẫu `G0_RUN_PLAN_ID`. Test CPU `test_run.py` giữ bản chép bằng hợp đồng.
- Kiểm tận nguồn thứ tự 28 chiều: `STATE_SLICES` lấy từ `WHOLE_BODY_JOINTS` của `g1_sonic` (SIMPLE `b75c678`) đúng các khớp của `UPPER_BODY`, theo đúng thứ tự (tay trái thumb, middle, index; tay phải thumb, index, middle), và `WAIST_RPY` là roll, pitch, yaw. Có test `sim` cho điều này.
- Test `sim` mới chạy entry module trong vòng eval thật (stub thay server Ψ₀). Kết quả: đúng một thư mục `<trace_id>/` với 40 dòng `steps.jsonl`, hai camera mang hash đã ghim, `trace_ref.uri` là thư mục đó, `infra_status` là `ok`. Trên `rtx3060` 4/11/2026 00:34, SIMPLE `b75c678`, task hai bàn: 5 passed, 2 skipped (khay chưa đặt dữ liệu; test hợp đồng vì venv không có `flywheel`) trong 53 s.
- Chưa chạy với `--num-workers > 1`; lượt chạy thật của nhiệm vụ 5 sẽ chạy.
