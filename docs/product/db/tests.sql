-- Scenario tests for schema.sql. Run on an empty database after schema.sql:
--   psql -v ON_ERROR_STOP=1 -f schema.sql -f tests.sql
-- Each block walks one flow of docs/product/09-data-flows.md and checks that invariant
-- violations are rejected. Any failed assertion stops the script with a non-zero exit code.

\set ON_ERROR_STOP on
\o /dev/null
SET client_min_messages = warning;

CREATE SCHEMA t;
CREATE TABLE t.ctx (k text PRIMARY KEY, v text NOT NULL);

CREATE FUNCTION t.v(p text) RETURNS text LANGUAGE sql AS $$ SELECT v FROM t.ctx WHERE k = p $$;
CREATE FUNCTION t.u(p text) RETURNS uuid LANGUAGE sql AS $$ SELECT v::uuid FROM t.ctx WHERE k = p $$;
CREATE FUNCTION t.put(p text, val text) RETURNS text LANGUAGE sql AS $$
    INSERT INTO t.ctx VALUES (p, val) ON CONFLICT (k) DO UPDATE SET v = EXCLUDED.v RETURNING v $$;
CREATE FUNCTION t.ulid(n int) RETURNS text LANGUAGE sql IMMUTABLE AS $$ SELECT '01JC' || lpad(n::text, 22, '0') $$;
CREATE FUNCTION t.sha(x text) RETURNS text LANGUAGE sql IMMUTABLE AS $$ SELECT md5(x) || md5(x || '#') $$;
CREATE FUNCTION t.h16(x text) RETURNS text LANGUAGE sql IMMUTABLE AS $$ SELECT left(md5(x), 16) $$;

CREATE FUNCTION t.expect_error(p_sql text, p_pattern text) RETURNS void
LANGUAGE plpgsql AS $$
BEGIN
    BEGIN
        EXECUTE p_sql;
    EXCEPTION WHEN others THEN
        IF SQLERRM !~* p_pattern THEN
            RAISE EXCEPTION 'expected error /%/, got: %', p_pattern, SQLERRM;
        END IF;
        RETURN;
    END;
    RAISE EXCEPTION 'expected error /%/ but statement succeeded: %', p_pattern, p_sql;
END $$;

CREATE FUNCTION t.cfg(p_kind text, p_name text) RETURNS text
LANGUAGE sql AS $$
    INSERT INTO fw.config_artifact (id, kind, name, version, sha256, repo_path, body)
    VALUES ('cfg_' || left(t.sha(p_kind || p_name), 16), p_kind, p_name, '1', t.sha(p_kind || p_name),
            'configs/' || p_kind || '/' || p_name || '.yaml', '{}')
    RETURNING id $$;

CREATE FUNCTION t.cur_stage(p_batch uuid, p_stage int) RETURNS uuid
LANGUAGE sql AS $$ SELECT id FROM fw.stage_run WHERE batch_id = p_batch AND stage_no = p_stage AND is_current $$;

CREATE FUNCTION t.agent(p_stage_run uuid, p_verdict text) RETURNS uuid
LANGUAGE sql AS $$
    INSERT INTO fw.agent_report (subject_kind, subject_id, model, model_revision, prompt_cfg_id, verdict, summary)
    VALUES ('stage_run', p_stage_run::text, 'nemotron-3.5-bolt-e4b-q4', 'rev1', t.v('cfg_prompt'), p_verdict, 'test')
    RETURNING id $$;

CREATE FUNCTION t.pass_stage(p_batch uuid, p_stage int) RETURNS text
LANGUAGE plpgsql AS $$
DECLARE
    sr uuid := t.cur_stage(p_batch, p_stage);
BEGIN
    PERFORM fw.stage_start(sr, NULL);
    RETURN fw.stage_finish(sr, 'PASS', '{}', 'out/' || p_stage, 'log/' || p_stage, t.agent(sr, 'PASS'));
END $$;

CREATE FUNCTION t.batch(p_code text, p_kind text, p_detail text, p_tier text DEFAULT NULL,
                        p_injected_from uuid DEFAULT NULL) RETURNS uuid
LANGUAGE sql AS $$
    INSERT INTO fw.ingest_batch (code, name, task_id, source_kind, source_detail, synthetic_tier, source_id,
                                 injected_from_batch_id, data_class, raw_uri, created_by)
    VALUES (p_code, p_code, 'g1_locomotion_pick_between_tables', p_kind, p_detail, p_tier, t.v('src_psi_data'),
            p_injected_from, 'public', 'raw/' || p_code, t.u('user_data'))
    RETURNING id $$;

CREATE FUNCTION t.ep(n int, p_batch uuid, p_cond text, p_kind text DEFAULT 'teleop_demo',
                     p_source_kind text DEFAULT 'teleop', p_tier text DEFAULT NULL, p_defect jsonb DEFAULT NULL)
RETURNS text
LANGUAGE sql AS $$
    INSERT INTO fw.episode (id, kind, source_kind, synthetic_tier, action_quality, operator_kind, condition_id,
                            batch_id, created_by_stage_run_id, task_id, embodiment_id, data_class, license, split,
                            renderer, bundle_uri, n_frames, fps, injected_defect)
    VALUES ('ep_' || t.ulid(n), p_kind, p_source_kind, p_tier,
            CASE p_source_kind WHEN 'teleop' THEN 'measured' WHEN 'synthetic' THEN 'planned' ELSE 'retargeted' END,
            CASE p_source_kind WHEN 'synthetic' THEN 'machine' ELSE 'human' END,
            p_cond, p_batch, t.cur_stage(p_batch, 2), 'g1_locomotion_pick_between_tables',
            CASE p_source_kind WHEN 'egocentric' THEN 'human_ego@1' ELSE 'g1_sonic_dwbc@1' END,
            'public', 'unknown', 'train', CASE WHEN p_source_kind = 'egocentric' THEN NULL ELSE 'mujoco' END,
            'episodes/' || n, 300, 30, p_defect)
    RETURNING id $$;

CREATE FUNCTION t.qa(p_ep text, p_decision text, p_reviewed uuid DEFAULT NULL) RETURNS text
LANGUAGE sql AS $$
    INSERT INTO fw.qa_report (id, episode_id, stage_run_id, thresholds_cfg_id, decision, reasons, checks, reviewed_by)
    SELECT fw.new_id('qa'), e.id, t.cur_stage(e.batch_id, 4), t.v('cfg_thr'), p_decision,
           CASE WHEN p_decision = 'pass' THEN '{}'::text[] ELSE ARRAY['test reason'] END, '{}', p_reviewed
    FROM fw.episode e WHERE e.id = p_ep
    RETURNING id $$;

CREATE FUNCTION t.cond(n int, p_split text, p_level int DEFAULT 0, p_layout text DEFAULT NULL) RETURNS text
LANGUAGE sql AS $$
    INSERT INTO fw.condition (id, task_id, condition_seed, level, "values", layout_hash, split, origin)
    VALUES ('cond_' || t.h16('c' || n), 'g1_locomotion_pick_between_tables', n, p_level,
            jsonb_build_object('obj_x', n * 0.01), coalesce(p_layout, 'layout' || n), p_split, 'generated')
    RETURNING id $$;

-- ===========================================================================
\echo '1. Reference data, users, configs, sources'
-- ===========================================================================
WITH x AS (INSERT INTO fw.app_user (username, display_name, role, person_code, can_run_gpu_jobs)
    VALUES ('hieu', 'Hiếu', 'LEAD', 'P01', true) RETURNING id) SELECT t.put('user_lead', id::text) FROM x;
WITH x AS (INSERT INTO fw.app_user (username, display_name, role, person_code)
    VALUES ('thong', 'Thông', 'DATA_ENGINEER', 'P02') RETURNING id) SELECT t.put('user_data', id::text) FROM x;

SELECT t.put('cfg_thr', t.cfg('thresholds', 'thr_v1'));
SELECT t.put('cfg_pb', t.cfg('pricebook', 'pb_v1'));
SELECT t.put('cfg_scorer', t.cfg('scorer', 'scorer_1_0'));
SELECT t.put('cfg_recipe', t.cfg('recipe', 'psi0_simple'));
SELECT t.put('cfg_prompt', t.cfg('agent_prompt', 'qa_v1'));
SELECT t.put('cfg_split', t.cfg('split_plan', 'spl_v1'));

INSERT INTO fw.price_rate (pricebook_cfg_id, resource_type, unit, usd_per_unit, human_hours_per_unit, note)
SELECT t.v('cfg_pb'), r, u, p, h, 'giả định cho test'
FROM (VALUES ('operator_hour', 'hour', 20, 1), ('gpu_hour_a100', 'gpu_hour', 2.5, 0),
             ('gpu_hour_3060', 'gpu_hour', 0.3, 0), ('intervention_sim_s1', 'rollout', 2, 0),
             ('intervention_teleop_correction', 'correction', 15, 0.5),
             ('intervention_recovery', 'segment', 10, 0.3)) v(r, u, p, h);

INSERT INTO fw.source (id, kind, uri, repo, revision, sha256, license, data_class, clean_for_main_task, downloaded_at)
VALUES ('src_' || t.h16('psi-data'), 'dataset', 'hf://USC-PSI-Lab/psi-data', 'USC-PSI-Lab/psi-data', 'abc',
        t.sha('psi-data'), 'unknown', 'public', 'unknown', now()),
       ('src_' || t.h16('psi-model-clean'), 'checkpoint', 'hf://USC-PSI-Lab/psi-model', 'USC-PSI-Lab/psi-model', 'abc',
        t.sha('psi-model-clean'), 'apache-2.0', 'public', 'true', now()),
       ('src_' || t.h16('psi-model-unknown'), 'checkpoint', 'hf://USC-PSI-Lab/psi-model', 'USC-PSI-Lab/psi-model', 'abc',
        t.sha('psi-model-unknown'), 'apache-2.0', 'public', 'unknown', now());
SELECT t.put('src_psi_data', 'src_' || t.h16('psi-data'));
SELECT t.put('src_clean', 'src_' || t.h16('psi-model-clean'));
SELECT t.put('src_unknown', 'src_' || t.h16('psi-model-unknown'));

SELECT t.put('cond_train_' || n, t.cond(n, 'train', n % 3)) FROM generate_series(1, 12) n;
SELECT t.put('cond_dev_' || n, t.cond(100 + n, 'dev', n % 3)) FROM generate_series(1, 6) n;

DO $$ BEGIN
    ASSERT fw.new_ulid() ~ '^[0-9A-HJKMNP-TV-Z]{26}$', 'new_ulid format';
    ASSERT (SELECT count(*) FROM fw.pipeline_stage_def) = 6, 'six pipeline stages';
    ASSERT (SELECT count(*) FROM fw.round_step_def) = 12, 'twelve algorithm steps';
END $$;

-- ===========================================================================
\echo '2. F1-F2: teleop batch through stages 1-4 with a review hop'
-- ===========================================================================
SELECT t.put('b_tel', t.batch('DS-TEL-PSI-001', 'teleop', 'psi_data')::text);

DO $$ BEGIN
    ASSERT (SELECT count(*) FROM fw.stage_run WHERE batch_id = t.u('b_tel')) = 4, 'four PENDING attempts';
    PERFORM t.expect_error(format('SELECT fw.stage_start(%L, NULL)', t.cur_stage(t.u('b_tel'), 2)),
                           'previous stage has not passed');
    ASSERT t.pass_stage(t.u('b_tel'), 1) = 'PASSED', 'stage 1 passes';
    PERFORM fw.stage_start(t.cur_stage(t.u('b_tel'), 2), NULL);
END $$;

SELECT t.put('ep_tel_' || n, t.ep(n, t.u('b_tel'), t.v('cond_train_' || n))) FROM generate_series(1, 5) n;

DO $$ BEGIN
    PERFORM t.expect_error(format($q$SELECT t.ep(90, %L, %L)$q$, t.u('b_tel'), t.v('cond_dev_1')),
                           'dev condition is forbidden');
    PERFORM t.cond(200, 'train', 0, 'layout101');   -- same layout as a dev condition
    PERFORM t.expect_error(format($q$SELECT t.ep(91, %L, %L)$q$, t.u('b_tel'), 'cond_' || t.h16('c200')),
                           'layout_hash equals a dev condition');
    PERFORM t.expect_error(format($q$SELECT t.ep(92, %L, %L, 'teleop_demo', 'synthetic', 'S1')$q$,
                                  t.u('b_tel'), t.v('cond_train_1')), 'must match batch');
    ASSERT (SELECT is_root FROM fw.episode WHERE id = t.v('ep_tel_1')), 'human teleop demo is a root';

    ASSERT fw.stage_finish(t.cur_stage(t.u('b_tel'), 2), 'PASS', '{}', 'o', 'l',
                           t.agent(t.cur_stage(t.u('b_tel'), 2), 'PASS')) = 'PASSED', 'stage 2 passes';
    ASSERT t.pass_stage(t.u('b_tel'), 3) = 'PASSED', 'stage 3 passes';

    PERFORM fw.stage_start(t.cur_stage(t.u('b_tel'), 4), NULL);
    PERFORM t.qa(t.v('ep_tel_1'), 'pass');
    PERFORM t.qa(t.v('ep_tel_2'), 'pass');
    PERFORM t.qa(t.v('ep_tel_3'), 'pass');
    PERFORM t.qa(t.v('ep_tel_4'), 'flag');
    PERFORM t.qa(t.v('ep_tel_5'), 'reject');
    -- the stage waits for the agent, then pauses because the code verdict is WARNING
    ASSERT fw.stage_finish(t.cur_stage(t.u('b_tel'), 4), 'WARNING', '{"reject": 1, "flag": 1}', 'o', 'l')
           = 'AGENT_REVIEWING', 'waits for the agent';
    ASSERT fw.stage_attach_agent_report(t.cur_stage(t.u('b_tel'), 4), t.agent(t.cur_stage(t.u('b_tel'), 4), 'PASS'))
           = 'PAUSED_FOR_REVIEW', 'code WARNING pauses even when the agent says PASS';
    ASSERT (SELECT status FROM fw.ingest_batch WHERE id = t.u('b_tel')) = 'PAUSED_FOR_REVIEW', 'batch paused';
    ASSERT EXISTS (SELECT 1 FROM fw.notification WHERE kind = 'STAGE_PAUSED'), 'pause notification';

    PERFORM t.expect_error(format($q$SELECT fw.stage_review(%L, 'FORCE_CONTINUE', %L, '  ')$q$,
                                  t.cur_stage(t.u('b_tel'), 4), t.u('user_data')), 'check constraint|stage_review');
    PERFORM fw.stage_review(t.cur_stage(t.u('b_tel'), 4), 'FORCE_CONTINUE', t.u('user_data'),
                            'One reject and one flag are expected on psi-data; flag reviewed in release step');
    ASSERT (SELECT status FROM fw.stage_run WHERE id = t.cur_stage(t.u('b_tel'), 4)) = 'OVERRIDDEN', 'overridden';
    ASSERT (SELECT status FROM fw.ingest_batch WHERE id = t.u('b_tel')) = 'READY_FOR_RELEASE', 'batch ready';
    ASSERT EXISTS (SELECT 1 FROM fw.decision WHERE kind = 'stage_review' AND verdict = 'overridden'), 'decision kept';

    PERFORM t.expect_error(format($q$UPDATE fw.stage_run SET stage_no = 3 WHERE id = %L$q$,
                                  t.cur_stage(t.u('b_tel'), 4)), 'only columns');
    PERFORM t.expect_error(format($q$UPDATE fw.stage_run SET status = 'PENDING' WHERE id = %L$q$,
                                  t.cur_stage(t.u('b_tel'), 4)), 'illegal status transition');
END $$;

-- ===========================================================================
\echo '3. F2: retry keeps history and old episodes; synthetic S1 batch'
-- ===========================================================================
SELECT t.put('b_retry', t.batch('DS-TEL-KB-001', 'teleop', 'teleop_keyboard')::text);
DO $$ BEGIN
    PERFORM t.pass_stage(t.u('b_retry'), 1);
    PERFORM fw.stage_start(t.cur_stage(t.u('b_retry'), 2), NULL);
    PERFORM t.put('ep_old', t.ep(30, t.u('b_retry'), t.v('cond_train_6')));
    PERFORM fw.stage_fail(t.cur_stage(t.u('b_retry'), 2), 'action_layout mismatch');
    ASSERT (SELECT status FROM fw.ingest_batch WHERE id = t.u('b_retry')) = 'FAILED', 'batch failed';
    PERFORM fw.stage_review(t.cur_stage(t.u('b_retry'), 2), 'APPLY_FIX_AND_RETRY', t.u('user_data'),
                            'remap wrist channels', '{"layout": "g1_pad36_v2"}');
    ASSERT (SELECT attempt_no FROM fw.stage_run WHERE id = t.cur_stage(t.u('b_retry'), 2)) = 2, 'attempt 2';
    ASSERT (SELECT params->>'layout' FROM fw.stage_run WHERE id = t.cur_stage(t.u('b_retry'), 2)) = 'g1_pad36_v2',
           'fix params carried';
    ASSERT (SELECT count(*) FROM fw.stage_run WHERE batch_id = t.u('b_retry')) = 7, '4 + 3 new attempts';
    ASSERT (SELECT count(*) FROM fw.stage_run WHERE batch_id = t.u('b_retry') AND status = 'SUPERSEDED') = 2,
           'pending attempts superseded';
    ASSERT NOT (SELECT is_current_in_batch FROM fw.v_episode_current WHERE id = t.v('ep_old')), 'old episode not current';
END $$;

SELECT t.put('b_syn', t.batch('DS-SYN-S1-001', 'synthetic', 'planner_wbc', 'S1')::text);
DO $$ BEGIN
    PERFORM t.pass_stage(t.u('b_syn'), 1);
    PERFORM fw.stage_start(t.cur_stage(t.u('b_syn'), 2), NULL);
    PERFORM t.put('ep_syn_' || n, t.ep(10 + n, t.u('b_syn'), t.v('cond_train_' || (6 + n)), 'sim_rollout', 'synthetic', 'S1'))
    FROM generate_series(1, 4) n;
    ASSERT NOT (SELECT is_root FROM fw.episode WHERE id = t.v('ep_syn_1')), 'synthetic is never a root';
    PERFORM fw.stage_finish(t.cur_stage(t.u('b_syn'), 2), 'PASS', '{}', 'o', 'l', t.agent(t.cur_stage(t.u('b_syn'), 2), 'PASS'));
    PERFORM t.pass_stage(t.u('b_syn'), 3);
    PERFORM fw.stage_start(t.cur_stage(t.u('b_syn'), 4), NULL);
    PERFORM t.qa(t.v('ep_syn_' || n), 'pass') FROM generate_series(1, 4) n;
    PERFORM fw.stage_finish(t.cur_stage(t.u('b_syn'), 4), 'PASS', '{}', 'o', 'l', t.agent(t.cur_stage(t.u('b_syn'), 4), 'PASS'));
    ASSERT (SELECT status FROM fw.ingest_batch WHERE id = t.u('b_syn')) = 'READY_FOR_RELEASE', 'synthetic ready';
END $$;

-- ===========================================================================
\echo '4. F9: injected-defect copy and sealed answer key'
-- ===========================================================================
SELECT t.put('b_inj', t.batch('DS-TEL-PSI-001-INJ', 'teleop', 'psi_data', NULL, t.u('b_tel'))::text);
DO $$ BEGIN
    PERFORM t.pass_stage(t.u('b_inj'), 1);
    PERFORM fw.stage_start(t.cur_stage(t.u('b_inj'), 2), NULL);
    PERFORM t.put('ep_inj', t.ep(40, t.u('b_inj'), t.v('cond_train_5'), 'teleop_demo', 'teleop', NULL,
                                 '{"code": "D2", "shift_frames": 3}'));
    ASSERT (SELECT is_injected_copy FROM fw.episode WHERE id = t.v('ep_inj')), 'flag derived from the batch';
END $$;

INSERT INTO fw_sealed.defect_manifest (injected_batch_id, sha256) VALUES (t.u('b_inj'), t.sha('answer-key'));
DO $$ BEGIN
    PERFORM fw.stage_finish(t.cur_stage(t.u('b_inj'), 2), 'PASS', '{}', 'o', 'l', t.agent(t.cur_stage(t.u('b_inj'), 2), 'PASS'));
    PERFORM t.pass_stage(t.u('b_inj'), 3);
    PERFORM fw.stage_start(t.cur_stage(t.u('b_inj'), 4), NULL);
    PERFORM t.qa(t.v('ep_inj'), 'pass');
END $$;

GRANT USAGE ON SCHEMA t TO fw_app;
GRANT SELECT ON t.ctx TO fw_app;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA t TO fw_app;
SET ROLE fw_app;
DO $$ BEGIN
    PERFORM t.expect_error('SELECT * FROM fw_sealed.defect_manifest', 'permission denied');
END $$;
RESET ROLE;

-- ===========================================================================
\echo '5. F3: egocentric de-identification gate'
-- ===========================================================================
SELECT t.put('b_ego', t.batch('DS-EGO-EGODEX-001', 'egocentric', 'egodex')::text);
DO $$ BEGIN
    PERFORM t.pass_stage(t.u('b_ego'), 1);
    PERFORM fw.stage_start(t.cur_stage(t.u('b_ego'), 2), NULL);
    PERFORM t.put('ep_ego', t.ep(50, t.u('b_ego'), NULL, 'ego_demo', 'egocentric'));
    ASSERT NOT (SELECT is_root FROM fw.episode WHERE id = t.v('ep_ego')), 'human video never counts as a robot demo';
    PERFORM t.expect_error(format($q$SELECT t.ep(51, %L, NULL, 'teleop_demo', 'egocentric')$q$, t.u('b_ego')),
                           'check constraint');
    PERFORM t.expect_error(format($q$INSERT INTO fw.episode_segment (episode_id, seq, t_start, t_end, step_id, text, label_source)
                                    VALUES (%L, 1, 0, 1, 1, 'reach', 'rule')$q$, t.v('ep_ego')), 'de-identified before annotation');
    INSERT INTO fw.episode_deid (episode_id, status, method) VALUES (t.v('ep_ego'), 'blurred', 'face_blur_v1');
    INSERT INTO fw.episode_segment (episode_id, seq, t_start, t_end, step_id, text, label_source)
    VALUES (t.v('ep_ego'), 1, 0, 1, 1, 'reach', 'rule');
    PERFORM t.expect_error(format($q$INSERT INTO fw.episode_deid (episode_id, status, method) VALUES (%L, 'blurred', 'x')$q$,
                                  t.v('ep_tel_1')), 'egocentric episodes only');
    PERFORM fw.stage_finish(t.cur_stage(t.u('b_ego'), 2), 'PASS', '{}', 'o', 'l', t.agent(t.cur_stage(t.u('b_ego'), 2), 'PASS'));
    PERFORM t.pass_stage(t.u('b_ego'), 3);
    PERFORM fw.stage_start(t.cur_stage(t.u('b_ego'), 4), NULL);
    PERFORM t.qa(t.v('ep_ego'), 'pass');
    PERFORM fw.stage_finish(t.cur_stage(t.u('b_ego'), 4), 'PASS', '{}', 'o', 'l', t.agent(t.cur_stage(t.u('b_ego'), 4), 'PASS'));
END $$;

-- ===========================================================================
\echo '6. F4: release freeze guard, child-free immutability, exports and MixSpec'
-- ===========================================================================
INSERT INTO fw.release (id, name, kind, task_id, split_plan_cfg_id, thresholds_cfg_id, created_by)
VALUES ('rel_' || t.h16('robot-1'), 'robot-1', 'robot', 'g1_locomotion_pick_between_tables', t.v('cfg_split'),
        t.v('cfg_thr'), t.u('user_lead'));
SELECT t.put('rel_robot', 'rel_' || t.h16('robot-1'));
INSERT INTO fw.release_item (release_id, episode_id)
SELECT t.v('rel_robot'), id FROM fw.episode
WHERE id IN (t.v('ep_tel_1'), t.v('ep_tel_2'), t.v('ep_tel_3'), t.v('ep_tel_4'), t.v('ep_inj'), t.v('ep_ego'), t.v('ep_old'))
   OR batch_id = t.u('b_syn');
INSERT INTO fw.release_item (release_id, episode_id, excluded, exclude_reason)
VALUES (t.v('rel_robot'), t.v('ep_tel_5'), true, 'QA reject: joint limit');

DO $$
DECLARE
    problems text;
BEGIN
    SELECT string_agg(problem, ' | ') INTO problems FROM fw.release_violations(t.v('rel_robot'));
    ASSERT problems ~ 'injected-defect copy', 'injected copy detected: ' || problems;
    ASSERT problems ~ 'current QA is flag', 'unreviewed flag detected';
    ASSERT problems ~ 'superseded', 'superseded episode detected';
    ASSERT problems ~ 'egocentric and robot', 'egocentric in robot release detected';
    ASSERT problems ~ 'current QA is missing', 'episode without QA detected';
    PERFORM t.expect_error(format($q$SELECT fw.release_freeze(%L, %L, %L, true)$q$,
                                  t.v('rel_robot'), t.sha('m'), t.u('user_lead')), 'cannot be frozen');

    DELETE FROM fw.release_item WHERE release_id = t.v('rel_robot') AND episode_id IN (t.v('ep_inj'), t.v('ep_ego'), t.v('ep_old'));
    PERFORM t.qa(t.v('ep_tel_4'), 'flag', t.u('user_data'));   -- engineer looked at the flag
    PERFORM t.expect_error(format($q$SELECT fw.release_freeze(%L, %L, %L, false)$q$,
                                  t.v('rel_robot'), t.sha('m'), t.u('user_lead')), 'holdout guard');
    PERFORM fw.release_freeze(t.v('rel_robot'), t.sha('m'), t.u('user_lead'), true);
    ASSERT (SELECT counts->>'human_roots' FROM fw.release WHERE id = t.v('rel_robot')) = '4', 'four human demos';
    ASSERT (SELECT counts->'by_source'->>'synthetic_s1' FROM fw.release WHERE id = t.v('rel_robot')) = '4', 'four S1';

    PERFORM t.expect_error(format($q$DELETE FROM fw.release_item WHERE release_id = %L$q$, t.v('rel_robot')), 'frozen');
    PERFORM t.expect_error(format($q$UPDATE fw.release SET name = 'x' WHERE id = %L$q$, t.v('rel_robot')), 'frozen');
    PERFORM t.expect_error(format($q$DELETE FROM fw.release WHERE id = %L$q$, t.v('rel_robot')), 'not allowed');

    PERFORM t.expect_error(format($q$INSERT INTO fw.dataset_export (release_id, format, mix_spec, mix_hash)
                                    VALUES (%L, 'lerobot_v2_1', '{"teleop": 0.5, "synthetic_s1": 0.4}', 'h1')$q$,
                                  t.v('rel_robot')), 'sum to 1');
    PERFORM t.expect_error(format($q$INSERT INTO fw.dataset_export (release_id, format, mix_spec, mix_hash)
                                    VALUES (%L, 'lerobot_v2_1', '{"teleop": 0.5, "synthetic_s2": 0.5}', 'h2')$q$,
                                  t.v('rel_robot')), 'has no episode');
    PERFORM t.expect_error(format($q$INSERT INTO fw.dataset_export (release_id, format, mix_spec, mix_hash)
                                    VALUES (%L, 'psi0_stage1', '{"teleop": 1}', 'h3')$q$,
                                  t.v('rel_robot')), 'does not fit');
END $$;

WITH x AS (INSERT INTO fw.dataset_export (release_id, format, mix_spec, mix_hash)
    VALUES (t.v('rel_robot'), 'lerobot_v2_1', '{"teleop": 0.5, "synthetic_s1": 0.5}', 'rho05') RETURNING id) SELECT t.put('exp_robot', id::text) FROM x;
DO $$ BEGIN
    UPDATE fw.dataset_export SET status = 'RUNNING' WHERE id = t.u('exp_robot');
    PERFORM t.expect_error(format($q$UPDATE fw.dataset_export SET status = 'READY', uri = 'x' WHERE id = %L$q$,
                                  t.u('exp_robot')), 'check constraint');
    UPDATE fw.dataset_export SET status = 'READY', uri = 'exports/robot-1/lerobot', contract_test_passed = true
    WHERE id = t.u('exp_robot');
END $$;

-- egocentric release: needs verified de-identification
INSERT INTO fw.release (id, name, kind, task_id, created_by)
VALUES ('rel_' || t.h16('ego-1'), 'ego-1', 'egocentric', 'g1_locomotion_pick_between_tables', t.u('user_lead'));
INSERT INTO fw.release_item (release_id, episode_id) VALUES ('rel_' || t.h16('ego-1'), t.v('ep_ego'));
DO $$ BEGIN
    ASSERT (SELECT string_agg(problem, ',') FROM fw.release_violations('rel_' || t.h16('ego-1'))) ~ 'not verified',
           'blurred is not enough for a release';
    INSERT INTO fw.episode_deid (episode_id, status, method, by_user) VALUES (t.v('ep_ego'), 'verified', 'manual', t.u('user_data'));
    PERFORM fw.release_freeze('rel_' || t.h16('ego-1'), t.sha('ego'), t.u('user_lead'), true);
END $$;
WITH x AS (INSERT INTO fw.dataset_export (release_id, format, mix_spec, mix_hash)
    VALUES ('rel_' || t.h16('ego-1'), 'psi0_stage1', '{"egocentric": 1}', 'ego') RETURNING id) SELECT t.put('exp_ego', id::text) FROM x;
UPDATE fw.dataset_export SET status = 'RUNNING' WHERE id = t.u('exp_ego');
UPDATE fw.dataset_export SET status = 'READY', uri = 'exports/ego-1', contract_test_passed = true WHERE id = t.u('exp_ego');

-- ===========================================================================
\echo '7. Run plans: freeze rules, Q0 clean checkpoint, immutability'
-- ===========================================================================
CREATE FUNCTION t.rp(p_name text, p_purpose text, p_src text, p_path text, p_dirty boolean) RETURNS text
LANGUAGE sql AS $$
    INSERT INTO fw.run_plan (id, name, purpose, task_id, embodiment_id, base_source_id, base_checkpoint_path,
                             recipe_cfg_id, scorer_cfg_id, pricebook_cfg_id, body, git_sha, git_dirty, image_digests,
                             created_by)
    VALUES ('rp_' || t.h16(p_name), p_name, p_purpose, 'g1_locomotion_pick_between_tables', 'g1_sonic_dwbc@1', p_src,
            p_path, t.v('cfg_recipe'), t.v('cfg_scorer'), t.v('cfg_pb'), '{}', repeat('a', 40), p_dirty,
            jsonb_build_object('psi0', 'ghcr.io/x/psi0@sha256:' || repeat('b', 64)), t.u('user_lead'))
    RETURNING id $$;

DO $$ BEGIN
    PERFORM t.expect_error(format('SELECT fw.run_plan_freeze(%L, %L, %L)',
        t.rp('dirty', 'he', t.v('src_clean'), 'psi0/pre.fast', true), t.sha('l'), t.u('user_lead')), 'clean git tree');
    PERFORM t.expect_error(format('SELECT fw.run_plan_freeze(%L, %L, %L)',
        t.rp('unclean', 'branch_train', t.v('src_unknown'), 'psi0/pre.fast', false), t.sha('l'), t.u('user_lead')),
        'not confirmed clean');
    PERFORM t.expect_error(format('SELECT fw.run_plan_freeze(%L, %L, %L)',
        t.rp('leaky', 'he', t.v('src_clean'), 'psi0/simple-checkpoints/teleop-v0', false), t.sha('l'), t.u('user_lead')),
        'g0_repro only');
    PERFORM fw.run_plan_freeze(t.rp('g0', 'g0_repro', t.v('src_unknown'), 'psi0/simple-checkpoints/teleop-v0', false),
                               t.sha('g0'), t.u('user_lead'));

    PERFORM t.put('rp_he', t.rp('he-1', 'he', t.v('src_clean'), 'psi0/pre.fast.1by1', false));
    INSERT INTO fw.run_plan_branch (run_plan_id, branch, method, seeds, release_id)
    VALUES (t.v('rp_he'), 'V_EGO', 'psi0', '{0}', t.v('rel_robot')),
           (t.v('rp_he'), 'V_NOEGO', 'psi0', '{0}', t.v('rel_robot'));
    INSERT INTO fw.run_plan_comparison VALUES (t.v('rp_he'), 'HE', 'V_EGO', 'V_NOEGO', 'psi0');
    PERFORM fw.run_plan_freeze(t.v('rp_he'), t.sha('he'), t.u('user_lead'));
    PERFORM t.expect_error(format($q$UPDATE fw.run_plan SET name = 'x' WHERE id = %L$q$, t.v('rp_he')), 'frozen');
    PERFORM t.expect_error(format($q$INSERT INTO fw.run_plan_branch (run_plan_id, branch, method, seeds)
                                    VALUES (%L, 'A', 'psi0', '{0}')$q$, t.v('rp_he')), 'frozen');
END $$;

-- ===========================================================================
\echo '8. F5: jobs, training, metrics, checkpoints'
-- ===========================================================================
DO $$
DECLARE
    new_id uuid;
BEGIN
    PERFORM t.expect_error(format($q$INSERT INTO fw.job (id, run_plan_id, kind, uses_gpu, requested_by)
                                    VALUES (%L, %L, 'train', true, %L)$q$,
                                  'job_' || t.ulid(1), t.v('rp_he'), t.u('user_data')), 'may not start GPU jobs');
    PERFORM t.expect_error(format($q$INSERT INTO fw.job (id, run_plan_id, kind, uses_gpu, requested_by)
                                    VALUES (%L, %L, 'train', true, %L)$q$,
                                  'job_' || t.ulid(2), 'rp_' || t.h16('dirty'), t.u('user_lead')), 'frozen run plan');
    INSERT INTO fw.job (id, run_plan_id, kind, uses_gpu, requested_by, machine)
    VALUES ('job_' || t.ulid(3), t.v('rp_he'), 'train', true, t.u('user_lead'), 'colab_a100');
    PERFORM t.expect_error(format($q$UPDATE fw.job SET status = 'succeeded' WHERE id = %L$q$, 'job_' || t.ulid(3)),
                           'illegal status transition');

    PERFORM t.expect_error(format($q$INSERT INTO fw.train_run (run_plan_id, branch, seed, stage, method, export_id)
                                    VALUES (%L, 'V_EGO', 0, 1, 'psi0', %L)$q$, t.v('rp_he'), t.u('exp_robot')),
                           'egocentric only feeds stage 1');
    PERFORM t.expect_error(format($q$INSERT INTO fw.train_run (run_plan_id, branch, seed, stage, method, export_id)
                                    VALUES (%L, 'V_EGO', 0, 3, 'psi0', %L)$q$, t.v('rp_he'), t.u('exp_ego')),
                           'egocentric only feeds stage 1');
    INSERT INTO fw.train_run (run_plan_id, branch, seed, stage, method, export_id, job_id)
    VALUES (t.v('rp_he'), 'V_EGO', 0, 3, 'psi0', t.u('exp_robot'), 'job_' || t.ulid(3)) RETURNING id INTO new_id;
    PERFORM t.put('tr_ego', new_id::text);
END $$;

INSERT INTO fw.train_metric (train_run_id, split, name, step, value)
SELECT t.u('tr_ego'), 'train', 'loss', s, 1.0 / (s + 1) FROM generate_series(0, 99) s;
INSERT INTO fw.train_metric (train_run_id, split, name, step, value)
SELECT t.u('tr_ego'), 'train', 'loss', s, 9 FROM generate_series(0, 99) s
ON CONFLICT DO NOTHING;   -- webhook resend is a no-op

INSERT INTO fw.checkpoint (id, origin, train_run_id, method, branch, seed, stage, step, release_id, weights_sha256, uri, is_final)
VALUES ('ckpt_' || t.h16('ego-final'), 'trained', t.u('tr_ego'), 'psi0', 'V_EGO', 0, 3, 3000, t.v('rel_robot'),
        t.sha('w1'), 'ckpt/ego/3000', true),
       ('ckpt_' || t.h16('ego-mid'), 'trained', t.u('tr_ego'), 'psi0', 'V_EGO', 0, 3, 1500, t.v('rel_robot'),
        t.sha('w2'), 'ckpt/ego/1500', false);
SELECT t.put('ckpt', 'ckpt_' || t.h16('ego-final'));

INSERT INTO fw.ledger_entry (id, activity, resource_type, quantity, unit, pricebook_cfg_id, usd_amount, measure_kind,
                             branch, run_plan_id, train_run_id, job_id)
VALUES (fw.new_id('led'), 'train', 'gpu_hour_a100', 6, 'gpu_hour', t.v('cfg_pb'), 15, 'measured', 'V_EGO',
        t.v('rp_he'), t.u('tr_ego'), 'job_' || t.ulid(3));
INSERT INTO fw.ledger_entry (id, activity, resource_type, quantity, unit, pricebook_cfg_id, usd_amount, human_hours,
                             measure_kind, batch_id)
VALUES (fw.new_id('led'), 'data_download', 'operator_hour', 2, 'hour', t.v('cfg_pb'), 40, 2, 'measured', t.u('b_tel')),
       (fw.new_id('led'), 'data_generation', 'gpu_hour_3060', 10, 'gpu_hour', t.v('cfg_pb'), 3, 0, 'measured', t.u('b_syn'));

DO $$ BEGIN
    ASSERT (SELECT count(*) FROM fw.train_metric WHERE train_run_id = t.u('tr_ego')) = 100, 'idempotent metrics';
    ASSERT (SELECT value FROM fw.train_metric WHERE train_run_id = t.u('tr_ego') AND step = 0) = 1, 'first write wins';
    PERFORM t.expect_error(format($q$UPDATE fw.checkpoint SET uri = 'x' WHERE id = %L$q$, t.v('ckpt')), 'only columns');
END $$;

-- ===========================================================================
\echo '9. F6: eval, infrastructure errors, scores, funnel'
-- ===========================================================================
INSERT INTO fw.condition_set (id, purpose, run_plan_id, sha256) VALUES ('cset_' || t.h16('dev'), 'dev_find', t.v('rp_he'), t.sha('dev'));
INSERT INTO fw.condition_set_member SELECT 'cset_' || t.h16('dev'), t.v('cond_dev_' || n) FROM generate_series(1, 6) n;
WITH x AS (INSERT INTO fw.eval_run (run_plan_id, purpose, checkpoint_id, condition_set_id, timing, sim_mode,
                                             renderer, scorer_cfg_id)
    VALUES (t.v('rp_he'), 'he_eval', t.v('ckpt'), 'cset_' || t.h16('dev'), 'sync', 'mujoco', 'mujoco', t.v('cfg_scorer'))
    RETURNING id) SELECT t.put('ev', id::text) FROM x;

CREATE FUNCTION t.trace(n int, p_cond text, p_success boolean, p_infra text DEFAULT 'ok') RETURNS text
LANGUAGE sql AS $$
    INSERT INTO fw.episode (id, kind, action_quality, operator_kind, condition_id, eval_run_id, checkpoint_id, rollout_seed,
                            replicate, sim_success, infra_status, task_id, embodiment_id, data_class, license, split,
                            renderer, bundle_uri, run_plan_id)
    VALUES ('ep_' || t.ulid(n), 'eval_rollout', 'measured', 'machine', p_cond, t.u('ev'), t.v('ckpt'), n, 0, p_success,
            p_infra, 'g1_locomotion_pick_between_tables', 'g1_sonic_dwbc@1', 'public', 'apache-2.0', 'dev', 'mujoco',
            'traces/' || n, t.v('rp_he'))
    RETURNING id $$;

CREATE FUNCTION t.score(p_ep text, p_success boolean, p_steps text[], p_k int, p_kind text, p_class text) RETURNS text
LANGUAGE sql AS $$
    INSERT INTO fw.score (id, episode_id, scorer_version, scorer_cfg_id, success, step_status, first_failed_step,
                          failure_kind, failure_class, level)
    VALUES ('sc_' || t.h16(p_ep), p_ep, '1.0.0', t.v('cfg_scorer'), p_success, p_steps, p_k, p_kind, p_class, 0)
    RETURNING id $$;

DO $$
DECLARE
    ok6 text[] := ARRAY['passed', 'passed', 'passed', 'passed', 'passed', 'passed'];
    slip text[] := ARRAY['passed', 'passed', 'failed', 'not_attempted', 'not_attempted', 'not_attempted'];
BEGIN
    PERFORM t.put('tr_s1', t.trace(201, t.v('cond_dev_1'), true));
    PERFORM t.put('tr_s2', t.trace(202, t.v('cond_dev_2'), true));
    PERFORM t.put('tr_f1', t.trace(203, t.v('cond_dev_3'), false));
    PERFORM t.put('tr_f2', t.trace(204, t.v('cond_dev_4'), false));
    PERFORM t.put('tr_f3', t.trace(206, t.v('cond_dev_6'), false));
    PERFORM t.trace(205, t.v('cond_dev_5'), NULL, 'simulator_error');
    PERFORM t.expect_error(format('SELECT t.trace(207, %L, false, %L)', t.v('cond_dev_5'), 'timeout'), 'check constraint');
    PERFORM t.expect_error(format('SELECT t.trace(208, %L, true)', t.v('cond_train_1')), 'not in the eval run condition set');

    PERFORM t.score(t.v('tr_s1'), true, ok6, NULL, NULL, NULL);
    PERFORM t.score(t.v('tr_s2'), true, ok6, NULL, NULL, NULL);
    PERFORM t.score(t.v('tr_f1'), false, slip, 3, 'L-SLIP', 'carry');
    PERFORM t.score(t.v('tr_f2'), false, slip, 3, 'L-COLLIDE', 'carry');   -- class from step 3
    PERFORM t.score(t.v('tr_f3'), false, ARRAY['passed', 'failed', 'not_attempted', 'not_attempted', 'not_attempted',
                                               'not_attempted'], 2, 'L-GRASP', 'grasp');
    PERFORM t.expect_error(format($q$SELECT t.score(%L, false, ARRAY['passed','failed'], 2, 'L-GRASP', 'grasp')$q$,
                                  t.v('tr_f1') || ''), 'has 6 steps|duplicate');
    PERFORM t.expect_error(format($q$INSERT INTO fw.score (id, episode_id, scorer_version, scorer_cfg_id, success,
                                    step_status, first_failed_step, failure_kind, failure_class)
                                    VALUES (%L, %L, '2.0.0', %L, false, %L, 3, 'L-COLLIDE', 'grasp')$q$,
                                  'sc_' || t.h16('x'), t.v('tr_f2'), t.v('cfg_scorer'), slip), 'must be carry');

    ASSERT (SELECT success_rate FROM fw.v_eval_summary WHERE eval_run_id = t.u('ev') AND is_total) = 0.4,
           'success over valid episodes only: 2 of 5';
    ASSERT (SELECT infra_errors FROM fw.v_eval_summary WHERE eval_run_id = t.u('ev') AND is_total) = 1, 'one infra error';
    ASSERT (SELECT (valid_episodes, phase_pick, phase_walk, phase_place_success) = (5::bigint, 4::bigint, 2::bigint, 2::bigint)
            FROM fw.v_eval_funnel WHERE eval_run_id = t.u('ev')), 'funnel counts';
    ASSERT (SELECT count(*) FROM fw.v_failure_table WHERE eval_run_id = t.u('ev')) = 3, 'three failures, infra excluded';
END $$;

-- ===========================================================================
\echo '10. F7: Failure -> Data round, diagnosis, proposals, review, ledger'
-- ===========================================================================
DO $$
DECLARE
    new_id uuid;
BEGIN
    PERFORM t.put('rp_round', t.rp('round-1-C', 'round', t.v('src_clean'), 'psi0/pre.fast.1by1', false));
    INSERT INTO fw.run_plan_branch (run_plan_id, branch, method, seeds, release_id)
    VALUES (t.v('rp_round'), 'C', 'psi0', '{0}', t.v('rel_robot'));
    PERFORM t.expect_error(format($q$INSERT INTO fw.flywheel_round (run_plan_id, branch, round_no, parent_checkpoint_id, budget_usd)
                                    VALUES (%L, 'C', 1, %L, 100)$q$, t.v('rp_round'), t.v('ckpt')), 'not frozen');
    PERFORM fw.run_plan_freeze(t.v('rp_round'), t.sha('round'), t.u('user_lead'));
    INSERT INTO fw.flywheel_round (run_plan_id, branch, round_no, parent_checkpoint_id, budget_usd, find_eval_run_id)
    VALUES (t.v('rp_round'), 'C', 1, t.v('ckpt'), 100, t.u('ev')) RETURNING id INTO new_id;
    PERFORM t.put('round', new_id::text);
    ASSERT (SELECT count(*) FROM fw.round_step WHERE round_id = t.u('round')) = 12, 'twelve steps laid out';
    PERFORM t.expect_error(format($q$INSERT INTO fw.flywheel_round (run_plan_id, branch, round_no, parent_checkpoint_id, budget_usd)
                                    VALUES (%L, 'V_EGO', 1, %L, 100)$q$, t.v('rp_he'), t.v('ckpt')), 'not a round plan');

    INSERT INTO fw.cluster (id, round_id, first_failed_step, failure_kind, level)
    VALUES ('clu_' || t.h16('slip'), t.u('round'), 3, 'L-SLIP', 0),
           ('clu_' || t.h16('grasp'), t.u('round'), 2, 'L-GRASP', 0);
    INSERT INTO fw.cluster_member VALUES ('clu_' || t.h16('slip'), t.v('tr_f1'), true), ('clu_' || t.h16('slip'), t.v('tr_f2'), false),
                                         ('clu_' || t.h16('grasp'), t.v('tr_f3'), true);
    PERFORM t.expect_error(format($q$INSERT INTO fw.cluster_member VALUES (%L, %L, false)$q$,
                                  'clu_' || t.h16('slip'), t.v('tr_s1')), 'failed dev eval rollout');
    PERFORM t.expect_error(format($q$INSERT INTO fw.diagnostic_check (cluster_id, check_no, code, status)
                                    VALUES (%L, 7, 'feasibility', 'skipped')$q$, 'clu_' || t.h16('slip')), 'check constraint');
    INSERT INTO fw.diagnostic_check (cluster_id, episode_id, check_no, code, status, value, threshold, positive, skip_reason)
    VALUES ('clu_' || t.h16('slip'), t.v('tr_f1'), 4, 'cmd_tracking', 'ran', 0.02, 0.05, false, NULL),
           ('clu_' || t.h16('slip'), t.v('tr_f1'), 6, 'train_domain', 'ran', 0.1, 0.3, false, NULL),
           ('clu_' || t.h16('slip'), t.v('tr_f1'), 8, 'localization', 'skipped', NULL, NULL, NULL,
            'restore_state = false; chưa khoanh vùng'),
           ('clu_' || t.h16('slip'), t.v('tr_f1'), 10, 'coverage', 'ran', 0.42, 0.25, true, NULL);
    INSERT INTO fw.cluster_diagnosis (cluster_id, diagnosis, decided_by)
    VALUES ('clu_' || t.h16('slip'), 'THIEU_VUNG_PHU', 'machine'), ('clu_' || t.h16('grasp'), 'KY_NANG_YEU', 'machine');
    PERFORM t.expect_error(format($q$INSERT INTO fw.cluster_diagnosis (cluster_id, diagnosis, decided_by, engineer)
                                    VALUES (%L, 'NHAN_THUC', 'engineer', %L)$q$, 'clu_' || t.h16('grasp'), t.u('user_lead')),
                           'check constraint');

    PERFORM t.expect_error(format($q$INSERT INTO fw.intervention (id, round_id, cluster_id, type, n_failures, n_eff, quantity,
                                    gain_g, cost_c_usd, rank, selected_by_algorithm)
                                    VALUES (%L, %L, %L, 'teleop_correction', 2, 2, 2, 0.01, 30, 1, true)$q$,
                                  'iv_' || t.ulid(1), t.u('round'), 'clu_' || t.h16('slip')), 'not allowed for diagnosis');
    PERFORM t.expect_error(format($q$INSERT INTO fw.intervention (id, round_id, cluster_id, type, n_failures, n_eff, quantity,
                                    gain_g, cost_c_usd, rank, selected_by_algorithm)
                                    VALUES (%L, %L, %L, 'sim_s1', 2, 1, 20, 0.01, 40, 1, true)$q$,
                                  'iv_' || t.ulid(2), t.u('round'), 'clu_' || t.h16('slip')), 'n_eff must be');
    PERFORM t.expect_error(format($q$INSERT INTO fw.intervention (id, round_id, cluster_id, type, n_failures, n_eff, quantity,
                                    gain_g, cost_c_usd, rank, selected_by_algorithm)
                                    VALUES (%L, %L, %L, 'sim_s3', 2, 2, 40, 0.01, 80, 1, true)$q$,
                                  'iv_' || t.ulid(3), t.u('round'), 'clu_' || t.h16('slip')), 'not enabled');
    INSERT INTO fw.intervention (id, round_id, cluster_id, type, n_failures, n_eff, quantity, gain_g, cost_c_usd, rank,
                                 selected_by_algorithm)
    VALUES ('iv_' || t.ulid(10), t.u('round'), 'clu_' || t.h16('slip'), 'sim_s1', 2, 2, 40, 0.0111, 80, 1, true),
           ('iv_' || t.ulid(11), t.u('round'), 'clu_' || t.h16('grasp'), 'teleop_correction', 1, 1, 1, 0.0056, 15, 2, true);

    UPDATE fw.flywheel_round SET status = 'DIAGNOSING' WHERE id = t.u('round');
    UPDATE fw.flywheel_round SET status = 'PLANNING' WHERE id = t.u('round');
    UPDATE fw.flywheel_round SET status = 'AWAITING_REVIEW' WHERE id = t.u('round');

    PERFORM t.expect_error(format($q$SELECT fw.round_review(%L, %L, 'ok', '[{"intervention_id": "%s", "approved": true, "qty": 40}]')$q$,
                                  t.u('round'), t.u('user_lead'), 'iv_' || t.ulid(10)), 'missing');
    PERFORM t.expect_error(format($q$SELECT fw.round_review(%L, %L, 'ok', '[{"intervention_id": "%s", "approved": true, "qty": 60},
                                    {"intervention_id": "%s", "approved": true, "qty": 1}]')$q$,
                                  t.u('round'), t.u('user_lead'), 'iv_' || t.ulid(10), 'iv_' || t.ulid(11)), 'exceeds the round budget');
    PERFORM t.expect_error(format($q$SELECT fw.round_review(%L, %L, 'ok', '[{"intervention_id": "%s", "approved": true, "qty": 30},
                                    {"intervention_id": "%s", "approved": true, "qty": 1}]')$q$,
                                  t.u('round'), t.u('user_lead'), 'iv_' || t.ulid(10), 'iv_' || t.ulid(11)), 'needs a reason');
    PERFORM t.put('dec_review', fw.round_review(t.u('round'), t.u('user_lead'), 'Cut S1 to keep budget for a second round',
        format('[{"intervention_id": "%s", "approved": true, "qty": 30, "override_reason": "giữ ngân sách"},
                 {"intervention_id": "%s", "approved": true, "qty": 1}]', 'iv_' || t.ulid(10), 'iv_' || t.ulid(11))::jsonb));

    ASSERT (SELECT verdict FROM fw.decision WHERE id = t.v('dec_review')) = 'overridden', 'override recorded';
    ASSERT (SELECT status FROM fw.flywheel_round WHERE id = t.u('round')) = 'ACQUIRING', 'round acquiring';
    ASSERT (SELECT estimated_usd FROM fw.v_round_progress WHERE round_id = t.u('round')) = 75, '60 + 15 estimated';
    ASSERT (SELECT count(*) FROM fw.intervention_task) = 2, 'one task per approved intervention';
    ASSERT (SELECT approved_qty FROM fw.v_intervention_progress WHERE id = 'iv_' || t.ulid(10)) = 30, 'approved qty';
END $$;

-- acquisition: a new synthetic batch points back to the intervention
DO $$
DECLARE
    b uuid;
BEGIN
    INSERT INTO fw.ingest_batch (code, name, task_id, source_kind, source_detail, synthetic_tier, origin_intervention_id,
                                 data_class, raw_uri, created_by)
    VALUES ('DS-SYN-S1-R1', 'round 1 S1', 'g1_locomotion_pick_between_tables', 'synthetic', 'planner_wbc', 'S1',
            'iv_' || t.ulid(10), 'public', 'raw/r1', t.u('user_lead')) RETURNING id INTO b;
    PERFORM t.pass_stage(b, 1);
    PERFORM fw.stage_start(t.cur_stage(b, 2), NULL);
    INSERT INTO fw.episode (id, kind, source_kind, synthetic_tier, action_quality, operator_kind, condition_id, batch_id,
                            created_by_stage_run_id, intervention_id, task_id, embodiment_id, data_class, license, split,
                            renderer, bundle_uri)
    VALUES ('ep_' || t.ulid(300), 'sim_rollout', 'synthetic', 'S1', 'planned', 'machine', t.v('cond_train_11'), b,
            t.cur_stage(b, 2), 'iv_' || t.ulid(10), 'g1_locomotion_pick_between_tables', 'g1_sonic_dwbc@1', 'public',
            'unknown', 'train', 'mujoco', 'episodes/300');
    PERFORM fw.stage_finish(t.cur_stage(b, 2), 'PASS', '{}', 'o', 'l', t.agent(t.cur_stage(b, 2), 'PASS'));
    PERFORM t.pass_stage(b, 3);
    PERFORM fw.stage_start(t.cur_stage(b, 4), NULL);
    PERFORM t.qa('ep_' || t.ulid(300), 'pass');
    INSERT INTO fw.ledger_entry (id, activity, resource_type, quantity, unit, pricebook_cfg_id, usd_amount, measure_kind,
                                 branch, run_plan_id, round_id, intervention_id, batch_id)
    VALUES (fw.new_id('led'), 'data_generation', 'intervention_sim_s1', 30, 'rollout', t.v('cfg_pb'), 66, 'measured',
            'C', t.v('rp_round'), t.u('round'), 'iv_' || t.ulid(10), b);
    ASSERT (SELECT collected_qa_pass FROM fw.v_intervention_progress WHERE id = 'iv_' || t.ulid(10)) = 1, 'collected';
    ASSERT (SELECT relative_error FROM fw.v_cost_forecast_error WHERE intervention_id = 'iv_' || t.ulid(10)) = 0.1,
           '66 measured vs 60 estimated';
END $$;

-- ===========================================================================
\echo '11. Fix rates, ledger append-only and reversals'
-- ===========================================================================
WITH x AS (INSERT INTO fw.eval_run (run_plan_id, purpose, checkpoint_id, condition_set_id, timing, sim_mode,
    renderer, scorer_cfg_id, round_id) VALUES (t.v('rp_round'), 'fix_rate_parent', t.v('ckpt'), 'cset_' || t.h16('dev'),
    'sync', 'mujoco', 'mujoco', t.v('cfg_scorer'), t.u('round')) RETURNING id) SELECT t.put('ev_parent', id::text) FROM x;
INSERT INTO fw.fix_rate_event (id, round_id, cluster_id, intervention_id, intervention_type, diagnosis, failure_kind,
                               failure_class, task_family, n_conditions, p_parent, p_candidate, parent_eval_run_id,
                               candidate_eval_run_id)
VALUES ('fre_' || t.ulid(1), t.u('round'), 'clu_' || t.h16('slip'), 'iv_' || t.ulid(10), 'sim_s1', 'THIEU_VUNG_PHU', 'L-SLIP',
        'carry', 'pick_place', 10, 0.3, 0.6, t.u('ev_parent'), t.u('ev_parent')),
       ('fre_' || t.ulid(2), t.u('round'), 'clu_' || t.h16('grasp'), 'iv_' || t.ulid(11), 'teleop_correction', 'KY_NANG_YEU',
        'L-GRASP', 'grasp', 'pick_place', 5, 0.6, 0.2, t.u('ev_parent'), t.u('ev_parent'));

DO $$
DECLARE
    led text;
BEGIN
    ASSERT (SELECT fixed FROM fw.fix_rate_event WHERE id = 'fre_' || t.ulid(1)) = 3, 'round(10 * 0.3) = 3';
    ASSERT (SELECT fixed FROM fw.fix_rate_event WHERE id = 'fre_' || t.ulid(2)) = 0, 'clamped at 0';
    ASSERT (SELECT (alpha, beta) = (4::bigint, 8::bigint) FROM fw.v_fix_rate_posterior WHERE intervention_type = 'sim_s1'),
           'Beta(1 + 3, 1 + 7)';
    ASSERT (SELECT mean FROM fw.v_fix_rate_posterior WHERE intervention_type = 'recovery') = 0.5, 'untouched prior 0.5';

    SELECT id INTO led FROM fw.ledger_entry WHERE activity = 'train' LIMIT 1;
    PERFORM t.expect_error(format($q$UPDATE fw.ledger_entry SET usd_amount = 1 WHERE id = %L$q$, led), 'append-only');
    PERFORM t.expect_error(format($q$DELETE FROM fw.ledger_entry WHERE id = %L$q$, led), 'append-only');
    PERFORM t.expect_error(format($q$INSERT INTO fw.ledger_entry (id, activity, resource_type, quantity, unit, pricebook_cfg_id,
                                    usd_amount, measure_kind, run_plan_id, reverses_entry_id, note)
                                    VALUES (fw.new_id('led'), 'train', 'gpu_hour_a100', -6, 'gpu_hour', %L, -10, 'measured',
                                    %L, %L, 'wrong amount')$q$, t.v('cfg_pb'), t.v('rp_he'), led), 'must negate');
    INSERT INTO fw.ledger_entry (id, activity, resource_type, quantity, unit, pricebook_cfg_id, usd_amount, measure_kind,
                                 branch, run_plan_id, reverses_entry_id, note)
    VALUES (fw.new_id('led'), 'train', 'gpu_hour_a100', -6, 'gpu_hour', t.v('cfg_pb'), -15, 'measured', 'V_EGO',
            t.v('rp_he'), led, 'logged twice by the Colab wrapper');
    PERFORM t.expect_error(format($q$INSERT INTO fw.ledger_entry (id, activity, resource_type, quantity, unit, pricebook_cfg_id,
                                    usd_amount, measure_kind, run_plan_id, reverses_entry_id, note)
                                    VALUES (fw.new_id('led'), 'train', 'gpu_hour_a100', -6, 'gpu_hour', %L, -15, 'measured',
                                    %L, %L, 'again')$q$, t.v('cfg_pb'), t.v('rp_he'), led), 'already reversed');
    ASSERT (SELECT sum(usd_measured) FROM fw.v_cost_by_branch WHERE run_plan_id = t.v('rp_he') AND branch = 'V_EGO') = 0,
           'reversal nets to zero';
    ASSERT (SELECT usd FROM fw.v_release_data_cost WHERE release_id = t.v('rel_robot') AND source_kind = 'teleop') = 40,
           'teleop batch cost carried by its 4 accepted demos';
END $$;

-- ===========================================================================
\echo '12. Refs, holdout locks and seals, checkpoint retention'
-- ===========================================================================
DO $$
DECLARE
    d text := fw.new_id('dec');
    d2 text := fw.new_id('dec');
BEGIN
    INSERT INTO fw.decision (id, kind, subject_kind, subject_id, verdict, signed_by, reason)
    VALUES (d, 'dev_gate', 'checkpoint', t.v('ckpt'), 'fail', t.u('user_lead'), 'no gain over 1 SE'),
           (d2, 'dev_gate', 'checkpoint', t.v('ckpt'), 'pass', t.u('user_lead'), 'gain 1.4 SE, regression 3%');
    PERFORM t.expect_error(format('SELECT fw.ref_set(%L, %L, %L, %L)', 'policy/C/current', t.v('ckpt'), d, 'x'),
                           'passing dev_gate');
    PERFORM fw.ref_set('policy/C/current', t.v('ckpt'), d2, 'promoted after round 1');
    ASSERT (SELECT count(*) FROM fw.ref_log) = 1, 'ref change logged';
    ASSERT (SELECT verdict FROM fw.v_decision_current WHERE subject_id = t.v('ckpt') AND kind = 'dev_gate') = 'pass',
           'latest decision wins';

    INSERT INTO fw.holdout_lock (checkpoint_id, run_plan_id, protocol_sha256) VALUES (t.v('ckpt'), t.v('rp_he'), t.sha('hp'));
    PERFORM t.expect_error(format($q$INSERT INTO fw.holdout_lock (checkpoint_id, run_plan_id, protocol_sha256)
                                    VALUES (%L, %L, %L)$q$, t.v('ckpt'), t.v('rp_he'), t.sha('hp')), 'duplicate key');
    INSERT INTO fw.holdout_seal (run_plan_id, checkpoint_id, result_sha256) VALUES (t.v('rp_he'), t.v('ckpt'), t.sha('r'));
    PERFORM t.expect_error(format($q$INSERT INTO fw.holdout_result (run_plan_id, checkpoint_id, level, n_conditions, n_success)
                                    VALUES (%L, %L, 0, 50, 30)$q$, t.v('rp_he'), t.v('ckpt')), 'still sealed');
    PERFORM t.expect_error(format('SELECT fw.holdout_unseal(%L)', t.v('rp_he')), 'must be locked');   -- V_NOEGO missing
END $$;

INSERT INTO fw.train_run (run_plan_id, branch, seed, stage, method, export_id)
VALUES (t.v('rp_he'), 'V_NOEGO', 0, 3, 'psi0', t.u('exp_robot'));
INSERT INTO fw.checkpoint (id, origin, train_run_id, method, branch, seed, stage, release_id, weights_sha256, uri, is_final)
SELECT 'ckpt_' || t.h16('noego-final'), 'trained', id, 'psi0', 'V_NOEGO', 0, 3, t.v('rel_robot'), t.sha('w3'), 'ckpt/noego', true
FROM fw.train_run WHERE branch = 'V_NOEGO';
INSERT INTO fw.holdout_lock (checkpoint_id, run_plan_id, protocol_sha256)
VALUES ('ckpt_' || t.h16('noego-final'), t.v('rp_he'), t.sha('hp'));
SELECT fw.holdout_unseal(t.v('rp_he'));
INSERT INTO fw.holdout_result (run_plan_id, checkpoint_id, level, n_conditions, n_success) VALUES (t.v('rp_he'), t.v('ckpt'), 0, 50, 30);

DO $$ BEGIN
    PERFORM t.expect_error(format($q$UPDATE fw.checkpoint SET file_purged = true, purged_at = now(), purge_reason = 'x'
                                    WHERE id = %L$q$, t.v('ckpt')), 'still needed');
    UPDATE fw.checkpoint SET file_purged = true, purged_at = now(), purge_reason = 'intermediate, unreferenced'
    WHERE id = 'ckpt_' || t.h16('ego-mid');
    PERFORM t.expect_error(format($q$UPDATE fw.checkpoint SET file_purged = false, purged_at = NULL, purge_reason = NULL
                                    WHERE id = %L$q$, 'ckpt_' || t.h16('ego-mid')), 'un-purged');
END $$;

-- ===========================================================================
\echo '13. Chat agent actions'
-- ===========================================================================
DO $$
DECLARE
    s uuid;
    um uuid;
    am uuid;
    a uuid;
BEGIN
    INSERT INTO fw.chat_session (user_id, context_kind, context_ref, title)
    VALUES (t.u('user_data'), 'STAGE_RUN', t.cur_stage(t.u('b_tel'), 4)::text, 'Why did QA pause?') RETURNING id INTO s;
    PERFORM t.expect_error(format($q$INSERT INTO fw.chat_session (user_id, context_kind, title) VALUES (%L, 'BATCH', 'x')$q$,
                                  t.u('user_data')), 'check constraint');
    INSERT INTO fw.chat_message (session_id, sender_role, sender_user_id, text_content)
    VALUES (s, 'USER', t.u('user_data'), 'Tại sao tầng 4 dừng?') RETURNING id INTO um;
    INSERT INTO fw.chat_message (session_id, sender_role, agent_model, text_content)
    VALUES (s, 'QA_QC_AGENT', 'nemotron-3.5-bolt-e4b-q4', 'Một episode vượt giới hạn khớp.') RETURNING id INTO am;
    PERFORM t.expect_error(format($q$INSERT INTO fw.chat_action (message_id, kind, payload) VALUES (%L, 'stage_retry', '{}')$q$, um),
                           'only an agent message');
    PERFORM t.expect_error(format($q$INSERT INTO fw.chat_action (message_id, kind, payload) VALUES (%L, 'approve_plan', '{}')$q$, am),
                           'check constraint');
    INSERT INTO fw.chat_action (message_id, kind, payload) VALUES (am, 'stage_retry', '{"stage": 4}') RETURNING id INTO a;
    PERFORM t.expect_error(format($q$UPDATE fw.chat_action SET status = 'EXECUTED', decided_by = %L, decided_at = now()
                                    WHERE id = %L$q$, t.u('user_data'), a), 'illegal status transition');
    UPDATE fw.chat_action SET status = 'CONFIRMED', decided_by = t.u('user_data'), decided_at = now() WHERE id = a;
    PERFORM t.expect_error(format($q$UPDATE fw.chat_message SET text_content = 'edited' WHERE id = %L$q$, am), 'append-only');
END $$;

-- ===========================================================================
\echo '14. No deletes anywhere; every view answers'
-- ===========================================================================
DO $$
DECLARE
    v record;
BEGIN
    PERFORM t.expect_error(format($q$DELETE FROM fw.episode WHERE id = %L$q$, t.v('ep_tel_1')), 'append-only');
    PERFORM t.expect_error(format($q$DELETE FROM fw.ingest_batch WHERE id = %L$q$, t.u('b_tel')), 'not allowed');
    PERFORM t.expect_error($q$DELETE FROM fw.job$q$, 'not allowed');
    UPDATE fw.ingest_batch SET hidden_at = now(), hidden_by = t.u('user_lead'), hidden_reason = 'demo clutter'
    WHERE id = t.u('b_retry');
    ASSERT NOT EXISTS (SELECT 1 FROM fw.v_batch_overview WHERE id = t.u('b_retry')), 'hidden batch filtered';
    PERFORM t.expect_error(format($q$UPDATE fw.ingest_batch SET hidden_at = now() WHERE id = %L$q$, t.u('b_syn')),
                           'check constraint');

    FOR v IN SELECT table_schema, table_name FROM information_schema.views WHERE table_schema IN ('fw', 'fw_sealed') LOOP
        EXECUTE format('SELECT count(*) FROM %I.%I', v.table_schema, v.table_name);
    END LOOP;
    ASSERT (SELECT human_demos FROM fw.v_branch_comparison WHERE run_plan_id = t.v('rp_he') AND branch = 'V_EGO') = 4,
           'branch card shows human demos';
    ASSERT (SELECT latest_success_rate FROM fw.v_branch_comparison WHERE run_plan_id = t.v('rp_he') AND branch = 'V_EGO') = 0.4,
           'branch card shows latest dev success';
    ASSERT (SELECT count(*) FROM fw.v_pipeline_stepper WHERE batch_id = t.u('b_tel')) = 6, 'six-stage stepper';
    ASSERT (SELECT status FROM fw.v_pipeline_stepper WHERE batch_id = t.u('b_tel') AND stage_no = 6) = 'PASSED',
           'export stage derived from READY export';
    ASSERT NOT EXISTS (SELECT 1 FROM fw.v_episode_public WHERE source_kind = 'egocentric' AND deid_status <> 'verified'),
           'public view hides unverified egocentric video';
END $$;

\echo 'ALL TESTS PASSED'
