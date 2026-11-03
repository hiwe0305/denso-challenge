-- Quyền của ba role (DESIGN.md §2, luật R1, R4, R8).
--
-- Đây là nơi ba luật được cưỡng chế, không phải trong code API:
--
--   R1  fw_api chỉ SELECT trên bảng nhóm P. Không có endpoint nào ghi bảng
--       chiếu, vì role của API không có quyền. Một PR thêm endpoint như thế
--       sẽ chết lúc chạy, không lúc review.
--   R4  Sổ chi phí chỉ được thêm. Trigger một mình không đủ vì chủ bảng tắt
--       được trigger, nên UPDATE và DELETE bị REVOKE khỏi **cả hai** role.
--   R8  agent_ro không có đường nào tới nhóm S, và chỉ đọc các view *_agent.
--
-- Chạy sau 70-views.sql, vì GRANT cần view đã tồn tại.

-- ---------------------------------------------------------------------------
-- fw_api · API
-- ---------------------------------------------------------------------------
GRANT USAGE ON SCHEMA public TO fw_api;

-- Nhóm W: ghi được, trừ những chỗ append-only.
GRANT SELECT, INSERT, UPDATE ON
  app_users, dataset_intakes, experiment_drafts, job_requests,
  agent_chat_sessions, agent_chat_messages, notifications, jobs
TO fw_api;

-- human_actions là append-only với API: nội dung một hành động không bao giờ
-- sửa được sau khi ghi. Năm cột trạng thái đồng bộ thuộc fw_sync.
GRANT SELECT, INSERT ON human_actions TO fw_api;
REVOKE UPDATE, DELETE ON human_actions FROM fw_api;

GRANT USAGE, SELECT ON SEQUENCE
  notifications_id_seq, agent_chat_messages_id_seq, jobs_id_seq
TO fw_api;

-- Nhóm P: chỉ đọc. Đây là luật R1, và nó đúng với mọi bảng P không trừ bảng
-- nào.
DO $$
DECLARE
  p_table TEXT;
BEGIN
  FOR p_table IN
    SELECT c.relname FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'public' AND c.relkind = 'r'
      AND EXISTS (SELECT 1 FROM pg_attribute a
                   WHERE a.attrelid = c.oid AND a.attname = 'sync_run_id'
                     AND NOT a.attisdropped)
  LOOP
    EXECUTE format('GRANT SELECT ON %I TO fw_api', p_table);
    EXECUTE format('REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON %I FROM fw_api', p_table);
  END LOOP;
END
$$;

-- sync_runs: API đọc để hiện v_sync_health, không ghi.
GRANT SELECT ON sync_runs TO fw_api;

-- Nhóm S: API đọc được `defect_scores` để dựng bảng điểm M3, nhưng **không**
-- đọc đáp án. Đáp án chỉ bộ chấm của lõi đọc (CLAUDE.md, bất biến kiến trúc).
GRANT SELECT ON defect_scores TO fw_api;
REVOKE ALL ON defect_manifests, defect_items FROM fw_api;

-- View: API đọc hết, kể cả bản có cột is_sealed. Lọc theo vai làm ở tầng API
-- (BR-10), vì ADMIN phải xem được.
GRANT SELECT ON
  v_pipeline_current, v_dataset_report, v_defect_detection, v_eval_funnel,
  v_eval_summary, v_system_check, v_branch_comparison, v_he_curve,
  v_cluster_board, v_cost_by_branch, v_cost_by_intervention, v_r_demo,
  v_fix_rate, v_action_status, v_sync_health, failure_records
TO fw_api;

-- ---------------------------------------------------------------------------
-- fw_sync · bộ nạp
-- ---------------------------------------------------------------------------
GRANT USAGE ON SCHEMA public TO fw_sync;

-- Nhóm P và S: role duy nhất được ghi.
DO $$
DECLARE
  p_table TEXT;
BEGIN
  FOR p_table IN
    SELECT c.relname FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'public' AND c.relkind = 'r'
      AND EXISTS (SELECT 1 FROM pg_attribute a
                   WHERE a.attrelid = c.oid AND a.attname = 'sync_run_id'
                     AND NOT a.attisdropped)
  LOOP
    EXECUTE format('GRANT SELECT, INSERT, UPDATE ON %I TO fw_sync', p_table);
  END LOOP;
END
$$;

GRANT SELECT, INSERT, UPDATE ON sync_runs TO fw_sync;
GRANT USAGE, SELECT ON SEQUENCE sync_runs_id_seq, training_metrics_id_seq TO fw_sync;

-- R4: sổ chi phí chỉ được thêm, kể cả với bộ nạp. Sửa sai bằng bút toán đảo.
-- Hai bảng append-only khác cùng luật.
REVOKE UPDATE, DELETE ON cost_ledger_entries FROM fw_sync;
REVOKE UPDATE, DELETE ON episode_qa_reports FROM fw_sync;
REVOKE UPDATE, DELETE ON defect_scores FROM fw_sync;

-- Năm cột trạng thái của human_actions: quyền theo cột, nên bộ nạp không sửa
-- được nội dung một hành động, chỉ đánh dấu nó đã đi tới đâu.
GRANT SELECT ON human_actions TO fw_sync;
GRANT UPDATE (sync_status, exported_at, artifact_uri, applied_at, reject_reason)
  ON human_actions TO fw_sync;

-- Ba cột kết quả trên hai bảng nháp, cùng lý do.
GRANT SELECT ON dataset_intakes, experiment_drafts TO fw_sync;
GRANT UPDATE (status, dataset_id, reject_reason) ON dataset_intakes TO fw_sync;
GRANT UPDATE (status, experiment_id, reject_reason) ON experiment_drafts TO fw_sync;

-- Bộ nạp cập nhật trạng thái job từ artifact JobStatus của lõi (W7), và bắn
-- chuông khi một tầng dừng hoặc train xong.
GRANT SELECT, UPDATE (status, picked_by, result_ref, updated_at)
  ON job_requests TO fw_sync;
GRANT SELECT, INSERT ON notifications TO fw_sync;
GRANT USAGE, SELECT ON SEQUENCE notifications_id_seq TO fw_sync;

-- ---------------------------------------------------------------------------
-- agent_ro · connection pool dựng prompt cho agent chat
-- ---------------------------------------------------------------------------
GRANT USAGE ON SCHEMA public TO agent_ro;

-- Mặc định là không có gì. Chỉ các view *_agent được mở, và chúng đã lọc cứng
-- dòng niêm phong (BR-10) và không join nhóm S (R8).
GRANT SELECT ON
  v_eval_summary_agent, v_eval_funnel_agent, v_system_check_agent,
  v_cluster_board_agent, v_dataset_report_agent
TO agent_ro;

-- Nói rõ ràng điều quan trọng nhất, dù mặc định đã là không có quyền: nếu
-- một PR sau này GRANT rộng tay cho agent_ro, ba dòng này vẫn chặn đáp án.
REVOKE ALL ON defect_manifests, defect_items FROM agent_ro;
REVOKE ALL ON episodes FROM agent_ro;
REVOKE ALL ON sim_evaluations, eval_episodes FROM agent_ro;

-- Không role nào được dùng quyền mặc định của PUBLIC để lách.
ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM PUBLIC;
