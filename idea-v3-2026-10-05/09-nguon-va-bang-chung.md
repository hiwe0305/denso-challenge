# 09 · Nguồn, versions và phạm vi bằng chứng v3.1

Native code/source observations ở main cần pin trước run. Reference dùng NumPy ridge BC và MuJoCo3.5, không chuyển cơ chế/benchmarks của các paper thành kết quả reference.

_Các trang/code dưới đây đã được đọc trong thảo luận 05/10/2026. Review cơ chế và phạm vi, không tái lập thí nghiệm. Code main là snapshot quan sát theo ngày, chưa commit pin; phải pin trước implementation._

| ID | Nguồn đã đọc | Hỗ trợ | Không chứng minh |
|---|---|---|---|
| S1 | [GR00T N1 arXiv:2503.14734v1](https://arxiv.org/html/2503.14734v1), §2.1–2.3, §4.4 | VLM/DiT, latent/IDM labels, sim-executed generation, downstream neural-data comparison | Selected N1.5 config có mọi bridge của paper hoặc team savings |
| S2 | [EgoVLA arXiv:2507.12440v1](https://arxiv.org/html/2507.12440v1), §3 và §7 | Pose/camera-aware human action learning, unified representation/robot adaptation; cần pose và robot fine-tune trong recipe | RGB-only clip thành robot joints; transfer GR1/MuJoCo đã port |
| S3 | [EgoScale](https://research.nvidia.com/labs/gear/egoscale/), framework/model/scaling | Action-labeled human pretraining + aligned midtraining + robot posttraining; VLM/DiT prior | Project replicate 20k-hour training, one-shot mọi task hoặc monetary saving |
| S4 | [EgoMimic](https://egomimic.github.io/), method/scaling | Aria tracking/domain alignment/shared policy, pose và robot-joint supervision roles | Mọi human hour hữu ích hơn mọi robot hour ở mọi embodiment |
| S5 | [MimicGen](https://mimicgen.github.io/), [TaskSpec](https://mimicgen.github.io/docs/modules/task_spec.html) | Seed data scaling, subtasks/object frames/termination signals | Plugin tự chạy GR1/task khay, guaranteed sim-to-real |
| S6 | [DexMimicGen](https://dexmimicgen.github.io/), generation/pipeline | 20k+ demos từ 60 source demos trên 9 tasks; scalable execution-generation prior | 20k independent real roots hoặc giảm tương ứng total cost |
| S7 | [Cosmos-Transfer2.5](https://docs.nvidia.com/cosmos/latest/transfer2.5/index.html) | RGB/depth/segmentation conditioned visual augmentation | Generated video tự có measured robot commands |
| S8 | [FluxVLA N1.5 config](https://github.com/FluxVLA/FluxVLA/blob/main/configs/gr00tn15/gr00tn15_eagle_3b_robocasa_30_eps_full_finetune.py), model/data portions | EagleBackbone/FlowMatchingHead; tuning flags, selected schema/normalization path | Human-motion custom branch hoặc task wrapper đã triển khai |
| S9 | [LlavaVLA](https://raw.githubusercontent.com/FluxVLA/FluxVLA/main/fluxvla/models/vlas/llava_vla.py), forward/predict_action | Feature + mask interface; final output là predicted actions | VLM mặc định semantic JSON hoặc exposure mọi debug tensors |
| S10 | [FlowMatchingHead](https://raw.githubusercontent.com/FluxVLA/FluxVLA/main/fluxvla/models/heads/flow_matching_head.py), forward/denoise/predict | Training velocity target khác final integrated chunk; state/embodiment conditioning | Hooks/optimized paths parity hoặc per-human adapter đã validated |
| S11 | [FOCA 2606.20867v1](https://arxiv.org/html/2606.20867v1), §3–5, Table 2; [official code](https://github.com/cair-vinuni/FOCA), đọc 06/10/2026 | Action-free future objectives, few-shot adaptation; Q2 generated-video/implicit route | Policy hoàn toàn không action supervision; code co-training mọi nhánh đã sẵn; A1 đã transfer |
| S12 | [GR00T N1.5 official](https://research.nvidia.com/labs/gear/gr00t-n1_5/), architecture/objective/training, đọc 06/10/2026 | Frozen VLM + flow objective + FLARE future alignment | Selected FluxVLA flags trùng official, wrist pilot có sẵn |
| S13 | [π0 2410.24164v1](https://arxiv.org/html/2410.24164v1), §III–V / A-B | Pretrained PaliGemma + action expert; robot pretrain/posttrain; flow action chunks | Mọi VLA freeze VLM hoặc mọi model dùng flow loss |
| S14 | [OpenVLA official](https://openvla.github.io/), [code](https://github.com/openvla/openvla), đọc 06/10/2026 | Action token learning, full/partial/LoRA; frozen-vision ablation có scope | Frozen VLM luôn không học control được; token accuracy là task success |
| S15 | [DreamGen official](https://research.nvidia.com/labs/gear/dreamgen/), four stages | Video generator → inferred-action labels → downstream policy | Generated video có measured actions hoặc physically valid contact mặc định |
| S16 | [DreamZero 2602.15922v1](https://arxiv.org/html/2602.15922v1), §3–4 / C | Joint video/action flow, DiT updates và frozen encoders/VAE; distinct runtime | WAM chỉ là data augmentation hoặc drop-in GR1 solution |
| S17 | [DreamerV3 2301.04104v2](https://arxiv.org/html/2301.04104v2), Learning algorithm | Action-conditioned RSSM; reward/continuation targets; imagined actor/critic | RGB-only video đủ RL transition labels hoặc online lookahead ở mọi step |

Không so success percentages giữa papers như leaderboard. Paper N1, implementation/config N1.5 và repo main có versions khác nhau. Model cards/generic diagrams cần đối chiếu selected source code khi labels/architectures không khớp; không tự thay model để ghép claims.

## Tuyên bố truyền thông được phép trước thực nghiệm

“Human motion và synthetic execution là hướng có tiền lệ để tăng data efficiency.” “Project đề xuất recipe trên GR1 và kiểm lượng robot data/tổng chi phí.” “Sim generation có thể ghi actions đã thực thi trong sim.”

Chưa được viết: “Đội đã giảm mạnh chi phí”, “video bất kỳ tạo đúng robot action”, “đã biết chính xác module lỗi”, “mọi latent giải mã được”, “sim pass chứng minh robot thật pass”.

## Mối liên hệ với repo trước v3.1

Base commit e45cf7f0309f3fe58112c98c10b1111f5bee1864. Docs 01–14/website tại commit đó là thiết kế v2: stage/correction workflow và T/F/A acquisition. Folder này là design v3.1 và executed reference; giữ lịch sử cũ, không chỉnh paper figures/public media thành team outcomes. Tài liệu trong folder tự chứa tất cả quyết định cần đọc; Website và canonical docs nay trình bày v3.1; history giữ designs trước. Native implementation chưa validated.
