# 08 · PoC 30 ngày: dữ liệu có sẵn trước, hướng tới robot thật

**Ưu tiên cập nhật 07/10/2026.** Đội xác nhận có RTX 3060 12GB và RTX 5090. Robot/camera/collector phụ thuộc BTC, chưa biết embodiment hoặc ngày tiếp cận. Mục tiêu là một model học task và chạy closed-loop ngoài đời, cùng một vòng data flywheel tối thiểu. Chưa có native training/rollout của đội.

## 1. Kết quả sau tháng đầu

Một dataset release đúng task, checkpoint fine-tune nạp lại được, evaluation trên môi trường tương ứng, trace lỗi và candidate sau data update. Đầu ra đích là video **robot thật** thực hiện task bằng policy học được, báo cáo mọi lượt thử và công đã dùng. Chỉ có sim thì ghi rõ hoàn thành phần sim, chưa đạt physical demo.

Phạm vi demo cuối: một embodiment, một task thao tác cứng, một miền khởi đầu đã khóa. GR1 public là tuyến kiểm pipeline ban đầu. Nếu robot BTC khác, không cam kết tái sử dụng checkpoint GR1 hoặc hoàn thành hai task trong tháng; demo cuối chốt một robot/task tương thích riêng. Task public ưu tiên `PnPBottleToCabinetClose` trong FluxVLAData/RoboCasa GR1, giữ đúng instruction và task scorer. Task gắp linh kiện vào A1 là **proxy thiết kế riêng**, không phải nhãn mới cho public episodes và chưa nằm trên đường bắt buộc tháng đầu. Nếu robot BTC khác GR1, phải chốt task/policy/dataset tương thích robot đó; thành công public GR1 không chứng minh chuyển embodiment.

## 2. Mapping lịch ba vòng

Nguồn: [website chính thức DENSO Factory Hacks 2026](https://densohackathon.vn/), kiểm 07/10/2026. Mốc công bố: nộp ý tưởng 12/10, đánh giá online 13–19/10, thuyết trình 16/11, chung kết 02/12. Không áp lịch 2025 sang 2026.

| Mốc chương trình | Nhóm cần trình bày | Trạng thái của mục tiêu |
|---|---|---|
| Hồ sơ/ý tưởng, hạn 12/10, xét 13–19/10 | Vấn đề, điểm nhấn data flywheel, pipeline, nguồn lực, task public, phụ thuộc robot và tiêu chí demo | Kế hoạch khả thi cần kiểm, chưa hứa kết quả |
| Thuyết trình 16/11 | PoC 30 ngày từ 13/10–11/11, buffer 12–15/11. Train/update/reload, eval, một vòng data update. Hướng tới physical demo nếu hardware gate đạt | Khuyến nghị của nhóm, không suy đây là yêu cầu bắt buộc của BTC |
| Chung kết 02/12 | Củng cố 17–29/11 theo phản hồi, thêm lần kiểm, hoàn thiện hardware còn thiếu và bằng chứng giá trị; nộp hồ sơ trước 23:59:59 ngày 30/11, chuẩn bị demo 01/12 | Không thêm một tháng sau thuyết trình; hạn nộp sớm hơn ngày thi |

13/10–11/11 gồm 30 ngày lịch tính cả hai đầu. Nếu đợi hết 19/10 mới bắt đầu 30 ngày, kết thúc 18/11, sau vòng thuyết trình. Vì thế cần phát triển song song trong thời gian chờ xét ý tưởng. Ngày robot được cấp có thể buộc đổi cam kết physical demo; mốc chương trình không tự bảo đảm thiết bị hoặc robot-compatible pretrained policy.

## 3. Bốn pipeline cần khóa

| Pipeline | Input và xử lý | Artifact / gate |
|---|---|---|
| P1 · Dataset → release | Public MP4 RGB + Parquet state/action/time + JSON/JSONL instructions/meta. Pin revision/rights, kiểm decode/sync/action semantics. Tách theo root/session và nhóm duplicate trước augmentation. | Release v1, split manifest, QA/rejects, processor/stats chỉ từ train khi cần. Metadata preview ghi train 0:100 nhưng folder chỉ có 30 episodes: không kế thừa split này. |
| P2 · Release → model học | Frames/text qua pretrained VLM thành features. State theo profile. Features/state/noisy future actions/time vào Action Expert, action targets tạo flow velocity loss. | Baseline/candidate checkpoint, modules/optimizer/gradient receipts, validation/reload. Ưu tiên ACT/adapters, backbone frozen khi recipe hỗ trợ; không mặc định LoRA hay visual freeze hoạt động trong mọi config. |
| P3 · Checkpoint → robot | Processor/stats + camera/state profile + inference runner tạo action chunks. Binding đổi units/order/limits thành commands, readback và quan sát mới đóng vòng. | Latency/parity trace và full-task rollout. Inference không nhận future labels hay scorer privileged state. Runtime lỗi phải sửa trước khi quy lỗi cho dữ liệu. |
| P4 · Lỗi → data → đo lại | Development trace, kiểm giả thuyết, chọn reuse/correction/augmentation đủ nhãn trong cap. Release v2, update cùng recipe với replay. | So parent/candidate trên development, regression và tổng công. No-gain giữ parent; freeze trước final riêng. |

**Data flywheel tối thiểu:** một decision receipt nối failure bucket với dữ liệu được chọn, lý do chưa chọn phương án khác, release ID, update scope và outcome/cost. Không cần xây platform phân tán hay hệ tự động chẩn đoán nguyên nhân trong tháng đầu.

## 4. Kịch bản dùng dữ liệu có sẵn khi chưa có robot

1. Pin `limxdynamics/FluxVLAData`, revision `7998ab57bc70be66234b5374800705e2b6c14545`, RoboCasa GR1 task folder nêu trên. Mẫu đã đọc có 30 episodes, RGB 256×256, 20fps, state/action 29D, LeRobot v2.1. Kiểm rights và instruction của từng episode trước run; 24 tasks/720 episodes là toàn subset, không số mẫu một task.
2. Chốt môi trường RoboCasa/task/controller/camera cùng profile dữ liệu và checkpoint, không ghép profile GR1 vào một arm. Tách train/development/final theo nguồn gốc/duplicate groups. Tỷ lệ phụ thuộc audit; không gọi các windows/variants là demonstrations độc lập.
3. Đo pretrained parent trước task fine-tune; từ train release học baseline rồi kiểm update/reload và task closed-loop ở sim giữ riêng. Loss/offline prediction chỉ là kiểm trung gian, chưa chứng minh task control.
4. Chọn một failure bucket trên development. Thử reuse/selection hoặc augmentation bảo toàn labels. Nếu cần correction mới mà chưa có robot, chỉ sinh sim execution khi task/controller/scorer và physics QA đã có; public failures không trở thành positive demonstrations. Giữ cùng recipe/cap hợp lý, cộng công bổ sung.
5. Baseline và candidate phải khóa trước final. Public-only đường này chứng minh feasibility trong sim và kiểm vòng dữ liệu ở đúng task, **chưa chứng minh inference ngoài đời hoặc lợi ích so với workflow thu dữ liệu thông thường**.

## 5. Robot BTC: nhánh chuyển sang thực tế

Ngay tuần 1 lấy robot model/SDK, gripper, action space/units/frequency, camera, quyền thu demos, lịch sử dụng và policy/runner tương thích. Đề nghị quyền truy cập chậm nhất tuần 2 là **giả định để còn thời gian tích hợp**, chưa cam kết hai tuần đủ cho thiết bị mới.

- Có robot/profile tương thích: kiểm controller/parity và teleop trước, thử policy parent, thu task demonstrations/corrections nếu cần. Pin real release/stats/profile riêng, fine-tune/reload và đo closed-loop vật lý.
- Robot khác public GR1: chọn robot-compatible policy/dataset/runner và adaptation plan. Không dùng GR1 29D/stats trực tiếp, không coi đổi tên config là retargeting. Có thể giữ Data Core/QA/trace/report, nhưng phần model binding phải kiểm lại.
- Chưa có thiết bị/collector, task expert chưa làm được hoặc recipe không chạy: báo phần đã đạt và điều kiện thiếu, rescope/date. Demo sim không được gọi là physical PoC. Giữ hardware integration là mục tiêu, không tự hạ cam kết mà không nói rõ.

## 6. Lịch bốn tuần và bằng chứng

| Mốc | Việc bắt buộc | Điều kiện tiếp tục / bàn giao |
|---|---|---|
| Tuần 1 · 13–19/10 | P1 + P2 smoke, pretrained baseline; khóa public task, robot request, code/checkpoint. Đo VRAM/throughput. | Batch/update/reload đúng. Cuối tuần khóa recipe khả thi và tình trạng hardware; chưa được thì repair/thu hẹp ngay. |
| Tuần 2 · 20–26/10 | Fine-tune public baseline, P3 sim/eval; tiếp cận bridge robot nếu có. | Checkpoint learned baseline, all-trial sim report. **26/10:** cần quyền truy cập robot, profile/task đã chốt, camera/controller đọc–ghi được và recipe tương thích đã update/reload để nhận mục tiêu physical demo trước 16/11; thiếu thì lịch vật lý tiếp tục có điều kiện. |
| Tuần 3 · 27/10–02/11 | Tích hợp/adapt robot đúng profile nếu có. P4 chọn một failure bucket, correction/reuse + replay. | Candidate, release v2 và development before/after. Nếu chưa đủ để chọn train scope thì kiểm tiếp, không gán nguyên nhân. |
| Tuần 4 · 03–09/11, chốt 10–11/11 | Freeze parent/candidate/checkpoint/profile/scorer. Final giữ riêng, báo cáo, video và gói nạp lại. | Ghi mọi fail/unknown/timeout/intervention. Hardware kết quả riêng; final không quay lại tune. |
| 12–15/11 | Buffer cho packaging và tập thuyết trình | Sửa kỹ thuật sau final nếu ảnh hưởng policy/profile phải chạy fresh final, không sửa rồi dùng kết quả cũ |

## 7. Ba mức bằng chứng

**A · Model học task:** có gradient/weights update, checkpoint nạp lại và full-task closed-loop trên starts giữ riêng, so pretrained parent với fine-tuned baseline. Pretrained đã làm tốt mà không gain thì không nhận năng lực sẵn có là do dữ liệu mới. Loss giảm/video playback không đủ.

**B · Model chạy ngoài đời:** cùng policy bundle tương thích tạo commands thật, nhận quan sát mới. Đề xuất small final **20 lượt cho mỗi baseline/candidate**, cùng danh sách starts giữ riêng, cân bằng thứ tự/reset. Gate PoC dự thảo candidate ≥16/20 successes không can thiệp trong timeout đã khóa; công bố độ bất định và toàn bộ failures. 16/20 là chỉ tiêu planning cần owner chốt, không bằng chứng true success ≥80% hay chuẩn sản xuất.

**C · Flywheel có ích:** ít nhất một vòng data update có trace và so sánh development/final riêng, kiểm regression và tổng công. Nếu no-gain thì pipeline có thể đã chạy nhưng giả thuyết utility chưa đạt. So workflow thông thường cùng cap, hoặc chứng minh cost saving/scale/skill 2, là nghiên cứu mở rộng; một before/after chưa đủ attribution.

## 8. GPU và chi phí

Thông tin người dùng: **RTX 3060 12GB + RTX 5090**. Phân công dự kiến 5090 cho smoke/fine-tune/inference, 3060 cho decode/QA hoặc model nhỏ khi đo fits. Chưa biết máy/driver/VRAM thực tế của 5090 hoặc khả năng truy cập từ runtime hiện tại. Không cộng VRAM hai card thành bộ nhớ một GPU và không mặc định distributed training giải quyết fits.

Tuần 1 đo batch 1 theo recipe đã chọn, trainable modules/dtype/views/horizon, peak train/infer VRAM, step time, checkpoint update/reload và latency. Pin CUDA/PyTorch/FlashAttention phù hợp mỗi GPU; chỉ dùng recipe/PEFT thực sự hỗ trợ. Full GR00T ACT+visual recipe cũ chưa được đo trên hai card này. Nếu không fits: giảm batch/views/horizon trong phạm vi semantic hợp lệ, đóng backbone, chọn policy nhỏ/compatible hoặc lập phương án compute khác. Đổi recipe phải ghi lại và so baseline/candidate cùng recipe.

Ledger tháng đầu ghi giờ người, capture/reset/QA, robot access, GPU/điện/thuê, storage/vật tư và retries. Chưa có đủ dữ kiện để chốt tiền/ROI. Ví dụ $5.187,20 trong hồ sơ cũ là **capacity budget sim dùng A100 thuê**, không là ngân sách hiện hành cho PoC dùng GPU sẵn có và robot BTC.

## 9. Sau PoC

Kế hoạch 8–12 tuần cũ dành cho nghiên cứu native A1/source comparisons mở rộng, cần lập lại theo kết quả PoC và lịch BTC. Human common-wrist, FOCA/action-free video, World Models, full-body/dexterity và skill 2 có gates/caps riêng. Phụ lục kỹ thuật cũ giữ làm thiết kế nghiên cứu; không phải mọi nhánh phải hoàn thành trước 16/11.

### Yêu cầu demo theo thể thức BTC

[Trang thể thức](https://densohackathon.vn/challenges), đọc trực tiếp 07/10/2026: vòng 2 yêu cầu video demo tối đa 15 phút và pitch, thể hiện input/output, environment, thiết bị, data/resource và quy trình xử lý. Vòng 3 ghi mentoring/phát triển 20/10–02/12, hạn nộp trước 23:59:59 ngày 30/11 và demo trực tiếp 02/12. Giai đoạn phát triển hiển thị chồng với vòng 2, không phải ba tháng nối tiếp. Nộp slide PPTX hoặc Canva công khai ở vòng 3. Chưa thấy yêu cầu mọi video vòng 2 bắt buộc phải là robot thật; đây là mục tiêu mạnh hơn do nhóm đề xuất, phụ thuộc BTC cấp thiết bị.
