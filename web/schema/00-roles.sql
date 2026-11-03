-- Ba role của tầng web (DESIGN.md §2, §3.1).
--
-- Luật R1 và R8 được cưỡng chế ở đây, không bằng lời dặn trong code:
--   fw_api   chỉ SELECT trên bảng nhóm P. Không có endpoint nào ghi bảng
--            chiếu vì role của API không có quyền ghi.
--   fw_sync  là role duy nhất ghi bảng P, và là role duy nhất UPDATE được
--            năm cột trạng thái của human_actions.
--   agent_ro là role của connection pool dựng prompt cho agent chat. Nó
--            không đọc được nhóm S (đáp án lỗi cấy) và chỉ đọc các view
--            *_agent đã lọc cứng dòng niêm phong.
--
-- File này chạy một lần lúc dựng cluster. GRANT cụ thể nằm ở 70-grants.sql,
-- sau khi bảng và view đã tồn tại.

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'fw_api') THEN
    CREATE ROLE fw_api LOGIN;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'fw_sync') THEN
    CREATE ROLE fw_sync LOGIN;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'agent_ro') THEN
    CREATE ROLE agent_ro LOGIN;
  END IF;
END
$$;

-- Không role nào được tạo bảng. Schema chỉ đổi qua migration Alembic chạy
-- bằng role chủ, nên một lỗi trong API không thể tạo ra một bảng lạ.
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
