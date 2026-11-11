-- Ba bảng không phụ thuộc bảng nào khác (DESIGN.md §4.4a).
--
-- `app_users` và `sync_runs` đứng đầu vì gần như mọi bảng khác trỏ về chúng:
-- bảng W trỏ `actor_id`, mọi bảng P trỏ `sync_run_id`. `jobs` là hạ tầng của
-- hàng đợi web, không tính trong 40 bảng nghiệp vụ (§3.1).

-- ---------------------------------------------------------------------------
-- app_users · nhóm W
-- ---------------------------------------------------------------------------
CREATE TABLE app_users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email VARCHAR(255) NOT NULL UNIQUE,
  display_name VARCHAR(128) NOT NULL,
  -- Năm vai của DESIGN.md Phụ lục A.2. Không phân quyền chi tiết hơn (§1.1
  -- "ngoài phạm vi"), nên vai là một cột chứ không phải một bảng quan hệ.
  role VARCHAR(16) NOT NULL CHECK (role IN (
    'DATA_ENGINEER','ML_ENGINEER','LEAD','JUDGE_VIEWER','ADMIN')),
  -- Mã giả danh dùng trong sổ chi phí. Sổ không bao giờ lưu tên người
  -- (§4.4b), nên ánh xạ sang tên chỉ tồn tại ở đây.
  operator_code VARCHAR(16) UNIQUE,
  password_hash TEXT,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- sync_runs · nhóm W, nhưng do fw_sync ghi
-- ---------------------------------------------------------------------------
CREATE TABLE sync_runs (
  id BIGSERIAL PRIMARY KEY,
  direction VARCHAR(8) NOT NULL CHECK (direction IN ('import','export','verify')),
  source_dir TEXT NOT NULL,
  started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  finished_at TIMESTAMPTZ,
  -- {bảng: {inserted, updated, unchanged, rejected}}; unchanged = dòng append-only đã có, bỏ qua không sửa
  counts JSONB NOT NULL DEFAULT '{}',
  -- [{bảng, ref, code, message}]. Một dòng artifact vi phạm bị từ chối và ghi
  -- vào đây; bộ nạp chạy tiếp các dòng khác (§2, lưới an toàn).
  errors JSONB NOT NULL DEFAULT '[]',
  status VARCHAR(8) NOT NULL DEFAULT 'running'
    CHECK (status IN ('running','ok','partial','failed')),
  CHECK (status = 'running' OR finished_at IS NOT NULL),
  -- Một lần chạy có lỗi mà vẫn báo `ok` là cách che mất dòng bị từ chối.
  CHECK (status <> 'ok' OR jsonb_array_length(errors) = 0),
  CHECK (status <> 'partial' OR jsonb_array_length(errors) > 0)
);
CREATE INDEX ON sync_runs (direction, started_at DESC);

-- ---------------------------------------------------------------------------
-- jobs · hạ tầng hàng đợi của web
-- ---------------------------------------------------------------------------
-- Không phải `job_requests`. `jobs` là việc web tự chạy (fwsync, dựng lại
-- view); `job_requests` là việc người có máy chạy bằng lõi.
CREATE TABLE jobs (
  id BIGSERIAL PRIMARY KEY,
  kind VARCHAR(24) NOT NULL CHECK (kind IN ('SYNC_IMPORT','SYNC_EXPORT','SYNC_VERIFY')),
  payload JSONB NOT NULL DEFAULT '{}',
  status VARCHAR(12) NOT NULL DEFAULT 'queued'
    CHECK (status IN ('queued','running','done','failed')),
  attempts SMALLINT NOT NULL DEFAULT 0,
  last_error TEXT,
  requested_by UUID REFERENCES app_users(id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ON jobs (status, created_at) WHERE status IN ('queued','running');
