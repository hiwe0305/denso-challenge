-- Schema đầy đủ của tầng web (DESIGN.md §4).
--
-- Chạy: psql -v ON_ERROR_STOP=1 -f web/schema/schema.sql -d flywheel_web
--
-- Thứ tự file theo khoá ngoại, không theo nhóm logic W/P/S của §4.1: nhóm W
-- trỏ sang nhóm P (dataset_intakes.dataset_id) và ngược lại, nên bảng không
-- chia được thành ba khối chạy nối tiếp. Mỗi file nói nó thuộc nhóm nào.
--
-- 42 bảng nghiệp vụ: 9 nhóm W, 29 nhóm P, 4 nhóm S (bản 0.6 thêm
-- `defect_bench_groups`). Cộng `jobs` là hạ tầng
-- hàng đợi, không tính (§3.1).
--
-- Chạy lại trên một database đã có sẽ lỗi: file này dựng từ đầu. Đổi schema
-- trên database đang chạy đi qua migration Alembic trong web/api/migrations/.

\set ON_ERROR_STOP on

\i web/schema/00-roles.sql
\i web/schema/10-core.sql
\i web/schema/20-group-p-data.sql
\i web/schema/30-group-p-ml.sql
\i web/schema/40-group-w.sql
\i web/schema/50-group-s.sql
\i web/schema/60-constraints.sql
\i web/schema/70-views.sql
\i web/schema/80-grants.sql
