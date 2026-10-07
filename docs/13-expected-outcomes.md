# 18 · Kết quả kỳ vọng và tiêu chuẩn bàn giao

_Snapshot kỹ thuật từ [hồ sơ engineering](../idea-v3-2026-10-05/18-ket-qua-ky-vong.md); [IDEA.md](../IDEA.md) là bản trình bày gửi đánh giá, recipe mới nhất ở docs/implementation-plan/skill-a1._
Phạm vi MVP đề xuất: GR1 gắp–đặt A1 trong mô phỏng. Native VLA, human transfer và savings chưa được đo. Dự kiến bốn đầu ra:

| Bàn giao | Nội dung | Acceptance |
|---|---|---|
| Policy/SkillBundle A1 | Checkpoint, processor/stats, task/profile/controller/camera, code/config hashes, update/reload receipts | Learned closed-loop natural starts; full-task, regression và cycle theo owner/protocol đã khóa |
| Dataset releases | Nguồn, targets/masks/timebase, provenance, roots/duplicate groups/splits và QA/coverage | Sample→batch đúng semantics; no prohibited overlap; requested/attempted/accepted gaps công khai |
| Trace/scorer/decision receipts | Observation→action→command→response→outcome; facts/hypotheses/alternatives/decision | Giữ failure/unknown/timeout/intervention/no-gain; không auto-cause; temporal/binding checks đúng |
| QualityCostReport | R/R+S pilot, total work tới quality threshold, setup/recurring và skill2 reuse | Cùng quality mới so saving; source effect và workflow selection effect có comparator riêng |

## Bằng chứng hiện có

Reference nhỏ thực thi trong MuJoCo, idealized state, scripted sequencer và linear predictor35×4: final R0/12, S12/12, C0/12. C local pass nhưng final fail, không promote. Đây là engineering evidence, chưa visual/native/contact-valid GR1 hay tiết kiệm.

[Claim ledger và receipts](../idea-v3-2026-10-05/12-bang-kiem-chung.md) · [A1 protocol](../idea-v3-2026-10-05/../docs/implementation-plan/skill-a1/04-evaluation-and-cost.md) · [Decision/coverage/RunPlan contracts](../idea-v3-2026-10-05/../docs/implementation-plan/skill-a1/05-data-decision-and-run-contracts.md).

## Điều kiện tiếp tục

Native feasibility và useful robot-only baseline trước source studies. Không đạt gate thì repair/rescope/defer với receipt. H/video là optional, không là điều kiện bắt buộc của MVP R+S. Robot thật/production cần acceptance phase riêng. Bộ hồ sơ nộp phải đồng bộ scope/budget/timeline/status; form Markdown và PowerPoint đã đồng bộ ngày 07/10/2026. PowerPoint hiện hành gồm 21 slide, dưới 15MB. Tên đội, thành viên và task owner còn cần bổ sung trước nộp.
