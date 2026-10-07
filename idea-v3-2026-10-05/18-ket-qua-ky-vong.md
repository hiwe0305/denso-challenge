# 18 · Kết quả kỳ vọng và tiêu chuẩn bàn giao

Ưu tiên triển khai 07/10/2026: **Ước lượng 30 ngày phát triển MVP sản phẩm đầu-cuối**, gồm Data Core, engine jobs/checkpoints, eval/inference và feedback data. Một task là test case; model học task/robot inference kiểm tính khả thi khi hardware gate đạt. Một vòng dữ liệu từ lỗi tới release/candidate và before/after. Native training, robot thật, human transfer và savings chưa đo. [Lịch/bốn pipeline/gates hiện hành](08-ke-hoach-trien-khai.md). Thiết kế A1/source studies mở rộng giữ ở phụ lục, chưa bắt buộc trong tháng đầu. Dự kiến bốn đầu ra:

| Bàn giao | Nội dung | Acceptance |
|---|---|---|
| Policy/SkillBundle một task | Checkpoint, processor/stats, task/profile/controller/camera, code/config hashes, update/reload receipts | Learned closed-loop natural starts; full-task, regression và cycle theo owner/protocol đã khóa |
| Dataset releases | Nguồn, targets/masks/timebase, provenance, roots/duplicate groups/splits và QA/coverage | Sample→batch đúng semantics; no prohibited overlap; requested/attempted/accepted gaps công khai |
| Trace/scorer/decision receipts | Observation→action→command→response→outcome; facts/hypotheses/alternatives/decision | Giữ failure/unknown/timeout/intervention/no-gain; không auto-cause; temporal/binding checks đúng |
| QualityCostReport | PoC baseline/candidate, full-task và total work. Source/workflow controls và skill2 reuse kiểm sau PoC | Cùng quality mới so saving; source effect và workflow selection effect có comparator riêng |

## Bằng chứng hiện có

Reference nhỏ thực thi trong MuJoCo, idealized state, scripted sequencer và linear predictor35×4: final R0/12, S12/12, C0/12. C local pass nhưng final fail, không promote. Đây là engineering evidence, chưa visual/native/contact-valid GR1 hay tiết kiệm.

[Claim ledger và receipts](12-bang-kiem-chung.md) · [A1 protocol](../docs/implementation-plan/skill-a1/04-evaluation-and-cost.md) · [Decision/coverage/RunPlan contracts](../docs/implementation-plan/skill-a1/05-data-decision-and-run-contracts.md).

## Điều kiện tiếp tục

Native feasibility và useful robot-only baseline trước source studies. Không đạt gate thì repair/rescope/defer với receipt. H/video là optional, không là điều kiện bắt buộc của MVP R+S. Robot thật là đích PoC có hardware gate riêng; production cần nghiệm thu mở rộng. Bộ hồ sơ nộp phải đồng bộ scope/budget/timeline/status; form Markdown và PowerPoint đã đồng bộ ngày 07/10/2026. PowerPoint hiện hành gồm 24 slide, dưới 15MB. Bổ sung tên đội/thành viên. Robot/task/lịch tiếp cận chưa được BTC xác nhận ghi pending, không chờ thiết bị mới nộp ý tưởng.
