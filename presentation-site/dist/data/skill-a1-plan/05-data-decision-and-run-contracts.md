# 05 · Hợp đồng quyết định dữ liệu và RunPlan

Đề xuất cập nhật 07/10/2026. Các templates là contract để triển khai và thu receipts; chưa có native backend, selector tự động hoặc measurements A1.

## Chọn dữ liệu rồi đo utility

[AcquisitionDecisionReceipt](acquisition-decision.template.json) nối parent/task/profile/scorer → failure bucket/facts/alternatives → supervision cần → những lựa chọn khả thi và cost → selection rule/reviewer → release/candidate → development gain/regression/uncertainty/actual effort → quyết định vòng sau. Retrieval thêm query/candidate pool/selected IDs. Similarity, QA pass và train loss không tự là downstream utility.

Secondary workflow study sau native/source feasibility: phân bổ K parent–case pairs chưa được người tham gia xem trước; workflow thường và evidence workflow có cùng intervention access/source/compute cap. Counterbalance case/order hoặc dùng case chưa từng thấy cho mỗi người; ghi expertise và familiarity. Tối thiểu 2K intervention/train/eval paths ngoài baseline chung, tính cả selection/debug time. So gain, regression và tổng công tới acceptance; nếu hai workflow cùng chọn/cùng công thì ghi chưa có added value. Final độc lập không cấp đáp án cho selection.

## Release QA, coverage và content identity

[ReleaseQualityReceipt](release-quality.template.json) ghi requested/attempted/accepted/rejected theo object, pose/target, appearance, reachability/contact và failure bucket. Ghi unique parents, reject reasons/cost, sampling weights và khoảng trống còn lại. Không bỏ QA để đủ quota. Generator không đạt một bucket quan trọng thì defer, dùng expert correction hoặc thu hẹp domain có khai báo.

Canonicalize repository/revision/recording/episode/time range; exact hash raw content và duplicate-family IDs cho mirror/crop/re-encode. Near-duplicate retrieval chỉ đề xuất pairs để review khi corpus cần; similarity không tự là duplicate. Split connected components của root/ancestor/duplicate/session graph trước derivatives; audit prohibited overlap và ghi pretraining overlap chưa quan sát được.

Kiểm trước nhập corpus: cùng recording dưới ID khác, clip con, re-encode và derivative phải chung group hoặc quarantine; đổi tên scene không xóa overlap. Đây là yêu cầu native ingest, chưa được reference validator tự động thực hiện.

## RunPlan từ measurements

[RunPlan](run-plan.template.json) cần hashes/config, trainable modules, batch/dtype/horizon/views, measured peak VRAM/throughput, steps/repeats/seeds, GPU type/count/wall-hours, source generation attempts/yield/QA, eval/reset, engineer/operator work, CPU/storage và retry contingencies. Null là chưa đo, khác measured0.

Native feasibility gồm loader/batch, update/reload và bounded development closed-loop; generation batch đo yield/QA. Dùng measurements lập job set R/R+S tối thiểu trong cap. H, action-free và workflow experiment có jobs/caps riêng. Cap hết → stop/defer/replan; không nhận 180 A100 GPU-hours đủ chỉ vì có subtotal tiền.

## FOCA candidate: task-negative contract

[FOCA v1 §3.3 Eq. (10)–(11)](https://arxiv.org/html/2606.20867v1) dùng negatives từ task descriptions khác. A1 đơn task phải khai semantic task IDs, train-only pool/revision, sampling/minimum eligible negatives và zero-negative handling. Nếu eligible negatives rỗng, nguyên InfoNCE chỉ có positive cho loss0. Reject/skip có receipt hoặc dùng pool hợp lệ; paraphrase cùng instruction không tạo nhiều semantic tasks.

Nếu đổi objective/negative semantics cho single-task, ghi adaptation và kiểm collapse/false negatives. Future target encoder frozen không đồng nghĩa source representation frozen. Trước training lớn: single-task/multitask batches, negative counts, loss/source–target gradients; sau đó matched action-only vs action+implicit, downstream control và extra cost. Không dùng warning upstream `main` chưa pin để nhận A1 runtime failure.

## Final operating characteristics

Draft n=100, q_min=.90, exact one-sided95% lower bound≥.90 cần X≥96 dưới IID Bernoulli. Tính toán planning: P(pass | p=.95)≈.4359813; P(pass | p=.97)≈.8178548. Không phải hiệu năng đo được. Owner chốt power/trade-off, sampling/strata, seed estimand và total rollout/reset cost trước final. Nếu sampling không IID, dùng analysis phù hợp thay vì áp bound tổng cho mọi condition. Source advantage/equivalence cần paired effect/margin/power riêng; cùng pass chưa là equivalent.

[Recipe](02-recipes-and-data.md) · [Protocol/cost](04-evaluation-and-cost.md) · [Native task](01-native-task.md).
