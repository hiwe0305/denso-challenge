# 10 · Phép thử reference pipeline đã chạy

**Run thực: 2026-10-07T07:50:53Z.** Scope: `executed_reference_pipeline_not_native_vla`. Đây là dataset/model/simulator/evaluator thực thi trên CPU, không backend VLA/GR1. Website replay bản ghi đã chạy, không giả tiến độ training.

## Cấu hình khai rõ

MuJoCo Cartesian mocap effector, xyz/grip4D; proximity-triggered weld attachment; idealized scene-state adapter; scripted sequencer7stages. Predictor35×4 học absolute waypoint/grip bằng ridge MSE; không VLM/flow matching. Instruction cố định A1 qua task binding, không learned language grounding. Image trên viewer là sơ đồ từ measured positions, không camera input của model.

## Từng bước có artifact

| Bước | Input / xử lý thật | Output |
|---|---|---|
| 1 Seed | Reference expert điều khiển world, scorer chấm | seed-episode.json; robot-release.json |
| 2 QA | Rights/profile/frame/time/shape/finite/root/split | Fail → reject, không train |
| 3 Baseline R | Fit action targets trên seed recording | R.checkpoint.json + loss/reload/hash |
| 4 Development | Đổi object/target; same physics/binding | before.json: approach fail, bước sau not_attempted |
| 5 Evidence | predicted/sent/measured/stage timeline | report.json evidence_card; hypothesis coverage, không auto cause |
| 6 S alternative | Seed waypoint offset theo object/target;24variants execute/QA | synthetic-release.json;S checkpoint;after-synthetic.json |
| 7 C alternative | Expert full-reset correction trên development + replay seed | correction-release.json;C checkpoint;after-correction.json |
| 8 Regression | Scene gần seed riêng | Cả R/S/C pass |
| 9 Freeze/final | Recipes/checkpoints đã freeze;12scenarios mới, không train | final-results.json |
| 10 Gate | Local + final + regression + scope | S reference eligible; C reference rejected; native/real không promote |

C là **alternative từ R**, không thêm correction mặc định sau S đã thành công. Correction là expert-reset full episode, chưa actual human takeover trên policy-induced states. Native SOP cần capture mode phù hợp.

## Kết quả phép thử model thu nhỏ, không native benchmark

| Candidate | Data | Development | Final12trials | Quyết định |
|---|---|---|---|---|
| R | Một seed | Fail | 0/12 | Chưa generalize |
| S | Seed +24executed variants, cùng1independent seed root | Pass | 12/12 | Pass trong reference test scope |
| C | Seed +1correction recording | Pass | 0/12 | Không promote; local gain chưa global quality |

12trials nhỏ/deterministic, không uncertainty benchmark/statistical efficiency. R thiếu coverage trong basis đơn giản; S thêm coverage không chứng minh native VLA transfer. Human không integrated. Không measured monetary saving.

## Negative cases thực thi

- binding-fault.json: command x lệch0.08m so prediction, grasp fail → health route, không training chữa mapping.
- unknown.json: scorer grasp sensor deliberately withheld → grasp unknown; reference uncertainty gate dừng stage advance nên later not_attempted; không pass dù policy có thể di chuyển.
- zero-skill.json: zero predictor fail approach → cold-start, không quy fail các bước chưa tới.
- Validators từ chối human-motion ở robot BC, wrong29Dprofile, frame/dt sai, NaN, final contamination, clock không tăng và wrong checkpoint profile.

## Chạy lại / đọc raw

Từ repo root:

```bash
python examples/engineering-loop/run.py
python -m pytest -q examples/engineering-loop/test_pipeline.py
```

Chạy từ repository root: `python examples/engineering-loop/run.py --out examples/engineering-loop/results`; `python -m pytest -q examples/engineering-loop/test_pipeline.py`. Requirements NumPy/MuJoCo/Pytest ở examples/engineering-loop/requirements.txt. Không tải checkpoint/media hoặc dùng GPU cho reference. Website ZIP thêm bản portable của example khi xuất.

[Report](../examples/engineering-loop/results/report.json) · [Manifest và hashes](../examples/engineering-loop/results/manifest.json) · [Code](../examples/engineering-loop/run.py) · [World](../examples/engineering-loop/world.xml).

## Vì sao correction local pass nhưng final fail?

C là model35×4 fit từ seed và một correction scene. Nó khớp hai scenes đó nhưng chưa học mapping tổng quát trong basis/domain reference. 0/12 chỉ kết quả12newscenes của phép thử này, không correction trên GR00T. “Reject” ở đây là không chọn candidate reference, chưa nghiệm thu task DENSO. S có24variant recordings, C chỉ1correction; không matched acquisition/compute study, không causal comparison hoặc ROI. Native walkthrough ở13.

## Để chứng minh native chạy cần thêm

FluxVLA/code+checkpoint pin; actual GR1 task/profile/controller; camera/state/action datasets; native objective/gradient/reload/debug-optimized parity; learned natural closed-loop; native source generator/human route; independent scorer/evidence/final. Tất cả hiện not-tested/not-integrated, không lấy file reference thay thế. Quy trình và contracts ở02/08/11.
