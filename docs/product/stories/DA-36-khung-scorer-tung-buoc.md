# DA-36 · Khung scorer từng bước và lớp lỗi chung

## Trạng thái

| Trường | Giá trị |
|---|---|
| Trạng thái | Nháp (Châu viết 2/11/2026; PO đặt mã DA-36 ngày 3/11/2026) |
| Người làm | Châu |
| Làn | Đánh giá (`flywheel-eval`) |
| Story PRD | 3.3 · Epic 3 · FR16, FR17; [spec v10.5](../../spec-v10-failure-to-data.md) mục 5.1, 5.2; [design 27/10/2026](../../superpowers/specs/2026-10-27-g1-psi0-demo-design.md) mục 3 (bảng 6 bước), mục 10 |
| Nhãn | [Lõi] · `epic:3` · `gate:G1` · `area:core` |
| Sprint | S2 · **Lịch 3/11/2026:** merge trước **8/11/2026** (07 mục 2.4) |
| Ước lượng | 13 giờ (04 mục 4.2, ước lượng) |
| Phụ thuộc | S1-08 (04 mục 4.2); `Score` nằm trong S1-10 (#36, **chưa merge**); `StageSpec`, `FailureKindSpec`, `StageEvaluation` của `flywheel.contracts` (đã có trên master). Không chặn: `Trace` thật của SIMPLE — story chạy trên trace tổng hợp, xem AC 6 |

## Story

Là kỹ sư đánh giá, tôi muốn một scorer độc lập chấm từng bước của task từ một trace đã ghi, để mỗi lượt lỗi nói được **hỏng ở bước nào và kiểu lỗi gì** chứ không chỉ "trượt", vì cả chuỗi chẩn đoán (DA-13), cụm lỗi và evidence card đều bắt đầu từ bước hỏng k.

## Tiêu chí chấp nhận

1. Scorer nhận `TaskDefinition` (các bước, vị từ, điều kiện chạy suốt) và ghi ra **`Score`** (03 mục 4.3): trạng thái mỗi bước là **đạt, trượt, chưa thử, chưa rõ**. `StageEvaluation.stage_success` hiện là `bool | None` (3 trạng thái) và là output của `TaskDefinition.evaluate()`; trường còn thiếu (enum 4 trạng thái, lý do "chưa rõ", thời điểm vào và ra từng bước) đi qua issue Contract change cho Long, không thêm trong code làn. Số bước lấy từ `TaskDefinition`, **không viết cứng trong mã**: task hai bàn có 6 bước (spec mục 5.1), task bê khay có 7 bước con (design 28/10 mục 3.2), và một scorer phải chấm được cả hai.
2. Quy ước trạng thái đúng spec mục 5.1, không được lẫn: bước chưa tới là **chưa thử**, không phải trượt; thiếu tín hiệu là **chưa rõ**, không phải đạt. Có test cho đúng hai ca lẫn này.
3. Gán **bước hỏng đầu tiên k** và một kiểu lỗi của spec mục 5.2; thiếu tín hiệu thì `L-UNKNOWN` và không gán kiểu. Mỗi kiểu lỗi mang **lớp lỗi chung** (tiếp cận, gắp, mang, đặt, thăng bằng) để L1 gộp thống kê giữa task (06 mục 9); ở L0 trường này chỉ được ghi, không dùng để chọn can thiệp.
4. Kiểu lỗi và lớp lỗi chung đọc từ `FailureKindSpec` của `TaskDefinition`, không viết cứng: bộ mã của task hai bàn và bộ mã của task bê khay khác nhau (xem "Chỗ cần PO quyết" mục 1).
5. Scorer là **bước tính thuần**: cùng một trace vào thì cùng một kết quả ra, không chạy simulator, không gọi model, không đọc đồng hồ (NFR1, 04 mục 9.3). Chạy lại cho kết quả trùng, có test.
6. Chạy trên CPU với trace tổng hợp dựng trong test, một ca cho **mỗi** kiểu lỗi của bộ mã đang khai, cộng một ca thành công và một ca thiếu tín hiệu. Không cần `Trace` thật của SIMPLE để đạt AC này; hiệu chỉnh với cờ `check_success` của SIMPLE là story 3.5, không thuộc story này.

## Nhiệm vụ

- [x] 1. Đọc `TaskDefinition` và trace tổng hợp qua contracts, lớp đọc tách khỏi phần chấm (AC 1, 5)
- [x] 2. Chấm trạng thái từng bước, bốn trạng thái và hai quy ước của AC 2 (AC 1, 2)
- [x] 3. Bước hỏng đầu tiên k và kiểu lỗi từ `FailureKindSpec`, lớp lỗi chung (AC 3, 4)
- [x] 4. Điều kiện chạy suốt episode (thăng bằng) và `L-BALANCE` ở bất kỳ bước nào (AC 1, 3)
- [x] 5. `api.py`, lệnh `fw eval score` và artifact kết quả (AC 5)
- [ ] 6. Test một ca mỗi kiểu lỗi, ca thành công, ca thiếu tín hiệu (AC 6)

## Phạm vi file

Theo 07 mục 3.1. pr-guard chặn PR sửa file ngoài danh sách này; file story luôn được sửa.

- `packages/flywheel-eval/src/flywheel/eval/scorer/`
- `packages/flywheel-eval/src/flywheel/eval/api.py`, `packages/flywheel-eval/src/flywheel/eval/cli.py`, `packages/flywheel-eval/src/flywheel/eval/config.py`
- `packages/flywheel-eval/tests/unit/scorer/`, `packages/flywheel-eval/tests/contract/scorer/`
- `configs/eval/scorer/`
- `packages/flywheel-eval/pyproject.toml` (chủ package là Châu, 07 mục 2.1 luật 2): khai `pyarrow`, thư viện mà `TaskDefinition.evaluate()` nhận bảng tín hiệu bằng
- `uv.lock` (file dùng chung, R6): chỉ ba dòng ghi lại `pyarrow` cho `flywheel-eval`; không thêm gói mới vào khóa, `pyarrow` đã có sẵn qua `flywheel-contracts`

## Chỗ cần PO quyết trước khi làm

1. **Hai bộ mã kiểu lỗi chưa khớp.** Spec mục 5.2 có 10 mã (L-REACH, L-GRASP, L-SLIP, L-WALK, L-COLLIDE, L-PLACE, L-RELEASE, L-BALANCE, L-TIMEOUT, L-UNKNOWN). Design 28/10 mục 3.3 thêm 4 mã cho task bê khay, **vẫn ở trạng thái [Đề xuất]**: L-PART-DROP, L-TRAY-TILT, L-ONE-HAND, L-PLACE-POSE. DA-32 đã code 6 nhãn trong `flywheel_simple.tray.predicates`, trong đó 4 nhãn mới chưa có trong spec mục 5.2 và 2 nhãn (L-PLACE-POSE so với L-PLACE) gần trùng nhau.
   Story này **không tự chốt**: scorer đọc bộ mã từ `FailureKindSpec` nên chạy được với cả hai bộ, nhưng cần PO (a) đưa 4 mã của design 28/10 vào spec mục 5.2 kèm lớp lỗi chung của từng mã, hoặc (b) ghi rõ chúng là mã riêng của task bê khay. Thiếu quyết định này thì **lớp lỗi chung của 4 mã mới không có giá trị**, và FR17 (gộp thống kê ở L1) không đạt được.
2. **Ranh giới với DA-32.** DA-32 đã có vị từ 7 bước và `check_success()` trong `flywheel_simple.tray.predicates`, đọc trạng thái MuJoCo. Story này là phần của **làn Đánh giá**: chấm từ trace đã ghi, không chạy simulator, dùng được cho mọi task. Hai thứ không trùng nhưng phải không lệch nhau; đề nghị DA-32 là nguồn sự thật cho vị từ của task bê khay và story này đọc lại cùng tham số từ `configs/sim/tray.yaml` qua `TaskDefinition`, không chép lại số.
3. **Chỉ số chính ở holdout là cờ `check_success` của SIMPLE**, scorer chỉ cho chỉ số theo bước (03 ADR-14, FR39). Story này không được dùng để tính chỉ số chính.

## Ghi chú cho người làm

- Chỉ import nhân (`flywheel.contracts`, `flywheel.store`, `flywheel.testkit`); không import `simple`, `mujoco`, `torch` hay adapter (03 mục 5.2, 7.3).
- `scorer/` là thư mục của Châu trong `flywheel-eval`; `agentqa/` của Hưng không chạm vào (07 mục 2.1).
- Kết quả scorer là `Score` theo 03 mục 4.3, có `failure_class`; Long đọc nó trong `decide`, Hưng đọc trong Agent QA/QC — qua `api.py`, không import module bên trong (07 mục 2.0 luật 3).
- Mọi ngưỡng vị từ (r_reach, h_grasp, h_lift, h_place, T_stable) nằm trong cấu hình, không trong mã; cách làm giống `configs/eval/diagnosis/train.yaml` của DA-08 (có hash, ghi `config_sha256` vào artifact).
- Bài học từ DA-08 nên áp lại: **thiếu tín hiệu phải ra "chưa rõ" kèm lý do**, không bao giờ im lặng thành "đạt" (FR21). Đối chứng phải kiểm cả "không có lỗi" **và** "không có bước nào chưa rõ", vì một trace không chấm được cũng cho danh sách lỗi rỗng.

## Kiểm thử

- `uv run pytest packages/flywheel-eval/tests/unit/scorer packages/flywheel-eval/tests/contract/scorer`
- `uv run ruff check`, `uv run mypy`, `uv run lint-imports` theo README gốc.

## Người phụ trách

- Làm: Trần Trịnh Hoàng Châu
- Duyệt và merge: Dương Đình Hiếu (người duy nhất, 07 mục 3.4)
- Bình luận: Hiếu (vị từ task, `TaskDefinition`, DA-32 vị từ task bê khay), Long (`Score` cho `decide`), Thông (mã story, mẫu story)

## Change log

| Ngày | Nội dung | Người |
|---|---|---|
| 3/11/2026 | Đặt mã DA-36 (DA-35 đã dùng cho #40); phụ thuộc S1-08, `Score` của S1-10 chưa merge; AC 1 ghi ra `Score`, trường thiếu qua issue Contract change; hạn 8/11 theo 07 mục 2.4; gộp người bình luận DA-32 vào Hiếu | PO (Hiếu) |
| 2/11/2026 | Nháp story theo PRD 3.3, spec mục 5.1, 5.2 và 04 mục 4.2; nêu ba chỗ cần PO quyết | Châu (chờ SM, PO) |

## Ghi chép khi làm

- Giờ thực:
- Công cụ AI đã dùng:
- Ghi chú hoàn thành:
- File đã tạo hoặc sửa:
