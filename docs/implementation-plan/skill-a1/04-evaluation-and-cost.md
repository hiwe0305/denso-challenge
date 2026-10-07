# 04 · Chất lượng, tổng công và khả năng dùng lại

## Câu hỏi chính và controls

Primary: nguồn S hoặc H có giúp đạt **cùng ngưỡng chấp nhận task** với ít robot-data usage hoặc thấp hơn total cost hay không? Không gọi hai success estimates là tương đương về thống kê chỉ vì đều pass threshold. Equivalence/noninferiority giữa policies cần margin/power/paired analysis riêng nếu owner yêu cầu.

Pilot đầu R vs R+S, cùng parent/robot-budget/task/profile/dev rules. First-skill setup và recurring skill work báo riêng. S chưa hợp lệ hoặc baseline chưa usable thì không mở study. H route gates pass mới mở **R_common vs R_common+H** với architecture/common wrist objective và VLM freeze giống nhau như tài liệu02. Native-only R và R_common khác recipe; không gom gain của auxiliary objective vào human source effect. Economic comparison với workflow robot-only thực tế cũng phải tính setup/common motion overhead phát sinh. HS chỉ sau từng nguồn có lý do để phối hợp. Không bắt full factorial hoặc nhiều budgets/seeds trước feasibility.

Draft initial train budget20 robot seed roots, không khẳng định20 đủ. Nếu muốn claim giảm robot data, cần curve với budgets khác được chốt sau pilot; ghi tất cả calibration/bridge/correction/tuning roots đã dùng, kể cả ngoài train loader. Một comparison chỉ ở20 roots có thể kiểm quality gain ở budget đó, chưa xác định ít nhất bao nhiêu roots để đạt quality.

## Acceptance proposal cho MVP sim

Đề xuất q_min=90% full-task trong domain đã khóa. Đây là ngưỡng thử cho prototype, không chuẩn nhà máy. Task owner phải chốt tolerances/domain/cycle/q_min trước freeze. Per-episode deadline30s và stability2s cũng là draft, phải calibration.

Draft confirmatory final:100 independent scene starts lấy từ distribution/domain đã preregister, có object/target/appearance/contact conditions và sampling weights rõ. Mỗi policy được chấm cùng final scenarios để paired comparison; noise/seeds kiểm soát. Không lặp cùng scene100 lần rồi gọi là100 independent starts. Multiple training seeds phải có plan/cost riêng; một checkpoint không xác nhận seed robustness.

Acceptance thống kê candidate: one-sided95% exact binomial lower confidence bound của full-task success phải≥q_min, với assumptions độc lập/same-distribution đã chốt. Nếu stratified/fixed conditions làm binomial model không phù hợp, thay bằng analysis đúng sampling design **trước** final; không dùng bound tổng để bảo đảm từng condition. Coverage/regression và cycle cũng phải đạt thresholds đã khóa. Unknown/intervention/timeout không là successes.

Ví dụ tính toán, không kết quả robot: ở100 trials với binomial assumptions,96 successes cho lower bound≈91,08%;95 successes chỉ≈89,77%. Đây là xác minh công thức bằng SciPy, không minh chứng policy pass. Không lựa chọn n/threshold sau khi thấy final. Final phát hiện sai scorer/protocol → invalidate, sửa rồi dùng final mới.

## Cost ledger

Mỗi activity có unique ID, arm, skill/round, scope, hours, rate/currency, compute units và evidence. Blank=unknown, không default0. Không cộng chung engineer time hai lần. Sponsored usage vẫn báo economic cost; cash riêng. Dataset descendants không inflate independent robot roots.

`C_total = allocated setup + collection/reset + source processing + generation/rejects + QA + training/retries + probes/correction + evaluation/reporting`.

Chỉ so savings khi cả baseline/candidate đáp ứng functional quality/domain/cycle đã chốt; nếu baseline chưa đạt, phải tìm baseline usable trong budget hoặc báo comparator không đủ. Mọi failed runs/corrections tính trong study cost. Tiết kiệm giờ operator, giờ engineer, GPU, robot usage và tiền phải hiển thị riêng.

`Savings_per_accepted_skill = C_baseline − C_candidate`.

Lợi ích năm cần số skill changes/năm thực. One-time setup và recurring work phải phân bổ nhất quán; không nhân first-skill cost lên mỗi skill và không trừ setup hai lần. Chưa có số đo thì annual saving pending. Ngưỡng điểm hiệu quả6/8/10 trong PROMPT cần cơ sở lợi ích năm; không lấy nhiều clips, test pass hoặc wall time Python thay economic benefit.

## Kiểm đóng góp evidence workflow

Data flywheel dùng iterative development acquisition sau useful baseline. Mỗi round pin parent/binding/scorer và lưu plan/release/checkpoint/eval/decision/cost. Integration repair tách khỏi data-only contrasts. Reject/no-gain giữ evidence và parent. R/R+S và R_common/R_common+H kiểm sources; không đưa targeted corrections không kiểm soát vào source comparison. Kết thúc development mới freeze/final; final không làm acquisition signal cho claim đó. Nếu round sau dùng final cũ thì chuyển nó sang development và tạo final mới.

Đây là secondary experiment sau native/source feasibility, không claim của R vs R+S. Cùng catalog các lỗi có reference review labels, cùng khả năng can thiệp và compute/source cap; so engineer workflow thông thường với trace/cards/templates của đội. Đo time-to-accepted-plan/total debugging work, interventions đúng scope, unknown retained, full-task gain và no-gain. Engineer expertise/case familiarity là confounds cần controls; làm thêm experiment thì tính thêm cost. Không chạy thí nghiệm này trước khi có native failures và cards thật.

## Kiểm mở rộng

Task2 đầu tiên trên cùng robot và physics: thay một rigid object hoặc target layout trong phạm vi đã chốt. Liệt kê modules/artifacts reused, dataset/normalization changes, scorer/controller changes, engineer/operator/GPU cost và acceptance mới. Chỉ thêm scenario trong cùng distribution là robustness coverage, không tự task2. Task2 cần định nghĩa task khác và heldout riêng. Robot2 sau task2, với binding/acceptance riêng.

## Gates trước khi hứa kết quả

| Gate | Chặn khi |
|---|---|
| Task/owner | Tolerances/domain/quality/cycle chưa chốt hoặc expert replay không feasible |
| Native | Loader/gradient/reload/controller/scorer chưa có receipts |
| S/H eligibility | Labels/rights/geometry/profile/action semantics hoặc route chưa đạt |
| Development | No useful gain, regression, cost quá cap hoặc decision còn unknown |
| Final | Quality/coverage/regression/cycle không đạt, leakage hoặc analysis đổi sau xem outcome |
| Savings | Important costs còn unknown, comparator chưa đạt quality hoặc setup allocation không nhất quán |

Thứ tự triển khai giữ thesis v3.1: task/native baseline → source pilot → development recipe → fixed study/final → bundle. Kết quả có thể saving/no-saving/no-transfer; không đổi mục tiêu để giữ câu chuyện thắng.

## Operating characteristics và secondary workflow design

[Contract05](05-data-decision-and-run-contracts.md) chốt các trường cần có: planning power/estimand, paired case allocation/counterbalancing, selection receipts và measured RunPlan. Gate n100/X≥96 có P(pass|p=.95)≈43,6% dưới IID; owner chốt trade-off trước final. Đây là tính toán planning, không kết quả robot.
