-- Nhóm P, nửa huấn luyện và đánh giá: thí nghiệm, checkpoint, telemetry,
-- chẩn đoán, eval, Failure → Data, sổ chi phí. Chỉ fw_sync ghi (luật R1).
--
-- Cuối file: FK vòng của episodes, và vòng thêm ba cột chung cho mọi bảng P.

-- ---------------------------------------------------------------------------
-- experiments · một nhánh × một phương pháp
-- ---------------------------------------------------------------------------
CREATE TABLE experiments (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  experiment_code VARCHAR(64) NOT NULL,
  run_plan_id UUID REFERENCES run_plans(id),
  task_id VARCHAR(16) NOT NULL CHECK (task_id IN ('two_table','tray')),
  -- Nhánh luôn đi kèm task_id: chữ A, B, C mang nghĩa khác nhau trên hai
  -- task, và so nhánh B của task hai bàn với nhánh B của task khay là một
  -- kết luận sai (DESIGN.md Phụ lục A, lưu ý nhánh).
  branch VARCHAR(16) NOT NULL,
  method VARCHAR(24) NOT NULL CHECK (method IN ('PSI0','ACT','DIFFUSION_POLICY')),
  hypothesis VARCHAR(8),
  base_source_id UUID REFERENCES sources(id),
  status VARCHAR(12) NOT NULL DEFAULT 'QUEUED' CHECK (status IN (
    'QUEUED','RUNNING','DONE','FAILED','CANCELLED')),
  train_seed BIGINT,
  hyperparams JSONB NOT NULL DEFAULT '{}',
  started_at TIMESTAMPTZ,
  finished_at TIMESTAMPTZ,
  is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  deleted_at TIMESTAMPTZ,
  delete_reason TEXT,
  CONSTRAINT c12_experiment_delete_reason CHECK (NOT is_deleted OR delete_reason IS NOT NULL),
  CONSTRAINT c7_branch_matches_task CHECK (
    (task_id = 'two_table' AND branch IN ('A','A_07','B','C','B_FAIL','B_PLUS'))
    OR (task_id = 'tray' AND branch IN ('TRAY_A','TRAY_C','TRAY_B','TRAY_C_EGO','TRAY_C_NOEGO')))
);
CREATE UNIQUE INDEX c1_experiment_code ON experiments (experiment_code) WHERE NOT is_deleted;
CREATE INDEX ON experiments (task_id, branch);

-- ---------------------------------------------------------------------------
-- experiment_datasets · release nào vào thí nghiệm nào, với tỉ trọng nào
-- ---------------------------------------------------------------------------
CREATE TABLE experiment_datasets (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  experiment_id UUID NOT NULL REFERENCES experiments(id),
  release_id UUID NOT NULL REFERENCES releases(id),
  mix_weight NUMERIC(6,5) NOT NULL CHECK (mix_weight > 0 AND mix_weight <= 1),
  episodes_used INTEGER CHECK (episodes_used >= 0),
  UNIQUE (experiment_id, release_id)
);

-- ---------------------------------------------------------------------------
-- model_checkpoints
-- ---------------------------------------------------------------------------
CREATE TABLE model_checkpoints (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  checkpoint_ref VARCHAR(64) NOT NULL UNIQUE,  -- ckpt_<hash>
  experiment_id UUID NOT NULL REFERENCES experiments(id),
  parent_checkpoint_id UUID REFERENCES model_checkpoints(id),
  release_id UUID REFERENCES releases(id),
  method VARCHAR(24) NOT NULL,
  step INTEGER CHECK (step >= 0),
  weights_sha256 CHAR(64) NOT NULL,
  uri TEXT NOT NULL,
  is_best BOOLEAN NOT NULL DEFAULT FALSE,
  is_latest BOOLEAN NOT NULL DEFAULT FALSE,
  train_seed BIGINT,
  meta JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- C4: mỗi thí nghiệm đúng một best và một latest.
CREATE UNIQUE INDEX c4_one_best ON model_checkpoints (experiment_id) WHERE is_best;
CREATE UNIQUE INDEX c4_one_latest ON model_checkpoints (experiment_id) WHERE is_latest;

-- ---------------------------------------------------------------------------
-- training_metrics · telemetry theo step
-- ---------------------------------------------------------------------------
CREATE TABLE training_metrics (
  id BIGSERIAL PRIMARY KEY,
  experiment_id UUID NOT NULL REFERENCES experiments(id),
  run_plan_id UUID REFERENCES run_plans(id),
  release_id UUID REFERENCES releases(id),
  -- Job trên Colab resume từ checkpoint sẽ phát lại step cũ, nên attempt là
  -- phần của khoá.
  attempt SMALLINT NOT NULL DEFAULT 0,
  step INTEGER NOT NULL CHECK (step >= 0),
  epoch INTEGER NOT NULL DEFAULT 0,
  split VARCHAR(8) NOT NULL CHECK (split IN ('train','val')),
  loss DOUBLE PRECISION,
  -- Loss không hữu hạn đi vào cột riêng. AVG() trên cột có NaN trả NaN và làm
  -- trắng cả biểu đồ, nên NaN không bao giờ được nhét vào `loss`.
  loss_nonfinite VARCHAR(12) CHECK (loss_nonfinite IN ('NaN','Infinity','-Infinity')),
  lr DOUBLE PRECISION NOT NULL,
  vlm_frozen BOOLEAN NOT NULL,
  -- Bốn trường dưới chỉ có trên dòng `split = 'val'`; dòng train để trống
  -- (quyết định 3/11/2026, issue #44).
  loss_by_group JSONB NOT NULL DEFAULT '{}',
  pred_var_by_dim DOUBLE PRECISION[],
  pred_std DOUBLE PRECISION[],
  target_std DOUBLE PRECISION[],
  loss_by_chunk_pos DOUBLE PRECISION[],
  grad_norm_vlm DOUBLE PRECISION,
  grad_norm_action DOUBLE PRECISION,
  hand_open_hist DOUBLE PRECISION[],
  vram_gb DOUBLE PRECISION,
  throughput DOUBLE PRECISION,
  wall_time_s DOUBLE PRECISION NOT NULL,
  recorded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  -- Một step có hai dòng, train và val. Khoá thiếu `split` sẽ chặn mất dòng
  -- val, mà mất val là mất T2 và T3.
  UNIQUE (experiment_id, attempt, step, split),
  CHECK ((loss IS NULL) <> (loss_nonfinite IS NULL))
);
CREATE INDEX ON training_metrics (experiment_id, split, step);

-- ---------------------------------------------------------------------------
-- train_diagnoses · T1–T8 và O1–O4, một dòng một mã đã nổ
-- ---------------------------------------------------------------------------
CREATE TABLE train_diagnoses (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  experiment_id UUID NOT NULL REFERENCES experiments(id),
  checkpoint_id UUID REFERENCES model_checkpoints(id),
  config_sha256 CHAR(64) NOT NULL,
  code VARCHAR(4) NOT NULL CHECK (code IN (
    'T1','T2','T3','T4','T5','T6','T7','T8','O1','O2','O3','O4')),
  start_step INTEGER NOT NULL CHECK (start_step >= 0),
  group_name VARCHAR(32),
  dim INTEGER CHECK (dim >= 0),
  value DOUBLE PRECISION,
  value_nonfinite VARCHAR(12) CHECK (value_nonfinite IN ('NaN','Infinity','-Infinity')),
  -- NULL khi luật đếm thay vì so ngưỡng, đúng cách `DiagnosisFinding.threshold`
  -- của hợp đồng khai cho T1 trên loss không hữu hạn.
  threshold DOUBLE PRECISION,
  stop_job BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (stop_job = FALSE OR code = 'T1'),
  CHECK ((value IS NULL) <> (value_nonfinite IS NULL))
);
CREATE INDEX ON train_diagnoses (experiment_id, code);

-- ---------------------------------------------------------------------------
-- train_diagnosis_skips · mã không chấm được (BR-12)
-- ---------------------------------------------------------------------------
-- DESIGN.md §4.4b để ngỏ chỗ này tới mốc M1; đây là quyết định.
-- `TrainDiagnosis` của hợp đồng mang một danh sách `skipped` bên cạnh
-- `findings`, và nó phải nạp về cùng lý do như `system_diagnoses.skipped`: một
-- checkpoint không có probe P4 thì T7 **không chấm được**, không phải không
-- quên. `train_diagnoses` là một dòng một mã đã nổ, nên không có chỗ treo
-- danh sách này; nó thuộc về một *lần chạy*, khoá là (checkpoint, config).
CREATE TABLE train_diagnosis_skips (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  experiment_id UUID NOT NULL REFERENCES experiments(id),
  checkpoint_id UUID REFERENCES model_checkpoints(id),
  config_sha256 CHAR(64) NOT NULL,
  code VARCHAR(8) NOT NULL,                    -- một mã, hoặc một nhánh: T8a
  reason TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (experiment_id, config_sha256, code),
  CHECK (length(btrim(reason)) > 0)
);

-- ---------------------------------------------------------------------------
-- probe_results · P1–P4
-- ---------------------------------------------------------------------------
CREATE TABLE probe_results (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  probe VARCHAR(4) NOT NULL CHECK (probe IN ('P1','P2','P3','P4')),
  checkpoint_id UUID NOT NULL REFERENCES model_checkpoints(id),
  parent_checkpoint_id UUID REFERENCES model_checkpoints(id),
  dataset_sha256 CHAR(64),
  payload JSONB NOT NULL,                      -- theo schema ProbeP1..P4
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  -- P4 là phép đo quên, nên nó vô nghĩa không có checkpoint cha để so.
  CHECK (probe <> 'P4' OR parent_checkpoint_id IS NOT NULL)
);
CREATE INDEX ON probe_results (checkpoint_id, probe);

-- ---------------------------------------------------------------------------
-- sim_evaluations · một lượt eval
-- ---------------------------------------------------------------------------
CREATE TABLE sim_evaluations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  evaluation_ref VARCHAR(64) NOT NULL UNIQUE,   -- khoá tự nhiên của lõi
  checkpoint_id UUID NOT NULL REFERENCES model_checkpoints(id),
  run_plan_id UUID REFERENCES run_plans(id),
  task_id VARCHAR(16) NOT NULL CHECK (task_id IN ('two_table','tray')),
  condition_set_id VARCHAR(64) NOT NULL,
  split VARCHAR(16) NOT NULL DEFAULT 'dev' CHECK (split IN ('train','dev','holdout')),
  level SMALLINT CHECK (level BETWEEN 0 AND 2),
  renderer VARCHAR(8) NOT NULL DEFAULT 'mujoco' CHECK (renderer IN ('mujoco','isaac')),
  eval_mode VARCHAR(8) NOT NULL DEFAULT 'sync' CHECK (eval_mode IN ('sync','async')),
  scorer_version VARCHAR(32) NOT NULL,
  total_episodes INTEGER NOT NULL DEFAULT 0 CHECK (total_episodes >= 0),
  -- Cột đếm NOT NULL DEFAULT 0: một CHECK so với NULL luôn đúng, nên cột đếm
  -- cho phép NULL làm C13 thành vô dụng.
  success_count INTEGER NOT NULL DEFAULT 0,
  infra_failed_count INTEGER NOT NULL DEFAULT 0,
  -- Holdout niêm phong. Khác NULL và còn ở tương lai thì API trả 403 cho mọi
  -- vai trừ ADMIN (BR-10).
  sealed_until TIMESTAMPTZ,
  started_at TIMESTAMPTZ,
  finished_at TIMESTAMPTZ,
  is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  deleted_at TIMESTAMPTZ,
  delete_reason TEXT,
  CONSTRAINT c12_eval_delete_reason CHECK (NOT is_deleted OR delete_reason IS NOT NULL),
  CONSTRAINT c13_counts CHECK (
    infra_failed_count BETWEEN 0 AND total_episodes
    AND success_count BETWEEN 0 AND total_episodes - infra_failed_count),
  -- Lỗi hạ tầng bị loại khỏi mẫu số: simulator sập không bao giờ là
  -- `sim_success = FALSE` (03 §4.3 luật 8).
  overall_sr NUMERIC(5,4) GENERATED ALWAYS AS (
    CASE WHEN total_episodes - infra_failed_count > 0
         THEN success_count::numeric / (total_episodes - infra_failed_count)
    END) STORED
);
CREATE INDEX ON sim_evaluations (checkpoint_id, split, level);
CREATE INDEX ON sim_evaluations (sealed_until) WHERE sealed_until IS NOT NULL;

-- ---------------------------------------------------------------------------
-- eval_episodes · mọi episode eval, kể cả thành công
-- ---------------------------------------------------------------------------
CREATE TABLE eval_episodes (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  eval_episode_ref VARCHAR(64) NOT NULL UNIQUE, -- khoá tự nhiên của lõi
  evaluation_id UUID NOT NULL REFERENCES sim_evaluations(id),
  episode_index INTEGER NOT NULL,
  condition_id VARCHAR(64) NOT NULL,
  level SMALLINT NOT NULL CHECK (level BETWEEN 0 AND 2),
  episode_seed BIGINT NOT NULL,
  rollout_seed BIGINT,
  scorer_version VARCHAR(32) NOT NULL,
  -- Hai cột cạnh nhau, không gộp: cờ simulator là chỉ số chính (ADR-14), kết
  -- luận scorer chỉ để đối chiếu. Lệch quá 5% nghĩa là scorer hỏng (§1 điểm 9).
  sim_success BOOLEAN,
  scorer_success BOOLEAN,
  infra_status VARCHAR(24) NOT NULL DEFAULT 'ok' CHECK (infra_status IN (
    'ok','simulator_error','policy_error','timeout','out_of_memory')),
  -- Bản 0.3: bốn chuỗi của `StepStatus` trong DA-36 (PR #58), không phải mã
  -- số 0/1/2/3 của DESIGN.md v0.2. Hai cách mã hoá cho cùng một thứ là hai
  -- nguồn sự thật, và bản số không đọc được bằng mắt trong JSONL. Issue #59.
  step_status TEXT[] NOT NULL,
  first_failed_step SMALLINT,
  failure_code VARCHAR(32),
  failure_class VARCHAR(16) CHECK (failure_class IN (
    'approach','grasp','carry','place','balance')),
  failure_time_s NUMERIC(8,3),
  -- Provenance của episode (03 §4.3), không phải kết quả một phép kiểm; kết
  -- quả kiểm hệ thống nằm ở `system_diagnoses`.
  camera_params_hash VARCHAR(64),
  video_uri TEXT,
  trajectory_log_uri TEXT,
  -- Lý do từng bước `unknown`, tín hiệu thiếu, lớp lỗi chung. Thành trường có
  -- kiểu khi issue #59 merge.
  details JSONB NOT NULL DEFAULT '{}',
  UNIQUE (evaluation_id, episode_index, scorer_version),
  CONSTRAINT c18_step_status CHECK (
    step_status <@ ARRAY['pass','fail','not_attempted','unknown']::text[]),
  -- L-UNKNOWN không có lớp lỗi chung (03 §4.3, lớp lỗi chung AR5).
  CHECK (failure_code IS DISTINCT FROM 'L-UNKNOWN' OR failure_class IS NULL),
  -- Một episode lỗi hạ tầng không mang kết luận về policy.
  CHECK (infra_status = 'ok' OR sim_success IS NULL)
);
CREATE INDEX ON eval_episodes (evaluation_id, level, sim_success);
CREATE INDEX ON eval_episodes (evaluation_id, failure_code, first_failed_step);

-- Giữ tên cũ cho FE và báo cáo cũ. `failure_records` của bản BA là view, không
-- phải bảng: một lượt lỗi là một dòng eval_episodes đã có.
CREATE VIEW failure_records AS
SELECT * FROM eval_episodes
WHERE sim_success IS NOT TRUE AND infra_status = 'ok';

-- ---------------------------------------------------------------------------
-- system_diagnoses · kiểm hệ thống R1–R6 (bản 0.3, mới)
-- ---------------------------------------------------------------------------
-- Thay bốn cột phẳng của bản 0.2 (`tracking_error`, `latency_p99_ms`,
-- `sync_offset_ms`, `camera_params_hash` trên eval_episodes). Bốn cột không
-- chở được "chưa chấm được": episode không có log RTC thì `latency_p99_ms` là
-- NULL, mọi truy vấn `WHERE latency_p99_ms > τ` bỏ qua nó, và nó đọc ra
-- không có lỗi độ trễ — đúng silent pass FR21 cấm.
--
-- Nguồn: `SystemDiagnosis` của `flywheel.contracts.diagnosis` (issue #70), mà
-- `SystemDiagnosisRecord` của DA-13 khớp từng trường.
--
-- Bản 0.5: `timing`, `recorded`, `recorded_skipped` theo PR #146. Quyết định
-- (a) của PO (5/11/2026): trên rollout đồng bộ, R1 và R2 vẫn đo nhưng chỉ ghi
-- nhận, không quy lỗi. Chúng nằm ở hai cột riêng để C17 vẫn đúng nguyên văn:
-- `clean` cạnh R1, R2 ghi nhận là hợp lệ, vì hai mã đó không quyết định nhãn.
CREATE TABLE system_diagnoses (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  eval_episode_id UUID NOT NULL REFERENCES eval_episodes(id),
  diagnosis VARCHAR(16) NOT NULL CHECK (diagnosis IN (
    'clean','unknown','controller','runtime','sync','calibration','infra')),
  config_sha256 CHAR(64) NOT NULL,             -- hash system.yaml đã chấm
  trace_sha256 CHAR(64) NOT NULL,
  infra_status VARCHAR(24),                    -- R6; ghi dù R6 không nổ
  -- [{code, value, threshold, part, where, detail}]
  findings JSONB NOT NULL DEFAULT '[]',
  -- [{code, reason}] mã không chấm được. Đây là cột làm cả bảng này tồn tại.
  skipped JSONB NOT NULL DEFAULT '[]',
  -- Số để M6 hiện dù không mã nào nổ ngưỡng: sai số bám lệnh theo nhóm, độ
  -- trễ p99, lệch đồng bộ. Giữ được ý của bản 0.2 mà không mất `skipped`.
  measurements JSONB NOT NULL DEFAULT '{}',
  -- Chế độ rollout (bản 0.5). NULL là producer không nói, và không bao giờ
  -- được đọc là đồng bộ (FR21): R1, R2 khi đó vẫn tính.
  timing VARCHAR(8) CHECK (timing IN ('sync','async')),
  -- R1, R2 của rollout đồng bộ: đã đo, giữ lại, không vào nhãn.
  recorded JSONB NOT NULL DEFAULT '[]',
  recorded_skipped JSONB NOT NULL DEFAULT '[]',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  -- Chấm lại dưới một file ngưỡng khác là một dòng mới, không ghi đè.
  UNIQUE (eval_episode_id, config_sha256),
  -- C17: `clean` nghĩa là đã chấm hết và không mã nào nổ. Không có CHECK này
  -- thì một episode không ai chấm được vẫn đọc ra "không có lỗi hệ thống".
  CONSTRAINT c17_clean_is_measured CHECK (
    diagnosis <> 'clean'
    OR (jsonb_array_length(findings) = 0 AND jsonb_array_length(skipped) = 0)),
  -- Ngược lại: có mã đã nổ thì không thể là `clean` hay `unknown`.
  CONSTRAINT c17_findings_imply_fault CHECK (
    jsonb_array_length(findings) = 0
    OR diagnosis NOT IN ('clean','unknown')),
  -- C20 (bản 0.5), ba luật của validator `SystemDiagnosis` (PR #146). Ghi
  -- nhận chỉ có trên rollout đồng bộ; chỉ R1, R2 được ghi nhận; và rollout
  -- đồng bộ không được vừa ghi nhận vừa tính R1, R2.
  CONSTRAINT c20_recorded_only_on_sync CHECK (
    timing = 'sync'
    OR (jsonb_array_length(recorded) = 0 AND jsonb_array_length(recorded_skipped) = 0)),
  CONSTRAINT c20_only_r1_r2_recorded CHECK (NOT jsonb_path_exists(
    recorded || recorded_skipped, '$[*] ? (@.code != "R1" && @.code != "R2")')),
  CONSTRAINT c20_sync_does_not_count_r1_r2 CHECK (
    timing IS DISTINCT FROM 'sync'
    OR NOT jsonb_path_exists(
      findings || skipped, '$[*] ? (@.code == "R1" || @.code == "R2")')),
  CHECK (jsonb_typeof(findings) = 'array' AND jsonb_typeof(skipped) = 'array'),
  CHECK (jsonb_typeof(recorded) = 'array' AND jsonb_typeof(recorded_skipped) = 'array')
);
CREATE INDEX ON system_diagnoses (eval_episode_id, created_at DESC);
CREATE INDEX ON system_diagnoses (diagnosis);

-- ---------------------------------------------------------------------------
-- flywheel_recommendations · một lượt Failure → Data
-- ---------------------------------------------------------------------------
CREATE TABLE flywheel_recommendations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  recommendation_ref VARCHAR(64) NOT NULL UNIQUE, -- khoá tự nhiên của lõi
  run_plan_id UUID REFERENCES run_plans(id),
  checkpoint_id UUID NOT NULL REFERENCES model_checkpoints(id),
  evaluation_id UUID REFERENCES sim_evaluations(id),
  task_id VARCHAR(16) NOT NULL CHECK (task_id IN ('two_table','tray')),
  round_no INTEGER NOT NULL DEFAULT 1 CHECK (round_no >= 1),
  status VARCHAR(16) NOT NULL DEFAULT 'RUNNING' CHECK (status IN (
    'RUNNING','AWAITING_REVIEW','APPROVED','REJECTED','DONE','FAILED')),
  -- Ba trần song song (BR-07). Vượt trần nào cũng dừng, nên ba cột chứ không
  -- phải một con số quy đổi.
  budget_usd NUMERIC(12,2),
  budget_human_minutes NUMERIC(10,2),
  budget_gpu_hours NUMERIC(10,3),
  started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  finished_at TIMESTAMPTZ
);

-- ---------------------------------------------------------------------------
-- failure_clusters · cụm lỗi và chẩn đoán
-- ---------------------------------------------------------------------------
CREATE TABLE failure_clusters (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  cluster_ref VARCHAR(64) NOT NULL UNIQUE,      -- clu_<hash> (03 §4.3)
  recommendation_id UUID NOT NULL REFERENCES flywheel_recommendations(id),
  failed_step SMALLINT NOT NULL,
  failure_code VARCHAR(32) NOT NULL,
  level SMALLINT NOT NULL CHECK (level BETWEEN 0 AND 2),
  member_count INTEGER NOT NULL CHECK (member_count > 0),
  -- Ref `eval_episode_ref` của lõi, không phải UUID: bộ nạp chỉ có ref, và
  -- một mảng UUID không có khoá ngoại nào kiểm được từng phần tử.
  representative_refs VARCHAR(64)[] NOT NULL
    CHECK (cardinality(representative_refs) BETWEEN 1 AND 5),
  representative_seed BIGINT NOT NULL,
  diagnosis VARCHAR(32),
  diagnosis_source VARCHAR(20) CHECK (diagnosis_source IN ('auto','engineer_override')),
  override_reason TEXT,
  -- COALESCE là cần: không có nó thì cụm chưa chẩn đoán ra NULL, và truy vấn
  -- `WHERE NOT consumes_data_budget` bỏ sót đúng những cụm đó.
  consumes_data_budget BOOLEAN GENERATED ALWAYS AS (COALESCE(
    diagnosis IN ('TRANG_THAI_DAU_XAU','THIEU_VUNG_PHU','KY_NANG_YEU'), FALSE)) STORED,
  parent_cluster_id UUID REFERENCES failure_clusters(id),
  -- Giá trị và ngưỡng từng phép kiểm, cộng `skipped` kèm lý do.
  checks JSONB NOT NULL DEFAULT '{}',
  card_uri TEXT,                               -- evidence card HTML
  UNIQUE (recommendation_id, failed_step, failure_code, level),
  CHECK (diagnosis IS NULL OR diagnosis IN (
    'CHUA_RO','HE_THONG_CONTROLLER','HE_THONG_RUNTIME','HE_THONG_DONG_BO',
    'HE_THONG_CALIBRATION','KHONG_KHA_THI','TRANG_THAI_DAU_XAU','NHAN_THUC',
    'NGOAI_MIEN','THIEU_VUNG_PHU','KY_NANG_YEU')),
  CHECK ((diagnosis IS NULL) = (diagnosis_source IS NULL)),
  CHECK (diagnosis_source IS DISTINCT FROM 'engineer_override' OR override_reason IS NOT NULL)
);
CREATE INDEX ON failure_clusters (recommendation_id, consumes_data_budget);

-- ---------------------------------------------------------------------------
-- diagnostic_runs · rollout của bước 5, 6, 7 và chi phí của chúng
-- ---------------------------------------------------------------------------
CREATE TABLE diagnostic_runs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  cluster_id UUID NOT NULL REFERENCES failure_clusters(id),
  step_no SMALLINT NOT NULL CHECK (step_no BETWEEN 1 AND 12),
  check_name VARCHAR(32) NOT NULL,
  representative_episode_id UUID REFERENCES eval_episodes(id),
  rollout_count INTEGER NOT NULL DEFAULT 0 CHECK (rollout_count >= 0),
  -- Phép kiểm không chạy được thì `skipped`, không phải `failed`: simulator
  -- không khôi phục được trạng thái là chuyện bình thường (§5.3).
  outcome VARCHAR(12) NOT NULL CHECK (outcome IN ('passed','failed','skipped')),
  skip_reason TEXT,
  value DOUBLE PRECISION,
  threshold DOUBLE PRECISION,
  gpu_seconds NUMERIC(10,2),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (outcome <> 'skipped' OR skip_reason IS NOT NULL)
);
CREATE INDEX ON diagnostic_runs (cluster_id, step_no);

-- ---------------------------------------------------------------------------
-- interventions · can thiệp đề xuất (thay data_collection_requests)
-- ---------------------------------------------------------------------------
CREATE TABLE interventions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  intervention_ref VARCHAR(64) NOT NULL UNIQUE,   -- iv_<ULID>
  recommendation_id UUID NOT NULL REFERENCES flywheel_recommendations(id),
  cluster_id UUID REFERENCES failure_clusters(id),
  kind VARCHAR(24) NOT NULL CHECK (kind IN (
    'SIM_AROUND_FAILURE','TELEOP_CORRECTION','RECOVERY_DATA')),
  target_quantity INTEGER NOT NULL CHECK (target_quantity > 0),
  unit VARCHAR(16) NOT NULL,
  spec JSONB NOT NULL DEFAULT '{}',               -- bán kính, mức, bước k
  n_failures INTEGER CHECK (n_failures >= 0),      -- m_j của cụm
  n_eff INTEGER CHECK (n_eff >= 0),                -- min(m_j, L_t)
  expected_gain_pp NUMERIC(6,3),                   -- g_j, điểm % trên dev
  estimated_usd NUMERIC(12,2),
  estimated_human_minutes NUMERIC(10,2),
  estimated_gpu_hours NUMERIC(10,3),
  status VARCHAR(16) NOT NULL DEFAULT 'PROPOSED' CHECK (status IN (
    'PROPOSED','APPROVED','REJECTED','IN_PROGRESS','FULFILLED','CANCELLED')),
  approved_quantity INTEGER CHECK (approved_quantity > 0),
  assignee_id UUID REFERENCES app_users(id),
  due_at TIMESTAMPTZ,
  -- n_eff = min(m_j, L) nên không bao giờ lớn hơn số lỗi của cụm.
  CHECK (n_eff IS NULL OR n_failures IS NULL OR n_eff <= n_failures),
  CHECK (status <> 'APPROVED' OR approved_quantity IS NOT NULL)
);
CREATE INDEX ON interventions (recommendation_id, status);

-- Episode thu về trỏ ngược về can thiệp sinh ra nó. Số đã thực hiện đếm bằng
-- truy vấn, không nhập tay.
ALTER TABLE episodes
  ADD CONSTRAINT episodes_intervention_fk
  FOREIGN KEY (intervention_id) REFERENCES interventions(id);
ALTER TABLE episodes
  ADD CONSTRAINT episodes_checkpoint_fk
  FOREIGN KEY (checkpoint_id) REFERENCES model_checkpoints(id);

-- ---------------------------------------------------------------------------
-- fix_rate_events · tỉ lệ sửa được, đo có đối chứng
-- ---------------------------------------------------------------------------
CREATE TABLE fix_rate_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  intervention_kind VARCHAR(24) NOT NULL,
  cluster_id UUID NOT NULL REFERENCES failure_clusters(id),
  intervention_id UUID NOT NULL REFERENCES interventions(id),
  failure_code VARCHAR(32),
  failure_class VARCHAR(16),
  n_conditions INTEGER NOT NULL CHECK (n_conditions > 0),
  p_parent NUMERIC(5,4) NOT NULL CHECK (p_parent BETWEEN 0 AND 1),
  p_candidate NUMERIC(5,4) NOT NULL CHECK (p_candidate BETWEEN 0 AND 1),
  fixed_count INTEGER NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (fixed_count BETWEEN 0 AND n_conditions)
);
-- Hậu nghiệm Beta gộp lúc đọc: α = 1 + Σ fixed_count,
-- β = 1 + Σ (n_conditions − fixed_count). Bảng chỉ thêm.
CREATE INDEX ON fix_rate_events (intervention_kind);

-- ---------------------------------------------------------------------------
-- repair_tickets · lỗi hệ thống, không tiêu ngân sách dữ liệu
-- ---------------------------------------------------------------------------
CREATE TABLE repair_tickets (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  cluster_id UUID NOT NULL REFERENCES failure_clusters(id),
  diagnosis VARCHAR(32) NOT NULL,
  title TEXT NOT NULL,
  detail TEXT,
  status VARCHAR(16) NOT NULL DEFAULT 'OPEN' CHECK (status IN (
    'OPEN','IN_PROGRESS','FIXED','WONT_FIX')),
  -- Sửa lỗi hệ thống xong thì mọi số đo trước đó phải chạy lại; FE hiện cảnh
  -- báo đỏ trên các nhánh bị ảnh hưởng.
  rebaseline_required BOOLEAN NOT NULL DEFAULT TRUE,
  assignee_id UUID REFERENCES app_users(id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ON repair_tickets (status) WHERE status IN ('OPEN','IN_PROGRESS');

-- ---------------------------------------------------------------------------
-- flywheel_algo_steps · 12 bước, một dòng một bước
-- ---------------------------------------------------------------------------
CREATE TABLE flywheel_algo_steps (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  recommendation_id UUID NOT NULL REFERENCES flywheel_recommendations(id),
  -- Hai khoá giữa để NULL ở các bước chạy một lần cho cả lượt (§5.3).
  cluster_id UUID REFERENCES failure_clusters(id),
  eval_episode_id UUID REFERENCES eval_episodes(id),
  step_no SMALLINT NOT NULL CHECK (step_no BETWEEN 1 AND 12),
  status VARCHAR(12) NOT NULL DEFAULT 'pending' CHECK (status IN (
    'pending','running','done','skipped','failed')),
  skip_reason TEXT,
  rollout_count INTEGER NOT NULL DEFAULT 0 CHECK (rollout_count >= 0),
  started_at TIMESTAMPTZ,
  finished_at TIMESTAMPTZ,
  detail JSONB NOT NULL DEFAULT '{}',
  CHECK (status <> 'skipped' OR skip_reason IS NOT NULL)
);
CREATE UNIQUE INDEX ON flywheel_algo_steps (
  recommendation_id, step_no,
  COALESCE(cluster_id, '00000000-0000-0000-0000-000000000000'::uuid),
  COALESCE(eval_episode_id, '00000000-0000-0000-0000-000000000000'::uuid));

-- ---------------------------------------------------------------------------
-- decisions · nhật ký quyết định, append-only
-- ---------------------------------------------------------------------------
CREATE TABLE decisions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  decision_ref VARCHAR(64) NOT NULL UNIQUE,    -- dec_<ULID>
  kind VARCHAR(24) NOT NULL CHECK (kind IN (
    'plan_review','dev_gate','aa_test','holdout','milestone','repair_ticket',
    'diagnosis_override','holdout_unseal','stage_review')),
  target_kind VARCHAR(32) NOT NULL,
  target_id UUID,
  measures JSONB NOT NULL DEFAULT '{}',
  criteria JSONB NOT NULL DEFAULT '{}',
  conclusion TEXT NOT NULL,
  -- Tỉ lệ kỹ sư ghi đè đề xuất (M10) đếm trên cột này, nên nó phải có mặt
  -- trên mọi quyết định ghi đè.
  signed_by UUID REFERENCES app_users(id),
  reason TEXT,
  -- Hành động của web sinh ra quyết định này. Đây là chỗ fwsync import nối
  -- một `human_actions` với kết quả của nó (§3.2, W7).
  source_action_id UUID,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  meta JSONB NOT NULL DEFAULT '{}',
  CHECK (kind NOT IN ('diagnosis_override','holdout_unseal') OR reason IS NOT NULL)
);
CREATE INDEX ON decisions (kind, created_at DESC);
CREATE INDEX ON decisions (source_action_id) WHERE source_action_id IS NOT NULL;

-- ---------------------------------------------------------------------------
-- cost_ledger_entries · sổ chi phí, chỉ thêm
-- ---------------------------------------------------------------------------
CREATE TABLE cost_ledger_entries (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  entry_ref VARCHAR(64) NOT NULL UNIQUE,       -- led_<ULID>
  entry_kind VARCHAR(12) NOT NULL DEFAULT 'ENTRY' CHECK (entry_kind IN (
    'ENTRY','REVERSAL')),
  reverses_entry_id UUID REFERENCES cost_ledger_entries(id),
  activity VARCHAR(32) NOT NULL,
  resource_type VARCHAR(32) NOT NULL,
  quantity NUMERIC(14,4) NOT NULL,
  unit VARCHAR(16) NOT NULL,
  price_book_id UUID NOT NULL REFERENCES price_books(id),
  -- Ước tính và thực đo cùng một dòng, hai cột (luật R5), nên sai số dự báo
  -- chi phí là một phép trừ, không phải một phép join.
  estimated_usd NUMERIC(12,2),
  measured_usd NUMERIC(12,2),
  estimated_human_minutes NUMERIC(10,2),
  measured_human_minutes NUMERIC(10,2),
  estimated_gpu_hours NUMERIC(10,3),
  measured_gpu_hours NUMERIC(10,3),
  dataset_id UUID REFERENCES datasets(id),
  experiment_id UUID REFERENCES experiments(id),
  evaluation_id UUID REFERENCES sim_evaluations(id),
  recommendation_id UUID REFERENCES flywheel_recommendations(id),
  intervention_id UUID REFERENCES interventions(id),
  cluster_id UUID REFERENCES failure_clusters(id),
  run_plan_id UUID REFERENCES run_plans(id),
  branch VARCHAR(16),
  job_id VARCHAR(64),
  -- Mã giả danh, không phải tên người. Ánh xạ sang tên chỉ có ở app_users.
  operator_code VARCHAR(16),
  note TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  -- C10: bút toán ước tính phải gắn khuyến nghị hoặc can thiệp, nếu không thì
  -- không ai biết nó ước tính cho việc gì.
  CONSTRAINT c10_estimate_has_owner CHECK (
    estimated_usd IS NULL OR num_nonnulls(recommendation_id, intervention_id) >= 1),
  -- C11: mỗi bút toán gắn ít nhất một đối tượng.
  CONSTRAINT c11_entry_has_target CHECK (
    num_nonnulls(dataset_id, experiment_id, evaluation_id,
                 recommendation_id, intervention_id) >= 1),
  CONSTRAINT c9_reversal_has_target CHECK (
    (entry_kind = 'REVERSAL') = (reverses_entry_id IS NOT NULL))
);
CREATE INDEX ON cost_ledger_entries (branch, created_at);
CREATE INDEX ON cost_ledger_entries (intervention_id) WHERE intervention_id IS NOT NULL;
-- C9: một bút toán chỉ bị đảo một lần.
CREATE UNIQUE INDEX c9_reverse_once ON cost_ledger_entries (reverses_entry_id)
  WHERE reverses_entry_id IS NOT NULL;

-- ---------------------------------------------------------------------------
-- Ba cột chung của mọi bảng nhóm P (§4.4b)
-- ---------------------------------------------------------------------------
-- Thêm bằng một vòng thay vì lặp 29 lần: danh sách này cũng là định nghĩa
-- "bảng nào thuộc nhóm P", nên test kiểm được bất biến bằng cách so nó với
-- pg_catalog.
DO $$
DECLARE
  p_table TEXT;
  p_tables TEXT[] := ARRAY[
    'sources','price_books','run_plans','datasets','pipeline_stage_defs',
    'pipeline_stage_runs','episodes','episode_qa_reports','releases',
    'release_items','experiments','experiment_datasets','model_checkpoints',
    'training_metrics','train_diagnoses','train_diagnosis_skips',
    'probe_results','sim_evaluations','eval_episodes','system_diagnoses',
    'flywheel_recommendations','failure_clusters','diagnostic_runs',
    'interventions','fix_rate_events','repair_tickets','flywheel_algo_steps',
    'decisions','cost_ledger_entries'];
BEGIN
  FOREACH p_table IN ARRAY p_tables LOOP
    EXECUTE format(
      'ALTER TABLE %I
         ADD COLUMN origin VARCHAR(8) NOT NULL DEFAULT ''core''
           CHECK (origin IN (''core'',''mock'')),
         ADD COLUMN sync_run_id BIGINT REFERENCES sync_runs(id),
         ADD COLUMN synced_at TIMESTAMPTZ NOT NULL DEFAULT now()', p_table);
  END LOOP;
END
$$;

-- `pipeline_stage_defs` được seed bằng INSERT trong file này, không qua
-- fwsync, nên nó là bảng P duy nhất có dòng không mang sync_run_id.
