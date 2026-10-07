# 15 · Dataset → training → evaluation → inference

_Rà nguồn gốc ngày 06/10/2026. Đây là đề xuất triển khai sau khảo sát, chưa native training result. Bản này làm rõ taxonomy và các nhánh học; không thay recipe A1 bằng FOCA hay World Action Model một cách mặc định._

## Đánh giá các nhận xét

| Nhận xét | Đánh giá và điều chỉnh cần thiết |
|---|---|
| Synthetic không nên là một modality đầu vào đứng ngang RGB/text/action | Đúng. Synthetic mô tả cách tạo dữ liệu. Loader phải dựa vào tín hiệu thật có, không dựa vào nhãn synthetic. Vẫn có thể phát hành một synthetic dataset riêng để versioning và ablation. |
| Synthetic là augmentation và simulation generation | Đúng nhưng chưa đủ. Còn neural video generation. Appearance augmentation có thể kế thừa nhãn; sim execution ghi nhãn mới; generated video thường chưa có action. Ba đường có quyền kế thừa target khác nhau. |
| VLM học ảnh + text, có thể dùng video/frame | Đúng ở mức modality, nhưng file MP4 không tự là input tensor. Decoder/sampler tạo frames; video-capable backbone mới xử lý temporal tokens theo interface của nó. Tách frame để học độc lập không tự học dynamics. Caption, grounding, contrastive và generative objectives cần targets khác nhau. |
| Latent là vector từ encoder | Đúng, nhưng chưa đủ để ghép hai encoder. Phải pin encoder/layer/shape/normalization và adapter. Visual embedding, future embedding, VAE video latent và latent-action code là các representation khác nhau. |
| Robot actions dùng để học Action Expert, không cần pretrain lại VLM | Hợp lý cho recipe frozen VLM. Không phải quy luật mọi VLA: action loss vẫn có thể cập nhật visual/projector/LLM khi được mở. Tận dụng pretrained checkpoint khác với train VLM từ đầu. |
| Action-free có ích cho few-shot | Là giả thuyết có tiền lệ. Phải phân biệt action-free auxiliary learning với toàn bộ policy training không action. Kiểm robot outcome và tổng công, không chỉ representation loss. |

## Khảo sát cách training nhiều model

| Model / version đã đọc | Dataset và training | Module / inference | Bài học cho A1 |
|---|---|---|---|
| [OpenVLA, project + official code](https://openvla.github.io/) · đọc 06/10/2026 | Pretrained Prismatic VLM → robot image/instruction/action trajectories; discretized action tokens, autoregressive supervision. Code hỗ trợ RLDS và full/partial/LoRA adaptation. | Action-token generation, unnormalize theo robot. Frozen-vision/last-layer-only yếu trong ablation Franka của tác giả; không suy ra mọi frozen VLM đều yếu. | Không gọi flow matching là loss chung cho mọi VLA. [Code](https://github.com/openvla/openvla). |
| [π0 · arXiv:2410.24164v1](https://arxiv.org/html/2410.24164v1) · §III–V, Appendix A-B | PaliGemma initialization + diverse robot pretraining → curated task posttraining. Images/text/state condition noisy action chunks; flow velocity là target. | Backbone thích nghi cùng robotics-specific action expert; inference tích phân noise → continuous chunk. | Tách VLM foundation pretraining, VLA robot pretraining và task adaptation. Các giai đoạn không đồng nghĩa. |
| [GR00T N1.5 · official release](https://research.nvidia.com/labs/gear/gr00t-n1_5/) · architecture/objective/training | Mixed robot/sim/neural trajectories; flow action loss + FLARE future-feature alignment. | Official recipe giữ VLM frozen; policy/DiT học control và alignment. | Frozen VLM có tiền lệ. FluxVLA selected config `tune_visual=True` là lựa chọn implementation khác, phải kiểm manifest. |
| [FOCA · arXiv:2606.20867v1](https://arxiv.org/html/2606.20867v1) · §3–5, Table 2 | Current visual/language context → future-aware tokens; explicit region-feature regression + implicit future alignment. Q2: generated video phase dùng implicit loss, rồi action-labeled adaptation. | Frozen vision target encoder; trainable conditioning/policy theo implementation. Inference dùng current context, không yêu cầu future GT. | Action-free auxiliary, không thay robot action supervision. Không đồng nhất FOCA với full dynamics simulator. |
| [DreamGen · official pipeline](https://research.nvidia.com/labs/gear/dreamgen/) · 4 stages | Tune video model trên target embodiment → generate từ initial image + instruction → IDM/latent-action pseudo-labels → train downstream policy. | Generator và policy là hai roles; generator không bắt buộc chạy khi policy điều khiển. | Generated video khác sim-executed trajectory; pseudo-action khác measured action. |
| [DreamZero · arXiv:2602.15922v1](https://arxiv.org/html/2602.15922v1) · §3, §4, Appendix C | Wan video backbone; joint flow-matching video-latent/action chunks, teacher-forced clean history; robot state/text conditioning. | Update DiT/state/action modules; freeze text/image encoders và VAE. Inference joint denoising, nhận observation thật để cập nhật history/cache. | WAM là thay đổi backbone/objective/runtime; cần kiểm latency, không chỉ thêm dataset vào VLA. |
| [DreamerV3 · arXiv:2301.04104v2](https://arxiv.org/html/2301.04104v2) · Learning algorithm | Replay observations/actions/rewards/continuation → RSSM reconstruction/prediction + KL; actor/critic học trên imagined rollouts. | Online observation → latent state → actor action; không lookahead planner ở mỗi bước trong recipe này. | Action-conditioned dynamics và RL cần transitions/reward/termination; không có trong RGB-only video mặc định. |

Không so các benchmark này thành leaderboard: budget, embodiment, success/task-progress/return và protocols khác nhau. World Models có thể đóng ba vai trò: **tạo dữ liệu offline**, **auxiliary future representation**, hoặc **dynamics dùng cho control/imagination**. Chọn vai trò trước khi chọn file và loss.

### FOCA và few-shot: đọc đúng điều kiện

Table 2 ở LIBERO, 40% demonstrations (~20/task): π0 89.9%; implicit FOCA 93.0%; FOCA + DreamGen 95.7%. Con số cuối thuộc nhánh thêm generated video, không plain FOCA. Đây là kết quả tác giả, chưa kết quả GR1/A1. Appendix D.3 ghi thêm generation/training compute; phải tính vào cost.

[Official repository](https://github.com/cair-vinuni/FOCA), mục co-training, còn ghi code pipeline LIBERO “coming soon” tại lần đọc này. Có pretrained checkpoints và hướng dẫn adaptation không đồng nghĩa mọi nhánh tái lập đã sẵn. Pin code/checkpoint/config và xác nhận gradient routes trước port. Frozen target vision encoder không tự có nghĩa toàn VLM frozen.

## Phân loại sạch: bốn trục riêng

1. **Nguồn gốc:** robot hardware, robot simulator, human recording; nơi publish/download là metadata riêng.
2. **Cách tạo:** recorded/executed, appearance augmentation, simulation trajectory generation, neural video generation. Giữ generator/seed/parent revisions.
3. **Supervision:** image-text; temporal video; robot state/action; human pose/geometry; outcome/contact nếu thực có. Một episode có thể hỗ trợ nhiều views/objectives.
4. **Representation:** RGB pixels, token IDs, encoded features, normalized actions, future latents. Đây là kết quả preprocessing/model, không thêm nguồn độc lập.

Ví dụ: human ego clip tải internet = human-origin + recorded + temporal RGB/text; thêm tracking thì có motion supervision. Sim-generated execution = sim-origin + trajectory-generation + RGB/text/state/action + sim readback. DreamGen video = neural-generated + temporal RGB/text + action missing, trừ nhánh pseudo-label được khai riêng.

## File formats và release contract đề xuất

Các paths dưới đây là **schema dự kiến của project**, không tuyên bố tất cả papers dùng cùng định dạng. Adapter chuyển vào selected model loader sau compatibility gate.

| Payload / lưu trên đĩa | Nội dung bắt buộc | Tensor / vai trò |
|---|---|---|
| `.mp4` hoặc frames `.png/.jpg` | camera ID, decoded timestamps, frame index, resolution, intrinsics/extrinsics nếu objective cần | RGB tensor; sampler chọn camera/time/history theo config |
| `.jsonl` / `.parquet` instructions | task/episode IDs, text, language, segment start/end | Token IDs + attention masks; không coi caption là robot action |
| `.parquet` robot signals | timestamps, state, action targets, separate issued commands/readback, validity masks | `state[B,Ds]`, `action[B,H,Da]`; units/order/controller profile bắt buộc |
| `.parquet` hoặc source `.csv` human tracking | timestamps, wrist/hand pose, confidence, frame convention; camera calibration `.json` | Motion targets + masks; adapter riêng, không đổi tên thành robot joints |
| `.png` masks hoặc encoded masks trong sidecar | camera/time, instance/region IDs, annotation method/revision | Training region targets nếu recipe cần; không tự là sensor ở inference |
| `.json/.jsonl` QA/provenance/splits | origin, creation method, root/parents, schema, rights, generator, action provenance, task outcome, accepted/rejected | Release eligibility và sampler routing; không vào policy như privileged hints |
| Optional `.safetensors/.npz` feature cache | encoder/checkpoint hash, layer, processor, input hash, shape/dtype, target stop-gradient status | Derived representation; rebuild khi encoder/preprocessing thay đổi |

[Manifest mẫu có cấu trúc](../docs/implementation-plan/skill-a1/dataset-manifest.proposed.json) định rõ file fields, capabilities, missing-target rules và split contracts. Đây là schema proposal; IDs/dimensions để null tới khi pin source và robot profile, chưa native dataset đã thu.

Canonical robot storage ưu tiên adapter LeRobot theo version pin. [LeRobotDataset v3 docs](https://huggingface.co/docs/lerobot/lerobot-dataset-v3) mô tả Parquet signals + MP4 camera shards + schema/episode metadata; một shard có nhiều episodes, boundaries lấy từ metadata. Docs hiện ghi `meta/tasks.jsonl`, public samples đã quan sát có `tasks.parquet`: inspect actual release, không đoán extension từ tên v3.

```text
release-a1/                          # proposed; not a dataset already collected
  manifest.json                     # version, hashes, features, origin/method
  splits.json                       # root/scenario/session groups
  episodes.parquet                  # boundaries, camera maps, task refs
  instructions.jsonl
  videos/ego/file-000.mp4
  signals/file-000.parquet           # timestamp, state/action/commands/readback
  annotations/poses.parquet          # optional human geometry + masks
  annotations/regions.parquet        # optional region/frame mapping
  calibration/cameras.json
  qa/receipts.jsonl                  # rejects, contact/readback, costs
  derived/features.safetensors      # optional; separately versioned
```

Missing actions: field absent / capability=false, không vector zero với valid mask. Dtype/shape khai trong manifest. `Da/Ds/H/V` lấy selected robot/model profile, không một số chiều chung cho mọi model. Padded dimensions cần explicit mask; stats chỉ từ train roots. Human invalid pose giữ null/mask, không bàn tay giả ở gốc tọa độ.

## Data qua architecture: điều kiện và target tách riêng

Ký hiệu `B` batch, `V` cameras, `T` sampled history, `H` action horizon. Images conceptually `[B,T,V,C,height,width]`, tokens `[B,L]`; wrapper có thể flatten/chọn T=1. Future target không được lẫn vào current observation path.

```text
                         CURRENT CONDITIONING
MP4/frames + instruction → decode/sample/tokenize → pretrained VLM → features
current robot state + embodiment/profile ──────────────────────────┐
features + allowed masks ─────────────────────────────────────────┤
                                                                 ↓
                                                          Action Expert
                                                                 ↓
                                                          predicted velocity
                                                                 ↓
robot future actions → normalize + noise → target (actions−noise) → L_action
                                                                 ↓
                                              backward to allowed modules only

                         AUXILIARY TRAINING TARGETS (optional recipe)
future frames from same episode → frozen target encoder → future features
current learned tokens / policy features → predictor/alignment → L_future
tracked future wrists + geometry → common motion branch → L_motion (A1 pilot)
```

Noise/time enter the selected flow head in training; inference starts from sampled noise and integrates to actions. `L_action` chỉ tính trên valid action targets. Generated RGB-only samples có `L_action=disabled`, không noisy fake actions. `L_future` chỉ chạy khi future sampler/target branch implemented. Semantic image-text objective cũng cần riêng labels, head/forward và gradient path; không phát sinh chỉ vì có text.

### Three training recipes của project

| Recipe | Có gì trong batch | Loss và modules | Lúc robot chạy |
|---|---|---|---|
| A · Native action baseline + sim variants | Current RGB/text/state/ID; valid future robot actions | Selected native objective; Action Expert + allowed adapters/visual modules. Freeze/tune do config/manifest, không gọi tất cả là frozen GR00T. | Current RGB/text/state/ID → actions → binding/controller |
| B · Action-free future alignment candidate | Current/future frames + task text, temporal/region masks theo variant; replay labeled robot data ở adaptation | Video-only future loss; robot batches action loss. Specify tokens/adapters/LLM/vision/DiT trainability. FOCA vs FLARE routes khác nhau, không thay cho nhau. | Current context; không cần actual future frame, training-only decoder hoặc future box |
| C · Existing human wrist pilot | R_common và R_common+H có common wrist convention; native robot targets giữ riêng | Frozen VLM giống nhau; robot native + common wrist objective, H wrist objective → shared motor trunk/common head; H không update native decoder trực tiếp | Native robot branch, không human tracking ở robot runtime |

B và C là hai câu hỏi khác nhau: video future representation có giúp control, và structured human motion có giúp motor learning. Không đưa cả hai cùng sim augmentation vào một experiment rồi quy gain cho một nguồn. B chưa được chọn/implemented; C vẫn là candidate đã đặc tả ở A1.

## Chuẩn bị → train → evaluation → inference

### 1. Chuẩn bị

Audit task/rights/relevance → pin raw data/code/schema → split roots/scenarios/sessions trước derivatives → decode/time-align → derive eligible targets → QA → immutable release. Appearance augmentation kế thừa actions chỉ sau kiểm geometry/timing/object cues; sim execution ghi actions/readback mới; neural videos giữ action-free hoặc pseudo status.

Future pairs ở cùng episode, không vượt termination hoặc split. Region annotations và encoder caches giữ source hash. Scorer privileged state chỉ ở evaluation/QA. Recovery expert có thể được học; policy failure traces không tự thành positive BC.

### 2. Train

Khởi tạo từ checkpoint đã pin → adapter/normalization sanity → một batch mỗi capability → per-loss gradients + frozen/update hashes → optimizer groups → schedule/replay → checkpoint/reload → rollout. Mỗi RunPlan ghi target definition, noise convention, mask reduction, lambda, trainable modules, batch mixture, root/compute budget. Verify no future-frame leakage vào current-conditioning path.

Foundation VLM pretraining đã nằm trong upstream checkpoint. Native VLA pretraining cũng có thể đã nằm trong checkpoint. MVP chỉ task adaptation/auxiliary extension cần thiết; không chi tiền train foundation từ đầu để gọi idea mạnh hơn.

### 3. Evaluation: cùng quality, giảm robot-data hoặc tổng cost?

- Baseline action-only và baseline + basic appearance augmentation trước heavy generation.
- R vs R+S_exec: cùng seed roots, thêm sim generation đã QA; báo thêm compute/yield.
- Future branch: B0 native; B1 cùng architecture có future objective trên robot videos; B2 B1 + recorded action-free video; B3 B1 + generated video. Chọn subset khả thi trong cap. B1 tách auxiliary-objective gain; B2/B3 tách thêm video. Có compute-matched replay control khi cần source attribution.
- Human wrist pilot: R_common vs R_common+H như đặc tả A1; không dùng native-only B0 làm sole control.
- Few-shot curve theo số **unique target-robot roots**, proposed 5/10/20 khi pilot resources cho phép; seed repeats và confidence intervals trên rollouts, giữ splits/session/domain ngang. Video variants không độc lập như robot roots.
- Full-task natural starts, stage/transition diagnostics, first-attempt/eventual success, grasp retention, collision, intervention, latency/stale action, regression. Đo source rights/processing, rejects, generation, annotation/IDM, train/eval, engineer/robot/GPU-hours.
- World Model branch nếu mở: temporal/instruction/physics consistency và action-response sensitivity nếu action-conditioned; downstream robot task là end metric. FVD/visual realism/future loss không tự là controllability.
- Freeze checkpoint/recipe/normalization/binding/scorer rồi final độc lập. Final failures giữ failure/unknown; không tune lại trên final rồi báo independent success.

### 4. Inference và flywheel

Acquire current sensor frames + instruction + state → same processor → pretrained VLM/interface → action chunk → denormalize/schedule/controller → measured response → independent scorer. Log input/model/action/command/response timestamps và version IDs. Future ground-truth frames, action labels, human target poses và QA outcome không vào runtime input.

FOCA-style policy dùng learned future-aware conditioning từ hiện tại; DreamZero-style WAM có joint video/action runtime khác; Dreamer dùng latent-state actor. Không vẽ cả ba thành cùng một action-head pipeline. Khi đổi runtime, re-pin acceptance/latency/binding và evaluate lại.

Flywheel quyết định **cần thêm supervision nào** trước khi chọn cách tạo nó: control labels → correction/sim execution; semantic/temporal gap → eligible video/auxiliary; geometry motion gap → tracked human pilot; binding fault → repair. Theo dõi coverage và quality/cost qua rounds. Đây là điểm thiết kế của project; hiệu quả phải đo trên A1 rồi kiểm reuse ở skill kế tiếp.

## Đề xuất chốt cho idea

Giữ một native VLA baseline có thể chạy closed-loop, một Data Core quản lý origin/method/capability/lineage, và các training views theo objective. Triển khai A trước; mở B hoặc C khi source/interface/compute gate đủ, từng hypothesis một. World Model generation là optional acquisition tool; WAM/RL là architecture alternatives, không dependency MVP bắt buộc.

Đóng góp mạnh cần chứng minh: **chọn đúng tín hiệu thiếu → tạo/release dữ liệu đúng semantics → học đúng modules → đạt cùng chất lượng bằng ít robot roots hoặc ít tổng công hơn**. Tăng số nhánh, số files hay số papers không thay được phép kiểm đó.

[Workflow Data Core](03-workflow-du-lieu.md) · [Kiến trúc](02-kien-truc-va-cach-hoc.md) · [Protocol](05-thiet-ke-kiem-chung.md) · [A1 recipe](../docs/implementation-plan/skill-a1/02-recipes-and-data.md).

## Hợp đồng bổ sung sau review 07/10/2026

[Decision/coverage/dedup/RunPlan và FOCA task-negative contract](../docs/implementation-plan/skill-a1/05-data-decision-and-run-contracts.md). Đây là đặc tả cần triển khai, không native receipts. QA pass chưa utility; source pilot chưa workflow advantage. Nhánh FOCA đơn task cần train-only task-mismatched negative pool hoặc adaptation công khai.
