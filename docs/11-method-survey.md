# 11 · Khảo sát phương pháp học từ dữ liệu đa nguồn

_Catalog gốc kiểm 02/10/2026; DataMIL và DAgger/PARTS/CR-DAgger bổ sung, kiểm 05/10/2026. Đây là kết quả/thiết kế của tác giả; không là kết quả của đội. P0/P1/P2 là ưu tiên MVP, không xếp hạng chất lượng công trình._

## Kết luận cho thiết kế

Human/video mở prior và coverage; bridge cần chọn theo tín hiệu. Synthetic có ba loại supervision khác nhau. Dữ liệu robot thật giữ vai trò học điều khiển, hiệu chuẩn, contact/recovery và đánh giá độc lập. FluxVLA có sẵn nhiều năng lực platform/SDG/HITL; đóng góp của đội phải đo ở recipe, binding, mixture và hiệu quả theo task, không chỉ wrapper.

Không đối chiếu success percentages giữa các paper như leaderboard: task, robot, splits và protocol khác nhau. HumanEgo có cấu hình robot-data-free; không nói mọi human-to-robot learning đều bắt buộc teleop. Thiết kế này chủ động dùng real-robot anchors.

## EgoVLA · 2025

Nguồn: [EgoVLA](https://rchalyang.github.io/EgoVLA/).

**Input:** Human ego + wrist/MANO; robot demos cho adaptation
**Cơ chế:** Học biểu diễn thao tác chung của cổ tay và bàn tay, rồi thích nghi sang humanoid bằng dữ liệu robot.
**Tận dụng:** Tham khảo wrist/hand masks, representation và retargeting. MVP chọn auxiliary human heads trên FluxVLA thay vì port toàn bộ EgoVLA/IsaacLab.
**Giới hạn:** Cần tracking và retargeting phù hợp. Demo trong benchmark là mô phỏng; port sang FluxVLA chưa được kiểm.
**Ưu tiên:** P1 · Tiền lệ structured human supervision; chưa port nguyên model

## HumanEgo · 2026

Nguồn: [HumanEgo](https://humanego-ai.github.io/).

**Input:** Human ego + hand–object geometry; cấu hình robot-data-free của tác giả
**Cơ chế:** Biểu diễn tương tác tay–vật và mục tiêu phụ giúp học policy từ thao tác người trong cấu hình được công bố.
**Tận dụng:** Mẫu Aria thực tế để kiểm geometry, confidence và missing signals; đối chiếu cách tận dụng một trajectory.
**Giới hạn:** Không tự suy chuyển sang humanoid/FluxVLA. Data CC BY-NC 4.0; code PolyForm Noncommercial. Cần quyền riêng cho triển khai thương mại.
**Ưu tiên:** P1 · nguồn và đối chiếu

## EgoScale · 2026

Nguồn: [EgoScale](https://research.nvidia.com/labs/gear/egoscale/).

**Input:** Human quy mô lớn → human–robot aligned data → downstream robot demos
**Cơ chế:** Tách pretraining, mid-training để nối embodiment và post-training theo task.
**Tận dụng:** Thiết kế staged learning và embodiment adapters; ưu tiên pretrained assets phù hợp.
**Giới hạn:** Không tái lập foundation pretraining trong 12 tuần. One-shot downstream không có nghĩa toàn bộ lịch sử huấn luyện không dùng robot.
**Ưu tiên:** P1 · kiến trúc tham khảo

## LAPA · 2024

Nguồn: [LAPA](https://latentactionpretraining.github.io/).

**Input:** Video không có robot-action labels; thêm robot-action finetuning
**Cơ chế:** Lượng tử hóa chuyển tiếp hình ảnh thành latent actions, pretrain VLA rồi thích nghi sang action của robot.
**Tận dụng:** Đường học cho internet/RGB-only nếu có pretrained components và objective tương thích.
**Giới hạn:** Latent token không phải lệnh khớp. Chuyển động camera có thể lẫn với thao tác; train quantizer và VLA từ đầu vượt MVP.
**Ưu tiên:** P1 · route thay thế

## MimicGen · 2023

Nguồn: [MimicGen](https://mimicgen.github.io/).

**Input:** Seed demos + object frames + physics simulator/controller
**Cơ chế:** Chia demo thành đoạn, biến đổi quỹ đạo theo vị trí vật, thực thi trong sim rồi lọc theo kết quả.
**Tận dụng:** Tạo biến thể vật/vị trí với actions và outcomes được thực thi. Ưu tiên nếu simulator đích hỗ trợ.
**Giới hạn:** Cần subtask, object frames và controller đúng. Các video tham khảo dùng robot arms; chưa là triển khai humanoid của đội.
**Ưu tiên:** P2 · Physics branch sau fidelity/controller/scorer gate

## Cosmos-Transfer2.5 · 2025–2026

Nguồn: [Cosmos-Transfer2.5](https://docs.nvidia.com/cosmos/latest/transfer2.5/index.html).

**Input:** Video + điều kiện depth/segmentation/edges
**Cơ chế:** Biến đổi bối cảnh và hình thức video với điều kiện hình học; giúp đa dạng hình ảnh quan sát.
**Tận dụng:** RGB/depth/segmentation controls của train trajectories để tạo biến thể hình ảnh; QA geometry/timing và action semantics trước kế thừa labels.
**Giới hạn:** Không tự tạo action ground truth. Hình ảnh có thể thay đổi vật/contact. Cosmos 3 là tiến bộ 2026, chưa là lựa chọn đã tích hợp.
**Ưu tiên:** P1 · Sau basic augmentation và condition/QA/cost gate; không bắt mọi recipe dùng

## DreamGen · 2025

Nguồn: [DreamGen](https://research.nvidia.com/labs/gear/dreamgen/).

**Input:** Robot-conditioned video model + IDM hoặc latent actions
**Cơ chế:** Sinh video thao tác ở điều kiện mới, ước lượng pseudo-actions, dùng chúng để huấn luyện policy.
**Tận dụng:** Nhánh world-model mở rộng coverage; minh họa riêng video được sinh và robot thực thi sau học.
**Giới hạn:** Video đẹp chưa là trajectory khả thi. Pseudo-actions cần provenance/QA; finetuning generation và IDM có thêm compute/data.
**Ưu tiên:** P2 · sau E1/E2

## DreamZero · 2026

Nguồn: [DreamZero](https://dreamzero0.github.io/).

**Input:** Video/action để học World Action Model; video-only transfer trong protocol riêng
**Cơ chế:** Học và sinh video cùng hành động, dùng prior vật lý/thị giác để điều khiển và thích nghi embodiment.
**Tận dụng:** Tham khảo hướng world-action dài hạn và phân biệt predicted future với executed outcome.
**Giới hạn:** Mô hình 14B và hệ thống suy luận tối ưu của tác giả vượt giả định RTX 3060. Không mặc định adapter FluxVLA hỗ trợ.
**Ưu tiên:** P2 · tầm nhìn

## GRAIL · 2026

Nguồn: [GRAIL](https://research.nvidia.com/labs/dair/grail/).

**Input:** 3D scene + generated human video + metric 4D reconstruction
**Cơ chế:** Tái dựng tương tác người–vật có hình học, retarget và học robot tracking để thực hiện.
**Tận dụng:** Ví dụ synthetic có cấu trúc và bước kiểm thực thi, thay vì chỉ tăng số video.
**Giới hạn:** Loco-manipulation và stack geometry/tracking phức tạp hơn upper-body MVP; không đưa full-body vào critical path.
**Ưu tiên:** P2 · mở rộng

## GR00T 1.7 · 2026

Nguồn: [GR00T 1.7](https://developer.nvidia.com/blog/develop-humanoid-robot-policies-end-to-end-with-nvidia-isaac-gr00t/).

**Input:** Foundation policy học real robot, human ego và simulation; robot post-training
**Cơ chế:** Tận dụng prior đa nguồn rồi post-train cho robot/task cụ thể trong hệ sinh thái NVIDIA.
**Tận dụng:** Ứng viên checkpoint và recipe. Ghi rõ lịch sử pretraining khi thiết kế comparator.
**Giới hạn:** Checkpoint 3B không bảo đảm training trên 12GB. Ví dụ tutorial G1 apple/plate là simulation; chưa chứng minh hỗ trợ FluxVLA.
**Ưu tiên:** P1 · N1.7 khảo sát; main chọn N1.5/GR1 vì config upstream

## DROID · 2024

Nguồn: [DROID](https://droid-dataset.github.io/).

**Input:** Real robot observations, state/action, language ở nhiều môi trường
**Cơ chế:** Thu robot data phân tán để mở rộng độ đa dạng thực tế và hỗ trợ robot learning.
**Tận dụng:** Chuẩn collection và nguồn compatible subset; phản biện giả định robot data luôn ít đa dạng.
**Giới hạn:** Embodiment robot arm khác target humanoid. Dữ liệu công khai không thay teleop của robot đích hoặc chi phí thu tại DENSO.
**Ưu tiên:** P1 · tham khảo collection

## FluxVLA · 2026

Nguồn: [FluxVLA](https://github.com/FluxVLA/FluxVLA).

**Input:** Dataset/model recipes, training/evaluation, SDG và human corrections
**Cơ chế:** Engine kỹ thuật để tổ chức data, training, inference và đánh giá robot policies.
**Tận dụng:** Robot-action path và RoboCasa GR1/config công khai; đội xây source adapters/auxiliary heads, task wrapper và source-choice experiment.
**Giới hạn:** FluxVLA có SDG/HITL/mixtures nên wrapper không là novelty. Task khay, custom losses và closed-loop của đội chưa pass E0.
**Ưu tiên:** P0 · Engine; GR00T N1.5/GR1 là đường chính

## DataMIL · 2025

Nguồn: [DataMIL](https://arxiv.org/html/2505.09603v1).

**Input:** Dữ liệu robot ngoài domain và tập target-domain; selection prior art, không human-to-robot recipe của đội.
**Cơ chế:** Chọn dữ liệu imitation learning qua bi-level optimization và influence estimation theo target domain.
**Tận dụng:** Thiết kế comparator selection; tránh nhận chọn dữ liệu là first-ever. Đội tập trung condition, acquisition package và tổng công tới acceptance.
**Giới hạn:** Paper ghi selection thêm compute đáng kể; không suy method này tự chọn gói chưa thu hoặc chắc giảm chi phí task khay.
**Ưu tiên:** P0 · prior art và cost/selection controls; không bắt buộc tích hợp method.

## DAgger · 2011

Nguồn: [DAgger](https://proceedings.mlr.press/v15/ross11a.html).

**Input:** Policy-induced observations và expert action labels
**Cơ chế:** Thu labels tại states do policy gây ra, tổng hợp dữ liệu qua các vòng imitation learning.
**Tận dụng:** Correction gần rollout states; giữ failed actions và expert-corrected targets riêng.
**Giới hạn:** Expert availability/action compatibility và collection cost; không tự diagnosis, không bằng chứng saving của GR1 proposal.
**Ưu tiên:** P0 · cơ sở collection targeted; không cần port nguyên algorithm trước MVP

## PARTS · v2 · 2026

Nguồn: [PARTS · v2](https://arxiv.org/html/2609.21788v2).

**Input:** Task-specific base policy, local contracts/selectors/verifiers và robot rollout
**Cơ chế:** Luyện residual RL ở bottleneck với local outcomes; kiểm readiness và full-task execution.
**Tận dụng:** Thiết kế local probes, preconditions/readiness và natural/restaged entry tests.
**Giới hạn:** Paper v2 §I/III đọc; chưa port pi0.5/residual RL sang GR00T/GR1; reset/verifier/base là điều kiện, không auto fix mọi task.
**Ưu tiên:** P0 · thiết kế diagnosis/protocol; residual RL P2 sau gate

## Compliant Residual DAgger · 2025

Nguồn: [Compliant Residual DAgger](https://compliant-residual-dagger.github.io/).

**Input:** Base policy, human delta corrections, force feedback/control
**Cơ chế:** Correction interface và residual learner cho contact-rich tasks; phân biệt correction với fine-tune base.
**Tận dụng:** QA takeover/action authority, state distribution và continuity; teacher action labels cho corrections.
**Giới hạn:** Force/controller/action composition phụ thuộc robot; chưa GR1 integration, không chuyển kết quả tác giả thành evidence đội.
**Ưu tiên:** P1 · collection QA; residual controller/learner P2

## Chọn đường trong ba tháng

P0: FluxVLA/GR00T N1.5/GR1 robot baseline và E4 T/F/A từ parent R0. P1: human/video heads, source-drop, compute control và Cosmos-vs-basic sau gate. P2: physics/world-model generation, full-body geometry và WAM. Không train foundation models từ đầu.

MVP chọn robot baseline trên FluxVLA/GR00T N1.5/GR1 trước; auxiliary stage/order/wrist heads có gate signals/rights/E0 riêng. Bốn nguồn là catalog, không mandatory recipe. E0/D0 và E1 tạo useful parent trước E4; core15 conditional: 6 R0 +9 T/F/A; bootstrap/extra jobs replan, extension tối đa12. DataMIL là prior art về selection; selection/QA compute và engineer hours phải tính vào total cost.

[Learning Core](04-learning-core.md) · [Protocol](06-validation-and-roadmap.md) · [Mẫu dữ liệu](12-public-data-examples.md).
