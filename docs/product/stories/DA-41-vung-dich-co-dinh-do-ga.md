# DA-41 · Vùng đích cố định có đồ gá định vị cho task bê khay

## Trạng thái

| Trường | Giá trị |
|---|---|
| Trạng thái | Nhiệm vụ 6 chưa đánh dấu xong: planner `da41-planner-8` trên laptop được 60/61 ở mỗi cảnh (98 %, Wilson 95 % 91–100 %), gồm 31 episode cũ 30/31 và 30 seed mới 30/30 (jig.md mục 4.8). Đạt ≥ 95 % theo số điểm, chưa theo cận dưới khoảng tin cậy. Kiểm 50 seed trên `rtx3060` chờ Hiếu chạy (runbook jig.md mục 5) |
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
  - [x] 6.2 Sửa planner (căn góc trước khi hạ và trong lúc hạ, tư thế tay giơ sẵn) và hạ thấp cánh ngắn phía robot của đồ gá (nguyên nhân (a) ở hình học), test CPU và test `sim`
  - [x] 6.3 Đo lại đúng 31 episode cũ trên laptop, có và không đồ gá; bảng trước/sau và runbook 50 seed mới trong jig.md
  - [x] 6.4 (Thêm 20/11/2026, PO xem video mẫu và chọn "Sửa tiếp") Đo tỉ lệ lặp lại của ba lỗi còn lại (1:10, 1:16, 1:20) bằng nhiễu nhỏ ở chỗ đứng và tư thế khay; nguyên nhân gốc, ghi trong jig.md
  - [x] 6.5 Sửa theo nguyên nhân, theo thứ tự 1:10 (nhả khay trong đồ gá), 1:16 (cầm lệch một tay), 1:20 (ARRIVE_B); test CPU. Kết quả: sửa được 1:20 (ARRIVE_B quyết bước trên base đã lọc, `da41-planner-8`); 1:10 và 1:16 chưa có cách sửa nào qua được kiểm tra (`release_dz` −0,02 làm hỏng hai lượt khác, độ lệch cầm không dự báo lỗi), ghi là lỗi còn lại trong jig.md 4.8
  - [x] 6.6 Đo lại 31 episode cũ và một tập seed chưa dùng để chỉnh (mức 1 seed 21–40, mức 2 seed 110–119), có và không đồ gá; bảng, n và khoảng tin cậy trong jig.md; runbook
  - [x] 6.7 Bộ video mẫu mới trong `fwdata/da-41-samples/` (ngoài repo) cho Hiếu xem; dọn file tạm. Bốn video planner-8: 1:20 không đồ gá, 1:10 và 2:115 đồ gá (trước hỏng, nay đạt), 1:16 đồ gá (còn hỏng); xóa bốn video planner-7 cũ và file tạm (khoảng 26 MB)
- [x] 7. Lô mẫu dữ liệu nhỏ với `da41-planner-8` trên cảnh có đồ gá (PO 20/11/2026: "Oke và mục tiêu của tôi là nâng các chỉ số của nó lên được 9x"), xem mẫu trước khi sinh cả lô
  - [x] 7.1 Trên laptop, sinh khoảng 20 episode bằng đường S1 thật (`generate.py --scene jig`, QA phát lại, bộ lọc chất lượng, export Ψ₀), mức 1 và mức 2, seed train chưa dùng; thư mục riêng ngoài repo, không phải release. Lô `fwdata/da-41-sample-batch/`: 20 lượt, 19 ghi được, 19 qua QA phát lại (sau khi sửa `replay_qa` chạy đúng cảnh đồ gá), QA DA-03, bộ lọc chất lượng
  - [x] 7.2 Kiểm lô như dữ liệu train: số episode qua lọc, độ dài, chiều action và state, camera đầu, `visuals_revision`, `planner_version`, cờ 7 bước; so với lô 606 episode cũ. Bảng ở jig.md mục 4.9; đủ chiều, không NaN, video khớp số dòng. Bất thường: phát lại động học DA-17 chạy cảnh cũ nên mọi episode bị `flag` D7/D8 (việc ngoài DA-41)
  - [x] 7.3 Mẫu xem: 4 episode (2 mỗi mức) camera đầu đúng như policy thấy cạnh góc nhìn ngoài; ảnh tổng hợp cả lô: vị trí và góc đặt cuối so với đích, độ thấy đồ gá và vùng đích trong camera đầu lúc hạ và nhả; thời gian sinh mỗi episode; dọn file tạm. `fwdata/da-41-sample-batch/xem-mau/`: 4 video, ảnh tổng hợp; vùng đích chiếm 3,2–6 % ảnh camera đầu lúc hạ, đồ gá 0,4–0,7 %
- [ ] 8. Sửa phát lại động học DA-17 cho cảnh đồ gá và soạn runbook sinh lô 600 (PO 20/11/2026: "Làm đi")
  - [x] 8.1 Adapter `flywheel_simple/replay/run.py` chọn env theo `uid` đã ghi; dừng với lỗi rõ khi episode sẽ phát lại trên cảnh khác; giữ hành vi với cảnh cũ (có test)
  - [x] 8.2 Chạy lại phát lại động học và `fw data qa --replay` trên lô mẫu 19 episode; cờ D7, D8 trước và sau trong jig.md mục 4.9. Kết quả ở mục 4.10: không còn dòng `mismatch`; D8 15 → 7, D7 19 → 19. Cờ còn lại do ngưỡng `replay-1` (hiệu chỉnh trên psi-data) và bộ phát lại của SIMPLE, không do đồ gá: đối chứng 3 episode cảnh cũ cho cùng kết quả (việc của DA-17, mục 6)
  - [ ] 8.3 Kết luận ngắn: (a) seed 400005 `timeout:RELEASE`; (b) độ lệch +1,0 cm theo trục dọc, có sửa được bằng một tham số không
  - [ ] 8.4 Runbook `rtx3060` cho lô khoảng 632 lượt (khoảng 600 episode qua lọc), từ sinh tới `demo_sets`, kèm điều kiện dừng; Hiếu chạy

## Phạm vi file

Theo 07 mục 3.1. pr-guard chặn PR sửa file ngoài danh sách này; file story luôn được sửa.

- `packages/flywheel-simple/src/flywheel_simple/tray/` trừ `predicates.py`, `run.py` (DA-42)
- `packages/flywheel-simple/tests/tray/` trừ `test_predicates.py`, `test_run_*.py` (DA-42)
- `configs/sim/tray_jig.yaml`, `configs/sim/tray_planner.yaml`
- `scripts/g0/tray/`
- `docs/g0/tray/`
- `docs/superpowers/specs/2026-10-28-tray-transfer-he-design.md` (chỉ mục 3.1, 3.5 và dòng sửa đổi)
- `packages/flywheel-simple/src/flywheel_simple/replay/run.py` và test của nó `packages/flywheel-simple/tests/replay/test_replay_trace.py`: PO (Hiếu) mở rộng phạm vi ngày 20/11/2026 cho nhiệm vụ 8.1, chỉ hai file này

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
| 20/11/2026 | Thêm nhiệm vụ 8 và mở rộng phạm vi file cho `replay/run.py` và test của nó (PO: "Làm đi") | PO (Hiếu) |
| 20/11/2026 | Thêm nhiệm vụ 7: lô mẫu dữ liệu nhỏ với planner-8 (PO đồng ý sinh thử) | PO (Hiếu) |
| 20/11/2026 | Thêm nhiệm vụ 6.4–6.7: sửa tiếp ba lượt còn hỏng sau khi xem video mẫu (PO: "Sửa tiếp") | PO (Hiếu) |
| 19/11/2026 | AC 3: cấu hình đồ gá ở `configs/sim/tray_jig.yaml` thay vì `tray.yaml` (file bị run plan DA-34 ghim sha256) | Hiếu (cùng Claude) |

## Ghi chép khi làm

- 19/11/2026 · Chỉ thêm file; sáu file bị ghim không đổi (test sha256 trong `test_jig.py`). Đồ gá là geom của `table_b`, để `tray_state` tính khay trên đồ gá là trên bàn B.
- 19/11/2026 · Hình học chốt sau nhiều vòng chạy planner: tường đứng 3,5 cm, vát tới 6,5 cm, bỏ cánh dài phía robot (khuỷu tay trái chạm). Lý do từng lựa chọn ở jig.md mục 3.
- 19/11/2026 · Planner trên 31 lượt: 25/31 với đồ gá, 26/31 không đồ gá. Lỗi còn lại ở planner (cổ tay chạm cánh ngắn phía robot, xoay khi buông, REACH hết giờ); việc sau ở jig.md mục 6.
- 19/11/2026 · Ảnh camera đầu: đồ gá thấy được từ CARRY trở đi nhưng dưới 0,7 % ảnh, ít hơn vùng đích 2–7 lần; lúc TURN không thấy cả hai.
- 20/11/2026 · Nhiệm vụ 6: nguyên nhân gốc ở jig.md mục 4.5; cổ tay chạm cánh ngắn phía robot là do hình học, nên cánh đó thấp hơn (`jig2`). Planner `da41-planner-7`: căn góc ở ARRIVE_B và trong LOWER, tay giơ sẵn rộng hơn.
- 20/11/2026 · Đo lại 31 episode (laptop): đồ gá 25/31 → 29/31, không đồ gá 26/31 → 29/31. Lỗi cũ hết; còn 1:16 (cầm lệch một tay, cả hai cảnh), 1:10 (khay dội khi nhả trong đồ gá), 1:20 (ARRIVE_B hết giờ, không đồ gá). Chưa đạt ≥ 95 % nên nhiệm vụ 6 chưa đánh dấu xong.
- 20/11/2026 · Nhiệm vụ 6.4–6.6: ba lỗi còn lại là lỗi xác suất thấp (0–15 % khi chạy lại có nhiễu). Sửa được 1:20 ở nguyên nhân (pelvis đung đưa ±2 cm, ARRIVE_B nay quyết bước trên vị trí đã lọc, `da41-planner-8`). Đo lại: 31 episode cũ 30/31, 30 seed mới (mức 1 seed 21–40, mức 2 seed 110–119) 30/30, ở cả hai cảnh. Còn 1:16 (cầm lệch một tay).
