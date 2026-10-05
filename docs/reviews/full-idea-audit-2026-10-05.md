# Rà soát toàn idea · task-improvement revision 2

_05/10/2026. Điểm xuất phát: Git `d82725c9c211c0d4d5420447bb15d9b94325ab52`. Phạm vi: Product, TDD, Data/Learning Core, contracts, protocol, PRD, SOP, cost models, nguồn phương pháp, pitch và 12 trang website. Bản sửa là đặc tả/website, chưa tái lập ML hoặc verifier robot. Review/score cũ được giữ làm lịch sử, không là đánh giá sau sửa._

## Kết luận

Idea có mục tiêu/người dùng, robot-action baseline, source eligibility và T/F/A controls hợp lý ở mức đề xuất. Nhưng đóng góp chọn can thiệp chưa được mô tả đủ từ failure evidence đến kế hoạch thu và học. Gọi đây là chỉ thiếu hình trình bày sẽ bỏ sót khoảng trống cốt lõi. Revision 2 bổ sung task contracts, stage evidence, diagnosis probes, cold-start, targeted training/regression và ledger; các lợi ích vẫn cần thử nghiệm.

## Bản đồ phạm vi và nguồn

Graph `task-improvement/improvement-v2` là kiến trúc đề xuất riêng tại [docs14](../14-task-improvement.md), không Figure 1 của paper. Node IDs TASK/RUNTIME/TRACE/STAGE/HEALTH/REPAIR/PROBE/SELECT/BOOT/DATA/TRAIN/CHECK/FREEZE/FINAL/BUNDLE/COST/STATUS. Graph chia thực thi, phát triển và nghiệm thu. JSON audit cùng tên ghi anchors, reasoning và nguồn. Không có benchmark tác giả được tái lập trong audit.

| ID / vị trí | Tiền đề quan sát ở bản d82725c → kết luận có phạm vi | Sửa, chi phí và phép kiểm còn cần |
|---|---|---|
| G1 · TASK→STAGE | Docs01 có chuỗi bước/final success; docs05 có ConditionReport nhưng chưa contract entry/exit, unknown/not_attempted. Không đủ phân biệt bước fail với chưa tới. Đây là **missing specification**, không chứng minh scorer sai. | SubtaskSpec/StageAttempt và denominators/coverage. Thêm công annotation/verifier. Chấm traces do người review; never-reached không thành fail, retries vẫn tính. Nếu scorer thật đã có semantics này thì thiếu được thu hẹp về hồ sơ, cần implementation refs. |
| G2 · PROBE | Docs04 có health/hypothesis, chưa đối chiếu natural/restaged entry để phát hiện lỗi bước trước. Lỗi ở chuyển không tự chỉ ra cần train chuyển. **Design risk/missing protocol**. | Paired stage/transition probes, log entry distribution và uncertainty. Cost reset/setup. Thử gắp sai khiến chuyển rơi; kiểm canonical-grasp control và whole-task. Probe bias còn có thể tồn tại nên không claim causal certainty. |
| G3 · SELECT→DATA | Catalog/eligibility/cap đã có; plan chưa target stage, context/chunk windows hoặc action-authority during correction. **Missing specification** ở interface collection. | AcquisitionPlan chi tiết; correction gần policy-induced states, QA discontinuity. Tính collection/QA/reject. Loader/window tests và downstream comparison; dữ liệu thêm có thể không giúp. |
| G4 · BOOT | R0/E0/fallback đã có, chưa tách zero complete-task success khỏi no basic skill/never-reached. **Missing cold-start policy**. | Bootstrap robot experts/curriculum, useful-parent gate hoặc rescope/stop. Extra jobs phải replan; không bảo đảm learnability. Thử fixtures 0 full-task có local pass và 0 basic; sau đó learned rollout thật để xác nhận. |
| G5 · TRAIN | Docs04 đã có native action loss, trainable params gate; chưa replay/regression gắn targeted correction. Shared weights không có một neuron set riêng cho mỗi bước. **Robustness risk**. | Mix prior/correction, valid horizon/masks, E0 manifest, regression các bước/conditions tốt. Extra train/eval cost. Downstream local và global comparison; adapter/freeze chưa bảo đảm không quên. |
| G6 · CHECK→FINAL | Protocol đã có split/final/cost controls; chưa local/transition/reach metrics và verifier-validation gate. **Missing evaluation coverage**. | D0 trước E4, whole-task từ natural starts, unknown coverage, regression. Chấm local tốt mà end-to-end fail để kiểm không promote. Privileged sim state không thành real verifier hoặc policy input. |
| G7 · COST | Ledger gốc tính reset/QA/retry/selection; hours cho scorer/probe/bootstrap chưa có fields/scope rõ. Không được coi mô hình full-source gốc là total đủ của thiết kế mới. **Resource feasibility unknown**. | Stage/probe/reset/annotation/bootstrap ledger và planning inputs chưa đo; shared setup tránh double-count. Cap/RunPlan mới nếu extra jobs. Audit activity IDs và matched T/F/A cost; giá trị có thể no-advantage. |
| G8 · STATUS/BUNDLE | Website là pitch/scripted 3D; chưa robot ML integration. Old score có thể khiến người đọc tưởng design đã đủ. **Unresolved evidence**, không lỗi 3D renderer. | Hiện implementation/evidence boundary và audit hiện hành; không tăng điểm chỉ vì viết docs. Website examples/fixtures pass chỉ chứng minh nội dung/logic demo; E0/D0/E1/E4/final mới kiểm skill và benefit. |

Mỗi finding được sửa ở mức **đặc tả revision 2**; scientific resolution vẫn `not_validated`. Expected benefit là giảm chọn sai nơi thu và giảm lặp lại bước tốt; added costs/new risks gồm verifier sai, staged-entry bias, correction discontinuities, catastrophic forgetting và selection overhead.

## Kiểm toàn chuỗi, không chỉ lỗi task

| Phần | Giữ / điều chỉnh và giới hạn |
|---|---|
| Người dùng/pain point | Đội AI/robotics; cần owner/time-motion và lý do dùng humanoid, chưa xác nhận DENSO task |
| Task và observability | Entry/exit/readiness, known/unknown/not_attempted, independent verifier; tolerance phải pilot |
| Binding/runtime | Camera/action/state/controller/normalization checks và abort; RTC không thay low-level control |
| Data/multisource | Lineage/splits/rights/masks giữ; corrections có role/authority/context; video không tự robot action |
| Diagnosis/planning | Hypotheses + controlled probes + engineer approval; không fail-rate→source lookup đơn giản |
| Training | Native target action post-training, prior replay/regression; residual/RL là extension |
| Zero success | Phân biệt partial progress/no basic/unknown; bootstrap, curriculum, stop/rescope |
| Evaluation | D0/scorer gates, local/transitions/global/regression, independent final; no-gain giữ |
| Costs | Mọi reset/probe/verifier/bootstrap và retraining ghi actual/estimated/unknown; core15 có điều kiện |
| Novelty | DAgger/PARTS/CR-DAgger/MimicGen là tiền lệ; khác biệt workflow condition/effort cần hơn expert T |
| Reuse/production | Task2 đo công định nghĩa scorer/reset, robot2 acceptance riêng; sim không chứng minh real |
| UX/handover | Interactive declared examples + docs/model/status; video9cảnh là bản nhập môn, chưa engine diagnosis |

## Ưu tiên sau đặc tả

1. Owner khóa một task khả thi; E0 native policy path, scorer robot và command/response.
2. D0: scorer agreement, unknown/coverage, boundary/retry/abort; natural/restaged probes trên GR1 thực sự chạy.
3. E1 useful baseline; nếu chưa có, bootstrap/rescope theo cap. Cập nhật training jobs thực tế, không giữ 15 như budget tuyệt đối.
4. E4 A vs expert T/F từ cùng parents và quyền truy cập evidence/probe; target correction + prior replay, paired whole-task trials, total cost.
5. Freeze/final/owner acceptance; báo achieved/no-gain/inconclusive. Mở source/RL/real/task2 chỉ sau gate.

## Bằng chứng nguồn đã đọc

[PARTS arXiv:2609.21788v2 §I, §III-A/B](https://arxiv.org/html/2609.21788v2) hỗ trợ phân biệt local bottleneck, readiness và staged entries; giả thiết task-specific base và local verifier/reset. [DAgger PMLR 2011 abstract](https://proceedings.mlr.press/v15/ross11a.html) hỗ trợ distribution shift của sequential actions. [CR-DAgger system/method](https://compliant-residual-dagger.github.io/) hỗ trợ correction interface/learner và risks của takeover. [MimicGen TaskSpec](https://mimicgen.github.io/docs/modules/task_spec.html) xác định subtask signals/segmentation settings. Chưa audit tất cả appendix hoặc chuyển benchmark vào humanoid task này.

[Đặc tả solution](../14-task-improvement.md) · [PRD](../08-prd.md) · [Protocol](../06-validation-and-roadmap.md) · [Chi phí](../07-business-case.md).
