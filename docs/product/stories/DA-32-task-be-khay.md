# DA-32 · Task bê khay công nghiệp trên SIMPLE (MuJoCo)

## Trạng thái

| Trường | Giá trị |
|---|---|
| Trạng thái | Sẵn sàng (PO duyệt 28/10/2026) |
| Người làm | Hiếu |
| Làn | Adapter simulator (`flywheel-simple`) |
| Story PRD | Story của [design 28/10/2026](../../superpowers/specs/2026-10-28-tray-transfer-he-design.md) mục 3, 4, 7 (M0, M1) |
| Nhãn | [Adapter] · `epic:9` · `gate:G1` · `area:sim` |
| Sprint | S1 tuần 1 đến S2 tuần 1; M0 1/11/2026, M1 4/11/2026 |
| Ước lượng | 20 giờ (khoảng 16–26, ước lượng) |
| Phụ thuộc | S1-02 (môi trường SIMPLE chỉ MuJoCo, `scripts/g0/setup_simple.sh`, cùng người làm). PR `chore-restructure` (khung `packages/flywheel-simple/`, merge 29/10). Không phụ thuộc người khác |

## Story

Là trưởng nhóm, tôi muốn có task G1 bê khay linh kiện từ bàn A sang vùng đích trên bàn B, chạy trong SIMPLE ở chế độ chỉ MuJoCo, để sinh synthetic (DA-33) và chạy thí nghiệm egocentric (DA-34) trên một task giống công việc nhà máy.

## Tiêu chí chấp nhận

1. Bộ điều khiển đứng và đi dùng chung trên decoupled WBC (`flywheel_simple.wbc`), chạy trong môi trường của S1-02: trên task hai bàn, G1 tháo dây treo trong 200 bước, đứng 400 bước với hông 0,70–0,78 m và trục thân ≥ 0,99, đi lùi 0,5–0,9 m với `navigate_cmd = [−0,25, 0, 0, 0]` trong 3 s.
2. Mọi kích thước, khối lượng, ma sát, dung sai của task nằm trong `configs/sim/tray.yaml`, mặc định theo design mục 3.1; hình học cảnh (tâm hai bàn, hành lang, chỗ đặt khay, vùng đích) tính từ cấu hình và có test.
3. Cảnh tĩnh trong MuJoCo thuần (sàn, hai bàn, khay có hai tay cầm và 6 ô, 6 linh kiện tự do): sau 30 giây sim, khay xê dịch < 5 mm, mọi linh kiện còn trong ô của nó, không có tiếp xúc xuyên quá 2 mm (M0).
4. Task `g1_wholebody_tray_transfer_teleop` (robot `g1_sonic`, decoupled WBC) đăng ký từ `flywheel-simple` (không fork SIMPLE), env id `simple/G1WholebodyTrayTransferTeleop-v0`; reset ở `sim_mode=mujoco`, G1 đứng giữa hai bàn gần bàn A, khay và linh kiện đứng yên; camera đầu ra ảnh; tay G1 với tới độ cao tay cầm (M0).
5. Ngẫu nhiên hóa ba mức (design mục 3.5), tất định theo hạt giống; dải hạt giống train, dev, holdout rời nhau.
6. Vị từ 7 bước (design mục 3.2), `check_success()` theo design mục 3.4, nhãn lỗi L-PART-DROP, L-TRAY-TILT, L-ONE-HAND, L-PLACE-POSE, L-TIMEOUT, L-BALANCE; logic thuần có test chạy trong CI (M1).
7. `check_success()` trong sim đúng với quỹ đạo oracle: khay đặt đúng vùng đích thì đạt, lệch vùng đích hoặc rơi linh kiện thì không đạt; script xem cảnh ghi video (M1).

## Nhiệm vụ

- [x] 1. Bộ điều khiển đứng và đi trên decoupled WBC (AC 1)
- [x] 2. Cấu hình và hình học cảnh (AC 2)
- [x] 3. MJCF khay và linh kiện, kiểm cảnh tĩnh (AC 3)
- [x] 4. Task SIMPLE và env id, reset ở `mujoco` (AC 4)
- [x] 5. Ngẫu nhiên hóa ba mức và dải hạt giống (AC 5)
- [x] 6. Vị từ 7 bước, thành công, nhãn lỗi (AC 6)
- [ ] 7. Kiểm thành công bằng quỹ đạo oracle, script xem cảnh (AC 7)

## Phạm vi file

Theo 07 mục 3.1. pr-guard chặn PR sửa file ngoài danh sách này; file story luôn được sửa.

- `packages/flywheel-simple/src/flywheel_simple/tray/`, `packages/flywheel-simple/tests/tray/`
- `packages/flywheel-simple/src/flywheel_simple/wbc/`, `packages/flywheel-simple/tests/wbc/`
- `configs/sim/tray.yaml`
- `scripts/g0/tray/`
- `docs/g0/tray/`, `docs/g0/ledger/DA-32.csv`

## Ghi chú cho người làm

- Kế hoạch chi tiết: [docs/superpowers/plans/2026-10-28-da32-tray-task.md](../../superpowers/plans/2026-10-28-da32-tray-task.md).
- Logic thuần (cấu hình, hình học, ngẫu nhiên hóa, vị từ) không import `simple` hay `mujoco`, có test chạy trong CI. Mã import `simple` hoặc `mujoco` chỉ chạy trong môi trường SIMPLE; test của nó gắn marker `sim` (03 mục 7).
- Nếu tay G1 không với tới tay cầm ở bàn 0,85 m, hạ bàn về 0,65 m như task hai bàn của SIMPLE và ghi `Decision` (AC 4).
- Không commit dữ liệu, video, asset tải về; để trong `fwdata/`.

## Kiểm thử

- `uv run pytest packages/flywheel-simple/tests/tray -m "not sim"` trong workspace.
- `pytest packages/flywheel-simple/tests/tray packages/flywheel-simple/tests/wbc -m sim` trong môi trường SIMPLE của S1-02 (`fwdata/simple/.venv`).

## Người phụ trách

- Làm: Dương Đình Hiếu
- Duyệt và merge: Dương Đình Hiếu (người duy nhất, 07 mục 3.4)

## Change log

| Ngày | Nội dung | Người |
|---|---|---|
| 28/10/2026 | Tạo story theo design 28/10/2026 | PO (Hiếu) |
| 28/10/2026 | Đổi sang decoupled WBC (`g1_sonic`); môi trường chuyển về S1-02; nhiệm vụ con 1 thành bộ điều khiển đứng và đi dùng chung | PO (Hiếu) |

## Ghi chép khi làm
