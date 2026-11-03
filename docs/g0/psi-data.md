# Phân tích gói psi-data (Q1, V1, V6, V9)

_Ngày 3/11/2026. Story [S1-07](../product/stories/S1-07-phan-tich-psi-data.md), cổng G0. Làm lại từ PR #24 của Thông (nhánh `S1-07-psi-data` @ `e96da77`): giữ cách đọc cấu trúc gói, bỏ mọi số gán cứng. Mọi số trong file này do [`scripts/g0/inspect_psi_data.py`](../../scripts/g0/inspect_psi_data.py) in ra, chạy trên máy `rtx3060`; bảng trong file là output của lệnh, chép nguyên. Số nào script không đo được thì ghi là giả định hoặc "không suy được"._

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
