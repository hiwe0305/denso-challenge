# 02 · Recipes dữ liệu và training

## Schema và phạm vi recipe

[Blueprint sau khảo sát VLA/World Models](../../../idea-v3-2026-10-05/15-dataset-training-blueprint.md) là đặc tả file formats và data/loss routes: MP4/frames + instruction JSONL + state/action Parquet; motion poses/geometry có adapter riêng. Synthetic là creation method, latent là derived representation. S_exec dùng cùng native robot action view sau QA; chưa một input modality độc lập.

Action-free FOCA/FLARE-style future route là candidate khác human common-wrist route dưới đây. Chưa thay chọn pilot hoặc gộp các routes vào một contrast. Training targets tương lai tách khỏi current conditioning; generated videos thiếu action thì action loss disabled.

## Pilot đầu: R và R+S

R là cùng pretrained checkpoint + demonstrations robot đích; R+S thêm positive simulator executions từ training roots. Robot observations/actions phải ghi từ controller thật của native task. Không gọi simulated roots là robot-real recordings.

Draft collection budget đầu:20 independent seed episodes cho training. Đây là lựa chọn pilot để benchmark, không số mẫu được chứng minh đủ. Scenario/session/root split khóa trước windows/variants. Development recordings và expert corrections tính vào robot-data usage của study nếu dùng để chọn/tune; evaluation không tính là training roots nhưng công đánh giá luôn vào total cost. Phải log actual unique roots; con số20 không che seed/calibration/correction ngoài loader.

Synthetic generation:

1. Lấy seed hợp lệ; xác định các đoạn liên hệ với object và target frame. Segmentation đến từ expert/action/scene traces; không đoán stage ground truth từ animation.
2. Chọn transform trong miền train đã kiểm reachability; nối waypoint/trajectory bằng adapter native.
3. Thực thi qua controller/physics; ghi desired action, command đã gửi, actual state/contact/images và outcome.
4. QA action semantics, tracking error, collision/task constraints và success. Failed executions không làm positive BC targets; giữ reasons và generation cost.
5. Freeze release R+S. Parent/descendant lineage giữ nguyên;100 variants không là100 independent seed roots.

Physics QA cụ thể cần contact-pair validity, penetration/collision/task constraints, tracking error, command limits và object retention. Contact forces chỉ là một signal; success cuối không thay QA. Reference weld không native gripper-contact proof. Thresholds cần calibration trên native expert replay và negative cases trước phát hành.

[MimicGen TaskSpec](https://mimicgen.github.io/docs/modules/task_spec.html) là tiền lệ generation dùng object-frame/subtask signals; project vẫn phải port task/controller. Video augmentation là appearance branch riêng, chỉ kế thừa nhãn sau QA. Pilot đầu không dùng neural video/IDM để mở thêm một nguồn nhãn chưa kiểm.

Training giữ native robot action objective: valid action sequence và masks → flow-matching training target theo selected head. Final integrated inference chunk khác velocity target training. R và R+S dùng cùng parent, profile, eligible robot budget và development rules. Mixture ratio/steps/normalization chọn trên development, lưu cả extra compute; chưa có forced winner.

## Human: chọn route B làm candidate motor pilot

Lý do chọn pilot này: user muốn kiểm human motion có cải thiện Action Expert. Một objective chỉ lên VLM không trả lời đủ câu hỏi đó. Candidate là **human-specific state adapter + human/robot common wrist-motion objective + shared Action Expert trunk**, bên cạnh native robot action path. Đây là custom training extension cần implement; không nói selected FluxVLA config đã cung cấp bridge này. Không dùng “cùng hidden width” làm lý do cho transfer giữa wrist pose người và robot joint actions.

[EgoScale](https://research.nvidia.com/labs/gear/egoscale/) cung cấp tiền lệ common wrist representation với embodiment adapters. Proposal dưới đây là adaptation cần thử, không replication EgoScale hoặc guarantee transfer.

### Human source và target

Chỉ dùng purposeful manipulation source có RGB, hand/wrist pose, camera poses/time/calibration, masks và provenance phù hợp. Source cần transfer relevance với rigid pick/transport/place. RGB-only source có thể có objective khác về representation nhưng không được gọi là motor pilot này.

Target candidate: tương lai wrist poses của tối đa hai tay, biểu diễn trong camera frame tại thời điểm input hiện tại. Mỗi wrist có translation3 + rotation6D =9 channels; hai tay là18 channels, masks cho tay/khung thiếu. Đây là human motion, không joint targets GR1. Không tự thêm open/close/grasp labels từ motion; không có contact supervision khi source không đo contact.

Nếu source có world-camera và world-wrist transforms, target hình học là:

`T_camera(t)_wrist(t+k) = inverse(T_world_camera(t)) × T_world_wrist(t+k)`.

Đây là absolute pose trong current-camera frame, không camera frame di chuyển ở thời điểm tương lai. Clocks và horizon sampling phải align; future poses chỉ là offline supervision. Current human state lấy tracked current wrists/masks. Rotation6D valid theo geometry QA; invalid orientation mask riêng. Target horizon/time spacing kiểm so với native chunk/timebase trước pilot.

**Robot cũng cần common wrist targets:** từ future measured robot states của executed demonstrations, lấy wrist transforms bằng calibrated forward kinematics/readback rồi biểu diễn trong robot camera frame tại input time, cùng pose/time/rotation conventions và masks như H. Không lấy future desired joint command làm measured wrist outcome. Wrist targets của R/H cùng physical units và cùng normalization pin trong RunPlan; scale được chọn từ physical units/shared robot training-development, không dùng H labels để thay normalization của robot-only control và không dùng final. Native joint-action statistics giữ riêng. Human/robot recordings không cần paired, nhưng cùng mathematical representation không tự bảo đảm distributions đã align hoặc transfer có ích.

### Modules và loss

| Source | Input/targets | Update route đề xuất |
|---|---|---|
| Robot native branch của human pilot | Native images/tokens/state/embodiment; native future actions/masks | Native robot encoders/decoder, shared ACT trunk; VLM frozen trong cả hai human-study arms |
| Robot common-motion branch | Robot state adapter, common noisy future wrist sequence18D; measured wrist targets/masks | Common motion encoder/decoder, shared ACT trunk; VLM frozen |
| Human H common-motion branch | Human images/tokens; tracked state adapter; same18D noisy future wrist convention/masks | Human state adapter, common motion encoder/decoder, shared ACT trunk |

Pilot H đầu freeze VLM trong **cả R_common và R_common+H**, dùng features detached cho robot/human losses để kiểm human supervision trên Action Expert. Đây là recipe mới cho human pilot; khác lựa chọn tune_visual của baseline/S pilot và phải có config/manifest riêng. Không nhận pilot này kiểm toàn bộ lợi ích human video. Geometry/current human state vẫn đến từ source audit, không từ semantic JSON do VLM tưởng tượng.

Frozen weights không đồng nghĩa features giống nhau giữa inputs. [GR00T N1.5](https://research.nvidia.com/labs/gear/gr00t-n1_5/) có frozen VLM và human-video learning qua FLARE, objective khác pilot này. No downstream gain chỉ là no-gain trong frozen wrist recipe; chưa bác bỏ human transfer nói chung. Nếu probe/control evidence cho thấy representation bottleneck, preregister selected visual/interface tuning ở cả no-H và H controls với trainable/compute manifests giống nhau; trial này thêm cost, không mở mặc định.

Real human + sim robot là domain-risk cần đo, chưa là incompatibility đã chứng minh. Teleoperation chính robot trong sim tạo robot demonstration route; không đổi nó thành human ego source để giữ tên contrast. Appearance randomization chọn theo train domain/development và giữ task cues; không bắt mức cực nặng trước evidence.

Objective candidate: `L_total = L_robot_action_flow + lambda_RW × L_robot_wrist_flow + lambda_H × L_human_wrist_flow`. Native robot loss dùng native actions/stats; hai wrist losses dùng common target convention/noise/normalization và masks. Mỗi loss mean trên valid elements. Human tensors không pad giả robot29D; common motion encoder/decoder18D và explicit branch conditioning đi vào shared trunk với interface đã kiểm. Khi không có valid targets trong window thì bỏ loss của window, không mean trên mask rỗng. Lambda và schedule là development choices có receipt; không chạy cả ba bridge hoặc mặc định human-prefix pretraining.

Việc thêm adapters không tự làm shared trunk hiểu action semantics. Prototype phải instantiate module shapes, branch/embodiment conditioning, time/noise handling, attention masks và optimizer groups từ pin config. Per-source gradient test phải cho thấy H cập nhật shared ACT/human state/common motion modules và không cập nhật native robot action decoder hoặc detached VLM; R cập nhật đúng robot/native và robot common-motion paths. New modules phải có initialization/checkpoint key/loading/inference policy rõ. Robot inference dùng native action branch, không cần chạy wrist decoder, nhưng shared weights và explicit native branch conditioning sau training vẫn phải reload và parity-check. Training-only branch không được âm thầm làm inference schema không load được.

### Khi nào được nói human đã giúp?

1. Source/batch/geometry/loss/gradient/reload gates pass.
2. Tạo robot-only control `R_common` cũng có architecture/common wrist objective, cùng parent initialization, target robot data, task/domain và development rules với `R_common+H`; ghi human volume/processing và extra compute. Không so thêm robot auxiliary loss + human với baseline không có auxiliary rồi quy toàn gain cho H. R_common là comparator của human pilot, khác native-only R của pilot S; phải ghi recipe/version mới.
3. Robot full-task/transitions/regression tốt hơn hoặc đạt cùng quality threshold với ít robot data/tổng công hơn. Human motion loss giảm một mình không đủ.
4. Có compute-matched robot-only control nếu muốn tách human benefit khỏi extra training. Cost advantage workflow và causal source attribution là hai estimands riêng.

Nếu geometry/interface/cost gate fail: H not_integrated. Nếu valid training nhưng downstream không gain: ghi negative/no transfer trong scope. Không đổi labels, tăng grid hoặc chuyển route chỉ để giữ kết luận thắng. Một route mới là vòng thử riêng với budget/final plan mới.

Wrist-only pilot đo approach/transport và grasp/retention riêng. Không có finger/contact supervision thì chưa claim human data dạy grasp/contact. EgoScale v1 §3.6 báo wrist-only yếu trong dexterous tasks của paper; đó là risk prior, chưa là kết quả task A1.
