-- Nhóm S · đáp án lỗi cấy, cách ly khỏi agent (DESIGN.md §4.4c, luật R8).
--
-- Ba bảng này là đáp án của bộ chấm Agent QA/QC. Chúng đứng riêng một nhóm
-- vì **một lý do duy nhất**: role agent_ro không được đọc chúng. Nếu agent
-- đọc được đáp án thì mọi số precision và recall ở M3 vô nghĩa.
--
-- Bản 0.3 nhắc lại: bảng `episodes` không còn cột `injected_defect`, nên
-- cách ly ở đây mới thật sự có hiệu lực. Ở bản 0.2 thì không: agent_ro đọc
-- được `episodes` qua view và thấy đáp án ngay trên episode.

CREATE TABLE defect_manifests (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  -- = DefectManifest.dataset_id: mã bản sao chấm, cũng là giá trị mà
  -- `episodes.benchmark_copy_id` mang khi #62 merge.
  manifest_ref VARCHAR(64) NOT NULL UNIQUE,
  dataset_id UUID NOT NULL REFERENCES datasets(id),
  seed BIGINT NOT NULL CHECK (seed >= 0),
  sha256 CHAR(64) NOT NULL,                    -- khoá đáp án
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  origin VARCHAR(8) NOT NULL DEFAULT 'core' CHECK (origin IN ('core','mock')),
  sync_run_id BIGINT REFERENCES sync_runs(id),
  synced_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  -- Một lô có một bản sao chấm; chấm lại cùng seed cho cùng đáp án.
  UNIQUE (dataset_id, seed)
);

CREATE TABLE defect_items (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  manifest_id UUID NOT NULL REFERENCES defect_manifests(id),
  target_ref VARCHAR(64) NOT NULL,             -- episode hoặc file log
  code VARCHAR(8) NOT NULL CHECK (code IN (
    'D1','D2','D3','D4','D5','D6','D7','D8',
    'T1','T2','T3','T4','T5','T6','T7','T8',
    'R1','R2')),
  parameters JSONB NOT NULL DEFAULT '{}',
  origin VARCHAR(8) NOT NULL DEFAULT 'core' CHECK (origin IN ('core','mock')),
  sync_run_id BIGINT REFERENCES sync_runs(id),
  synced_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (manifest_id, target_ref, code)
);

-- Kết quả chấm, append-only. Chấm lại là một dòng mới, không ghi đè lần
-- trước: hai `scorer_version` là hai số đo, và ghi đè sẽ xoá mất số đã báo.
CREATE TABLE defect_scores (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  manifest_id UUID NOT NULL REFERENCES defect_manifests(id),
  scorer_version VARCHAR(32) NOT NULL,
  -- Cột này là thứ cho phép M3 nói "code bắt được 6/10, agent bắt thêm 2 và
  -- giải thích đúng 7". Gộp hai bộ vào một dòng thì mất câu đó.
  detector VARCHAR(16) NOT NULL CHECK (detector IN ('code','agent')),
  agent_model VARCHAR(64),
  code VARCHAR(8) NOT NULL,
  tp INTEGER NOT NULL CHECK (tp >= 0),
  fp INTEGER NOT NULL CHECK (fp >= 0),
  fn INTEGER NOT NULL CHECK (fn >= 0),
  false_alarm_rate NUMERIC(5,4) CHECK (false_alarm_rate BETWEEN 0 AND 1),
  latency_s NUMERIC(8,2),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  origin VARCHAR(8) NOT NULL DEFAULT 'core' CHECK (origin IN ('core','mock')),
  sync_run_id BIGINT REFERENCES sync_runs(id),
  synced_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  -- Một số của agent mà không nói model nào thì không tái lập được.
  CHECK (detector <> 'agent' OR agent_model IS NOT NULL),
  UNIQUE (manifest_id, scorer_version, detector, code)
);
CREATE INDEX ON defect_scores (manifest_id, detector, code);
