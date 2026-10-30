# DA-08 và DA-13 · Plan triển khai chuỗi chẩn đoán của làn Đánh giá

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Mục tiêu:** Hai bộ phát hiện lỗi của làn Đánh giá chạy được trên CPU: DA-08 đọc `metrics.jsonl` và kết quả probe để bắt T1–T8 (F-TRAIN) và O1–O4 (F-OFF); DA-13 đọc `Trace` và log RTC để kiểm hệ thống R1–R6 (F-SYS) rồi gắn giả thuyết stage kèm bằng chứng probe. Mỗi mã lỗi có một test dương và một test âm.

**Kiến trúc:** Mọi thứ nằm trong `packages/flywheel-eval`, chỉ import nhân (`flywheel.contracts`, `flywheel.store`, `flywheel.testkit`) cộng `numpy`. Không `torch`, không adapter, không chạy model — toàn bộ tính trên số đã ghi trong log và kết quả probe. Trong mỗi nhánh `diagnosis/` có hai lớp tách rời: một **lớp đọc** (`reader.py`) chuyển bản ghi hợp đồng thành chuỗi thời gian thuần numpy, và các **bộ phát hiện** chỉ làm việc trên chuỗi đó. Khi schema hợp đồng chốt khác đề xuất ở issue #5 thì chỉ sửa lớp đọc, bộ phát hiện không đổi. Ngưỡng không nằm trong mã: mọi con số đọc từ YAML trong `configs/eval/diagnosis/`, và artifact kết quả ghi lại `sha256` của file cấu hình đã dùng.

**Công nghệ:** Python của workspace, `numpy`, `typer` (lệnh `fw`), `pytest`. Không phụ thuộc GPU, SIMPLE hay Ψ₀.

**Nguồn:** [design 27/10/2026](../specs/2026-10-27-g1-psi0-demo-design.md) mục 8.2 (trường log), 8.3 (probe P1–P4), 10 (bảng lỗi); [spec v10.4](../../spec-v10-failure-to-data.md) mục 6.4 (thứ tự kiểm hệ thống, bước 4b), 7.6 (nghiệm thu trên lỗi cấy); story [DA-08](../../product/stories/DA-08-phat-hien-loi-train-va-offline.md), [DA-13](../../product/stories/DA-13-quy-loi-ve-stage.md); hợp đồng còn thiếu ở issue #5.

## Điều kiện tiên quyết

Hai thứ phải vào `master` trước khi nhiệm vụ con nào của plan này chạy được. Tình trạng 30/10/2026:

| Điều kiện | Trạng thái 30/10 | Chặn gì |
|---|---|---|
| PR #17 `chore-restructure` | Mở, CI xanh trên `63b8e23`, chờ Hiếu merge | `packages/flywheel-eval/` và `configs/eval/` chưa tồn tại trên `master`, tức toàn bộ "Phạm vi file" của hai story |
| DA-25 (Long): schema `metrics.jsonl`, `TrainDiagnosis`, trường của P3 và P4, file mẫu trong `flywheel.testkit` | Chưa bắt đầu; bốn câu hỏi hợp đồng còn mở ở issue #5 | Nhiệm vụ 1 và 6 của DA-08; nhiệm vụ 1 và 5 của DA-13 |

CLAUDE.md không cho tạo nhánh từ nhánh chưa merge, nên **không** rẽ nhánh từ `chore-restructure` để chạy sớm. Trong lúc chờ, phần làm được là plan này và nội dung YAML ngưỡng ở nhiệm vụ 5 (DA-08) và 4 (DA-13).

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

1. **Job resume làm bản ghi trùng.** `metrics.jsonl` của job chạy tiếp trên Colab có thể có hai bản ghi cùng `(job_id, split, step)`. Nếu không xử lý, T1 thấy loss "tăng k lần" chỉ vì hai lần đo cạnh nhau thuộc hai lần chạy. Lớp đọc phải quyết một lần cho cả hai story (issue #5 mục 2c) và có test riêng.
2. **Tần số ghi log đổi giữa các job.** Mọi cửa sổ đếm theo `step`, không theo số dòng. Một test cho hai file cùng nội dung nhưng tần số ghi khác nhau phải ra cùng kết luận.
3. **T3 báo nhầm trên job bình thường.** Loss train theo batch nhiễu hơn loss val; không làm mượt thì T3 bật trên job đang học tốt. Test âm phải có một job sạch với loss train răng cưa.
4. **Chiều bị mask.** G1 có 5 chiều đệm (S1-07). T5 và T6 chạy trên chiều mask sẽ báo lỗi hàng loạt trên mọi checkpoint. Test phải có một file mẫu mà đúng chiều đệm có phương sai 0 và không được đánh dấu.
5. **Thứ tự kiểm hệ thống không được đổi.** Spec mục 6.4 là thứ tự có nghĩa: một episode trễ camera cũng có sai số bám lệnh cao, nên nếu kiểm R1 trước R3 thì ra sai lớp. Test phải có một episode hỏng ở hai chỗ và kiểm rằng kết luận là lớp của bước sớm hơn.
6. **Thiếu tín hiệu phải ra CHƯA RÕ, không ra "sạch".** Trace thiếu trường hoặc camera mất khung mà vẫn chấm tiếp là lỗi nguy hiểm nhất của DA-13, vì nó biến một episode không chẩn đoán được thành một episode "không phải lỗi hệ thống" rồi quy sang stage.
7. **Góc và phân vị.** τ lấy phân vị 99; với episode ngắn (dưới 100 mẫu) phân vị 99 gần như là giá trị lớn nhất. Lớp đọc phải báo số mẫu cùng giá trị τ để người đọc biết độ tin.

## Quyết định chưa chốt, ảnh hưởng plan

| Chỗ | Trạng thái | Cách plan xử lý |
|---|---|---|
| `vlm_frozen` ở bản ghi log hay ở `TrainSpec`/RunPlan (issue #5 mục 2a) | Mở | Lớp đọc nhận cả hai nguồn qua một hàm; T8 chỉ chạy khi có giá trị, không có thì ghi "bỏ qua" chứ không im lặng |
| `parent_checkpoint_id` ở P4 hay ở `metrics.jsonl` (mục 2b) | Mở | T7 đọc từ kết quả P4 trước, không có thì đọc từ định danh log |
| `attempt` của job resume (mục 2c) | Mở | Lớp đọc dedupe theo `(job_id, split, step)` giữ bản ghi cuối; nếu hợp đồng chốt có `attempt` thì đổi thành nhóm theo `attempt` và bỏ dedupe |
| `action_layout` vào story nào (mục 2d) | Mở | T5, T6, O1, O4 lấy nhóm, mask và giới hạn từ `action_layout` của embodiment qua contracts; không có thì dừng nhiệm vụ 4 và báo, không chép số vào mã |
| Bảng quy lỗi stage: spec mục 6.4 khác design mục 10 | Mở, Hiếu chốt | Cả hai bản nằm trong `stage.yaml`, mỗi dòng có `source: spec-v10.4` hay `source: design-2026-10-27`; khóa `table_variant` chọn bản dùng, mặc định `design-2026-10-27` vì design là bản hiện hành duy nhất. Đổi bản không cần sửa mã |

---

## DA-08 · Lỗi train F-TRAIN và lỗi offline F-OFF

### Nhiệm vụ 1: Lớp đọc `metrics.jsonl` và kết quả probe

**File:**
- Tạo: `packages/flywheel-eval/src/flywheel/eval/diagnosis/train/__init__.py`, `reader.py`, `series.py`
- Test: `packages/flywheel-eval/tests/unit/diagnosis/train/conftest.py`, `test_reader.py`

**Giao diện:**
- Nhận: bản ghi `metrics.jsonl` và kết quả probe P3, P4 theo schema của `flywheel.contracts` (DA-25); `action_layout` của embodiment.
- Cho ra: `TrainSeries` với `step: np.ndarray`, `loss_train`, `loss_val` (cặp `(step, value)` riêng cho từng split), `loss_by_group: dict[str, np.ndarray]`, `pred_var_by_dim: np.ndarray` dạng `(n_records, n_dims)`, `pred_std`, `target_std`, `grad_norm_vlm`, `grad_norm_action`, `vlm_frozen: bool | None`, `parent_checkpoint_id: str | None`, `n_dropped_duplicates: int`; cộng `ProbeView` cho P3 và P4.

`series.py` chỉ chứa hàm thuần trên numpy mà bộ phát hiện dùng chung: `window_mask(step, start, width)`, `median_in_window`, `at_val_points`, `relative_drop`, `linear_slope`, `percentile_with_count`. Giữ chúng tách khỏi `reader.py` để bộ phát hiện không phụ thuộc hình dạng hợp đồng.

- [ ] **Bước 1: Viết test trước**

```python
def test_reader_counts_steps_not_records(tmp_path, metrics_builder):
    dense = metrics_builder(steps=range(0, 1000, 10), loss=lambda s: 1.0)
    sparse = metrics_builder(steps=range(0, 1000, 50), loss=lambda s: 1.0)
    assert read_series(dense).step[-1] == read_series(sparse).step[-1] == 990

def test_reader_dedupes_resumed_job(tmp_path, metrics_builder):
    path = metrics_builder(steps=[0, 10, 20, 10, 20, 30], loss=[1.0, 0.9, 0.8, 0.95, 0.85, 0.7])
    series = read_series(path)
    assert series.n_dropped_duplicates == 2
    assert list(series.step) == [0, 10, 20, 30]
    assert series.loss_train[1] == pytest.approx(0.95)  # bản ghi cuối thắng

def test_reader_keeps_val_and_train_separate(metrics_builder):
    series = read_series(metrics_builder(val_every=100))
    assert series.loss_val.size * 10 == series.loss_train.size

def test_reader_reports_missing_vlm_frozen(metrics_builder):
    assert read_series(metrics_builder(vlm_frozen=None)).vlm_frozen is None
```

`metrics_builder` là fixture trong `conftest.py`: nhận các tham số trên, ghi một `metrics.jsonl` hợp lệ vào `tmp_path` và trả đường dẫn. Nó là **nguồn duy nhất** sinh file mẫu trong test của DA-08; khi DA-25 có file mẫu trong `flywheel.testkit` thì fixture gọi sang testkit cho ca "sạch" và vẫn tự sinh cho các ca cấy lỗi.

- [ ] **Bước 2: Chạy để thấy đỏ** — `uv run pytest packages/flywheel-eval/tests/unit/diagnosis/train -v`, kỳ vọng `ImportError`.
- [ ] **Bước 3: Viết `reader.py` và `series.py`.**
- [ ] **Bước 4: Chạy để thấy xanh**, cộng `uv run lint-imports` và `uv run mypy`.
- [ ] **Bước 5: Commit** — `DA-08/1: Add the metrics.jsonl and probe reader for train diagnosis`

### Nhiệm vụ 2: T1, T2, T3

**File:**
- Tạo: `diagnosis/train/divergence.py` (T1), `learning.py` (T2, T3)
- Test: `tests/unit/diagnosis/train/test_divergence.py`, `test_learning.py`

**Giao diện:** mỗi bộ phát hiện là một hàm `detect_t1(series: TrainSeries, cfg: TrainThresholds) -> list[Finding]`. `Finding` gồm `code`, `start_step`, `group | None`, `dim | None`, `value`, `threshold`, `stop_job: bool`. Định nghĩa `Finding` ở `diagnosis/train/finding.py` dưới dạng dataclass nội bộ của làn; nó **không** phải bản ghi hợp đồng, việc chuyển sang artifact là nhiệm vụ 6.

Công thức, theo design mục 10 và ba câu đã chốt ở issue #5:

- **T1 · phân kỳ.** Hai nhánh. (a) Bản ghi có `loss` là NaN hoặc Inf → `Finding` tại `step` đó, `stop_job=True`, không cần cửa sổ. (b) `loss > k × min(loss trong cửa sổ W step tính lùi từ step hiện tại)` → `Finding`, `stop_job=True`. W đếm theo `step`.
- **T2 · không học.** Gọi `baseline` là trung vị `t2.baseline_val_count` lần đo val đầu. Tại lần đo val đầu tiên có `step >= t2.n_steps`: nếu `(baseline − loss_val) / baseline < t2.min_relative_drop` → `Finding` tại step đó. Không có lần đo val nào sau `n_steps` thì không kết luận.
- **T3 · quá khớp.** Tại mỗi lần đo val ở step `s`, `train_med(s)` là trung vị các bản ghi `split=train` trong khoảng `(step đo val trước, s]`. Điều kiện: dãy `train_med` giảm đơn điệu trên `M+1` điểm đo liên tiếp **và** `loss_val` tăng ở cả `M` bước đo cuối trong đó → `Finding` tại điểm đo đầu của đoạn tăng.

- [ ] **Bước 1: Viết test trước** — mỗi mã một test dương và một test âm.

```python
def test_t1_flags_nan_and_stops_job(metrics_builder, cfg):
    f = detect_t1(read_series(metrics_builder(loss_at={500: float("nan")})), cfg)
    assert [x.code for x in f] == ["T1"] and f[0].start_step == 500 and f[0].stop_job

def test_t1_flags_spike_over_k_times_window_min(metrics_builder, cfg):
    # cfg.t1.k = 10, window_steps = 500
    f = detect_t1(read_series(metrics_builder(loss=lambda s: 0.5, loss_at={600: 8.0})), cfg)
    assert f and f[0].start_step == 600

def test_t1_silent_on_clean_run(clean_metrics, cfg):
    assert detect_t1(read_series(clean_metrics), cfg) == []

def test_t2_flags_flat_val_loss(metrics_builder, cfg):
    f = detect_t2(read_series(metrics_builder(val_loss=lambda s: 1.0)), cfg)
    assert [x.code for x in f] == ["T2"]

def test_t2_ignores_one_bad_first_measurement(metrics_builder, cfg):
    # lần đo val đầu nhiễu cao; trung vị 3 điểm đầu phải hấp thụ được
    series = read_series(metrics_builder(val_loss_points={0: 9.9, 100: 1.0, 200: 0.98, 1000: 0.55}))
    assert detect_t2(series, cfg) == []

def test_t3_flags_rising_val_with_falling_train(metrics_builder, cfg):
    f = detect_t3(read_series(metrics_builder(train_loss=decreasing, val_loss=rising_after(600))), cfg)
    assert [x.code for x in f] == ["T3"] and f[0].start_step == 600

def test_t3_silent_on_noisy_but_healthy_train_loss(metrics_builder, cfg):
    series = read_series(metrics_builder(train_loss=decreasing_with_jitter(0.3), val_loss=decreasing))
    assert detect_t3(series, cfg) == []
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
    assert detect_t5(series, g1_layout, cfg) == []

def test_t5_flags_unmasked_dead_dim(metrics_builder, g1_layout, cfg):
    f = detect_t5(read_series(metrics_builder(zero_var_dims=[14])), g1_layout, cfg)
    assert [x.dim for x in f] == [14]

def test_t4_names_the_slow_group(metrics_builder, g1_layout, cfg):
    series = read_series(metrics_builder(group_drop={"hand": 0.01, "arm": 0.6, "leg": 0.5}))
    f = detect_t4(series, g1_layout, cfg)
    assert [x.group for x in f] == ["hand"]

def test_t8_flags_nonzero_grad_on_frozen_vlm(metrics_builder, cfg):
    f = detect_t8(read_series(metrics_builder(vlm_frozen=True, grad_norm_vlm=0.4)), cfg)
    assert [x.code for x in f] == ["T8"]

def test_t8_skips_when_frozen_flag_absent(metrics_builder, cfg):
    f = detect_t8(read_series(metrics_builder(vlm_frozen=None, grad_norm_vlm=0.4)), cfg)
    assert [x.code for x in f] == [] and skipped_codes(f) == ["T8a"]
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
    f = detect_t7(probe_builder(p4_child={"p1_acc": 0.5}, p4_parent=None), cfg)
    assert f == [] and skipped_codes(f) == ["T7"]

def test_t7_flags_drop_against_parent(probe_builder, cfg):
    f = detect_t7(probe_builder(p4_child={"p1_acc": 0.5}, p4_parent={"p1_acc": 0.9}), cfg)
    assert [x.code for x in f] == ["T7"] and f[0].value == pytest.approx(0.444, abs=1e-3)

def test_o4_uses_layout_limits_not_hardcoded(probe_builder, g1_layout, cfg):
    f = detect_o4(probe_builder(out_of_limit_dims=[3]), g1_layout, cfg)
    assert [x.dim for x in f] == [3]

def test_o2_flags_growing_error_along_chunk(probe_builder, cfg):
    f = detect_o2(probe_builder(error_by_chunk_pos=[0.1, 0.2, 0.4, 0.8]), cfg)
    assert [x.code for x in f] == ["O2"]
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

- [ ] **Bước 1: Viết test trước** — artifact ghi đúng `config_sha256`; hai lần chạy trên cùng job cho hai bản ghi (append-only, không ghi đè); mã `skipped` xuất hiện trong artifact chứ không bị bỏ im lặng; `fw eval diag-train --help` chạy; chạy lệnh trên một job cấy lỗi in đúng số dòng.
- [ ] **Bước 2: Chạy để thấy đỏ.**
- [ ] **Bước 3: Viết `artifact.py`, thêm hàm vào `api.py`, thêm lệnh vào `cli.py`.**
- [ ] **Bước 4: Chạy để thấy xanh**, cộng `uv run lint-imports`.
- [ ] **Bước 5: Commit** — `DA-08/6: Write the train diagnosis artifact and add fw eval diag-train`

### Nhiệm vụ 7: Bộ log cấy lỗi và test dương, âm đủ 12 mã

**File:**
- Tạo: `tests/unit/diagnosis/train/test_all_codes.py`
- Sửa: `tests/unit/diagnosis/train/conftest.py`

**Giao diện:** một bảng tham số hóa, mỗi dòng là một mã (T1–T8, O1–O4) với một hàm dựng log hay probe cấy đúng lỗi đó. Test chạy **toàn bộ** chuỗi phát hiện, không chỉ một hàm, để bắt trường hợp một bộ phát hiện ăn mất tín hiệu của bộ khác.

```python
@pytest.mark.parametrize("code,build", INJECTED_CASES)
def test_each_code_is_detected(code, build, cfg, g1_layout):
    found = {f.code for f in diagnose_all(build(), cfg, g1_layout)}
    assert code in found

def test_clean_job_has_no_findings(clean_metrics, clean_probes, cfg, g1_layout):
    assert diagnose_all((clean_metrics, clean_probes), cfg, g1_layout) == []
```

`INJECTED_CASES` phải đủ 12 dòng. AC 6 đạt khi test này xanh và `test_clean_job_has_no_findings` xanh.

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
    assert r.verdict == "UNCLEAR" and r.evaluated == ["missing_signal"]

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

| Thứ tự | Kiểm | Điều kiện | Kết luận |
|---|---|---|---|
| 1 | Thiếu tín hiệu | nhiệm vụ 2 | `UNCLEAR` |
| 2 | R3 bám lệnh | nhiệm vụ 2 | `CONTROLLER` |
| 3 | R1 độ trễ | `p99(latency_ms) > tau_lat` | `RUNTIME` |
| 3 | R2 buffer cạn | `buffer_underruns > r2.max_underruns` | `RUNTIME` |
| 4 | R4 đồng bộ | `max(abs(t_image − t_state)) > tau_sync` | `SYNC` |
| 5 | R5 camera | tham số camera khác bản tham chiếu đã hash | `CALIBRATION` |
| — | R6 hạ tầng | `infra_status != "ok"` | ghi `infra_status`, **không** tính là lỗi policy |

`chain.py` chạy chuỗi theo thứ tự trên và **dừng ở kết luận đầu tiên**, nhưng vẫn ghi lại mọi bước đã chấm cùng giá trị và ngưỡng vào `evaluated`, cộng các bước `skipped` kèm lý do (FR21: không bỏ im lặng). R6 kiểm trước chuỗi: `infra_status != "ok"` thì ghi và không chấm lỗi policy.

- [ ] **Bước 1: Viết test trước**, bắt buộc có test thứ tự:

```python
def test_order_puts_tracking_before_latency(trace_builder, cfg):
    # episode hỏng cả hai chỗ; kết luận phải là lớp của bước sớm hơn
    view = read_system_view(trace_builder(upper_track_error=0.5, latency_p99=200))
    r = check_system(view, cfg)
    assert r.verdict == "CONTROLLER"
    assert [e.name for e in r.evaluated] == ["missing_signal", "r3_tracking"]

def test_infra_error_is_not_a_policy_failure(trace_builder, cfg):
    r = check_system(read_system_view(trace_builder(infra_status="simulator_error")), cfg)
    assert r.infra_status == "simulator_error" and r.verdict == "INFRA"

def test_clean_episode_has_no_system_fault(clean_trace, cfg):
    assert check_system(read_system_view(clean_trace), cfg).verdict == "OK"
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

**Giao diện:** `attribute_stage(cluster, probes, system_result, train_findings, cfg) -> StageHypothesis` với `stage`, `suggested_intervention`, `confidence_note`, và `evidence: list[Evidence]` trong đó mỗi `Evidence` ghi `probe` (P1, P3, P4 hay T7), `scope` (khung hình hay episode nào), `value`, `threshold`. Chỉ chạy khi `system_result.verdict == "OK"` và kiểm dữ liệu đã qua; nếu không thì trả `stage=None` kèm lý do.

Bảng nằm trong YAML, mỗi dòng một điều kiện:

```yaml
table_variant: design-2026-10-27   # đổi sang spec-v10.4 khi Hiếu chốt
rows:
  - id: p1_wrong
    source: design-2026-10-27
    when: {p1_correct_on_failure_frame: false}
    stage: "1 · nhận thức"
    intervention: "Tăng cường thị giác; dữ liệu thêm ở điều kiện hình ảnh đó"
  - id: p1_wrong
    source: spec-v10.4
    when: {p1_correct_on_failure_frame: false}
    stage: "1 · nhận thức"
    intervention: "Synthetic tầng S3 (đổi ngoại hình)"
  - id: p3_group_high
    source: design-2026-10-27
    when: {p1_correct_on_failure_frame: true, p3_group_error_high: true}
    stage: "3 · học action nhóm đó"
    intervention: "Thêm demo hoặc dữ liệu sinh cho bước k"
  - id: p3_group_high
    source: spec-v10.4
    when: {p1_correct_on_failure_frame: true, p3_group_error_high: true}
    stage: "2 hoặc 3 · học action"
    intervention: "Thêm teleop hoặc synthetic S1-S2 cho bước k"
  - id: distribution_shift
    source: design-2026-10-27
    when: {p1_correct_on_failure_frame: true, p3_group_error_high: false, closed_loop_failed: true}
    stage: "Lệch phân phối khi chạy"
    intervention: "Correction từ trạng thái lỗi"
  - id: forgetting
    source: design-2026-10-27
    when: {new_failure_after_finetune: true, t7_present: true}
    stage: "3 · quên"
    intervention: "Giảm learning rate, tăng replay"
  - id: out_of_domain
    source: design-2026-10-27
    when: {out_of_train_domain: true}
    stage: null
    intervention: "Chỉ báo cáo"
```

Hai dòng `source: spec-v10.4` ghi lại khác biệt đã nêu trong story; `table_variant` chọn bản dùng. Khi Hiếu chốt thì bỏ bản không dùng và thêm dòng change log vào story, không sửa mã.

- [ ] **Bước 1: Viết test trước**:

```python
def test_no_hypothesis_when_system_fault_present(cfg):
    h = attribute_stage(cluster, probes, system_result=controller_fault, train_findings=[], cfg=cfg)
    assert h.stage is None and "lỗi hệ thống" in h.confidence_note

def test_every_hypothesis_carries_evidence(cfg):
    h = attribute_stage(cluster, probes_p1_wrong, system_ok, [], cfg)
    assert h.evidence and all(e.probe and e.scope and e.value is not None for e in h.evidence)

def test_variant_switch_changes_intervention_not_stage(cfg):
    a = attribute_stage(cluster, probes_p1_wrong, system_ok, [], variant(cfg, "design-2026-10-27"))
    b = attribute_stage(cluster, probes_p1_wrong, system_ok, [], variant(cfg, "spec-v10.4"))
    assert a.stage == b.stage and a.suggested_intervention != b.suggested_intervention

def test_out_of_domain_is_not_a_stage_fault(cfg):
    assert attribute_stage(cluster, probes_ood, system_ok, [], cfg).stage is None
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

Bộ lỗi cấy thật là DA-27 của Thông (`DefectManifest`); tới đó dùng trace cấy do `conftest.py` tự dựng. Khi DA-27 có bản sao cấy lỗi thì thêm một test ở `tests/contract/diagnosis/system/` đọc bản sao đó; đáp án `DefectManifest` **chỉ bộ chấm đọc**, test của DA-13 không được đọc đáp án để tự chấm.

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
