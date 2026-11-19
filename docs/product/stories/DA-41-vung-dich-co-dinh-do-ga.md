# DA-41 · Vùng đích cố định có đồ gá định vị cho task bê khay

## Trạng thái

| Trường | Giá trị |
|---|---|
| Trạng thái | Đang làm (PO duyệt 19/11/2026, kế hoạch hai tuần cho vòng chung kết) |
| Người làm | Hiếu |
| Làn | Adapter simulator (`flywheel-simple`) |
| Story PRD | [Design 28/10/2026](../../superpowers/specs/2026-10-28-tray-transfer-he-design.md) mục 3.1, 3.5 (sửa 19/11/2026) |
| Nhãn | [Adapter] · `epic:9` · `area:sim` |
| Sprint | Tuần 1 của kế hoạch 19/11/2026 |
| Ước lượng | 10 giờ (khoảng 8–14, ước lượng) |
| Phụ thuộc | DA-32, DA-33 (đã merge). Chạy song song với DA-42 (vị từ, trường kết quả, driver eval), DA-43, DA-44; không sửa file của ba story đó |

## Story

Là trưởng nhóm, tôi muốn vùng đích trên bàn B đứng yên và có đồ gá định vị bằng vật lý, để bước `place` không còn phụ thuộc vào việc policy đoán một tư thế đích bị khay che khi đến gần.

Số đo dẫn tới story ([docs/he/tray.md](../../he/tray.md) mục 19–20): policy tới bàn B ở 62–80 % lượt nhưng chỉ thành công 5–10 trên 60; lỗi dồn ở bước `place`, sai lệch trung vị 7,5 cm so với dung sai 5 cm và 10°. Trước story này, tư thế đích rung ±5 cm và ±10° ở mức 1–2 và chỉ được vẽ bằng một hình chữ nhật phẳng ([target-zone.md](../../g0/tray/target-zone.md)).

## Tiêu chí chấp nhận

1. Trên cảnh có đồ gá, tư thế đích cố định so với bàn B ở mọi mức; khay trên bàn A vẫn rung như cũ. Với cùng hạt giống, tư thế khay, khoảng cách bàn, chỗ đứng, khối lượng linh kiện và ánh sáng giữ nguyên giá trị trước DA-41. Cảnh cũ (`+zone1`) và tư thế đích rung của nó vẫn dựng lại được: các file mà run plan đã đóng băng của DA-34 ghim bằng sha256 không đổi một byte.
2. Có lựa chọn 2–3 vị trí đồ gá rời rạc, tách riêng, mặc định tắt; khi tắt, hành vi đúng như AC 1.
3. Đồ gá là body tĩnh ở tư thế đích: thanh dẫn thấp ở bốn góc, có vát, để trống chỗ hai tay cầm; kích thước và ma sát nằm trong `configs/sim/tray.yaml`; hình học tính từ cấu hình và có test CPU.
4. `visuals_revision` có hậu tố mới; `generate` và `export` từ chối trộn episode cũ với episode mới như đã làm với `+zone1`.
5. Trong MuJoCo: khay đặt đúng đích đứng yên trong đồ gá; khay thả lệch vài cm tự trượt vào trong dung sai; planner hạ được khay vào đồ gá và hoàn thành episode.
6. Có script ghi ảnh camera đầu của episode planner trên cảnh có đồ gá, và đo đồ gá còn thấy bao nhiêu khi khay đang bưng.
7. [docs/g0/tray/jig.md](../../g0/tray/jig.md) ghi thay đổi, lý do, số đo, và runbook chạy test `sim` cùng kiểm planner (mục tiêu ≥ 95 % trên khoảng 50 hạt giống) trên `rtx3060`.

## Nhiệm vụ

- [ ] 1. Story và design
  - [x] 1.1 File story này (AC 1–7)
  - [ ] 1.2 Design 28/10/2026 mục 3.1, 3.5 và dòng sửa đổi (quyết định PO 19/11/2026)
- [x] 2. Đích cố định, vị trí rời rạc (tắt), hình học thanh dẫn trong `jig.py` và `configs/sim/tray_jig.yaml`, test CPU (AC 1–3)
- [ ] 3. Đồ gá trong cảnh
  - [x] 3.1 Thanh dẫn và tấm trượt là geom của `table_b` trong MJCF, `visuals_revision` có hậu tố `+jig1` (AC 3, 4)
  - [ ] 3.2 Env SIMPLE có đồ gá, chọn cảnh trong `generate` (AC 4, 5)
- [ ] 4. Kiểm trong sim
  - [x] 4.1 Test `sim` MuJoCo thuần: khay đứng yên, khay thả lệch trượt vào (AC 5)
  - [ ] 4.2 Planner hạ khay vào đồ gá, test `sim` qua SIMPLE (AC 5)
  - [ ] 4.3 Script ảnh camera đầu và độ thấy đồ gá (AC 6)
- [ ] 5. Tài liệu
  - [ ] 5.1 `docs/g0/tray/jig.md`: thay đổi, số đo, runbook `rtx3060` (AC 7)

## Phạm vi file

Theo 07 mục 3.1. pr-guard chặn PR sửa file ngoài danh sách này; file story luôn được sửa.

- `packages/flywheel-simple/src/flywheel_simple/tray/` trừ `predicates.py`, `run.py` (DA-42)
- `packages/flywheel-simple/tests/tray/` trừ `test_predicates.py`, `test_run_*.py` (DA-42)
- `configs/sim/tray_jig.yaml`, `configs/sim/tray_planner.yaml`
- `scripts/g0/tray/`
- `docs/g0/tray/`
- `docs/superpowers/specs/2026-10-28-tray-transfer-he-design.md` (chỉ mục 3.1, 3.5 và dòng sửa đổi)

## Ghi chú cho người làm

- Run plan đã đóng băng của DA-34 (`configs/runplans/tray/*.yaml`, `pinned_files`) ghim `randomize.py`, `mjcf.py`, `simple_task.py`, `config.py`, `geometry.py`, `configs/sim/tray.yaml`. Sửa một file trong số đó làm job của plan ấy từ chối chạy và làm đỏ test của `flywheel-psi0`. Vì vậy DA-41 chỉ **thêm** file (`jig.py`, `jig_task.py`, `configs/sim/tray_jig.yaml`); `test_jig.py` giữ sha256 của sáu file đó.
- Logic thuần (cấu hình, hình học, ngẫu nhiên hóa) không import `simple` hay `mujoco` và có test chạy trong CI. Test cần MuJoCo gắn marker `sim`.
- Không chạy job trên `rtx3060` hay Colab khi chưa hỏi Hiếu. Việc cần máy đó viết thành runbook trong `jig.md`.
- Không sinh lại dữ liệu và không train trong story này; cảnh mới cần lô mới, thuộc story sau.
- Mã đọc episode cũ theo hạt giống (`flywheel_psi0.tray.place_error`, `evidence`) nằm ngoài phạm vi; story chỉ cung cấp hàm tính đích kiểu cũ và ghi việc cần làm tiếp.

## Kiểm thử

- `uv run pytest packages/flywheel-simple/tests/tray -m "not sim"` trong workspace.
- `MUJOCO_GL=egl PYTHONPATH=packages/flywheel-simple/src fwdata/simple/.venv/bin/python -m pytest packages/flywheel-simple/tests/tray/test_jig_sim.py -m sim` trong môi trường SIMPLE.

## Người phụ trách

- Làm: Dương Đình Hiếu (cùng Claude)
- Duyệt và merge: Dương Đình Hiếu (người duy nhất, 07 mục 3.4)

## Change log

| Ngày | Nội dung | Người |
|---|---|---|
| 19/11/2026 | Tạo story theo quyết định PO 19/11/2026: vùng đích cố định, thêm đồ gá định vị | PO (Hiếu) |

## Ghi chép khi làm
