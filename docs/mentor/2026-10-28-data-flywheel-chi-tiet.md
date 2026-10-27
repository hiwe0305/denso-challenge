# Data flywheel · Chi tiết pipeline, hệ thống và kiến trúc

_Tài liệu đi kèm [tổng quan hệ thống](2026-10-28-tong-quan-he-thong.md), viết ngày 27/10/2026 cho buổi với mentor ngày 28/10/2026. Đi sâu vào từng pipeline, từng thành phần và kiến trúc của data flywheel theo spec v10.4, design ngày 27/10/2026 và 03 · Kiến trúc bản 0.7. Chưa nói tiến độ code. Lệnh `fw` ghi **[Đề xuất]** là tên người viết đề xuất, chưa có trong 03; các lệnh khác đã có trong 03 hoặc PRD. Mọi con số chưa đo là giả định hoặc ước lượng._

---

## 0. Bản đồ của tài liệu

Data flywheel gồm bốn lớp. Lớp dưới không biết lớp trên; lớp trên chỉ đọc artifact của lớp dưới.

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ 4 · VÒNG QUYẾT ĐỊNH    RunPlan · runner · decide · acquisition · gate ·      │  mục 6
│                        holdout · sổ chi phí · báo cáo · HD                    │
├──────────────────────────────────────────────────────────────────────────────┤
│ 3 · ĐÁNH GIÁ           tập điều kiện · scorer · chẩn đoán · evidence card ·   │  mục 5
│                        probe · Agent QA/QC · bộ chấm lỗi cấy                  │
├──────────────────────────────────────────────────────────────────────────────┤
│ 2 · MODEL (adapter)    Ψ₀ stage 1 / 3 · ACT · DP · serve · RTC · model phụ trợ│  mục 4
├──────────────────────────────────────────────────────────────────────────────┤
│ 1 · DỮ LIỆU            egocentric · teleop · synthetic → 6 tầng → release →   │  mục 3
│                        export; bộ lỗi cấy                                    │
├──────────────────────────────────────────────────────────────────────────────┤
│ 0 · NHÂN               contracts (schema, 6 Protocol) · store (kho, catalog,  │  mục 2
│                        vault) · testkit (bộ giả, file mẫu) · cli (fw)        │
└──────────────────────────────────────────────────────────────────────────────┘
        Hạ tầng chạy (máy, container, Colab, LLM cục bộ): mục 7 · Kiến trúc phần mềm: mục 8
```

---

## 1. Luồng đầu cuối

Một lượt đi trọn của dữ liệu, ghi artifact trên từng mũi tên:

```text
 NGUỒN                      LÀN DỮ LIỆU                          ADAPTER Ψ₀
 ─────                      ───────────                          ──────────
 EgoDex ─┐                  ┌ Ingest ──► Source, bundle thô
 video   ├─ egocentric ────►│ Normalize ─► bundle chuẩn
 tự quay ┘                  │ Annotate ──► segments, deid_status
                            │ QA ────────► QAReport, ReplayReport ──┐
 psi-data ┐                 │ Release ───► ReleaseManifest (FROZEN) │
 bàn phím ├─ teleop ───────►│ Export ────► DatasetRef ──────────────┼──► stage 1 (egocentric)
          ┘                 └────────────────────────────────────── │──► stage 3 (teleop, synthetic)
 S1 planner ┐                                                       │        │
 S2 biến thể├─ synthetic ──► (cùng 6 tầng)                          │        ▼ Checkpoint, metrics.jsonl
            ┘                                                       │
                                                                    │   LÀN VÒNG: runner
                                                                    │        │ RolloutRequest ──► SimpleSim
                                                                    │        ▼ Trace, RolloutResult
                                    LÀN ĐÁNH GIÁ                    │
                                    scorer ──► Score                │
                                    diagnosis ──► Cluster, EvidenceCard
                                    Agent QA/QC ◄── DatasetReport, ReplayReport, metrics, log RTC
                                         │ QAReport (báo cáo agent)
                                         ▼
                                    LÀN VÒNG: decide ──► đề xuất (g/c) ──► fw review ──► Decision
                                         │
                                         ▼
                                    acquisition ──► GenerationRequest (S1, S2), TeleopRequest (correction)
                                         │
                                         └──────────► quay lại NGUỒN, thành episode mới, đi lại 6 tầng
                                    gate ──► cổng dev, FixRateEvent ──► cập nhật tỉ lệ sửa được
                                    ledger ◄── LedgerEntry từ MỌI job
```

Hai vòng chạy song song:

- **Vòng dữ liệu** (mục 3): đưa dữ liệu từ nguồn bất kỳ thành release có lineage. Chạy được một mình, không cần model.
- **Vòng quyết định** (mục 6): từ thất bại của policy ra kế hoạch thu dữ liệu, rồi đo lại xem kế hoạch có sửa được lỗi không. Dùng vòng dữ liệu để nạp phần thu mới.

---

## 2. Nhân: lưu trữ, mô hình dữ liệu, hợp đồng

### 2.1 Bố cục lưu trữ

```text
$FW_ROOT/                         # mặc định ./fwdata (gitignore); đĩa cục bộ ở L0
  sites/local/
    sources/<source_id>/          # tệp tải về nguyên vẹn, SOURCE.json kèm provenance
    objects/sha256/ab/cd/<hash>   # blob bất biến: mp4, parquet, layout, snapshot
    episodes/<episode_id>/        # meta.json, frames.parquet, signals.parquet, segments.parquet, videos/
    catalog/<bảng>/part-<ulid>.jsonl   # 12 bảng append-only
    releases/<release_id>/        # manifest.json, items.parquet, FROZEN
    exports/<release_id>/<format>-<mix_hash>/   # LeRobot v2.1, v3, định dạng stage 1; dựng lại được
    plans/<run_plan_id>/          # runplan.yaml, runplan.lock.json
    runs/<run_plan_id>/<job_id>/  # job.json, result.json, logs.jsonl, ledger.jsonl, metrics.jsonl
    rounds/<run_plan_id>/         # plan.json (can thiệp), cards/<cluster_id>.html
    checkpoints/<checkpoint_id>/  # CHECKPOINT.json, trọng số hoặc URI ngoài
    refs/                         # con trỏ đổi được, kèm refs.log
    vault/holdout/                # conditions.parquet, locks/, sealed/
    hd/                           # phân công và phiên của thí nghiệm HD
  index/fw.duckdb                 # chỉ chứa view; xóa thì tự tạo lại
```

Nguyên tắc:

- **Blob bất biến theo sha256**; mọi thứ khác trỏ tới blob bằng hash.
- **Catalog là JSONL append-only**: mỗi tiến trình ghi tệp `part-<ulid>.jsonl` riêng nên không tranh khóa. Sửa sai bằng bản ghi mới, không xóa.
- **DuckDB chỉ chứa view** trên glob của catalog; mất tệp index không mất dữ liệu.
- **Không có DB server, MLflow hay Streamlit ở L0** (03 mục 2.4); báo cáo là HTML tĩnh.

### 2.2 Mười hai thực thể catalog

| Thực thể | Là gì | Ai ghi |
|---|---|---|
| Source | Một nguồn tải về: URL, revision, sha256, giấy phép, provenance | Làn Dữ liệu (ingest), adapter Ψ₀ (checkpoint gốc) |
| Condition | Một điều kiện môi trường: hạt giống, mức, vector c, `layout_hash`, tập (train, dev) | Làn Đánh giá (scenarios) |
| Episode | Một episode bất kỳ: demo, correction, rollout sim, biến thể, rollout eval, rollout chẩn đoán, đoạn egocentric | Làn Dữ liệu, runner |
| QAReport | Kết quả QA của một episode: pass, flag, quarantine, reject kèm lý do và giá trị từng phép kiểm | Làn Dữ liệu |
| Release | Một bộ episode đóng băng: manifest, cha, SplitPlan, giấy phép gộp | Làn Dữ liệu |
| Checkpoint | Một bộ trọng số: phương pháp, nhánh, cha, release, seed | Adapter Ψ₀, LeRobot |
| RunPlan | Kế hoạch chạy đóng băng (mục 6.1) | Làn Vòng |
| Score | Kết quả scorer trên một trace: trạng thái 6 bước, bước hỏng k, kiểu lỗi | Làn Đánh giá |
| Cluster | Một cụm lỗi: thành viên, đại diện, kết quả từng phép kiểm, chẩn đoán, đề xuất | Làn Đánh giá |
| FixRateEvent | Một lần đo tỉ lệ sửa được của một can thiệp | Làn Vòng (gate) |
| LedgerEntry | Một mục sổ chi phí | Mọi job |
| Decision | Một quyết định có chữ ký: duyệt kế hoạch, cổng dev, holdout, mốc, phiếu sửa hệ thống | Làn Vòng, kỹ sư |

### 2.3 Episode bundle

Một thư mục cho mỗi episode, dùng chung cho cả ba loại dữ liệu:

| Tệp | Nội dung |
|---|---|
| `meta.json` | ID, `source_kind` (egocentric, teleop, synthetic), `source_detail` (`egodex`, `ego_video`, `psi_data`, `teleop_keyboard`, `planner_wbc`, `planner_amo`, `variant`), `action_quality` (measured, planned, retargeted, pseudo, none), `embodiment_id`, `renderer`, `deid_status`, `synthetic_tier`, `condition_id`, cha và gốc, giấy phép, `data_class`; tham số camera và `camera_params_hash` |
| `frames.parquet` | Mỗi dòng một chu kỳ điều khiển: `t_state`, state và action theo nhóm của `action_layout`, mỗi nhóm có cột `_cmd` (lệnh gửi) và `_meas` (đo được); với egocentric: khớp tay 3D và tư thế camera |
| `signals.parquet` | Tín hiệu cho scorer: tư thế vật, tiếp xúc tay–vật, tư thế thân, va chạm |
| `segments.parquet` | Mỗi dòng một đoạn: `t_start`, `t_end`, `step_id` (bước của task), câu lệnh, nguồn nhãn (rule, human, model) |
| `videos/<camera>.mp4` | Video theo camera; `t_image` từng khung ghi trong `frames.parquet` hoặc tệp riêng |

`action_layout` của G1 xếp các nhóm action vào khung 36 chiều của Ψ₀ (`pad36`), kèm mask cho chiều đệm để loss bỏ qua.

### 2.4 Đồ thị lineage

```text
Source ──► Episode gốc (is_root) ──► Episode biến thể (parent_id, root_id)
   │             │
   │             └──► QAReport ──► Release (manifest, FROZEN) ──► Export (DatasetRef)
   │                                    │
Source (checkpoint gốc, provenance)     ▼
   └────────────────────────────────► Checkpoint (release_id, parent_checkpoint_id)
                                            │
                                            ▼  rollout
                                   Episode eval_rollout ──► Score ──► Cluster ──► Decision (plan_review)
                                                                                     │ intervention_id
                                                                                     ▼
                                                                Episode mới (sim_rollout, variant, correction)
```

Từ bất kỳ con số nào trong báo cáo đều truy ngược được tới Source, RunPlan và commit mã đã tạo ra nó.

### 2.5 Sáu Protocol

| Protocol | Hàm chính | Hiện thực ở L0 |
|---|---|---|
| SimulatorAdapter | `capabilities`, `control_spec`, `materialize_conditions`, `rollout`, `replay`, `snapshot` | `SimpleSim` |
| PolicyAdapter | `describe`, `serve` | `Psi0Policy`, `LeRobotPolicy` (ACT, DP) |
| TrainerAdapter | `export_dataset`, `estimate`, `train` | `Psi0Trainer`, `LeRobotTrainer` |
| GeneratorAdapter | `capabilities`, `plan`, `estimate`, `generate` | `WbcPlannerGenerator` hoặc `SimpleMPGenerator` (S1), `TeleopVariantGenerator` (S2) |
| TeleopSource | `operator_kind`, `request`, `collect` | `PsiDataSource`, `KeyboardTeleop` |
| TaskDefinition | `stages`, `failure_kinds`, `condition_schema`, `required_signals`, `evaluate` | `G1LocomotionPickBetweenTables`, `G1BendPick` (F1) |

Nguồn egocentric (`EgoDexSource`, `EgoVideoSource`) không phải Protocol vì không chạy sim; chúng là bộ đọc trong làn Dữ liệu.

Mọi adapter phải khai **năng lực trung thực** (`capabilities`): ví dụ `restore_state` chỉ được `True` khi khôi phục giữa episode thật sự đúng. Phép kiểm cần năng lực không có thì ghi `skipped` kèm lý do.

---

## 3. Lớp dữ liệu: các pipeline

### 3.1 Khung chung: sáu tầng

| Tầng | Vào | Ra | Quy tắc |
|---|---|---|---|
| 1 · Ingest | Tệp thô hoặc kết quả generator | Source, bundle thô | sha256 mọi tệp; ghi giấy phép và `data_class`; không sửa tệp gốc |
| 2 · Normalize | Bundle thô | Bundle chuẩn | Đồng hồ chung; SI, radian; khung theo URDF; ánh xạ vào `action_layout` |
| 3 · Annotate | Bundle chuẩn | `segments.parquet`, `deid_status` | Egocentric che danh tính trước mọi bước; cắt đoạn theo 6 bước của task |
| 4 · QA | Bundle đã gắn nhãn | QAReport, ReplayReport | 7 phép kiểm chung, phép kiểm riêng từng loại, phát lại action với dữ liệu robot |
| 5 · Release | Episode đã qua QA | ReleaseManifest (FROZEN) | Guard chia tập, gần trùng, giấy phép gộp; bất biến sau khi đóng băng |
| 6 · Export | Release | DatasetRef | Định dạng đúng loader của model; stats tính trên đúng release; contract test |

Mỗi tầng ghi một `LedgerEntry` (giây tường, GPU-giây, phút người nếu có). Mẫu bị loại vẫn giữ cùng lý do và chi phí.

**Bảy phép kiểm QA chung** (ngưỡng hiệu chỉnh từ episode teleop thành công, không đoán trước):

| # | Phép kiểm | Ngưỡng | Khi trượt |
|---|---|---|---|
| 1 | Timestamp đơn điệu, bước đều | Lệch ≤ 1 chu kỳ điều khiển | Loại |
| 2 | Đồng bộ ảnh và state | Lệch ≤ 1 khung | Sửa, không được thì loại |
| 3 | Giới hạn khớp, giá trị hữu hạn | Theo URDF; không NaN, Inf | Loại |
| 4 | Bước nhảy action | ≤ phân vị 99,9 của demo teleop | Đánh dấu cho kỹ sư |
| 5 | Kết quả task | Scorer báo thành công | Không làm mẫu dương; giữ làm bằng chứng lỗi |
| 6 | Lineage | Đủ nguồn, giấy phép, cha, hạt giống, phiên bản bộ sinh | Cách ly |
| 7 | Chia tập | Hạt giống thuộc dải train | Vô hiệu hóa release |

Ngưỡng ghi trong `configs/` có hash; release ghi phiên bản ngưỡng nó dùng.

### 3.2 Pipeline egocentric

```text
EgoDex (E-B) ─┐
              ├─► Ingest ─► Che danh tính ─► Cắt đoạn ─► Pose tay, camera ─► QA riêng ─► Release ─► Export stage 1
video tự quay ┘   (sha256)   (deid_status)    (6 bước,     (E-B đọc,           (độ tin    (đoạn      (khớp tay kiểu
(E-A)                                          câu lệnh)    E-A ước lượng)      pose)      egocentric) EgoDex + mp4)
```

| Bước | Chi tiết |
|---|---|
| Ingest | EgoDex: một tập con ghim (task gần gắp và đặt). Video tự quay: video kèm thông tin thiết bị, người quay (mã giả danh), ngày |
| Che danh tính | Mặt, thẻ tên, màn hình. Bắt buộc trước mọi bước khác. `deid_status`: `raw` → `blurred` → `verified` (người kiểm mẫu). Catalog chặn episode `raw` rời tầng Annotate |
| Cắt đoạn | Theo 6 bước của task hai bàn (với video tự quay) hoặc đoạn gắp và đặt (với EgoDex). Luật trước (vận tốc tay, tay chạm vật); model gợi ý khi luật mơ hồ; người duyệt một phần mẫu |
| Pose | E-B: đọc biến đổi khớp tay và tư thế đầu từ EgoDex. E-A: ước lượng bằng model hand pose và SLAM chạy cục bộ, gắn `pseudo` |
| QA riêng | Độ tin pose; tỉ lệ khung mất tay; độ rung; so E-A với E-B trên cùng mẫu EgoDex (bỏ tracking) để biết pose ước lượng lệch bao nhiêu |
| Export | Đúng định dạng mà `egodex_dataset.py` của Ψ₀ đọc: biến đổi khớp tay cộng mp4, `chunk_size`, `upsample_rate`, delta action như config gốc, action 48 chiều theo tiền xử lý H-RDT; stats theo `calc_egodex_stats.py`; contract test đọc lại bằng loader |

Quy tắc: episode egocentric có `action_quality` là `retargeted` (EgoDex) hoặc `pseudo` (tự quay), không có action robot, nên **không bao giờ vào stage 3**. Chúng vào stage 1, probe P1 và P2, và làm mẫu cho bộ sinh.

### 3.3 Pipeline teleop

```text
psi-data (LeRobot v2.1) ─┐
                         ├─► Ingest ─► Normalize ─► Cắt đoạn ─► QA + phát lại ─► Release ─► Export LeRobot v2.1 (+v3)
bàn phím (bản ghi SIMPLE)┘
```

| Bước | Chi tiết |
|---|---|
| Ingest | psi-data: tải gói task hai bàn ở revision ghim; tách LeRobot thành từng bundle; gán `embodiment_id = g1_sonic_dwbc@1`. Bàn phím: đọc bản ghi `--record` của SIMPLE, kèm người điều khiển, hạt giống điều kiện, kết quả người bấm |
| Điều kiện | Trích vector điều kiện từ layout (`state_dict` của SIMPLE) hoặc suy ra từ khung đầu nếu không có hạt giống; gán tập train theo SplitPlan |
| Normalize | Đồng bộ mọi luồng; nội suy state về tần số điều khiển; ánh xạ khớp vào `action_layout` đệm 36 chiều; ảnh về kích thước của config fine-tune Ψ₀, giữ bản gốc |
| Cắt đoạn | Luật: bàn tay đóng (bắt đầu gắp), vận tốc thân khác 0 (bắt đầu đi), thân dừng gần bàn đích, bàn tay mở (nhả) |
| QA riêng | psi-data: số khung video khớp số dòng, mọi episode có câu lệnh. Bàn phím: khoảng dừng dài khi người buông phím, bước nhảy lệnh cổ tay, episode người bấm "thành công" mà scorer chấm hỏng |
| Phát lại | Động học (đặt `qpos` từng khung): bắt sai ánh xạ khớp, sai đơn vị, vượt giới hạn, ảnh lệch state; trượt thì loại. Động lực học (áp action qua WBC từ state đầu): bắt sai tần số, delta hay tuyệt đối, sai dấu, lệch thời điểm bàn tay; vượt phân vị 99 thì đánh dấu |
| Export | LeRobot v2.1 đúng fork của Ψ₀; `stats_psi0.json` trên đúng release; checklist 7 mục (mục 3.6); bản v3 chuyển từ v2.1 bằng script chính thức của LeRobot |

Mỗi phiên teleop bàn phím ghi một `LedgerEntry`: phút người, số episode, số episode đạt.

### 3.4 Pipeline synthetic

```text
            ┌── S1 · Planner (tuyến A: WBC, tuyến B: AMO) ──┐
decide ─────┤                                                ├─► rollout lại trong sim ─► Ingest ─► ... ─► Release
hoặc lô     └── S2 · Biến thể từ đoạn teleop, correction ───┘   (chỉ nhận lượt đạt;
sinh sẵn                                                          lượt hỏng vẫn ghi)
```

| Phần | S1 · Planner | S2 · Biến thể từ teleop |
|---|---|---|
| Đầu vào | Điều kiện ngẫu nhiên trong miền train, hoặc quanh điều kiện lỗi (khi `decide` yêu cầu) | Đoạn teleop đạt QA đã cắt theo bước; hoặc trạng thái lỗi đã lưu của policy |
| Cách sinh | Tuyến A: script đi bộ (lệnh vận tốc tới WBC) cộng cuRobo cho hai tay trong env Teleop. Tuyến B: task MP mới chạy `datagen` của SIMPLE (AMO). Chọn bằng V3 | Đoạn gần vật biến đổi theo tư thế vật và vị trí bàn mới (kiểu MimicGen); đoạn đi bộ sinh lại; nối bằng IK. Correction: planner từ trạng thái lỗi tới hết bước k |
| Bộ điều khiển | A: WBC; B: AMO | WBC |
| Kiểm trước khi nhận | Rollout lại đạt `check_success`; tỉ lệ sinh đạt | Như S1, cộng khoảng cách điều kiện tới demo gốc |
| `meta` | `synthetic_tier = S1`, tuyến, phiên bản planner | `synthetic_tier = S2`, episode cha, tham số biến đổi |
| Đếm là demo gốc | Không | Không; luôn trỏ về episode cha |

Quy tắc chung của synthetic:

- Không sinh bằng tham số của Level 1, Level 2, và không sinh trong bán kính d_dup quanh holdout (chống rò).
- Episode tuyến B (AMO) có `embodiment_id` khác, không trộn với teleop trong một release khi chưa có ánh xạ (ADR-08).
- Mỗi tầng là một loại can thiệp riêng trong `decide`, có đơn giá và tỉ lệ sửa được f_t riêng; nhờ vậy flywheel tự học tầng nào đáng tiền.
- S3 (Cosmos Transfer, đổi ngoại hình, giữ action) và S4 (Cosmos Predict, video task mới, action suy ra) để sau demo, qua `NimClient` có định tuyến theo `data_class`.

### 3.5 Release, chia tập và trộn

**SplitPlan** đóng băng trước lần train đầu:

| Tập | Kích thước | Ai dùng |
|---|---|---|
| Train | Điều kiện của demo và vùng được phép sinh | Mọi nhánh |
| Dev | 90 điều kiện (30 mỗi mức) cho tìm lỗi; tập cổng mới mỗi vòng và điều kiện đo tỉ lệ sửa được lấy từ phần dev chưa dùng | E1, HE, nhánh C, B-fail, chọn ρ |
| Holdout | 150 điều kiện (50 mỗi mức), trong `vault/` | Chỉ `gate`, một lần mỗi cặp nhánh và seed |

**Guard khi đóng băng release:** episode train có hạt giống thuộc dải dev hoặc holdout, hoặc `layout_hash` trùng, hoặc khoảng cách điều kiện dưới d_dup (phân vị 1 khoảng cách láng giềng gần nhất trong train) so với holdout, thì release không đóng băng được. Bản sao có `injected_defect` không bao giờ vào release train.

**Trộn khi export:** tỉ lệ synthetic trong batch ρ chọn trong {0,25; 0,5} trên dev bằng nhánh B, rồi áp nguyên cho các nhánh khác; mỗi tổ hợp release và tỉ lệ trộn có `mix_hash` riêng.

### 3.6 Export và checklist chuẩn hóa

| Đích | Dùng cho | Contract test |
|---|---|---|
| LeRobot v2.1 (fork `songlin/lerobot@09929d8`) | Ψ₀ stage 3 | Loader Ψ₀ ở commit ghim đọc ra đúng một batch mẫu đã lưu |
| LeRobot v3 | ACT, DP, công cụ mới | `lerobot` bản mới đọc lại được |
| Định dạng stage 1 (kiểu EgoDex) | Ψ₀ stage 1 | Loader stage 1 của Ψ₀ đọc lại được |

Checklist 7 mục cho LeRobot, chạy tự động: `info.json` khớp `action_layout` (tên và shape từng chiều); `episode_index`, `index` liên tục, `frame_index` từ 0; `timestamp` khớp `frame_index / fps`; video giải mã được, đủ khung, đúng codec và độ phân giải; mọi episode có câu lệnh; stats đúng release, không NaN, chiều đệm có mask; đọc lại bằng loader ra đúng batch mẫu.

### 3.7 Báo cáo dataset

Một trang HTML tĩnh cho mỗi release, cũng là đầu vào của Agent QA/QC:

- Số episode theo loại dữ liệu và theo nguồn; pass, flag, quarantine, reject theo từng phép kiểm.
- Phân bố điều kiện so với dải train; độ dài episode; stats theo nhóm action.
- Egocentric: độ tin pose, độ lệch E-A so với E-B.
- Synthetic: tỉ lệ sinh đạt theo tầng và tuyến, chi phí mỗi mẫu.
- Vài video phát lại đặt cạnh video gốc.

### 3.8 Bộ lỗi cấy

Bộ lỗi cấy là một nhánh phụ của lớp dữ liệu, dùng để đo QA và Agent QA/QC:

```text
release thật ──► bản sao ──► cấy lỗi theo cấu hình (tỉ lệ 5–10% mỗi loại, hạt giống ghi lại) ──► chạy QA và agent
                                    │
                                    └──► DefectManifest (đáp án, hash khóa trước; agent không đọc được)
                                                     │
                                         bộ chấm (làn Đánh giá) ◄── kết quả QA, báo cáo agent
                                                     ▼
                                 precision, recall theo loại · báo nhầm trên bản sạch · thời gian
```

| Nhóm | Lỗi cấy | Mã lỗi |
|---|---|---|
| Dữ liệu | Rơi khung ảnh; lệch thời gian ảnh và state; nhảy khớp; vượt giới hạn; NaN; sai đơn vị; đảo dấu một chiều action; episode hỏng gắn nhãn thành công; sai câu lệnh; trùng episode; rò hạt giống holdout | D1–D8 |
| Log train | Phân kỳ; không học; quá khớp; nhóm action không học; chiều chết; gradient VLM khác 0 khi đóng băng | T1–T8 |
| Log inference | Độ trễ p99 vượt ngưỡng; buffer cạn; giật ở ranh giới chunk | R1, R2 |

---

## 4. Lớp model: pipeline train, probe và suy luận

### 4.1 Ba stage của Ψ₀ và dữ liệu vào từng stage

| Stage | Thành phần | Code của tác giả | Dữ liệu vào | Đội làm gì |
|---|---|---|---|---|
| 1 | VLM Qwen3-VL-2B | `pretrain-egodex-psi0-fast.sh`, `trainers/pretrain.py` | Egocentric (định dạng stage 1) | Không pretrain lại. Chạy ngắn trên EgoDex do pipeline xuất ra để chứng minh đường đi; fine-tune từ `pre.*` trên video tự quay khi còn thời gian |
| 2 | Action expert | `posttrain-*-psi0.sh`, `trainers/posttrain.py` | Humanoid Everyday | Không train; dùng `postpre.*` của tác giả |
| 3 | Cả model theo task | `finetune-simple-psi0.sh`, `trainers/finetune.py` | Teleop, synthetic (LeRobot v2.1) | Fine-tune ở mọi điểm của E1, HE và các nhánh |
| Baseline | ACT, Diffusion Policy | `baselines/act`, `baselines/dp` | Như stage 3 | So sánh phương pháp; chạy F-ACT |

### 4.2 Một job train

```text
RunPlan (đóng băng) ──► training dựng TrainSpec (release, mix, recipe chung, checkpoint cha, seed)
                         │
                         ▼
             TrainerAdapter.export_dataset ──► DatasetRef
             TrainerAdapter.estimate      ──► ResourceEstimate (ghi "ước tính")
             TrainerAdapter.train         ──► gọi script của tác giả trong container hoặc trên Colab
                         │                      (commit Ψ₀ ghim, tiếp tục được từ checkpoint)
                         ▼
             lớp bọc log ──► metrics.jsonl (nguồn sự thật) + W&B offline
                         ▼
             Checkpoint ứng viên, LedgerEntry ("thực đo": GPU-giờ, compute unit)
```

**Log phải có** (một phần có sẵn trong code tác giả, phần còn lại do lớp bọc tính lại trên batch val, không sửa code gốc):

| Nhóm | Có sẵn | Lớp bọc thêm |
|---|---|---|
| Loss tổng, learning rate, epoch, eval loss | Có | |
| Chuẩn gradient theo khối | Có | |
| Loss theo nhóm action, theo vị trí trong chunk | | Có |
| Phương sai action dự đoán, phân bố độ mở bàn tay | | Có |
| VRAM, thông lượng, GPU-giờ | Một phần | Đo từ adapter |
| Probe trên checkpoint trung gian | | Chạy sau mỗi lần lưu |

### 4.3 Probe theo stage

| Probe | Trên | Đo gì | Dùng để |
|---|---|---|---|
| P1 · Hiểu cảnh | VLM | Hỏi đáp có đáp án về vật, bàn, bước đang làm trên khung hình SIMPLE | Quy lỗi về stage 1; bằng chứng phụ cho HE |
| P2 · Token action | VLM | Loss token FAST trên egocentric giữ lại | Đo stage 1 trước và sau fine-tune |
| P3 · Action offline | Checkpoint stage 3 | Sai số action theo nhóm và vị trí trong chunk trên episode giữ lại | Quy lỗi về stage 3 |
| P4 · Giữ năng lực | Sau fine-tune | P1, P3 trên dữ liệu gốc | Phát hiện quên |

Bộ probe đóng băng có hash trước khi train, như tập cổng.

### 4.4 Suy luận và eval

- `Psi0Policy.serve` mở server suy luận (`/health`), `runner` gửi quan sát và nhận action chunk.
- **Real-time chunking**: robot chạy tiếp action cũ trong lúc chờ chunk mới (khoảng 160 ms mỗi lần suy luận, tác giả báo).
- Hai chế độ eval: **đồng bộ** (sim dừng chờ policy; dùng cho G0, HE, gỡ lỗi) và **bất đồng bộ** (chèn độ trễ đo từ log inference thật; dùng cho chỉ số chính của HS, HT).
- Log inference ghi đủ để dựng dòng thời gian: lúc gửi quan sát, độ trễ, lúc chunk về, số action đã tiêu trong lúc chờ, mức buffer, bước nhảy action ở ranh giới chunk.

### 4.5 Model phụ trợ cho các pipeline dữ liệu

Ngoài Ψ₀, mỗi pipeline dùng một số model nhỏ để xử lý dữ liệu. Thông tin model tra ngày 25/10/2026 (khi trưởng nhóm hỏi so sánh Nemotron 3.5 Bolt E4B với Qwen3.5, RoboBrain 2.5, Molmo2, SmolVLM2, HY-Embodied); mọi điểm benchmark là số **tự công bố** của từng nhóm, chưa đo trên task của đội.

**Nguyên tắc chọn** [Đề xuất, đã duyệt ở design chia làn 25/10]:

- Trọng số mở, **chạy cục bộ** trên RTX 3060 12 GB, để giữ quy tắc `data_class`: dữ liệu DENSO sau này không rời máy.
- Model và revision ghim trong `configs/models/`; dev và CI dùng model giả trong `flywheel.testkit`.
- Model chỉ **gợi ý**; luật và người duyệt mẫu vẫn quyết. Mọi kết quả do model sinh ghi nguồn nhãn `model` kèm tên và revision.
- Chọn cuối cùng bằng một vòng thử trên dữ liệu của đội (mục 4.5.4), không chọn theo benchmark công bố.

#### 4.5.1 Bảng so sánh

| Model | Nhận gì | Kích thước | Mạnh ở (tác giả báo) | Giấy phép | Trên RTX 3060 12 GB |
|---|---|---|---|---|---|
| Nemotron 3.5 Bolt E4B 4GB | Chữ (theo NVIDIA; trang Ollama ghi có ảnh, hai nguồn mâu thuẫn) | 8B tổng, 4B hiệu dụng | Hội thoại, gọi tool, ngữ cảnh 64K | OpenMDW-1.1 | Có, bản Q4 khoảng 3–4 GB |
| Qwen3.5-2B, 4B | Chữ, ảnh | 2B, 4B | VLM tổng quát; Qwen báo hơn Qwen3-VL về hiểu ảnh; ngữ cảnh 262K | Apache 2.0 | Có, bản lượng tử khoảng 2–3 GB |
| RoboBrain 2.5-4B | Ảnh, video | 4B, kiến trúc Qwen3-VL | Không gian 3D có độ sâu, quỹ đạo thao tác 3D, ước tiến độ task theo từng khung | Xem model card | Có |
| Molmo2-4B | Ảnh, video | 4B, LLM Qwen3, SigLIP 2 | Chỉ điểm và theo dõi vật trong video, đếm | Apache 2.0 (dữ liệu xem riêng) | Có |
| SmolVLM2-2.2B | Ảnh, video | 2,2B | Nhẹ (5,2 GB khi xử lý video); Video-MME 52,1 | Apache 2.0 | Có |
| HY-Embodied-0.5 (bản 2B) | Ảnh, video | 4B tổng, 2,2B hoạt động (Mixture-of-Transformers) | Suy luận không gian và hành động; đứng đầu 16/22 benchmark cùng cỡ | Xem model card | Có, trọng số khoảng 8 GB |

#### 4.5.2 Chọn theo vai

| Vai | Chọn | Lý do |
|---|---|---|
| VLM stage 1 của Ψ₀ | Giữ **Qwen3-VL-2B** | Action expert học trên đặc trưng của backbone này; đổi backbone là train lại stage 1 (khoảng 829 giờ video, tác giả báo) và stage 2, ngoài phạm vi 12 tuần. RoboBrain 2.5 cùng họ Qwen3-VL nhưng bản 4B khác kích thước ẩn, không lắp thẳng được |
| Gợi ý ranh giới bước trong video egocentric (ước tiến độ task) | **RoboBrain 2.5-4B** | Ước tiến độ theo từng khung; chạy cục bộ; thay vai của Cosmos Reason (cần GPU lớn) trong pipeline egocentric |
| Theo dõi tay và vật, chỉ điểm gắp trong video egocentric | **Molmo2-4B** | Chỉ điểm và theo dõi vật trong video |
| Sinh và kiểm cặp hỏi đáp cho probe P1 | RoboBrain 2.5-4B, có người duyệt | Hiểu không gian; P1 cần đáp án đúng, nên người duyệt mọi câu |
| Đối chứng cho probe P1 | RoboBrain 2.5-4B hoặc HY-Embodied-0.5 | Cho thấy Qwen3-VL-2B của Ψ₀ yếu hơn mức có thể ở loại câu hỏi nào |
| Lọc thô, tóm tắt video nhanh | SmolVLM2-2.2B | Rẻ nhất, yếu nhất về không gian; chỉ dùng để lọc đoạn không có tay hay vật |
| Agent QA/QC đọc log và báo cáo | **Nemotron 3.5 Bolt E4B 4GB** [Đã chốt 25/10] | Việc là đọc số và chữ, gọi tool; xem mục 5.5 |
| Agent QA/QC nhìn hình | **Qwen3.5-4B**, tùy chọn | Nemotron không nhìn được; chỉ thêm khi trưởng nhóm muốn agent tự xem hình (câu Q-M) |
| Egocentric với Nemotron | **Không dùng** | Nemotron chỉ đọc chữ |

#### 4.5.3 Model theo từng pipeline

| Pipeline | Bước | Model hoặc công cụ | Chạy ở đâu | Trạng thái |
|---|---|---|---|---|
| Egocentric | Che danh tính | Model phát hiện mặt và chữ (thẻ tên, màn hình) rồi làm mờ; người kiểm mẫu đặt `verified` | Cục bộ | Model cụ thể chọn khi làm DA-04 [Để lại cho người làm] |
| Egocentric | Lọc thô | SmolVLM2-2.2B | Cục bộ | Tùy chọn |
| Egocentric | Gợi ý ranh giới bước | RoboBrain 2.5-4B; luật trước, model khi luật mơ hồ | Cục bộ | Chốt sau vòng thử |
| Egocentric | Theo dõi tay, vật, điểm gắp | Molmo2-4B | Cục bộ | Chốt sau vòng thử |
| Egocentric | Pose tay 3D (E-A, video tự quay) | Model hand pose từ RGB | Cục bộ | Chọn khi làm DA-04 [Để lại cho người làm] |
| Egocentric | Tư thế camera (E-A) | Thư viện visual SLAM | Cục bộ | Chọn khi làm DA-04 [Để lại cho người làm] |
| Egocentric | Pose (E-B, EgoDex) | Không cần model; đọc tracking có sẵn | | |
| Teleop | Cắt đoạn | Luật (bàn tay đóng mở, vận tốc thân); không cần model | | |
| Teleop | Phát lại action | MuJoCo của SIMPLE | Cục bộ | |
| Synthetic S1 | Lập quỹ đạo | cuRobo (hai tay), script đi bộ hoặc AMO | Cục bộ | Theo V3 |
| Synthetic S2 | Biến đổi đoạn teleop | IK của SIMPLE, lệnh vận tốc tới WBC | Cục bộ | |
| Synthetic S3 (sau demo) | Đổi ngoại hình | Cosmos Transfer qua NIM | NIM tự host (A100 thuê) hoặc API hosted với dữ liệu `public` | Sau demo |
| Synthetic S4 (sau PoC) | Video task mới | Cosmos Predict qua NIM; action suy ra bằng inverse dynamics model | Như trên | Sau PoC |
| Synthetic S3, S4 | Lọc mẫu sai vật lý | Cosmos Reason qua NIM | Như trên | Sau demo |
| Đánh giá | Probe P1 | Qwen3-VL-2B của Ψ₀ (đối tượng đo); RoboBrain hoặc HY-Embodied làm đối chứng | Cục bộ | |
| Đánh giá | Agent QA/QC | Nemotron 3.5 Bolt E4B 4GB; Qwen3.5-4B tùy chọn | Cục bộ | Mục 5.5 |

**NVIDIA NIM** (sau demo, cho S3, S4): hai phương án triển khai, chọn theo `data_class`:

| | N-A · API hosted | N-B · NIM tự host |
|---|---|---|
| Nơi chạy | build.nvidia.com hoặc endpoint NVIDIA quản lý | Container NIM trên máy đội hoặc máy thuê |
| Dữ liệu được gửi | Chỉ `public` | Mọi `data_class` |
| Nhược | Model có thể bị ngừng (API hosted của Cosmos Reason1-7B ngừng 24/03/2026) | Cần GPU lớn: Reasoner bản nano khoảng 23 GB; Generator bản nano 58 GB BF16, khoảng 31 GB khi offload (nên chạy trên A100 80 GB thuê) |

`NimClient` định tuyến theo `data_class`: `restricted`, `internal` chỉ đi N-B; mỗi lời gọi ghi `LedgerEntry` (giây video, token, GPU-giây) và phiên bản model.

**Bộ nhớ trên 3060** (ước lượng, chưa đo): mỗi model 4B ở bản lượng tử cần vài GB, nên chạy **lần lượt theo job**, không giữ cùng lúc với server Ψ₀. Lịch chạy model do runner xếp; đo VRAM thật ở vòng thử.

#### 4.5.4 Vòng thử trước khi chốt

Trước khi chốt model gán nhãn và model nhìn hình: một vòng thử 4–6 giờ (ước lượng) trong DA-04 và DA-20, trên 30 khung EgoDex mẫu, 30 khung render SIMPLE của task hai bàn và bộ câu hỏi P1. Đo: độ đúng câu hỏi đáp, sai số ranh giới bước (số khung), tỉ lệ chỉ đúng điểm gắp, VRAM và độ trễ trên 3060. Kết quả ghi `Decision`.

---

## 5. Lớp đánh giá

### 5.1 Tập điều kiện

- `scenarios` sinh điều kiện theo vector c: vị trí và góc vật (x, y, yaw), vị trí bàn đích, vị trí tương đối hai bàn nếu SIMPLE cho đổi, lệch xuất phát của robot, ánh sáng, vật liệu bàn, số vật gây nhiễu.
- Khoảng cách điều kiện: Euclid có trọng số cho phần liên tục (chuẩn hóa theo khoảng của train), Hamming cho phần phân loại.
- kNN (K = 5) tới tập train cho phép kiểm vùng phủ; τ_cov là phân vị 95 leave-one-out.
- Ba chế độ lấy mẫu: đều trong miền train (nhánh B); trong bán kính τ_cov quanh lỗi đã chẩn đoán (nhánh C); quanh mọi lỗi dev (B-fail).

### 5.2 Scorer từng bước

```text
signals.parquet ──► TaskDefinition.evaluate ──► Score
                    6 vị từ (tiếp cận, gắp, đi, tới bàn đích, đặt, nhả và ổn định)
                    + điều kiện thăng bằng suốt episode
                    trạng thái mỗi bước: đạt · trượt · chưa thử · chưa rõ (kèm t vào, t ra)
                    bước hỏng đầu tiên k · kiểu lỗi · lớp lỗi chung · mức
```

- Scorer phải trùng cờ `check_success` của SIMPLE ≥ 95% trên 100 episode, và kỹ sư xem 20 episode thất bại thấy bước hỏng gán đúng (cổng G1).
- Chỉ số chính ở holdout là cờ của SIMPLE; scorer cho chỉ số theo bước và nhãn lỗi. Lỗi scorer vì vậy không làm sai kết luận chính.

### 5.3 Chuỗi chẩn đoán

Cho mỗi cụm lỗi (gom theo bước hỏng, kiểu lỗi, mức), chạy trên tối đa R = 5 đại diện, theo **thứ tự cố định**:

```text
① thiếu tín hiệu?          ──có──► CHƯA RÕ
② sai số bám lệnh WBC?     ──có──► LỖI CONTROLLER          ┐
③ độ trễ p99?              ──có──► LỖI RUNTIME             │ hệ thống: sửa trước,
④ lệch ảnh và state?       ──có──► LỖI ĐỒNG BỘ             │ không tiêu ngân sách dữ liệu
⑤ camera khác tham chiếu?  ──có──► LỖI CALIBRATION         ┘
   ④b quy lỗi về stage (probe P1, P3, P4) ──► giả thuyết trên card, kỹ sư xác nhận
⑥ planner chuẩn thất bại?  ──có──► KHÔNG KHẢ THI
⑦ khởi động từ trạng thái chuẩn ở đầu bước k thì làm được? ──có──► TRẠNG THÁI ĐẦU XẤU   → dữ liệu phục hồi
⑧ đổi hình ảnh về chuẩn thì làm được?  ──có──► NHẬN THỨC                                → báo cáo
⑨ ngoài miền train?        ──có──► NGOÀI MIỀN                                          → báo cáo
⑩ xa dữ liệu train (d > τ_cov)? ──có──► THIẾU VÙNG PHỦ   → sinh sim quanh lỗi (S1, S2)
                               ──không──► KỸ NĂNG YẾU    → teleop correction ở bước k
chẩn đoán cụm = đa số của các đại diện; hòa thì kỹ sư quyết
```

Phép ⑥ gọi `GeneratorAdapter.plan`; ⑦ lấy trạng thái chuẩn từ `plan(until_stage=k)` rồi chạy M = 10 lượt; ⑧ chạy lại với `VisualOverride`. Phép nào adapter không có năng lực thì `skipped` kèm lý do.

### 5.4 Evidence card

Một trang cho mỗi cụm lỗi: danh sách episode và đại diện; bước hỏng và kiểu lỗi; kết quả từng phép kiểm **kèm ngưỡng và số lượt**; giả thuyết stage; chẩn đoán; can thiệp đề xuất, lợi ích kỳ vọng, chi phí ước tính; quyết định của kỹ sư (đồng ý hoặc ghi đè kèm lý do); kết quả sau khi train lại. Card là bản dựng từ Cluster và Decision, dựng lại được.

### 5.5 Agent QA/QC

#### 5.5.1 Vai trò và giới hạn

[Đã chốt 25/10, giữ ở 27/10] Agent QA/QC chỉ **đánh giá** báo cáo dataset, log train và output của từng bước của train, eval, inference; phải **biểu diễn cho người hiểu** (stage 1 ra ảnh và chữ, stage 3 ra action phát lại trên MuJoCo, inference ra dòng thời gian của real-time chunking để xử lý bài toán bất đồng bộ); đưa insight và ước lượng; **AI Engineer quyết**.

```text
job dữ liệu / train / eval / infer
        │
        ▼
code tính mọi con số, dựng hình kèm chú thích chữ          ← tất định, có test
        │  DatasetReport · ReplayReport · metrics.jsonl · kết quả probe · Score · Cluster · log RTC
        ▼
Agent QA/QC (Nemotron, cục bộ)                             ← diễn giải, xếp hạng, đề xuất, trích số
        │  QAReport + báo cáo HTML
        ▼
kỹ sư đồng ý hoặc ghi đè kèm lý do (fw review) ──► Decision
```

Vị trí trong vòng flywheel: giữa bước chẩn đoán (bước 4–9) và bước đề xuất (bước 10). Kỹ sư đọc báo cáo của agent cùng evidence card khi chạy `fw review`.

#### 5.5.2 Model

| Mục | Nemotron 3.5 Bolt E4B 4GB |
|---|---|
| Nhà làm, ngày | NVIDIA, ra ngày 23/10/2026 |
| Dựng trên | Gemma-4-E4B-it |
| Kích thước | 8B tham số tổng, 4B hiệu dụng |
| Ngữ cảnh | 64K token |
| Đầu vào | Chữ (theo tài liệu NVIDIA; trang Ollama ghi có ảnh, mâu thuẫn; đội coi là chỉ chữ) |
| Gọi tool | Có |
| Bộ nhớ | Bản Q4 khoảng 3–4 GB VRAM, chạy được trên RTX 3060 12 GB |
| Giấy phép | OpenMDW-1.1; ghi vào Source trước khi dùng cho sản phẩm giao DENSO |
| Trạng thái | Model đã chốt [25/10]; ghim revision trên Hugging Face [Đề xuất] |

**Vì sao chọn:** việc của agent là đọc số và chữ có cấu trúc, so với ngưỡng, xếp hạng và viết đề xuất; không cần nhìn ảnh. Model nhỏ chạy cục bộ nên dữ liệu không rời máy (đúng quy tắc `data_class` khi có dữ liệu DENSO), chi phí gần bằng 0 mỗi lần chạy, và chạy được song song với dev trên máy 3060.

**Tùy chọn nhìn hình:** **Qwen3.5-4B** (Apache 2.0, nhận ảnh, bản lượng tử khoảng 2–3 GB) qua endpoint thứ hai, chỉ khi trưởng nhóm muốn agent tự xem bảng ảnh stage 1 hay khung hình video phát lại (câu Q-M, chưa chốt). Dùng cùng bộ chấm như Nemotron.

#### 5.5.3 Triển khai

| Phần | Cách làm |
|---|---|
| Serve | Hiếu serve Nemotron Q4 trên máy 3060 (service `llm-serve`), API kiểu OpenAI; endpoint, model và revision khai trong `configs/models/` |
| Dev và CI | Model giả trong `flywheel.testkit` trả lời tất định theo kịch bản; test không cần GPU |
| Prompt | Trong `configs/eval/agentqa/`, có hash; đổi prompt là phiên bản mới và phải chấm lại |
| Tool [Đề xuất] | Chỉ tool đọc: lấy một phần của artifact theo ID (bảng số, tóm tắt log theo cửa sổ, danh sách lỗi QA). Không có tool ghi, chạy job hay đọc `vault/` |
| Ngữ cảnh | Log dài được code tóm tắt trước (theo cửa sổ, theo nhóm action) để vừa 64K; agent xin thêm chi tiết qua tool |
| Đầu ra | `QAReport` đúng schema (phát hiện, bằng chứng gồm đường dẫn hình và số trích dẫn, insight, ước lượng có khoảng, đề xuất), dựng thành HTML tĩnh |

#### 5.5.4 Đầu vào theo từng stage

| Stage | Code dựng gì | Agent đọc gì |
|---|---|---|
| Dataset | Báo cáo dataset: pass, flag, reject theo phép kiểm và theo loại dữ liệu; báo cáo phát lại | Phép kiểm trượt nhiều nhất, nguồn tệ nhất, gợi ý sửa bộ đọc hay cách thu |
| Stage 1 · VLM | Bảng ảnh: khung hình, câu hỏi, câu trả lời của VLM, đáp án; khung xương tay dự đoán vẽ chồng lên khung (`draw_utils` của Ψ₀) | Tỉ lệ đúng P1 theo loại câu hỏi, loss P2, độ tụt P4, các ca sai tiêu biểu |
| Stage 3 · Action | Đồ thị action dự đoán so với thật theo nhóm và theo vị trí trong chunk; video MuJoCo phát lại action dự đoán từ cùng state đầu, đặt cạnh phát lại action thật | Sai số theo nhóm, nhóm tệ nhất, vị trí trong chunk bắt đầu lệch, kết quả task khi phát lại |
| Train | `metrics.jsonl`: loss tổng, theo nhóm, theo vị trí trong chunk, chuẩn gradient, phương sai dự đoán | Dấu hiệu T1–T8, so với checkpoint cha |
| Inference (RTC) | Dòng thời gian: lúc gửi quan sát, độ trễ suy luận, lúc chunk về, số action đã tiêu trong lúc chờ (delay d), mức buffer, bước nhảy ở ranh giới chunk, lúc buffer cạn | Độ trễ p50, p99 so với chu kỳ điều khiển; tần suất buffer cạn; bước nhảy ở ranh giới so với trong chunk |
| Eval closed-loop | Thành công theo mức, bước hỏng, video lượt lỗi, cụm lỗi | Cụm lỗi, liên kết tới evidence card |

**Bài toán bất đồng bộ:** Ψ₀ cần khoảng 160 ms mỗi lần suy luận (tác giả báo) và chạy real-time chunking. Eval đồng bộ (sim dừng chờ policy) không bao giờ thấy lỗi do trễ. Vì vậy agent đọc log của eval bất đồng bộ, và lỗi trễ (độ trễ, buffer cạn, giật ở ranh giới chunk) được đưa vào kiểm hệ thống (LỖI RUNTIME) trước khi coi là lỗi dữ liệu.

#### 5.5.5 Kiểm soát

| Kiểm soát | Cách làm |
|---|---|
| Không bịa số | Mọi con số (CI, xu hướng loss, độ trễ p99, tỉ lệ sửa được, ước lượng lợi ích) do code tính; câu nêu số không có trong đầu vào làm báo cáo bị đánh dấu hỏng (có test) |
| Không vượt quyền | Không đọc `vault/`; không tự chạy job; không tự chọn dữ liệu thay kỹ sư (có test) |
| Ước lượng có khoảng | Mỗi ước lượng của agent được lưu; khi có kết quả đo thì so lại, như cặp "ước tính" và "thực đo" của sổ chi phí |
| Kỹ sư quyết | Mọi đề xuất qua `fw review`; ghi đè có lý do; tỉ lệ ghi đè được báo cáo |
| Phản mục tiêu | Agent nêu số không có trong log, hoặc tự chọn dữ liệu thay kỹ sư, coi là hỏng dù báo cáo đọc trôi chảy |

#### 5.5.6 Đánh giá agent

| Bộ chấm | Nội dung | Khi nào |
|---|---|---|
| Bộ ca mẫu | ≥ 10 ca có đáp án: log train bình thường, loss phân kỳ, chiều action chết, độ trễ vượt ngưỡng, chunk giật… | Trước khi dùng; chạy lại khi đổi model hoặc prompt |
| Bộ lỗi cấy (mục 3.8) | Precision, recall theo từng loại lỗi trên dữ liệu và log thật có cấy lỗi; báo nhầm trên bản sạch; thời gian ra báo cáo; tách phần phép kiểm bằng code bắt được khỏi phần agent thêm | Trước khi train (demo 17/11) |
| Log thật | Chạy trên log fine-tune và eval thật của HE; báo riêng với kết quả trên lỗi cấy | Sau khi có log thật |
| So ước lượng với đo | Tỉ lệ ước lượng của agent có khoảng chứa giá trị đo | Mỗi vòng |

#### 5.5.7 Câu hỏi còn mở

| Mã | Câu hỏi |
|---|---|
| Q-M | Agent có cần tự nhìn hình không; nếu có thì thêm Qwen3.5-4B bên cạnh Nemotron |
| Q-revision | Ghim revision nào của Nemotron trên Hugging Face, và bản lượng tử nào |
| Q-tool | Có cho agent gọi tool đọc artifact không, hay chỉ đưa toàn bộ đầu vào đã tóm tắt vào ngữ cảnh |

---

## 6. Lớp vòng quyết định

### 6.1 RunPlan

Mọi lần chạy chính thức có một RunPlan đóng băng (`fw plan freeze`): mục đích (`g0_repro`, `e1`, `branch_train`, `aa_test`, `round`, `holdout`, `hd`, cộng thí nghiệm HE), task, embodiment, commit mã, digest image, revision checkpoint gốc (có provenance sạch), revision dataset, SplitPlan, recipe chung (số bước, batch, ρ, tăng cường thị giác), nhánh và seed, phép so sánh khai trước, chỉ số, phương pháp thống kê, phiên bản scorer và ngưỡng, bảng giá. Lệnh chạy từ chối RunPlan chưa đóng băng, cây git bẩn, image không ghim digest, hoặc checkpoint gốc nằm trong `simple-checkpoints/`.

### 6.2 runner

- Nhận danh sách `RolloutRequest` (điều kiện, mức, seed, trạng thái đầu, ghi đè hình ảnh, lỗi cấy, chế độ đồng bộ hay bất đồng bộ), chạy W worker song song qua `SimulatorAdapter.rollout`.
- Lỗi hạ tầng: thử lại tối đa 2 lần cùng seed; vẫn hỏng thì `infra_failed`, loại khỏi mẫu số, đếm riêng.
- Bị ngắt thì chạy tiếp, không chạy lại episode đã xong.

### 6.3 decide và kỹ sư duyệt

- Mỗi loại can thiệp t (sinh sim S1, biến thể S2, teleop correction, dữ liệu phục hồi) có tỉ lệ sửa được f_t ~ Beta, khởi đầu Beta(1, 1).
- Đề xuất cho cụm j: lợi ích g_j = (min(m_j, L_t) / 90) × trung bình f_t; chi phí c_j từ bảng giá. Chọn theo g/c giảm dần tới hết ngân sách; hòa thì ưu tiên bước hỏng sớm hơn.
- Định lượng mặc định: 20 rollout sim mỗi lỗi (tối đa 200 mỗi cụm); 1 correction mỗi lỗi (tối đa 10); 1 đoạn phục hồi mỗi lỗi (tối đa 10); xử lý tối đa L_t = 10 lỗi mỗi cụm.
- Kỹ sư duyệt hoặc ghi đè bằng `fw review`; ghi đè bắt buộc có lý do; tỉ lệ ghi đè được báo cáo. Cụm lỗi hệ thống thành phiếu sửa (`repair_ticket`).

### 6.4 acquisition

Thực thi kế hoạch đã duyệt qua `GeneratorAdapter.generate` và `TeleopSource`; đo ngân sách theo thời gian thực, dừng ở trần và ghi phần chưa làm; mọi episode mới đi lại sáu tầng của lớp dữ liệu; tạo release con (cũ cộng mới, giữ lineage, dữ liệu cũ luôn được trộn lại).

### 6.5 gate

| Việc | Cách làm |
|---|---|
| Cổng dev | Tập 90 điều kiện **mới** mỗi vòng; cha và ứng viên ≥ 3 lượt mỗi điều kiện; ứng viên đạt khi tăng ≥ 1 sai số chuẩn ghép cặp, cụm được can thiệp cải thiện, và hồi quy ≤ max(5%, sàn A/A) |
| A/A test | Chạy policy cha hai lần độc lập để đo sàn hồi quy giả do nhiễu; một lần ở G3 |
| Tỉ lệ sửa được | Trên điều kiện mới quanh lỗi (bán kính τ_cov / 2, tối đa 5 điều kiện mỗi lỗi, 30 mỗi cụm), so cha với ứng viên ≥ 3 lượt; fixed_j = n × (p_ứng viên − p_cha); cập nhật Beta. Tránh thiên lệch hồi quy về trung bình |
| Holdout | Chỉ `gate.holdout` đọc vault; khóa theo checkpoint; nhánh không phụ thuộc C chạy sớm và niêm phong; `fw holdout unseal` khi mọi checkpoint của RunPlan cuối đã khóa cùng giao thức |

Điều kiện dừng vòng: hết ngân sách; đề xuất tốt nhất dưới 1 điểm % mỗi $100; hai vòng liên tiếp trượt cổng; đủ số vòng đã khai.

### 6.6 ledger và reports

- `ledger.meter()` bọc mọi job: giây tường, GPU lấy mẫu mỗi 10 giây, phút người (teleop, `fw review`, HD), quy ra tiền theo bảng giá; mỗi mục có cờ "ước tính" hoặc "thực đo".
- `reports` dựng HTML tĩnh: báo cáo dataset, evidence card, báo cáo vòng, sổ chi phí, đường cong E1 và HE, bảng so sánh phương pháp, khuyến nghị thu dữ liệu.

### 6.7 Công cụ HD

Console để đo thời gian chẩn đoán của kỹ sư: phân công chéo người và episode, bấm giờ, ghi chẩn đoán; điều kiện có evidence card so với công cụ chuẩn (Rerun cộng đồ thị mặc định); có card sai cố ý để đo mức tin mù quáng.

---

## 7. Hạ tầng chạy

### 7.1 Tiến trình và container

```text
┌────────────────────────────── máy host (RTX 3060 12 GB) ───────────────────────────────┐
│  fw CLI + lõi flywheel (Python, CPU)  ── job spec JSON, thư mục chung ──┐               │
│        │                                                                 │               │
│        ├─ container simple-worker (SIMPLE, Python 3.10, MuJoCo, Isaac Sim khi cần)       │
│        │      worker chỉ dùng stdlib + simple; đọc job, ghi bundle                       │
│        ├─ container psi0-serve (Ψ₀, Python 3.11, torch 2.7) ◄── HTTP/WebSocket ── worker │
│        ├─ llm-serve (Nemotron Q4; Qwen3.5-4B tùy chọn) ◄── Agent QA/QC                   │
        ├─ model phụ trợ chạy lần lượt (RoboBrain 2.5-4B, Molmo2-4B, SmolVLM2) ◄── egocentric │
│        └─ ACT, Diffusion Policy (train trên 3060)                                         │
└──────────────────────────────────────────────────────────────────────────────────────────┘
            │ job spec + bản export dataset                ▲ checkpoint, log, sổ chi phí
            ▼                                              │
┌──────────── Colab Pro (A100, H100, qua CLI) ─────────────┐
│ psi0-train: fine-tune stage 3, chạy stage 1 ngắn          │
│ tiếp tục được từ checkpoint; ghi compute unit             │
└───────────────────────────────────────────────────────────┘
```

Vì sao tách tiến trình: SIMPLE và Ψ₀ cần phiên bản Python, PyTorch, CUDA khác nhau; ghép một môi trường là nguồn lỗi lớn nhất. Lõi và container nói chuyện qua job spec JSON và thư mục chung; simulator và policy nói chuyện qua server policy có sẵn của SIMPLE.

### 7.2 Phân vai máy

| Việc | Máy |
|---|---|
| Lõi, catalog, báo cáo, test CPU | Host |
| SIMPLE ở `--sim-mode=mujoco` (teleop, sinh tự động, phát lại, eval nhanh) | Host (cần đo ở G0) |
| SIMPLE ở `mujoco_isaac` (eval so số công bố, video) | Máy có Isaac Sim; Colab nếu chạy được (câu Q-27D) |
| Fine-tune Ψ₀, stage 1 ngắn | Colab |
| Agent QA/QC, model phụ trợ của pipeline egocentric (chạy lần lượt) | Host |

### 7.3 Quyền dữ liệu

| `data_class` | Ví dụ | Được đi đâu |
|---|---|---|
| `public` | psi-data, EgoDex, sim G1 đội tự sinh | Mọi máy, kể cả Colab và API hosted |
| `internal`, `restricted` | Mọi dữ liệu DENSO, video tự quay có người thật nếu đội khai như vậy | Chỉ máy cục bộ và NIM tự host; không bao giờ ra dịch vụ hosted |

`NimClient` và mọi adapter gọi ra ngoài nhận `data_class` của từng yêu cầu và từ chối khi không hợp lệ (có test). Release ghi `data_class` gộp theo mức chặt nhất.

---

## 8. Kiến trúc phần mềm

### 8.1 Package

```text
packages/
  flywheel-contracts/   NHÂN  schema Pydantic, 6 Protocol, artifact giữa làn
  flywheel-store/       NHÂN  kho sha256, catalog JSONL, view DuckDB, refs, vault, ghi sổ chi phí
  flywheel-testkit/     NHÂN  bộ giả (FakeSim2D, FakePolicy, FakeTrainer, FakeGenerator, FakeTeleop,
                              ToyPickPlace), contract suite, file mẫu mọi artifact, bộ lỗi cấy mẫu
  flywheel-cli/         NHÂN  lệnh fw; composition root duy nhất được import cả làn và adapter
  flywheel-data/        LÀN   ingest (egocentric, teleop, synthetic), normalize, annotate, qa,
                              replay_check, release, export, inject
  flywheel-eval/        LÀN   scenarios, tasks, scorer, diagnosis, cards, agentqa (gồm bench)
  flywheel-loop/        LÀN   runplan, runner, decide, acquisition, gate (holdout), ledger, reports, hd
  flywheel-simple/      ADAPTER  SimpleSim, KeyboardTeleop, generator S1 (A, B), S2, worker
  flywheel-psi0/        ADAPTER  policy, trainer, stage 1, probe, client RTC
  flywheel-lerobot/     ADAPTER  ACT, Diffusion Policy
  flywheel-nim/         ADAPTER  NimClient (sau demo)
```

### 8.2 Luật import

| Luật | Kiểm bằng |
|---|---|
| Nhân không import làn, adapter hay runtime (`simple`, `psi0`, `lerobot`, `torch`, `isaacsim`, `mujoco`) | import-linter (forbidden) |
| Ba làn độc lập với nhau | import-linter (independence) |
| Làn không import adapter hay runtime; chỉ dùng Protocol | import-linter (forbidden) |
| Chỉ `flywheel.cli` được import cả làn và adapter | import-linter |
| Chỉ `gate.holdout` đọc đường dẫn vault | Test quét mã trong CI |

Hệ quả: đổi simulator, model hay robot chỉ là viết adapter mới; lõi và ba làn không đổi. Ba làn code song song được vì chỉ phụ thuộc hợp đồng.

### 8.3 Artifact giữa các làn

| Artifact | Làn ghi | Làn đọc |
|---|---|---|
| `Episode`, `Segment`, `ReleaseManifest`, `DatasetRef`, `DatasetReport` | Dữ liệu | Đánh giá, Vòng, adapter Ψ₀ |
| `ReplayReport` | Dữ liệu | Đánh giá (Agent QA/QC) |
| `DefectManifest` | Dữ liệu | Chỉ bộ chấm của Đánh giá, sau khi agent đã chạy |
| `RunPlan`, `TrainSpec`, `RolloutRequest` | Vòng | Adapter |
| `Trace`, `RolloutResult` | Adapter simulator | Đánh giá |
| `Checkpoint`, `metrics.jsonl`, kết quả probe, log RTC | Adapter Ψ₀ | Đánh giá |
| `Score`, `Cluster`, `EvidenceCard`, `QAReport` | Đánh giá | Vòng |
| `Decision`, `LedgerEntry`, `FixRateEvent` | Vòng | Mọi làn |

Đổi hay thêm trường đi qua PR hợp đồng riêng, có file mẫu trong testkit ngay khi merge; không thêm trường tạm trong code làn.

### 8.4 Cấu hình

```text
configs/
  kernel/       data_class, đường dẫn kho, phiên bản schema
  models/       recipe Ψ₀ stage 1 và 3, ACT, DP; endpoint LLM (model, revision)
  runplans/     RunPlan từng nhánh và thí nghiệm (HE, stage 1)
  embodiments/  g1.yaml: action_layout 36 chiều, control_spec WBC; bản AMO riêng
  sim/          domain randomization task hai bàn, dải hạt giống, renderer, biến thể S2
  data/         ngưỡng QA, ngưỡng phát lại, cấu hình export, egocentric, lỗi cấy
  eval/         tham số vị từ của task, ngưỡng chẩn đoán, prompt Agent QA/QC
  loop/         bảng giá, ngưỡng cổng, ngân sách vòng
```

Mỗi thư mục một chủ; mỗi tệp YAML có Pydantic model trong `config.py` của package chủ và một test nạp; số chưa đo ghi chú thích `# giả định: <nguồn>`.

### 8.5 Kiểm thử

| Mức | Nội dung |
|---|---|
| Unit | Mỗi module; chạy CPU |
| Contract | Mỗi adapter qua bộ contract test chung; mỗi làn đọc file mẫu và ghi đúng schema; export đọc lại bằng loader Ψ₀ |
| Tính chất | Validate schema; "vòng 1 xếp theo đơn giá"; bootstrap phân cấp trên dữ liệu giả biết đáp án |
| End-to-end giả | Vòng flywheel rỗng chạy trọn trên bộ giả trong CI, dưới 10 phút |
| GPU, sim | Marker riêng, không chạy trong CI mặc định |

### 8.6 Lệnh `fw`

| Lệnh | Việc | Nguồn |
|---|---|---|
| `fw --version` | Phiên bản kèm git SHA | Đã có (S1-01) |
| `fw import <nguồn>` | Ingest từ psi-data, EgoDex, bản ghi bàn phím, video | [Đề xuất] |
| `fw qa run`, `fw replay` | Chạy QA và phát lại trên một lô | [Đề xuất] |
| `fw release create`, `fw release freeze` | Tạo và đóng băng release | 03 |
| `fw export --format lerobot-v21\|lerobot-v3\|stage1` | Xuất dataset | [Đề xuất] |
| `fw inject`, `fw bench` | Tạo bộ lỗi cấy, chấm QA và agent | [Đề xuất] |
| `fw plan freeze` | Đóng băng RunPlan | 03 |
| `fw train` | Chạy job train từ RunPlan | 03 |
| `fw review` | Kỹ sư duyệt đề xuất và card | 03 |
| `fw holdout precheck`, `run`, `unseal` | Holdout | 03 |
| `fw ledger add` | Thêm mục sổ chi phí tay | 03 |
| `fw status` | Job, ngân sách, tỉ lệ lỗi hạ tầng | 03 |
| `fw hd` | Console thí nghiệm HD | 03 |

---

## 9. Ví dụ chạy một vòng

Giả sử policy π₀ là Ψ₀ V-EGO fine-tune trên 20 demo teleop của task hai bàn.

1. `fw plan freeze` cho RunPlan `purpose = round`, nhánh C, ngân sách B_add.
2. `runner` chạy π₀ trên 90 điều kiện dev, ra 90 trace. Giả sử 40 lượt thất bại (con số minh họa).
3. `scorer` gán nhãn: ví dụ 18 lỗi L-GRASP ở bước 2 Level 0, 12 lỗi L-WALK ở bước 3 Level 1, 10 lỗi L-PLACE ở bước 5 Level 2.
4. `diagnosis` gom 3 cụm, chạy chuỗi kiểm trên 5 đại diện mỗi cụm. Ví dụ kết quả: cụm L-GRASP là KỸ NĂNG YẾU (trong miền, gần train); cụm L-WALK là THIẾU VÙNG PHỦ (vị trí bàn xa dữ liệu train); cụm L-PLACE là NGOÀI MIỀN (Level 2 ngoài khoảng train), chỉ báo cáo.
5. Agent QA/QC đọc cụm, log và báo cáo dataset, viết báo cáo: xếp cụm theo lợi ích, chỉ ra nhóm action `arm_r` có sai số P3 cao nhất ở cụm L-GRASP.
6. `decide` đề xuất: 10 teleop correction cho cụm L-GRASP, 200 rollout S1 hoặc S2 quanh điều kiện của cụm L-WALK; xếp theo g/c. Kỹ sư duyệt bằng `fw review`, ghi `Decision`.
7. `acquisition` thu correction bằng bàn phím từ trạng thái lỗi đã lưu, sinh S2 quanh điều kiện lỗi; mọi episode qua sáu tầng; release con đóng băng.
8. `training` fine-tune từ checkpoint cha trên release con; `gate` chạy cổng dev trên 90 điều kiện mới, 3 lượt; đo tỉ lệ sửa được của correction và S2 trên điều kiện mới quanh lỗi.
9. `ledger` tổng hợp: phút người của correction, GPU-giờ sinh và train, chi phí chẩn đoán; `reports` ra card, báo cáo vòng, chi phí mỗi điểm % tăng.

---

## 10. Điểm chưa chốt

| Điểm | Ảnh hưởng | Chốt ở đâu |
|---|---|---|
| V3: dữ liệu sinh tuyến A hay B | Có trộn synthetic S1 với teleop được không | S1-11, tuần 1 |
| Q3: khôi phục trạng thái giữa episode | Có phép khoanh vùng, dữ liệu phục hồi, correction S2 không | S1-06 |
| Q4: tách hình ảnh khỏi vật lý | Có phép kiểm thị giác không | S1-06 |
| Ψ₀ eval ở MuJoCo thuần có giữ độ chính xác | Renderer của mọi thí nghiệm, chi phí eval | S1-03, S1-04 |
| N_teleop của gói task hai bàn | Điểm cuối của lưới HE và E1 | S1-07 |
| Thiết bị và lượng video egocentric tự quay | Độ tin pose, giá trị fine-tune stage 1 | Hiếu, mentor |
| Model gán nhãn egocentric (RoboBrain, Molmo2) và model nhìn hình của agent (Qwen3.5-4B) | Chất lượng cắt đoạn, có cần agent tự xem hình | Vòng thử mục 4.5.4; câu Q-M |
| Model che danh tính, hand pose, SLAM | Pipeline egocentric E-A | Người làm DA-04 |
| Giấy phép psi-data (V9) | Dữ liệu demo có coi là `public` để lên Colab không | Hiếu hỏi PSI Lab |
| Tên lệnh `fw` mới | Giao diện của làn Dữ liệu và bộ lỗi cấy | Khi viết story |
