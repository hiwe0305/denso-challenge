# Phát lại action: ngưỡng hiệu chỉnh trên psi-data và report cho QA

_Ngày 4/11/2026. Story [DA-17](../product/stories/DA-17-phat-lai-action.md) nhiệm vụ 3 và 4. Mọi số trong file này là output của `python -m flywheel.data.replay_check` và `fw data qa`, chạy trên máy `rtx3060` với code của nhánh `DA-17-replay-check`. SIMPLE ở commit `b75c678` (bản sửa spawn và tay khởi đầu bằng 0). Thời gian chạy và RSS đỉnh đo bằng `/usr/bin/time -v`. Dữ liệu và kết quả nằm ở `rtx3060:~/denso-da17/fwdata/` và không commit._

## Kết luận

- **Phát lại động lực học chạy hết 99 episode psi-data** qua decoupled WBC trên MuJoCo, với 4 tiến trình, trong 12 phút 42 giây. RSS đỉnh là 3,9 GB mỗi tiến trình. Kết quả tất định: ba lần chạy episode 0–3 cho ra cùng một dòng `replay_outcomes.jsonl`, giống nhau đến từng chữ số.
- **Chỉ 26/99 episode đạt `check_success` khi phát lại.** Khớp lại được tái tạo tốt như nhau ở episode đạt và episode trượt: trung vị sai lệch cánh tay là 0,049 rad ở episode đạt và 0,046 rad ở episode trượt. Vậy lý do trượt không nằm ở các khớp đã ghi. **[Giả định]** Nguyên nhân là đế robot trôi khi đi giữa hai bàn, vì psi-data không ghi tư thế đế để so sánh (mục 3.2).
- **Ngưỡng ghi ở `configs/data/replay.yaml`, phiên bản `replay-1@cf2515483a8c`.** Ngưỡng động học lấy giá trị lớn nhất của 99 episode sạch. Ngưỡng động lực học lấy p99 của 26 episode phát lại đạt (design 6.3).
- **Ba lỗi cấy đều bị bắt, episode sạch không bị đánh dấu.** Test chạy trên CPU với simulator giả, không cần MuJoCo (mục 4).
- **QA đọc được report.** psi-data chỉ có report động học: 95 `pass`, 4 `flag`, 0 `reject`, giống hệt kết quả không có report. Khay S1 chỉ có report động học: 101 `flag` (đều do `action_jump.arm` của DA-03) và 1 `reject` do `replay_kinematic`.
- **Lần hiệu chỉnh đầu bị thay** vì nó loại cả 102 episode khay S1 (mục 5).

Việc phát sinh, Hiếu quyết:

| # | Phát hiện | Ảnh hưởng | Ai |
|---|---|---|---|
| 1 | Chỉ 26/99 episode psi-data đạt `check_success` khi phát lại, dù khớp được tái tạo tốt (mục 3.2) | Nếu đưa report động lực học vào QA, `task_success` (mức `reject`) loại 73 episode psi-data. **[Đề xuất]** Với psi-data, chỉ đưa report động học vào QA (`reports` không có `--outcomes`), hoặc đổi `task_success` sang `flag` trong `qa.yaml` (PR riêng cho người giữ `qa.yaml`) | Hiếu |
| 2 | Episode `ep_7f0a5ca73db8348e` của khay S1 bị loại: tương quan giữa action và state của `right_hand_middle_0_joint` là 0,349, dưới sàn 0,5 | Chưa biết đây là lỗi thật hay planner ra lệnh cho tay khi tay bị vật chặn. Tỉ lệ loại là 1/102 | DA-33 xem episode này |
| 3 | Sàn tương quan của `right_hand_thumb_1_joint` (−0,53) và `left_shoulder_roll_joint` (−0,12) âm ngay trên dữ liệu sạch | Đảo dấu ở hai khớp này chỉ bị bắt khi tương quan sạch của episode đó cao hơn trị tuyệt đối của sàn. Phát lại động lực học vẫn thấy lỗi qua `state_error` | Giữ như vậy |
| 4 | Không kiểm tự va chạm (AC 1), vì phép kiểm này cần hình học của robot | Một phần của AC 1 chưa làm | Hiếu: làm trong adapter sau 13/11, hoặc bỏ khỏi AC |
| 5 | Đảo dấu ở các chiều lệnh 31–35 (chiều cao, vận tốc, cờ rẽ, hướng) không bị phép kiểm động học bắt, vì các chiều này không phải khớp và state không có cột tương ứng | Chỉ phát lại động lực học thấy được, qua việc task trượt | Giữ như vậy |
| 6 | `FakeSim2D` của `flywheel.testkit` không mô phỏng được G1. Test của làn dùng một WBC giả riêng trong `tests/unit/replay_check/test_replay_faults.py` | Không ảnh hưởng | Không cần làm gì |
| 7 | `check_kinematic` nhận `episode_id` và `fps` qua tham số từ khóa, vì `EpisodeFrames` không chứa hai trường này | Không đổi hợp đồng | Không cần làm gì |

## 1. Lệnh

Code ở `rtx3060:~/denso-da17/repo` được chép từ worktree của nhánh. Môi trường là venv của DA-33 (`~/denso-da33/fwdata/simple/.venv`, SIMPLE cài sẵn), với `PYTHONPATH` đặt `flywheel-simple/src` và `~/denso-da17/SIMPLE/src` (bản clone ở `b75c678`) lên trước. Gốc kho là `FW_ROOT=~/denso-da17/fwdata`. Hai nguồn đã qua `fw data ingest`: `src_33e3556ebc9bbaeb` (psi-data `e78fb93`) và `src_61905ccdc2df03b6` (khay `tray_s1_0d84cc87b1e5`).

Phát lại chạy trong `nohup setsid systemd-run --user --scope -p MemoryMax=20G -p MemorySwapMax=0`, với `MUJOCO_GL=egl`:

```bash
python -m flywheel.data.replay_check replay $PSI_DATA --work fwdata/replay/psi-data-e78fb93 \
  --python ~/denso-da33/fwdata/simple/.venv/bin/python --workers 4
python -m flywheel.data.replay_check calibrate $PSI_DATA --outcomes fwdata/replay/psi-data-e78fb93/replay_outcomes.jsonl \
  --calibration "psi-data e78fb93 two-table teleop, 99 episodes; SIMPLE b75c678 decoupled WBC on MuJoCo, sim clock; rtx3060 4/11/2026"
python -m flywheel.data.replay_check reports $W --out fwdata/reports/<tên> [--outcomes …/replay_outcomes.jsonl]
fw data qa $W --replay fwdata/reports/<tên>
```

`replay` chạy adapter `flywheel_simple.replay.outcomes` như một tiến trình con. Làn không import adapter. Mỗi tiến trình con phát lại một dải episode liền nhau, trên một bản sao của thư mục `meta/`, vì SIMPLE ghi `meta/replay.txt` vào thư mục dữ liệu. `calibrate` ghi `configs/data/replay.yaml`, sau đó file này được chép về repo. `qa` chạy trên một bản sao của thư mục làm việc cho mỗi bộ report. Mỗi lệnh ghi hai dòng `LedgerEntry` (một ước tính, một thực đo) vào `$FW_ROOT/sites/local/runs/g0-DA-17-20261104/<job_id>/ledger.jsonl`.

## 2. Thời gian và bộ nhớ

| Lệnh | Wall | RSS đỉnh | Sổ thực đo / ước tính |
|---|---|---|---|
| `replay`, 99 episode, 4 tiến trình | 12 phút 42 giây | 3,88 GB | 761 / 785 s |
| `calibrate` | 2,5 s | 371 MB | 1,5 / 3,1 s |
| `reports` psi-data, có outcome | 2,6 s | 342 MB | 1,8 / 3,1 s |
| `reports` khay S1 | 3,5 s | 377 MB | 2,6 / 7,4 s |
| `fw data qa --replay` | 2,3–3,1 s | 400–482 MB | |

Mỗi tiến trình con mất 744–756 s cho 24–25 episode, tức khoảng 30 s mỗi episode, lúc máy đang có load khoảng 45 do các session khác. Ước tính của `replay` dùng giả định 0,05 s mỗi frame cho một tiến trình (`cli.REPLAY_S_PER_FRAME`), lệch 3% so với thực đo. Tiền là 0 USD vì job chạy trên CPU của máy đội.

## 3. Kết quả phát lại

### 3.1 Ngưỡng

| Khóa | Giá trị | Cách lấy |
|---|---|---|
| `limit_tolerance` | action 1e-5; states 0,00193 rad | Giá trị lớn nhất mỗi episode, sàn 1e-5 (`g1.yaml` làm tròn giới hạn URDF) |
| `unit_ratio` | tay 7,81; cánh tay 1,34; hông 1,32 | Lớn nhất của std(action)/std(state) mỗi khớp |
| `mapping_correlation` | 0,5 ở 22 khớp; −0,53 (`right_hand_thumb_1`); −0,12 (`left_shoulder_roll`) | Nhỏ nhất của 99 episode, nhưng không cao hơn 0,5 (`MAPPING_CEILING`) |
| `timestamp_tolerance_frames` | 0,5 | Cố định: timestamp sạch nằm đúng `frame_index / fps` |
| `state_error` | tay 0,752; cánh tay 0,0755; hông 0,217 rad | p99 của 26 episode đạt |
| `hand_event_offset_steps` | 2 | p99 của \|độ lệch\|, làm tròn lên |

Các khớp của tay trái không có sàn tương quan, vì tay trái chỉ cử động trong 2/99 episode, dưới mức 10 episode cần có.

### 3.2 Phát lại động lực học

| | Đạt (26) | Trượt (73) |
|---|---|---|
| Sai lệch tay: nhỏ nhất, trung vị, lớn nhất (rad) | 0,057, 0,094, 0,938 | 0,061, 0,097, 1,53 |
| Sai lệch cánh tay | 0,035, 0,049, 0,077 | 0,029, 0,046, 0,123 |
| Sai lệch hông (roll, pitch, yaw) | 0,102, 0,146, 0,221 | 0,094, 0,123, 0,236 |
| Độ lệch thời điểm đóng tay (bước) | 0–2 | 0–3 |
| Phát lại dừng sớm | 0 | 0 |

Episode đạt: 0, 1, 4, 12, 16, 24, 26, 32, 35, 41, 46, 53, 68, 69, 71, 72, 78, 81, 82, 85, 86, 87, 89, 92, 95, 96.

Mọi episode đều phát lại đủ số frame đã ghi. Sai lệch khớp không phân biệt được episode đạt với episode trượt, nên `check_success` trượt vì một thứ khác các khớp. Report động lực học của psi-data có 76 episode có issue: 73 `replay_failed`, 22 `state_error`, 1 `hand_event_offset`.

**Đồng hồ.** `ReplayDecoupledAgent` của SIMPLE gọi `time.monotonic()` hai lần mỗi bước. Adapter mặc định dùng giờ mô phỏng (`--clock sim`), có kết quả tất định. Phần chạy thử với giờ thật (`--clock wall`) trên 26 episode cho 4 episode đạt, còn giờ mô phỏng cho 6 episode đạt trên cùng 26 episode đó. Có 3 episode đạt ở cả hai. Episode 3 chỉ đạt với giờ thật; episode 1, 26, 53 chỉ đạt với giờ mô phỏng. Vậy đồng hồ không phải nguyên nhân của tỉ lệ đạt thấp. `--clock wall` vẫn còn là một tùy chọn.

### 3.3 Report và QA

| Bộ report | Report có issue | `fw data qa --replay` |
|---|---|---|
| psi-data, động học và động lực học | động học 0, động lực học 76 | 21 `pass`, 5 `flag`, 73 `reject` (`task_success` 73, `replay_dynamic` 76) |
| psi-data, chỉ động học | 0 | 95 `pass`, 4 `flag`, 0 `reject`, giống [data-pipeline.md](data-pipeline.md) mục 3.1 |
| khay S1, chỉ động học | 1 (`joint_mapping`) | 0 `pass`, 101 `flag` (`action_jump.arm`), 1 `reject` (`replay_kinematic`) |

Ngưỡng QA là `qa-1@95fbc11570b7`. Khay S1 không có report động lực học, vì DA-33 đã phát lại khay trong quá trình sinh dữ liệu (102/102 đạt).

## 4. Lỗi cấy

`tests/unit/replay_check/test_replay_faults.py` sinh 12 episode G1 sạch ngay trong test, rồi hiệu chỉnh ngưỡng trên chúng bằng một WBC giả. WBC giả bám action trễ 2 frame và đọc qua encoder 0,01 rad. Sau đó test cấy lỗi vào một episode và chạy đủ chuỗi `fw data ingest`, `reports`, `fw data qa --replay`:

| Lỗi cấy | Issue động học | Issue động lực học | QA |
|---|---|---|---|
| Không cấy | không có | không có | `pass` |
| Đảo dấu `right_elbow_joint` trong action | `joint_mapping` | `state_error`, `replay_failed` | `reject` (`replay_kinematic`) |
| Action `right_elbow_joint` ghi bằng độ | `unit_deg_rad`, `joint_limit` | (test không kiểm) | `reject` |
| Timestamp lệch 2 frame | `timestamp_offset` | không có (đồng hồ không phải khớp) | `reject` |

## 5. Lần hiệu chỉnh đầu bị thay

Lần hiệu chỉnh đầu (`replay-1@782d018c60ef`) có thêm hai điều kiện:

- một phép kiểm `joint_jump` trên state đã ghi;
- sàn tương quan lấy đúng giá trị nhỏ nhất của dữ liệu sạch.

Với ngưỡng này, cả 102 episode khay S1 đều bị loại. Lý do: `joint_jump` 102 episode (bước nhảy cánh tay 0,080 rad, ngưỡng 0,056 rad) và `joint_mapping` 36 episode (ví dụ `right_elbow_joint` 0,953, sàn 0,960). Hai thay đổi đã làm:

- **Bỏ `joint_jump` khỏi phát lại.** Design 6.3 không liệt kê phép kiểm này cho chế độ động học. Nhảy khớp là D3, và `action_jump` của QA đã đánh dấu nó (mức `flag`, DA-03).
- **Sàn tương quan không cao hơn 0,5.** Một khớp bị đảo dấu cho tương quan âm, nên sàn cao hơn 0,5 không bắt thêm được lỗi nào mà chỉ loại nguồn bám kém hơn psi-data một chút.

Kết quả lần đầu nằm ở `rtx3060:~/denso-da17/fwdata/superseded-1/`. Sổ chi phí chỉ ghi thêm, nên `g0-DA-17-20261104` giữ cả các job của lần đầu. Hai lần chạy phát lại một phần (giờ mô phỏng 40 episode, giờ thật 26 episode) đã bị dừng, nhưng dòng thực đo của chúng vẫn được ghi.
