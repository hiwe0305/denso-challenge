# DA-42 · Bộ chấm khay bản 2, tín hiệu lỗi trong outcome và eval nhiều lượt mỗi điều kiện

## Trạng thái

| Trường | Giá trị |
|---|---|
| Trạng thái | Đang làm (Claude viết 19/11/2026 theo kế hoạch hai tuần cho vòng chung kết mà PO duyệt ngày 19/11/2026) |
| Người làm | Hiếu (làm cùng Claude) |
| Làn | Adapter simulator (`flywheel-simple`) và eval task khay (`flywheel-psi0`, `tray/`) |
| Story PRD | Spec v10.6 mục 6.4 (kiểm hệ thống và bộ chấm trước dữ liệu); design 28/10/2026 mục 3.2–3.4; hai phiếu soạn sẵn ở [docs/he/tray.md](../../he/tray.md) mục 20.11 |
| Nhãn | [Adapter] · `area:sim` · `area:eval` |
| Sprint | Sau demo 17/11/2026, kế hoạch hai tuần cho vòng chung kết |
| Ước lượng | 14 giờ (ước lượng) |
| Phụ thuộc | Không chờ ai để làm phần CPU. Phần đo trên rollout thật cần một lô eval trên SIMPLE, chỉ Hiếu chạy (runbook ở [scorer-v2.md](../../g0/tray/scorer-v2.md)) |

## Story

Là người chạy vòng Failure → Data trên task khay, tôi muốn bộ chấm của task khay chấm đúng hai chỗ đã thấy sai, outcome của mỗi rollout ghi đủ tín hiệu để giải thích nhãn lỗi, và eval chạy được nhiều lượt mỗi điều kiện, để chẩn đoán ở bước 4 (spec 6.4) không còn "CHƯA RÕ" vì thiếu tín hiệu và để tỉ lệ thành công mỗi điều kiện không còn là một lần tung đồng xu.

## Quan hệ với DA-36, DA-37, DA-38

- **DA-36** (Châu, Hiếu; xong) dựng khung scorer của làn Đánh giá (`flywheel.eval.scorer`, `configs/eval/scorer/tray.yaml`). Bộ chấm mà DA-42 sửa là bộ khác: vị từ của task SIMPLE ở `flywheel_simple/tray/predicates.py` (DA-32), cái quyết `check_success`, nhãn lỗi và `scorer_steps` của outcome. `configs/eval/scorer/tray.yaml` chỉ chép ngưỡng (`r_reach`, `tilt_max_deg`) và không mã nào của làn đọc chúng, nên DA-42 không sửa file đó.
- **DA-37** (Châu; đang làm) đối chiếu scorer của làn với cờ `check_success` của SIMPLE và hiệu chỉnh τ. Phiếu "DA-37" soạn ở tray.md 20.11 nhắm vào `predicates.py`, nằm ngoài phạm vi file của DA-37, nên DA-42 nhận phiếu đó. Hệ quả cho DA-37: cờ `check_success` của rollout mới đến từ bộ chấm bản 2; báo cáo đối chiếu của DA-37 đã ghi `scorer_version` của làn, còn phiên bản bộ chấm SIMPLE nằm trong outcome (`scorer_version`) mà DA-42 thêm.
- **DA-38** (Hiếu; xong) ghi `TraceStep` mỗi chu kỳ. Phiếu "DA-38" ở tray.md 20.11 xin thêm tín hiệu lỗi vào **outcome**, không vào trace. DA-38 đã xong và hợp đồng `TraceStep` không đổi, nên DA-42 làm phiếu đó trong dòng outcome; không chạm `flywheel.contracts` hay `flywheel_simple/trace/`.

## Tiêu chí chấp nhận

1. Outcome của rollout eval có thêm, chỉ thêm (trường cũ giữ tên, kiểu và nghĩa): `failure_t`; tại `failure_t`: bàn khay đang nằm, tiếp xúc tay–khay từng tay, độ nghiêng và tư thế khay; thời điểm chốt của từng bước trong bảy bước; khoảng cách nhỏ nhất từ điểm lòng bàn tay tới tâm tay cầm của từng tay.
2. Bộ chấm có số phiên bản (`SCORER_VERSION = 2`), ghi trong mọi outcome của eval. Bản 2 sửa `approach_a` và `L-TRAY-TILT`; mỗi sửa có lý do từ hình học hoặc từ mã, và bằng chứng từ dữ liệu đã ghi nếu có. Bản 1 vẫn chạy được (`StepTracker(..., version=1)`) và eval ghi kết quả của bản 1 trên cùng rollout cạnh bản 2, để so trên cùng một lượt.
3. Nơi gộp kết quả (`eval_results`, `place_error`) ghi phiên bản bộ chấm trong kết quả và từ chối gộp hay ghép cặp hai phiên bản khác nhau, trừ khi người chạy khai rõ; dòng outcome không có `scorer_version` là "không ghi", không được coi im lặng là bản nào.
4. `eval_batch --repeats N` chạy N lượt mỗi điều kiện, mặc định 1 cho đúng thứ tự và thư mục như cũ. Kết quả có số thành công từng điều kiện, tỉ lệ qua từng bước và khoảng Wilson tính với cỡ mẫu hiệu dụng khi các lượt của một điều kiện tương quan; cách tính ghi trong kết quả.
5. Phần thuần có test CPU; phần cần MuJoCo có test gắn marker `sim`, chạy trong venv SIMPLE. Runbook cho Hiếu chạy lô eval đo bộ chấm bản 2.
6. Tài liệu `docs/g0/tray/scorer-v2.md`: mỗi thay đổi, bằng chứng, điều chưa kiểm.

## Nhiệm vụ

- [x] 1. Viết story này (AC 1–6)
- [ ] 2. Tín hiệu lỗi trong outcome (AC 1)
  - [x] 2.1 `StepTracker` ghi tín hiệu: `failure_t`, trạng thái lúc lỗi, thời điểm chốt từng bước, khoảng cách lòng bàn tay–tay cầm nhỏ nhất
  - [x] 2.2 `eval_driver` ghi tín hiệu, `scorer_version` và kết quả của bản 1 trên cùng rollout vào dòng outcome
- [ ] 3. Bộ chấm bản 2 (AC 2, 3)
  - [x] 3.1 Số phiên bản; `approach_a` đo tới đoạn tay cầm và chốt khi hai tay đã cầm
  - [x] 3.2 `L-TRAY-TILT` chỉ khi robot còn cầm khay bằng hai tay
  - [x] 3.3 `eval_results`, `place_error` ghi phiên bản và từ chối trộn
- [ ] 4. Eval nhiều lượt mỗi điều kiện (AC 4)
  - [ ] 4.1 `eval_batch --repeats N`, hạt nhiễu policy khác nhau theo lượt
  - [ ] 4.2 `eval_results`: số thành công từng điều kiện, tỉ lệ từng bước, Wilson theo cỡ mẫu hiệu dụng
- [ ] 5. Test MuJoCo và runbook (AC 5)
  - [ ] 5.1 Test `sim`: khay rơi nghiêng trên cảnh thật, bản 1 gắn `L-TRAY-TILT`, bản 2 không
  - [ ] 5.2 Runbook đo bộ chấm bản 2 trên một lô eval
- [ ] 6. Tài liệu `docs/g0/tray/scorer-v2.md` (AC 6)

## Phạm vi file

Theo 07 mục 3.1. pr-guard chặn PR sửa file ngoài danh sách này; file story luôn được sửa.

- `packages/flywheel-simple/src/flywheel_simple/tray/predicates.py`
- `packages/flywheel-simple/src/flywheel_simple/tray/run.py` (hạt nhiễu policy theo lượt)
- `packages/flywheel-simple/tests/tray/test_predicates.py`, `packages/flywheel-simple/tests/tray/test_predicates_v2.py`, `packages/flywheel-simple/tests/tray/test_predicates_sim.py`, `packages/flywheel-simple/tests/tray/test_run_eval.py`
- `packages/flywheel-psi0/src/flywheel_psi0/tray/eval_driver.py`, `packages/flywheel-psi0/src/flywheel_psi0/tray/eval_batch.py`, `packages/flywheel-psi0/src/flywheel_psi0/tray/eval_results.py`, `packages/flywheel-psi0/src/flywheel_psi0/tray/place_error.py`
- `packages/flywheel-psi0/tests/tray/test_psi0_tray_eval_driver.py`, `packages/flywheel-psi0/tests/tray/test_psi0_tray_eval_batch.py`, `packages/flywheel-psi0/tests/tray/test_psi0_tray_eval_results.py`, `packages/flywheel-psi0/tests/tray/test_psi0_tray_place_error.py`
- `docs/g0/tray/scorer-v2.md`, `docs/g0/tray/README.md` (một dòng liên kết)

Không chạm: `simple_task.py`, `randomize.py`, `mjcf.py`, planner và `configs/sim/tray.yaml` (DA-41); `flywheel-eval` (DA-43, DA-44 và làn Đánh giá); `flywheel.contracts`.

## Chỗ cần quyết hoặc chờ người khác

1. **Outcome ngoài eval không có phiên bản.** `TrayTransferEnv.outcome()` nằm trong `simple_task.py` (DA-41 đang giữ). DA-42 thêm trường bằng bản vá lúc chạy trong `eval_driver`, như `scorer_steps` đã làm, nên chỉ outcome của eval có `scorer_version`. Outcome của replay QA và sinh dữ liệu vẫn chấm bằng bản 2 (bộ chấm mặc định đổi) mà không ghi phiên bản. Đề xuất PR riêng sau DA-41: `outcome()` thêm `**self.task.tracker.outcome_fields()`.
2. **Đổi bộ chấm làm số cũ hết so được** (spec 6.4, tray.md 20.3). Bản 2 không áp lại cho các lô đã chấm; số của chúng vẫn là bản 1. Mọi so sánh bản 1 và bản 2 dùng cặp kết quả trên cùng rollout mà eval ghi (AC 2), không so hai lô.
3. **Bộ chấm mặc định đổi cho mọi nơi dùng `StepTracker`**, gồm `check_success` khi sinh S1, S2 và replay QA. Cả hai sửa chỉ nới (không làm lượt nào đang thành công thành thất bại), nên episode đã nhận vẫn nhận.

## Ghi chú cho người làm

- Mã trong `predicates.py` thuần, không import `mujoco`; mọi tín hiệu tính từ `TrayState`.
- `eval_driver` chạy trong venv SIMPLE; test CPU dùng bản giả như cũ.
- Không chạy job trên `rtx3060` hay Colab; runbook để Hiếu chạy.

## Kiểm thử

- `uv run pytest packages/flywheel-simple/tests/tray packages/flywheel-psi0/tests/tray`
- `MUJOCO_GL=egl PYTHONPATH=packages/flywheel-simple/src fwdata/simple/.venv/bin/python -m pytest packages/flywheel-simple/tests/tray/test_predicates_sim.py -m sim`
- `uv run ruff check`, `uv run mypy`, `uv run lint-imports` theo README gốc.

## Người phụ trách

- Làm: Hiếu, cùng Claude
- Duyệt và merge: Dương Đình Hiếu (người duy nhất, 07 mục 3.4)
- Bình luận: Châu (DA-37, cờ `check_success`), Long (Vòng, đọc nhãn lỗi)

## Change log

| Ngày | Nội dung | Người |
|---|---|---|
| 19/11/2026 | Viết story từ hai phiếu soạn sẵn ở tray.md 20.11 và yêu cầu eval nhiều lượt | Claude (chờ PO xem) |

## Ghi chép khi làm

- Công cụ AI đã dùng: Claude Code.
