# 06 · Chi phí và nguồn lực

_Snapshot kỹ thuật từ [hồ sơ engineering](../idea-v3-2026-10-05/06-chi-phi-va-kha-thi.md); [IDEA.md](../IDEA.md) là bản trình bày gửi đánh giá, recipe mới nhất ở docs/implementation-plan/skill-a1._
## Pilot hiện hành: capacity budget, chưa forecast

Subtotal phần đã tính **5.187,20 USD**: capture/reset40; QA40; integration/preparation/report4.800; cap180 A100 GPUh×1,59=286,20; storage21. Inputs:20 accepted roots/yield50%=40 attempts,6 phút capture/reset,3 phút QA,240 engineer-h. Đơn giá/giờ/yield là giả định; giá GPU/storage tham khảo kiểm06/10/2026. Chưa robot/cell, CPU riêng, data/license fees, thuế/downtime/production; không saving. Website dùng `content/overview-flywheel.json` cho cùng subtotal trên overview/business.

[RunPlan cần measurements](../idea-v3-2026-10-05/../docs/implementation-plan/skill-a1/run-plan.template.json) · [Contract quyết định/coverage/resource](../idea-v3-2026-10-05/../docs/implementation-plan/skill-a1/05-data-decision-and-run-contracts.md). Job set R/R+S, seeds/repeats/eval/retries và công người cần chốt từ pilot, không suy từ cap.

## Total cost

Human acquisition/license/tracking/geometry/QA + robot capture/calibration/reset/corrections + sim assets/controller/generation/rejects + bridge/target training/retries + evidence/probes/evaluation + storage/reporting + allocated setup. Cùng quality mới so saving.

Unique activity ID và scope: source acquisition / study R&D / per-skill / production. Không cộng subtotal chứa cùng engineer time. Sponsored GPU/operator vẫn economic usage; cash riêng. Blank/unknown khác measured0. Parents/variants không inflate independent robot samples.

## Hiện đo được gì?

Reference ghi train loss, recording counts, independent roots, checkpoint hashes/reload parity, generation yield, all outcomes và wall time. Không measured operator/engineer/robot-real costs, không hardware quotes hoặc human license cost; saving vẫn not_established. Python wall time là thời gian chương trình, không engineer-hours.

Môi trường lần kiểm: Torch2.10/CUDA runtime installed nhưng cuda.is_available=False, MuJoCo3.5 CPU chạy, chưa checkpoint/native stack. Không suy model không thể chạy ở máy khác; cần config/VRAM/inference benchmark và actual weights.

## Resource gate native

Code/checkpoint/rights + loader/action/controller/scorer → one-batch memory/time → learned closed-loop → source labels/gradients + generation effort/yield → estimate GPU/engineer/operator/eval/storage → resource cap trước grid. Một người12tuần×40h không chứng minh đủ bridge+generator+study. V3.1 không hứa calendar/job budget chưa benchmark.

## Kinh tế lịch sử

Stress model v2 400→280robot roots cho 9.315,89→16.359,98USD trong giả định cũ: giảm collection nhưng total tăng. Không estimate v3.1, không đổi inputs để tạo savings đẹp. Website giữ tham khảo historical, bảng chính chưa có monetary result.

## Điều kiện dừng

Sources xử lý/generation/bridge đắt hơn collection tránh được; native path chưa usable; labels/rights không đủ; no transfer/regression; resource cap hết. Ghi receipts/no-gain/unknown và thu hẹp claim. Real commercial claim cần task owner, cycle/downtime/quality và rights/hardware riêng.
