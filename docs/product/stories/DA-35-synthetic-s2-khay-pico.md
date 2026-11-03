# DA-35 · Synthetic cho task bê khay: teleop ảo qua ống PICO và biến thể S2

## Trạng thái

| Trường | Giá trị |
|---|---|
| Trạng thái | Đang làm (PO duyệt bản teleop ảo cộng S2 và việc tải psi-data, 3/11/2026). Nhiệm vụ 1–7 xong; demo cha cho S2 đã có |
| Người làm | Hiếu (đề xuất, PO giao) |
| Làn | Adapter simulator (`flywheel-simple`) |
| Story PRD | Story của [design 28/10/2026](../../superpowers/specs/2026-10-28-tray-transfer-he-design.md) mục 5 (dòng Synthetic S1, S2) · [design 27/10/2026](../../superpowers/specs/2026-10-27-g1-psi0-demo-design.md) mục 5.3, 5.4 · spec mục 6.10, tuyến T2 ở mục 10 |
| Nhãn | [Adapter] · `epic:9` · `gate:G1` · `area:sim` |
| Sprint | S2; demo cha trước 10/11/2026, lô S2 trước 13/11/2026 (đề xuất, cho demo 17/11) |
| Ước lượng | Chưa chốt. Người viết ước lượng thô 30–45 giờ; PO chốt |
| Phụ thuộc | DA-32 (task, vị từ 7 bước, `check_success`; đã merge). [PR #27](https://github.com/hiwe0305/denso-challenge/pull/27) (gói ghi LeRobot trong `setup_simple.sh`; đã cài trên laptop và rtx3060). DA-33 nhiệm vụ 1–4 (planner `TrayPlanner`, cách cầm D-19): PO chọn merge DA-33 rồi dùng lại mã planner (3/11/2026); nhiệm vụ 5 trở đi cần DA-33 đã merge, trong lúc chờ chỉ làm phần không phụ thuộc planner, với planner giả |

## Story

Là trưởng nhóm, tôi muốn sinh tự động demo G1 bê khay mà chuyển động như người teleop PICO (nghiêng eo, khuỷu sát thân, lòng bàn tay hướng vào, hai tay liền mạch, mỗi lượt một kiểu), rồi nhân lên hàng nghìn episode bằng biến thể S2, để có dữ liệu robot đủ lớn cho Ψ₀ và DA-34 khi đội không có kính PICO.

Bối cảnh:
- 3/11/2026 [Đã chốt, Hiếu]: chọn S2 từ demo teleop PICO, không dùng video người retarget hay bàn phím (bàn phím ra chuyển động từng nấc).
- 3/11/2026 [Đã chốt, Hiếu]: đội không có kính PICO, nên demo cha do **teleop ảo** sinh, rồi nhân bằng S2. Teleop ảo là một người điều khiển tự động phát tín hiệu tay cầm, cần gạt và nút vào đúng ống teleop PICO của SIMPLE (nhiệm vụ 2), nên dữ liệu cùng định dạng và `action_layout` với demo PICO thật. Khi có kính, demo PICO thật thay demo ảo mà không phải sửa code.
- Teleop ảo không phải dữ liệu người. Mọi episode ghi `source_kind = synthetic`, không bao giờ ghi là teleop.
- Planner S1 của DA-33 khóa eo và ra một kiểu chuyển động (D-12 trên nhánh DA-33). Teleop ảo đi qua IK có eo của SIMPLE và rút phong cách ngẫu nhiên mỗi lượt.

## Tiêu chí chấp nhận

1. Phiên teleop chạy trên `simple/G1WholebodyTrayTransferTeleop-v0` ở `--sim-mode=mujoco` qua wrapper của đội, không fork SIMPLE. Wrapper: reset theo danh sách (level, seed) của dải train ở mức 0 và 1; giới hạn 4500 bước; ghi thêm vào mỗi frame tư thế khay, vị trí 6 linh kiện và 7 cờ bước của `StepTracker`; ghi khối `flywheel` vào `environment_config`; ghi log mọi lượt thử. Chỗ cắm ở [docs/g0/tray/pico-teleop.md](../../g0/tray/pico-teleop.md).
2. Teleop ảo: phát tư thế hai tay cầm trong khung PICO (đổi ngược từ mục tiêu cổ tay qua `WristsPreProcessor`), cần gạt đi và quay, cò và grip (ba mức đóng của PICO), nút kích hoạt; vòng kín trên tư thế khay và vùng đích như người nhìn qua kính; máy pha theo 7 bước scorer. Mỗi episode rút một bộ tham số phong cách từ seed phong cách; dải tham số lấy từ số đo teleop người của tác giả (AC 8) nếu PO cho dùng psi-data, không thì ghi là giả định. Chạy bằng đồng hồ sim: cùng (điều kiện, seed phong cách) thì ra cùng episode.
3. Ít nhất 100 demo cha teleop ảo đạt `check_success`, mỗi demo ghi `source_kind = synthetic`, `synthetic_tier = S1`, `source_detail = virtual_teleop`, `action_quality = planned`, tham số phong cách, seed phong cách, level, seed, phiên bản. Sổ lượt và sổ chi phí như AC 1.
4. Mỗi demo cha cắt theo 7 bước bằng `StepTracker` thành ba đoạn: gần khay (bước 1–3), đi mang (bước 4–5), đặt (bước 6–7). Ranh giới đoạn ghi kèm demo.
5. Generator S2: với điều kiện mới (level 0 hoặc 1, seed train, không dùng mức 2, dev hay holdout; spec mục 7.3), đoạn gần khay biến đổi theo tư thế khay mới, đoạn đặt theo vùng đích mới, kiểu MimicGen; đoạn đi sinh lại bằng `navigate_cmd`; nối đoạn bằng nội suy cổ tay và IK có eo của ống teleop. Cùng (demo cha, điều kiện, seed sinh) thì ra cùng biến thể. Demo cha có thể là teleop ảo hoặc PICO thật.
6. Chỉ nhận biến thể đạt `check_success` trong 4500 bước. Lượt hỏng vẫn ghi nhãn lỗi, thời gian, chi phí vào sổ lượt sinh chỉ ghi thêm. Mỗi biến thể ghi `source_kind = synthetic`, `synthetic_tier = S2`, `action_quality = planned`, `parent_episode`, tham số biến đổi, khoảng cách điều kiện tới demo cha, phiên bản generator; định dạng LeRobot và `action_layout` giống demo cha.
7. Đo tỉ lệ đạt và giây máy mỗi episode đạt, cho teleop ảo và cho S2, trên 100 lượt mỗi loại ở rtx3060 (tối đa 22 worker). Chạy lô sản xuất (mục tiêu ít nhất 1000 biến thể S2 đạt, chốt sau phép đo); release có hash; sổ chi phí.
8. Bảng so chuyển động giữa teleop người của tác giả (psi-data, nếu được dùng), teleop ảo, S2 và S1 của DA-33 (nếu đã merge): biên độ góc eo, khoảng cách khuỷu tới thân, tốc độ đỉnh và jerk cổ tay, thời gian dừng giữa pha, độ phân tán quỹ đạo cổ tay giữa các lượt. Kiểm mắt 10 video ngẫu nhiên mỗi loại.

## Nhiệm vụ

Kế hoạch ở mục "Kế hoạch teleop ảo" và "Kế hoạch generator S2" bên dưới.

- [x] 1. Đọc đường teleop PICO của SIMPLE trên env khay, ghi chỗ cắm và khoảng trống (AC 1)
- [x] 2. Wrapper teleop khay: reset theo (level, seed), ghi trạng thái khay, khối `flywheel`, log lượt thử; test bằng streamer giả, không cần kính (AC 1)
- [x] 3. Đo phong cách teleop người từ psi-data của tác giả (ôm thùng hai tay, đi giữa hai bàn), ra dải tham số phong cách (AC 2, 8)
- [x] 4. Đồng hồ sim cho agent: tất định, không chờ thời gian thực; hai lần chạy cùng seed ra cùng frame (AC 2, 5). Đo: gần 1× thời gian thực mỗi worker, xem [virtual-teleop.md](../../g0/tray/virtual-teleop.md)
- [x] 5. Teleop ảo: phép đổi ngược của `WristsPreProcessor` (test CPU khứ hồi), streamer ảo lấy ý định từ `TrayPlanner` của DA-33 (cổ tay, lệnh đi, bàn tay) và phát tín hiệu PICO; một episode đạt `check_success` (AC 2). Đo: 8/9 lượt đạt, xem [virtual-teleop.md](../../g0/tray/virtual-teleop.md)
- [x] 6. Phong cách ngẫu nhiên mỗi episode theo seed phong cách; meta của AC 3 (AC 2, 3). Đo: 16/16 đạt, đủ 7 cờ bước, xem [virtual-teleop.md](../../g0/tray/virtual-teleop.md)
- [x] 7. Sinh hàng loạt demo cha: ít nhất 100 đạt, sổ lượt, sổ chi phí (AC 3, 7). Đo: 129 demo cha đủ 7 cờ bước từ 160 lượt với planner D-25 (lô `parents-1103b`), 121 s worker mỗi demo cha, xem [virtual-teleop.md](../../g0/tray/virtual-teleop.md)
- [ ] 8. Cắt demo theo 7 bước (AC 4)
- [ ] 9. Streamer phát lại S2: phát lại demo không biến đổi qua ống teleop, đo tỉ lệ tái tạo (AC 5)
- [ ] 10. Biến đổi theo khung khay và vùng đích, sinh lại đoạn đi, nối đoạn (AC 5)
- [ ] 11. Lọc theo `check_success`, meta, lineage, sổ lượt sinh (AC 6)
- [ ] 12. Đo tỉ lệ đạt và chi phí, chạy lô, release, bảng so chuyển động (AC 7, 8)

Khi có kính PICO (ngoài phần Done của story này): cài `xrobotoolkit_sdk` và XRoboToolkit PC service, thu 5–10 demo PICO bằng `--streamer pico`, cho chúng làm demo cha của S2.

## Phạm vi file

Theo 07 mục 3.1. pr-guard chặn PR sửa file ngoài danh sách này; file story luôn được sửa.

- `packages/flywheel-simple/src/flywheel_simple/tray/pico/`, `packages/flywheel-simple/tests/tray/pico/`
- `packages/flywheel-simple/src/flywheel_simple/tray/s2/`, `packages/flywheel-simple/tests/tray/s2/`
- `configs/sim/tray_virtual_teleop.yaml`, `configs/sim/tray_s2.yaml`
- `scripts/g0/tray/pico/`, `scripts/g0/tray/s2/`
- `docs/g0/tray/pico-teleop.md`, `docs/g0/tray/virtual-teleop.md`, `docs/g0/tray/s2.md`, `docs/g0/ledger/DA-35.csv`

Teleop ảo là một streamer, nên nằm trong `tray/pico/`. Thư mục con mới, không trùng file với DA-32 hay DA-33. Quyết định ghi ở `docs/g0/tray/virtual-teleop.md` và `docs/g0/tray/s2.md`, không ở `docs/g0/tray/decisions.md`, để không đụng số D-xx của nhánh DA-33 chưa merge.

Ngoài phạm vi, cần PR riêng: dòng DA-35 trong 07 mục 2.2; sửa design 28/10 mục 5 và design 27/10 mục 4.4, 5.4 (PO).

## Kế hoạch teleop ảo

| Phần | Cách làm [Đề xuất] |
|---|---|
| Chỗ cắm | Một streamer thay `PicoStreamer` trong `StreamerDecoupledAgent` (nhiệm vụ 2). Ra `StreamerOutput` giống hệt PICO: `left_wrist`, `right_wrist` (4 × 4, khung tay cầm so với kính), ngón tay dạng ba mức của PICO, `navigate_cmd` từ cần gạt (tối đa 0,5 m/s và 1 rad/s như `PicoStreamer`), chiều cao thân, nút kích hoạt |
| Đổi ngược cổ tay | Người điều khiển ảo nghĩ bằng mục tiêu cổ tay trong khung robot. `WristsPreProcessor` là phép affine (`T_robot = T_ee_hiệu_chuẩn · S(T_tay_cầm_lúc_kích_hoạt⁻¹ · T_tay_cầm)`, `S` nhân phần tịnh tiến với `motion_scale`), nên đổi ngược chính xác được. Test CPU: khứ hồi sai số dưới 1e-9 |
| Quan sát | Tư thế khay và vùng đích lấy từ `info["privileged"]`, như người thấy qua kính. Chỉ teleop ảo đọc, policy không thấy (design 28/10 mục 3.6) |
| Máy pha | Dùng lại `flywheel_simple.tray.planner.TrayPlanner` của DA-33 (sau khi merge): pha theo 7 bước scorer, cách cầm D-19, bù cổ tay chùng theo lòng bàn tay đo được. Teleop ảo đổi đầu ra của planner (cổ tay trong khung đế, lệnh đi, hướng, độ đóng tay) thành tín hiệu PICO và thêm lớp phong cách. Planner được chỉnh khi eo khóa; IK của PICO cho eo cử động, nên kiểm lại tỉ lệ đạt |
| Chuyển động | Mỗi đoạn tay là min-jerk có điểm qua giữa (đường cong), hồ sơ vận tốc lệch đỉnh, thời gian theo khoảng cách; tư thế nghỉ khuỷu sát thân, lòng bàn tay hướng vào; với thấp thì IK có eo tự nghiêng thân. Cần gạt tăng và giảm dần như tay người |
| Phong cách mỗi lượt | Rút từ seed phong cách trong dải đã chốt: tốc độ với, độ cong, lệch đỉnh vận tốc, thời gian dừng giữa pha, độ cao mang, khoảng cách hai tay, tốc độ đi, gia tốc cần gạt, biên độ và tần số rung nhỏ. Ghi cả bộ tham số vào meta |
| Dải phong cách | Đo từ psi-data (nhiệm vụ 3): `G1WholebodyPickAndPlaceAndHugContainerTeleop-v0` (119,4 MB, decoupled WBC, ôm thùng hai tay) và `G1WholebodyLocomotionPickBetweenTablesTeleop-v0` (202,6 MB, đi giữa hai bàn). Nếu không được dùng, ước lượng và ghi là giả định |
| Đồng hồ | Agent con thay `time.monotonic()` bằng thời gian sim (cùng ý D-17), không ngủ cho đủ 50 Hz: tất định; tốc độ đo được gần 1× thời gian thực mỗi worker (nhiệm vụ 4) |
| Bàn tay | Chỉ ba mức đóng của PICO (cò, grip). Nếu không cầm chắc được tay cầm, ghi `Decision` và hỏi PO trước khi cho bàn tay đóng liên tục (lệch khỏi dữ liệu PICO thật) |

Rủi ro: chỉnh cách cầm có thể tốn nhiều vòng như DA-33 (40/48 sau nhiều lượt quét); ba mức đóng của PICO có thể không đủ cho tay cầm khay; "giống người" chỉ đúng tới mức dải phong cách đo được. Teleop ảo tự sinh được nhiều; S2 vẫn làm vì nó là đường nhân demo PICO thật sau này, và spec mục 6.10 cần đơn giá riêng của S1 và S2.

## Kế hoạch generator S2

| Bước | Cách làm [Đề xuất] |
|---|---|
| Đầu vào | Demo cha đạt QA, mỗi frame có `action` 43 khớp, `action.eef` (hai cổ tay trong khung gốc của robot model, vị trí và quaternion wxyz), `teleop.navigate_command`, tư thế đế, tư thế khay và linh kiện, cờ 7 bước |
| Cắt đoạn | Theo cờ của `StepTracker`: đoạn K (gần khay) từ đầu tới khi đạt bước 3 cộng 0,5 s giữ; đoạn W (đi mang) tới hết bước 5; đoạn P (đặt) tới khi đạt bước 7 |
| Biến đổi K | Tư thế cổ tay đổi sang khung khay lúc bắt đầu đoạn: `T_khay_cha⁻¹ · T_cổtay`, rồi đặt vào khay mới: `T_khay_mới · (…)`. Tính trong khung thế giới; mỗi bước đổi về khung robot bằng tư thế đế đo được (vòng kín, bù đế trôi) |
| Đi tới bàn A | Chỗ đứng trước bàn A dịch theo độ lệch của khay; `navigate_cmd` sinh bằng bộ điều khiển P tới chỗ đứng mới, theo hồ sơ vận tốc của demo (co giãn thời gian) |
| Biến đổi W | Giữ quỹ đạo cổ tay của demo trong khung robot; `navigate_cmd` sinh lại tới chỗ đứng trước bàn B, đặt so với vùng đích mới như trong demo |
| Biến đổi P | Như K nhưng theo khung vùng đích: `T_đích_mới · T_đích_cha⁻¹ · T_cổtay` |
| Nối đoạn | Nội suy vị trí và slerp hướng từ cổ tay hiện tại tới tư thế đầu của đoạn sau, mặc định 0,5 s (tham số) |
| Chạy | Streamer phát lại đưa mục tiêu cổ tay đã biến đổi vào IK có eo của ống teleop (qua phép đổi ngược của nhiệm vụ 5 hoặc thẳng vào `TeleopRetargetingIK`), đồng hồ sim, headless, mỗi worker một env |
| Chọn điều kiện | Demo cha rút đều; (level, seed) rút trong dải train mức 0 và 1 |
| Quy mô | Ước lượng, chưa đo: bước env 12–14 ms nên một lượt 90 s sim mất khoảng 1 phút máy; 22 worker cho khoảng 1300 lượt mỗi giờ trước khi lọc. Số thật lấy ở nhiệm vụ 12 |

Rủi ro: điều kiện xa demo cha thì cầm trượt; đế trôi khi mang làm lệch vùng đích. Cách đỡ: chọn demo cha gần điều kiện mới, ghi khoảng cách điều kiện để lọc sau.

## Ghi chú cho người làm

- Nguồn: design 27/10 mục 5.3, 5.4; design 28/10 mục 4, 5; story DA-29 (cùng ý cho task hai bàn), DA-33 (planner S1, cách cầm D-19), DA-16 (chỗ cắm thiết bị vào `teleop_decoupled_wbc`); spec 4.1 (biến thể không tính là demo gốc), 6.10, 10 (tuyến T2).
- psi-data trên Hugging Face không khai license (đọc API 3/11/2026). Chỉ dùng để đo thống kê phong cách sau khi PO cho phép; không train, không đưa vào release.
- Theo CLAUDE.md, không tạo nhánh từ nhánh chưa merge: trước khi DA-33 merge, phần cần planner dùng planner giả cùng giao diện (`step(state, base, report) -> PlannerCommand`).
- `flywheel_block` hiện ghi cứng `source_kind = teleop`; nhiệm vụ 6 cho nó nhận `synthetic` và tham số phong cách.
- Dữ liệu là sim G1, mức `public` (design 27/10 mục 8.4). Dữ liệu ở `fwdata/`, không commit.
- Chạy trên rtx3060 trong `~/denso-da35` (bản sao nhánh, venv SIMPLE dùng chung với `~/denso-da33`), lệnh dài chạy `nohup setsid … < /dev/null &`, tối đa 22 worker.

## Kiểm thử

- Đổi ngược `WristsPreProcessor` khứ hồi đúng (test CPU).
- Cùng (điều kiện, seed phong cách) thì teleop ảo ra cùng episode; cùng (demo cha, điều kiện, seed sinh) thì S2 ra cùng biến thể.
- Hai seed phong cách khác nhau cho quỹ đạo cổ tay khác nhau đo được.
- Phát lại demo không biến đổi đạt `check_success` ở đa số demo; số đo ghi ở `docs/g0/tray/s2.md`.
- Người review chạy lại 5 episode mỗi loại và ra tỉ lệ đạt cùng bậc.

## Người phụ trách

- Làm: Dương Đình Hiếu (đề xuất)
- Duyệt và merge: Dương Đình Hiếu (người duy nhất, 07 mục 3.4)

## Change log

| Ngày | Nội dung | Người |
|---|---|---|
| 3/11/2026 | PO chốt: S2 chỉ dùng lô demo cha D-25 `parents-1103b` (129 demo), lô D-19 `parents-1103` giữ để tham khảo; nhận hai giới hạn phong cách (tay có phong cách chỉ khi xa khay, dải cần gạt hẹp hơn người) làm giới hạn đã biết ([virtual-teleop.md](../../g0/tray/virtual-teleop.md)) | PO (Hiếu) |
| 3/11/2026 | PO chọn merge DA-33 và dùng lại `TrayPlanner` làm phần ý định của teleop ảo (thay cho chỉ chép số D-19); nhiệm vụ 5 trở đi phụ thuộc DA-33 đã merge | PO (Hiếu) |
| 3/11/2026 | PO duyệt bản teleop ảo cộng S2 và việc tải hai file psi-data (322 MB) chỉ để đo phong cách | PO (Hiếu) |
| 3/11/2026 | Viết lại theo hướng teleop ảo cộng S2 (PO chọn, vì đội không có kính PICO): AC 2, 3, 7, 8 mới, nhiệm vụ 3–12, thêm `configs/sim/tray_virtual_teleop.yaml` và `docs/g0/tray/virtual-teleop.md` vào Phạm vi file; demo PICO thật thành phần làm khi có kính | Claude |
| 3/11/2026 | PO duyệt story và Phạm vi file. Người làm, ước lượng, phần cứng PICO, người thu và máy chạy sim chưa chốt | PO (Hiếu) |
| 3/11/2026 | Tạo story nháp: S2 cho task khay từ demo PICO; nhiệm vụ 1 (đọc đường teleop PICO) đã làm | Claude |

## Ghi chép khi làm

- Giờ thực:
- Công cụ AI đã dùng: Claude Code (nhiệm vụ 1–7)
- Ghi chú hoàn thành: Nhiệm vụ 2 (3/11/2026): wrapper, agent với streamer bất kỳ và vòng phiên; ghi được dataset LeRobot thật sau khi cài các gói ghi của [PR #27](https://github.com/hiwe0305/denso-challenge/pull/27) ([pico-teleop.md](../../g0/tray/pico-teleop.md) khoảng trống 11)
- File đã tạo hoặc sửa: `configs/sim/tray_virtual_teleop.yaml`, `docs/g0/ledger/DA-35.csv`, `docs/g0/tray/pico-teleop.md`, `docs/g0/tray/virtual-teleop.md`, `packages/flywheel-simple/src/flywheel_simple/tray/pico/`, `packages/flywheel-simple/tests/tray/pico/`, `scripts/g0/tray/pico/generate_parents.py`, `scripts/g0/tray/pico/measure_teleop_style.py`
