# 03 · Data Core: data flywheel có kiểm chứng

_Snapshot kỹ thuật từ [hồ sơ engineering](../idea-v3-2026-10-05/03-workflow-du-lieu.md); [IDEA.md](../IDEA.md) là bản trình bày gửi đánh giá, recipe mới nhất ở docs/implementation-plan/skill-a1._
**Cập nhật 06/10/2026.** Data Core giữ dữ liệu, lineage, QA và evidence để quyết định lần học tiếp theo. Vòng lặp được điều phối bởi kỹ sư; native VLA flywheel chưa được triển khai. Reference nhỏ đã kiểm một số đường execution/training/evaluation, chưa chứng minh human transfer hoặc data efficiency.

## Vòng lặp và trách nhiệm

| Node | Việc làm | Đầu ra / điều kiện |
|---|---|---|
| RUN | Policy chạy task trong miền đã khóa; ghi cả success/failure/unknown/timeout/intervention | Episode trace nối observations → action → command → response → independent outcome |
| DIAG | Kiểm integration trước; thử giả thuyết với matched scenes/entry states | EvidenceCard giữ facts/alternatives/test/decision; chưa chắc → collect evidence/defer |
| ACQUIRE | Chọn reuse, expert correction/recovery, sim execution hoặc eligible human motion | AcquisitionPlan có context/source/rights/cost cap; không ép đủ R/H/S |
| RELEASE | QA semantics/geometry/time/contact/outcome và roots/splits | Immutable release; accepted/rejected/cost; failed actions không positive BC |
| TRAIN | Parent checkpoint + eligible release + prior replay, loss/module route rõ | Candidate + gradient/reload/runtime receipts; giảm loss chưa đủ |
| EVAL | Full-task natural starts, transitions, regression và total cost | Promote development candidate khi đạt gate; reject/no-gain giữ evidence và parent |

Luồng: RUN → DIAG → ACQUIRE → RELEASE → TRAIN → EVAL → RUN. Lỗi binding/controller đi DIAG → repair/re-pin → RUN để lập lại baseline; không cần vòng training. Candidate fail evaluation giữ ngoài rollout chính; evidence quay lại DIAG để quyết định thử tiếp hoặc stop trong cap.

Kết thúc development study mới freeze và chạy final độc lập để nghiệm thu. Final không được quay vào acquisition/tuning; nếu dùng nó để phát triển vòng mới, phải đổi vai trò dữ liệu và có fresh final cho claim tiếp theo. Source pilots R/R+S và R_common/R_common+H giữ recipe/source definitions; adaptive correction rounds là study riêng, không nhập thêm can thiệp rồi vẫn gọi source-only gain.

## Flywheel tích lũy và đo giá trị

Tích lũy trải nghiệm có provenance, expert actions đúng, coverage đã thử, recipes, lỗi integration và cả interventions no-gain. Policy tốt hơn có thể cung cấp trải nghiệm ở miền rộng hơn sau gate; không mặc định mỗi vòng đều cải thiện. Reference/robot-sim/robot-real giữ scope riêng.

Đo theo vòng: full-task/regression/cycle/interventions, unique robot roots và coverage, accepted generation yield, engineer/operator/GPU/robot-hours, total cost tới quality acceptance. Đo reuse ở skill kế tiếp. Số video, số variants hoặc số rounds không tự là hiệu quả flywheel. Lợi ích acquisition/evidence workflow cần so với workflow kỹ sư thường cùng intervention access và cap; source ablation không trả lời thay.

## Ba đường can thiệp minh họa

- Command lệch prediction: kiểm units/order/timing/readback; repair rồi re-pin baseline. Fault traces là debug evidence.
- Policy yếu ở vị trí mới nhưng expert feasible: thử correction hoặc sim variants trong train domain, QA rồi kiểm cả vùng mới và regression.
- Gắp hụt và task cho phép retry: thu expert recovery từ trạng thái sau hụt tới hoàn thành. Failed prefix giữ failure role; không train nguyên failed actions như positive demo. Báo first-attempt/eventual success, retries, cycle và interventions.

Common wrist representation chỉ thống nhất conventions, chưa xóa visual/embodiment gap. Human motion không có finger/contact labels thì chưa kỳ vọng sửa grasp chỉ bằng wrist loss. Source cần audit và downstream robot comparison theo recipe A1 hiện tại.

## Dataset release chung

**Phân loại hiện hành:** origin (robot/human/simulator), creation method (recorded/augmentation/sim-generated/neural-generated), supervision (RGB/text/state/action/pose/temporal) và representation (pixels/tokens/features) là các trục riêng. Internet là nơi phân phối; synthetic là cách tạo. R/H/S giữ tên arms lịch sử: S_exec là sim-generated **robot action view**, không tensor input thứ ba. Một action-free video view có thể lấy từ recording hoặc neural generation.

File formats: RGB MP4/PNG/JPG; instructions JSONL/Parquet; state/action/time/readback Parquet; human tracking CSV/Parquet + calibration JSON; QA/lineage/splits JSON/JSONL; optional encoder cache safetensors/NPZ có version. [Blueprint](../idea-v3-2026-10-05/15-dataset-training-blueprint.md) định rõ fields, capabilities, paths, training targets và adapter boundary. Shape/extension phải inspect actual release theo pinned loader, không đoán từ source category.

Mỗi recording/window có source revision/rights, root/ancestors, scenario/session, split, timestamps/units, camera/state/action schema, embodiment/profile, normalization revision, validity/confidence và action provenance. Canonical role: robot_recorded / sim_executed / inherited_validated / human_motion / pseudo_inferred / missing. Reference seed/correction dùng reference_*_executed để tránh gọi là thu robot thật.

Split roots/ancestors và scenario instances trước derivatives/windows. Final tách khỏi source choice/calibration/checkpoint selection/correction. Recording derivatives không independent robot roots. Không đếm một human internet clip thành hai samples theo source categories.

## R · Robot anchor và correction

Capture observations, issued action và response riêng; đồng bộ/camera/binding/units QA. Expert seed successful tạo useful baseline. Corrections phải expert đúng với states/context/takeover authority; failed policy action không positive imitation target. Khi reset/full expert episode thay vì takeover, ghi đúng collection mode; reference dùng expert-reset full episode trên development.

Seed/calibration/corrections thực dùng training/tuning tính vào robot budget. Evaluation recordings giữ riêng nhưng công vẫn vào cost. Robot thật cần hardware/operator/stop/calibration; chưa có thì scope sim.

## S · Synthetic execution

Input: seed actions/states/task binding/scorer. Tách stage/object frames, chọn transforms khả thi trong train domain, biến waypoint/trajectory và nối đoạn. Controller chạy trong physics → ghi commands/measured state/images/outcome → scorer/QA → accepted positive release. Rejects giữ reason/cost; không âm thầm xóa để cải thiện yield.

Reference triển khai seed waypoint templates: stage approach/grasp/lift offset theo object frame; transfer/place/release/retreat offset theo target frame. Mỗi variant thực chạy MuJoCo. Grasp dùng proximity weld, chưa contact-accurate. Native MimicGen-style port vào GR1 chưa có; cùng MuJoCo không bảo đảm task/controller compatibility.

Appearance: basic hoặc generated views chỉ kế thừa target nếu hình học/timing/vật/tay/outcome giữ nghĩa. Không là new motion coverage. Neural video không tự có action labels; có thể vào action-free temporal/future objective khi branch implemented. IDM/latent-action pseudo labels là route khác, không lệnh robot measured.

## H · Human egocentric

1. Audit dataset/task relevance/rights và actual RGB/pose/camera availability.
2. Đồng bộ clocks/intrinsics/extrinsics; bù ego motion. Không giả human/robot clips paired.
3. Chọn target như future wrist trong current-camera frame, định rõ absolute/delta/time horizon; orientation chỉ có nhãn valid.
4. Masks và confidence; invalid wrist không zero target. Sample overlays/readback/duplicates.
5. Chọn bridge/objective/module route; mini-batch gradient và native regression checks.
6. Robot downstream comparison; report negative transfer/not-integrated.

RGB-only không qua native BC loader thiếu robot targets. Public HumanEgo preview chỉ proof nguồn/schema, chưa train release được chọn. Reference hiện **không train human branch**, giữ not_integrated.

## QA không chỉ là shape

| Ranh giới | Từ chối / xử lý |
|---|---|
| Quyền/revision không rõ | Quarantine/not eligible |
| Units/frame/time/action semantics khác | Reprocess/adapter riêng, không concatenate |
| Missing target/confidence | Mask đúng objective hoặc reject |
| Failed/infeasible demo | Không positive BC; giữ failure/cost |
| Parent/final leakage | Invalidate release/run, thiết kế final round mới |
| Human geometry chưa đủ | Disable motion claim; không đổi nhãn thành robot action |
| High generation count | Report accepted attempts + parents; chưa claim independent coverage/saving |

Reference validator thực từ chối profile29D, frame/time sai, human labels đưa vào BC, NaN, nonmonotonic steps và final scenarios trong train. Contracts native chi tiết ở11.

## Hợp đồng bổ sung sau review 07/10/2026

[Decision/coverage/dedup/RunPlan và FOCA task-negative contract](../idea-v3-2026-10-05/../docs/implementation-plan/skill-a1/05-data-decision-and-run-contracts.md). Đây là đặc tả cần triển khai, không native receipts. QA pass chưa utility; source pilot chưa workflow advantage. Nhánh FOCA đơn task cần train-only task-mismatched negative pool hoặc adaptation công khai.
