# DA-47 · Eval trên cảnh đồ gá và outcome K1 có thời điểm lỗi

## Trạng thái

| Trường | Giá trị |
|---|---|
| Trạng thái | Đang làm (mở ngày 25/11/2026; code chờ DA-42 merge) |
| Người làm | Hiếu |
| Làn | Ngoài ba làn: adapter `flywheel-psi0` và `flywheel-simple` (task bê khay), không sửa nhân hay làn |
| Nguồn yêu cầu | Kế hoạch vòng chung kết ngày 19/11/2026, nhóm A (task, bộ chấm, eval), việc 2 và 3. Hiếu giao ngày 25/11/2026 |
| Nhãn | `area:sim`, `area:eval` |
| Sprint | Trước vòng chung kết. Mốc cứng 28/11/2026: bộ chấm bản 2 trên master và đã thử trên cảnh `jig2` |
| Ước lượng | 10 giờ (ước lượng), không tính lô eval checkpoint |
| Phụ thuộc | DA-42 (PR 221, chưa merge): bộ chấm bản 2, tín hiệu lỗi, `--repeats`. DA-41 (đã merge): cảnh `jig2`. DA-43 K1 (đã merge): hợp đồng `RolloutOutcome`. Nhóm B: plan train và checkpoint mới (26–28/11/2026) |

## Story

Là người đánh giá checkpoint Ψ₀ của vòng chung kết, tôi muốn chạy eval trên cảnh đồ gá `jig2` với bộ chấm bản 2, ba lượt mỗi điều kiện, và xuất kết quả theo hợp đồng K1 có thời điểm lỗi, để Agent QA/QC (nhóm C) đọc được từng rollout và số của checkpoint mới so được với nhau.

Hiện trạng ngày 25/11/2026 (đọc code trên master `d54a4d89` và nhánh DA-42):

- `eval_batch` gọi cứng env `simple/G1WholebodyTrayTransferTeleop-v0` (cảnh `+zone1`). Env đồ gá `simple/G1WholebodyTrayTransferJigTeleop-v0` có sẵn từ DA-41 nhưng chưa lệnh eval nào dùng.
- `export_outcomes` và `place_error` dựng lại đích bằng `sample_episode`; trên cảnh đồ gá đích là `sample_jig_episode`, nên sai lệch đặt sẽ tính sai.
- `export_outcomes` để trống `failure_t`, `step_latch_t`, `at_failure`, đặt `repeat` bằng 0 và ghi `scorer_version` là một chuỗi cố định. Dòng outcome của DA-42 đã có đủ các tín hiệu đó.
- Chưa có tập điều kiện eval nào cho cảnh đồ gá.

## Cách làm

**[Đề xuất, Claude 25/11/2026.]**

1. **Cảnh là một tham số của lô eval.** `eval_batch --scene {zone1,jig2}`, mặc định `zone1` cho đúng lệnh và thư mục cũ. `jig2` chọn env đồ gá. `eval_driver` đăng ký env đồ gá và ghi `task_uid` vào dòng outcome; bản vá bộ chấm đặt trên lớp cha nên lớp đồ gá dùng luôn.
2. **Đích theo cảnh, một chỗ.** Một hàm `target_of(task_uid)` dùng chung cho `export_outcomes` và `place_error`: `sample_jig_episode` cho đồ gá, `sample_episode` cho phần còn lại. Dòng outcome cũ không có `task_uid` đọc là `zone1`.
3. **Tập điều kiện.** `eval_set` dựng tập từ plan của nhóm B và một release `jig2` làm mẫu; tập ghi cảnh của nó, và `eval_batch` từ chối chạy tập của cảnh này trên env của cảnh kia. Cỡ đề xuất: mức 1 và 2, mỗi mức 30 điều kiện, 3 lượt, tức 180 rollout mỗi checkpoint. Seed `1000100–1000129` ở cả hai mức: mô phỏng chỉ nhận seed eval trong dải dev `1000000–1000999` (`randomize.py`), và dải này không trùng seed train nào của run M (`500000–501189`, `520000–521212`); `eval_set --exclude-seeds-of` kiểm điều đó với bốn release của plan.
4. **K1 đủ tín hiệu.** `export_outcomes` đọc dòng outcome của DA-42: phiên bản bộ chấm, `failure_t`, `step_latch_t`, `at_failure`, bản 1 chạy kèm vào `other_verdicts`, khoảng cách tay–tay cầm vào `extrema`, `repeat` thật. Dòng cũ không có các trường đó vẫn xuất như hiện nay.

Tên số đo K1 đề xuất (hợp đồng yêu cầu hậu tố đơn vị):

| Chỗ | Tên |
|---|---|
| `at_failure` | `tilt_deg`, `tray_pos_m`, `tray_quat`, `tray_on_table` (chuỗi), `hand_contact_left`, `hand_contact_right` (bool) |
| `extrema` | `palm_handle_left_min_m`, `palm_handle_right_min_m`, `palm_handle_both_min_m`, `palm_bar_left_min_m`, `palm_bar_right_min_m`, `palm_bar_both_min_m` |
| `scorer_version` | `simple-tray-predicates@2`; bản chạy kèm `simple-tray-predicates@1`; dòng cũ giữ `simple-tray-predicates` |

## Tiêu chí chấp nhận

1. `eval_batch --scene jig2` chạy env đồ gá; mặc định giữ nguyên lệnh, thứ tự và thư mục của `zone1` (có test so lệnh).
2. Dòng outcome ghi `task_uid`. Tập điều kiện ghi cảnh; chạy lệch cảnh bị từ chối trước khi mở sim.
3. `export_outcomes` và `place_error` dùng đích đồ gá cho rollout đồ gá; có test rằng một khay nằm đúng đồ gá cho sai lệch đặt gần 0, và cùng trạng thái đó tính theo đích `zone1` thì không.
4. `export_outcomes` xuất đủ tín hiệu của DA-42 thành `RolloutOutcome` hợp lệ, một bản ghi cho mỗi lượt (`repeat`); dòng outcome trước DA-42 xuất ra đúng như trước (test giữ nguyên).
5. Tập điều kiện `jig2` dựng được bằng lệnh, có `conditions.sha256`, seed không trùng seed train.
6. Thử trên cảnh `jig2` trên laptop: cổng phát lại một episode của `fwdata/datasets/tray-s1-jig2-20261122` qua `eval_driver` thật, rồi xuất K1 từ dòng outcome đó; kết quả ghi trong tài liệu. Hạn 28/11/2026.
7. Runbook cho Hiếu: eval một checkpoint trên `jig2`, 3 lượt, kèm ước lượng giờ và CU. Không chạy gì trên `rtx3060` hay Colab trong story này khi Hiếu chưa bảo.
8. `uv run ruff check`, `uv run mypy`, `uv run pytest`, `uv run lint-imports` sạch; `check_links.py` và `pr_guard.py` qua.

## Nhiệm vụ

- [x] 1. Viết story này
- [ ] 2. Eval trên cảnh đồ gá (AC 1, 2)
  - [x] 2.1 `eval_driver`: đăng ký env đồ gá, ghi `task_uid` vào dòng outcome
  - [x] 2.2 `eval_batch --scene`, từ chối lệch cảnh với tập điều kiện
- [x] 3. Đích theo cảnh trong `export_outcomes` và `place_error` (AC 3)
- [ ] 4. `export_outcomes` xuất tín hiệu của DA-42 và `repeat` (AC 4)
- [x] 5. Tập điều kiện `jig2` (AC 5)
- [ ] 6. Thử trên laptop và runbook (AC 6, 7)
  - [ ] 6.1 Cổng phát lại trên `jig2`, xuất K1, ghi kết quả
  - [ ] 6.2 Runbook eval checkpoint trên `jig2`
- [x] 8. Sửa theo review PR 221: Wilson mô tả dùng n_eff = số điều kiện; `missing` ghi lượt; `--stage1` chỉ kiểm lượt 0; báo khi thư mục có nhiều lượt hơn số đọc; `evidence` từ chối lô có `.rN`
- [ ] 7. Kiểm tra đủ, `pr_guard`, mở PR (AC 8)

Thứ tự: 2.1, 3 và 4 làm được ngay sau khi DA-42 merge. 5 và 6.2 cần plan của nhóm B.

## Phạm vi file

Theo 07 mục 3.1. File story luôn được sửa.

- `packages/flywheel-psi0/src/flywheel_psi0/tray/eval_driver.py`, `packages/flywheel-psi0/src/flywheel_psi0/tray/eval_batch.py`, `packages/flywheel-psi0/src/flywheel_psi0/tray/eval_set.py`, `packages/flywheel-psi0/src/flywheel_psi0/tray/export_outcomes.py`, `packages/flywheel-psi0/src/flywheel_psi0/tray/place_error.py`, `packages/flywheel-psi0/src/flywheel_psi0/tray/replay_server.py`, `packages/flywheel-psi0/src/flywheel_psi0/tray/export_scores.py`, `packages/flywheel-psi0/src/flywheel_psi0/tray/eval_results.py`, `packages/flywheel-psi0/src/flywheel_psi0/tray/evidence.py`
- `packages/flywheel-psi0/tests/tray/`
- `packages/flywheel-simple/src/flywheel_simple/tray/run.py`, `packages/flywheel-simple/tests/tray/test_run_eval.py`
- `docs/g0/tray/`

## Chỗ cần quyết hoặc chờ người khác

1. **DA-42 chưa merge.** Mọi nhiệm vụ code dựa trên nó. Rule của repo cấm tạo nhánh từ nhánh chưa merge, nên code bắt đầu sau khi PR 221 vào master.
2. **Plan của nhóm B.** `eval_set` cần một plan có `eval.by_level` và `run_plan_id`. Cần nhóm B cho biết plan nào, và dải seed train để tránh.
3. **Cỡ tập điều kiện** (30 điều kiện × 2 mức × 3 lượt) là đề xuất; Hiếu chốt. Ước lượng, chưa đo: 18 lô 10 rollout × 50–61 phút ≈ 15–18 giờ trên một làn cho mỗi checkpoint, khoảng 5–6 giờ với ba làn.
4. **Tên số đo K1.** `configs/eval/agentqa/tasks/tray.yaml` (`signal_measures`, file của DA-43) ghi tên là giả định cho tới khi bộ xuất chốt. Nhóm C cần thêm ba tín hiệu `tray_tilt_at_failure`, `tray_contact_at_failure`, `tray_on_table_at_failure` trỏ vào tên ở bảng trên. DA-47 không sửa file đó.
7. **`task_id` của outcome giữ `tray` trên cả hai cảnh** (25/11/2026 chưa hỏi PO): lane chọn task view theo `task_id` và `admit` của agentqa từ chối bản ghi lệch `task_id`, nên đặt id riêng cho đồ gá sẽ bị từ chối cho tới khi có task view đồ gá. Cảnh nhận ra qua `final.target_xy_m`. `evidence.py` vẫn dùng đích `zone1`: không chạy nó trên lô `jig2`.
5. **`run.py` bị plan đóng băng ghim.** Nếu phải sửa `run.py`, `Decision` của DA-42 hết hiệu lực với file đó và cần ghi lại. Ưu tiên cách không đụng `run.py`.
6. **Thay đổi hợp đồng:** không cần. `RolloutOutcome` đã đủ chỗ; nếu phát hiện thiếu thì dừng và đề xuất PR hợp đồng cho Hiếu.

## Ghi chú cho người làm

- Không sửa `flywheel.contracts`, `simple_task.py`, `jig_task.py`, `jig.py`, `predicates.py` và `configs/`.
- Lane không đọc `outcomes.jsonl`; chỉ đọc `RolloutOutcome` (03 mục 7.3).
- Kết quả thi lại của `C70_R1` không trình bày (Hiếu, 16/11/2026).
- Số chưa đo ghi là ước lượng.

## Kiểm thử

- CPU, bộ giả: test lệnh của `eval_batch` theo cảnh, test `export_outcomes` với dòng outcome mới và cũ, test đích theo cảnh.
- Venv SIMPLE trên laptop: cổng phát lại trên `jig2` (AC 6).

## Người phụ trách

| Vai | Người |
|---|---|
| Làm | Hiếu, cùng Claude |
| Duyệt và merge | Hiếu |

## Change log

| Ngày | Thay đổi | Người |
|---|---|---|
| 25/11/2026 | Viết story từ kế hoạch vòng chung kết, nhóm A việc 2 và 3 | Claude (chờ PO xem) |

## Ghi chép khi làm

- Công cụ AI đã dùng: Claude Code (Fable thiết kế và duyệt; Opus, Sonnet viết code).
