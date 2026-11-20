# DA-41 · Vùng đích cố định có đồ gá định vị cho task bê khay

## Trạng thái

| Trường | Giá trị |
|---|---|
| Trạng thái | Đang làm nhiệm vụ 6 (sửa planner, PO 20/11/2026). Nhiệm vụ 1–5 xong trên laptop; kiểm 50 seed trên `rtx3060` chờ Hiếu chạy (runbook ở jig.md mục 5). Mục tiêu planner ≥ 95 % chưa đạt (25/31 trên laptop) |
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
3. Đồ gá là body tĩnh ở tư thế đích: thanh dẫn thấp ở bốn góc, có vát, để trống chỗ hai tay cầm; kích thước và ma sát nằm trong file cấu hình, không viết cứng (`configs/sim/tray_jig.yaml`, vì `tray.yaml` bị run plan ghim; sửa 19/11/2026); hình học tính từ cấu hình và có test CPU.
4. `visuals_revision` có hậu tố mới; `generate` và `export` từ chối trộn episode cũ với episode mới như đã làm với `+zone1`.
5. Trong MuJoCo: khay đặt đúng đích đứng yên trong đồ gá; khay thả lệch vài cm tự trượt vào trong dung sai; planner hạ được khay vào đồ gá và hoàn thành episode.
6. Có script ghi ảnh camera đầu của episode planner trên cảnh có đồ gá, và đo đồ gá còn thấy bao nhiêu khi khay đang bưng.
7. [docs/g0/tray/jig.md](../../g0/tray/jig.md) ghi thay đổi, lý do, số đo, và runbook chạy test `sim` cùng kiểm planner (mục tiêu ≥ 95 % trên khoảng 50 hạt giống) trên `rtx3060`.
8. (Thêm 20/11/2026) Planner tìm và sửa nguyên nhân gốc của các lỗi còn lại trên cảnh đồ gá, không nới dung sai chấm và không sửa bộ chấm (DA-42). Mục tiêu ≥ 95 % trên 31 episode laptop và khoảng 50 hạt giống trên `rtx3060`; không đạt thì ghi số thật, không đánh dấu xong.

## Nhiệm vụ

- [x] 1. Story và design
  - [x] 1.1 File story này (AC 1–7)
  - [x] 1.2 Design 28/10/2026 mục 3.1, 3.5 và dòng sửa đổi (quyết định PO 19/11/2026)
- [x] 2. Đích cố định, vị trí rời rạc (tắt), hình học thanh dẫn trong `jig.py` và `configs/sim/tray_jig.yaml`, test CPU (AC 1–3)
- [x] 3. Đồ gá trong cảnh
  - [x] 3.1 Thanh dẫn và tấm trượt là geom của `table_b` trong MJCF, `visuals_revision` có hậu tố `+jig1` (AC 3, 4)
  - [x] 3.2 Env SIMPLE có đồ gá, chọn cảnh trong `generate` (AC 4, 5)
- [x] 4. Kiểm trong sim
  - [x] 4.1 Test `sim` MuJoCo thuần: khay đứng yên, khay thả lệch trượt vào (AC 5)
  - [x] 4.2 Planner hạ khay vào đồ gá, test `sim` qua SIMPLE (AC 5)
  - [x] 4.3 Script ảnh camera đầu và độ thấy đồ gá (AC 6)
- [x] 5. Tài liệu
  - [x] 5.1 `docs/g0/tray/jig.md`: thay đổi, số đo, runbook `rtx3060` (AC 7)
- [ ] 6. Sửa planner cho đạt ≥ 95 % trên cảnh đích cố định có đồ gá (PO 20/11/2026: "Sửa planner trước", trước khi sinh lại dữ liệu; AC 8)
  - [x] 6.1 Nguyên nhân gốc của từng nhóm lỗi còn lại, từ trace của episode hỏng, ghi trong jig.md
  - [ ] 6.2 Sửa planner (căn góc trước khi hạ và trong lúc hạ, tư thế tay giơ sẵn) và hạ thấp cánh ngắn phía robot của đồ gá (nguyên nhân (a) ở hình học), test CPU và test `sim`
  - [ ] 6.3 Đo lại đúng 31 episode cũ trên laptop, có và không đồ gá; bảng trước/sau và runbook 50 seed mới trong jig.md

## Phạm vi file

Theo 07 mục 3.1. pr-guard chặn PR sửa file ngoài danh sách này; file story luôn được sửa.

- `packages/flywheel-simple/src/flywheel_simple/tray/` trừ `predicates.py`, `run.py` (DA-42)
- `packages/flywheel-simple/tests/tray/` trừ `test_predicates.py`, `test_run_*.py` (DA-42)
- `configs/sim/tray_jig.yaml`, `configs/sim/tray_planner.yaml`
- `scripts/g0/tray/`
- `docs/g0/tray/`
- `docs/superpowers/specs/2026-10-28-tray-transfer-he-design.md` (chỉ mục 3.1, 3.5 và dòng sửa đổi)

Nhiệm vụ 6 (20/11/2026) sửa `planner.py`, `jig.py` (trong `flywheel_simple/tray/`), `configs/sim/tray_planner.yaml`, `configs/sim/tray_jig.yaml` và test trong `tests/tray/`; mọi file đều đã nằm trong danh sách trên, nên không cần mở rộng phạm vi. Không file nào bị run plan ghim. Planner mới đổi `PLANNER_VERSION` (`da41-planner-7`) và đồ gá đổi revision (`jig2`), nên episode sinh bằng chúng tách khỏi lô cũ. Hình học đồ gá chỉ đổi ở cánh ngắn phía robot, vì nguyên nhân gốc của nhóm lỗi (a) nằm ở đó (jig.md mục 4.5).

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
| 20/11/2026 | Thêm AC 8 và nhiệm vụ 6: sửa planner trước khi sinh lại dữ liệu (PO: "Sửa planner trước") | PO (Hiếu) |
| 19/11/2026 | AC 3: cấu hình đồ gá ở `configs/sim/tray_jig.yaml` thay vì `tray.yaml` (file bị run plan DA-34 ghim sha256) | Hiếu (cùng Claude) |

## Ghi chép khi làm

- 19/11/2026 · Chỉ thêm file; sáu file bị ghim không đổi (test sha256 trong `test_jig.py`). Đồ gá là geom của `table_b`, để `tray_state` tính khay trên đồ gá là trên bàn B.
- 19/11/2026 · Hình học chốt sau nhiều vòng chạy planner: tường đứng 3,5 cm, vát tới 6,5 cm, bỏ cánh dài phía robot (khuỷu tay trái chạm). Lý do từng lựa chọn ở jig.md mục 3.
- 19/11/2026 · Planner trên 31 lượt: 25/31 với đồ gá, 26/31 không đồ gá. Lỗi còn lại ở planner (cổ tay chạm cánh ngắn phía robot, xoay khi buông, REACH hết giờ); việc sau ở jig.md mục 6.
- 19/11/2026 · Ảnh camera đầu: đồ gá thấy được từ CARRY trở đi nhưng dưới 0,7 % ảnh, ít hơn vùng đích 2–7 lần; lúc TURN không thấy cả hai.
