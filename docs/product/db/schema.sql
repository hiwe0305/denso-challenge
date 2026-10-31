-- Humanoid Data Flywheel: PostgreSQL schema for the web backend.
-- Draft 0.1, 30/10/2026. Design rationale: docs/product/10-database.md.
--
-- Invariants enforced here (CLAUDE.md, 03 sections 4.4 and 8.3):
--   * catalog, ledger and decision tables are append-only; no table allows DELETE
--   * frozen releases and frozen run plans are immutable
--   * injected-defect copies never enter a frozen release; answer keys live in fw_sealed
--   * egocentric episodes are de-identified before annotation and release
--   * infrastructure errors are never counted as policy failures
--   * holdout conditions are not stored here; only locks, seals and unsealed results
--   * every status column moves only along fw.status_transition
--
-- Requires PostgreSQL 14+ (gen_random_uuid, uuid_send are core).

BEGIN;

CREATE SCHEMA fw;
CREATE SCHEMA fw_sealed;

-- ---------------------------------------------------------------------------
-- 0. Generic helpers
-- ---------------------------------------------------------------------------

-- ULID (Crockford base32): 10 chars of millisecond time, 16 chars of randomness.
-- The catalog writer normally creates IDs in Python; this is for backend-side rows.
CREATE FUNCTION fw.new_ulid() RETURNS text
LANGUAGE plpgsql VOLATILE AS $$
DECLARE
    enc constant text := '0123456789ABCDEFGHJKMNPQRSTVWXYZ';
    ts bigint := (extract(epoch FROM clock_timestamp()) * 1000)::bigint;
    rnd bytea := uuid_send(gen_random_uuid());
    head text := '';
    tail text := '';
    i int;
BEGIN
    FOR i IN 1..10 LOOP
        head := substr(enc, (ts % 32)::int + 1, 1) || head;
        ts := ts / 32;
    END LOOP;
    FOR i IN 0..15 LOOP
        tail := tail || substr(enc, get_byte(rnd, i) % 32 + 1, 1);
    END LOOP;
    RETURN head || tail;
END $$;

CREATE FUNCTION fw.new_id(prefix text) RETURNS text
LANGUAGE sql VOLATILE AS $$ SELECT prefix || '_' || fw.new_ulid() $$;

CREATE FUNCTION fw.tg_append_only() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION '% on fw.% is not allowed: table is append-only', TG_OP, TG_TABLE_NAME
        USING ERRCODE = 'restrict_violation';
END $$;

CREATE FUNCTION fw.tg_no_delete() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'DELETE on fw.% is not allowed: mark the row instead', TG_TABLE_NAME
        USING ERRCODE = 'restrict_violation';
END $$;

-- Rejects an UPDATE that changes any column not listed in the trigger arguments.
CREATE FUNCTION fw.tg_only_columns_mutable() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    old_row jsonb := to_jsonb(OLD);
    new_row jsonb := to_jsonb(NEW);
    col text;
BEGIN
    FOREACH col IN ARRAY TG_ARGV LOOP
        old_row := old_row - col;
        new_row := new_row - col;
    END LOOP;
    IF old_row IS DISTINCT FROM new_row THEN
        RAISE EXCEPTION 'fw.%: only columns (%) may change', TG_TABLE_NAME, array_to_string(TG_ARGV, ', ')
            USING ERRCODE = 'restrict_violation';
    END IF;
    RETURN NEW;
END $$;

CREATE TABLE fw.status_transition (
    tbl         text NOT NULL,
    from_status text NOT NULL,
    to_status   text NOT NULL,
    PRIMARY KEY (tbl, from_status, to_status)
);

CREATE FUNCTION fw.tg_check_status() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.status IS DISTINCT FROM OLD.status AND NOT EXISTS (
        SELECT 1 FROM fw.status_transition t
        WHERE t.tbl = TG_TABLE_NAME AND t.from_status = OLD.status AND t.to_status = NEW.status
    ) THEN
        RAISE EXCEPTION 'fw.%: illegal status transition % -> %', TG_TABLE_NAME, OLD.status, NEW.status
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END $$;

CREATE FUNCTION fw.tg_touch_updated_at() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END $$;

-- ---------------------------------------------------------------------------
-- 1. Users and hashed configuration
-- ---------------------------------------------------------------------------

CREATE TABLE fw.app_user (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    username         text NOT NULL UNIQUE,
    display_name     text NOT NULL,
    role             text NOT NULL CHECK (role IN ('DATA_ENGINEER', 'ML_ENGINEER', 'LEAD', 'JUDGE_VIEWER', 'ADMIN')),
    person_code      text NOT NULL UNIQUE,          -- pseudonym written to the ledger
    can_run_gpu_jobs boolean NOT NULL DEFAULT false, -- CLAUDE.md: GPU jobs only from the lead
    created_at       timestamptz NOT NULL DEFAULT now(),
    disabled_at      timestamptz
);

-- YAML configs in configs/ with their hash (03 section 4.1). Not catalog entities.
CREATE TABLE fw.config_artifact (
    id         text PRIMARY KEY,
    kind       text NOT NULL CHECK (kind IN ('embodiment', 'task', 'split_plan', 'pricebook', 'thresholds',
                                             'recipe', 'scorer', 'agent_prompt', 'probe_set', 'sim',
                                             'holdout_protocol')),
    name       text NOT NULL,
    version    text NOT NULL,
    sha256     text NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'),
    repo_path  text NOT NULL,
    body       jsonb NOT NULL,
    git_sha    text CHECK (git_sha ~ '^[0-9a-f]{40}$'),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (kind, name, version),
    CHECK (id = 'cfg_' || left(sha256, 16))
);

CREATE TABLE fw.task_def (
    task_id        text PRIMARY KEY,
    version        text NOT NULL,
    family         text NOT NULL,                  -- e.g. pick_place; used to pool fix rates at L1
    n_steps        smallint NOT NULL CHECK (n_steps BETWEEN 1 AND 12),
    step_names     text[] NOT NULL,
    simple_env_id  text,
    cfg_id         text REFERENCES fw.config_artifact,
    CHECK (cardinality(step_names) = n_steps)
);

CREATE TABLE fw.failure_kind_def (
    task_id       text NOT NULL REFERENCES fw.task_def,
    code          text NOT NULL CHECK (code ~ '^L-[A-Z]+$'),
    -- NULL means the class comes from the first failed step (L-COLLIDE, L-TIMEOUT) or none (L-UNKNOWN)
    failure_class text CHECK (failure_class IN ('approach', 'grasp', 'carry', 'place', 'balance')),
    description   text NOT NULL,
    PRIMARY KEY (task_id, code)
);

-- Default failure class of each task step (03 section 4.3, "Lớp lỗi chung").
CREATE TABLE fw.task_step_class (
    task_id       text NOT NULL REFERENCES fw.task_def,
    step_no       smallint NOT NULL,
    failure_class text NOT NULL CHECK (failure_class IN ('approach', 'grasp', 'carry', 'place', 'balance')),
    PRIMARY KEY (task_id, step_no)
);

-- ---------------------------------------------------------------------------
-- 2. Sources, run plans, jobs
-- ---------------------------------------------------------------------------

CREATE TABLE fw.source (
    id                  text PRIMARY KEY CHECK (id ~ '^src_[0-9a-f]{16}$'),
    kind                text NOT NULL CHECK (kind IN ('dataset', 'checkpoint', 'video_upload', 'code')),
    uri                 text NOT NULL,
    repo                text,
    revision            text,
    path                text,
    sha256              text NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'),
    license             text NOT NULL,              -- 'unknown' is allowed but must be explicit
    data_class          text NOT NULL CHECK (data_class IN ('public', 'internal', 'restricted')),
    clean_for_main_task text NOT NULL DEFAULT 'unknown' CHECK (clean_for_main_task IN ('true', 'false', 'unknown')),
    provenance          jsonb NOT NULL DEFAULT '{}',
    downloaded_at       timestamptz NOT NULL,
    site_id             text NOT NULL DEFAULT 'local',
    schema_version      text NOT NULL DEFAULT '1',
    meta                jsonb NOT NULL DEFAULT '{}',
    created_at          timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE fw.run_plan (
    id                   text PRIMARY KEY CHECK (id ~ '^rp_[0-9a-f]{16}$'),
    name                 text NOT NULL UNIQUE,
    -- he, stage1, tray_he are proposed additions (09 gap G6); the rest is 03 section 4.3
    purpose              text NOT NULL CHECK (purpose IN ('g0_repro', 'e1', 'branch_train', 'aa_test', 'round',
                                                          'holdout', 'hd', 'he', 'stage1', 'tray_he')),
    task_id              text NOT NULL REFERENCES fw.task_def,
    embodiment_id        text NOT NULL CHECK (embodiment_id ~ '^[a-z0-9_]+@[0-9]+$'),
    base_source_id       text REFERENCES fw.source,
    base_checkpoint_path text,
    split_plan_cfg_id    text REFERENCES fw.config_artifact,
    recipe_cfg_id        text REFERENCES fw.config_artifact,
    scorer_cfg_id        text REFERENCES fw.config_artifact,
    pricebook_cfg_id     text REFERENCES fw.config_artifact,
    body                 jsonb NOT NULL,             -- runplan.yaml as JSON
    budget_cap_usd       numeric(12, 2) CHECK (budget_cap_usd >= 0),
    gpu_hours_cap        numeric(10, 2) CHECK (gpu_hours_cap >= 0),
    status               text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'frozen')),
    lock_sha256          text CHECK (lock_sha256 ~ '^[0-9a-f]{64}$'),
    git_sha              text CHECK (git_sha ~ '^[0-9a-f]{40}$'),
    git_dirty            boolean,
    image_digests        jsonb NOT NULL DEFAULT '{}',
    frozen_at            timestamptz,
    frozen_by            uuid REFERENCES fw.app_user,
    created_by           uuid NOT NULL REFERENCES fw.app_user,
    created_at           timestamptz NOT NULL DEFAULT now(),
    site_id              text NOT NULL DEFAULT 'local',
    schema_version       text NOT NULL DEFAULT '1',
    meta                 jsonb NOT NULL DEFAULT '{}',
    CHECK (status = 'draft' OR (lock_sha256 IS NOT NULL AND frozen_at IS NOT NULL AND frozen_by IS NOT NULL))
);

-- One row per branch; a branch can serve several hypotheses (see run_plan_comparison).
CREATE TABLE fw.run_plan_branch (
    run_plan_id text NOT NULL REFERENCES fw.run_plan,
    branch      text NOT NULL CHECK (branch ~ '^[A-Za-z0-9_.]+$'),  -- A, A0.7, B, C, B_fail, F_ACT, V_EGO, ...
    method      text NOT NULL CHECK (method IN ('psi0', 'act', 'dp')),
    seeds       int[] NOT NULL CHECK (cardinality(seeds) >= 1),
    release_id  text,                                -- data of the branch, when fixed up front
    note        text,
    PRIMARY KEY (run_plan_id, branch)
);

-- Comparisons declared before the holdout (03 section 8.1); gate refuses pairs of different methods.
CREATE TABLE fw.run_plan_comparison (
    run_plan_id text NOT NULL REFERENCES fw.run_plan,
    hypothesis  text NOT NULL CHECK (hypothesis IN ('HS', 'HT', 'HTa', 'HTb', 'HE', 'HE_T')),
    branch_a    text NOT NULL,
    branch_b    text NOT NULL,
    method      text NOT NULL CHECK (method IN ('psi0', 'act', 'dp')),
    PRIMARY KEY (run_plan_id, hypothesis, branch_a, branch_b),
    FOREIGN KEY (run_plan_id, branch_a) REFERENCES fw.run_plan_branch,
    FOREIGN KEY (run_plan_id, branch_b) REFERENCES fw.run_plan_branch,
    CHECK (branch_a <> branch_b)
);

CREATE TABLE fw.job (
    id             text PRIMARY KEY CHECK (id ~ '^job_[0-9A-HJKMNP-TV-Z]{26}$'),
    run_plan_id    text REFERENCES fw.run_plan,
    kind           text NOT NULL CHECK (kind IN ('ingest', 'pipeline_stage', 'replay', 'export', 'teleop_session',
                                                 'generate', 'train', 'probe', 'eval', 'diagnosis', 'agent_qa',
                                                 'holdout', 'report', 'hd')),
    status         text NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'running', 'succeeded', 'failed', 'cancelled')),
    infra_status   text CHECK (infra_status IN ('ok', 'simulator_error', 'policy_error', 'timeout', 'out_of_memory')),
    uses_gpu       boolean NOT NULL DEFAULT false,
    machine        text,                             -- rtx3060, colab_a100, rented_h100, ...
    requested_by   uuid NOT NULL REFERENCES fw.app_user,
    retry_of_job_id text REFERENCES fw.job,
    spec           jsonb NOT NULL DEFAULT '{}',      -- job.json
    result         jsonb,                            -- result.json
    dir_uri        text,                             -- runs/<run_plan_id>/<job_id>/
    error_message  text,
    queued_at      timestamptz NOT NULL DEFAULT now(),
    started_at     timestamptz,
    ended_at       timestamptz,
    -- data jobs may run outside a run plan; experiment jobs may not (03 section 8.1)
    CHECK (run_plan_id IS NOT NULL OR kind IN ('ingest', 'pipeline_stage', 'replay', 'export', 'teleop_session',
                                                'agent_qa', 'report'))
);

-- ---------------------------------------------------------------------------
-- 3. Conditions and condition sets (holdout conditions stay in vault/, never here)
-- ---------------------------------------------------------------------------

CREATE TABLE fw.condition (
    id             text PRIMARY KEY CHECK (id ~ '^cond_[0-9a-f]{16}$'),
    task_id        text NOT NULL REFERENCES fw.task_def,
    condition_seed bigint NOT NULL,
    level          smallint NOT NULL CHECK (level BETWEEN 0 AND 2),
    "values"       jsonb NOT NULL,                   -- map typed by ConditionSchema
    vector         double precision[] NOT NULL DEFAULT '{}',
    layout_hash    text NOT NULL,
    split          text NOT NULL CHECK (split IN ('train', 'dev')),
    origin         text NOT NULL CHECK (origin IN ('generated', 'extracted_from_demo')),
    layout_uri     text,
    quarantined    boolean NOT NULL DEFAULT false,
    quarantine_reason text,
    site_id        text NOT NULL DEFAULT 'local',
    schema_version text NOT NULL DEFAULT '1',
    meta           jsonb NOT NULL DEFAULT '{}',
    created_at     timestamptz NOT NULL DEFAULT now(),
    CHECK (NOT quarantined OR quarantine_reason IS NOT NULL)
);
CREATE INDEX condition_layout_idx ON fw.condition (layout_hash);

CREATE TABLE fw.condition_set (
    id          text PRIMARY KEY CHECK (id ~ '^cset_[0-9a-f]{16}$'),
    purpose     text NOT NULL CHECK (purpose IN ('dev_find', 'gate', 'fix_rate', 'aa', 'he_eval', 'g0', 'tray_eval', 'hd')),
    run_plan_id text REFERENCES fw.run_plan,
    seed_slice  int8range,
    sha256      text NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'),
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE fw.condition_set_member (
    set_id       text NOT NULL REFERENCES fw.condition_set,
    condition_id text NOT NULL REFERENCES fw.condition,
    PRIMARY KEY (set_id, condition_id)
);

-- ---------------------------------------------------------------------------
-- 4. Data lane: ingest batches, pipeline stages 1-4, episodes
-- ---------------------------------------------------------------------------

-- Fixed stage names (design 27/10 section 6). Stages 1-4 run per batch; 5-6 per release.
CREATE TABLE fw.pipeline_stage_def (
    stage_no smallint PRIMARY KEY CHECK (stage_no BETWEEN 1 AND 6),
    code     text NOT NULL UNIQUE,
    name     text NOT NULL,
    scope    text NOT NULL CHECK (scope IN ('batch', 'release'))
);

-- What the web document calls a "dataset": one upload or import from one source.
CREATE TABLE fw.ingest_batch (
    id                     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    code                   text NOT NULL UNIQUE,
    name                   text NOT NULL,
    task_id                text NOT NULL REFERENCES fw.task_def,
    source_kind            text NOT NULL CHECK (source_kind IN ('teleop', 'synthetic', 'egocentric')),
    source_detail          text NOT NULL,
    synthetic_tier         text CHECK (synthetic_tier IN ('S1', 'S2', 'S3', 'S4')),
    source_id              text REFERENCES fw.source,
    origin_intervention_id text,                    -- FK added after fw.intervention
    injected_from_batch_id uuid REFERENCES fw.ingest_batch,   -- non-null: copy with injected defects
    data_class             text NOT NULL CHECK (data_class IN ('public', 'internal', 'restricted')),
    raw_uri                text NOT NULL,
    raw_size_bytes         bigint CHECK (raw_size_bytes >= 0),
    force_manual_review    boolean NOT NULL DEFAULT false,
    status                 text NOT NULL DEFAULT 'INGESTED'
                           CHECK (status IN ('INGESTED', 'PROCESSING', 'PAUSED_FOR_REVIEW', 'READY_FOR_RELEASE',
                                             'ABORTED', 'FAILED')),
    current_stage          smallint CHECK (current_stage BETWEEN 1 AND 4),
    meta                   jsonb NOT NULL DEFAULT '{}',
    created_by             uuid NOT NULL REFERENCES fw.app_user,
    created_at             timestamptz NOT NULL DEFAULT now(),
    updated_at             timestamptz NOT NULL DEFAULT now(),
    hidden_at              timestamptz,
    hidden_by              uuid REFERENCES fw.app_user,
    hidden_reason          text,
    CHECK ((hidden_at IS NULL) = (hidden_reason IS NULL)),
    CHECK ((source_kind = 'teleop' AND source_detail IN ('psi_data', 'teleop_keyboard', 'teleop_pico'))
        OR (source_kind = 'synthetic' AND source_detail IN ('planner_wbc', 'planner_amo'))
        OR (source_kind = 'egocentric' AND source_detail IN ('egodex', 'ego_self_recorded'))),
    CHECK ((source_kind = 'synthetic') = (synthetic_tier IS NOT NULL))
);

CREATE TABLE fw.agent_report (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id        text REFERENCES fw.job,
    subject_kind  text NOT NULL CHECK (subject_kind IN ('stage_run', 'release', 'train_run', 'checkpoint',
                                                       'eval_run', 'round', 'rtc_log')),
    subject_id    text NOT NULL,
    model         text NOT NULL,
    model_revision text NOT NULL,
    prompt_cfg_id text NOT NULL REFERENCES fw.config_artifact,
    verdict       text NOT NULL CHECK (verdict IN ('PASS', 'WARNING', 'FAIL')),
    summary       text NOT NULL,
    inputs        jsonb NOT NULL DEFAULT '[]',      -- artifact IDs the agent read; never vault/
    estimates     jsonb NOT NULL DEFAULT '{}',      -- estimates with intervals, compared later with measurements
    html_uri      text,
    created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE fw.agent_finding (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    report_id   uuid NOT NULL REFERENCES fw.agent_report,
    code        text NOT NULL CHECK (code ~ '^(D[1-8]|T[1-8]|O[1-4]|R[1-6]|OTHER)$'),
    severity    text NOT NULL CHECK (severity IN ('info', 'warning', 'critical')),
    episode_id  text,
    frame_start int,
    frame_end   int,
    step        int,
    evidence    jsonb NOT NULL DEFAULT '{}',
    suggestion  text,
    CHECK (frame_end IS NULL OR frame_start <= frame_end)
);

-- Each attempt of a batch stage; retries add attempts and keep history (web doc idea, kept).
CREATE TABLE fw.stage_run (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_id         uuid NOT NULL REFERENCES fw.ingest_batch,
    stage_no         smallint NOT NULL REFERENCES fw.pipeline_stage_def CHECK (stage_no BETWEEN 1 AND 4),
    attempt_no       smallint NOT NULL CHECK (attempt_no >= 1),
    is_current       boolean NOT NULL DEFAULT true,
    status           text NOT NULL DEFAULT 'PENDING'
                     CHECK (status IN ('PENDING', 'RUNNING', 'AGENT_REVIEWING', 'PASSED', 'PAUSED_FOR_REVIEW',
                                       'OVERRIDDEN', 'FAILED', 'ABORTED', 'SUPERSEDED')),
    params           jsonb NOT NULL DEFAULT '{}',
    job_id           text REFERENCES fw.job,
    output_uri       text,
    log_uri          text,
    stats            jsonb,                          -- counts computed by code, e.g. pass/flag/reject per check
    code_verdict     text CHECK (code_verdict IN ('PASS', 'WARNING', 'FAIL')),
    agent_report_id  uuid REFERENCES fw.agent_report,
    error_message    text,
    started_at       timestamptz,
    ended_at         timestamptz,
    output_purged    boolean NOT NULL DEFAULT false,
    created_at       timestamptz NOT NULL DEFAULT now(),
    UNIQUE (batch_id, stage_no, attempt_no),
    -- only regenerable outputs may be purged: replay comparison videos of stage 4
    CHECK (NOT output_purged OR stage_no = 4)
);
CREATE UNIQUE INDEX stage_run_current_idx ON fw.stage_run (batch_id, stage_no) WHERE is_current;

CREATE TABLE fw.episode (
    id                      text PRIMARY KEY CHECK (id ~ '^ep_[0-9A-HJKMNP-TV-Z]{26}$'),
    -- ego_demo is a proposed addition: 03 has no kind for human video, which must never count as a robot demo
    kind                    text NOT NULL CHECK (kind IN ('teleop_demo', 'teleop_correction', 'recovery', 'sim_rollout',
                                                          'variant', 'eval_rollout', 'diag_rollout', 'ego_demo')),
    source_kind             text CHECK (source_kind IN ('teleop', 'synthetic', 'egocentric')),
    synthetic_tier          text CHECK (synthetic_tier IN ('S1', 'S2', 'S3', 'S4')),
    action_quality          text NOT NULL CHECK (action_quality IN ('measured', 'planned', 'retargeted', 'pseudo', 'none')),
    operator_kind           text NOT NULL CHECK (operator_kind IN ('human', 'machine')),
    is_root                 boolean GENERATED ALWAYS AS (
                                kind IN ('teleop_demo', 'teleop_correction', 'recovery') AND operator_kind = 'human'
                            ) STORED,
    root_id                 text REFERENCES fw.episode,
    parent_id               text REFERENCES fw.episode,
    condition_id            text REFERENCES fw.condition,
    source_id               text REFERENCES fw.source,
    batch_id                uuid REFERENCES fw.ingest_batch,
    created_by_stage_run_id uuid REFERENCES fw.stage_run,
    intervention_id         text,                   -- FK added after fw.intervention
    run_plan_id             text REFERENCES fw.run_plan,
    job_id                  text REFERENCES fw.job,
    task_id                 text NOT NULL REFERENCES fw.task_def,
    embodiment_id           text NOT NULL CHECK (embodiment_id ~ '^[a-z0-9_]+@[0-9]+$'),
    data_class              text NOT NULL CHECK (data_class IN ('public', 'internal', 'restricted')),
    license                 text NOT NULL,
    split                   text NOT NULL CHECK (split IN ('train', 'dev', 'holdout')),
    renderer                text CHECK (renderer IN ('mujoco', 'isaac')),
    bundle_uri              text NOT NULL,
    n_frames                int CHECK (n_frames >= 0),
    fps                     numeric(6, 2) CHECK (fps > 0),
    -- trace fields (kind eval_rollout or diag_rollout)
    eval_run_id             uuid,                   -- FK added after fw.eval_run
    checkpoint_id           text,                   -- FK added after fw.checkpoint
    rollout_seed            bigint,
    replicate               smallint CHECK (replicate >= 0),
    sim_success             boolean,
    infra_status            text CHECK (infra_status IN ('ok', 'simulator_error', 'policy_error', 'timeout', 'out_of_memory')),
    camera_params_hash      text,
    -- injected defects (design 27/10 section 6.1)
    injected_defect         jsonb,
    is_injected_copy        boolean NOT NULL DEFAULT false,
    site_id                 text NOT NULL DEFAULT 'local',
    schema_version          text NOT NULL DEFAULT '1',
    meta                    jsonb NOT NULL DEFAULT '{}',
    created_at              timestamptz NOT NULL DEFAULT now(),
    CHECK ((kind IN ('eval_rollout', 'diag_rollout')) = (source_kind IS NULL)),
    CHECK (kind NOT IN ('eval_rollout', 'diag_rollout')
           OR (checkpoint_id IS NOT NULL AND rollout_seed IS NOT NULL AND infra_status IS NOT NULL)),
    -- an infrastructure error is never a policy failure (03 section 5.3, rule 8)
    CHECK (infra_status IS DISTINCT FROM 'ok' OR kind NOT IN ('eval_rollout', 'diag_rollout') OR sim_success IS NOT NULL),
    CHECK (infra_status IS NULL OR infra_status = 'ok' OR sim_success IS NULL),
    CHECK (kind IN ('eval_rollout', 'diag_rollout') OR (batch_id IS NOT NULL AND split = 'train')),
    CHECK (split <> 'holdout' OR kind = 'eval_rollout'),
    CHECK ((source_kind = 'synthetic') = (synthetic_tier IS NOT NULL)),
    CHECK (source_kind IS DISTINCT FROM 'synthetic' OR (operator_kind = 'machine' AND action_quality = 'planned')),
    CHECK (source_kind IS DISTINCT FROM 'teleop' OR action_quality = 'measured'),
    CHECK (source_kind IS DISTINCT FROM 'egocentric'
           OR (action_quality IN ('retargeted', 'pseudo') AND embodiment_id = 'human_ego@1')),
    CHECK ((source_kind = 'egocentric') = (kind = 'ego_demo')),
    CHECK (injected_defect IS NULL OR is_injected_copy)
);
CREATE INDEX episode_batch_idx ON fw.episode (batch_id);
CREATE INDEX episode_eval_idx ON fw.episode (eval_run_id);
CREATE INDEX episode_intervention_idx ON fw.episode (intervention_id);

CREATE TABLE fw.episode_deid (
    seq         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    episode_id  text NOT NULL REFERENCES fw.episode,
    status      text NOT NULL CHECK (status IN ('blurred', 'verified')),
    method      text NOT NULL,
    evidence_uri text,
    by_user     uuid REFERENCES fw.app_user,
    created_at  timestamptz NOT NULL DEFAULT now(),
    CHECK (status <> 'verified' OR by_user IS NOT NULL)
);

CREATE TABLE fw.episode_segment (
    episode_id   text NOT NULL REFERENCES fw.episode,
    label_version smallint NOT NULL DEFAULT 1,
    seq          smallint NOT NULL,
    t_start      double precision NOT NULL,
    t_end        double precision NOT NULL,
    step_id      smallint NOT NULL,
    text         text NOT NULL,
    label_source text NOT NULL CHECK (label_source IN ('rule', 'human', 'model')),
    created_at   timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (episode_id, label_version, seq),
    CHECK (t_start < t_end)
);

CREATE TABLE fw.qa_report (
    seq               bigint GENERATED ALWAYS AS IDENTITY,
    id                text PRIMARY KEY CHECK (id ~ '^qa_[0-9A-HJKMNP-TV-Z]{26}$'),
    episode_id        text NOT NULL REFERENCES fw.episode,
    stage_run_id      uuid REFERENCES fw.stage_run,
    thresholds_cfg_id text NOT NULL REFERENCES fw.config_artifact,
    decision          text NOT NULL CHECK (decision IN ('pass', 'flag', 'quarantine', 'reject')),
    reasons           text[] NOT NULL DEFAULT '{}',
    checks            jsonb NOT NULL,                -- value and threshold per check (spec 4.4)
    reviewed_by       uuid REFERENCES fw.app_user,   -- set when an engineer re-decides a flag
    created_at        timestamptz NOT NULL DEFAULT now(),
    CHECK (decision = 'pass' OR cardinality(reasons) > 0)
);
CREATE INDEX qa_report_episode_idx ON fw.qa_report (episode_id, seq DESC);

CREATE TABLE fw.replay_report (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    episode_id    text NOT NULL REFERENCES fw.episode,
    stage_run_id  uuid REFERENCES fw.stage_run,
    mode          text NOT NULL CHECK (mode IN ('kinematic', 'dynamic')),
    outcome       text NOT NULL CHECK (outcome IN ('pass', 'flag', 'reject')),
    max_error     double precision,
    per_group     jsonb NOT NULL DEFAULT '{}',
    failed_frames int[] NOT NULL DEFAULT '{}',
    video_uri     text,
    thresholds_cfg_id text REFERENCES fw.config_artifact,
    created_at    timestamptz NOT NULL DEFAULT now(),
    -- kinematic failures reject, dynamic failures only flag (design 27/10 section 6.3)
    CHECK (NOT (mode = 'dynamic' AND outcome = 'reject'))
);

-- ---------------------------------------------------------------------------
-- 5. Releases and exports (pipeline stages 5 and 6)
-- ---------------------------------------------------------------------------

CREATE TABLE fw.release (
    id                   text PRIMARY KEY CHECK (id ~ '^rel_[0-9a-f]{16}$'),
    name                 text NOT NULL UNIQUE,
    kind                 text NOT NULL CHECK (kind IN ('robot', 'egocentric')),  -- stage 3 vs stage 1 data
    task_id              text NOT NULL REFERENCES fw.task_def,
    parent_release_id    text REFERENCES fw.release,
    split_plan_cfg_id    text REFERENCES fw.config_artifact,
    thresholds_cfg_id    text REFERENCES fw.config_artifact,
    -- Decision of question V3 that allows mixing embodiments (ADR-08)
    mixed_embodiment_decision_id text,
    status               text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'frozen')),
    manifest_sha256      text CHECK (manifest_sha256 ~ '^[0-9a-f]{64}$'),
    holdout_guard_passed boolean,                    -- answer of gate.holdout guard; DB never sees vault/
    combined_license     text,
    counts               jsonb NOT NULL DEFAULT '{}',
    frozen_at            timestamptz,
    frozen_by            uuid REFERENCES fw.app_user,
    created_by           uuid NOT NULL REFERENCES fw.app_user,
    created_at           timestamptz NOT NULL DEFAULT now(),
    site_id              text NOT NULL DEFAULT 'local',
    schema_version       text NOT NULL DEFAULT '1',
    meta                 jsonb NOT NULL DEFAULT '{}',
    CHECK (status = 'draft' OR (manifest_sha256 IS NOT NULL AND frozen_at IS NOT NULL
                                AND holdout_guard_passed IS TRUE AND combined_license IS NOT NULL))
);

CREATE TABLE fw.release_item (
    release_id     text NOT NULL REFERENCES fw.release,
    episode_id     text NOT NULL REFERENCES fw.episode,
    sample_weight  numeric(8, 4) NOT NULL DEFAULT 1 CHECK (sample_weight > 0),
    excluded       boolean NOT NULL DEFAULT false,
    exclude_reason text,
    PRIMARY KEY (release_id, episode_id),
    CHECK (NOT excluded OR exclude_reason IS NOT NULL)
);

ALTER TABLE fw.run_plan_branch ADD FOREIGN KEY (release_id) REFERENCES fw.release;

-- DatasetRef: a rebuildable export of a frozen release with one MixSpec.
CREATE TABLE fw.dataset_export (
    id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    release_id           text NOT NULL REFERENCES fw.release,
    format               text NOT NULL CHECK (format IN ('lerobot_v2_1', 'lerobot_v3', 'psi0_stage1')),
    mix_spec             jsonb NOT NULL,             -- {"teleop": 0.5, "synthetic_s1": 0.5}
    mix_hash             text NOT NULL,
    uri                  text,
    stats_uri            text,                       -- stats_psi0.json
    status               text NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'RUNNING', 'READY', 'FAILED')),
    contract_test_passed boolean,
    job_id               text REFERENCES fw.job,
    file_purged          boolean NOT NULL DEFAULT false,
    created_at           timestamptz NOT NULL DEFAULT now(),
    UNIQUE (release_id, format, mix_hash),
    CHECK (status <> 'READY' OR (contract_test_passed IS TRUE AND uri IS NOT NULL))
);

CREATE TABLE fw.dataset_report (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_id    uuid REFERENCES fw.ingest_batch,
    release_id  text REFERENCES fw.release,
    html_uri    text NOT NULL,
    stats       jsonb NOT NULL,
    job_id      text REFERENCES fw.job,
    created_at  timestamptz NOT NULL DEFAULT now(),
    CHECK ((batch_id IS NULL) <> (release_id IS NULL))
);

-- ---------------------------------------------------------------------------
-- 6. Training, checkpoints, probes
-- ---------------------------------------------------------------------------

CREATE TABLE fw.train_run (
    id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    run_plan_id          text NOT NULL REFERENCES fw.run_plan,
    branch               text NOT NULL,
    seed                 int NOT NULL,
    stage                smallint NOT NULL CHECK (stage IN (1, 3)),
    method               text NOT NULL CHECK (method IN ('psi0', 'act', 'dp')),
    export_id            uuid NOT NULL REFERENCES fw.dataset_export,
    parent_checkpoint_id text,                       -- FK added after fw.checkpoint
    round_id             uuid,                       -- FK added after fw.flywheel_round
    recipe_cfg_id        text REFERENCES fw.config_artifact,
    job_id               text REFERENCES fw.job,
    status               text NOT NULL DEFAULT 'QUEUED' CHECK (status IN ('QUEUED', 'TRAINING', 'TRAINED', 'FAILED', 'CANCELLED')),
    started_at           timestamptz,
    ended_at             timestamptz,
    created_at           timestamptz NOT NULL DEFAULT now(),
    hidden_at            timestamptz,
    hidden_by            uuid REFERENCES fw.app_user,
    hidden_reason        text,
    FOREIGN KEY (run_plan_id, branch) REFERENCES fw.run_plan_branch,
    CHECK ((hidden_at IS NULL) = (hidden_reason IS NULL))
);
CREATE UNIQUE INDEX train_run_unique_idx
    ON fw.train_run (run_plan_id, branch, seed, stage, COALESCE(round_id, '00000000-0000-0000-0000-000000000000'));

-- Long format: one row per (run, split, metric, step). Webhook resends are idempotent.
CREATE TABLE fw.train_metric (
    train_run_id uuid NOT NULL REFERENCES fw.train_run,
    split        text NOT NULL CHECK (split IN ('train', 'val', 'system')),
    name         text NOT NULL,                      -- loss, lr, grad_norm, loss/arm_left, gpu_util, ...
    step         int NOT NULL CHECK (step >= 0),
    value        double precision NOT NULL,
    recorded_at  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (train_run_id, split, name, step)
);

CREATE TABLE fw.checkpoint (
    id                   text PRIMARY KEY CHECK (id ~ '^ckpt_[0-9a-f]{16}$'),
    origin               text NOT NULL CHECK (origin IN ('upstream', 'trained')),
    train_run_id         uuid REFERENCES fw.train_run,
    source_id            text REFERENCES fw.source,  -- upstream psi-model checkpoints
    method               text NOT NULL CHECK (method IN ('psi0', 'act', 'dp')),
    branch               text,
    seed                 int,
    stage                smallint CHECK (stage IN (1, 2, 3)),
    step                 int CHECK (step >= 0),
    parent_checkpoint_id text REFERENCES fw.checkpoint,
    release_id           text REFERENCES fw.release,
    embodiment_id        text,
    weights_sha256       text NOT NULL CHECK (weights_sha256 ~ '^[0-9a-f]{64}$'),
    uri                  text NOT NULL,
    size_bytes           bigint CHECK (size_bytes >= 0),
    is_final             boolean NOT NULL DEFAULT false,  -- the checkpoint evaluated for its (branch, seed)
    file_purged          boolean NOT NULL DEFAULT false,
    purged_at            timestamptz,
    purge_reason         text,
    site_id              text NOT NULL DEFAULT 'local',
    schema_version       text NOT NULL DEFAULT '1',
    meta                 jsonb NOT NULL DEFAULT '{}',
    created_at           timestamptz NOT NULL DEFAULT now(),
    CHECK ((origin = 'upstream') = (source_id IS NOT NULL AND train_run_id IS NULL)),
    CHECK (file_purged = (purged_at IS NOT NULL)),
    CHECK (NOT file_purged OR purge_reason IS NOT NULL)
);

ALTER TABLE fw.train_run ADD FOREIGN KEY (parent_checkpoint_id) REFERENCES fw.checkpoint;

CREATE TABLE fw.probe_result (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    checkpoint_id    text NOT NULL REFERENCES fw.checkpoint,
    probe            text NOT NULL CHECK (probe IN ('P1', 'P2', 'P3', 'P4')),
    probe_set_cfg_id text NOT NULL REFERENCES fw.config_artifact,
    metrics          jsonb NOT NULL,
    report_uri       text,
    job_id           text REFERENCES fw.job,
    created_at       timestamptz NOT NULL DEFAULT now()
);

-- F-TRAIN and F-OFF detections (design 27/10 section 10; 09 gap G5).
CREATE TABLE fw.train_flag (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    train_run_id     uuid NOT NULL REFERENCES fw.train_run,
    checkpoint_id    text REFERENCES fw.checkpoint,
    code             text NOT NULL CHECK (code ~ '^(T[1-8]|O[1-4])$'),
    step             int,
    detector_version text NOT NULL,
    evidence         jsonb NOT NULL DEFAULT '{}',
    created_at       timestamptz NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- 7. Decisions and mutable pointers
-- ---------------------------------------------------------------------------

CREATE TABLE fw.decision (
    seq                    bigint GENERATED ALWAYS AS IDENTITY,
    id                     text PRIMARY KEY CHECK (id ~ '^dec_[0-9A-HJKMNP-TV-Z]{26}$'),
    -- stage_review, agent_report_review, v3_controller, scope_reduction are proposed additions (09 gap G4)
    kind                   text NOT NULL CHECK (kind IN ('plan_review', 'dev_gate', 'aa_test', 'holdout', 'milestone',
                                                         'repair_ticket', 'stage_review', 'agent_report_review',
                                                         'v3_controller', 'scope_reduction')),
    subject_kind           text NOT NULL,
    subject_id             text NOT NULL,
    run_plan_id            text REFERENCES fw.run_plan,
    verdict                text NOT NULL CHECK (verdict IN ('approved', 'overridden', 'rejected', 'pass', 'fail',
                                                            'open', 'closed', 'recorded')),
    metrics                jsonb NOT NULL DEFAULT '{}',
    criteria               jsonb NOT NULL DEFAULT '{}',
    signed_by              uuid NOT NULL REFERENCES fw.app_user,
    reason                 text NOT NULL CHECK (length(btrim(reason)) > 0),
    supersedes_decision_id text REFERENCES fw.decision,
    meta                   jsonb NOT NULL DEFAULT '{}',
    created_at             timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX decision_subject_idx ON fw.decision (subject_kind, subject_id, seq DESC);

ALTER TABLE fw.release ADD FOREIGN KEY (mixed_embodiment_decision_id) REFERENCES fw.decision;

CREATE TABLE fw.stage_review (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    stage_run_id uuid NOT NULL REFERENCES fw.stage_run,
    action       text NOT NULL CHECK (action IN ('RETRY_STAGE', 'APPLY_FIX_AND_RETRY', 'FORCE_CONTINUE', 'ABORT_PIPELINE')),
    params       jsonb NOT NULL DEFAULT '{}',
    note         text,
    decision_id  text NOT NULL REFERENCES fw.decision,
    reviewed_by  uuid NOT NULL REFERENCES fw.app_user,
    reviewed_at  timestamptz NOT NULL DEFAULT now(),
    CHECK (action <> 'FORCE_CONTINUE' OR length(btrim(coalesce(note, ''))) > 0),
    CHECK (action <> 'APPLY_FIX_AND_RETRY' OR params <> '{}'::jsonb)
);

CREATE TABLE fw.ref_pointer (
    name          text PRIMARY KEY CHECK (name ~ '^policy/[A-Za-z0-9_.]+/current$'),
    checkpoint_id text NOT NULL REFERENCES fw.checkpoint,
    decision_id   text NOT NULL REFERENCES fw.decision,
    updated_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE fw.ref_log (
    seq               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name              text NOT NULL,
    old_checkpoint_id text REFERENCES fw.checkpoint,
    new_checkpoint_id text NOT NULL REFERENCES fw.checkpoint,
    decision_id       text NOT NULL REFERENCES fw.decision,
    reason            text NOT NULL,
    created_at        timestamptz NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- 8. Closed-loop evaluation and scores
-- ---------------------------------------------------------------------------

CREATE TABLE fw.eval_run (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    run_plan_id         text NOT NULL REFERENCES fw.run_plan,
    purpose             text NOT NULL CHECK (purpose IN ('dev_find', 'gate_parent', 'gate_candidate', 'fix_rate_parent',
                                                         'fix_rate_candidate', 'aa_first', 'aa_second', 'he_eval',
                                                         'g0', 'tray_eval', 'hd')),
    checkpoint_id       text NOT NULL REFERENCES fw.checkpoint,
    condition_set_id    text NOT NULL REFERENCES fw.condition_set,
    round_id            uuid,                        -- FK added after fw.flywheel_round
    replicates          smallint NOT NULL DEFAULT 1 CHECK (replicates >= 1),
    timing              text NOT NULL CHECK (timing IN ('sync', 'async')),
    sim_mode            text NOT NULL CHECK (sim_mode IN ('mujoco', 'mujoco_isaac')),
    renderer            text NOT NULL CHECK (renderer IN ('mujoco', 'isaac')),
    latency_profile_uri text,
    scorer_cfg_id       text NOT NULL REFERENCES fw.config_artifact,
    job_id              text REFERENCES fw.job,
    status              text NOT NULL DEFAULT 'QUEUED' CHECK (status IN ('QUEUED', 'RUNNING', 'COMPLETED', 'FAILED', 'CANCELLED')),
    started_at          timestamptz,
    ended_at            timestamptz,
    created_at          timestamptz NOT NULL DEFAULT now(),
    hidden_at           timestamptz,
    hidden_by           uuid REFERENCES fw.app_user,
    hidden_reason       text,
    CHECK ((sim_mode = 'mujoco_isaac') = (renderer = 'isaac')),
    CHECK (timing = 'sync' OR latency_profile_uri IS NOT NULL),
    CHECK ((hidden_at IS NULL) = (hidden_reason IS NULL))
);

CREATE TABLE fw.score (
    id                text PRIMARY KEY CHECK (id ~ '^sc_[0-9a-f]{16}$'),
    episode_id        text NOT NULL REFERENCES fw.episode,
    scorer_version    text NOT NULL,
    scorer_cfg_id     text NOT NULL REFERENCES fw.config_artifact,
    success           boolean,                       -- NULL: unknown (missing signals)
    step_status       text[] NOT NULL,               -- passed, failed, not_attempted, unknown
    step_times        jsonb NOT NULL DEFAULT '{}',   -- t_in, t_out per step
    first_failed_step smallint,
    failure_kind      text,
    failure_class     text CHECK (failure_class IN ('approach', 'grasp', 'carry', 'place', 'balance')),
    level             smallint CHECK (level BETWEEN 0 AND 2),
    balance_violated  boolean NOT NULL DEFAULT false,
    meta              jsonb NOT NULL DEFAULT '{}',   -- tracking error per WBC group, latency p99, sync p99, missing signals
    created_at        timestamptz NOT NULL DEFAULT now(),
    UNIQUE (episode_id, scorer_version),
    CHECK (step_status <@ ARRAY['passed', 'failed', 'not_attempted', 'unknown']),
    CHECK ((success IS FALSE) = (failure_kind IS NOT NULL))
);

-- ---------------------------------------------------------------------------
-- 9. Failure -> Data rounds (spec section 6; 03 section 6.2)
-- ---------------------------------------------------------------------------

CREATE TABLE fw.round_step_def (
    step_no smallint PRIMARY KEY CHECK (step_no BETWEEN 1 AND 12),
    code    text NOT NULL UNIQUE,
    name    text NOT NULL
);

CREATE TABLE fw.flywheel_round (
    id                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    run_plan_id             text NOT NULL REFERENCES fw.run_plan,
    branch                  text NOT NULL,
    round_no                smallint NOT NULL CHECK (round_no >= 1),
    parent_checkpoint_id    text NOT NULL REFERENCES fw.checkpoint,
    diagnosis_enabled       boolean NOT NULL DEFAULT true,    -- false for B_fail
    budget_usd              numeric(12, 2) NOT NULL CHECK (budget_usd >= 0),
    find_eval_run_id        uuid REFERENCES fw.eval_run,
    child_release_id        text REFERENCES fw.release,
    candidate_checkpoint_id text REFERENCES fw.checkpoint,
    gate_decision_id        text REFERENCES fw.decision,
    promoted                boolean,
    status                  text NOT NULL DEFAULT 'FINDING'
                            CHECK (status IN ('FINDING', 'DIAGNOSING', 'PLANNING', 'AWAITING_REVIEW', 'ACQUIRING',
                                              'TRAINING', 'GATING', 'DONE', 'STOPPED', 'FAILED')),
    stop_reason             text CHECK (stop_reason IN ('budget_exhausted', 'low_gain', 'two_gate_failures',
                                                        'max_rounds', 'manual')),
    created_at              timestamptz NOT NULL DEFAULT now(),
    updated_at              timestamptz NOT NULL DEFAULT now(),
    UNIQUE (run_plan_id, branch, round_no),
    FOREIGN KEY (run_plan_id, branch) REFERENCES fw.run_plan_branch,
    CHECK ((status = 'STOPPED') = (stop_reason IS NOT NULL))
);

ALTER TABLE fw.train_run ADD FOREIGN KEY (round_id) REFERENCES fw.flywheel_round;
ALTER TABLE fw.eval_run ADD FOREIGN KEY (round_id) REFERENCES fw.flywheel_round;
ALTER TABLE fw.episode ADD FOREIGN KEY (eval_run_id) REFERENCES fw.eval_run;
ALTER TABLE fw.episode ADD FOREIGN KEY (checkpoint_id) REFERENCES fw.checkpoint;

CREATE TABLE fw.round_step (
    round_id   uuid NOT NULL REFERENCES fw.flywheel_round,
    step_no    smallint NOT NULL REFERENCES fw.round_step_def,
    status     text NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'RUNNING', 'DONE', 'SKIPPED', 'FAILED')),
    summary    jsonb NOT NULL DEFAULT '{}',
    started_at timestamptz,
    ended_at   timestamptz,
    PRIMARY KEY (round_id, step_no)
);

CREATE TABLE fw.cluster (
    id                text PRIMARY KEY CHECK (id ~ '^clu_[0-9a-f]{16}$'),
    round_id          uuid NOT NULL REFERENCES fw.flywheel_round,
    first_failed_step smallint NOT NULL,
    failure_kind      text NOT NULL,
    level             smallint NOT NULL CHECK (level BETWEEN 0 AND 2),
    parent_cluster_id text REFERENCES fw.cluster,   -- set when split by diagnosis
    representative_seed bigint,
    stage_hypothesis  jsonb,                         -- step 4b; shown on the card only
    card_uri          text,
    created_at        timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE fw.cluster_member (
    cluster_id        text NOT NULL REFERENCES fw.cluster,
    episode_id        text NOT NULL REFERENCES fw.episode,
    is_representative boolean NOT NULL DEFAULT false,
    PRIMARY KEY (cluster_id, episode_id)
);

CREATE TABLE fw.diagnostic_check (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    cluster_id          text NOT NULL REFERENCES fw.cluster,
    episode_id          text REFERENCES fw.episode,  -- representative; NULL for cluster-level checks
    check_no            smallint NOT NULL CHECK (check_no BETWEEN 1 AND 10),
    code                text NOT NULL CHECK (code IN ('missing_signal', 'sensor_sync', 'camera_ref', 'cmd_tracking',
                                                      'latency', 'train_domain', 'feasibility', 'localization',
                                                      'visual', 'coverage')),
    status              text NOT NULL CHECK (status IN ('ran', 'skipped')),
    value               double precision,
    threshold           double precision,
    positive            boolean,
    n_rollouts          int NOT NULL DEFAULT 0 CHECK (n_rollouts >= 0),
    rollout_episode_ids text[] NOT NULL DEFAULT '{}',
    approximate         boolean NOT NULL DEFAULT false,   -- e.g. feasibility from nearest demo when plan() is absent
    skip_reason         text,
    created_at          timestamptz NOT NULL DEFAULT now(),
    CHECK ((status = 'skipped') = (skip_reason IS NOT NULL)),
    CHECK (status = 'skipped' OR positive IS NOT NULL)
);

-- The 11 diagnoses of spec 6.9; engineer overrides append a new row with a reason.
CREATE TABLE fw.cluster_diagnosis (
    seq        bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    cluster_id text NOT NULL REFERENCES fw.cluster,
    diagnosis  text NOT NULL CHECK (diagnosis IN ('CHUA_RO', 'HE_THONG_CONTROLLER', 'HE_THONG_RUNTIME', 'HE_THONG_DONG_BO',
                                                 'HE_THONG_CALIBRATION', 'KHONG_KHA_THI', 'TRANG_THAI_DAU_XAU',
                                                 'NHAN_THUC', 'NGOAI_MIEN', 'THIEU_VUNG_PHU', 'KY_NANG_YEU')),
    decided_by text NOT NULL CHECK (decided_by IN ('machine', 'engineer')),
    engineer   uuid REFERENCES fw.app_user,
    reason     text,
    created_at timestamptz NOT NULL DEFAULT now(),
    CHECK (decided_by = 'machine' OR (engineer IS NOT NULL AND length(btrim(coalesce(reason, ''))) > 0))
);

-- Intervention catalogue with defaults of spec 6.10; quantities are per failure.
CREATE TABLE fw.intervention_type (
    code              text PRIMARY KEY CHECK (code IN ('sim_s1', 'sim_s2', 'sim_s3', 'sim_s4', 'teleop_correction', 'recovery')),
    per_failure_qty   int NOT NULL CHECK (per_failure_qty > 0),
    unit              text NOT NULL,
    max_failures_l_t  int NOT NULL CHECK (max_failures_l_t > 0),
    max_qty_per_cluster int NOT NULL CHECK (max_qty_per_cluster > 0),
    allowed_diagnoses text[] NOT NULL,
    enabled           boolean NOT NULL DEFAULT true,
    note              text
);

-- Proposals of steps 10-11. Immutable; the engineer's answer is in intervention_approval.
CREATE TABLE fw.intervention (
    id                    text PRIMARY KEY CHECK (id ~ '^iv_[0-9A-HJKMNP-TV-Z]{26}$'),
    round_id              uuid NOT NULL REFERENCES fw.flywheel_round,
    cluster_id            text REFERENCES fw.cluster,   -- NULL only for B_fail (no diagnosis)
    type                  text NOT NULL REFERENCES fw.intervention_type,
    n_failures            int NOT NULL CHECK (n_failures > 0),
    n_eff                 int NOT NULL CHECK (n_eff > 0),
    quantity              int NOT NULL CHECK (quantity > 0),
    gain_g                double precision NOT NULL CHECK (gain_g >= 0),
    cost_c_usd            numeric(12, 2) NOT NULL CHECK (cost_c_usd > 0),
    ratio_g_per_c         double precision GENERATED ALWAYS AS (gain_g / cost_c_usd::double precision) STORED,
    rank                  int NOT NULL CHECK (rank >= 1),
    selected_by_algorithm boolean NOT NULL,
    target_spec           jsonb NOT NULL DEFAULT '{}',  -- conditions, radius, start state, step k
    created_at            timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE fw.ingest_batch ADD FOREIGN KEY (origin_intervention_id) REFERENCES fw.intervention;
ALTER TABLE fw.episode ADD FOREIGN KEY (intervention_id) REFERENCES fw.intervention;

CREATE TABLE fw.intervention_approval (
    intervention_id text NOT NULL REFERENCES fw.intervention,
    decision_id     text NOT NULL REFERENCES fw.decision,
    approved        boolean NOT NULL,
    approved_qty    int CHECK (approved_qty > 0),
    override_reason text,
    PRIMARY KEY (intervention_id, decision_id),
    CHECK (approved = (approved_qty IS NOT NULL))
);

-- Operational follow-up of an approved intervention (web doc "data_collection_requests").
CREATE TABLE fw.intervention_task (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    intervention_id text NOT NULL REFERENCES fw.intervention,
    assignee_id     uuid REFERENCES fw.app_user,
    status          text NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN', 'IN_PROGRESS', 'FULFILLED', 'CANCELLED')),
    due_at          timestamptz,
    note            text,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE fw.fix_rate_event (
    id                    text PRIMARY KEY CHECK (id ~ '^fre_[0-9A-HJKMNP-TV-Z]{26}$'),
    round_id              uuid NOT NULL REFERENCES fw.flywheel_round,
    cluster_id            text REFERENCES fw.cluster,
    intervention_id       text NOT NULL REFERENCES fw.intervention,
    intervention_type     text NOT NULL REFERENCES fw.intervention_type,
    diagnosis             text,
    failure_kind          text NOT NULL,
    failure_class         text CHECK (failure_class IN ('approach', 'grasp', 'carry', 'place', 'balance')),
    task_family           text NOT NULL,
    n_conditions          int NOT NULL CHECK (n_conditions > 0),
    p_parent              numeric(6, 5) NOT NULL CHECK (p_parent BETWEEN 0 AND 1),
    p_candidate           numeric(6, 5) NOT NULL CHECK (p_candidate BETWEEN 0 AND 1),
    -- spec 6.13: fixed_j = round(n * (p_candidate - p_parent)) clamped to [0, n]
    fixed                 int GENERATED ALWAYS AS (
                              LEAST(GREATEST(round(n_conditions * (p_candidate - p_parent))::int, 0), n_conditions)
                          ) STORED,
    parent_eval_run_id    uuid NOT NULL REFERENCES fw.eval_run,
    candidate_eval_run_id uuid NOT NULL REFERENCES fw.eval_run,
    created_at            timestamptz NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- 10. Cost ledger (spec section 8; append-only, corrections by reversal)
-- ---------------------------------------------------------------------------

CREATE TABLE fw.price_rate (
    pricebook_cfg_id     text NOT NULL REFERENCES fw.config_artifact,
    resource_type        text NOT NULL CHECK (resource_type ~ '^[a-z0-9_]+$'),  -- operator_hour, gpu_hour_a100, ...
    unit                 text NOT NULL,
    usd_per_unit         numeric(12, 4) NOT NULL CHECK (usd_per_unit >= 0),
    human_hours_per_unit numeric(10, 4) NOT NULL DEFAULT 0 CHECK (human_hours_per_unit >= 0),
    is_assumption        boolean NOT NULL DEFAULT true,   -- docs/CLAUDE.md: unmeasured numbers are assumptions
    note                 text NOT NULL,
    PRIMARY KEY (pricebook_cfg_id, resource_type)
);

CREATE TABLE fw.ledger_entry (
    seq               bigint GENERATED ALWAYS AS IDENTITY,
    id                text PRIMARY KEY CHECK (id ~ '^led_[0-9A-HJKMNP-TV-Z]{26}$'),
    activity          text NOT NULL CHECK (activity IN ('data_download', 'teleop_session', 'data_generation', 'pipeline',
                                                        'qa', 'replay', 'export', 'train', 'probe', 'eval', 'diagnosis',
                                                        'agent_qa', 'holdout', 'storage', 'hd', 'review', 'other')),
    resource_type     text NOT NULL,
    quantity          numeric(14, 4) NOT NULL,
    unit              text NOT NULL,
    pricebook_cfg_id  text NOT NULL,
    usd_amount        numeric(14, 4) NOT NULL,
    human_hours       numeric(10, 4) NOT NULL DEFAULT 0,
    -- 03: estimate and measurement are separate records; neither overwrites the other
    measure_kind      text NOT NULL CHECK (measure_kind IN ('estimated', 'measured')),
    reverses_entry_id text REFERENCES fw.ledger_entry,
    branch            text,
    run_plan_id       text REFERENCES fw.run_plan,
    round_id          uuid REFERENCES fw.flywheel_round,
    cluster_id        text REFERENCES fw.cluster,
    intervention_id   text REFERENCES fw.intervention,
    job_id            text REFERENCES fw.job,
    batch_id          uuid REFERENCES fw.ingest_batch,
    train_run_id      uuid REFERENCES fw.train_run,
    eval_run_id       uuid REFERENCES fw.eval_run,
    person_code       text,
    note              text,
    created_at        timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (pricebook_cfg_id, resource_type) REFERENCES fw.price_rate,
    CHECK (num_nonnulls(run_plan_id, round_id, intervention_id, job_id, batch_id, train_run_id, eval_run_id) >= 1),
    CHECK (reverses_entry_id IS NOT NULL OR (quantity >= 0 AND usd_amount >= 0 AND human_hours >= 0))
);
CREATE INDEX ledger_run_plan_idx ON fw.ledger_entry (run_plan_id, branch);

-- ---------------------------------------------------------------------------
-- 11. Holdout: locks, seals, unsealed results. Conditions stay in vault/.
-- ---------------------------------------------------------------------------

CREATE TABLE fw.holdout_lock (
    checkpoint_id   text PRIMARY KEY REFERENCES fw.checkpoint,   -- one run per checkpoint
    run_plan_id     text NOT NULL REFERENCES fw.run_plan,
    protocol_sha256 text NOT NULL CHECK (protocol_sha256 ~ '^[0-9a-f]{64}$'),
    locked_at       timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE fw.holdout_seal (
    run_plan_id   text NOT NULL REFERENCES fw.run_plan,
    checkpoint_id text NOT NULL REFERENCES fw.holdout_lock,
    result_sha256 text NOT NULL CHECK (result_sha256 ~ '^[0-9a-f]{64}$'),
    sealed_at     timestamptz NOT NULL DEFAULT now(),
    unsealed_at   timestamptz,
    PRIMARY KEY (run_plan_id, checkpoint_id)
);

CREATE TABLE fw.holdout_result (
    run_plan_id     text NOT NULL REFERENCES fw.run_plan,
    checkpoint_id   text NOT NULL REFERENCES fw.holdout_lock,
    level           smallint NOT NULL CHECK (level BETWEEN 0 AND 2),
    n_conditions    int NOT NULL CHECK (n_conditions > 0),
    n_success       int NOT NULL CHECK (n_success >= 0),
    n_infra_retries int NOT NULL DEFAULT 0 CHECK (n_infra_retries >= 0),
    created_at      timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (run_plan_id, checkpoint_id, level),
    CHECK (n_success <= n_conditions)
);

-- ---------------------------------------------------------------------------
-- 12. Agent chat and notifications
-- ---------------------------------------------------------------------------

CREATE TABLE fw.chat_session (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       uuid NOT NULL REFERENCES fw.app_user,
    context_kind  text NOT NULL CHECK (context_kind IN ('GLOBAL', 'BATCH', 'STAGE_RUN', 'RELEASE', 'TRAIN_RUN',
                                                        'EVAL_RUN', 'ROUND', 'CLUSTER', 'LEDGER')),
    context_ref   text,
    title         text NOT NULL,
    created_at    timestamptz NOT NULL DEFAULT now(),
    hidden_at     timestamptz,
    hidden_reason text,
    CHECK ((context_kind = 'GLOBAL') = (context_ref IS NULL)),
    CHECK ((hidden_at IS NULL) = (hidden_reason IS NULL))
);

CREATE TABLE fw.chat_message (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id       uuid NOT NULL REFERENCES fw.chat_session,
    sender_role      text NOT NULL CHECK (sender_role IN ('USER', 'QA_QC_AGENT', 'FLYWHEEL_AGENT', 'SYSTEM')),
    sender_user_id   uuid REFERENCES fw.app_user,
    agent_model      text,
    text_content     text,
    attachments      jsonb NOT NULL DEFAULT '[]',
    context_snapshot jsonb,                          -- what the agent was shown, for audit
    created_at       timestamptz NOT NULL DEFAULT now(),
    CHECK ((sender_role = 'USER') = (sender_user_id IS NOT NULL)),
    CHECK (sender_role NOT IN ('QA_QC_AGENT', 'FLYWHEEL_AGENT') OR agent_model IS NOT NULL),
    CHECK (length(coalesce(text_content, '')) > 0 OR jsonb_array_length(attachments) > 0)
);

-- Agent-proposed actions. Kinds that select data, freeze, approve, train or touch the holdout are excluded:
-- the agent never chooses data or runs jobs on its own (design 27/10 section 9.1).
CREATE TABLE fw.chat_action (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id  uuid NOT NULL REFERENCES fw.chat_message,
    kind        text NOT NULL CHECK (kind IN ('stage_retry', 'stage_retry_with_params', 'rerun_agent_report',
                                              'open_artifact', 'draft_review_note')),
    payload     jsonb NOT NULL,
    status      text NOT NULL DEFAULT 'PROPOSED' CHECK (status IN ('PROPOSED', 'CONFIRMED', 'REJECTED', 'EXECUTED', 'FAILED')),
    decided_by  uuid REFERENCES fw.app_user,
    decided_at  timestamptz,
    job_id      text REFERENCES fw.job,
    result      jsonb,
    created_at  timestamptz NOT NULL DEFAULT now(),
    CHECK (status = 'PROPOSED' OR (decided_by IS NOT NULL AND decided_at IS NOT NULL))
);

CREATE TABLE fw.notification (
    id         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id    uuid REFERENCES fw.app_user,          -- NULL: whole team
    kind       text NOT NULL CHECK (kind IN ('STAGE_PAUSED', 'STAGE_FAILED', 'BATCH_READY', 'RELEASE_FROZEN',
                                             'TRAINING_DONE', 'TRAINING_FAILED', 'EVAL_DONE', 'ROUND_AWAITING_REVIEW',
                                             'ACTION_EXECUTED', 'TRAIN_FLAG')),
    ref_kind   text NOT NULL,
    ref_id     text NOT NULL,
    payload    jsonb NOT NULL DEFAULT '{}',
    created_at timestamptz NOT NULL DEFAULT now(),
    read_at    timestamptz
);

-- ---------------------------------------------------------------------------
-- 13. Sealed answer keys of injected defects (only role fw_grader reads them)
-- ---------------------------------------------------------------------------

CREATE TABLE fw_sealed.defect_manifest (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    injected_batch_id uuid NOT NULL UNIQUE REFERENCES fw.ingest_batch,
    sha256            text NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'),   -- locked before the agent runs
    created_at        timestamptz NOT NULL DEFAULT now(),
    revealed_at       timestamptz
);

CREATE TABLE fw_sealed.injected_defect (
    id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    manifest_id          uuid NOT NULL REFERENCES fw_sealed.defect_manifest,
    code                 text NOT NULL CHECK (code ~ '^(D[1-8]|T[1-8]|R[1-2])$'),
    target_kind          text NOT NULL CHECK (target_kind IN ('episode', 'train_log', 'rtc_log')),
    episode_id           text REFERENCES fw.episode,
    stage_no             smallint CHECK (stage_no BETWEEN 1 AND 4),
    frame_start          int,
    frame_end            int,
    params               jsonb NOT NULL DEFAULT '{}',
    expected_min_verdict text NOT NULL CHECK (expected_min_verdict IN ('WARNING', 'FAIL')),
    CHECK (target_kind <> 'episode' OR episode_id IS NOT NULL)
);

-- Grading rows written after reveal: did the code layer or the agent layer catch the defect?
CREATE TABLE fw_sealed.defect_match (
    defect_id    uuid NOT NULL REFERENCES fw_sealed.injected_defect,
    layer        text NOT NULL CHECK (layer IN ('code', 'agent')),
    detected     boolean NOT NULL,
    finding_id   uuid REFERENCES fw.agent_finding,
    qa_report_id text REFERENCES fw.qa_report,
    graded_at    timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (defect_id, layer),
    CHECK (NOT detected OR finding_id IS NOT NULL OR qa_report_id IS NOT NULL)
);

-- ---------------------------------------------------------------------------
-- 14. Status transitions
-- ---------------------------------------------------------------------------

INSERT INTO fw.status_transition (tbl, from_status, to_status) VALUES
    ('ingest_batch', 'INGESTED', 'PROCESSING'), ('ingest_batch', 'INGESTED', 'ABORTED'),
    ('ingest_batch', 'PROCESSING', 'PAUSED_FOR_REVIEW'), ('ingest_batch', 'PROCESSING', 'READY_FOR_RELEASE'),
    ('ingest_batch', 'PROCESSING', 'FAILED'), ('ingest_batch', 'PROCESSING', 'ABORTED'),
    ('ingest_batch', 'PAUSED_FOR_REVIEW', 'PROCESSING'), ('ingest_batch', 'PAUSED_FOR_REVIEW', 'READY_FOR_RELEASE'),
    ('ingest_batch', 'PAUSED_FOR_REVIEW', 'ABORTED'),
    ('ingest_batch', 'FAILED', 'PROCESSING'), ('ingest_batch', 'FAILED', 'ABORTED'),
    ('ingest_batch', 'READY_FOR_RELEASE', 'PROCESSING'),
    ('stage_run', 'PENDING', 'RUNNING'), ('stage_run', 'PENDING', 'ABORTED'), ('stage_run', 'PENDING', 'SUPERSEDED'),
    ('stage_run', 'RUNNING', 'AGENT_REVIEWING'), ('stage_run', 'RUNNING', 'PASSED'),
    ('stage_run', 'RUNNING', 'PAUSED_FOR_REVIEW'), ('stage_run', 'RUNNING', 'FAILED'), ('stage_run', 'RUNNING', 'ABORTED'),
    ('stage_run', 'AGENT_REVIEWING', 'PASSED'), ('stage_run', 'AGENT_REVIEWING', 'PAUSED_FOR_REVIEW'),
    ('stage_run', 'AGENT_REVIEWING', 'FAILED'), ('stage_run', 'AGENT_REVIEWING', 'ABORTED'),
    ('stage_run', 'PAUSED_FOR_REVIEW', 'OVERRIDDEN'), ('stage_run', 'PAUSED_FOR_REVIEW', 'ABORTED'),
    ('job', 'queued', 'running'), ('job', 'queued', 'cancelled'),
    ('job', 'running', 'succeeded'), ('job', 'running', 'failed'), ('job', 'running', 'cancelled'),
    ('dataset_export', 'PENDING', 'RUNNING'), ('dataset_export', 'RUNNING', 'READY'), ('dataset_export', 'RUNNING', 'FAILED'),
    ('train_run', 'QUEUED', 'TRAINING'), ('train_run', 'QUEUED', 'CANCELLED'),
    ('train_run', 'TRAINING', 'TRAINED'), ('train_run', 'TRAINING', 'FAILED'), ('train_run', 'TRAINING', 'CANCELLED'),
    ('eval_run', 'QUEUED', 'RUNNING'), ('eval_run', 'QUEUED', 'CANCELLED'),
    ('eval_run', 'RUNNING', 'COMPLETED'), ('eval_run', 'RUNNING', 'FAILED'), ('eval_run', 'RUNNING', 'CANCELLED'),
    ('flywheel_round', 'FINDING', 'DIAGNOSING'), ('flywheel_round', 'FINDING', 'PLANNING'),
    ('flywheel_round', 'DIAGNOSING', 'PLANNING'), ('flywheel_round', 'PLANNING', 'AWAITING_REVIEW'),
    ('flywheel_round', 'AWAITING_REVIEW', 'ACQUIRING'), ('flywheel_round', 'AWAITING_REVIEW', 'STOPPED'),
    ('flywheel_round', 'ACQUIRING', 'TRAINING'), ('flywheel_round', 'TRAINING', 'GATING'),
    ('flywheel_round', 'GATING', 'DONE'),
    ('round_step', 'PENDING', 'RUNNING'), ('round_step', 'PENDING', 'SKIPPED'),
    ('round_step', 'RUNNING', 'DONE'), ('round_step', 'RUNNING', 'FAILED'),
    ('intervention_task', 'OPEN', 'IN_PROGRESS'), ('intervention_task', 'OPEN', 'CANCELLED'),
    ('intervention_task', 'IN_PROGRESS', 'FULFILLED'), ('intervention_task', 'IN_PROGRESS', 'CANCELLED'),
    ('chat_action', 'PROPOSED', 'CONFIRMED'), ('chat_action', 'PROPOSED', 'REJECTED'),
    ('chat_action', 'CONFIRMED', 'EXECUTED'), ('chat_action', 'CONFIRMED', 'FAILED');

-- Any non-terminal round can fail or be stopped by hand.
INSERT INTO fw.status_transition (tbl, from_status, to_status)
SELECT 'flywheel_round', s, t
FROM unnest(ARRAY['FINDING', 'DIAGNOSING', 'PLANNING', 'ACQUIRING', 'TRAINING', 'GATING']) s,
     unnest(ARRAY['FAILED', 'STOPPED']) t
ON CONFLICT DO NOTHING;

-- ---------------------------------------------------------------------------
-- 15. Row rules (triggers)
-- ---------------------------------------------------------------------------

-- Episodes: lineage, batch consistency and the dev-split guard (03 section 8.3, point 3).
CREATE FUNCTION fw.tg_episode_insert() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    b fw.ingest_batch;
    c fw.condition;
    sr fw.stage_run;
    r fw.eval_run;
BEGIN
    IF NEW.batch_id IS NOT NULL THEN
        SELECT * INTO b FROM fw.ingest_batch WHERE id = NEW.batch_id;
        IF NEW.source_kind IS DISTINCT FROM b.source_kind OR NEW.data_class <> b.data_class
           OR NEW.synthetic_tier IS DISTINCT FROM b.synthetic_tier THEN
            RAISE EXCEPTION 'episode %: source_kind, synthetic_tier and data_class must match batch %', NEW.id, b.code
                USING ERRCODE = 'check_violation';
        END IF;
        NEW.is_injected_copy := b.injected_from_batch_id IS NOT NULL;
        IF NEW.created_by_stage_run_id IS NOT NULL THEN
            SELECT * INTO sr FROM fw.stage_run WHERE id = NEW.created_by_stage_run_id;
            IF sr.batch_id <> NEW.batch_id OR sr.stage_no <> 2 THEN
                RAISE EXCEPTION 'episode %: must be created by the NORMALIZE stage of its own batch', NEW.id
                    USING ERRCODE = 'check_violation';
            END IF;
        END IF;
    END IF;

    IF NEW.kind NOT IN ('eval_rollout', 'diag_rollout') AND NEW.condition_id IS NOT NULL THEN
        SELECT * INTO c FROM fw.condition WHERE id = NEW.condition_id;
        IF c.split = 'dev' THEN
            RAISE EXCEPTION 'episode %: training data on a dev condition is forbidden (holdout/dev leak guard)', NEW.id
                USING ERRCODE = 'check_violation';
        END IF;
        IF EXISTS (SELECT 1 FROM fw.condition d WHERE d.split = 'dev' AND d.layout_hash = c.layout_hash) THEN
            RAISE EXCEPTION 'episode %: layout_hash equals a dev condition', NEW.id USING ERRCODE = 'check_violation';
        END IF;
    END IF;

    IF NEW.eval_run_id IS NOT NULL THEN
        SELECT * INTO r FROM fw.eval_run WHERE id = NEW.eval_run_id;
        IF NEW.checkpoint_id <> r.checkpoint_id THEN
            RAISE EXCEPTION 'episode %: checkpoint differs from its eval run', NEW.id USING ERRCODE = 'check_violation';
        END IF;
        IF NEW.condition_id IS NULL OR NOT EXISTS (
            SELECT 1 FROM fw.condition_set_member m WHERE m.set_id = r.condition_set_id AND m.condition_id = NEW.condition_id
        ) THEN
            RAISE EXCEPTION 'episode %: condition is not in the eval run condition set', NEW.id
                USING ERRCODE = 'check_violation';
        END IF;
    END IF;

    IF NEW.kind = 'variant' AND NEW.parent_id IS NULL THEN
        RAISE EXCEPTION 'episode %: a variant must point to its parent episode', NEW.id USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END $$;

CREATE TRIGGER episode_insert BEFORE INSERT ON fw.episode FOR EACH ROW EXECUTE FUNCTION fw.tg_episode_insert();

-- Egocentric: annotation only after de-identification (CLAUDE.md invariant).
CREATE FUNCTION fw.tg_segment_insert() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF EXISTS (SELECT 1 FROM fw.episode e WHERE e.id = NEW.episode_id AND e.source_kind = 'egocentric')
       AND NOT EXISTS (SELECT 1 FROM fw.episode_deid d WHERE d.episode_id = NEW.episode_id) THEN
        RAISE EXCEPTION 'episode %: egocentric video must be de-identified before annotation', NEW.episode_id
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END $$;

CREATE TRIGGER segment_insert BEFORE INSERT ON fw.episode_segment FOR EACH ROW EXECUTE FUNCTION fw.tg_segment_insert();

CREATE FUNCTION fw.tg_deid_insert() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM fw.episode e WHERE e.id = NEW.episode_id AND e.source_kind = 'egocentric') THEN
        RAISE EXCEPTION 'episode %: de-identification applies to egocentric episodes only', NEW.episode_id
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END $$;

CREATE TRIGGER deid_insert BEFORE INSERT ON fw.episode_deid FOR EACH ROW EXECUTE FUNCTION fw.tg_deid_insert();

CREATE FUNCTION fw.tg_qa_report_insert() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.stage_run_id IS NOT NULL
       AND (SELECT stage_no FROM fw.stage_run WHERE id = NEW.stage_run_id) <> 4 THEN
        RAISE EXCEPTION 'qa_report %: must belong to stage 4 (QA)', NEW.id USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END $$;

CREATE TRIGGER qa_report_insert BEFORE INSERT ON fw.qa_report FOR EACH ROW EXECUTE FUNCTION fw.tg_qa_report_insert();

-- Batch creation lays out the four batch stages as PENDING attempts.
CREATE FUNCTION fw.tg_batch_after_insert() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    INSERT INTO fw.stage_run (batch_id, stage_no, attempt_no)
    SELECT NEW.id, s, 1 FROM generate_series(1, 4) s;
    RETURN NEW;
END $$;

CREATE TRIGGER batch_after_insert AFTER INSERT ON fw.ingest_batch FOR EACH ROW EXECUTE FUNCTION fw.tg_batch_after_insert();

-- Releases: frozen means read-only; items change only while draft.
CREATE FUNCTION fw.tg_release_update() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF OLD.status = 'frozen' THEN
        RAISE EXCEPTION 'release % is frozen; create a child release instead', OLD.id USING ERRCODE = 'restrict_violation';
    END IF;
    RETURN NEW;
END $$;

CREATE TRIGGER release_update BEFORE UPDATE ON fw.release FOR EACH ROW EXECUTE FUNCTION fw.tg_release_update();

CREATE FUNCTION fw.tg_release_item_change() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    rel_id text := COALESCE(NEW.release_id, OLD.release_id);
BEGIN
    IF (SELECT status FROM fw.release WHERE id = rel_id) = 'frozen' THEN
        RAISE EXCEPTION 'release % is frozen; its manifest cannot change', rel_id USING ERRCODE = 'restrict_violation';
    END IF;
    IF TG_OP = 'INSERT' AND EXISTS (
        SELECT 1 FROM fw.episode e WHERE e.id = NEW.episode_id AND e.kind IN ('eval_rollout', 'diag_rollout')
    ) THEN
        RAISE EXCEPTION 'episode %: evaluation traces never enter a training release', NEW.episode_id
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN COALESCE(NEW, OLD);
END $$;

CREATE TRIGGER release_item_change BEFORE INSERT OR UPDATE OR DELETE ON fw.release_item
    FOR EACH ROW EXECUTE FUNCTION fw.tg_release_item_change();

CREATE FUNCTION fw.tg_run_plan_update() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF OLD.status = 'frozen' THEN
        RAISE EXCEPTION 'run plan % is frozen', OLD.id USING ERRCODE = 'restrict_violation';
    END IF;
    RETURN NEW;
END $$;

CREATE TRIGGER run_plan_update BEFORE UPDATE ON fw.run_plan FOR EACH ROW EXECUTE FUNCTION fw.tg_run_plan_update();

CREATE FUNCTION fw.tg_run_plan_children() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF (SELECT status FROM fw.run_plan WHERE id = COALESCE(NEW.run_plan_id, OLD.run_plan_id)) = 'frozen' THEN
        RAISE EXCEPTION 'run plan % is frozen', COALESCE(NEW.run_plan_id, OLD.run_plan_id)
            USING ERRCODE = 'restrict_violation';
    END IF;
    RETURN COALESCE(NEW, OLD);
END $$;

CREATE TRIGGER run_plan_branch_change BEFORE INSERT OR UPDATE OR DELETE ON fw.run_plan_branch
    FOR EACH ROW EXECUTE FUNCTION fw.tg_run_plan_children();
CREATE TRIGGER run_plan_comparison_change BEFORE INSERT OR UPDATE OR DELETE ON fw.run_plan_comparison
    FOR EACH ROW EXECUTE FUNCTION fw.tg_run_plan_children();

-- Jobs: GPU jobs and experiment jobs need a frozen run plan and a GPU-enabled requester.
CREATE FUNCTION fw.tg_job_insert() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.uses_gpu AND NOT (SELECT can_run_gpu_jobs FROM fw.app_user WHERE id = NEW.requested_by) THEN
        RAISE EXCEPTION 'job %: requester may not start GPU jobs', NEW.id USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF NEW.kind IN ('train', 'eval', 'holdout', 'generate', 'probe')
       AND (SELECT status FROM fw.run_plan WHERE id = NEW.run_plan_id) IS DISTINCT FROM 'frozen' THEN
        RAISE EXCEPTION 'job %: % jobs run only from a frozen run plan', NEW.id, NEW.kind USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END $$;

CREATE TRIGGER job_insert BEFORE INSERT ON fw.job FOR EACH ROW EXECUTE FUNCTION fw.tg_job_insert();

-- Exports: only of frozen releases; stage-1 format only for egocentric releases; MixSpec weights sum to 1.
CREATE FUNCTION fw.tg_export_insert() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    rel fw.release;
    total numeric;
    bad_key text;
BEGIN
    SELECT * INTO rel FROM fw.release WHERE id = NEW.release_id;
    IF rel.status <> 'frozen' THEN
        RAISE EXCEPTION 'export: release % is not frozen', rel.id USING ERRCODE = 'check_violation';
    END IF;
    IF (NEW.format = 'psi0_stage1') <> (rel.kind = 'egocentric') THEN
        RAISE EXCEPTION 'export: format % does not fit a % release', NEW.format, rel.kind USING ERRCODE = 'check_violation';
    END IF;
    IF jsonb_typeof(NEW.mix_spec) <> 'object' OR NEW.mix_spec = '{}'::jsonb THEN
        RAISE EXCEPTION 'export: mix_spec must be a non-empty object of weights' USING ERRCODE = 'check_violation';
    END IF;
    SELECT sum(value::numeric) INTO total FROM jsonb_each_text(NEW.mix_spec);
    IF abs(total - 1) > 0.000001 OR EXISTS (SELECT 1 FROM jsonb_each_text(NEW.mix_spec) WHERE value::numeric <= 0) THEN
        RAISE EXCEPTION 'export: mix_spec weights must be positive and sum to 1 (got %)', total
            USING ERRCODE = 'check_violation';
    END IF;
    SELECT k INTO bad_key FROM jsonb_object_keys(NEW.mix_spec) k
    WHERE NOT EXISTS (
        SELECT 1 FROM fw.release_item i JOIN fw.episode e ON e.id = i.episode_id
        WHERE i.release_id = rel.id AND NOT i.excluded
          AND k = CASE WHEN e.source_kind = 'synthetic' THEN 'synthetic_' || lower(e.synthetic_tier) ELSE e.source_kind END
    ) LIMIT 1;
    IF bad_key IS NOT NULL THEN
        RAISE EXCEPTION 'export: mix_spec group % has no episode in release %', bad_key, rel.id
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END $$;

CREATE TRIGGER export_insert BEFORE INSERT ON fw.dataset_export FOR EACH ROW EXECUTE FUNCTION fw.tg_export_insert();

-- Training: stage 3 reads robot data, stage 1 reads egocentric data (spec 2.5); branch data must match the plan.
CREATE FUNCTION fw.tg_train_run_insert() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    ex fw.dataset_export;
    planned_release text;
BEGIN
    SELECT * INTO ex FROM fw.dataset_export WHERE id = NEW.export_id;
    IF ex.status <> 'READY' THEN
        RAISE EXCEPTION 'train run: export % is not READY', ex.id USING ERRCODE = 'check_violation';
    END IF;
    IF (NEW.stage = 1) <> (ex.format = 'psi0_stage1') THEN
        RAISE EXCEPTION 'train run: stage % cannot read format % (egocentric only feeds stage 1)', NEW.stage, ex.format
            USING ERRCODE = 'check_violation';
    END IF;
    SELECT release_id INTO planned_release FROM fw.run_plan_branch WHERE run_plan_id = NEW.run_plan_id AND branch = NEW.branch;
    IF planned_release IS NOT NULL AND planned_release <> ex.release_id AND NEW.round_id IS NULL THEN
        RAISE EXCEPTION 'train run: branch % is declared on release %, export is of %', NEW.branch, planned_release, ex.release_id
            USING ERRCODE = 'check_violation';
    END IF;
    IF (SELECT status FROM fw.run_plan WHERE id = NEW.run_plan_id) <> 'frozen' THEN
        RAISE EXCEPTION 'train run: run plan % is not frozen', NEW.run_plan_id USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END $$;

CREATE TRIGGER train_run_insert BEFORE INSERT ON fw.train_run FOR EACH ROW EXECUTE FUNCTION fw.tg_train_run_insert();

CREATE FUNCTION fw.tg_score_insert() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    ep fw.episode;
    t fw.task_def;
    def_class text;
    has_def boolean;
BEGIN
    SELECT * INTO ep FROM fw.episode WHERE id = NEW.episode_id;
    IF ep.source_kind = 'egocentric' THEN
        RAISE EXCEPTION 'score: egocentric episodes have no robot signals to score' USING ERRCODE = 'check_violation';
    END IF;
    SELECT * INTO t FROM fw.task_def WHERE task_id = ep.task_id;
    IF cardinality(NEW.step_status) <> t.n_steps THEN
        RAISE EXCEPTION 'score: task % has % steps, got %', t.task_id, t.n_steps, cardinality(NEW.step_status)
            USING ERRCODE = 'check_violation';
    END IF;
    IF NEW.failure_kind IS NOT NULL THEN
        SELECT true, failure_class INTO has_def, def_class
        FROM fw.failure_kind_def WHERE task_id = ep.task_id AND code = NEW.failure_kind;
        IF has_def IS NULL THEN
            RAISE EXCEPTION 'score: unknown failure kind % for task %', NEW.failure_kind, ep.task_id
                USING ERRCODE = 'check_violation';
        END IF;
        IF def_class IS NULL AND NEW.failure_kind <> 'L-UNKNOWN' THEN
            SELECT failure_class INTO def_class FROM fw.task_step_class
            WHERE task_id = ep.task_id AND step_no = NEW.first_failed_step;
        END IF;
        IF NEW.failure_class IS DISTINCT FROM def_class THEN
            RAISE EXCEPTION 'score: failure class of % must be %', NEW.failure_kind, coalesce(def_class, 'NULL')
                USING ERRCODE = 'check_violation';
        END IF;
    END IF;
    RETURN NEW;
END $$;

CREATE TRIGGER score_insert BEFORE INSERT ON fw.score FOR EACH ROW EXECUTE FUNCTION fw.tg_score_insert();

-- Diagnosis is blind to the holdout and works on dev traces only (03 section 8.3, point 5).
CREATE FUNCTION fw.tg_cluster_member_insert() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM fw.episode e
        WHERE e.id = NEW.episode_id AND e.kind = 'eval_rollout' AND e.split = 'dev'
          AND e.infra_status = 'ok' AND e.sim_success IS FALSE
    ) THEN
        RAISE EXCEPTION 'cluster member %: must be a failed dev eval rollout without infrastructure error', NEW.episode_id
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END $$;

CREATE TRIGGER cluster_member_insert BEFORE INSERT ON fw.cluster_member
    FOR EACH ROW EXECUTE FUNCTION fw.tg_cluster_member_insert();

CREATE FUNCTION fw.tg_round_insert() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF (SELECT purpose FROM fw.run_plan WHERE id = NEW.run_plan_id) <> 'round' THEN
        RAISE EXCEPTION 'round: run plan % is not a round plan', NEW.run_plan_id USING ERRCODE = 'check_violation';
    END IF;
    IF (SELECT status FROM fw.run_plan WHERE id = NEW.run_plan_id) <> 'frozen' THEN
        RAISE EXCEPTION 'round: run plan % is not frozen', NEW.run_plan_id USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END $$;

CREATE TRIGGER round_insert BEFORE INSERT ON fw.flywheel_round FOR EACH ROW EXECUTE FUNCTION fw.tg_round_insert();

CREATE FUNCTION fw.tg_round_after_insert() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    INSERT INTO fw.round_step (round_id, step_no) SELECT NEW.id, step_no FROM fw.round_step_def;
    RETURN NEW;
END $$;

CREATE TRIGGER round_after_insert AFTER INSERT ON fw.flywheel_round
    FOR EACH ROW EXECUTE FUNCTION fw.tg_round_after_insert();

-- Proposals respect the decision table (spec 6.9) and n_eff = min(m_j, L_t) (spec 6.10).
CREATE FUNCTION fw.tg_intervention_insert() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    it fw.intervention_type;
    rnd fw.flywheel_round;
    diag text;
BEGIN
    SELECT * INTO it FROM fw.intervention_type WHERE code = NEW.type;
    SELECT * INTO rnd FROM fw.flywheel_round WHERE id = NEW.round_id;
    IF NOT it.enabled THEN
        RAISE EXCEPTION 'intervention: type % is not enabled', it.code USING ERRCODE = 'check_violation';
    END IF;
    IF NEW.n_eff <> LEAST(NEW.n_failures, it.max_failures_l_t) THEN
        RAISE EXCEPTION 'intervention: n_eff must be min(m_j = %, L_t = %)', NEW.n_failures, it.max_failures_l_t
            USING ERRCODE = 'check_violation';
    END IF;
    IF NEW.quantity > LEAST(NEW.n_eff * it.per_failure_qty, it.max_qty_per_cluster) THEN
        RAISE EXCEPTION 'intervention: quantity % exceeds the per-cluster cap of %', NEW.quantity, it.code
            USING ERRCODE = 'check_violation';
    END IF;
    IF rnd.diagnosis_enabled THEN
        IF NEW.cluster_id IS NULL THEN
            RAISE EXCEPTION 'intervention: a cluster is required when diagnosis is on' USING ERRCODE = 'check_violation';
        END IF;
        SELECT diagnosis INTO diag FROM fw.cluster_diagnosis
        WHERE cluster_id = NEW.cluster_id ORDER BY seq DESC LIMIT 1;
        IF diag IS NULL OR NOT diag = ANY (it.allowed_diagnoses) THEN
            RAISE EXCEPTION 'intervention: % is not allowed for diagnosis %', it.code, coalesce(diag, 'NONE')
                USING ERRCODE = 'check_violation';
        END IF;
    ELSIF NEW.type NOT LIKE 'sim_%' THEN
        RAISE EXCEPTION 'intervention: without diagnosis (B_fail) only simulation around failures is allowed'
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END $$;

CREATE TRIGGER intervention_insert BEFORE INSERT ON fw.intervention
    FOR EACH ROW EXECUTE FUNCTION fw.tg_intervention_insert();

-- Ledger reversals mirror the original exactly with opposite sign.
CREATE FUNCTION fw.tg_ledger_insert() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    orig fw.ledger_entry;
BEGIN
    IF NEW.reverses_entry_id IS NOT NULL THEN
        SELECT * INTO orig FROM fw.ledger_entry WHERE id = NEW.reverses_entry_id;
        IF orig.reverses_entry_id IS NOT NULL THEN
            RAISE EXCEPTION 'ledger: a reversal cannot be reversed' USING ERRCODE = 'check_violation';
        END IF;
        IF EXISTS (SELECT 1 FROM fw.ledger_entry WHERE reverses_entry_id = orig.id) THEN
            RAISE EXCEPTION 'ledger: entry % is already reversed', orig.id USING ERRCODE = 'check_violation';
        END IF;
        IF NEW.quantity <> -orig.quantity OR NEW.usd_amount <> -orig.usd_amount OR NEW.human_hours <> -orig.human_hours
           OR NEW.measure_kind <> orig.measure_kind OR NEW.resource_type <> orig.resource_type THEN
            RAISE EXCEPTION 'ledger: reversal of % must negate quantity, usd_amount and human_hours of the same kind', orig.id
                USING ERRCODE = 'check_violation';
        END IF;
        IF NEW.note IS NULL THEN
            RAISE EXCEPTION 'ledger: a reversal needs a note' USING ERRCODE = 'check_violation';
        END IF;
    END IF;
    RETURN NEW;
END $$;

CREATE TRIGGER ledger_insert BEFORE INSERT ON fw.ledger_entry FOR EACH ROW EXECUTE FUNCTION fw.tg_ledger_insert();

CREATE FUNCTION fw.tg_holdout_result_insert() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM fw.holdout_seal s
        WHERE s.run_plan_id = NEW.run_plan_id AND s.checkpoint_id = NEW.checkpoint_id AND s.unsealed_at IS NOT NULL
    ) THEN
        RAISE EXCEPTION 'holdout result for % is still sealed', NEW.checkpoint_id USING ERRCODE = 'insufficient_privilege';
    END IF;
    RETURN NEW;
END $$;

CREATE TRIGGER holdout_result_insert BEFORE INSERT ON fw.holdout_result
    FOR EACH ROW EXECUTE FUNCTION fw.tg_holdout_result_insert();

CREATE FUNCTION fw.tg_chat_action_insert() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF (SELECT sender_role FROM fw.chat_message WHERE id = NEW.message_id) NOT IN ('QA_QC_AGENT', 'FLYWHEEL_AGENT') THEN
        RAISE EXCEPTION 'chat action: only an agent message can propose an action' USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END $$;

CREATE TRIGGER chat_action_insert BEFORE INSERT ON fw.chat_action FOR EACH ROW EXECUTE FUNCTION fw.tg_chat_action_insert();

CREATE FUNCTION fw.tg_checkpoint_update() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.file_purged AND NOT OLD.file_purged AND NOT fw.checkpoint_purgeable(OLD.id) THEN
        RAISE EXCEPTION 'checkpoint % is still needed (final, upstream, referenced or locked)', OLD.id
            USING ERRCODE = 'restrict_violation';
    END IF;
    IF OLD.file_purged AND NOT NEW.file_purged THEN
        RAISE EXCEPTION 'checkpoint %: a purged file cannot be un-purged', OLD.id USING ERRCODE = 'restrict_violation';
    END IF;
    RETURN NEW;
END $$;

-- ---------------------------------------------------------------------------
-- 16. Domain functions called by the backend
-- ---------------------------------------------------------------------------

-- Retention: which checkpoint files may be deleted from storage. The row always stays.
CREATE FUNCTION fw.checkpoint_purgeable(p_checkpoint text) RETURNS boolean
LANGUAGE sql STABLE AS $$
    SELECT c.origin = 'trained'
       AND NOT c.is_final
       AND NOT EXISTS (SELECT 1 FROM fw.eval_run r WHERE r.checkpoint_id = c.id)
       AND NOT EXISTS (SELECT 1 FROM fw.holdout_lock h WHERE h.checkpoint_id = c.id)
       AND NOT EXISTS (SELECT 1 FROM fw.ref_pointer p WHERE p.checkpoint_id = c.id)
       AND NOT EXISTS (SELECT 1 FROM fw.checkpoint k WHERE k.parent_checkpoint_id = c.id)
       AND NOT EXISTS (SELECT 1 FROM fw.train_run t WHERE t.parent_checkpoint_id = c.id)
       AND NOT EXISTS (SELECT 1 FROM fw.flywheel_round f
                       WHERE c.id IN (f.parent_checkpoint_id, f.candidate_checkpoint_id))
    FROM fw.checkpoint c WHERE c.id = p_checkpoint
$$;

-- When a finished batch stage must stop for a human (web doc BR-02; design 27/10 section 9.1).
-- code_verdict comes from deterministic checks; agent_verdict is the QA/QC agent's reading of the report.
CREATE FUNCTION fw.stage_needs_review(
    p_code_verdict text, p_agent_verdict text, p_force_manual_review boolean
) RETURNS boolean
LANGUAGE sql IMMUTABLE AS $$
    SELECT p_force_manual_review
        OR p_code_verdict IS DISTINCT FROM 'PASS'
        OR p_agent_verdict IN ('WARNING', 'FAIL')
$$;

CREATE FUNCTION fw.notify(p_kind text, p_ref_kind text, p_ref_id text, p_payload jsonb DEFAULT '{}')
RETURNS void LANGUAGE sql AS $$
    INSERT INTO fw.notification (kind, ref_kind, ref_id, payload) VALUES (p_kind, p_ref_kind, p_ref_id, p_payload)
$$;

CREATE FUNCTION fw.stage_start(p_stage_run uuid, p_job text) RETURNS void
LANGUAGE plpgsql AS $$
DECLARE
    sr fw.stage_run;
BEGIN
    SELECT * INTO sr FROM fw.stage_run WHERE id = p_stage_run FOR UPDATE;
    IF NOT sr.is_current THEN
        RAISE EXCEPTION 'stage run % is not the current attempt', p_stage_run USING ERRCODE = 'check_violation';
    END IF;
    IF sr.stage_no > 1 AND NOT EXISTS (
        SELECT 1 FROM fw.stage_run p
        WHERE p.batch_id = sr.batch_id AND p.stage_no = sr.stage_no - 1 AND p.is_current
          AND p.status IN ('PASSED', 'OVERRIDDEN')
    ) THEN
        RAISE EXCEPTION 'stage %: previous stage has not passed', sr.stage_no USING ERRCODE = 'check_violation';
    END IF;
    UPDATE fw.stage_run SET status = 'RUNNING', job_id = p_job, started_at = now() WHERE id = p_stage_run;
    UPDATE fw.ingest_batch SET status = 'PROCESSING', current_stage = sr.stage_no WHERE id = sr.batch_id;
END $$;

CREATE FUNCTION fw._stage_resolve(p_stage_run uuid) RETURNS text
LANGUAGE plpgsql AS $$
DECLARE
    sr fw.stage_run;
    b fw.ingest_batch;
    agent_verdict text;
BEGIN
    SELECT * INTO sr FROM fw.stage_run WHERE id = p_stage_run FOR UPDATE;
    SELECT * INTO b FROM fw.ingest_batch WHERE id = sr.batch_id FOR UPDATE;
    SELECT verdict INTO agent_verdict FROM fw.agent_report WHERE id = sr.agent_report_id;
    IF fw.stage_needs_review(sr.code_verdict, agent_verdict, b.force_manual_review) THEN
        UPDATE fw.stage_run SET status = 'PAUSED_FOR_REVIEW', ended_at = now() WHERE id = sr.id;
        UPDATE fw.ingest_batch SET status = 'PAUSED_FOR_REVIEW' WHERE id = b.id;
        PERFORM fw.notify('STAGE_PAUSED', 'stage_run', sr.id::text,
                          jsonb_build_object('batch', b.code, 'stage', sr.stage_no,
                                             'code_verdict', sr.code_verdict, 'agent_verdict', agent_verdict));
        RETURN 'PAUSED_FOR_REVIEW';
    END IF;
    UPDATE fw.stage_run SET status = 'PASSED', ended_at = now() WHERE id = sr.id;
    PERFORM fw._batch_after_stage_ok(sr.batch_id, sr.stage_no);
    RETURN 'PASSED';
END $$;

CREATE FUNCTION fw._batch_after_stage_ok(p_batch uuid, p_stage smallint) RETURNS void
LANGUAGE plpgsql AS $$
BEGIN
    IF p_stage = 4 THEN
        UPDATE fw.ingest_batch SET status = 'READY_FOR_RELEASE' WHERE id = p_batch;
        PERFORM fw.notify('BATCH_READY', 'ingest_batch', p_batch::text);
    ELSE
        UPDATE fw.ingest_batch SET status = 'PROCESSING' WHERE id = p_batch AND status <> 'PROCESSING';
    END IF;
END $$;

-- Worker reports the end of a stage. Without an agent report the stage waits in AGENT_REVIEWING.
CREATE FUNCTION fw.stage_finish(
    p_stage_run uuid, p_code_verdict text, p_stats jsonb, p_output_uri text, p_log_uri text,
    p_agent_report uuid DEFAULT NULL
) RETURNS text
LANGUAGE plpgsql AS $$
BEGIN
    UPDATE fw.stage_run
    SET code_verdict = p_code_verdict, stats = p_stats, output_uri = p_output_uri, log_uri = p_log_uri,
        agent_report_id = p_agent_report,
        status = CASE WHEN p_agent_report IS NULL THEN 'AGENT_REVIEWING' ELSE status END
    WHERE id = p_stage_run;
    IF p_agent_report IS NULL THEN
        RETURN 'AGENT_REVIEWING';
    END IF;
    RETURN fw._stage_resolve(p_stage_run);
END $$;

CREATE FUNCTION fw.stage_attach_agent_report(p_stage_run uuid, p_agent_report uuid) RETURNS text
LANGUAGE plpgsql AS $$
BEGIN
    UPDATE fw.stage_run SET agent_report_id = p_agent_report WHERE id = p_stage_run AND status = 'AGENT_REVIEWING';
    IF NOT FOUND THEN
        RAISE EXCEPTION 'stage run % is not waiting for an agent report', p_stage_run USING ERRCODE = 'check_violation';
    END IF;
    RETURN fw._stage_resolve(p_stage_run);
END $$;

CREATE FUNCTION fw.stage_fail(p_stage_run uuid, p_error text) RETURNS void
LANGUAGE plpgsql AS $$
DECLARE
    sr fw.stage_run;
BEGIN
    UPDATE fw.stage_run SET status = 'FAILED', error_message = p_error, ended_at = now()
    WHERE id = p_stage_run RETURNING * INTO sr;
    UPDATE fw.ingest_batch SET status = 'FAILED' WHERE id = sr.batch_id;
    PERFORM fw.notify('STAGE_FAILED', 'stage_run', sr.id::text, jsonb_build_object('error', p_error));
END $$;

-- New attempts from stage k to 4. Old attempts and the episodes they created stay untouched,
-- so frozen releases built on them remain reproducible.
CREATE FUNCTION fw.stage_retry_from(p_batch uuid, p_stage smallint, p_params jsonb DEFAULT '{}') RETURNS void
LANGUAGE plpgsql AS $$
BEGIN
    IF (SELECT status FROM fw.ingest_batch WHERE id = p_batch) = 'ABORTED' THEN
        RAISE EXCEPTION 'batch % is aborted', p_batch USING ERRCODE = 'check_violation';
    END IF;
    UPDATE fw.stage_run SET status = 'SUPERSEDED' WHERE batch_id = p_batch AND stage_no >= p_stage
        AND is_current AND status = 'PENDING';
    UPDATE fw.stage_run SET is_current = false WHERE batch_id = p_batch AND stage_no >= p_stage AND is_current;
    INSERT INTO fw.stage_run (batch_id, stage_no, attempt_no, params)
    SELECT p_batch, s,
           (SELECT coalesce(max(attempt_no), 0) + 1 FROM fw.stage_run WHERE batch_id = p_batch AND stage_no = s),
           CASE WHEN s = p_stage THEN p_params ELSE '{}'::jsonb END
    FROM generate_series(p_stage, 4) s;
    UPDATE fw.ingest_batch SET status = 'PROCESSING', current_stage = p_stage WHERE id = p_batch;
END $$;

-- The four hop actions of the web doc, each recorded as a Decision.
CREATE FUNCTION fw.stage_review(
    p_stage_run uuid, p_action text, p_user uuid, p_note text, p_params jsonb DEFAULT '{}'
) RETURNS text
LANGUAGE plpgsql AS $$
DECLARE
    sr fw.stage_run;
    dec_id text := fw.new_id('dec');
BEGIN
    SELECT * INTO sr FROM fw.stage_run WHERE id = p_stage_run FOR UPDATE;
    IF sr.status NOT IN ('PAUSED_FOR_REVIEW', 'FAILED') OR NOT sr.is_current THEN
        RAISE EXCEPTION 'stage run % is not waiting for review', p_stage_run USING ERRCODE = 'check_violation';
    END IF;
    IF p_action = 'FORCE_CONTINUE' AND sr.status = 'FAILED' THEN
        RAISE EXCEPTION 'a failed stage has no output to continue with' USING ERRCODE = 'check_violation';
    END IF;
    INSERT INTO fw.decision (id, kind, subject_kind, subject_id, verdict, signed_by, reason, meta)
    VALUES (dec_id, 'stage_review', 'stage_run', sr.id::text,
            CASE p_action WHEN 'FORCE_CONTINUE' THEN 'overridden' WHEN 'ABORT_PIPELINE' THEN 'rejected' ELSE 'recorded' END,
            p_user, coalesce(nullif(btrim(p_note), ''), p_action),
            jsonb_build_object('action', p_action, 'params', p_params));
    INSERT INTO fw.stage_review (stage_run_id, action, params, note, decision_id, reviewed_by)
    VALUES (sr.id, p_action, p_params, p_note, dec_id, p_user);

    CASE p_action
        WHEN 'FORCE_CONTINUE' THEN
            UPDATE fw.stage_run SET status = 'OVERRIDDEN' WHERE id = sr.id;
            PERFORM fw._batch_after_stage_ok(sr.batch_id, sr.stage_no);
        WHEN 'ABORT_PIPELINE' THEN
            IF sr.status = 'PAUSED_FOR_REVIEW' THEN
                UPDATE fw.stage_run SET status = 'ABORTED' WHERE id = sr.id;
            END IF;
            UPDATE fw.stage_run SET status = 'ABORTED'
            WHERE batch_id = sr.batch_id AND is_current AND status = 'PENDING';
            UPDATE fw.ingest_batch SET status = 'ABORTED' WHERE id = sr.batch_id;
        WHEN 'RETRY_STAGE' THEN
            PERFORM fw.stage_retry_from(sr.batch_id, sr.stage_no, sr.params);
        WHEN 'APPLY_FIX_AND_RETRY' THEN
            PERFORM fw.stage_retry_from(sr.batch_id, sr.stage_no, sr.params || p_params);
    END CASE;
    RETURN dec_id;
END $$;

-- Freeze of a run plan (03 section 8.1, 8.3 point 7).
CREATE FUNCTION fw.run_plan_freeze(p_run_plan text, p_lock_sha256 text, p_user uuid) RETURNS void
LANGUAGE plpgsql AS $$
DECLARE
    rp fw.run_plan;
    src fw.source;
BEGIN
    SELECT * INTO rp FROM fw.run_plan WHERE id = p_run_plan FOR UPDATE;
    IF rp.git_sha IS NULL OR rp.git_dirty IS DISTINCT FROM false THEN
        RAISE EXCEPTION 'run plan %: needs a clean git tree and a pinned SHA', rp.id USING ERRCODE = 'check_violation';
    END IF;
    IF EXISTS (SELECT 1 FROM jsonb_each_text(rp.image_digests) WHERE value !~ '@sha256:[0-9a-f]{64}$') THEN
        RAISE EXCEPTION 'run plan %: every image must be pinned by digest', rp.id USING ERRCODE = 'check_violation';
    END IF;
    IF rp.purpose <> 'g0_repro' AND rp.base_source_id IS NOT NULL THEN
        SELECT * INTO src FROM fw.source WHERE id = rp.base_source_id;
        IF src.clean_for_main_task <> 'true' THEN
            RAISE EXCEPTION 'run plan %: base checkpoint source % is not confirmed clean (Q0)', rp.id, src.id
                USING ERRCODE = 'check_violation';
        END IF;
        IF coalesce(rp.base_checkpoint_path, '') ~ '(simple|sonic)-checkpoints' THEN
            RAISE EXCEPTION 'run plan %: simple-checkpoints and sonic-checkpoints are for g0_repro only', rp.id
                USING ERRCODE = 'check_violation';
        END IF;
    END IF;
    UPDATE fw.run_plan SET status = 'frozen', lock_sha256 = p_lock_sha256, frozen_at = now(), frozen_by = p_user
    WHERE id = p_run_plan;
END $$;

-- Moves refs/policy/<branch>/current after a passing dev gate or a milestone decision.
CREATE FUNCTION fw.ref_set(p_name text, p_checkpoint text, p_decision text, p_reason text) RETURNS void
LANGUAGE plpgsql AS $$
DECLARE
    d fw.decision;
    old_ckpt text;
BEGIN
    SELECT * INTO d FROM fw.decision WHERE id = p_decision;
    IF NOT ((d.kind = 'dev_gate' AND d.verdict = 'pass') OR d.kind = 'milestone') THEN
        RAISE EXCEPTION 'ref %: needs a passing dev_gate or a milestone decision', p_name USING ERRCODE = 'check_violation';
    END IF;
    SELECT checkpoint_id INTO old_ckpt FROM fw.ref_pointer WHERE name = p_name FOR UPDATE;
    INSERT INTO fw.ref_pointer (name, checkpoint_id, decision_id) VALUES (p_name, p_checkpoint, p_decision)
    ON CONFLICT (name) DO UPDATE SET checkpoint_id = EXCLUDED.checkpoint_id, decision_id = EXCLUDED.decision_id,
                                     updated_at = now();
    INSERT INTO fw.ref_log (name, old_checkpoint_id, new_checkpoint_id, decision_id, reason)
    VALUES (p_name, old_ckpt, p_checkpoint, p_decision, p_reason);
END $$;

-- Step 11 review: the engineer approves, edits or rejects each proposal within the round budget.
-- p_approvals: [{"intervention_id": "iv_...", "approved": true, "qty": 120, "override_reason": "..."}]
CREATE FUNCTION fw.round_review(p_round uuid, p_user uuid, p_reason text, p_approvals jsonb) RETURNS text
LANGUAGE plpgsql AS $$
DECLARE
    rnd fw.flywheel_round;
    dec_id text := fw.new_id('dec');
    approved_cost numeric;
    missing text;
BEGIN
    SELECT * INTO rnd FROM fw.flywheel_round WHERE id = p_round FOR UPDATE;
    IF rnd.status <> 'AWAITING_REVIEW' THEN
        RAISE EXCEPTION 'round % is not awaiting review', p_round USING ERRCODE = 'check_violation';
    END IF;
    SELECT string_agg(iv.id, ', ') INTO missing FROM fw.intervention iv
    WHERE iv.round_id = p_round
      AND NOT EXISTS (SELECT 1 FROM jsonb_array_elements(p_approvals) a WHERE a->>'intervention_id' = iv.id);
    IF missing IS NOT NULL THEN
        RAISE EXCEPTION 'round review must answer every proposal; missing %', missing USING ERRCODE = 'check_violation';
    END IF;

    SELECT coalesce(sum(iv.cost_c_usd * (a->>'qty')::numeric / iv.quantity), 0) INTO approved_cost
    FROM jsonb_array_elements(p_approvals) a JOIN fw.intervention iv ON iv.id = a->>'intervention_id'
    WHERE (a->>'approved')::boolean;
    IF approved_cost > rnd.budget_usd THEN
        RAISE EXCEPTION 'round review: approved cost % exceeds the round budget %', approved_cost, rnd.budget_usd
            USING ERRCODE = 'check_violation';
    END IF;

    INSERT INTO fw.decision (id, kind, subject_kind, subject_id, run_plan_id, verdict, signed_by, reason, metrics)
    VALUES (dec_id, 'plan_review', 'flywheel_round', p_round::text, rnd.run_plan_id,
            CASE WHEN EXISTS (
                SELECT 1 FROM jsonb_array_elements(p_approvals) a JOIN fw.intervention iv ON iv.id = a->>'intervention_id'
                WHERE (a->>'approved')::boolean IS DISTINCT FROM iv.selected_by_algorithm
                   OR ((a->>'approved')::boolean AND (a->>'qty')::int <> iv.quantity))
                 THEN 'overridden' ELSE 'approved' END,
            p_user, p_reason, jsonb_build_object('approved_cost_usd', approved_cost, 'budget_usd', rnd.budget_usd));

    INSERT INTO fw.intervention_approval (intervention_id, decision_id, approved, approved_qty, override_reason)
    SELECT a->>'intervention_id', dec_id, (a->>'approved')::boolean,
           CASE WHEN (a->>'approved')::boolean THEN (a->>'qty')::int END, a->>'override_reason'
    FROM jsonb_array_elements(p_approvals) a;

    IF EXISTS (
        SELECT 1 FROM fw.intervention_approval ap JOIN fw.intervention iv ON iv.id = ap.intervention_id
        WHERE ap.decision_id = dec_id
          AND (ap.approved IS DISTINCT FROM iv.selected_by_algorithm OR ap.approved_qty <> iv.quantity)
          AND length(btrim(coalesce(ap.override_reason, ''))) = 0
    ) THEN
        RAISE EXCEPTION 'round review: every override needs a reason (spec 6.14)' USING ERRCODE = 'check_violation';
    END IF;

    INSERT INTO fw.ledger_entry (id, activity, resource_type, quantity, unit, pricebook_cfg_id, usd_amount,
                                 measure_kind, branch, run_plan_id, round_id, cluster_id, intervention_id, note)
    SELECT fw.new_id('led'), 'data_generation', 'intervention_' || iv.type, ap.approved_qty, it.unit,
           rp.pricebook_cfg_id, round(iv.cost_c_usd * ap.approved_qty / iv.quantity, 4),
           'estimated', rnd.branch, rnd.run_plan_id, rnd.id, iv.cluster_id, iv.id, 'approved in ' || dec_id
    FROM fw.intervention_approval ap
    JOIN fw.intervention iv ON iv.id = ap.intervention_id
    JOIN fw.intervention_type it ON it.code = iv.type
    JOIN fw.run_plan rp ON rp.id = rnd.run_plan_id
    WHERE ap.decision_id = dec_id AND ap.approved;

    INSERT INTO fw.intervention_task (intervention_id)
    SELECT intervention_id FROM fw.intervention_approval WHERE decision_id = dec_id AND approved;

    UPDATE fw.flywheel_round SET status = 'ACQUIRING' WHERE id = p_round;
    RETURN dec_id;
END $$;

CREATE FUNCTION fw.holdout_unseal(p_run_plan text) RETURNS void
LANGUAGE plpgsql AS $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM fw.run_plan_branch b, unnest(b.seeds) s
        WHERE b.run_plan_id = p_run_plan
          AND NOT EXISTS (
              SELECT 1 FROM fw.checkpoint c JOIN fw.holdout_lock l ON l.checkpoint_id = c.id
              WHERE c.branch = b.branch AND c.seed = s AND c.is_final AND l.run_plan_id = p_run_plan)
    ) THEN
        RAISE EXCEPTION 'holdout %: every (branch, seed) checkpoint must be locked before unsealing', p_run_plan
            USING ERRCODE = 'check_violation';
    END IF;
    IF (SELECT count(DISTINCT protocol_sha256) FROM fw.holdout_lock WHERE run_plan_id = p_run_plan) > 1 THEN
        RAISE EXCEPTION 'holdout %: locks use different protocol hashes', p_run_plan USING ERRCODE = 'check_violation';
    END IF;
    UPDATE fw.holdout_seal SET unsealed_at = now() WHERE run_plan_id = p_run_plan AND unsealed_at IS NULL;
END $$;

-- ---------------------------------------------------------------------------
-- 17. Views for the website and the algorithm
-- ---------------------------------------------------------------------------

CREATE VIEW fw.v_episode_current AS
SELECT e.*,
       q.decision     AS qa_decision,
       q.reviewed_by  AS qa_reviewed_by,
       q.id           AS qa_report_id,
       CASE WHEN e.source_kind = 'egocentric' THEN coalesce(d.status, 'raw') END AS deid_status,
       coalesce(sr.is_current, true) AS is_current_in_batch
FROM fw.episode e
LEFT JOIN LATERAL (SELECT * FROM fw.qa_report q WHERE q.episode_id = e.id ORDER BY q.seq DESC LIMIT 1) q ON true
LEFT JOIN LATERAL (SELECT status FROM fw.episode_deid d WHERE d.episode_id = e.id ORDER BY d.seq DESC LIMIT 1) d ON true
LEFT JOIN fw.stage_run sr ON sr.id = e.created_by_stage_run_id;

-- Public projection for a site served outside the team machine (CLAUDE.md data_class rule).
CREATE VIEW fw.v_episode_public AS
SELECT * FROM fw.v_episode_current
WHERE data_class = 'public' AND (source_kind IS DISTINCT FROM 'egocentric' OR deid_status = 'verified');

CREATE VIEW fw.v_decision_current AS
SELECT DISTINCT ON (subject_kind, subject_id, kind) *
FROM fw.decision
ORDER BY subject_kind, subject_id, kind, seq DESC;

-- Six-stage stepper: stages 1-4 from the current attempts, 5-6 from releases and exports that use the batch.
CREATE VIEW fw.v_pipeline_stepper AS
SELECT b.id AS batch_id, b.code, d.stage_no, d.code AS stage_code, d.name AS stage_name,
       sr.id AS stage_run_id, sr.attempt_no, sr.status, sr.code_verdict, ar.verdict AS agent_verdict,
       sr.started_at, sr.ended_at
FROM fw.ingest_batch b
JOIN fw.pipeline_stage_def d ON d.scope = 'batch'
LEFT JOIN fw.stage_run sr ON sr.batch_id = b.id AND sr.stage_no = d.stage_no AND sr.is_current
LEFT JOIN fw.agent_report ar ON ar.id = sr.agent_report_id
WHERE b.hidden_at IS NULL
UNION ALL
SELECT b.id, b.code, d.stage_no, d.code, d.name, NULL, NULL,
       CASE
           WHEN d.stage_no = 5 AND EXISTS (
               SELECT 1 FROM fw.release_item i JOIN fw.episode e ON e.id = i.episode_id
               JOIN fw.release r ON r.id = i.release_id
               WHERE e.batch_id = b.id AND NOT i.excluded AND r.status = 'frozen') THEN 'PASSED'
           WHEN d.stage_no = 6 AND EXISTS (
               SELECT 1 FROM fw.release_item i JOIN fw.episode e ON e.id = i.episode_id
               JOIN fw.dataset_export x ON x.release_id = i.release_id
               WHERE e.batch_id = b.id AND NOT i.excluded AND x.status = 'READY') THEN 'PASSED'
           ELSE 'PENDING'
       END,
       NULL, NULL, NULL, NULL
FROM fw.ingest_batch b
JOIN fw.pipeline_stage_def d ON d.scope = 'release'
WHERE b.hidden_at IS NULL;

CREATE VIEW fw.v_batch_overview AS
SELECT b.id, b.code, b.name, b.source_kind, b.source_detail, b.synthetic_tier, b.status, b.current_stage,
       b.injected_from_batch_id IS NOT NULL AS is_injected_copy, b.data_class, b.created_at,
       count(e.id) FILTER (WHERE e.is_current_in_batch) AS episodes,
       count(e.id) FILTER (WHERE e.is_current_in_batch AND e.qa_decision = 'pass') AS qa_pass,
       count(e.id) FILTER (WHERE e.is_current_in_batch AND e.qa_decision = 'flag') AS qa_flag,
       count(e.id) FILTER (WHERE e.is_current_in_batch AND e.qa_decision = 'quarantine') AS qa_quarantine,
       count(e.id) FILTER (WHERE e.is_current_in_batch AND e.qa_decision = 'reject') AS qa_reject
FROM fw.ingest_batch b
LEFT JOIN fw.v_episode_current e ON e.batch_id = b.id
WHERE b.hidden_at IS NULL
GROUP BY b.id;

CREATE VIEW fw.v_train_curve AS
SELECT t.run_plan_id, t.branch, t.seed, t.stage, m.train_run_id, m.split, m.name, m.step, m.value
FROM fw.train_metric m JOIN fw.train_run t ON t.id = m.train_run_id
WHERE t.hidden_at IS NULL;

-- Success over valid episodes only: infrastructure errors are excluded, never counted as failures.
CREATE VIEW fw.v_eval_summary AS
SELECT r.id AS eval_run_id, r.run_plan_id, r.purpose, r.checkpoint_id, c.branch, c.seed, r.renderer, r.timing,
       cond.level, GROUPING(cond.level) = 1 AS is_total,
       count(e.id) AS episodes,
       count(e.id) FILTER (WHERE e.infra_status <> 'ok') AS infra_errors,
       count(e.id) FILTER (WHERE e.infra_status = 'ok') AS valid,
       count(e.id) FILTER (WHERE e.sim_success) AS successes,
       round(count(e.id) FILTER (WHERE e.sim_success)::numeric
             / nullif(count(e.id) FILTER (WHERE e.infra_status = 'ok'), 0), 4) AS success_rate
FROM fw.eval_run r
JOIN fw.checkpoint c ON c.id = r.checkpoint_id
LEFT JOIN fw.episode e ON e.eval_run_id = r.id AND e.kind = 'eval_rollout'
LEFT JOIN fw.condition cond ON cond.id = e.condition_id
WHERE r.hidden_at IS NULL
GROUP BY r.id, r.run_plan_id, r.purpose, r.checkpoint_id, c.branch, c.seed, r.renderer, r.timing,
         GROUPING SETS ((), (cond.level));

-- Funnel of the scorer steps plus the three phases the web doc shows (pick = step 2, walk = step 4, place = success).
CREATE VIEW fw.v_eval_funnel AS
WITH s AS (
    SELECT r.id AS eval_run_id, e.id AS episode_id, e.sim_success, sc.step_status
    FROM fw.eval_run r
    JOIN fw.episode e ON e.eval_run_id = r.id AND e.kind = 'eval_rollout' AND e.infra_status = 'ok'
    LEFT JOIN fw.score sc ON sc.episode_id = e.id AND sc.scorer_cfg_id = r.scorer_cfg_id
    WHERE r.hidden_at IS NULL
)
SELECT eval_run_id,
       count(*) AS valid_episodes,
       count(*) FILTER (WHERE step_status[1] = 'passed') AS step1,
       count(*) FILTER (WHERE step_status[2] = 'passed') AS step2,
       count(*) FILTER (WHERE step_status[3] = 'passed') AS step3,
       count(*) FILTER (WHERE step_status[4] = 'passed') AS step4,
       count(*) FILTER (WHERE step_status[5] = 'passed') AS step5,
       count(*) FILTER (WHERE step_status[6] = 'passed') AS step6,
       count(*) FILTER (WHERE step_status[2] = 'passed') AS phase_pick,
       count(*) FILTER (WHERE step_status[4] = 'passed') AS phase_walk,
       count(*) FILTER (WHERE sim_success) AS phase_place_success,
       count(*) FILTER (WHERE step_status IS NULL) AS unscored
FROM s GROUP BY eval_run_id;

-- The web doc's "Bảng lỗi": one row per failed valid episode.
CREATE VIEW fw.v_failure_table AS
SELECT r.id AS eval_run_id, r.run_plan_id, r.checkpoint_id, e.id AS episode_id, e.condition_id, cond.level,
       e.rollout_seed, e.replicate, sc.first_failed_step, sc.failure_kind, sc.failure_class,
       sc.step_times, e.bundle_uri, e.meta->>'failure_video_uri' AS video_uri
FROM fw.eval_run r
JOIN fw.episode e ON e.eval_run_id = r.id AND e.kind = 'eval_rollout'
JOIN fw.condition cond ON cond.id = e.condition_id
LEFT JOIN fw.score sc ON sc.episode_id = e.id AND sc.scorer_cfg_id = r.scorer_cfg_id
WHERE e.infra_status = 'ok' AND e.sim_success IS FALSE AND r.hidden_at IS NULL;

CREATE VIEW fw.v_failure_summary AS
SELECT eval_run_id, first_failed_step, failure_kind, failure_class, level, count(*) AS failures
FROM fw.v_failure_table
GROUP BY eval_run_id, first_failed_step, failure_kind, failure_class, level;

CREATE VIEW fw.v_cluster_current AS
SELECT c.*, d.diagnosis, d.decided_by AS diagnosis_by,
       (SELECT count(*) FROM fw.cluster_member m WHERE m.cluster_id = c.id) AS members,
       (SELECT count(*) FROM fw.cluster_member m WHERE m.cluster_id = c.id AND m.is_representative) AS representatives,
       d.diagnosis IN ('TRANG_THAI_DAU_XAU', 'THIEU_VUNG_PHU', 'KY_NANG_YEU') AS uses_data_budget,
       d.diagnosis IN ('CHUA_RO', 'HE_THONG_CONTROLLER', 'HE_THONG_RUNTIME', 'HE_THONG_DONG_BO',
                       'HE_THONG_CALIBRATION', 'KHONG_KHA_THI') AS needs_repair_ticket
FROM fw.cluster c
LEFT JOIN LATERAL (SELECT * FROM fw.cluster_diagnosis d WHERE d.cluster_id = c.id ORDER BY d.seq DESC LIMIT 1) d ON true;

CREATE VIEW fw.v_round_progress AS
SELECT f.id AS round_id, f.run_plan_id, f.branch, f.round_no, f.status, f.budget_usd,
       (SELECT count(*) FROM fw.round_step s WHERE s.round_id = f.id AND s.status IN ('DONE', 'SKIPPED')) AS steps_done,
       (SELECT coalesce(sum(usd_amount), 0) FROM fw.ledger_entry l
        WHERE l.round_id = f.id AND l.measure_kind = 'estimated') AS estimated_usd,
       (SELECT coalesce(sum(usd_amount), 0) FROM fw.ledger_entry l
        WHERE l.round_id = f.id AND l.measure_kind = 'measured') AS measured_usd,
       f.promoted
FROM fw.flywheel_round f;

CREATE VIEW fw.v_intervention_progress AS
SELECT iv.id, iv.round_id, iv.cluster_id, iv.type, iv.quantity AS proposed_qty, iv.selected_by_algorithm,
       ap.approved, ap.approved_qty, ap.override_reason,
       (SELECT count(*) FROM fw.v_episode_current e
        WHERE e.intervention_id = iv.id AND e.qa_decision = 'pass') AS collected_qa_pass,
       (SELECT coalesce(sum(usd_amount), 0) FROM fw.ledger_entry l
        WHERE l.intervention_id = iv.id AND l.measure_kind = 'measured') AS measured_usd
FROM fw.intervention iv
LEFT JOIN LATERAL (
    SELECT a.* FROM fw.intervention_approval a JOIN fw.decision d ON d.id = a.decision_id
    WHERE a.intervention_id = iv.id ORDER BY d.seq DESC LIMIT 1
) ap ON true;

-- Beta(1, 1) prior updated by controlled fix-rate measurements (spec 6.11, 6.13).
CREATE VIEW fw.v_fix_rate_posterior AS
SELECT it.code AS intervention_type,
       1 + coalesce(sum(f.fixed), 0) AS alpha,
       1 + coalesce(sum(f.n_conditions - f.fixed), 0) AS beta,
       round((1 + coalesce(sum(f.fixed), 0))::numeric / (2 + coalesce(sum(f.n_conditions), 0)), 4) AS mean,
       count(f.id) AS events
FROM fw.intervention_type it
LEFT JOIN fw.fix_rate_event f ON f.intervention_type = it.code
GROUP BY it.code;

CREATE VIEW fw.v_cost_by_branch AS
SELECT run_plan_id, branch, activity,
       sum(usd_amount) FILTER (WHERE measure_kind = 'measured') AS usd_measured,
       sum(usd_amount) FILTER (WHERE measure_kind = 'estimated') AS usd_estimated,
       sum(human_hours) FILTER (WHERE measure_kind = 'measured') AS human_hours_measured
FROM fw.ledger_entry
GROUP BY run_plan_id, branch, activity;

-- Measured cost of each batch and its accepted episodes (current attempt, QA pass or reviewed flag).
CREATE VIEW fw.v_batch_cost AS
SELECT b.id AS batch_id, b.code, b.source_kind, b.source_detail,
       (SELECT coalesce(sum(usd_amount), 0) FROM fw.ledger_entry l
        WHERE l.batch_id = b.id AND l.measure_kind = 'measured') AS usd_measured,
       (SELECT coalesce(sum(human_hours), 0) FROM fw.ledger_entry l
        WHERE l.batch_id = b.id AND l.measure_kind = 'measured') AS human_hours_measured,
       (SELECT count(*) FROM fw.v_episode_current e WHERE e.batch_id = b.id AND e.is_current_in_batch) AS episodes,
       (SELECT count(*) FROM fw.v_episode_current e WHERE e.batch_id = b.id AND e.is_current_in_batch
          AND (e.qa_decision = 'pass' OR (e.qa_decision = 'flag' AND e.qa_reviewed_by IS NOT NULL))) AS accepted
FROM fw.ingest_batch b;

-- Data cost carried by a release: batch cost spread over accepted episodes, so rejected samples are
-- paid for by the data that survived (spec 7.3 point 5: B_add includes rejected rollouts).
CREATE VIEW fw.v_release_data_cost AS
SELECT i.release_id, bc.source_kind,
       count(*) AS episodes,
       round(sum(bc.usd_measured / nullif(bc.accepted, 0)), 2) AS usd,
       round(sum(bc.human_hours_measured / nullif(bc.accepted, 0)), 2) AS human_hours
FROM fw.release_item i
JOIN fw.episode e ON e.id = i.episode_id
JOIN fw.v_batch_cost bc ON bc.batch_id = e.batch_id
WHERE NOT i.excluded
GROUP BY i.release_id, bc.source_kind;

-- Branch comparison card: data composition, latest success on dev-type evals, cost.
CREATE VIEW fw.v_branch_comparison AS
SELECT b.run_plan_id, b.branch, b.method, cardinality(b.seeds) AS seeds_planned,
       rel.id AS release_id,
       (rel.counts->>'human_roots')::int AS human_demos,
       rel.counts->'by_source' AS data_by_source,
       ev.success_rate AS latest_success_rate, ev.valid AS latest_valid_episodes, ev.purpose AS latest_eval_purpose,
       (SELECT coalesce(sum(usd), 0) FROM fw.v_release_data_cost dc WHERE dc.release_id = rel.id) AS data_usd,
       (SELECT coalesce(sum(usd_measured), 0) FROM fw.v_cost_by_branch cb
        WHERE cb.run_plan_id = b.run_plan_id AND cb.branch = b.branch) AS run_usd_measured
FROM fw.run_plan_branch b
LEFT JOIN fw.release rel ON rel.id = b.release_id
LEFT JOIN LATERAL (
    SELECT s.success_rate, s.valid, s.purpose FROM fw.v_eval_summary s
    JOIN fw.eval_run r ON r.id = s.eval_run_id
    WHERE s.run_plan_id = b.run_plan_id AND s.branch = b.branch AND s.is_total
      AND s.purpose IN ('dev_find', 'he_eval', 'g0', 'tray_eval')
    ORDER BY r.created_at DESC LIMIT 1
) ev ON true;

CREATE VIEW fw.v_cost_forecast_error AS
SELECT intervention_id,
       sum(usd_amount) FILTER (WHERE measure_kind = 'estimated') AS usd_estimated,
       sum(usd_amount) FILTER (WHERE measure_kind = 'measured') AS usd_measured,
       round(sum(usd_amount) FILTER (WHERE measure_kind = 'measured')
             / nullif(sum(usd_amount) FILTER (WHERE measure_kind = 'estimated'), 0) - 1, 4) AS relative_error
FROM fw.ledger_entry
WHERE intervention_id IS NOT NULL
GROUP BY intervention_id;

-- Detection scores on injected defects, per code and layer (design 27/10 section 9.2). Sealed schema.
CREATE VIEW fw_sealed.v_defect_detection AS
SELECT d.code, m.layer,
       count(*) AS defects,
       count(*) FILTER (WHERE m.detected) AS detected,
       round(count(*) FILTER (WHERE m.detected)::numeric / count(*), 4) AS recall
FROM fw_sealed.injected_defect d
JOIN fw_sealed.defect_match m ON m.defect_id = d.id
GROUP BY d.code, m.layer;

CREATE VIEW fw_sealed.v_agent_precision AS
SELECT dm.injected_batch_id,
       count(f.id) AS findings,
       count(f.id) FILTER (WHERE EXISTS (SELECT 1 FROM fw_sealed.defect_match m WHERE m.finding_id = f.id AND m.detected))
           AS true_findings,
       round(count(f.id) FILTER (WHERE EXISTS (
                 SELECT 1 FROM fw_sealed.defect_match m WHERE m.finding_id = f.id AND m.detected))::numeric
             / nullif(count(f.id), 0), 4) AS precision
FROM fw_sealed.defect_manifest dm
JOIN fw.stage_run sr ON sr.batch_id = dm.injected_batch_id
JOIN fw.agent_report ar ON ar.id = sr.agent_report_id
JOIN fw.agent_finding f ON f.report_id = ar.id
WHERE dm.revealed_at IS NOT NULL
GROUP BY dm.injected_batch_id;

-- Release freeze (needs v_episode_current, so it follows the views).

-- Freeze guard of 03 section 4.4 and 8.3. Returns the list of violations; empty means frozen.
CREATE FUNCTION fw.release_violations(p_release text) RETURNS TABLE (episode_id text, problem text)
LANGUAGE sql STABLE AS $$
    WITH items AS (
        SELECT e.*, i.release_id
        FROM fw.release_item i JOIN fw.v_episode_current e ON e.id = i.episode_id
        WHERE i.release_id = p_release AND NOT i.excluded
    ), rel AS (SELECT * FROM fw.release WHERE id = p_release)
    SELECT NULL::text, 'release has no included episode'
    WHERE NOT EXISTS (SELECT 1 FROM items)
    UNION ALL
    SELECT NULL, 'parent release is not frozen'
    FROM rel JOIN fw.release p ON p.id = rel.parent_release_id WHERE p.status <> 'frozen'
    UNION ALL
    SELECT id, 'episode is an injected-defect copy' FROM items WHERE is_injected_copy
    UNION ALL
    SELECT id, 'current QA is ' || coalesce(qa_decision, 'missing')
    FROM items
    WHERE qa_decision IS NULL
       OR NOT (qa_decision = 'pass' OR (qa_decision = 'flag' AND qa_reviewed_by IS NOT NULL))
    UNION ALL
    SELECT id, 'episode was superseded by a newer attempt of its batch' FROM items WHERE NOT is_current_in_batch
    UNION ALL
    SELECT id, 'egocentric episode not verified as de-identified'
    FROM items WHERE source_kind = 'egocentric' AND deid_status IS DISTINCT FROM 'verified'
    UNION ALL
    SELECT items.id, 'egocentric and robot data cannot share a release'
    FROM items, rel
    WHERE (rel.kind = 'egocentric') <> (items.source_kind = 'egocentric')
    UNION ALL
    SELECT NULL, 'mixed embodiments ' || string_agg(DISTINCT embodiment_id, ', ') || ' without a V3 decision'
    FROM items, rel
    WHERE rel.mixed_embodiment_decision_id IS NULL
    HAVING count(DISTINCT embodiment_id) > 1
$$;

CREATE FUNCTION fw.release_freeze(
    p_release text, p_manifest_sha256 text, p_user uuid, p_holdout_guard_passed boolean
) RETURNS void
LANGUAGE plpgsql AS $$
DECLARE
    problems text;
BEGIN
    PERFORM 1 FROM fw.release WHERE id = p_release FOR UPDATE;
    SELECT string_agg(coalesce(episode_id || ': ', '') || problem, '; ') INTO problems
    FROM (SELECT * FROM fw.release_violations(p_release) LIMIT 20) v;
    IF problems IS NOT NULL THEN
        RAISE EXCEPTION 'release % cannot be frozen: %', p_release, problems USING ERRCODE = 'check_violation';
    END IF;
    IF p_holdout_guard_passed IS NOT TRUE THEN
        RAISE EXCEPTION 'release %: holdout guard of gate.holdout did not pass', p_release USING ERRCODE = 'check_violation';
    END IF;
    UPDATE fw.release r
    SET status = 'frozen', manifest_sha256 = p_manifest_sha256, holdout_guard_passed = true,
        frozen_at = now(), frozen_by = p_user,
        combined_license = (SELECT string_agg(DISTINCT e.license, ' + ' ORDER BY e.license)
                            FROM fw.release_item i JOIN fw.episode e ON e.id = i.episode_id
                            WHERE i.release_id = r.id AND NOT i.excluded),
        counts = (SELECT jsonb_build_object(
                      'episodes', count(*),
                      'human_roots', count(*) FILTER (WHERE e.is_root),
                      'by_source', (SELECT jsonb_object_agg(k, n) FROM (
                          SELECT coalesce(e2.source_kind || coalesce('_' || lower(e2.synthetic_tier), ''), 'other') k,
                                 count(*) n
                          FROM fw.release_item i2 JOIN fw.episode e2 ON e2.id = i2.episode_id
                          WHERE i2.release_id = r.id AND NOT i2.excluded GROUP BY 1) s))
                  FROM fw.release_item i JOIN fw.episode e ON e.id = i.episode_id
                  WHERE i.release_id = r.id AND NOT i.excluded)
    WHERE r.id = p_release;
    PERFORM fw.notify('RELEASE_FROZEN', 'release', p_release);
END $$;

-- ---------------------------------------------------------------------------
-- 18. Mutability rules per table
-- ---------------------------------------------------------------------------

DO $$
DECLARE
    t text;
BEGIN
    -- Pure append-only tables: no UPDATE, no DELETE.
    FOREACH t IN ARRAY ARRAY['config_artifact', 'source', 'condition', 'condition_set', 'condition_set_member',
                             'agent_report', 'agent_finding', 'episode', 'episode_deid', 'episode_segment',
                             'qa_report', 'replay_report', 'dataset_report', 'train_metric', 'probe_result',
                             'train_flag', 'decision', 'stage_review', 'ref_log', 'score', 'cluster',
                             'cluster_member', 'diagnostic_check', 'cluster_diagnosis', 'intervention',
                             'intervention_approval', 'fix_rate_event', 'ledger_entry', 'holdout_lock',
                             'holdout_result', 'chat_message', 'price_rate']
    LOOP
        EXECUTE format('CREATE TRIGGER %I BEFORE UPDATE OR DELETE ON fw.%I FOR EACH ROW EXECUTE FUNCTION fw.tg_append_only()',
                       t || '_append_only', t);
    END LOOP;

    -- Every other table: no DELETE (release_item handles its own draft-only rule).
    FOREACH t IN ARRAY ARRAY['app_user', 'task_def', 'failure_kind_def', 'task_step_class', 'run_plan', 'job',
                             'pipeline_stage_def', 'ingest_batch', 'stage_run', 'release', 'dataset_export',
                             'train_run', 'checkpoint', 'ref_pointer', 'eval_run', 'round_step_def',
                             'flywheel_round', 'round_step', 'intervention_type', 'intervention_task',
                             'holdout_seal', 'chat_session', 'chat_action', 'notification', 'status_transition']
    LOOP
        EXECUTE format('CREATE TRIGGER %I BEFORE DELETE ON fw.%I FOR EACH ROW EXECUTE FUNCTION fw.tg_no_delete()',
                       t || '_no_delete', t);
    END LOOP;

    -- Status columns follow fw.status_transition.
    FOREACH t IN ARRAY ARRAY['ingest_batch', 'stage_run', 'job', 'dataset_export', 'train_run', 'eval_run',
                             'flywheel_round', 'round_step', 'intervention_task', 'chat_action']
    LOOP
        EXECUTE format('CREATE TRIGGER %I BEFORE UPDATE ON fw.%I FOR EACH ROW EXECUTE FUNCTION fw.tg_check_status()',
                       t || '_status', t);
    END LOOP;
END $$;

CREATE TRIGGER ingest_batch_mutable BEFORE UPDATE ON fw.ingest_batch FOR EACH ROW EXECUTE FUNCTION
    fw.tg_only_columns_mutable('status', 'current_stage', 'updated_at', 'hidden_at', 'hidden_by', 'hidden_reason', 'meta');
CREATE TRIGGER ingest_batch_touch BEFORE UPDATE ON fw.ingest_batch FOR EACH ROW EXECUTE FUNCTION fw.tg_touch_updated_at();
CREATE TRIGGER stage_run_mutable BEFORE UPDATE ON fw.stage_run FOR EACH ROW EXECUTE FUNCTION
    fw.tg_only_columns_mutable('status', 'is_current', 'job_id', 'output_uri', 'log_uri', 'stats', 'code_verdict',
                               'agent_report_id', 'error_message', 'started_at', 'ended_at', 'output_purged');
CREATE TRIGGER job_mutable BEFORE UPDATE ON fw.job FOR EACH ROW EXECUTE FUNCTION
    fw.tg_only_columns_mutable('status', 'infra_status', 'result', 'error_message', 'started_at', 'ended_at', 'machine');
CREATE TRIGGER dataset_export_mutable BEFORE UPDATE ON fw.dataset_export FOR EACH ROW EXECUTE FUNCTION
    fw.tg_only_columns_mutable('status', 'uri', 'stats_uri', 'contract_test_passed', 'job_id', 'file_purged');
CREATE TRIGGER train_run_mutable BEFORE UPDATE ON fw.train_run FOR EACH ROW EXECUTE FUNCTION
    fw.tg_only_columns_mutable('status', 'job_id', 'started_at', 'ended_at', 'hidden_at', 'hidden_by', 'hidden_reason');
CREATE TRIGGER checkpoint_mutable BEFORE UPDATE ON fw.checkpoint FOR EACH ROW EXECUTE FUNCTION
    fw.tg_only_columns_mutable('file_purged', 'purged_at', 'purge_reason');
CREATE TRIGGER checkpoint_update BEFORE UPDATE ON fw.checkpoint FOR EACH ROW EXECUTE FUNCTION fw.tg_checkpoint_update();
CREATE TRIGGER eval_run_mutable BEFORE UPDATE ON fw.eval_run FOR EACH ROW EXECUTE FUNCTION
    fw.tg_only_columns_mutable('status', 'job_id', 'started_at', 'ended_at', 'hidden_at', 'hidden_by', 'hidden_reason');
CREATE TRIGGER flywheel_round_mutable BEFORE UPDATE ON fw.flywheel_round FOR EACH ROW EXECUTE FUNCTION
    fw.tg_only_columns_mutable('status', 'stop_reason', 'find_eval_run_id', 'child_release_id',
                               'candidate_checkpoint_id', 'gate_decision_id', 'promoted', 'updated_at');
CREATE TRIGGER flywheel_round_touch BEFORE UPDATE ON fw.flywheel_round FOR EACH ROW EXECUTE FUNCTION fw.tg_touch_updated_at();
CREATE TRIGGER round_step_mutable BEFORE UPDATE ON fw.round_step FOR EACH ROW EXECUTE FUNCTION
    fw.tg_only_columns_mutable('status', 'summary', 'started_at', 'ended_at');
CREATE TRIGGER intervention_task_mutable BEFORE UPDATE ON fw.intervention_task FOR EACH ROW EXECUTE FUNCTION
    fw.tg_only_columns_mutable('status', 'assignee_id', 'due_at', 'note', 'updated_at');
CREATE TRIGGER intervention_task_touch BEFORE UPDATE ON fw.intervention_task FOR EACH ROW EXECUTE FUNCTION fw.tg_touch_updated_at();
CREATE TRIGGER holdout_seal_mutable BEFORE UPDATE ON fw.holdout_seal FOR EACH ROW EXECUTE FUNCTION
    fw.tg_only_columns_mutable('unsealed_at');
CREATE TRIGGER chat_session_mutable BEFORE UPDATE ON fw.chat_session FOR EACH ROW EXECUTE FUNCTION
    fw.tg_only_columns_mutable('title', 'hidden_at', 'hidden_reason');
CREATE TRIGGER chat_action_mutable BEFORE UPDATE ON fw.chat_action FOR EACH ROW EXECUTE FUNCTION
    fw.tg_only_columns_mutable('status', 'decided_by', 'decided_at', 'job_id', 'result');
CREATE TRIGGER notification_mutable BEFORE UPDATE ON fw.notification FOR EACH ROW EXECUTE FUNCTION
    fw.tg_only_columns_mutable('read_at');

-- ---------------------------------------------------------------------------
-- 19. Reference data
-- ---------------------------------------------------------------------------

INSERT INTO fw.pipeline_stage_def (stage_no, code, name, scope) VALUES
    (1, 'INGEST', 'Ingest: raw files, sha256, Source with license and data_class', 'batch'),
    (2, 'NORMALIZE', 'Normalize: time sync, units and frames, action_layout; pose for egocentric', 'batch'),
    (3, 'ANNOTATE', 'Annotate: de-identification first for egocentric, segments, language', 'batch'),
    (4, 'QA', 'QA: spec 4.4 checks, source checks, action replay', 'batch'),
    (5, 'RELEASE', 'Release: frozen manifest, split guard, combined license', 'release'),
    (6, 'EXPORT', 'Export: LeRobot v2.1 or Psi0 stage 1, stats, contract test', 'release');

INSERT INTO fw.round_step_def (step_no, code, name) VALUES
    (1, 'run', 'Chạy policy trên 90 điều kiện dev'),
    (2, 'label', 'Gán nhãn: bước hỏng đầu tiên, kiểu lỗi'),
    (3, 'cluster', 'Gom cụm sơ bộ theo (k, kiểu lỗi, mức)'),
    (4, 'system_check', 'Kiểm hệ thống: tín hiệu, đồng bộ, camera, bám lệnh, độ trễ'),
    (5, 'feasibility', 'Kiểm khả thi bằng planner'),
    (6, 'localize', 'Khoanh vùng bằng reset về trạng thái chuẩn'),
    (7, 'visual', 'Kiểm thị giác'),
    (8, 'coverage', 'Kiểm vùng phủ và miền train'),
    (9, 'diagnose', 'Chẩn đoán cụm theo đa số'),
    (10, 'propose', 'Đề xuất và định lượng can thiệp'),
    (11, 'select', 'Chọn theo g/c trong ngân sách, kỹ sư duyệt'),
    (12, 'acquire_train_gate', 'Thu, QA, train, cổng dev, đo tỉ lệ sửa được');

INSERT INTO fw.intervention_type (code, per_failure_qty, unit, max_failures_l_t, max_qty_per_cluster,
                                  allowed_diagnoses, enabled, note) VALUES
    ('sim_s1', 20, 'rollout', 10, 200, ARRAY['THIEU_VUNG_PHU'], true, 'Planner trong sim (spec 6.10)'),
    ('sim_s2', 20, 'rollout', 10, 200, ARRAY['THIEU_VUNG_PHU'], true, 'Biến thể từ đoạn teleop'),
    ('sim_s3', 20, 'rollout', 10, 200, ARRAY['THIEU_VUNG_PHU'], false, 'Cosmos Transfer; sau demo'),
    ('sim_s4', 20, 'rollout', 10, 200, ARRAY['THIEU_VUNG_PHU'], false, 'Cosmos Predict; sau demo'),
    ('teleop_correction', 1, 'correction', 10, 10, ARRAY['KY_NANG_YEU'], true, 'Teleop correction ở bước k'),
    ('recovery', 1, 'segment', 10, 10, ARRAY['TRANG_THAI_DAU_XAU'], true, 'Đoạn phục hồi từ trạng thái lỗi');

INSERT INTO fw.task_def (task_id, version, family, n_steps, step_names, simple_env_id) VALUES
    ('g1_locomotion_pick_between_tables', '1.0.0', 'pick_place', 6,
     ARRAY['approach', 'grasp', 'walk', 'arrive', 'place', 'release_stable'],
     'G1WholebodyLocomotionPickBetweenTablesTeleop-v0');

INSERT INTO fw.task_step_class (task_id, step_no, failure_class) VALUES
    ('g1_locomotion_pick_between_tables', 1, 'approach'),
    ('g1_locomotion_pick_between_tables', 2, 'grasp'),
    ('g1_locomotion_pick_between_tables', 3, 'carry'),
    ('g1_locomotion_pick_between_tables', 4, 'carry'),
    ('g1_locomotion_pick_between_tables', 5, 'place'),
    ('g1_locomotion_pick_between_tables', 6, 'place');

INSERT INTO fw.failure_kind_def (task_id, code, failure_class, description) VALUES
    ('g1_locomotion_pick_between_tables', 'L-REACH', 'approach', 'Không tới được vật'),
    ('g1_locomotion_pick_between_tables', 'L-GRASP', 'grasp', 'Gắp trượt'),
    ('g1_locomotion_pick_between_tables', 'L-SLIP', 'carry', 'Rơi khi mang'),
    ('g1_locomotion_pick_between_tables', 'L-WALK', 'carry', 'Đi sai ở bước 3-4'),
    ('g1_locomotion_pick_between_tables', 'L-COLLIDE', NULL, 'Va chạm; lớp theo bước hỏng'),
    ('g1_locomotion_pick_between_tables', 'L-PLACE', 'place', 'Đặt lệch'),
    ('g1_locomotion_pick_between_tables', 'L-RELEASE', 'place', 'Nhả sai lúc'),
    ('g1_locomotion_pick_between_tables', 'L-BALANCE', 'balance', 'Mất thăng bằng'),
    ('g1_locomotion_pick_between_tables', 'L-TIMEOUT', NULL, 'Đứng yên; lớp theo bước hỏng'),
    ('g1_locomotion_pick_between_tables', 'L-UNKNOWN', NULL, 'Thiếu tín hiệu');

-- ---------------------------------------------------------------------------
-- 20. Roles. fw_app is the backend; fw_grader alone reads answer keys; fw_viewer is read-only.
-- ---------------------------------------------------------------------------

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'fw_app') THEN CREATE ROLE fw_app NOLOGIN; END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'fw_grader') THEN CREATE ROLE fw_grader NOLOGIN; END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'fw_viewer') THEN CREATE ROLE fw_viewer NOLOGIN; END IF;
END $$;

REVOKE ALL ON SCHEMA fw_sealed FROM PUBLIC;
GRANT USAGE ON SCHEMA fw TO fw_app, fw_grader, fw_viewer;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA fw TO fw_app;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA fw TO fw_app;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA fw TO fw_app;
GRANT SELECT ON ALL TABLES IN SCHEMA fw TO fw_grader, fw_viewer;
GRANT USAGE ON SCHEMA fw_sealed TO fw_grader;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA fw_sealed TO fw_grader;
-- The backend writes the manifest once (locked hash) but cannot read it back.
GRANT USAGE ON SCHEMA fw_sealed TO fw_app;
GRANT INSERT ON fw_sealed.defect_manifest, fw_sealed.injected_defect TO fw_app;

COMMIT;
