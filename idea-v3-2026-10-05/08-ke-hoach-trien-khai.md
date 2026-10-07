# 08 · Kế hoạch theo artifacts và gates

| Bước | Công việc | Output | Gate/owner |
|---|---|---|---|
| P0 | Khóa task/domain/action/rights/resources | TaskSpec, BindingManifest, source audit | Engineer + task owner |
| P1 | Native loader/head/normalization/controller/scorer | Batch/gradient/reload receipt + closed-loop trace | Đúng command và response, useful parent |
| P2-S | Native seed trajectory transform và execute | Sim release, rejects, QA/effort | Positive demos/profile/scorer đúng |
| Optional H | Audit human geometry + chọn một route | Human release + loss/param manifest | Valid targets, gradients, native regression |
| P3 | Input/features/action/runtime recorder | EvidenceTrace/Card, overhead/parity | Không biến missing thành pass/cause |
| P4 | Development source pilots | R/S, H khi eligible, HS khi có lý do | Same robot budget, all source/compute cost |
| P5 | Preregister contrasts/controls/resources | RunPlan có seeds/budgets/jobs | Owner duyệt cap và statistical question |
| P6 | Freeze → independent final | SkillBundle + QualityCostReport | No local-only promotion, native scope đúng |

Không mở platform multi-user/distributed trainer riêng hoặc world-video/RL/full-body/dexterous branch trước gates. FluxVLA capabilities phải kiểm selected config, không mặc định mọi LoRA/RTC/accelerated path compatible.

## Lịch planning có điều kiện

Dự kiến8–12tuần sau đủ người/GPU/checkpoint/task owner. Bốn chặng2–3tuần: native feasibility/baseline → release/sim generation/QA → development contrasts/decision receipts → freeze/final/report. Các việc có thể chồng lấp; gate fail thì repair/rescope/replan, không lịch cam kết. H/video và secondary workflow comparison có lịch/cap riêng sau native/source feasibility; robot thật là phase riêng.

## Example hiện chạy để kiểm plumbing

`python examples/engineering-loop/run.py`; `python -m pytest -q examples/engineering-loop/test_pipeline.py` từ repo root. Reference physics/dataset/training/reload/scoring/gates chạy CPU. Website đọc artifacts đã ghi; replay không chạy backend ML trong browser. Case R/S/C, binding fault, unknown scorer và zero skill có actual traces.

## Bàn giao native sau P6

Checkpoint+hashes, dataset releases/lineage/rights, normalization/controller/camera profile, trainer/optimizer/config/environment versions, scores/all trials+uncertainty/regressions, cost ledger và SOP. Chưa các artifact này thì native not-tested/integration prototype. Real-cell acceptance cần domain/sensors/physics/operator và quality/cycle riêng.

## Khi pipeline không chạy

Contract fail → không training/deploy. Native inference fail → sửa E0/re-pin. No basic skill → expert seed/curriculum trong cap, thêm jobs/cost. Source branch fail → report not-integrated, tiếp tục source eligible với claim thu hẹp. Final fail → no promote; round mới fresh final. Không tăng complexity để che thiếu baseline.
