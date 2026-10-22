# Data flywheel: định nghĩa, paper robotics và hạ tầng

_Tổng hợp ngày 22/10/2026 để thảo luận định vị của [spec v10.1](../spec-v10-failure-to-data.md). Số liệu là kết quả tác giả báo trong abstract hoặc trang dự án, chưa đọc toàn văn và chưa kiểm lại; không phải kết quả của đội._

## 1. Định nghĩa của NVIDIA

Nguồn: [NVIDIA Glossary: Data Flywheel](https://www.nvidia.com/en-us/glossary/data-flywheel/).

Data flywheel là vòng tự cải thiện: dữ liệu sinh ra khi AI vận hành được dùng để tinh chỉnh model, model tốt hơn cho kết quả tốt hơn và dữ liệu giá trị hơn cho vòng sau. Trang nhắm vào AI agent và LLM trong doanh nghiệp; bộ công cụ đi kèm là NeMo (Curator, Customizer, Evaluator, Guardrails, Retriever), NIM và AI Data Flywheel Blueprint.

| # | Bước theo NVIDIA | Nội dung | Tương ứng trong thiết kế của đội |
|---|---|---|---|
| 1 | Data processing | Trích xuất, lọc nhiễu, PII, nội dung độc hại, curate | `catalog`, `qa` (7 phép kiểm), lineage |
| 2 | Model customization | DAPT, LoRA, SFT | `training`: fine-tune từ cha, có replay |
| 3 | Model evaluation | Kiểm theo yêu cầu ứng dụng; lặp 1–3 tới khi đạt | `runner`, `scorer`, `gate` |
| 4 | Guardrails | Quyền riêng tư, bảo mật, an toàn khi tương tác | Không có tương đương trực tiếp; "kiểm hệ thống trước" và vault holdout bảo vệ tính đúng của kết luận, không phải an toàn |
| 5 | Custom model deployment | Deploy, RAG cho ngữ cảnh mới | L0 chỉ chạy trong sim; deploy thật thuộc L2 |
| 6 | Enterprise data refinement | Log suy luận, feedback người và AI quay về bước 1 | `diagnosis`, `decide`, `acquisition`: lõi Failure → Data |

Bốn khó khăn trang nêu và chỗ thiết kế của đội trả lời:

| Khó khăn | Trong thiết kế |
|---|---|
| Thiếu log và feedback tập trung | Catalog 12 bảng, ledger append-only |
| Tập đánh giá không đại diện | Tập cổng mới mỗi vòng, holdout niêm phong |
| Feedback mất dần giá trị | Tỉ lệ sửa được f_t cập nhật có đối chứng |
| Công người tốn kém | Giả thuyết HD, evidence card |

**Khác biệt quan trọng.** Với LLM agent, dữ liệu tự chảy về từ lưu lượng sản phẩm và gần như miễn phí; mục tiêu chính là chưng cất sang model nhỏ để giảm TCO. Với robot, mỗi mẫu tốn phút người hoặc GPU-giờ, nên câu hỏi trung tâm là **thu dữ liệu nào tiếp theo**. NVIDIA cũng khuyên tập trung vào dữ liệu "high-signal" (dự đoán sai, độ tin thấp), cùng tinh thần với Failure → Data.

## 2. Paper data flywheel cho robotics

Chia theo cách vòng lấy dữ liệu mới.

### 2.1 Nhóm A: deploy là thu dữ liệu

| Paper | Ngày | Vòng lặp | Kết quả tác giả báo |
|---|---|---|---|
| [Robot-Powered Data Flywheels](https://arxiv.org/abs/2511.19647) (Grannen, Pan, Llontop, Ho, Zolotas, Bohg, Sadigh) | 11/2025 | Robot Scanford làm việc thật trong thư viện 2 tuần, dùng catalog thư viện tự gán nhãn ảnh, fine-tune VLM, deploy lại | Nhận diện sách 32,0% → 71,8%; OCR tiếng Anh 24,8% → 46,6%, tiếng Trung 30,8% → 38,0%; 2.103 kệ; tiết kiệm khoảng 18,7 giờ người |
| AutoRT (Google DeepMind, arXiv 2401.12963) | 2024 | Foundation model đề xuất task và điều phối đội robot ngoài thực tế để thu dữ liệu quy mô lớn | Không kiểm số trong đợt này |
| Sirius: Robot Learning on the Job (arXiv 2211.08416) | 2022 | Người can thiệp khi robot đang deploy; đoạn can thiệp được dùng làm dữ liệu train | Không kiểm số trong đợt này |

Gần định nghĩa NVIDIA nhất: dữ liệu là sản phẩm phụ của việc robot làm việc có ích.

### 2.2 Nhóm B: học từ rollout của chính mình, kể cả lượt lỗi

| Paper | Ngày | Cách dùng dữ liệu lỗi | Kết quả tác giả báo |
|---|---|---|---|
| [π\*0.6, RECAP](https://pi.website/blog/pistar06) (Physical Intelligence, arXiv 2511.14759) | 11/2025 | Demo, correction của người và trải nghiệm tự động; policy điều kiện hóa theo advantage | Throughput tăng hơn 2 lần, tỉ lệ lỗi giảm 2 lần trở lên ở một số task khó (số của công ty) |
| [Learning While Deploying](https://arxiv.org/abs/2605.00416) (Wang và cộng sự, Luo) | 5/2026 | Offline-to-online RL trên rollout tự động và can thiệp của người từ cả đội robot; DIVL cho value, QAM cho policy flow | 16 robot hai tay, 8 task thật, trung bình 95%; lợi nhiều nhất ở task dài 3–5 phút |
| [LoopWAM](https://arxiv.org/abs/2610.18873) (Guo và cộng sự, Lu) | 10/2026 | World-action model giữ giám sát video trên mọi lượt, giám sát action có trọng số theo chất lượng | Table30-V2: 23,67% → 43,33% sau 3 vòng; gấp áo 13,20% → 55,56% sau 2 vòng |
| [Robo-COP](https://arxiv.org/abs/2610.09228) | 10/2026 | Đồng tiến hóa VLM điều phối và policy qua deploy | Held-out 38,3% → 50,0% |

### 2.3 Nhóm C: sinh dữ liệu bằng sim hoặc generative

| Paper | Ngày | Vòng lặp | Kết quả tác giả báo |
|---|---|---|---|
| [DexFlyWheel](https://arxiv.org/abs/2509.23829) (NeurIPS 2025) | 9/2025 | Từ 1 demo người mỗi task: IL → residual RL → rollout → augment cảnh → vòng sau | Hơn 2.000 demo trên hơn 500 cảnh; 81,9% trên tập thử; 78,3% nâng hai tay ngoài đời qua digital twin |
| [MimicGen](https://arxiv.org/abs/2310.17596) | 2023 | Biến đổi đoạn demo theo tư thế vật để nhân demo | Dùng trong tuyến T2 của spec |
| DreamGen (PDF trong `papers/`) | 2025 | Video world model sinh quỹ đạo mới | Hướng mở rộng sau PoC |

### 2.4 Nhóm D: chọn dữ liệu cần thu (nhóm của thiết kế Failure → Data)

| Paper | Ngày | Ý chính | Kết quả tác giả báo | Liên quan tới spec |
|---|---|---|---|---|
| [Mulligan](https://arxiv.org/abs/2610.05882) (Ankile, Dong, Bhowmik, Muppidi, Yuan, Song, Finn) | 10/2026 | Coi phân phối trạng thái đầu là quyết định: mỗi vòng bắt đầu ở lỗi đã thấy và trạng thái chưa thử; value function train trên mọi dữ liệu, kể cả lỗi | Thắng lấy mẫu đều ở cùng ngân sách thu; HiL-IDQL+Mulligan +10 đến +34 điểm % trên task thật; 2.550 episode held-out, đánh giá mù | Tiền lệ trực tiếp của HT và nhánh B-fail; dùng dữ liệu lỗi để train là hướng L1 của spec |
| [DISEIL](https://arxiv.org/abs/2609.08123) (Khanal, Kumar A V, Rana) | 9/2026 | Đánh dấu điểm policy bắt đầu không tin cậy, gom lỗi thành chế độ lỗi, VLM và LLM viết yêu cầu demo, kiểm khả thi bằng kho ràng buộc trước khi tốn công expert | Cao nhất ở 10/10 setting (1 hòa), lợi nhiều nhất ở ngân sách nhỏ; chỉ 1 vòng, trong sim, expert phần lớn là script | Gần với bước 3 (gom cụm) và bước 5 (kiểm khả thi) |
| [Human-Robot Copilot](https://arxiv.org/abs/2604.03613) | 4/2026 | Tìm điều kiện lỗi của policy gốc rồi thu demo nhắm vào đó | Nhiều lỗi bất ngờ; tác giả cho rằng augment mù không đủ | Ủng hộ bước chẩn đoán |
| [F-ACIL: Towards Generalizable Robotic Data Flywheel](https://arxiv.org/abs/2603.25583) (Xiao, Zhou, Wang, Ou, Liu) | 3/2026 | Phân rã phân phối dữ liệu theo yếu tố (vật, hành động, môi trường), thu theo từng yếu tố, train lặp để tổng quát tổ hợp | Hơn 45% lợi ích với số demo ít hơn 5–10 lần | Gợi ý phân rã vector điều kiện c cho phép kiểm vùng phủ và NGOÀI MIỀN |
| [So You Think You Can Scale Up Autonomous Robot Data Collection?](https://arxiv.org/abs/2411.01813) (Mirchandani, Belkhale, Hejna, Choi, Islam, Sadigh; CoRL 2024) | 11/2024 | Kiểm thu dữ liệu tự động bắt đầu từ bộ demo người | **Kết quả âm:** thu tự động giúp vừa phải; thu thêm dữ liệu người thường giúp nhiều hơn hẳn; tốn công thiết kế môi trường | Bằng chứng ngược chiều cho HS, cần nêu trong rủi ro |

Một kết quả tìm kiếm gán cho paper Mirchandani phát hiện "demo người gần điểm lỗi tốt hơn demo ngẫu nhiên"; trang abstract không nhắc tới, chưa xác nhận.

### 2.5 Survey

- [Data Pyramid for Embodied Manipulation](https://arxiv.org/abs/2607.24744) (7/2026): dữ liệu robot hiện thiên về demo thành công; lượt lỗi, gần lỗi và kém tối ưu thường bị bỏ.
- [Self-Evolving AI for Humanoids](https://arxiv.org/abs/2609.13236) (9/2026): cơ chế, an toàn và đánh giá tự cải thiện sau deploy cho humanoid; nhắc HOMIE (teleop toàn thân bằng exoskeleton kèm policy RL) làm điểm khởi đầu vòng.
- [Self-Improvements in Modern Agentic Systems](https://arxiv.org/abs/2607.13104) (7/2026).

## 3. Thiết kế của đội đứng ở đâu

Failure → Data thuộc nhóm D, dùng nhóm C (sinh sim) làm một loại can thiệp. Ba điểm mà các paper trên chưa gộp:

1. **Tách lỗi hệ thống khỏi lỗi dữ liệu** trước khi chi tiền (controller WBC, đồng bộ cảm biến, calibration, độ trễ). Mulligan và DISEIL mặc định lỗi là do thiếu dữ liệu.
2. **Chọn giữa nhiều loại can thiệp theo chi phí thật**, có sổ chi phí gồm cả chi phí chẩn đoán. DISEIL chỉ có một loại là demo expert.
3. **Đo tỉ lệ sửa được có đối chứng với policy cha** và dùng nó cho vòng sau.

Spec đã định vị HT là kiểm lại kết quả kiểu Mulligan / DISEIL, không phải điểm mới (spec mục 1.2). Phần trên củng cố định vị đó.

## 4. Câu hỏi mở cho thảo luận

| # | Câu hỏi | Vì sao |
|---|---|---|
| D1 | Có gọi là "flywheel" ở L0 không, hay "failure-driven acquisition loop"? | NVIDIA định nghĩa flywheel quay nhờ dữ liệu deploy; L0 chạy trong sim và Ψ₀ chỉ 1 vòng |
| D2 | Có kéo "dùng dữ liệu lỗi để train" từ L1 vào PoC không? | Mulligan, LoopWAM, RECAP, LWD đều làm; mentor dễ hỏi |
| D3 | Có phân rã vector điều kiện c theo yếu tố như F-ACIL không? | Làm rõ phép kiểm vùng phủ và luật NGOÀI MIỀN |
| D4 | Có thêm bước "deploy" nào ở L0 để khớp 6 bước của NVIDIA không? | Ví dụ rollout liên tục trên tập dev mới như một "deploy trong sim" |
| D5 | Trả lời kết quả âm của Mirchandani thế nào trong pitch? | Là bằng chứng ngược chiều cho HS |

## 5. Hạ tầng: NVIDIA OSMO

Nguồn: [trang sản phẩm](https://developer.nvidia.com/osmo), [user guide](https://nvidia.github.io/OSMO/main/user_guide/index.html), [GitHub NVIDIA/OSMO](https://github.com/NVIDIA/OSMO). Kiểm ngày 22/10/2026.

### 5.1 OSMO là gì

Bộ điều phối workflow mã nguồn mở (Apache-2.0 theo trang GitHub) cho physical AI. Một file YAML mô tả cả pipeline: sinh dữ liệu tổng hợp, train, RL, đánh giá trong sim, kiểm software-in-the-loop và hardware-in-the-loop. OSMO lập lịch các task lên phần cứng khác nhau và tự giải phụ thuộc.

- **"Three Computer Problem":** robotics cần GPU train (GB200, H100), máy sim (RTX PRO 6000) và thiết bị edge (Jetson AGX Thor); OSMO điều phối cả ba trong một workflow.
- **Nền:** chạy trên Kubernetes bất kỳ (EKS, AKS, GKE, on-prem, air-gapped), người dùng không viết manifest. Bản cục bộ chạy bằng Docker và KIND. Lưu trữ là object store tương thích S3, GCS hoặc Azure Blob.
- **Dữ liệu:** trang sản phẩm nêu dataset địa chỉ hóa theo nội dung, có phiên bản, lineage, khử trùng lặp. Mỗi task đọc `/osmo/input/` và ghi `/osmo/output/`; YAML dùng token `{{input:N}}`, `{{output}}`, `{{workflow_id}}`.
- **Tương tác:** VSCode, Jupyter, SSH, exec, port-forward, rsync vào task đang chạy.
- **Agent:** CLI kèm tệp ngữ cảnh cho coding agent và MCP; repo có `AGENTS.md`, `CLAUDE.md`.
- **Cookbook:** Isaac Sim SDG, RL, train, notebook Isaac GR00T, ROS 2, HIL.
- **Không làm** (theo trang sản phẩm): không deploy model lên robot production; không phải nền MLOps, không có dashboard thí nghiệm hay artifact registry. Định vị là thay SLURM cho workload physical AI.

Cấu trúc YAML (rút gọn từ trang Workflow Specification):

```yaml
workflow:
  name: train-policy
  pool: my-pool
  groups:
    - name: train-group
      tasks:
        - name: train
          lead: true
          image: <image>
          command: [bash]
          args: [-lc, "..."]
          resource: default
          inputs: []
          outputs: []
```

### 5.2 Đối chiếu với kiến trúc L0

| OSMO | Trong [03-architecture](../product/03-architecture.md) |
|---|---|
| Workflow YAML | RunPlan đóng băng cộng job spec JSON |
| Task, group | Thư mục `runs/<run_plan_id>/<job_id>/` |
| Pool, platform | Bảng máy ở mục 2.1: 5090, 3060, A100 thuê |
| Inputs, outputs qua object store | Thư mục staging dùng chung, rsync với máy A100 |
| Dataset có phiên bản, lineage | `catalog` và `store` (sha256, release đóng băng) |
| Lập lịch song song | `concurrent.futures` trên W container SIMPLE; Ray dự kiến ở L1 |
| HIL trên Jetson | L2 robot thật |
| Không có | Scorer, chẩn đoán, `decide`, ledger chi phí, gate, holdout |

**Nhận định:** OSMO thay được lớp thực thi (chạy job, chuyển dữ liệu giữa máy, lập lịch GPU), không thay lõi flywheel. Ở L0 nó đi ngược nguyên tắc L0-lite (không dịch vụ, không Kubernetes, đĩa cục bộ) và thêm việc cho đội đang quá tải. Hợp lý hơn là để ở L1: thêm một executor gửi job sang OSMO thay cho `docker compose run`, và giữ catalog và ledger làm nguồn sự thật. Trong pitch có thể nêu OSMO là đường mở rộng L1–L3 thuộc hệ sinh thái NVIDIA.

Cần kiểm trước khi dùng: phiên bản phát hành hiện hành (docs có nhánh 6.0–6.3), yêu cầu GPU của bản KIND cục bộ, cách nối với máy A100 thuê theo giờ không có Kubernetes, và tính năng dataset nằm trong bản mã nguồn mở hay chỉ trong bản managed.
