-- Nhóm S · đáp án lỗi cấy, cách ly khỏi agent (DESIGN.md §4.4c, luật R8).
--
-- Bốn bảng này là đáp án của bộ chấm Agent QA/QC và kết quả chấm. Chúng
-- đứng riêng một nhóm vì **một lý do duy nhất**: role agent_ro không được đọc
-- chúng. Nếu agent đọc được đáp án thì mọi số precision và recall ở M3 vô
-- nghĩa; kết quả chấm cũng vậy, vì nhãn từng phát hiện suy ra từ đáp án.
--
-- Bản 0.3 nhắc lại: bảng `episodes` không còn cột `injected_defect`, nên
-- cách ly ở đây mới thật sự có hiệu lực. Ở bản 0.2 thì không: agent_ro đọc
-- được `episodes` qua view và thấy đáp án ngay trên episode.

CREATE TABLE defect_manifests (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  -- = DefectManifest.dataset_id: mã bản sao chấm, cũng là giá trị mà
  -- `episodes.benchmark_copy_id` mang khi #62 merge.
  manifest_ref VARCHAR(64) NOT NULL UNIQUE,
  -- Lô của bản sao dữ liệu. NULL với bản sao log train (DA-27 inject-logs):
  -- nó là một thư mục log, không phải lô nào của web (bản 0.6).
  dataset_id UUID REFERENCES datasets(id),
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

-- Kết quả chấm của DA-31 (`bench_result.json`, dạng `da31-2`), append-only.
--
-- Bản 0.6: bảng cũ (tp, fp, fn theo mã, mỗi detector một dòng) không khớp
-- thứ bộ chấm thật ghi ra. DA-31 tính recall **theo loại** lỗi (một mã D3
-- có thể là hai loại khác nhau), precision **theo mã** báo, báo nhầm trên bản
-- sạch theo **đơn vị** và chỉ là **cận trên**, và tách phần lỗi agent bắt
-- thêm so với code. Gộp về tp/fp/fn thì mất cả bốn. Nay mỗi số là một dòng
-- `hit`/`total`, đúng `{hit, total, value}` của file, và view tính `value`.
--
-- Một lần chấm = một file = một `result_sha256` (sha256 của đúng chuỗi JSON,
-- như `bench_result.sha256` bên cạnh). Chấm lại là file khác, hash khác, dòng
-- khác: không ghi đè số đã báo.

-- Một nhóm (`data`, `logs`) của một lần chấm: phần không phải tỉ lệ.
CREATE TABLE defect_bench_groups (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  result_sha256 CHAR(64) NOT NULL,
  bench_version VARCHAR(16) NOT NULL,
  -- `measured_on` và `false_alarm_on_clean` của file: hai câu M3 phải in
  -- nguyên văn, vì số trên lỗi cấy không phải tỉ lệ trên lỗi tự nhiên.
  measured_on TEXT NOT NULL,
  false_alarm_note TEXT NOT NULL,
  group_name VARCHAR(16) NOT NULL,
  -- Mã hai bản sao. Bản có lỗi bằng `defect_manifests.manifest_ref` của đáp
  -- án nó, nhưng không là khoá ngoại: đáp án nằm ở chỗ niêm phong của lõi và
  -- web có thể không bao giờ được nạp nó, mà bảng điểm vẫn phải hiện được.
  injected_copy VARCHAR(64) NOT NULL,
  clean_copy VARCHAR(64) NOT NULL,
  defects INTEGER NOT NULL CHECK (defects >= 0),
  -- [{kind, code, injected, by_code, agent_adds, together, agent_alone}]
  split JSONB NOT NULL,
  -- Theo lớp: {code: {...}, agent: {...}}. Giây tới báo cáo theo bản sao
  -- (null = không đo được), cặp (target, code) báo trên bản sạch, lỗi tự
  -- nhiên, target không gắn đơn vị nào, dòng không mã.
  seconds_to_report JSONB NOT NULL,
  clean_reports JSONB NOT NULL,
  natural JSONB NOT NULL,
  not_a_unit JSONB NOT NULL,
  uncoded JSONB NOT NULL,
  -- Chất lượng báo cáo của agent: thứ hạng đúng / số cặp, quyết định của kỹ
  -- sư theo nhãn, và từng phát hiện kèm nhãn so với đáp án.
  agent_ranking_hit INTEGER NOT NULL CHECK (agent_ranking_hit >= 0),
  agent_ranking_total INTEGER NOT NULL CHECK (agent_ranking_total >= agent_ranking_hit),
  agent_reviews JSONB NOT NULL,
  agent_findings JSONB NOT NULL,
  manifest_sha256 JSONB NOT NULL,
  inputs JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL,
  origin VARCHAR(8) NOT NULL DEFAULT 'core' CHECK (origin IN ('core','mock')),
  sync_run_id BIGINT REFERENCES sync_runs(id),
  synced_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (result_sha256, group_name)
);

-- Mỗi tỉ lệ của một lớp trong một nhóm là một dòng.
CREATE TABLE defect_scores (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  result_sha256 CHAR(64) NOT NULL,
  group_name VARCHAR(16) NOT NULL,
  -- Cột này là thứ cho phép M3 nói "code bắt 6/10, agent bắt thêm 2". Gộp
  -- hai lớp vào một dòng thì mất câu đó.
  layer VARCHAR(8) NOT NULL CHECK (layer IN ('code','agent')),
  metric VARCHAR(16) NOT NULL CHECK (metric IN (
    'recall','recall_unmasked','precision','false_alarm')),
  -- Loại lỗi với recall, mã với precision, '*' với báo nhầm (một số mỗi lớp).
  subject VARCHAR(64) NOT NULL,
  hit INTEGER NOT NULL CHECK (hit >= 0),
  total INTEGER NOT NULL CHECK (total >= hit),
  -- Số lỗi của loại bị lỗi tự nhiên che (chỉ dòng recall).
  masked INTEGER CHECK (masked >= 0),
  -- 'upper' với báo nhầm: bản sạch vẫn mang lỗi tự nhiên của dữ liệu thật.
  bound VARCHAR(8) CHECK (bound IN ('upper')),
  created_at TIMESTAMPTZ NOT NULL,
  origin VARCHAR(8) NOT NULL DEFAULT 'core' CHECK (origin IN ('core','mock')),
  sync_run_id BIGINT REFERENCES sync_runs(id),
  synced_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  FOREIGN KEY (result_sha256, group_name)
    REFERENCES defect_bench_groups (result_sha256, group_name),
  CHECK ((metric = 'recall') = (masked IS NOT NULL)),
  CHECK ((metric = 'false_alarm') = (bound IS NOT NULL)),
  CHECK (metric <> 'false_alarm' OR subject = '*'),
  UNIQUE (result_sha256, group_name, layer, metric, subject)
);
CREATE INDEX ON defect_scores (result_sha256, group_name, layer, metric);
