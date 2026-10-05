# 01 · Humanoid Skill Learning — định nghĩa sản phẩm

_05/10/2026 · Đề xuất cho H1, vòng idea. Nội dung mô tả giải pháp, kế hoạch và kết quả kỳ vọng; chưa có kết quả thử nghiệm của đội._

## Luận điểm trong một câu

Công cụ dành cho đội AI/robotics giúp humanoid học và cải thiện kỹ năng: chấm từng bước, kiểm điểm nghẽn, chọn sửa hệ thống hoặc dữ liệu đúng, huấn luyện và đo tổng công tới cùng chất lượng.

## Hiểu sản phẩm trong một phút

- **Ai dùng:** đội kỹ sư đưa tác vụ mới lên humanoid, cùng người vận hành và người phụ trách tác vụ.
- **Đầu vào:** nhiệm vụ, tiêu chuẩn hoàn thành, mẫu thao tác robot đích, video liên quan có quyền và dữ liệu bổ sung qua kiểm tra.
- **Cách hoạt động:** định nghĩa task/bước → tạo baseline → chạy và chấm từng bước → kiểm hệ thống/probe → thu correction hoặc bootstrap → học với dữ liệu cũ + mới → kiểm cả task/tổng công.
- **Đầu ra:** mô hình điều khiển đã đánh giá trong mô phỏng, SOP dữ liệu và báo cáo so sánh có thể tái lập.

Ví dụ xuyên suốt: **“Đặt linh kiện màu vàng vào ô A1.”** Phạm vi đầu là một tay gắp–đặt, torso cố định, GR1 trong mô phỏng. Video người cung cấp tín hiệu trình tự; wrist motion chỉ dùng khi nhãn đủ tin cậy. Mẫu robot dạy hành động đúng với robot đích. Video người không tự là lệnh robot.

H1 đã xác định nhu cầu huấn luyện nhanh, chính xác, giảm công sức. Khi tiếp cận DENSO cần xác nhận tác vụ cụ thể, công việc đang tốn thời gian nhất và tiêu chuẩn nghiệm thu. Task khay là ví dụ đề xuất, chưa phải tác vụ nhà máy đã khảo sát.

MVP gồm task/stage contracts, dấu vết thực thi, diagnostic probes, acquisition/training plan và báo cáo tối giản cho một kỹ năng. Sau khi kiểm chứng, đóng gói thành workbench dùng lại cho kỹ năng khác. Tầm nhìn sản phẩm rộng hơn phạm vi thử nghiệm đầu.

## Quy trình hỗ trợ hiệu quả

Giảm tổng công và thời gian tới nghiệm thu: kiểm nguyên nhân lỗi, chọn can thiệp tiếp theo theo điều kiện và chi phí, rồi so với kỹ sư thu targeted teleop trên cùng FluxVLA. Health checks là bước bảo đảm quy trình; giá trị chính là phát triển kỹ năng hiệu quả hơn.

Can thiệp gồm sửa binding/calibration/controller trước khi học, tái dùng dữ liệu hợp lệ, augmentation thông thường, targeted teleop, human/internet bridge hoặc synthetic phù hợp. Bốn nguồn vẫn có SOP/catalog; không bắt mọi recipe dùng cả bốn. Chỉ coi giảm chi phí là kết quả sau cùng accepted quality và ledger đầy đủ.

Đơn vị sản phẩm là **một kỹ năng được nghiệm thu trên một robot**, gồm policy, dữ liệu có nguồn gốc, phép đánh giá, SOP và báo cáo chi phí. Khách hàng nhận được kỹ năng và quy trình đưa kỹ năng tiếp theo lên robot; số màn hình quản lý dữ liệu không phải thước đo giá trị.

## Vấn đề và người sử dụng

Teleop cung cấp action/state đúng embodiment nhưng mỗi lượt cần robot, người vận hành, setup và reset. Human egocentric, video internet và synthetic mở rộng tình huống học; chúng có tín hiệu, hình học và độ tin cậy khác nhau. Tăng số frames chưa trả lời được liệu robot có gắp đúng khi vật đổi vị trí, nền đổi hoặc thao tác có contact khó hơn.

Người sử dụng chính: kỹ sư AI/robotics đưa task mới lên humanoid. Kỹ sư dữ liệu hỗ trợ chất lượng dữ liệu; người sở hữu task xác nhận điều kiện và tiêu chuẩn nghiệm thu. Personas và chi phí DENSO cụ thể chưa được khảo sát. Giá trị nghiệp vụ được đo bằng engineer-hours, robot-hours, elapsed time tới nghiệm thu, đầu ra đạt chuẩn/giờ và interventions; demo count là chỉ số phụ.

## Khóa đúng điểm nghẽn trước pilot

Trong tuần 1, task owner và kỹ sư ghi current workflow, số lần đổi SKU/task, công calibration/thu/QA/debug/eval, khả năng truy cập robot và nguyên nhân fail. So phương án hiện hành hoặc robot arm/chương trình phù hợp về cùng outcome; không dùng giả định mọi task cần humanoid. Chọn case khi đổi task/vật/điều kiện làm tăng công đưa skill tới nghiệm thu và dữ liệu là một nguyên nhân có thể kiểm. Nếu controller/fixture/reachability mới là hạn chế chính, sửa phần đó và lập baseline lại trước acquisition experiment.

Case khay là proxy kỹ thuật; lý do kinh tế dùng humanoid và mức chất lượng/cycle time thực tế cần owner xác nhận, chưa có số đo DENSO. Kiểm một condition hình ảnh/vị trí và một condition contact/recovery trong miền khả thi; không chỉ đổi nền để tạo benchmark dễ hơn.

## Một case xuyên suốt: lấy linh kiện và đặt vào ô khay

Đây là **task đại diện đề xuất**, chưa phải task BTC giao. Kịch bản đầu: linh kiện cứng, cỡ vừa bộ gắp, một tay lấy và đặt, khay cố định, base/chân và torso khóa; tay còn lại ở vị trí nghỉ. Phối hợp hai tay và khay di động là phần mở rộng sau acceptance, tránh thêm biến ngay ở phép kiểm đầu.

| Phần của case | Định nghĩa cần khóa trước huấn luyện |
|---|---|
| Quan sát | Camera đầu/góc nhìn thứ nhất, camera cổ tay nếu môi trường có, measured state và câu lệnh đặt vào ô đích |
| Chuỗi thao tác | Tiếp cận → gắp → nâng/chuyển → đặt → nhả và rút tay |
| Điều khiển | Action profile robot/controller: joints hoặc end-effector theo config đã kiểm; không trộn hai cách biểu diễn ngầm |
| Thành công đề xuất | Đúng linh kiện nằm hoàn toàn trong ô đích, bộ gắp đã nhả, vật ổn định ≥2 giây, không vi phạm giới hạn thao tác |
| Giới hạn lượt | Tối đa 30 giây; timeout/rơi/đặt sai ô được tính thất bại, không loại khỏi mẫu số |
| Điều kiện học | Vị trí trong vùng đã định, một số vật phù hợp bộ gắp, các nền/ánh sáng thuộc train/development |
| Kiểm tra giữ riêng | Vùng vị trí, instance vật và hình ảnh chưa train/tune; tách từng loại thay đổi để hiểu lỗi |

30 giây và 2 giây là thông số thiết kế ban đầu, cần task owner phê duyệt; không là cycle time đã đo. Các vật ngoài khả năng bộ gắp/reachability không được gọi OOD có thể giải bằng thêm dữ liệu. OOD không thay mục tiêu kỹ năng thành lắp ráp chính xác hoặc thao tác ngón tay tinh.

## Bốn nguồn đi vào học như thế nào?

| Nguồn | Khi nên thử | Tín hiệu dùng được | Giới hạn |
|---|---|---|---|
| Human ego | Học cấu trúc tiếp cận–gắp–đặt và chuyển động tay liên quan task | RGB, nhãn bước; wrist motion khi geometry/timing hợp lệ | Human wrist chưa là robot action; tracking thiếu phải mask |
| Internet | Bổ sung vật, cách thao tác và bối cảnh trong subset có quyền dùng | RGB/text, nhãn bước đã QA; temporal representation | Ghi riêng priors có sẵn trong checkpoint và video đội bổ sung; không tự sinh ground-truth action |
| Synthetic | Mở điều kiện hình ảnh của train; sau đó thử physics variants có action/outcome đã thực thi | Labels kế thừa qua appearance QA hoặc controller-executed trajectories | Video sinh từ world model chưa là demonstration được thực thi |
| Teleop robot đích | Học action, hiệu chuẩn mapping, contact/correction và kiểm tra trên phần giữ riêng | Command/state/timing, outcome/correction nếu có nhãn | Dùng lại nhiều views không làm tăng số demo độc lập; holdout không quay về train |

Các nhóm có thể chồng lấp, như human ego được publish trên internet. Phải đếm recording gốc theo lineage, không đếm hai lần. Dữ liệu real robot có thể đa dạng, như DROID; giả thuyết ở đây là tận dụng độ đa dạng ngoài robot để bổ sung collection đích, không mặc định real data luôn kém đa dạng.

## Đường triển khai được chọn

**Phương án chính:** FluxVLA + GR00T N1.5 pretrained base + humanoid GR1 trong RoboCasa/MuJoCo. Chọn N1.5 vì có đường GR1/config công khai để giảm việc nối simulator, không vì cho rằng nó tốt hơn N1.7. Chạy robot-action baseline và scorer trước; task khay là wrapper cần kiểm. Human/internet auxiliary objectives chỉ mở khi có source eligibility, hypothesis và gói QA trong cost cap. Thử appearance augmentation thông thường trước Cosmos-Transfer2.5; physics sau controller/scorer gate. Chi tiết model, losses, fallback và E0 ở [Learning Core](04-learning-core.md).

Lựa chọn này là quyết định thiết kế, **chưa chạy tích hợp của đội**. Không coi các ví dụ G1/HumanEgo đang hiển thị là dữ liệu của GR1/task khay. Khi DENSO giao robot/task khác: giữ pipeline và thay task/controller adapter, chạy lại compatibility và acceptance; kết quả GR1 không tự là kết quả robot DENSO.

**Phương án dự phòng:** nếu N1.5 path không qua E0, thử SmolVLA với cùng GR1/action profile; reset comparator từ một initialization chung và báo thay đổi. Nếu chỉ task khay chưa chạy, dùng task pick-and-place GR1 đã có trong upstream, cập nhật tên/scorer/domain trước tạo final split. Không dùng benchmark cánh tay đơn để thay nghiệm thu humanoid.

## Đóng góp và đối chứng

FluxVLA đã có engine, data generation và human-in-the-loop; EgoVLA/EgoScale đã có human transfer; [DataMIL v1](https://arxiv.org/html/2505.09603v1) có policy-aware data selection và nêu compute overhead của selection. Đóng góp đề xuất là **quy trình chọn can thiệp/gói thu hoặc tái dùng dữ liệu theo điều kiện và tổng chi phí, đo thêm giá trị so với targeted teleop của kỹ sư**. DataMIL chọn subset từ prior dataset khác bài acquisition này; không tuyên bố thuật toán mới hoặc first-ever.

| Phần cần xây | Người dùng nhận gì | Phép kiểm cần có |
|---|---|---|
| Adapter đa nguồn và objective masks | Human/video được dùng đúng phần học, teleop giữ semantics | Đọc lại mẫu → gradient từng objective → rollout; không chỉ import thành công |
| Bảng điều kiện kỹ năng | Biết robot yếu ở vị trí, hình ảnh hay contact nào | Development probes + kiểm mapping/reachability trước kết luận coverage |
| Quyết định can thiệp tiếp theo | Health-check, hypothesis, gói đủ quyền/tín hiệu, cost range và stop/defer | T: expert-targeted teleop, F: mixture cố định và A: condition/cost selection từ cùng parent |
| SOP và báo cáo kỹ năng | Có thể lặp lại cách thu, học, nghiệm thu | Model/data/binding/scorer versions + kết quả âm + tổng công |

Ví dụ: camera lệch → sửa calibration và baseline lại; nền mới → thử basic augmentation trước gói appearance/RGB tốn công hơn; trượt contact → kiểm controller rồi targeted teleop/corrections, physics chỉ khi fidelity đủ. Human/internet không thay measured contact. Engineer duyệt hypothesis; không suy nguyên nhân từ một video lỗi. Không có evidence/hợp lệ/cap thì defer hoặc collect một pilot nhỏ; no-gain giữ nguyên.

Vòng lựa chọn dùng danh sách gói đã chốt và chi phí tối đa, không hứa dự đoán gain chính xác. Chỉ xếp theo measured development utility khi có receipts cùng domain; dữ liệu mới chưa đo thì ghi unknown. Binding repair là bước riêng trước E4, không trộn nó vào data-only arms rồi nhận source attribution.

## Phạm vi và ba đầu ra

MVP: một task, một humanoid, một checkpoint family; robot baseline, health checks, catalog/SOP bốn nguồn và E4 ba arms T/F/A. Một bridge nhỏ và một augmentation contrast chỉ chạy khi tín hiệu/QA/compute đủ; gate fail thì báo not-tested và giới hạn claim, không nhận đã chứng minh cả bốn nguồn. Core 15 training runs theo [Protocol](06-validation-and-roadmap.md); ablations bổ sung có gate. CLI + receipts + report trước, workbench nhiều người sau pilot. Không train foundation model/WM/IDM từ đầu.

Ba đầu ra H1: SOP thu/QA dữ liệu; báo cáo so ≥2 phương pháp huấn luyện theo demo budget/chất lượng/tổng chi phí; learned-policy demo trong mô phỏng humanoid. Các ngưỡng trong ảnh đề địa phương (success ≥75%, demo saving ≥30%, OOD ≥70%) là mục tiêu thử nghiệm, chưa kết quả và chưa là điều kiện đã đạt ở vòng idea.

75%/30% là PoC targets, không factory acceptance. Báo cycle time p50/p95, fail/recovery/intervention, good outputs/giờ và engineering/robot-hours, không biến giảm demos thành cash saving. Ba ngân sách tách: R&D simulation study, một skill sau pipeline sẵn, production/real-cell acceptance. Không cộng lại các khoản đã nằm trong subtotal của một ngân sách.

Website BTC hiện xếp bài toán vào [H1](https://densohackathon.vn/theme). [Thể lệ](https://densohackathon.vn/challenges) yêu cầu slide theo mẫu chính thức cho vòng idea; website là tài liệu bổ sung. Ảnh đề lưu trong repo ghi H2 là tài liệu tham chiếu cũ, không dùng nhãn đó trong hồ sơ hiện hành.

## Hướng phát triển thành sản phẩm

Trước hết bàn giao một kỹ năng và quy trình tái lập. Sau pilot được nghiệm thu, đóng gói task/controller adapter, source adapters, experiment runner và report thành workbench dùng lại. Mở task thứ hai trên cùng robot trước, rồi mới robot khác; mỗi lần phải đo công tích hợp và chạy acceptance riêng. Backend nhiều workspace và mở rộng world models chỉ theo nhu cầu pilot, không dùng số module làm khác biệt.

[PRD](08-prd.md) · [Kiến trúc](02-system-architecture.md) · [Huấn luyện](04-learning-core.md) · [Protocol và rủi ro](06-validation-and-roadmap.md) · [Hiệu quả](07-business-case.md).

## Vòng cải thiện là chức năng cốt lõi · revision 2

TaskProfile cần preconditions/completion/readiness, pass/fail/not_attempted/unknown từng bước, health và reset semantics. Lỗi biểu hiện ở chuyển có thể do gắp trước đó; controlled natural/restaged probes giúp khoanh vùng, không tự chẩn đoán nhân quả từ clip.

Có useful baseline: targeted corrections gần policy states, giữ context và trộn prior dữ liệu tốt, kiểm regression/full task. Không full-task success nhưng có local progress: luyện bottleneck. Không có basic skill: expert robot seed + curriculum để tạo R0; chưa có parent hữu ích sau cap thì rescope/stop. Chưa tới bước sau giữ not_attempted.

Đóng góp cần đo là workflow chọn can thiệp có evidence, engineer approval và total cost so expert T, không novelty của subtask learning/DAgger. [Đặc tả đầy đủ](14-task-improvement.md) là nguồn canonical của vòng này; [audit](reviews/full-idea-audit-2026-10-05.md) giữ gaps và phép kiểm. Việc bổ sung đặc tả chưa là implementation/evidence ML.
