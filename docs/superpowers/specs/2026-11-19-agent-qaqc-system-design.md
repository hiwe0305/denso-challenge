# Design: hệ Agent QA/QC chẩn đoán một vòng (DA-43)

| Ngày | Phiên bản | Nội dung | Người viết |
|---|---|---|---|
| 20/11/2026 | 0.4 | Hiếu duyệt [kiến trúc 20/11/2026](2026-11-20-agent-qaqc-architecture-design.md) bản 0.3. Từ nay mục 5.1, 5.4, 12, phần chọn model của mục 8 và luật 8 của mục 6 đọc theo tài liệu đó; cửa xin thêm công cụ rút khỏi DA-43; bản ghi lời gọi công cụ rút khỏi K3. Thân bài ở đây giữ nguyên làm lịch sử | Hiếu (soạn với Claude) |
| 20/11/2026 | 0.3 | Thêm con trỏ tới [kiến trúc 20/11/2026](2026-11-20-agent-qaqc-architecture-design.md) (**[Đề xuất]**, chờ duyệt): tài liệu đó đề xuất thay mục 5.1, 5.4, 8, 12 và luật 8 của mục 6. Nội dung các mục ở đây chưa sửa | Hiếu (soạn với Claude) |
| 19/11/2026 | 0.2 | Hiếu duyệt theo đề xuất ("Approve as proposed"): Q1–Q10 của mục 14 thành **[Đã chốt]** | Hiếu (soạn với Claude) |
| 19/11/2026 | 0.1 | Bản đầu, chờ Hiếu duyệt trước khi viết mã | Hiếu (soạn với Claude) |

_Trạng thái: **đã duyệt 19/11/2026** (bản 0.2: Q1–Q10 của mục 14 chốt theo đề xuất). Các nhãn **[Đề xuất]** trong thân bài mà mục 14 có quyết định tương ứng nay đọc là đã chốt; ngưỡng ghi "chỉnh sau lần chạy đầu" vẫn là giả định cho tới khi có số đo._ Tài liệu này sửa và mở rộng mục 9 của [design 27/10/2026](2026-10-27-g1-psi0-demo-design.md); mục 9.2 (bộ lỗi cấy) giữ nguyên. Story: [DA-43](../../product/stories/DA-43-he-agent-qa-qc.md). Nhãn quyết định theo [docs/CLAUDE.md](../../CLAUDE.md): **[Đã chốt]** là quyết định của Hiếu, **[Đề xuất]** là lựa chọn của người viết, **[Option]** là các phương án song song. Số chưa đo ghi là giả định hoặc ước lượng._

## 0. Đọc nhanh

1. Sau vòng 2, ban giám khảo yêu cầu Agent QA/QC chạy tốt và phân tích được nguyên nhân gốc của lỗi task, lỗi robot và lỗi kết quả. Agent hiện tại (DA-20, bản 3) chưa làm được việc đó: nó xét từng chủ thể riêng, không nối các stage, và mọi phát hiện đúng của nó đều là của code ([agent-qa](../../g0/agent-qa.md) mục 3.7).
2. Phần phân tích có giá trị nhất của đội tới nay là phần làm tay ở [tray.md](../../he/tray.md) mục 20.11–20.13: lỗi bộ chấm ở `approach_a` (H1), hết giờ là lỗi policy chứ không phải controller (H2), thiếu tín hiệu để xét nghiêng (H3), kiểm vùng phủ ra KỸ NĂNG YẾU. Mục tiêu của DA-43 là agent tự tới được các kết luận đó từ artifact của một vòng.
3. Cách làm **[Đề xuất]**: thêm một **lớp công cụ** bằng code (chỉ đọc, tất định) tính đúng các bảng mà đội đã tính tay; code đề xuất **giả thuyết ứng viên** từ kết quả công cụ; model chỉ giữ, bỏ, xếp hạng và giải thích, như bản 3. Một **bộ tổng hợp** nối các stage thành chuỗi nguyên nhân có xếp hạng, nêu phép kiểm rẻ nhất tách hai giả thuyết đứng đầu, và đề xuất can thiệp kèm chi phí do code tính.
4. Luật cứng giữ nguyên: model không viết số, mọi câu trích fact của code, câu trả lời hỏng không được tính công, không đọc `vault/` hay file đáp án, làn không import lẫn nhau, dữ liệu `internal` và `restricted` chỉ tới model tự host.
5. Chấm bằng bốn thứ: bộ lỗi cấy (DA-31, không được tụt), **bộ ca lịch sử** mới (đáp án là chẩn đoán đội đã viết, niêm phong như `DefectManifest`), báo nhầm trên job khỏe, thời gian và chi phí mỗi báo cáo. Phần của code và phần của model luôn báo tách nhau.
6. Câu hỏi model là **[Option]** (mục 8). Người viết đề xuất dựng hệ không phụ thuộc model, rồi đo Nemotron cục bộ và một model hosted (chỉ dữ liệu `public`) trên bộ ca lịch sử, để Hiếu chọn bằng số.

## 1. Bối cảnh

### 1.1 Agent bản 3 làm gì

Theo [agent-qa](../../g0/agent-qa.md) và mã ở `packages/flywheel-eval/src/flywheel/eval/agentqa/`:

| Điểm | Hiện trạng (đo, 12/11/2026) |
|---|---|
| Đơn vị làm việc | Một lượt cho mỗi chủ thể (dataset, `train/<job>`, `rtc/<job>`, probe, eval). Không có bước nào nhìn hai chủ thể cùng lúc |
| Phần của code | `analyze.py` dựng `FactBook` và ứng viên phát hiện từ bộ phát hiện của làn (QA tầng 4, F-TRAIN T1–T8, R1, R2, O1–O4) |
| Phần của model | Nemotron 3.5 Bolt E4B 4 GB, chỉ đọc chữ, cửa sổ server 16 384 token: giữ, bỏ, xếp hạng, viết insight và đề xuất |
| Trên bộ lỗi cấy | Bắt 30/30, nhưng `agent_adds` = 0 ở mọi loại: mọi lỗi bắt được là của code. Hai phát hiện model tự thêm đều sai (T4, đọc nhầm đơn vị) |
| Stage `eval` | `analyze_eval` chỉ đếm: số lượt, tỉ lệ thành công, bước hỏng đầu tiên, nhãn lỗi, cỡ cụm. Không đề xuất ứng viên nào |
| Nhìn hình | `vision.py` có nhưng tắt; chưa chạy với model thật |
| Thời gian | 18,6 s cho một job sạch; 266 s cho một job có 36 ứng viên; 757 s cho 40 job sạch |

### 1.2 Phân tích tay mà agent phải tới được

| Kết luận của đội | Nguồn | Cần tính gì để thấy |
|---|---|---|
| Tỉ lệ qua từng bước rơi ở `place` | tray.md 19.2 (b), 20.2; bảng `step_pass` của `eval_results` | Tỉ lệ qua 7 bước theo mức và theo run. Ví dụ `C_ALL`, 60 điều kiện: `reach_b` 0,65, `place` 0,10 (file `stage1-C_ALL-table.json`, ngoài repo) |
| Thành công theo dung sai nới | tray.md 19.2 (c) | Đếm lại ở 5; 7,5; 10; 15; 20 cm, chỉ nới nhãn `L-PLACE-POSE` |
| H1: bộ chấm gãy ở `approach_a` | tray.md 20.11 | Lượt chưa bao giờ qua `approach_a` mà khay đã sang bàn B, trong đó có lượt thành công; lặp ở ba run (7/60, 10/60, 7/60) |
| H2: hết giờ đọc là lỗi policy | tray.md 20.11 | Sai số bám theo kênh so với τ_track; τ đó cũng bị vượt ở lượt thành công, nên không phân biệt được; lệnh vận tốc có phát; quãng đường đi |
| H3: thiếu tín hiệu để xét nghiêng | tray.md 20.11 | Outcome và trace không có thời điểm lỗi, tiếp xúc, độ nghiêng lúc lỗi |
| Kiểm vùng phủ ra KỸ NĂNG YẾU | tray.md 20.12, 20.13 | Khoảng cách tới 5 điều kiện train gần nhất so với τ_cov; kiểm trong miền |

Cả sáu dòng đều là phép tính trên file đã có, cộng một bước suy luận ngắn. Không dòng nào cần model "tự nghĩ ra số". Đây là căn cứ cho cách chia việc ở mục 5.

### 1.3 Một vòng xong để lại gì trên đĩa

Kiểm trên bản chép lô `pair60k-C_ALL-60000-rp_a04c14e79dfd` (từ `rtx3060`, trong `fwdata/`, không commit):

| Artifact | File | Schema | Agent bản 3 đọc được |
|---|---|---|---|
| Outcome từng lượt | `<lô>/attempt-N/outcomes.jsonl` | **Không có hợp đồng.** Dòng JSON của adapter `flywheel_psi0`: `seed`, `level`, `success`, `failure`, `tray_pos`, `tray_quat`, `steps`, `scorer_steps` (7 giá trị đúng/sai), `sim_time_s` | Không |
| Sổ lô | `<eval>/runs.jsonl` | Không có hợp đồng: `chunk`, `level`, `attempt`, `seeds`, `began`, `wall_s`, `exit`, `finished`, `missing` | Không |
| Trace | `traces/<trace_id>/steps.jsonl` | `TraceStep` (`flywheel.contracts.trace`): `cmd_upper`, `meas_upper`, `cmd_lower`, `meas_lower`, `t_state`, `t_image`, `dropped_frames` | Không (chưa có trong danh sách của `inputs.py`) |
| Kết quả rollout | `traces/<trace_id>/rollout_result.json` | `RolloutResult` (`flywheel.contracts.v0`): `sim_success`, `infra_status`, `timing`, `usage` | Không |
| Request tới server policy | `requests.jsonl` | Không có hợp đồng: `latency_s`, `status`, `episode`, `seed` | Không |
| Video | `data/evals/…/episode_N/head_stereo_left_*.mp4`, `…right…` | mp4, **chỉ camera đầu của robot** | Không |
| Log train | `<job>/metrics.jsonl` | `TrainingMetric` | Có |
| Điểm theo bước | `scores.jsonl` | `Score` (có `step_status`, `step_enter_s`, `first_failed_step`, `failure_kind`, `level`) | Có, nhưng eval khay chưa ghi file này |
| Cụm, evidence card | `clusters.jsonl`, card | `Cluster`, `EvidenceCard` (DA-39) | `Cluster` có; card chưa |
| Dataset | `dataset_report.json`, `qa/reports.jsonl`, `episodes.jsonl`, `replay*.jsonl` | `DatasetReport`, `QAReport`, `Episode`, `ReplayReport` | Có |
| Điều kiện | `round-c70-rollouts.jsonl`, `…-conditions.jsonl` trong `configs/runplans/tray/` | File của RunPlan; entity `Condition` có `condition_seed`, `level`, `values`, `vector` | Không |
| Kết quả đã tính | `stage1-*-table.json`, `place-error-*.json`, `evidence.json` | Đầu ra của `flywheel_psi0.tray.eval_results`, `place_error`, `evidence`; không có hợp đồng | Không |

Hai hệ quả:

- **Dữ liệu eval của task khay nằm ở dạng của adapter.** Làn Đánh giá không được import adapter và chỉ đọc artifact có schema trong `flywheel.contracts` (03 mục 7.3). Muốn agent đọc eval thật thì cần một bước xuất sang hợp đồng (mục 7.2). Đây là việc đầu tiên phải quyết.
- **Các bảng đội đã tính tay nằm trong adapter và trong script ngoài repo** (`h123.py`, `step8.py`). Lớp công cụ của mục 4 đưa chúng về làn Đánh giá, tính trên artifact hợp đồng.

### 1.4 Việc của các story chạy song song

| Story | Việc | DA-43 dùng gì |
|---|---|---|
| DA-41 | Cảnh khay | Không sửa file của DA-41. Nếu cảnh có thêm camera ngoài thì mục 9 dùng được |
| DA-42 | Bộ chấm: trường mới của outcome (`failure_t`, tiếp xúc, thời điểm chốt bước, eval lặp) | Công cụ `latch_consistency`, `signal_presence`, `frames_at` đọc các trường này khi có; khi chưa có thì báo "thiếu tín hiệu" |
| DA-44 | Báo nhầm của bộ phát hiện log train | Agent dùng bộ phát hiện đã sửa qua `flywheel.eval.api.diagnose_train`; không sửa bộ phát hiện ở đây |

## 2. Mục tiêu, không làm, phản mục tiêu

**Mục tiêu**

1. Đầu vào là artifact của một vòng: ảnh và video, log train, kết quả eval, log inference của robot. Đầu ra là lời khuyên "làm gì tiếp" đặt trong vòng Failure → Data của spec mục 6: chẩn đoán theo bảng 6.9, can thiệp theo 6.10, hệ thống trước, dữ liệu sau.
2. Tới được các kết luận ở mục 1.2 từ artifact, không có người chỉ.
3. Nối các stage: một cụm lỗi eval được truy về log train, dataset và runtime của đúng checkpoint đó.
4. Với hai giả thuyết còn cạnh tranh, nêu **phép kiểm rẻ nhất** tách được chúng, kèm chi phí.
5. Đề xuất can thiệp kèm chi phí ước tính và, khi có lịch sử, tỉ lệ sửa được của loại can thiệp đó.
6. Chạy được trên CPU với model giả; báo cáo vẫn có ích khi model chỉ là `EchoModel` (phần của code đứng một mình).
7. Đo được: mỗi phiên bản agent có điểm trên bộ lỗi cấy và bộ ca lịch sử trước khi dùng.

**Không làm (trong DA-43)**

- Không tự chạy job, không tự chọn dữ liệu, không ký `Decision`. Kỹ sư vẫn duyệt (spec 6.14).
- Không sửa bộ chấm, bộ phát hiện log train hay cảnh (DA-42, DA-44, DA-41).
- Không viết adapter cho log robot thật; chỉ định chỗ cắm và câu hỏi còn mở (mục 10).
- Không đưa lên Flywheel Console; Console là package khác, làm story sau.
- Không fine-tune model của agent.

**Phản mục tiêu**

- Model viết ra một con số, hay một câu không trích fact, mà vẫn tới tay kỹ sư.
- Điểm của code được ghi cho model.
- Agent đọc `vault/`, file đáp án, hay tài liệu chẩn đoán của đội (`docs/he/`), rồi "chẩn đoán" lại đúng điều đã viết.
- Dữ liệu `internal` hay `restricted` rời khỏi máy của đội.
- Luật hay prompt được chỉnh cho khớp đúng các ca dùng để chấm.
- Báo cáo dài mà không nói bước tiếp theo.

## 3. Các cách tiếp cận

| | A. Đường ống có kế hoạch cố định | B. Agent tự gọi công cụ | C. Chỉ code |
|---|---|---|---|
| Cách chạy | Code chạy một danh sách công cụ cố định theo loại nguồn; chuyên viên từng nguồn giữ, bỏ, giải thích; bộ tổng hợp xếp hạng | Một model mạnh nhận danh sách công cụ, tự quyết gọi gì, lặp tới khi đủ | Bảng luật ánh xạ kết quả công cụ sang chẩn đoán; chữ theo mẫu; không model |
| Model cần | Nhỏ là đủ (Nemotron 4 GB đang làm đúng vai giữ, bỏ, giải thích) | Mạnh. Nemotron 4 GB gọi công cụ không ổn định: ghi nhận khi làm chat của Console ngày 16/11/2026 (ghi chép phiên, chưa có trong repo); vì vậy chat của Console để code tự chạy tra cứu | Không |
| Tới được nguyên nhân chưa lường trước | Chỉ trong phạm vi công cụ và luật đã viết | Có thể | Không |
| Lặp lại được | Có (nhiệt độ 0, file `--record`) | Kém hơn: đường đi khác nhau giữa hai lần chạy | Hoàn toàn |
| Giữ luật "không viết số" | Như bản 3 | Phải kiểm cả tham số của lời gọi công cụ | Không cần |
| Dữ liệu `internal` | Chạy được, model cục bộ | Cần model mạnh cục bộ; máy 3060 chưa có model nào như vậy đã đo | Chạy được |
| Chi phí mỗi báo cáo | Thấp, biết trước | Cao hơn, không biết trước | Gần 0 |
| Rủi ro chính | Cứng: ca mới ngoài kế hoạch thì im lặng | Bịa đường suy luận; khó chấm; phụ thuộc hosted | Ban giám khảo hỏi "agent"; không xếp hạng được khi bằng chứng mâu thuẫn |

**[Đề xuất] A, có một cửa B hẹp, và C là sàn.**

- Kế hoạch công cụ cố định chạy trước (A). Số liệu ở mục 1.2 cho thấy phần lớn giá trị nằm ở đây.
- Sau đó bộ tổng hợp được **xin thêm** tối đa một số lời gọi công cụ từ danh sách đóng (cửa B), theo luật ở mục 6. Cửa này tắt được bằng config, và tắt mặc định khi model là Nemotron 4 GB.
- Báo cáo dựng được khi model là `EchoModel` (C): mọi bảng, mọi giả thuyết ứng viên và chi phí đều có. Điểm của lớp này báo riêng, nên biết chính xác model thêm được gì.

Không đề xuất B thuần: nó cần model mạnh, tức hosted, mà dữ liệu DENSO không được tới hosted. Hệ phải chạy đủ trên model cục bộ.

## 4. Lớp công cụ

Mỗi công cụ là một hàm thuần: nhận artifact đã nạp và tham số, trả một `ToolResult` gồm các fact (tên, giá trị, đơn vị, nguồn), một bảng nhỏ và, nếu có, hình. Công cụ chỉ đọc, tất định, chạy trên CPU, không gọi model, không import adapter. Mọi fact vào `FactBook` hiện có, nên luật trích số áp nguyên.

| Công cụ | Tính gì | Đầu vào (hợp đồng) | Tái tạo phân tích nào |
|---|---|---|---|
| `step_pass_table` | Tỉ lệ qua từng bước theo mức và theo run; số bước qua liên tiếp; bước có mức rơi lớn nhất | `Score.step_status`, `level` | Rơi ở `place` (19.2, 20.2) |
| `failure_clusters` | Gom theo (bước hỏng đầu tiên, nhãn, mức) của spec 6.3; cỡ cụm; cụm lặp ở run khác | `Score`, `Cluster` | Bảng c1–c8 (20.2) |
| `relaxed_sweep` | Số lượt đạt khi nới một dung sai theo lưới khai trong config task; chỉ nới nhãn được phép | `Score` cộng số đo cuối lượt (mục 7.2) | Bảng dung sai nới (19.2 c) |
| `latch_consistency` | Lượt có bước sau đã qua, hoặc đã thành công, mà một bước trước chưa bao giờ chốt; nhãn bị tắt do chuỗi gãy | `Score.step_status`, `step_enter_s` | H1: lỗi bộ chấm ở `approach_a` |
| `trace_stats` | Sai số bám theo phần thân và theo kênh (phân vị 99) so với τ; tỉ lệ chu kỳ có lệnh vận tốc; quãng đường; thời điểm quay đầu; **cùng phép đo trên lượt thành công** để biết ngưỡng có phân biệt được không | `TraceStep` | H2: hết giờ là lỗi policy |
| `signal_presence` | Với mỗi nhãn lỗi: tín hiệu cần để xét (khai trong config task) có trong outcome và trace không | Schema của artifact, config task | H3: thiếu tín hiệu, chẩn đoán CHƯA RÕ |
| `coverage_distance` | Khoảng cách tới k điều kiện train gần nhất, τ_cov leave-one-out, kiểm trong miền | `Condition.vector`, `values` | Bước 8 (20.12) |
| `train_window` | Loss, loss theo nhóm, grad norm (trung vị, phân vị 99), nhịp đo val trong cửa sổ quanh `start_step` của một phát hiện | `TrainingMetric` | Báo nhầm F-TRAIN trên log thật (agent-qa 3.3) |
| `paired_compare` | Hiệu ghép cặp theo điều kiện giữa hai run, CI bootstrap, McNemar chính xác, Wilson | `Score` của hai run | Cách tính của 19.2 (a′) |
| `lineage` | Bảng nối: lượt eval → checkpoint → job train → release → dataset report | `Episode`, `TrainingMetric`, `Release` | Điều kiện để nối stage (mục 5.3) |
| `task_lookup` | Định nghĩa bước, điều kiện chốt, ngưỡng, nhãn lỗi của task | `TaskConfig`, `configs/eval/scorer/` | "`approach_a` cần gì" |
| `cost_lookup` | Đơn giá và chi phí đã đo của loại việc tương tự | `LedgerEntry`, `PriceBookConfig` qua `flywheel.store` | Chi phí của phép kiểm và can thiệp |
| `history_lookup` | Kết quả của can thiệp cùng loại ở vòng trước | `EvidenceCard.result`, `FixRateEvent` | "Sinh S1 quanh điều kiện lỗi đã ra F" (20.1) |
| `frames_at` | Cắt khung hình ở thời điểm lỗi, hoặc ở thời điểm chốt bước, hoặc N giây cuối khi thiếu cả hai | Video của lượt, `failure_t` (DA-42) | Đầu vào của chuyên viên nhìn hình (mục 9) |

Ghi chú:

- `coverage_distance` cần một định nghĩa khoảng cách trong làn. Bản tính tay dùng `flywheel_simple.tray.targets.distance` của adapter. **[Đề xuất]** khoảng cách chuẩn hóa trên `Condition.vector`, nhóm thành phần khai trong config task; một test đối chiếu với số của tray.md 20.12 (τ_cov mức 1 là 1,143, mức 2 là 1,524) trên file mẫu. Khi card đã có `CheckResult` `coverage_distance` thì công cụ đọc card, không tính lại.
- `paired_compare` viết lại phép tính đã có trong adapter (`eval_results`). Làn không import được adapter, nên chép phép tính và kiểm bằng test đối chiếu. Luật đọc (E1, E3, F) thuộc RunPlan, không thuộc agent: agent chỉ báo số, không tự đọc luật.
- `frames_at` cần giải mã video. `opencv-python-headless` đã có trong `uv.lock` (Console và làn Dữ liệu dùng). **[Đề xuất]** thêm vào nhóm phụ thuộc tùy chọn `agentqa` của `flywheel-eval`; gói đã có trong khóa nên theo 07 mục 3.2 không cần duyệt riêng.
- Công cụ nào thiếu đầu vào thì trả kết quả "không xét được" kèm lý do, và lý do đó là một fact. Im lặng không được đọc thành "sạch" (bài học `cleared_by_code` của bản 3).

## 5. Các agent

### 5.1 Sơ đồ

```text
gói vòng (artifact hợp đồng, có data_class)
  │  cổng dữ liệu: vault/, answers/, docs/ bị từ chối; data_class quyết định model nào được gọi
  ▼
lớp công cụ (code): kế hoạch cố định theo loại nguồn  ──►  FactBook + bảng + hình
  ▼
bộ đề xuất giả thuyết (code): bảng luật  ──►  giả thuyết ứng viên, mỗi cái có fact ủng hộ và fact phản bác
  ▼
chuyên viên từng nguồn (model): dataset · train · eval và bộ chấm · runtime và trace · nhìn hình
  │  giữ, bỏ, giải thích ứng viên của nguồn mình; ra AgentReport như bản 3
  ▼
bộ tổng hợp (model): xếp hạng chuỗi nguyên nhân qua các stage, chọn phép kiểm tách, chọn can thiệp
  │  (tùy chọn) xin thêm lời gọi công cụ từ danh sách đóng
  ▼
code: gắn chi phí, kiểm từng câu, dựng báo cáo vòng  ──►  kỹ sư duyệt (AgentReview)
```

### 5.2 Chuyên viên

Mỗi chuyên viên là agent bản 3 với prompt riêng và tập fact của một nguồn. Cửa sổ 16K giữ được vì mỗi chuyên viên chỉ thấy nguồn của mình.

| Chuyên viên | Nguồn | Ứng viên do code đề xuất |
|---|---|---|
| Dataset | `DatasetReport`, `QAReport`, `ReplayReport` | D1–D8 như bản 3 |
| Train | `TrainingMetric`, `TrainDiagnosis` | T1–T8 (bộ phát hiện sau DA-44), kèm `train_window` |
| Eval và bộ chấm | `Score`, `Cluster`, card | Cụm lỗi; lỗi chuỗi bước (`latch_consistency`); thiếu tín hiệu (`signal_presence`); kết quả nới |
| Runtime và trace | `TraceStep`, `RTCInferenceRecord`, `RolloutResult` | R1–R6; sai số bám; ngưỡng không phân biệt được |
| Nhìn hình | Khung hình của `frames_at` | Câu trả lời đóng cho câu hỏi cố định (mục 9) |

Ba chỗ sửa so với bản 3, nhắm đúng ba lỗi đã đo (agent-qa 3.7):

- Mục model tự thêm phải trích ít nhất một fact **thuộc chính mã hay giả thuyết đó**. Hai T4 sai của bản 3 không trích fact T4 nào.
- Bỏ một ứng viên mà fact chiều của nó (`<mã>_flag_when`) đang đúng thì phải trích một fact phản bác; không có thì mục bỏ bị từ chối. Sáu lần bỏ tự mâu thuẫn của bản 3 rơi vào đây.
- Một phát hiện cho mỗi `(mã, target)` giữ nguyên, nhưng bằng chứng gộp đủ các chiều, không chỉ chiều xếp đầu.

### 5.3 Bộ tổng hợp

Bộ tổng hợp không thấy artifact thô. Nó nhận: phát hiện đã qua kiểm của các chuyên viên, bảng `lineage`, và danh sách **giả thuyết ứng viên** do code dựng.

**Giả thuyết ứng viên.** Một bảng luật trong config ánh xạ dấu hiệu của công cụ sang chẩn đoán của spec 6.9 (`Diagnosis` của hợp đồng evidence card). Ví dụ, viết theo đúng các ca đã gặp:

| Dấu hiệu (fact của công cụ) | Giả thuyết | Chẩn đoán | Can thiệp được phép |
|---|---|---|---|
| Bước trước chưa chốt mà bước sau đã qua, có cả lượt thành công, lặp ở nhiều run | Điều kiện chốt của bộ chấm quá chặt | `unknown` (ngưỡng bộ chấm) | `repair_ticket` |
| Nhãn lỗi cần tín hiệu mà outcome không ghi | Không xét được | `unknown` (thiếu tín hiệu) | `repair_ticket` |
| Sai số bám vượt τ, và τ **không** bị vượt ở lượt thành công | Controller | `controller` | `repair_ticket` |
| Sai số bám vượt τ, nhưng τ cũng bị vượt ở lượt thành công; lệnh có phát | Policy, không phải controller | sang bước 5–8 | — |
| Trong miền, d ≤ τ_cov, planner làm được | Kỹ năng yếu | `weak_skill` | `teleop_correction` |
| d > τ_cov | Thiếu vùng phủ | `coverage_gap` | `sim_s1`…`sim_s4` |
| Ngoài miền train | Ngoài miền | `out_of_domain` | `report_only` |
| Phát hiện T hoặc D trên đúng job và dataset của checkpoint (qua `lineage`) | Nguyên nhân ở stage trước | theo mã | theo mã |

Thứ tự của bảng theo spec 6.4: hệ thống và bộ chấm trước, dữ liệu sau. Một cụm còn giả thuyết hệ thống chưa bị loại thì không được đề xuất tiêu ngân sách dữ liệu; code chặn, không phải model.

**Việc của model.** Với mỗi cụm lỗi lớn (theo cỡ), model:

1. xếp hạng các giả thuyết ứng viên thành chuỗi nguyên nhân, mỗi mắt xích trích fact;
2. chọn, từ **danh mục phép kiểm** của config, phép kiểm tách hai giả thuyết đứng đầu;
3. chọn một can thiệp trong tập mà `INTERVENTIONS_OF_DIAGNOSIS` cho phép.

Model không được tạo loại giả thuyết mới. Nó được ghi một mục "khác" kèm fact, và mục đó luôn là `report_only`.

**Danh mục phép kiểm.** Mỗi dòng: tên, tách được cặp chẩn đoán nào, cần gì, chi phí. Chi phí lấy từ `cost_lookup` (sổ chi phí và bảng giá), không do model viết. Ví dụ từ vòng `C_70`: chạy planner trên điều kiện lỗi (bước 5) tốn 0 CU và 58–85 s mỗi lượt (đo, tray.md 20.12); kiểm vùng phủ chạy trên CPU trong vài giây (đo, 20.12); bước 7 theo phương án (b) của R9 ước khoảng 4 CU và 2 giờ (ước lượng, 20.12). "Rẻ nhất" là dòng có chi phí thấp nhất trong các dòng tách được cặp đó; code sắp xếp, model chọn trong danh sách đã sắp và nêu lý do.

**Chi phí và lợi ích của can thiệp.** Code dựng `InterventionProposal` (hợp đồng DA-39): `Cost` với `measure_kind = estimated` trỏ về dòng sổ, và `ExpectedGain` theo công thức spec 6.10 khi đủ tham số. Model chỉ chọn loại và viết lý do. Khi `history_lookup` có kết quả của cùng loại can thiệp, fact đó bắt buộc xuất hiện cạnh đề xuất.

### 5.4 Cửa xin thêm công cụ

Sau lượt đầu, bộ tổng hợp được gửi một danh sách `requests`: tên công cụ và tham số. Giới hạn **[Đề xuất]**: tối đa 6 lời gọi, một vòng; tắt mặc định với Nemotron 4 GB. Code kiểm rồi chạy; kết quả thành fact mới và bộ tổng hợp trả lời lại một lần. Luật ở mục 6.

## 6. Luật trích số, mở rộng cho lời gọi công cụ

Luật của bản 3 giữ nguyên: số trong câu phải là giá trị của một fact mà chính mục đó trích; câu trả lời sai được gửi lại một lần; lô sai hai lần không góp gì và báo cáo là `broken`. Thêm:

| # | Luật | Vì sao |
|---|---|---|
| 1 | Kết quả công cụ chỉ tới model dưới dạng fact có id. Model không thấy bảng thô ngoài `FactBook` | Một đường duy nhất cho mọi con số |
| 2 | Tham số của lời gọi công cụ do model xin phải là một trong ba loại: giá trị trong tập đóng khai sẵn (tên bước, nhãn, run, mức, lưới dung sai của config); id của một đơn vị có trong đầu vào; hoặc id của một fact. Số viết tay bị từ chối | Tham số là một con số model có thể bịa. Ví dụ: xin `relaxed_sweep` ở "0,12 m" không được; phải chọn trong lưới của task |
| 3 | Mỗi lời gọi ghi một dòng: công cụ, tham số, sha256 của đầu vào, id các fact sinh ra, ai gọi (kế hoạch hay model) | Kiểm lại được; biết model có tự tìm ra gì không |
| 4 | Fact mang **nguồn gốc**: `code` (công cụ tính), `vision` (model nhìn hình trả lời), `history` (kết quả vòng trước). Giả thuyết chỉ có fact `vision` ủng hộ thì không được xếp hạng 1 | Câu trả lời của model nhìn hình không phải số đo |
| 5 | Mỗi câu của bộ tổng hợp phải trích ít nhất một fact, kể cả câu không có số. Hiện chỉ câu có số bị kiểm | Yêu cầu "mọi câu trích fact của code" |
| 6 | So sánh hai đại lượng phải trích một **fact so sánh** do code dựng (ví dụ `tracking_p99_exceeds_tau: true`), không tự so hai fact | T4 sai của bản 3: model so `steps_logged` (đơn vị `rows`) với `train_last_step` (đơn vị `steps`) |
| 7 | Chi phí, lợi ích kỳ vọng và xếp hạng "rẻ nhất" do code gắn sau khi model chọn; model không viết chúng | Lời khuyên có số thì số phải của code |
| 8 | Lời gọi bị từ chối, hay câu trả lời lần hai còn sai, làm phần tổng hợp `broken`. Báo cáo của các chuyên viên đã qua vẫn giữ | Như luật "lô đã qua giữ quyết định" của bản 3 |

Luật 6 không kiểm được hết bằng máy (câu chữ tự do). Phần kiểm được: câu có từ so sánh và trích hai fact khác đơn vị mà không trích fact so sánh nào thì bị từ chối. Phần còn lại do bộ ca lịch sử và người duyệt bắt; ghi là giới hạn.

## 7. Đầu ra và hợp đồng

### 7.1 Dùng lại

| Thứ | Dùng lại thế nào |
|---|---|
| `AgentReport` | Mỗi chuyên viên vẫn ra một `AgentReport` cho mỗi chủ thể. Không đổi trường nào. Bộ chấm DA-31 đọc như cũ |
| `AgentReview` | Kỹ sư duyệt từng phát hiện như cũ |
| `Diagnosis`, `InterventionKind`, `INTERVENTIONS_OF_DIAGNOSIS` | Từ vựng của giả thuyết và can thiệp; agent không có từ vựng riêng |
| `InterventionProposal`, `Cost`, `ExpectedGain` | Dạng của đề xuất can thiệp |
| `CheckResult`, `CheckName` | Phép kiểm của bước 4–8; công cụ ra kết quả theo dạng này khi phép kiểm có tên trong `CheckName` |
| `EvidenceCard` | Agent **đọc** card đã có. Agent **không ghi** card: card mang `decision` của kỹ sư và thuộc đường của vòng lặp. Đề xuất của agent là bản nháp cho người dựng card |
| `LedgerEntry` | Mỗi lần chạy vẫn ghi một dòng ước tính và một dòng thực đo |

### 7.2 Đổi hợp đồng cần xin (đề xuất PR, chưa làm)

Theo 07 mục 3.2: mở issue "Contract change", PR nhỏ trên nhánh `DA-43-contract`, kèm file mẫu trong testkit, merge trước. Trong lúc chờ, mã của làn chạy trên file mẫu; không thêm trường tạm trong mã làn.

| # | Đổi | Lý do | Phụ thuộc |
|---|---|---|---|
| K1 | Outcome của một lượt eval thành artifact có hợp đồng: seed và mức của điều kiện, nhãn lỗi, các số đo cuối lượt có tên (khoảng cách và sai số góc tới đích, vật có trên bàn đích), `sim_time_s`, đường tới video; cùng các trường DA-42 thêm (`failure_t`, tiếp xúc, thời điểm chốt bước, chỉ số lần lặp) | `outcomes.jsonl` hiện là dạng riêng của adapter (mục 1.3). Không có K1 thì agent không đọc được eval khay | Làm **chung một PR với DA-42** để không có hai lần đổi cùng chỗ. Cần Hiếu điều phối |
| K2 | Artifact mới `RoundDiagnosis` trong `flywheel.contracts.agentqa`: chủ thể là một vòng; `data_class`; danh sách `report_id` của chuyên viên; giả thuyết (id, `Diagnosis`, ghi chú loại con, cụm, hạng, fact ủng hộ, fact phản bác, câu giải thích); phép kiểm tách (tên, tách cặp nào, `Cost`); đề xuất (`InterventionProposal`, cho giả thuyết nào); `status` và `problems` như `AgentReport` | Chuỗi nguyên nhân qua nhiều chủ thể không vừa `AgentReport`: `FINDING_CODE` chỉ nhận mã D, T, O, R, và một báo cáo chỉ có một `subject_ref` | Không |
| K3 | Bản ghi lời gọi công cụ (`AgentToolCall`) và hai trường đã nêu thiếu ở agent-qa mục 6: phiên bản agent, nguồn gốc của phát hiện và của fact (`code`, `hint`, `vision`, `history`) | Luật 3 và 4 của mục 6; bộ chấm tách code và model mà không phải chạy lại lớp code | Có thể gộp vào K2 |

Không đổi: `AgentFinding`, `FINDING_CODE`, `Stage`, `EvidenceCard`.

Trước khi K1 merge, eval thật được đưa vào bằng một lệnh xuất của adapter (`flywheel_psi0`, đường dẫn của Hiếu) ghi `scores.jsonl` theo hợp đồng `Score` đang có. `Score` đã mang trạng thái từng bước, bước hỏng đầu tiên, nhãn và mức, đủ cho `step_pass_table`, `failure_clusters`, `latch_consistency`. `relaxed_sweep` và `frames_at` chờ K1.

### 7.3 Báo cáo cho người

Một trang HTML tĩnh cho mỗi vòng, dựng từ `RoundDiagnosis` và các `AgentReport`:

1. Ba dòng đầu: nguyên nhân xếp hạng 1, phép kiểm rẻ nhất nên chạy, can thiệp đề xuất kèm chi phí.
2. Chuỗi nguyên nhân theo cụm, mỗi mắt xích mở ra fact và hình.
3. Thứ **không xét được** và vì sao (thiếu tín hiệu, thiếu artifact).
4. Bảng của công cụ (tỉ lệ qua từng bước, dung sai nới, cụm).
5. Liên kết tới báo cáo của từng chuyên viên, ứng viên bị bỏ, lời gọi công cụ.

Mọi số trên trang là giá trị fact do code chèn, như `{F#}` của bản 3.

## 8. Model [Option]

Số đo dưới đây lấy từ repo, trừ chỗ ghi khác.

| | M1. Nemotron 3.5 Bolt E4B 4 GB, cục bộ | M2. Model lớn hơn, cục bộ trên `rtx3060` (12 GB) | M3. Model hosted, chỉ dữ liệu `public` | M4. Lai: chuyên viên cục bộ, bộ tổng hợp theo `data_class` |
|---|---|---|---|---|
| Đã đo | 30/30 trên lỗi cấy, mọi cái là của code; 2 mục tự thêm đều sai; 18,6 s mỗi job sạch; 3,4 GB VRAM; cửa sổ 16K (agent-qa 3.7) | Chưa đo cho việc này. Ghi chép phiên Console 16/11/2026 (chưa có trong repo): một model 27B lượng tử thấp nạp được nhưng tràn sang CPU, 22–33 s mỗi câu hỏi có ảnh, và đẩy Nemotron khỏi VRAM | Chat của Console qua OpenRouter, `nvidia/nemotron-3.5-super-vl:free`: 1–4 s mỗi câu; gói miễn phí hết lượt sau khoảng 60–70 lượt mỗi ngày ([kịch bản demo](../../demo/2026-11-17-kich-ban-video.md)). Chưa đo cho việc chẩn đoán | Chưa đo |
| Dữ liệu được dùng | Mọi lớp | Mọi lớp | Chỉ `public` | Chuyên viên: mọi lớp. Bộ tổng hợp hosted chỉ khi cả gói là `public`; không thì cục bộ |
| Gọi công cụ | Không ổn định (ghi chép phiên Console); cửa B tắt | Chưa biết | Kỳ vọng dùng được; chưa đo | Cửa B chỉ mở ở nhánh hosted |
| Chi phí | Điện và thời gian máy dùng chung | Như M1, chậm hơn; tranh GPU với eval và sinh dữ liệu | Miễn phí thì bị giới hạn lượt; trả tiền thì chưa có báo giá trong repo (cần ước lượng trước khi chọn) | Giữa M1 và M3 |
| Lặp lại | Nhiệt độ 0, digest ghim | Như M1 | Nhà cung cấp có thể đổi model sau tên; phải ghi `--record` | Như từng nhánh |
| Rủi ro | Xếp hạng và giải thích yếu; đã thấy câu tự mâu thuẫn | Chiếm máy; chưa chắc tốt hơn | Dữ liệu ra ngoài (dù là `public`); giới hạn lượt làm hỏng buổi demo; DENSO không dùng được | Hai đường mã phải chấm riêng |

**[Đề xuất]** Dựng hệ không phụ thuộc model (đã có giao diện `ChatModel`, `--record`, `--replay`), rồi trong tuần đầu đo M1 và M3 trên bộ ca lịch sử (mục 11.2), cùng prompt, cùng công cụ. Hiếu chọn sau khi có số. Nếu phải chọn trước khi đo: M4, vì M1 đã cho thấy giới hạn ở đúng phần cần nhất (xếp hạng, tự thêm), còn dữ liệu DENSO buộc phải có đường cục bộ.

**Chặn cứng cho `internal` và `restricted` [Đề xuất, không tùy chọn].** Hiện `endpoint.check_local_url` từ chối mọi host ngoài mạng của đội ngay khi đọc config. Đường hosted, nếu Hiếu cho mở, phải qua đủ các điều sau:

1. Một khối config riêng `hosted`, tắt mặc định. Khối `models` cục bộ không nhận URL ngoài mạng, như hiện nay.
2. Gói vòng khai `data_class`. Code kiểm lại trên mọi `Episode` và `Source` mà gói trỏ tới. Một bản ghi không phải `public`, hoặc **không rõ lớp**, thì cả gói không phải `public`. Mặc định là từ chối.
3. Gói không phải `public` mà config bật hosted: dừng trước lời gọi đầu tiên, mã thoát khác 0, có test.
4. Adapter log robot thật (mục 10) luôn đóng dấu `internal`; không có cờ nào hạ lớp.
5. Mỗi `RoundDiagnosis` ghi `data_class` và host của model đã gọi; sổ chi phí ghi cùng.
6. Fact loại `history` chỉ kéo từ vòng có cùng lớp hoặc lớp thấp hơn, để dữ liệu `internal` không rò qua lịch sử vào một gói `public`.

## 9. Nhìn hình

**Hiện có.** `vision.py`: gửi tối đa 6 ảnh tới một model thứ hai, câu mô tả thành fact chữ, câu có số bị bỏ. Chưa chạy với model thật. Video của eval khay chỉ có camera đầu của robot (mục 1.3).

**[Đề xuất]**

- Ảnh vào từ `frames_at`: quanh `failure_t` khi DA-42 có; trước đó, quanh thời điểm chốt bước cuối và N giây cuối.
- Thay mô tả tự do bằng **câu hỏi đóng** khai trong config task, trả lời `có`, `không` hoặc `không rõ`. Ví dụ: "Khay có nằm trên bàn B không?", "Hai tay có đang cầm tay cầm không?", "Có vật rơi khỏi khay không?".
- **Hiệu chỉnh bằng câu hỏi code đã biết đáp án.** Một phần câu hỏi có đáp án từ outcome (khay trên bàn B, lượt thành công). Tỉ lệ model nhìn hình trả lời khớp code trên các câu đó là thước đo độ tin của nó trên task này, và không tốn công gán nhãn. Dưới ngưỡng **[Đề xuất: 90 %, giả định, chỉnh sau lần đo đầu]** thì fact `vision` của loại câu hỏi đó không được dùng.
- Fact `vision` chỉ **ủng hộ**; không một mình đưa giả thuyết lên hạng 1 (mục 6, luật 4). Khi code có đáp án cho cùng câu hỏi, lấy của code và ghi chỗ lệch.

**Model [Option].**

| | Trạng thái |
|---|---|
| RoboBrain 2.5-4B, cục bộ | Đã chạy trên `rtx3060` cho egocentric (DA-04). Ghi chép phiên 16/11/2026: khoảng 3,7 GB VRAM, khoảng 2 s mỗi câu hỏi có ảnh (chưa có trong repo) |
| Qwen3.5-4B, cục bộ | Khai trong `agent.yaml`, chưa chạy lần nào |
| Model hosted có ảnh | Chỉ khi gói là `public`; như M3 |

**Giới hạn.** Camera đầu có thể không thấy khay lúc đặt. Phép hiệu chỉnh ở trên sẽ cho biết điều đó trước khi đội dựa vào nó. Nếu tỉ lệ khớp thấp vì góc nhìn, việc cần là một camera ngoài trong cảnh eval (câu hỏi cho DA-41), không phải model khác. Nhìn hình vì thế là nhiệm vụ cuối của story, và có thể rút khỏi DA-43 mà không ảnh hưởng phần còn lại.

## 10. Log robot thật: chỗ cắm adapter

DENSO có thể gửi log robot thật; định dạng chưa biết, câu hỏi đã gửi mentor. Thiết kế chỉ giữ chỗ:

- Agent và công cụ chỉ thấy artifact hợp đồng. Một **adapter** (package adapter, không nằm trong làn) đổi log của DENSO sang `TraceStep`, `RTCInferenceRecord`, outcome của K1 và `Episode` với `data_class = internal`.
- Tín hiệu thiếu không làm hỏng lần chạy: `signal_presence` liệt kê công cụ nào không chạy được và vì sao, và bộ tổng hợp ghi CHƯA RÕ (thiếu tín hiệu) đúng như H3.
- Với gói `internal`, chỉ model cục bộ được gọi (mục 8).
- DA-43 chỉ làm một **gói giả** trong testkit: trace thiếu kênh, không video, không nhãn bước; để kiểm agent xuống cấp đúng cách.

Câu hỏi còn mở, cần trước khi viết adapter:

| # | Câu hỏi | Ảnh hưởng |
|---|---|---|
| 1 | Định dạng file (rosbag, MCAP, CSV, log riêng của bộ điều khiển) và tần số ghi | Cách đọc, cỡ dữ liệu |
| 2 | Có cả lệnh và giá trị đo của từng khớp không; tên khớp, đơn vị, thứ tự | `trace_stats` (sai số bám) cần cả hai |
| 3 | Đồng hồ: một nguồn hay nhiều; có dấu thời gian của ảnh không | Kiểm đồng bộ (R4) |
| 4 | Có log phía policy không: thời điểm gửi quan sát, nhận chunk, mức buffer | R1, R2 |
| 5 | Camera nào, độ phân giải, có ghi trong lúc lỗi không; video có người trong khung không | Nhìn hình; che danh tính trước mọi xử lý |
| 6 | Ai gán thành công hay thất bại, theo tiêu chí nào; có nhãn bước hay thời điểm lỗi không | Không có thì không có bảng theo bước; chỉ còn chẩn đoán hệ thống |
| 7 | Task và điều kiện đầu của mỗi lượt có được ghi không | Gom cụm, kiểm vùng phủ |
| 8 | Robot nào (bậc tự do, tay kẹp), bộ điều khiển nào | `EmbodimentConfig`, ngưỡng τ |
| 9 | Dữ liệu được lưu và xử lý ở đâu; có được rời máy của DENSO không | Agent chạy tại chỗ hay trên máy của đội |
| 10 | Khối lượng: bao nhiêu lượt, bao nhiêu giờ | Thời gian chạy công cụ |

## 11. Đánh giá

Mỗi phiên bản agent (đổi prompt, model, công cụ, bảng luật) phải có đủ bốn phần trước khi dùng. Mọi bảng tách ba cột: **lớp code** (model là `EchoModel`), **agent** (có model), **model thêm** (agent trừ code).

### 11.1 Bộ lỗi cấy (DA-31), chống tụt

Chạy lại như agent-qa mục 5.1. Mốc là bản 3: recall 30/30, báo nhầm trên bản sạch 1/40 (cận trên), precision 3/3 ở 9 mã và 3/4 ở T4. Điều kiện qua **[Đề xuất]**: recall không giảm; hai T4 sai biến mất (luật "fact thuộc chính mã đó"); không có lần bỏ tự mâu thuẫn nào trong `dropped.jsonl`. Mã của bộ chấm (`agentqa/bench/`, của Châu) không sửa.

### 11.2 Bộ ca lịch sử (mới)

**Một ca** gồm: gói artifact của một vòng đã qua, đúng như lúc đội phân tích, và một **đáp án** rút từ chẩn đoán đội đã viết.

**Đáp án** là danh sách điểm chốt có cấu trúc, không phải văn xuôi. Mỗi điểm: loại (phát hiện, chẩn đoán, phép kiểm, can thiệp, "không xét được"), đối tượng (cụm, bước, run), giá trị (`Diagnosis`, tên phép kiểm, `InterventionKind`), và câu gốc kèm mục của tài liệu. Ví dụ cho ca vòng `C_70`: rơi ở `place`; chuỗi bước gãy ở `approach_a` là `unknown` (ngưỡng bộ chấm) với `repair_ticket`; c3 và c8 không phải `controller`; c4 và c5 là `unknown` (thiếu tín hiệu); c1 là `weak_skill`.

**Niêm phong**, như `DefectManifest`:

- Đáp án nằm trong thư mục `answers/` ngoài gói, có sha256. `inputs.py` đã từ chối mọi đường có phần `answers` hay `vault`.
- Thêm `docs` vào danh sách từ chối của agent: chẩn đoán gốc nằm ở `docs/he/`.
- Chỉ module chấm ca (`agentqa/casebench/`, mới, tách khỏi `bench/` của DA-31) đọc đáp án, và chỉ sau khi mọi báo cáo của lượt chạy đã ghi xong. Test rào quét các module khác, như `test_bench_barrier.py`.
- Trước khi mở đáp án, mọi ref mà lượt chạy nói đã đọc được kiểm rò (`AnswerLeak` của DA-31).
- Gói của ca không chứa file kết quả đã tính của đội (`h123-*.json`, `step8-*.json`, `evidence.json`): agent phải tự tính.

**Ca ứng viên** (cần kiểm artifact còn đủ; nhiệm vụ 6.1):

| Ca | Nguồn đáp án | Điểm chốt chính | Tập |
|---|---|---|---|
| Vòng `C_70`, bước 4 | tray.md 20.2, 20.11 | H1, H2, H3; rơi ở `place` | Phát triển |
| Vòng `C_70`, bước 5 và 8 | tray.md 20.12, 20.13 | Vùng phủ, KỸ NĂNG YẾU, một lượt NGOÀI MIỀN | Phát triển |
| Bốn run 60k, giai đoạn 1 | tray.md 19.2 và kết quả theo luật đó | Số theo bước và dung sai nới; H1 lặp ở ba run | Kiểm |
| Eval C trên SimReady và card `L-PLACE-POSE` của C+ | tray.md 16, 17.2 | Cụm chính, can thiệp đã chọn | Kiểm |
| Kiểm pipeline ảnh và chuỗi train/serve | tray.md 14, 15 | Lỗi hệ thống tìm trước dữ liệu | Kiểm |
| Task hai bàn | [two-table-diagnosis](../../he/two-table-diagnosis.md) | Chẩn đoán của tài liệu đó | Kiểm |
| Ba job fine-tune khỏe | agent-qa 3.3 | "Job khỏe; T1, T2, T8 là báo nhầm của bộ phát hiện" | Kiểm |

Kết quả thi lại của `C70_R1` **không** đưa vào bộ ca, theo quyết định ngày 16/11/2026 không trình bày kết quả đó. Hiếu quyết nếu muốn khác.

**Chống chỉnh theo đề.** Người viết luật và prompt đã đọc các chẩn đoán này, nên rò qua người là rủi ro thật. Hai rào: tập **phát triển** dùng khi viết luật, tập **kiểm** chỉ chạy khi một phiên bản đã đóng, và số của tập kiểm báo riêng; đáp án của tập kiểm do một người viết từ tài liệu mà không xem bảng luật. Với 7 ca và ước lượng 25–35 điểm chốt, kết quả báo bằng **số đếm**, không bằng tỉ lệ có vẻ chính xác.

**Chấm.**

| Số đo | Cách tính |
|---|---|
| Điểm chốt tới được | Điểm của đáp án có một giả thuyết, phép kiểm hay đề xuất khớp đối tượng và giá trị. Khớp trên trường có cấu trúc, không trên chữ |
| Hạng | Với mỗi cụm có đáp án: chẩn đoán đúng đứng hạng mấy |
| Khẳng định sai | Giả thuyết trong ba hạng đầu mà đáp án ghi rõ là không đúng (ví dụ `controller` cho c3) |
| Phép kiểm | Phép kiểm agent chọn có nằm trong các phép đội đã chạy cho cặp đó không; chi phí so với phép đội chọn |
| Giải thích | Kỹ sư duyệt bằng `AgentReview` (`agree`, `override`) |

Điều kiện qua **[Đề xuất, chỉnh sau lần chạy đầu]**: trên tập phát triển, lớp code một mình tới được H1, H3 và mức rơi ở `place`; agent không có khẳng định sai nào ở hạng 1. Tập kiểm chỉ báo số, không đặt ngưỡng ở bản đầu.

### 11.3 Báo nhầm trên job khỏe

| Đầu vào khỏe | Kỳ vọng |
|---|---|
| Bản sạch của bộ lỗi cấy (40 job) | Không quá mốc 1/40 |
| Ba job fine-tune thật (agent-qa 3.3), sau khi DA-44 sửa bộ phát hiện | Không có giả thuyết stage train nào ở hạng 1 |
| Gói chỉ gồm lượt thành công | Không có chuỗi nguyên nhân; riêng lượt thành công mà chuỗi bước gãy vẫn phải được nêu (đó là H1) |
| Hai run cùng cấu hình, khác seed eval | Không có giả thuyết "khác nhau có ý nghĩa" khi CI của `paired_compare` chứa 0 |

Báo số giả thuyết hạng 1 trên mỗi gói khỏe. Số này là cận trên, như ở DA-31: gói "khỏe" vẫn có thể mang lỗi thật.

### 11.4 Thời gian và chi phí mỗi báo cáo

Từ sổ chi phí (dòng ước tính và dòng thực đo riêng) và file `--record`: thời gian tường cho lớp công cụ, cho từng chuyên viên, cho bộ tổng hợp; số lời gọi model; token vào và ra; số lời gọi công cụ do model xin; với hosted, số tiền theo báo cáo của nhà cung cấp. Mốc so là bản 3 (mục 1.1). Mục tiêu **[Đề xuất, giả định]**: một báo cáo vòng trên `rtx3060` dưới 15 phút. Đo xong mới chốt.

Thêm hai số: tỉ lệ báo cáo `broken`, và độ ổn định (chạy hai lần cùng gói, giả thuyết hạng 1 có đổi không).

## 12. Kiến trúc mã

- Mọi mã mới nằm trong làn Đánh giá, dưới `packages/flywheel-eval/src/flywheel/eval/agentqa/`: `tools/` (lớp công cụ), `round/` (giả thuyết, chuyên viên, bộ tổng hợp, cổng dữ liệu), `casebench/` (bộ ca lịch sử). Không sửa `bench/` (DA-31, của Châu).
- Chỉ import `flywheel.contracts`, `flywheel.store`, `flywheel.testkit`, và `flywheel.eval.api`. Không import `flywheel.data`, `flywheel.loop`, adapter hay runtime.
- Config trong `configs/eval/agentqa/`: bảng luật giả thuyết, danh mục phép kiểm, kế hoạch công cụ, prompt từng chuyên viên, câu hỏi nhìn hình. Mỗi file có hash trong báo cáo; đổi là phiên bản agent mới và phải chấm lại.
- Lệnh: `fw agentqa round --pack <thư mục> --out <thư mục mới>`; `python -m flywheel.eval.agentqa.casebench` cho bộ ca.
- Bước xuất eval thật sang `scores.jsonl` là một file mới trong adapter `flywheel_psi0` (đường dẫn của Hiếu), không đụng file của DA-42.
- Job trên `rtx3060` chỉ chạy khi Hiếu đồng ý; mỗi lần chạy thật có runbook trong `docs/g0/agent-qa.md`.

## 13. Rủi ro

| Rủi ro | Giảm bằng |
|---|---|
| K1 chậm vì chờ DA-42 | Đường `Score` hiện có đủ cho ba công cụ chính; `relaxed_sweep`, `frames_at` làm sau |
| Bảng luật giả thuyết thành "chép đáp án" | Tập kiểm tách riêng; mỗi luật ghi nguồn là mục của spec, không phải một ca |
| Model nhỏ xếp hạng sai | Lớp code báo riêng; so M1 với M3 bằng số trước khi chọn |
| Ít ca, số đo nhiễu | Báo số đếm; thêm ca sau mỗi vòng mới |
| Artifact của ca cũ không còn đủ | Nhiệm vụ 6.1 kiểm trước; ca thiếu thì loại, ghi lý do |
| Camera đầu không thấy chỗ lỗi | Phép hiệu chỉnh của mục 9 phát hiện sớm; nhìn hình rút được khỏi story |
| Mười ngày không đủ | Thứ tự nhiệm vụ để mỗi mốc dùng được một mình: công cụ, rồi lớp code, rồi model, rồi nhìn hình |

## 14. Quyết định cần Hiếu

**[Đã chốt 19/11/2026, Hiếu]** "Approve as proposed": mọi dòng dưới đây chốt theo cột đề xuất (bản 0.2).

| # | Quyết định | Đề xuất (đã chốt) |
|---|---|---|
| Q1 | Cách tiếp cận | A, có cửa B hẹp, C là sàn (mục 3) |
| Q2 | Model của bộ tổng hợp; có mở đường hosted cho gói `public` không | Đo M1 và M3 trên bộ ca lịch sử rồi chọn; nếu chọn ngay thì M4 (mục 8) |
| Q3 | K1 làm chung PR hợp đồng với DA-42 | Có; cần Hiếu điều phối hai story |
| Q4 | Thêm artifact `RoundDiagnosis` (K2, K3); ai làm PR hợp đồng (Long giữ `flywheel-contracts`) | Thêm; Hiếu làm PR trên `DA-43-contract`, Long bình luận |
| Q5 | Bộ ca lịch sử: danh sách ca, chia phát triển và kiểm; ai viết đáp án tập kiểm | Như mục 11.2; một người không viết bảng luật |
| Q6 | `C70_R1` có vào bộ ca không | Không |
| Q7 | Nhìn hình có trong DA-43 không | Có, làm cuối, rút được |
| Q8 | Cho chạy trên `rtx3060` các lượt đo của mục 11 | Theo runbook, khi máy rảnh |
| Q9 | Khoảng cách vùng phủ viết lại trong làn | Có, kèm test đối chiếu với số của 20.12 |
| Q10 | Ngưỡng qua của mục 11.1–11.3 | Như đề xuất, chỉnh sau lần chạy đầu và ghi `Decision` |

## Nguồn

- [Agent QA/QC (DA-20)](../../g0/agent-qa.md), [bộ chấm lỗi cấy (DA-31)](../../g0/defect-bench.md)
- [Thí nghiệm khay](../../he/tray.md) mục 19.2, 20.2, 20.11–20.13
- [Design 27/10/2026](2026-10-27-g1-psi0-demo-design.md) mục 9, 10
- [Spec v10.6](../../spec-v10-failure-to-data.md) mục 6
- [03 · Kiến trúc](../../product/03-architecture.md) mục 7.3; [07 · Chia việc](../../product/07-team-workflow.md) mục 2.1, 3.2
- Hợp đồng: `packages/flywheel-contracts/src/flywheel/contracts/agentqa.py`, `evidence.py`, `trace.py`, `entities.py`
