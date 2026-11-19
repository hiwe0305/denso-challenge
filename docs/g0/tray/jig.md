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
| Phía robot | Không có cánh cạnh dài (`near_side_arm: 0`); giữ cánh cạnh ngắn (`near_end_arm: 0.035`) | Xem mục 3 |
| Tấm trượt | Dày 2 mm, phủ footprint + khe hở, vô hình | Không có tấm, mép xa của khay bám mặt bàn thép (ma sát 1,0) và khay kẹt trên mặt vát |
| Ma sát | 0,2 (nhựa acetal / PTFE), ưu tiên tiếp xúc 1 | Ma sát của thanh dẫn và tấm thắng ma sát 1,0 của khay |
| Màu | Xanh lam `(0.05, 0.40, 0.95)`, nhóm vẽ 0 | Khác cam của vùng đích, xanh lá của thùng, xám của bàn |

Vùng đích cam vẫn được vẽ ở tư thế đích (dưới tấm trượt vô hình).

### 2.4 Revision hình ảnh

`visuals_revision` của cảnh có đồ gá là `<revision SimReady>+zone1+jig1` (cảnh hộp trơn: `none+zone1+jig1`). `generate` từ chối viết tiếp vào lô `+zone1` bằng cảnh `jig` và ngược lại; `export` từ chối lô có hai revision (như với `+zone1`). Guard eval ngoài repo trên `rtx3060` (`simple-guard.sh`) cần so với revision mới khi eval trên cảnh có đồ gá.

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

Lựa chọn còn mở:
- Cổ tay G1 vẫn chạm cánh cạnh ngắn phía robot ở mức 1 seed 7 và mức 2 seed 107 (khay bị nâng một đầu, L-TRAY-TILT). Hướng cho story sau: planner hạ cổ tay theo đường tránh thanh dẫn, hoặc cánh cạnh ngắn phía robot thấp hơn phía xa.
- Phía robot để trống nên khay lệch về phía robot không được đẩy lại (mức 1 seed 5, 11: lệch 6 cm). Hướng: planner nhắm hơi về phía xa (dựa vào thanh dẫn phía xa), hoặc một gờ thấp phía robot dưới tầm khuỷu tay.
- Chọn 5 cm hay 6,5 cm: trên 31 episode, khác 1 lượt, trong nhiễu. Cần kiểm 50 seed (mục 5) trước khi sinh lô.

## 4. Số đo

### 4.1 Test CPU

`uv run pytest packages/flywheel-simple/tests/tray/test_jig.py`: 38 qua. Kiểm cấu hình và `check` (từ chối đồ gá không vừa), đích cố định và mọi trường khác giữ nguyên ở 3 mức × 200 seed, vị trí rời rạc 2 và 3 không đổi dãy số, mọi vị trí nằm trên bàn B với khoảng cách bàn 1,6–2,0 m, mặt trong của tường ở đúng khe hở, mặt vát ra tới lead-in, cánh tránh tay cầm, `visuals_revision` và `generate` từ chối trộn lô, sha256 của sáu file bị ghim.

### 4.2 Test `sim` MuJoCo thuần

[`test_jig_sim.py`](../../../packages/flywheel-simple/tests/tray/test_jig_sim.py): 23 qua trong 2,6 s trên laptop.

- 4 cặp (mức, seed): mọi geom đồ gá thuộc `table_b` đúng tư thế đích, va chạm, ưu tiên 1, ma sát 0,2; không thêm body, khớp hay khối lượng.
- Khay đặt đúng đích không bao giờ chạm thanh dẫn và dịch < 1 mm trong 3 s.
- Khay được giữ và hạ như planner (mối hàn mềm tới một mocap, hạ 5 cm/s, buông ở 3,5 cm) với độ lệch về phía các cạnh có thanh dẫn: 2 và 4 cm không lệch góc, 2 cm lệch 4°. Mọi lượt kết thúc phẳng, cách đích ≤ 2 cm, lệch góc ≤ 3°, đủ 6 linh kiện.

Vùng bắt ([`jig_capture.py`](../../../scripts/g0/tray/jig_capture.py), mức 1 seed 1279, hạ có giữ, 8 hướng; "căn" = cách đích ≤ 1,2 cm, lệch góc ≤ 3°, nghiêng ≤ 2°):

| Lệch | 0° | 4° | 8° |
|---|---|---|---|
| 1 cm | 7/8 | 4/8 | 0/8 |
| 2 cm | 5/8 | 4/8 | 1/8 |
| 3 cm | 4/8 | 2/8 | 1/8 |
| 4 cm | 4/8 | 0/8 | 0/8 |
| 5 cm | 0/8 | 0/8 | 0/8 |

Ba trong tám hướng nghiêng về phía robot (cạnh để trống): đồ gá không đẩy khay về phía xa robot. Với 4–8° lệch góc, mối hàn giữ góc cứng nên khay không được xoay thẳng; phần lớn vẫn nằm phẳng trong dung sai 5 cm, 10° của bộ chấm, chỉ không "căn".

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

[`jig_views.py`](../../../scripts/g0/tray/jig_views.py) chạy planner trên ba lượt (0:0, 1:1279, 2:125195): cả ba đạt, `visuals_revision` là `4763fbfa…+zone1+jig1`. Script đếm số pixel màu xanh của đồ gá và màu cam của vùng đích trên `head_stereo_left`; bảng dưới là khoảng của ba lượt. PNG và `report.json` để ngoài repo (`fwdata/simple/tray/jig-views`).

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

## 5. Runbook cho Hiếu trên `rtx3060`

Chưa chạy trên `rtx3060` (không chạy job ở đó khi chưa hỏi). Mọi lệnh dưới đây đã chạy trên laptop, trừ kiểm 50 seed.

Chuẩn bị (một lần), trong một thư mục làm việc riêng:

```bash
git -C ~/denso-da41 fetch origin && git -C ~/denso-da41 checkout DA-41-tray-fixed-target-jig
```

Test `sim` (khoảng 2 s cho MuJoCo thuần, khoảng 5 phút cho test qua SIMPLE):

```bash
cd ~/denso-da41 && MUJOCO_GL=egl PYTHONPATH=packages/flywheel-simple/src fwdata/simple/.venv/bin/python -m pytest packages/flywheel-simple/tests/tray/test_jig_sim.py packages/flywheel-simple/tests/tray/test_jig_task_sim.py -m sim -v
```

Kiểm planner 50 seed (mục tiêu ≥ 95 %; một worker khoảng 35 s một episode trên laptop, ước lượng khoảng 30 phút một worker; chia 5 shard thì khoảng 6 phút), sinh vào thư mục mới (episode thành công được ghi kèm; thư mục này chỉ để kiểm, xóa được sau khi đọc số):

```bash
cd ~/denso-da41 && MUJOCO_GL=egl PYTHONPATH=packages/flywheel-simple/src nohup setsid fwdata/simple/.venv/bin/python scripts/g0/tray/generate.py --scene jig --out fwdata/simple/tray/gen/jig1-check --n 50 --level 1 --seed-start 1000 --workers 5 --allow-plain > jig1-check.log 2>&1 &
```

Đọc kết quả: `gen_log.jsonl` của mỗi shard có `success`, `failure`, `abort_reason` cho từng seed.

```bash
cd ~/denso-da41 && cat fwdata/simple/tray/gen/jig1-check/shard-*/gen_log.jsonl | python3 -c "import sys,json; r=[json.loads(l) for l in sys.stdin]; print(sum(x['success'] for x in r), '/', len(r))"
```

So với cảnh cũ cùng seed (cùng planner, đích rung): đổi `--scene zone1` và `--out .../zone1-check`.

Ảnh camera đầu (3 episode, khoảng 2 phút):

```bash
cd ~/denso-da41 && MUJOCO_GL=egl PYTHONPATH=packages/flywheel-simple/src fwdata/simple/.venv/bin/python scripts/g0/tray/jig_views.py --out fwdata/simple/tray/jig-views --cases 0:0 1:1279 2:125195
```

## 6. Việc tiếp theo (ngoài DA-41)

- Driver eval của DA-42 (`run.py`) cần chọn env `jig_task.make_env` và guard theo `visuals_revision(..., jig=True)` để eval trên cảnh có đồ gá.
- `flywheel_psi0/tray/place_error.py` và `evidence.py` tính lại đích từ `sample_episode`; đúng cho run `+zone1`, sai cho run trên đồ gá. Cần chọn hàm theo revision.
- S2 (`tray/s2/streamer.py`) dựng lại mẫu cha bằng `sample_episode`; biến thể trên cảnh đồ gá cần `sample_jig_episode`.
- Sinh lô mới trên cảnh đồ gá và train lại: story sau, cần duyệt ngân sách.
- Planner: cổ tay chạm cánh cạnh ngắn phía robot (mục 3) và lỗi REACH hết giờ ở mức 2 seed 102 (có cả trên cảnh cũ).
- Thí nghiệm: policy train trên cảnh đồ gá có dùng đồ gá làm mốc không (ví dụ che đồ gá lúc eval). Đồ gá chỉ chiếm dưới 0,7 % ảnh camera đầu (mục 4.4).
