-- View cho FE (DESIGN.md §4.6).
--
-- Ba quy tắc lọc chung, áp cho mọi view:
--   1. Lọc `is_deleted = FALSE` trên bốn bảng có cột đó, và ẩn bản ghi con
--      của bản ghi cha đã xoá mềm.
--   2. View liên quan eval mang cột `is_sealed`; API bỏ dòng niêm phong với
--      mọi vai trừ ADMIN (BR-10).
--   3. Bản `*_agent` là bản đã lọc cứng dòng niêm phong và không join nhóm S;
--      role agent_ro chỉ đọc bản đó.
--
-- Không view nào hiện số 0 thay cho "chưa chạy": FE phân biệt bằng NULL và
-- `EmptyState` (§6.4, BR-12).

-- ---------------------------------------------------------------------------
-- v_pipeline_current · stepper 6 tầng (M2)
-- ---------------------------------------------------------------------------
CREATE VIEW v_pipeline_current AS
SELECT
  d.id                AS dataset_id,
  d.dataset_code,
  sd.stage_number,
  sd.code             AS stage_code,
  sd.display_name     AS stage_name,
  sd.is_gate,
  r.id                AS stage_run_id,
  r.attempt_no,
  r.status,
  -- Hai nhãn cạnh nhau: cổng là code, agent chỉ diễn giải (§1 điểm 7).
  r.qa_code_decision,
  r.qa_agent_verdict,
  r.started_at,
  r.finished_at,
  r.log_uri,
  r.origin
FROM datasets d
CROSS JOIN pipeline_stage_defs sd
LEFT JOIN pipeline_stage_runs r
       ON r.dataset_id = d.id
      AND r.stage_number = sd.stage_number
      AND r.is_current
WHERE NOT d.is_deleted;

-- ---------------------------------------------------------------------------
-- v_dataset_report · báo cáo dataset (M2)
-- ---------------------------------------------------------------------------
-- Trạng thái QA của một episode là dòng qa_report mới nhất của nó, nên view
-- lấy dòng mới nhất bằng DISTINCT ON thay vì gộp mọi lần chấm.
CREATE VIEW v_dataset_report AS
WITH latest_qa AS (
  SELECT DISTINCT ON (episode_id)
         episode_id, decision, created_at
    FROM episode_qa_reports
   ORDER BY episode_id, created_at DESC
)
SELECT
  d.id                AS dataset_id,
  d.dataset_code,
  e.source_kind,
  e.synthetic_tier,
  count(*)                                             AS episode_count,
  count(*) FILTER (WHERE e.is_root AND e.operator_kind = 'human') AS root_human_count,
  count(*) FILTER (WHERE q.decision = 'pass')          AS qa_pass,
  count(*) FILTER (WHERE q.decision = 'flag')          AS qa_flag,
  count(*) FILTER (WHERE q.decision = 'quarantine')    AS qa_quarantine,
  count(*) FILTER (WHERE q.decision = 'reject')        AS qa_reject,
  -- Episode chưa ai chấm là một con số riêng, không gộp vào `pass`.
  count(*) FILTER (WHERE q.decision IS NULL)           AS qa_not_run,
  count(*) FILTER (WHERE e.deid_status = 'raw' AND e.source_kind = 'egocentric')
                                                       AS egocentric_raw,
  avg(e.duration_s)                                    AS mean_duration_s,
  d.origin
FROM datasets d
JOIN episodes e ON e.dataset_id = d.id
LEFT JOIN latest_qa q ON q.episode_id = e.id
WHERE NOT d.is_deleted
GROUP BY d.id, d.dataset_code, e.source_kind, e.synthetic_tier, d.origin;

-- ---------------------------------------------------------------------------
-- v_defect_detection · bảng điểm lỗi cấy (M3)
-- ---------------------------------------------------------------------------
-- Hai cột `code` và `agent` cạnh nhau là lý do bảng defect_scores có cột
-- `detector`. Precision và recall tính ở đây, không ở FE, để M3 và báo cáo
-- không thể lệch công thức.
CREATE VIEW v_defect_detection AS
SELECT
  s.manifest_id,
  m.dataset_id,
  s.scorer_version,
  s.detector,
  s.agent_model,
  s.code,
  s.tp, s.fp, s.fn,
  CASE WHEN s.tp + s.fp > 0 THEN s.tp::numeric / (s.tp + s.fp) END AS precision,
  CASE WHEN s.tp + s.fn > 0 THEN s.tp::numeric / (s.tp + s.fn) END AS recall,
  s.false_alarm_rate,
  s.latency_s,
  s.created_at,
  s.origin
FROM defect_scores s
JOIN defect_manifests m ON m.id = s.manifest_id;

-- ---------------------------------------------------------------------------
-- v_eval_funnel · phễu theo bước (M6)
-- ---------------------------------------------------------------------------
-- Phễu có đúng số bước của task, lấy từ độ dài step_status, không ép về 3 pha.
CREATE VIEW v_eval_funnel AS
SELECT
  ev.id               AS evaluation_id,
  ev.task_id,
  ev.split,
  ev.level            AS eval_level,
  ev.renderer,
  ev.eval_mode,
  ee.level            AS episode_level,
  step.ordinality     AS step_no,
  count(*)                                                  AS reached_or_beyond,
  count(*) FILTER (WHERE step.status = 'pass')              AS step_pass,
  count(*) FILTER (WHERE step.status = 'fail')              AS step_fail,
  count(*) FILTER (WHERE step.status = 'not_attempted')     AS step_not_attempted,
  -- `unknown` là một cột riêng, không gộp vào `fail` hay `pass`: thiếu tín
  -- hiệu không phải là trượt (spec §5.1).
  count(*) FILTER (WHERE step.status = 'unknown')           AS step_unknown,
  ev.sealed_until > now() AS is_sealed,
  ev.origin
FROM sim_evaluations ev
JOIN eval_episodes ee ON ee.evaluation_id = ev.id
CROSS JOIN LATERAL unnest(ee.step_status) WITH ORDINALITY AS step(status, ordinality)
WHERE NOT ev.is_deleted
  AND ee.infra_status = 'ok'
GROUP BY ev.id, ev.task_id, ev.split, ev.level, ev.renderer, ev.eval_mode,
         ee.level, step.ordinality, ev.sealed_until, ev.origin;

-- ---------------------------------------------------------------------------
-- v_eval_summary · cờ sim cạnh scorer (M6)
-- ---------------------------------------------------------------------------
CREATE VIEW v_eval_summary AS
SELECT
  ev.id               AS evaluation_id,
  ev.task_id, ev.split, ev.level, ev.renderer, ev.eval_mode,
  ev.scorer_version,
  ev.total_episodes,
  ev.infra_failed_count,
  ev.success_count,
  -- Chỉ số chính là cờ simulator (ADR-14).
  ev.overall_sr       AS sim_success_rate,
  -- Kết luận scorer chỉ để đối chiếu. Lệch quá 5% nghĩa là scorer hỏng.
  CASE WHEN ev.total_episodes - ev.infra_failed_count > 0
       THEN count(*) FILTER (WHERE ee.scorer_success)::numeric
            / (ev.total_episodes - ev.infra_failed_count)
  END                 AS scorer_success_rate,
  CASE WHEN ev.total_episodes - ev.infra_failed_count > 0
       THEN abs(ev.overall_sr
                - count(*) FILTER (WHERE ee.scorer_success)::numeric
                  / (ev.total_episodes - ev.infra_failed_count))
  END                 AS sim_scorer_gap,
  ev.sealed_until > now() AS is_sealed,
  ev.origin
FROM sim_evaluations ev
LEFT JOIN eval_episodes ee
       ON ee.evaluation_id = ev.id AND ee.infra_status = 'ok'
WHERE NOT ev.is_deleted
GROUP BY ev.id, ev.task_id, ev.split, ev.level, ev.renderer, ev.eval_mode,
         ev.scorer_version, ev.total_episodes, ev.infra_failed_count,
         ev.success_count, ev.overall_sr, ev.sealed_until, ev.origin;

-- ---------------------------------------------------------------------------
-- v_system_check · kiểm hệ thống từng episode (M6, M7) · bản 0.3
-- ---------------------------------------------------------------------------
-- Mã đã nổ và mã không chấm được là **hai cột riêng**. Gộp chúng, hay bỏ cột
-- thứ hai, là cách web vẽ "không có lỗi hệ thống" cho một episode nobody
-- chấm được (BR-12).
CREATE VIEW v_system_check AS
SELECT
  sd.id,
  sd.eval_episode_id,
  ee.evaluation_id,
  ev.task_id,
  ee.episode_index,
  ee.level,
  sd.diagnosis,
  sd.config_sha256,
  sd.trace_sha256,
  sd.infra_status,
  -- Mã đã nổ, theo thứ tự của spec §6.4; nhãn là mã đầu tiên.
  (SELECT array_agg(f->>'code' ORDER BY f->>'code')
     FROM jsonb_array_elements(sd.findings) f)              AS fired_codes,
  (SELECT array_agg(s->>'code' ORDER BY s->>'code')
     FROM jsonb_array_elements(sd.skipped) s)               AS skipped_codes,
  jsonb_array_length(sd.findings)                           AS finding_count,
  jsonb_array_length(sd.skipped)                            AS skipped_count,
  sd.findings,
  sd.skipped,
  -- Số để hiện dù không mã nào nổ ngưỡng.
  sd.measurements,
  -- Episode chỉ dùng được làm bằng chứng về policy khi đã chấm hết và sạch.
  (sd.diagnosis = 'clean')                                  AS usable_as_policy_evidence,
  ev.sealed_until > now()                                   AS is_sealed,
  sd.created_at,
  sd.origin
FROM system_diagnoses sd
JOIN eval_episodes ee ON ee.id = sd.eval_episode_id
JOIN sim_evaluations ev ON ev.id = ee.evaluation_id
WHERE NOT ev.is_deleted;

-- ---------------------------------------------------------------------------
-- v_branch_comparison · tỉ lệ thành công cạnh chi phí (M1, M9)
-- ---------------------------------------------------------------------------
-- "Mới nhất" nghĩa là eval của checkpoint is_best, split = dev, chưa niêm
-- phong. Nhánh luôn đi kèm task_id.
CREATE VIEW v_branch_comparison AS
SELECT
  x.task_id,
  x.branch,
  x.method,
  x.experiment_id,
  x.evaluation_id,
  x.level,
  x.sim_success_rate,
  x.total_episodes,
  x.infra_failed_count,
  cost.measured_usd,
  cost.measured_human_minutes,
  cost.measured_gpu_hours,
  cost.estimated_usd,
  x.origin
FROM (
  SELECT DISTINCT ON (e.task_id, e.branch, e.method, ev.level)
         e.task_id, e.branch, e.method, e.id AS experiment_id,
         ev.id AS evaluation_id, ev.level, ev.overall_sr AS sim_success_rate,
         ev.total_episodes, ev.infra_failed_count, ev.origin
    FROM experiments e
    JOIN model_checkpoints c ON c.experiment_id = e.id AND c.is_best
    JOIN sim_evaluations ev ON ev.checkpoint_id = c.id
   WHERE NOT e.is_deleted
     AND NOT ev.is_deleted
     AND ev.split = 'dev'
     AND (ev.sealed_until IS NULL OR ev.sealed_until <= now())
   ORDER BY e.task_id, e.branch, e.method, ev.level, ev.finished_at DESC
) x
LEFT JOIN LATERAL (
  SELECT sum(l.measured_usd)            AS measured_usd,
         sum(l.measured_human_minutes)  AS measured_human_minutes,
         sum(l.measured_gpu_hours)      AS measured_gpu_hours,
         sum(l.estimated_usd)           AS estimated_usd
    FROM cost_ledger_entries l
   WHERE l.experiment_id = x.experiment_id
) cost ON TRUE;

-- ---------------------------------------------------------------------------
-- v_he_curve · đường cong HE (M9)
-- ---------------------------------------------------------------------------
CREATE VIEW v_he_curve AS
SELECT
  e.task_id,
  e.branch,
  e.hypothesis,
  -- Số demo robot của nhánh: đếm episode gốc do người làm, không nhập tay.
  (SELECT count(*)
     FROM experiment_datasets ed
     JOIN release_items ri ON ri.release_id = ed.release_id AND NOT ri.excluded
     JOIN episodes ep ON ep.id = ri.episode_id
    WHERE ed.experiment_id = e.id
      AND ep.is_root AND ep.operator_kind = 'human')         AS n_demos,
  e.train_seed,
  ev.level,
  ev.overall_sr        AS sim_success_rate,
  ev.total_episodes - ev.infra_failed_count                   AS n_scored,
  ev.sealed_until > now() AS is_sealed,
  ev.origin
FROM experiments e
JOIN model_checkpoints c ON c.experiment_id = e.id AND c.is_best
JOIN sim_evaluations ev ON ev.checkpoint_id = c.id
WHERE NOT e.is_deleted
  AND NOT ev.is_deleted
  AND e.hypothesis IN ('HE','HE_T');

-- ---------------------------------------------------------------------------
-- v_cluster_board · bảng cụm (M7)
-- ---------------------------------------------------------------------------
CREATE VIEW v_cluster_board AS
SELECT
  fc.id               AS cluster_id,
  fc.recommendation_id,
  fr.task_id,
  fc.failed_step,
  fc.failure_code,
  fc.level,
  fc.member_count,
  fc.diagnosis,
  fc.diagnosis_source,
  fc.override_reason,
  -- Ba màu chip của M7 lấy từ hai cờ này, không từ một chuỗi tên nhóm.
  fc.consumes_data_budget,
  (fc.diagnosis LIKE 'HE_THONG%')                            AS is_system_fault,
  fc.card_uri,
  fc.checks,
  (SELECT count(*) FROM diagnostic_runs dr WHERE dr.cluster_id = fc.id)
                                                             AS diagnostic_run_count,
  (SELECT coalesce(sum(dr.rollout_count), 0) FROM diagnostic_runs dr
    WHERE dr.cluster_id = fc.id)                             AS diagnostic_rollouts,
  -- Phép kiểm bỏ qua hiện riêng, không hiện là `failed` (§5.3).
  (SELECT count(*) FROM diagnostic_runs dr
    WHERE dr.cluster_id = fc.id AND dr.outcome = 'skipped')  AS skipped_checks,
  (SELECT count(*) FROM repair_tickets rt WHERE rt.cluster_id = fc.id)
                                                             AS repair_ticket_count,
  fc.origin
FROM failure_clusters fc
JOIN flywheel_recommendations fr ON fr.id = fc.recommendation_id;

-- ---------------------------------------------------------------------------
-- v_cost_by_branch và v_cost_by_intervention (M8)
-- ---------------------------------------------------------------------------
-- Ước tính và thực đo cạnh nhau, phút người và GPU-giờ tách riêng: ba trần
-- ngân sách là ba ràng buộc song song, nên không quy đổi về một con số.
CREATE VIEW v_cost_by_branch AS
SELECT
  l.branch,
  e.task_id,
  l.price_book_id,
  pb.name             AS price_book_name,
  count(*)                                     AS entry_count,
  sum(l.estimated_usd)                         AS estimated_usd,
  sum(l.measured_usd)                          AS measured_usd,
  sum(l.measured_usd) - sum(l.estimated_usd)   AS usd_forecast_error,
  sum(l.estimated_human_minutes)               AS estimated_human_minutes,
  sum(l.measured_human_minutes)                AS measured_human_minutes,
  sum(l.estimated_gpu_hours)                   AS estimated_gpu_hours,
  sum(l.measured_gpu_hours)                    AS measured_gpu_hours,
  count(*) FILTER (WHERE l.entry_kind = 'REVERSAL') AS reversal_count,
  l.origin
FROM cost_ledger_entries l
LEFT JOIN experiments e ON e.id = l.experiment_id
LEFT JOIN price_books pb ON pb.id = l.price_book_id
GROUP BY l.branch, e.task_id, l.price_book_id, pb.name, l.origin;

CREATE VIEW v_cost_by_intervention AS
SELECT
  iv.id               AS intervention_id,
  iv.intervention_ref,
  iv.kind,
  iv.cluster_id,
  iv.status,
  iv.target_quantity,
  iv.approved_quantity,
  -- Số đã thực hiện đếm từ episode, không nhập tay.
  (SELECT count(*) FROM episodes ep WHERE ep.intervention_id = iv.id) AS fulfilled_count,
  iv.expected_gain_pp,
  iv.estimated_usd,
  iv.estimated_human_minutes,
  iv.estimated_gpu_hours,
  cost.measured_usd,
  cost.measured_human_minutes,
  cost.measured_gpu_hours,
  iv.origin
FROM interventions iv
LEFT JOIN LATERAL (
  SELECT sum(measured_usd) AS measured_usd,
         sum(measured_human_minutes) AS measured_human_minutes,
         sum(measured_gpu_hours) AS measured_gpu_hours
    FROM cost_ledger_entries l WHERE l.intervention_id = iv.id
) cost ON TRUE;

-- ---------------------------------------------------------------------------
-- v_r_demo · số demo người theo nhánh (M8)
-- ---------------------------------------------------------------------------
CREATE VIEW v_r_demo AS
SELECT
  e.task_id,
  e.branch,
  e.method,
  count(DISTINCT ep.id) AS human_root_episodes,
  e.origin
FROM experiments e
JOIN experiment_datasets ed ON ed.experiment_id = e.id
JOIN release_items ri ON ri.release_id = ed.release_id AND NOT ri.excluded
JOIN episodes ep ON ep.id = ri.episode_id
WHERE NOT e.is_deleted
  AND ep.is_root
  AND ep.operator_kind = 'human'
GROUP BY e.task_id, e.branch, e.method, e.origin;

-- ---------------------------------------------------------------------------
-- v_fix_rate · tỉ lệ sửa được, hậu nghiệm Beta gộp lúc đọc (M7)
-- ---------------------------------------------------------------------------
CREATE VIEW v_fix_rate AS
SELECT
  intervention_kind,
  count(*)                                        AS event_count,
  sum(n_conditions)                               AS n_conditions,
  sum(fixed_count)                                AS fixed_count,
  -- prior Beta(1, 1)
  1 + sum(fixed_count)                            AS alpha,
  1 + sum(n_conditions) - sum(fixed_count)        AS beta,
  (1 + sum(fixed_count))::numeric
    / (2 + sum(n_conditions))                     AS mean_fix_rate
FROM fix_rate_events
GROUP BY intervention_kind;

-- ---------------------------------------------------------------------------
-- v_action_status · vòng đời hành động (mọi màn hình có nút)
-- ---------------------------------------------------------------------------
CREATE VIEW v_action_status AS
SELECT
  a.id                AS action_id,
  a.action_kind,
  a.target_kind,
  a.target_id,
  a.sync_status,
  a.reason,
  a.reject_reason,
  a.created_at,
  a.exported_at,
  a.applied_at,
  u.display_name      AS actor_name,
  u.role              AS actor_role,
  jr.id               AS job_request_id,
  jr.job_kind,
  jr.status           AS job_status,
  -- "Đang đồng bộ" quá 30 phút thì chuông báo lõi chưa xử lý (§5.5).
  (a.sync_status = 'EXPORTED' AND a.exported_at < now() - INTERVAL '30 minutes')
                      AS is_late,
  d.id                AS decision_id,
  d.conclusion        AS decision_conclusion
FROM human_actions a
JOIN app_users u ON u.id = a.actor_id
LEFT JOIN job_requests jr ON jr.action_id = a.id
LEFT JOIN decisions d ON d.source_action_id = a.id;

-- ---------------------------------------------------------------------------
-- v_sync_health · sức khoẻ bộ nạp (M1, M10)
-- ---------------------------------------------------------------------------
CREATE VIEW v_sync_health AS
SELECT
  direction,
  max(started_at)                                            AS last_started_at,
  max(finished_at)                                           AS last_finished_at,
  now() - max(coalesce(finished_at, started_at))              AS staleness,
  -- fwsync không chạy quá 15 phút thì chuông báo (§5.5).
  (now() - max(coalesce(finished_at, started_at)) > INTERVAL '15 minutes') AS is_late,
  (SELECT count(*) FROM sync_runs s2
    WHERE s2.direction = s.direction AND s2.status IN ('partial','failed')) AS bad_runs,
  (SELECT coalesce(sum(jsonb_array_length(s3.errors)), 0) FROM sync_runs s3
    WHERE s3.direction = s.direction)                        AS rejected_rows
FROM sync_runs s
GROUP BY direction;

-- ---------------------------------------------------------------------------
-- Bản *_agent · role agent_ro chỉ đọc những view này
-- ---------------------------------------------------------------------------
-- Lọc **cứng**, không dựa vào API: dòng niêm phong bị bỏ ở đây, nên một lỗi
-- trong lớp gọi model cũng không làm agent thấy holdout. Không view nào trong
-- nhóm này join nhóm S, nên agent không có đường nào tới đáp án lỗi cấy
-- (luật R8).
CREATE VIEW v_eval_summary_agent AS
SELECT evaluation_id, task_id, split, level, renderer, eval_mode, scorer_version,
       total_episodes, infra_failed_count, success_count, sim_success_rate,
       scorer_success_rate, sim_scorer_gap, origin
FROM v_eval_summary
WHERE NOT is_sealed;

CREATE VIEW v_eval_funnel_agent AS
SELECT evaluation_id, task_id, split, eval_level, renderer, eval_mode,
       episode_level, step_no, reached_or_beyond, step_pass, step_fail,
       step_not_attempted, step_unknown, origin
FROM v_eval_funnel
WHERE NOT is_sealed;

CREATE VIEW v_system_check_agent AS
SELECT id, eval_episode_id, evaluation_id, task_id, episode_index, level,
       diagnosis, fired_codes, skipped_codes, finding_count, skipped_count,
       measurements, usable_as_policy_evidence, created_at, origin
FROM v_system_check
WHERE NOT is_sealed;

CREATE VIEW v_cluster_board_agent AS
SELECT * FROM v_cluster_board;

-- Lô có lỗi cấy bị bỏ khỏi bản của agent: đọc được danh sách episode của bản
-- sao là một nửa đáp án, kể cả khi mã lỗi nằm trong nhóm S.
CREATE VIEW v_dataset_report_agent AS
SELECT r.*
FROM v_dataset_report r
JOIN datasets d ON d.id = r.dataset_id
WHERE NOT d.has_seeded_faults;
