# DA-40 · Flywheel Console trong repo

## Trạng thái

| Trường | Giá trị |
|---|---|
| Trạng thái | Đang làm (Hiếu mở ngày 11/11/2026: "Vào repo, story DA-40") |
| Người làm | Hiếu |
| Làn | Ngoài ba làn: công cụ của đội, đọc file và gọi lệnh `fw`, không import làn hay adapter |
| Nguồn yêu cầu | BA Flywheel Console bản 0.5 (`docs/superpowers/specs/2026-11-11-flywheel-console-design.md`, PR #193 chưa merge), mục 11, 12, 15.1a, 15.1b, 17 |
| Nhãn | `area:console` |
| Sprint | S2 · bản chạy được trong repo trước demo **17/11/2026**; buổi chạy thử 12/11 vẫn dùng bản v5 ngoài repo |
| Ước lượng | 10 giờ (ước lượng), chia cho các subagent Sonnet theo plan |
| Phụ thuộc | Không chặn ai. Đọc `fwdata/` và `docs/he/tray.md` ở `master`; chatbot cần đường hầm SSH tới Ollama trên `rtx3060` (đã có) |

## Story

Là kỹ sư của đội, tôi muốn Flywheel Console nằm trong repo thành một package có test, để ai cũng dựng lại được chỉ mục từ `fwdata/` và chạy console bằng `fw console serve`, thay cho bản thử v5 đang nằm ngoài git và đọc dữ liệu dựng tay bằng script trong thư mục tạm.

## Tiêu chí chấp nhận

1. Package mới `packages/flywheel-console` (module `flywheel.console`) đăng ký lệnh `fw console index`, `fw console serve`, `fw console bench` qua entry-point `flywheel.commands`.
2. `fw console index` dựng toàn bộ dữ liệu của console từ `fwdata/`, seed catalog và file trích dẫn trong package, ghi vào `$FW_ROOT/console/index/`. Không đường dẫn tuyệt đối nào của máy cá nhân nằm trong mã. Chạy trên một `FW_ROOT` rỗng vẫn ra chỉ mục hợp lệ, không lỗi.
3. Số chỉ có trong tài liệu (eval C, chuỗi Failure→Data) nằm trong `seed/cited.yaml`, mỗi dòng có tài liệu, mục và câu gốc; một test kiểm câu gốc còn trong tài liệu ở commit hiện tại (BA mục 17 ý 5).
4. `fw console serve` chỉ nghe `127.0.0.1`, phục vụ giao diện v5 đã ghép (BA 15.1b), có HTTP Range, và giữ mọi ràng buộc của BA mục 12 và 15.1a: POST chỉ từ chính console, đường dẫn chỉ trong `fwdata/`, từ chối `vault/` và holdout, ảnh egocentric chỉ từ `*.deid.mp4`, bộ chạy việc chỉ nhận loại việc trong danh sách cho phép.
5. Chatbot chỉ gọi `http://127.0.0.1:11435/v1`; công cụ, nhãn CODE/LLM, kiểm số có nguồn và lệnh `/` giữ như BA 15.1b. Bench chạy được bằng `fw console bench`.
6. Sửa bốn điểm còn hở của BA 15.1b: theme sáng đúng trên mọi trang; nhãn sankey Failure→Data không chồng nhau; filmstrip khi di chuột cho episode egocentric (chỉ từ bản deid); câu hỏi chéo trang và câu "vì sao 68 lần sinh S1 thất bại" qua bench.
7. Giới hạn chữ của giao diện có test pytest.
8. `uv run ruff check`, `uv run mypy`, `uv run pytest`, `uv run lint-imports` sạch; import-linter có hợp đồng mới: `flywheel.console` không import `flywheel.data`, `flywheel.eval`, `flywheel.loop`, `flywheel.cli`, adapter hay runtime.

## Nhiệm vụ

Theo [plan DA-40](../../superpowers/plans/2026-11-11-da40-flywheel-console.md); mỗi nhiệm vụ một commit.

- [x] 1. Khung package, `ConsolePaths`, lệnh `fw console`, đăng ký trong workspace và import-linter (AC 1, 8)
- [x] 2. Chỉ mục catalog và dữ liệu trích dẫn (AC 2, 3)
- [x] 3. Chỉ mục dataset robot, egocentric và ảnh đại diện (AC 2)
- [x] 4. Chỉ mục run, eval, vòng lặp, chi phí; lệnh `fw console index` (AC 2)
- [x] 5. Server, media và bộ chạy việc (AC 4)
- [ ] 6. Chatbot, công cụ và bench (AC 5, 6)
- [x] 7. Giao diện, bốn điểm hở và giới hạn chữ (AC 6, 7)
- [ ] 8. Ghép trên dữ liệu thật, kiểm trên trình duyệt, bench (AC 1–8)

## Phạm vi file

Theo 07 mục 3.1. File story luôn được sửa.

- `packages/flywheel-console/**` (package mới)
- `pyproject.toml` gốc: chỉ thêm `flywheel-console` vào `dependencies`, `tool.uv.sources`, `mypy_path`, overrides mypy của `cv2`, và một hợp đồng import-linter mới
- `uv.lock`: chỉ phần do thêm package
- `docs/superpowers/plans/2026-11-11-da40-flywheel-console.md`

## Ghi chú cho người làm

- Nguồn chuyển sang là bản v5 ngoài repo, `.superpowers/brainstorm/mockups/v5/` trong worktree của phiên này, cùng `CONTRACTS.md`, `DESIGN.md` ở đó. Không commit `data/` và `cache/` của v5: chỉ mục dựng lại từ `fwdata/`.
- Không commit dữ liệu (`fwdata/`), checkpoint, `.env`.
- Console là công cụ đọc. Ghi chỉ qua bộ chạy việc (lệnh `fw` trong danh sách cho phép) và trace chat, đều dưới `fwdata/console/`.

## Kiểm thử

- `uv run pytest packages/flywheel-console`
- `uv run ruff check`, `uv run mypy`, `uv run lint-imports` theo README gốc.

## Người phụ trách

- Làm: Dương Đình Hiếu, qua phiên Claude điều phối các subagent Sonnet
- Duyệt và merge: Dương Đình Hiếu (người duy nhất, 07 mục 3.4)

## Change log

| Ngày | Nội dung | Người |
|---|---|---|
| 11/11/2026 | Tạo story theo quyết định của PO; mã DA-40 chưa dùng trong `docs/` và trên các nhánh | Hiếu |
