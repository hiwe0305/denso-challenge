# Vùng đích cố định có đồ gá định vị (DA-41)

Ngày 19/11/2026. Hiếu quyết định [Đã chốt, 19/11/2026]: vùng đích trên bàn B đứng yên, thêm đồ gá định vị bằng vật lý. Story: [DA-41](../../product/stories/DA-41-vung-dich-co-dinh-do-ga.md).

## 1. Vì sao

- Số đo của DA-34 ([docs/he/tray.md](../../he/tray.md) mục 19–20): policy tới bàn B ở 62–80 % lượt nhưng chỉ thành công 5–10 trên 60; lỗi dồn ở bước `place`, sai lệch trung vị 7,5 cm so với dung sai 5 cm, 10°.
- Trước DA-41, đích rung ±5 cm và ±10° ở mức 1–2 (`randomize.py`, `POSE_JITTER`, `YAW_JITTER`) và chỉ hiện bằng hình chữ nhật cam phẳng ([target-zone.md](target-zone.md)), bị khay đang bưng che từ khoảng CARRY + 2 s.
- Đích cố định bỏ một nguồn biến thiên mà policy phải đoán từ ảnh. Đồ gá cho một mốc đứng (thấy được từ CARRY trở đi, nhỏ hơn vùng đích; mục 4.4) và sửa một phần sai lệch nhỏ bằng vật lý.

## 2. Thay đổi gì

### 2.1 Chỉ thêm, không sửa cảnh cũ

Run plan đã đóng băng của DA-34 (`configs/runplans/tray/*.yaml`, `pinned_files`) ghim sha256 của `randomize.py`, `mjcf.py`, `simple_task.py`, `config.py`, `geometry.py`, `configs/sim/tray.yaml`. Sửa một file trong số đó làm job của plan ấy từ chối chạy và làm đỏ test của `flywheel-psi0`. Vì vậy DA-41 **chỉ thêm** [Đề xuất của người làm, cần Hiếu xem]:

| File mới | Vai trò |
|---|---|
| `packages/flywheel-simple/src/flywheel_simple/tray/jig.py` | `JigConfig`, `sample_jig_episode`, hình học thanh dẫn, `add_jig`, `jig_scene_spec`, `write_jig_scene_mjcf` |
| `packages/flywheel-simple/src/flywheel_simple/tray/jig_task.py` | Task SIMPLE thứ hai `g1_wholebody_tray_transfer_jig_teleop`, env id `simple/G1WholebodyTrayTransferJigTeleop-v0`, `make_env` |
| `configs/sim/tray_jig.yaml` | Kích thước, ma sát, lựa chọn vị trí rời rạc |
| `scripts/g0/tray/jig_capture.py`, `scripts/g0/tray/jig_views.py` | Đo vùng bắt của đồ gá; ảnh camera đầu |

Sửa nhỏ ở file không bị ghim: `recorder.visuals_revision(manifest, jig=True)` thêm hậu tố; `generate()` và `scripts/g0/tray/generate.py` có `--scene {zone1,jig}`, mặc định `zone1` (như cũ). [`test_jig.py`](../../../packages/flywheel-simple/tests/tray/test_jig.py) giữ sha256 của sáu file bị ghim.

### 2.2 Đích

- `sample_jig_episode(cfg, jig, level, seed)` = `sample_episode(...)` rồi thay `target_pose` bằng tư thế cố định trên bàn B: tư thế mặc định của `scene_geometry_with_gap` (cách mép bàn B phía hành lang `tray_edge_offset` = 0,20 m, yaw 0). Ở mức 2 đích dời theo khoảng cách hai bàn, tức là đứng yên so với bàn B.
- Mọi trường khác của một hạt giống (tư thế khay trên bàn A, chỗ đứng, khối lượng linh kiện, ánh sáng) giữ nguyên, vì `sample_episode` vẫn rút đích rung ở đúng chỗ cũ trong dãy số ngẫu nhiên rồi mới bị thay.
- `sample_episode` không đổi: episode và eval `+zone1` cũ vẫn tính lại được đích rung của chúng.
- Vị trí rời rạc: `slots: 2` hoặc `3` cho hạt giống chọn một trong các vị trí cách nhau `slot_spacing` dọc bàn B, từ dãy số riêng `[seed, 41]`. **Tắt** (`slots: 1`) theo quyết định 19/11; để cho story sau.

### 2.3 Đồ gá

| Mục | Giá trị (`configs/sim/tray_jig.yaml`) | Vì sao |
|---|---|---|
| Vị trí | Geom của body `table_b`, tên `jig_*`, quanh tư thế đích | `simple_task.tray_state` coi khay "trên bàn B" chỉ khi chạm body `table_b`; khay tựa vào thanh dẫn phải được tính là trên B |
| Khe hở | 6 mm mỗi bên quanh footprint khay | Khay đặt đúng đích không chạm thanh dẫn |
| Tường đứng | Cao 3,5 cm, dày 1 cm | Cao hơn độ cao planner buông khay (`lower_tray_clear` 3,5 cm): khay đã nằm trong tường trước khi tay mở |
| Vát | Từ 3,5 cm lên 6,5 cm, nghiêng 50° so với phương đứng; lead-in 4,2 cm mỗi trục | Khay hạ lệch tới khoảng 4 cm rơi lên mặt vát và trượt vào; 6,5 cm còn thấp hơn mặt dưới tay cầm (7 cm) |
| Cánh | Cạnh dài phía xa 8 cm từ mỗi góc; cạnh ngắn 3,5 cm từ mỗi góc, dừng cách tay cầm ≥ 2 cm | Để trống chỗ tay cầm |
| Phía robot | Không có cánh cạnh dài (`near_side_arm: 0`); giữ cánh cạnh ngắn (`near_end_arm: 0.035`) nhưng thấp hơn: tường 1,5 cm, vát tới 3 cm, lead-in 2,4 cm (`near_end_wall`, `near_end_height`; từ `jig2`, nhiệm vụ 6) | Cổ tay đi qua phía trên khi hạ; xem mục 3 và 4.5 |
| Tấm trượt | Dày 2 mm, phủ footprint + khe hở, vô hình | Không có tấm, mép xa của khay bám mặt bàn thép (ma sát 1,0) và khay kẹt trên mặt vát |
| Ma sát | 0,2 (nhựa acetal / PTFE), ưu tiên tiếp xúc 1 | Ma sát của thanh dẫn và tấm thắng ma sát 1,0 của khay |
| Màu | Xanh lam `(0.05, 0.40, 0.95)`, nhóm vẽ 0 | Khác cam của vùng đích, xanh lá của thùng, xám của bàn |

Vùng đích cam vẫn được vẽ ở tư thế đích (dưới tấm trượt vô hình).

### 2.4 Revision hình ảnh

`visuals_revision` của cảnh có đồ gá là `<revision SimReady>+zone1+jig2` (cảnh hộp trơn: `none+zone1+jig2`). `jig1` là hình học trước nhiệm vụ 6 (cánh ngắn phía robot cao bằng phía xa); không lô nào được ghi bằng nó. `generate` từ chối viết tiếp vào lô `+zone1` bằng cảnh `jig` và ngược lại; `export` từ chối lô có hai revision (như với `+zone1`). Guard eval ngoài repo trên `rtx3060` (`simple-guard.sh`) cần so với revision mới khi eval trên cảnh có đồ gá.

## 3. Quyết định hình học khi làm [Đề xuất, cần Hiếu xem]

Mỗi dòng là một lần thử trên laptop (RTX 3050, venv SIMPLE `fwdata/simple/.venv`, `MUJOCO_GL=egl`).

| Thử | Thấy gì | Đổi |
|---|---|---|
| Thanh dẫn là body riêng | Khay tựa vào đồ gá không chạm `table_b`: bộ chấm coi là còn đang bưng | Geom của `table_b` |
| Vát 45° xuống tận mặt bàn, cao 3 cm, không tấm | Khay thả lệch 3 cm kẹt trên mặt vát, lệch 1,9 cm, nghiêng 2,5° | Thêm tấm trượt 0,2 |
| Cao 4 cm | Thanh dẫn phía robot thò quá mép bàn B 4,5 mm (đích chỉ cách mép 20 cm, `tray_edge_offset` bị ghim) | Bỏ cánh cạnh dài phía robot (dòng sau) |
| Cánh cạnh dài phía robot | Khuỷu tay trái G1 đè lên thanh dẫn khi hạ và nhả khay (mức 0 seed 0: RELEASE hết giờ) | `near_side_arm: 0` |
| Vát xuống tận mặt bàn, có tấm | Tay mở đẩy khay (D-21) trượt 6 cm trên tấm, leo lên mặt vát, kẹt (L-PLACE-POSE) | Thêm tường đứng |
| Tường 1,5 cm | Tay mở xoay khay khoảng 5° khi buông ở 3,3 cm; khay vượt tường (mức 1 seed 1, 2: lệch góc 10,3°) | Tường 3,5 cm |
| Vát tới 5 cm (lead-in 2,4 cm) | 26/31 episode planner; 3 lượt khay rơi lên đỉnh thanh dẫn | Vát tới 6,5 cm (lead-in 4,2 cm): 25/31, sửa 2 lượt đó nhưng thêm 2 lượt khay trượt 6 cm về phía robot (mục 4.3). Giữ 6,5 cm vì lead-in lớn hơn hợp với sai lệch của policy (trung vị 7,5 cm), không vì planner |
| Bỏ cả cánh cạnh ngắn phía robot | Cổ tay không còn chạm, nhưng khay không được căn theo y và góc: 3/8 seed khó đạt, so với 5/8 khi giữ | Giữ `near_end_arm: 0.035` |
| (Nhiệm vụ 6) Cánh ngắn phía robot có vát, dời vào 3,5 cm từ góc | Thanh dẫn nằm dưới lòng bàn tay thay vì cổ tay: 5/8 seed khó nghiêng 15° | Bỏ |
| (Nhiệm vụ 6) Cánh ngắn phía robot chỉ có tường 3,5 cm, không vát | Planner 7/8 seed khó; nhưng trong test MuJoCo thuần, khay thả lệch ≥ 1,5 cm theo y rơi lên đỉnh tường (12/23 test hỏng) | Tường 1,5 cm, vát tới 3 cm (dòng sau) |
| (Nhiệm vụ 6) Cánh ngắn phía robot: tường 1,5 cm, vát tới 3 cm (`jig2`) | Dưới cổ tay còn khoảng 1 cm khi buông ở 3,5 cm; vùng bắt ở mục 4.2; planner ở mục 4.6 | Giữ |

Lựa chọn còn mở:
- Phía robot để trống nên khay lệch về phía robot không được đẩy lại. Sau nhiệm vụ 6, planner đặt trong khoảng 1,5 cm (mục 4.6) nên chưa gặp lại; với policy (sai lệch trung vị 7,5 cm) có thể còn gặp. Hướng: một gờ thấp phía robot dưới tầm khuỷu tay.
- Chọn 5 cm hay 6,5 cm cho vát phía xa: trên 31 episode planner-5, khác 1 lượt, trong nhiễu. Giữ 6,5 cm; kiểm 50 seed (mục 5) trước khi sinh lô.

## 4. Số đo

### 4.1 Test CPU

`uv run pytest packages/flywheel-simple/tests/tray/test_jig.py`: 38 qua (19/11/2026); 42 qua sau nhiệm vụ 6 (thêm kiểm cánh ngắn phía robot thấp hơn). Kiểm cấu hình và `check` (từ chối đồ gá không vừa), đích cố định và mọi trường khác giữ nguyên ở 3 mức × 200 seed, vị trí rời rạc 2 và 3 không đổi dãy số, mọi vị trí nằm trên bàn B với khoảng cách bàn 1,6–2,0 m, mặt trong của tường ở đúng khe hở, mặt vát ra tới lead-in, cánh tránh tay cầm, `visuals_revision` và `generate` từ chối trộn lô, sha256 của sáu file bị ghim.

### 4.2 Test `sim` MuJoCo thuần

[`test_jig_sim.py`](../../../packages/flywheel-simple/tests/tray/test_jig_sim.py): 23 qua trong 2,6 s trên laptop.

- 4 cặp (mức, seed): mọi geom đồ gá thuộc `table_b` đúng tư thế đích, va chạm, ưu tiên 1, ma sát 0,2; không thêm body, khớp hay khối lượng.
- Khay đặt đúng đích không bao giờ chạm thanh dẫn và dịch < 1 mm trong 3 s.
- Khay được giữ và hạ như planner (mối hàn mềm tới một mocap, hạ 5 cm/s, buông ở 3,5 cm) với độ lệch về phía các cạnh có thanh dẫn. Với `jig1`: 2 và 4 cm không lệch góc, 2 cm lệch 4°. Từ `jig2` (nhiệm vụ 6, cánh ngắn phía robot thấp hơn): 1 và 2 cm không lệch góc, 1 cm lệch 2°; 23 test qua trong 2,1 s (20/11/2026). Mọi lượt kết thúc phẳng, cách đích ≤ 2 cm, lệch góc ≤ 3°, đủ 6 linh kiện.

Vùng bắt ([`jig_capture.py`](../../../scripts/g0/tray/jig_capture.py), mức 1 seed 1279, hạ có giữ, 8 hướng; "căn" = cách đích ≤ 1,2 cm, lệch góc ≤ 3°, nghiêng ≤ 2°):

| Lệch | 0° | 4° | 8° |
|---|---|---|---|
| 1 cm | 7/8 | 4/8 | 0/8 |
| 2 cm | 5/8 | 4/8 | 1/8 |
| 3 cm | 4/8 | 2/8 | 1/8 |
| 4 cm | 4/8 | 0/8 | 0/8 |
| 5 cm | 0/8 | 0/8 | 0/8 |

Ba trong tám hướng nghiêng về phía robot (cạnh để trống): đồ gá không đẩy khay về phía xa robot. Với 4–8° lệch góc, mối hàn giữ góc cứng nên khay không được xoay thẳng; phần lớn vẫn nằm phẳng trong dung sai 5 cm, 10° của bộ chấm, chỉ không "căn".

Vùng bắt của `jig2` (20/11/2026, cùng cách đo, hạ có giữ, 8 hướng). Ô ghi "căn / phẳng trong dung sai bộ chấm" (phẳng = nghiêng ≤ 2°, cao < 5 mm; dung sai = cách đích ≤ 5 cm, lệch góc ≤ 10°):

| Lệch | 0° | 2° | 4° |
|---|---|---|---|
| 0,5 cm | 7/8, 8/8 | 8/8, 8/8 | 3/8, 8/8 |
| 1 cm | 6/8, 8/8 | 8/8, 8/8 | 3/8, 8/8 |
| 1,5 cm | 6/8, 8/8 | 6/8, 8/8 | 4/8, 6/8 |
| 2 cm | 5/8, 8/8 | 4/8, 8/8 | 3/8, 7/8 |
| 3 cm | 1/8, 8/8 | 3/8, 8/8 | 1/8, 6/8 |
| 4 cm | 1/8, 8/8 | 1/8, 7/8 | 0/8, 4/8 |

Cánh ngắn phía robot thấp hơn dẫn ít hơn: số lượt "căn" ở 3–4 cm giảm so với `jig1`. Nhưng tới 3 cm và 2°, mọi lượt vẫn nằm phẳng trong dung sai của bộ chấm. Các lượt không phẳng (nghiêng 3,4°, cao 1,6 cm) đều ở lệch góc 4° và lệch về phía +y hoặc chéo: góc khay tựa lên thanh dẫn. Planner sau nhiệm vụ 6 buông trong khoảng 1 cm và 2° (mục 4.6), trong vùng này.

### 4.3 Planner qua SIMPLE

Planner kịch bản (planner-5, `configs/sim/tray_planner.yaml` không đổi) trên env có đồ gá, laptop, một tiến trình, khoảng 35 s một episode. Cùng 31 episode: mức 0 seed 0, mức 1 seed 1–20, mức 2 seed 100–109. "Không đồ gá" là env có đồ gá với `add_jig` tắt: cùng đích cố định, cùng mọi thứ khác.

| Cảnh | Mức 0 | Mức 1 | Mức 2 | Tổng |
|---|---|---|---|---|
| Đích cố định, không đồ gá | 1/1 | 16/20 | 9/10 | **26/31** |
| Đồ gá, vát tới 5 cm | 1/1 | 18/20 | 7/10 | **26/31** |
| Đồ gá, vát tới 6,5 cm (cấu hình giao) | 1/1 | 16/20 | 8/10 | **25/31** |

Lỗi theo seed:

| Seed | Không đồ gá | Đồ gá 5 cm | Đồ gá 6,5 cm |
|---|---|---|---|
| 1:1, 1:2, 1:12 | L-PLACE-POSE, lệch góc 10,1–10,7° | đạt | đạt |
| 1:3 | RELEASE hết giờ | đạt | RELEASE hết giờ, lệch góc 13° |
| 1:5, 1:11 | đạt | đạt | L-PLACE-POSE, khay lệch 6 cm về phía robot |
| 1:7 | đạt | L-TRAY-TILT, 18° | L-TRAY-TILT, 22° (cổ tay trên cánh phía robot) |
| 1:20, 2:108 | đạt | khay trên đỉnh thanh dẫn / lệch 5,9 cm | đạt |
| 2:107 | đạt | L-TRAY-TILT, 22° | L-TRAY-TILT, 15° |
| 2:102 | REACH hết giờ | REACH hết giờ | REACH hết giờ |

Đọc:
- Không đồ gá, lỗi chính trên đích cố định là **lệch góc lúc buông**: khay trượt khoảng 5° trong tay khi đi (ARRIVE_B giữ hướng đã tính lúc TURN) và tay mở xoay thêm khoảng 5° khi buông ở 3,3 cm (`lower_tray_clear`). Trên cảnh cũ, đích rung che lỗi này một phần. Đồ gá sửa đúng loại lỗi này (1:1, 1:2, 1:12).
- Đồ gá thêm hai loại lỗi: cổ tay đè cánh phía robot (1:7, 2:107) và, với vát 6,5 cm, khay trượt về phía robot đang để trống (1:5, 1:11). Seed 1:3 đạt với vát 5 cm nhưng hỏng với 6,5 cm.
- Tổng **chưa đạt mục tiêu ≥ 95 %**; cả ba cấu hình quanh 84 %, như planner trên cảnh cũ (80/95, D-24). Lỗi còn lại cần sửa planner, không phải đồ gá; mục 3 và 6 ghi hướng.
- Trong các lượt đạt, sai lệch cuối với đồ gá 6,5 cm: trung vị 1,8 cm, lớn nhất 4,2 cm; lệch góc trung vị 0,8°, lớn nhất 6,4°. Không đồ gá: trung vị 1,5 cm, lớn nhất 4,4 cm; lệch góc trung vị 3,1°, lớn nhất 8,8°.

Test qua SIMPLE ([`test_jig_task_sim.py`](../../../packages/flywheel-simple/tests/tray/test_jig_task_sim.py)): 5 test đạt trên laptop (19/11/2026). Gồm ba test reset (đích nằm trên đồ gá, phần còn lại của lượt giữ nguyên, vùng đích vẽ đúng chỗ); planner đạt ở mức 0 seed 0; và ít nhất 4/6 lượt đạt ở mức 1 seed 1–6. Lần chạy đầu: 4 đạt, 1 hỏng (245 s, RSS 3,7 GB). Test hỏng là do test sai: nó đòi pha cuối là DONE, trong khi env kết thúc ngay khi task báo đạt, có thể trước DONE (lượt kết thúc ở RETREAT nhưng đã đạt). Test đã sửa và chạy lại đạt (43 s).

### 4.4 Camera đầu

[`jig_views.py`](../../../scripts/g0/tray/jig_views.py) chạy planner trên ba lượt (0:0, 1:1279, 2:125195): cả ba đạt, `visuals_revision` là `4763fbfa…+zone1+jig1` (hình học trước nhiệm vụ 6; cánh ngắn phía robot nay thấp hơn nên còn ít pixel xanh hơn, chưa chạy lại). Script đếm số pixel màu xanh của đồ gá và màu cam của vùng đích trên `head_stereo_left`; bảng dưới là khoảng của ba lượt. PNG và `report.json` để ngoài repo (`fwdata/simple/tray/jig-views`).

| Thời điểm | Pixel xanh (đồ gá) | Pixel cam (vùng đích) |
|---|---|---|
| Đầu TURN | 0 | 0 |
| Đầu CARRY | 313–436 | 1 735–2 108 |
| CARRY + 1 s | 545–659 | 2 002–2 853 |
| CARRY + 2 s | 612–828 | 788–2 146 |
| ARRIVE_B | 576–1 201 | 4 452–7 460 |
| LOWER | 1 023–1 446 | 6 050–7 279 |

Ảnh 640 × 360, tức 230 400 pixel. Đếm màu xanh cần loại sàn: sàn ô vuông cũng xanh xám (khoảng 41, 81, 120). Lần chạy đầu dùng ngưỡng lỏng và đếm nhầm sàn, ra 70–120 nghìn pixel. Script đã sửa: pixel đồ gá có kênh đỏ dưới 1/5 kênh xanh, sàn khoảng 1/3. Số trong bảng là của lần chạy lại với ngưỡng đã sửa.

Đọc:
- Lúc TURN, camera đầu không thấy cả đồ gá lẫn vùng đích: khay đang bê che bàn B.
- Từ CARRY trở đi, đồ gá luôn hiện, nhưng nhỏ: dưới 0,7 % ảnh, ít hơn vùng đích 2–7 lần. Lúc CARRY + 2 s, khi khay che bớt vùng đích, số pixel của hai thứ gần bằng nhau.
- Đồ gá **thấy được** từ camera đầu (AC đạt), nhưng là tín hiệu phụ. Mốc thị giác chính vẫn là vùng đích. Policy có học được vị trí từ đồ gá hay không cần thí nghiệm riêng (mục 6). Nếu cần đồ gá nổi hơn, có thể làm cạnh dẫn cao hoặc dày hơn; đổi hình học thì phải đo lại vùng bắt và planner (mục 4.2, 4.3).

### 4.5 Nguyên nhân gốc của lỗi còn lại (nhiệm vụ 6.1, 20/11/2026)

Hiếu chọn "Sửa planner trước" (20/11/2026). Mỗi nhóm lỗi ở mục 4.3 được xem lại từ trace từng bước của episode hỏng: pha, tư thế khay, pelvis, cổ tay trong hệ khay, tiếp xúc của khay và đồ gá với robot. Script trace để ngoài repo; bảng dưới là điều thấy được.

| Nhóm lỗi | Seed | Thấy trong trace | Nguyên nhân gốc |
|---|---|---|---|
| (a) Cổ tay chạm cánh ngắn phía robot | 1:5, 1:7, 1:11; sau khi sửa (c) thêm 1:8, 1:12, 2:109 | Kiểu cầm ngửa tay giữ cổ tay dưới tay cầm, cách góc gần của khay 2–3 cm ra ngoài: hệ đồ gá x ≈ 0,17–0,19 m, y ≈ ±0,25 m, đúng trên mặt vát của cánh ngắn phía robot (3,5–6,5 cm). Link cổ tay chạm mặt vát từ khi khay còn cao 6,1 cm: khay bị chống ở 4,3–4,8 cm (nghiêng tới 22°) hoặc bị đẩy 4–8 cm theo y lên mặt vát phía xa | **Hình học đồ gá**: cánh ngắn phía robot cao bằng phía xa nằm dưới đường hạ của cổ tay. Planner không có chỗ hạ cổ tay khác với kiểu cầm này |
| (b) REACH hết giờ | 2:102 | Hai tay giơ sẵn lệch khoảng 3 cm so với trục khay (trong hệ khay, tay trái y +0,30, tay phải −0,36). Ngón giữa tay trái móc tay cầm trái trong APPROACH_A, đẩy khay ra xa 2,5 cm (x 1,041 → 1,066), ra ngoài tầm với | Tay giơ sẵn (`ready_y` 0,32 m) chỉ rộng hơn đầu ngoài tay cầm (0,265 m) 5,5 cm. Chỗ đứng lệch ngang 3 cm cộng dao động của bước đưa ngón tay vào đúng hàng tay cầm |
| (c) Lệch góc 10,1–10,7° | 1:1, 1:2, 1:12 (không đồ gá); 1:3 (RELEASE hết giờ, đồ gá) | Lúc buông khay đã lệch −4 đến −5,5°: pelvis trôi −1 đến −3° khi đứng ở ARRIVE_B, và góc khay trong tay khác với góc đã tính lúc LIFT. Mở tay xoay thêm khoảng −5° so với pelvis, cộng lại khoảng −10,6° | ARRIVE_B giữ hướng tính từ lúc LIFT; không đo lại góc khay trước khi hạ, và trong LOWER không có gì sửa góc |
| (d) Khay trượt 6 cm về phía robot | 1:5, 1:11 | Khay đã kẹt trên tường hoặc mặt vát vì (a) hoặc (c); RELEASE đưa tay ra rồi lùi (`release_back` 0,05 m) kéo khay trên tấm trượt ma sát 0,2, phía robot không có gì chặn | Hệ quả của (a) và (c), không phải lỗi riêng của cách nhả: khi khay nằm đúng trong đồ gá, cùng chuyển động nhả không kéo khay |

### 4.6 Sửa và đo lại (nhiệm vụ 6.2, 6.3, 20/11/2026)

Sửa theo nguyên nhân ở mục 4.5. Không đổi bộ chấm, dung sai hay `predicates.py`.

| Nhóm | Sửa | File |
|---|---|---|
| (a) | Cánh ngắn phía robot thấp hơn: tường 1,5 cm, vát tới 3 cm (`jig2`). Hai cách khác đã thử và bỏ (mục 3) | `jig.py`, `tray_jig.yaml` |
| (b) | Tay giơ sẵn rộng hơn: `ready_y` 0,32 → 0,35 m, cách đầu ngoài tay cầm 8,5 cm | `tray_planner.yaml` |
| (c) | ARRIVE_B tính lại hướng và chỗ đứng từ góc khay đo được khi bắt đầu pha (không giữ hướng tính lúc LIFT); trong LOWER, hai tay xoay khay quanh trục đứng qua trung điểm hai tay về đúng góc đích, tối đa 8° (`place_yaw_max_deg`), chỉ khi khay còn trên không | `planner.py`, `tray_planner.yaml` |
| (d) | Không sửa riêng: hết khi (a) và (c) hết (1:5, 1:11 đạt). `release_back` giữ nguyên | |

`PLANNER_VERSION` = `da41-planner-7` (6 là thử nghiệm D-29 chưa merge). Thử và bỏ khi làm:
- ARRIVE_B bước tới khi lệch hướng ≤ 1–2°: robot bước tới bước lui (nhiễu bước ±1°), lắc tuột một tay (1:12 L-ONE-HAND). Góc nhỏ còn lại giao cho tay trong LOWER.
- Dời tay giơ sẵn theo độ lệch ngang đo được của khay, có lọc thông thấp 1 s, thay cho tay rộng hơn: sửa được 2:102, nhưng tín hiệu dao động theo bước hoặc trễ khi robot còn bước ngang, và tay chạm khay ở chỗ khác. Hai seed hỏng: 1:15 và 2:107 (L-ONE-HAND, một lòng bàn tay khép lệch khỏi điểm cầm 2 cm). Bỏ, thay bằng `ready_y` 0,35.

Test CPU: `packages/flywheel-simple/tests/tray` 1 389 qua (20/11/2026). Thêm thế giới đồ chơi xoay khay theo đường nối hai tay, kèm trượt trong tay một lần. Thêm test: tay xoay khay về góc đích khi hạ, ARRIVE_B tính đúng hướng và chỗ đứng, tay giơ sẵn tránh tay cầm, hình học cánh ngắn phía robot. Test `sim` MuJoCo thuần 23 qua (mục 4.2).

**Đo lại trên laptop**: cùng 31 episode như mục 4.3 (mức 0 seed 0, mức 1 seed 1–20, mức 2 seed 100–109), một tiến trình. **Chỉ 31 episode, khoảng tin cậy rộng**: 29/31 là 94 %, khoảng tin cậy Wilson 95 % khoảng 79–98 %; khác 1–2 lượt nằm trong nhiễu.

| Cảnh | Planner | Mức 0 | Mức 1 | Mức 2 | Tổng |
|---|---|---|---|---|---|
| Đồ gá (cấu hình giao) | planner-5, `jig1` (trước) | 1/1 | 16/20 | 8/10 | 25/31 (81 %) |
| Đồ gá (cấu hình giao) | `da41-planner-7`, `jig2` (sau) | 1/1 | 18/20 | 10/10 | **29/31 (94 %)** |
| Đích cố định, không đồ gá | planner-5 (trước) | 1/1 | 16/20 | 9/10 | 26/31 (84 %) |
| Đích cố định, không đồ gá | `da41-planner-7` (sau) | 1/1 | 18/20 | 10/10 | **29/31 (94 %)** |

Lỗi theo seed (trước → sau):

| Seed | Đồ gá | Không đồ gá |
|---|---|---|
| 1:1, 1:2, 1:12 | đạt → đạt | L-PLACE-POSE 10,1–10,7° → đạt |
| 1:3 | RELEASE hết giờ, 13° → đạt | RELEASE hết giờ → đạt |
| 1:5, 1:11 | L-PLACE-POSE, lệch 6 cm → đạt | đạt → đạt |
| 1:7 | L-TRAY-TILT 22° → đạt | đạt → đạt |
| 2:102 | REACH hết giờ → đạt | REACH hết giờ → đạt |
| 2:107 | L-TRAY-TILT 15° → đạt | đạt → đạt |
| 1:10 | đạt → **L-TRAY-TILT 18°** | đạt → đạt |
| 1:16 | đạt → **L-ONE-HAND** | đạt → **L-ONE-HAND** |
| 1:20 | đạt → đạt | đạt → **ARRIVE_B hết giờ** |

Trong các lượt đạt, sai lệch cuối: đồ gá trung vị 1,5 cm, lớn nhất 3,8 cm, lệch góc trung vị 0,3°, lớn nhất 5,8°; không đồ gá trung vị 1,9 cm, lớn nhất 3,6 cm, lệch góc trung vị 2,0°, lớn nhất 6,2° (trước: lệch góc trung vị 0,8° và 3,1°).

Đọc:
- **Chưa đạt mục tiêu ≥ 95 %**: 29/31 ở cả hai cảnh; cần 30/31. Bốn nhóm lỗi (a)–(d) của mục 4.5 không còn trên 31 episode này. Lệch góc lúc đặt giảm rõ: không lượt nào lệch quá 6,2°.
- Ba lượt mới hỏng, mỗi lượt một kiểu, đều đạt với planner-5. Có thể chúng là cùng lớp lỗi với trước, chỉ hiện ở seed khác khi quỹ đạo đổi chút ít. Chưa kiểm bằng cách chạy lại có nhiễu.
  - **1:16, L-ONE-HAND (cả hai cảnh, lúc LIFT ở bàn A)**: tay phải chạm tay cầm trước và đẩy khay 3 cm theo y trước khi tay trái kẹp. Lòng bàn tay trái khép lệch 2,6–4,5 cm ra ngoài điểm cầm, tiếp xúc chập chờn rồi mất. Cùng lớp với 1:15 và 2:107 khi thử dời tay. Hướng: kiểm hai lòng bàn tay đối xứng trước LIFT, lệch thì nhả và cầm lại.
  - **1:10, L-TRAY-TILT (đồ gá)**: khay buông đúng chỗ (lệch 0,5 cm, 0°) ở 3,5 cm. Khi tay mở, khay dội giữa hai tường cạnh dài phía xa, nghiêng tới 14,5° và rời tiếp xúc, nên bị chấm là còn đang bưng. Đây là động lực khi nhả, không phải vị trí đặt. Hướng: buông thấp hơn hoặc mở tay chậm hơn khi khay đã trong tường.
  - **1:20, ARRIVE_B hết giờ (không đồ gá)**: pelvis bước tới bước lui ±2–4 cm quanh chỗ đứng đã tính, không giữ được trong `arrive_lat_tol` 2 cm. Chưa tìm nguyên nhân gốc; có thể liên quan việc ARRIVE_B nay xoay hướng trong lúc bước. Chưa kiểm.

### 4.7 Ba lượt còn hỏng: tỉ lệ lặp lại và nguyên nhân gốc (nhiệm vụ 6.4, 20/11/2026)

Hiếu xem video mẫu và chọn "Sửa tiếp" (20/11/2026). Trước khi sửa, mỗi lượt hỏng được chạy lại với nhiễu nhỏ: chỗ đứng của robot lệch ±1 cm và ±0,5°, tư thế khay trên bàn A lệch ±3 mm và ±0,5°. Nhiễu rút từ dãy số riêng; mọi thứ khác của hạt giống giữ nguyên (khối lượng, ánh sáng, khoảng cách bàn, đích). k = 0 là lượt gốc, k = 1–7 là bảy lần nhiễu. Planner `da41-planner-7` (trước 6.5).

| Lượt | Cảnh | Hỏng ở k = 0 | Hỏng ở k = 1–7 |
|---|---|---|---|
| 1:10 | Đồ gá | L-TRAY-TILT 18° | 1/7 (k = 6, L-TRAY-TILT 19°) |
| 1:16 | Đồ gá | L-ONE-HAND | 0/7 |
| 1:16 | Không đồ gá | L-ONE-HAND | 0/7 |
| 1:20 | Không đồ gá | ARRIVE_B hết giờ | 0/7 |

Đọc: cả ba là lỗi xác suất thấp, không gắn với hạt giống. Mỗi cơ chế lặp lại khoảng 0–15 % quanh lượt gốc, đúng như giả thuyết ở mục 4.6. Vì thế không chỉnh riêng cho seed nào. Mỗi cơ chế được sửa ở nguyên nhân, rồi kiểm trên tập lớn hơn có nhiễu và trên tập seed chưa dùng (mục 4.8).

| Lượt | Thấy trong trace | Nguyên nhân gốc |
|---|---|---|
| 1:10 (k = 0 và 6) | Khay buông ở 2,5–3 cm, nhưng vẫn tựa trên cổ tay (`wrist_yaw`–`tray_base`) và ngón cái (`thumb`–`tray_handle`), không rơi xuống. Cổ tay giữ nguyên độ cao, nhưng khi bàn tay ngửa mở ra, ngón cái quẹt lên dưới tay cầm và nâng khay thêm 1–2,5 cm. Lượt đạt (k = 4) cũng bị nâng tới 4 cm nhưng đều hai bên, nên khay rơi phẳng khi tay rút ra. Ở hai lượt hỏng, lực nâng lệch: khay nghiêng 12–19° trong khi chỉ chạm tay | Mở tay tại chỗ (`release_dz` 0) khi khay còn trên không. Nhận định của bộ chấm đúng: khay đang được tay nâng, không nằm trên đồ gá. Đây không phải việc cho DA-42 |
| 1:16 (cả hai cảnh) | Tay phải chạm tay cầm trước, đẩy khay 3 cm theo y trước khi tay trái kẹp. Lòng bàn tay trái khép lệch 2,6–4,5 cm khỏi điểm cầm, tiếp xúc chập chờn rồi mất lúc LIFT. Cùng kiểu với 1:15 và 2:107 khi thử dời tay (mục 4.6) | Không kiểm chất lượng cái cầm trước khi nâng: LIFT bắt đầu ngay khi cả hai tay báo chạm, dù một tay chỉ móc vào đầu tay cầm |
| 1:20 (không đồ gá) | Lệnh hướng (179,0°) khớp hướng pelvis trong vòng 0,5°: **không phải** do ARRIVE_B xoay hướng. Pelvis đứng bưng khay đung đưa ±2 cm theo x, chu kỳ khoảng 1,6 s, quanh chỗ đứng đích (lệch trung bình chỉ 0,8 cm) | ARRIVE_B xét vị trí tức thời: biên độ đung đưa bằng `arrive_lat_tol` 2 cm, nên mỗi lần đung đưa ra ngoài lại bắt đầu một bước, làm đung đưa tiếp. Tốc độ đung đưa (khoảng 0,08 m/s) cao hơn `arrive_speed` 0,05, nên robot không bao giờ được coi là đứng yên |

### 4.8 Sửa 1:20 và đo lại trên tập seed mới (nhiệm vụ 6.5, 6.6, 20/11/2026)

**Sửa (6.5).** Chỉ lỗi 1:20 có cách sửa qua được kiểm tra. ARRIVE_B nay lọc thông thấp vị trí pelvis (`arrive_filter_tau` 1 s). Bước sửa được quyết trên vị trí đã lọc: chọn trục nào lệch quá `arrive_lat_tol` và chiều bước. Sau đó bước chạy theo vị trí tức thời, mỗi trục dừng hẳn khi còn lệch dưới nửa dung sai hoặc đã vượt đích. Lần quyết tiếp theo chờ 2 hằng số thời gian để bộ lọc bắt kịp. `PLANNER_VERSION` = `da41-planner-8`. Test CPU mới: thế giới đồ chơi có pelvis đung đưa 2 cm, 0,6 Hz; ARRIVE_B không bước tới bước lui.

Thử và bỏ:
- Bước theo vị trí tức thời tới nửa dung sai (bản đầu của 6.5): đung đưa ngang làm lệnh bước ngang đổi chiều liên tục trong 1,3 s.
- `release_dz` −0,02 (buông thấp hơn 2 cm) cho lỗi nhả khay 1:10: sửa được 1:10 nhưng làm khay bị cạy lên ở hai lượt khác trong 31 (1:5, 1:14, nhiễu k = 1). Giữ 0. Hạ thấp hơn nữa (−0,03) thì cổ tay chạm cánh ngắn phía robot, RELEASE hết giờ.
- Kiểm độ lệch lòng bàn tay khỏi điểm cầm cuối GRASP rồi cầm lại (cho 1:16): độ lệch không phân biệt lượt hỏng. Chín lượt đạt lệch 2,5–3,3 cm, lượt hỏng 1:18 (nhiễu k = 1) chỉ lệch 1,5 cm. Không thêm.

Hai lượt có nhiễu k = 1 hỏng L-ONE-HAND với cả planner-7 lẫn planner-8: 1:7 và 1:18 (đồ gá). Lỗi không do 6.5 gây ra.

**Đo lại (6.6).** Laptop, một tiến trình, đúng 31 episode cũ (mức 0 seed 0, mức 1 seed 1–20, mức 2 seed 100–109) và một tập seed chưa dùng để chỉnh trong DA-41: mức 1 seed 21–40, mức 2 seed 110–119 (30 episode). Một chú thích cũ trong `planner.py` (từ trước DA-41) có nhắc seed 22, nên tập mới chưa hẳn sạch hoàn toàn. Khoảng tin cậy là Wilson 95 %. Planner-7 trên 31 episode cũ lấy từ mục 4.6.

| Tập | Cảnh | `da41-planner-7` (trước) | `da41-planner-8` (sau) |
|---|---|---|---|
| 31 episode cũ | Đồ gá | 29/31, 94 % (79–98 %) | **30/31, 97 % (84–99 %)** |
| 31 episode cũ | Không đồ gá | 29/31, 94 % (79–98 %) | **30/31, 97 % (84–99 %)** |
| 30 seed mới | Đồ gá | 29/30, 97 % (83–99 %) | **30/30, 100 % (89–100 %)** |
| 30 seed mới | Không đồ gá | 29/30, 97 % (83–99 %) | **30/30, 100 % (89–100 %)** |
| Gộp 61 | Đồ gá | 58/61, 95 % (87–98 %) | **60/61, 98 % (91–100 %)** |
| Gộp 61 | Không đồ gá | 58/61, 95 % (87–98 %) | **60/61, 98 % (91–100 %)** |

Lỗi theo seed (planner-7 → planner-8):

| Seed | Đồ gá | Không đồ gá |
|---|---|---|
| 1:10 | L-TRAY-TILT 18° → đạt | đạt → đạt |
| 1:20 | đạt → đạt | ARRIVE_B hết giờ → **đạt** |
| 2:115 | L-ONE-HAND → đạt | L-ONE-HAND → đạt |
| 1:16 | L-ONE-HAND → **L-ONE-HAND** | L-ONE-HAND → **L-ONE-HAND** |

Trong các lượt đạt của planner-8, sai lệch cuối: đồ gá trung vị 1,8 cm (cũ) và 1,3 cm (mới), lớn nhất 3,7 cm; không đồ gá trung vị 2,1 cm và 1,4 cm, lớn nhất 4,0 cm. Lệch góc lớn nhất 7,6°.

Đọc:
- **Đạt mục tiêu ≥ 95 % theo số điểm** ở cả hai cảnh, trên cả tập cũ lẫn tập mới. **Chưa chứng minh được theo khoảng tin cậy**: cận dưới của 60/61 là 91 %. Muốn cận dưới vượt 95 % cần khoảng 100 episode không hỏng lượt nào; kiểm 50 seed mỗi mức trên `rtx3060` (mục 5) chưa chạy.
- Tập mới không kém tập cũ (100 % so với 97 %), nên không thấy dấu hiệu chỉnh khớp riêng cho 31 episode cũ.
- **Hết**: 1:20 (sửa ở nguyên nhân).
- **Đạt nhưng không do sửa trực tiếp**: 1:10 và 2:115. Không đổi gì ở pha nhả hay pha cầm; quỹ đạo đổi chút ít sau khi sửa ARRIVE_B. Mục 4.7 đo lỗi nhả khay khoảng 1/7 quanh 1:10, nên lớp lỗi này vẫn có thể gặp ở seed khác.
- **Còn**: 1:16 (cầm lệch một tay, cả hai cảnh) và lớp lỗi L-ONE-HAND tỉ lệ thấp (1:7, 1:18 khi có nhiễu). Chưa có cách sửa đã kiểm.

Số liệu thô: `fwdata/da-41-samples/evidence/m66/` (không commit).

### 4.9 Lô mẫu dữ liệu với planner-8 (nhiệm vụ 7, 20/11/2026)

Hiếu đồng ý sinh thử một lô nhỏ để xem mẫu trước khi sinh cả lô. Đây không phải release. Laptop, một worker, `da41-planner-8+cfg.bee61399`, cảnh `jig2`, seed train chưa dùng ở đâu: mức 1 seed 400000–400009, mức 2 seed 400100–400109. Chạy đúng đường của lô 606 episode (mục 5.1–5.2 của [target-zone.md](target-zone.md)): `generate.py --scene jig`, `replay_qa.py`, `release.py`, `fw data ingest`, phát lại động học DA-17 (`replay_check replay`, `reports`), `fw data qa --replay`, `flywheel_psi0.tray.quality`, `demo_sets --qa-work --quality` (nghiêng ≤ 10°, linh kiện trượt ≤ 20 mm). Mọi file nằm trong `fwdata/da-41-sample-batch/` (không commit), có `FW_ROOT` riêng nên không chạm kho thật.

**Lỗi đường ống tìm thấy và đã sửa.** QA phát lại (`replay_qa`) chạy mọi lô qua `flywheel_simple.tray.run`, chỉ đăng ký env của cảnh cũ. Episode ghi trên đồ gá được dựng lại không có đồ gá và với đích rung; SIMPLE chỉ in cảnh báo "env/dataset task mismatch" rồi chạy tiếp. Kết quả lần đầu: qua 2/9 và 4/10, khay lệch trung vị 1,1–1,7 cm. Sửa: `jig_run` đăng ký thêm env đồ gá, `replay_qa` chọn theo `uid` đã ghi. Sau sửa: qua 9/9 và 10/10, lệch 0,0 mm, trùng từng bit như các lô cũ. `run.py` (DA-42) không đổi.

**Kiểm như dữ liệu train**

| Mục | Lô mẫu (19 episode) | Lô 606 episode cũ (ALL) |
|---|---|---|
| Lượt sinh → ghi được | 20 → 19 (95 %); hỏng 1: seed 400005, `timeout:RELEASE` | 610 → 542 (89 %), kho planner-5 |
| QA phát lại | 19/19, lệch 0,0 mm | 542/542, lệch 0,0 mm |
| QA DA-03 | 0 reject; 19 `flag`, chỉ do D7 và D8 (phát lại động học, xem bất thường 2) | 534 pass, 7 reject (D7) |
| Bộ lọc chất lượng | 19/19 giữ: nghiêng khi bưng lớn nhất 7,4°, linh kiện trượt lớn nhất 18,4 mm | 534 → 429 |
| Còn lại sau mọi bước | 19/20 lượt sinh (95 %) | 429/610 (70 %) |
| Độ dài | 1322–1602 frame, trung bình 1412 (26,4–32,0 s ở 50 Hz) | trung bình 1422 frame |
| `action`, `states` | 36 và 32 chiều, không NaN, mọi episode | 36 và 32 |
| Camera đầu | `egocentric` 640 × 360, 50 fps; số frame video bằng số dòng parquet ở mọi episode | như vậy |
| `visuals_revision` | `4763fbf…+zone1+jig2` | `4763fbf…+zone1` |
| `planner_version` | `da41-planner-8+cfg.bee61399` | planner-5 |
| Task `uid` | `g1_wholebody_tray_transfer_jig_teleop` | `g1_wholebody_tray_transfer_teleop` |
| Câu lệnh task | giống hệt (vẫn nói "target zone", không nhắc đồ gá) | |
| Cờ 7 bước (lô thô) | đủ 7 cột; 6 bước đầu đạt ở mọi episode; cờ thứ 7 (`release_stand` = thành công) bằng 0 ở frame cuối | cùng code ghi, chưa so trên dữ liệu cũ (không có trên laptop) |
| Sai lệch đặt cuối | trung vị 1,2 cm, lớn nhất 3,3 cm; góc trung vị 0,7°, lớn nhất 5,9° | |

**Camera đầu lúc hạ và nhả.** Đo bằng ảnh phân đoạn của MuJoCo từ đúng camera `head_stereo_left`, chạy lại 19 seed (planner tất định: số bước trùng bản ghi ở 19/19, ảnh RGB khớp video đã xuất, kiểm bằng mắt ở 3 frame). Đo màu trên video cho số sai: lưới đáy khay là hình học thật, nên vùng đích màu cam hiện qua lỗ lưới, và mặt nạ màu tưởng là khay. Trung vị trên 19 episode, phần trăm điểm ảnh:

| Pha | Đồ gá | Vùng đích | Khay |
|---|---|---|---|
| CARRY | 0,38 | 0,78 | 22,1 |
| ARRIVE_B | 0,57 | 4,83 | 22,7 |
| LOWER (hạ) | 0,67 | 3,58 | 22,1 |
| RELEASE (nhả) | 0,61 | 3,00 | 17,8 |
| RETREAT | 0,55 | 1,84 | 13,3 |

Vùng đích luôn thấy được lúc hạ: thấp nhất 3,2 % ở một episode. Phần thấy được là dải cam trước mép gần của khay và vùng đích qua lưới đáy. Đồ gá chỉ chiếm 0,4–0,7 % (bốn góc xanh), như mục 4.4.

**Thời gian.** Laptop, một worker: sinh trung bình 36,4 s mỗi lượt (p95 49 s), QA phát lại 32–33 s, phát lại động học 30–34 s mỗi episode. Ước lượng cho 600 episode qua lọc trên `rtx3060`, dựa trên số giờ-worker của lô 872 lượt (mục 5.1 của target-zone.md: 82 s mỗi lượt sinh, 88 s mỗi lượt QA phát lại): khoảng 632 lượt sinh (95 % giữ được), 14 giờ-worker sinh, 15 giờ-worker QA phát lại, thêm phát lại động học cỡ đó. Với 14 worker, khoảng 3–3,5 giờ đồng hồ. Đây là ước lượng, chưa đo.

**Bất thường.**
1. Seed 400005 (mức 1) hỏng `timeout:RELEASE`, kiểu lỗi không gặp trên 61 episode của mục 4.8. Mất một lượt sinh, không vào dữ liệu. Nguyên nhân ở mục 4.10 (a): cùng lớp lỗi nhả 1:10.
2. Phát lại DA-17 (`flywheel_simple/replay/run.py`) chỉ đăng ký env cảnh cũ, nên cũng dựng lại episode không có đồ gá. Mọi episode bị `flag` vì D7 (sai số trạng thái tay tới 1,36 rad lúc nhả, phát lại không thành công) và D8. Các kiểm tĩnh đều qua. `demo_sets` giữ `flag`, nên lô vẫn đủ 19. Đã sửa ở nhiệm vụ 8.1 và chạy lại ở 8.2 (mục 4.10).
3. Khay dừng lệch theo trục dọc của đích trung bình +1,0 cm (16/19 episode lệch dương, thấp nhất −0,2 cm), cả hai mức; lệch ngang trung bình −0,2 cm. Nằm trong dung sai, nhưng là độ lệch có hệ thống của planner trong dữ liệu.
4. Câu lệnh task vẫn nói "target zone". Nếu muốn policy phân biệt hai cảnh bằng lời thì phải đổi câu, nhưng như vậy sẽ khác dữ liệu cũ.

Mẫu xem: `fwdata/da-41-sample-batch/xem-mau/` (bốn video camera đầu cạnh góc nhìn ngoài, ảnh tổng hợp cả lô).

### 4.10 Phát lại DA-17 trên cảnh đồ gá và hai điều còn mở của lô mẫu (nhiệm vụ 8, 20/11/2026)

**Sửa adapter (8.1).** `flywheel_simple/replay/run.py` chọn env theo `uid` đã ghi, như `replay_qa` ở 7.1: `uid` khay cũ đăng ký `tray.run`, `uid` đồ gá đăng ký `tray.jig_run`. `--env-id` của cảnh khác, hay một dải episode trộn hai `uid`, bị từ chối trước khi dựng env. Với mọi dataset, khi một episode sắp được dựng trong cảnh khác `uid` đã ghi, adapter dừng tiến trình (`SceneMismatch`, một `SystemExit`; `except Exception` của SIMPLE không bắt nó) thay vì chạy tiếp như SIMPLE vẫn làm. Làm trong adapter của repo, không sửa SIMPLE. `--allow-uid-override` giữ cách cũ để chẩn đoán. Episode của cảnh cũ chạy như trước (test).

**Chạy lại trên lô mẫu (8.2).** `replay_check replay --env-id simple/G1WholebodyTrayTransferJigTeleop-v0`, `reports --outcomes`, `fw data qa --replay`, trên đúng hai release của mục 4.9. Không còn dòng "env/dataset task mismatch" nào trong log. Bản QA trước sửa được giữ ở `pipeline/src_*/qa-oldscene/`.

| Mức | Trước sửa (cảnh cũ) | Sau sửa (cảnh đồ gá) |
|---|---|---|
| Mức 1 (9 episode) | 9 `flag`: D7 9, D8 7 | 9 `flag`: D7 9, D8 3 |
| Mức 2 (10 episode) | 10 `flag`: D7 10, D8 8 | 10 `flag`: D7 10, D8 4 |
| Cả lô | D7 19, D8 15; phát lại đạt 4/19 | D7 19, D8 7; phát lại đạt 12/19 |

Sau sửa vẫn còn cờ, nên tìm nguyên nhân, không coi là qua:
- **D7 ở cả 19 episode** do hai issue của phép kiểm động lực học (`replay_dynamic`), cả hai có ở mọi episode, trước và sau sửa: `state_error` của tay 1,36 rad (ngưỡng 0,75) và `hand_event_offset` 3–9 bước (ngưỡng 2). Hai ngưỡng hiệu chỉnh trên psi-data teleop (`replay-1`, [replay.md](../replay.md)), nơi tay đóng mở chậm. Planner khay đóng và mở tay trọn hành trình trong 0,5 s (`hand_close_s`), nên lệch vài bước giữa bản ghi và lần phát lại cho sai số bằng gần cả hành trình khớp (1,36 rad, đỉnh ở frame đóng tay lúc cầm hoặc mở tay lúc nhả). Phần động học của D7 (`replay_kinematic`) qua ở 19/19, như lô 606 cũ.
- **D8 ở 7 episode** là phát lại không đạt. Không tương quan với độ lệch đặt đã ghi: episode lệch 0,24 cm vẫn trượt, episode lệch 2,2 cm vẫn đạt. Cùng các episode đó, `replay_qa` (phát lại từng frame của DA-33) tái tạo đúng từng bit, lệch 0,0 mm. Vậy D8 đến từ bộ phát lại của SIMPLE (`replay_decoupled_wbc`: đứng ổn định 162 bước, đệm 10 frame, lệch 3–9 bước), không phải từ dữ liệu. Psi-data teleop cũng trượt 73/99 qua đúng bộ này (replay.md mục 3.3).
- Lô 606 cũ chưa từng chạy phần động lực học: QA của nó dùng `replay_check reports` không có `--outcomes` (replay.md mục 3.3, "khay S1, chỉ động học"). Vì thế không có số D7 động lực học hay D8 của lô cũ để so. Đối chứng thay thế: 3 episode planner-8 trên cảnh cũ (không đồ gá, mức 1, seed 400200–400202, 3/3 thành công), qua QA phát lại, release và `replay_check replay --env-id simple/G1WholebodyTrayTransferTeleop-v0`. Kết quả giống hệt cảnh đồ gá: sai số tay 1,358–1,359 rad, lệch 4–8 bước ở cả 3, phát lại trượt 1/3, không có dòng `mismatch`. Vậy cờ còn lại không do đồ gá. Số thô: `fwdata/da-41-samples/evidence/r8/zone1-ctl-*.jsonl` (không commit).

Theo quyết định PO 4/11/2026, D7 động lực học và D8 chỉ là `flag`; `demo_sets` giữ `flag`, nên cả 19 episode vẫn ở lại. Muốn D7 có ý nghĩa trên dữ liệu khay thì phải hiệu chỉnh lại ngưỡng `replay-1` trên dữ liệu planner khay. Đó là việc của chủ `configs/data/replay.yaml`, ngoài DA-41 (mục 6).

**(a) Seed 400005, `timeout:RELEASE` (8.3).** Chạy lại seed (planner tất định, cùng chuỗi pha và thời điểm như `gen_log`) với vết tiếp xúc của tay theo từng bước (`fwdata/da-41-samples/evidence/r8/trace-400005.txt`, không commit). LOWER kết thúc như thường: khay cao 3,5 cm trên bàn B, nghiêng 1,5°. Khi tay mở, ngón cái và ngón giữa phải còn móc quai phải. Trong 0,4 s khay bị cạy lên: nghiêng 11°, nâng thêm 0,7 cm, trượt 3 cm theo trục dọc. Sau đó khay nằm yên, nghiêng 4°, cách mặt bàn 1,8 cm, lệch 4,0 cm dọc và 7,9 cm ngang, tựa lên cổ tay phải. Cổ tay chạm quai không lúc nào rời, nên RELEASE (chờ hai tay hết chạm 0,5 s) hết 4 s và hủy. **Kết luận: cùng lớp với lỗi nhả 1:10** (mục 4.7: khay tựa trên cổ tay và ngón cái, ngón cái quẹt lên dưới quai khi bàn tay mở và nâng lệch một bên). Ở 1:10 lực nâng lệch làm khay nghiêng 12–19° và bị chấm `L-TRAY-TILT`. Ở đây khay mắc lại trên cổ tay phải, nên cùng cơ chế hiện thành `timeout:RELEASE`. Mục 4.7 đo lớp này khoảng 1/7 quanh 1:10; trên 81 lượt planner-8 trên đồ gá (61 của mục 4.8 và 20 của lô mẫu) nó gặp 1 lần, chính là 400005. Không sửa trong DA-41; lớp này đã ghi ở mục 6.

**(b) Độ lệch dọc +1,0 cm (8.3).** Đo trên 19 episode thô của lô mẫu: độ lệch dọc của khay (dương là khay dừng ngắn, lệch về phía robot) tại frame cuối mà khay còn cao hơn mỗi mức so với lúc nằm yên.

| Khay còn cao | 5 cm | 4 cm | 3,5 cm | 3 cm | 2 cm | 1 cm | Cuối |
|---|---|---|---|---|---|---|---|
| Lệch dọc trung bình (cm) | 0,20 | 0,37 | 0,67 | 0,74 | 0,95 | 1,03 | 1,00 |

Nguồn:
- **Không phải chỗ đứng.** Khi khay còn cao 5 cm, ARRIVE_B đã xong và tay đang hạ, khay chỉ lệch 0,2 cm. Đế lùi 4–13 cm sau khi khay chạm bàn (RETREAT), nhưng khay không dịch thêm (1,02 cm lúc chạm, 1,00 cm cuối).
- **Phần lớn ở 5 cm cuối, quanh điểm buông.** Khoảng 0,5 cm sinh ra trong 1,5 cm cuối của LOWER (từ 5 xuống 3,5 cm). Giả thuyết, chưa kiểm bằng vết tiếp xúc: cổ tay dưới quai chạm bàn (D-25) và đẩy tay về phía robot. Khoảng 0,35 cm sinh ra sau khi buông ở 3,5 cm (`lower_tray_clear`), khi tay mở và khay rơi. Vòng kín `place_shift` chỉ cập nhật khi khay chưa chạm bàn, nên không bù được phần sau.
- **Đồ gá chỉ góp phần nhỏ.** Trên 61 episode của mục 4.8, không đồ gá vẫn lệch +0,8 cm (tập mới) đến +1,1 cm (tập cũ); có đồ gá +1,3 cm và +1,7 cm. Đồ gá thêm khoảng 0,5 cm.

Thử sửa bằng một tham số, ngoài repo: ngắm xa hơn 0,8 cm theo trục dọc trong vòng kín của LOWER (`aim_probe.py`, vá `_place_error`, không đổi planner). Trên đúng 19 seed: 19/19 vẫn đạt, nhưng độ lệch trung bình chỉ giảm từ 1,00 xuống 0,78 cm, trung vị 0,74. Từng seed đổi từ −1,6 đến +1,1 cm. Lệch ngang từ −0,22 thành −0,04 cm. Dời đích 0,8 cm chỉ dời kết quả 0,2 cm, vì phần lệch đến từ tiếp xúc lúc chạm và lúc nhả, không phải một độ dời cố định.

**Kết luận: để nguyên, không đổi `PLANNER_VERSION`.** Lý do: (1) không có tham số đơn nào bù được, vì phép ngắm xa đã thử chỉ gỡ một phần năm; (2) nếu hiệu ứng tuyến tính thì muốn bù hết phải ngắm xa khoảng 3,5 cm (ước lượng). Lúc đó khay buông sát tường đồ gá phía xa, chính chỗ sinh lỗi nhả 1:10, và phải đo lại 61 episode ở cả hai cảnh; (3) 1,0 cm nằm trong dung sai đặt, và có cả ở cảnh không đồ gá. Muốn sửa tận gốc thì phải đổi pha nhả (buông thấp hơn, mở tay chậm hơn, mục 4.7), cùng việc với lớp lỗi 1:10 ở mục 6. Số thô: `fwdata/da-41-samples/evidence/r8/aim-0.008.jsonl` (không commit).

### 4.11 Kiểm 50 seed mỗi mức trên `rtx3060` (nhiệm vụ 6.8, 21/11/2026)

PO (Hiếu) cho Claude tự chạy ngày 21/11/2026 ("Chạy đi"). Thực đo, một lần chạy, đúng lệnh của mục 5: commit `0594d2dd`, SIMPLE `b75c678`, cảnh đồ gá, seed 1000–1049 mỗi mức, 5 worker, trong scope `systemd-run` `MemoryMax=24G`. Máy đang có job của người khác (tải trung bình 6–12). Khoảng tin cậy là Wilson 95 %.

| Mức | Đạt | Tỉ lệ | Lỗi (seed) |
|---|---|---|---|
| 1 | 46/50 | 92 % (81–97 %) | L-ONE-HAND (1006, 1011), L-TRAY-TILT (1028), L-PLACE-POSE (1037) |
| 2 | 45/50 | 90 % (79–96 %) | L-PLACE-POSE (1015, 1023), L-ONE-HAND (1010), L-TRAY-TILT (1030), RELEASE hết giờ (1000) |
| Gộp | 91/100 | 91 % (84–95 %) | L-ONE-HAND 3, L-PLACE-POSE 3, L-TRAY-TILT 2, RELEASE hết giờ 1 |

Mọi lượt mang `da41-planner-8+cfg.bee61399` và `none+zone1+jig2`. Trung vị 47 s một lượt (mức 1: 47,2 s; mức 2: 47,9 s) khi 5 worker chạy cùng lúc. Test `sim` của mục 5 trên máy này: 28/28 qua, 282 s.

Đọc:
- **Chưa đạt AC 8 (≥ 95 %)**: cả hai mức dưới 48/50. Số laptop 60/61 (mục 4.8) cao hơn số này; khoảng tin cậy của hai phép đo chồng nhau (91–100 % và 84–95 %), nên chưa kết luận được là hai máy khác nhau. Chưa chạy lại cùng seed trên laptop.
- Lỗi thuộc các lớp đã biết của mục 4.7 và 4.8 (cầm lệch một tay, khay dội hoặc nghiêng khi nhả, sai lệch đặt), không có lớp mới. Nguyên nhân của từng lượt ở đây chưa xem trace.
- Cả hai mức trên ngưỡng dừng 85 % của lô 600 (mục 5.1), nhưng dưới điều kiện "≥ 48/50 mới sinh lô". Nếu sinh với tỉ lệ này, 632 lượt cho khoảng 575 episode ghi được trước QA [Ước lượng], không phải khoảng 600.

Dựng máy: `rtx3060` không còn thư mục `~/denso-*` (đã xóa 15/11/2026). `~/denso-da41` là checkout git của nhánh này, `bash scripts/g0/setup_simple.sh` rồi chép tay `scripts/g0/simple/curobo_stub/curobo` vào `site-packages` của venv (máy có `nvcc` nên script không tự chép). Số liệu thô: `~/denso-da41/fwdata/simple/tray/gen/jig2-check-l{1,2}/` trên `rtx3060` (540 MB, xóa được) và bản sao `gen_log` ở `fwdata/da-41-samples/evidence/rtx3060-check/` (không commit).

## 5. Runbook cho Hiếu trên `rtx3060`

Test `sim` và kiểm 50 seed đã chạy trên `rtx3060` ngày 21/11/2026 (mục 4.11: 46/50 và 45/50, dưới mục tiêu); mục 5.1 chưa chạy. Mọi lệnh dưới đây đã chạy trên laptop. Cập nhật 20/11/2026 cho planner `da41-planner-8` và đồ gá `jig2` (nhiệm vụ 6.6). Lô `jig1-check`, nếu đã chạy theo bản trước, dùng planner-5 và `jig1`: không gộp với lô mới (`generate` từ chối trộn hai `planner_version` trong một thư mục).

Chuẩn bị (một lần), trong một thư mục làm việc riêng, rồi kiểm phiên bản:

```bash
git -C ~/denso-da41 fetch origin && git -C ~/denso-da41 checkout DA-41-tray-fixed-target-jig && git -C ~/denso-da41 pull --ff-only
```

```bash
cd ~/denso-da41 && grep -n "^PLANNER_VERSION\|^JIG_REVISION" packages/flywheel-simple/src/flywheel_simple/tray/planner.py packages/flywheel-simple/src/flywheel_simple/tray/jig.py
```

Phải in `da41-planner-8` và `jig2`.

Test `sim` (khoảng 2 s cho MuJoCo thuần, khoảng 5 phút cho test qua SIMPLE):

```bash
cd ~/denso-da41 && MUJOCO_GL=egl PYTHONPATH=packages/flywheel-simple/src fwdata/simple/.venv/bin/python -m pytest packages/flywheel-simple/tests/tray/test_jig_sim.py packages/flywheel-simple/tests/tray/test_jig_task_sim.py -m sim -v
```

Kiểm planner 50 seed mỗi mức 1 và 2 (mục tiêu ≥ 95 %, tức ≥ 48/50; trên laptop 60/61 ở mỗi cảnh, mục 4.8). Một worker khoảng 35 s một episode trên laptop; ước lượng mỗi lô 50 seed khoảng 30 phút một worker, chia 5 shard khoảng 6 phút. Máy dùng chung: tổng worker trên `rtx3060` không quá 22, nên chạy lần lượt hai lô. Sinh vào thư mục mới (episode thành công được ghi kèm; thư mục chỉ để kiểm, xóa được sau khi đọc số):

```bash
cd ~/denso-da41 && MUJOCO_GL=egl PYTHONPATH=packages/flywheel-simple/src nohup setsid fwdata/simple/.venv/bin/python scripts/g0/tray/generate.py --scene jig --out fwdata/simple/tray/gen/jig2-check-l1 --n 50 --level 1 --seed-start 1000 --workers 5 --allow-plain > jig2-check-l1.log 2>&1 &
```

```bash
cd ~/denso-da41 && MUJOCO_GL=egl PYTHONPATH=packages/flywheel-simple/src nohup setsid fwdata/simple/.venv/bin/python scripts/g0/tray/generate.py --scene jig --out fwdata/simple/tray/gen/jig2-check-l2 --n 50 --level 2 --seed-start 1000 --workers 5 --allow-plain > jig2-check-l2.log 2>&1 &
```

Đọc kết quả: `gen_log.jsonl` của mỗi shard có `success`, `failure`, `abort_reason`, `planner_version` cho từng seed. Lệnh dưới in số đạt, các phiên bản planner trong lô (phải chỉ có `da41-planner-8`) và đếm lỗi:

```bash
cd ~/denso-da41 && for L in l1 l2; do cat fwdata/simple/tray/gen/jig2-check-$L/shard-*/gen_log.jsonl | python3 -c "import sys,json,collections; r=[json.loads(l) for l in sys.stdin]; print('$L', sum(x['success'] for x in r), '/', len(r), {x['planner_version'] for x in r}, collections.Counter(x['failure'] or x['abort_reason'] for x in r if not x['success']))"; done
```

So với cảnh không đồ gá cùng planner thì không có lệnh sẵn (số laptop ở mục 4.6 dùng `add_jig` tắt trong script ngoài repo). So với cảnh cũ cùng seed (đích rung): đổi `--scene zone1` và `--out .../zone1-check-l1`.

Ảnh camera đầu (3 episode, khoảng 2 phút):

```bash
cd ~/denso-da41 && MUJOCO_GL=egl PYTHONPATH=packages/flywheel-simple/src fwdata/simple/.venv/bin/python scripts/g0/tray/jig_views.py --out fwdata/simple/tray/jig-views --cases 0:0 1:1279 2:125195
```

### 5.1 Sinh lô khoảng 600 episode trên cảnh đồ gá (nhiệm vụ 8.4)

**[Đề xuất]**, Hiếu chạy. Claude không chạy trên `rtx3060`. Đây là **lô mới**, tách khỏi kho planner-5 (`~/denso-da34-pool`): thư mục riêng, `FW_ROOT` riêng, planner `da41-planner-8`, cảnh `jig2`. Không gộp release, catalog hay ledger của lô này với kho cũ. Mọi lệnh đã chạy trên laptop với lô mẫu 19 episode (mục 4.9), trừ số worker.

| Mục | Giá trị |
|---|---|
| Thư mục | `~/denso-da41/fwdata/da41-jig-600/` (`$B`): `gen-l1/`, `gen-l2/`, `releases/`, `pipeline/`, `replay17/`, `reports/`, ledger `fw/` và `sites/` (append-only, giữ) |
| Số lượt | 632 lượt, để còn khoảng 600 episode với tỉ lệ giữ 95 % của lô mẫu |
| Chia mức | Theo lô 606 cũ: phần kho 429 episode toàn mức 1; phần nhắm lỗi 177 episode, 82 mức 1 và 78 mức 2 theo `cplus-selection.jsonl`, 17 không rõ mức. Tổng khoảng 86 % mức 1, 14 % mức 2. **PO (Hiếu) chọn ngày 21/11/2026 tăng mức 2 lên khoảng 30 %**, vì eval chia đều hai mức và mục tiêu là nâng chỉ số của policy, không phải so với lô cũ; đổi lại, kết quả train trên lô này không so thẳng được với lô 606. Lô mới: **442 lượt mức 1, 190 lượt mức 2** |
| Seed | Train, chưa dùng ở đâu: mức 1 `500000–500441`, mức 2 `501000–501189`. Đã dùng: 0–143, 1000–1609, 100000–199999, 300000–300089, 400000–400109 (lô mẫu), 400200–400202 (đối chứng 8.2) |
| Worker | Mức 1: 10, mức 2: 4, chạy cùng lúc, tổng 14 (giới hạn máy dùng chung là 22) |
| Thời gian (ước lượng) | Sinh 632 × 82 s ≈ 14,4 giờ-worker, khoảng 1,1 giờ đồng hồ (mức 1: 442 lượt trên 10 worker, mức 2: 190 lượt trên 4 worker, mỗi mức khoảng 1,0–1,1 giờ nếu hai mức tốn cùng số giây mỗi lượt; chưa đo riêng mức 2). QA phát lại 600 × 88 s ≈ 14,7 giờ-worker, khoảng 1,1 giờ. Phát lại DA-17 cỡ QA phát lại (trên laptop 30–34 s mỗi episode, ngang QA phát lại), khoảng 1,1 giờ. Tổng khoảng 3,5–4 giờ. Số giây mỗi lượt lấy từ lô 872 lượt của mục 5.1 [target-zone.md](target-zone.md); chưa đo trên cảnh đồ gá ở `rtx3060` |
| Dung lượng (ước lượng) | Lô mẫu: thô 8,9 MB, release 8,2 MB mỗi episode. 600 episode: thô khoảng 5,4 GB, release khoảng 4,9 GB, cộng thư mục làm việc, tổng khoảng 11 GB |
| Chưa gồm | Dữ liệu riêng cho bước đặt (đoạn hạ và nhả). Đây là việc sau |

Điều kiện dừng: sau mỗi bước, nếu tỉ lệ giữ dưới **85 %** thì dừng, không chạy bước sau, gửi lại output của lệnh đọc kết quả. Tỉ lệ giữ là số episode còn lại chia cho số lượt sinh của mức đó. Lô mẫu giữ 95 %.

Chuẩn bị: code ở mục 5 (nhánh `DA-41-tray-fixed-target-jig`, phải in `da41-planner-8` và `jig2`). Nên chạy trước phần kiểm 50 seed mỗi mức của mục 5; nếu một mức dưới 95 % (dưới 48/50) thì chưa sinh lô này, gửi số cho Claude. Mỗi lệnh sim chạy trong một scope `systemd-run` có `MemoryMax` (một worker cần khoảng 3,7 GB; trên laptop đo được), như các lô trước trên máy này.

```bash
mkdir -p ~/denso-da41/fwdata/da41-jig-600 && df -h ~/denso-da41/fwdata
```

**Bước 1. Sinh**, hai mức chạy cùng lúc:

```bash
cd ~/denso-da41 && B=$PWD/fwdata/da41-jig-600 && MUJOCO_GL=egl PYTHONPATH=packages/flywheel-simple/src nohup setsid systemd-run --user --scope -p MemoryMax=48G -p MemorySwapMax=0 fwdata/simple/.venv/bin/python scripts/g0/tray/generate.py --scene jig --out $B/gen-l1 --n 442 --level 1 --seed-start 500000 --workers 10 > $B/gen-l1.log 2>&1 < /dev/null &
```

```bash
cd ~/denso-da41 && B=$PWD/fwdata/da41-jig-600 && MUJOCO_GL=egl PYTHONPATH=packages/flywheel-simple/src nohup setsid systemd-run --user --scope -p MemoryMax=16G -p MemorySwapMax=0 fwdata/simple/.venv/bin/python scripts/g0/tray/generate.py --scene jig --out $B/gen-l2 --n 190 --level 2 --seed-start 501000 --workers 4 > $B/gen-l2.log 2>&1 < /dev/null &
```

Đọc kết quả (tiến độ, và khi xong): số lượt, số ghi được, tỉ lệ, phiên bản planner (phải chỉ có `da41-planner-8+cfg.bee61399`), lỗi:

```bash
cd ~/denso-da41/fwdata/da41-jig-600 && for L in 1 2; do cat gen-l$L/shard-*/gen_log.jsonl | python3 -c "import sys,json,collections; r=[json.loads(l) for l in sys.stdin]; ok=sum(x['recorded'] for x in r); print('L$L', len(r), 'lượt', ok, 'ghi', f'{ok/max(len(r),1):.1%}', {x['planner_version'] for x in r}, collections.Counter(x['failure'] or x['abort_reason'] for x in r if not x['success']))"; done
```

Dừng nếu một mức ghi được dưới 85 %. Lô mẫu: 19/20.

**Bước 2. QA phát lại** (dựng lại trong cảnh đồ gá theo `uid` đã ghi, mục 4.9):

```bash
cd ~/denso-da41 && B=$PWD/fwdata/da41-jig-600 && MUJOCO_GL=egl PYTHONPATH=packages/flywheel-simple/src nohup setsid systemd-run --user --scope -p MemoryMax=48G -p MemorySwapMax=0 bash -c "fwdata/simple/.venv/bin/python scripts/g0/tray/replay_qa.py --out $B/gen-l1 --workers 12 > $B/replay-l1.log 2>&1; fwdata/simple/.venv/bin/python scripts/g0/tray/replay_qa.py --out $B/gen-l2 --workers 12 > $B/replay-l2.log 2>&1" < /dev/null > /dev/null 2>&1 &
```

```bash
cd ~/denso-da41/fwdata/da41-jig-600 && for L in 1 2; do echo L$L; python3 -m json.tool gen-l$L/replay_summary.json | head -20; grep -c "mismatch" replay-l$L.log; done
```

Phải qua gần hết, lệch 0,0 mm, và không có dòng `mismatch` (số 0). Có dòng `mismatch` là dựng sai cảnh: dừng.

**Bước 3. Release** (không cần GPU):

```bash
cd ~/denso-da41 && B=$PWD/fwdata/da41-jig-600 && for L in 1 2; do PYTHONPATH=packages/flywheel-simple/src fwdata/simple/.venv/bin/python scripts/g0/tray/release.py --batch $B/gen-l$L --releases $B/releases 2>&1 | tail -3; done; ls $B/releases
```

**Bước 4. Ingest** vào store riêng của lô (release phải nằm dưới `FW_ROOT`):

```bash
cd ~/denso-da41 && export FW_ROOT=$PWD/fwdata/da41-jig-600 && for R in $FW_ROOT/releases/tray_s1_*; do uv run fw data ingest $R --source-detail planner_wbc --license unknown --data-class public --split train 2>&1 | tail -2; done; ls -d $FW_ROOT/pipeline/src_*
```

Ghi lại cặp `src_…` và `tray_s1_…` của từng mức. Release mức 1 có khoảng 420 episode, mức 2 khoảng 180. Các bước sau dùng hai biến `SRC` (cột đầu) và `REL` (tên thư mục sau `releases/`) cho từng mức:

```bash
cd ~/denso-da41/fwdata/da41-jig-600 && for W in pipeline/src_*; do python3 -c "import json; d=json.load(open('$W/ingest.json')); print(d['source_id'], d['store_path'], d['episodes'], 'episode')"; done
```

**Bước 5. Phát lại DA-17 trong cảnh đồ gá** (chạy sim; thay `SRC` và `REL` bằng cặp của từng mức, chạy lần lượt hai mức):

```bash
cd ~/denso-da41 && B=$PWD/fwdata/da41-jig-600 && SRC=src_XXXX && REL=tray_s1_XXXX && export FW_ROOT=$B MUJOCO_GL=egl PYTHONPATH=$PWD/packages/flywheel-simple/src && nohup setsid systemd-run --user --scope -p MemoryMax=48G -p MemorySwapMax=0 uv run python -m flywheel.data.replay_check replay $B/releases/$REL --work $B/replay17/$REL --python $PWD/fwdata/simple/.venv/bin/python --env-id simple/G1WholebodyTrayTransferJigTeleop-v0 --workers 12 > $B/replay17-$REL.log 2>&1 < /dev/null &
```

`--env-id` phải là env đồ gá. Adapter dừng với lỗi `SceneMismatch` nếu env khác cảnh đã ghi (nhiệm vụ 8.1). Kiểm không có dòng `mismatch` và đủ một dòng mỗi episode:

```bash
cd ~/denso-da41/fwdata/da41-jig-600 && for R in releases/tray_s1_*; do R=$(basename $R); echo $R $(wc -l < releases/$R/meta/episodes.jsonl) episode, $(cat replay17/$R/replay_outcomes.jsonl 2>/dev/null | wc -l) outcomes, $(cat replay17/$R/shard-*/replay.log | grep -c mismatch) mismatch; done
```

**Bước 6. Report và QA DA-03** (không cần GPU; thay `SRC`, `REL` như bước 5):

```bash
cd ~/denso-da41 && B=$PWD/fwdata/da41-jig-600 && SRC=src_XXXX && REL=tray_s1_XXXX && export FW_ROOT=$B && uv run python -m flywheel.data.replay_check reports $B/pipeline/$SRC --out $B/reports/$REL --outcomes $B/replay17/$REL/replay_outcomes.jsonl 2>&1 | tail -1 && uv run fw data qa $B/pipeline/$SRC --replay $B/reports/$REL 2>&1 | tail -1
```

```bash
cd ~/denso-da41/fwdata/da41-jig-600 && for W in pipeline/src_*; do python3 -c "import json,collections,sys; r=[json.loads(l) for l in open('$W/qa/reports.jsonl')]; print('$W', collections.Counter(x['decision'] for x in r), collections.Counter(s.split(' (')[1].split(')')[0] for x in r for s in x['reasons']))"; done
```

`reject` và `quarantine` bị bỏ ở bước 8; `flag` được giữ. Cờ D7 (`replay_dynamic`) và D8 dự kiến có ở nhiều episode (mục 4.9, nhiệm vụ 8.2), không phải lý do dừng. Dừng nếu `reject` cộng `quarantine` làm tỉ lệ giữ dưới 85 %.

**Bước 7. Bộ lọc chất lượng** (không cần GPU):

```bash
cd ~/denso-da41 && B=$PWD/fwdata/da41-jig-600 && for L in 1 2; do uv run python -m flywheel_psi0.tray.quality --batch $B/gen-l$L --out $B/gen-l$L/quality.jsonl 2>&1 | tail -1; done
```

**Bước 8. Tập demo** (thay `SRC`, `REL`, mức `L` và số episode của release `N` cho từng mức):

```bash
cd ~/denso-da41 && B=$PWD/fwdata/da41-jig-600 && SRC=src_XXXX && REL=tray_s1_XXXX && L=1 && N=$(wc -l < $B/releases/$REL/meta/episodes.jsonl) && uv run python -m flywheel_psi0.tray.demo_sets --release $B/releases/$REL --size ALL=$N --qa-work $B/pipeline/$SRC --quality $B/gen-l$L/quality.jsonl --max-tilt-carry-deg 10 --max-part-shift-end-mm 20 --out $B/demo_sets-l$L.json 2>&1 | tail -3
```

Đọc tỉ lệ giữ cuối của từng mức (số trong tập `ALL` chia số lượt sinh):

```bash
cd ~/denso-da41/fwdata/da41-jig-600 && for L in 1 2; do python3 -c "import json,glob; n=json.load(open('demo_sets-l$L.json'))['sets']['ALL']['n']; a=sum(len(open(p).readlines()) for p in glob.glob('gen-l$L/shard-*/gen_log.jsonl')); print('L$L', n, '/', a, f'{n/a:.1%}')"; done
```

Dừng nếu một mức dưới 85 %. Nếu `demo_sets` báo thiếu episode cho `ALL=$N`, giảm `N` về số nó báo còn lại. Gửi Claude bốn output: bước 1, 2, 6 và 8.

## 6. Việc tiếp theo (ngoài DA-41)

- Driver eval của DA-42 (`run.py`) cần chọn env `jig_task.make_env` và guard theo `visuals_revision(..., jig=True)` để eval trên cảnh có đồ gá.
- `flywheel_psi0/tray/place_error.py` và `evidence.py` tính lại đích từ `sample_episode`; đúng cho run `+zone1`, sai cho run trên đồ gá. Cần chọn hàm theo revision.
- S2 (`tray/s2/streamer.py`) dựng lại mẫu cha bằng `sample_episode`; biến thể trên cảnh đồ gá cần `sample_jig_episode`.
- Sinh lô mới trên cảnh đồ gá và train lại: story sau, cần duyệt ngân sách.
- Planner (nếu kiểm 50 seed dưới 95 %): hai lớp lỗi còn lại của mục 4.8. Cầm lệch một tay (1:16; độ lệch lòng bàn tay cuối GRASP không dự báo được lỗi, cần tín hiệu khác). Ngón cái cạy khay lên khi nhả trong đồ gá (1:10, khoảng 1/7 quanh seed đó).
- Phát lại DA-17 trên dữ liệu khay (chủ `configs/data/replay.yaml`, DA-17): ngưỡng `state_error.hand` và `hand_event_offset_steps` của `replay-1` hiệu chỉnh trên psi-data teleop, nên D7 động lực học bật ở mọi episode planner khay, cả cảnh cũ lẫn đồ gá (mục 4.10). `replay_decoupled_wbc` của SIMPLE còn trượt khoảng 1/3 số episode (D8) dù `replay_qa` tái tạo đúng từng bit. Cần hiệu chỉnh ngưỡng trên dữ liệu khay, hoặc ghi rằng hai phép kiểm này không dùng cho nguồn `planner_wbc`. Phần chọn đúng cảnh đã sửa ở 8.1.
- Pha nhả (planner): lớp lỗi 1:10 (mục 4.7, 400005 ở mục 4.10) và độ lệch dọc +1,0 cm có chung chỗ, là 5 cm cuối và lúc mở tay. Sửa cùng một lần (buông thấp hơn hoặc mở tay chậm hơn), rồi đo lại 61 episode ở cả hai cảnh.
- Thí nghiệm: policy train trên cảnh đồ gá có dùng đồ gá làm mốc không (ví dụ che đồ gá lúc eval). Đồ gá chỉ chiếm dưới 0,7 % ảnh camera đầu (mục 4.4).
