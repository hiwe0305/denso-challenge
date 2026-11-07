-- Nhóm W, phần còn lại: hành động của người, hàng đợi yêu cầu, bản nháp,
-- chat và thông báo (DESIGN.md §4.4a).
--
-- Đây là toàn bộ chỗ web được ghi. Không endpoint nào ghi bảng nhóm P, và
-- role fw_api không có quyền để làm việc đó (luật R1, R2).

-- ---------------------------------------------------------------------------
-- human_actions · một đường ghi duy nhất
-- ---------------------------------------------------------------------------
CREATE TABLE human_actions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  action_kind VARCHAR(32) NOT NULL CHECK (action_kind IN (
    'INTAKE_SUBMIT','STAGE_REVIEW','EXPERIMENT_SUBMIT',
    'RECOMMENDATION_DECISION','DIAGNOSIS_OVERRIDE',
    'RELEASE_FREEZE_REQUEST','EVAL_REQUEST','FLYWHEEL_RUN_REQUEST',
    'HOLDOUT_UNSEAL','SOFT_DELETE','CHAT_ACTION_CONFIRM')),
  target_kind VARCHAR(32) NOT NULL,            -- bảng đích
  target_id UUID,                              -- NULL khi hành động tạo mới
  payload JSONB NOT NULL,
  reason TEXT,
  actor_id UUID NOT NULL REFERENCES app_users(id),
  idempotency_key VARCHAR(64) NOT NULL UNIQUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  -- Năm cột dưới: chỉ fw_sync được UPDATE, bằng quyền theo cột ở 70-grants.sql.
  sync_status VARCHAR(12) NOT NULL DEFAULT 'PENDING' CHECK (sync_status IN (
    'PENDING','EXPORTED','APPLIED','REJECTED')),
  exported_at TIMESTAMPTZ,
  artifact_uri TEXT,
  applied_at TIMESTAMPTZ,
  reject_reason TEXT,
  -- Ba hành động bắt buộc có lý do (BR-04, BR-10). Ghi đè chẩn đoán mà không
  -- nói vì sao thì chỉ số "tỉ lệ kỹ sư ghi đè" của M10 mất nghĩa.
  CONSTRAINT w_reason_required CHECK (
    action_kind NOT IN ('DIAGNOSIS_OVERRIDE','HOLDOUT_UNSEAL','SOFT_DELETE')
    OR reason IS NOT NULL),
  CONSTRAINT w_reject_has_reason CHECK (
    sync_status <> 'REJECTED' OR reject_reason IS NOT NULL),
  -- Vòng đời tiến một chiều (§5.5): đã xuất ra outbox thì phải có dấu thời
  -- gian, đã áp dụng thì phải từng được xuất.
  CONSTRAINT w_lifecycle CHECK (
    (sync_status = 'PENDING' AND exported_at IS NULL AND applied_at IS NULL)
    OR (sync_status = 'EXPORTED' AND exported_at IS NOT NULL AND applied_at IS NULL)
    OR (sync_status = 'APPLIED' AND exported_at IS NOT NULL AND applied_at IS NOT NULL)
    OR (sync_status = 'REJECTED' AND exported_at IS NOT NULL))
);
CREATE INDEX ON human_actions (sync_status, created_at);
CREATE INDEX ON human_actions (target_kind, target_id);
CREATE INDEX ON human_actions (actor_id, created_at DESC);

-- ---------------------------------------------------------------------------
-- job_requests · việc người có máy chạy bằng lõi
-- ---------------------------------------------------------------------------
CREATE TABLE job_requests (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  action_id UUID NOT NULL UNIQUE REFERENCES human_actions(id),
  job_kind VARCHAR(24) NOT NULL CHECK (job_kind IN (
    'PIPELINE_RUN','PIPELINE_RETRY_FROM','TRAIN','PROBE','EVAL',
    'RELEASE_FREEZE','FLYWHEEL_RUN')),
  spec JSONB NOT NULL,
  status VARCHAR(12) NOT NULL DEFAULT 'OPEN' CHECK (status IN (
    'OPEN','PICKED','DONE','FAILED','CANCELLED')),
  picked_by VARCHAR(16),                       -- operator_code
  result_ref VARCHAR(64),                      -- fw_sync điền từ JobStatus (W7)
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (status = 'OPEN' OR picked_by IS NOT NULL),
  CHECK (status <> 'DONE' OR result_ref IS NOT NULL)
);
CREATE INDEX ON job_requests (status, created_at) WHERE status = 'OPEN';

-- ---------------------------------------------------------------------------
-- dataset_intakes · phiếu nạp dữ liệu
-- ---------------------------------------------------------------------------
CREATE TABLE dataset_intakes (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  intake_code VARCHAR(64) NOT NULL UNIQUE,
  source_kind VARCHAR(16) NOT NULL CHECK (source_kind IN (
    'teleop','synthetic','egocentric')),
  source_detail VARCHAR(32),
  data_class VARCHAR(16) NOT NULL CHECK (data_class IN (
    'public','internal','restricted')),
  license VARCHAR(64) NOT NULL,
  upload_uris TEXT[] NOT NULL DEFAULT '{}',    -- trong $FW_WEB_BLOBS
  manual_review BOOLEAN NOT NULL DEFAULT FALSE,
  seeded_faults BOOLEAN NOT NULL DEFAULT FALSE,
  defect_seed BIGINT,
  note TEXT,
  status VARCHAR(12) NOT NULL DEFAULT 'DRAFT' CHECK (status IN (
    'DRAFT','SUBMITTED','ACCEPTED','REJECTED')),
  submit_action_id UUID REFERENCES human_actions(id),
  dataset_id UUID REFERENCES datasets(id),     -- fw_sync điền
  reject_reason TEXT,
  created_by UUID NOT NULL REFERENCES app_users(id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  -- Bật lỗi cấy mà không ghim seed thì bản sao không tái lập được, nên bộ
  -- chấm Agent QA/QC không so được hai lần chạy.
  CHECK (seeded_faults = FALSE OR defect_seed IS NOT NULL),
  CHECK (status = 'DRAFT' OR submit_action_id IS NOT NULL),
  CHECK (status <> 'REJECTED' OR reject_reason IS NOT NULL)
);
CREATE INDEX ON dataset_intakes (status, created_at DESC);

-- ---------------------------------------------------------------------------
-- experiment_drafts · bản nháp thí nghiệm
-- ---------------------------------------------------------------------------
CREATE TABLE experiment_drafts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  task_id VARCHAR(16) NOT NULL CHECK (task_id IN ('two_table','tray')),
  branch VARCHAR(16) NOT NULL,
  method VARCHAR(24) NOT NULL CHECK (method IN ('PSI0','ACT','DIFFUSION_POLICY')),
  hypothesis VARCHAR(8),
  base_checkpoint_ref VARCHAR(64) NOT NULL,    -- trỏ sources.source_ref
  run_plan_ref VARCHAR(64),                    -- NULL thì lõi sinh mới
  hyperparams JSONB NOT NULL DEFAULT '{}',
  release_mix JSONB NOT NULL DEFAULT '[]',     -- [{release_id, mix_weight}]
  status VARCHAR(12) NOT NULL DEFAULT 'DRAFT' CHECK (status IN (
    'DRAFT','SUBMITTED','ACCEPTED','REJECTED')),
  submit_action_id UUID REFERENCES human_actions(id),
  experiment_id UUID REFERENCES experiments(id),   -- fw_sync điền
  reject_reason TEXT,
  created_by UUID NOT NULL REFERENCES app_users(id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (status = 'DRAFT' OR submit_action_id IS NOT NULL),
  CHECK (status <> 'REJECTED' OR reject_reason IS NOT NULL),
  -- Cùng luật nhánh-theo-task như bảng experiments: chữ A, B, C khác nghĩa
  -- trên hai task.
  CONSTRAINT c7_draft_branch_matches_task CHECK (
    (task_id = 'two_table' AND branch IN ('A','A_07','B','C','B_FAIL','B_PLUS'))
    OR (task_id = 'tray' AND branch IN ('TRAY_A','TRAY_C','TRAY_B','TRAY_C_EGO','TRAY_C_NOEGO'))),
  CONSTRAINT c5_release_mix_is_array CHECK (jsonb_typeof(release_mix) = 'array')
);
CREATE INDEX ON experiment_drafts (status, created_at DESC);

-- ---------------------------------------------------------------------------
-- notifications · chuông
-- ---------------------------------------------------------------------------
CREATE TABLE notifications (
  id BIGSERIAL PRIMARY KEY,
  kind VARCHAR(32) NOT NULL CHECK (kind IN (
    'STAGE_PAUSED','TRAIN_DONE','TRAIN_FAILED','EVAL_DONE',
    'RECOMMENDATION_AWAITING','REPAIR_TICKET_NEW','BUDGET_EXCEEDED',
    'SYNC_LATE','ACTION_REJECTED','SCORER_SIM_MISMATCH')),
  title TEXT NOT NULL,
  body TEXT,
  target_kind VARCHAR(32),
  target_id UUID,
  -- NULL là thông báo cho cả đội; fw_sync bắn loại này khi một tầng dừng.
  recipient_id UUID REFERENCES app_users(id),
  read_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ON notifications (recipient_id, created_at DESC) WHERE read_at IS NULL;

-- ---------------------------------------------------------------------------
-- agent_chat_sessions và agent_chat_messages
-- ---------------------------------------------------------------------------
CREATE TABLE agent_chat_sessions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES app_users(id),
  title VARCHAR(255),
  -- Ngữ cảnh dùng cột riêng theo loại bản ghi, có khoá ngoại thật, thay cho
  -- một `context_ref_id` đa hình (§5.4 điểm 1): một cột đa hình không có khoá
  -- ngoại nào kiểm được, nên nó trỏ vào bản ghi đã xoá mà không ai biết.
  context_dataset_id UUID REFERENCES datasets(id),
  context_experiment_id UUID REFERENCES experiments(id),
  context_evaluation_id UUID REFERENCES sim_evaluations(id),
  context_recommendation_id UUID REFERENCES flywheel_recommendations(id),
  context_cluster_id UUID REFERENCES failure_clusters(id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  closed_at TIMESTAMPTZ
);
CREATE INDEX ON agent_chat_sessions (user_id, created_at DESC);

CREATE TABLE agent_chat_messages (
  id BIGSERIAL PRIMARY KEY,
  session_id UUID NOT NULL REFERENCES agent_chat_sessions(id),
  role VARCHAR(12) NOT NULL CHECK (role IN ('user','assistant','system')),
  content TEXT NOT NULL,
  -- Danh sách ID đã nạp cộng sha256 của prompt, không lưu nguyên khối (§5.4
  -- điểm 3): khối prompt có thể chứa dữ liệu không public, và lưu lại là mở
  -- một đường rò thứ hai cho luật R6.
  context_snapshot JSONB NOT NULL DEFAULT '{}',
  prompt_sha256 CHAR(64),
  model VARCHAR(64),
  -- Hành động agent đề xuất chỉ hiện thành nút; người bấm xác nhận thì API
  -- tạo human_actions qua đúng endpoint công khai (§5.4 điểm 4).
  proposed_action JSONB,
  confirmed_action_id UUID REFERENCES human_actions(id),
  attachments JSONB NOT NULL DEFAULT '[]',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (role <> 'assistant' OR model IS NOT NULL),
  CHECK (confirmed_action_id IS NULL OR proposed_action IS NOT NULL)
);
CREATE INDEX ON agent_chat_messages (session_id, created_at);
