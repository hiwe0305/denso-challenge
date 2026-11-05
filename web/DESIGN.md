# Web Humanoid Data Flywheel · thiết kế

Bản v0.4. Tài liệu này là nguồn duy nhất cho tầng web: API, Postgres, bộ nạp `fwsync` và FE. Lõi `flywheel` vẫn là nơi duy nhất chạy pipeline, train, eval và engine Failure → Data.

## Change log

| Ngày | Bản | Nội dung | Người |
|---|---|---|---|
| 1/11/2026 | 0.2 | Bản BA viết lại từ v0.1: chia Postgres hai nửa, một đường ghi, 39 bảng | — |
| 3/11/2026 | 0.3 | Ba chỗ sửa theo quyết định và mã đã merge trong ngày, xem bảng dưới. Số bảng 39 → 41 (thêm `system_diagnoses` và `train_diagnosis_skips`), nhóm P 27 → 29. Thêm C17, C18, C19 và BR-12. DDL chuyển thành khối SQL thật | Châu |
| 3/11/2026 | 0.3 | Bỏ `episodes.episode_index` và `UNIQUE (dataset_id, episode_index)`: hợp đồng không có trường nào như thế, nên bộ nạp sẽ phải tự phát số. `episode_ref` đã là khoá tự nhiên và đã UNIQUE. Thêm W12 (`Episode` không mang `dataset_id`) | Châu |
| 3/11/2026 | 0.3 | Dựng `web/schema/` theo tài liệu này: 9 file SQL, 41 bảng, 3 role, trigger C5–C9/C14/C19, 18 view, GRANT theo cột. `train_diagnosis_skips` là chỗ §4.4b để ngỏ tới M1, nay chốt | Châu |
| 5/11/2026 | 0.3 | W11 đóng: hợp đồng đã có `EpisodeMetadata.benchmark_copy_id` (#62), bộ nạp map nó vào `episodes.benchmark_copy_id` thay vì để NULL, và bộ mock gắn nó cho 10 episode của bản sao chấm | Châu |
| 5/11/2026 | 0.4 | Mốc M0 xong phần FE: thêm §7.4 hình dạng response cho 5 màn hình lõi (nguồn là `fe/src/api/types.ts`); §7.1 thêm `GET /recommendations` và `GET /evaluations/{id}`; quy ước trang, header vai tạm `X-Fw-Role`, id trong mock là mã `*_ref`. Dựng `fe/`: Vite, MSW đọc thẳng `mock/demo-17-11/`, type hợp đồng sinh bằng `json-schema-to-typescript`, màn hình M7 | Châu |
| 5/11/2026 | 0.4 | Dựng `api/` trước khi có Postgres: FastAPI với mọi endpoint đọc của §7.1 và hai endpoint ghi của M7, trên lớp đọc thay được (`SinkReadModel` đọc sink JSONL của `fwsync`; `PostgresReadModel` chờ M1). Hành động ghi vào `human_actions.jsonl`, đầu vào của `fwsync export`. Test đối chiếu 38 request với response của MSW. Đi trước W8: thêm một dịch vụ ở L0, chờ PO | Châu |
| 5/11/2026 | 0.4 | Hai view sửa: `v_branch_comparison` bỏ thí nghiệm HE và HE_T (mọi điểm HE chung một nhánh, nên `DISTINCT ON` sẽ lấy một điểm bất kỳ làm "nhánh"); `v_he_curve` thêm cột `he_variant` để vẽ một đường cho mỗi biến thể. Bộ mock thêm lượt eval cho A_07, B_FAIL và lưới HE; M9 vẽ đường cong HE có khoảng tin cậy Wilson 95% và N₅₀ | Châu |
| 5/11/2026 | 0.4 | M8 làm lộ ba lỗi view, sửa cả ở SQL lẫn hai lớp đọc: `v_cost_by_branch` lấy task theo thí nghiệm → lượt eval → khuyến nghị (trước đó bút toán eval của B mất task và B tách làm hai dòng); sai số dự báo chỉ tính trên dòng có cả ước tính lẫn thực đo, kèm cột `forecast_pairs` (trước đó trừ hai tổng, lấy ước tính của can thiệp chưa làm trừ vào thực đo của việc khác); `v_r_demo` bỏ HE. Thêm `v_cost_data_allocation` hiện thực BR-05. Bộ mock: A_07 có release riêng 70% mỗi nguồn | Châu |
| 5/11/2026 | 0.4 | Mốc M4 đạt trên sink JSONL: nhật ký `human_actions.jsonl` chỉ thêm, trạng thái chỉ đi tới; `fwsync export` đánh dấu EXPORTED, `fwsync import --actions` đánh dấu APPLIED; `POST /sync/run` chạy cả vòng (chỉ ADMIN, LEAD); thêm `GET /actions`, `/decisions`, `/sync/runs`. Sửa lỗi làm vòng ghi chưa bao giờ khép: lõi giả ghi `decisions-<id>.jsonl` ở gốc inbox, bộ nạp không nhận ra bảng và bỏ qua; nay ghi `decisions/part-<id>.jsonl` như lõi. FE: chuông, chọn vai tạm, M10 bản tối thiểu | Châu |

Ba chỗ sửa ở bản 0.3:

| \# | Chỗ | Trước | Sau | Lý do |
|---|---|---|---|---|
| 1 | `episodes` | `injected_defect JSONB` | `benchmark_copy_id VARCHAR(64)` | [03 bản 1.0](../docs/product/03-architecture.md) (PO, 3/11/2026) bỏ trường này; đáp án chỉ nằm trong `DefectManifest`. Giữ nguyên thì **phá chính luật R8** của tài liệu: `agent_ro` bị chặn `defect_manifests` nhưng đọc được `episodes` qua view. Issue #62 |
| 2 | `eval_episodes.step_status` | `SMALLINT[]`, mã 0/1/2/3 | `TEXT[]`, giá trị `pass`/`fail`/`not_attempted`/`unknown` | DA-36 đã merge (PR #58) với đúng bốn chuỗi này trong `StepStatus`; issue #59 là PR hợp đồng. Hai cách mã hoá cho cùng một thứ là hai nguồn sự thật |
| 3 | Kiểm hệ thống | 4 cột phẳng trên `eval_episodes` | Bảng `system_diagnoses` với `findings` + `skipped` + `measurements` | 4 cột không chở được "chưa chấm được": episode không có log RTC có `latency_p99_ms = NULL`, và NULL đọc ra "không có lỗi độ trễ" — đúng silent pass FR21 cấm. DA-13 (PR #71) sinh `SystemDiagnosisRecord` gồm cả `skipped`. Issue #70 |

**Chỗ còn chờ PO, chưa giải quyết trong bản này:** [03 §2.4](../docs/product/03-architecture.md) (ADR-13) xếp "Streamlit hoặc web" vào hàng **hoãn tới L1+**, và CLAUDE.md cấm thêm DB server ở L0. Toàn bộ tài liệu này là một console web có Postgres, nên cần Hiếu đổi ADR-13 hoặc khoanh web ra ngoài phạm vi L0 trước khi tầng API và Postgres được dựng thật. Phần FE chạy trên MSW không thêm dịch vụ nào nên không vướng, và mốc M0–M3 đi được trong lúc chờ.

---

# 1. Đọc nhanh cho dev

1. **Web là tầng nhìn và tầng điều phối** của data flywheel, không phải một hệ thống mới. Mọi con số nó hiện phải truy ngược được về một artifact có schema.
2. **Postgres chia hai nửa.** Nửa W do web tự quản: người dùng, chat, thông báo, bản nháp, hàng đợi hành động. Nửa P chiếu lại dữ liệu của lõi, chỉ đọc, do bộ nạp `fwsync` ghi. Web không bịa dữ liệu khoa học.
3. **Một đường ghi.** Mọi thao tác ghi của người dùng tạo một dòng `human_actions`. `fwsync export` biến dòng đó thành artifact trong outbox cho lõi. Lõi xử lý xong, `fwsync import` nạp kết quả về nửa P. Web không `UPDATE` thẳng vào bảng chiếu.
4. **Endpoint ghi trả về `action_id`, không trả bản ghi đã đổi.** Trạng thái chỉ đổi sau khi lõi xử lý và `fwsync` nạp lại. FE hiện "đang đồng bộ" trong khoảng đó.
5. **Tên trường lấy từ `packages/flywheel-contracts/schemas/*.json`.** Không đặt tên mới. Phụ lục B là bảng ánh xạ.
6. **Mock trước, thật sau.** FE và API chạy được trên bộ mock trong `flywheel.testkit` ngay từ ngày đầu. Khi lõi chạy thật, chỉ đổi thư mục nguồn của `fwsync`.
7. **Agent QA/QC không chặn pipeline.** Cổng là 7 phép kiểm bằng code. Agent viết diễn giải và xếp hạng. Hai kết quả nằm ở hai cột riêng, vì demo cần câu "code bắt x, agent bắt thêm y".
8. **Đơn vị dữ liệu nhỏ nhất là episode, không phải lô.** Thiếu bảng episode thì không làm được báo cáo dataset, phân bổ chi phí, khoảng tin cậy và chỉ số "giảm bao nhiêu % demo".
9. **Chỉ số thành công chính là cờ `check_success` của simulator,** không phải vị từ của scorer. Giữ cả hai cạnh nhau. Lệch nhau quá 5% nghĩa là scorer hỏng.
10. **Failure → Data có 11 chẩn đoán, chỉ 3 được tiêu ngân sách dữ liệu.** Không có cột chẩn đoán thì màn hình M7 không có gì để hiện.

Ba luật an toàn được cưỡng chế bằng cột, trigger và role, không bằng lời dặn: dữ liệu `restricted` / `internal` không rời máy; video người phải che danh tính trước mọi bước khác; holdout niêm phong chỉ `ADMIN` xem.

## 1.1 Phạm vi

Bảng dưới là danh sách nghiệm thu: còn một dòng chưa có màn hình nào phụ trách thì web chưa "đầy đủ".

Ba yêu cầu: hiện thông số huấn luyện, có giao diện nhập liệu và điều khiển, hiện kết quả đánh giá theo đầu vào tuỳ chỉnh.

| \# | Tài sản dự án | Màn hình |
|---|---|---|
| 1 | Ba loại dữ liệu cố định (egocentric, teleop, synthetic) và 6 nguồn test hiện tại | M2 |
| 2 | Pipeline 6 tầng: Ingest → Normalize → Annotate → QA → Release → Export | M2 |
| 3 | 7 phép kiểm QA bắt buộc; phát lại action động học và động lực học | M2 |
| 4 | Báo cáo dataset: số episode, pass/flag/reject theo nguồn, phân bố điều kiện | M2 |
| 5 | Agent QA/QC; bộ lỗi cấy D1–D8, T1–T8, R1–R2; precision và recall theo từng mã | M3 |
| 6 | Export LeRobot v2.1 (bắt buộc) và v3 (tuỳ chọn); contract test đọc lại bằng loader Ψ₀ | M4 |
| 7 | Release đóng băng có hash; chia tập train / dev / holdout; guard gần trùng | M4 |
| 8 | Hai task: hai bàn (6 bước) và bê khay (7 bước); 3 mức ngẫu nhiên hoá | M6 |
| 9 | Thí nghiệm: đường cong E1 và D\*; nhánh A, A₀.₇, B, C, B-fail, B⁺; HE (V-EGO, V-EGO10, V-NOEGO × N); HE-T của task khay; ma trận Ψ₀ / ACT / Diffusion Policy | M5, M9 |
| 10 | Telemetry train theo step; chẩn đoán train T1–T8 và offline O1–O4 | M5 |
| 11 | Probe P1–P4 theo stage của Ψ₀ | M5 |
| 12 | Eval closed-loop: đồng bộ và bất đồng bộ, renderer, mức, cờ sim so với scorer | M6 |
| 13 | Bảng lỗi 5 họ tín hiệu: F-DATA, F-TRAIN, F-OFF, F-CL, F-SYS | M6 |
| 14 | Failure → Data 12 bước; cụm lỗi; 11 chẩn đoán; evidence card; phiếu sửa; can thiệp; ngân sách; tỉ lệ sửa được | M7 |
| 15 | Cổng dev, A/A test, holdout niêm phong | M4, M9 |
| 16 | Sổ chi phí: ước tính và thực đo, bảng giá có phiên bản, độ nhạy 4 kịch bản, r_demo, chi phí mỗi điểm % | M8 |
| 17 | RunPlan đóng băng có hash; tái lập thí nghiệm | M5, M10 |
| 18 | Nhật ký quyết định; tỉ lệ kỹ sư ghi đè đề xuất | M10 |
| 19 | Kịch bản demo 17/11 gồm 6 phần | M1 |

Dòng 6 chuyển từ M2 (v0.1) sang M4, vì export là thuộc tính của release.

**Ngoài phạm vi:** nhập liệu bằng giọng nói; phân quyền chi tiết ngoài 5 vai; chạy job GPU hoặc chạy pipeline từ web. Web chỉ tạo yêu cầu (`job_requests`); người có máy chạy bằng lõi.

## 2. Tám nguyên tắc không được phá

Vi phạm một trong tám điều dưới đây là lỗi chặn khi review PR, kể cả khi tính năng chạy đúng.

Có ba role Postgres: `fw_api` (API), `fw_sync` (bộ nạp) và `agent_ro` (kết nối của agent chat).

| \# | Nguyên tắc | Cưỡng chế bằng |
|---|---|---|
| R1 | Web không là nguồn sự thật của dữ liệu khoa học. Bảng nhóm P chỉ do `fwsync` ghi | `fw_api` chỉ có `SELECT` trên bảng P; chỉ `fw_sync` có quyền ghi |
| R2 | Một đường ghi: thao tác của người → bảng nhóm W → artifact trong outbox → lõi | API không có endpoint nào ghi bảng P; review PR |
| R3 | Tên trường và enum theo `flywheel-contracts`. Thêm trường mới phải qua PR hợp đồng | Test so enum trong DB với JSON Schema (`web/tests/test_enum_sync.py`) |
| R4 | Sổ chi phí chỉ được thêm. Sai thì thêm bút toán đảo | Trigger chặn `UPDATE`/`DELETE`, cộng `REVOKE UPDATE, DELETE` khỏi cả `fw_api` lẫn `fw_sync` |
| R5 | Ước tính và thực đo là hai cột riêng trên cùng một bút toán | Schema |
| R6 | Dữ liệu `restricted` và `internal` không đi tới dịch vụ ngoài máy | Cột `data_class`; lớp gọi model lọc trước khi dựng prompt |
| R7 | Episode egocentric `deid_status = 'raw'` không rời tầng Annotate | Trigger trên `episodes` và `release_items` (C14) |
| R8 | Bản sao có lỗi cấy không bao giờ vào thí nghiệm; agent không đọc được đáp án lỗi cấy | **Bản 0.3:** `episodes` không mang đáp án, chỉ mang `benchmark_copy_id`; đáp án nằm trong nhóm S mà `agent_ro` bị `REVOKE`. Cộng validation khi submit bản nháp (C7) |

**R8 ở bản 0.2 không đứng được.** `agent_ro` bị chặn `defect_manifests` và `defect_items`, nhưng `episodes.injected_defect` thì agent đọc được qua view, nên đáp án vẫn lộ qua đúng bảng mà schema để nó. Bản 0.3 bỏ cột đó theo 03 bản 1.0: `episodes` chỉ nói "episode này thuộc bản sao chấm nào" (`benchmark_copy_id`), không nói "lỗi gì, tham số nào".

Trigger trên bảng nhóm P là **lưới an toàn**, không phải nơi xử lý nghiệp vụ. Nếu lõi đẩy sang dữ liệu vi phạm, `fwsync` từ chối dòng đó, ghi lỗi vào `sync_runs` và chạy tiếp các dòng khác.

## 3. Kiến trúc

### 3.1 Thành phần [Đề xuất]

| Thành phần | Chọn | Ghi chú |
|---|---|---|
| API | Python 3.11, FastAPI, SQLAlchemy 2.0, Alembic | Cùng ngôn ngữ với lõi; import `flywheel-contracts` để validate, không import làn nào khác của lõi |
| CSDL | PostgreSQL 16 | Ba role: `fw_api`, `fw_sync`, `agent_ro`. **Chưa có trên máy dev (3/11), xem Change log** |
| Bộ nạp | `fwsync` (CLI Python, cùng repo với API) | Chạy định kỳ 5 phút một lần và chạy được bằng tay |
| Hàng đợi | Bảng `jobs` + worker polling [Đề xuất]; `arq` trên Redis là [Option] | Bảng `jobs` là hạ tầng, không tính trong 40 bảng nghiệp vụ |
| File | Thư mục cục bộ `$FW_WEB_BLOBS`, bọc sau module `storage` | Đổi sang MinIO hay S3 sau mà không sửa chỗ khác |
| Đẩy thông báo | SSE, nguồn là `LISTEN`/`NOTIFY` của Postgres | Không thêm message broker |
| FE | React 18, TypeScript, Vite, TanStack Query, Recharts, Tailwind | Type sinh từ JSON Schema của contract; mock bằng MSW |
| Xác thực | Phiên đăng nhập đơn giản, 5 vai trong `app_users` | Không OAuth |

### 3.2 Hai đường dữ liệu

Dữ liệu chỉ chảy từ lõi vào nửa P. Thao tác ghi duy nhất của web là một dòng `human_actions` trong nửa W.

**Đường vào.** `fwsync import --from <dir>` đọc artifact, validate bằng model Pydantic của `flywheel-contracts`, rồi upsert vào bảng nhóm P theo ID nội dung. Chạy lại từ đầu cho cùng kết quả.

| Giai đoạn | Thư mục nguồn |
|---|---|
| Từ 1/11 | `packages/flywheel-testkit/src/flywheel/testkit/fixtures/` cộng bộ mock `mock/demo-17-11/` (Phụ lục C) |
| Khi lõi chạy thật | `$FW_ROOT/sites/local/catalog/**/*.jsonl` và `$FW_ROOT/runs/**` |

**Đường ra.** Mọi thao tác ghi của người tạo một dòng `human_actions`. `fwsync export` biến dòng đó thành artifact trong `$FW_WEB_OUTBOX/`:

| Hành động trên web | Artifact xuất ra |
|---|---|
| Nộp phiếu nạp dữ liệu | `intake.json` kèm đường dẫn file đã tải |
| Duyệt một tầng đang dừng | `QAReport` ghi đè kèm lý do, hoặc `job_request.json` chạy lại từ tầng k |
| Nộp bản nháp thí nghiệm | `RunPlan` nháp + `job_request.json` loại `TRAIN` |
| Duyệt, sửa hoặc từ chối đề xuất can thiệp | `Decision` kind `plan_review` |
| Ghi đè chẩn đoán cụm | `Decision` kind `diagnosis_override` |
| Yêu cầu đóng băng release, chạy eval, chạy Failure → Data | `job_request.json` |
| Mở niêm phong holdout | `Decision` kind `holdout_unseal` |

Mọi artifact xuất ra mang `source_action_id`. Lõi phải chép trường này sang artifact kết quả, để `fwsync import` biết hành động nào đã được áp dụng. **Đây là yêu cầu mới với hợp đồng**, ghi ở Phụ lục D (W7).

### 3.3 Ai ghi gì

| Việc | Web | Lõi |
|---|---|---|
| Tạo phiếu nạp, bản nháp thí nghiệm | Ghi bảng W | Đọc từ outbox |
| Chạy 6 tầng, chạy lại tầng, chuyển trạng thái tầng | Chỉ hiển thị | Thực hiện |
| Train, probe, eval, Failure → Data | Chỉ hiển thị, gửi yêu cầu | Thực hiện |
| Duyệt hop, duyệt đề xuất, ghi đè chẩn đoán | Ghi `human_actions` | Áp dụng, sinh `Decision` |
| Sổ chi phí | Chỉ hiển thị | Ghi bút toán |
| Chat, thông báo, người dùng | Ghi bảng W | Không liên quan |

### 3.4 Vì sao chia hai nửa

Lõi đã có kho append-only riêng (JSONL + DuckDB) và sổ chi phí riêng. Nếu web cũng ghi số khoa học thì hai bên sẽ lệch, và không bên nào có hash để biết bên nào đúng. Chia hai nửa thì web vẫn có SQL đầy đủ để join và vẽ, còn con số chỉ có một nguồn.

Đổi lại, thao tác trên web là bất đồng bộ: bấm duyệt xong, trạng thái chỉ đổi sau khi lõi xử lý và `fwsync` nạp lại. Mục 5.5 định nghĩa vòng đời trạng thái để FE hiển thị khoảng chờ này.

**Cần PO chốt (W1):** giữ phương án chia hai nửa như trên, hay cho web ghi thẳng và chấp nhận hai nguồn số. Toàn bộ bản này viết theo phương án chia hai nửa.

## 4. Mô hình dữ liệu

Schema có **41 bảng**, chia ba nhóm theo ai được ghi. File đầy đủ: `web/schema/schema.sql`, gọi 9 file đánh số theo thứ tự khoá ngoại.

### 4.1 Ba nhóm bảng

| Nhóm | Số bảng | Bảng | Ai ghi |
|---|---|---|---|
| **W** · web tự quản | 9 | `app_users`, `agent_chat_sessions`, `agent_chat_messages`, `notifications`, `human_actions`, `job_requests`, `dataset_intakes`, `experiment_drafts`, `sync_runs` | `fw_api` (riêng `sync_runs` do `fw_sync` ghi) |
| **P** · chiếu từ lõi | 29 | `sources`, `datasets`, `episodes`, `episode_qa_reports`, `pipeline_stage_defs`, `pipeline_stage_runs`, `releases`, `release_items`, `run_plans`, `experiments`, `experiment_datasets`, `model_checkpoints`, `training_metrics`, `train_diagnoses`, **`train_diagnosis_skips`**, `probe_results`, `sim_evaluations`, `eval_episodes`, **`system_diagnoses`**, `failure_clusters`, `diagnostic_runs`, `interventions`, `fix_rate_events`, `repair_tickets`, `flywheel_recommendations`, `flywheel_algo_steps`, `decisions`, `cost_ledger_entries`, `price_books` | `fw_sync` |
| **S** · bộ chấm, cách ly | 3 | `defect_manifests`, `defect_items`, `defect_scores` | `fw_sync`; `agent_ro` không đọc được |

### 4.2 So với bản BA cũ (19 bảng)

| Thay đổi | Bảng |
|---|---|
| Giữ, chỉ sửa theo mục 4.5 | `datasets`, `pipeline_stage_defs`, `pipeline_stage_runs`, `experiments`, `experiment_datasets`, `model_checkpoints`, `sim_evaluations`, `flywheel_recommendations`, `flywheel_algo_steps`, `cost_ledger_entries`, `agent_chat_sessions`, `agent_chat_messages`, `notifications`, `app_users` |
| Đổi tên | `data_collection_requests` → `interventions`; `training_telemetry_logs` → `training_metrics` (mở rộng) |
| Bỏ | `seeded_faults` (thay bằng nhóm S); `cost_rates` (thay bằng `price_books`); `failure_records` (thành view trên `eval_episodes`) |

### 4.3 Bảng mới và lý do

| Bảng | Có thì làm được gì | Không có thì hỏng gì |
|---|---|---|
| `episodes` | Đơn vị dữ liệu thật | Báo cáo dataset, BR-05, r_demo |
| `episode_qa_reports` | Kết quả 7 phép kiểm từng episode, append-only | Tầng 4 không có đầu ra; release không lọc được item |
| `releases`, `release_items` | Manifest đóng băng có hash | Thí nghiệm không tái lập được |
| `run_plans` | Ghim hash cấu hình, recipe, dải seed | Hai nhánh khác nhau ở chỗ không ai biết |
| `sources` | Giấy phép, sha256, nguồn gốc checkpoint | Không chặn được checkpoint gốc chưa sạch |
| `eval_episodes` | Mọi episode eval, kể cả thành công | Khoảng tin cậy, lỗi hạ tầng, bước hỏng, chấm lại |
| **`system_diagnoses`** | **Kiểm hệ thống R1–R6 của từng episode, kèm mã không chấm được** | **Bước 4 đọc NULL ra "không có lỗi"; engine đề xuất thu dữ liệu cho một lỗi calibration (bản 0.3)** |
| `failure_clusters` | Cụm lỗi + chẩn đoán | Toàn bộ màn hình M7 |
| `diagnostic_runs` | Rollout của bước 5, 6, 7 và chi phí của chúng | Không tách được chi phí chẩn đoán |
| `fix_rate_events` | Tỉ lệ sửa được đo có đối chứng | Bước 11 không có công thức; vòng lặp không khép |
| `repair_tickets` | Lỗi hệ thống không tiêu ngân sách dữ liệu | Hệ thống đòi thu dữ liệu cho một lỗi calibration |
| `train_diagnoses`, `probe_results` | T1–T8, O1–O4, P1–P4 | M5 chỉ vẽ được đường loss |
| `decisions` | Ai ký, tiêu chí, lý do ghi đè | Không tính được tỉ lệ ghi đè |
| `price_books` | Bảng giá có phiên bản, nhiều kịch bản song song | Không chạy được bảng độ nhạy |
| `defect_manifests`, `defect_items`, `defect_scores` | Đáp án lỗi cấy tách khỏi kết quả chấm | Agent đọc được đáp án; chấm lại ghi đè lần trước |
| `human_actions`, `job_requests` | Một đường ghi | Web ghi thẳng, hai nguồn số |
| `dataset_intakes`, `experiment_drafts` | Web soạn yêu cầu mà không chạm bảng P | Luồng 1–2 phải ghi thẳng vào `datasets` và `experiments` (lỗi của v0.1) |
| `sync_runs` | Lịch sử `fwsync`, phát hiện đồng bộ trễ | M10 không trả lời được "số này nạp lúc nào" |

### 4.4a DDL nhóm W

#### `human_actions`

```sql
CREATE TABLE human_actions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  action_kind VARCHAR(32) NOT NULL CHECK (action_kind IN (
    'INTAKE_SUBMIT','STAGE_REVIEW','EXPERIMENT_SUBMIT',
    'RECOMMENDATION_DECISION','DIAGNOSIS_OVERRIDE',
    'RELEASE_FREEZE_REQUEST','EVAL_REQUEST','FLYWHEEL_RUN_REQUEST',
    'HOLDOUT_UNSEAL','SOFT_DELETE','CHAT_ACTION_CONFIRM')),
  target_kind VARCHAR(32) NOT NULL,   -- bảng đích: pipeline_stage_runs, interventions, ...
  target_id UUID,                     -- NULL khi hành động tạo mới (yêu cầu job)
  payload JSONB NOT NULL,             -- nội dung, theo schema của từng action_kind
  reason TEXT,
  actor_id UUID NOT NULL REFERENCES app_users(id),
  idempotency_key VARCHAR(64) NOT NULL UNIQUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  -- năm cột dưới: chỉ fw_sync được UPDATE
  sync_status VARCHAR(12) NOT NULL DEFAULT 'PENDING'
    CHECK (sync_status IN ('PENDING','EXPORTED','APPLIED','REJECTED')),
  exported_at TIMESTAMPTZ,
  artifact_uri TEXT,
  applied_at TIMESTAMPTZ,
  reject_reason TEXT,
  CHECK (action_kind NOT IN ('DIAGNOSIS_OVERRIDE','HOLDOUT_UNSEAL','SOFT_DELETE')
         OR reason IS NOT NULL),
  CHECK (sync_status <> 'REJECTED' OR reject_reason IS NOT NULL)
);
CREATE INDEX ON human_actions (sync_status, created_at);

REVOKE UPDATE, DELETE ON human_actions FROM fw_api;
GRANT UPDATE (sync_status, exported_at, artifact_uri, applied_at, reject_reason)
  ON human_actions TO fw_sync;
```

Nội dung hành động là append-only với API. Chỉ năm cột trạng thái đồng bộ được `fw_sync` cập nhật, nhờ quyền theo cột của Postgres. Ghi chú bắt buộc với `FORCE_CONTINUE` nằm trong `payload` của `STAGE_REVIEW`, nên API kiểm (BR-04).

#### `job_requests`

```sql
CREATE TABLE job_requests (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  action_id UUID NOT NULL UNIQUE REFERENCES human_actions(id),
  job_kind VARCHAR(24) NOT NULL CHECK (job_kind IN (
    'PIPELINE_RUN','PIPELINE_RETRY_FROM','TRAIN','PROBE','EVAL',
    'RELEASE_FREEZE','FLYWHEEL_RUN')),
  spec JSONB NOT NULL,            -- tầng k, release, checkpoint, tập điều kiện, ...
  status VARCHAR(12) NOT NULL DEFAULT 'OPEN'
    CHECK (status IN ('OPEN','PICKED','DONE','FAILED','CANCELLED')),
  picked_by VARCHAR(16),          -- operator_code, không phải tên người
  result_ref VARCHAR(64),         -- ID artifact kết quả, fw_sync điền
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

Web không chạy job. Người có máy lấy yêu cầu từ outbox và chạy bằng lõi. Trạng thái `PICKED` / `DONE` / `FAILED` đến từ artifact trạng thái job của lõi (Phụ lục D, W7).

#### `dataset_intakes` — phiếu nạp dữ liệu

```sql
CREATE TABLE dataset_intakes (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  intake_code VARCHAR(64) NOT NULL UNIQUE,
  source_kind VARCHAR(16) NOT NULL,            -- teleop | synthetic | egocentric
  source_detail VARCHAR(32),
  data_class VARCHAR(16) NOT NULL,             -- public | internal | restricted
  license VARCHAR(64) NOT NULL,
  upload_uris TEXT[] NOT NULL DEFAULT '{}',    -- trong $FW_WEB_BLOBS
  manual_review BOOLEAN NOT NULL DEFAULT FALSE,
  seeded_faults BOOLEAN NOT NULL DEFAULT FALSE,
  defect_seed BIGINT,
  note TEXT,
  status VARCHAR(12) NOT NULL DEFAULT 'DRAFT'
    CHECK (status IN ('DRAFT','SUBMITTED','ACCEPTED','REJECTED')),
  submit_action_id UUID REFERENCES human_actions(id),
  dataset_id UUID REFERENCES datasets(id),     -- fw_sync điền khi lõi tạo dataset
  created_by UUID NOT NULL REFERENCES app_users(id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (seeded_faults = FALSE OR defect_seed IS NOT NULL),
  CHECK (status = 'DRAFT' OR submit_action_id IS NOT NULL)
);
```

#### `experiment_drafts` — bản nháp thí nghiệm

```sql
CREATE TABLE experiment_drafts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  task_id VARCHAR(16) NOT NULL,                -- two_table | tray
  branch VARCHAR(16) NOT NULL,                 -- phụ lục A, phải khớp task_id
  method VARCHAR(24) NOT NULL,                 -- PSI0 | ACT | DIFFUSION_POLICY
  hypothesis VARCHAR(8),
  base_checkpoint_ref VARCHAR(64) NOT NULL,    -- trỏ sources
  run_plan_ref VARCHAR(64),                    -- RunPlan có sẵn; NULL thì lõi sinh mới
  hyperparams JSONB NOT NULL DEFAULT '{}',
  release_mix JSONB NOT NULL DEFAULT '[]',     -- [{release_id, mix_weight}]
  status VARCHAR(12) NOT NULL DEFAULT 'DRAFT'
    CHECK (status IN ('DRAFT','SUBMITTED','ACCEPTED','REJECTED')),
  submit_action_id UUID REFERENCES human_actions(id),
  experiment_id UUID REFERENCES experiments(id),
  reject_reason TEXT,
  created_by UUID NOT NULL REFERENCES app_users(id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

Với hai bảng nháp, `fw_sync` chỉ được `UPDATE` ba cột: `status`, `dataset_id` / `experiment_id`, `reject_reason`. Luật C5, C6, C7 và C15 chạy trên `experiment_drafts`.

#### `sync_runs`

```sql
CREATE TABLE sync_runs (
  id BIGSERIAL PRIMARY KEY,
  direction VARCHAR(8) NOT NULL CHECK (direction IN ('import','export','verify')),
  source_dir TEXT NOT NULL,
  started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  finished_at TIMESTAMPTZ,
  counts JSONB NOT NULL DEFAULT '{}',   -- {bảng: {inserted, updated, unchanged, rejected}}
  errors JSONB NOT NULL DEFAULT '[]',   -- [{bảng, ref, code, message}]
  status VARCHAR(8) NOT NULL DEFAULT 'running'
    CHECK (status IN ('running','ok','partial','failed'))
);
```

### 4.4b DDL nhóm P

**Cột chung cho mọi bảng P.** Mỗi bảng nhóm P có thêm ba cột do `fw_sync` điền:

```sql
origin VARCHAR(8) NOT NULL DEFAULT 'core' CHECK (origin IN ('core','mock')),
sync_run_id BIGINT NOT NULL REFERENCES sync_runs(id),
synced_at TIMESTAMPTZ NOT NULL DEFAULT now()
```

Cột `origin` là thứ cho phép FE dán nhãn "mock" đúng từng bản ghi khi dữ liệu thật và mock chạy song song (mốc M6, 15/11).

**Cột xoá mềm** (`is_deleted`, `deleted_at`, `delete_reason`) chỉ có trên `datasets`, `experiments`, `releases`, `sim_evaluations`. Bảng con bị ẩn khi bản ghi cha bị xoá mềm, thông qua view.

#### `episodes`

```sql
CREATE TABLE episodes (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  episode_ref VARCHAR(64) NOT NULL UNIQUE,     -- ep_<ULID> từ lõi
  dataset_id UUID NOT NULL REFERENCES datasets(id),
  episode_index INTEGER NOT NULL,
  kind VARCHAR(24) NOT NULL,                   -- phụ lục A
  source_kind VARCHAR(16) NOT NULL,            -- teleop | synthetic | egocentric
  source_detail VARCHAR(32),
  synthetic_tier VARCHAR(4),                   -- S1..S4
  action_quality VARCHAR(16) NOT NULL,
  operator_kind VARCHAR(8) NOT NULL,           -- human | machine
  embodiment_id VARCHAR(64) NOT NULL,
  is_root BOOLEAN NOT NULL DEFAULT FALSE,
  parent_id UUID REFERENCES episodes(id),
  intervention_id UUID,                        -- FK thêm sau khi tạo interventions
  condition_seed BIGINT,
  split VARCHAR(16) NOT NULL DEFAULT 'unassigned',
  data_class VARCHAR(16) NOT NULL,
  license VARCHAR(64) NOT NULL,
  deid_status VARCHAR(16) NOT NULL DEFAULT 'raw',
  renderer VARCHAR(8),                         -- mujoco | isaac
  bundle_uri TEXT NOT NULL,
  sha256 CHAR(64),
  frame_count INTEGER CHECK (frame_count >= 0),
  duration_s NUMERIC(8,3),
  -- Bản 0.3: cột injected_defect bị bỏ theo 03 bản 1.0 (PO, 3/11/2026).
  -- Episode của bản sao dùng để chấm Agent QA/QC chỉ nói nó thuộc bản sao nào;
  -- đáp án (episode nào, mã gì, tham số nào) chỉ nằm trong DefectManifest,
  -- mà agent_ro bị REVOKE. Giữ đáp án ở đây là phá R8 (xem mục 2).
  benchmark_copy_id VARCHAR(64),               -- = DefectManifest.dataset_id của bản sao
  meta JSONB NOT NULL DEFAULT '{}',
  UNIQUE (dataset_id, episode_index),
  CHECK (is_root = FALSE OR (operator_kind = 'human'
         AND kind IN ('teleop_demo','teleop_correction','recovery'))),
  CHECK (source_kind <> 'synthetic' OR synthetic_tier IS NOT NULL)
);
CREATE INDEX ON episodes (dataset_id, source_kind);
CREATE INDEX ON episodes (split) WHERE split <> 'unassigned';
CREATE INDEX ON episodes (benchmark_copy_id) WHERE benchmark_copy_id IS NOT NULL;
-- sau khi tạo interventions:
ALTER TABLE episodes ADD FOREIGN KEY (intervention_id) REFERENCES interventions(id);
```

#### `episode_qa_reports`

```sql
CREATE TABLE episode_qa_reports (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  episode_id UUID NOT NULL REFERENCES episodes(id),
  stage_run_id UUID REFERENCES pipeline_stage_runs(id),
  threshold_version VARCHAR(32) NOT NULL,
  decision VARCHAR(16) NOT NULL
    CHECK (decision IN ('pass','flag','quarantine','reject')),
  reasons TEXT[] NOT NULL DEFAULT '{}',
  checks JSONB NOT NULL,                       -- [{name, value, threshold, passed}]
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ON episode_qa_reports (episode_id, created_at DESC);
```

Append-only. Trạng thái QA hiện hành của một episode là dòng mới nhất. Chấm lại tạo dòng mới, không sửa dòng cũ.

#### `sim_evaluations` (sửa)

```sql
ALTER TABLE sim_evaluations
  ADD COLUMN run_plan_id UUID REFERENCES run_plans(id),
  ADD COLUMN task_id VARCHAR(16) NOT NULL,
  ADD COLUMN condition_set_id VARCHAR(64) NOT NULL,
  ADD COLUMN split VARCHAR(16) NOT NULL DEFAULT 'dev',
  ADD COLUMN level SMALLINT CHECK (level BETWEEN 0 AND 2),
  ADD COLUMN renderer VARCHAR(8) NOT NULL DEFAULT 'mujoco',
  ADD COLUMN eval_mode VARCHAR(8) NOT NULL DEFAULT 'sync',
  ADD COLUMN success_count INTEGER NOT NULL DEFAULT 0,
  ADD COLUMN infra_failed_count INTEGER NOT NULL DEFAULT 0,
  ADD COLUMN sealed_until TIMESTAMPTZ,
  ADD CONSTRAINT c13_counts CHECK (
    infra_failed_count BETWEEN 0 AND total_episodes
    AND success_count BETWEEN 0 AND total_episodes - infra_failed_count);

ALTER TABLE sim_evaluations ADD COLUMN overall_sr NUMERIC(5,4) GENERATED ALWAYS AS (
  CASE WHEN total_episodes - infra_failed_count > 0
       THEN success_count::numeric / (total_episodes - infra_failed_count)
  END) STORED;
```

Lỗi hạ tầng bị loại khỏi mẫu số. `sealed_until` khác NULL và còn ở tương lai thì API trả 403 cho mọi vai trừ `ADMIN`.

#### `eval_episodes`

```sql
CREATE TABLE eval_episodes (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  evaluation_id UUID NOT NULL REFERENCES sim_evaluations(id),
  episode_index INTEGER NOT NULL,
  condition_id VARCHAR(64) NOT NULL,
  level SMALLINT NOT NULL CHECK (level BETWEEN 0 AND 2),
  episode_seed BIGINT NOT NULL,
  rollout_seed BIGINT,
  scorer_version VARCHAR(32) NOT NULL,
  sim_success BOOLEAN,                 -- cờ simulator: CHỈ SỐ CHÍNH
  scorer_success BOOLEAN,              -- kết luận của scorer, để đối chiếu
  infra_status VARCHAR(24) NOT NULL DEFAULT 'ok',
  -- Bản 0.3: step_status là bốn chuỗi của StepStatus trong DA-36 (PR #58),
  -- không phải mã số 0/1/2/3 của bản 0.2. Hai cách mã hoá cho cùng một thứ
  -- là hai nguồn sự thật, và bản số không đọc được bằng mắt trong JSONL.
  step_status TEXT[] NOT NULL,
  first_failed_step SMALLINT,
  failure_code VARCHAR(32),            -- L-GRASP, L-PART-DROP, ...
  failure_class VARCHAR(16),           -- approach | grasp | carry | place | balance
  failure_time_s NUMERIC(8,3),
  camera_params_hash VARCHAR(64),      -- provenance của Episode, không phải kết quả kiểm
  video_uri TEXT,
  trajectory_log_uri TEXT,
  details JSONB NOT NULL DEFAULT '{}', -- lý do từng bước "unknown", tín hiệu thiếu (#59)
  UNIQUE (evaluation_id, episode_index, scorer_version),
  CONSTRAINT c18_step_status CHECK (
    step_status <@ ARRAY['pass','fail','not_attempted','unknown']::text[])
);
CREATE INDEX ON eval_episodes (evaluation_id, level, sim_success);
CREATE INDEX ON eval_episodes (evaluation_id, failure_code, first_failed_step);

-- giữ tên cũ cho FE và báo cáo cũ
CREATE VIEW failure_records AS
SELECT * FROM eval_episodes
WHERE sim_success IS NOT TRUE AND infra_status = 'ok';
```

**Bản 0.2 để bốn cột `tracking_error`, `latency_p99_ms`, `sync_offset_ms`, `camera_params_hash` ở đây làm đầu vào bước 4.** Ba cột đầu đã chuyển sang `system_diagnoses` dưới đây; `camera_params_hash` giữ lại vì nó là provenance của episode theo 03 §4.3, không phải kết quả của một phép kiểm.

#### `system_diagnoses` — kiểm hệ thống R1–R6 (bản 0.3, mới)

```sql
CREATE TABLE system_diagnoses (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  eval_episode_id UUID NOT NULL REFERENCES eval_episodes(id),
  diagnosis VARCHAR(16) NOT NULL CHECK (diagnosis IN (
    'clean','unknown','controller','runtime','sync','calibration','infra')),
  config_sha256 CHAR(64) NOT NULL,     -- hash system.yaml đã chấm
  trace_sha256 CHAR(64) NOT NULL,
  infra_status VARCHAR(24),            -- R6; ghi dù R6 không nổ
  findings JSONB NOT NULL DEFAULT '[]',      -- [{code, value, threshold, part, where, detail}]
  skipped  JSONB NOT NULL DEFAULT '[]',      -- [{code, reason}] mã không chấm được
  measurements JSONB NOT NULL DEFAULT '{}',  -- số để hiện ở M6 dù không nổ ngưỡng
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (eval_episode_id, config_sha256),
  -- C17: sạch nghĩa là đã chấm hết và không mã nào nổ. Không có CHECK này thì
  -- một episode không ai chấm được vẫn đọc ra "không có lỗi hệ thống" (FR21).
  CONSTRAINT c17_clean_is_measured CHECK (
    diagnosis <> 'clean'
    OR (jsonb_array_length(findings) = 0 AND jsonb_array_length(skipped) = 0))
);
CREATE INDEX ON system_diagnoses (eval_episode_id, created_at DESC);
```

Ba lý do bảng này thay bốn cột phẳng:

- **NULL không phân biệt được "đo rồi, không lỗi" với "chưa ai đo".** Episode không có log RTC thì `latency_p99_ms` là NULL, và mọi truy vấn `WHERE latency_p99_ms > τ` bỏ qua nó, nên nó đọc ra không có lỗi độ trễ. `skipped` là chỗ nói rõ mã nào không chấm được và vì sao.
- **R3 đo riêng thân trên và thân dưới** (spec §6.4 bước 2), nên một dòng finding phải mang `part`. Một cột `tracking_error JSONB` không có chỗ cho ngưỡng của từng nửa.
- **`measurements` giữ được ý của bản 0.2**: M6 vẫn hiện sai số bám lệnh theo nhóm và độ trễ p99 dù không mã nào nổ ngưỡng.

Nguồn: `SystemDiagnosisRecord` của `flywheel.eval.diagnosis.system.artifact` (DA-13, PR #71). Kiểu contract đang chờ issue #70; tới khi có, bộ nạp đọc bản ghi của làn.

#### `failure_clusters`

```sql
CREATE TABLE failure_clusters (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  recommendation_id UUID NOT NULL REFERENCES flywheel_recommendations(id),
  failed_step SMALLINT NOT NULL,
  failure_code VARCHAR(32) NOT NULL,
  level SMALLINT NOT NULL,
  member_count INTEGER NOT NULL CHECK (member_count > 0),
  representative_refs VARCHAR(64)[] NOT NULL
    CHECK (cardinality(representative_refs) BETWEEN 1 AND 5),  -- ref eval_episode của lõi
  representative_seed BIGINT NOT NULL,
  diagnosis VARCHAR(32),
  diagnosis_source VARCHAR(20) CHECK (diagnosis_source IN ('auto','engineer_override')),
  override_reason TEXT,
  consumes_data_budget BOOLEAN GENERATED ALWAYS AS (COALESCE(
    diagnosis IN ('TRANG_THAI_DAU_XAU','THIEU_VUNG_PHU','KY_NANG_YEU'), FALSE)) STORED,
  parent_cluster_id UUID REFERENCES failure_clusters(id),
  checks JSONB NOT NULL DEFAULT '{}',
  card_uri TEXT,
  UNIQUE (recommendation_id, failed_step, failure_code, level),
  CHECK (diagnosis IS NULL OR diagnosis IN (
    'CHUA_RO','HE_THONG_CONTROLLER','HE_THONG_RUNTIME','HE_THONG_DONG_BO',
    'HE_THONG_CALIBRATION','KHONG_KHA_THI','TRANG_THAI_DAU_XAU','NHAN_THUC',
    'NGOAI_MIEN','THIEU_VUNG_PHU','KY_NANG_YEU')),
  CHECK ((diagnosis IS NULL) = (diagnosis_source IS NULL)),
  CHECK (diagnosis_source IS DISTINCT FROM 'engineer_override' OR override_reason IS NOT NULL)
);
```

`consumes_data_budget` bọc `COALESCE` nên luôn là TRUE hoặc FALSE; bản v0.1 ra NULL khi cụm chưa chẩn đoán, làm truy vấn `WHERE NOT consumes_data_budget` bỏ sót cụm.

**Ánh xạ với chẩn đoán của `system_diagnoses`** (bản 0.3). Hai enum ở hai mức khác nhau và không được trộn: `system_diagnoses.diagnosis` là kết luận của **một episode** sau bước 4, `failure_clusters.diagnosis` là kết luận của **một cụm** sau cả 11 bước.

| `system_diagnoses` (episode) | `failure_clusters` (cụm) |
|---|---|
| `controller` | `HE_THONG_CONTROLLER` |
| `runtime` | `HE_THONG_RUNTIME` |
| `sync` | `HE_THONG_DONG_BO` |
| `calibration` | `HE_THONG_CALIBRATION` |
| `unknown` | `CHUA_RO` |
| `infra` | — (loại khỏi mẫu số, không thành cụm) |
| `clean` | — (đi tiếp sang bước 5) |

#### `interventions` (thay `data_collection_requests`)

```sql
CREATE TABLE interventions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  intervention_ref VARCHAR(64) NOT NULL UNIQUE,   -- iv_<ULID>
  recommendation_id UUID NOT NULL REFERENCES flywheel_recommendations(id),
  cluster_id UUID REFERENCES failure_clusters(id),
  kind VARCHAR(24) NOT NULL,                      -- phụ lục A
  target_quantity INTEGER NOT NULL CHECK (target_quantity > 0),
  unit VARCHAR(16) NOT NULL,
  spec JSONB NOT NULL DEFAULT '{}',               -- bán kính, mức, bước k
  n_failures INTEGER,                             -- m_j của cụm
  n_eff INTEGER,                                  -- min(m_j, L_t)
  expected_gain_pp NUMERIC(6,3),                  -- g_j, điểm % trên dev
  estimated_usd NUMERIC(12,2),
  estimated_human_minutes NUMERIC(10,2),
  estimated_gpu_hours NUMERIC(10,3),
  status VARCHAR(16) NOT NULL DEFAULT 'PROPOSED',
  approved_quantity INTEGER,
  assignee_id UUID REFERENCES app_users(id),
  due_at TIMESTAMPTZ,
  CHECK (status IN ('PROPOSED','APPROVED','REJECTED','IN_PROGRESS','FULFILLED','CANCELLED'))
);
```

Episode thu về trỏ ngược qua `episodes.intervention_id`. Số đã thực hiện đếm bằng truy vấn, không nhập tay.

#### `fix_rate_events`

```sql
CREATE TABLE fix_rate_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  intervention_kind VARCHAR(24) NOT NULL,
  cluster_id UUID NOT NULL REFERENCES failure_clusters(id),
  intervention_id UUID NOT NULL REFERENCES interventions(id),
  n_conditions INTEGER NOT NULL CHECK (n_conditions > 0),
  p_parent NUMERIC(5,4) NOT NULL,
  p_candidate NUMERIC(5,4) NOT NULL,
  fixed_count INTEGER NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (fixed_count BETWEEN 0 AND n_conditions)
);
```

Tỉ lệ sửa được của một loại can thiệp là hậu nghiệm Beta, gộp lúc đọc: α = 1 + Σ `fixed_count`, β = 1 + Σ (`n_conditions` − `fixed_count`).

#### `repair_tickets`

```sql
CREATE TABLE repair_tickets (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  cluster_id UUID NOT NULL REFERENCES failure_clusters(id),
  diagnosis VARCHAR(32) NOT NULL,
  title TEXT NOT NULL,
  detail TEXT,
  status VARCHAR(16) NOT NULL DEFAULT 'OPEN'
    CHECK (status IN ('OPEN','IN_PROGRESS','FIXED','WONT_FIX')),
  rebaseline_required BOOLEAN NOT NULL DEFAULT TRUE,
  assignee_id UUID REFERENCES app_users(id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

#### `training_metrics` (thay `training_telemetry_logs`)

```sql
CREATE TABLE training_metrics (
  id BIGSERIAL PRIMARY KEY,
  experiment_id UUID NOT NULL REFERENCES experiments(id),
  run_plan_id UUID REFERENCES run_plans(id),
  release_id UUID REFERENCES releases(id),
  attempt SMALLINT NOT NULL DEFAULT 0,
  step INTEGER NOT NULL CHECK (step >= 0),
  epoch INTEGER NOT NULL DEFAULT 0,
  split VARCHAR(8) NOT NULL CHECK (split IN ('train','val')),
  loss DOUBLE PRECISION,
  loss_nonfinite VARCHAR(12) CHECK (loss_nonfinite IN ('NaN','Infinity','-Infinity')),
  lr DOUBLE PRECISION NOT NULL,
  vlm_frozen BOOLEAN NOT NULL,
  loss_by_group JSONB NOT NULL DEFAULT '{}',
  loss_by_chunk_pos DOUBLE PRECISION[],
  grad_norm_vlm DOUBLE PRECISION,
  grad_norm_action DOUBLE PRECISION,
  pred_std DOUBLE PRECISION[],
  target_std DOUBLE PRECISION[],
  pred_var_by_dim DOUBLE PRECISION[],
  hand_open_hist DOUBLE PRECISION[],
  vram_gb DOUBLE PRECISION,
  throughput DOUBLE PRECISION,
  wall_time_s DOUBLE PRECISION NOT NULL,
  recorded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (experiment_id, attempt, step, split),
  CHECK ((loss IS NULL) <> (loss_nonfinite IS NULL))   -- đúng một trong hai
);
```

Bốn điểm dev hay sai:

- Một step có **hai** dòng, train và val. Khoá cũ `(experiment_id, step)` chặn mất dòng val, mà mất val là mất T2 và T3.
- `attempt` cần thiết vì job trên Colab resume từ checkpoint sẽ phát lại step cũ.
- Loss không hữu hạn đi vào `loss_nonfinite`, không nhét vào `loss`. `AVG()` trên cột có NaN trả NaN và làm trắng cả biểu đồ.
- CHECK cũ cho phép có cả hai cột cùng lúc. Bản này bắt buộc **đúng một**.

**Lưu ý với bộ nạp:** bốn trường `loss_by_group`, `pred_var_by_dim`, `pred_std`, `target_std` chỉ có trên dòng `split = 'val'`; dòng `train` để trống (quyết định 3/11/2026, issue #44).

#### `train_diagnoses` và `probe_results`

```sql
CREATE TABLE train_diagnoses (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  experiment_id UUID NOT NULL REFERENCES experiments(id),
  checkpoint_id UUID REFERENCES model_checkpoints(id),
  config_sha256 CHAR(64) NOT NULL,
  code VARCHAR(4) NOT NULL CHECK (code IN
    ('T1','T2','T3','T4','T5','T6','T7','T8','O1','O2','O3','O4')),
  start_step INTEGER NOT NULL,
  group_name VARCHAR(32),
  dim INTEGER,
  value DOUBLE PRECISION,
  value_nonfinite VARCHAR(12),
  threshold DOUBLE PRECISION,
  stop_job BOOLEAN NOT NULL DEFAULT FALSE,
  CHECK (stop_job = FALSE OR code = 'T1')
);

CREATE TABLE probe_results (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  probe VARCHAR(4) NOT NULL CHECK (probe IN ('P1','P2','P3','P4')),
  checkpoint_id UUID NOT NULL REFERENCES model_checkpoints(id),
  parent_checkpoint_id UUID REFERENCES model_checkpoints(id),
  dataset_sha256 CHAR(64),
  payload JSONB NOT NULL,                      -- theo schema ProbeP1..P4
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (probe <> 'P4' OR parent_checkpoint_id IS NOT NULL)
);
```

`train_diagnoses` là một dòng một mã **đã nổ**, nên không có chỗ treo danh sách `skipped` mà `TrainDiagnosis` của `flywheel.contracts.training` mang theo. Danh sách đó **phải nạp về**, cùng lý do như `system_diagnoses.skipped`: một checkpoint không có probe P4 thì T7 không chấm được, không phải không quên (BR-12).

**Chốt ở M1 (3/11/2026):** một bảng riêng `train_diagnosis_skips`, khoá `(experiment_id, config_sha256, code)`. Không chọn cột `skipped JSONB` trên `train_diagnoses` vì danh sách đó thuộc về một *lần chạy*, không thuộc về một finding, nên đặt trên dòng finding sẽ lặp lại nó mỗi mã đã nổ và biến mất khi không mã nào nổ — đúng lúc nó cần thiết nhất.

#### `price_books` và `cost_ledger_entries` (sửa)

```sql
CREATE TABLE price_books (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name VARCHAR(32) NOT NULL,            -- pitch_v10 | denso | cell_dat | gpu_dat
  sha256 CHAR(64) NOT NULL,
  rates JSONB NOT NULL,
  cell_hour_usd NUMERIC(10,2) NOT NULL DEFAULT 0,
  effective_from DATE NOT NULL,
  note TEXT,
  UNIQUE (name, sha256)
);

ALTER TABLE cost_ledger_entries
  ADD COLUMN price_book_id UUID NOT NULL REFERENCES price_books(id),
  ADD COLUMN run_plan_id UUID REFERENCES run_plans(id),
  ADD COLUMN branch VARCHAR(16),
  ADD COLUMN cluster_id UUID REFERENCES failure_clusters(id),
  ADD COLUMN intervention_id UUID REFERENCES interventions(id),
  ADD COLUMN job_id VARCHAR(64),
  ADD COLUMN operator_code VARCHAR(16),        -- mã giả danh, không phải tên
  ADD COLUMN estimated_usd NUMERIC(12,2),
  ADD COLUMN measured_usd NUMERIC(12,2),
  ADD COLUMN estimated_human_minutes NUMERIC(10,2),
  ADD COLUMN measured_human_minutes NUMERIC(10,2),
  ADD COLUMN estimated_gpu_hours NUMERIC(10,3),
  ADD COLUMN measured_gpu_hours NUMERIC(10,3);
```

Ước tính và thực đo nằm **cùng một dòng, hai cột**, nên sai số dự báo chi phí là một phép trừ. `entry_kind` còn hai giá trị: `ENTRY` và `REVERSAL`.

**Không lưu tên người trong sổ.** `operator_code` là mã giả danh; bảng ánh xạ sang tên nằm ngoài DB này.

### 4.4c Nhóm S · lỗi cấy, cách ly

```sql
CREATE TABLE defect_manifests (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  dataset_id UUID NOT NULL REFERENCES datasets(id),
  seed BIGINT NOT NULL CHECK (seed >= 0),
  sha256 CHAR(64) NOT NULL,                    -- khoá đáp án
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE defect_items (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  manifest_id UUID NOT NULL REFERENCES defect_manifests(id),
  target_ref VARCHAR(64) NOT NULL,             -- episode hoặc file log
  code VARCHAR(8) NOT NULL,                    -- D1..D8, T1..T8, R1, R2
  parameters JSONB NOT NULL DEFAULT '{}'
);

CREATE TABLE defect_scores (                   -- kết quả chấm, append-only
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  manifest_id UUID NOT NULL REFERENCES defect_manifests(id),
  scorer_version VARCHAR(32) NOT NULL,
  detector VARCHAR(16) NOT NULL CHECK (detector IN ('code','agent')),
  agent_model VARCHAR(64),
  code VARCHAR(8) NOT NULL,
  tp INTEGER NOT NULL, fp INTEGER NOT NULL, fn INTEGER NOT NULL,
  false_alarm_rate NUMERIC(5,4),               -- đo trên bản sạch
  latency_s NUMERIC(8,2),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (detector <> 'agent' OR agent_model IS NOT NULL)
);

CREATE ROLE agent_ro;
REVOKE ALL ON defect_manifests, defect_items FROM agent_ro;
-- GRANT SELECT chỉ trên các view *_agent của mục 4.6
```

Cột `detector` cho phép M3 nói "code bắt được 6/10, agent bắt thêm 2 và giải thích đúng 7". Kết nối dùng cho prompt của agent chat phải dùng role `agent_ro`, với connection pool riêng.

**Bản 0.3:** vì `episodes` không còn `injected_defect`, `agent_ro` có thể đọc `episodes` qua view mà không thấy đáp án. Trước đó thì không, và đó là lỗ R8.

### 4.5 Ràng buộc phải cưỡng chế

| \# | Luật | Cách làm | Nơi |
|---|---|---|---|
| C1 | Mã dataset, mã thí nghiệm, mã phiếu nạp duy nhất; xoá mềm rồi tạo lại cùng mã vẫn được | `CREATE UNIQUE INDEX ... (dataset_code) WHERE NOT is_deleted` | P, W |
| C2 | Mỗi dataset và tầng chỉ một attempt đang hiệu lực | `CREATE UNIQUE INDEX ... (dataset_id, stage_number) WHERE is_current` | P |
| C3 | Số attempt không trùng | `UNIQUE (dataset_id, stage_number, attempt_no)` | P |
| C4 | Mỗi thí nghiệm đúng một checkpoint best và một latest | Hai partial unique index | P |
| C5 | Nộp bản nháp thí nghiệm cần ≥ 1 release và tổng `mix_weight` bằng 1 (sai số 1e-6) | Trigger khi `experiment_drafts.status` chuyển `SUBMITTED` | W |
| C6 | Bản nháp chỉ sửa được khi còn `DRAFT` | Trigger `BEFORE UPDATE` trên `experiment_drafts` và `dataset_intakes` | W |
| C7 | Mỗi release trong bản nháp phải: đã đóng băng, chưa xoá, **không chứa episode có `benchmark_copy_id`**, không thuộc dataset có lỗi cấy. Checkpoint gốc phải trỏ `sources` có `clean_for_main_task <> 'false'`. `branch` phải hợp lệ với `task_id` | Trigger khi chuyển `SUBMITTED`; lỗi trả mã BR-01 | W |
| C8 | Sổ chi phí chỉ thêm | Trigger chặn `UPDATE`/`DELETE` **và** `REVOKE UPDATE, DELETE` khỏi mọi role | P |
| C9 | Bút toán đảo đúng dấu, đúng đối tượng, chỉ đảo một lần | Trigger so với `reverses_entry_id` | P |
| C10 | Bút toán ước tính phải gắn khuyến nghị hoặc can thiệp | `CHECK (estimated_usd IS NULL OR num_nonnulls(recommendation_id, intervention_id) >= 1)` | P |
| C11 | Mỗi bút toán gắn ít nhất một đối tượng | `CHECK (num_nonnulls(dataset_id, experiment_id, evaluation_id, recommendation_id, intervention_id) >= 1)` | P |
| C12 | Xoá mềm phải có lý do | `CHECK (NOT is_deleted OR delete_reason IS NOT NULL)` | P |
| C13 | Số đếm eval hợp lệ; cột đếm `NOT NULL DEFAULT 0` | `CHECK c13_counts` trên `sim_evaluations` | P |
| C14 | Egocentric raw không được gán split khác `unassigned` và không vào release | Trigger trên `episodes` và `release_items` | P |
| C15 | Phiếu nạp và bản nháp chỉ nộp một lần | Compare-and-set: `UPDATE ... SET status='SUBMITTED' WHERE id=$1 AND status='DRAFT' RETURNING id`; không có dòng thì trả 409 | API |
| C16 | Cùng `Idempotency-Key` trả về cùng `action_id` | `UNIQUE (idempotency_key)` + `INSERT ... ON CONFLICT DO NOTHING RETURNING` | W, API |
| **C17** | **Kiểm hệ thống kết luận `clean` chỉ khi `findings` và `skipped` đều rỗng** | `CHECK c17_clean_is_measured` trên `system_diagnoses` | **P** |
| **C18** | **`step_status` chỉ nhận `pass`, `fail`, `not_attempted`, `unknown`** | `CHECK c18_step_status` trên `eval_episodes` | **P** |
| **C19** | **Release từ chối mọi episode có `benchmark_copy_id`** | Trigger trên `release_items` (03 bản 1.0) | **P** |

### 4.6 View cho FE

| View | Trả về | Màn hình |
|---|---|---|
| `v_pipeline_current` | Stepper 6 tầng theo attempt hiện hành, kèm verdict code và verdict agent | M2 |
| `v_dataset_report` | Số episode theo nguồn; pass / flag / quarantine / reject theo dataset | M2 |
| `v_defect_detection` | Precision, recall, báo nhầm theo từng mã lỗi, tách code và agent | M3 |
| `v_eval_funnel` | Tỉ lệ từng bước, tuyệt đối và có điều kiện, theo task và theo mức | M6 |
| `v_system_check` | Chẩn đoán hệ thống từng episode, kèm mã đã nổ và mã không chấm được (bản 0.3) | M6, M7 |
| `v_branch_comparison` | Tỉ lệ thành công cạnh chi phí theo (task, nhánh) | M1, M9 |
| `v_he_curve` | Tỉ lệ thành công theo (biến thể, N, seed) | M9 |
| `v_cluster_board` | Cụm, chẩn đoán, số thành viên, có tiêu ngân sách hay không, link card | M7 |
| `v_cost_by_branch`, `v_cost_by_intervention` | Chi phí ước tính và thực đo; phút người và GPU-giờ tách riêng | M8 |
| `v_cost_data_allocation` | BR-05: chi phí thực đo của mỗi lô chia cho thí nghiệm theo episode đã dùng, một dòng cho mỗi (thí nghiệm, lô) (bản 0.4) | M8 |
| `v_r_demo` | Số demo người theo nhánh: đếm episode `is_root AND operator_kind='human'`; không gồm điểm HE (bản 0.4) | M8 |
| `v_action_status` | Mỗi `human_actions` kèm trạng thái hiện tại của bản ghi đích | Mọi màn hình có nút |
| `v_sync_health` | Lần import gần nhất, độ trễ, số dòng bị từ chối | M1, M10 |

Quy tắc lọc chung: mọi view lọc `is_deleted = FALSE`; view eval có cột `is_sealed`; role `agent_ro` chỉ đọc bản `*_agent` đã lọc cứng dòng niêm phong và không join nhóm S.

## 5. Luồng nghiệp vụ

### 5.1 Luồng 1 — nạp dữ liệu và pipeline 6 tầng

Tên sáu tầng đã chốt: **1 Ingest, 2 Normalize, 3 Annotate, 4 QA, 5 Release, 6 Export**.

| \# | Việc | Ai | Ghi vào |
|---|---|---|---|
| 1 | Tạo phiếu nạp: nguồn, giấy phép, `data_class`; tải file; bật duyệt tay; với kịch bản thử thì bật lỗi cấy | Web | `dataset_intakes` (DRAFT), file vào `$FW_WEB_BLOBS` |
| 2 | Nộp phiếu | Web | `human_actions` `INTAKE_SUBMIT` → `intake.json` |
| 3 | Tạo dataset và 6 attempt PENDING | Lõi | `datasets` (INGESTED), `pipeline_stage_runs`; phiếu chuyển ACCEPTED |
| 4 | Chạy tầng i. Tầng 1–4 xuất `episodes` và `episode_qa_reports` | Lõi | `pipeline_stage_runs`, `episodes`, `episode_qa_reports` |
| 5 | Tầng 4 chạy 7 phép kiểm và phát lại action. **Đây là cổng** | Lõi | `episode_qa_reports`, `pipeline_stage_runs` |
| 6 | Agent QA trả `qa_agent_verdict`, `detected_anomalies`, `remediation_suggestion`. Agent **không** đổi cổng | Lõi | `pipeline_stage_runs.qa_agent_report` |
| 7 | Rẽ nhánh: pass và không bật duyệt tay → PASSED. Còn lại → PAUSED_FOR_REVIEW | Lõi | `pipeline_stage_runs`; web bắn chuông |
| 8 | Người chọn `RETRY_STAGE`, `APPLY_FIX_AND_RETRY`, `FORCE_CONTINUE` (bắt buộc ghi chú) hoặc `ABORT_PIPELINE` | Web | `human_actions` `STAGE_REVIEW` |
| 9 | Áp dụng lựa chọn. Chạy lại từ tầng k: sinh attempt mới cho k..6, attempt cũ `is_current = FALSE` | Lõi | `pipeline_stage_runs`, `decisions` |
| 10 | Tầng 6 đạt: tạo release nháp + `release_items`; dataset READY_FOR_TRAINING | Lõi | `releases`, `release_items`, `datasets` |

### 5.2 Luồng 2 — huấn luyện và đánh giá

| \# | Việc | Ai | Ghi vào |
|---|---|---|---|
| 1 | Tạo bản nháp: task, nhánh, phương pháp, giả thuyết, checkpoint gốc, RunPlan, hyperparameter, release và tỉ trọng | Web | `experiment_drafts` (DRAFT) |
| 2 | Nộp bản nháp. C5, C7, C15 chạy | Web | `human_actions` `EXPERIMENT_SUBMIT` → RunPlan nháp + `job_request` TRAIN |
| 3 | Nhận yêu cầu: tạo thí nghiệm QUEUED, đóng băng RunPlan có hash | Lõi | `experiments`, `run_plans` |
| 4 | Train: gửi `training_metrics` theo step, cả train và val. Xong thì ghi checkpoint, chạy chẩn đoán train, ghi bút toán GPU-giờ | Lõi | `training_metrics`, `model_checkpoints`, `train_diagnoses`, `cost_ledger_entries` |
| 5 | Probe P1–P4 trên checkpoint | Lõi | `probe_results` |
| 6 | Đánh giá: một `sim_evaluations` cho mỗi (checkpoint, tập điều kiện, mức, renderer, chế độ). Mỗi episode một dòng, **kể cả thành công và lỗi hạ tầng** | Lõi | `sim_evaluations`, `eval_episodes` |
| 7 | Tổng hợp: `success_count` lấy từ cờ simulator; phễu theo bước lấy từ `step_status` | Lõi | `sim_evaluations` |
| 8 | Đối chiếu: lệch giữa scorer và cờ sim vượt 5% thì bắn cảnh báo | Web | View `v_eval_funnel`; `notifications` |

### 5.3 Luồng 3 — Failure → Data, 12 bước

| Bước | Việc | Ai | Ghi vào |
|---|---|---|---|
| 1 | Chạy policy trên 90 điều kiện dev | Lõi | `sim_evaluations`, `eval_episodes` |
| 2 | Gán nhãn bước hỏng và kiểu lỗi | Lõi | `eval_episodes` |
| 3 | Gom cụm theo (bước hỏng, kiểu lỗi, mức), chọn tối đa 5 đại diện | Lõi | `failure_clusters` |
| 4 | Kiểm hệ thống R1–R6. Chạy cho **mọi** episode lỗi | Lõi | **`system_diagnoses`** (bản 0.3), rồi tổng hợp vào `failure_clusters.checks` |
| 5 | Kiểm khả thi: planner chuẩn từ cùng điều kiện đầu | Lõi | `diagnostic_runs` |
| 6 | Khoanh vùng: 10 lượt từ trạng thái chuẩn ở đầu bước hỏng | Lõi | `diagnostic_runs` |
| 7 | Kiểm thị giác: giữ vật lý, đổi hình ảnh về mức chuẩn | Lõi | `diagnostic_runs` |
| 8 | Kiểm vùng phủ: có trong miền train không, khoảng cách kNN | Lõi | `failure_clusters.checks` |
| 9 | Chẩn đoán cụm theo đa số; hoà thì kỹ sư quyết | Lõi + Web | `failure_clusters.diagnosis`; ghi đè qua `DIAGNOSIS_OVERRIDE` |
| 10 | Đề xuất và định lượng can thiệp | Lõi | `interventions` |
| 11 | Chọn theo lợi ích trên chi phí trong ngân sách | Lõi | `interventions.status` |
| — | **Kỹ sư duyệt, duyệt có sửa, hoặc từ chối** | Web | `human_actions` `RECOMMENDATION_DECISION` → `Decision` |
| 12 | Thu dữ liệu, QA, train lại, cổng dev, đo tỉ lệ sửa được có đối chứng | Lõi | `fix_rate_events`, `decisions` |

Bốn điểm phải hiển thị đúng ở M7:

- **Bước 4–8 chạy theo đại diện.** Bước 4 và 8 rẻ nên chạy cho mọi lỗi; bước 5, 6, 7 đắt nên tối đa 5 đại diện mỗi cụm.
- **Thứ tự cố định: hệ thống trước, dữ liệu sau.** Cụm đã có chẩn đoán hệ thống thì dừng.
- **Chỉ 3 trong 11 chẩn đoán tiêu ngân sách dữ liệu.** Tám chẩn đoán còn lại ra `repair_tickets` hoặc chỉ ghi nhận.
- **Phép kiểm không chạy được thì hiện `skipped` kèm lý do**, không hiện `failed`. Đây chính là lý do `system_diagnoses.skipped` tồn tại: không có nó thì FE không phân biệt được hai trạng thái này.

Công thức bước 11:

```
n_eff = min(m_cụm, L_loại)            L mặc định 10 cho mọi loại can thiệp
f̄     = α / (α + β)                   α, β từ fix_rate_events, prior Beta(1, 1)
g     = (n_eff / 90) × f̄              điểm % trên dev
c     = đơn giá(loại) × số lượng(n_eff)
```

Chọn tham lam theo `g / c` giảm dần, dừng khi hết ngân sách. Hoà thì ưu tiên cụm có bước hỏng sớm hơn. Ngân sách là **ba trần song song**: USD, phút người, GPU-giờ. Vượt trần nào cũng dừng. Khi kỹ sư duyệt có sửa số lượng, API tính lại tổng; vượt trần thì trả BR-07.

### 5.4 Luồng 4 — chat agent

1. Ngữ cảnh dùng cột riêng theo loại bản ghi, có khoá ngoại thật, thay cho `context_ref_id` đa hình.
2. Kết nối của agent dùng role `agent_ro`: không đọc được nhóm S, không đọc được eval đang niêm phong. Bản ghi `data_class` khác `public` bị lọc trước khi dựng prompt (R6).
3. `context_snapshot` lưu danh sách ID đã nạp cộng sha256 của prompt, không lưu nguyên khối.
4. Hành động agent đề xuất chỉ hiện thành nút. Người bấm xác nhận thì API tạo `human_actions` `CHAT_ACTION_CONFIRM` qua đúng các endpoint công khai của luồng 1–3, kèm `Idempotency-Key`.

### 5.5 Luồng 5 — đồng bộ với lõi

| Lệnh | Việc | Lịch |
|---|---|---|
| `fwsync import --from <dir>` | Nạp artifact vào bảng P, upsert theo ID nội dung, idempotent | 5 phút một lần + bấm tay ở M10 |
| `fwsync export --to <dir>` | Xuất `human_actions` đang PENDING thành artifact | Ngay sau khi có hành động mới + 5 phút một lần |
| `fwsync verify` | So số dòng và hash giữa DB và nguồn; chênh thì báo, **không tự sửa** | Mỗi đêm + bấm tay |

Mỗi lần chạy ghi một dòng `sync_runs`. `fwsync` không chạy quá 15 phút thì chuông báo. Sau mỗi lần import, `fw_sync` phát `NOTIFY fw_changed`; SSE đẩy xuống FE.

**Vòng đời một hành động:**

| `sync_status` | Nghĩa | FE hiện |
|---|---|---|
| PENDING | Đã ghi, chưa xuất ra outbox | "Đang chờ gửi" |
| EXPORTED | Đã nằm trong outbox, lõi chưa áp dụng | "Đang đồng bộ"; quá 30 phút thì chuông |
| APPLIED | `fwsync import` gặp artifact có `source_action_id` này | Trạng thái mới của bản ghi đích |
| REJECTED | Lõi từ chối, có `reject_reason` | Nhãn đỏ kèm lý do |

## 6. Website

Mười màn hình, một ngăn chat và một chuông. Thanh điều hướng xếp đúng thứ tự vòng flywheel: **M1 Tổng quan · M2 Dữ liệu · M3 Agent QA/QC · M4 Release · M5 Huấn luyện · M6 Đánh giá · M7 Failure→Data · M8 Chi phí · M9 Kết quả · M10 Kiểm toán**.

Năm màn hình **lõi** (M2, M6, M7, M8, M9) là kế hoạch chính. Năm màn hình còn lại là **làm thêm**.

### 6.1 Năm màn hình lõi

**M7 · Failure → Data** — ba cột.

- **Cột trái, tiến trình 12 bước.** Trạng thái, thời gian, số rollout chẩn đoán đã tốn; bước bỏ qua hiện `skipped` kèm lý do.
- **Cột giữa, bảng cụm.** Bước hỏng, kiểu lỗi, mức, số thành viên, chip chẩn đoán (xám = hệ thống, xanh = dữ liệu, vàng = chỉ ghi nhận), cờ có tiêu ngân sách. Mở cụm ra là evidence card: từng phép kiểm với giá trị và ngưỡng, **cộng mã không chấm được kèm lý do**, video đại diện, chẩn đoán, can thiệp đề xuất, lợi ích kỳ vọng, chi phí ước tính. Nút "ghi đè chẩn đoán" bắt buộc ghi lý do.
- **Cột phải, đề xuất và ngân sách.** Can thiệp xếp theo `g / c`, chỉnh được số lượng. Ba thanh ngân sách cập nhật ngay. Ba nút: duyệt, duyệt có sửa, từ chối.
- **Dưới cùng, phiếu sửa** sinh từ cụm lỗi hệ thống, kèm cảnh báo "sửa xong phải đo lại baseline".
- Nguồn: `v_cluster_board`, `v_system_check`, `flywheel_algo_steps`, `diagnostic_runs`, `interventions`, `fix_rate_events`, `repair_tickets`.

**M6 · Đánh giá và bảng lỗi**

- Chọn task trước. Phễu có đúng số bước của task đó, 6 bước (hai bàn) hoặc 7 bước (khay).
- Lọc theo mức (0, 1, 2), renderer, chế độ đồng bộ, tập (dev / holdout).
- Hai con số cạnh nhau: cờ simulator và kết luận scorer, cảnh báo khi lệch quá 5%.
- Số episode bị loại vì lỗi hạ tầng, tách khỏi mẫu số.
- Bảng lỗi 5 họ (F-DATA, F-TRAIN, F-OFF, F-CL, F-SYS). Họ F-SYS đọc từ `v_system_check`, và **mã không chấm được hiện riêng, không gộp vào "không lỗi"**.
- Trình phát clip lỗi, log quỹ đạo, sai số bám lệnh theo nhóm (từ `system_diagnoses.measurements`).
- Nguồn: `v_eval_funnel`, `v_system_check`, `eval_episodes`, `train_diagnoses`, `sim_evaluations`.

**M2 · Dữ liệu và pipeline 6 tầng**

- Danh sách lô: mã, nguồn, loại dữ liệu, `data_class`, giấy phép, số episode, trạng thái. Phiếu nạp đang chờ hiện ở đầu với nhãn "đang đồng bộ".
- Stepper 6 tầng. Mỗi tầng có **hai** nhãn: kết quả phép kiểm code và nhận xét của agent.
- Báo cáo dataset: số episode theo nguồn, pass / flag / quarantine / reject theo từng phép kiểm, phân bố điều kiện, độ dài episode, thống kê theo nhóm action.
- Kết quả phát lại action: video phát lại cạnh video gốc, danh sách khung lỗi.
- Lịch sử attempt. Egocentric: cột `deid_status`; còn `raw` thì khoá mọi thao tác chia tập.
- Nguồn: `datasets`, `dataset_intakes`, `v_pipeline_current`, `episodes`, `v_dataset_report`, `pipeline_stage_runs`.

**M9 · Kết quả và so sánh nhánh**

- Đường cong E1 theo số demo và phương pháp; đánh dấu D\*.
- Đường cong HE: V-EGO, V-EGO10, V-NOEGO theo N ∈ {10, 20, 40, 80}, có khoảng tin cậy, đánh dấu N₅₀.
- Task khay: A, C, B và tầng phụ C-EGO, C-NOEGO.
- Bảng theo mức, báo riêng Level 1 và Level 2 so với mốc 70%.
- Video ba cột cùng điều kiện; tỉ lệ thành công đặt cạnh chi phí.
- Nhãn rõ dev hay holdout; holdout chưa mở niêm phong thì hiện ổ khoá.
- Nguồn: `v_he_curve`, `v_branch_comparison`, `sim_evaluations`.

**M8 · Sổ chi phí và kinh tế**

- Sổ lọc theo nhánh, vòng, cụm, can thiệp, loại nguồn lực; ước tính và thực đo cạnh nhau; bút toán đảo hiện rõ.
- Bốn chỉ số: số demo người để đạt ngưỡng; phút operator mỗi điểm %; chi phí mỗi điểm % của C so với B; sai số dự báo chi phí.
- `r_demo` theo nhánh. Bảng độ nhạy bốn kịch bản giá.
- Hai ràng buộc báo riêng: phút người và GPU-giờ.
- Nguồn: `cost_ledger_entries`, `price_books`, `v_cost_by_branch`, `v_cost_by_intervention`, `v_r_demo`.

### 6.2 Năm màn hình làm thêm

| Màn hình | Bản đầy đủ | Bản tối thiểu nếu trễ |
|---|---|---|
| M1 · Tổng quan | Sáu thẻ đúng sáu phần kịch bản demo 17/11, mỗi thẻ có trạng thái, số đo chính, nút mở màn hình liên quan; dải trạng thái hệ thống; dòng tóm tắt | Sáu thẻ, mỗi thẻ một link |
| M3 · Agent QA/QC | Bảng điểm precision / recall / báo nhầm theo từng mã lỗi, hai cột code và agent; thời gian tới khi có báo cáo; một báo cáo agent mẫu; model và hash prompt | Bảng điểm |
| M4 · Release | Danh sách release (hash, nháp / đóng băng, release cha, giấy phép gộp, số item); guard chia tập; export LeRobot v2.1 / v3; cây lineage; nút yêu cầu đóng băng | Danh sách + manifest |
| M5 · Huấn luyện | Form bản nháp; thẻ RunPlan có hash; loss train và val, LR, GPU, thông lượng, loss theo nhóm action; bảng T1–T8, O1–O4 **kèm mã bị bỏ qua**; probe P1–P4 so với checkpoint cha | Form + biểu đồ loss + bảng chẩn đoán |
| M10 · Kiểm toán | Nhật ký `decisions`; tỉ lệ kỹ sư ghi đè; hành động chưa áp dụng; lịch sử `fwsync`; chênh lệch DB và nguồn; danh sách RunPlan | Nhật ký + lịch sử đồng bộ |

**Ngăn chat và chuông.** Ngăn chat bên phải tự nhận màn hình đang mở và bản ghi đang chọn. Chat là phần **cắt đầu tiên** nếu trễ: bản tối thiểu chỉ đọc. Chuông báo khi: tầng dừng chờ duyệt, train xong, train hỏng, eval xong, khuyến nghị chờ duyệt, phiếu sửa mới, vượt ngân sách, đồng bộ trễ, hành động bị lõi từ chối.

### 6.3 Component dùng chung

| Component | Việc |
|---|---|
| `DiagnosisChip` | 11 chẩn đoán cụm, ba màu theo nhóm hệ thống / dữ liệu / chỉ ghi nhận |
| `SystemVerdictChip` | 7 chẩn đoán episode của `system_diagnoses`, kèm dạng riêng cho `unknown` (bản 0.3) |
| `StepFunnel` | Phễu theo số bước của task, tuyệt đối và có điều kiện |
| `BudgetBar` | Một trần ngân sách: đã dùng, đề xuất, còn lại |
| `HashBadge` | Hash rút gọn 8 ký tự, bấm để chép bản đầy đủ |
| `EmptyState` | Hiện "chưa chạy", không bao giờ hiện số 0 khi chưa có dữ liệu |
| `SkippedList` | Mã không chấm được kèm lý do; dùng ở M5, M6, M7 (bản 0.3) |
| `ActionStatus` | Nhãn theo vòng đời `sync_status` |
| `SealedLock` | Ổ khoá cho holdout chưa mở niêm phong |
| `MockBadge` | Nhãn "mock" trên mọi bản ghi `origin = 'mock'` |

### 6.4 Quy ước FE

- **Mock ở tầng mạng.** MSW chặn đúng các endpoint ở mục 7, trả dữ liệu dựng từ `mock/demo-17-11/`. Component luôn gọi API thật; tắt MSW là chuyển sang BE.
- **Type sinh từ contract** bằng `json-schema-to-typescript`, chạy lại mỗi khi `flywheel-contracts` đổi: `npm run gen:types`; CI chạy `npm run check:types` và đỏ khi file sinh ra cũ hơn hợp đồng. Type của response API xem §7.4.
- **Sau khi bấm nút ghi**, không cập nhật lạc quan. Hiện `ActionStatus` và chờ SSE `fw_changed`.
- **`Idempotency-Key`** sinh một lần cho mỗi lần bấm, giữ nguyên khi retry.
- **Biểu đồ train** luôn gọi kèm `?every=` để lấy mẫu thưa.
- **Nhánh luôn đi kèm `task_id`**, kể cả trong query key của TanStack Query.
- **Không bao giờ vẽ "không có lỗi" từ một giá trị NULL.** Thiếu số là `EmptyState` hoặc `SkippedList`, không phải số 0 (bản 0.3).

## 7. API

**Đọc** (GET) đi thẳng vào view và bảng. **Ghi** chỉ chạm bảng W và trả về `action_id`.

### 7.1 Đọc

| Nhóm | Endpoint |
|---|---|
| Dữ liệu | `GET /datasets`, `/datasets/{id}`, `/datasets/{id}/stages`, `/datasets/{id}/episodes`, `/datasets/{id}/report`, `/intakes` |
| Lỗi cấy | `GET /defects/scoreboard`, `/defects/scores` |
| Release | `GET /releases`, `/releases/{id}/items` |
| Huấn luyện | `GET /experiments`, `/experiment-drafts`, `/experiments/{id}/metrics?split=&every=`, `/experiments/{id}/diagnoses`, `/experiments/{id}/probes`, `/experiments/{id}/checkpoints` |
| Đánh giá | `GET /evaluations`, `/evaluations/{id}`, `/evaluations/{id}/episodes`, `/evaluations/{id}/funnel`, `/evaluations/{id}/failures`, `/evaluations/{id}/system-checks` |
| Flywheel | `GET /recommendations`, `/recommendations/{id}`, `/recommendations/{id}/steps`, `/recommendations/{id}/clusters`, `/clusters/{id}/card`, `/repair-tickets`, `/fix-rates` |
| Chi phí | `GET /cost/ledger`, `/cost/by-branch`, `/cost/by-intervention`, `/cost/sensitivity?price_book=` |
| Kết quả | `GET /results/branches?task_id=`, `/results/he-curve`, `/results/e1-curve` |
| Hệ thống | `GET /actions/{id}`, `/actions?sync_status=`, `/notifications/stream` (SSE), `/sync/runs`, `/decisions` |

### 7.2 Ghi

| Endpoint | Ghi vào | `action_kind` |
|---|---|---|
| `POST /intakes`, `PATCH /intakes/{id}` | `dataset_intakes` (nháp) | — |
| `POST /intakes/{id}/submit` | `dataset_intakes`, `human_actions` | `INTAKE_SUBMIT` |
| `POST /uploads` | `$FW_WEB_BLOBS` | — |
| `POST /stage-runs/{id}/review` | `human_actions` | `STAGE_REVIEW` |
| `POST /experiment-drafts`, `PATCH /experiment-drafts/{id}` | `experiment_drafts` (nháp) | — |
| `POST /experiment-drafts/{id}/submit` | `experiment_drafts`, `human_actions`, `job_requests` | `EXPERIMENT_SUBMIT` |
| `POST /releases/{id}/freeze-request` | `human_actions`, `job_requests` | `RELEASE_FREEZE_REQUEST` |
| `POST /evaluation-requests` | `human_actions`, `job_requests` | `EVAL_REQUEST` |
| `POST /flywheel-runs` | `human_actions`, `job_requests` | `FLYWHEEL_RUN_REQUEST` |
| `POST /recommendations/{id}/decision` | `human_actions` | `RECOMMENDATION_DECISION` |
| `POST /clusters/{id}/diagnosis-override` | `human_actions` | `DIAGNOSIS_OVERRIDE` |
| `POST /evaluations/{id}/unseal` (chỉ ADMIN) | `human_actions` | `HOLDOUT_UNSEAL` |
| `POST /{resource}/{id}/delete` (chỉ ADMIN, LEAD) | `human_actions` | `SOFT_DELETE` |
| `POST /chat/sessions`, `POST /chat/sessions/{id}/messages` | Bảng chat | — |
| `POST /chat/actions/{id}/confirm` | `human_actions` | `CHAT_ACTION_CONFIRM` |
| `POST /sync/run` (chỉ ADMIN, LEAD) | `jobs` | — |

### 7.3 Quy ước

- Endpoint tạo hành động trả **202 Accepted** với thân `{action_id, sync_status}`. Không trả bản ghi đích.
- Bắt buộc header `Idempotency-Key`. Gửi lại cùng key thì nhận lại cùng `action_id` (C16).
- Endpoint danh sách có phân trang (`cursor`, `limit`), lọc và sắp xếp. Mặc định ẩn bản ghi xoá mềm; `?include_deleted=true` chỉ cho ADMIN và LEAD (BR-11).
- Mọi endpoint trả eval bỏ bản niêm phong với mọi vai trừ ADMIN (BR-10).
- Mọi bản ghi trả về có trường `origin` (`core` / `mock`).
- Lỗi theo một khuôn: `{code, message, hint, ref}`. Lỗi luật thì `code` là mã business rule; trùng nộp thì 409 với `code = "ALREADY_SUBMITTED"`.

Ví dụ duyệt đề xuất:

```http
POST /recommendations/7b1e.../decision
Idempotency-Key: 9f2c4a10-...

{
  "items": [
    {"intervention_id": "a1...", "decision": "APPROVE"},
    {"intervention_id": "b2...", "decision": "APPROVE_EDITED", "approved_quantity": 6,
     "reason": "Giảm vì thiếu operator tuần này"},
    {"intervention_id": "c3...", "decision": "REJECT", "reason": "Cụm đã có phiếu sửa calibration"}
  ]
}

→ 202 {"action_id": "e4...", "sync_status": "PENDING"}
```

### 7.4 Hình dạng response (bản 0.4)

Nguồn duy nhất là [`fe/src/api/types.ts`](fe/src/api/types.ts). Mỗi kiểu ứng với đúng một view hoặc bảng ở `schema/70-views.sql`, cột nào ra trường nấy, để tầng FastAPI (mốc M2) trả dòng view mà không đổi tên. Bộ handler MSW ở `fe/src/mocks/` dựng đúng các hình dạng này từ `mock/demo-17-11/`, và `fe/src/mocks/handlers.test.ts` là nghiệm thu của M0.

| Màn hình | Endpoint | Kiểu trả về | Ghi chú |
|---|---|---|---|
| M7 | `GET /recommendations` | `RecommendationSummary[]` | Mới ở 0.4: M7 cần biết lượt nào đang mở trước khi có id |
| M7 | `GET /recommendations/{id}` | `Recommendation` | Mang luôn **ba trần ngân sách** (`used`, `proposed`, `remaining`) và **can thiệp xếp theo g/c**, vì cột phải cần cả hai trong một lần đọc |
| M7 | `/steps`, `/clusters`, `/clusters/{id}/card` | `AlgoStep[]`, `ClusterBoardRow[]`, `ClusterCard` | Card gộp mã không chấm được từ **ba nguồn** (bước thuật toán, phép kiểm chẩn đoán, kiểm hệ thống từng episode) vào một `skipped` |
| M7 | `/repair-tickets?recommendation_id=`, `/fix-rates` | `RepairTicket[]`, `FixRate[]` | Loại can thiệp không có dòng `FixRate` chỉ có prior Beta(1, 1) |
| M6 | `GET /evaluations`, `GET /evaluations/{id}` | `Page<EvaluationSummary>`, `EvaluationSummary` | `GET /evaluations/{id}` mới ở 0.4. Mang `step_names` để phễu có đúng số bước của task |
| M6 | `/episodes`, `/funnel`, `/system-checks` | `Page<EvalEpisodeRow>`, `FunnelRow[]`, `SystemCheckRow[]` | |
| M6 | `/failures` | `FailureBoard` | Năm họ, mỗi họ có `status`: `not_run` khi không ai sinh họ đó cho lượt eval này, khác với `ok` mà không có dòng nào |
| M2 | `GET /datasets`, `/{id}`, `/{id}/stages`, `/{id}/episodes`, `/{id}/report`, `/intakes` | `Page<DatasetRow>`, `DatasetRow`, `PipelineView`, `Page<EpisodeRow>`, `DatasetReport`, `Page<…>` | `PipelineView` có cả stepper hiện hành lẫn mọi attempt |
| M9 | `/results/branches?task_id=`, `/results/he-curve`, `/results/e1-curve` | `BranchComparisonRow[]`, `HeCurvePoint[]`, `E1CurvePoint[]` | Thiếu `task_id` → 400 |
| M10, chuông | `GET /actions?sync_status=`, `/actions/{id}`, `/decisions`, `/sync/runs`; `POST /sync/run` | `Page<ActionStatusRow>`, `ActionStatusRow`, `Page<DecisionRow>`, `SyncRunRow[]`, `SyncRunRow` | Chuông không có bảng riêng: FE suy thông báo từ khuyến nghị, lô, phiếu sửa và hành động. Hành động EXPORTED quá 30 phút là "đồng bộ trễ" |
| M8 | `/cost/ledger`, `/cost/by-branch`, `/cost/by-intervention`, `/cost/sensitivity` | `Page<LedgerRow>`, `CostByBranch`, `InterventionRow[]`, `SensitivityRow[]` | `CostByBranch` mang luôn `r_demo` và `data_allocation` (BR-05). Độ nhạy định giá lại từng bút toán theo tỉ lệ giá của bảng mới so với bảng đã ghi |

Bốn quy ước thêm ở bản 0.4:

- Trang danh sách là `{items, next_cursor, total}`.
- Trước khi có phiên đăng nhập, vai lấy từ header `X-Fw-Role` (mặc định `ML_ENGINEER`). Chỉ MSW và môi trường dev dùng header này; API thật lấy vai từ phiên.
- Trong bộ mock, id là chính mã `*_ref` của file (`clu_1`, `ev_B_dev`); trong DB là UUID. FE không được suy gì từ hình dạng của id.
- Type của artifact **hợp đồng** sinh bằng `json-schema-to-typescript` vào `fe/src/contracts/schemas/` (§6.4). Type của **response** viết tay ở `types.ts`, vì API trả dòng view chứ không trả artifact; tên trường vẫn lấy từ hợp đồng (§1 điểm 5).

## 8. Business rules

| Mã | Luật | Cưỡng chế |
|---|---|---|
| BR-01 | Release được vào thí nghiệm khi: đã đóng băng, chưa xoá, **không chứa episode có `benchmark_copy_id`**; checkpoint gốc sạch; nhánh hợp lệ với task | C7 khi nộp bản nháp |
| BR-02 | Chạy lại tầng k sinh attempt mới cho k..6; attempt cũ giữ làm lịch sử | Lõi thực hiện; web gửi `STAGE_REVIEW`; C2, C3 là lưới an toàn |
| BR-03 | Bản nháp thí nghiệm chỉ sửa khi DRAFT; nộp cần ≥ 1 release và tổng tỉ trọng bằng 1 | C5, C6 |
| BR-04 | `FORCE_CONTINUE` bắt buộc ghi chú và sinh một `Decision` | API kiểm payload; lõi sinh `Decision` |
| BR-05 | Chi phí dữ liệu ghi một lần theo dataset lúc nạp. Chi phí một thí nghiệm = chi phí dataset × (episode dùng ÷ tổng episode) | C10, C11; view `v_cost_data_allocation` (bản 0.4) |
| BR-06 | Sổ chỉ được thêm; sửa sai bằng bút toán đảo mang số âm | C8, C9 |
| BR-07 | Ngân sách một vòng có ba trần song song: USD, phút người, GPU-giờ. Chỉ `TRANG_THAI_DAU_XAU`, `THIEU_VUNG_PHU`, `KY_NANG_YEU` được tiêu ngân sách dữ liệu | Cột sinh `consumes_data_budget`; API chặn duyệt vượt trần |
| BR-08 | Lô có lỗi cấy phải khai đủ trong `defect_items`; agent không đọc được đáp án; mỗi lần chấm là một dòng mới. **Đáp án không bao giờ nằm trên `episodes`** | Role `agent_ro`; `defect_scores` append-only; C19 |
| BR-09 | Episode egocentric `deid_status = 'raw'` không được gán split và không vào release | C14 |
| BR-10 | Eval có `sealed_until` ở tương lai chỉ ADMIN xem; mở niêm phong phải ghi lý do và sinh một `Decision` | API lọc theo vai; `HOLDOUT_UNSEAL` bắt buộc `reason` |
| BR-11 | Mọi GET danh sách ẩn bản ghi xoá mềm; `?include_deleted=true` chỉ cho ADMIN và LEAD. Bản ghi xoá mềm vẫn tính vào sổ chi phí | View + API |
| **BR-12** | **Một phép kiểm không chạy được không bao giờ hiển thị là "không có lỗi".** Mọi màn hình có bảng chẩn đoán phải hiện danh sách mã bị bỏ qua kèm lý do | C17; `SkippedList` ở FE (bản 0.3) |

## 9. Kế hoạch

Hôm nay 3/11/2026, demo 17/11/2026, còn 14 ngày. Châu làm cả FE, BE và bộ nạp (quyết định 3/11), nên rủi ro W2 của bản 0.2 không còn là chặn, nhưng tổng giờ thì không đổi.

### 9.1 Nguyên tắc

1. **Mock trước.** FE không chờ BE, BE không chờ lõi. FE mock ở tầng mạng bằng MSW; BE nạp mock bằng `fwsync`; vòng ghi thử bằng một **lõi giả** (`fwsync fake-core`).
2. **Ưu tiên theo màn hình ăn điểm:** M7 > M6 > M2 > M9 > M8 > M3 > M1 > M5 > M4 > M10.
3. **Mỗi mốc phải chạy được end-to-end.**
4. **Phần FE trên MSW không thêm dịch vụ nào**, nên đi được ngay. Phần Postgres và FastAPI chờ PO đổi ADR-13 (xem Change log).

### 9.2 Mốc

| Mốc | Hạn | Giao nộp | Nghiệm thu |
|---|---|---|---|
| M0 · Chốt hợp đồng | 4/11 | Enum (Phụ lục A) đối chiếu xong với `flywheel-contracts`; hình dạng response GET cho 5 màn hình lõi; bộ mock tối thiểu cho M7 | Test so enum xanh; MSW trả được mock M7 |
| M1 · Schema và bộ nạp | 6/11 | `schema.sql` 41 bảng, migration Alembic, 3 role, `fwsync import` trên bộ mock, trigger và CHECK của mục 4.5 | Nạp mock hai lần cho cùng kết quả; mỗi luật một ca đúng và một ca sai; `fw_api` không ghi được bảng P |
| M2 · API đọc | 8/11 | Toàn bộ endpoint mục 7.1; SSE | Postman collection chạy hết |
| M3 · 4 màn hình lõi | 10/11 | M7, M6, M2, M9 chạy trên API thật | Đi hết kịch bản demo bằng chuột, không chỗ nào trắng |
| M4 · Hành động | 12/11 | Endpoint mục 7.2, `fwsync export`, `fwsync fake-core`, vòng đời hành động trên FE, chuông; chat chỉ đọc | Bấm duyệt → artifact trong outbox → lõi giả áp dụng → nạp lại thấy APPLIED |
| M5 · Màn hình còn lại | 14/11 | M8 đầy đủ; M1, M3, M4, M5, M10 ít nhất bản tối thiểu | Danh sách mục 1.1 không còn dòng nào thiếu màn hình |
| M6 · Ghép dữ liệu thật | 15/11 | `fwsync` trỏ sang output thật của lõi; phần chưa có giữ mock, FE dán nhãn theo `origin` | Ít nhất pipeline và một lượt eval là dữ liệu thật |
| M7 · Tổng duyệt | 16/11 | Chạy trọn kịch bản hai lần liên tiếp; công tắc chuyển sang mock dự phòng | Hai lần không lỗi |

**Trạng thái 5/11/2026.** M0 đạt: test so enum xanh, và MSW trả bộ mock của cả 5 màn hình lõi (`fe/src/mocks/handlers.test.ts`, 18 ca), trễ 1 ngày so với hạn. M1 mới đạt phần không cần database: 41 bảng, 3 role, trigger, `fwsync import` nạp hai lần cho cùng kết quả trên sink JSONL. Còn thiếu migration Alembic, ca đúng/ca sai của từng luật trên Postgres thật, và kiểm `fw_api` không ghi được bảng P; cả ba chờ Postgres 16 và W8. Màn hình M7 đã chạy trên MSW, đi trước phần FE của M3. M2 (API đọc) đạt trên sink JSONL: mọi endpoint §7.1 trả đúng response MSW trả (`tests/test_api.py`, 38 ca đối chiếu); còn thiếu SSE và bản Postgres. Bốn màn lõi của M3 (M7, M6, M2, M9) đã chạy, cả trên MSW lẫn trên API sink; bộ mock nay có đủ bốn nhánh và lưới HE 3 biến thể × N ∈ {10, 20, 40, 80}, nên M9 vẽ được cả bảng nhánh lẫn đường cong HE. M8 đã chạy: đủ năm màn lõi. Trong bốn chỉ số của M8, bộ mock cho số thật ở hai chỉ số (demo người để đạt 50%, phút operator mỗi điểm %); hai chỉ số còn lại hiện "chưa có" vì chưa có nhánh C và chưa bút toán nào có cả ước tính lẫn thực đo. M4 đạt trên sink JSONL: bấm duyệt → outbox → lõi giả áp dụng → nạp lại thấy APPLIED, cả bằng lệnh (`tests/test_action_loop.py`), qua HTTP (`tests/test_api.py::test_click_to_applied`) lẫn trên FE (`fe/src/screens/Audit.test.tsx`). Còn thiếu ở M4: SSE (FE hỏi lại 10 giây một lần), REJECTED từ lõi (chờ artifact `JobStatus`, W7), và chat chỉ đọc.

### 9.3 Môi trường cần có

| Thứ | Trạng thái 3/11 | Cần cho mốc |
|---|---|---|
| Node 24, npm 11 | **có** | M0 trở đi |
| PostgreSQL 16 | **chưa cài** | M1 (6/11) |
| Docker | chưa cài | không bắt buộc |
| Quyết định ADR-13 | chưa có | M1 (6/11) |

### 9.4 Rủi ro

| Rủi ro | Dấu hiệu sớm | Phương án |
|---|---|---|
| ADR-13 không được đổi | PO từ chối thêm DB server ở L0 | FE giữ nguyên trên MSW; thay Postgres bằng đọc trực tiếp JSONL của lõi qua DuckDB, mất phần ghi (`human_actions`) |
| Chưa cài Postgres | 5/11 vẫn chưa có | M1 trễ; FE không ảnh hưởng |
| Lõi chưa sinh dữ liệu thật kịp 15/11 | 10/11 chưa có artifact thật nào | Demo trên mock, nhãn "mock" trên từng bản ghi |
| Hợp đồng còn đổi | PR hợp đồng mở sau 5/11 | Bộ nạp khoan dung: trường lạ bỏ qua và ghi log, trường thiếu dùng mặc định |
| M7 không có dữ liệu | 8/11 chưa có cụm nào | Dùng lượt mock đầy đủ, có cả cụm hệ thống lẫn cụm dữ liệu |
| Trễ | Mốc M3 trễ quá 1 ngày | Năm màn hình làm thêm chỉ làm bản tối thiểu; cắt chat |
| Số trên web lệch số trong báo cáo của lõi | `fwsync verify` báo chênh | Dừng, sửa bộ nạp. Không bao giờ sửa số trong DB bằng tay |
| Việc làn Đánh giá trễ hạn | DA-31 chưa xong 11/11 | 07 §2.4 vẫn là hạn đã cam kết; web không được đẩy nó trễ mà không báo PO |

## Phụ lục A · Danh mục enum

Nguồn duy nhất cho cả BE và FE là `web/fe/src/contracts/enums.ts` và `web/contracts/enums.py`, cả hai sinh ra và kiểm lại bằng `web/tests/test_enum_sync.py`. Enum dữ liệu lấy từ `packages/flywheel-contracts/schemas/`; đổi một giá trị phải qua PR hợp đồng.

### A.1 Enum dữ liệu (theo contract)

| Nhóm | Giá trị |
|---|---|
| `source_kind` | teleop, synthetic, egocentric |
| `source_detail` | psi_data, teleop_keyboard, teleop_pico, planner_wbc, planner_amo |
| `synthetic_tier` | S1, S2, S3, S4 |
| `action_quality` | measured, planned, retargeted, pseudo, none |
| `episode.kind` | teleop_demo, teleop_correction, recovery, sim_rollout, variant, eval_rollout, diag_rollout |
| `operator_kind` | human, machine |
| `data_class` | public, internal, restricted |
| `deid_status` | raw, blurred, verified |
| `split` | train, dev, holdout, unassigned |
| `renderer` | mujoco, isaac |
| QA decision (code) | pass, flag, quarantine, reject |
| `qa_agent_verdict` | PASS, WARNING, FAIL |
| Tầng 1–6 | INGEST, NORMALIZE, ANNOTATE, QA, RELEASE, EXPORT |
| `stage_run.status` | PENDING, RUNNING, QA_EVALUATING, PASSED, PAUSED_FOR_REVIEW, OVERRIDDEN, FAILED, ABORTED |
| `human_review_action` | RETRY_STAGE, APPLY_FIX_AND_RETRY, FORCE_CONTINUE, ABORT_PIPELINE |
| `infra_status` | ok, simulator_error, policy_error, timeout, out_of_memory |
| **`step_status`** (bản 0.3) | **pass, fail, not_attempted, unknown** |
| Kiểu lỗi · task hai bàn | L-REACH, L-GRASP, L-SLIP, L-WALK, L-COLLIDE, L-PLACE, L-RELEASE, L-BALANCE, L-TIMEOUT, L-UNKNOWN |
| Kiểu lỗi · task khay | L-PART-DROP, L-TRAY-TILT, L-ONE-HAND, L-PLACE-POSE, L-TIMEOUT, L-BALANCE |
| Bước · task hai bàn | 1 tiếp cận, 2 gắp, 3 đi, 4 tới bàn đích, 5 đặt, 6 nhả và ổn định |
| Bước · task khay | approach_a, grasp, lift, carry, reach_b, place, release_stand |
| `failure_class` | approach, grasp, carry, place, balance |
| Mã lỗi dữ liệu | D1…D8 |
| Mã lỗi train | T1…T8 |
| Mã lỗi offline | O1…O4 |
| Mã lỗi hệ thống | R1…R6 (bộ lỗi cấy chỉ dùng R1, R2) |
| **Chẩn đoán hệ thống · episode** (bản 0.3) | **clean, unknown, controller, runtime, sync, calibration, infra** |
| Chẩn đoán cụm (11) | CHUA_RO, HE_THONG_CONTROLLER, HE_THONG_RUNTIME, HE_THONG_DONG_BO, HE_THONG_CALIBRATION, KHONG_KHA_THI, TRANG_THAI_DAU_XAU, NHAN_THUC, NGOAI_MIEN, THIEU_VUNG_PHU, KY_NANG_YEU |
| Chẩn đoán tiêu ngân sách dữ liệu (3) | TRANG_THAI_DAU_XAU, THIEU_VUNG_PHU, KY_NANG_YEU |
| Loại can thiệp | SIM_AROUND_FAILURE (S1–S4), TELEOP_CORRECTION, RECOVERY_DATA |
| `task_id` [Đề xuất, đối chiếu contract ở M0] | two_table, tray |
| Nhánh · task hai bàn | A, A_07, B, C, B_FAIL, B_PLUS |
| Nhánh · task khay | TRAY_A, TRAY_C, TRAY_B, TRAY_C_EGO, TRAY_C_NOEGO |
| Biến thể HE | V_EGO, V_EGO10, V_NOEGO |
| Phương pháp | PSI0, ACT, DIFFUSION_POLICY |
| Giả thuyết | HS, HT, HTa, HTb, HD, HE, HE_T, M |

**Lưu ý nhánh:** chữ A, B, C mang nghĩa khác nhau trên hai task. Luôn lưu và truy vấn kèm `task_id`.

### A.2 Enum của web (nhóm W)

| Nhóm | Giá trị |
|---|---|
| `action_kind` | INTAKE_SUBMIT, STAGE_REVIEW, EXPERIMENT_SUBMIT, RECOMMENDATION_DECISION, DIAGNOSIS_OVERRIDE, RELEASE_FREEZE_REQUEST, EVAL_REQUEST, FLYWHEEL_RUN_REQUEST, HOLDOUT_UNSEAL, SOFT_DELETE, CHAT_ACTION_CONFIRM |
| `sync_status` | PENDING, EXPORTED, APPLIED, REJECTED |
| `job_kind` | PIPELINE_RUN, PIPELINE_RETRY_FROM, TRAIN, PROBE, EVAL, RELEASE_FREEZE, FLYWHEEL_RUN |
| `job_requests.status` | OPEN, PICKED, DONE, FAILED, CANCELLED |
| Trạng thái phiếu nạp và bản nháp | DRAFT, SUBMITTED, ACCEPTED, REJECTED |
| Quyết định trên một can thiệp | APPROVE, APPROVE_EDITED, REJECT |
| `origin` | core, mock |
| Vai người dùng | DATA_ENGINEER, ML_ENGINEER, LEAD, JUDGE_VIEWER, ADMIN |

## Phụ lục B · Ánh xạ sang contract

| Bảng / thành phần web | Artifact nguồn | File schema | Trạng thái 3/11 |
|---|---|---|---|
| `episodes` | `Episode`, `EpisodeMetadata` | `Episode.json`, `EpisodeMetadata.json` | **có**; từ S1-10/7 (#62) `EpisodeMetadata` có `benchmark_copy_id`, bộ nạp map thẳng vào cột cùng tên. Artifact còn mang `injected_defect` bị model hợp đồng từ chối, nên không cột nào nhận được nó |
| `episode_qa_reports` | `QAReport` | `QAReport.json` | có |
| `training_metrics` | `TrainingMetric` | `TrainingMetric.json` | có |
| `train_diagnoses` | `TrainDiagnosis` | `TrainDiagnosis.json` | có; `skipped` của nó phải nạp về, xem mục 4.4b |
| `probe_results` | `ProbeP1`–`ProbeP4` | `ProbeP1.json` … `ProbeP4.json` | có |
| `defect_manifests`, `defect_items` | `DefectManifest` | `DefectManifest.json` | có |
| Phát lại action (M2) | `ReplayReport` | `ReplayReport.json` | có |
| Báo cáo dataset (M2) | `DatasetReport` | `DatasetReport.json` | có |
| Log suy luận (M6) | `RTCInferenceRecord` | `RTCInferenceRecord.json` | có |
| Cột nhóm action | `ActionLayout` | `ActionLayout.json` | có |
| Yêu cầu rollout (M6) | `RolloutRequest` | `RolloutRequest.json` | có |
| **`system_diagnoses`** | `SystemDiagnosisRecord` của `flywheel.eval.diagnosis.system.artifact` | **chưa có** | Issue #70 đề nghị `SystemDiagnosis`; tới khi merge, đọc bản ghi JSONL của làn |
| Giả thuyết stage (M7) | `StageAttributionRecord` của `flywheel.eval.diagnosis.stage.artifact` | **chưa có** | Issue #70 |

Các thực thể còn lại (`Source`, `Condition`, `Release`, `Checkpoint`, `RunPlan`, `Score`, `Cluster`, `FixRateEvent`, `LedgerEntry`, `Decision`) do story S1-10 (#36, **chưa merge**) giao; tên cột theo [03 §4.3](../docs/product/03-architecture.md). Chúng chưa có file schema, nên **bộ nạp phải khoan dung** với phần này cho tới khi S1-10 merge.

## Phụ lục C · Bộ mock kịch bản demo

Một thư mục, nạp bằng `fwsync import --from mock/demo-17-11 --origin mock`. FE dùng cùng thư mục này để dựng handler MSW, nên hai bên nhìn thấy cùng một bộ số.

**Đã dựng (4/11/2026).** Thư mục **sinh ra** bằng `uv run python -m web.mock.generate` với một seed cố định, không gõ tay, vì nó phải nhất quán với chính nó: số thành viên của một cụm bằng đúng số episode lỗi mang khoá của cụm, bút toán đảo mang đúng số đối của bút toán gốc. `web/tests/test_mock.py` so thư mục với bản sinh lại và kiểm các bất biến đó. Mọi số là bịa; `mock/demo-17-11/README.md` nói rõ, kèm bốn giả định riêng của bộ mock.

Bảng dưới là file **thật** của thư mục. Nó khác bản 0.2 ở hai chỗ: bộ nạp đọc một bảng một file, nên `recommendation.json` của bản 0.2 tách ra thành file cụm, can thiệp, bước, phiếu sửa; và thêm những bảng mà các bảng kia trỏ tới (nguồn, RunPlan, checkpoint, tầng pipeline).

| File | Nội dung |
|---|---|
| `sources.jsonl`, `run_plans.jsonl` | 6 nguồn (`repo: mock://…`), 9 RunPlan |
| `datasets.jsonl` | 5 lô: psi-data teleop, teleop bàn phím, synthetic S1, mẫu EgoDex, **và bản sao chấm** có lỗi cấy |
| `pipeline_stage_runs.jsonl` | 33 lần chạy tầng: psi tầng 4 `OVERRIDDEN`, bàn phím tầng 4 có hai attempt, bản sao dừng ở tầng 4 |
| `episodes.jsonl` | 210 episode, đủ bốn nguồn; 10 episode egocentric còn `raw` nằm ở `unassigned` |
| `qa_reports.jsonl` | 200 báo cáo (egocentric raw chưa qua tầng 4); flag, quarantine, reject đều có lý do |
| `releases.jsonl`, `release_items.jsonl` | 1 release đóng băng có hash (166 item, 2 item bị loại kèm lý do), 1 release nháp, 12 release HE: mỗi release đúng N demo gốc của người cộng 20 / 10 / 0 clip egocentric theo biến thể, và release của A_07: 70% mỗi nguồn của v1 (66 demo người so với 94) |
| `experiments.jsonl`, `experiment_datasets.jsonl`, `checkpoints.jsonl` | 4 nhánh A, A_07, B, B_FAIL cộng lưới HE 3 biến thể (V_EGO, V_EGO10, V_NOEGO) × N ∈ {10, 20, 40, 80} |
| `training_metrics.jsonl`, `train_diagnoses.jsonl` | 2 run, train và val; B_FAIL có T3; cả hai bỏ qua T7 kèm lý do |
| `probes.jsonl` | P1, P3 của hai checkpoint; P4 của B so với cha A |
| `evaluations.jsonl`, `eval_episodes.jsonl` | 4 lượt dev × 90 episode (A, A_07, B, B_FAIL), đủ ba mức, 2 episode lỗi hạ tầng mỗi lượt; 12 lượt dev chỉ có số tổng cho điểm HE (V_EGO chạm 50% ở N = 20, hai biến thể kia ở N = 40); 1 holdout niêm phong tới 20/11 |
| `system_diagnoses.jsonl` | 27 episode lỗi của B: `controller`, `sync`, **`unknown` vì thiếu log RTC**, `clean` |
| `recommendation.json`, `failure_clusters.jsonl` | 1 lượt, 4 cụm: HE_THONG_CONTROLLER, NGOAI_MIEN, THIEU_VUNG_PHU, KY_NANG_YEU |
| `flywheel_algo_steps.jsonl`, `diagnostic_runs.jsonl` | 12 bước; rollout chẩn đoán của ba cụm, một phép kiểm `skipped` kèm lý do |
| `interventions.jsonl`, `repair_tickets.jsonl` | 4 can thiệp, chỉ trên hai cụm dữ liệu; 1 phiếu sửa cho cụm hệ thống |
| `decisions.jsonl` | 2 quyết định duyệt tầng: FORCE_CONTINUE, APPLY_FIX_AND_RETRY |
| `ledger.jsonl` | 14 bút toán: thực đo, ước tính của 4 can thiệp, 1 bút toán đảo |
| `price_books.jsonl` | 4 bảng giá cho bảng độ nhạy |
| `defect_manifest.json`, `defect_scores.jsonl` | 10 lỗi cấy (7 dữ liệu, 3 log train); code bắt 6/10, agent bắt thêm 2 |

Bốn cụm với bốn chẩn đoán khác nhau là cố ý: nó cho phép demo nói câu quan trọng nhất — *"hai cụm này là lỗi hệ thống và ngoài miền, không tốn một đồng dữ liệu nào; chỉ hai cụm còn lại mới cần thu thêm"*.

Ca `unknown` trong `system_diagnoses.jsonl` cũng cố ý: nó là ca chứng minh BR-12 chạy, tức là web không bao giờ vẽ "không có lỗi" từ một phép kiểm không chạy được.

Mọi bản ghi nạp từ thư mục này có `origin = 'mock'`.

**Lõi giả** `fwsync fake-core --outbox <dir> --to <dir>`: đọc artifact trong outbox, sinh artifact kết quả có `source_action_id`. Dùng để nghiệm thu mốc M4 khi lõi thật chưa sẵn sàng.

## Phụ lục D · Yêu cầu với hợp đồng lõi

| Mã | Yêu cầu | Trạng thái |
|---|---|---|
| W1 | PO chốt: Postgres chia hai nửa, hay web ghi thẳng | **chưa có**, bản này viết theo phương án chia hai nửa |
| W2 | Người làm BE | Châu nhận cả FE và BE (3/11) |
| W7 | Trường `source_action_id` trên mọi artifact lõi sinh ra để đáp lại một hành động của web; artifact `JobStatus` (`job_request_id`, `status`, `picked_by`, `result_ref`, `updated_at`) | **chưa có**, cần PR hợp đồng cho Long |
| W8 | ADR-13: web và DB server ở L0 hay L1+ | **chưa có**, chặn mốc M1 |
| W9 | `SystemDiagnosis` và `StageAttribution` trong `flywheel.contracts` | issue #70 đã mở (3/11) |
| W10 | `Score` bốn trạng thái, lý do "chưa rõ" | issue #59 |
| W11 | `benchmark_copy_id` thay `injected_defect` trong `Episode` | **đã merge** (S1-10/7, PR #36, 3/11); bộ nạp dùng từ 5/11 |
| W12 | `Episode` không mang `dataset_id`. Ở lõi một episode trỏ `source_id` hoặc `intervention_id` (03 §4.3 cũng vậy), còn "lô" là khái niệm của web, không có thực thể tương ứng ở L0-lite. Bộ nạp suy `episodes.dataset_id` qua hai đường đó và **từ chối** dòng không suy được, chứ không gán lô mặc định — gán sai lô làm sai báo cáo dataset, phân bổ chi phí (BR-05) và `r_demo` mà không gì báo. Cần Long và PO quyết: thêm `dataset_id` vào `Episode`, hay web nhận đây là phép suy chính thức | **phát hiện 3/11 lúc viết mapper**; chưa mở issue |
