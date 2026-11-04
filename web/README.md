# Tầng web · Humanoid Data Flywheel

Thiết kế đầy đủ: [DESIGN.md](DESIGN.md). File này chỉ nói cách chạy.

## Cây thư mục

| Đường dẫn | Vai |
|---|---|
| `DESIGN.md` | Thiết kế v0.3: 41 bảng, 8 nguyên tắc, 5 luồng, 10 màn hình, API |
| `schema/` | 9 file SQL đánh số theo thứ tự khoá ngoại; `schema.sql` gọi cả chín |
| `contracts/` | Nguồn enum duy nhất (`enums.py`) và bộ sinh `enums.ts` |
| `tests/` | Test chạy trong CI, không cần Postgres |
| `api/` | FastAPI, SQLAlchemy, Alembic (chưa dựng) |
| `fwsync/` | Bộ nạp: `source.py` đọc, `mapping.py` ánh xạ, `sink.py` ghi, `runner.py` bốn việc, `cli.py` lệnh |
| `mock/` | Generator của bộ mock; output ở `mock/demo-17-11/` ngoài thư mục `web/` |
| `fe/` | React, Vite, TanStack Query, Tailwind, MSW. `src/api/types.ts` là hình dạng response (DESIGN.md §7.4); `src/mocks/` dựng response từ `mock/demo-17-11/`; `src/contracts/schemas/` sinh từ hợp đồng. Màn hình đã dựng: M7 |

## Chạy test

Test của tầng web nằm trong `testpaths` của workspace, nên hai lệnh chuẩn của
repo đã bao gồm nó:

```bash
uv run pytest web/tests -q      # chỉ tầng web
uv run ruff check               # cả repo, đã gồm web/**/*.py
```

Không cần Postgres: test kiểm enum so với hợp đồng, và kiểm bất biến của
schema từ văn bản SQL.

## Chạy FE

Cần Node 24, npm 11. Mặc định FE chạy trên MSW: service worker chặn `/api/*` và trả
bộ mock `mock/demo-17-11/`, nên không cần backend.

```bash
cd web/fe
npm ci
npm run dev            # http://localhost:5173, dữ liệu mock
npm test               # vitest: hình dạng response M0 và màn hình M7
npm run typecheck && npm run lint && npm run build
npm run gen:types      # sinh lại type từ packages/flywheel-contracts/schemas/
```

`VITE_API_MODE=real npm run dev` tắt MSW và gọi API thật (mốc M2). Workflow
`web-fe` chạy `check:types`, typecheck, lint, test và build khi `web/`, `mock/`
hay schema hợp đồng đổi.

## Sinh lại enum cho FE

```bash
uv run python -m web.contracts.generate_ts
```

`web/tests/test_generated_ts.py` so file trên đĩa với bản sinh lại, nên quên
chạy lệnh này là test đỏ.

## Bộ mock

`mock/demo-17-11/` là dữ liệu mẫu của kịch bản demo 17/11 (DESIGN.md Phụ lục C):
210 episode, 180 episode eval, một lượt Failure → Data với bốn cụm. **Mọi số là
bịa.** Thư mục sinh ra, không sửa tay:

```bash
uv run python -m web.mock.generate          # ghi lại mock/demo-17-11/
uv run python -m web.fwsync.cli import --from mock/demo-17-11 --origin mock
```

Luôn nạp với `--origin mock`, để FE dán nhãn "mock" lên từng bản ghi.

## Chạy bộ nạp

Sink tách khỏi pipeline, nên bốn lệnh chạy được **khi chưa có Postgres**:

```bash
# nạp artifact vào sink JSONL
uv run python -m web.fwsync.cli import --from mock/demo-17-11 --out fwdata/web-sink

# xuất hành động đang chờ thành artifact trong outbox
uv run python -m web.fwsync.cli export --actions actions.jsonl --to fwdata/outbox

# lõi giả: đọc outbox, sinh kết quả mang source_action_id (mốc M4)
uv run python -m web.fwsync.cli fake-core --outbox fwdata/outbox --to fwdata/inbox

# so số dòng giữa nguồn và những gì đã nạp; báo chênh, không tự sửa
uv run python -m web.fwsync.cli verify --from mock/demo-17-11 --loaded counts.json
```

Mã thoát: `0` khi sạch, `1` khi có dòng bị từ chối, `2` khi không đọc được
nguồn. Thoát `0` khi có dòng bị từ chối là cách để lỗi đó không ai thấy trong
cron, nên lệnh không làm vậy.

`--sink jsonl` là mặc định. Nó **không phải một database**: nó không kiểm được
CHECK, trigger hay quyền, nên nó không thay được nghiệm thu mốc M1. Nó chứng
minh đường đọc và ánh xạ đúng. `--sink postgres` báo đúng ba thứ còn thiếu
thay vì đổ `ModuleNotFoundError`.

Hai mức khoan dung, khác nhau có chủ ý:

- Bảng có model hợp đồng bị **từ chối** nếu sai schema.
- Bảng chưa có file schema (`Source`, `Release`, `Decision`, … đều ở S1-10
  #36) đi đường khoan dung: cột lạ bị bỏ **kèm log**, không im lặng. Phụ lục B
  đòi như vậy tới khi #36 merge. Chuyển một bảng sang đường nghiêm là xoá một
  dòng ở `TOLERANT_TABLES`.

## Dựng database

**Cần PostgreSQL 16; máy dev chưa cài** (DESIGN.md §9.3). Khi đã có:

```bash
createdb flywheel_web
psql -v ON_ERROR_STOP=1 -d flywheel_web -f web/schema/schema.sql
```

`schema.sql` dựng từ đầu, không chạy lại được trên database đã có. Đổi schema
trên database đang chạy đi qua migration Alembic.

Ba role được tạo không kèm mật khẩu. Đặt mật khẩu và chuỗi kết nối ngoài repo:

```bash
psql -d flywheel_web -c "ALTER ROLE fw_api LOGIN PASSWORD '...'"
```

### Kiểm cú pháp SQL khi chưa có Postgres

```bash
uv run --with sqlglot python -c "
import pathlib, sqlglot
for f in sorted(pathlib.Path('web/schema').glob('*.sql')):
    if f.name != 'schema.sql':
        sqlglot.parse(f.read_text(encoding='utf-8'), dialect='postgres')
print('ok')"
```

`--with` dùng env tạm, không chạm `uv.lock`. Lệnh này **không** kiểm được thân
PL/pgSQL của trigger: `sqlglot` đọc `DO $$ ... $$` như một khối mờ. Nghiệm thu
thật của trigger là mốc M1 trên Postgres thật, mỗi luật một ca đúng một ca sai.

## Chỗ còn chờ quyết định

| Mã | Việc | Chặn gì |
|---|---|---|
| W8 | 03 §2.4 (ADR-13) xếp "Streamlit hoặc web" vào hàng hoãn tới L1+, và CLAUDE.md cấm thêm DB server ở L0. Cần PO đổi ADR-13 hoặc khoanh web ra ngoài L0 | Dựng Postgres và FastAPI thật (mốc M1) |
| W1 | Postgres chia hai nửa, hay web ghi thẳng | Hình dạng schema; bản này viết theo phương án chia hai nửa |
| W7 | `source_action_id` trên artifact lõi, và artifact `JobStatus` | Vòng ghi end-to-end (mốc M4) |

Phần FE trên MSW và phần test hiện tại không thêm dịch vụ nào nên không vướng
W8, và mốc M0–M3 đi được trong lúc chờ.
