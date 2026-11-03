# Chia lại việc của Thông: plan theo session

> **Cho agent thực thi:** mỗi session dưới đây là một story (hoặc một việc ngoài story) với nhánh, worktree và phiên Claude riêng (CLAUDE.md, "Quy tắc làm việc với story"). Khi mở session, đọc file story, file này, rồi dùng superpowers:writing-plans viết plan TDD chi tiết của riêng story đó trước khi sửa mã. Plan chi tiết để trong mô tả PR, không commit (phạm vi file của story không gồm `docs/superpowers/`).

**Mục tiêu:** đưa 5 story trên đường găng của Thông (S1-07, DA-27, DA-02, DA-03, DA-17) vào `master` trước 9/11/2026, do Hiếu và Claude làm, để phần 3 và 4 của demo (pipeline, Agent QA/QC trên bộ lỗi cấy) chạy được ở buổi chạy thử 12/11.

**Kiến trúc:** dùng lại phần adapter đã có của DA-33 (`flywheel-simple/tray/`: export Ψ₀, phát lại QA, release có hash). Phần còn thiếu là lớp phía làn trong `flywheel-data`: đọc LeRobot v2.1, chạy QA, sinh artifact đúng hợp đồng (`QAReport`, `ReplayReport`, `DatasetReport`, `DefectManifest`, `ReleaseManifest`). Làn chạy trên CPU với bộ giả của testkit; phần cần MuJoCo nằm trong adapter.

**Công nghệ:** Python 3, pydantic (hợp đồng), pyarrow và numpy (đọc parquet), pytest; MuJoCo của SIMPLE trên máy `rtx3060` cho phát lại.

**Nguồn:** [Design 27/10/2026](../specs/2026-10-27-g1-psi0-demo-design.md) mục 6, 9.2, 10, 11; [03 · Kiến trúc](../../product/03-architecture.md) mục 7.3; [07 · Chia việc](../../product/07-team-workflow.md) mục 2.2–2.4; file story trong `docs/product/stories/`.

_Ngày 3/11/2026. Trạng thái: [Đã chốt 3/11/2026] Hiếu chốt Q1–Q6 ở mục 3; lịch và giờ ở mục 5, 6 là ước lượng. Session 0 cập nhật 07 (bản 1.6), 08 (bản 0.4), RULE.md, CLAUDE.md gốc và file story._

## 1. Lý do

Số liệu tới 3/11/2026, kể từ khi giao việc ngày 27/10/2026:

| Chỉ số | Thông | Đội |
|---|---|---|
| Story trên đường găng | 5 (S1-07, DA-27, DA-02, DA-03, DA-17), khoảng 58 giờ ước lượng | — |
| Commit đã merge vào `master` | 0 | Hiếu 84, Long 17, Châu 14 |
| `Time-spent` đã ghi | 9 giờ, đều trên nhánh chưa merge | Đã merge: Hiếu 55 giờ, Châu 19 giờ, Long 9,2 giờ |
| PR #24 (S1-07) | Lần đẩy cuối 29/10; 5 comment review từ 1/11 đến 3/11 chưa trả lời; 1 commit thay vì 7 | Hạn 4/11 |
| DA-27 | 5 commit đẩy trong 74 giây ngày 1/11, chưa mở PR, không dùng `DefectManifest` của hợp đồng | Hạn 6/11 |
| File story DA-02, DA-03 | Chưa viết (hạn 28/10) | — |
| Báo cáo ngày (issue #2) | 0 | — |

## 2. Hiện trạng: đã có gì

| Phần | Ở đâu | Dùng được gì |
|---|---|---|
| S1-07 của Thông | PR #24, nhánh `S1-07-psi-data` @ `e96da77` | Cấu trúc gói đúng: LeRobot v2.1, 50 Hz, state 32, camera 360×640, N = 99, độ dài episode. Sai: layout action, QA gán cứng, hash F1 gán cứng, `data_class`, seed (comment của Hiếu ngày 3/11 trên #24) |
| DA-27 của Thông | Nhánh `DA-27-bo-loi-cay` @ `6b4e327`, 5 commit | 11 hàm cấy lỗi, log T1–T8 và R1–R2, bản sạch, `InjectConfig`, `configs/data/inject.yaml`; 29/29 test qua, `ruff` và `mypy` sạch; rebase lên `0030bbc` không xung đột. Thiếu: dùng hợp đồng, mã lỗi D/T/R, chạy trên parquet thật |
| Export Ψ₀ v2.1 | [tray/export.py](../../../packages/flywheel-simple/src/flywheel_simple/tray/export.py) | Ra đúng layout của psi-data qua `postprocess_psi0_sonic.py` của SIMPLE, kèm `meta/action_layout.json`, `stats_psi0.json` |
| Phát lại QA | [tray/replay_qa.py](../../../packages/flywheel-simple/src/flywheel_simple/tray/replay_qa.py) | Phát lại qua `replay-decoupled-wbc` của SIMPLE, `check_success`, sai lệch tư thế khay |
| Release có hash | [tray/release.py](../../../packages/flywheel-simple/src/flywheel_simple/tray/release.py) | Manifest sha256 từng file, `release_hash` |
| Hợp đồng | [artifacts.py](../../../packages/flywheel-contracts/src/flywheel/contracts/artifacts.py), `v0.py` | `Episode`, `EpisodeMetadata.injected_defect`, `ActionLayout`, `ReplayReport`, `DatasetReport`, `QAReport`, `DefectManifest`, `ReleaseManifest`; file mẫu trong `flywheel-testkit/fixtures/artifacts/` |
| Dữ liệu | `rtx3060:~/denso-da33/fwdata/psi-data/simple/G1WholebodyLocomotionPickBetweenTablesTeleop-v0`; `rtx3060:~/denso-s103/fwdata/simple-eval/` | Gói task hai bàn và tập eval đã tải; F1 chưa tải |
| `flywheel-data` | `packages/flywheel-data/` | Chỉ có khung rỗng; phụ thuộc chỉ gồm `flywheel-contracts`, `pyyaml`, `typer`, chưa đọc được parquet |

## 3. Quyết định đã chốt

| # | Quyết định | Kết quả |
|---|---|---|
| Q1 | Rút Thông khỏi S1-07, DA-27, DA-02, DA-03, DA-17, DA-21 và vai Scrum Master | [Đã chốt 3/11/2026] Có. Hiếu làm với Claude; DA-21 để sau 13/11, chưa có chủ |
| Q2 | Thu hẹp DA-02, DA-03, DA-17 về lớp phía làn, dùng lại adapter DA-33 | [Đã chốt 3/11/2026] Có, theo mục 5 |
| Q3 | Dời sau 13/11: DA-17 AC 5 (phát lại action dự đoán, video); DA-03 tầng normalize và annotate (cắt đoạn), nguồn bàn phím | [Đã chốt 3/11/2026] Có. Cả ba nguồn trước demo đã ở layout Ψ₀; DA-29 và DA-16 đã dời ngày 3/11 |
| Q4 | Giữ phần dùng được của Thông | [Đã chốt 3/11/2026] DA-27: cherry-pick 5 commit, giữ tác giả Thông. S1-07: nhánh mới, dùng lại số đúng của #24, đóng #24 kèm lời cảm ơn |
| Q5 | Rào chặn release (DA-27 AC 5) | [Đã chốt 3/11/2026] DA-27 xuất `has_injected_defect()`; `release` của DA-03 gọi hàm này, mỗi bên có test riêng |
| Q6 | Chủ đường dẫn của Thông (07 mục 2.1) | [Đã chốt 3/11/2026] Chuyển sang Hiếu; người dự phòng của phần egocentric trong `flywheel-data` đổi từ Thông sang Hiếu |

## 4. Ràng buộc chung

- Làn `flywheel.data` chỉ import `flywheel.contracts`, `flywheel.store`, `flywheel.testkit`; không import `simple`, `psi0`, `lerobot`, `torch`, `mujoco` hay adapter (03 mục 7.3).
- Thiếu trường trong hợp đồng thì dừng, mở PR hợp đồng riêng; không thêm trường tạm.
- Bản cấy lỗi không bao giờ vào release train; `DefectManifest` chỉ bộ chấm đọc.
- Dữ liệu trong `fwdata/`, không commit.
- Mọi lệnh nặng chạy trên `rtx3060`: RAM tối đa 60 GB, nhiều nhất 14 worker, qua `systemd-run` với `MemoryMax`.
- Commit `<story-id>/<n>: …`, mỗi nhiệm vụ con một commit, đánh `[x]` trong file story cùng commit, có bằng chứng và `Time-spent`.
- Trước PR: `uv run ruff check`, `uv run mypy`, `uv run pytest`, import-linter, `python3 scripts/repo/pr_guard.py --base origin/master --head HEAD --branch "$(git branch --show-current)"`.
- `api.py`, `cli.py`, `pyproject.toml` của `flywheel-data` chỉ session DA-03 sửa; các session khác xuất API qua module của mình.

## 5. Các session

| Session | Nhánh | Việc | Hạn merge | Cần trước | Giờ (ước lượng) |
|---|---|---|---|---|---|
| 0 | `docs-reassign-thong`, `chore-data-pyarrow` | Tài liệu chia lại việc; thêm `pyarrow`, `numpy` cho `flywheel-data` | 3/11 | Q1–Q6 (đã chốt) | 1,5 |
| 1 | `S1-07-psi-data-v2` | S1-07 | 4/11 | — | 3,5 |
| 2 | `DA-27-defect-inject` | DA-27 | 6/11 | Session 0 (pyarrow), session 3 PR 1 (bộ đọc) cho nhiệm vụ 4 | 5 |
| 3 | `DA-03-data-pipeline` | DA-03, hai PR | PR 1: 5/11; PR 2: 9/11 | Session 0 | 10 |
| 4 | `DA-17-replay-check` | DA-17 | 8/11 | Session 3 PR 1 | 5 |
| 5 | `DA-02-export-checklist` | DA-02 | 9/11 | Session 3 PR 1 | 3,5 |

Tổng khoảng 28,5 giờ ước lượng, so với khoảng 48 giờ còn lại của Thông theo 07 mục 2.4.

### Session 0 · tài liệu và phụ thuộc (phiên hiện tại)

**PR `docs-reassign-thong`:**

- [x] 0.1 Sửa 07: mục 2.0 (vai của Thông), 2.1 (chủ đường dẫn theo Q6), 2.2 (cột Chủ, Giờ của DA-02, DA-03, DA-17, DA-21, DA-27), 2.3, 2.4 (hạn mới theo bảng trên); tăng bản, thêm change log.
- [x] 0.2 Sửa file story S1-07, DA-17, DA-21, DA-27: "Người làm", "Người phụ trách", phạm vi theo Q2–Q5, change log. DA-17 thêm vào phạm vi `packages/flywheel-simple/src/flywheel_simple/replay/` và test tương ứng.
- [x] 0.3 Viết file story DA-02, DA-03 theo mẫu, có "Phạm vi file" (mục 2.2 của 07 và session 3, 5 dưới đây).
- [ ] 0.4 `python3 scripts/repo/check_links.py`, `pr_guard.py`, mở PR.

**PR `chore-data-pyarrow`:**

- [ ] 0.5 Thêm `numpy`, `pyarrow` vào `dependencies` của `packages/flywheel-data/pyproject.toml`; `uv lock`; `uv run pytest` xanh; mở PR.

**Việc của Hiếu, không giao Claude:** báo Thông; đóng #24 sau khi PR của session 1 mở; merge.

### Session 1 · S1-07 phân tích psi-data

**Đầu vào:** comment của Hiếu ngày 3/11 trên #24 (6 điểm); `scripts/g0/inspect_psi_data.py` của nhánh `S1-07-psi-data` làm điểm xuất phát; dữ liệu đã tải trên `rtx3060`.

**Phạm vi file:** `docs/g0/psi-data.md`, `docs/g0/ledger/S1-07.csv`, `scripts/g0/inspect_psi_data.py`.

- [ ] 1 Tải gói F1 (`BendPickTeleop`, `BendPickMP`) ở revision `e78fb93`; băm sha256 mọi file, gồm cả hai gói đã có; ghi đường dẫn đầy đủ. Kích thước gói eval là 480.532 B.
- [ ] 2 Bảng 36 dòng `index, name, group, masked` lấy từ `meta/info.json` và `ACTION_SLICES_36D` của Ψ₀ @ `cda3fdf`. Action có 36 chiều thật; 4 chiều đệm là của state.
- [ ] 3 QA thật trên parquet: timestamp đơn điệu, không NaN hay Inf, độ dài trong khoảng, cờ thành công nếu có. Ra N_teleop của task hai bàn và của F1. Bỏ phần sinh 80 episode giả.
- [ ] 4 Seed: dẫn `configs/splits/default.yaml`; seed của tập eval nếu không có trong gói thì ghi "không suy được".
- [ ] 5 Giấy phép: `data_class = public`, `license = unknown`, ngày kiểm từng dòng; soạn thư hỏi PSI Lab cho Hiếu gửi.
  - Ghi chú 3/11/2026: thư không gửi; PO bỏ mọi việc xin giấy phép, `license = unknown` ghi là giới hạn (PR S1-07 #55 đã merge, mục 5 của `docs/g0/psi-data.md` chỉ giữ hai câu về tập eval).
- [ ] 6 Thống kê mô tả: độ dài, tỉ lệ thành công, phân bố vị trí vật và bàn (hoặc một câu "không có").
- [ ] 7 `docs/g0/psi-data.md` có mục "Đề xuất cho 03 §3.3" (V1, V6, V9); mô tả PR ghi lệnh và output cho từng AC.

**Xong khi:** 7 AC có bằng chứng là output lệnh; không còn số nào gán cứng trong script.

### Session 2 · DA-27 bộ lỗi cấy

**Đầu vào:** nhánh `DA-27-bo-loi-cay` @ `6b4e327`; bảng ánh xạ mã lỗi ở design 27/10 mục 10 (sửa 3/11); bộ đọc của session 3 PR 1.

**Phạm vi file:** như story (`flywheel-data/inject/`, `tests/unit/inject/`, `configs/data/inject.yaml`, `docs/g0/defect-inject.md`).

**Giao diện xuất (`flywheel.data.inject.api`):**

```python
def inject_copy(src_root: Path, out_root: Path, cfg: InjectConfig) -> DefectManifest: ...
def clean_copy(src_root: Path, out_root: Path, cfg: InjectConfig) -> DatasetRef: ...
def seal_manifest(manifest: DefectManifest, path: Path) -> str: ...  # trả sha256
def has_injected_defect(episode: Episode) -> bool: ...
```

- [ ] 1 Cherry-pick 5 commit của Thông lên `origin/master`, giữ tác giả; chạy lại 29 test.
- [ ] 2 Thay `DefectManifestRecord`, `DefectRecord` bằng `DefectManifest`, `Defect` của hợp đồng; episode cấy lỗi mang `EpisodeMetadata.injected_defect`.
- [ ] 3 Đổi mã lỗi theo design: rơi khung và lệch đồng bộ → D2; nhảy khớp, vượt giới hạn, NaN, sai đơn vị → D3; trùng episode, rò hạt giống → D5; nhãn thành công sai, câu lệnh sai → D6; đảo dấu một chiều action → D7; tên cũ giữ trong `parameters["kind"]`. Log giữ T1–T8, R1–R2.
- [ ] 4 Cấy lên bản sao parquet thật (đọc bằng bộ đọc của session 3 PR 1, ghi lại cùng layout), tỉ lệ 5–10%, hạt giống ghi trong manifest.
- [ ] 5 Bản sạch cùng số episode; `seal_manifest` ghi `defect_manifest.json` và `.sha256`; test agent không đọc được manifest.
- [ ] 6 `has_injected_defect` và test; chạy trên `rtx3060` ra `fwdata/inject/<dataset_id>/{injected,clean}`, gửi `DatasetRef` và đường dẫn manifest cho Châu (DA-31).

**Xong khi:** mỗi loại lỗi có một test cấy và kiểm; bản cấy lỗi và bản sạch có trên `rtx3060`; Châu xác nhận đọc được.

### Session 3 · DA-03 pipeline teleop và synthetic

**PR 1 (hạn 5/11): bộ đọc và ingest.** Session 2, 4, 5 dùng PR này.

```python
# flywheel/data/ingest/lerobot.py
@dataclass(frozen=True)
class EpisodeFrames:
    episode_index: int
    task: str
    timestamp: NDArray[np.float64]    # (T,)
    frame_index: NDArray[np.int64]    # (T,)
    states: NDArray[np.float32]       # (T, 32)
    action: NDArray[np.float32]       # (T, 36)
    video_frames: dict[str, int]      # camera -> số khung giải mã được từ meta

def read_info(root: Path) -> dict[str, Any]: ...
def iter_episodes(root: Path) -> Iterator[EpisodeFrames]: ...
def write_episode(root: Path, frames: EpisodeFrames) -> None: ...  # cho DA-27

# flywheel/data/ingest/sources.py
def register_source(root: Path, source_detail: str, license: str,
                    data_class: Literal["public", "internal", "restricted"]) -> SourceRecord: ...
def to_episode(frames: EpisodeFrames, source: SourceRecord, split: str) -> Episode: ...
```

- [ ] 1 Viết bộ đọc LeRobot v2.1 và test trên một dataset 3 episode sinh trong test.
- [ ] 2 `register_source` ghi sha256 từng file và `SourceRecord`; `to_episode` ra `Episode` đúng hợp đồng cho ba nguồn: psi-data (`teleop`, `measured`), khay S1 (`synthetic`, `planned`, `S1`), khay S2 (`teleop_pico`).

**PR 2 (hạn 9/11): QA, release, báo cáo.**

```python
def run_qa(frames: EpisodeFrames, episode: Episode, replay: ReplayReport | None,
           cfg: QAConfig) -> QAReport: ...                                  # qa/checks.py
def build_release(episodes: Sequence[Episode], reports: Sequence[QAReport],
                  split_plan: Path, out: Path) -> ReleaseManifest: ...      # release/build.py
def dataset_report(dataset_id: str, episodes: Sequence[Episode],
                   reports: Sequence[QAReport]) -> DatasetReport: ...       # release/report.py
def render_html(report: DatasetReport, out: Path) -> Path: ...
```

- [ ] 3 QA: 7 phép kiểm của spec mục 4.4 và phép kiểm riêng nguồn của design mục 6.3; ngưỡng trong `configs/data/qa.yaml`; đọc `ReplayReport` nếu có (`decision` theo AC 3 của DA-17: trượt động học thì `reject`, trượt động lực học thì `flag`).
- [ ] 4 Release: chặn episode `has_injected_defect`, chặn hạt giống ngoài dải của `configs/splits/default.yaml`, manifest đóng băng có hash.
- [ ] 5 `DatasetReport` và trang HTML tĩnh: số episode theo nguồn, pass/flag/reject theo phép kiểm, độ dài, stats theo nhóm action.
- [ ] 6 Lệnh `fw data ingest | qa | release | report` trong `cli.py`; chạy trên psi-data và release khay S1 trên `rtx3060`.

**Phạm vi file:** `flywheel-data/ingest/` (trừ `egocentric/`), `qa/` (trừ `egocentric.py`), `release/`, `api.py`, `cli.py`, `config.py`, test tương ứng, `configs/data/qa.yaml`, `docs/g0/data-pipeline.md`.

**Xong khi:** `fw data report` ra trang HTML cho release khay S1 và psi-data; release từ chối bản cấy lỗi của session 2.

### Session 4 · DA-17 phát lại action

```python
# flywheel/data/replay_check/kinematic.py
def check_kinematic(frames: EpisodeFrames, layout: ActionLayout,
                    th: ReplayThresholds) -> ReplayReport: ...   # mode="kinematic"
# flywheel/data/replay_check/dynamic.py
def report_from_outcome(episode_id: str, outcome: ReplayOutcome,
                        th: ReplayThresholds) -> ReplayReport: ...  # mode="dynamic"
# flywheel/data/replay_check/thresholds.py
def calibrate(outcomes: Sequence[ReplayOutcome], quantile: float = 0.99) -> ReplayThresholds: ...
# flywheel_simple/replay/outcomes.py (adapter)
def replay_lerobot(root: Path, work: Path, workers: int) -> Path: ...  # ghi replay_outcomes.jsonl
```

`ReplayOutcome` là một dòng của `replay_outcomes.jsonl`: `episode_index`, `success`, `state_error_by_group`, `hand_event_offset_steps`. Làn chỉ đọc JSON, không import adapter.

- [ ] 1 Động học: vượt giới hạn khớp (`ActionDimension.limit_low/high`), nghi sai độ/radian, nhảy khớp, lệch `timestamp` so với `frame_index / fps`; ra danh sách khung lỗi.
- [ ] 2 Động lực học: `replay_lerobot` dùng lại cách chạy của `tray/replay_qa.py` cho mọi dataset LeRobot của SIMPLE; `report_from_outcome` ra `error_by_group`, `hand_event_offset_steps`, `sim_success`.
- [ ] 3 Ngưỡng: chạy trên 99 episode psi-data trên `rtx3060`, `calibrate` ra phân vị 99, ghi `configs/data/replay.yaml` có hash.
- [ ] 4 Test với 3 lỗi cấy (đảo dấu một khớp, độ thay radian, lệch 2 khung) trên dữ liệu sinh trong test và sim giả của testkit; episode sạch không bị đánh dấu.
- [ ] 5 (dời sau 13/11 nếu Q3 được chốt) phát lại action dự đoán, video.

Giới hạn khớp lấy từ `meta/action_layout.json` của export khay cho tới khi DA-01 (Long, hạn 5/11) điền `configs/embodiments/g1.yaml`.

**Phạm vi file:** `flywheel-data/replay_check/`, test tương ứng, `configs/data/replay.yaml`, `docs/g0/replay.md`, `flywheel-simple/src/flywheel_simple/replay/` và test.

### Session 5 · DA-02 checklist export v2.1

```python
# flywheel/data/export/checklist.py
def check_lerobot_v21(root: Path, layout: ActionLayout) -> list[QACheck]: ...  # điểm 1–6 của design 6.4
```

- [ ] 1 Điểm 1–6 của checklist design mục 6.4 trong làn (pyarrow, json; điểm 4 đọc số khung từ meta, không giải mã video trong làn).
- [ ] 2 Điểm 7 trong `flywheel-psi0`: contract test đọc lại một batch bằng loader Ψ₀ @ `cda3fdf`, so với batch mẫu đã lưu; chạy trong venv Ψ₀.
- [ ] 3 Chạy checklist trên release khay S1 và trên psi-data; ghi output vào `docs/g0/export-v21.md`.

**Phạm vi file:** `flywheel-data/export/` (trừ `egodex.py`), test tương ứng, `packages/flywheel-psi0/tests/contract/test_loader_roundtrip.py`, `docs/g0/export-v21.md`.

## 6. Lịch

| Ngày | Việc |
|---|---|
| 3/11 | Session 0; mở session 1 và session 2 (nhiệm vụ 1–3, chưa cần bộ đọc) |
| 4/11 | Merge session 1 và `chore-data-pyarrow`; mở session 3 PR 1 |
| 5/11 | Merge session 3 PR 1; mở session 4 và 5; session 2 làm nhiệm vụ 4–6 |
| 6/11 | Merge session 2; Châu nhận bản cấy lỗi |
| 7–8/11 | Session 4 chạy ngưỡng trên `rtx3060`, merge 8/11; session 3 PR 2 |
| 9/11 | Merge session 3 PR 2 và session 5 |
| 10–11/11 | Dự phòng; 11/11 là hạn merge cuối của đội |

Nhiều nhất ba session viết mã chạy cùng lúc, vì Hiếu là người duyệt duy nhất và còn đường găng riêng (DA-19, DA-26, DA-34, DA-35, hook `SimpleSim`).

## 7. Điểm cần soát

Các tình huống dưới đây không AC nào nhắc nhưng dễ gây hỏng nhất; session chủ quản thêm một test cho mỗi dòng.

| Tình huống | Hành vi mong đợi | Session |
|---|---|---|
| Episode 0 khung hoặc 1 khung | QA `reject` kèm lý do, không ném lỗi | 3 |
| Parquet thiếu cột `action` hoặc sai chiều (không phải 36) | Bộ đọc ném lỗi có tên file và cột | 3 |
| Bản cấy lỗi bị đưa vào `build_release` | Release từ chối toàn bộ, không bỏ qua âm thầm | 3, 2 |
| Agent hoặc QA mở `defect_manifest.json` | Test chặn; chỉ bộ chấm có quyền đọc | 2 |
| Chiều action bị mask có độ lệch chuẩn 0 | Checklist không báo lỗi stats cho chiều đã mask | 5 |

## 8. Rủi ro

| Rủi ro | Cách giảm |
|---|---|
| Hiếu duyệt khoảng 8 PR trong 6 ngày, cùng đường găng riêng | Tối đa ba session cùng lúc; PR nhỏ theo nhiệm vụ con |
| DA-01 trễ | Dùng `meta/action_layout.json` của export khay |
| `rtx3060` bận vì chạy DA-34 | Phát lại psi-data dùng ít worker, chạy ngoài giờ fine-tune |
| Gói F1 lớn | S1-07 chỉ cần hash và N_teleop; không giữ bản giải nén |
