# 07 · Chia việc 5 người và quy trình git khi dùng Claude

_Ngày 23/10/2026. Vai trò BMAD: Scrum Master cộng Product Owner. Đầu vào: [04 · Kế hoạch](04-delivery-plan.md) mục 3 (vai, RACI) và mục 4.9, [design 27/10/2026](../superpowers/specs/2026-10-27-g1-psi0-demo-design.md) mục 12, 13. Bản 0.1 là [Đề xuất]; Hiếu và Thông chốt ở họp lập kế hoạch Sprint 1 ngày 26/10/2026._

| Ngày | Phiên bản | Thay đổi | Tác giả |
|---|---|---|---|
| 28/10/2026 | 0.9 | Mục 3.4: lệnh merge chuẩn `--admin --rebase` và lý do PR xanh vẫn BLOCKED (ruleset "Only Hiếu merges into master") | PO (Hiếu) |
| 28/10/2026 | 0.8 | Mục 2.2: thêm DA-32, DA-33, DA-34 (nhánh task bê khay của Hiếu, chạy song song, [design 28/10/2026](../superpowers/specs/2026-10-28-tray-transfer-he-design.md)) | PO (Hiếu) |
| 28/10/2026 | 0.7 | Mục 3.2: chủ `flywheel-contracts`, `flywheel-testkit` là Long theo mục 2.0, thay ghi chú bản 0.4 | PO (Hiếu) |
| 27/10/2026 | 0.6 | Phân công: thêm mục 2.0 (bốn người làm data flywheel, Hiếu làm phần còn lại; dữ liệu đi giữa người; luật để không đụng nhau; thứ tự ngày đầu); mục 2.1 điền chủ theo thư mục con; mục 2.2 điền người làm, tách DA-18 thành DA-18 và DA-30, DA-27 thành DA-27 và DA-31; mục 2.3 tải mới; mục 3.6 PR restructure tạo nhóm phụ thuộc và cập nhật `CODEOWNERS` | PO (Hiếu) |
| 27/10/2026 | 0.5 | Theo [design ngày 27/10/2026](../superpowers/specs/2026-10-27-g1-psi0-demo-design.md): mục 2.1 bỏ `denso-sim`, `flywheel-mujoco`, `ros2_ws`, `docker/ros2-sim`; `flywheel-simple` thành adapter simulator chính, chủ chờ PO giao; mục 2.2 bảng story mới: giữ, sửa, hoãn, xóa, mở lại DA-04, khôi phục DA-18, thêm DA-26 đến DA-29 (ba loại dữ liệu egocentric, teleop, synthetic); mục 2.3 tải theo người chờ PO giao lại; mục 3.6 PR `chore-restructure` bỏ khung `flywheel-mujoco`, `denso-sim` | PO (Hiếu) |
| 25/10/2026 | 0.4 | Theo design chia làn ngày 25/10/2026 (file đã xóa ngày 27/10/2026): mục 2.1 sở hữu theo nhân, ba làn, adapter, `denso-sim`, `ros2_ws`, `configs/` theo làn; mục 2.2 đổi chủ DA-01, DA-04, DA-08, DA-13, DA-17, DA-18, DA-20, DA-23, thêm DA-24, DA-25; mục 2.3 tải mới; mục 3.2 hợp đồng do Hiếu giữ; mục 3.6 PR `chore-restructure` | PO (Hiếu) |
| 25/10/2026 | 0.3 | Theo design ngày 25/10/2026 (file đã xóa ngày 27/10/2026): mục 2.1 thêm `flywheel-mujoco`, `flywheel-agentqa`, cột review thành người bình luận vì Hiếu duyệt duy nhất; mục 2.2 thêm DA-15…DA-23, DA-07 gộp vào DA-19, DA-10 gộp vào DA-15, DA-11 dời sau demo, DA-03, DA-06, DA-12 đổi theo MuJoCo; khung package `flywheel-psi0` thuộc DA-19, `flywheel-ingest` thuộc DA-22; mục 2.3 tải mới; mục 3.4, 3.5 quy trình duyệt và merge | PO (Hiếu) |
| 24/10/2026 | 0.2 | Mục 2.1: thêm `scripts/g0/`, `docs/g0/` (chủ Hưng, review Hiếu); mục 3.2: bảng tổng hợp và sổ chi phí chung không sửa trong nhánh story | PO (Hiếu) |
| 23/10/2026 | 0.1 | Bản đầu: bản đồ sở hữu đường dẫn, 14 story Pha A, quy trình git và Claude, cách theo dõi theo nhiệm vụ con | SM, PO |

## 1. Ba lớp chống "chèn code vào nhau"

Năm người cùng dùng Claude trên một repo thì xung đột đến từ ba chỗ: hai người sửa cùng file, ai đó đổi file dùng chung (schema, cấu hình, lock file) mà người khác đang dựa vào, và một phiên Claude sửa lan ra ngoài việc được giao. Ba lớp dưới đây chặn từng chỗ.

| Lớp | Cách làm | Chặn gì |
|---|---|---|
| 1 · Sở hữu đường dẫn | Mỗi thư mục có một chủ (mục 2.1), ghi trong `.github/CODEOWNERS`. Story khai "Phạm vi file"; Claude chỉ sửa trong phạm vi đó (CLAUDE.md gốc) | Hai người sửa cùng file |
| 2 · Contract trước | File dùng chung chỉ đổi qua PR nhỏ riêng của chủ sở hữu, merge trước việc dựa vào nó (mục 3.2) | Đổi schema làm vỡ việc người khác |
| 3 · Một story, một nhánh, một worktree, một phiên Claude | Mỗi người làm trong worktree riêng, rebase lên `master` hằng ngày, PR nhỏ (mục 3.3) | Phiên Claude sửa lan; nhánh sống lâu rồi xung đột lớn |

## 2. Chia việc

### 2.0 Phân công ngày 27/10/2026

[Đã chốt hướng: bốn người làm toàn bộ data flywheel, Hiếu làm phần còn lại và duyệt cuối. Cách chia là Đề xuất; Hiếu chốt khi merge PR này.]

**Ranh giới:** data flywheel là phần chạy được trên CPU với bộ giả: nhân và ba làn (`flywheel-contracts`, `flywheel-store`, `flywheel-testkit`, `flywheel-cli`, `flywheel-data`, `flywheel-eval`, `flywheel-loop`). Phần còn lại là adapter và mọi việc cần SIMPLE, Ψ₀ hay GPU (`flywheel-simple`, `flywheel-psi0`, `flywheel-lerobot`, `flywheel-nim`, docker, job GPU, thí nghiệm). Ranh giới này trùng với luật import (03 mục 7.3): làn không import adapter, nên bốn người không phải chờ máy của Hiếu.

| Người | Phần | Story | Giờ story DA và S1 (ước lượng) |
|---|---|---|---|
| **Long** | **Nhân và Vòng quyết định**: hợp đồng, kho, bộ giả, CLI, test e2e, công cụ repo và CI; RunPlan, runner, decide, acquisition, gate, holdout, sổ chi phí, báo cáo, HD; kịch bản demo | S1-08, PR `chore-restructure`, S1-10, DA-01, DA-25, DA-23, DA-28; story Epic của `runner`, `ledger`, `gate`, `decide`, `acquisition`, `reports`, HD, thống kê, backup | khoảng 70, cộng story Epic |
| **Thông** | **Dữ liệu robot**: pipeline teleop và synthetic qua 6 tầng, phát lại action, release và chia tập, export LeRobot, báo cáo dataset, cấy lỗi; vai Scrum Master | S1-07, DA-02, DA-03, DA-17, DA-21, DA-27; story Epic nạp, QA, release; SOP | khoảng 60, cộng story Epic và việc SM |
| **Hưng** | **Dữ liệu egocentric và Agent QA/QC**: pipeline egocentric (che danh tính, cắt đoạn, pose, QA, export stage 1), model phụ trợ gán nhãn và vòng thử; Agent QA/QC và bộ chấm lỗi cấy | DA-04, DA-18, DA-20, DA-31 | khoảng 75 |
| **Châu** | **Đánh giá**: tập điều kiện và chia tập, TaskDefinition và scorer của task hai bàn, chuỗi chẩn đoán, phát hiện lỗi train và offline, quy lỗi về stage, evidence card | DA-08, DA-13; story Epic `scenarios`, `scorer`, `diagnosis`, `cards` | khoảng 20, cộng story Epic (phần lớn tải của Châu) |
| **Hiếu** | **Phần còn lại**: SIMPLE, Ψ₀, ACT, DP, mọi job GPU, thí nghiệm HE, thiết bị bàn phím, sinh tự động S1 và S2, probe; tài liệu, website; duyệt và merge | S1-02, S1-03, S1-04, S1-05, S1-06, S1-09, S1-11, DA-09, DA-16, DA-19, DA-26, DA-29, DA-30, story 3.1a | khoảng 230, cộng duyệt PR (mục 2.3) |

Hưng không cần chạy SIMPLE: pipeline egocentric và Agent QA/QC code trên bộ giả và file mẫu; model phụ trợ và Nemotron chạy thật trên máy 3060 qua job.

**Dữ liệu đi giữa bốn người** (chỉ qua artifact có schema, 03 mục 7.3):

| Từ | Tới | Artifact |
|---|---|---|
| Long | Mọi người | Schema và file mẫu trong `flywheel.testkit`; `RunPlan`, `Decision`, `LedgerEntry` |
| Thông | Châu | `Episode`, `ReleaseManifest`, `DatasetRef` (scorer hiệu chỉnh trên demo của psi-data) |
| Thông | Hưng | `DatasetReport`, `ReplayReport` (Agent QA/QC đọc); bản sao cấy lỗi và `DefectManifest` (bộ chấm đọc sau khi agent chạy) |
| Hưng | Thông | Episode egocentric đã qua QA, đi vào `release` của Thông qua API công khai của làn |
| Châu | Long | `Score`, `Cluster`, `EvidenceCard` (cho `decide`) |
| Châu | Hưng | `Score`, `Cluster` (cho Agent QA/QC) |
| Hưng | Long | `QAReport` (kỹ sư đọc trong `fw review`) |
| Hiếu | Mọi người | `Trace`, `RolloutResult`, `Checkpoint`, `metrics.jsonl`, log RTC, kết quả probe |

**Luật để không đụng nhau:**

1. **Mỗi đường dẫn một chủ** (bảng mục 2.1). Hai người cùng một package thì chia theo thư mục con không chồng nhau: Thông và Hưng trong `flywheel-data`, Châu và Hưng trong `flywheel-eval`.
2. **Tệp chung trong một package do chủ package giữ**: `pyproject.toml`, `api.py`, `cli.py`, `config.py` của `flywheel-data` do Thông giữ, của `flywheel-eval` do Châu giữ. PR `chore-restructure` tạo sẵn nhóm phụ thuộc tùy chọn `egocentric` và `agentqa` cho Hưng; Hưng chỉ sửa dòng của nhóm mình. Hưng xuất API qua module riêng (`flywheel.data.ingest.egocentric.api`, `flywheel.eval.agentqa.api`) và đăng ký lệnh `fw` qua entry point riêng, không sửa `api.py`, `cli.py` của chủ package.
3. **Trong một làn vẫn gọi qua API công khai**: Hưng gọi `release`, `qa` của Thông qua hàm công khai; Hưng đọc `Score`, `Cluster` của Châu như artifact, không import module bên trong.
4. **Hợp đồng trước**: thêm hay đổi trường đi qua PR nhỏ vào `flywheel-contracts` (Long viết, Hiếu duyệt), kèm file mẫu trong testkit; người cần dùng rebase rồi làm tiếp.
5. **Không nhánh chồng nhánh**: nhánh tạo từ `origin/master`; cần code chưa merge thì dùng bản giả và file mẫu.
6. **pr-guard** chặn PR sửa ngoài "Phạm vi file" của story; `CODEOWNERS` báo chủ đường dẫn khi PR chạm phần của họ.
7. **Hiếu duyệt và merge mọi PR**; chủ đường dẫn bình luận.

**Thứ tự những ngày đầu:**

| Ngày | Việc |
|---|---|
| 28/10 | Long: merge S1-08, mở PR `chore-restructure` (mục 3.6). Người khác: đọc story, viết file story còn thiếu (Thông viết DA-01, DA-02, DA-03, DA-08, DA-13 cho chủ tương ứng), việc không chạm package (đọc dữ liệu psi-data, EgoDex; đọc code Ψ₀) |
| 29/10 | Merge `chore-restructure`. Long bắt đầu DA-25 |
| 30/10 | Merge DA-25: schema và file mẫu của mọi artifact ở bảng trên. Ba làn bắt đầu code trên file mẫu |
| Từ 2/11 | Hiếu đưa dữ liệu thật theo mốc: gói psi-data có hash (30/10), trace SIMPLE và `metrics.jsonl` đầu tiên (6/11), log eval HE (12/11) |

### 2.1 Bản đồ sở hữu đường dẫn

**Bản 0.6 (27/10/2026)** theo mục 2.0. Đường dẫn theo cây ở 03 mục 7.1 (bản 0.7); trước PR `chore-restructure` (mục 3.6) các package mới chưa tồn tại. `CODEOWNERS` cập nhật trong PR đó.

| Đường dẫn | Chủ | Bình luận |
|---|---|---|
| `packages/flywheel-contracts/`, `packages/flywheel-store/`, `packages/flywheel-testkit/`, `packages/flywheel-cli/` (nhân) | Long (Hiếu duyệt mọi thay đổi schema) | Hiếu |
| `tests/e2e/` | Long | Hiếu |
| `packages/flywheel-loop/` | Long | Châu |
| `packages/flywheel-data/` trừ các đường dẫn egocentric dưới đây | Thông | Hưng |
| `packages/flywheel-data/src/flywheel/data/ingest/egocentric/`, `annotate/deid/`, `qa/egocentric.py`, `export/egodex.py` và test tương ứng | Hưng | Thông |
| `packages/flywheel-eval/` trừ `agentqa/` | Châu | Hưng |
| `packages/flywheel-eval/src/flywheel/eval/agentqa/` (gồm `bench/`) và test tương ứng | Hưng | Châu |
| `packages/flywheel-simple/`, `packages/flywheel-psi0/`, `packages/flywheel-lerobot/`, `packages/flywheel-nim/` | Hiếu | Long |
| `configs/kernel/`, `configs/loop/` | Long | Hiếu |
| `configs/runplans/` | Long viết công cụ, Hiếu viết và duyệt RunPlan | Châu |
| `configs/data/` trừ `egocentric.yaml` | Thông | Hưng |
| `configs/data/egocentric.yaml` | Hưng | Thông |
| `configs/eval/` trừ `agentqa/` | Châu | Hưng |
| `configs/eval/agentqa/` | Hưng | Châu |
| `configs/models/`, `configs/embodiments/`, `configs/sim/` | Hiếu | Long |
| `docker/`, `compose.yaml` | Hiếu | Long |
| `pyproject.toml` gốc, `uv.lock`, `.github/`, `scripts/repo/`, `ops/` | Long | Hiếu |
| `scripts/g0/`, `docs/g0/` | Hiếu (spike G0 nay là việc của Hiếu) | Long |
| `scripts/demo/`, `docs/demo/` | Long | Hiếu |
| `docs/spec-v10-failure-to-data.md`, `docs/product/01`–`08`, `docs/superpowers/`, `docs/mentor/` | Hiếu | Thông |
| `docs/product/stories/` | Thông | Hiếu |
| `website/`, `deliverables/` | Hiếu | Long |

Chủ sở hữu không có nghĩa là người duy nhất được sửa. Người khác sửa được khi story của họ khai đường dẫn đó trong "Phạm vi file" và chủ sở hữu bình luận trên PR.

**Bản 0.3, 0.4.** Hiếu là người duyệt và merge duy nhất vào `master` (mục 3.4). Chủ đường dẫn và người ở cột thứ ba bình luận, không chặn merge. Ba làn chỉ import nhân; import-linter chặn làn import lẫn nhau (03 mục 7.3).

### 2.2 Story DA

Đặt mã `DA-xx` cho story của design; mã đã dùng không dùng lại. Bản 0.6 điền người làm theo mục 2.0. Giờ là ước lượng thô (04 mục 4.9).

| Mã | Story | Trạng thái 27/10 | Chủ | Phạm vi file chính | Phụ thuộc | Giờ | Sprint |
|---|---|---|---|---|---|---|---|
| DA-01 | Định dạng episode chung, `action_layout` của G1 (đệm 36 chiều), trường mới của Episode (design mục 6.1) | Giữ | Long (Hiếu duyệt schema; Hiếu điền giá trị `configs/embodiments/g1.yaml`) | `flywheel-contracts/` | S1-10 | 8–12 | S1 |
| DA-02 | Export LeRobot v2.1 theo `action_layout`, `stats_psi0.json`, contract test bằng loader Ψ₀ | Giữ | Thông | `flywheel-data/export/` (trừ `egodex.py`) | DA-01 | 8–12 | S2 |
| DA-03 | Pipeline teleop và synthetic: ingest, normalize, cắt đoạn, QA riêng nguồn trên psi-data, bàn phím, S1, S2; báo cáo dataset | Sửa | Thông | `flywheel-data/ingest/` (trừ `egocentric/`), `normalize/`, `annotate/` (trừ `deid/`), `qa/` (trừ `egocentric.py`), `release/` | DA-01 | 20–25 | S1–S2 |
| DA-04 | Pipeline egocentric E-A, E-B: che danh tính, cắt đoạn, pose tay và camera, QA; mẫu EgoDex, sau đó video tự quay; vòng thử model gán nhãn | Mở lại | Hưng | `flywheel-data/ingest/egocentric/`, `annotate/deid/`, `qa/egocentric.py` | DA-01 | 25–35 | S1–S2 |
| DA-05 | `NimClient`, định tuyến theo `data_class` | Hoãn sau demo | | | | | |
| DA-06 | Tầng S3: Cosmos Transfer | Hoãn sau PoC | | | | | |
| DA-07 | Log train theo nhóm action | Đã gộp vào DA-19 | | | | | |
| DA-08 | Bộ phát hiện lỗi F-TRAIN (T1–T8) và F-OFF (O1–O4) từ `metrics.jsonl` | Giữ | Châu | `flywheel-eval/diagnosis/` | DA-25 (file mẫu), DA-19 (log thật) | 8–12 | S2–S3 |
| DA-09 | Probe P1–P4 đóng băng có hash; chạy trên `pre.*`, `postpre.*` và ba VLM của HE | Sửa | Hiếu | `flywheel-psi0/` phần probe | S1-03 | 12–18 | S2–S3 |
| DA-10, DA-11, DA-12, DA-14 | Robot thay thế, cảnh trạm Isaac Sim, task khay → máy, xin thông tin DENSO | Xóa | | | | | |
| DA-13 | Quy lỗi về stage và quy tắc F-SYS trong `diagnosis` | Giữ | Châu | `flywheel-eval/diagnosis/` | DA-09 | 8–10 | S3 |
| DA-15, DA-22, DA-24 | Robot DENSO trên MuJoCo, dataset BTC, ROS 2 | Xóa | | | | | |
| DA-16 | Thiết bị bàn phím cho teleop decoupled WBC của SIMPLE, ghi episode, mục sổ chi phí mỗi phiên | Sửa | Hiếu | `flywheel-simple/teleop/` | S1-02 | 10–15 | S1–S2 |
| DA-17 | Phát lại action động học và động lực học trên MuJoCo của SIMPLE, video so sánh, ngưỡng | Sửa | Thông | `flywheel-data/replay_check/` | `SimpleSim.replay()` (code trên bản giả) | 7–11 | S1–S2 |
| DA-18 | Egocentric sang định dạng stage 1 của Ψ₀, stats, contract test bằng loader | Khôi phục, nội dung mới | Hưng | `flywheel-data/export/egodex.py` | DA-04 | 6–10 | S2 |
| DA-19 | Khung `flywheel-psi0`; đọc code train của tác giả, lớp bọc log, adapter fine-tune trên Colab, client RTC | Giữ | Hiếu | `flywheel-psi0/` | Không | 22–30 | S1–S2 |
| DA-20 | Agent QA/QC: Nemotron cục bộ, dựng hình từng stage, báo cáo HTML, bộ ca mẫu | Sửa | Hưng | `flywheel-eval/agentqa/` (trừ `bench/`), `configs/eval/agentqa/` | DA-25 (file mẫu) | 20–30 | S2 |
| DA-21 | Export LeRobot v3 từ v2.1, checklist chuẩn hóa trong contract test | Giữ | Thông | `flywheel-data/export/` (trừ `egodex.py`) | DA-02 | 4–6 | S2 |
| DA-23 | Eval bất đồng bộ trên SIMPLE, log inference RTC, dòng thời gian | Sửa | Long | `flywheel-loop/runner/` | `SimpleSim` (code trên policy giả) | 8–12 | S2–S3 |
| DA-25 | Schema và file mẫu cho artifact giữa các làn (03 mục 7.3) | Sửa | Long (Hiếu duyệt) | `flywheel-contracts/`, `flywheel-testkit/` | PR restructure | 6–10 | S1, trước 30/10 |
| DA-26 | Thí nghiệm HE: ba checkpoint ablation × lưới N, eval, đường cong, video | Mới | Hiếu | `configs/runplans/he/`, `docs/he/` | S1-03, S1-04, S1-07, DA-19 | 15–25 | S1–S3 |
| DA-27 | Bộ lỗi cấy: cấy lỗi có đáp án khóa trên bản sao dữ liệu và log thật, `DefectManifest` | Mới | Thông | `flywheel-data/inject/` | DA-01, DA-25 | 6–8 | S2 |
| DA-28 | Kịch bản demo 17/11/2026 chạy trọn luồng, mỗi phần một lệnh | Mới | Long | `scripts/demo/`, `docs/demo/` | Mọi story trên | 8–12 | S2 |
| DA-29 | Synthetic S2: biến thể từ đoạn teleop kiểu MimicGen và correction từ trạng thái lỗi | Mới | Hiếu | `flywheel-simple/generators/variants/` | S1-02, S1-06 (Q3), DA-03 | 15–20 | S2 |
| DA-30 | Stage 1 trên dữ liệu egocentric: lần chạy ngắn trên EgoDex, fine-tune trên video tự quay | Mới (tách từ DA-18) | Hiếu | `flywheel-psi0/stage1/`, `configs/runplans/stage1/`, `docs/he/stage1.md` | DA-18, DA-19 | 10–15 | S2–S3 |
| DA-31 | Bộ chấm lỗi cấy: precision, recall theo loại, báo nhầm, tách phần code và phần agent | Mới (tách từ DA-27) | Hưng | `flywheel-eval/agentqa/bench/` | DA-27, DA-20 | 5–8 | S2 |
| DA-32 | Task bê khay trên SIMPLE ở `mujoco`: cảnh, task, ngẫu nhiên hóa, vị từ 7 bước, thành công (design 28/10/2026) | Mới | Hiếu | `flywheel-simple/tray/`, `configs/sim/tray.yaml` | PR restructure | 16–26 | S1–S2 |
| DA-33 | Synthetic S1 cho task bê khay: cầm hai tay trong MP agent, `decompose()`, sinh hàng loạt, release | Mới | Hiếu | `flywheel-simple/tray/` | DA-32 | 15–30 | S2 |
| DA-34 | Thí nghiệm egocentric trên task bê khay: nhánh A, C, C-NOEGO trước demo, B sau | Mới | Hiếu | `configs/runplans/tray/`, `flywheel-psi0/tray/`, `docs/he/tray.md` | DA-33, DA-19 | 15 | S2 |

File story nằm trong `docs/product/stories/`. DA-01, DA-02, DA-03, DA-08, DA-13 chưa có file; Thông viết ngày 28/10 theo mẫu story hiện có. Việc chưa có chủ: cập nhật website và Pitch khi chuẩn bị demo 17/11 [Đã chốt: chưa làm trước đó].

**Nhiệm vụ con gợi ý** (người làm story viết đủ vào file story, mỗi dòng là một commit):

- DA-01: 1 schema Episode thêm trường mới; 2 schema `action_layout` và mask; 3 `segments.parquet`; 4 test tính chất cho validate.
- DA-03: 1 bộ đọc psi-data sang bundle chung; 2 đồng bộ thời gian và nội suy; 3 cắt đoạn theo luật; 4 QA riêng nguồn; 5 chạy trên gói task hai bàn, báo số pass, flag, reject; 6 báo cáo dataset.
- DA-09: 1 bộ câu hỏi P1 có đáp án và hash trên khung hình SIMPLE; 2 P3 trên episode held-out; 3 P4 so checkpoint cha; 4 báo cáo theo checkpoint; 5 P1 trên ba VLM của HE.

### 2.3 Tải theo người

**Bản 0.6 (27/10/2026).** Giờ của story DA và S1 theo mục 2.2 và file story (giữa khoảng, ước lượng). Story Epic 1–8 của 04 mục 4 đi theo chủ module ở mục 2.1 và chưa cộng vào bảng này; tính lại đủ ở họp cuối Sprint 1 khi có k.

| Người | Story DA và S1 | Khoảng giờ |
|---|---|---|
| Long | S1-10 10, DA-01 10, DA-25 8, PR restructure 6, DA-23 10, DA-28 10 | khoảng 55, cộng story Epic của làn Vòng (nhiều nhất trong ba làn) |
| Thông | S1-07 10, DA-02 10, DA-03 22, DA-17 9, DA-21 5, DA-27 7 | khoảng 63, cộng story Epic nạp, QA, release và việc SM |
| Hưng | DA-04 30, DA-18 8, DA-20 25, DA-31 6, vòng thử model 5 | khoảng 74 |
| Châu | DA-08 10, DA-13 9 | khoảng 19, cộng story Epic của làn Đánh giá (scorer, tập điều kiện, chẩn đoán, evidence card) |
| Hiếu | S1-02 14, S1-03 28, S1-04 20, S1-05 20, S1-06 8, S1-09 8, S1-11 8, DA-09 15, DA-16 12, DA-19 26, DA-26 20, DA-29 18, DA-30 12 | khoảng 209, cộng story 3.1a, ACT và DP, job GPU, duyệt PR |

**Hiếu vẫn quá tải** (khoảng gấp ba người khác chỉ tính phần story DA và S1). Nếu Hưng có máy chạy được SIMPLE ở chế độ MuJoCo, chuyển S1-06, S1-09, DA-16 (khoảng 28 giờ) sang Hưng là bước giảm tải đầu tiên; mọi việc này nằm trong `flywheel-simple/` và `scripts/g0/`, không chạm phần của người khác. Quy tắc giữ từ 23/10/2026: giữ đủ phạm vi; đo k sau Sprint 1; vượt thì chuyển phần trễ sang API hoặc phần có sẵn trước, rồi mới cắt.

## 3. Quy trình git khi dùng Claude

### 3.1 Phạm vi file của story

Mỗi story có mục "Phạm vi file": danh sách thư mục hoặc file được sửa. CLAUDE.md gốc yêu cầu Claude dừng lại khi cần sửa ngoài danh sách này. Người review kiểm `git diff --stat origin/master...` chỉ chạm các đường dẫn đã khai.

### 3.2 File dùng chung: contract trước

File dùng chung: `contracts/`, schema trong `configs/`, `pyproject.toml` gốc, `uv.lock`, `.github/workflows/`.

1. Người cần đổi mở issue "Contract change: …" mô tả trường cần thêm và lý do.
2. Chủ sở hữu (bản 0.7: Long giữ `flywheel-contracts`, `flywheel-testkit` theo mục 2.0, 2.1; Hiếu duyệt) làm một PR nhỏ chỉ đổi contract, kèm schema, file mẫu trong `flywheel-testkit` và test; nhánh `<story-id>-contract`.
3. PR contract merge trước. Người cần dùng rebase lên `master` rồi làm tiếp.
4. Bảng tổng hợp và sổ chi phí chung (bản 0.2): nhánh story không sửa 03 §3.3 hay một file sổ chi phí dùng chung. Story ghi kết quả và chi phí vào file của mình; chủ của bảng gom lại vào mốc cố định. Quy ước cho G0 ở [docs/g0/README.md](../g0/README.md).
5. Thêm phụ thuộc Python: người cần thêm sửa `pyproject.toml` của package mình; `uv.lock` chỉ được tạo lại bằng `uv lock` sau khi rebase, không sửa tay; xung đột ở `uv.lock` thì lấy bản của `master` rồi chạy lại `uv lock`.

### 3.3 Vòng đời một story

```text
Issue story (template) → nhánh và worktree → phiên Claude → commit theo nhiệm vụ con
→ rebase hằng ngày → PR (template) → review của chủ sở hữu → Rebase and merge → xóa nhánh, xóa worktree
```

Lệnh mẫu:

```bash
git fetch origin && git worktree add ../denso-DA-03 -b DA-03-teleop-pipeline origin/master
```

```bash
git fetch origin && git rebase origin/master
```

```bash
git worktree remove ../denso-DA-03 && git branch -d DA-03-teleop-pipeline
```

Câu mở phiên Claude gợi ý, dán vào phiên mới mở trong worktree:

```text
Đọc CLAUDE.md và docs/product/stories/DA-03-*.md. Chỉ sửa file trong "Phạm vi file" của story.
Làm nhiệm vụ con 1. Xong thì chạy kiểm tra, cho tôi xem diff và bằng chứng, rồi commit theo quy ước
"DA-03/1: ..." và đánh dấu [x] trong file story. Dừng lại chờ tôi trước khi sang nhiệm vụ con kế.
```

Dừng sau mỗi nhiệm vụ con giữ cho mỗi commit nhỏ, người làm xem được diff trước khi commit, và lịch sử khớp đúng danh sách nhiệm vụ.

### 3.4 PR và merge

- Một PR cho một story; tiêu đề `[DA-03] Teleop pipeline on psi-data`.
- Kích thước: khoảng 400 dòng thay đổi trở xuống, không tính lock file và fixture sinh ra. Lớn hơn thì tách story.
- Review (bản 0.3, thay quy tắc cũ "Hiếu không là người review duy nhất"): **Hiếu là người duyệt và merge duy nhất** vào `master`. Chủ sở hữu đường dẫn và người ở cột thứ ba của mục 2.1 bình luận, không chặn merge. Trước khi xin duyệt, PR phải xanh ở `core` và `guard`. Lịch tracking tự động (10:00, 14:00, 18:00) liệt kê PR chờ Hiếu; tổng kết 21:30 đề xuất thứ tự duyệt, ưu tiên PR đang chặn người khác và PR sửa `contracts/`.
- Không ai chờ PR của người khác để code tiếp: dùng schema trong `flywheel.contracts`, bản giả và file mẫu trong `flywheel.testkit` (trước PR restructure là `flywheel-fakes`); không tạo nhánh từ nhánh chưa merge.
- Merge bằng **Rebase and merge** để giữ từng commit nhiệm vụ con trên `master`, lịch sử thẳng. Không dùng squash, vì squash gộp mất ranh giới nhiệm vụ con.
- Bản 0.9: lệnh merge chuẩn là `gh pr merge <số> --admin --rebase`. Ruleset "Only Hiếu merges into master" (luật `update`, chỉ vai Admin bypass) chặn mọi cập nhật `master` khác, kể cả PR đã có approval, nên PR xanh vẫn hiện BLOCKED cho tới khi Hiếu merge. PR của chính Hiếu không cần approval của người khác (GitHub không cho tác giả tự approve); chủ đường dẫn vẫn bình luận.

### 3.5 Cài đặt GitHub (Hiếu làm một lần)

1. Thêm 4 người làm collaborator; điền tên GitHub vào `.github/CODEOWNERS` (các dòng đang để trống).
2. Settings → Branches → luật cho `master`: bắt buộc PR, 1 approval, review của Code Owners (bản 0.3: CODEOWNERS chỉ có dòng `*` là Hiếu; muốn bắt buộc thật thì bật "Require review from Code Owners" và tắt "Do not allow bypassing" để Hiếu merge được PR của chính mình, chờ Hiếu quyết). Ruleset "Only Hiếu merges into master" đã bật ngày 24/10/2026. Còn lại: status check (`core-ci` khi S1-01 xong, build website), lịch sử thẳng, cấm force-push và cấm xóa.
3. Settings → General → Pull Requests: chỉ bật "Allow rebase merging"; bật tự xóa nhánh sau merge.
4. Tạo label `person:hieu`, `person:hung`, `person:chau`, `person:long`, `person:thong`, `sprint:S1`–`sprint:S6`, `area:core`, `area:adapter`, `area:data`, `area:docs`, `contract-change`.
5. Tạo GitHub Project kiểu board: cột Todo, In progress, Review, Done; trường Sprint, Người, Cổng.

### 3.6 PR `chore-restructure` (bản 0.4)

Một lần, trước khi các làn viết code (design chia làn mục 8):

1. Merge S1-08 như hiện tại.
2. Long mở nhánh `chore-restructure` từ `origin/master`: tách `packages/flywheel` thành `flywheel-contracts`, `flywheel-store`, `flywheel-testkit` (gồm `flywheel-fakes`), `flywheel-cli`; tạo khung rỗng `flywheel-data`, `flywheel-eval`, `flywheel-loop`, `flywheel-simple`, `flywheel-psi0` (bản 0.5: không còn `flywheel-mujoco`, `denso-sim`); bản 0.6: tạo sẵn thư mục con và module API riêng của Hưng (`ingest/egocentric/`, `annotate/deid/`, `export/egodex.py`, `agentqa/`, `agentqa/bench/`), nhóm phụ thuộc tùy chọn `egocentric` trong `flywheel-data` và `agentqa` trong `flywheel-eval`, entry point riêng cho lệnh của Hưng; cập nhật `.github/CODEOWNERS` theo mục 2.1; chuyển test e2e ra `tests/e2e/`; sửa ruff, mypy, pytest, import-linter, CI; dời `scripts/*.py` vào `scripts/repo/` và sửa đường dẫn trong workflow, `CLAUDE.md`, `RULE.md`, `08`.
3. Chỉ di chuyển file và sửa cấu hình; không đổi logic. Bằng chứng: CI xanh, `uv run pytest` chạy cả test của testkit, `lint-imports` báo đủ các luật mới.
4. Hạn (bản 0.6): mở PR ngày 28/10, merge ngày 29/10/2026. Ngày 26–27/10 các làn làm nhiệm vụ con không nằm trong package mới (đọc, kiểm kê, `docs/g0/`).

## 4. Theo dõi và đánh giá theo nhiệm vụ con

Rule kiểm soát theo ngày (R1–R9), báo cáo ngày tự động, nhãn nguyên nhân lỗi và trang Tiến độ nằm ở [08 · Kiểm soát dự án theo ngày](08-daily-control.md). Label ở mục 3.5 được tạo bằng `bash scripts/setup_labels.sh`.

Đơn vị theo dõi là **nhiệm vụ con**: một dòng `- [ ]` trong file story, một commit `<story-id>/<số>: …`, một dòng trong checklist của issue.

| Muốn biết | Cách xem |
|---|---|
| Tiến độ mọi story theo người | `python3 scripts/progress.py` (đếm nhiệm vụ con đã đánh dấu trong file story) |
| Nhiệm vụ con nào của một story đã vào `master` | `git log origin/master --oneline --grep '^DA-03/'` |
| Ai đang làm gì | Board của GitHub Project; `gh pr list --state open` |
| Bằng chứng của một nhiệm vụ con | Thân commit và mục "Bằng chứng" của PR |

Khi review một nhiệm vụ con, chấm theo 4 câu, ghi trong PR:

1. AC liên quan có bằng chứng chạy lại được không (lệnh và output, test, file số đo)?
2. Diff có nằm trong "Phạm vi file" không?
3. Có đổi file dùng chung mà không qua PR contract không?
4. Số liệu mới có ghi là ước lượng hay thực đo không?

Thông tổng hợp trong bản tin tuần (04 mục 2.2): số nhiệm vụ con xong theo người, PR chờ review quá 2 ngày, nhiệm vụ con bị mở lại.
