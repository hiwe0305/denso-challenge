# Pitch outline — Humanoid Skill Learning

_Dàn ý nội dung để chuyển sang slide theo mẫu BTC; chưa là deck đã điền mẫu chính thức. Không chấm đội hoặc nguồn lực._

## Câu chuyện 10 slide

| Slide | Thông điệp | Ví dụ/bằng chứng |
|---|---|---|
| 1 | Công cụ giúp đội AI/robotics huấn luyện kỹ năng với ít công hơn | Linh kiện → ô khay; humanoid fixed-base; proposal H1 |
| 2 | Thu thêm teleop chưa giải mọi thay đổi | Vị trí/nền/contact khác nhau; chi phí DENSO chưa đo |
| 3 | Video người bổ sung trải nghiệm, mẫu robot dạy điều khiển | Human stage/order/wrist hợp lệ; robot action/contact; các nguồn mở theo điều kiện |
| 4 | Tái sử dụng phương pháp hiện có | EgoVLA/HumanEgo/LAPA/synthetic/FluxVLA; không nhận engine hoặc human transfer là novelty |
| 5 | Dữ liệu thật và giới hạn | G1 620 frames, HumanEgo 1002 rows/missing wrist; public samples khác task/robot, chưa paired |
| 6 | Phương án chính đã chọn | FluxVLA/GR00T N1.5/GR1; custom human/video auxiliary heads; task wrapper và E0 |
| 7 | Đóng góp cần chứng minh | Development conditions → health check → source package → T expert teleop / F fixed mixture / A condition-cost cùng cost |
| 8 | Nghiệm thu theo task outcome | Đúng ô/nhả/ổn định/timeout; ID/OOD, demo budget, same-quality và total cost |
| 9 | 12 tuần, main/fallback gates | E0 robot baseline → E1 → catalog/caps → E4 T/F/A → gated extensions → final |
| 10 | Ba đầu ra và lợi ích cần đo | SOP/report/learned sim demo; cùng quality, demo count và tổng công; task thứ hai rồi robot thật |

## Bài nói khoảng 5 phút

**0:00–1:00 — Bài toán.** Chúng tôi bắt đầu từ một thao tác: humanoid lấy linh kiện cứng và đặt vào ô khay. Khi vật đổi vị trí, nền đổi hoặc contact khó, thu thêm demonstrations robot cho mọi trường hợp mất công và thời gian sử dụng robot. Human video, internet và synthetic có thể bổ sung trải nghiệm, nhưng không tự chứa lệnh đúng cho robot. Sản phẩm giúp học kỹ năng và kiểm xem nên bổ sung nguồn nào để đạt chất lượng với tổng công/chi phí thấp hơn.

**1:00–2:00 — Bốn nguồn và ví dụ.** Human ego dạy cấu trúc thao tác/chuyển động có tín hiệu hợp lệ; internet subset có quyền dùng mở thêm cách thao tác và hình ảnh; synthetic tạo biến thể có QA; teleop giữ action/state, calibration và contact của robot đích. Website có public numerical samples G1/HumanEgo và media tác giả để giải thích. Chúng không phải dữ liệu của task khay và không là kết quả đội. Trường hợp wrist tracking mất nhưng raw tọa độ bằng zero minh họa vì sao phải mask nhãn thiếu.

**2:00–3:00 — Cách học và đóng góp.** Đường chính là FluxVLA, GR00T N1.5 và GR1 trong RoboCasa/MuJoCo. Dùng robot head upstream, chạy robot baseline trước; source adapters và stage/order/wrist heads mở sau rights/signals/E0 gate. E0 kiểm từng loss, gradient, reload và closed-loop, chưa coi setup là thành công task. Điểm cần chứng minh hơn tích hợp engine là quyết định bổ sung dữ liệu theo điều kiện yếu, có health checks và đối chứng expert targeted teleop T và fixed mixture F cùng quality/caps. Chưa nhận thuật toán mới.

**3:00–4:00 — Phép kiểm.** So cùng pretrained init và toàn bộ target-robot roots, core15 runs; source-drop/compute/Cosmos contrasts là extensions có gate. Từ cùng parent policy, ba acquisition arms T/F/A dùng catalog đủ điều kiện và cost cap. Thành công là đúng vật/đúng ô/đã nhả/ổn định trong timeout; báo ID và từng OOD. Demo saving chỉ tính khi baseline và candidate đạt cùng quality. Capture/reset/QA/generation/train/eval/retry đều vào total cost; giữ negative transfer và no-gain.

**4:00–5:00 — Đầu ra và giới hạn.** Trong 12 tuần bàn giao SOP thu dữ liệu, báo cáo so phương pháp và learned-policy demo trong mô phỏng humanoid. Task khay là proxy đề xuất; task/robot DENSO khác cần adapter và nghiệm thu riêng. Nếu đường chính fail E0, dùng fallback đã khai và reset comparator. Sau một kỹ năng được nghiệm thu, mở task thứ hai rồi robot thứ hai, đo công dùng lại. Proposal hiện chưa có training/savings của đội; nghiên cứu và website là nền tảng thiết kế.

Nội dung canonical: [Product](../docs/01-product.md), [Learning](../docs/04-learning-core.md), [Protocol](../docs/06-validation-and-roadmap.md). Sources/media: [Survey](../docs/11-method-survey.md), [Examples](../docs/12-public-data-examples.md). [BTC](https://densohackathon.vn/challenges) yêu cầu deck template; website localhost không là link nộp từ xa.

## Phạm vi và giả định của đề xuất

Không bắt mọi recipe dùng đủ bốn nguồn. Health fail thì sửa ngoài E4 và pin baseline lại; A được chọn reuse/basic augmentation/teleop/defer. DataMIL là prior art, chưa claim thuật toán mới. Cost report tách R&D-sim toàn study, per-skill sau pipeline và production-real; bản full-source gốc chưa kinh tế ở giả định400 →280 roots. Đo tổng engineering/operator/robot/GPU-hours, elapsed time, cycle p50/p95/interventions/recovery/outputs. H1 đã xác định nhu cầu tổng quát; tác vụ và điểm nghẽn cụ thể tại nhà máy cần owner xác nhận. Sim/PoC pass cần nghiệm thu riêng trước production.
