# DA-08 và DA-13 · Plan triển khai chuỗi chẩn đoán của làn Đánh giá

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Mục tiêu:** Hai bộ phát hiện lỗi của làn Đánh giá chạy được trên CPU: DA-08 đọc `metrics.jsonl` và kết quả probe để bắt T1–T8 (F-TRAIN) và O1–O4 (F-OFF); DA-13 đọc `Trace` và log RTC để kiểm hệ thống R1–R6 (F-SYS) rồi gắn giả thuyết stage kèm bằng chứng probe. Mỗi mã lỗi có một test dương và một test âm.

**Kiến trúc:** Mọi thứ nằm trong `packages/flywheel-eval`, chỉ import nhân (`flywheel.contracts`, `flywheel.store`, `flywheel.testkit`) cộng `numpy`. Không `torch`, không adapter, không chạy model — toàn bộ tính trên số đã ghi trong log và kết quả probe. Trong mỗi nhánh `diagnosis/` có hai lớp tách rời: một **lớp đọc** (`reader.py`) chuyển bản ghi hợp đồng thành chuỗi thời gian thuần numpy, và các **bộ phát hiện** chỉ làm việc trên chuỗi đó. Khi schema hợp đồng chốt khác đề xuất ở issue #5 thì chỉ sửa lớp đọc, bộ phát hiện không đổi. Ngưỡng không nằm trong mã: mọi con số đọc từ YAML trong `configs/eval/diagnosis/`, và artifact kết quả ghi lại `sha256` của file cấu hình đã dùng.

**Công nghệ:** Python của workspace, `numpy`, `typer` (lệnh `fw`), `pytest`. Không phụ thuộc GPU, SIMPLE hay Ψ₀.

**Nguồn:** [design 27/10/2026](../specs/2026-10-27-g1-psi0-demo-design.md) mục 8.2 (trường log), 8.3 (probe P1–P4), 10 (bảng lỗi); [spec v10.5](../../spec-v10-failure-to-data.md) mục 6.4 (thứ tự kiểm hệ thống, bước 4b, bảng quy lỗi stage đã chốt), 7.6 (nghiệm thu trên lỗi cấy); story [DA-08](../../product/stories/DA-08-phat-hien-loi-train-va-offline.md), [DA-13](../../product/stories/DA-13-quy-loi-ve-stage.md); hợp đồng còn thiếu ở issue #5.

## Điều kiện tiên quyết

Tình trạng 31/10/2026:

| Điều kiện | Trạng thái 31/10 | Chặn gì |
|---|---|---|
| PR #17 `chore-restructure` | **Đã merge 30/10** (`3015b6f`, `16811eb`, `bf773b4`). `packages/flywheel-eval/src/flywheel/eval/diagnosis/` và `configs/eval/` đã có trên `master` | Không còn chặn gì |
| DA-25 (Long): schema `metrics.jsonl`, `TrainDiagnosis`, trường của P3 và P4, file mẫu trong `flywheel.testkit` | PR #22 mở từ 31/10, chờ Hiếu duyệt | Nhiệm vụ 1 và 6 của DA-08; nhiệm vụ 1 và 5 của DA-13 |

DA-25 là điều kiện tiên quyết duy nhất còn lại. CLAUDE.md không cho tạo nhánh từ nhánh chưa merge, nên **không** rẽ nhánh từ `DA-25-artifact-contracts` để chạy sớm. Trong lúc chờ DA-25, phần làm được là nhiệm vụ 5 của DA-08 và nhiệm vụ 4 của DA-13 (nội dung YAML ngưỡng, không phụ thuộc hợp đồng), cộng `series.py` của nhiệm vụ 1 DA-08 vì nó chỉ là hàm thuần trên numpy.

**Soát PR #22 ngày 31/10:** bản ghi `TrainingMetric`, `ProbeP1`–`P4` và `ActionLayout` đủ cho mọi công thức của DA-08 (chi tiết ở bảng mục "Quyết định chưa chốt"). Còn **hai chỗ phải chốt với Long trước khi làm nhiệm vụ 6 của DA-08 và nhiệm vụ 4 của cả hai story**; đã nêu dưới PR #22:

| # | Chỗ | Vì sao chặn | Đề xuất |
|---|---|---|---|
| 1 | `TrainDiagnosis` không có trường `skipped`, và `Contract` đặt `extra="forbid"` (`additionalProperties: false` trong schema) | Nhiệm vụ 6 phải ghi `DetectorResult.skipped` vào artifact. Không có trường thì mã `skipped` biến mất khỏi artifact — đúng điều FR21 cấm, và cũng là mục 1 trong review của PO cho plan này. Hợp đồng `forbid` nên làn **không** thêm được trường tạm (CLAUDE.md, 03 mục 7.3) | Thêm `DiagnosisSkip(code: str, reason: str)` và `TrainDiagnosis.skipped: list[DiagnosisSkip]` (mặc định rỗng, nên tương thích ngược). `code` rộng hơn `FindingCode` vì có nhánh như `T8a` |
| 2 | `ProbeP4` chứa `p1`, `p3` của **chính checkpoint con**, không chứa số của cha | T7 cần `(cha − con) / cha`, nên phải nạp P4 của cha theo `parent_checkpoint_id`. Với lần fine-tune **đầu tiên** từ checkpoint Ψ₀ công bố thì cha không có P4 (design mục 8.3: P4 chạy "sau fine-tune"), nên T7 luôn `skipped` ở đúng ca quan trọng nhất của demo | Hỏi Long và Hiếu: cho T7 so P4 của con với `ProbeP1`, `ProbeP3` độc lập của cha được không, và nếu được thì hợp đồng cần bảo đảm hai bên chạy trên cùng bộ probe (ví dụ một trường `probe_set_id` chung). Nếu không bảo đảm được thì T7 chỉ chạy từ lần fine-tune thứ hai, và plan ghi rõ giới hạn đó |

Cả hai là PR hợp đồng nhỏ của Long, Hiếu duyệt (07 mục 2.0 luật 4). DA-08 nhiệm vụ 6 **dừng** tới khi chỗ 1 có kết luận.

Nếu DA-25 merge mà thiếu một trường trong bảng dưới thì **dừng** nhiệm vụ con đó, ghi vào issue #5, không thêm trường tạm vào `flywheel.contracts` và không đọc trường không có trong hợp đồng (CLAUDE.md, 03 mục 7.3).

## Ràng buộc chung

- Chỉ import `flywheel.contracts`, `flywheel.store`, `flywheel.testkit`, `numpy`, `typer`, thư viện chuẩn. Một `import torch` hay `import flywheel_psi0` làm `lint-imports` đỏ.
- `diagnosis/` dùng chung với DA-13 và với `agentqa/` của Hưng. DA-08 chỉ sửa `diagnosis/train/`; DA-13 chỉ sửa `diagnosis/system/` và `diagnosis/stage/`. File chung của package (`api.py`, `cli.py`, `config.py`) do Châu giữ (07 mục 2.1) nên hai story sửa được, nhưng mỗi lần sửa chỉ thêm, không đổi chữ ký hàm đã có.
- Không con số ngưỡng nào trong mã `.py`. Giá trị chưa hiệu chỉnh ghi `# giả định` kèm nguồn trong YAML; giá trị hiệu chỉnh được từ log của checkpoint công bố thì ghi cách tính ngay trên dòng đó.
- Artifact kết quả là **đánh dấu, không xóa**: ghi thêm bản ghi mới vào kho, không sửa hay xóa bản ghi cũ của cùng checkpoint.
- Chỉ T1 được đặt `stop_job=true`. Việc dừng job thật do adapter train làm, ngoài phạm vi hai story.
- Giả thuyết stage của DA-13 là **đề xuất cho kỹ sư xác nhận**, không tự chuyển thành can thiệp; không có đường nào từ `diagnosis/stage/` sang `acquisition`.
- Mọi test chạy trên CPU, không marker đặc biệt, vào `uv run pytest` mặc định.
- Commit trên nhánh `DA-08-train-offline-detectors` và `DA-13-system-stage-attribution`: dòng đầu `DA-08/<nhiệm vụ con>: <việc, tiếng Anh, thể mệnh lệnh>`, thân ghi AC liên quan, bằng chứng, dòng cuối `Time-spent: <giờ>h` (hỏi Châu số giờ, không tự đoán).
- Mỗi nhiệm vụ con xong thì đánh `[x]` cho nhiệm vụ con đó trong file story, trong cùng commit.

## Chỗ cần soát kỹ

1. **Job resume làm bản ghi trùng.** `metrics.jsonl` của job chạy tiếp trên Colab có hai bản ghi cùng `(job_id, split, step)` khác `attempt`. Nếu không xử lý, T1 thấy loss "tăng k lần" chỉ vì hai lần đo cạnh nhau thuộc hai lần chạy. PR #22 có `attempt` nhưng README nói rõ người dùng tự chọn cách lấy, nên lớp đọc quyết một lần cho cả hai story: **giữ bản ghi có `attempt` lớn nhất**, không giữ "bản ghi cuối trong file", vì thứ tự dòng không bảo đảm. Có test riêng cho một file mà `attempt` cao hơn nằm trước trong file.
2. **Tần số ghi log đổi giữa các job.** Mọi cửa sổ đếm theo `step`, không theo số dòng. Một test cho hai file cùng nội dung nhưng tần số ghi khác nhau phải ra cùng kết luận.
3. **T3 báo nhầm trên job bình thường.** Loss train theo batch nhiễu hơn loss val; không làm mượt thì T3 bật trên job đang học tốt. Test âm phải có một job sạch với loss train răng cưa.
4. **Chiều bị mask.** G1 có 5 chiều đệm (S1-07). T5 và T6 chạy trên chiều mask sẽ báo lỗi hàng loạt trên mọi checkpoint. Test phải có một file mẫu mà đúng chiều đệm có phương sai 0 và không được đánh dấu.
5. **Thứ tự kiểm hệ thống không được đổi.** Spec mục 6.4 là thứ tự có nghĩa: một episode trễ camera cũng có sai số bám lệnh cao, nên nếu kiểm R1 trước R3 thì ra sai lớp. Test phải có một episode hỏng ở hai chỗ và kiểm rằng kết luận là lớp của bước sớm hơn.
6. **Thiếu tín hiệu phải ra CHƯA RÕ, không ra "sạch".** Trace thiếu trường hoặc camera mất khung mà vẫn chấm tiếp là lỗi nguy hiểm nhất của DA-13, vì nó biến một episode không chẩn đoán được thành một episode "không phải lỗi hệ thống" rồi quy sang stage.
7. **Góc và phân vị.** τ lấy phân vị 99; với episode ngắn (dưới 100 mẫu) phân vị 99 gần như là giá trị lớn nhất. Lớp đọc phải báo số mẫu cùng giá trị τ để người đọc biết độ tin.

## Quyết định chưa chốt, ảnh hưởng plan

Bốn câu hỏi hợp đồng ở issue #5 đã có câu trả lời trong PR #22 (DA-25, mở 31/10, chờ Hiếu duyệt). Plan đọc theo PR #22; nếu bản merge khác thì sửa lại bảng này trước khi code.

| Chỗ | Trạng thái 31/10 | Cách plan xử lý |
|---|---|---|
| `vlm_frozen` ở bản ghi log hay ở `TrainSpec`/RunPlan (issue #5 mục 2a) | PR #22: `TrainingMetric.vlm_frozen: bool`, **bắt buộc** ở mỗi bản ghi | T8 nhánh (a) chạy trên mọi bản ghi hợp lệ. `Skipped("T8a", …)` chỉ còn cho file cũ trước hợp đồng; giữ nhánh đó nhưng không còn là ca chính |
| `parent_checkpoint_id` ở P4 hay ở `metrics.jsonl` (mục 2b) | PR #22: `ProbeP4.parent_checkpoint_id: str` bắt buộc, không có trong `TrainingMetric` | T7 đọc P4 của con, lấy `parent_checkpoint_id` từ đó, rồi nạp P4 của cha theo định danh ấy. Không có P4 của cha → `Skipped("T7", …)` (xem câu hỏi gửi Long dưới đây) |
| `attempt` của job resume (mục 2c) | PR #22: `TrainingMetric.attempt: int`, tăng mỗi lần chạy lại. README của fixture ghi rõ **người dùng tự chọn cách lấy** | Lớp đọc chọn bản ghi có `attempt` lớn nhất cho mỗi `(job_id, split, step)`, không phải "bản ghi cuối trong file": thứ tự dòng không bảo đảm. `n_dropped_duplicates` đếm số bản ghi bị bỏ |
| `action_layout` vào story nào (mục 2d) | PR #22: `ActionLayout.dimensions: list[ActionDimension]`, mỗi chiều có `group`, `masked`, `limit_low`, `limit_high` | T5, T6, O1, O4 lấy nhóm, mask và giới hạn từ đó. `masked_dims` và `limit_*` là **dẫn xuất** trong lớp đọc, không phải trường hợp đồng; không chép số vào mã (AC 2) |

Hai chỗ `metrics.jsonl` khác dự đoán của plan, lớp đọc phải xử:

- **Loss không hữu hạn là chuỗi.** `TrainingMetric.loss: float | Literal["NaN", "Infinity", "-Infinity"]` với `allow_inf_nan=False`, để JSONL vẫn là JSON hợp lệ. Lớp đọc đổi ba chuỗi đó thành `float("nan")`, `inf`, `-inf` ngay khi nạp, nên T1 nhánh (a) vẫn chỉ kiểm `np.isfinite`. Một test riêng cho việc này.
- **`loss_by_chunk_pos` nằm ở `TrainingMetric`, không ở P3.** O2 vẫn đọc `ProbeP3.error_by_chunk_pos` (sai số offline), còn `loss_by_chunk_pos` của log là tín hiệu train; hai thứ khác nhau, không trộn.
- **`DiagnosisFinding.threshold` là `float | None`** và `value` nhận cả chuỗi không hữu hạn. `Finding` nội bộ của làn giữ `threshold: float | None` cho khớp, và lúc ghi artifact thì đổi `value` không hữu hạn về chuỗi tương ứng.

**Bảng quy lỗi stage [Đã chốt 30/10/2026]** (quyết định của PO khi duyệt PR này; spec v10.5 mục 6.4, design mục 10 sửa cho khớp). Dùng **một bảng duy nhất** là bảng của design mục 10, với can thiệp của dòng Stage 1 đổi thành "ghi nhận và báo cáo" theo spec mục 6.7 và 7.3. `stage.yaml` không còn khóa `table_variant` và không còn dòng `source: spec-v10.4`; nhiệm vụ 5 của DA-13 làm theo bảng đã chốt, không còn chờ quyết định nào.

---

## DA-08 · Lỗi train F-TRAIN và lỗi offline F-OFF

### Nhiệm vụ 1: Lớp đọc `metrics.jsonl` và kết quả probe

**File:**
- Tạo: `packages/flywheel-eval/src/flywheel/eval/diagnosis/train/__init__.py`, `reader.py`, `series.py`
- Test: `packages/flywheel-eval/tests/unit/diagnosis/train/conftest.py`, `test_reader.py`

**Giao diện:**
- Nhận: bản ghi `TrainingMetric` của `metrics.jsonl` và các artifact `ProbeP1`, `ProbeP3`, `ProbeP4` theo schema của `flywheel.contracts` (DA-25, PR #22); `ActionLayout` của embodiment.
- Cho ra: `TrainSeries` với `step: np.ndarray`, `loss_train`, `loss_val` (cặp `(step, value)` riêng cho từng split), `loss_by_group: dict[str, np.ndarray]`, `pred_var_by_dim: np.ndarray` dạng `(n_records, n_dims)`, `pred_std`, `target_std`, `grad_norm_vlm`, `grad_norm_action`, `vlm_frozen: bool | None`, `parent_checkpoint_id: str | None`, `n_dropped_duplicates: int`; cộng `ProbeView` cho P3 và P4.
- Hai việc lớp đọc làm ngay khi nạp: đổi `loss` chuỗi (`"NaN"`, `"Infinity"`, `"-Infinity"`) thành `float` không hữu hạn, và chọn bản ghi có `attempt` lớn nhất cho mỗi `(job_id, split, step)`. Sau hai bước này bộ phát hiện không bao giờ thấy chuỗi hay bản ghi trùng.
- `LayoutView` là dẫn xuất từ `ActionLayout.dimensions`: `masked_dims: list[int]`, `groups: dict[str, list[int]]`, `limit_low`, `limit_high` dạng mảng. Nó ở lớp đọc, không phải trường hợp đồng, nên khi `ActionLayout` đổi hình dạng thì chỉ sửa một chỗ.

`series.py` chỉ chứa hàm thuần trên numpy mà bộ phát hiện dùng chung: `window_mask(step, start, width)`, `median_in_window`, `at_val_points`, `relative_drop`, `linear_slope`, `percentile_with_count`. Giữ chúng tách khỏi `reader.py` để bộ phát hiện không phụ thuộc hình dạng hợp đồng.

- [ ] **Bước 1: Viết test trước**

```python
def test_reader_counts_steps_not_records(tmp_path, metrics_builder):
    dense = metrics_builder(steps=range(0, 1000, 10), loss=lambda s: 1.0)
    sparse = metrics_builder(steps=range(0, 1000, 50), loss=lambda s: 1.0)
    assert read_series(dense).step[-1] == read_series(sparse).step[-1] == 990

def test_reader_keeps_highest_attempt_not_last_line(tmp_path, metrics_builder):
    # attempt 1 ghi TRƯỚC attempt 0 trong file: thứ tự dòng không được quyết
    path = metrics_builder(
        records=[
            (0, 0, 1.0), (0, 10, 0.9), (0, 20, 0.8),
            (1, 10, 0.95), (1, 20, 0.85), (1, 30, 0.7),
        ],  # (attempt, step, loss)
        shuffle_lines=True,
    )
    series = read_series(path)
    assert series.n_dropped_duplicates == 2
    assert list(series.step) == [0, 10, 20, 30]
    assert series.loss_train[1] == pytest.approx(0.95)  # attempt 1 thắng

def test_reader_decodes_non_finite_loss_strings(metrics_builder):
    # hợp đồng ghi NaN và Inf dưới dạng chuỗi để JSONL vẫn là JSON hợp lệ
    series = read_series(metrics_builder(loss_at={500: "NaN", 600: "-Infinity"}))
    assert np.isnan(series.loss_train[series.step == 500][0])
    assert series.loss_train[series.step == 600][0] == -np.inf

def test_reader_keeps_val_and_train_separate(metrics_builder):
    series = read_series(metrics_builder(val_every=100))
    assert series.loss_val.size * 10 == series.loss_train.size

def test_reader_reports_missing_vlm_frozen(metrics_builder):
    assert read_series(metrics_builder(vlm_frozen=None)).vlm_frozen is None
```

`metrics_builder` là fixture trong `conftest.py`: nhận các tham số trên, ghi một `metrics.jsonl` hợp lệ vào `tmp_path` và trả đường dẫn. Nó là **nguồn duy nhất** sinh file mẫu trong test của DA-08, và phải dựng bản ghi qua `TrainingMetric` của contracts chứ không viết dict tay, để một trường đổi tên thì test đỏ ngay ở đây.

PR #22 đã có file mẫu trong `flywheel.testkit` ở `fixtures/training/`: `clean.jsonl` cho đối chứng sạch, và `t1_nan.jsonl`, `t2_val_high.jsonl`, `t3_overfit.jsonl`, `t4_group_loss.jsonl`, `t5_low_variance.jsonl`, `t6_std_mismatch.jsonl`, `t8_vlm_gradient.jsonl` cho bảy mã. Dùng chúng làm ca cơ bản (gọi sang testkit, không chép file vào `tests/`), và `metrics_builder` chỉ dựng thêm ca mà testkit chưa có: `attempt` trùng, tần số ghi log khác nhau, chiều đệm phương sai 0, loss train răng cưa, và `target_std == 0`. README của testkit nói rõ các file đó chỉ minh họa tín hiệu, **ngưỡng và cửa sổ thuộc DA-08**, nên không suy ngưỡng từ file mẫu.

- [ ] **Bước 2: Chạy để thấy đỏ** — `uv run pytest packages/flywheel-eval/tests/unit/diagnosis/train -v`, kỳ vọng `ImportError`.
- [ ] **Bước 3: Viết `reader.py` và `series.py`.**
- [ ] **Bước 4: Chạy để thấy xanh**, cộng `uv run lint-imports` và `uv run mypy`.
- [ ] **Bước 5: Commit** — `DA-08/1: Add the metrics.jsonl and probe reader for train diagnosis`

### Nhiệm vụ 2: T1, T2, T3

**File:**
- Tạo: `diagnosis/train/divergence.py` (T1), `learning.py` (T2, T3)
- Test: `tests/unit/diagnosis/train/test_divergence.py`, `test_learning.py`

**Giao diện:** mỗi bộ phát hiện là một hàm `detect_t1(series: TrainSeries, cfg: TrainThresholds) -> DetectorResult`.

`DetectorResult` là dataclass dùng chung cho **mọi** bộ phát hiện của DA-08, định nghĩa ở `diagnosis/train/finding.py`:

```python
@dataclass(frozen=True)
class Finding:
    code: str
    start_step: int
    group: str | None
    dim: int | None
    value: float
    threshold: float
    stop_job: bool

@dataclass(frozen=True)
class Skipped:
    code: str      # mã, hoặc nhánh của mã: "T7", "T8a"
    reason: str    # vì sao không chấm được, bằng tiếng Việt cho người đọc

@dataclass(frozen=True)
class DetectorResult:
    findings: list[Finding]
    skipped: list[Skipped]
```

Lý do có hai phần: một list rỗng không mang được thông tin "đã bỏ qua", nên nếu bộ phát hiện chỉ trả `list[Finding]` thì ca thiếu tín hiệu (T7 không có P4 của cha, T8 không có `vlm_frozen`, T6 có `target_std == 0`) im lặng thành "sạch" — đúng lỗi mà FR21 cấm. `Finding` và `Skipped` là dataclass nội bộ của làn, **không** phải bản ghi hợp đồng; việc chuyển sang artifact là nhiệm vụ 6.

Test đọc hai phần qua helper trong `conftest.py`: `codes(r) == [...]` cho `r.findings`, `skipped_codes(r) == [...]` cho `r.skipped`. `diagnose_all` gộp kết quả của mọi bộ phát hiện thành một `DetectorResult` duy nhất (nối `findings`, nối `skipped`).

Công thức, theo design mục 10 và ba câu đã chốt ở issue #5:

- **T1 · phân kỳ.** Hai nhánh. (a) Bản ghi có `loss` là NaN hoặc Inf → `Finding` tại `step` đó, `stop_job=True`, không cần cửa sổ. (b) `loss > k × min(loss trong cửa sổ W step tính lùi từ step hiện tại)` → `Finding`, `stop_job=True`. W đếm theo `step`.
- **T2 · không học.** Gọi `baseline` là trung vị `t2.baseline_val_count` lần đo val đầu. Tại lần đo val đầu tiên có `step >= t2.n_steps`: nếu `(baseline − loss_val) / baseline < t2.min_relative_drop` → `Finding` tại step đó. Không có lần đo val nào sau `n_steps` thì ghi `Skipped("T2", …)`, **không** coi là sạch.
- **T3 · quá khớp.** Tại mỗi lần đo val ở step `s`, `train_med(s)` là trung vị các bản ghi `split=train` trong khoảng `(step đo val trước, s]`. Điều kiện: dãy `train_med` giảm đơn điệu trên `M+1` điểm đo liên tiếp **và** `loss_val` tăng ở cả `M` bước đo cuối trong đó → `Finding` tại điểm đo đầu của đoạn tăng.

- [ ] **Bước 1: Viết test trước** — mỗi mã một test dương và một test âm.

```python
def test_t1_flags_nan_and_stops_job(metrics_builder, cfg):
    r = detect_t1(read_series(metrics_builder(loss_at={500: float("nan")})), cfg)
    assert codes(r) == ["T1"]
    assert r.findings[0].start_step == 500 and r.findings[0].stop_job

def test_t1_flags_spike_over_k_times_window_min(metrics_builder, cfg):
    # cfg.t1.k = 10, window_steps = 500
    r = detect_t1(read_series(metrics_builder(loss=lambda s: 0.5, loss_at={600: 8.0})), cfg)
    assert codes(r) == ["T1"] and r.findings[0].start_step == 600

def test_t1_silent_on_clean_run(clean_metrics, cfg):
    r = detect_t1(read_series(clean_metrics), cfg)
    assert codes(r) == [] and skipped_codes(r) == []

def test_t2_flags_flat_val_loss(metrics_builder, cfg):
    assert codes(detect_t2(read_series(metrics_builder(val_loss=lambda s: 1.0)), cfg)) == ["T2"]

def test_t2_ignores_one_bad_first_measurement(metrics_builder, cfg):
    # lần đo val đầu nhiễu cao; trung vị 3 điểm đầu phải hấp thụ được
    series = read_series(metrics_builder(val_loss_points={0: 9.9, 100: 1.0, 200: 0.98, 1000: 0.55}))
    assert codes(detect_t2(series, cfg)) == []

def test_t2_skips_when_no_val_after_n_steps(metrics_builder, cfg):
    # cfg.t2.n_steps = 2000 mà job dừng ở step 800: không kết luận, nhưng phải nói ra
    r = detect_t2(read_series(metrics_builder(steps=range(0, 800, 10), val_every=100)), cfg)
    assert codes(r) == [] and skipped_codes(r) == ["T2"]

def test_t3_flags_rising_val_with_falling_train(metrics_builder, cfg):
    r = detect_t3(read_series(metrics_builder(train_loss=decreasing, val_loss=rising_after(600))), cfg)
    assert codes(r) == ["T3"] and r.findings[0].start_step == 600

def test_t3_silent_on_noisy_but_healthy_train_loss(metrics_builder, cfg):
    series = read_series(metrics_builder(train_loss=decreasing_with_jitter(0.3), val_loss=decreasing))
    assert codes(detect_t3(series, cfg)) == []
```

- [ ] **Bước 2: Chạy để thấy đỏ.**
- [ ] **Bước 3: Viết `divergence.py` và `learning.py`.**
- [ ] **Bước 4: Chạy để thấy xanh.**
- [ ] **Bước 5: Commit** — `DA-08/2: Detect divergence, no-learning and overfitting (T1-T3)`

### Nhiệm vụ 3: T4, T5, T6, T8

**File:**
- Tạo: `diagnosis/train/groups.py` (T4), `predictions.py` (T5, T6), `gradients.py` (T8)
- Test: `tests/unit/diagnosis/train/test_groups.py`, `test_predictions.py`, `test_gradients.py`

Công thức:

- **T4 · mất cân bằng nhóm.** Với mỗi nhóm của `action_layout`, `drop(g) = (baseline(g) − cuối(g)) / baseline(g)` trên cửa sổ `t4.window_steps`. Nếu tồn tại nhóm có `drop < t4.min_group_drop` trong khi một nhóm khác có `drop >= t4.ref_group_drop` → `Finding` cho nhóm chậm, `group` điền tên nhóm.
- **T5 · chiều chết.** Trung bình `pred_var_by_dim[:, i]` trên cửa sổ `t5.window_steps` nhỏ hơn `t5.epsilon`, **và** chiều `i` không `masked` trong `action_layout` → `Finding` với `dim=i`. Chiều `masked` bỏ qua, không đếm.
- **T6 · sụp mode.** `pred_std[i] / target_std[i] < t6.min_std_ratio` với `target_std[i] > 0` → `Finding` với `dim=i`. `target_std[i] == 0` trên chiều không mask là dấu hiệu dữ liệu, thuộc D4, ghi `skipped` chứ không báo T6.
- **T8 · gradient bất thường.** Hai nhánh. (a) `vlm_frozen is True` và `grad_norm_vlm > t8.frozen_tolerance` → `Finding` tại step đầu tiên vượt. (b) Số bản ghi có `grad_norm_action > t8.max_grad_norm` vượt `t8.max_exceedances` → `Finding` tại step vượt đầu tiên. `vlm_frozen is None` → nhánh (a) ghi `skipped`.

- [ ] **Bước 1: Viết test trước**, mỗi mã một dương một âm. Bắt buộc có:

```python
def test_t5_ignores_padding_dims(metrics_builder, g1_layout, cfg):
    # 5 chiều đệm của G1 có phương sai 0 trên mọi job
    series = read_series(metrics_builder(zero_var_dims=g1_layout.masked_dims))
    assert codes(detect_t5(series, g1_layout, cfg)) == []

def test_t5_flags_unmasked_dead_dim(metrics_builder, g1_layout, cfg):
    r = detect_t5(read_series(metrics_builder(zero_var_dims=[14])), g1_layout, cfg)
    assert [x.dim for x in r.findings] == [14]

def test_t4_names_the_slow_group(metrics_builder, g1_layout, cfg):
    series = read_series(metrics_builder(group_drop={"hand": 0.01, "arm": 0.6, "leg": 0.5}))
    r = detect_t4(series, g1_layout, cfg)
    assert [x.group for x in r.findings] == ["hand"]

def test_t6_skips_dim_with_zero_target_std(metrics_builder, g1_layout, cfg):
    # chiều không mask mà target_std == 0 là dấu hiệu dữ liệu (D4), không phải T6
    r = detect_t6(read_series(metrics_builder(zero_target_std_dims=[14])), g1_layout, cfg)
    assert codes(r) == [] and skipped_codes(r) == ["T6"]

def test_t8_flags_nonzero_grad_on_frozen_vlm(metrics_builder, cfg):
    r = detect_t8(read_series(metrics_builder(vlm_frozen=True, grad_norm_vlm=0.4)), cfg)
    assert codes(r) == ["T8"]

def test_t8_skips_when_frozen_flag_absent(metrics_builder, cfg):
    r = detect_t8(read_series(metrics_builder(vlm_frozen=None, grad_norm_vlm=0.4)), cfg)
    assert codes(r) == [] and skipped_codes(r) == ["T8a"]
```

- [ ] **Bước 2: Chạy để thấy đỏ.**
- [ ] **Bước 3: Viết ba module.**
- [ ] **Bước 4: Chạy để thấy xanh.**
- [ ] **Bước 5: Commit** — `DA-08/3: Detect group imbalance, dead dims, mode collapse and gradient faults (T4-T6, T8)`

### Nhiệm vụ 4: T7 và O1–O4 từ P3, P4

**File:**
- Tạo: `diagnosis/train/forgetting.py` (T7), `offline.py` (O1–O4)
- Test: `tests/unit/diagnosis/train/test_forgetting.py`, `test_offline.py`

Công thức:

- **T7 · quên.** Đọc kết quả P4 của checkpoint và của `parent_checkpoint_id`. Với mỗi chỉ số chung của P1 và P3 trong P4: `(cha − con) / cha > t7.max_relative_drop` → `Finding` với `value` là mức giảm. Không có P4 của cha → ghi `skipped`, **không** coi là sạch.
- **O1 · sai số nhóm cao.** `error_by_group[g] > o1.max_error_by_group[g]` → `Finding` cho nhóm đó. Nhóm không có ngưỡng trong YAML thì so với `o1.max_error_ratio × trung vị các nhóm`.
- **O2 · sai số tăng theo vị trí chunk.** Hệ số góc hồi quy tuyến tính của `error_by_chunk_pos` theo vị trí `> o2.max_slope`, hoặc `cuối / đầu > o2.max_ratio` → `Finding`.
- **O3 · lệch thời điểm bàn tay.** `abs(hand_event_offset_steps) > o3.max_offset_steps` → `Finding`.
- **O4 · ngoài giới hạn.** `out_of_limit_dims` không rỗng, hoặc tỉ lệ khung vượt giới hạn `> o4.max_fraction` → `Finding` với `dim`. Giới hạn lấy từ `action_layout.limit_low`, `limit_high`; **không** chép số vào mã (AC 2).

- [ ] **Bước 1: Viết test trước**, gồm:

```python
def test_t7_needs_parent_probe(probe_builder, cfg):
    r = detect_t7(probe_builder(p4_child={"p1_acc": 0.5}, p4_parent=None), cfg)
    assert codes(r) == [] and skipped_codes(r) == ["T7"]
    assert "cha" in r.skipped[0].reason   # lý do phải nói rõ là thiếu P4 của cha

def test_t7_flags_drop_against_parent(probe_builder, cfg):
    r = detect_t7(probe_builder(p4_child={"p1_acc": 0.5}, p4_parent={"p1_acc": 0.9}), cfg)
    assert codes(r) == ["T7"] and r.findings[0].value == pytest.approx(0.444, abs=1e-3)

def test_o4_uses_layout_limits_not_hardcoded(probe_builder, g1_layout, cfg):
    r = detect_o4(probe_builder(out_of_limit_dims=[3]), g1_layout, cfg)
    assert [x.dim for x in r.findings] == [3]

def test_o2_flags_growing_error_along_chunk(probe_builder, cfg):
    r = detect_o2(probe_builder(error_by_chunk_pos=[0.1, 0.2, 0.4, 0.8]), cfg)
    assert codes(r) == ["O2"]
```

- [ ] **Bước 2: Chạy để thấy đỏ.**
- [ ] **Bước 3: Viết hai module.**
- [ ] **Bước 4: Chạy để thấy xanh.**
- [ ] **Bước 5: Commit** — `DA-08/4: Detect forgetting and offline action faults (T7, O1-O4)`

### Nhiệm vụ 5: Cấu hình ngưỡng có hash

**File:**
- Tạo: `configs/eval/diagnosis/train.yaml`
- Sửa: `packages/flywheel-eval/src/flywheel/eval/config.py`
- Test: `tests/unit/diagnosis/train/test_config.py`

**Giao diện:** `load_train_thresholds(path) -> tuple[TrainThresholds, str]` trả cấu hình đã validate và `sha256` của byte file. `TrainThresholds` là dataclass trong làn, một trường cho mỗi ngưỡng, không có giá trị mặc định trong mã — thiếu khóa trong YAML là lỗi, không phải mặc định ngầm.

Nội dung YAML, mọi dòng ghi nguồn. Giá trị dưới đây là **giả định** cho tới khi có log thật của DA-19 (khoảng 6/11):

```yaml
# Ngưỡng chẩn đoán train. Mọi giá trị `# giả định` phải hiệu chỉnh lại trên log
# thật của DA-19 trước G2; cách hiệu chỉnh ghi ngay trên dòng.
t1:
  k: 10.0            # giả định; design mục 10 "tăng quá k lần"
  window_steps: 500  # giả định; đơn vị steps (issue #5, chốt 29/10)
t2:
  n_steps: 2000             # giả định
  min_relative_drop: 0.05   # giả định; "giảm dưới x%" của design mục 10
  baseline_val_count: 3     # chốt ở issue #5: trung vị 3 lần đo val đầu
t3:
  m_measurements: 3  # giả định; "tăng liên tiếp M lần đo"
t4:
  window_steps: 2000
  min_group_drop: 0.05   # giả định
  ref_group_drop: 0.30   # giả định
t5:
  window_steps: 1000
  epsilon: 1.0e-6        # giả định
t6:
  min_std_ratio: 0.30    # giả định
t7:
  max_relative_drop: 0.10  # giả định
t8:
  frozen_tolerance: 0.0    # chốt: VLM khai đóng băng thì gradient phải bằng 0
  max_grad_norm: 10.0      # giả định
  max_exceedances: 5       # giả định
o1:
  max_error_by_group: {}   # để rỗng tới khi có P3 thật; rơi về max_error_ratio
  max_error_ratio: 2.0     # giả định
o2:
  max_slope: 0.05          # giả định
  max_ratio: 3.0           # giả định
o3:
  max_offset_steps: 5      # giả định
o4:
  max_fraction: 0.0        # chốt: một khung ngoài giới hạn khớp là đã lỗi
```

- [ ] **Bước 1: Viết test trước** — `test_missing_key_is_an_error`, `test_hash_changes_with_content`, `test_hash_stable_across_reads`, và một test rà rằng mọi ngưỡng mà bộ phát hiện dùng đều có khóa trong YAML (duyệt `TrainThresholds.__dataclass_fields__`).
- [ ] **Bước 2: Chạy để thấy đỏ.**
- [ ] **Bước 3: Viết YAML và `config.py`.**
- [ ] **Bước 4: Chạy để thấy xanh.**
- [ ] **Bước 5: Commit** — `DA-08/5: Add hashed train diagnosis thresholds`

### Nhiệm vụ 6: Artifact kết quả và lệnh `fw`

**File:**
- Tạo: `diagnosis/train/artifact.py`
- Sửa: `packages/flywheel-eval/src/flywheel/eval/api.py`, `cli.py`
- Test: `tests/unit/diagnosis/train/test_artifact.py`, `tests/contract/diagnosis/train/test_diag_train_cli.py`

**Giao diện:**
- `diagnose_train(job_path, config_path) -> TrainDiagnosis` trong `api.py` là API công khai của làn; Hưng và Long gọi hàm này, không import module bên trong (07 mục 2.0 luật 3).
- `fw eval diag-train --job <đường dẫn> [--config <đường dẫn>] [--store <đường dẫn>]` in bảng phát hiện (`code`, `start_step`, `group`/`dim`, `value`, `threshold`, `stop_job`) và ghi artifact vào kho.
- Artifact `TrainDiagnosis` dùng **schema của `flywheel.contracts`** (DA-25): `checkpoint_id`, `config_sha256`, `findings[]`, cộng danh sách mã `skipped` kèm lý do. Nhiệm vụ này **chặn** nếu DA-25 chưa có bản ghi đó; khi đó dừng và ghi vào issue #5, không tự thêm vào contracts.
- `diagnose_train` gọi `diagnose_all`, nhận một `DetectorResult` rồi ghi **cả hai phần** vào artifact: `findings` của `DetectorResult` sang `findings[]`, `skipped` sang danh sách mã bỏ qua kèm lý do. Nếu schema của DA-25 không có chỗ cho `skipped` thì dừng nhiệm vụ này và ghi vào issue #5 — bỏ `skipped` khỏi artifact là vi phạm FR21, không phải cách đi tạm.

- [ ] **Bước 1: Viết test trước** — artifact ghi đúng `config_sha256`; hai lần chạy trên cùng job cho hai bản ghi (append-only, không ghi đè); mã `skipped` xuất hiện trong artifact chứ không bị bỏ im lặng; `fw eval diag-train --help` chạy; chạy lệnh trên một job cấy lỗi in đúng số dòng.
- [ ] **Bước 2: Chạy để thấy đỏ.**
- [ ] **Bước 3: Viết `artifact.py`, thêm hàm vào `api.py`, thêm lệnh vào `cli.py`.**
- [ ] **Bước 4: Chạy để thấy xanh**, cộng `uv run lint-imports`.
- [ ] **Bước 5: Commit** — `DA-08/6: Write the train diagnosis artifact and add fw eval diag-train`

### Nhiệm vụ 7: Bộ log cấy lỗi và test dương, âm đủ 12 mã

**File:**
- Tạo: `tests/unit/diagnosis/train/test_all_codes.py`
- Sửa: `tests/unit/diagnosis/train/conftest.py`

**Giao diện:** một bảng tham số hóa, mỗi dòng là một mã (T1–T8, O1–O4) với một hàm dựng log hay probe cấy đúng lỗi đó. Test chạy **toàn bộ** chuỗi phát hiện qua `diagnose_all`, không chỉ một hàm, để bắt trường hợp một bộ phát hiện ăn mất tín hiệu của bộ khác. `diagnose_all` trả một `DetectorResult` gộp của 12 mã.

```python
@pytest.mark.parametrize("code,build", INJECTED_CASES)
def test_each_code_is_detected(code, build, cfg, g1_layout):
    assert code in set(codes(diagnose_all(build(), cfg, g1_layout)))

def test_clean_job_has_no_findings(clean_metrics, clean_probes, cfg, g1_layout):
    r = diagnose_all((clean_metrics, clean_probes), cfg, g1_layout)
    assert codes(r) == []

def test_clean_job_with_full_signals_skips_nothing(clean_metrics, clean_probes, cfg, g1_layout):
    # đối chứng sạch phải có `vlm_frozen`, P4 của cha và `target_std > 0`,
    # nếu không thì `test_clean_job_has_no_findings` xanh vì bỏ qua, không vì sạch
    r = diagnose_all((clean_metrics, clean_probes), cfg, g1_layout)
    assert skipped_codes(r) == []
```

`INJECTED_CASES` phải đủ 12 dòng. Bảy dòng T1–T6, T8 lấy file mẫu của `flywheel.testkit` (`fixtures/training/t*.jsonl`); năm dòng còn lại (T7, O1–O4) chạy trên probe do `probe_builder` dựng, vì testkit chưa có file mẫu probe cấy lỗi. Nếu một file mẫu của testkit không bật đúng mã của nó thì **không** nới ngưỡng: báo cho Long dưới PR #22, vì hoặc ngưỡng của mình sai hoặc file mẫu không đủ tín hiệu, và cả hai đều cần sửa đúng chỗ.

AC 6 đạt khi test này xanh và `test_clean_job_has_no_findings` xanh.

- [ ] **Bước 1: Viết bảng `INJECTED_CASES` và hai test.**
- [ ] **Bước 2: Chạy để thấy đỏ ở các mã còn thiếu.**
- [ ] **Bước 3: Sửa bộ phát hiện cho tới khi đủ 12 mã**, không nới ngưỡng trong YAML để test xanh — nếu phải nới thì ghi lý do vào thân commit.
- [ ] **Bước 4: Chạy đủ bộ kiểm** — `uv run ruff check`, `uv run mypy`, `uv run pytest`, `uv run lint-imports`.
- [ ] **Bước 5: Commit** — `DA-08/7: Add injected-fault cases and clean controls for all 12 codes`

---

## DA-13 · Kiểm hệ thống F-SYS và quy lỗi về stage

### Nhiệm vụ 1: Lớp đọc `Trace`, log RTC, kết quả probe

**File:**
- Tạo: `diagnosis/system/__init__.py`, `reader.py`
- Test: `tests/unit/diagnosis/system/conftest.py`, `test_reader.py`

**Giao diện:** `read_system_view(trace, rtc_log, camera_params) -> SystemView` với `cmd_upper`, `meas_upper`, `cmd_lower`, `meas_lower` (mảng theo chu kỳ), `t_image`, `t_state`, `latency_ms`, `buffer_underruns`, `infra_status`, `camera`, cộng `missing: list[str]` liệt kê trường thiếu và `n_samples`. Trường "lệnh gửi" và "trạng thái đo" của WBC chốt ở G0 theo agent `psi0_decoupled_wbc`; tới đó lớp đọc lấy tên trường từ `Trace` mẫu và khai chúng ở một chỗ duy nhất trong `reader.py`.

- [ ] **Bước 1: Viết test trước** — trace đủ trường cho `missing == []`; trace thiếu `t_state` cho `missing == ["t_state"]`; `percentile_with_count` báo đúng số mẫu trên trace 40 mẫu.
- [ ] **Bước 2: Chạy để thấy đỏ.**
- [ ] **Bước 3: Viết `reader.py`.**
- [ ] **Bước 4: Chạy để thấy xanh.**
- [ ] **Bước 5: Commit** — `DA-13/1: Add the trace, RTC log and probe reader for system checks`

### Nhiệm vụ 2: Thiếu tín hiệu và R3 bám lệnh

**File:**
- Tạo: `diagnosis/system/signals.py`, `tracking.py`
- Test: `tests/unit/diagnosis/system/test_signals.py`, `test_tracking.py`

Công thức:

- **Thiếu tín hiệu.** `missing` không rỗng, hoặc số khung camera hụt vượt `missing.max_dropped_frames` → kết luận `UNCLEAR` kèm đề xuất thu thêm bằng chứng; **dừng chuỗi**, không chấm các bước sau, không can thiệp dữ liệu (spec mục 6.4 bước 1).
- **R3 bám lệnh.** Tính riêng hai phần: `norm(cmd_upper − meas_upper)` phân vị 99 so với `tau_track_upper`, và `norm(cmd_lower − meas_lower)` phân vị 99 so với `tau_track_lower`. Vượt → `LỖI CONTROLLER`, ghi phần nào (`upper` hay `lower`) và giá trị.

- [ ] **Bước 1: Viết test trước**, gồm test âm cho episode sạch và:

```python
def test_missing_signal_short_circuits(trace_builder, cfg):
    r = check_system(read_system_view(trace_builder(drop_field="t_state")), cfg)
    assert r.verdict == "UNCLEAR"
    assert [e.name for e in r.evaluated] == ["r6_infra", "missing_signal"]

def test_r3_separates_upper_and_lower(trace_builder, cfg):
    r = check_system(read_system_view(trace_builder(upper_track_error=0.5)), cfg)
    assert r.verdict == "CONTROLLER" and r.part == "upper"
```

- [ ] **Bước 2: Chạy để thấy đỏ.**
- [ ] **Bước 3: Viết hai module.**
- [ ] **Bước 4: Chạy để thấy xanh.**
- [ ] **Bước 5: Commit** — `DA-13/2: Check missing signals and WBC command tracking (R3)`

### Nhiệm vụ 3: R1, R2 độ trễ; R4 đồng bộ; R5 camera; R6 hạ tầng

**File:**
- Tạo: `diagnosis/system/latency.py`, `sync.py`, `calibration.py`, `infra.py`, `chain.py`
- Test: `tests/unit/diagnosis/system/test_latency.py`, `test_sync.py`, `test_calibration.py`, `test_chain.py`

Công thức, theo đúng thứ tự spec mục 6.4:

| Thứ tự | Bước | Kiểm | Điều kiện | Kết luận |
|---|---|---|---|---|
| 0 | `r6_infra` | R6 hạ tầng | `infra_status != "ok"` | `INFRA` |
| 1 | `missing_signal` | Thiếu tín hiệu | nhiệm vụ 2 | `UNCLEAR` |
| 2 | `r3_tracking` | R3 bám lệnh | nhiệm vụ 2 | `CONTROLLER` |
| 3 | `r1_latency` | R1 độ trễ | `p99(latency_ms) > tau_lat` | `RUNTIME` |
| 3 | `r2_buffer` | R2 buffer cạn | `buffer_underruns > r2.max_underruns` | `RUNTIME` |
| 4 | `r4_sync` | R4 đồng bộ | `max(abs(t_image − t_state)) > tau_sync` | `SYNC` |
| 5 | `r5_camera` | R5 camera | tham số camera khác bản tham chiếu đã hash | `CALIBRATION` |

`chain.py` chạy chuỗi theo thứ tự trên và **dừng ở kết luận đầu tiên**, nhưng vẫn ghi lại mọi bước đã chấm cùng giá trị và ngưỡng vào `evaluated`, cộng các bước `skipped` kèm lý do (FR21: không bỏ im lặng). Thứ tự của năm bước 1–5 là thứ tự spec mục 6.4, không được đổi.

**R6 là bước 0 của chính chuỗi**, không phải một phép kiểm nằm ngoài. Nó luôn có trong `evaluated`; `infra_status != "ok"` thì `verdict = "INFRA"` và chuỗi dừng ngay, nên `evaluated == ["r6_infra"]`. Lý do R6 đi trước mọi bước khác: một episode mà simulator chết giữa đường có cả trace thiếu trường và sai số bám lệnh cao, nên nếu chấm sau thì nó ra `UNCLEAR` hay `CONTROLLER` — hai kết luận đều sai về một lượt chạy chưa bao giờ hoàn thành.

`INFRA` **không phải lỗi policy**: nó không vào `Cluster` để tính tỉ lệ thành công và không sang `diagnosis/stage/` (`attribute_stage` chỉ chạy khi `verdict == "OK"`). Nó cũng khác `UNCLEAR`: `UNCLEAR` là "chạy xong nhưng không đủ tín hiệu để chẩn đoán", `INFRA` là "lượt chạy không có giá trị, chạy lại". Phân biệt này là dữ liệu mà `decide` của Long cần, nên nó là một `verdict` chứ không phải một cờ phụ.

- [ ] **Bước 1: Viết test trước**, bắt buộc có test thứ tự:

```python
def test_order_puts_tracking_before_latency(trace_builder, cfg):
    # episode hỏng cả hai chỗ; kết luận phải là lớp của bước sớm hơn
    view = read_system_view(trace_builder(upper_track_error=0.5, latency_p99=200))
    r = check_system(view, cfg)
    assert r.verdict == "CONTROLLER"
    assert [e.name for e in r.evaluated] == ["r6_infra", "missing_signal", "r3_tracking"]

def test_infra_error_stops_the_chain_first(trace_builder, cfg):
    # hỏng cả ở R6 và R3; R6 là bước 0 nên chuỗi dừng ngay ở đó
    view = read_system_view(trace_builder(infra_status="simulator_error", upper_track_error=0.5))
    r = check_system(view, cfg)
    assert r.verdict == "INFRA" and r.infra_status == "simulator_error"
    assert [e.name for e in r.evaluated] == ["r6_infra"]

def test_clean_episode_has_no_system_fault(clean_trace, cfg):
    r = check_system(read_system_view(clean_trace), cfg)
    assert r.verdict == "OK"
    assert [e.name for e in r.evaluated][0] == "r6_infra"   # R6 luôn được chấm
```

- [ ] **Bước 2: Chạy để thấy đỏ.**
- [ ] **Bước 3: Viết năm module.**
- [ ] **Bước 4: Chạy để thấy xanh.**
- [ ] **Bước 5: Commit** — `DA-13/3: Check latency, buffers, sensor sync, camera calibration and infra (R1, R2, R4-R6)`

### Nhiệm vụ 4: Cấu hình ngưỡng có hash

**File:**
- Tạo: `configs/eval/diagnosis/system.yaml`
- Sửa: `packages/flywheel-eval/src/flywheel/eval/config.py`
- Test: `tests/unit/diagnosis/system/test_config.py`

τ lấy **phân vị 99** trên episode teleop thành công (τ_track, τ_sync) hoặc lần chạy chuẩn G0 (τ_lat); YAML ghi cách tính và số mẫu đã dùng, không chỉ con số.

```yaml
# τ hiệu chỉnh theo spec mục 6.4. Mỗi giá trị ghi cách tính và số mẫu;
# giá trị `# giả định` phải thay bằng số đo trước G4.
missing:
  max_dropped_frames: 0    # chốt: mất khung là CHƯA RÕ, không chấm tiếp
r3:
  tau_track_upper: null    # giả định chưa có số; p99 norm(cmd-meas) thân trên
                           # trên episode teleop thành công của psi-data
  tau_track_lower: null    # như trên, thân dưới (vận tốc gốc, chiều cao, hướng)
r1:
  tau_lat_ms: null         # p99 độ trễ chu kỳ suy luận, lần chạy chuẩn G0
r2:
  max_underruns: 0         # giả định
r4:
  tau_sync_ms: null        # p99 lệch t_image và t_state, demo teleop thành công
r5:
  reference_sha256: null   # hash bản tham chiếu camera đóng băng ở G0
  max_intrinsics_rel_diff: 0.01   # giả định
  max_pose_diff_m: 0.005          # giả định
  max_pose_diff_deg: 0.5          # giả định
calibration_min_samples: 100  # dưới mức này thì p99 không đáng tin, ghi cảnh báo
```

`null` nghĩa là **chưa hiệu chỉnh**: bộ kiểm tương ứng ghi `skipped` kèm lý do "τ chưa có", không mặc định cho qua. Đây là điểm dễ sai nhất của story: một τ thiếu mà im lặng sẽ biến mọi episode thành "không phải lỗi hệ thống".

- [ ] **Bước 1: Viết test trước** — `test_null_tau_skips_not_passes`, `test_hash_changes_with_content`, test rà mọi ngưỡng có khóa, và test cảnh báo khi `n_samples < calibration_min_samples`.
- [ ] **Bước 2: Chạy để thấy đỏ.**
- [ ] **Bước 3: Viết YAML và phần `config.py`.**
- [ ] **Bước 4: Chạy để thấy xanh.**
- [ ] **Bước 5: Commit** — `DA-13/4: Add hashed system check thresholds`

### Nhiệm vụ 5: Bảng quy lỗi về stage và bằng chứng gắn kèm

**File:**
- Tạo: `diagnosis/stage/__init__.py`, `table.py`, `attribute.py`, `configs/eval/diagnosis/stage.yaml`
- Sửa: `packages/flywheel-eval/src/flywheel/eval/api.py`, `cli.py`
- Test: `tests/unit/diagnosis/stage/test_table.py`, `test_attribute.py`

**Giao diện:** `attribute_stage(cluster, probes, system_result, train_findings, cfg) -> StageHypothesis` với `stage`, `suggested_intervention`, `spends_budget: bool`, `confidence_note`, và `evidence: list[Evidence]` trong đó mỗi `Evidence` ghi `probe` (P1, P3, P4 hay T7), `scope` (khung hình hay episode nào), `value`, `threshold`. Chỉ chạy khi `system_result.verdict == "OK"` và kiểm dữ liệu đã qua; nếu không thì trả `stage=None` kèm lý do — `verdict` là `INFRA`, `UNCLEAR` hay một lớp lỗi hệ thống thì đều không quy về stage.

Bảng nằm trong YAML, mỗi dòng một điều kiện:

```yaml
# Bảng quy lỗi về stage, bản đã chốt 30/10/2026: spec v10.5 mục 6.4
# (bằng bảng design mục 10, trừ can thiệp dòng Stage 1 theo mục 6.7 và 7.3).
# Một bảng duy nhất, không có biến thể. Đổi bảng phải sửa spec trước.
source: spec-v10.5-6.4
rows:
  - id: p1_wrong
    when: {p1_correct_on_failure_frame: false}
    stage: "1 · nhận thức"
    budget: false
    intervention: "Ghi nhận và báo cáo; tăng cường thị giác đã cố định cho mọi nhánh (spec mục 7.3)"
  - id: p3_group_high
    when: {p1_correct_on_failure_frame: true, p3_group_error_high: true}
    stage: "3 · học action nhóm đó"
    budget: true
    intervention: "Thêm demo hoặc dữ liệu sinh (S1, S2) cho bước k"
  - id: distribution_shift
    when: {p1_correct_on_failure_frame: true, p3_group_error_high: false, closed_loop_failed: true}
    stage: "Lệch phân phối khi chạy"
    budget: true
    intervention: "Correction từ trạng thái lỗi (spec bước 6, 8)"
  - id: forgetting
    when: {new_failure_after_finetune: true, t7_present: true}
    stage: "3 · quên"
    budget: true
    intervention: "Giảm learning rate, tăng replay"
  - id: out_of_domain
    when: {out_of_train_domain: true}
    stage: null
    budget: false
    intervention: "Chỉ báo cáo (NGOÀI MIỀN, spec mục 6.8)"
```

`budget: false` nghĩa là dòng đó **không tiêu ngân sách thu dữ liệu**: `p1_wrong` chỉ ghi nhận và báo cáo vì tăng cường thị giác đã cố định cho mọi nhánh (spec mục 7.3) và synthetic S3 là hướng sau PoC (spec mục 1.1); `out_of_domain` không phải lỗi stage. Hai dòng này vẫn lên evidence card, nhưng `decide` của Long đọc `budget` để không đề xuất can thiệp tốn tiền từ chúng.

Bảng chỉ có một bản. Đổi bảng là sửa spec mục 6.4 trước (cần quyết định của PO và một dòng change log), rồi sửa YAML cho khớp; không thêm biến thể vào YAML và không sửa mã.

- [ ] **Bước 1: Viết test trước**:

```python
def test_no_hypothesis_when_system_fault_present(cfg):
    h = attribute_stage(cluster, probes, system_result=controller_fault, train_findings=[], cfg=cfg)
    assert h.stage is None and "lỗi hệ thống" in h.confidence_note

def test_every_hypothesis_carries_evidence(cfg):
    h = attribute_stage(cluster, probes_p1_wrong, system_ok, [], cfg)
    assert h.evidence and all(e.probe and e.scope and e.value is not None for e in h.evidence)

def test_stage1_is_report_only_and_spends_no_budget(cfg):
    # chốt 30/10: dòng p1_wrong chỉ ghi nhận, không đề xuất can thiệp tốn tiền
    h = attribute_stage(cluster, probes_p1_wrong, system_ok, [], cfg)
    assert h.stage == "1 · nhận thức" and h.spends_budget is False

def test_table_has_exactly_the_five_rows_of_spec_6_4(cfg):
    # khóa bảng lại: thêm hay bớt dòng phải đi qua một PR sửa spec mục 6.4
    assert [r.id for r in load_stage_table(cfg).rows] == [
        "p1_wrong", "p3_group_high", "distribution_shift", "forgetting", "out_of_domain",
    ]

def test_out_of_domain_is_not_a_stage_fault(cfg):
    h = attribute_stage(cluster, probes_ood, system_ok, [], cfg)
    assert h.stage is None and h.spends_budget is False
```

- [ ] **Bước 2: Chạy để thấy đỏ.**
- [ ] **Bước 3: Viết `table.py`, `attribute.py`, YAML; thêm `fw eval diag-system` và `fw eval diag-stage` vào `cli.py`, hàm tương ứng vào `api.py`.**
- [ ] **Bước 4: Chạy để thấy xanh**, cộng `uv run lint-imports`.
- [ ] **Bước 5: Commit** — `DA-13/5: Add the stage attribution table with attached evidence`

### Nhiệm vụ 6: Test trên bộ lỗi cấy hệ thống và đối chứng sạch

**File:**
- Tạo: `tests/unit/diagnosis/system/test_injected_faults.py`
- Sửa: `tests/unit/diagnosis/system/conftest.py`

Theo AC 5 và spec mục 7.6, ba ca bắt buộc: **trễ camera → `SYNC`**, **lệch calibration → `CALIBRATION`**, **episode sạch → không báo lỗi hệ thống**. Thêm một ca cho mỗi mã R1, R2, R3, R6 để đủ bộ, và một ca hỏng hai chỗ để khóa thứ tự.

Bộ lỗi cấy thật là DA-27 của Thông (`DefectManifest`); tới đó dùng trace cấy do `conftest.py` tự dựng, và **mọi test của nhiệm vụ này nằm trong `tests/unit/diagnosis/system/`**.

Việc chạy DA-13 trên bản sao cấy lỗi thật của DA-27 **không thuộc story này**: `tests/contract/diagnosis/system/` không có trong "Phạm vi file" của DA-13 (chỉ có `tests/unit/diagnosis/system/` và `tests/unit/diagnosis/stage/`), nên pr-guard sẽ chặn. Việc đó thuộc **DA-31** (Agent QA/QC và bộ chấm lỗi cấy của Hưng), là story đã có nhiệm vụ chấm `DefectManifest`. Nghiệm thu theo spec mục 7.6 vì vậy đạt qua DA-31, không qua DA-13; DA-13 chỉ cung cấp `api.py` để bộ chấm gọi. Nếu sau này đội muốn test đó nằm trong DA-13 thì phải thêm `packages/flywheel-eval/tests/contract/diagnosis/system/` vào "Phạm vi file" của story qua một PR sửa story (chủ `docs/product/stories/` là Thông), trước khi viết test.

Trong cả hai cách, đáp án `DefectManifest` **chỉ bộ chấm đọc**; test của DA-13 không được đọc đáp án để tự chấm.

- [ ] **Bước 1: Viết bảng ca cấy và test tham số hóa.**
- [ ] **Bước 2: Chạy để thấy đỏ.**
- [ ] **Bước 3: Sửa tới khi đủ**, không nới τ để test xanh.
- [ ] **Bước 4: Chạy đủ bộ kiểm** — `uv run ruff check`, `uv run mypy`, `uv run pytest`, `uv run lint-imports`.
- [ ] **Bước 5: Commit** — `DA-13/6: Add injected system faults and a clean control episode`

---

## Sau DA-08 và DA-13

- Khi DA-19 có log thật (khoảng 6/11): chạy `fw eval diag-train` trên một job fine-tune, hiệu chỉnh mọi ngưỡng `# giả định` trong `train.yaml`, ghi số phát hiện vào mục "Ghi chép khi làm" của DA-08.
- Khi có `Trace` thật của SIMPLE: hiệu chỉnh τ_track, τ_lat, τ_sync từ phân vị 99 trên episode teleop thành công, thay `null` trong `system.yaml`, ghi số mẫu đã dùng.
- Evidence card (story Epic `cards`) đọc `StageHypothesis` và `TrainDiagnosis`; chưa có story file, cần viết trước khi làm.
- `decide` của Long và Agent QA/QC của Hưng đọc kết quả qua `api.py`, không import module bên trong.
