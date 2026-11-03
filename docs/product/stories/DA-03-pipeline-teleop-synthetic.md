# DA-03 · Pipeline teleop và synthetic: ingest, QA, release, báo cáo dataset

## Trạng thái

| Trường | Giá trị |
|---|---|
| Trạng thái | Sẵn sàng (PO chốt phạm vi 3/11/2026, [plan chia lại việc](../../superpowers/plans/2026-11-03-thong-reassignment.md) Q2, Q3) |
| Người làm | Hiếu |
| Làn | Dữ liệu |
| Story PRD | Story của [design 27/10/2026](../../superpowers/specs/2026-10-27-g1-psi0-demo-design.md) mục 6 · Epic 9 |
| Nhãn | [Lõi] · `epic:9` · `gate:G1` · `area:data` |
| Sprint | S1–S2 · **Lịch 3/11/2026:** hai PR; PR 1 (nhiệm vụ 1, 2) merge trước **5/11/2026**, PR 2 (nhiệm vụ 3–6) merge trước **9/11/2026** |
| Ước lượng | 10 giờ (PR 1 khoảng 4, PR 2 khoảng 6; ước lượng 3/11/2026; bản 07 0.6: 22 giờ cho cả 6 tầng) |
| Phụ thuộc | DA-25 (schema `Episode`, `QAReport`, `ReplayReport`, `DatasetReport`, file mẫu), PR `chore-data-pyarrow` (`numpy`, `pyarrow` cho `flywheel-data`). Đọc `has_injected_defect()` của DA-27 (Q5) và `ReplayReport` của DA-17 khi có; trong lúc chờ dùng file mẫu của testkit. Chặn DA-27 nhiệm vụ 8, DA-17, DA-02 (cần bộ đọc của PR 1) |

## Story

Là kỹ sư dữ liệu, tôi muốn mọi episode teleop và synthetic của task hai bàn và task khay đi qua cùng một pipeline ingest, QA, release có hash và báo cáo dataset, để biết dữ liệu nào đủ sạch cho Ψ₀ và cho demo phần "hiệu suất pipeline" ngày 17/11.

## Tiêu chí chấp nhận

_Phạm vi 3/11/2026 (Q2, Q3): trước 13/11 làm tầng 1 (ingest), 4 (QA), 5 (release) và báo cáo dataset của design mục 6, cho ba nguồn đã ở layout LeRobot v2.1 của Ψ₀: psi-data task hai bàn, khay S1 (DA-33), khay S2 (DA-35). Tầng 2 (normalize), tầng 3 (annotate, cắt đoạn) và nguồn bàn phím (DA-16) dời sau 13/11. Phần cần MuJoCo nằm trong adapter (`flywheel-simple/tray/`), không trong làn._

1. **Bộ đọc LeRobot v2.1.** `read_info`, `iter_episodes` đọc `meta/info.json` và parquet ra `EpisodeFrames` (timestamp, `frame_index`, state 32 chiều, action 36 chiều, số khung video theo camera lấy từ meta); `write_episode` ghi lại cùng layout (cho DA-27). Parquet thiếu cột `action` hoặc sai chiều (khác 36) thì ném lỗi có tên file và tên cột.
2. **Ingest.** `register_source` ghi sha256 từng file của gói và giấy phép, `data_class`; `to_episode` ra `Episode` đúng hợp đồng cho ba nguồn: psi-data (`source_kind = teleop`, `action_quality = measured`, `source_detail = psi_data`), khay S1 (`synthetic`, `planned`, `synthetic_tier = S1`), khay S2 (`source_detail = teleop_pico`).
3. **QA.** Bảy phép kiểm của spec mục 4.4 và phép kiểm riêng nguồn của design mục 6.3 (psi-data: số khung video khớp số dòng, `tasks` có câu lệnh; sinh tự động: kết quả rollout lại); ngưỡng trong `configs/data/qa.yaml`. Đọc `ReplayReport` nếu có: trượt động học thì `reject`, trượt động lực học thì `flag` (AC 3 của DA-17). Episode 0 hoặc 1 khung ra `reject` kèm lý do, không ném lỗi. Ra `QAReport` cho từng episode.
4. **Release.** `build_release` chặn episode `has_injected_defect()` (Q5): có một episode cấy lỗi thì từ chối cả release, không bỏ qua âm thầm. Chặn hạt giống điều kiện ngoài dải `train` của `configs/splits/default.yaml`. Manifest đóng băng có hash (`ReleaseManifest`); episode bị loại vẫn giữ cùng lý do (spec mục 4.4).
5. **Báo cáo dataset.** `DatasetReport` và một trang HTML tĩnh (design mục 6.5): số episode theo nguồn, pass, flag, reject theo phép kiểm, độ dài episode, stats theo nhóm action.
6. **Lệnh.** `fw data ingest | qa | release | report`; chạy trên psi-data và release khay S1 trên `rtx3060`; `fw data report` ra trang HTML cho cả hai.

## Nhiệm vụ

PR 1 (hạn 5/11/2026):

- [x] 1. Bộ đọc và ghi LeRobot v2.1, test trên dataset 3 episode sinh trong test (AC 1)
  - [x] 1.1 Không ép kiểu âm thầm: giá trị đổi khi đọc ra float32 (hay int64) thì báo lỗi có tên file, cột, số giá trị đổi (review #69 mục 2)
  - [x] 1.2 Số khung video đọc từ box `stsz` của mp4, video giả trong test có số khung bằng số dòng; ghi lại meta giữ các khóa bộ ghi không sở hữu (review #69 mục 6, 7)
  - [x] 1.3 Cột `index`: đánh số lại theo LeRobot v2.1 một cách tường minh, ghi dòng lineage, báo ở ingest, có test (review #69 mục 1; Q7 đã chốt 3/11 [Hiếu])
- [x] 2. `register_source`, `to_episode` cho ba nguồn (AC 2)
  - [x] 2.1 Lineage: `parent_id`, `root_id`, seed và level của episode sinh ra lấy từ `environment_config.flywheel`; nhãn ghi theo từng episode phải khớp nguồn (review #69 mục 3, 8)
  - [x] 2.2 Kiểm `split`: từ chối `holdout` (chỉ nằm trong `vault/`, chỉ `gate` đọc) và tên lạ; đối chiếu split đã ghi trong episode (review #69 mục 4)
  - [x] 2.3 `bundle_uri` tương đối theo gốc kho (`$FW_ROOT`, mặc định `./fwdata`); dataset ngoài gốc kho bị từ chối (Q6, đã chốt 3/11 [Hiếu])
  - [x] 2.4 Chặn `deid_status = raw` ở Annotate chỉ áp cho `source_kind = egocentric`; dữ liệu robot, sim, teleop không bị chặn (Q4, đã chốt 3/11 [Hiếu])
  - [x] 2.5 Ghi quyết định Q5 (id episode do bên ghi đặt, theo DA-25) và Q7 (đánh số lại `index` theo v2.1) vào mã và test (đã chốt 3/11 [Hiếu])

PR 2 (hạn 9/11/2026):

- [x] 3. QA: phép kiểm, ngưỡng, đọc `ReplayReport` (AC 3)
  - [x] 3.1 Ngưỡng và hành động khi trượt trong `configs/data/qa.yaml`, bộ nạp không có giá trị mặc định ngầm; ngưỡng bước nhảy action hiệu chỉnh trên psi-data
  - [x] 3.2 Bảy phép kiểm của spec mục 4.4 và phép kiểm riêng nguồn, mỗi phép kiểm mang một mã D của design mục 10; episode 0 hoặc 1 khung ra `reject`; đọc `ReplayReport` (động học trượt thì `reject`, động lực học thì `flag`); kiểm stats của dataset (D4)
- [x] 4. Release: chặn bản cấy lỗi, chặn hạt giống ngoài dải, manifest có hash (AC 4)
  - [x] 4.1 `build_release` từ chối cả release khi có bản sao chấm lỗi, hạt giống ngoài dải `train`, episode thiếu `QAReport` hoặc không thuộc split `train`
  - [x] 4.2 `Release` đóng băng có `manifest_sha256`, giữ episode bị loại cùng lý do; `ReleaseManifest` và file mẫu dùng chung trong testkit (mối nối `3-ReleaseManifest`)
- [x] 5. `DatasetReport` và trang HTML (AC 5)
- [ ] 6. Lệnh `fw data`; chạy trên psi-data và khay S1 trên `rtx3060` (AC 6)
  - [x] 6.1 `flywheel-data` phụ thuộc `flywheel-store`; mọi job ghi một dòng `LedgerEntry` ước tính và một dòng thực đo trỏ về nó (đã chốt 4/11 [Hiếu], "Cho phụ thuộc")
  - [x] 6.2 `fw data ingest | qa | release | report`
  - [ ] 6.3 Chạy trên psi-data và release khay S1 trên `rtx3060`, ghi số đo vào `docs/g0/data-pipeline.md`

## Giao diện

Theo plan chia lại việc mục 5, session 3. Session DA-27, DA-17, DA-02 dùng các hàm này qua API công khai của làn; chỉ story này sửa `api.py`, `cli.py`, `config.py` của `flywheel-data`.

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
    video_frames: dict[str, int]      # camera -> frame count from meta

def read_info(root: Path) -> dict[str, Any]: ...
def iter_episodes(root: Path) -> Iterator[EpisodeFrames]: ...
def write_episode(root: Path, frames: EpisodeFrames) -> None: ...

# flywheel/data/ingest/sources.py
def register_source(root: Path, source_detail: str, license: str,
                    data_class: Literal["public", "internal", "restricted"]) -> SourceRecord: ...
def to_episode(frames: EpisodeFrames, source: SourceRecord, split: str) -> Episode: ...

# flywheel/data/qa/checks.py
def run_qa(frames: EpisodeFrames, episode: Episode, replay: ReplayReport | None,
           cfg: QAConfig) -> QAReport: ...
# flywheel/data/release/build.py
def build_release(episodes: Sequence[Episode], reports: Sequence[QAReport],
                  split_plan: Path, out: Path) -> ReleaseManifest: ...
# flywheel/data/release/report.py
def dataset_report(dataset_id: str, episodes: Sequence[Episode],
                   reports: Sequence[QAReport]) -> DatasetReport: ...
def render_html(report: DatasetReport, out: Path) -> Path: ...
```

## Phạm vi file

Theo 07 mục 3.1. pr-guard chặn PR sửa file ngoài danh sách này; file story luôn được sửa. Phần egocentric của Hưng (thư mục ingest egocentric, `qa/egocentric.py`) không thuộc story này.

- `packages/flywheel-data/src/flywheel/data/ingest/lerobot.py`, `packages/flywheel-data/src/flywheel/data/ingest/sources.py`
- `packages/flywheel-data/src/flywheel/data/qa/checks.py`
- `packages/flywheel-data/src/flywheel/data/release/`
- `packages/flywheel-data/src/flywheel/data/api.py`, `packages/flywheel-data/src/flywheel/data/cli.py`, `packages/flywheel-data/src/flywheel/data/config.py`
- `packages/flywheel-data/src/flywheel/data/ledger.py` (dòng `LedgerEntry` của mọi job, 4/11/2026)
- `packages/flywheel-data/pyproject.toml`, `uv.lock` (chỉ thêm `flywheel-store`, 4/11/2026)
- `packages/flywheel-testkit/src/flywheel/testkit/fixtures/artifacts/ReleaseManifest.json` (file mẫu của mối nối `3-ReleaseManifest`, 4/11/2026)
- `packages/flywheel-data/tests/unit/pipeline/`, `packages/flywheel-data/tests/contract/pipeline/`
- `configs/data/qa.yaml`
- `docs/g0/data-pipeline.md`

## Ghi chú cho người làm

- Nguồn: design 27/10 mục 6 (6.1 định dạng, 6.3 QA, 6.5 báo cáo), 10 (mã lỗi D); spec mục 4.4; 03 mục 7.3 (artifact giữa làn); plan chia lại việc mục 4, 5 (session 3), 7.
- Chỉ import nhân (`flywheel.contracts`, `flywheel.store`, `flywheel.testkit`); không import `simple`, `psi0`, `lerobot`, `torch`, `mujoco` hay adapter (03 mục 7.3). Đọc parquet bằng `pyarrow`, không bằng `lerobot`. Thiếu trường trong hợp đồng thì dừng, báo Hiếu mở PR hợp đồng, không thêm trường tạm.
- `SourceRecord` là kiểu nội bộ của làn (không đi giữa làn); `Episode.source_id` trỏ về nó. Nếu làn khác cần đọc thì mở PR hợp đồng.
- Dùng lại phần adapter đã có của DA-33: export Ψ₀ (`flywheel-simple/tray/export.py`), phát lại QA (`tray/replay_qa.py`), release có hash (`tray/release.py`). Làn không import chúng; chỉ đọc file chúng ghi.
- Dữ liệu: `rtx3060:~/denso-da33/fwdata/psi-data/simple/G1WholebodyLocomotionPickBetweenTablesTeleop-v0`; release khay S1 của DA-33. Mọi lệnh nặng chạy trên `rtx3060` (RAM tối đa 60 GB, nhiều nhất 14 worker, qua `systemd-run` có `MemoryMax`). Dữ liệu trong `fwdata/`, không commit.
- Dữ liệu demo (psi-data, sim G1) là `public` (design mục 8.4).
- Tình huống cần test (plan mục 7): episode 0 hoặc 1 khung; parquet thiếu cột hay sai chiều; bản cấy lỗi đưa vào `build_release`.

## Kiểm thử

- Bộ đọc: dataset 3 episode sinh trong test, đọc ra đúng shape; ghi rồi đọc lại khớp từng giá trị; thiếu cột hay sai chiều ném lỗi có tên file và cột.
- QA: mỗi phép kiểm có một episode sai cố ý bị bắt; episode sạch qua.
- Release: một episode có `injected_defect` làm cả release bị từ chối; hạt giống thuộc dải dev hoặc holdout bị chặn.
- Chạy trên CPU với bộ giả và file mẫu của testkit; phần chạy trên dữ liệu thật ghi lệnh và output trong mô tả PR.

## Người phụ trách

- Làm: Dương Đình Hiếu, cùng Claude (từ 3/11/2026; trước đó Dương Tiến Thông, chưa có commit)
- Duyệt và merge: Dương Đình Hiếu (người duy nhất, 07 mục 3.4)
- Bình luận: Hưng (gọi `qa`, `release` qua API công khai cho episode egocentric), Châu (đọc `Episode`, `ReleaseManifest`)

## Change log

| Ngày | Nội dung | Người |
|---|---|---|
| 4/11/2026 | Thêm nhiệm vụ con 3.1–3.2, 4.1–4.2, 6.1–6.3 cho PR 2; thêm vào phạm vi file `ledger.py`, `pyproject.toml` của `flywheel-data`, `uv.lock` (PO chốt 4/11 "Cho phụ thuộc": `flywheel-data` phụ thuộc `flywheel-store`, job ghi `LedgerEntry`) và file mẫu `ReleaseManifest.json` của testkit | Claude, theo yêu cầu PO (Hiếu) |
| 3/11/2026 | Thêm nhiệm vụ con 2.3–2.5 theo quyết định Q4–Q7 của PO ("Chốt theo đề xuất") | Claude, theo yêu cầu PO (Hiếu) |
| 3/11/2026 | Thêm nhiệm vụ con 1.1–1.3, 2.1–2.2 theo review PR #69 của PO | Claude, theo yêu cầu PO (Hiếu) |
| 3/11/2026 | Tạo file story theo 07 bản 1.6 và plan chia lại việc (Q2, Q3, Q5): ingest, QA, release, báo cáo cho psi-data, khay S1, khay S2; normalize, cắt đoạn, nguồn bàn phím sau 13/11; hai PR | PO (Hiếu) |

## Ghi chép khi làm

- Giờ thực:
- Công cụ AI đã dùng:
- Ghi chú hoàn thành:
- File đã tạo hoặc sửa:
