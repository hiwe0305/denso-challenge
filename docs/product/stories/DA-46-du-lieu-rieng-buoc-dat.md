# DA-46 · Dữ liệu riêng cho bước đặt khay

## Trạng thái

| Trường | Giá trị |
|---|---|
| Trạng thái | Đang làm (mở ngày 23/11/2026; dừng sau lô mẫu trên laptop để Hiếu xem) |
| Người làm | Hiếu |
| Làn | Ngoài ba làn: adapter `flywheel-simple` (task bê khay), không sửa nhân hay làn |
| Nguồn yêu cầu | Kế hoạch vòng chung kết ngày 19/11/2026 (`docs/mentor/2026-11-19-ke-hoach-vong-chung-ket.md`, chưa có trong git), hướng B: dữ liệu riêng cho bước đặt. Quyết định của Hiếu ngày 23/11/2026: sinh dữ liệu này trước, rồi train một lần trên toàn bộ |
| Nhãn | `area:sim`, `area:data` |
| Sprint | Sau demo 17/11/2026, trước vòng chung kết (khoảng 3/12/2026) |
| Ước lượng | 10 giờ tới hết lô mẫu (ước lượng); lô trên `rtx3060` tính riêng sau khi Hiếu xem mẫu |
| Phụ thuộc | DA-41 (đã merge, PR 205): cảnh đồ gá `jig2`, planner `da41-planner-8`, lô 568 episode. Không chặn ai |

## Story

Là người train policy Ψ₀ cho task bê khay, tôi muốn có thêm dữ liệu tập trung vào đoạn tới bàn B, chỉnh vị trí, hạ và nhả khay, trong đó robot tới nơi lệch đích rồi tự sửa, để policy học được bước đặt, là bước nó hỏng nhiều nhất.

Hiện trạng ngày 23/11/2026 (thực đo trên lô DA-41, [jig.md](../../g0/tray/jig.md) mục 4.13): trong 568 episode, ARRIVE_B + LOWER + RELEASE chiếm trung vị 18,8 % số khung, riêng LOWER + RELEASE 8,5 %. Planner luôn tới gần đúng chỗ (lệch ngang trung bình gần 0), nên dữ liệu gần như không có trường hợp "tới lệch, sửa, rồi đặt".

## Cách làm

**[Claude đề xuất 23/11/2026; Hiếu đã xem dàn ý, chưa duyệt chính thức.]** Ba phương án đã cân nhắc:

| Phương án | Nội dung | Được | Mất |
|---|---|---|---|
| A | Cắt đoạn đặt ra từ 568 episode đang có | Không tốn sim | Không có trạng thái mới, chỉ đổi tỉ trọng: vẫn không có ca tới lệch rồi sửa |
| B | Khởi tạo sim ở trạng thái đã cầm khay gần bàn B | Rẻ nhất mỗi episode | Phải lưu và nạp lại trạng thái sim lẫn planner giữa episode; QA phát lại theo `uid` không còn dựng lại được cảnh. Quá rủi ro cho ba ngày |
| **C (chọn)** | Sinh episode đầy đủ với seed mới, làm lệch đích của pha CARRY để robot tới nơi lệch, rồi cắt lấy phần từ ARRIVE_B tới hết | Có trạng thái mới đúng loại đang thiếu; episode đầy đủ đi qua đúng đường sinh, QA phát lại và release của lô DA-41 | Tốn sim ngang một lô đầy đủ (khoảng 70 s mỗi lượt trên `rtx3060`, thực đo ở lô DA-41) |

Vì sao C: pha ARRIVE_B của planner đã có sẵn vòng sửa (bước tới khi khay cách đích dưới `arrive_lat_tol` theo hai trục, `_arrive_plan` trong `tray/planner.py`), nên chỉ cần cho robot tới lệch là thu được đúng đoạn "sửa rồi đặt" mà không viết hành vi mới. Bản cắt là một release dẫn xuất, ghi release cha và khoảng khung nguồn của từng episode.

## Tiêu chí chấp nhận

1. `gen_log.jsonl` ghi cho mỗi lượt các mốc vào pha (`phases`: tên pha, giây sim tính từ lúc planner bắt đầu) và độ lệch đích CARRY đã áp (`carry_offset`: tới trước, sang ngang, mét).
2. Planner có tùy chọn làm lệch đích CARRY (tới trước và sang ngang, mét), rút từ seed của episode nên chạy lại ra đúng độ lệch đó. Với mặc định (0), lệnh, quỹ đạo và chuỗi `planner_version` giữ nguyên `da41-planner-8+cfg.bee61399` (có test). Khi bật, chuỗi `planner_version` khác, nên `generate` không cho hai loại vào chung một thư mục.
3. Lệnh cắt: từ một release đầy đủ và mốc pha trong `gen_log`, dựng release dẫn xuất giữ mỗi episode từ ARRIVE_B (trừ một đoạn dẫn chỉnh được, mặc định khoảng 1 s) tới hết. Đầu ra là LeRobot v2.1 cùng layout Ψ₀ với release cha (state 32, action 36, 50 fps, video camera đầu có số khung bằng số dòng), `stats.json` và `stats_psi0.json` tính lại trên bản cắt, có bản ghi release cha và khoảng khung nguồn của từng episode. Đường train hiện có (`demo_sets`, `scripts/he/demo_subset.py`, ghép tập) nhận release này cạnh hai release kiểu cha. Có test trên dữ liệu nhỏ.
4. Lô mẫu trên laptop: ít nhất 6 lượt có lệch và đúng các seed đó không lệch, mức 1 và vài lượt mức 2. Báo tỉ lệ thành công có và không lệch, sai lệch đặt (vị trí và góc so với đích đồ gá), độ dài đoạn đặt, và một video bản cắt để Hiếu xem. Biên độ lệch chọn theo số đo: bắt đầu quanh ±5 cm, thử lớn hơn (ví dụ ±10 cm) nếu tỉ lệ thành công giữ được; ghi lại những gì đã thử.
5. Sau khi Hiếu xem mẫu (ngoài phiên làm việc đầu của story): lô trên `rtx3060`, kho riêng dưới `fwdata/datasets/<store>/`, có thẻ dataset và `round.yaml` như lô DA-41.
6. `uv run ruff check`, `uv run mypy`, `uv run pytest`, `uv run lint-imports` sạch; `scripts/repo/pr_guard.py` qua.

## Nhiệm vụ

- [x] 1.1 Viết story (file này)
- [x] 2.1 `gen_log.jsonl` ghi `phases` và `carry_offset` của từng lượt, có test (AC 1)
- [x] 2.2 Tùy chọn làm lệch đích CARRY theo seed trong planner, agent, `generate` và `planner_version`, có test (AC 2)
- [x] 3.1 Lệnh cắt release dẫn xuất từ ARRIVE_B, có test trên dữ liệu nhỏ (AC 3)
- [ ] 4.1 Lô mẫu trên laptop, số đo và runbook nháp cho `rtx3060` trong `docs/g0/tray/place-data.md` (AC 4)
- [ ] 4.2 Chạy đủ kiểm tra, `pr_guard`, mở PR (AC 6)
- [ ] 5.1 Lô trên `rtx3060`, kho, thẻ dataset, `round.yaml` (AC 5; sau khi Hiếu xem mẫu)

## Phạm vi file

Theo 07 mục 3.1. File story luôn được sửa.

- `packages/flywheel-simple/src/flywheel_simple/tray/`
- `packages/flywheel-simple/tests/tray/`
- `scripts/g0/tray/`
- `docs/g0/tray/`

## Ghi chú cho người làm

- Không sửa `flywheel.contracts`. Nếu bản cắt cần trường hợp đồng mới thì dừng lại và báo Hiếu.
- `planner_version` băm mọi trường của `PlannerConfig` (`recorder.planner_version`), và `configs/sim/tray_planner.yaml` nằm ngoài phạm vi. Vì vậy độ lệch không được là trường của `PlannerConfig`: nó là tham số riêng, chỉ thêm hậu tố vào chuỗi phiên bản khi khác 0.
- Một thư mục sinh chỉ chứa một `planner_version`. Lô có lệch và lô đối chứng không lệch nằm ở hai thư mục.
- Lấy một dải seed train mới, chưa dùng (bảng seed ở [jig.md](../../g0/tray/jig.md) mục 5.1), và ghi dải đó vào `docs/g0/tray/place-data.md`.
- Khay dừng ngắn khoảng 1,5 cm theo trục dọc (jig.md mục 4.13) không sửa ở story này, để dữ liệu mới nhất quán với 568 episode đang có.
- QA phát lại, QA DA-03 và bộ lọc chất lượng chạy trên episode đầy đủ của release cha. Bản cắt chỉ lấy các episode cha đã qua (tập `ALL` của cha), vì một episode bắt đầu giữa chừng không phát lại được theo `uid`.
- Không chạy gì trên `rtx3060` trước khi Hiếu xem lô mẫu. Laptop chỉ chạy một worker sim mỗi lúc (khoảng 3,7 GB), xem `free -g` trước.
- Số chưa đo ghi là ước lượng.

## Kiểm thử

- `uv run pytest packages/flywheel-simple`
- Test `sim` trong venv SIMPLE: `MUJOCO_GL=egl PYTHONPATH=packages/flywheel-simple/src fwdata/simple/.venv/bin/python -m pytest packages/flywheel-simple/tests/tray -m sim -k "cut or jitter" -v`
- `uv run ruff check`, `uv run mypy`, `uv run lint-imports` theo README gốc
- `python3 scripts/repo/check_links.py`

## Người phụ trách

- Làm: Dương Đình Hiếu, cùng Claude
- Duyệt và merge: Dương Đình Hiếu (người duy nhất, 07 mục 3.4)

## Change log

| Ngày | Nội dung | Người |
|---|---|---|
| 23/11/2026 | Tạo story theo quyết định của Hiếu ngày 23/11/2026 (sinh dữ liệu bước đặt trước, train một lần); phương án C do Claude đề xuất | Hiếu (soạn với Claude) |
