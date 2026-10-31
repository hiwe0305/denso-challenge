# 10 · Cơ sở dữ liệu cho backend và website

_Ngày 30/10/2026. Trạng thái: **[Đề xuất]**, chờ Product Owner (Hiếu) duyệt. Tài liệu này làm hai việc: (1) thống kê và kiểm chứng tài liệu tham khảo "Hệ thống Web Humanoid Data Flywheel" (file ngoài repo, tác giả ngoài đội, dưới đây gọi là **tài liệu web**) so với spec v10.4, 03 bản 0.7 và design 27/10/2026; (2) đặc tả schema PostgreSQL [db/schema.sql](db/schema.sql) cho các luồng ở [09](09-data-flows.md), đã chạy thật cùng bộ test [db/tests.sql](db/tests.sql). Khi mâu thuẫn, spec, design và 03 thắng tài liệu này._

| Ngày | Phiên bản | Thay đổi | Tác giả |
|---|---|---|---|
| 30/10/2026 | 0.1 | Bản đầu | PO (Hiếu), soạn cùng Claude |

## 0. Đọc nhanh

1. **Tài liệu web có khung tốt nhưng sai lõi.** Giữ được 10 ý (attempt có lịch sử, Bảng lỗi theo episode, sổ chi phí chỉ thêm, chat theo ngữ cảnh…). Có 23 điểm phải sửa. Trong đó 8 điểm trái quyết định đã chốt, ví dụ: Agent QA/QC làm cổng; bản cấy lỗi vào được train; đề xuất "thêm video egocentric" làm can thiệp; xóa output trung gian và checkpoint mà holdout còn cần. Thiếu sót lớn nhất là toàn bộ phần chẩn đoán của Failure → Data (mục 2).
2. **Schema mới**: 63 bảng (60 trong `fw`, 3 trong `fw_sealed`), 21 view, 45 hàm, 106 trigger, 222 ràng buộc CHECK, 77 chuyển trạng thái hợp lệ. Mọi bất biến của CLAUDE.md có thể cưỡng chế trong DB đều đã là trigger hoặc ràng buộc (mục 5).
3. **Đã kiểm chứng trên PostgreSQL 16** (image `postgres:16-alpine`): schema nạp sạch; 14 nhóm kịch bản đi trọn các luồng F1–F9 và thử từng vi phạm; tất cả qua. Bộ test bắt được một lỗi thật trong bản nháp đầu: episode chưa có QA lọt được vào release đóng băng. Lỗi đã sửa (mục 7).
4. **Một quyết định phải chốt trước khi dùng** (Q-B1 của 09): 03 và CLAUDE.md không cho DB server ở L0. Schema được thiết kế để dùng được theo cả hai cách: làm bản chiếu dựng lại được từ file, hoặc làm nguồn sự thật mới (mục 3.1).
5. **Bốn đề xuất hợp đồng** cần PR vào `flywheel-contracts` trước khi code dùng schema: kind `ego_demo`, bốn loại Decision mới, ba `purpose` mới của RunPlan, đơn giá theo loại can thiệp trong PriceBook (mục 8).

## 1. Thống kê tài liệu web

| Hạng mục | Số lượng | Ghi chú |
|---|---|---|
| Luồng backend | 4 | Pipeline 6 tầng; train và eval; Failure → Data; chat Agent |
| Bảng | 19, chia 5 nhóm | A dữ liệu 4, B huấn luyện 4, C đánh giá 2, D flywheel và chi phí 5, E chat và hệ thống 4 |
| View | 6 | Stepper, lỗi cấy, phễu, chi phí, so nhánh, tóm tắt lỗi |
| Nhóm business rule | 4 | BR-01 pipeline, BR-02 lỗi cấy, BR-03 chi phí, BR-04 xóa mềm |
| Màn hình | 4 + khung chat + chuông | Data Hub, Huấn luyện, Đánh giá, Failure → Data |
| Nhóm endpoint REST | 11 | Cộng `/internal/...` cho worker |
| Vai trò | 5 | DATA_ENGINEER, ML_ENGINEER, LEAD, JUDGE_VIEWER, ADMIN |
| Dòng nhật ký chuẩn hóa | 10 | So với "bản gốc v10.4" của tài liệu web |
| Bước triển khai | 5 | 29/10 tới 17/11 |

## 2. Kiểm chứng

### 2.1 Giữ (đã đưa vào schema)

| # | Ý của tài liệu web | Ở schema |
|---|---|---|
| K1 | Mỗi lần chạy một tầng là một attempt; chạy lại không ghi đè | `stage_run` (`attempt_no`, `is_current`) |
| K2 | Bốn hành động duyệt hop; `FORCE_CONTINUE` bắt buộc ghi chú | `stage_review` + hàm `fw.stage_review`, mỗi lần duyệt là một `decision` |
| K3 | Bảng lỗi mỗi episode một dòng; phễu bằng số đếm | View `v_failure_table`, `v_eval_funnel` trên `score` |
| K4 | Sổ chi phí chỉ thêm, sửa bằng bút toán đảo; đơn giá có phiên bản | `ledger_entry` append-only, trigger kiểm bút toán đảo; `price_rate` theo PriceBook có hash |
| K5 | Tách bảng thay cho cột JSON danh sách dataset | `release_item` và `MixSpec` trong `dataset_export` |
| K6 | Telemetry không trùng khi webhook gửi lại | `train_metric` khóa (run, split, tên, step) |
| K7 | Chat theo ngữ cảnh; hành động của agent phải được người xác nhận | `chat_session`, `chat_message`, `chat_action` |
| K8 | Đo "Agent bắt được x/y lỗi cấy" | `fw_sealed.v_defect_detection`, `v_agent_precision` |
| K9 | Thông báo đẩy lên web; 5 vai trò | `notification`; `app_user.role` |
| K10 | Một hệ quản trị (PostgreSQL + JSONB) thay vì thêm MongoDB | Giữ, với điều kiện ở mục 3.1 |

### 2.2 Phải sửa

Cột "Mức": **Vi phạm** là trái quyết định đã chốt hoặc bất biến của CLAUDE.md; **Sai** là sai về sự kiện hay về thuật toán; **Thiếu** là thiếu thứ luồng cần.

| # | Tài liệu web nói | Repo nói | Mức | Schema làm gì |
|---|---|---|---|---|
| W1 | "Luồng AI đã xây xong" | Code mới có khung: hợp đồng v0, Protocol, bộ giả, `fw --version` ([09](09-data-flows.md) mục 7.1) | Sai | Không áp dụng; kế hoạch của tài liệu web phải tính lại |
| W2 | PostgreSQL là nơi lưu chính | File là nguồn sự thật; không có DB server ở L0 (03 mục 1.2, 2.4; CLAUDE.md "Không làm") | Vi phạm | Thiết kế dùng được ở cả hai vai; chờ Q-B1 (mục 3.1) |
| W3 | Agent QA/QC trả PASS, WARNING, FAIL và quyết định tầng có đi tiếp | Mọi con số do code tính; agent viết báo cáo, kỹ sư duyệt (design mục 9.1) | Vi phạm | Tách `code_verdict` (code) và `agent_report.verdict`; agent chỉ có thể làm tầng dừng để người xem, không bao giờ cho qua |
| W4 | Pipeline 6 tầng chạy trên từng "dataset", xong thì `READY_FOR_TRAINING` | Tầng 5–6 làm trên release: gom episode nhiều nguồn, đóng băng có hash, guard chia tập; train đọc export của release (03 mục 4.4; design mục 6) | Sai | Lô nhập (`ingest_batch`) đi tầng 1–4 rồi thành `READY_FOR_RELEASE`; tầng 5–6 là `release` và `dataset_export`; view stepper vẫn hiện đủ 6 tầng |
| W5 | QA là một kết luận cho cả dataset | QA theo từng episode: pass, flag, quarantine, reject (spec mục 4.4) | Sai | `qa_report` theo episode, append-only; trạng thái hiện hành là bản mới nhất |
| W6 | Dataset có lỗi cấy vẫn `READY_FOR_TRAINING`; BE so với danh sách lỗi cấy sau mỗi tầng; mã lỗi tự đặt | Bản cấy lỗi không bao giờ vào release train; `DefectManifest` chỉ bộ chấm đọc, sau khi agent chạy; mã D1–D8, T1–T8, R1–R2 (CLAUDE.md; design mục 9.2, 10) | Vi phạm | Guard đóng băng release từ chối bản cấy lỗi; đáp án nằm ở schema `fw_sealed`, role `fw_app` ghi được nhưng không đọc được; mã lỗi theo design |
| W7 | Thí nghiệm là một nhánh, một giả thuyết; `base_checkpoint_uri` nhập tự do | RunPlan đóng băng; mỗi nhánh nhiều seed; so sánh khai trước; checkpoint gốc phải sạch (Q0) (spec mục 7.2–7.3; 03 mục 8.1, 8.3) | Vi phạm | `run_plan`, `run_plan_branch`, `run_plan_comparison`; `fw.run_plan_freeze` từ chối cây git bẩn, image không ghim digest, `simple-checkpoints` ngoài `g0_repro`, nguồn chưa sạch |
| W8 | Người dùng chọn giả thuyết ưu tiên (HS, HTa, HTb, HD, HE) để thuật toán tính tỉ lệ pha trộn | Thuật toán chọn theo chẩn đoán, tỉ lệ g/c, tỉ lệ sửa được và ngân sách (spec mục 6.11). Giả thuyết là câu hỏi của thí nghiệm; HD là thí nghiệm đo giờ chẩn đoán, không liên quan tới trộn dữ liệu | Sai | Bỏ trường này; giả thuyết chỉ nằm ở `run_plan_comparison` |
| W9 | Đề xuất kiểu "50 video egocentric" | Egocentric chỉ vào stage 1. Can thiệp chỉ gồm sim S1–S4, teleop correction, dữ liệu phục hồi (spec mục 2.5, 6.10; design mục 6.6) | Vi phạm | `intervention_type` chỉ có 6 loại đó; trigger chặn loại không hợp chẩn đoán |
| W10 | Failure → Data đọc Bảng lỗi rồi ra đề xuất; "12 bước" chỉ là thanh tiến trình | Lõi gồm gom cụm, 10 phép kiểm theo thứ tự, 11 chẩn đoán, phiếu sửa, cổng dev với sàn A/A, tỉ lệ sửa được đo có đối chứng (spec mục 6; 03 mục 6.2) | Thiếu | `cluster`, `diagnostic_check`, `cluster_diagnosis`, `intervention`, `intervention_approval`, `fix_rate_event`, `decision`; `round_step` mang đúng tên 12 bước của spec mục 6.1 |
| W11 | Đánh giá 3 pha; thành công là "đặt được" | Scorer 6 bước cộng điều kiện thăng bằng; chỉ số chính là `sim_success` của SIMPLE (spec mục 5; ADR-14) | Sai | `score` theo số bước của task; phễu 3 pha là view suy từ bước 2, bước 4 và `sim_success` |
| W12 | Mã lỗi `GRASP_MISS`, `FALL`, `MISPLACE`… "cần chốt" | Đã chốt: L-REACH … L-UNKNOWN kèm lớp lỗi chung (spec mục 5.2; 03 mục 4.3) | Sai | `failure_kind_def`, `task_step_class`; trigger kiểm lớp lỗi khớp mã |
| W13 | Mỗi episode thất bại là một dòng lỗi | Lỗi hạ tầng không bao giờ là lỗi policy (03 mục 5.3 điểm 8) | Vi phạm | CHECK: `infra_status ≠ ok` thì `sim_success` là NULL; mọi view tỉ lệ thành công chỉ đếm lượt hợp lệ |
| W14 | Không có điều kiện, mức, split, holdout | Điều kiện có seed, mức, `layout_hash`, split; holdout trong vault, chạy một lần mỗi checkpoint (spec mục 4.2–4.3; 03 mục 8.3) | Thiếu | `condition`, `condition_set`; `holdout_lock`, `holdout_seal`, `holdout_result`. Điều kiện holdout không bao giờ vào DB |
| W15 | Xóa output tầng 1–5 sau 7 ngày; chỉ giữ checkpoint best và latest | Bundle episode bất biến; mẫu bị loại giữ cùng lý do; holdout cần checkpoint của mọi (nhánh, seed) (03 mục 4.4; spec mục 4.4, 7.3) | Vi phạm | Chỉ được dọn: video phát lại của tầng 4, bản export (dựng lại được), checkpoint trung gian không ai tham chiếu (`fw.checkpoint_purgeable`). Dòng dữ liệu luôn ở lại |
| W16 | Xóa mềm cho mọi bảng nghiệp vụ, không cần lý do | Không xóa, chỉ đánh dấu kèm lý do (03 mục 1.2) | Sai | Bảng catalog không có xóa mềm; bảng vận hành có `hidden_at` kèm `hidden_reason` bắt buộc; không bảng nào cho DELETE |
| W17 | Không có `data_class`, giấy phép, `deid_status`, provenance | Bất biến che danh tính; dữ liệu `internal`, `restricted` không ra API ngoài (CLAUDE.md) | Thiếu | Các cột tương ứng; `episode_deid`; trigger chặn gán nhãn khi chưa che; release egocentric cần `verified`; view `v_episode_public` cho site public |
| W18 | Kỹ sư ML tự tạo thí nghiệm và chạy train | Job GPU chỉ Hiếu chạy, từ RunPlan (CLAUDE.md) | Vi phạm | `app_user.can_run_gpu_jobs`; trigger `job` từ chối job GPU của người khác và job thí nghiệm khi RunPlan chưa đóng băng |
| W19 | Agent đề xuất được hành động bất kỳ | Agent không chọn dữ liệu, không chạy job, không đọc vault (design mục 9.1) | Thiếu | `chat_action.kind` chỉ gồm chạy lại tầng, chạy lại báo cáo, mở artifact, nháp ghi chú duyệt |
| W20 | Cấm chạy lại pipeline của dataset đã có thí nghiệm dùng | Episode bất biến; attempt mới tạo episode mới, release cũ vẫn tái lập được | Sai (quá chặt) | Cho chạy lại; episode cũ thành "không hiện hành" và guard đóng băng release mới từ chối chúng |
| W21 | Chi phí dữ liệu của thí nghiệm = chi phí dataset × (episode dùng ÷ tổng episode) | B_add tính cả rollout bị loại (spec mục 7.3 điểm 5) | Sai | `v_release_data_cost` chia chi phí lô cho episode được nhận, để mẫu bị loại vẫn được tính vào phần dữ liệu đã dùng |
| W22 | `action_loss` là "sai số điều khiển khớp G1" | Đây là loss dự đoán action khi train; loss theo nhóm action do lớp bọc tính (design mục 8.2) | Sai | `train_metric` dạng dài: một dòng cho mỗi (run, split, tên, step); tên tự do theo log |
| W23 | Bút toán ACTUAL, PROJECTED, REVERSAL | Ước tính và thực đo là hai bản ghi riêng, không ghi đè nhau (03 mục 1.2) | Thiếu | `measure_kind` (estimated, measured) và `reverses_entry_id` là hai trục riêng; view `v_cost_forecast_error` so hai loại |

## 3. Quyết định thiết kế

### 3.1 Vai trò của DB so với file [Đề xuất]

| Cách | Nội dung | Ưu | Nhược |
|---|---|---|---|
| **A · Bản chiếu (khuyên dùng tới sau demo)** | Bảng catalog (12 thực thể của 03 mục 4.3 và phần mở rộng) được nạp từ `catalog/**.jsonl` và `runs/**` bằng một tiến trình đồng bộ, cùng ID. Bảng vận hành của web (`stage_run`, trạng thái `job`, chat, thông báo, người dùng, `intervention_task`) do DB giữ | Giữ đúng 03: mất DB thì dựng lại phần catalog từ file. Không cần sửa CLAUDE.md lớn | Phải viết bộ đồng bộ; hành động ghi từ web vẫn đi qua lệnh `fw` |
| B · Nguồn sự thật | Lõi `flywheel.store` ghi thẳng vào Postgres thay cho JSONL | Một chỗ ghi, truy vấn mạnh | Đổi kiến trúc L0 (03 mục 2.4, ADR-13); phải sửa 03, CLAUDE.md, S1-10; thêm backup Postgres |

Schema không phụ thuộc vào lựa chọn này: ID dùng đúng định dạng của 03 (`ep_<ULID>`, `rel_<hash>`…), và mọi bất biến nằm trong trigger nên đúng ở cả hai vai.

### 3.2 Quy ước

- Hai schema: `fw` cho mọi thứ; `fw_sealed` cho đáp án lỗi cấy, chỉ role `fw_grader` đọc. Ba role: `fw_app` (backend), `fw_grader`, `fw_viewer` (chỉ đọc).
- Khóa: thực thể catalog dùng ID văn bản theo 03 mục 4.1 và có CHECK định dạng; bảng chỉ có ở web dùng UUID. `fw.new_ulid()` sinh ULID khi backend cần.
- Ba kiểu bảng: **append-only** (32 bảng: không UPDATE, không DELETE); **có trạng thái** (cấm DELETE, chỉ một số cột đổi được, trạng thái đi theo `fw.status_transition`); **tham chiếu** (định nghĩa tầng, 12 bước, loại can thiệp, task, mã lỗi).
- "Trạng thái hiện hành" là bản ghi mới nhất (cột `seq` tăng dần): QA của episode, che danh tính, chẩn đoán cụm, Decision theo đối tượng.
- Thời gian `timestamptz`; số tiền `numeric`; JSONB chỉ cho phần thật sự mở (`meta`, `checks`, `body` của RunPlan, báo cáo).

## 4. Bản đồ bảng

| Nhóm | Bảng | Luồng ở 09 | Thay bảng nào của tài liệu web |
|---|---|---|---|
| Người dùng và cấu hình | `app_user`, `config_artifact`, `task_def`, `task_step_class`, `failure_kind_def`, `status_transition` | mọi luồng | `app_users` |
| Nguồn, kế hoạch, job | `source`, `run_plan`, `run_plan_branch`, `run_plan_comparison`, `job` | F1, F5–F8 | Một phần của `experiments` |
| Điều kiện | `condition`, `condition_set`, `condition_set_member` | F1, F6–F8 | Mới |
| Lô nhập và tầng 1–4 | `ingest_batch`, `pipeline_stage_def`, `stage_run`, `stage_review`, `agent_report`, `agent_finding` | F1–F3, F9 | `datasets`, `pipeline_stage_defs`, `pipeline_stage_runs` |
| Episode | `episode`, `episode_deid`, `episode_segment`, `qa_report`, `replay_report`, `dataset_report` | F1–F3 | Mới (tài liệu web không có mức episode) |
| Release và export (tầng 5–6) | `release`, `release_item`, `dataset_export` | F4 | `experiment_datasets` |
| Train | `train_run`, `train_metric`, `checkpoint`, `probe_result`, `train_flag` | F5 | `experiments`, `training_telemetry_logs`, `model_checkpoints` |
| Đánh giá | `eval_run`, `score` | F6 | `sim_evaluations`, `failure_records` |
| Vòng Failure → Data | `round_step_def`, `flywheel_round`, `round_step`, `cluster`, `cluster_member`, `diagnostic_check`, `cluster_diagnosis`, `intervention_type`, `intervention`, `intervention_approval`, `intervention_task`, `fix_rate_event` | F7 | `flywheel_recommendations`, `flywheel_algo_steps`, `data_collection_requests` |
| Quyết định và con trỏ | `decision`, `ref_pointer`, `ref_log` | X2, F7, F8 | Mới |
| Sổ chi phí | `price_rate`, `ledger_entry` | X1 | `cost_rates`, `cost_ledger_entries` |
| Holdout | `holdout_lock`, `holdout_seal`, `holdout_result` | F8 | Mới |
| Chat và thông báo | `chat_session`, `chat_message`, `chat_action`, `notification` | Web | `agent_chat_sessions`, `agent_chat_messages`, `notifications` |
| Đáp án lỗi cấy (`fw_sealed`) | `defect_manifest`, `injected_defect`, `defect_match` | F9 | `seeded_faults` |

**Vòng đời chính.** Lô nhập: INGESTED → PROCESSING ⇄ PAUSED_FOR_REVIEW → READY_FOR_RELEASE, hoặc FAILED, ABORTED. Tầng: PENDING → RUNNING → AGENT_REVIEWING → PASSED hoặc PAUSED_FOR_REVIEW → OVERRIDDEN, ABORTED; chạy lại tạo attempt mới. Vòng: FINDING → DIAGNOSING → PLANNING → AWAITING_REVIEW → ACQUIRING → TRAINING → GATING → DONE, hoặc STOPPED kèm lý do dừng của spec mục 6.13. Danh sách đầy đủ ở bảng `fw.status_transition`.

## 5. Bất biến được cưỡng chế trong DB

| Bất biến | Nguồn | Cơ chế | Test |
|---|---|---|---|
| Catalog, sổ chi phí, Decision chỉ thêm | CLAUDE.md | Trigger `*_append_only` trên 32 bảng; `*_no_delete` trên mọi bảng còn lại | 11, 13, 14 |
| Release đóng băng bất biến; thêm dữ liệu là release con | 03 mục 4.4 | `tg_release_update`, `tg_release_item_change` | 6 |
| Guard đóng băng: QA pass hoặc flag đã xem, không bản cấy lỗi, không episode bị thay, egocentric đã che và tách khỏi robot, một embodiment trừ khi có Decision V3, guard holdout đạt | 03 mục 4.4, 8.3; ADR-08; CLAUDE.md | `fw.release_violations`, `fw.release_freeze` | 6 |
| Dữ liệu train không dùng điều kiện dev hay `layout_hash` của dev | 03 mục 8.3 điểm 3 | `tg_episode_insert` | 2 |
| Lỗi hạ tầng không phải lỗi policy | 03 mục 5.3 điểm 8 | CHECK trên `episode`; view chỉ đếm lượt hợp lệ | 9 |
| Chẩn đoán mù holdout, chỉ trên lượt dev thất bại hợp lệ | 03 mục 8.3 điểm 5 | `tg_cluster_member_insert` | 10 |
| Can thiệp đúng bảng quyết định; n_eff = min(m_j, L_t); trần mỗi cụm | spec mục 6.9, 6.10 | `tg_intervention_insert` | 10 |
| Kỹ sư duyệt mọi đề xuất, ghi đè phải có lý do, trong ngân sách vòng | spec mục 6.11, 6.14 | `fw.round_review` | 10 |
| fixed_j = làm tròn(n × (p_ứng viên − p_cha)), kẹp [0, n]; prior Beta(1, 1) | spec mục 6.13 | Cột sinh trong `fix_rate_event`; view `v_fix_rate_posterior` | 11 |
| Bút toán đảo phải đối đúng bút toán gốc, một lần | spec mục 8; CLAUDE.md | `tg_ledger_insert` | 11 |
| RunPlan đóng băng: git sạch, image có digest, checkpoint gốc sạch | 03 mục 8.1, 8.3 điểm 7 | `fw.run_plan_freeze`, `tg_run_plan_update` | 7 |
| Job GPU chỉ người được phép, từ RunPlan đóng băng | CLAUDE.md | `tg_job_insert` | 8 |
| Stage 3 đọc dữ liệu robot, stage 1 đọc egocentric; MixSpec có tổng 1 và mỗi nhóm có dữ liệu | spec mục 2.5, 7.3 | `tg_export_insert`, `tg_train_run_insert` | 6, 8 |
| Holdout một lần mỗi checkpoint; kết quả niêm phong tới khi mọi (nhánh, seed) đã khóa | 03 mục 8.3 điểm 6 | Khóa chính `holdout_lock`; `fw.holdout_unseal`; `tg_holdout_result_insert` | 12 |
| Con trỏ chỉ đổi sau cổng dev đạt hoặc mốc, có log | 03 mục 4.4 điểm 4 | `fw.ref_set` | 12 |
| Che danh tính trước gán nhãn | CLAUDE.md | `tg_segment_insert` | 5 |
| Video người không bao giờ là demo robot | 03 mục 4.4 điểm 2 | Kind `ego_demo`; `is_root` là cột sinh | 5 |
| Đáp án lỗi cấy chỉ bộ chấm đọc | CLAUDE.md | Schema `fw_sealed`, quyền role | 4 |
| Agent không tự chạy job hay chọn dữ liệu | design mục 9.1 | `chat_action.kind`, trigger chỉ cho tin nhắn của agent đề xuất | 13 |
| Trạng thái chỉ đi theo chuyển hợp lệ; cột định danh không đổi | Mục 4 | `tg_check_status`, `tg_only_columns_mutable` | 2, 8, 13 |

**Không cưỡng chế được trong DB** (phải nằm ở code): điều kiện holdout và guard gần trùng theo khoảng cách (cần `vault/`, chỉ `gate.holdout` đọc; DB chỉ nhận kết quả đạt hay không); agent không đọc `vault/`; không gửi dữ liệu `internal`, `restricted` ra API ngoài (DB chỉ cho view lọc sẵn).

## 6. View cho website

| Màn hình (tài liệu web) | View |
|---|---|
| Data Hub: stepper 6 tầng, thẻ agent, lịch sử attempt, lỗi cấy | `v_pipeline_stepper`, `v_batch_overview`, `v_episode_current`; `fw_sealed.v_defect_detection`, `v_agent_precision` (chỉ `fw_grader`) |
| Huấn luyện và so nhánh | `v_train_curve`, `v_branch_comparison` |
| Đánh giá và Bảng lỗi | `v_eval_summary` (tổng và theo mức), `v_eval_funnel` (6 bước và 3 pha), `v_failure_table`, `v_failure_summary` |
| Failure → Data và Sổ chi phí | `v_round_progress`, `v_cluster_current`, `v_intervention_progress`, `v_fix_rate_posterior`, `v_cost_by_branch`, `v_batch_cost`, `v_release_data_cost`, `v_cost_forecast_error` |
| Chung | `v_decision_current`, `v_episode_public` (cho site public) |

## 7. Kiểm chứng đã chạy

Ngày 30/10/2026 trên máy dev, container tạm `postgres:16-alpine` (đã dừng sau khi chạy):

```bash
psql -v ON_ERROR_STOP=1 -f docs/product/db/schema.sql -f docs/product/db/tests.sql
```

| Nhóm test | Luồng | Kiểm gì |
|---|---|---|
| 1 | Dữ liệu tham chiếu | Người dùng, cấu hình, nguồn, điều kiện; ULID |
| 2 | F1–F2 | Lô teleop qua 4 tầng; điều kiện dev và `layout_hash` bị chặn; tầng dừng vì code WARNING dù agent PASS; `FORCE_CONTINUE` thiếu ghi chú bị chặn |
| 3 | F2 | Chạy lại có tham số sửa: attempt mới, attempt PENDING thành SUPERSEDED, episode cũ không còn hiện hành; lô synthetic S1 |
| 4 | F9 | Bản cấy lỗi; role `fw_app` không đọc được đáp án |
| 5 | F3 | Gán nhãn trước khi che bị chặn; video người không là demo robot |
| 6 | F4 | Guard đóng băng phát hiện đủ 5 loại vi phạm; release đóng băng bất biến; MixSpec sai tổng, nhóm rỗng, sai định dạng đều bị chặn; release egocentric cần `verified` |
| 7 | RunPlan | Git bẩn, nguồn chưa sạch, `simple-checkpoints` ngoài G0 bị chặn; sửa sau đóng băng bị chặn |
| 8 | F5 | Job GPU của người không được phép; stage và định dạng export không khớp; telemetry gửi lại không trùng |
| 9 | F6 | Tỉ lệ thành công 2/5 loại trừ lượt lỗi hạ tầng; phễu; lớp lỗi sai mã bị chặn |
| 10 | F7 | 12 bước tự tạo; cụm chỉ nhận lượt dev thất bại; can thiệp sai chẩn đoán, sai n_eff, chưa bật bị chặn; duyệt thiếu đề xuất, vượt ngân sách, ghi đè thiếu lý do bị chặn; sổ ước tính 75 USD; sai số dự báo 10% |
| 11 | X1 | fixed = 3 và kẹp về 0; posterior Beta(4, 8); bút toán đảo sai số tiền, đảo lần hai bị chặn |
| 12 | F8, X2 | Con trỏ cần cổng đạt; khóa holdout hai lần bị chặn; kết quả trước khi mở niêm phong bị chặn; dọn checkpoint đang cần bị chặn |
| 13 | Chat | Tin nhắn người không đề xuất hành động; loại hành động ngoài danh sách; nhảy trạng thái |
| 14 | Toàn cục | Không DELETE; ẩn cần lý do; mọi view trả lời; thẻ so nhánh, stepper 6 tầng, view public |

Kết quả: cả 14 nhóm qua. Lần chạy đầu bắt được một lỗi của schema: trong `fw.release_violations`, episode chưa có QAReport cho ra NULL ở phép so sánh nên bị bỏ qua, tức là lọt được vào release đóng băng. Bản hiện tại kiểm NULL tường minh.

Giới hạn của lần kiểm này: dữ liệu là dữ liệu giả nhỏ; chưa đo hiệu năng (ước lượng L0 vài chục nghìn episode và vài triệu dòng `train_metric`, trong tầm Postgres một máy); chưa thử quyền của `fw_app` trên mọi thao tác ghi.

## 8. Việc cần chốt

| # | Việc | Vì sao | Người |
|---|---|---|---|
| D1 | Q-B1 của 09: DB là bản chiếu (cách A) hay nguồn sự thật (cách B) | Đổi 03 mục 2.4 và CLAUDE.md nếu chọn B | Hiếu |
| D2 | Thêm `Episode.kind = ego_demo` | 03 không có kind cho video người; mượn kind khác thì bị đếm thành demo robot | Long (PR hợp đồng), Hiếu duyệt |
| D3 | Thêm `Decision.kind`: `stage_review`, `agent_report_review`, `v3_controller`, `scope_reduction` | 09 khoảng trống G4; các hop duyệt của web cần có người ký | Long, Hiếu |
| D4 | Thêm `RunPlan.purpose`: `he`, `stage1`, `tray_he` | 09 khoảng trống G6 | Hiếu |
| D5 | PriceBook có đơn giá theo loại can thiệp (`intervention_sim_s1`, …) | `decide` tính c_j từ đơn giá mỗi loại (spec mục 6.11); sổ ước tính cần khóa tới đơn giá | Long |
| D6 | Chính sách dừng tầng khi demo: `fw.stage_needs_review` | Tài liệu web BR-02 để ngỏ: chỉ dừng khi code hoặc agent báo, hay bật duyệt tay mọi tầng | Hiếu |
| D7 | Task bê khay: `task_def` 7 bước, mã lỗi mới | design 28/10 còn nháp | Hiếu khi duyệt design 28/10 |
| D8 | Đường dẫn file của `DatasetReport`, `ReplayReport`, probe, log RTC, báo cáo agent | 09 khoảng trống G3; DB chỉ giữ URI | Long (DA-25) |

## 9. Cách chạy

Cần PostgreSQL 14 trở lên. Trên máy có Docker:

```bash
docker run -d --rm --name fw-db -e POSTGRES_PASSWORD=dev -v "$PWD/docs/product/db:/sql:ro" postgres:16-alpine
```

```bash
docker exec fw-db sh -c 'createdb -U postgres fw && psql -U postgres -d fw -v ON_ERROR_STOP=1 -f /sql/schema.sql -f /sql/tests.sql'
```

Lệnh thứ hai in `ALL TESTS PASSED` khi mọi nhóm qua và trả mã khác 0 ở lỗi đầu tiên. Bộ test để lại dữ liệu mẫu trong DB `fw`, dùng được làm mock cho frontend; xóa DB và chỉ chạy `schema.sql` để có DB trống.
