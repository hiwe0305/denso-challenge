# Phân tích gói psi-data (Q1, V1, V6, V9)

_Ngày 3/11/2026. Story [S1-07](../product/stories/S1-07-phan-tich-psi-data.md), cổng G0. Làm lại từ PR #24 của Thông (nhánh `S1-07-psi-data` @ `e96da77`): giữ cách đọc cấu trúc gói, bỏ mọi số gán cứng. Mọi số trong file này do [`scripts/g0/inspect_psi_data.py`](../../scripts/g0/inspect_psi_data.py) in ra, chạy trên máy `rtx3060`; bảng trong file là output của lệnh, chép nguyên. Số nào script không đo được thì ghi là giả định hoặc "không suy được"._

## Kết luận

- **Q1:** N_teleop của task hai bàn là **99**, cả 99 episode đạt QA sơ bộ; điểm cuối lưới HE giữ ở 80 demo. F1: `BendPickTeleop` N_teleop = 97, `BendPickMP` 100 episode sinh tự động. Gói không có cờ thành công (mục 3).
- **V1:** LeRobot `v2.1`, 50 Hz, `action` **36 chiều thật, không chiều đệm, không khớp chân**; `states` 32 chiều, Ψ₀ đệm state lên 36 (chỉ số 32–35). Camera `observation.images.egocentric` 360×640. Bảng 36 dòng `index, name, group, masked` ở mục 2.
- **V6:** episode ghi `layout`, `dr_cfgs` và `dr_state_dict` (vị trí ban đầu), không ghi seed. Dải seed của `simple-eval` không suy được số, nhưng ở mức 0 và 1 episode eval i có vị trí ban đầu trùng episode train i đến từng bit (mục 4). Dải của đội theo [`configs/splits/default.yaml`](../../configs/splits/default.yaml).
- **V9:** psi-data và psi-model không ghi giấy phép (`license = unknown`); `data_class = public` theo quyết định của Hiếu ngày 2/11/2026. Cảnh HSSD và vật GraspNet trong video là phi thương mại (mục 5). Thư hỏi PSI Lab ở mục 5.

Việc phát sinh cho người khác, Hiếu quyết:

| # | Phát hiện | Ảnh hưởng | Ai |
|---|---|---|---|
| 1 | Chiều action 34 là `vyaw` liên tục trong `[-1, 1]`, không phải `turning_flag` 0/1 như chú thích Ψ₀ và comment 3/11 trên #24 | `configs/embodiments/g1.yaml`; T4, O4 của DA-08 | Hiếu (DA-01), Châu |
| 2 | Chiều 31 (`base_height_command`) hằng số 0,74 trong gói hai bàn; F1 có 4–10 chiều hằng số | T5, T6 của DA-08 phải loại theo phương sai đích, không theo `masked` | Châu |
| 3 | Tập eval trên `rtx3060:~/denso-s103` là bản ở `main` (`de140d6`, 4 mức, vị trí robot khác), không phải `e78fb93` | Số eval S1-03 so với gói train đã ghim | Hiếu chốt bản eval |
| 4 | Eval mức 0, 1 dùng lại vị trí ban đầu của 10 episode train đầu | Số eval của tác giả không đo trên điều kiện mới; dev và holdout của đội rời cả hai | Hiếu, Châu |
| 5 | HSSD CC-BY-NC-4.0 và GraspNet CC BY-NC-SA 4.0 nằm trong video psi-data | Rủi ro giấy phép nếu demo bị coi là dùng thương mại; khác với `data_class` | Hiếu |

## 1. Tải và sha256 (AC 1)

Revision ghim: `USC-PSI-Lab/psi-data` @ `e78fb93cc28912a3031a10b8656d32d7f0a2b867` (commit ngày 14/09/2026). Script lấy kích thước và `lfs.oid` của từng file từ API cây thư mục của Hugging Face ở đúng revision này, tải file qua `resolve/<sha>/<đường dẫn>`, băm sha256 trong lúc tải rồi so với `lfs.oid`. Dữ liệu nằm ngoài git, ở `rtx3060:~/denso-s107/fwdata/psi-data/e78fb93/<đường dẫn trên HF>`; script ghi kết quả vào `fetch.json` cạnh đó.

```bash
python3 -I scripts/g0/inspect_psi_data.py fetch --revision e78fb93 --out fwdata/psi-data/e78fb93 \
    simple/G1WholebodyLocomotionPickBetweenTablesTeleop-v0.zip \
    simple-eval/G1WholebodyLocomotionPickBetweenTablesTeleop-v0.zip \
    simple/G1WholebodyBendPickTeleop-v0.zip simple/G1WholebodyBendPickMP-v0.zip \
    simple-eval/G1WholebodyBendPickTeleop-v0.zip simple-eval/G1WholebodyBendPickMP-v0.zip
```

| Đường dẫn trên HF | Kích thước (B) | sha256 | Khớp `lfs.oid` của HF |
|---|---|---|---|
| `simple/G1WholebodyLocomotionPickBetweenTablesTeleop-v0.zip` | 202,607,109 | `6cdf9022c23649f68d2faf418a97c47c01aca9d1fac27e9af366116d69927586` | có |
| `simple-eval/G1WholebodyLocomotionPickBetweenTablesTeleop-v0.zip` | 480,532 | `8a4b0ff7d068967dac8baec2c4a4deca4f644215a1ee15e921739f3dfe90e7e0` | có |
| `simple/G1WholebodyBendPickTeleop-v0.zip` | 41,839,721 | `f14802cd95a387f70df2d7601d2f7b804570e431377980acfffee9e6160dce3c` | có |
| `simple/G1WholebodyBendPickMP-v0.zip` | 43,314,543 | `8f1df4dc44c27526029d02d2883343a5cb0f98e9cb84d214e7fef57c331cad6a` | có |
| `simple-eval/G1WholebodyBendPickTeleop-v0.zip` | 382,543 | `b532ece10d05ef22c549006f936599fc0954e4eaac7c5d16cec3bc30e294f548` | có |
| `simple-eval/G1WholebodyBendPickMP-v0.zip` | 1,630,050 | `6bcdb9ddfa1d3f851144f585bda19507ad9efb53e71514dad98836fcefadc5e2` | có |

Sáu file, tổng 290.269.326 B trên đĩa. Tải và băm mất 16 s, RSS đỉnh 23 MB.

Ghi chú:

- HF có hai gói hai bàn. Gói dùng ở đây là `simple/…` (đúng gói của S1-07 và của Ψ₀). Gói `simple-teleop/G1WholebodyLocomotionPickBetweenTablesTeleop-v0.zip` (222.159.491 B, `lfs.oid` `cbe6dddc…`) không dùng.
- Bản cũ đã có trên máy, băm bằng `inspect_psi_data.py hash`:

  | File | Kích thước (B) | sha256 | So với `e78fb93` |
  |---|---|---|---|
  | laptop `fwdata/psi-data/simple/G1WholebodyLocomotionPickBetweenTablesTeleop-v0.zip` | 202,607,109 | `6cdf9022…927586` | trùng |
  | `rtx3060:~/denso-s103/fwdata/simple-eval/G1WholebodyLocomotionPickBetweenTablesTeleop-v0.zip` | 689,559 | `7d215cf3…c28dee` | **khác**: đây là bản ở `main` hiện tại (`de140d67…`, API trả 689.559 B), không phải bản ở `e78fb93` |

  Tập eval S1-03 đang dùng trên `rtx3060` là bản mới hơn revision ghim. Mục 4 so hai bản.
- `rtx3060:~/denso-da33/fwdata/psi-data/simple/G1WholebodyLocomotionPickBetweenTablesTeleop-v0/` chỉ có `meta/info.json`, không phải gói đầy đủ.

## 2. Cấu trúc LeRobot và layout action 36 chiều (AC 3 · V1)

```bash
python3 -I scripts/g0/inspect_psi_data.py layout <gói>.zip \
    --psi0-slices psi0_simple_init.py --psi0-stage3 finetune-simple-psi0.sh \
    --names-from tray_s1_0d84cc87b1e5/meta/action_layout.json --json layout-<gói>.json
```

Đầu vào của bảng, mỗi cột một nguồn:

| Cột | Nguồn |
|---|---|
| shape, dtype, names | `meta/info.json` của gói. `info.json` ghi `action` và `states` là shape `[-1]`, không đặt tên chiều; số chiều đo trên parquet |
| key `modality.json`, abs/rel | `meta/modality.json` của gói: chỉ số đầu, cuối, cờ `absolute` của từng nhóm |
| Ψ₀ `ACTION_SLICES_36D`, chú thích Ψ₀ | `src/psi/data/simple/__init__.py` của Ψ₀ @ `cda3fdf` (`git show`, sha256 file `ddb135a2…`): danh sách `ACTION_SLICES_36D` và khối chú thích layout ở đầu file |
| pad-action-dim, pad-state-dim | bản cuối của `scripts/train/psi0/finetune-simple-psi0.sh` (`git show 2830f93^:…`, sha256 `729fd4b9…`; script bị xóa trước `cda3fdf`, xem [psi0-logging.md](psi0-logging.md)) |
| name, group | `meta/action_layout.json` của release khay DA-33 `tray_s1_0d84cc87b1e5` (sha256 `29c2b281…`): tên khớp `WHOLE_BODY_JOINTS` của `g1_sonic` theo thứ tự của `postprocess_psi0_sonic.py` của SIMPLE, cùng script tác giả dùng để tạo gói psi-data. **Giả định:** gói psi-data đi qua đúng script đó; dữ liệu không mang tên chiều để kiểm trực tiếp |
| min, max, số giá trị khác nhau | đo trên mọi khung của mọi episode |

Kết quả cho gói hai bàn (output của lệnh, chép nguyên):

`G1WholebodyLocomotionPickBetweenTablesTeleop-v0.zip`: codebase_version `v2.1`, fps 50, robot_type `g1`, 62,764 khung

| Trường | dtype | shape trong `info.json` | names |
|---|---|---|---|
| `observation.images.egocentric` | video | [360, 640, 3] | ['height', 'width', 'channel'] |
| `observation.hand_joints` | float32 | [14] | ['hand_joints'] |
| `observation.arm_joints` | float32 | [14] | ['arm_joints'] |
| `observation.leg_joints` | float32 | [15] | ['leg_joints'] |
| `observation.prev_torso_rpy` | float32 | [3] | ['prev_roll', 'prev_pitch', 'prev_yaw'] |
| `observation.prev_height` | float32 | [1] | ['prev_height'] |
| `states` | float32 | [-1] | None |
| `action` | float32 | [-1] | None |
| `timestamp` | float32 | [1] | None |
| `frame_index` | int64 | [1] | None |
| `episode_index` | int64 | [1] | None |
| `index` | int64 | [1] | None |
| `next.done` | bool | [1] | None |
| `task_index` | int64 | [1] | None |

Đo trên parquet: `action` 36 chiều, `states` 32 chiều. Ψ₀ stage 3: pad-action-dim 36, pad-state-dim 36; chỉ số state được đệm: [32, 33, 34, 35].

| index | name | group | masked | key `modality.json` | Ψ₀ `ACTION_SLICES_36D` | chú thích Ψ₀ | min | max | số giá trị khác nhau |
|---|---|---|---|---|---|---|---|---|---|
| 0 | `left_hand_thumb_0_joint` | left_hand | false | `left_hand` (abs) | left_hand_thumb | hand qpos absolute (L_thumb 3, L_index 2, L_middle 2, R_hand 7) | 0 | 0.5 | 7 |
| 1 | `left_hand_thumb_1_joint` | left_hand | false | `left_hand` (abs) | left_hand_thumb | hand qpos absolute (L_thumb 3, L_index 2, L_middle 2, R_hand 7) | 0 | 0.7 | 6 |
| 2 | `left_hand_thumb_2_joint` | left_hand | false | `left_hand` (abs) | left_hand_thumb | hand qpos absolute (L_thumb 3, L_index 2, L_middle 2, R_hand 7) | 0 | 0.7 | 6 |
| 3 | `left_hand_middle_0_joint` | left_hand | false | `left_hand` (abs) | left_hand_index | hand qpos absolute (L_thumb 3, L_index 2, L_middle 2, R_hand 7) | -1.5 | 0 | 6 |
| 4 | `left_hand_middle_1_joint` | left_hand | false | `left_hand` (abs) | left_hand_index | hand qpos absolute (L_thumb 3, L_index 2, L_middle 2, R_hand 7) | -1.5 | 0 | 6 |
| 5 | `left_hand_index_0_joint` | left_hand | false | `left_hand` (abs) | left_hand_middle | hand qpos absolute (L_thumb 3, L_index 2, L_middle 2, R_hand 7) | -0.6 | 0 | 6 |
| 6 | `left_hand_index_1_joint` | left_hand | false | `left_hand` (abs) | left_hand_middle | hand qpos absolute (L_thumb 3, L_index 2, L_middle 2, R_hand 7) | -1.5 | 0 | 6 |
| 7 | `right_hand_thumb_0_joint` | right_hand | false | `right_hand` (abs) | right_hand | hand qpos absolute (L_thumb 3, L_index 2, L_middle 2, R_hand 7) | -0.5 | 6.931e-19 | 2,066 |
| 8 | `right_hand_thumb_1_joint` | right_hand | false | `right_hand` (abs) | right_hand | hand qpos absolute (L_thumb 3, L_index 2, L_middle 2, R_hand 7) | -0.7 | 1.108e-16 | 2,061 |
| 9 | `right_hand_thumb_2_joint` | right_hand | false | `right_hand` (abs) | right_hand | hand qpos absolute (L_thumb 3, L_index 2, L_middle 2, R_hand 7) | -0.7 | 1.108e-16 | 2,061 |
| 10 | `right_hand_index_0_joint` | right_hand | false | `right_hand` (abs) | right_hand | hand qpos absolute (L_thumb 3, L_index 2, L_middle 2, R_hand 7) | -2.217e-16 | 1.5 | 2,062 |
| 11 | `right_hand_index_1_joint` | right_hand | false | `right_hand` (abs) | right_hand | hand qpos absolute (L_thumb 3, L_index 2, L_middle 2, R_hand 7) | -2.217e-16 | 1.5 | 2,060 |
| 12 | `right_hand_middle_0_joint` | right_hand | false | `right_hand` (abs) | right_hand | hand qpos absolute (L_thumb 3, L_index 2, L_middle 2, R_hand 7) | -4.085e-18 | 1 | 2,040 |
| 13 | `right_hand_middle_1_joint` | right_hand | false | `right_hand` (abs) | right_hand | hand qpos absolute (L_thumb 3, L_index 2, L_middle 2, R_hand 7) | -2.217e-16 | 1.5 | 2,060 |
| 14 | `left_shoulder_pitch_joint` | left_arm | false | `left_arm` (abs) | left_arm | arm qpos absolute (L_arm 7, R_arm 7) | -0.4883 | 0.2558 | 62,728 |
| 15 | `left_shoulder_roll_joint` | left_arm | false | `left_arm` (abs) | left_arm | arm qpos absolute (L_arm 7, R_arm 7) | 0.19 | 0.3588 | 22,699 |
| 16 | `left_shoulder_yaw_joint` | left_arm | false | `left_arm` (abs) | left_arm | arm qpos absolute (L_arm 7, R_arm 7) | -0.5471 | 0.5091 | 62,696 |
| 17 | `left_elbow_joint` | left_arm | false | `left_arm` (abs) | left_arm | arm qpos absolute (L_arm 7, R_arm 7) | -0.3432 | 0.1913 | 62,742 |
| 18 | `left_wrist_roll_joint` | left_arm | false | `left_arm` (abs) | left_arm | arm qpos absolute (L_arm 7, R_arm 7) | -0.3595 | 0.2125 | 62,652 |
| 19 | `left_wrist_pitch_joint` | left_arm | false | `left_arm` (abs) | left_arm | arm qpos absolute (L_arm 7, R_arm 7) | -0.353 | 0.3993 | 62,722 |
| 20 | `left_wrist_yaw_joint` | left_arm | false | `left_arm` (abs) | left_arm | arm qpos absolute (L_arm 7, R_arm 7) | -0.447 | 0.4283 | 62,648 |
| 21 | `right_shoulder_pitch_joint` | right_arm | false | `right_arm` (abs) | right_arm | arm qpos absolute (L_arm 7, R_arm 7) | -0.6371 | 0.1457 | 62,628 |
| 22 | `right_shoulder_roll_joint` | right_arm | false | `right_arm` (abs) | right_arm | arm qpos absolute (L_arm 7, R_arm 7) | -0.7684 | -0.19 | 53,290 |
| 23 | `right_shoulder_yaw_joint` | right_arm | false | `right_arm` (abs) | right_arm | arm qpos absolute (L_arm 7, R_arm 7) | -1.065 | 0.615 | 62,724 |
| 24 | `right_elbow_joint` | right_arm | false | `right_arm` (abs) | right_arm | arm qpos absolute (L_arm 7, R_arm 7) | -0.8479 | 0.3547 | 62,660 |
| 25 | `right_wrist_roll_joint` | right_arm | false | `right_arm` (abs) | right_arm | arm qpos absolute (L_arm 7, R_arm 7) | -1.03 | 0.8703 | 62,696 |
| 26 | `right_wrist_pitch_joint` | right_arm | false | `right_arm` (abs) | right_arm | arm qpos absolute (L_arm 7, R_arm 7) | -0.4294 | 0.7532 | 62,724 |
| 27 | `right_wrist_yaw_joint` | right_arm | false | `right_arm` (abs) | right_arm | arm qpos absolute (L_arm 7, R_arm 7) | -0.5148 | 0.9712 | 62,706 |
| 28 | `waist_roll_joint` | waist | false | `rpy` (abs) | — | waist roll/pitch/yaw absolute | -0.1682 | 0.1399 | 62,726 |
| 29 | `waist_pitch_joint` | waist | false | `rpy` (abs) | — | waist roll/pitch/yaw absolute | -0.04533 | 0.1569 | 62,574 |
| 30 | `waist_yaw_joint` | waist | false | `rpy` (abs) | — | waist roll/pitch/yaw absolute | -0.1328 | 0.4661 | 62,735 |
| 31 | `base_height_command` | base_height | false | `height` (abs) | — | base_height absolute (m; reference 0.75) | 0.74 | 0.74 | 1 |
| 32 | `navigate.vx` | navigate | false | `torso_vx` (rel) | — | vx relative (m/s, base frame) | -0.5 | 0.5 | 3,987 |
| 33 | `navigate.vy` | navigate | false | `torso_vy` (rel) | — | vy relative | -0.5 | 0.5 | 5,807 |
| 34 | `navigate.vyaw` | navigate | false | `torso_vyaw` (rel) | — | turning_flag discrete (0/1) | -1 | 1 | 51,104 |
| 35 | `navigate.target_yaw` | navigate | false | `target_yaw` (abs) | — | target_yaw absolute (world heading, rad) | -3.138 | 3.141 | 20,482 |

Chiều action hằng số trên mọi khung (1 giá trị): [31]

Kết luận:

- **Action có 36 chiều thật, không chiều nào là đệm** (`masked = false` cả 36): parquet có đúng 36 chiều, bằng `pad-action-dim` của Ψ₀, nên `pad_to_len` không thêm gì. Không có khớp chân: thân dưới nhận lệnh qua chiều 31–35. Bảng này thay mục "pad36" của bản #24 (12 chân, 3 thắt lưng, 14 tay, 2 bàn tay, 5 đệm), vốn sai.
- **4 chiều đệm là của state**: `states` có 32 chiều (`modality.json`: `left_hand` 0–6, `right_hand` 7–13, `left_arm` 14–20, `right_arm` 21–27, `rpy` 28–30, `height` 31), Ψ₀ đệm lên 36 nên chỉ số state 32–35 là đệm.
- **Chiều 34 là `vyaw` liên tục, không phải cờ rời rạc.** Chú thích Ψ₀ ghi `turning_flag discrete (0/1)`, comment ngày 3/11 trên #24 cũng ghi vậy. Dữ liệu cho 51.104 giá trị khác nhau trong `[-1, 1]`, và `modality.json` gọi chiều này là `torso_vyaw`, tương đối. Khớp với ghi chú trong [export.py](../../packages/flywheel-simple/src/flywheel_simple/tray/export.py) của DA-33: bộ WBC đọc chiều này như cờ quay, còn PICO và bộ lập kế hoạch gửi `vyaw` (rad/s). Báo Hiếu: `configs/embodiments/g1.yaml` và DA-08 nên coi chiều 34 là liên tục.
- **Chiều 3–6 của tay trái:** Ψ₀ gọi 3:5 là `index`, 5:7 là `middle`; tên của SIMPLE theo thứ tự `postprocess_psi0_sonic.py` là `middle` ở 3–4, `index` ở 5–6 (DA-33 đã ghi). Tay phải thứ tự cái, trỏ, giữa.
- **Chiều hằng số không phải chiều đệm.** Gói hai bàn có chiều 31 (`base_height_command`) bằng 0,74 ở mọi khung; tay trái (0–6) chỉ có 6–7 giá trị, tức teleop gửi vài tư thế cố định. Với T5 và T6 của DA-08: phương sai đích bằng 0 ở chiều 31 là thật, không phải lỗi; cần loại theo phương sai đích, không theo `masked`.
- Đơn vị lấy từ chú thích Ψ₀, chưa kiểm độc lập: qpos theo rad, `base_height` theo m (mốc 0,75), `vx`, `vy` theo m/s trong hệ thân, `target_yaw` theo rad trong hệ thế giới. Giới hạn khớp không có trong gói; sẽ đến từ MJCF `g1_sonic` qua `configs/embodiments/g1.yaml` (DA-01), không áp cho chiều 32–34.
- F1 cùng cấu trúc: cả hai gói `v2.1`, 50 Hz, `action` 36, `states` 32, camera 360×640, cùng `modality.json`. Chiều hằng số: `BendPickTeleop` 0–6 (tay trái không dùng), 32, 33, 35; `BendPickMP` 32–35 (không di chuyển thân). Bảng đầy đủ trong `layout-<gói>.md` trên `rtx3060`.

## 3. QA sơ bộ và N_teleop (AC 2 · Q1)

Script đọc từng parquet trong zip và kiểm 7 phép trên mỗi episode. Ngưỡng độ dài 2–60 s là **giả định** của S1-07 (không có trong spec hay gói); độ dài thật nằm trong 9,6–25,0 s (mục 6), xa cả hai ngưỡng. Gói không có trường thành công nào (`episodes.jsonl` và các cột parquet đều được quét tìm `success`), nên phép kiểm cờ thành công không áp được; thành công thật chỉ kiểm được bằng phát lại (DA-17).

```bash
python3 -I scripts/g0/inspect_psi_data.py qa <gói>.zip --min-seconds 2 --max-seconds 60 --json qa-<gói>.json
```

Gói hai bàn:

`G1WholebodyLocomotionPickBetweenTablesTeleop-v0.zip`: `info.json` 99 episode, 62,764 khung; parquet 99 episode, 62,764 khung; `episodes.jsonl` 99 dòng; video 99

| Phép kiểm | Đạt |
|---|---|
| Số khung parquet = `length` trong `episodes.jsonl` | 99/99 |
| `frame_index` = 0, 1, …, T−1 | 99/99 |
| `timestamp` tăng nghiêm ngặt | 99/99 |
| Không NaN hay Inf ở mọi cột số thực | 99/99 |
| Độ dài trong [2 s, 60 s] (ngưỡng giả định) | 99/99 |
| `next.done` chỉ đúng ở khung cuối | 99/99 |
| Có file video của episode | 99/99 |
| Cờ thành công | không có trường nào |
| **Đạt mọi phép kiểm** | **99/99** |

Lệch lớn nhất giữa `timestamp` và `frame_index / fps`: 0 s

Gói F1:

`G1WholebodyBendPickTeleop-v0.zip`: `info.json` 97 episode, 17,623 khung; parquet 97 episode, 17,623 khung; `episodes.jsonl` 97 dòng; video 97

| Phép kiểm | Đạt |
|---|---|
| Số khung parquet = `length` trong `episodes.jsonl` | 97/97 |
| `frame_index` = 0, 1, …, T−1 | 97/97 |
| `timestamp` tăng nghiêm ngặt | 97/97 |
| Không NaN hay Inf ở mọi cột số thực | 97/97 |
| Độ dài trong [2 s, 60 s] (ngưỡng giả định) | 97/97 |
| `next.done` chỉ đúng ở khung cuối | 97/97 |
| Có file video của episode | 97/97 |
| Cờ thành công | không có trường nào |
| **Đạt mọi phép kiểm** | **97/97** |

Lệch lớn nhất giữa `timestamp` và `frame_index / fps`: 0 s

`G1WholebodyBendPickMP-v0.zip`: `info.json` 100 episode, 15,509 khung; parquet 100 episode, 15,509 khung; `episodes.jsonl` 100 dòng; video 100

| Phép kiểm | Đạt |
|---|---|
| Số khung parquet = `length` trong `episodes.jsonl` | 100/100 |
| `frame_index` = 0, 1, …, T−1 | 100/100 |
| `timestamp` tăng nghiêm ngặt | 100/100 |
| Không NaN hay Inf ở mọi cột số thực | 100/100 |
| Độ dài trong [2 s, 60 s] (ngưỡng giả định) | 100/100 |
| `next.done` chỉ đúng ở khung cuối | 100/100 |
| Có file video của episode | 100/100 |
| Cờ thành công | không có trường nào |
| **Đạt mọi phép kiểm** | **100/100** |

Lệch lớn nhất giữa `timestamp` và `frame_index / fps`: 0 s

| Gói | Nguồn | N đạt QA sơ bộ |
|---|---|---|
| `simple/G1WholebodyLocomotionPickBetweenTablesTeleop-v0` | teleop | **N_teleop = 99** |
| `simple/G1WholebodyBendPickTeleop-v0` (F1) | teleop | **N_teleop = 97** |
| `simple/G1WholebodyBendPickMP-v0` (F1) | MP, sinh tự động | 100 (không tính vào N_teleop) |

**Kết luận cho lưới HE (design mục 7.3):** N_teleop của task hai bàn là 99 ≥ 80, nên điểm cuối của lưới giữ ở 80 demo; không cần báo động (< 40).

Kiểm rằng phép kiểm không rỗng: một zip giả 5 episode cấy lần lượt NaN, `timestamp` lùi, episode 1 s, `next.done` giữa chừng và thiếu video. Script bắt đúng 4 episode lỗi, mỗi episode đúng phép kiểm đã cấy, và cho 1/5 đạt.

## 4. Layout, seed và tham số ngẫu nhiên hóa (AC 4 · V6 phần dữ liệu)

Lệnh `seeds` quét mọi file JSON và JSONL trong `meta/` của từng dataset (gồm cả chuỗi JSON `environment_config` lồng trong `episodes.jsonl`) để tìm khóa chứa `seed`, và quét tên cột parquet. Gói eval chứa nhiều dataset (mỗi mức một thư mục `dr-level-*`); script đọc từng cái. Bản eval ở `main` (`de140d6`) chép từ `~/denso-s103` để so.

```bash
python3 -I scripts/g0/inspect_psi_data.py seeds --train <gói train>.zip <gói eval>.zip ... --json seeds-<task>.json
```

Task hai bàn:

| Gói (sha256) | Dataset | Episode | Khóa `seed` trong meta | Cột `seed` | `split` | `dr_level` | Có `layout` | Có `dr_state_dict` | `dr_cfgs` khác nhau |
|---|---|---|---|---|---|---|---|---|---|
| `e78fb93/simple/G1WholebodyLocomotionPickBetweenTablesTeleop-v0.zip` (`6cdf9022`) | `G1WholebodyLocomotionPickBetweenTablesTeleop-v0` | 99 | không | không | train | 0 | 99/99 | 99/99 | 2 |
| `e78fb93/simple-eval/G1WholebodyLocomotionPickBetweenTablesTeleop-v0.zip` (`8a4b0ff7`) | `G1WholebodyLocomotionPickBetweenTablesTeleop-v0/dr-level-0` | 10 | không | không | train | 0 | 10/10 | 10/10 | 1 |
| `e78fb93/simple-eval/G1WholebodyLocomotionPickBetweenTablesTeleop-v0.zip` (`8a4b0ff7`) | `G1WholebodyLocomotionPickBetweenTablesTeleop-v0/dr-level-1` | 10 | không | không | train | 0 | 10/10 | 10/10 | 1 |
| `e78fb93/simple-eval/G1WholebodyLocomotionPickBetweenTablesTeleop-v0.zip` (`8a4b0ff7`) | `G1WholebodyLocomotionPickBetweenTablesTeleop-v0/dr-level-2` | 10 | không | không | train | 0 | 10/10 | 10/10 | 1 |
| `main-de140d6/simple-eval/G1WholebodyLocomotionPickBetweenTablesTeleop-v0.zip` (`7d215cf3`) | `G1WholebodyLocomotionPickBetweenTablesTeleop-v0/dr-level-0` | 10 | không | không | train | 0 | 10/10 | 10/10 | 1 |
| `main-de140d6/simple-eval/G1WholebodyLocomotionPickBetweenTablesTeleop-v0.zip` (`7d215cf3`) | `G1WholebodyLocomotionPickBetweenTablesTeleop-v0/dr-level-1` | 10 | không | không | train | 0 | 10/10 | 10/10 | 1 |
| `main-de140d6/simple-eval/G1WholebodyLocomotionPickBetweenTablesTeleop-v0.zip` (`7d215cf3`) | `G1WholebodyLocomotionPickBetweenTablesTeleop-v0/dr-level-2` | 10 | không | không | train | 0 | 10/10 | 10/10 | 1 |
| `main-de140d6/simple-eval/G1WholebodyLocomotionPickBetweenTablesTeleop-v0.zip` (`7d215cf3`) | `G1WholebodyLocomotionPickBetweenTablesTeleop-v0/dr-level-hard` | 10 | không | không | train | 0 | 10/10 | 10/10 | 1 |

So với gói train `e78fb93/simple/G1WholebodyLocomotionPickBetweenTablesTeleop-v0.zip`: số episode i có vị trí ban đầu trùng đúng từng số với episode i của train, theo từng vật có mặt ở mọi episode của `dr_state_dict.spatial` (vật gây nhiễu đổi theo episode nên không so).

| Gói | Dataset | Episode | Vị trí trùng theo vật | `dr_state_dict` trùng cùng chỉ số | `dr_state_dict` có trong train |
|---|---|---|---|---|---|
| `e78fb93/simple-eval/G1WholebodyLocomotionPickBetweenTablesTeleop-v0.zip` | `G1WholebodyLocomotionPickBetweenTablesTeleop-v0/dr-level-0` | 10 | `0` 10, `container_0` 10, `g1_sonic` 10 | 0 | 0 |
| `e78fb93/simple-eval/G1WholebodyLocomotionPickBetweenTablesTeleop-v0.zip` | `G1WholebodyLocomotionPickBetweenTablesTeleop-v0/dr-level-1` | 10 | `0` 10, `container_0` 10, `g1_sonic` 10 | 0 | 0 |
| `e78fb93/simple-eval/G1WholebodyLocomotionPickBetweenTablesTeleop-v0.zip` | `G1WholebodyLocomotionPickBetweenTablesTeleop-v0/dr-level-2` | 10 | `0` 0, `container_0` 0, `g1_sonic` 10 | 0 | 0 |
| `main-de140d6/simple-eval/G1WholebodyLocomotionPickBetweenTablesTeleop-v0.zip` | `G1WholebodyLocomotionPickBetweenTablesTeleop-v0/dr-level-0` | 10 | `0` 10, `container_0` 10, `g1_sonic` 0 | 0 | 0 |
| `main-de140d6/simple-eval/G1WholebodyLocomotionPickBetweenTablesTeleop-v0.zip` | `G1WholebodyLocomotionPickBetweenTablesTeleop-v0/dr-level-1` | 10 | `0` 10, `container_0` 10, `g1_sonic` 0 | 0 | 0 |
| `main-de140d6/simple-eval/G1WholebodyLocomotionPickBetweenTablesTeleop-v0.zip` | `G1WholebodyLocomotionPickBetweenTablesTeleop-v0/dr-level-2` | 10 | `0` 0, `container_0` 0, `g1_sonic` 0 | 0 | 0 |
| `main-de140d6/simple-eval/G1WholebodyLocomotionPickBetweenTablesTeleop-v0.zip` | `G1WholebodyLocomotionPickBetweenTablesTeleop-v0/dr-level-hard` | 10 | `0` 0, `container_0` 0, `g1_sonic` 0 | 0 | 0 |

F1 (`BendPickTeleop` so với eval của nó; `BendPickMP` so với eval của nó):

So với gói train `e78fb93/simple/G1WholebodyBendPickTeleop-v0.zip`: số episode i có vị trí ban đầu trùng đúng từng số với episode i của train, theo từng vật có mặt ở mọi episode của `dr_state_dict.spatial` (vật gây nhiễu đổi theo episode nên không so).

| Gói | Dataset | Episode | Vị trí trùng theo vật | `dr_state_dict` trùng cùng chỉ số | `dr_state_dict` có trong train |
|---|---|---|---|---|---|
| `e78fb93/simple-eval/G1WholebodyBendPickTeleop-v0.zip` | `G1WholebodyBendPickTeleop-v0/dr-level-0` | 10 | `0` 10, `g1_sonic` 10 | 0 | 0 |
| `e78fb93/simple-eval/G1WholebodyBendPickTeleop-v0.zip` | `G1WholebodyBendPickTeleop-v0/dr-level-1` | 10 | `0` 10, `g1_sonic` 10 | 0 | 0 |
| `e78fb93/simple-eval/G1WholebodyBendPickTeleop-v0.zip` | `G1WholebodyBendPickTeleop-v0/dr-level-2` | 10 | `0` 0, `g1_sonic` 10 | 0 | 0 |

So với gói train `e78fb93/simple/G1WholebodyBendPickMP-v0.zip`: số episode i có vị trí ban đầu trùng đúng từng số với episode i của train, theo từng vật có mặt ở mọi episode của `dr_state_dict.spatial` (vật gây nhiễu đổi theo episode nên không so).

| Gói | Dataset | Episode | Vị trí trùng theo vật | `dr_state_dict` trùng cùng chỉ số | `dr_state_dict` có trong train |
|---|---|---|---|---|---|
| `e78fb93/simple-eval/G1WholebodyBendPickMP-v0.zip` | `G1WholebodyBendPickMP-v0/dr-level-0` | 10 | `0` 10, `g1_wholebody` 10 | 0 | 0 |
| `e78fb93/simple-eval/G1WholebodyBendPickMP-v0.zip` | `G1WholebodyBendPickMP-v0/dr-level-1` | 10 | `0` 10, `g1_wholebody` 10 | 0 | 0 |
| `e78fb93/simple-eval/G1WholebodyBendPickMP-v0.zip` | `G1WholebodyBendPickMP-v0/dr-level-2` | 10 | `0` 0, `g1_wholebody` 10 | 0 | 0 |

Kết luận:

- **Episode có ghi layout và tham số ngẫu nhiên hóa, không ghi seed.** Mỗi dòng `episodes.jsonl` có `environment_config` gồm `dr_cfgs` (cấu hình bộ ngẫu nhiên hóa: vùng đặt robot, vật, thùng, vật gây nhiễu, ánh sáng, cảnh `hssd:scene6`), `dr_state_dict` (giá trị đã rút cho episode đó, gồm vị trí ban đầu) và `layout`. Không có khóa hay cột nào chứa `seed` trong mọi gói và mọi mức eval.
- **Gói eval:** ở `e78fb93`, cả ba task có 3 mức (`dr-level-0`, `-1`, `-2`) × 10 episode; episode eval chỉ có 1 khung (trạng thái ban đầu để dựng điều kiện). Bản ở `main` của task hai bàn có thêm mức `dr-level-hard`, 4 × 10. Trường `metadata.split` ghi `train` và `metadata.dr_level` ghi `0` ở mọi mức, nên mức chỉ đọc được từ tên thư mục.
- **Dải hạt giống của `simple-eval`: không suy được số.** Bản #24 ghi `0..24`; số đó gán cứng trong script cũ, không có trong gói. Điều suy được, **suy luận** từ bảng trên: ở mức 0 và 1, episode eval thứ i có vị trí ban đầu của robot, vật và thùng trùng đến từng bit với episode train thứ i (10/10 ở cả ba task); ở mức 2 chỉ vị trí robot còn trùng. SpatialDR rút vị trí theo một thứ tự cố định từ bộ sinh số ngẫu nhiên của episode, nên trùng đến từng bit nghĩa là episode eval i và episode train i bắt đầu từ cùng một luồng ngẫu nhiên, tức cùng seed. Hệ quả: ở mức 0 và 1, tập eval của tác giả đặt vật và thùng đúng chỗ như 10 demo train đầu tiên (vật gây nhiễu, ánh sáng, vật liệu khác). Số đo trên eval của tác giả vì vậy không phải số trên điều kiện mới; dải `dev` và `holdout` của đội phải rời cả train lẫn eval của tác giả.
- **Dải hạt giống của đội** **[Đã chốt]** (Hiếu, 2/11/2026): một bảng chung cho mọi task và mọi nguồn, [`configs/splits/default.yaml`](../../configs/splits/default.yaml): `train` `[0, 1_000_000)`, `dev` `[1_000_000, 1_001_000)`, `holdout` `[2_000_000, 2_001_000)`; không có split `gate` riêng. Seed của tác giả, theo suy luận trên là số nhỏ quanh chỉ số episode, rơi vào `train`. Bản #24 đề xuất dải `1000..1999`, `2000..2999`, `9000..9999` và split `gate`; đã bỏ.
- Hai bộ eval khác nhau: bản `main` mà S1-03 đang dùng có vị trí robot khác hẳn train (0/10) nhưng giữ vật và thùng (10/10 ở mức 0, 1). Báo Hiếu chốt bản eval nào là bản của đội: `e78fb93` (khớp gói train đã ghim) hay `main`.

## 5. Giấy phép (AC 5 · V9)

Tài sản mà gói thật sự dùng, đọc từ `environment_config` của mọi episode:

```bash
python3 -I scripts/g0/inspect_psi_data.py assets <gói>.zip ...
```

| Gói | Dataset | `res_id` của vật | Cảnh (`room_choices`) | Thư viện vật liệu |
|---|---|---|---|---|
| `e78fb93/simple/G1WholebodyLocomotionPickBetweenTablesTeleop-v0.zip` | `G1WholebodyLocomotionPickBetweenTablesTeleop-v0` | `graspnet1b`, `objects` | `hssd:scene6` | `vMaterials_2` |
| `e78fb93/simple-eval/G1WholebodyLocomotionPickBetweenTablesTeleop-v0.zip` | `G1WholebodyLocomotionPickBetweenTablesTeleop-v0/dr-level-0` | `graspnet1b`, `objects` | `hssd:scene6` | `vMaterials_2` |
| `e78fb93/simple-eval/G1WholebodyLocomotionPickBetweenTablesTeleop-v0.zip` | `G1WholebodyLocomotionPickBetweenTablesTeleop-v0/dr-level-1` | `graspnet1b`, `objects` | `hssd:scene6` | `vMaterials_2` |
| `e78fb93/simple-eval/G1WholebodyLocomotionPickBetweenTablesTeleop-v0.zip` | `G1WholebodyLocomotionPickBetweenTablesTeleop-v0/dr-level-2` | `graspnet1b`, `objects` | `hssd:scene6` | `vMaterials_2` |
| `e78fb93/simple/G1WholebodyBendPickTeleop-v0.zip` | `G1WholebodyBendPickTeleop-v0` | `graspnet1b` | `hssd:scene0` | `vMaterials_2` |
| `e78fb93/simple/G1WholebodyBendPickMP-v0.zip` | `G1WholebodyBendPickMP-v0` | `graspnet1b` | `hssd:scene0` | `vMaterials_2` |
| `e78fb93/simple-eval/G1WholebodyBendPickTeleop-v0.zip` | `G1WholebodyBendPickTeleop-v0/dr-level-0` | `graspnet1b` | `hssd:scene0` | `vMaterials_2` |
| `e78fb93/simple-eval/G1WholebodyBendPickTeleop-v0.zip` | `G1WholebodyBendPickTeleop-v0/dr-level-1` | `graspnet1b` | `hssd:scene0` | `vMaterials_2` |
| `e78fb93/simple-eval/G1WholebodyBendPickTeleop-v0.zip` | `G1WholebodyBendPickTeleop-v0/dr-level-2` | `graspnet1b` | `hssd:scene0` | `vMaterials_2` |
| `e78fb93/simple-eval/G1WholebodyBendPickMP-v0.zip` | `G1WholebodyBendPickMP-v0/dr-level-0` | `graspnet1b` | `hssd:scene0` | `vMaterials_2` |
| `e78fb93/simple-eval/G1WholebodyBendPickMP-v0.zip` | `G1WholebodyBendPickMP-v0/dr-level-1` | `graspnet1b` | `hssd:scene0` | `vMaterials_2` |
| `e78fb93/simple-eval/G1WholebodyBendPickMP-v0.zip` | `G1WholebodyBendPickMP-v0/dr-level-2` | `graspnet1b` | `hssd:scene0` | `vMaterials_2` |

Gói không nhắc Objaverse; vật lấy từ GraspNet-1Billion (`graspnet1b`) và một thùng của SIMPLE (`objects`), cảnh từ HSSD, vật liệu từ NVIDIA vMaterials 2. Video egocentric trong gói là ảnh render các tài sản này.

Bảng kiểm ngày 3/11/2026. Trường license của Hugging Face đọc qua `https://huggingface.co/api/<loại>/<repo>` (`cardData.license`, thẻ `license:*`, file `LICENSE`/`README.md` gốc); GitHub qua `gh api repos/<repo>/license`.

| Tài sản | Nguồn đã kiểm | Ngày kiểm | Thấy gì | Kết luận |
|---|---|---|---|---|
| `USC-PSI-Lab/psi-data` (gói, gồm video) | HF API, revision `e78fb93` và `main` `de140d6` | 3/11/2026 | Không `cardData`, không thẻ `license`, không `LICENSE` hay `README.md` ở gốc | `license = unknown`. **`data_class = public`** **[Đã chốt]** (Hiếu, 2/11/2026, theo design 27/10 mục 8.4 và CLAUDE.md): Colab dùng được cho fine-tune. Thư hỏi tác giả vẫn gửi |
| `USC-PSI-Lab/psi-model` (checkpoint) | HF API, `main` `76febdc` | 3/11/2026 | Không `cardData`, không thẻ `license`, không `LICENSE` ở gốc | `license = unknown` cho trọng số. Giấy phép Apache 2.0 của mã Ψ₀ không tự áp cho checkpoint |
| Mã Ψ₀ (`physical-superintelligence-lab/Psi0`) | GitHub, file `LICENSE` | 3/11/2026 | Apache License 2.0, "Copyright 2026 PSI-lab, USC" (GitHub báo `NOASSERTION` vì file có thêm dòng bản quyền) | Dùng và sửa được, giữ thông báo bản quyền |
| SIMPLE (`physical-superintelligence-lab/SIMPLE`) | GitHub, file `license.md` | 3/11/2026 | MIT License, "Copyright (c) 2025-2026 The SIMPLE Authors" | Dùng và tích hợp được, giữ thông báo bản quyền. Chỉ áp cho mã; tài sản SIMPLE tải về theo giấy phép riêng của từng nguồn |
| Cảnh HSSD (`hssd:scene6` cho hai bàn, `hssd:scene0` cho F1) | HF API `hssd/hssd-hab` @ `4369cb9` | 3/11/2026 | `cc-by-nc-4.0` | Phi thương mại, phải ghi nguồn |
| Vật GraspNet-1Billion (`graspnet1b`) | [graspnet.net/datasets.html](https://graspnet.net/datasets.html) | 3/11/2026 | Trang ghi CC BY-NC-SA 4.0, "free non-commercial use"; dùng thương mại phải liên hệ tác giả. Repo `graspnet/graspnetAPI` là MIT nhưng chỉ cho mã | Phi thương mại, ghi nguồn, chia sẻ cùng điều kiện |
| NVIDIA vMaterials 2 (vật liệu bàn) | Tìm trên web | 3/11/2026 | Điều khoản là EULA hiện khi cài, cần tài khoản NVIDIA Developer; không thấy bản công khai | Chưa kiểm được. Không phân phối lại file `.mdl`; gói chỉ chứa đường dẫn và ảnh render |
| Objaverse | HF API `allenai/objaverse` @ `5566370` | 3/11/2026 | `odc-by` cho bộ dữ liệu, giấy phép riêng theo từng vật | Không áp: gói không tham chiếu Objaverse |

Báo Hiếu: HSSD và GraspNet đều phi thương mại, và video trong psi-data là ảnh render của hai nguồn này. Quyết định `data_class = public` ngày 2/11 nói về việc được gửi lên Colab, không nói về quyền dùng thương mại. Nếu kết quả demo cho DENSO được coi là dùng thương mại thì đây là rủi ro giấy phép riêng, ngoài `data_class`; thư dưới đây hỏi cả điểm này.

### Thư hỏi PSI Lab (cho Hiếu gửi)

Viết bằng tiếng Anh vì người nhận ở USC. Hiếu sửa phần chữ ký và kênh gửi (issue GitHub của Ψ₀ hoặc email tác giả liên hệ trong paper).

```text
Subject: License of USC-PSI-Lab/psi-data and psi-model checkpoints, and how simple-eval was built

Dear PSI Lab team,

We are ilovephysicalintelligence, a five-person team in the DENSO Factory Hacks
challenge. We build a data flywheel around Psi0 (arXiv:2603.12263) and SIMPLE:
when the policy fails in simulation we choose which data to collect next. We use
your released data and checkpoints as they are, pinned to psi-data revision
e78fb93cc28912a3031a10b8656d32d7f0a2b867 and Psi0 commit cda3fdf, mainly the
two-table task G1WholebodyLocomotionPickBetweenTablesTeleop-v0 and
G1WholebodyBendPickTeleop-v0 / BendPickMP-v0.

We could not find a license for the dataset or for the checkpoints on Hugging
Face, so we would like to ask:

1. Under which license are the psi-data bundles released (parquet, videos,
   meta), and the checkpoints in USC-PSI-Lab/psi-model? May we fine-tune the
   checkpoints, show the results in a demo to DENSO judges, and publish our
   benchmark numbers with attribution?
2. The episodes render HSSD scenes (CC BY-NC 4.0) and GraspNet-1Billion objects
   (CC BY-NC-SA 4.0). Do you consider the psi-data videos to carry those
   non-commercial terms? Is a demo inside an industry-sponsored challenge within
   the use you intend?
3. In simple-eval at e78fb93, episode i of dr-level-0 and dr-level-1 starts with
   exactly the robot, object and container positions of training episode i of
   the same task (bit for bit, 10/10, on all three tasks we checked). Were the
   eval conditions generated with the same seeds as the first training
   episodes? Which seeds did you use for training and for simple-eval?
4. The simple-eval bundle at main (de140d6) adds dr-level-hard and changes the
   robot start positions. Which revision do you report numbers on?

Thank you for releasing Psi0, SIMPLE and the data.

Best regards,
<name>, on behalf of team ilovephysicalintelligence
```

## 6. Thống kê mô tả (AC 6)

Cho báo cáo dataset (design mục 6.5). Độ dài đọc từ `episodes.jsonl`, đã khớp với số dòng parquet ở mục 3. Vị trí ban đầu đọc từ `dr_state_dict.spatial`, là giá trị bộ ngẫu nhiên hóa đã rút cho episode; vị trí bàn đọc từ `layout.actors`. Robot là `robot_cfg.uid`, vật cần gắp là `dr_state_dict.target.uid`, thùng là `container_0`.

```bash
python3 -I scripts/g0/inspect_psi_data.py stats <gói hai bàn>.zip <F1 teleop>.zip <F1 MP>.zip --json stats.json
```

| Dataset | Episode | Khung | Độ dài (s): min · p10 · trung vị · p90 · max · TB ± ĐLC | Tỉ lệ thành công |
|---|---|---|---|---|
| `G1WholebodyLocomotionPickBetweenTablesTeleop-v0` | 99 | 62,764 | 9.64 · 10.88 · 11.96 · 15.05 · 24.96 · 12.68 ± 2.18 | không suy được |
| `G1WholebodyBendPickTeleop-v0` | 97 | 17,623 | 2.70 · 2.94 · 3.50 · 4.41 · 5.78 · 3.63 ± 0.61 | không suy được |
| `G1WholebodyBendPickMP-v0` | 100 | 15,509 | 3.08 · 3.10 · 3.10 · 3.12 · 3.14 · 3.10 ± 0.01 | không suy được |

Vị trí ban đầu (m, hệ thế giới, từ `dr_state_dict.spatial`): min … max (TB ± ĐLC)

| Dataset | Vật | x | y |
|---|---|---|---|
| `G1WholebodyLocomotionPickBetweenTablesTeleop-v0` | robot | -0.650 … -0.630 (-0.639 ± 0.005) | 0.000 … 0.000 (0.000 ± 0.000) |
| `G1WholebodyLocomotionPickBetweenTablesTeleop-v0` | target | -0.329 … -0.310 (-0.319 ± 0.006) | -0.039 … 0.040 (-0.002 ± 0.025) |
| `G1WholebodyLocomotionPickBetweenTablesTeleop-v0` | container | -2.500 … -2.450 (-2.472 ± 0.014) | 0.150 … 0.249 (0.199 ± 0.029) |
| `G1WholebodyBendPickTeleop-v0` | robot | -0.660 … -0.602 (-0.630 ± 0.015) | 0.000 … 0.000 (0.000 ± 0.000) |
| `G1WholebodyBendPickTeleop-v0` | target | -0.369 … -0.320 (-0.347 ± 0.015) | -0.080 … -0.041 (-0.061 ± 0.012) |
| `G1WholebodyBendPickMP-v0` | robot | -0.659 … -0.600 (-0.628 ± 0.017) | 0.000 … 0.000 (0.000 ± 0.000) |
| `G1WholebodyBendPickMP-v0` | target | -0.320 … -0.290 (-0.306 ± 0.009) | -0.080 … -0.040 (-0.060 ± 0.012) |

Bàn (tâm, m, từ `layout.actors`): min … max

| Dataset | Bàn | x | y | z |
|---|---|---|---|---|
| `G1WholebodyLocomotionPickBetweenTablesTeleop-v0` | `table` | 0.000 … 0.000 | 0.250 … 0.250 | 0.600 … 0.600 |
| `G1WholebodyLocomotionPickBetweenTablesTeleop-v0` | `table2` | -2.940 … -2.940 | 0.000 … 0.000 | 0.600 … 0.600 |
| `G1WholebodyBendPickTeleop-v0` | `table` | 0.200 … 0.200 | 0.000 … 0.000 | 0.350 … 0.350 |
| `G1WholebodyBendPickMP-v0` | `table` | 0.300 … 0.300 | 0.000 … 0.000 | -0.050 … -0.050 |

| Dataset | Vật cần gắp | Thùng | Số vật gây nhiễu mỗi episode |
|---|---|---|---|
| `G1WholebodyLocomotionPickBetweenTablesTeleop-v0` | `cracker_box` 99 | `brasket` 99 | 4–4 |
| `G1WholebodyBendPickTeleop-v0` | `cracker_box` 97 | — | 2–2 |
| `G1WholebodyBendPickMP-v0` | `cracker_box` 100 | — | 3–3 |

Kết luận:

- **Tỉ lệ thành công: không suy được từ gói.** Không có cờ thành công (mục 3); các episode là demo tác giả giữ lại sau khi thu. Tỉ lệ thật chỉ đo được bằng phát lại trong sim (DA-17). Bản #24 ghi 100 % là do mặc định `success = True` trong script cũ.
- **Phân bố vị trí rất hẹp.** Task hai bàn: vật cần gắp chỉ dịch 2 cm theo x, 8 cm theo y; thùng 5 × 10 cm; robot 2 cm; cả hai bàn cố định (bàn 1 tâm `(0, 0,25, 0,6)`, bàn 2 `(−2,94, 0, 0,6)`). Mỗi episode cùng một vật (`cracker_box`), cùng một thùng (`brasket`), 4 vật gây nhiễu. Dải đo khớp `dr_cfgs.spatial` của gói (`target_region` x `[−0,33, −0,31]`, y `[−0,04, 0,04]`). Hệ quả cho lưới HE và cho việc tìm lỗi: điều kiện ngoài dải hẹp này là ngoài phân bố train của Ψ₀.
- Độ dài: task hai bàn 9,6–25,0 s (trung vị 12,0 s); F1 teleop 2,7–5,8 s; F1 MP gần như cố định 3,1 s, đúng tính chất của quỹ đạo do bộ lập kế hoạch sinh.

## 7. Kiểm lại

- Chạy lại trên cùng revision: `fetch` (băm lại sáu file đã có) cho `fetch.json` giống từng byte; `qa` trên gói hai bàn cho JSON giống từng byte, cùng N_teleop = 99.
- Kiểm tay 3 episode bằng `pyarrow` đọc thẳng từ zip, không qua script: episode 0, 49, 98 có 581, 544, 496 dòng (script: 581, 544, 496); `timestamp` từ 0 đến 11,6 s, 10,86 s, 9,9 s; `action` 36 cột, không NaN; chiều 34 có 482, 465, 413 giá trị khác nhau.
- Tài nguyên: toàn bộ lệnh chạy trên `rtx3060` qua `systemd-run --user --scope -p MemoryMax=… -p MemorySwapMax=0`, một tiến trình, RSS đỉnh 204 MB; tổng thời gian máy dưới 1 phút. Sổ chi phí: [ledger/S1-07.csv](ledger/S1-07.csv).

## Đề xuất cho 03 §3.3

| Dòng | Câu trả lời đề xuất | Trạng thái | Bằng chứng |
|---|---|---|---|
| V1 | Gói psi-data của SIMPLE (task hai bàn và F1) là LeRobot `v2.1`, 50 Hz. `action` có 36 chiều thật theo `meta/modality.json`: tay 0–13, cánh tay 14–27, hông roll/pitch/yaw 28–30 (tuyệt đối), `base_height` 31, `vx`, `vy`, `vyaw` 32–34 (tương đối, `vyaw` liên tục), `target_yaw` 35. Không chiều nào là đệm, không có khớp chân. `states` 32 chiều, Ψ₀ đệm lên 36 (state 32–35). Camera `observation.images.egocentric` 360×640, một camera. `ActionLayout` của nguồn psi-data dùng đúng bảng mục 2 | có | Mục 2: `inspect_psi_data.py layout` trên ba gói ở `e78fb93`; `modality.json`; Ψ₀ `cda3fdf` |
| V6 (phần dữ liệu) | Mỗi episode ghi `environment_config` với `layout`, `dr_cfgs`, `dr_state_dict`; không ghi seed. `simple-eval` ở `e78fb93`: 3 mức × 10 episode, 1 khung mỗi episode; ở mức 0, 1 vị trí ban đầu trùng 10 episode train đầu đến từng bit, nên seed eval suy ra là seed của các episode train đó, số cụ thể không suy được. Đội dùng một bảng seed chung [`configs/splits/default.yaml`](../../configs/splits/default.yaml) (train `[0, 10⁶)`, dev `[10⁶, 10⁶+1000)`, holdout `[2·10⁶, 2·10⁶+1000)`), không có split `gate`. Điều kiện của đội lưu như `dr_state_dict` để so trùng được | có, trừ số seed của tác giả (không suy được; đã hỏi PSI Lab) | Mục 4: `inspect_psi_data.py seeds` |
| V9 | psi-data và psi-model: không ghi giấy phép trên HF (`license = unknown`), `data_class = public` **[Đã chốt]** 2/11/2026. Mã Ψ₀ Apache 2.0, SIMPLE MIT. Cảnh HSSD CC-BY-NC-4.0, vật GraspNet-1Billion CC BY-NC-SA 4.0 (có trong video); vMaterials 2 chưa kiểm được; Objaverse không dùng | tạm: chờ PSI Lab trả lời thư mục 5; Hiếu quyết rủi ro phi thương mại | Mục 5, kiểm ngày 3/11/2026 |
