# Phát lại action: ngưỡng hiệu chỉnh trên psi-data và report cho QA

_Ngày 4/11/2026; mục 6 ngày 5/11/2026. Story [DA-17](../product/stories/DA-17-phat-lai-action.md) nhiệm vụ 3, 4, 4.1 và 6. Mọi số trong file này là output của `python -m flywheel.data.replay_check` và `fw data qa`, chạy trên máy `rtx3060` với code của nhánh `DA-17-replay-check`. SIMPLE ở commit `b75c678` (bản sửa spawn và tay khởi đầu bằng 0). Thời gian chạy và RSS đỉnh đo bằng `/usr/bin/time -v`. Dữ liệu và kết quả nằm ở `rtx3060:~/denso-da17/fwdata/` và không commit._

## Kết luận

- **Phát lại động lực học chạy hết 99 episode psi-data** qua decoupled WBC trên MuJoCo, với 4 tiến trình, trong 12 phút 42 giây. RSS đỉnh là 3,9 GB mỗi tiến trình. Kết quả tất định: ba lần chạy episode 0–3 cho ra cùng một dòng `replay_outcomes.jsonl`, giống nhau đến từng chữ số.
- **Chỉ 26/99 episode đạt `check_success` khi phát lại.** Khớp lại được tái tạo tốt như nhau ở episode đạt và episode trượt: trung vị sai lệch cánh tay là 0,049 rad ở episode đạt và 0,046 rad ở episode trượt. Vậy lý do trượt không nằm ở các khớp đã ghi. Ngày 5/11/2026 đã đo được nguyên nhân (mục 6). Bản ghi dừng 4–20 khung sau lệnh mở tay, trong khi SIMPLE chỉ tính thành công khi tay rời vật đủ 10 bước liên tiếp. Giữ lệnh cuối thêm 50 bước cho 44/99 episode đạt. 43 episode vẫn trượt vì tay mở vẫn chạm vật, và chỉ 12/99 episode lệch thật (rơi vật, đặt lệch giỏ). Giả định cũ "đế trôi" đã bị loại, và cảnh dựng lại khớp với `environment_config`.
- **Ngưỡng ghi ở `configs/data/replay.yaml`, phiên bản `replay-1@cf2515483a8c`.** Ngưỡng động học lấy giá trị lớn nhất của 99 episode sạch. Ngưỡng động lực học lấy p99 của 26 episode phát lại đạt (design 6.3).
- **Ba lỗi cấy đều bị bắt, episode sạch không bị đánh dấu.** Test chạy trên CPU với simulator giả, không cần MuJoCo (mục 4).
- **Phát lại động lực học trượt chỉ đánh dấu, với mọi nguồn** **[Đã chốt]** (PO 4/11/2026, DA-17 AC 3). Lý do: phát lại vòng hở action đã ghi trên task đi lại không tái tạo được thành công. Chỉ 26/99 episode đạt, và episode nào đạt còn đổi theo đồng hồ. Trong `qa.yaml`, `task_success` và `replay_success` chuyển từ `reject` sang `flag`.
- **QA đọc được report.** Với `qa-1@fb6ddaf9f48c`:
  - psi-data có cả report động học và động lực học: 21 `pass`, 78 `flag`, 0 `reject`.
  - psi-data chỉ có report động học: 95 `pass`, 4 `flag`, 0 `reject`.
  - Khay S1 chỉ có report động học: 101 `flag` và 1 `reject` do `replay_kinematic` (mục 3.3).
- **Khay S1 thô hơn psi-data thật sự.** Đây là phát hiện cho DA-33, không phải lỗi của ngưỡng (mục 5). Lần hiệu chỉnh đầu loại cả 102 episode khay; ngưỡng động học đã được nới ở hai chỗ để khay không bị loại hết.

Việc phát sinh, Hiếu quyết:

| # | Phát hiện | Ảnh hưởng | Ai |
|---|---|---|---|
| 1 | Chỉ 26/99 episode psi-data đạt `check_success` khi phát lại, dù khớp được tái tạo tốt (mục 3.2). Nguyên nhân (5/11/2026, mục 6): bản ghi dừng ngay sau khi thả vật; 12/99 episode lệch thật | **[Đã chốt]** PO 4/11/2026: `task_success` và `replay_success` chỉ `flag`. psi-data có report động lực học giờ cho 0 `reject` và 78 `flag` (73 episode trượt `task_success`) | Đã làm trong PR này |
| 2 | Episode `ep_7f0a5ca73db8348e` của khay S1 bị loại: tương quan giữa action và state của `right_hand_middle_0_joint` là 0,349, dưới sàn 0,5 | Chưa biết đây là lỗi thật hay planner ra lệnh cho tay khi tay bị vật chặn. Tỉ lệ loại là 1/102 | DA-33 xem episode này |
| 3 | Sàn tương quan của `right_hand_thumb_1_joint` (−0,53) và `left_shoulder_roll_joint` (−0,12) âm ngay trên dữ liệu sạch | Đảo dấu ở hai khớp này chỉ bị bắt khi tương quan sạch của episode đó cao hơn trị tuyệt đối của sàn. Phát lại động lực học vẫn thấy lỗi qua `state_error` | Giữ như vậy |
| 4 | Không kiểm tự va chạm (AC 1), vì phép kiểm này cần hình học của robot | **[Đã chốt]** Dời sau 13/11/2026; AC 1 còn mở phần này (ghi trong story) | Hiếu, sau 13/11 |
| 5 | Khay S1 thô hơn psi-data: bước nhảy state cánh tay lớn nhất là 0,080 rad, so với 0,056 rad ở psi-data. `action_jump.arm` của QA đánh dấu 101/102 episode. 36 episode có tương quan action–state thấp hơn mức thấp nhất của psi-data (mục 5) | Ngưỡng nới (không còn `joint_jump` trên state, sàn tương quan không quá 0,5) chỉ để khay không bị loại cả lô. Độ thô vẫn còn trong dữ liệu, và Ψ₀ sẽ học theo | DA-33 xem planner (giống phát hiện 1 của [data-pipeline.md](data-pipeline.md)) |
| 6 | Đảo dấu ở các chiều lệnh 31–35 (chiều cao, vận tốc, cờ rẽ, hướng) không bị phép kiểm động học bắt, vì các chiều này không phải khớp và state không có cột tương ứng | Chỉ phát lại động lực học thấy được, qua việc task trượt | Giữ như vậy |
| 7 | `FakeSim2D` của `flywheel.testkit` không mô phỏng được G1. Test của làn dùng một WBC giả riêng trong `tests/unit/replay_check/test_replay_faults.py` | Không ảnh hưởng | Không cần làm gì |
| 8 | `check_kinematic` nhận `episode_id` và `fps` qua tham số từ khóa, vì `EpisodeFrames` không chứa hai trường này | Không đổi hợp đồng | Không cần làm gì |

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

| Bộ report | Report có issue | `fw data qa --replay`, `qa-1@fb6ddaf9f48c` | Trước quyết định 4/11, `qa-1@95fbc11570b7` |
|---|---|---|---|
| psi-data, động học và động lực học | động học 0, động lực học 76 | 21 `pass`, 78 `flag`, **0 `reject`** (`replay_dynamic` 76, `task_success` 73, `action_jump` 4) | 21 `pass`, 5 `flag`, 73 `reject` (`task_success`) |
| psi-data, chỉ động học | 0 | 95 `pass`, 4 `flag`, 0 `reject`, giống [data-pipeline.md](data-pipeline.md) mục 3.1 | giống |
| khay S1, chỉ động học | 1 (`joint_mapping`) | 0 `pass`, 101 `flag` (`action_jump.arm` ở cả 102 episode), 1 `reject` (`replay_kinematic`) | giống |

Quyết định PO 4/11/2026 **[Đã chốt]**: phát lại động lực học trượt chỉ đánh dấu, với mọi nguồn (DA-17 AC 3). `qa.yaml` đổi `task_success` (D6) và `replay_success` (D8) từ `reject` sang `flag`. Đây là hai phép kiểm duy nhất ngoài `replay_dynamic` đọc report động lực học: cả hai đọc `sim_success`, mà chỉ report động lực học mới có. Phép phát lại lúc sinh dữ liệu của DA-33 không phải phép kiểm QA và không đổi; release khay vẫn chỉ gồm episode đã qua phép đó.

Mỗi lần `qa` chạy 1,7–2,6 s, RSS đỉnh dưới 0,5 GB. Khay S1 không có report động lực học, vì DA-33 đã phát lại khay trong quá trình sinh dữ liệu (102/102 đạt).

## 4. Lỗi cấy

`tests/unit/replay_check/test_replay_faults.py` sinh 12 episode G1 sạch ngay trong test, rồi hiệu chỉnh ngưỡng trên chúng bằng một WBC giả. WBC giả bám action trễ 2 frame và đọc qua encoder 0,01 rad. Sau đó test cấy lỗi vào một episode và chạy đủ chuỗi `fw data ingest`, `reports`, `fw data qa --replay`:

| Lỗi cấy | Issue động học | Issue động lực học | QA |
|---|---|---|---|
| Không cấy | không có | không có | `pass` |
| Đảo dấu `right_elbow_joint` trong action | `joint_mapping` | `state_error`, `replay_failed` | `reject` (`replay_kinematic`) |
| Action `right_elbow_joint` ghi bằng độ | `unit_deg_rad`, `joint_limit` | (test không kiểm) | `reject` |
| Timestamp lệch 2 frame | `timestamp_offset` | không có (đồng hồ không phải khớp) | `reject` |

## 5. Lần hiệu chỉnh đầu bị thay, và độ thô của khay S1

Lần hiệu chỉnh đầu (`replay-1@782d018c60ef`) có thêm hai điều kiện:

- một phép kiểm `joint_jump` trên state đã ghi;
- sàn tương quan lấy đúng giá trị nhỏ nhất của dữ liệu sạch.

Với ngưỡng này, cả 102 episode khay S1 đều bị loại. Lý do: `joint_jump` 102 episode (bước nhảy cánh tay 0,080 rad, ngưỡng 0,056 rad) và `joint_mapping` 36 episode (ví dụ `right_elbow_joint` 0,953, sàn 0,960). Hai thay đổi đã làm:

- **Bỏ `joint_jump` khỏi phát lại.** Design 6.3 không liệt kê phép kiểm này cho chế độ động học. Nhảy khớp là D3, và `action_jump` của QA đã đánh dấu nó (mức `flag`, DA-03).
- **Sàn tương quan không cao hơn 0,5.** Một khớp bị đảo dấu cho tương quan âm, nên sàn cao hơn 0,5 không bắt thêm được lỗi nào mà chỉ loại nguồn bám kém hơn psi-data một chút.

**Khay S1 thô hơn psi-data thật sự, và đây là phát hiện cho DA-33.** Ngưỡng nới chỉ để phát lại không loại cả lô; nó không giải thích được độ thô.

| Đo trên state và action đã ghi | psi-data (99 episode người) | khay S1 (102 episode planner) |
|---|---|---|
| Bước nhảy state cánh tay lớn nhất | 0,056 rad | 0,080 rad |
| Episode trượt `action_jump.arm` (p99,9 của psi-data) | 1 | 102 |
| Episode có một khớp với tương quan action–state dưới mức thấp nhất của psi-data | 0 (theo cách lấy ngưỡng) | 36 |

Các bước nhảy nằm quanh bước 25–40, 205–223 và 1295–1329 của episode (ví dụ `ep_00393522d8b4c69e`). Vùng 205–223 trùng với các bước 205–211 mà [data-pipeline.md](data-pipeline.md) mục 3.2 đã thấy ở action cổ tay. Ψ₀ sẽ học theo phân bố này.

Kết quả lần đầu nằm ở `rtx3060:~/denso-da17/fwdata/superseded-1/`. Sổ chi phí chỉ ghi thêm, nên `g0-DA-17-20261104` giữ cả các job của lần đầu. Hai lần chạy phát lại một phần (giờ mô phỏng 40 episode, giờ thật 26 episode) đã bị dừng, nhưng dòng thực đo của chúng vẫn được ghi.

## 6. Vì sao chỉ 26/99 episode psi-data đạt khi phát lại

_Ngày 5/11/2026. DA-17 nhiệm vụ 6. Mọi số trong mục này là output của `flywheel_simple.replay.run` với `--clock sim`, thêm cờ `--trace` (6.1) và `--hold-steps` (6.2), chạy trên `rtx3060` với SIMPLE `b75c678`. Script chọn mẫu và phân tích nằm ngoài repo, ở `rtx3060:~/denso-da17-26of99/` (`launch.py`, `analyze.py`, `holdsum.py`, `handend.py`). Vết và kết quả cũng nằm ở đó, không commit._

**Nguyên nhân chính: bản ghi psi-data dừng quá sớm sau khi thả vật, nên luật thành công của SIMPLE không kịp đạt.** Luật này đòi vật nằm trên giỏ và không bàn tay nào chạm vật trong 10 bước liên tiếp. Cả 99 bản ghi đều dừng 4–20 khung sau lệnh mở tay, lúc tay còn khép 38–85 % (mục 6.2). SIMPLE chỉ phát thêm 10 khung đệm sau khung cuối. Giữ lệnh cuối thêm 50 bước nâng số đạt từ 26 lên 44/99. Trong 55 episode vẫn trượt, 43 episode có vật đã nằm trên giỏ nhưng bàn tay mở vẫn chạm vật, vì dữ liệu không có đoạn rút tay. Chỉ 12/99 episode trượt vì phát lại lệch thật: 6 episode rơi vật lúc mang, 6 episode đặt trượt khỏi giỏ.

### 6.1 Giả thuyết và kết luận

| # | Giả thuyết | Episode đo | Kết quả | Kết luận |
|---|---|---|---|---|
| H0 | Trượt ở một chặng cụ thể | 40 (vết, 20 đạt + 20 trượt) và 99 (vết khi giữ 50 bước) | Cả 20 episode đạt đều kết thúc với vật trên giỏ và đúng 10 bước có thưởng. Trong 20 episode trượt, 17 có vật đã nằm trên giỏ: 14 có tay vẫn chạm vật tới bước cuối, 3 chỉ được 1–5 bước không chạm. 2 rơi vật lúc mang, 1 đặt cách giỏ 0,15 m. Trên 99 episode khi giữ 50 bước, xem bảng 6.3 | **Giữ**: chặng trượt là **sau khi thả**, không phải lúc gắp hay mang |
| H1 | Phát lại thiếu bước sau khung cuối | 99, giữ N = 50 và 100 bước; N = 10 và 25 suy ra từ lần N = 50 | Số đạt theo N là 26, 38, 41, 44, 45 với N = 0, 10, 25, 50, 100 (bảng 6.2): đường cong phẳng dần sau N = 50. 26 episode đạt cũ vẫn đạt, ở bước 0–10 sau khung cuối. 18 episode trượt cũ đạt khi được 12–60 bước sau khung cuối, và 19 episode khi được 110 bước | **Giữ** cho 19/73 episode trượt. Phần còn lại cần tay rút khỏi vật, mà dữ liệu không có |
| H2 | Cảnh dựng lại khác cảnh lúc thu | 40 (dòng `reset`) và 99 (lần N = 50) | Vật sau `reset` trùng `dr_state_dict.spatial` của `environment_config` tới 0,000 m ở cả 99 episode. `dr_level` là `None` (khôi phục mọi randomizer). Không episode nào bị ghi đè `uid`, và log không có dòng `[warn] … mismatch`, ở cả lần chạy 4/11. Đế lùi 0,061 m trong pha ổn định, như nhau ở mọi episode | **Loại** |
| H3 | Đế trôi trong pha đi | 40 | Khoảng cách đế tới mép bàn 2 ở bước cuối: đạt 0,252 / 0,374 / 0,471 m, trượt 0,234 / 0,328 / 0,429 m (nhỏ nhất / trung vị / lớn nhất). Vật cách tâm giỏ: đạt trung vị 0,031 m, trượt 0,041 m (chỉ tính episode có vật trên giỏ) | **Loại** như nguyên nhân chính: hai nhóm chồng lên nhau. Nhãn **[Giả định]** "đế trôi" ở mục Kết luận đã đổi theo kết quả này |
| H4 | Dữ liệu thu bằng phiên bản SIMPLE hoặc WBC khác `b75c678` | 99 (metadata) và lịch sử upstream | psi-data `e78fb93` không ghi phiên bản: không có README, `info.json` chỉ có `codebase_version: v2.1`. `environment_config` mang nhãn `G1 SONIC Pick Between Tables`, chuỗi này không có ở commit nào của SIMPLE (`b75c678` là `G1 TELEOP …`). `metadata` không có `success_criteria` và `max_episode_steps`. Đường dẫn asset là `/home/wenke/SIMPLE/…`. Ngưỡng thành công là 0,9 ở `a73ea6e` và `8e5fe20`, rồi hạ xuống 0,4 ở `d010f0f` (20/6/2026, "suppor replaying training data"). Luật thưởng (vật trên giỏ và tay không chạm) không đổi từ `a73ea6e` | **Chưa rõ**: dữ liệu được thu bằng một bản task chưa công bố. Lịch sử không cho biết bản đó có cùng luật chạm tay hay không |

### 6.2 Giữ lệnh cuối (H1)

`--hold-steps N` nâng số khung đệm của `ReplayDecoupledAgent` từ 10 lên 10 + N. Trong các khung này WBC vẫn giữ thăng bằng, với lệnh của khung cuối làm đích. Phát lại tất định, nên lần N = 25 chính là lần N = 50 cắt sớm 25 bước. Vì vậy số đạt với N ≤ 50 suy ra đúng từ `success_at_step` của lần N = 50, và sai lệch khớp của 99 episode giống hệt lần 4/11.

| N (bước giữ thêm) | Số bước sau khung cuối | Số đạt / 99 | Cách lấy |
|---|---|---|---|
| 0 | 10 | 26 | Lần chạy 4/11; lần N = 50 cũng cho đúng 26 episode này |
| 10 | 20 | 38 | Suy ra từ lần N = 50 |
| 25 | 35 | 41 | Suy ra từ lần N = 50 |
| 50 | 60 | 44 | Đo |
| 100 | 110 | 45 | Đo; 44 episode của lần N = 50 vẫn đạt, thêm episode 17 ở bước thứ 71 sau khung cuối |

18 episode trượt cũ đạt khi giữ 50 bước. Số trong ngoặc là số bước sau khung cuối lúc đạt: 5 (25), 13 (20), 27 (15), 31 (19), 34 (13), 39 (13), 42 (35), 51 (14), 57 (12), 58 (14), 60 (13), 63 (55), 66 (60), 70 (40), 80 (27), 84 (18), 90 (17), 93 (19).

**Bản ghi dừng ngay sau lệnh mở tay.** Đo trên tay phải của 99 bản ghi (`handend.py`):

| | Đạt khi phát lại (26) | Trượt (73) |
|---|---|---|
| Khung từ lệnh mở tay (`action`) tới cuối bản ghi: nhỏ nhất, trung vị, lớn nhất | 5, 10, 16 | 4, 7, 20 |
| Độ khép của tay ở khung cuối (`states`), so với lúc khép nhất | 0,46, 0,61, 0,84 | 0,38, 0,75, 0,85 |

Lệnh mở tay càng sát cuối bản ghi thì tay càng ít thời gian rời vật. Nhưng hai nhóm vẫn chồng lên nhau (có episode đạt chỉ có 5 khung), vì tay có chạm vật hay không còn tùy tư thế cánh tay lúc thả.

### 6.3 Episode vẫn trượt khi giữ 50 bước

Phân loại theo vết ở bước cuối của lần N = 50 (`analyze.py`), trên 73 episode trượt ở lần 4/11:

| Nhóm | Số episode | Episode |
|---|---|---|
| Đạt khi giữ thêm bước | 18 | 5, 13, 27, 31, 34, 39, 42, 51, 57, 58, 60, 63, 66, 70, 80, 84, 90, 93 |
| Vật trên giỏ, tay vẫn chạm vật ở bước cuối (40 tay phải, 2 tay trái) | 42 | 3, 7, 9, 10, 14, 15, 19, 21, 22, 23, 25, 29, 36, 37, 38, 40, 43, 44, 45, 47, 52, 54, 55, 56, 59, 61, 62, 64, 65, 67, 73, 74, 75, 76, 77, 79, 83, 88, 91, 94, 97, 98 |
| Vật trên giỏ, tay rời quá muộn (58 bước sau khung cuối); đạt khi giữ 100 bước | 1 | 17 |
| Rơi vật lúc mang (vật xuống sàn 317–584 bước trước khung cuối) | 6 | 2, 6, 8, 11, 28, 30 |
| Đặt lệch khỏi giỏ (vật cách tâm giỏ 0,18–0,40 m), hoặc vật rơi khỏi mép giỏ sau khi thả | 6 | 18, 20, 33, 48, 49, 50 |

Chỉ 12 episode cuối bảng là phát lại lệch thật: vật không tới được giỏ như trong bản ghi. 43 episode còn lại đặt vật đúng chỗ. Các episode này trượt vì luật thành công cần tay rời vật, mà bản ghi dừng trước lúc đó.

**Ngoài lề: `check_object_in_container` của SIMPLE chỉ đôi khi kiểm sai lệch xy ≤ 0,12 m.** Biểu thức `(A and B) or (C and D) and success` chỉ áp `success` (sai lệch xy) cho vế sau, nên một tiếp xúc giữa vật và giỏ theo thứ tự geom ngược lại là đủ. Có 3 episode đạt dù vật (vị trí body MuJoCo) cách tâm giỏ 0,121–0,140 m (26, 41, 72). Lỗi này không đổi kết luận trên, vì vật vẫn phải chạm giỏ.

### 6.4 Ảnh hưởng và đề xuất

- **Quyết định 4/11 vẫn đúng.** `task_success` và `replay_success` chỉ `flag` **[Đã chốt]**. Phát lại trượt trên psi-data phần lớn phản ánh việc bản ghi dừng sớm, không phải dữ liệu xấu. Chỉ 12/99 episode lệch thật khi phát lại.
- **[Đề xuất]** Phát lại psi-data với `--hold-steps 50`, cho số đạt 44/99. Nếu Hiếu chọn cách này thì phải hiệu chỉnh lại `state_error` trong `replay.yaml` ở một PR riêng. p99 trên 44 episode đạt là tay 1,341 / cánh tay 0,0785 / hông 0,220 rad, so với 0,752 / 0,0755 / 0,217 của `replay-1@cf2515483a8c` (26 episode). Ngưỡng tay tăng vì có episode sai lệch tay lớn nay đạt. Ngưỡng cánh tay và hông gần như không đổi. PR này không sửa `replay.yaml` hay `qa.yaml`.
- **[Đề xuất]** Thêm vào outcome một tín hiệu "vật trên giỏ ở bước cuối, bỏ qua tay chạm", để tách 12 episode lệch thật khỏi 43 episode chỉ dừng sớm. Tín hiệu này cần một trường mới trong `ReplayReport` (PR hợp đồng cho Hiếu), nên chưa làm.
- **Liên hệ S1-03 (eval mujoco 0/90).** Nguyên nhân ở đây không phải dựng cảnh: H2 đã loại trên 99 episode, và đường `reset` với `state_dict` khôi phục đúng cảnh. Có hai điểm người làm S1-03 nên kiểm, vì eval dùng cùng luật thành công:
  - policy phải rút tay khỏi vật và giữ 10 bước không chạm, vì `compute_reward` chạy hai lần mỗi bước nên mỗi bước cộng 0,04;
  - episode eval không được kết thúc ngay sau khi thả vật.

### 6.5 Thời gian máy

| Job | Episode | Wall | Giờ worker | Ước tính |
|---|---|---|---|---|
| Vết 40 episode, mỗi episode một tiến trình, 4 worker; thêm 1 worker chạy lại episode 0 và 5 | 40 + 2 | 11 phút 8 giây | 0,70 | 0,1 giờ wall |
| Giữ 50 bước, có vết, 4 shard liền nhau | 99 | 17 phút 39 giây | 1,01 | 0,25 giờ wall |
| Giữ 100 bước, có vết, 4 shard liền nhau | 99 | 22 phút 1 giây | 1,16 | 0,32 giờ wall |

Kiểm tất định: episode 0 (đạt) và 5 (trượt) chạy hai lần cho vết và outcome giống hệt từng byte. Episode 0 còn khớp với lần chạy thử trước đó. Sổ chi phí ở [ledger/DA-17.csv](ledger/DA-17.csv).
