# Nội dung đề xuất điền form DENSO

_Bản rà 06/10/2026; chưa gửi form. Native GR1/A1 data/training/savings còn ở mức đề xuất._

Tên ý tưởng: **Data Flywheel cho Robot Skill Learning — Dùng dữ liệu đúng để cải thiện kỹ năng với tổng công có thể kiểm chứng.**

## Danh mục quan tâm

Ưu tiên **Dữ liệu (Tạo giá trị tối đa từ dữ liệu)**. **Con người** là danh mục phụ khi đo được giảm công thu/kiểm/phân tích. Chưa có phép đo cho đúng hạn, năng lượng/carbon hay zero-defect.

## 1. Vấn đề bạn nhận thấy

Khi vật, vị trí, ánh sáng hoặc tiếp xúc thay đổi, phát triển kỹ năng robot có thể lặp lại thu mẫu, reset, QA, training và evaluation. Có thêm file chưa chắc có supervision dùng được: video người thiếu robot actions; tracking có nhãn mất; sim cần kiểm physics/readback; biến thể gần trùng chưa mở coverage cần.

Figure công bố Index 16 triệu video upload, 15 triệu USD trả creators và pipeline filtering/dedup/rebalance/annotation; payout chưa tổng cost dataset. FOCA LIBERO 40% demo (~20/task): π0 89,9%, FOCA+DreamGen 95,7%, cho thấy cách khai thác supervision có thể tạo khác biệt; robot adaptation vẫn dùng action labels. Đây là bằng chứng bên ngoài, chưa project result hoặc hiện trạng DENSO.

Điểm cần giải là **dữ liệu được chọn/tổ chức/sử dụng có ích ở nhiệm vụ đích và đáng công hơn**, với quality/cost truy vết được. Pilot GR1 gắp linh kiện vào A1 trong mô phỏng; cần owner xác nhận relevance, cost hiện trạng và lý do dùng humanoid ở công đoạn thực.

## 2. Giải pháp bạn đề xuất

### Mục đích của giải pháp

Xây Data Core flywheel: chạy/ghi trace → kiểm giả thuyết → chọn data/can thiệp → QA release → train có phạm vi + replay → đo full-task/regression/tổng công → giữ candidate có ích hoặc kiểm tiếp. Binding/controller faults sửa trước; hỗ trợ kỹ sư quyết định, chưa tự xác định nguyên nhân/retrain.

Mục tiêu là cùng quality với ít robot roots hoặc tổng công thấp hơn đối chứng. Ít mẫu phải đúng nhãn và đủ coverage; chưa hứa tỷ lệ tiết kiệm.

### Công nghệ sử dụng

Solution có **hai phần gắn với nhau**: Data Core cung cấp releases/targets/masks và quyết định acquisition; Model AI học representations/actions, cập nhật checkpoint và điều khiển robot. Chọn GR00T N1.5 qua FluxVLA: Eagle VLM + DiT Action Expert; không chỉ dashboard dữ liệu.

Kế thừa FluxVLA/pretrained GR00T N1.5/RoboCasa GR1 sau compatibility. Xây source adapters, capability loaders, versioned releases, root lineage/splits, action/physics QA, task binding/scorer và trace input–prediction–command–response–outcome.

Native route: current RGB/text→VLM features; current state/features + noisy future robot actions→Action Expert; flow objective cập nhật modules được mở. Selected Flux config visual tuning/LLM frozen cần pin/gradient check; không foundation VLM pretraining lại. H/video extensions có objectives và controls riêng.

### Dữ liệu đầu vào

1. Task/domain/acceptance/cost contract; camera/controller/robot profiles.
2. **Compatibility:** public `limxdynamics/FluxVLAData`, GR1 subset 24 tasks/720 episodes, LeRobotv2.1 MP4+Parquet+metadata. Preview RGB 256²/20fps, state/action 29D. Kiểm task/profile/adapter/recipe/binding; bottle-to-cabinet không đổi thành A1 labels. Parent rights và stale split metadata phải xử lý.
3. **R_A1 expert/correction, chưa thu:** draft 20 independent train seed roots. MP4, instruction JSONL, signals Parquet (state/action/timestamp), camera calibration, separate commands/readback và QA receipts. Development/final tách từ roots trước variants.
4. **S_exec từ R_A1, chưa sinh native:** transform train seeds→execute simulator/controller→log targets mới→QA→cùng robot action view. Synthetic là creation method. 100 variants từ 1 seed vẫn 1 root; appearance augmentation chỉ kế thừa labels khi bảo toàn semantics.
5. **Extensions có gate:** HumanEgo serve_bread preview RGB/wristCSV/confidence/geometry cho common-wrist pilot, chưa relevance/integration A1. Action-free video/DreamGen cho future-alignment pilot riêng; LIBERO kiểm phương pháp trên benchmark gốc, không trộn Panda7D vào GR1. Rights/relevance/geometry/recipe pass mới dùng.

Latent là output encoder có checkpoint/layer/shape/processor pin, có thể cache `.safetensors`; không nguồn data mới. Missing targets vô hiệu loss tương ứng, không gán zero giả.

### Dữ liệu đầu ra

Model output khi train: predicted flow velocity và candidate weights; khi inference: normalized action chunk. Binding đổi chunk thành issued commands, readback/scorer đo response/outcome. Những outputs này khác nhau; không coi feature vector là action hoặc command.

Dataset releases có QA/lineage/splits/capabilities; policy checkpoint+processor/normalization/binding; recipe manifests khai input/target/loss/trainable modules; traces/all outcomes; evidence/acquisition plans; report full-task/ID–OOD/regression/latency/unique roots và quality–cost.

Skill bundle sau nghiệm thu; native A1 chưa tạo. Reference MuJoCo nhỏ chỉ kiểm pipeline, không native policy evidence.

## 3. Quy trình thực hiện công việc

### Trước cải tiến

Đối chiếu đề xuất: định nghĩa task→thu/reset robot demos→QA/train→chạy thử→phân tích/thu thêm→học và thử lại. Chưa khẳng định đây là quy trình nhà máy DENSO. Thiếu lineage/cost/update scope thì khó biết gain đến từ data, extra compute hay đổi recipe.

### Sau cải tiến

**Bước 0:** pin checkpoint/source/profile; public GR1 sample kiểm decode/sync/stats/batch/gradients/reload/controller; chốt A1 feasible bằng expert.

**Bước 1:** thu R_A1 và khóa root splits. MP4→RGB, instruction→tokens, state→normalized state; future action chunks→noise/flow target. Native adaptation→baseline R.

**Bước 2:** targeted S_exec trong coverage còn yếu→execute→QA. R+S_exec+replay train cùng native recipe; so R trên development giữ riêng. Basic augmentation/targeted correction là đối chứng phù hợp khi kiểm acquisition.

**Bước 3 có gate:** Human pilot common wrists 18D từ human tracking và measured robot FK; R_common/R_common+H có VLM frozen giống nhau. H loss→human adapter/common head/shared motor trunk, không native decoder trực tiếp. Video pilot current/future frames→implicit alignment: generated-video phase không action loss, robot phase action+implicit. Hai pilots riêng, không bắt gộp đủ nguồn. DreamGen có thể tạo video offline; FOCA/FLARE học future representations; DreamZero/Dreamer là alternative stacks, chưa components bắt buộc ở MVP.

**Eval trước inference:** full-task/retention/transitions/ID–OOD/regression và tổng công. Robot runtime current camera/language/state/history→VLM→Action Expert→chunk→controller→readback/outcome, không future targets/scorer privileged state vào policy.

**Lỗi→vòng sau:** command sai mapping thì repair, không train. Controlled input/probe tests ủng hộ visual gap thì thử visual/interface update. Controller ổn nhưng thiếu grasp/retention supervision thì expert correction+replay và thử Action Expert post-training; kiểm transfer từ expert/policy grasp để tránh quy lỗi nhầm. QA release mới, tính actual cost; no-gain quay lại hypothesis trong cap, candidate đạt development mới freeze/final độc lập.

## 4. Hiệu quả mang lại

Kỳ vọng giảm công thu/reset/QA, xử lý data trùng/không dùng được và dùng lại release/adapter/QA/recipe cho skill 2. Chỉ xác nhận khi cùng quality; native saving/ROI chưa đo. Paper/company result không thay project benchmark.

Đo unique roots gồm development/correction data; operator/engineer/robot/GPU-hours, QA-yield/rejects/coverage, total cost tới quality threshold, success với CI, ID/OOD/intervention/latency/regression. Few-shot5/10/20 roots nếu đủ resources; variants/windows không independent demos.

**Ví dụ capacity budget pilot sim:5.187,20 USD cho phần đã tính.**20 accepted roots, yield50% →40 attempts;6 phút capture/reset→4 operator-h×10=40 USD;3 phút QA→2 engineer-h×20=40 USD;240 engineer-h integration/preparation/report×20=4.800 USD; cap 180 A100 GPUh×1,59=286,20 USD;100 GB×3 tháng×0,07=21 USD. Nhân công/yield/hours/caps là giả định sửa được, không quote/lương DENSO/VN hoặc runtime forecast. Giá Runpod Pods/Standard<1TB kiểm 06/10/2026. Chưa gồm robot/cell, CPU riêng, data/license fees, thuế/downtime/production; không saving. Actual ledger và replan quyết định spent thực.

## 5. Sự vượt trội/độc đáo của ý tưởng

Đóng góp dự kiến: **vòng quyết định dữ liệu kiểm được**, nối lỗi có trace→supervision cần→acquisition/reuse trong cap→release hợp lệ→update scope→outcome/cost. Phân biệt creation method/modality, targets/conditioning, integration fault/data hypothesis; lưu no-gain/negative cases để tránh update vô ích.

Không nhận human transfer/synthetic generation/flow matching là thuật toán mới. Superiority cần so reuse/basic augmentation/targeted correction phù hợp. Data organization/use là trọng tâm cần kiểm A1; architecture/controller/latency vẫn có thể bottleneck. Scale bằng lineage/coverage/releases và đo công reuse skill 2, không chỉ clips nhiều hơn.

## 6. Kế hoạch triển khai trong bao lâu

Planning 8–12 tuần cho MVP sim robot+S sau đủ people/GPU/checkpoint/task owner: (1)native feasibility/baseline; (2)data release+sim generation/QA; (3)trace/controlled diagnosis/acquisition/development contrasts; (4)freeze/final/report/skill bundle.2–3 tuần/chặng là giả định chưa lịch xác nhận; gate fail repair/rescope/replan.

Human/video pilots có lịch/budget riêng sau gate. Robot thật/production, defect/downtime benefits cần nghiệm thu riêng; không suy từ sim.

## Tải lên ý tưởng

PowerPoint hiện hành `DENSO-Humanoid-Data-Flywheel-2026.pptx` đã đồng bộ với nội dung website ngày 07/10/2026, gồm 21 slide và dưới 15MB. Chỉ giữ một bản PowerPoint hiện hành. Cần bổ sung tên đội, thành viên và task owner, rồi đối chiếu yêu cầu form trước nộp. Chưa gửi/tải form.

## Link liên quan

- [Repository project](https://github.com/hiwe0305/denso-challenge) — kiểm nội dung public trước link nộp; localhost không truy cập từ xa.
- [FOCA v1](https://arxiv.org/html/2606.20867v1), §5Q2/Table 2 và AppendixD.3.
- [Figure Index](https://www.figure.ai/news/introducing-index), [Helix 2.5](https://www.figure.ai/news/helix-2-5-zero-shot-30-home-generalization).
- [Runpod pricing](https://www.runpod.io/pricing), snapshot06/10/2026.
- [Video đã đối chiếu transcript/nguồn](https://www.youtube.com/watch?v=zKaeODg7xeE), chưa visual audit toàn video.

### Làm rõ lý do chọn engine

FluxVLA hỗ trợ training → evaluation → inference trên robot thật; Model Engine Core dùng framework này để nối dataset releases, pretrained GR00T N1.5 policy, checkpoint và robot runners/operators. Đội tích hợp A1 profile/scorer, QA/lineage, evidence và quality–cost gate để đóng data flywheel. Upstream hỗ trợ lifecycle chưa là native A1 đã chạy.
