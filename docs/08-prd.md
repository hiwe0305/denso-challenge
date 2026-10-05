# 08 · Product Requirements Document

_05/10/2026 · Specification sau review; chưa backend ML đã triển khai._

## Goal và workflow

Công cụ giúp đội AI/robotics chuẩn bị dữ liệu, huấn luyện và đánh giá kỹ năng humanoid, hướng tới giảm tổng công ở cùng chất lượng. Tầm nhìn là workbench dùng lại; MVP là công cụ chạy và báo cáo một kỹ năng GR1 gắp–đặt trong mô phỏng. Video người bổ sung tín hiệu trình tự/chuyển động hợp lệ; mẫu robot giữ vai trò dạy hành động robot đích.

Workflow: định nghĩa tác vụ → chuẩn bị và kiểm dữ liệu → huấn luyện → đọc chất lượng/tổng công → bổ sung dữ liệu phù hợp → đánh giá lại và bàn giao. Task owner xác nhận workflow hiện tại, tần suất đổi task/SKU, quality/cycle-time và automation/arm comparator. Engineer kiểm health; sửa binding/calibration/controller trước và pin baseline lại. Sau đó chọn gói acquisition/reuse/augmentation từ catalog đủ quyền/tín hiệu/chi phí và so T/F/A từ cùng R0. Product/Learning Core sở hữu task/model/fallback; PRD sở hữu chức năng và acceptance phần mềm.

## Requirements và acceptance

| Priority | Chức năng | Acceptance phần mềm |
|---|---|---|
| Must | Stage contracts/evidence | Entry/exit/readiness/version; pass/fail/not_attempted/unknown, entered/known/unknown/reach/retry, verifier review |
| Must | Diagnostic probes | Natural/restaged paired entry, hypothesis/held variables/uncertainty, reviewer/reset/cost refs |
| Must | Bootstrap/stop | 0 task success khác no basic skill; expert seed/curriculum/cap, useful parent hoặc rescope/stop |
| Must | Targeted training/regression | Correction authority/context/chunk targets + prior replay, pin params/schedule; local/transition/global checks |
| Must | Task/binding/health | Joints/frame/units/camera/timing/scorer đủ; health fail chặn data claim; repair tạo baseline version mới |
| Must | Robot baseline / FluxVLA | Loader/loss/gradient/save-reload/closed-loop selected path, pinned refs; playback không là learned rollout |
| Must | Rights/signals/QA/lineage | Root/session/parents, masks và measured/inferred/generated/missing; split trước derivatives; unknown rights quarantine |
| Must | Catalog và InterventionPlan | Eligible packages/reuse/new, condition hypothesis, estimated cost range hoặc unknown; engineer duyệt; cho phép defer/no-change |
| Must | Controlled acquisition | T expert teleop, F prereg fixed mixture, A condition/cost; chung parent R0/catalog/scorer/training/caps; giữ no-gain |
| Must | BudgetLedger và report | Acquisition và total incremental scopes, hours/receipts/activity IDs; blanks unknown; tính selection/QA/reject/retry và tránh double-count |
| Must | Core experiments | E0/D0 và E1 tạo useful parent trước E4; core conditional6 baseline +9 T/F/A; extra jobs replan; ít nhất hai cách học thực sự chạy trong report; alternative augmentation hợp lệ nếu branch fail |
| Must | Sim demo/SOP/bundle | Learned closed-loop checkpoint/config/normalizer/binding/scorer + SOP bốn nguồn có gate, final ID/OOD và cost report |
| Conditional | Human/internet objectives | Rights/task relevance/QA/masks + từng loss/gradient/reload qua E0; không giả action; branch fail disabled/not-integrated |
| Conditional | Cosmos appearance | Basic augmentation trước; hypothesis/control maps/semantics/cost gate; downstream contrast mới nhận model-generated gain |
| Could | Physics/world model | Fidelity/controller/scorer/labels gate, separate cost và scope; không bắt core dùng |
| Could | Real inference/multi-task | Controller/latency/stop/recovery/real acceptance riêng; task thứ hai đo công đổi scorer/data |
| Won't | Foundation training, marketplace, autonomous diagnosis | Ngoài critical path 12 tuần |

## User stories và business rules

Data engineer biết sample vào objective nào: validity/mask/quyền/root readback; không zero-fill missing action. ML engineer khóa init/parent/budget/seed/scorer trước, test không chọn checkpoint. Integration engineer tách command/response và policy error khỏi binding. Lead xem engineering/operator/robot/GPU-hours và elapsed time tới accepted quality, missing costs hiện rõ.

Engineer chọn can thiệp: condition report có denominator/uncertainty và health record; package có eligible signals/rights/cost range; DecisionReceipt giữ lựa chọn, alternatives và no-gain/inconclusive. A được chọn giống T; điều đó chưa chứng minh ưu thế. Repair ngoài E4; trong E4 binding cố định. F không cố ý lấy gói vô ích. Final holdout không quay lại train trong cùng vòng.

Software pass khi plans/receipts tái lập, kể cả kết quả âm. Product-value claim chỉ pass khi quality/cost contrast đủ evidence. PoC targets75%/30%/OOD70% chưa production thresholds.

## UX, integrations và NFR

CLI + tracker + report trước; screens task/data/release/run/eval/intervention sau gate. Report hiện domain/versions/not-measured/uncertainty trước narrative. Website hiện là hồ sơ giải thích, chưa workflow backend hoạt động.

Integrations: một FluxVLA path, pinned LeRobot loader, simulator/tracker/storage, robot SDK khi có. Jobs persisted/resumable/cancellable; idempotent import, refs reproducible, quotas/peak VRAM, credentials không trong artifacts. Metadata query p95≤2s ở10k episodes là target cần load-test, không benchmark đã đạt. Auth/isolation/audit/backup theo TDD khi pilot có nhu cầu.

Reliability report: cycle p50/p95, interventions/1000 cycles, recovery minutes, accepted outputs/hour, same domain/trial denominator. Real production gates cần task owner/cell acceptance riêng.

[Product](01-product.md) · [TDD](02-system-architecture.md) · [Contracts](05-contracts.md) · [Protocol](06-validation-and-roadmap.md).

## Acceptance chống quyết định sai

Với early fail, bước sau hiển thị chưa thử; unknown verifier không auto label. Với failure sau gắp, report đề xuất test readiness/entry trước khẳng định cần train chuyển. Với 0 full-task success nhưng local pass, route bottleneck; với no basic skill route bootstrap/rescope. Correction action thiếu thì chặn native imitation targets. Local success nhưng full-task/regression giảm thì không promote. Stage definitions/scorer/binding đổi tạo plan version mới.

Ví dụ website là dữ liệu kịch bản có nhãn nguồn; không upload/run robot backend. [Task improvement](14-task-improvement.md) sở hữu semantics; [audit](reviews/full-idea-audit-2026-10-05.md) ghi status chưa validated.
