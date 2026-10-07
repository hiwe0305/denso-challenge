# Phản hồi nhận xét kiến trúc và quyết định · 06/10/2026

Scope: IDEA.md ngày06/10, A1 proposal và pasted feedback của user. Native VLA/human transfer chưa chạy. Đây là review thiết kế và cập nhật đặc tả, chưa giải quyết các risks bằng thực nghiệm.

| Anchor | Nhận xét / basis | Quyết định và phép kiểm phân biệt |
|---|---|---|
| H→ACT | Shared trunk có tiền lệ, nhưng claim “đúng đắn” chưa established | Giữ candidate; geometry/time/noise/masks/gradient/reload và downstream robot transfer quyết định |
| STUDY | Source separation hợp lý; extra compute có thể confound | Giữ R/R+S, R_common/R_common+H; matched source definitions và compute controls khi cần causal attribution |
| EVID→DIAG | Trace có ích, chưa automatic causal attribution | Facts/alternatives + controlled probes; command/response và matched entry trước chọn module/data |
| H/R→VLM | Real-human/sim-robot là inferred domain risk | Pilot theo domain; không bắt sim teleop thay human source hoặc heavy randomization trước evidence |
| VLM→ACT | “Freeze không thể học human” là unsupported universal claim, có counterexample | Giữ frozen pilot; no-gain scoped; selected unfreeze trial khi representation evidence và cap cho phép |
| S→QA | Final success chưa đủ physics validity; material design risk | Contact pairs/penetration/tracking/limits/retention/outcome QA; calibrated predicates và native negative cases |
| Failure→R | Recovery là extension; failure không positive actions | Expert post-failure correction, verifier/task retry gate; first-attempt/eventual/retries/cycle riêng |
| PLAN | “Chắc chắn vỡ trận”,70% bắt buộc chưa có resource/acceptance premises | Giữ baseline→S→H→final gates; quality/domain/cap do owner/pilot chốt |
| H→grasp | Wrist-only không có finger/contact; design risk bị feedback bỏ sót | Đo approach/transport khác grasp/retention; không claim grasp transfer từ wrist loss một mình |

Nguồn đã đọc: [GR00T N1.5, 09/06/2025, Architecture và Human ego videos](https://research.nvidia.com/labs/gear/gr00t-n15/) nêu frozen VLM và FLARE human-video learning. FLARE khác wrist objective A1, nên đây là counterexample cho impossibility, chưa proof pilot. [EgoScale arXiv:2602.16710v1, §2.1–2.4, §3.4, §3.6](https://arxiv.org/html/2602.16710v1) cung cấp common relative wrist/action adapters, alignment recipe và wrist-only limitation trên tasks của tác giả. A1 dùng future absolute wrist trong current-camera frame, chưa replication. [MimicGen execution](https://mimicgen.github.io/docs/modules/datagen.html) và [generation workflow](https://mimicgen.github.io/docs/tutorials/getting_started.html) thực thi actions và tách successful/failed outputs; task-specific physics QA vẫn cần port/validate.

## Thiết kế bổ sung: Data Core flywheel

RUN→DIAG→ACQUIRE→RELEASE→TRAIN→EVAL→RUN. Repair route DIAG→repair/re-pin→RUN; no-gain EVAL→DIAG trong cap; independent final nằm ngoài development feedback. Sources R/H/S là alternatives theo eligibility và hypothesis, không forced mixture. Website minh họa ba cases, không ML backend. Đặc tả tại03-workflow-du-lieu và IDEA §6.1; recipe/update/evaluation contracts tại A1.

Next check: native useful baseline với đúng action/controller/scorer trước source pilot; contact QA negative cases; R_common/R_common+H downstream holdout. Chưa có evidence native để đánh dấu risks resolved hoặc savings established.
