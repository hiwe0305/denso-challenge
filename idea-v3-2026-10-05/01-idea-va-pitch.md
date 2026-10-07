# 01 · Ý tưởng, vấn đề thực tế và data flywheel

**Hai phần của solution:** Data Core quyết định dữ liệu hữu ích; [Model Engine Core · FluxVLA](17-model-engine-core-fluxvla.md) thực hiện training → evaluation → inference trên robot thật. Policy AI vẫn là GR00T N1.5 đề xuất, không đồng nhất với framework.
_Rà 06/10/2026 theo form DENSO. Đây là đề xuất; native GR1/A1 training, transfer và tiết kiệm chưa đo._

## Vấn đề trước giải pháp

Khi vật, vị trí, ánh sáng hoặc tiếp xúc thay đổi, một kỹ năng robot có thể cần demonstrations/corrections mới, reset môi trường, QA, training và evaluation lại. Điểm cần giải trong project là **chọn và tổ chức dữ liệu để mỗi vòng cải thiện đáng công hơn**, không chỉ tăng lượng file hoặc variants.

Video chưa chắc có nhãn điều khiển đúng robot; sim data cần kiểm physics/action semantics; tracking người có thể thiếu geometry/timing/contact. Sai nhãn, trùng lặp hoặc thiếu coverage có thể khiến thêm data vẫn không cải thiện toàn task. Đây là rủi ro thiết kế, chưa thống kê tại một công đoạn DENSO đã khảo sát.

| Nguồn nguyên bản | Số liệu và phạm vi | Ý nghĩa |
|---|---|---|
| [Figure Index, 25/08/2026](https://www.figure.ai/news/introducing-index) | 16 triệu video upload; 15 triệu USD đã trả creators; filtering/fraud review/dedup/rebalance/annotation. Công bố doanh nghiệp. | Chi phí acquisition/data operations là thật; upload chưa là training clips, payout chưa tổng cost dataset. |
| [FOCA v1, §5 Q2/Table 2](https://arxiv.org/html/2606.20867v1) | LIBERO 40% demo (~20/task): π0 89,9%; implicit FOCA 93,0%; FOCA+DreamGen 95,7%. | Supervision/recipe ảnh hưởng ích lợi data; generated-video phase implicit action-free, robot phase vẫn có action labels. Chưa GR1/A1 result. |
| [Figure Helix 2.5, 17/09/2026](https://www.figure.ai/news/helix-2-5-zero-shot-30-home-generalization) | Index pretraining9% →56% whole-task success; cùng downstream data/config;3 việc30 nhà chưa thấy. Công bố doanh nghiệp. | Broad experience có thể giúp transfer. Zero-shot ở nhà/vật eval; task fine-tuning vẫn có data ở nơi khác. |

[Video nguồn](https://www.youtube.com/watch?v=zKaeODg7xeE) đã đối chiếu transcript/description và nguồn Index/Helix; chưa kiểm trực quan toàn video. Sprint/backflip/dự báo thị trường không chứng minh manipulation A1 nên không dẫn mở đầu.

## Giải pháp: Data Core quyết định dữ liệu cho vòng sau

**RUN → kiểm giả thuyết → chọn data/can thiệp → QA release → train có phạm vi → eval → dùng hoặc kiểm tiếp.** Binding/controller faults đi repair; chưa đủ evidence thì hoãn acquisition. Xét supervision cần, rights, coverage và cost; không bắt mỗi round dùng đủ nguồn. Replay data tốt cũ, giữ fail/unknown/no-gain receipts; final độc lập ngoài vòng tune.

Kế thừa FluxVLA / pretrained GR00T N1.5 / RoboCasa GR1 sau compatibility. Đội xây Data Core lineage/QA/capability routing, adapters, task binding/scorer, trace, update plan và quality–cost report. Đóng góp dự kiến là cách quyết định/sử dụng dữ liệu kiểm được; chưa thuật toán VLA mới hoặc superiority đã chứng minh.

## Model AI là phần cốt lõi của solution

Data Core cấp eligible releases/batches/targets/masks; **Model AI** học representations và robot actions. Chọn pretrained **GR00T N1.5 qua FluxVLA** sau compatibility: Eagle VLM → features; measured state/embodiment + noisy actions/time → DiT Action Expert → flow velocity/chunk. Binding/controller ở ngoài model. [Nguồn NVIDIA](https://research.nvidia.com/labs/gear/gr00t-n1_5/) và [bản Model AI đầy đủ](16-model-ai-va-data-flywheel.md).

Robot adaptation: native action loss cập nhật expert/adapters và visual modules được selected recipe mở, LLM frozen theo Flux config tham chiếu. Human shared-trunk pilot freeze VLM cả hai controls, thêm common wrist branch; video action-free pilot thêm learned conditioning/future-alignment branch. Những extensions này là đề xuất cần implement, không tính mặc định đã có trong native model.

World Model có roles rõ: DreamGen tạo data offline; FOCA/FLARE là future-representation auxiliary; DreamZero/DreamerV3 là alternative policy stacks với recipe/runtime riêng. Data Core → Model training → inference/eval → evidence → Data Core đóng cùng vòng, không chỉ vòng thu/lưu file.

## Dataset và các bước training

| Bước | Dataset / trạng thái | Cách sử dụng và output |
|---|---|---|
| 0 · Compatibility | [limxdynamics/FluxVLAData](https://huggingface.co/datasets/limxdynamics/FluxVLAData/tree/7998ab57bc70be66234b5374800705e2b6c14545/robocasa_gr1_24tasks_first30ep): public GR1 subset 24 tasks/720 episodes | LeRobotv2.1 MP4+Parquet+metadata; preview ego256²/20fps, state/action 29D. Inspect task/profile/stats/rights, resolve stale split metadata, kiểm native batch/binding trên task tương thích. Bottle-to-cabinet không là A1 labels; waist-unlocked preview khác fixed-torso proposal. |
| 1 · Native baseline | R_A1 expert/correction, chưa thu; draft 20 train seed roots | Current RGB/text/state→VLM features+Action Expert; future actions normalize/noise→flow targets. Native adaptation→checkpoint R; selected Flux tune_llm=False/tune_visual=True cần pin/gradient check. |
| 2 · Coverage | S_exec từ R_A1 train roots, chưa sinh native | Transform→execute controller/physics→actions/readback/images mới→QA. R_A1+S_exec+replay, cùng native recipe với R. Synthetic là creation method; descendants không independent roots. |
| 3a · Human pilot riêng | [HumanEgo](https://huggingface.co/datasets/Leo-TX/HumanEgo) serve_bread preview, chưa relevance/geometry/integration pass | RGB+wristCSV/confidence/timestamps/calibration→camera-frame common wrists 18D. Robot common targets từ measured FK. So R_common/R_common+H, VLM frozen cả hai; H→human adapter/common head/shared motor trunk, không native decoder trực tiếp. Wrist-only chưa dạy contact. |
| 3b · Action-free candidate riêng | LIBERO/DreamGen recipe study; chưa chọn MVP A1 | LIBERO kiểm phương pháp ở embodiment benchmark; không gộp Panda7D vào GR1. Generated MP4/text/future masks→implicit alignment, action loss disabled; robot phase tiếp theo action+implicit. Conditioning/gradient route cần port và controls. |

Human/video là hai câu hỏi khác nhau, không gộp R+S rồi quy gain cho một nguồn. Public previews chưa release A1 hợp lệ; upstream có rights/non-commercial conditions. File→tensor→loss→modules chi tiết tại [15](15-dataset-training-blueprint.md) và [A1 recipes](../docs/implementation-plan/skill-a1/02-recipes-and-data.md).

## Chuỗi example: data → model → eval → inference → lỗi → flywheel

1. MP4/Parquet/JSON→sync/sample/tokenize/normalize→RGB tensor/tokens/state/action targets→VLM features. Latent có encoder/layer/shape/processor pin, không nguồn dataset mới.
2. Current features/state condition Action Expert; training future targets đi vào loss riêng, không vào current observation. Gradient chỉ vào modules mở trong manifest; inheritance pretrained khác pretraining foundation từ đầu.
3. So R/R+S cùng parent/task/domain/scorer/recipe; log unique roots, development/correction data, generation/QA/train/eval cost. Few-shot5/10/20 roots là đề xuất nếu đủ resources. Full-task, CI, ID/OOD, retention/intervention/latency/regression; native numbers chưa có.
4. Inference: current camera/language/state/history→cùng processor/VLM→action chunk→denormalization/controller→measured response→independent scorer. Không future labels, human targets hoặc privileged scorer input ở policy.
5. Error: trace→controlled tests→repair hoặc data/update plan. Ánh sáng có thể mở visual/interface study; thiếu control supervision có thể mở Action Expert post-training với correction+replay. Rơi khi chuyển có thể từ grasp trước đó; một triệu chứng chưa tự xác định module.
6. Development gain có ích mới xét dùng; no-gain quay lại hypothesis trong cap. Candidate freeze→final độc lập; không tune trên final rồi báo independent.

Reference [10](10-example-chay-toan-he-thong.md) đã chạy MuJoCo nhỏ, action4D/state idealized/scripted sequencer/ridge predictor/weld grasp; chưa VLM/GR1/human transfer. Video72giây/3D là minh họa thiết kế, chưa benchmark.

## Chi phí: giả định rõ, chưa ROI

Capacity-budget scenario pilot sim:20 accepted train roots/yield50% →40 attempts. 6 phút capture/reset→4 operator-h;3 phút QA→2 engineer-h. Giả định operator10 USD/h, engineer20 USD/h. 240 engineer-h integration/preparation/report chưa gồm2hQA này.

| Khoản | Cách tính | USD |
|---|---|---:|
| Thu/reset | 4 h×10 | 40,00 |
| QA attempts | 2 h×20 | 40,00 |
| Tích hợp/xử lý/báo cáo | 240 h×20 | 4.800,00 |
| GPU capacity cap | (train120+generation30+eval30)GPUh×1,59 | 286,20 |
| Storage | 100 GB×3 tháng×0,07 | 21,00 |
| **Phần đã tính** | **Chưa tổng triển khai** | **5.187,20** |

[Runpod Pods](https://www.runpod.io/pricing): A100PCIe80 GB1,59 USD/GPUh; network Standard dưới1TB0,07 USD/GB-tháng, kiểm 06/10/2026. Nhân công/yield/hours/caps là planning assumptions sửa được, không lương DENSO/VN. Cap chưa benchmark runtime/config fit; vượt cap replan. Chưa gồm robot/cell, CPU riêng, data/license fees, thuế, downtime/production. Real robot economics khác simulator capture.

FOCA AppendixD.3: DreamGen tuning28 h×8H100=224 GPUh; action-free15 h×4A100=60; robot18 h×4A100=72. Đây không cap A1 hoặc đủ mọi  video-generation cost. Bớt demos chưa tự tiết kiệm tổng công; actual ledger và cùng quality mới cho kết luận.

## Các giả định đã chọn cho MVP

Data organization/use/scale là **trọng tâm phù hợp project**, chưa được đo là bottleneck duy nhất/lớn nhất A1. Method/architecture/controller/latency quyết định data có train và execute được không; FOCA cho thấy training objectives vẫn quan trọng.

Ít nhưng chất lượng cần viết thành **ít robot roots hơn ở cùng quality, đủ coverage và tổng cost có ích**. Giảm redundancy khác giảm rare/recovery cases; nhãn sạch ở một scene vẫn thiếu generalization. Không có số mẫu tối thiểu phổ quát.

Flywheel mạnh khi decision-driven acquisition có lợi so reuse/basic augmentation/targeted correction phù hợp ở cùng constraints. Utility đo ở data-package/candidate qua holdout gain và cost, chưa model tự gán true value từng clip. Scale bằng versioned releases/capability/lineage/coverage; task2 mới đo reuse thực.

## Phạm vi, kế hoạch và bàn giao

A1 rigid pick-and-place là proxy công nghiệp, chưa DENSO task đã khảo sát hoặc chứng minh cần humanoid thay arm. Fixed torso/active arm/tolerance/cycle/acceptance cần owner và native profile chốt.8–12 tuần planning cho MVP robot+sim sau đủ people/GPU/checkpoint; human/video/real-deployment có gate/lịch riêng.

Bàn giao checkpoint+processor/normalization/binding; versioned data/rights/root splits; recipe/receipts; all traces/outcomes; SOP và quality–cost report. [Form draft](../deliverables/DENSO-Noi-dung-form-y-tuong.md).

## Pitch

Chúng tôi xây Data Core flywheel cho robot learning: từ lỗi có bằng chứng, xác định supervision cần, chọn data phù hợp, QA và đưa vào recipe có phạm vi, rồi đo toàn task và tổng công. MVP kế thừa pretrained VLA trên GR1 mô phỏng với robot demonstrations và sim executions; human motion/action-free video mở sau gate. Mục tiêu là dùng data có ích hơn để đạt cùng quality với ít công hơn; transfer và tiết kiệm còn phải kiểm chứng.
