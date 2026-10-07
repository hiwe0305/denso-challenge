# 07 · Đánh giá, anchors và quyết định v3.1

**05/10/2026.** Review design v3/v3.1 và executable reference. Source mechanism checks không scientific reproduction. Reference tests không transfer architecture correctness sang native GR1.

## Nhận định

Giữ thesis human/synthetic data efficiency và vòng cải thiện task. V3 trước đã chọn shared motor bridge/prefix/grid quá sớm; đây là decision risk, không demonstrated ML defect. V3.1 bổ sung contracts và executed reference, hạ choices chưa có support về hypotheses. Native integration/cost/human vẫn open.

| Finding/anchor | Premise → scoped conclusion | Alternative / discriminating check |
|---|---|---|
| F1 H→TRAIN | Human wrist khác robot action; shared DiT mới chỉ proposed → chưa chốt route | Auxiliary đủ hay adapter motor tốt hơn? Labels/gradient + R/H rollout/compute controls |
| F2 S→QA | Reference seed transforms execute nhưng controller/grasp khác GR1 → chưa native generator proof | Native seed replay/positive QA/yield; basic augmentation có thể rẻ hơn |
| F3 VLM→IFACE→ACT | Reference idealized state không VLM; numerical trace chưa semantic/causal evidence | Native feature exposure/debug parity + annotated probes, alternatives/controller controls |
| F4 ACT→EXEC | Reference4D và native29D khác semantics; optimized inference/debug paths khác | Native mapping/normalization/scheduler traces; wrong binding negative case |
| F5 QA/STUDY→SCORE | 12 reference trials/domain hẹp, privileged reference sensing → chưa visual/hardware generalization | Native independent split/natural rollout; real acceptance riêng |
| F6 TRAIN→COST | Generation count và local gain chưa total-cost saving | Actual activity ledger at same quality; compute/source confounds |
| F7 TASK/R | Rigid one-hand proxy và weld chưa factory/contact tasks | Owner/use-case assessment, contact-valid robot trials |
| F8 STUDY |27jobs dựa unverified prefix/reuse/resources → chưa commitment | Choose validated recipe, benchmark, then preregister actual grid |

Reference demonstrated behaviors: reject bad profile/human-as-robot/final leakage; executed object motion; reload parity; unknown/not_attempted; correction local pass/final fail blocks promotion. Scope hẹp; không nhận findings native đã được giải.

## Decision log

| ID | Giữ/sửa | Trigger/impact |
|---|---|---|
| D1 | Giữ mục tiêu same-quality data/cost | Theo user; chưa savings |
| D2 | Giữ engineer review/evidence | Không auto diagnosis/update |
| D3 | Giữ native FluxVLA/N1.5/GR1 | Compatibility và profile chưa tested |
| D4 | Sửa “shared human motor trunk đã chốt” thành candidate | Data/labels/module route/schedule cần pilot; không bắt prefix |
| D5 | Giữ executed synthetic để có action trace | Native generator conditional; reference weld không gripper proof |
| D6 | Giữ source comparisons trước acquisition selector | R/S eligibility trước H/HS full grid; T/F/A historical |
| D7 | Bỏ cam kết 27jobs/12tuần chưa benchmark | ActualRunPlan tính all costs/jobs sau recipes |
| D8 | Bổ sung executed reference + strict claim boundary | S/C alternatives; C not promoted despite local gain |

Đổi task/model/robot/action schema/scorer/splits phải ghi receipt: trigger/evidence, changed/held parts, budget/comparators/claim/final impacts, reviewer. Không âm thầm coi reference thành native hoặc đổi source definitions để giữ claim thắng.
