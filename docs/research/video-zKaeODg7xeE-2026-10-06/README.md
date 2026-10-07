# Đối chiếu paper, số liệu và tin tức trong video zKaeODg7xeE

Ngày rà soát: **06/10/2026**. Video: [Faster Than Usain Bolt, Can't Tidy a Room: Why Robot Companies Clean Your Home for Free](https://www.youtube.com/watch?v=zKaeODg7xeE), kênh AI Automate with Shek, đăng 29/09/2026, dài 19:18. Mô tả dẫn tới [bản gốc tiếng Quảng Đông](https://www.youtube.com/watch?v=MALP_SwIKhU).

Phương pháp: đọc toàn bộ phụ đề tiếng Anh tự động và mô tả; truy nguồn từng nhóm phát biểu; ưu tiên paper, tài liệu thử nghiệm, thông báo và điều khoản gốc. Mốc thời gian dưới đây xấp xỉ theo phụ đề. Chưa phân tích trực tiếp toàn bộ hình ảnh trong video, chưa tái lập thí nghiệm của các nhóm nghiên cứu.

**Kết luận:** video có nguồn hỗ trợ hướng tận dụng human video và simulation cho robot learning. Tuy nhiên, nó ghép kết quả nghiên cứu, công bố doanh nghiệp, tin tức và dự báo vào cùng một câu chuyện. Mỗi loại có giá trị chứng minh khác nhau. Chưa thể lấy các số liệu này làm kết quả hoặc mức tiết kiệm của project chúng ta.

## 1. Những paper thực sự liên quan

| Tài liệu | Quan hệ với video | Nội dung nên đọc | Giới hạn khi viện dẫn |
|---|---|---|---|
| [AgiBot World Colosseo: A Large-scale Manipulation Platform for Scalable and Intelligent Embodied Systems](https://arxiv.org/abs/2503.06669v4), arXiv v4, 04/08/2025 | Paper của dataset được nhắc khoảng 4:49 | [§III](https://arxiv.org/html/2503.06669v4): 1.001.552 trajectories, 2.976,4 giờ, 217 tasks, 87 skills, 106 scenes; quy trình teleoperation và QA. §IV giới thiệu GO-1 dùng latent action representations. | Đây là robot trajectories có action/state, không tương đương cùng số video người. Khoảng 1% có failure/recovery; việc chứa lỗi không tự xác định nguyên nhân lỗi. |
| [BEHAVIOR-1K: A Human-Centered, Embodied AI Benchmark with 1,000 Everyday Activities and Realistic Simulation](https://arxiv.org/abs/2403.09227), 14/03/2024 | Nền tảng benchmark được nhắc khoảng 12:12 | Định nghĩa hoạt động dài trong môi trường mô phỏng OmniGibson. [Challenge 2025](https://behavior.stanford.edu/challenge/archive/2025/call_for_participation.html) dùng 50 tasks, 10.000 expert demos, hơn 1.200 giờ. | Con số 12,4% thuộc kết quả challenge 2025 được Stanford tổng hợp năm 2026; không phải kết quả của toàn bộ 1.000 hoạt động trong paper. |
| [Task adaptation of Vision-Language-Action model: 1st Place Solution for the 2025 BEHAVIOR Challenge](https://arxiv.org/abs/2512.06951v2), v2, 21/12/2025 | Paper bổ sung để hiểu hệ thống đứng đầu; video không nêu tên paper này | Dựa trên π0.5: correlated flow-matching noise, mixed-layer attention, System 2 stage tracking, action compression và correction rules. Báo cáo khoảng 26% Q-score trên 50 tasks. | Q-score chấm cả tiến độ một phần; không được gọi 26% là tỷ lệ hoàn thành toàn bộ task. Correction rules riêng challenge cần được công bố khi so sánh. |

Các bản arXiv là tài liệu nghiên cứu công khai; không mặc định mọi bản đã qua phản biện chỉ vì có mã arXiv. Kết quả trên robot, embodiment, task và protocol này không tự chuyển thành kết quả cho GR1 hoặc robot target của project.

## 2. Các công bố kỹ thuật quan trọng nhưng không phải paper

### Figure Index và Helix 2.5

[Introducing Index](https://www.figure.ai/news/introducing-index), 25/08/2026: Figure công bố hơn **16 triệu video được upload**, **15 triệu USD** trả cho creators. Có lọc, kiểm tra gian lận, loại trùng và annotation. Upload chưa tương đương mẫu robot training hợp lệ.

[Helix 2.5: Zero-Shot 30-Home Generalization](https://www.figure.ai/news/helix-2-5-zero-shot-30-home-generalization), **17/09/2026**: ba việc nhà, 30 nhà chưa thấy; Index pretraining nâng whole-task success **9% → 56%**, giữ downstream robot data và cấu hình cố định. Zero-shot áp dụng cho nhà/đồ vật, vẫn fine-tune task bằng dữ liệu robot ở nơi khác. So sánh dùng nửa adaptation data là thí nghiệm khác. Bài chưa công bố đủ human-to-robot targets/loss/adapters để tái lập.

### World Labs: real-to-sim-to-real

[Building Worlds That Train Robots](https://www.worldlabs.ai/blog/real-to-sim-to-real), 28/07/2026: policy học hoàn toàn trong simulation; một số task chạy robot thật một giờ không can thiệp. Cube-handover đánh giá mỗi checkpoint bằng **2.000 sim trials và 100 real trials**, tách ID/OOD. Vẫn thu robot, scene, interactions/demonstrations thật để dựng và kiểm sim. Công bố doanh nghiệp dùng công nghệ proprietary; chưa đủ mã/recipe để tái lập. “Zero real-world policy-training data” không có nghĩa không cần dữ liệu thật hoặc chi phí dựng sim.

### Figure locomotion

[Natural Humanoid Walk Using Reinforcement Learning](https://www.figure.ai/news/reinforcement-learning-walking), 25/03/2025: nguồn gốc cho phần hàng nghìn robot mô phỏng học song song, domain randomization và chuyển policy sang robot thật. Đây là RL locomotion; không chứng minh cùng recipe đã giải được manipulation, lực tiếp xúc, đồ mềm hoặc việc nhà dài.

## 3. Bảng kiểm số liệu và tin tức theo video

“Có nguồn” dưới đây nghĩa là tìm thấy tài liệu hỗ trợ phát biểu trong phạm vi được ghi, không phải đã kiểm nghiệm độc lập kết quả doanh nghiệp. “Chưa xác minh” không có nghĩa phát biểu chắc chắn sai.

| Mốc | Video đề cập | Kết quả đối chiếu và nguồn |
|---|---|---|
| 0:00 | Robot chạy 100 m trong 9,39 s, nhanh hơn Bolt | Có tin [AP 25/08](https://apnews.com/article/069b76ee6748154fd67bec39fa927cf6) xác nhận mốc trước đó. [AP 26/08](https://apnews.com/article/b61c03c7dd570f6a3db1756b9e5ea63e) cập nhật 8,64 s ở chung kết. Đây là cuộc thi robot, không phải kỷ lục điền kinh người được thay thế. |
| 0:29 | Đội tự chủ làm việc nhà khoảng 26 phút; đội điều khiển từ xa nhanh hơn 10 phút nhưng mất điểm | [Bài AgeClub trên ThePaper](https://m.thepaper.cn/newsDetail_forward_34010891), 04/09/2026, ghi 26:12, 305 điểm; trọng số tự chủ 1,0 và remote 0,5. Chưa thấy số thời gian nhanh hơn đúng 10 phút trong bài. Đây là bài tổ chức đăng trên nền tảng, chưa có bảng kết quả chính thức để kiểm độc lập. |
| 1:00; 5:56 | Người lặp thao tác thu data; Trung Quốc có hơn 40 trung tâm | [Rest of World](https://restofworld.org/2026/china-robots-training-centers-workers/), 07/01/2026: hơn 40 trung tâm **được công bố** đến 12/2025, khoảng hai chục hoạt động. Không nên đổi thành hơn 40 trung tâm đã vận hành. |
| 2:01 | Figure học locomotion hàng nghìn mô phỏng song song | Có [công bố Figure](https://www.figure.ai/news/reinforcement-learning-walking). Nguồn về học đi, không phải whole-task household success. |
| 2:38 | Unitree luyện backflip hơn 100 triệu lần | Chưa tìm được phát biểu gốc và định nghĩa “lần”. Không thay bằng số motion frames của paper khác. |
| 3:29 | Moravec's paradox | Khung giải thích lịch sử; không phải một phép đo hay chứng minh mọi dạng robotics đều khó hơn mọi dạng reasoning. Video chưa cung cấp nguồn gốc học thuật cụ thể. |
| 4:04 | AI internet có lượng dữ liệu tương đương 100.000 năm lao động người | Chưa tìm được phép quy đổi và phát biểu gốc của giáo sư được nhắc. Không dùng làm số liệu định lượng trong slide. |
| 4:49 | AgiBot hơn một triệu trajectories, khoảng 3.000 giờ | Đúng khi làm tròn theo [paper v4, §III](https://arxiv.org/html/2503.06669v4). Quy đổi thành “năm làm việc” chỉ minh họa, không đo độ bao phủ, chất lượng hay lượng thông tin. |
| 5:37 | Spirit AI: robot brains tiến bộ năm 2027; cần ít nhất tám năm để vào nhà | [Reuters được The Standard đăng lại](https://www.thestandard.com.hk/china/article/343198/Founder-of-Chinese-startup-Spirit-AI-says-robot-brains-set-for-2027-breakthrough), 18/09/2026. Là nhận định của Gao Yang, không phải lịch kỹ thuật được bảo đảm. |
| 6:32 | Trung tâm Bắc Kinh: 100 người, hai người/robot, 15 tasks/ngày, lặp 10 lần | Video dẫn [Guardian](https://www.theguardian.com/technology/2026/mar/19/inside-chinas-robotics-revolution). Chưa đối chiếu đủ đoạn gốc cho toàn bộ chuỗi số; chưa coi là thống kê ngành. |
| 7:01 | Tesla trả tới 48 USD/giờ cho người mặc mocap, VR năm 2024 | [Tin 19/08/2024 dẫn tuyển dụng Tesla](https://decrypt.co/245399/TB4mh0Xzm1vH.php) ghi khoảng 25,25–48 USD/giờ. Mức tối đa của vị trí tuyển dụng, không phải chi phí trung bình hoặc đơn giá hiện tại. Chuyển sang backpack camera 06/2025 chưa xác minh bằng nguồn gốc. |
| 7:30 | Startup Đức dọn nhà miễn phí tại New York để lấy human video | [Shift](https://www.shiftapp.nyc/) và [Semafor 29/05/2026](https://www.semafor.com/article/05/29/2026/ai-startup-offers-free-home-cleaning-to-train-its-robots) hỗ trợ. Người thực hiện dịch vụ và thu first-person footage; chưa chứng minh policy robot tự làm việc. |
| 8:08 | Figure 16 triệu video, trả 15 triệu USD | Có [Index](https://www.figure.ai/news/introducing-index). Chưa xác minh chi tiết gửi thiết bị và trả tiền theo phút như video mô tả bằng chính trang này. |
| 8:30 | Người nội trợ ở Sơn Đông: sáu giờ/ngày, 20 đơn vị tiền/giờ | Chưa tìm nguồn trực tiếp cho case. Phụ đề ghi “yen”; bối cảnh có thể là nhân dân tệ, nhưng chưa đủ nguồn để chốt đơn vị và mức thu nhập. |
| 8:51 | Tau đưa hai robot tới nhà, giá 30 USD mỗi robot mỗi giờ | [Điều khoản Tau](https://www.tau-robotics.com/service-terms), 27/07/2026: invite-only, human-controlled, hai robot thành 60 USD/giờ. Giá dịch vụ có người điều khiển không chứng minh autonomous labor có cùng chi phí. |
| 9:00 | Tau giữ video dài hạn, không làm mờ mặt; xóa data không xóa kiến thức model | [Privacy Tau](https://www.tau-robotics.com/service-privacy): nêu retention vô thời hạn hoặc đến yêu cầu xóa; chưa blur faces; raw-data deletion không gỡ tác động từ model đã train. Đây là chính sách của Tau, không chứng minh mọi phương pháp machine unlearning đều bất khả thi. |
| 9:51 | World Labs dựng sim, sinh biến thể và học policy, chuyển về robot thật | Có [R2S2R](https://www.worldlabs.ai/blog/real-to-sim-to-real). Cần phân biệt pipeline interactive simulation với video generation thuần. |
| 10:57 | Tesla world simulator dùng cho FSD và Optimus | Truy được [bài đăng của Ashok Elluswamy](https://x.com/aelluswamy/status/1981644831790379245), nhưng nguồn gốc trả 403 khi truy cập. Chưa kiểm đủ kỹ thuật; không suy ra action labels chính xác từ demo. |
| 11:36 | AMD mua World Labs với 8,2 tỷ USD | [AMD 28/09/2026](https://newsroom.amd.com/news/amd-acquire-world-labs/): **thỏa thuận mua** bằng cổ phiếu, dự kiến hoàn tất cuối 2026 và có điều kiện. Thông báo giao dịch chưa đồng nghĩa đã hoàn tất. |
| 12:12 | Benchmark 50 việc nhà, hệ thống tốt nhất hoàn thành 12,4% | [Stanford AI Index 2026, tr.117, hình 2.7.2](https://hai.stanford.edu/assets/files/ai_index_report_2026.pdf#page=117): challenge 2025, held-out test, whole-task 12,40%; Q-score 25,99%. Đây là benchmark mô phỏng, không phải khảo sát mọi robot thực tế. |
| 12:38 | Figure 9% → 56%, 30 nhà, ba tasks | Có [Helix 2.5](https://www.figure.ai/news/helix-2-5-zero-shot-30-home-generalization), ngày nguồn 17/09/2026. Mốc 30/09 nói trong phụ đề không khớp ngày nguồn. |
| 13:14 | Trung tâm Quảng Tây: robot bằng 20% tốc độ người, bắt kịp sau 2–3 năm | Link [IBTimes trong mô tả](https://www.ibtimes.com/china-building-100000-humanoid-robots-they-still-struggle-basic-jobs-3806863) chưa truy cập được. Chưa xác minh task, sample size, cách tính hoặc phát biểu gốc. Không dùng như benchmark chung. |
| 13:40 | 20 bước, mỗi bước thành công 95%, cả chuỗi chỉ khoảng 36% | Phép tính minh họa: 0,95^20 = **35,85%**. Đúng với giả định mỗi bước có xác suất có điều kiện 95% sau khi các bước trước thành công; không tự áp dụng từ tỷ lệ marginal từng bước. Recovery và retry làm mô hình khác. |
| 14:08 | Figure 02 ở BMW: 90.000 parts, 30.000 xe, khoảng 10 tháng | [Figure 19/11/2025](https://www.figure.ai/news/production-at-bmw): deployment 11 tháng; 90.000+ parts, 1.250+ runtime hours, góp phần vào 30.000+ X3. Task là nạp parts vào welding fixtures, không tự lắp toàn bộ xe. Mốc 10 tháng liên quan đạt full deployment. |
| 14:36–15:55 | Tesla: costume, prototypes, bartender remote, targets 10.000/1 triệu, bán 2027, 10 tỷ robot 2040 | Chưa kiểm độc lập từng mốc bằng nguồn Tesla/filings. Target sản xuất, lịch bán và dự báo của Musk phải tách khỏi actual production/sales. Không sử dụng chuỗi này làm bằng chứng technical readiness. |
| 16:09 | Morgan Stanley: hơn một tỷ robot năm 2050, 80 triệu trong nhà | [Morgan Stanley 14/05/2025](https://www.morganstanley.com/insights/articles/humanoid-robot-market-5-trillion-by-2050): dự báo installed/in-use; 930 triệu industrial/commercial, 80 triệu household. Là dự báo tương lai, không phải measured installed base. |
| 16:24 | IFR: khoảng 7.000 humanoids bán năm 2025, chủ yếu research/data | [IFR 30/09/2026](https://ifr.org/ifr-press-releases/news/worldrobotics-2023-report-asia-ahead-of-europeand-the-americas): khoảng 7.000 humanoids **trên 140 cm**, phục vụ commercial/professional **beyond R&D/entertainment**. Số đúng trong phạm vi đó; diễn giải chủ yếu research/data không được thông cáo này hỗ trợ. Nguồn cập nhật sau ngày video. |
| 17:01 | Hong Kong: 380.000 domestic helpers, lương 5.100 HKD | Chưa kiểm số headcount. [Chính quyền HK 02/10/2026](https://www.news.gov.hk/eng/2026/10/20261002/20261002_163257_265.html) cho biết minimum allowable wage tăng từ 5.100 lên **5.220 HKD** với hợp đồng mới từ 03/10. Mốc cũ phù hợp thời điểm video, cần cập nhật khi trình bày hiện tại. |
| 17:10 | NEO: 20.000 USD hoặc 499 USD/tháng, so với helper | Có [1X order](https://www.1x.tech/order). [Trang NEO](https://www.1x.tech/neo) mô tả early access, basic autonomy và Expert Mode. Giá subscription chưa bao gồm một phép so sánh đầy đủ về năng lực, thời gian dịch vụ và chi phí vận hành. |
| 18:37–19:18 | Worker lo mất việc; Tesla có nhiều năm road data nên robot tương lai sẽ tốt | Phần lập luận/xã hội và suy diễn của video; số năm driving data không chứng minh dữ liệu đó bao phủ contact manipulation hoặc chuyển được action sang robot. |

## 4. Video này hỗ trợ gì cho idea hiện tại?

Phần dưới là **đánh giá engineering của chúng ta**, không phải phát biểu nguyên văn của các nguồn.

### Human video là nguồn kinh nghiệm có tiềm năng, cần chứng minh bridge cụ thể

Human footage cung cấp hình ảnh, diễn biến và context phong phú. Để dùng cho Action Expert, project phải công bố rõ mẫu supervision thực sự: tọa độ, hệ quy chiếu, timestamp, confidence/mask và loss. RGB/caption không tự tạo ground-truth joint targets, torque, force hay contact của robot target.

Kết quả Figure là lý do đáng để thử human pretraining. Nó chưa chứng minh representation common-wrist, adapter hay lựa chọn freeze VLM của project đã đúng. Cần ablation với cùng robot data, cùng model và cùng tập kiểm tra, thay riêng nguồn hoặc cách dùng human supervision.

### Synthetic action cần đến execution và kiểm định

Đường đi có thể kiểm tra được của project:

```text
Task + scene có geometry/dynamics + robot embodiment
              ↓
Planner / expert policy / demonstration được chuyển sang robot
              ↓
Controller chạy trong simulator
              ↓
Observation, action đã gửi, state readback, contact, outcome
              ↓
QA + provenance + phân loại success / failure / recovery
              ↓
Mẫu training theo schema của model target
              ↓
Closed-loop evaluation trên tập giữ riêng và robot thật
```

Simulator cho phép ghi robot-specific actions và transitions. Tuy nhiên, một action đã được thực thi không mặc nhiên là action tối ưu hoặc đúng mục tiêu. Phải kiểm khả năng đạt trạng thái, giới hạn động học, lực/tiếp xúc và kết quả task. Video synthetic chỉ có ảnh đẹp chưa thay thế pipeline này.

### Failure evidence và nguyên nhân cần tách nhau

Benchmark cho thấy phải báo cáo cả tiến độ từng bước và hoàn thành cả task. Với project, nên lưu input/time alignment, actual VLM features, Action Expert output, action sau controller và robot readback; dùng scorer độc lập kiểm outcome. Probe latent có thể bổ sung bằng chứng, nhưng kết quả probe hoặc attention visualization chưa đủ kết luận module gây lỗi.

Nếu task fail từ đầu đến cuối, cần kiểm input/schema/normalization/calibration và scorer trước, sau đó kiểm policy coverage và control execution. Quyết định sửa integration, bổ sung data, train module nào hay defer cần được kiểm bằng can thiệp có kiểm soát. Các nguồn trong video chưa cung cấp sẵn phương pháp chẩn đoán đó cho mọi VLA.

### Giảm chi phí phải đo tại cùng mức chất lượng

Nên so baseline robot-only với các nhánh thêm human và synthetic; giữ test set, rubric và ngân sách so sánh rõ ràng. Đếm chi phí toàn pipeline: thu thập, gán nhãn, bridge, dựng/kiểm sim, compute, lọc mẫu, sửa lỗi, thử trên hardware. So cả whole-task success, intervention, thời gian thực hiện và regression ở các điều kiện giữ riêng.

Một nhánh có ít robot demonstrations nhưng không đạt chất lượng yêu cầu chưa chứng minh tiết kiệm để bàn giao. Ngược lại, chi phí dựng sim ban đầu có thể được phân bổ cho nhiều lần sử dụng; cần ghi rõ số lần tái sử dụng và giả định phân bổ. Đây là đề xuất đo lường, chưa phải số tiết kiệm đã quan sát của project.

## 5. Cách dùng bằng chứng trong slide

| Luận điểm định trình bày | Bằng chứng phù hợp | Tránh kết luận vượt bằng chứng |
|---|---|---|
| Dataset robot có chi phí tổ chức và thu thập đáng kể | AgiBot pipeline; phóng sự teleoperation | Quy mô dataset tự chứng minh chất lượng hoặc một mức chi phí cố định |
| Human experience có thể giúp chuyển giao policy | Thí nghiệm Figure, ghi rõ self-reported và phạm vi | Human RGB tự biến thành action ground truth; mô hình của project đã đạt cùng kết quả |
| Simulation là nguồn train/evaluation tiềm năng | World Labs R2S2R và Figure locomotion | Sinh video đồng nghĩa sinh action vật lý đúng; không cần calibration hoặc real evaluation |
| Phải chấm toàn task, kiểm OOD | BEHAVIOR và protocol giữ riêng | So trực tiếp tỷ lệ giữa các benchmark, robot và task khác nhau |
| Có thị trường quan tâm | Morgan Stanley, IFR, 1X | Forecast thành actual sales; giá thuê thành ROI đã đo |

Nên ưu tiên đọc theo thứ tự: **Helix 2.5 → World Labs R2S2R → AgiBot paper §III/IV → BEHAVIOR protocol và paper đội thắng**. Các tin thị trường hỗ trợ bối cảnh; phần logic kỹ thuật phải dựa vào recipe, schema, ablation và kiểm nghiệm của chính project.

## 6. Tài liệu lưu và phạm vi chưa kiểm được

- [Stanford AI Index 2026, trang 117](https://hai.stanford.edu/assets/files/ai_index_report_2026.pdf#page=117) đã được tải và đối chiếu; bản PDF cache được dọn, giữ link nguồn chính thức. Báo cáo là tài liệu tổng hợp, không thay thế paper/protocol gốc.
- Chưa truy cập đầy đủ Reuters trực tiếp, bài IBTimes và bài đăng X gốc của Tesla. Những claim tương ứng được đánh dấu rõ trong bảng; không lấy search snippet làm bằng chứng kỹ thuật.
- Chưa xác minh: Unitree 100 triệu backflips, internet data 100.000 năm, case Sơn Đông, toàn bộ chuỗi số ở trung tâm Guardian, headcount helper và các targets/mốc Tesla.
- Không thay đổi website, slide hoặc specification của project trong lượt nghiên cứu này.
