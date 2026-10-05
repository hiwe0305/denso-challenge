# 05 · Contracts, data model và invariants

_Contracts đề xuất của platform, chưa API triển khai của đội hoặc upstream._

Common fields: id, schema_version, workspace_id, immutable_hash, created_at, owner, refs. Unknown evidence không pass, credentials không vào artifacts.

| Object | Required semantics |
|---|---|
| SourceRecord | origin/actor/viewpoint/embodiment/signals/confidence/domain/modalities/provider/rights/retention/session/raw hash và acquisition costs |
| CanonicalEpisode | measured/inferred/generated/missing signals, frame/time/units, command-vs-response, roots/parents/processing/outcome |
| DatasetRelease | Immutable views/splits/hashes, QA/quarantine, loader readback và cost refs |
| RecipeProfile | FluxVLA/model/weights/loader/objective revisions, human learning vs robot adaptation stages, required signals/masks, action/camera/normalization, source mix and compute |
| ExperimentPlan | Estimand, control/treatment, changed/held variables, budget/seed/trial/scorer/split protocol và confounds |
| TaskProfile / ConditionReport | Object/target region, timeout/stability/scorer, active/locked joints, ID/OOD/development domain, denominators/uncertainty và health checks |
| AcquisitionPackage / AcquisitionPlan | Source/condition/rights/objectives/roots, reuse/new, estimated range/actual cost; shared R0 parent, eligible catalog, T expert-targeted teleop / F fixed mixture / A condition-cost arms, cap/tolerance, training protocol và forbidden final-test refs |
| RunReceipt | Stages thực chạy, data/recipe/env/hardware/checkpoint refs, logs/status/person/GPU cost |
| EvaluationReceipt | Sim/real domain, binding/scenarios/scorer, trials/seeds/traces/outcomes/uncertainty/limits |
| TransferReport | Success-vs-demo comparisons, human/pretraining history, savings threshold, cost completeness and conclusions allowed |
| DatasetValueCard | Conditional source/cohort/model/task/domain/budget comparison, measured effect/uncertainty/not-tested |
| BottleneckCase/DecisionReceipt | Signals/hypotheses/controlled change/reviewer, actual run/outcome gain/no-gain/inconclusive |
| InterventionPlan | health-check status, repair/collect/reuse/augment/defer/stop, reason, reviewer; repairs ngoài E4 data contrast, version/baseline reset và unknown expected utility |
| BudgetLedger / SkillAcceptance | R&D-sim/skill-repeat/production-real scope, estimated/measured/unknown, unique activity/allocation refs, engineer/robot/elapsed hours; cycle p50/p95, interventions/recovery/good outputs và owner thresholds |
| InferenceBundle/DeploymentBinding | Weights/normalization/action/camera/controller/calibration, active/locked joints, domain/limits/deadline/stop/rollback/acceptance |

## Invariants

1. Shared root/derivatives giữ lineage/rights và cùng split. Final-test evidence không dùng làm training/tuning/acquisition cho cùng acceptance round.
2. Human approval không đổi inferred label thành measured action. Video-only không tự đáp ứng robot-action supervision.
3. Issued command và measured response tách. Candidate trajectory/qpos playback/predicted future không là controller-executed demo.
4. Source quality/value phụ thuộc recipe/task/budget. Unlike-model contrast ghi confound, không gọi nhân quả human data.
5. Unique roots/training seeds/trials riêng; nhiều frames/variants không giả independent samples. Missing/negative results giữ lại.
6. Sim, real và model prediction giữ domain riêng. Scorer/binding/version đổi phải đánh giá lại acceptance.
7. Candidate checkpoint không auto promote. Release/run immutable; retry idempotent; rollback matching controller/normalization.
8. Cost ghi cả sponsored resources theo usage/giá giả định hoặc chưa biết; không coi tài trợ làm mất chi phí kinh tế.
9. Binding/controller repair không trộn vào E4 data-only treatment. Re-pin baseline/plan khi binding/scorer đổi. T/F/A cùng parent, catalog/cap/train protocol; final refs bị chặn.
10. Nguồn không đủ tín hiệu/quyền/cap bị loại trước chọn. Unknown utility/cost không trở thành measured zero hoặc auto promote. Không claim algorithmic novelty hay tiết kiệm từ rules/template.
11. Một activity không double-count trong cùng budget scope. R&D train runs đã tính không cộng lại như per-skill runs. Cost incomplete hoặc same-quality chưa kiểm thì chưa claim net saving. Core run grid 6 baseline +9 T/F/A=15, theo protocol revision 05/10.

[Architecture](02-system-architecture.md) · [Evaluation](06-validation-and-roadmap.md).

SignalValidity: raw_value, normalized_value/null, evidence_kind, mask, confidence, units/frame, timing/processor refs. Public numeric preview có sample hash và acquisition provenance; paper media có source page và evidence domain.
