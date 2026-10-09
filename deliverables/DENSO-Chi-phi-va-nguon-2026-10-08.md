# Chi phí platform Humanoid Data Flywheel

Ngày đối chiếu nguồn: 08/10/2026. Đơn vị USD. Đây là mô hình nguồn lực dự kiến, chưa phải kết quả DENSO đo được.

## 1. Phạm vi và đơn vị so sánh
Một đợt cải thiện một skill sau khi platform đã có nền tảng tái sử dụng. So quy trình thu teleop và debug thông thường với quy trình dùng thêm human video, synthetic và dữ liệu có truy nguyên. Hai phương án phải đạt cùng chất lượng full-task và coverage trước khi công nhận giảm chi phí. Bản so sánh này không tính giá mua robot vào lợi ích, không tính tăng năng suất dây chuyền, không giả định giảm GPU huấn luyện chính.

## 2. Nguồn giá công khai
- [Runpod GPU pricing](https://www.runpod.io/pricing): A100 PCIe 80 GB $1.59/GPU-h, H100 SXM 80 GB $3.49/GPU-h, RTX 4090 24 GB $0.74/GPU-h. Trang ghi cập nhật 27/09/2026. Các mức dùng là mức niêm yết hiển thị, giá triển khai thực tế và khả dụng phải đối chiếu console.
- [Runpod Pods pricing](https://docs.runpod.io/pods/pricing): network volume dưới 1 TB $0.07/GB-tháng. Dùng một tier để lập kế hoạch, không suy ra các loại disk khác cùng giá.
- [Upwork ML engineer cost](https://www.upwork.com/hire/machine-learning-experts/cost/): tham khảo freelancer quốc tế $50–$200/h. Không dùng để chứng minh đơn giá nội bộ $20/h.

## 3. Giả định cần thay bằng số đo / báo giá
- Operator $10/h và kỹ sư $20/h là chi phí nguồn lực quy ước, chưa phải lương DENSO. Chưa cộng thuế, VAT, phí thanh toán hoặc chi phí mua thiết bị mới.
- Baseline 400 demo robot gốc đạt QA, phương án 280. Yield 80% nên lần thử 500 và 350. Một lần thu/reset 6 phút và QA 3 phút. Các biến thể synthetic không được tính là demo gốc độc lập.
- Debug cơ sở 80h, phương án 40h/đợt. Mức giảm 50% này là giả thuyết chính cần đo bằng timesheet. Chưa có nghiên cứu nguồn nào chứng minh mức giảm này cho DENSO.
- Huấn luyện chính 120 A100 GPU-h và đánh giá 20 A100 GPU-h cho mỗi phương án. Đây là ngân sách giờ máy giả định, chưa benchmark throughput hoặc VRAM.
- Hiệu chỉnh task/scorer 16 giờ kỹ sư. Nghiệm thu 4 giờ operator + 4 giờ kỹ sư. Scratch baseline 200GB và phương án 300GB lưu một tháng.
- Phương án thêm 200 human clips. Ngân sách 10 A100-h sinh mô phỏng và 20 H100-h sinh video không bảo đảm số mẫu đạt QA. 40 A100-h training phụ trợ là kế hoạch cần smoke test.

## 4. Chi phí trước và sau mỗi đợt
| Khoản | Trước | Sau |
|---|---:|---:|
| Thu teleop + reset | 500.00 | 350.00 |
| QA teleop | 500.00 | 350.00 |
| Debug / chọn can thiệp | 1,600.00 | 800.00 |
| Hiệu chỉnh task / scorer | 320.00 | 320.00 |
| Training chính | 190.80 | 190.80 |
| Đánh giá GPU | 31.80 | 31.80 |
| Nghiệm thu người | 120.00 | 120.00 |
| Scratch storage | 14.00 | 21.00 |
| Chi phí bổ sung ngoài scratch | 0.00 | 655.97 |
| Tổng | 3,276.60 | 2,839.57 |

Giảm gộp = (50−35)h × $10 + (25−17.5)h × $20 + (80−40)h × $20 = $1,100.00.

Chi phí tăng = $662.97. Lợi ích ròng mỗi đợt = $3,276.60 − $2,839.57 = $437.03. Tính theo số chưa làm tròn.

## 5. Các chi phí tăng thêm
| Khoản | Cách tính | USD/đợt |
|---|---|---:|
| Quay video người | 200 clip × 1 phút ÷ 60 × $10/h | 33.33 |
| QA video người | 200 clip × 2 phút ÷ 60 × $20/h | 133.33 |
| QA synthetic | 6 giờ kỹ sư × $20/h | 120.00 |
| Tích hợp / rà bằng chứng thêm | 6 giờ kỹ sư × $20/h | 120.00 |
| Sinh mô phỏng | 10 GPU-h A100 × $1.59 | 15.90 |
| Sinh video | 20 GPU-h H100 × $3.49 | 69.80 |
| Huấn luyện phụ trợ video | 40 GPU-h A100 × $1.59 | 63.60 |
| Dự phòng dữ liệu / giấy phép | Khoản dự phòng, chưa có báo giá | 100.00 |
| Lưu trữ tăng thêm | (300 − 200) GB × 1 tháng × $0.07 | 7.00 |
| Tổng | | 662.97 |

## 6. Setup và vận hành dùng chung
Phát triển / tích hợp: 240h kỹ sư × $20 + 40 A100 GPU-h × $1.59 + 50GB × 1 tháng × $0.07 = $4,867.10. Pilot đối chứng một cặp baseline + candidate: $3,276.60 + $2,839.57 = $6,116.17. Tổng đầu tư ban đầu lập kế hoạch = $10,983.27. Trừ toàn bộ cả hai nhánh pilot một lần theo cách bảo thủ, không đếm pilot vào số đợt tạo lợi ích. Đây là hạn mức giả định cho MVP, chưa phải báo giá hoàn thành toàn bộ R&D trong 30 ngày. Thêm seed, lần train, chỉnh generator hoặc tích hợp vượt ngân sách phải trừ thêm.

Vận hành dùng chung: 48h kỹ sư/năm × $20 + archive riêng 500GB × 12 tháng × $0.07 = $1,380.00/năm. Archive và scratch là hai phần dung lượng riêng, không tính cùng dữ liệu hai lần. Không cộng thêm tiền điện máy local vào kịch bản cloud.

## 7. Hiệu quả ước lượng hằng năm và đầu tư ban đầu
Hiệu quả vận hành năm ổn định = N × $437.033333 − $1,380.00. Với N=72, kết quả $30,086.40/năm. Đây là chỉ tiêu hiệu quả ước lượng hằng năm, chưa trừ chi phí đầu tư một lần. Để vượt $20,000/năm cần ít nhất 49 đợt theo mô hình này.

Công thức năm đầu = số đợt thực sự nghiệm thu trong năm × $437.033333 − $1,380.00 − $10,983.27.

| Đợt/năm | Năm đầu | Năm vận hành ổn định |
|---:|---:|---:|
| 12 | -7,118.87 | 3,864.40 |
| 24 | -1,874.47 | 9,108.80 |
| 60 | 13,858.73 | 24,842.00 |
| 72 | 19,103.13 | 30,086.40 |
| 75 | 20,414.23 | 31,397.50 |
| 84 | 24,347.53 | 35,330.80 |

72 đợt là ví dụ quy mô 6 nhóm × 12 đợt/năm, chưa có xác nhận nhu cầu DENSO. Chỉ đếm các đợt thực hiện sau khi rollout; không mặc định đủ 12 tháng ngay năm đầu. Để vượt $20,000, năm đầu cần ít nhất 75 đợt theo đúng bộ giả định này. 72 đợt chỉ đạt $19,103.13, chưa vượt ngưỡng. Hòa vốn năm đầu cần 29 đợt.

## 8. Độ nhạy
| Kịch bản | Demo robot đạt QA | Debug h | Ròng/đợt | Năm đầu với 72 đợt |
|---|---:|---:|---:|---:|
| Giảm ít | 360 | 72 | -402.97 | -41,376.87 |
| Cơ sở | 280 | 40 | 437.03 | 19,103.13 |
| Thuận lợi | 240 | 24 | 857.03 | 49,343.13 |

Nếu không giảm đủ demo / debug, chi phí có thể tăng. Giờ được giải phóng là giá trị năng lực lao động; chỉ gọi là tiết kiệm tiền mặt khi giảm được mua dịch vụ, overtime hoặc chi thực tế. Robot/camera/fixture mới, downtime, bảo mật, thuế, retraining ngoài ngân sách và giấy phép vượt $100/đợt cần báo giá rồi trừ thêm. Năm đầu 84 đợt có dư địa khoảng $51.76/đợt cho chi phí chưa mô hình hóa trước khi xuống dưới $20,000.

## 9. Dẫn chứng kỹ thuật và giới hạn suy luận
- [FLARE](https://research.nvidia.com/labs/gear/flare/): nghiên cứu báo cáo 37.5% thành công với một robot demo/vật và 60% khi thêm human egocentric video, trong thử nghiệm novel-object với 150 human demo/vật và GR1 pretrained setup. Tăng 22.5 điểm phần trăm. Đây là kết quả tác giả, chưa phải kết quả platform, không chứng minh giảm 30% demo hay 50% debug.
- [MimicGen](https://mimicgen.github.io/): hơn 50,000 demonstrations từ dưới 200 human demonstrations trên 18 tasks. Human demo ở đây là thao tác teleop robot, không đồng nghĩa video góc nhìn người. Không quy đổi hệ số sinh dữ liệu thành tiền tiết kiệm hay bảo đảm chất lượng ngang nhau.
- [MimicGen task specifications](https://mimicgen.github.io/docs/modules/task_spec.html): phân đoạn theo vật tham chiếu và subtask, biến đổi pose và nối chuyển động.
- [GR00T N1.5](https://research.nvidia.com/labs/gear/gr00t-n1_5/): Eagle VLM + DiT Action Expert, pretrained policy adaptation và future latent alignment.
- [DreamGen](https://research.nvidia.com/labs/gear/dreamgen/): video generation và action pseudo-labeling có bước thích nghi, lọc chất lượng và suy luận action. Video tạo ra tự thân không phải action đo từ robot.

## 10. Pilot xác nhận
Khóa task, root split, chất lượng và coverage trước thử. Đối chiếu baseline/candidate cùng recipe và điều kiện. Ghi tất cả giờ operator/kỹ sư, retry, QA reject, GPU-h, storage và tiền hóa đơn. Nghiệm thu full-task độc lập. Chỉ thay các giả định bằng số đo khi có đủ bằng chứng, giữ lại cả no-gain / regression.
