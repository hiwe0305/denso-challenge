# DA-08 · Bộ phát hiện lỗi train F-TRAIN và lỗi offline F-OFF

## Trạng thái

| Trường | Giá trị |
|---|---|
| Trạng thái | Sẵn sàng (PO duyệt 28/10/2026, từ nháp của Châu ở issue #6) |
| Người làm | Châu |
| Làn | Đánh giá |
| Story PRD | 9.8 · Epic 9 · FR54; [design 27/10/2026](../../superpowers/specs/2026-10-27-g1-psi0-demo-design.md) mục 8.2, 8.3, 10 |
| Nhãn | [Lõi] · `epic:9` · `gate:G2` · `area:core` |
| Sprint | S2–S3 |
| Ước lượng | 10 giờ (khoảng 8–12, 07 mục 2.2) |
| Phụ thuộc | DA-25 (file mẫu, gồm kết quả probe); schema `metrics.jsonl` (chưa có trong DA-25, xem Ghi chú); DA-19 (log thật, khoảng 6/11); DA-09 (kết quả P3, P4 thật). Trong lúc chờ code trên file mẫu của testkit |

## Story

Là kỹ sư đánh giá, tôi muốn mỗi checkpoint được kiểm động học train (T1–T8) và sai số action offline (O1–O4) từ log và probe, để loại checkpoint hỏng trước khi tốn rollout closed-loop và để chuỗi chẩn đoán có bằng chứng từ phía train.

## Tiêu chí chấp nhận

1. Đọc `metrics.jsonl` của một job qua schema trong `flywheel.contracts`, phát hiện T1–T6 và T8 đúng định nghĩa ở design mục 10. Mỗi phát hiện ghi mã lỗi, bước bắt đầu, nhóm action hoặc chiều liên quan (khi có), giá trị đo và ngưỡng.
2. T7 (quên) đọc kết quả P4 của checkpoint và của checkpoint cha; O1–O4 đọc kết quả P3. O4 dùng giới hạn khớp từ `action_layout` của embodiment, không chép số vào mã.
3. Ngưỡng (k, W, x%, N, M, ε và ngưỡng của O1–O4) nằm trong `configs/eval/diagnosis/train.yaml`, có hash. Giá trị chưa hiệu chỉnh ghi `# giả định` kèm nguồn; ngưỡng hiệu chỉnh được từ log của checkpoint công bố thì ghi cách tính.
4. Kết quả là một artifact có schema gắn vào checkpoint (đánh dấu, không xóa). Chỉ T1 được đánh dấu "dừng job"; việc dừng thật do adapter train làm, ngoài phạm vi story này.
5. Lệnh `fw eval diag-train --job <đường dẫn>` in bảng phát hiện và ghi artifact vào kho.
6. Mỗi mã T1–T8, O1–O4 có ít nhất một test dương (log hoặc probe cấy lỗi bắt được) và một test âm (log sạch không bị đánh dấu), chạy trên CPU với file mẫu.

## Nhiệm vụ

- [x] 1. Bộ đọc `metrics.jsonl` và kết quả probe qua contracts, chuỗi thời gian theo nhóm action (AC 1, 2)
- [x] 2. T1–T3: phân kỳ, không học, quá khớp (AC 1)
- [x] 3. T4–T6, T8: mất cân bằng nhóm, chiều chết, sụp mode, gradient bất thường (AC 1)
- [x] 4. T7 và O1–O4 từ P3, P4 (AC 2)
- [x] 5. Cấu hình ngưỡng có hash (AC 3)
- [x] 6. Artifact kết quả, lệnh `fw` (AC 4, 5)
- [x] 7. Bộ log cấy lỗi và test dương, âm cho từng mã (AC 6)

## Phạm vi file

Theo 07 mục 3.1. pr-guard chặn PR sửa file ngoài danh sách này; file story luôn được sửa.

- `packages/flywheel-eval/src/flywheel/eval/diagnosis/train/`
- `packages/flywheel-eval/src/flywheel/eval/api.py`, `packages/flywheel-eval/src/flywheel/eval/cli.py`, `packages/flywheel-eval/src/flywheel/eval/config.py`
- `packages/flywheel-eval/tests/unit/diagnosis/train/`, `packages/flywheel-eval/tests/contract/diagnosis/train/`
- `configs/eval/diagnosis/train.yaml`

## Ghi chú cho người làm

- Nguồn: design 27/10 mục 8.2 (trường log), 8.3 (probe), 10 (F-TRAIN, F-OFF); spec mục 6.4.
- **Hợp đồng còn thiếu** [Đề xuất]: DA-25 chưa có schema `metrics.jsonl` (DA-19 AC 3 cần "đúng schema") và chưa có artifact kết quả chẩn đoán train. Đã mở issue #5 "Contract change" cho Long và Hiếu; chờ chốt trước 30/10. Không thêm trường tạm trong code làn.
- Chỉ import nhân (`flywheel.contracts`, `flywheel.store`, `flywheel.testkit`); không import `torch` hay adapter Ψ₀. Tính toán trên số đã ghi trong log, không chạy model.
- `diagnosis/` dùng chung với DA-13: story này chỉ sửa `diagnosis/train/`.

## Kiểm thử

- Mỗi mã lỗi có một log hoặc probe cấy lỗi bị bắt và log sạch không bị đánh dấu; chạy CPU, không cần GPU.
- Khi có log thật của DA-19: chạy trên một job fine-tune, ghi số phát hiện vào ghi chép.

## Người phụ trách

- Làm: Trần Trịnh Hoàng Châu
- Duyệt và merge: Dương Đình Hiếu (người duy nhất, 07 mục 3.4)
- Bình luận: Hiếu (DA-19, lớp bọc log), Long (`decide` đọc kết quả), Hưng (Agent QA/QC đọc log train)

## Change log

| Ngày | Nội dung | Người |
|---|---|---|
| 28/10/2026 | Nháp story theo design 27/10 mục 10 và 07 mục 2.2 | Châu (chờ SM, PO) |
| 28/10/2026 | Đưa nháp của Châu (issue #6) vào repo; nhãn theo 02 bản 0.5 (story 9.8, Epic 9, cổng G2); hợp đồng còn thiếu theo dõi ở issue #5 | PO (Hiếu) |

## Ghi chép khi làm

- Giờ thực: 3h (1/11/2026) + 7h (2/11/2026: 3h sáng, 4h chiều)
- Công cụ AI đã dùng: Claude Code (Opus 5), theo plan DA-08 và DA-13 ngày 30/10/2026 (PR #18, chưa merge nên chưa liên kết được)
- Ghi chú hoàn thành:
  - 1/11/2026: làm phần không phụ thuộc hợp đồng của DA-25 (PR #22 còn mở). Xong **nhiệm vụ 5**; nhiệm vụ 1 và 2 mới có phần thuần numpy, chưa đánh dấu.
  - Nhiệm vụ 1 còn `reader.py`: cần `TrainingMetric`, `ProbeP1`, `ProbeP3`, `ProbeP4`, `ActionLayout` của DA-25. `series.py` đã xong vì chỉ là hàm thuần trên numpy.
  - Nhiệm vụ 2, 3, 4 cần `TrainSeries` của `reader.py`; đã có `finding.py` (`Finding`, `Skipped`, `DetectorResult`) là giao diện chung của mọi bộ phát hiện, theo soát của PO trên PR #18.
  - Nhiệm vụ 6 còn chờ hai chỗ hợp đồng đã nêu dưới PR #22: `TrainDiagnosis` chưa có trường `skipped` (mà `Contract` đặt `extra="forbid"`), và `ProbeP4` chưa cho T7 so với checkpoint cha ở lần fine-tune đầu.
  - Workspace chưa có thư viện đọc YAML nên `load_train_thresholds` cần thêm `pyyaml` (và `types-pyyaml` cho mypy). Theo quyết định của người làm story ngày 1/11, thêm luôn trong nhánh này; pr-guard sẽ báo R6 cho `pyproject.toml` gốc, `packages/flywheel-eval/pyproject.toml` và `uv.lock` vì ba file này ngoài Phạm vi file của DA-08. Hiếu quyết: hoặc mở rộng Phạm vi file, hoặc tách ba file đó sang một PR `chore-` của Long (07 mục 3.2).
  - Ngưỡng trong `train.yaml` đều là `# giả định` hoặc `# chốt`, chưa có số đo; hiệu chỉnh trên log thật của DA-19 trước G2. Có test chặn một dòng ngưỡng không ghi nguồn.
  - 2/11/2026: DA-25 (PR #22) và chore PyYAML (PR #29) đã merge, nên nhiệm vụ 1 và 3 hết chặn. Rebase lên `origin/master` làm biến mất luôn ba lỗi R6 ngày 1/11: `pyproject.toml`, `packages/flywheel-eval/pyproject.toml` và `uv.lock` không còn trong diff vì `pyyaml` đã vào master qua PR #29. Hiếu không phải quyết (a) hay (b) nữa.
  - Ba quyết định của issue #5 nằm trong `reader.py`, mỗi cái một test: giữ bản ghi có `attempt` lớn nhất cho mỗi `(split, step)` (không phải dòng cuối tệp, và có test cho cả hai thứ tự dòng); `"NaN"` thành float ngay lúc nạp; tín hiệu ghi thưa hơn loss được điền nan thay vì làm lệch trục step — nan là "không đo", `0.0` là cái T8 đọc thành VLM đóng băng, hai thứ không được trộn.
  - Bỏ `TrainSeries.parent_checkpoint_id`: hợp đồng đặt nó ở `ProbeP4` nên T7 đọc từ probe (issue #5 mục 2b). Thay bằng các trường định danh mà nhiệm vụ 6 cần cho `TrainDiagnosis.checkpoint_id`.
  - **File mẫu train của DA-25 chưa chạy được T2–T8** [cần Long xem]: mỗi tệp 1–6 dòng trong 5 step, mà cửa sổ của T2 là 2000 step, T4 2000 step, T5 1000 step; và quan trọng hơn, lỗi cấy nằm ở bản ghi `split: "val"` trong bốn tệp — `t4_group_loss` (`arm: 10.0`), `t5_low_variance` (`pred_var_by_dim: [0.2, 0.0]`, tệp chỉ có đúng một dòng val), `t6_std_mismatch` (`pred_std 0.01` vs `target_std 1.0`) và `t8_vlm_gradient` (`grad_norm_vlm: 1.0`). T4–T6, T8 đều là tín hiệu của split train, nên bốn tệp này ra "sạch" chứ không bắt được gì. Với `grad_norm_vlm` thì bản ghi val còn sai về nghĩa: lượt val không có gradient. Chạy cả bảy bộ phát hiện trên tám tệp cho thấy mọi mã đều `skipped` kèm lý do, không có mã nào im lặng thành sạch (FR21 đúng như thiết kế) — nhưng không tệp nào là test dương được. Bộ log cấy lỗi đủ dài là **nhiệm vụ 7** của story này, trong `packages/flywheel-eval/tests/`, nên không cần đổi file mẫu của DA-25; chỉ cần Long biết là README của fixture nói "minh hoạ" là đúng theo nghĩa hẹp.
  - T4 chỉ báo khi có một nhóm khác giảm được `ref_group_drop`: job mà mọi nhóm đều chậm là T2, gọi là T4 sẽ chỉ người đọc artifact đi thu sai loại dữ liệu. Có test cho đúng ca đó.
  - T5 và T6 không bao giờ báo chiều `masked` của `action_layout`, và `LayoutView` là nơi duy nhất đọc mask, nhóm và giới hạn khớp, nên lệnh cấm chép số của AC 2 đúng theo cấu trúc chứ không chỉ theo quy ước. Log sai số chiều so với layout thì `skipped` kèm lý do, không chấm chiều `i` vào khớp khác.
  - T6 với `target_std == 0` trên chiều không mask ra `DiagnosisSkip` kèm tên chiều, đúng ca mà Long thêm trường `skipped` cho (issue #5 chốt 1/11). T8 tách hai nhánh `T8a`, `T8b` để artifact nói rõ nửa nào chưa đo được; phát hiện vẫn mang mã `T8` vì `FindingCode` chỉ nhận T1–T8.
  - 2/11/2026 (phiên chiều): xong **nhiệm vụ 4, 6, 7**, story hết nhiệm vụ con. Trường `DiagnosisSkip` và `TrainDiagnosis.skipped` đã vào master cùng DA-25, nên chỗ hợp đồng chặn nhiệm vụ 6 đóng lại mà không phải sửa `flywheel.contracts`.
  - T7 quyết chiều so cho từng chỉ số: accuracy của P1 kém đi là giảm xuống, error của P3 kém đi là tăng lên, nên công thức `(cha − con) / cha` của plan áp cho điểm và công thức đối xứng áp cho sai số. Chỉ số chỉ có ở một bên, và chỉ số kém đi khi giá trị cha bằng 0, đều ra `skipped` kèm tên chỉ số chứ không ra sạch.
  - Câu hỏi thứ hai gửi Long ở plan (bảo đảm hai bên chạy cùng bộ probe) **không cần sửa hợp đồng**: `ProbeP1` và `ProbeP3` đã có `dataset_sha256`, nên T7 chỉ so khi hai bên trùng hash, lệch hash thì `skipped`. Giới hạn còn lại vẫn đúng như plan ghi: lần fine-tune đầu từ checkpoint công bố không có P4 của cha nên T7 `skipped`, đây là ca của demo.
  - O4 giữ hai nhánh của plan: `out_of_limit_dims` không rỗng là nhánh (a), đúng với `max_fraction: 0.0` đã chốt; nếu ai đặt `max_fraction > 0` thì ra `skipped` mã `O4b` vì P3 không ghi tỉ lệ khung. Chiều `masked`, chiều layout không có, và chiều layout không đặt giới hạn: cả ba ra `skipped` kèm tên chiều.
  - Lệnh `fw eval diag-train` chết giữa lúc in trên console Windows: Python nhận stream cp1252 mà lý do `skipped` viết tiếng Việt. `use_utf8` trong `cli.py` đặt stream về UTF-8 trước khi in, có test trên tệp cp1252 thật. Đây là lỗi thật, không phải lỗi môi trường của máy một người: cả đội chạy Windows.
  - Kho artifact là JSONL ghi thêm (`<store>/diagnosis/train.jsonl`), mỗi lần chạy một dòng, không ghi đè: `flywheel.store` còn là khung rỗng nên làn tự giữ, đúng bất biến append-only. Khi `flywheel.store` có API thì chỉ `write_artifact` phải đổi.
  - Nhiệm vụ 7 chạy **cả 12 mã qua `diagnose_all`**, không chạy từng bộ phát hiện, để bắt ca một bộ ăn mất tín hiệu của bộ khác. Đối chứng sạch kiểm hai lần: không có phát hiện **và** không có mã nào `skipped`.
  - Chỉ `t1_nan.jsonl` của testkit bật được mã của nó, đúng như ghi chú sáng nay; 11 ca còn lại dựng log cấy lỗi đủ dài ngay trong `tests/unit/diagnosis/train/test_all_codes.py`, **không nới ngưỡng nào** trong `train.yaml`. Khoảng trống của file mẫu đã ghi trong docstring của test và cần Long xem dưới PR #22.
- File đã tạo hoặc sửa:
  - Tạo: `packages/flywheel-eval/src/flywheel/eval/diagnosis/train/{__init__,series,finding,reader,divergence,learning,groups,dimensions,gradients,forgetting,offline,artifact}.py`, `packages/flywheel-eval/tests/unit/diagnosis/train/{conftest,test_series,test_finding,test_config,test_divergence,test_learning,test_reader,test_groups,test_dimensions,test_gradients,test_forgetting,test_offline,test_artifact,test_all_codes}.py`, `packages/flywheel-eval/tests/contract/diagnosis/train/{conftest,test_diag_train_cli}.py`, `configs/eval/diagnosis/train.yaml`
  - Sửa: `packages/flywheel-eval/src/flywheel/eval/{config,api,cli}.py`. (`pyproject.toml`, `packages/flywheel-eval/pyproject.toml` và `uv.lock` của ngày 1/11 đã bỏ khỏi nhánh sau khi rebase: `pyyaml` vào master qua PR #29.)
  - Bằng chứng (2/11/2026, phiên chiều): `uv run pytest` → 1342 passed, 38 deselected (207 test trong `tests/unit/diagnosis/train/` và `tests/contract/diagnosis/train/`); `uv run ruff check` xanh; `uv run mypy` 81 file xanh; `uv run lint-imports` 3 contract, 0 broken; `scripts/repo/check_links.py` 0 broken; `fw eval diag-train` chạy thật trên một job cấy lỗi, in T1 (stop yes), T4, T5, O2, O3, O4 và một mã `skipped`, ghi artifact vào kho
