-- Luật không viết được bằng CHECK: trigger cho C5–C9, C14, C19 (DESIGN.md §4.5).
--
-- CHECK chỉ thấy một dòng. Mọi luật dưới đây phải đọc bảng khác (release có
-- episode nào, episode thuộc dataset nào), nên chúng là trigger.
--
-- **Trigger trên bảng nhóm P là lưới an toàn, không phải nơi xử lý nghiệp vụ**
-- (§2). Nếu lõi đẩy sang dữ liệu vi phạm, fwsync từ chối dòng đó, ghi lỗi vào
-- sync_runs và chạy tiếp các dòng khác. Trigger ở đây là để một lỗi trong bộ
-- nạp không âm thầm phá bất biến.
--
-- Mỗi hàm nêu rõ mã luật trong thông điệp lỗi, vì API map mã đó sang mã BR
-- cho FE (§7.3).
--
-- Lưu ý khi review: sqlglot không phân tích được thân PL/pgSQL, nên file này
-- **chưa được kiểm cú pháp tự động**. Nghiệm thu của mốc M1 là chạy nó trên
-- PostgreSQL 16 thật, mỗi luật một ca đúng và một ca sai.

-- ---------------------------------------------------------------------------
-- C6 · bản nháp chỉ sửa được khi còn DRAFT
-- ---------------------------------------------------------------------------
CREATE FUNCTION w_draft_is_immutable_after_submit() RETURNS TRIGGER AS $$
BEGIN
  -- fw_sync được đổi ba cột kết quả trên bản nháp đã nộp; mọi cột khác thì
  -- không. Quyền theo cột ở 80-grants.sql chặn fw_api; trigger này chặn cả
  -- một lỗi trong bộ nạp.
  IF OLD.status <> 'DRAFT' THEN
    IF NEW.status IS DISTINCT FROM OLD.status
       OR NEW.reject_reason IS DISTINCT FROM OLD.reject_reason THEN
      RETURN NEW;
    END IF;
    RAISE EXCEPTION 'C6: bản nháp đã ở trạng thái % nên không sửa được nữa', OLD.status
      USING ERRCODE = 'check_violation';
  END IF;
  RETURN NEW;
END
$$ LANGUAGE plpgsql;

CREATE TRIGGER c6_experiment_draft_immutable
  BEFORE UPDATE ON experiment_drafts
  FOR EACH ROW EXECUTE FUNCTION w_draft_is_immutable_after_submit();

CREATE TRIGGER c6_dataset_intake_immutable
  BEFORE UPDATE ON dataset_intakes
  FOR EACH ROW EXECUTE FUNCTION w_draft_is_immutable_after_submit();

-- ---------------------------------------------------------------------------
-- C5 và C7 · kiểm bản nháp thí nghiệm lúc nộp
-- ---------------------------------------------------------------------------
CREATE FUNCTION w_validate_experiment_draft() RETURNS TRIGGER AS $$
DECLARE
  total NUMERIC := 0;
  item JSONB;
  release_row releases;
  bad_count INTEGER;
  source_clean VARCHAR(8);
BEGIN
  IF NEW.status <> 'SUBMITTED' OR OLD.status = 'SUBMITTED' THEN
    RETURN NEW;
  END IF;

  -- C5: cần ít nhất một release, và tổng tỉ trọng bằng 1.
  IF jsonb_array_length(NEW.release_mix) = 0 THEN
    RAISE EXCEPTION 'C5: bản nháp phải có ít nhất một release'
      USING ERRCODE = 'check_violation';
  END IF;

  FOR item IN SELECT * FROM jsonb_array_elements(NEW.release_mix) LOOP
    total := total + (item->>'mix_weight')::NUMERIC;

    SELECT * INTO release_row FROM releases
      WHERE id = (item->>'release_id')::UUID;
    IF NOT FOUND THEN
      RAISE EXCEPTION 'BR-01: không có release %', item->>'release_id'
        USING ERRCODE = 'check_violation';
    END IF;

    -- C7: release phải đã đóng băng và chưa xoá. Một release nháp còn đổi
    -- được nội dung, nên thí nghiệm dựng trên nó không tái lập được.
    IF release_row.status <> 'frozen' THEN
      RAISE EXCEPTION 'BR-01: release % chưa đóng băng', release_row.release_ref
        USING ERRCODE = 'check_violation';
    END IF;
    IF release_row.is_deleted THEN
      RAISE EXCEPTION 'BR-01: release % đã xoá', release_row.release_ref
        USING ERRCODE = 'check_violation';
    END IF;

    -- C7: không chứa episode của bản sao cấy lỗi. Bản 0.3 kiểm theo
    -- `benchmark_copy_id` thay cho `injected_defect` đã bị bỏ (03 bản 1.0).
    -- Kiểm cả hai phía vì episode sạch của bản sao cũng mang cờ này: rào theo
    -- đáp án sẽ cho episode sạch của bản sao lọt qua.
    SELECT count(*) INTO bad_count
      FROM release_items ri
      JOIN episodes e ON e.id = ri.episode_id
      JOIN datasets d ON d.id = e.dataset_id
     WHERE ri.release_id = release_row.id
       AND NOT ri.excluded
       AND (e.benchmark_copy_id IS NOT NULL OR d.has_seeded_faults);
    IF bad_count > 0 THEN
      RAISE EXCEPTION
        'BR-01: release % chứa % episode của bản sao cấy lỗi',
        release_row.release_ref, bad_count
        USING ERRCODE = 'check_violation';
    END IF;
  END LOOP;

  IF abs(total - 1) > 1e-6 THEN
    RAISE EXCEPTION 'C5: tổng mix_weight là %, phải bằng 1', total
      USING ERRCODE = 'check_violation';
  END IF;

  -- C7: checkpoint gốc phải trỏ một source chưa bị khai là không sạch. Ba
  -- trạng thái, và chỉ `false` bị chặn: `unknown` vẫn vào được, nhưng nó hiện
  -- ra ở M4 để kỹ sư biết mình đang dựng trên gì.
  SELECT clean_for_main_task INTO source_clean FROM sources
    WHERE source_ref = NEW.base_checkpoint_ref;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'BR-01: không có source % cho checkpoint gốc', NEW.base_checkpoint_ref
      USING ERRCODE = 'check_violation';
  END IF;
  IF source_clean = 'false' THEN
    RAISE EXCEPTION 'BR-01: checkpoint gốc % khai là không sạch cho task chính',
      NEW.base_checkpoint_ref
      USING ERRCODE = 'check_violation';
  END IF;

  RETURN NEW;
END
$$ LANGUAGE plpgsql;

CREATE TRIGGER c5_c7_validate_draft_on_submit
  BEFORE UPDATE ON experiment_drafts
  FOR EACH ROW EXECUTE FUNCTION w_validate_experiment_draft();

-- ---------------------------------------------------------------------------
-- C8 · sổ chi phí chỉ được thêm
-- ---------------------------------------------------------------------------
-- Trigger một mình không đủ: chủ bảng tắt được trigger. Quyền ở 80-grants.sql
-- REVOKE UPDATE, DELETE khỏi cả fw_api lẫn fw_sync, nên hai lớp cùng chặn.
CREATE FUNCTION p_ledger_is_append_only() RETURNS TRIGGER AS $$
BEGIN
  RAISE EXCEPTION 'C8: sổ chi phí chỉ được thêm; sửa sai bằng bút toán đảo (entry_kind = REVERSAL)'
    USING ERRCODE = 'check_violation';
END
$$ LANGUAGE plpgsql;

CREATE TRIGGER c8_ledger_no_update
  BEFORE UPDATE OR DELETE ON cost_ledger_entries
  FOR EACH ROW EXECUTE FUNCTION p_ledger_is_append_only();

-- Cùng luật cho hai bảng append-only khác.
CREATE TRIGGER c8_qa_report_no_update
  BEFORE UPDATE OR DELETE ON episode_qa_reports
  FOR EACH ROW EXECUTE FUNCTION p_ledger_is_append_only();

CREATE TRIGGER c8_defect_score_no_update
  BEFORE UPDATE OR DELETE ON defect_scores
  FOR EACH ROW EXECUTE FUNCTION p_ledger_is_append_only();

CREATE TRIGGER c8_defect_bench_group_no_update
  BEFORE UPDATE OR DELETE ON defect_bench_groups
  FOR EACH ROW EXECUTE FUNCTION p_ledger_is_append_only();

-- ---------------------------------------------------------------------------
-- C9 · bút toán đảo đúng dấu, đúng đối tượng
-- ---------------------------------------------------------------------------
CREATE FUNCTION p_reversal_matches_original() RETURNS TRIGGER AS $$
DECLARE
  original cost_ledger_entries;
BEGIN
  IF NEW.entry_kind <> 'REVERSAL' THEN
    RETURN NEW;
  END IF;

  SELECT * INTO original FROM cost_ledger_entries WHERE id = NEW.reverses_entry_id;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'C9: không có bút toán % để đảo', NEW.reverses_entry_id
      USING ERRCODE = 'check_violation';
  END IF;
  IF original.entry_kind = 'REVERSAL' THEN
    RAISE EXCEPTION 'C9: không đảo một bút toán đảo'
      USING ERRCODE = 'check_violation';
  END IF;

  -- Đúng đối tượng: đảo một bút toán của nhánh A bằng một dòng gắn nhánh B
  -- thì hai nhánh đều sai số.
  IF NEW.activity <> original.activity
     OR NEW.resource_type <> original.resource_type
     OR NEW.dataset_id IS DISTINCT FROM original.dataset_id
     OR NEW.experiment_id IS DISTINCT FROM original.experiment_id
     OR NEW.evaluation_id IS DISTINCT FROM original.evaluation_id
     OR NEW.recommendation_id IS DISTINCT FROM original.recommendation_id
     OR NEW.intervention_id IS DISTINCT FROM original.intervention_id THEN
    RAISE EXCEPTION 'C9: bút toán đảo phải gắn đúng đối tượng của bút toán gốc'
      USING ERRCODE = 'check_violation';
  END IF;

  -- Cùng loại đo và cùng dòng ước tính: đảo một dòng thực đo bằng một dòng
  -- ước tính thì sai số dự báo của job đó lệch.
  IF NEW.measure_kind <> original.measure_kind
     OR NEW.estimate_entry_id IS DISTINCT FROM original.estimate_entry_id THEN
    RAISE EXCEPTION 'C9: bút toán đảo phải cùng measure_kind và cùng dòng ước tính với bút toán gốc'
      USING ERRCODE = 'check_violation';
  END IF;

  -- Đúng dấu: tổng của gốc và đảo phải bằng 0 trên mọi cột tiền và lượng.
  IF NEW.quantity <> -original.quantity
     OR NEW.usd_amount <> -original.usd_amount
     OR COALESCE(NEW.human_minutes, 0) <> -COALESCE(original.human_minutes, 0)
     OR COALESCE(NEW.gpu_hours, 0) <> -COALESCE(original.gpu_hours, 0) THEN
    RAISE EXCEPTION 'C9: bút toán đảo phải mang đúng số đối của bút toán gốc'
      USING ERRCODE = 'check_violation';
  END IF;

  RETURN NEW;
END
$$ LANGUAGE plpgsql;

CREATE TRIGGER c9_reversal_matches
  BEFORE INSERT ON cost_ledger_entries
  FOR EACH ROW EXECUTE FUNCTION p_reversal_matches_original();

-- ---------------------------------------------------------------------------
-- C14 · egocentric raw không rời tầng Annotate
-- ---------------------------------------------------------------------------
-- Video người phải qua bước che danh tính trước mọi bước xử lý khác
-- (CLAUDE.md, bất biến kiến trúc). Hai cửa ra duy nhất là `split` và
-- `release_items`, nên luật chặn đúng hai chỗ đó.
CREATE FUNCTION p_raw_egocentric_stays_put() RETURNS TRIGGER AS $$
BEGIN
  IF NEW.source_kind = 'egocentric'
     AND NEW.deid_status = 'raw'
     AND NEW.split <> 'unassigned' THEN
    RAISE EXCEPTION
      'C14 / BR-09: episode egocentric còn deid_status = raw nên không được gán split %',
      NEW.split
      USING ERRCODE = 'check_violation';
  END IF;
  RETURN NEW;
END
$$ LANGUAGE plpgsql;

CREATE TRIGGER c14_raw_egocentric_no_split
  BEFORE INSERT OR UPDATE ON episodes
  FOR EACH ROW EXECUTE FUNCTION p_raw_egocentric_stays_put();

-- ---------------------------------------------------------------------------
-- C19 · release từ chối episode của bản sao cấy lỗi, và egocentric raw
-- ---------------------------------------------------------------------------
CREATE FUNCTION p_release_item_is_allowed() RETURNS TRIGGER AS $$
DECLARE
  episode episodes;
  parent_dataset datasets;
BEGIN
  SELECT * INTO episode FROM episodes WHERE id = NEW.episode_id;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'không có episode %', NEW.episode_id
      USING ERRCODE = 'foreign_key_violation';
  END IF;

  -- Một item đã `excluded` thì không vào train, nên nó được phép nằm trong
  -- manifest kèm lý do: manifest ghi cả thứ bị loại.
  IF NEW.excluded THEN
    RETURN NEW;
  END IF;

  -- C19 (03 bản 1.0): mọi episode của bản sao chấm Agent QA/QC, cả episode có
  -- lỗi lẫn episode sạch, đều bị từ chối. Rào theo đáp án thì episode sạch
  -- của bản sao vẫn lọt, và đó đúng là lỗ mà #62 vá.
  IF episode.benchmark_copy_id IS NOT NULL THEN
    RAISE EXCEPTION
      'C19 / BR-08: episode % thuộc bản sao chấm % nên không vào release',
      episode.episode_ref, episode.benchmark_copy_id
      USING ERRCODE = 'check_violation';
  END IF;

  SELECT * INTO parent_dataset FROM datasets WHERE id = episode.dataset_id;
  IF parent_dataset.has_seeded_faults THEN
    RAISE EXCEPTION
      'C19 / BR-08: episode % thuộc lô có lỗi cấy nên không vào release',
      episode.episode_ref
      USING ERRCODE = 'check_violation';
  END IF;

  -- C14, cửa ra thứ hai.
  IF episode.source_kind = 'egocentric' AND episode.deid_status = 'raw' THEN
    RAISE EXCEPTION
      'C14 / BR-09: episode % còn deid_status = raw nên không vào release',
      episode.episode_ref
      USING ERRCODE = 'check_violation';
  END IF;

  RETURN NEW;
END
$$ LANGUAGE plpgsql;

CREATE TRIGGER c19_release_item_allowed
  BEFORE INSERT OR UPDATE ON release_items
  FOR EACH ROW EXECUTE FUNCTION p_release_item_is_allowed();

-- ---------------------------------------------------------------------------
-- SSE · NOTIFY sau mỗi lần import
-- ---------------------------------------------------------------------------
-- Nguồn của đẩy thông báo là LISTEN/NOTIFY, không thêm message broker (§3.1).
-- fw_sync gọi hàm này một lần sau mỗi lần import, kèm danh sách bảng đã đổi,
-- để FE làm mới đúng các query liên quan thay vì tải lại tất cả.
CREATE FUNCTION fw_notify_changed(changed_tables TEXT[]) RETURNS VOID AS $$
BEGIN
  PERFORM pg_notify('fw_changed', json_build_object(
    'tables', changed_tables,
    'at', to_char(now(), 'YYYY-MM-DD"T"HH24:MI:SSOF')
  )::TEXT);
END
$$ LANGUAGE plpgsql;
