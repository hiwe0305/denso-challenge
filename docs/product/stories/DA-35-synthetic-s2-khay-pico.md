# DA-35 · Synthetic S2 cho task bê khay từ demo teleop PICO

## Trạng thái

| Trường | Giá trị |
|---|---|
| Trạng thái | Sẵn sàng (PO duyệt story và Phạm vi file 3/11/2026). Nhiệm vụ 3 trở đi chờ có bộ PICO |
| Người làm | Hiếu (đề xuất, PO giao) |
| Làn | Adapter simulator (`flywheel-simple`) |
| Story PRD | Story của [design 28/10/2026](../../superpowers/specs/2026-10-28-tray-transfer-he-design.md) mục 5 (dòng Synthetic S2) · [design 27/10/2026](../../superpowers/specs/2026-10-27-g1-psi0-demo-design.md) mục 5.4 · spec mục 6.10, tuyến T2 ở mục 10 |
| Nhãn | [Adapter] · `epic:9` · `gate:G1` · `area:sim` |
| Sprint | S2; ngày chốt sau khi biết có PICO và ai thu |
| Ước lượng | Chưa chốt. Người viết ước lượng thô 25–35 giờ, chưa tính giờ thu demo; PO chốt |
| Phụ thuộc | DA-32 (task, vị từ 7 bước, `check_success`; đã merge). Bộ PICO 4 cùng 2 tay cầm, người thu, máy chạy sim cùng mạng LAN với kính. PyAV và `xrobotoolkit_sdk` trong venv SIMPLE (PR `chore-` riêng cho `setup_simple.sh` của S1-02). Không phụ thuộc mã của DA-33: S2 chạy qua chính ống teleop của SIMPLE |

## Story

Là trưởng nhóm, tôi muốn thu 5–10 demo teleop PICO của task bê khay rồi sinh hàng nghìn biến thể kiểu MimicGen từ các demo đó, để dữ liệu robot cho Ψ₀ chuyển động như người teleop G1 (nghiêng eo, khuỷu sát thân, hai tay liền mạch, mỗi lượt khác nhau) và đủ lớn cho DA-34.

Bối cảnh [Đã chốt, Hiếu, 3/11/2026]: chọn S2 từ demo PICO, không dùng video người retarget hay bàn phím (bàn phím ra chuyển động từng nấc). Planner S1 của DA-33 chỉ ra một kiểu chuyển động và khóa eo (D-12 trên nhánh DA-33); nó giữ vai trò đường lui và sau này có thể giúp cắt demo theo pha.

## Tiêu chí chấp nhận

1. Teleop PICO chạy trên `simple/G1WholebodyTrayTransferTeleop-v0` ở `--sim-mode=mujoco` qua `flywheel_simple.tray.run` và một wrapper của đội, không fork SIMPLE. Wrapper: reset theo danh sách (level, seed) của dải train ở mức 0 và 1; giới hạn 4500 bước; ghi thêm vào mỗi frame tư thế khay, vị trí 6 linh kiện và 7 cờ bước của `StepTracker`; ghi khối `flywheel` vào `environment_config`; ghi log mọi lượt thử, kể cả lượt bị bỏ. Khoảng trống và chỗ cắm ở [docs/g0/tray/pico-teleop.md](../../g0/tray/pico-teleop.md).
2. Có ít nhất 5 demo PICO đạt `check_success` (mục tiêu 10, từ ít nhất 2 người thu nếu có), mỗi demo ghi `source_kind = teleop`, `source_detail = teleop_pico`, mã giả danh người thu, level, seed, phiên bản SIMPLE và wrapper. Mỗi phiên thu ghi một mục sổ chi phí: phút người, số lượt, số lượt đạt.
3. Mỗi demo đạt được cắt theo 7 bước scorer bằng `flywheel_simple.tray.predicates.StepTracker` thành ba đoạn: gần khay (bước 1–3), đi mang (bước 4–5), đặt (bước 6–7). Ranh giới đoạn ghi kèm demo.
4. Generator: với một điều kiện mới (level 0 hoặc 1, seed train, không dùng mức 2, dev hay holdout; spec mục 7.3), đoạn gần khay biến đổi theo tư thế khay mới, đoạn đặt theo vùng đích mới, kiểu MimicGen; đoạn đi sinh lại bằng `navigate_cmd`; các đoạn nối bằng nội suy cổ tay và IK. Biến thể chạy qua cùng ống của demo (`TeleopPolicy` với `TeleopRetargetingIK` có eo, `G1DecoupledWholeBodyPolicy`), chỉ thay `PicoStreamer` bằng streamer phát quỹ đạo đã biến đổi, với đồng hồ điều khiển theo thời gian sim. Cùng (demo cha, điều kiện, seed sinh) thì ra cùng biến thể.
5. Chỉ nhận biến thể đạt `check_success` trong 4500 bước. Lượt hỏng vẫn ghi nhãn lỗi của `StepTracker`, thời gian và chi phí vào sổ lượt sinh chỉ ghi thêm.
6. Mỗi biến thể ghi `source_kind = synthetic`, `synthetic_tier = S2`, `action_quality = planned`, `parent_episode`, tham số biến đổi (độ lệch tư thế khay, vùng đích, chỗ đứng), khoảng cách điều kiện tới demo cha, phiên bản generator. Định dạng LeRobot và `action_layout` giống hệt demo PICO.
7. Đo tỉ lệ sinh đạt và giây máy mỗi biến thể đạt trên 100 lượt ở rtx3060 (tối đa 22 worker). Chạy lô sản xuất; số biến thể đạt chốt sau phép đo (mục tiêu ít nhất 1000); release có hash; sổ chi phí.
8. Bảng so chuyển động giữa demo PICO, biến thể S2 và S1 của DA-33 (nếu đã merge): biên độ góc eo, khoảng cách khuỷu tới thân, jerk cổ tay, độ phân tán quỹ đạo cổ tay giữa các lượt. Kiểm mắt 10 video biến thể ngẫu nhiên.

## Nhiệm vụ

Kế hoạch generator ở mục "Kế hoạch generator" bên dưới.

- [x] 1. Đọc đường teleop PICO của SIMPLE trên env khay, ghi chỗ cắm và khoảng trống (AC 1)
- [x] 2. Wrapper teleop khay: reset theo (level, seed), ghi trạng thái khay, khối `flywheel`, log lượt thử; test bằng streamer giả, không cần kính (AC 1)
- [ ] 3. Cài PyAV, `xrobotoolkit_sdk`, XRoboToolkit PC service trên máy sim; nối kính; một demo thử (AC 1)
- [ ] 4. Thu 5–10 demo PICO, QA bằng `check_success`, sổ chi phí, hướng dẫn người thu (AC 2)
- [ ] 5. Cắt demo theo 7 bước, kiểm khung tọa độ của `action.eef` (AC 3)
- [ ] 6. Streamer phát lại và đồng hồ sim: phát lại demo không biến đổi qua ống teleop, đo tỉ lệ tái tạo (AC 4)
- [ ] 7. Biến đổi theo khung khay và vùng đích, sinh lại đoạn đi, nối đoạn (AC 4)
- [ ] 8. Lọc theo `check_success`, meta, lineage, sổ lượt sinh (AC 5, 6)
- [ ] 9. Đo tỉ lệ đạt và chi phí, chạy lô, release, bảng so chuyển động (AC 7, 8)

## Phạm vi file

Theo 07 mục 3.1. pr-guard chặn PR sửa file ngoài danh sách này; file story luôn được sửa.

- `packages/flywheel-simple/src/flywheel_simple/tray/pico/`, `packages/flywheel-simple/tests/tray/pico/`
- `packages/flywheel-simple/src/flywheel_simple/tray/s2/`, `packages/flywheel-simple/tests/tray/s2/`
- `configs/sim/tray_s2.yaml`
- `scripts/g0/tray/pico/`, `scripts/g0/tray/s2/`
- `docs/g0/tray/pico-teleop.md`, `docs/g0/tray/s2.md`, `docs/g0/ledger/DA-35.csv`

Thư mục con mới, không trùng file với DA-32 hay DA-33 (cùng nằm dưới `flywheel_simple/tray/`). Quyết định của story ghi ở `docs/g0/tray/s2.md`, không ở `docs/g0/tray/decisions.md`, để không đụng số D-xx của nhánh DA-33 chưa merge.

Ngoài phạm vi, cần PR riêng: `scripts/g0/simple/setup_simple.sh` (PyAV, `xrobotoolkit_sdk`; S1-02), dòng DA-35 trong 07 mục 2.2, sửa design 28/10 mục 5 và design 27/10 mục 4.4 (PO).

## Kế hoạch generator

| Bước | Cách làm [Đề xuất] |
|---|---|
| Đầu vào | Demo PICO đạt QA, mỗi frame có `action` 43 khớp, `action.eef` (hai cổ tay, vị trí và quaternion wxyz), `teleop.navigate_command`, tư thế đế, tư thế khay và linh kiện (wrapper ghi), cờ 7 bước |
| Cắt đoạn | Theo cờ của `StepTracker`: đoạn K (gần khay) từ đầu tới khi đạt bước 3 cộng 0,5 s giữ; đoạn W (đi mang) tới hết bước 5; đoạn P (đặt) tới khi đạt bước 7 |
| Biến đổi K | Tư thế cổ tay của demo đổi sang khung khay lúc bắt đầu đoạn: `T_khay_cha⁻¹ · T_cổtay`, rồi đặt vào khay mới: `T_khay_mới · (…)`. Tính trong khung thế giới; mỗi bước đổi về khung hông bằng tư thế đế đo được (vòng kín, bù đế trôi) |
| Đi tới bàn A | Chỗ đứng trước bàn A dịch theo độ lệch của khay; `navigate_cmd` sinh bằng bộ điều khiển P tới chỗ đứng mới, theo hồ sơ vận tốc của demo (co giãn thời gian) |
| Biến đổi W | Giữ quỹ đạo cổ tay của demo trong khung hông (giữ nguyên cách người cầm và lắc khi đi); `navigate_cmd` sinh lại tới chỗ đứng trước bàn B, đặt so với vùng đích mới như trong demo |
| Biến đổi P | Như K nhưng theo khung vùng đích: `T_đích_mới · T_đích_cha⁻¹ · T_cổtay` |
| Nối đoạn | Nội suy vị trí và slerp hướng từ cổ tay hiện tại tới tư thế đầu của đoạn sau, mặc định 0,5 s (tham số); IK do `TeleopRetargetingIK` của ống teleop giải, gồm eo |
| Bàn tay | Chép chuỗi lệnh đóng mở theo đoạn, căn theo thời gian của đoạn |
| Chạy | Streamer phát lại thay `PicoStreamer`; agent con của `PicoDecoupledAgent` dùng đồng hồ sim thay `time.monotonic` (cùng ý D-17); headless, EGL; mỗi worker một env |
| Chọn điều kiện | Demo cha rút đều; (level, seed) rút trong dải train mức 0 và 1; tùy chọn nhiễu nhỏ trên cổ tay (tham số, mặc định tắt) |
| Nhận | Chỉ biến thể đạt `check_success`; ghi meta của AC 6; lượt hỏng ghi nhãn lỗi |
| Quy mô | Ước lượng, chưa đo: bước env 12–14 ms nên một lượt 90 s sim mất khoảng 1 phút máy; 22 worker cho khoảng 1300 lượt mỗi giờ trước khi lọc. Số thật lấy ở nhiệm vụ 9 |

Rủi ro chính: điều kiện xa demo cha thì cầm trượt (MimicGen chỉ đúng khi tư thế tương đối giữ được); đế trôi khi mang làm lệch vùng đích; biến thể mang theo cả động tác thừa của người thu; số demo ít làm đa dạng thấp. Cách đỡ: chọn demo cha gần điều kiện mới, thu demo từ nhiều người, ghi khoảng cách điều kiện để lọc sau.

## Ghi chú cho người làm

- Nguồn: design 27/10 mục 5.4; design 28/10 mục 4, 5; story DA-29 (cùng ý cho task hai bàn); DA-16 (chỗ cắm thiết bị vào `teleop_decoupled_wbc`); spec 4.1 (biến thể không tính là demo gốc), 6.10, 10 (tuyến T2).
- Design 27/10 mục 4.4 ghi "PICO không có trong kế hoạch"; design 28/10 mục 5 ghi S2 từ S1 hoặc bàn phím. Story này đổi nguồn của S2 sang PICO theo quyết định của Hiếu; hai design cần dòng change log của PO.
- Dữ liệu demo và biến thể là sim G1, mức `public` (design 27/10 mục 8.4). Kính PICO chỉ gửi tư thế tay cầm và đầu, không quay người thu. Dữ liệu ở `fwdata/`, không commit.
- Sinh hàng loạt trên rtx3060 trong `~/denso-da33` (venv SIMPLE riêng), lệnh dài chạy `nohup setsid … < /dev/null &`, tối đa 22 worker.

## Kiểm thử

- Wrapper và streamer phát lại chạy được không cần kính (streamer giả), trên máy có venv SIMPLE.
- Với một demo mẫu, một điều kiện và một seed sinh cố định, biến thể ra giống nhau giữa hai lần chạy.
- Phát lại demo không biến đổi đạt `check_success` ở đa số demo; số đo ghi ở `docs/g0/tray/s2.md`.
- Người review chạy lại 5 biến thể và ra tỉ lệ sinh đạt cùng bậc.

## Người phụ trách

- Làm: Dương Đình Hiếu (đề xuất)
- Duyệt và merge: Dương Đình Hiếu (người duy nhất, 07 mục 3.4)

## Change log

| Ngày | Nội dung | Người |
|---|---|---|
| 3/11/2026 | PO duyệt story và Phạm vi file. Người làm, ước lượng, phần cứng PICO, người thu và máy chạy sim chưa chốt | PO (Hiếu) |
| 3/11/2026 | Tạo story nháp: S2 cho task khay từ demo PICO; nhiệm vụ 1 (đọc đường teleop PICO) đã làm | Claude |

## Ghi chép khi làm

- Giờ thực:
- Công cụ AI đã dùng: Claude Code (nhiệm vụ 1)
- Ghi chú hoàn thành: Nhiệm vụ 2 (3/11/2026): wrapper, agent với streamer bất kỳ và vòng phiên; ghi được dataset LeRobot thật sau khi cài các gói ghi của [PR #27](https://github.com/hiwe0305/denso-challenge/pull/27) ([pico-teleop.md](../../g0/tray/pico-teleop.md) khoảng trống 11)
- File đã tạo hoặc sửa: `docs/g0/tray/pico-teleop.md`, `packages/flywheel-simple/src/flywheel_simple/tray/pico/`, `packages/flywheel-simple/tests/tray/pico/`
