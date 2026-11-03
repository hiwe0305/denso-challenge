# Báo cáo và thiết kế Bộ cấy lỗi (DA-27)

Tài liệu kỹ thuật theo [design 27/10/2026](../superpowers/specs/2026-10-27-g1-psi0-demo-design.md) mục 9.2 và mục 10. Phục vụ bộ chấm DA-31 và Agent QA/QC DA-20 trước khi train model.

---

## 1. Mục tiêu và nguyên tắc thiết kế

1. **Không sửa bản gốc:** Mọi thao tác cấy lỗi chỉ thực hiện trên bản sao (deep copy), bảo toàn toàn vẹn dữ liệu gốc của `psi-data`.
2. **Khóa đáp án trước (Answer Key Lock):** Danh sách lỗi cấy và tham số được ghi vào `DefectManifest` của `flywheel.contracts` (mỗi lỗi là một `Defect`). `seal_manifest` ghi `defect_manifest.json` và `defect_manifest.sha256` ở thư mục đáp án riêng, và từ chối ghi vào bên trong thư mục bản sao mà agent đọc (`copy_roots`). Chỉ bộ chấm (`flywheel.eval.agentqa.bench`, DA-31) đọc file này; test `test_read_barrier.py` quét mã của agent (`flywheel.eval.agentqa`, trừ `bench/`) và của phép kiểm (`flywheel.data`, trừ `inject/`, `cli.py`, `api.py`) và đỏ nếu có chỗ nào nhắc tới `DefectManifest`, `defect_manifest` hay `load_manifest`.
3. **Đối chứng sạch (Clean Baseline):** Luôn sinh kèm một tập sạch có kích thước tương đương để đo tỉ lệ báo nhầm (False Positive Rate). Bản sạch chép từ bản gốc, không từ bản cấy. Hai bản sao mang id trung tính cùng dạng `bench-<12 hex>` (`copy_ids(seed)`), không chứa chữ nào lộ vai trò như `clean`, `defect`; bản nào là bản sạch chỉ thấy trong `DefectManifest` (bản sạch có `defects` rỗng), file chỉ bộ chấm đọc.
4. **Rào chắn Release (Release Barrier):** mọi episode của hai bản sao chấm, cả episode có lỗi lẫn episode sạch, mang `EpisodeMetadata.benchmark_copy_id` (bằng `dataset_id` của bản sao) và bị từ chối nếu đưa vào tập huấn luyện hoặc release chính thức. Đáp án chỉ nằm trong `DefectManifest`, không ghi lên episode, nên agent đọc episode không biết episode nào có lỗi (design mục 6.1, 9.2; 03 bản 1.0 mục 4.3; issue #62). `release` của DA-03 gọi `flywheel.data.inject.api.has_injected_defect(episode)` trên `Episode` của hợp đồng.

---

## 2. Danh mục 11 loại lỗi dữ liệu (F-DATA)

Cấu hình tại `configs/data/inject.yaml`. Mã lỗi theo bảng ánh xạ của design mục 9.2 (sửa 3/11/2026, issue #34): `Defect.code` ghi mã mục 10, `parameters["kind"]` ghi tên loại. Recall của DA-31 tính theo loại, precision tính theo mã.

Số episode cấy (quyết định PO 3/11/2026): mỗi loại đúng 3 episode khác nhau (`episodes_per_kind: 3`), tổng 33 trên 99; mỗi episode mang tối đa một lỗi. Với `duplicate_episode`, chỗ được chọn bị ghi đè bằng bản sao của một episode không cấy; bản gốc giữ nguyên, chỉ bản sao tính là episode cấy. Cùng `seed` cho cùng manifest.

Chỉ ghi lỗi đã cấy thật (DA-31 tính recall theo loại từ manifest): episode không có gì để lỗi đó thay đổi (ví dụ mọi chiều góc của action bằng 0) bị bỏ qua, bộ cấy chọn episode khác; sau khi cấy, `flywheel.data.inject.applied.defect_applied` kiểm từng dòng manifest đúng là đã đổi dữ liệu ở chỗ nó ghi, sai thì dừng. Chiều action theo layout 36 chiều của G1 (design mục 9.2). Khi truyền `ActionLayout` (ví dụ `meta/action_layout.json` của export), lỗi trên action bỏ qua chiều bị mask và chiều layout không có. `test_g1_layout.py` chạy bộ cấy trên `configs/embodiments/g1.yaml` thật (DA-01): `g1.yaml` đổi chiều, giới hạn hay mask thì test đỏ.

| Mã | Loại (`kind`) | Tên lỗi | Mô tả cơ chế cấy | Tham số cấu hình |
|---|---|---|---|---|
| D1 | `nan_values` | Giá trị NaN/Inf | Gán giá trị NaN vào quan sát hoặc hành động | `nan_ratio: 0.05` |
| D2 | `drop_frames` | Rơi khung ảnh | Bỏ hẳn dòng parquet của 10–20% khung (state, action, timestamp cùng mất; `frame_index` có khoảng trống); video giữ nguyên nên dài hơn số dòng | `drop_rate: 0.15` |
| D2 | `timestamp_sync_offset` | Lệch đồng bộ camera và state | Dịch cột `timestamp` (thời gian state) so với thời gian ảnh của video (`frame_index / fps`) | `offset_seconds: 0.08` (> τ_sync 0.033s) |
| D3 | `joint_jump` | Nhảy khớp đột ngột | Cộng bước nhảy vào một chiều khớp (0–30) của action ở giữa episode | `jump_magnitude: 1.5` |
| D3 | `joint_limit_exceeded` | Vượt giới hạn khớp | Đặt một chiều khớp (0–30) của action vượt `limit_high` của `ActionLayout` thêm 25% biên độ khớp; không có layout thì dùng ±π | `excess_factor: 1.25` |
| D3 | `unit_deg_rad` | Sai đơn vị góc | Nhân một chiều góc (0–30, 35) của action, khác 0 trên episode, với $180/\pi$ | `scale: 57.2957795` |
| D5 | `duplicate_episode` | Trùng lặp episode | Nhân bản episode với dữ liệu giống hệt | `dup_id` |
| D5 | `holdout_seed_leak` | Rò hạt giống holdout | Gán seed trong dải holdout của `configs/splits/default.yaml` | `holdout_seed_range: [2000000, 2000999]` |
| D6 | `corrupted_success_label` | Episode hỏng nhưng gắn nhãn thành công | Robot dừng từ `keep_fraction` số khung (action và state giữ nguyên tới hết), trước khi task xong; số khung, video và nhãn thành công giữ nguyên (demo teleop của psi-data mặc nhiên là thành công) | `keep_fraction: 0.5` |
| D6 | `wrong_task_instruction` | Sai câu lệnh task | Đổi câu lệnh gốc thành câu lệnh sai lệch | `corrupted_prompt` |
| D7 | `action_sign_flip` | Đảo dấu action | Đổi dấu một chiều action có độ lệch chuẩn khác 0 trên episode | chọn theo episode |

### Cấy trên bản sao LeRobot

`flywheel.data.inject.lerobot_copy.inject_copy(src_root, out_root, cfg, layout)` đọc gói bằng bộ đọc của DA-03 (`iter_episodes`), chọn và cấy lỗi như trên, rồi ghi bản sao bằng `write_episode`; làn không có mã parquet riêng. Bản gốc không bị ghi. Mọi episode của bản sao được ghi lại theo thứ tự tăng dần, không chỉ episode có lỗi, vì bộ ghi đánh số lại `index` và ghi `meta/flywheel_lineage.jsonl`; ghi lại một phần sẽ làm lộ episode có lỗi. `duplicate_episode` nhận parquet và video của episode nguồn. Seed rò ghi vào `environment_config.flywheel.seed` của dòng `meta/episodes.jsonl`. Bản sao có `meta/benchmark_copy.json` (`benchmark_copy_id`); đáp án chỉ ở manifest trả về. Id episode trong manifest là tên file parquet (`episode_000012`).

Hai bản sao không được lộ đáp án qua thứ gì ngoài chính lỗi (sửa 4/11/2026):

- **Stats tính lại từ dữ liệu của bản sao.** `flywheel.data.inject.stats.write_stats` ghi `episodes_stats.jsonl`, `stats.json`, `stats_psi0.json`, `relative_stats.json` cho mọi episode của cả hai bản, theo đúng `stats_block` của `scripts/postprocess_psi0_sonic.py` (SIMPLE `6d10628`). Nếu chép stats của bản gốc, ai tính lại stats cũng liệt kê được đúng các episode đã đổi mà không cần phát hiện lỗi. `stats.json` của psi-data `e78fb93` không suy ra được từ parquet của chính nó ở cột `states` (lệch mean tới 3,6e-4), nên stats của bản gốc không dùng làm chuẩn. Đo trên `e78fb93` (`tests/unit/inject/test_source_stats.py`, chạy với `DA27_PSI_DATA`): stats từng episode lệch tối đa 3e-8, stats toàn tập mọi cột trong 1e-6 trừ `states` (3,63e-4), một phát hiện D4 trên dữ liệu của tác giả. Stats không tính lại được (ảnh cần giải mã video) mang theo từ episode có video mà bản sao đang giữ, theo thứ tự feature của file gốc; psi-data không có stats ảnh.
- **Lineage của bộ ghi ở phía bộ chấm.** Mỗi dòng `meta/flywheel_lineage.jsonl` ghi `old_first` (index của bản gốc); từ đó suy ra độ dài episode gốc và lộ episode bị cắt, còn số dòng thì lộ bản nào sạch (95 so với 98 trên psi-data). Bản ghi vẫn giữ nguyên, append-only, nhưng chuyển sang `answers/<id>/flywheel_lineage.jsonl`. Hai bản sao có cùng tập file.
- **Một mtime cho mọi file** của cả hai bản, nên thời điểm ghi không chỉ episode nào.
- Ngoài `meta/benchmark_copy.json` (dấu bản sao, có ở cả hai), không file nào chứa chữ `inject`, `defect`, `duplicate`, `bench` (có test).
- **Mức file đồng nhất.** Cả 99 episode của cả hai bản đi qua cùng bộ ghi, nên footer parquet (`created_by`, codec, số row group, schema metadata) giống hệt nhau trong và giữa hai bản; đo trên psi-data: một biến thể duy nhất, `parquet-cpp-arrow 26.0.0`, SNAPPY, 1 row group (bản gốc là 23.0.1). Video không mã hóa lại: mọi file trùng từng byte với video cùng đường dẫn của bản gốc, trừ bản trùng mang video của episode nguồn. `length` của `episodes.jsonl` bằng số dòng ở mọi episode (có test).

Tín hiệu đổi theo từng loại, ngoài chính lỗi (giữ khi một lần xảy ra thật cũng tạo ra nó):

| Loại | Tín hiệu đổi ngoài lỗi | Một lần xảy ra thật có tạo ra không |
|---|---|---|
| `nan_values` | stats của episode có NaN | có |
| `timestamp_sync_offset` | stats `timestamp` của episode | có |
| `drop_frames` | ít dòng hơn số khung video; `index` của các episode sau dời đi; stats | có: bộ ghi mất dòng thì video vẫn đủ khung |
| `joint_jump`, `joint_limit_exceeded`, `unit_deg_rad`, `action_sign_flip` | stats action của episode | có |
| `corrupted_success_label` | stats action và state | có. Bản trước cắt episode nên số dòng nhỏ hơn số khung video, điều mà một episode dừng sớm thật không có; nay robot dừng tại chỗ, số khung giữ nguyên |
| `wrong_task_instruction` | thêm một dòng trong `tasks.jsonl`, `total_tasks` tăng | có |
| `duplicate_episode` | parquet, video, stats và `environment_config` giống episode nguồn | có; trước đây `environment_config` còn là của chỗ bị ghi đè, nay chép theo nguồn |
| `holdout_seed_leak` | seed của episode nằm trong dải holdout thay vì train | có. Trước đây chỉ 3 dòng có khối `flywheel` (psi-data không ghi seed); nay mọi episode của cả hai bản có seed dàn dựng (xem dưới), nên chỉ giá trị seed khác |

**Seed dàn dựng của bản sao [Đã chốt 4/11/2026, Hiếu].** psi-data không ghi seed điều kiện. Mỗi episode của cả hai bản sao có khối `environment_config.flywheel = {"seed": …}`: seed lấy tất định từ dải train của `configs/splits/default.yaml` (0–999.999), theo `scaffold_seed(seed cấu hình, episode)`, nên một episode có cùng seed ở hai bản; 3 episode `holdout_seed_leak` thay bằng seed dải holdout. Đây là dàn dựng của benchmark, **không phải dữ liệu của tác giả**; `meta/benchmark_copy.json` của cả hai bản ghi điều này ở khóa `scaffolding`. Nguồn nào đã ghi seed thì giữ seed của nguồn.

Mọi lỗi trên action và state còn lệch với video (video quay lần chạy gốc); đó là giới hạn chung của cấy lỗi vào dữ liệu đã ghi, chỉ phát lại hoặc nhìn ảnh mới thấy.

### Dựng hai bản sao và niêm phong

```bash
uv run python -m flywheel.data.inject.build --source <gốc LeRobot> --out fwdata/inject \
    --layout configs/embodiments/g1.yaml --config configs/data/inject.yaml
```

Lệnh ghi `copies/<id>/` (bản cấy và bản sạch, id trung tính từ `copy_ids(seed)`), `answers/<id>/defect_manifest.json` và `.sha256` (chỉ bộ chấm đọc), `ledger.jsonl` (một dòng ước tính, một dòng thực đo trỏ về dòng ước tính), rồi in `DatasetRef`, đường dẫn và hash manifest của từng bản cho DA-31. Bản sạch chép từ bản gốc qua cùng đường ghi như bản cấy, nên hai bản chỉ khác nhau ở lỗi. Ingest một bản sao gọi `flywheel.data.inject.api.mark_copy_episode` để mọi `Episode` mang `benchmark_copy_id`. `ledger.jsonl` chưa ghi vào sổ của store vì `flywheel-data` chưa khai phụ thuộc `flywheel-store` (`pyproject.toml` thuộc DA-03).

### Chạy trên psi-data thật (4/11/2026)

Nguồn: gói hai bàn `simple/G1WholebodyLocomotionPickBetweenTablesTeleop-v0.zip` của `USC-PSI-Lab/psi-data` @ `e78fb93`, bản S1-07 đã tải (`rtx3060:~/denso-s107/fwdata/psi-data/e78fb93/`, sha256 zip `6cdf9022…927586`, khớp `lfs.oid` của HF), giải nén vào `rtx3060:~/denso-da27/fwdata/psi-data/e78fb93/`: 99 episode, 62.764 khung, 207 file. Mã ở nhánh `DA-27-defect-inject` (`5f8d6bd`, sau khi sửa stats, lineage, kênh phụ và seed dàn dựng), chép sang `~/denso-da27`; các lần chạy trước ở `fwdata/inject-superseded-{1,2,3,4}/`, không dùng; bản chạy đầu (`59793bd`, stats chép từ bản gốc, lineage nằm trong bản sao) giữ ở `fwdata/inject-superseded-1/`, không dùng.

```bash
cd ~/denso-da27
nohup setsid systemd-run --user --scope -p MemoryMax=8G -p MemorySwapMax=0 \
  /usr/bin/time -v .venv/bin/python -m flywheel.data.inject.build \
  --source fwdata/psi-data/e78fb93/G1WholebodyLocomotionPickBetweenTablesTeleop-v0 \
  --out fwdata/inject --layout configs/embodiments/g1.yaml --config configs/data/inject.yaml \
  > fwdata/inject-run.log 2>&1 < /dev/null &
```

Kết quả lần chạy 4/11/2026 (đo, một tiến trình CPU, máy đang chạy job khác với load khoảng 50):

| Mục | Giá trị |
|---|---|
| Thời gian | 24,1 s wall; `LedgerEntry` ước tính 125,5 s (giả định 1 ms/khung/bản), thực đo 23,26 s |
| RAM đỉnh | 642 MB (`Maximum resident set size` 657.740 kB) |
| Bản gốc | hash cây trước và sau bằng nhau (`35984186…958ce9`) |
| Hai bản sao | `fwdata/inject/copies/bench-1e258c0a78ca` (sha256 cây `62f48eaf…2b186904`), `fwdata/inject/copies/bench-d19e112835e3` (sha256 cây `3a5630f7…5f56a786f`), mỗi bản 99 episode, cùng 208 file, cùng một mtime |
| Đáp án | `fwdata/inject/answers/<id>/defect_manifest.json` và `.sha256`; sha256 `8962a6cf…ea13a72` (`bench-1e258c0a78ca`, không đổi), `e41e8d49…0081820f` (`bench-d19e112835e3`) |

Kiểm lại từ đĩa (`fwdata/verify_inject.py`, đọc bằng bộ đọc của DA-03): một bản có 33 lỗi, đủ 11 loại × 3 (D1 3, D2 6, D3 9, D5 6, D6 6, D7 3), mỗi dòng manifest qua `defect_applied`; 66 episode không cấy và cả 99 episode của bản kia trùng bản gốc; `joint_limit_exceeded` vượt đúng `limit_high` của `g1.yaml` (ví dụ `left_elbow_joint` 2,0944 → 2,8798, `waist_pitch_joint` 0,52 → 0,78); `unit_deg_rad` trên chiều góc (15, 16, 30); `action_sign_flip` trên chiều có độ lệch chuẩn khác 0 (19, 24); seed rò 2000124, 2000587, 2000692; `drop_frames` bỏ 90–93 dòng.

Kiểm đối xứng (cùng script): mọi episode của hai bản có khối `flywheel` với seed dàn dựng, 3 episode rò mang 2000587, 2000692, 2000124, 66 episode không cấy cùng khối ở hai bản; footer parquet một biến thể trên 198 file; 99/99 video mỗi bản đi qua nguyên vẹn (bản trùng mang video của episode nguồn); chỉ 3 episode `drop_frames` có ít dòng hơn số khung video; `corrupted_success_label` dừng robot từ khung 279/559, 291/583, 353/707; 66 episode không cấy có stats từng episode giống hệt nhau ở hai bản; ở cả hai bản, `episodes_stats.jsonl`, `stats.json`, `stats_psi0.json` bằng stats tính lại từ dữ liệu đọc ngược; không bản nào có `meta/flywheel_lineage.jsonl` (95 và 98 dòng lineage nằm ở `answers/<id>/`); ngoài `meta/benchmark_copy.json`, không file nào chứa `inject`, `defect`, `duplicate`, `bench` nhiều hơn file cùng đường dẫn ở bản gốc (`allow_duplicates` có sẵn trong `environment_config` của psi-data, 99 lần ở cả ba).

Bàn giao cho DA-31 (Châu), in ra từ lệnh trên, đường dẫn tính từ `rtx3060:~/denso-da27/`; sha256 cây của bản sao (sha256 của danh sách `sha256  đường dẫn` đã sắp xếp) ở bảng trên:

```json
{
  "copies": [
    {"dataset_id": "bench-1e258c0a78ca", "uri": "fwdata/inject/copies/bench-1e258c0a78ca",
     "manifest": "fwdata/inject/answers/bench-1e258c0a78ca/defect_manifest.json",
     "manifest_sha256": "8962a6cf8281963fb190c570a6104bd51a543acfbf0d4209e4668e305ea13a72"},
    {"dataset_id": "bench-d19e112835e3", "uri": "fwdata/inject/copies/bench-d19e112835e3",
     "manifest": "fwdata/inject/answers/bench-d19e112835e3/defect_manifest.json",
     "manifest_sha256": "e41e8d49467c5ee30365c9c5993069195d6e41cf5ceae88b509de9bc0081820f"}
  ],
  "ledger": "fwdata/inject/ledger.jsonl"
}
```

Bộ chấm biết bản nào sạch qua manifest (`defects` rỗng); agent chỉ nhận `dataset_id` và `uri`. Mỗi lượt chạy agent nhận đúng một `DatasetRef`, gắn chỉ đọc, không kèm đường tới bản gốc, bản sao kia hay `answers/` (quy tắc chạy ở dưới). Đường dẫn khác plan 3/11 (`fwdata/inject/<dataset_id>/{injected,clean}`) vì tên `injected`, `clean` lộ vai trò.

Còn lại:

- **Quy tắc chạy [Đã chốt 4/11/2026, Hiếu]:** mỗi lượt chạy Agent QA/QC (DA-20) và mỗi lượt QA của DA-31 gắn đúng một bản sao, chỉ đọc; không có đường tới psi-data gốc, tới bản sao kia, hay tới `answers/`. So hai bản với nhau, hoặc với bản gốc, là thấy hết lỗi; đọc `answers/` là thấy đáp án.
- `ledger.jsonl` chưa vào sổ của store: cần thêm `"flywheel-store"` vào `dependencies` của `packages/flywheel-data/pyproject.toml` (và `uv lock`), thuộc DA-03; Hiếu quyết.

---

## 3. Lỗi log huấn luyện (F-TRAIN) và log RTC (F-SYS)

Log train cấy lỗi T1–T8 và log RTC cấy lỗi R1, R2 (nhiệm vụ 2 của story) chuyển sang PR sau `DA-27-log-defects`, để PR này dưới ngưỡng R9 (quyết định PO 4/11/2026). Mã của Thông giữ nguyên trong lịch sử nhánh này và sẽ được cherry-pick, giữ tác giả.

---

## 4. Kiểm thử và Nghiệm thu

* **Unit tests:** 92 test case tự động (một test chỉ chạy khi có `DA27_PSI_DATA`); chạy thật trên psi-data ở trên tại `packages/flywheel-data/tests/unit/inject/`.
* **Độ bao phủ:** 100% các loại lỗi cấy đều có test kiểm chứng.
* **Độc lập kiến trúc:** Không import vòng, tuân thủ nghiêm ngặt 3 hợp đồng kiến trúc của repo.
