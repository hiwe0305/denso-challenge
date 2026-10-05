# Tham chiếu đánh giá nội bộ trước PoC

_Bảng tham chiếu nội bộ trước PoC được giữ nguyên số và công thức. Không dùng bảng này để đánh giá hồ sơ vòng idea: thiếu kết quả huấn luyện ở giai đoạn đề xuất không tự là điểm trừ. Không phải rubric hoặc điểm BTC._

## Bảng tham chiếu: 6,5/10

Theo yêu cầu người dùng, loại đội ngũ và mức đáp ứng nguồn lực khỏi đánh giá. Năm trọng số PROMPT còn lại 30/20/20/15/10 được chia cho tổng 95, không thêm tiêu chí mới. Khả thi kỹ thuật chỉ xét thiết kế/tích hợp và evidence, không hạ điểm vì GPU, tài trợ hoặc kinh nghiệm thành viên.

| Tiêu chí | Trọng số sau chuẩn hóa | Điểm /10 | Căn cứ và evidence còn thiếu |
|---|---:|---:|---|
| Sáng tạo | 31,58% | 7 | Đóng góp chọn nguồn theo condition + full cost với T expert teleop / F fixed mixture control rõ; chưa measured advantage, không thuật toán mới |
| Nghiệp vụ | 21,05% | 8 | Case khay, outcome/time/conditions và deliverables cụ thể; owner/task DENSO còn cần nghiệm thu |
| Kỹ thuật | 21,05% | 6 | FluxVLA/GR00T N1.5/GR1 và auxiliary objectives/fallback được chọn; custom bridge/scorer chưa E0 |
| Hiệu quả | 15,79% | 4 | Có protocol/source controls/chi phí; không có kết quả transfer, saving hoặc cost thực |
| Mở rộng | 10,53% | 7 | Có task/controller adapters và acceptance gates; chưa kiểm task thứ hai |
| **Tổng** | **100%** | **6,53 → 6,5** | **(7×30+8×20+6×20+4×15+7×10)/95** |

Bản cũ nếu cũng bỏ đội: (6×30+6×20+6×20+4×15+6×10)/95=5,68 →5,7. Điểm tăng ở độ cụ thể của nghiệp vụ, đóng góp và cách nhân rộng. Không nâng technical/effectiveness vì thêm Markdown hoặc screenshot.

## Điểm BTC là một phép đánh giá khác

[BTC](https://densohackathon.vn/challenges) công bố thang 0–5 từng tiêu chí, gồm hồ sơ đội và innovation/originality, feasibility/effectiveness, practicality/scalability. Bảng trên là công cụ phát triển sản phẩm theo PROMPT; không đổi tên nó thành rubric BTC. Trong lượt review này không chấm hồ sơ đội/resources theo yêu cầu người dùng.

## Các thiếu sót đã được sửa ở mức thiết kế

| Vấn đề cũ | Thay đổi hiện tại | Khi nào xem là chứng minh? |
|---|---|---|
| Platform quá rộng, khó thấy robot làm gì | Một case rigid-part-to-tray, scorer/time/ID/OOD | Learned-policy rollout được chấm độc lập |
| Chưa có đóng góp hơn wrapper | Chọn nguồn theo condition; E4 T/F/A từ cùng R0 | E4 fair comparator với uncertainty/cost |
| Model/bridge/sim để mở | FluxVLA/GR00T N1.5/GR1, auxiliary human/video heads, fallback | E0 từng loss/gradient/reload/closed-loop |
| Internet/synthetic chỉ có mặt trong sơ đồ | Licensed subset vào RGB objective; appearance contrast; source-drop | Run receipts/source ablation, không chỉ pretrained-history claim |
| Giá trị chi phí thiếu đường chứng minh | Success/demo budget + full costs + cost-matched acquisition | Logs và same-quality acceptance |
| Tài liệu lặp/nhãn đề cũ | Một canonical product/PRD/protocol; H1 theo website BTC | Build/reference checks; slide template cần chuẩn bị riêng |

## Câu hỏi phản biện cho phát triển sản phẩm

1. **Khác dùng FluxVLA/EgoVLA trực tiếp ở đâu?** Engine/human transfer là prior art. Sản phẩm kiểm quy trình chọn gói dữ liệu theo condition ở cùng chi phí, có SOP/evidence tái lập. Chưa chứng minh gain.
2. **Human/internet có action robot không?** Không tự có. Auxiliary heads học stage/order/wrist motion hợp lệ; robot head học action thực. Mapping/calibration có mask và version.
3. **Human hay internet thật sự giúp?** E2a bỏ từng nguồn tại một budget; nếu chưa chạy chỉ claim workflow chứ chưa attribution riêng.
4. **Chọn dữ liệu có mục tiêu hơn expert targeted teleop và fixed mixture không?** E4 cùng parent, catalog hợp lệ, cost cap và training protocol; báo package draws/uncertainty. Dashboard không chứng minh.
5. **Giảm robot demos có che robot data ở calibration không?** Union tất cả target roots dùng học/bridge/corrections/model selection; eval báo riêng. Views không là demos mới.
6. **Thêm bridge compute có làm đối chứng yếu?** E2 khai extra stage và có compute-matched R0 tại một budget; còn confounds thì ghi.
7. **Synthetic có đổi nghĩa action không?** Appearance QA; physics executed outcomes riêng. Generated video chưa là command-ground-truth.
8. **Nếu cost tăng hoặc transfer âm?** Giữ no-gain/tradeoff, điều chỉnh overhead/source; không công bố saving chỉ vì demo giảm.
9. **GR1 proxy có nghĩa cho DENSO?** Chứng minh pipeline/scorer trong domain cụ thể, không cam kết real transfer. Task/controller DENSO cần adapter và acceptance riêng.
10. **Mở rộng sản phẩm thế nào?** Task thứ hai trước, robot thứ hai sau; đo công integration và quality/cost, không chỉ thêm source/model vào menu.

## Gate nâng điểm tiếp theo

Technical cần E0→repeated E1/E2, contribution cần E4 hợp lệ, hiệu quả cần measured quality/cost, scalability cần task thứ hai. Idea stage không đòi hoàn thành toàn bộ 12 tuần, nhưng proposal phải tách thiết kế, public evidence và kết quả đội.

[Product](../01-product.md) · [Protocol](../06-validation-and-roadmap.md) · [Score model](idea-score.json).

## Cập nhật sau cost/solution review05/10/2026

Health-first, robot baseline trước, branches theo gate, T/F/A từ R0 thay comparator yếu, core15 runs và extensions có điều kiện. Chi phí tách study/skill/production, acquisition unknown không thành0; thêm process/reliability KPI và DataMIL prior art. **Giữ điểm6,5/10:** chỉnh hồ sơ không thay E0, quality/cost logs, E4 hoặc task thứ hai. Reviews có ngày và cost audit cũ giữ như snapshot lịch sử.
