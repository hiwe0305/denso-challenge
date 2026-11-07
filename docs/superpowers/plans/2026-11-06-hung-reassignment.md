# Chia lại việc của Hưng: kiến trúc và plan

> **Cho agent thực thi:** mỗi story có nhánh và worktree riêng ở máy local (mục 6). Đọc file story, file này, rồi viết plan TDD chi tiết của story trước khi sửa mã. Chưa push lên GitHub cho tới khi Hiếu bảo.

**Mục tiêu:** làm đủ ba story của Hưng (DA-04 nhiệm vụ 1–7, DA-18 nhiệm vụ 1–3, DA-20 nhiệm vụ 1–7, cùng vòng thử model gán nhãn), trừ bước che danh tính, trên máy local trước. Demo cần phần 3 (egocentric ra định dạng stage 1) và phần 4 (Agent QA/QC trên bộ lỗi cấy) của DA-28.

**Nguồn:** [Design 27/10/2026](../specs/2026-10-27-g1-psi0-demo-design.md) mục 5.0, 6, 6.7, 9, 10, 11; [03 · Kiến trúc](../../product/03-architecture.md) mục 5.4, 7.3, ADR-19, ADR-24, ADR-26; [07](../../product/07-team-workflow.md) mục 2.0–2.4; story DA-04, DA-18, DA-20; Ψ₀ ở `cda3fdf` (`src/psi/data/egodex/egodex_dataset.py`, `src/h_rdt/datasets/pretrain/precompute_48d_actions.py`, `calc_stat.py`, `scripts/train/psi0/pretrain-egodex-psi0-fast.sh`).

_Ngày 6/11/2026. Trạng thái: quyết định ở mục 3 do Hiếu chốt trong chat ngày 6/11/2026; kiến trúc ở mục 4, 5 là [Đề xuất] của Claude; giờ là ước lượng. Kết quả cuối ngày 6/11 ở mục 8. Cập nhật 7/11/2026 theo review #150: mục 1 (nhánh của Hưng), D2 (ngoại lệ chờ PO), mục 8 (đã push, đã mở PR), mục 9 (đề xuất cho PO)._

## 1. Lý do

Lúc viết plan, sáng 6/11/2026, Hưng (GitHub `KhaazixGod`) có 0/17 nhiệm vụ con, 0 commit, không nhánh, không PR. Cùng ngày lúc 17:43 Hưng push nhánh `DA-20-agent-qa-qc` với một commit `cbdfc295` (DA-20/1, endpoint cục bộ, +788 dòng), không mở PR. Phần kiểm host và opener bỏ proxy của commit đó đã được lấy vào #151 (`868312f2`, có trailer `Co-authored-by`). Trước đó, việc duy nhất là issue #34 ngày 2/11 (hợp đồng `AgentReport`, đã merge ở #46). Báo cáo ngày 5/11 ghi **Đỏ**. Châu (DA-31) chờ `AgentReport` thật cho cột agent của bộ chấm; Long (DA-28) chờ phần 3 và 4 của kịch bản. DA-30 không còn chờ DA-18: Hiếu chạy stage 1 trên dữ liệu thay thế `egodex_sample.py`.

## 2. Hiện trạng: đã có gì

| Phần | Ở đâu | Dùng được gì |
|---|---|---|
| Hợp đồng Agent QA/QC | `flywheel/contracts/agentqa.py` | `AgentReport` (facts `F1..`, findings, estimates, `status`), `AgentReview`, `FINDING_CODE`; chặn `vault/`; placeholder `{F1}` trong insight phải nằm trong evidence |
| Hợp đồng egocentric | `artifacts.py`, `segments.py` | `Episode.source_kind = egocentric`, `action_quality` (`retargeted`, `pseudo`), `deid_status`; `Segment` (`t_start`, `t_end`, `step_id`, `description`, `label_source`) |
| QA, release, báo cáo | `flywheel.data.api` | `QAReport` theo episode, `build_release`, `dataset_report`, `render_html`, `job_ledger`, `deid_blocks_annotate` |
| Chẩn đoán train | `flywheel.eval.api.diagnose_train` | T1–T8 trên `metrics.jsonl` (DA-08) |
| Bộ chấm (Châu) | `flywheel.eval.agentqa.bench` | Đọc file `AgentReport` theo spec `bench.json`; target là `episode_000012` hoặc `train/<job>`, `rtc/<job>` |
| File mẫu, model giả | `flywheel-testkit` | `AgentReport*.json`, `DatasetReport.json`, `ProbeP1..P4.json`, `RTCInferenceRecord.json`, `Score.json`, `Cluster.json`; `FakeLLM` |
| Mẫu EgoDex của DA-30 | `flywheel_psi0/stage1/egodex_sample.py`, `fwdata/egodex-da30-probe/` | Tập con tất định, manifest CRC; quyết định "Waive for EgoDex" (4/11) |
| Log thật | `~/project/denso-qaqc-archive/`, `rtx3060:~/denso-qaqc-archive/` | Đầu vào của DA-20 nhiệm vụ 7 |
| Máy | laptop RTX 3050 4 GB; `rtx3060` 12 GB có Ollama | Model chạy trên `rtx3060`, lần lượt theo job |

Thư mục của Hưng trên `master` chỉ có file khung. `uv.lock` chưa có h5py, OpenCV.

## 3. Quyết định [Đã chốt 6/11/2026, Hiếu]

| # | Quyết định |
|---|---|
| D1 | Hiếu và Claude làm ba story; làm ở máy local, chưa push |
| D2 | **Bỏ bước che danh tính**, chỉ cho mẫu EgoDex công bố (`egodex`, `public`): mở rộng "Waive for EgoDex" của DA-30 (4/11) sang pipeline DA-04. Episode giữ `deid_status = raw`, Source ghi lý do miễn. Video tự quay và mọi nguồn khác vẫn bị cổng `deid_blocks_annotate` chặn cho tới khi có bước che (sau demo). Đây là **ngoại lệ** của bất biến "video egocentric phải qua bước che danh tính trước mọi bước xử lý khác" (CLAUDE.md, 03 mục 4.3, design mục 6.6). Ngoại lệ đã ghi vào 03 (bản 1.3, mục 4.3), design (mục 6.6) và CLAUDE.md ngày 7/11/2026 (mục 9); bất biến vẫn giữ cho mọi nguồn khác. DA-04 nhiệm vụ 2 thu về: cổng và miễn trừ, không làm mờ |
| D3 | **Làm đủ, không cắt phần nào khác**: DA-04 nhiệm vụ 5, 7; DA-18 nhiệm vụ 3; DA-20 nhiệm vụ 6 (Qwen3.5-4B, thay câu trả lời "không" của Q-M ngày 3/11), 7 (log thật); vòng thử model gán nhãn |
| D4 | Mỗi story một nhánh local, một worktree từ `origin/master`; thêm `chore-egocentric-deps` |
| D5 | Pose E-A: MediaPipe Hands cộng visual odometry đơn mắt của OpenCV, gắn `pseudo` |
| D6 | Gán nhãn egocentric bằng model mở chạy cục bộ: RoboBrain 2.5-4B gợi ý ranh giới bước và viết câu lệnh ngôn ngữ, Molmo2-4B theo dõi tay, vật và chỉ điểm gắp (design 6.7.2); luật đi trước, model gợi ý, người duyệt mẫu |
| D7 | Chạy trên laptop nếu vừa; job không vừa thì để lại runbook cho Hiếu chạy sau, không tự mở job trên `rtx3060` (chốt trong chat 6/11/2026, sau khi mục 5 đã viết) |

## 4. Kiến trúc

### 4.1 Toàn cảnh

```text
                     LÀN DỮ LIỆU (flywheel-data)                                        LÀN ĐÁNH GIÁ (flywheel-eval)
EgoDex hdf5+mp4 ─┐
                 ├─► 1 Ingest ─► 3 Annotate ──────────► 4 QA ──────────► 5 Release ─► 6 Export stage 1 (DA-18)
Video tự quay ───┘   EgoSource   cổng deid + miễn D2    qa/egocentric.py  build_release   <part>/<task>/<i>.hdf5 + mp4
 (EgoVideoSource)    sha256      cắt đoạn (luật, model)   QAReport          dataset_report  actions_48d, stats, meta
                     Source      câu lệnh (model)         + phần ego của                        │
                     Episode     pose E-B | E-A           báo cáo dataset                       ▼
                                 so E-A với E-B                 │                       loader Ψ₀ (DA-30)
                                                                ▼
DatasetReport, QAReport, ReplayReport, metrics.jsonl, probe P1–P4, Score, Cluster, rtc.jsonl
                                                                │ (chỉ file artifact, không import)
                                                                ▼
                       Agent QA/QC (DA-20): inputs ─► facts (code) ─► ứng viên phát hiện (code) ─► Nemotron xếp hạng, viết
                       insight {F#}, đề xuất, ước lượng ─► kiểm số ─► AgentReport ─► HTML + hình ─► AgentReview (fw agentqa review)
                                                                │
                                                                ▼
                                              bộ chấm DA-31 (Châu): precision, recall theo loại
```

Mọi model (Nemotron, Qwen3.5-4B, RoboBrain 2.5-4B, Molmo2-4B, MediaPipe) đứng sau một Protocol trong làn và chạy trên `rtx3060` qua endpoint kiểu OpenAI hoặc job ghi file; dev và CI dùng bản giả. Làn không import torch hay mediapipe.

### 4.2 DA-04 · pipeline egocentric (`flywheel.data.ingest.egocentric`, `annotate/deid`, `qa/egocentric.py`)

| Module | Việc | Ghi chú |
|---|---|---|
| `ingest/egocentric/egodex.py` | Đọc HDF5 của EgoDex: `transforms/<joint>` (T, 4, 4, khung thế giới ARKit), `confidences/<joint>`, `camera/intrinsic`, attrs `llm_description`, `llm_type`, `which_llm_description`; 30 Hz | h5py |
| `ingest/egocentric/source.py` | `EgoDexSource` (tập con ghim trong `configs/data/egocentric.yaml`: task, số episode mỗi task, chọn tất định như DA-30), `EgoVideoSource` (mp4 cộng `device.json`); `EgoSourceRecord`: sha256 từng file, giấy phép, `data_class`, `source_id` | AC 1, 6 |
| `ingest/egocentric/episodes.py` | Sinh `Episode` (`source_kind = egocentric`, `kind = teleop_demo`, `operator_kind = human`, `action_quality` theo nguồn, `deid_status = raw`, `embodiment_id = human_hands@egodex`) và bundle `<work>/episodes/<id>/` (`pose.npz`, `segments.parquet`, link video) | |
| `annotate/deid/gate.py` | `annotate_allowed(episode, source)`: miễn cho (`egodex`, `public`) theo D2, còn lại gọi `deid_blocks_annotate` của API; ghi lý do miễn vào Source | AC 2 thu theo D2 |
| `ingest/egocentric/pose.py` | `EgoPose`: cổ tay SE(3), 5 đầu ngón, camera SE(3), độ tin theo khớp. E-B đọc từ HDF5 (`retargeted`); E-A từ `HandPoseModel` và `CameraTracker` (`pseudo`) | AC 4 |
| `ingest/egocentric/estimate.py` | E-A: MediaPipe (21 điểm ảnh cộng điểm 3D quanh tay) đổi sang khung camera bằng kích thước lòng bàn tay chuẩn; VO OpenCV (ORB, essential matrix, `recoverPose`) cho xoay và hướng tịnh tiến, thang đo lấy từ chiều cao đầu giả định. Chạy dạng job trên `rtx3060`, ghi `pose_ea.npz`; làn chỉ đọc file | D5, AC 4 |
| `ingest/egocentric/compare.py` | So E-A với E-B trên cùng khung: chiếu khớp 3D của E-B lên ảnh bằng intrinsic, sai số pixel từng khớp; sai số góc xoay tương đối của camera, góc giữa hướng tịnh tiến | AC 5, có test với đáp án biết trước |
| `ingest/egocentric/segments.py` | Luật: độ mở kẹp (khoảng cách ngón cái và ngón trỏ) và tốc độ cổ tay cho sự kiện gắp, nhả; EgoDex cắt theo gắp và đặt; video task hai bàn map vào 6 bước của task. Đoạn mơ hồ (sự kiện gần nhau, độ tin thấp) gửi `SegmentSuggester` (RoboBrain); câu lệnh mỗi đoạn từ `Labeler` (RoboBrain, Molmo2 chỉ điểm gắp), không có model thì dùng `llm_description`. Ghi `segments.parquet` theo `Segment`, `label_source` rule, model hoặc human | AC 3, D6 |
| `ingest/egocentric/review.py` | Rút mẫu đoạn cho người duyệt (seed cố định), ghi phiếu duyệt; quyết định của người đổi `label_source` thành `human` | AC 3 |
| `ingest/egocentric/vlm.py` | Client endpoint kiểu OpenAI có ảnh (base64), qua `urllib`; Protocol để thay bằng bản giả | |
| `qa/egocentric.py` | Phép kiểm: số khung tối thiểu, độ tin pose, tỉ lệ tay ra khỏi khung (chiếu lên ảnh 1920×1080), độ rung camera (vận tốc góc tần số cao), có câu lệnh, có đoạn; ngưỡng trong `configs/data/egocentric.yaml`; ra `QAReport` | AC 5 |
| `ingest/egocentric/report.py` | Phần egocentric của báo cáo dataset: số đoạn, pass, flag, reject theo phép kiểm, độ lệch E-A với E-B; gộp vào HTML của `render_html` | AC 7 |
| `ingest/egocentric/api.py`, `egocentric_cli.py` | `fw egocentric ingest`, `annotate`, `pose`, `qa`, `report`, `review`; mọi job ghi hai dòng sổ chi phí qua `job_ledger` | |
| `ingest/egocentric/trial.py` | Vòng thử model gán nhãn: 30 khung EgoDex, 30 khung render SIMPLE; sai số ranh giới bước (số khung), tỉ lệ chỉ đúng điểm gắp, VRAM, độ trễ; ghi `Decision` | DA-04 ghi chú |

### 4.2a Work dir giữa DA-04 và DA-18 [Đề xuất, chốt 6/11/2026 để hai session làm song song]

DA-04 ghi, DA-18 đọc; không bên nào import module của bên kia (DA-18 đọc file).

| Đường dẫn trong `<work>/` | Nội dung |
|---|---|
| `source.json` | `EgoSourceRecord`: `source_id`, `source_detail` (`egodex` hoặc `ego_video`), `license`, `data_class`, `root`, `files` (đường dẫn tương đối → sha256), `deid_waiver` (lý do miễn D2 hoặc `null`) |
| `episodes.jsonl` | Một `Episode` của hợp đồng mỗi dòng (`source_kind = egocentric`) |
| `egocentric/<episode_id>/bundle.json` | `episode_id`, `hdf5` (đường dẫn tuyệt đối hoặc `null` với video tự quay), `mp4`, `frames` (T), `fps` (30), `task` (tên thư mục task), `instruction`, `pose_source` (`E-B` hoặc `E-A`), `action_quality`, `pose` (`pose.npz`) |
| `egocentric/<episode_id>/pose.npz` | `camera` (T, 4, 4), `left_wrist`, `right_wrist` (T, 4, 4), `left_tips`, `right_tips` (T, 5, 3) theo thứ tự Thumb, Index, Middle, Ring, Little; `confidence_left`, `confidence_right` (T,) float32. Khung thế giới: ARKit với E-B, khung VO với E-A. Tất cả float32 |
| `egocentric/<episode_id>/segments.parquet` | Một `Segment` mỗi dòng, thêm cột `frame_start`, `frame_end` (nửa mở, theo `fps`) |
| `qa/egocentric.jsonl` | Một `QAReport` mỗi episode (`fw egocentric qa`) |

DA-18 xuất mọi đoạn của episode có `decision = pass` (tùy chọn thêm `flag`); episode không có `QAReport` thì không xuất.

### 4.3 DA-18 · export stage 1 (`flywheel/data/export/egodex.py`)

- Mỗi đoạn đã qua QA ra `<root>/part1/<task>/<i>.hdf5` cộng `<i>.mp4` cùng số khung (cắt bằng OpenCV, codec mp4v).
- HDF5 chép `transforms` của 11 khớp loader cần cùng `camera`, `camera/intrinsic`, attrs câu lệnh; thêm `actions_48d` (T, 48) float32 khung thế giới, tính bằng numpy như `precompute_48d_actions.py`. Mỗi tay 24 chiều: cổ tay xyz, xoay 6D (hai cột đầu của R), xyz của 5 đầu ngón.
- Stats theo `calc_stat.py`: delta action trong khung camera, `{"egodex": {min, max, q01, q99, mean, std}}`, 48 chiều; recipe của tác giả dùng file stats có sẵn, nên file của đội để đối chiếu.
- `meta.json`: nguồn, `action_quality`, độ tin pose, release id; không ghi `filelist_cache.pkl`.
- E-A (nhiệm vụ 3): cùng định dạng từ `pose_ea.npz`, `pseudo`.
- Contract test: loader giả cùng logic với loader Ψ₀ (ghép hdf5 với mp4, delta trong khung camera, chuẩn hóa `bounds_q99`) đọc ra đúng batch mẫu đã lưu; test có marker riêng chạy loader thật trong môi trường Ψ₀ khi có `PSI0_ROOT`.
- Episode egocentric không vào stage 3: test release và export v2.1 từ chối.

### 4.4 DA-20 · Agent QA/QC (`flywheel/eval/agentqa/`, trừ `bench/`)

| Module | Việc |
|---|---|
| `endpoint.py` | Protocol `ChatModel.complete(messages) -> str`; `OpenAIEndpoint` (Ollama, vLLM) qua `urllib`; cấu hình model, revision, nhiệt độ trong `configs/eval/agentqa/models.yaml` (đề xuất chép sang `configs/models/` qua PR của chủ) |
| `inputs.py` | Đọc artifact theo đường dẫn, nhận loại theo schema (`DatasetReport`, `QAReport`, `ReplayReport`, `TrainingMetric`, probe, `Score`, `Cluster`, `RTCInferenceRecord`), sha256; từ chối `vault/` và mọi file đọc được như `DefectManifest` |
| `facts.py` | Code tính fact theo stage: dataset (phép kiểm trượt theo nguồn, lý do QA từng episode), train (`diagnose_train` của API, loss nhỏ nhất, cuối, theo nhóm), stage 1 (P1 đúng theo loại câu hỏi), stage 3 (sai số theo nhóm, theo vị trí trong chunk), inference (độ trễ p50, p99, buffer cạn, bước nhảy ở ranh giới chunk), eval (`Score`, `Cluster`) |
| `candidates.py` | Code đề xuất ứng viên phát hiện (mã, target, fact làm bằng chứng) |
| `summarize.py` | Tóm log dài theo cửa sổ để vừa 64K |
| `prompt.py`, `configs/eval/agentqa/prompts/` | Prompt có hash; đổi prompt là phiên bản mới |
| `agent.py` | Gửi fact và ứng viên, nhận JSON: xếp hạng, insight có `{F#}`, đề xuất, ước lượng; JSON hỏng thì hỏi lại một lần rồi `broken` |
| `numbers.py` | Mọi số trong chữ phải là placeholder hoặc khớp fact; không thì `broken` kèm lý do |
| `figures.py` | SVG viết tay: phép kiểm trượt theo nguồn, đường loss, bảng ảnh stage 1 (khung, câu hỏi, câu trả lời, đáp án), action dự đoán so với thật kèm link video phát lại, dòng thời gian RTC |
| `vision.py` | Nhiệm vụ 6: Qwen3.5-4B qua endpoint thứ hai xem ảnh của bảng stage 1 và khung phát lại; chỉ thêm nhận xét chữ trích fact, không thêm số; tắt mặc định |
| `report.py`, `html.py` | Ráp `AgentReport`, HTML tĩnh dựng từ nó, đọc ghi `AgentReview` |
| `estimates.py` | Sổ ước lượng append-only; so với số đo khi có |
| `cli.py` | `fw agentqa run`, `fw agentqa html`, `fw agentqa review`, `fw agentqa estimates` |

Bộ ca mẫu ≥ 10 ca có đáp án trong `tests/contract/agentqa/` (log bình thường, loss phân kỳ, không học, chiều chết, độ trễ vượt ngưỡng, buffer cạn, chunk giật, dataset sạch, NaN, nhãn sai...). Chạy trên bộ lỗi cấy của DA-27 và chấm bằng DA-31; rồi chạy trên log thật (nhiệm vụ 7) và báo riêng trong `docs/g0/agent-qa.md`.

### 4.5 Luật import và phụ thuộc

- `flywheel.data.ingest.egocentric`, `annotate.deid`, `qa.egocentric`, `export.egodex` chỉ import nhân và `flywheel.data.api`; `flywheel.eval.agentqa` chỉ import nhân và `flywheel.eval.api`, đọc file của làn khác.
- OpenCV chỉ nạp trong hàm cần nó (cắt video, VO); MediaPipe và model VLM chỉ chạy trong job ngoài venv của workspace.
- `chore-egocentric-deps`: `egocentric = ["h5py", "opencv-python-headless"]`; `agentqa` không thêm gì (`urllib`, SVG viết tay).
- Cần trường mới trong hợp đồng thì dừng lại, ghi đề xuất PR hợp đồng; không thêm trường tạm.

## 5. Model và máy

| Model | Vai | Chạy ở | Gọi qua |
|---|---|---|---|
| Nemotron 3.5 Bolt E4B (Q4) | Agent QA/QC | `rtx3060`, Ollama | `/v1/chat/completions` |
| Qwen3.5-4B | Agent nhìn hình (nhiệm vụ 6) | `rtx3060`, Ollama hoặc vLLM, sau Nemotron | Endpoint thứ hai |
| RoboBrain 2.5-4B | Ranh giới bước, câu lệnh | `rtx3060`, vLLM, lần lượt | Endpoint VLM |
| Molmo2-4B | Theo dõi tay, vật, điểm gắp | `rtx3060`, vLLM, lần lượt | Endpoint VLM |
| MediaPipe Hands, VO OpenCV | Pose E-A | `rtx3060`, venv riêng | Job ghi `pose_ea.npz` |

Bảng trên là kế hoạch lúc đầu. Theo D7, laptop chạy mọi job nhẹ; model chỉ chạy trên `rtx3060` khi Hiếu cho phép (mục 8). Quy tắc `rtx3060`: kiểm `MemAvailable` và GPU trước khi chạy, bọc job trong `systemd-run --user --scope`, `nohup setsid`.

## 6. Nhánh local và thứ tự

| Thứ tự | Nhánh | Việc | Giờ (ước lượng) |
|---|---|---|---|
| 0 | `chore-egocentric-deps` | h5py, OpenCV headless | 1 |
| 1 | `DA-20-agentqa` | Nhiệm vụ 1–5, rồi 6, 7 | 22 |
| 2 | `DA-04-egocentric-pipeline` | Nhiệm vụ 1–7, vòng thử model | 26 |
| 3 | `DA-18-egodex-export` | Nhiệm vụ 1–3 | 8 |
| 4 | `docs-hung-reassignment` | File này, 07 bản 1.9, người làm trong ba story | 1 |

DA-04 và DA-18 cần h5py: nhánh của hai story tạo từ đầu nhánh `chore-egocentric-deps` (commit `c11b88a6`), nên commit chore phải merge trước; khi mở PR thì rebase lên `origin/master` để bỏ commit đó. Mỗi nhiệm vụ con một commit có bằng chứng và `Time-spent`.

## 7. Rủi ro

| Rủi ro | Ứng phó |
|---|---|
| Tải của Hiếu: DA-26, DA-34, DA-35 cũng hạn 12–13/11 | DA-20 trước (chặn Châu, phần 4 của demo), DA-04 và DA-18 sau |
| GPU `rtx3060` đang có job khác (8 GB đã dùng lúc 6/11) | Model chạy lần lượt; Nemotron Q4 khoảng 3–4 GB |
| VO đơn mắt không có thang đo | Gắn `pseudo`, báo độ lệch so với E-B; không dùng cho stage 3 |
| Model gán nhãn sai câu lệnh | Luật trước, người duyệt mẫu, `label_source` ghi rõ |
| Giấy phép: EgoDex CC-BY-NC-ND, Nemotron OpenMDW-1.1 | Ghi trong Source; Q-EGO-LIC vẫn mở |

## 8. Kết quả ngày 6/11/2026

Cuối ngày 6/11 cả bốn nhánh còn ở máy local. Sau đó Hiếu cho push và mở PR theo thứ tự: #149 (`chore-egocentric-deps`), #150 (nhánh tài liệu này), #151 (DA-20), #152 (DA-04) và #153 (DA-18); #152 và #153 lấy #149 làm base. Ngày 7/11 cả năm PR được sửa theo review. Gộp thử bốn nhánh lên `origin/master` (`2e57f603`) không có xung đột.

| Nhánh | Commit | Đã chạy | Còn lại |
|---|---|---|---|
| `chore-egocentric-deps` | 1 (`c11b88a6`) | h5py 3.16, OpenCV headless vào `uv.lock` | Merge trước ba nhánh dưới |
| `DA-20-agentqa` | 7 | Bộ ca mẫu 13 ca; bộ log cấy DA-27 chấm bằng DA-31 với model giả: precision 3/3 mỗi mã, 0/40 báo nhầm trên bản sạch; log thật của DA-26, DA-34 (báo riêng) | Chạy Nemotron và Qwen3.5-4B theo runbook trong `docs/g0/agent-qa.md` của nhánh; T2, T8 báo nhầm trên log thật là việc của Châu |
| `DA-04-egocentric-pipeline` | 10 | 20 episode EgoDex thật: E-A so với E-B lệch đầu ngón 43–51 px, khoảng 7 cm; RoboBrain gán 13 sự kiện luật chưa quyết; QA 13 pass, 7 flag | Vòng thử model gán nhãn (dừng giữa chừng khi `rtx3060` dành cho eval C), phiếu duyệt 8 đoạn; runbook ở `docs/g0/egocentric.md` mục 10 |
| `DA-18-egodex-export` | 5 | Export work dir thật của DA-04: 38 mẫu, 4143 khung, 53 giây trên laptop; khớp script của tác giả | Loader thật của Ψ₀ trên laptop cần FFmpeg 7 (laptop có FFmpeg 8); lệnh trong ghi chép của story |

Đề xuất hợp đồng gom từ ba nhánh (chưa làm, cần PR của chủ): `source_detail` thêm `egodex`, `ego_video`; `read_segments` nhận `frame_start`, `frame_end`; danh sách câu hỏi P1 và mảng action theo episode cho hình của DA-20; khai endpoint model trong `configs/models/`. `.github/CODEOWNERS` cần đổi theo 07 bản 1.9 trong một PR `chore-…` riêng.

## 9. Đề xuất cho Product Owner: ghi ngoại lệ D2 [Đề xuất, 7/11/2026]

D2 đang là quyết định trong chat và trong plan này. Còn 03 và design vẫn viết bất biến che danh tính mà không có ngoại lệ, và theo CLAUDE.md chỉ Product Owner được sửa hai file đó. Đề xuất Hiếu sửa trong một PR `docs-…` riêng:

| File | Chỗ sửa | Câu đề xuất |
|---|---|---|
| 03 | Mục 4.3, đoạn trường `deid_status` | "Ngoại lệ (D2, 6/11/2026): mẫu EgoDex công bố (`source_detail = egodex`, `data_class = public`) được miễn bước che; episode giữ `deid_status = raw`, Source ghi lý do miễn và sha256 của file nguồn. Mọi nguồn egocentric khác vẫn bị cổng `deid_blocks_annotate` chặn tới khi đã che." |
| 03 | Bảng change log | "7/11/2026 · 1.3 · Mục 4.3: ghi ngoại lệ che danh tính cho mẫu EgoDex công bố (D2 của plan chia lại việc của Hưng; mở rộng miễn trừ của DA-30 ngày 4/11) · PO (Hiếu)" |
| design | Mục 6.6, dòng Annotate | Thêm sau "Che danh tính trước mọi bước khác": "(trừ mẫu EgoDex công bố, D2 ngày 6/11/2026; xem 03 mục 4.3)" |
| CLAUDE.md | Bất biến "Video egocentric phải qua bước che danh tính…" | Thêm "trừ mẫu EgoDex công bố (03 mục 4.3)" |

Chưa sửa ba file này thì PR #152 vẫn đúng code: cổng chỉ miễn cho cặp (`egodex`, `public`) và ghi lý do miễn. Còn tài liệu gốc thì vẫn nói một điều khác với code.

**Đã áp dụng 7/11/2026** (nhánh `docs-d2-deid-exception`): 03 bản 1.3 mục 4.3, design mục 6.6, CLAUDE.md. Câu chữ sửa theo code đã merge ở #152, #153: miễn chỉ khi `source.json` ghi `deid_waiver` và `deid_waiver_manifest`, và mọi mp4 của nguồn khớp sha256 trong `egodex_pin.json`.
