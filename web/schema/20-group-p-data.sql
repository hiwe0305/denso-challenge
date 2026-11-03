-- Nhóm P, nửa dữ liệu: nguồn, lô, episode, pipeline 6 tầng, release, bảng giá.
-- Chỉ fw_sync ghi (DESIGN.md luật R1). Thứ tự file theo khoá ngoại, không theo
-- nhóm logic của §4.1.
--
-- Ba cột chung của nhóm P (origin, sync_run_id, synced_at) được thêm ở cuối
-- 30-group-p-ml.sql bằng một vòng, nên không lặp lại ở từng bảng.

-- ---------------------------------------------------------------------------
-- sources · nguồn tải về và checkpoint gốc
-- ---------------------------------------------------------------------------
CREATE TABLE sources (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source_ref VARCHAR(64) NOT NULL UNIQUE,      -- src_<hash> từ lõi
  url TEXT,
  repo TEXT,
  revision VARCHAR(64),                        -- revision HF hoặc git
  sha256 CHAR(64),
  license VARCHAR(64) NOT NULL,
  downloaded_at TIMESTAMPTZ,
  kind VARCHAR(16) NOT NULL CHECK (kind IN ('dataset','checkpoint','model','other')),
  -- Dữ liệu đã dùng để train nếu là checkpoint, cộng bằng chứng. Ba trạng thái
  -- vì "không biết" khác "sạch": BR-01 chỉ chặn `false`, nên một checkpoint
  -- chưa ai kiểm vẫn vào được thí nghiệm và điều đó phải thấy được.
  clean_for_main_task VARCHAR(8) NOT NULL DEFAULT 'unknown'
    CHECK (clean_for_main_task IN ('true','false','unknown')),
  provenance JSONB NOT NULL DEFAULT '{}',
  CHECK (url IS NOT NULL OR repo IS NOT NULL)
);

-- ---------------------------------------------------------------------------
-- price_books · bảng giá có phiên bản
-- ---------------------------------------------------------------------------
CREATE TABLE price_books (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name VARCHAR(32) NOT NULL,                   -- pitch_v10 | denso | cell_dat | gpu_dat
  sha256 CHAR(64) NOT NULL,
  -- {resource_type: {unit, usd_per_unit, human_hours_per_unit}}
  rates JSONB NOT NULL,
  cell_hour_usd NUMERIC(10,2) NOT NULL DEFAULT 0,
  effective_from DATE NOT NULL,
  note TEXT,
  -- Nhiều bảng giá tồn tại song song để chạy bốn kịch bản độ nhạy, nên khoá
  -- là (tên, hash) chứ không phải tên: hai bản của cùng một tên là hai kịch
  -- bản, không phải một bản ghi đè bản kia.
  UNIQUE (name, sha256)
);

-- ---------------------------------------------------------------------------
-- run_plans · cấu hình đóng băng có hash
-- ---------------------------------------------------------------------------
CREATE TABLE run_plans (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  run_plan_ref VARCHAR(64) NOT NULL UNIQUE,    -- rp_<hash>
  purpose VARCHAR(16) NOT NULL CHECK (purpose IN (
    'g0_repro','e1','branch_train','aa_test','round','holdout','hd')),
  branch VARCHAR(16),
  method VARCHAR(24),
  task_id VARCHAR(16),
  lock_uri TEXT NOT NULL,                      -- đường dẫn runplan.lock.json
  config_sha256 CHAR(64) NOT NULL,
  frozen_at TIMESTAMPTZ NOT NULL,
  seed_range INT8RANGE,
  meta JSONB NOT NULL DEFAULT '{}'
);

-- ---------------------------------------------------------------------------
-- datasets · một lô dữ liệu
-- ---------------------------------------------------------------------------
CREATE TABLE datasets (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  dataset_code VARCHAR(64) NOT NULL,
  source_id UUID REFERENCES sources(id),
  source_kind VARCHAR(16) NOT NULL CHECK (source_kind IN (
    'teleop','synthetic','egocentric')),
  source_detail VARCHAR(32),
  data_class VARCHAR(16) NOT NULL CHECK (data_class IN (
    'public','internal','restricted')),
  license VARCHAR(64) NOT NULL,
  status VARCHAR(24) NOT NULL DEFAULT 'INGESTED' CHECK (status IN (
    'INGESTED','PROCESSING','PAUSED_FOR_REVIEW','READY_FOR_TRAINING','FAILED','ABORTED')),
  -- TRUE khi lô này là bản sao cấy lỗi dùng để chấm Agent QA/QC. Đáp án không
  -- nằm ở đây; nó nằm trong nhóm S mà agent_ro bị REVOKE (luật R8).
  has_seeded_faults BOOLEAN NOT NULL DEFAULT FALSE,
  episode_count INTEGER NOT NULL DEFAULT 0 CHECK (episode_count >= 0),
  note TEXT,
  is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  deleted_at TIMESTAMPTZ,
  delete_reason TEXT,
  CONSTRAINT c12_delete_reason CHECK (NOT is_deleted OR delete_reason IS NOT NULL)
);
-- C1: mã duy nhất trong số bản ghi còn sống; xoá mềm rồi tạo lại cùng mã vẫn được.
CREATE UNIQUE INDEX c1_dataset_code ON datasets (dataset_code) WHERE NOT is_deleted;

-- ---------------------------------------------------------------------------
-- pipeline_stage_defs · định nghĩa 6 tầng
-- ---------------------------------------------------------------------------
CREATE TABLE pipeline_stage_defs (
  stage_number SMALLINT PRIMARY KEY CHECK (stage_number BETWEEN 1 AND 6),
  code VARCHAR(16) NOT NULL UNIQUE CHECK (code IN (
    'INGEST','NORMALIZE','ANNOTATE','QA','RELEASE','EXPORT')),
  display_name VARCHAR(64) NOT NULL,
  -- Tầng 4 là cổng: 7 phép kiểm bằng code quyết định đi tiếp hay dừng, agent
  -- không đổi được (§1 điểm 7).
  is_gate BOOLEAN NOT NULL DEFAULT FALSE
);

INSERT INTO pipeline_stage_defs (stage_number, code, display_name, is_gate) VALUES
  (1, 'INGEST',    'Ingest',    FALSE),
  (2, 'NORMALIZE', 'Normalize', FALSE),
  (3, 'ANNOTATE',  'Annotate',  FALSE),
  (4, 'QA',        'QA',        TRUE),
  (5, 'RELEASE',   'Release',   FALSE),
  (6, 'EXPORT',    'Export',    FALSE);

-- ---------------------------------------------------------------------------
-- pipeline_stage_runs · một lần chạy một tầng
-- ---------------------------------------------------------------------------
CREATE TABLE pipeline_stage_runs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  dataset_id UUID NOT NULL REFERENCES datasets(id),
  stage_number SMALLINT NOT NULL REFERENCES pipeline_stage_defs(stage_number),
  attempt_no SMALLINT NOT NULL DEFAULT 1 CHECK (attempt_no >= 1),
  -- Chạy lại từ tầng k sinh attempt mới cho k..6 và hạ cờ này của attempt cũ
  -- (BR-02). Attempt cũ giữ làm lịch sử, không bị xoá.
  is_current BOOLEAN NOT NULL DEFAULT TRUE,
  status VARCHAR(20) NOT NULL DEFAULT 'PENDING' CHECK (status IN (
    'PENDING','RUNNING','QA_EVALUATING','PASSED','PAUSED_FOR_REVIEW',
    'OVERRIDDEN','FAILED','ABORTED')),
  -- Hai nhãn cạnh nhau, đúng ý §1 điểm 7: cổng là `qa_code_decision`, còn
  -- agent chỉ diễn giải. Gộp một cột thì demo mất câu "code bắt x, agent bắt
  -- thêm y".
  qa_code_decision VARCHAR(16) CHECK (qa_code_decision IN (
    'pass','flag','quarantine','reject')),
  qa_agent_verdict VARCHAR(8) CHECK (qa_agent_verdict IN ('PASS','WARNING','FAIL')),
  qa_agent_report JSONB,
  started_at TIMESTAMPTZ,
  finished_at TIMESTAMPTZ,
  log_uri TEXT,
  metrics JSONB NOT NULL DEFAULT '{}',
  -- C3: số attempt không trùng.
  CONSTRAINT c3_attempt_unique UNIQUE (dataset_id, stage_number, attempt_no)
);
-- C2: mỗi (lô, tầng) chỉ một attempt đang hiệu lực.
CREATE UNIQUE INDEX c2_one_current_attempt
  ON pipeline_stage_runs (dataset_id, stage_number) WHERE is_current;
CREATE INDEX ON pipeline_stage_runs (status) WHERE status = 'PAUSED_FOR_REVIEW';

-- ---------------------------------------------------------------------------
-- episodes · đơn vị dữ liệu nhỏ nhất
-- ---------------------------------------------------------------------------
CREATE TABLE episodes (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  episode_ref VARCHAR(64) NOT NULL UNIQUE,     -- ep_<ULID> từ lõi
  dataset_id UUID NOT NULL REFERENCES datasets(id),
  episode_index INTEGER NOT NULL,
  kind VARCHAR(24) NOT NULL CHECK (kind IN (
    'teleop_demo','teleop_correction','recovery','sim_rollout','variant',
    'eval_rollout','diag_rollout')),
  source_kind VARCHAR(16) NOT NULL CHECK (source_kind IN (
    'teleop','synthetic','egocentric')),
  source_detail VARCHAR(32),
  synthetic_tier VARCHAR(4) CHECK (synthetic_tier IN ('S1','S2','S3','S4')),
  action_quality VARCHAR(16) NOT NULL CHECK (action_quality IN (
    'measured','planned','retargeted','pseudo','none')),
  operator_kind VARCHAR(8) NOT NULL CHECK (operator_kind IN ('human','machine')),
  embodiment_id VARCHAR(64) NOT NULL,
  is_root BOOLEAN NOT NULL DEFAULT FALSE,
  parent_id UUID REFERENCES episodes(id),
  root_id UUID REFERENCES episodes(id),
  intervention_id UUID,                        -- FK thêm ở 30-group-p-ml.sql
  condition_id VARCHAR(64),
  condition_seed BIGINT,
  run_plan_id UUID REFERENCES run_plans(id),
  split VARCHAR(16) NOT NULL DEFAULT 'unassigned' CHECK (split IN (
    'train','dev','holdout','unassigned')),
  data_class VARCHAR(16) NOT NULL CHECK (data_class IN (
    'public','internal','restricted')),
  license VARCHAR(64) NOT NULL,
  deid_status VARCHAR(16) NOT NULL DEFAULT 'raw' CHECK (deid_status IN (
    'raw','blurred','verified')),
  renderer VARCHAR(8) CHECK (renderer IN ('mujoco','isaac')),
  bundle_uri TEXT NOT NULL,
  sha256 CHAR(64),
  frame_count INTEGER CHECK (frame_count >= 0),
  duration_s NUMERIC(8,3),
  -- Với trace: cờ của simulator và trạng thái hạ tầng của lượt chạy.
  checkpoint_id UUID,                          -- FK thêm ở 30-group-p-ml.sql
  rollout_seed BIGINT,
  sim_success BOOLEAN,
  infra_status VARCHAR(24),
  camera_params_hash VARCHAR(64),
  -- Bản 0.3: KHÔNG có cột đáp án lỗi cấy ở đây.
  -- 03 bản 1.0 (PO, 3/11/2026) bỏ `injected_defect` khỏi Episode. Episode của
  -- bản sao chấm Agent QA/QC chỉ nói nó thuộc bản sao nào; đáp án (episode
  -- nào, mã gì, tham số nào) chỉ nằm trong DefectManifest, mà agent_ro bị
  -- REVOKE. Để đáp án ở đây là phá luật R8, vì agent đọc được episodes qua
  -- view. Issue #62.
  benchmark_copy_id VARCHAR(64),
  meta JSONB NOT NULL DEFAULT '{}',
  UNIQUE (dataset_id, episode_index),
  -- Episode gốc là demo do người làm. `r_demo` của M8 đếm đúng cờ này, nên
  -- một episode máy sinh mang is_root sẽ làm sai chỉ số chính của bài toán
  -- kinh tế.
  CHECK (is_root = FALSE OR (operator_kind = 'human'
         AND kind IN ('teleop_demo','teleop_correction','recovery'))),
  CHECK (source_kind <> 'synthetic' OR synthetic_tier IS NOT NULL)
);
CREATE INDEX ON episodes (dataset_id, source_kind);
CREATE INDEX ON episodes (split) WHERE split <> 'unassigned';
CREATE INDEX ON episodes (benchmark_copy_id) WHERE benchmark_copy_id IS NOT NULL;
CREATE INDEX ON episodes (dataset_id) WHERE is_root AND operator_kind = 'human';

-- ---------------------------------------------------------------------------
-- episode_qa_reports · 7 phép kiểm từng episode, append-only
-- ---------------------------------------------------------------------------
CREATE TABLE episode_qa_reports (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  episode_id UUID NOT NULL REFERENCES episodes(id),
  stage_run_id UUID REFERENCES pipeline_stage_runs(id),
  threshold_version VARCHAR(32) NOT NULL,
  decision VARCHAR(16) NOT NULL CHECK (decision IN (
    'pass','flag','quarantine','reject')),
  reasons TEXT[] NOT NULL DEFAULT '{}',
  -- [{name, value, threshold, passed}]
  checks JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  -- Một quyết định khác `pass` mà không nói vì sao thì không ai sửa được.
  CHECK (decision = 'pass' OR cardinality(reasons) > 0)
);
-- Trạng thái QA hiện hành là dòng mới nhất. Chấm lại tạo dòng mới.
CREATE INDEX ON episode_qa_reports (episode_id, created_at DESC);

-- ---------------------------------------------------------------------------
-- releases · manifest đóng băng có hash
-- ---------------------------------------------------------------------------
CREATE TABLE releases (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  release_ref VARCHAR(64) NOT NULL,            -- rel_<hash>
  name VARCHAR(128) NOT NULL,
  parent_release_id UUID REFERENCES releases(id),
  split_plan_sha256 CHAR(64),
  status VARCHAR(8) NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','frozen')),
  manifest_sha256 CHAR(64),
  manifest_uri TEXT,
  license_summary VARCHAR(255),
  frozen_at TIMESTAMPTZ,
  meta JSONB NOT NULL DEFAULT '{}',
  is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  deleted_at TIMESTAMPTZ,
  delete_reason TEXT,
  CONSTRAINT c12_release_delete_reason CHECK (NOT is_deleted OR delete_reason IS NOT NULL),
  -- Đóng băng thì bất biến, và hash tính trên manifest. Một release `frozen`
  -- không có hash là một release không tái lập được, tức là vô dụng.
  CHECK (status <> 'frozen' OR (manifest_sha256 IS NOT NULL AND frozen_at IS NOT NULL))
);
CREATE UNIQUE INDEX c1_release_ref ON releases (release_ref) WHERE NOT is_deleted;

-- ---------------------------------------------------------------------------
-- release_items · mỗi dòng một episode trong release
-- ---------------------------------------------------------------------------
CREATE TABLE release_items (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  release_id UUID NOT NULL REFERENCES releases(id),
  episode_id UUID NOT NULL REFERENCES episodes(id),
  sample_weight NUMERIC(8,4) NOT NULL DEFAULT 1.0 CHECK (sample_weight >= 0),
  excluded BOOLEAN NOT NULL DEFAULT FALSE,
  exclude_reason TEXT,
  UNIQUE (release_id, episode_id),
  CHECK (NOT excluded OR exclude_reason IS NOT NULL)
);
CREATE INDEX ON release_items (release_id) WHERE NOT excluded;
