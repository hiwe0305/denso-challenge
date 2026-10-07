# Nội dung điền form DENSO · Robot Skill Data Flywheel

**Cập nhật 07/10/2026.** Mục tiêu mới là PoC 30 ngày: model học task từ dữ liệu có sẵn trước, hướng tới inference trên robot thật do BTC bố trí. Native training và robot demo của đội chưa thực hiện. Kế hoạch sim 8–12 tuần trước đây là tham khảo mở rộng, không thay thế mục tiêu vật lý.

## Danh mục quan tâm

Chọn **Dữ liệu (Tạo giá trị tối đa từ dữ liệu)**. Có thể chọn thêm **Con người** vì hướng tới giảm công thu mẫu và thử lại; hiệu quả này cần đo. Chưa có bằng chứng để chọn mục năng lượng, đúng hạn hay không lỗi.

## 1. Vấn đề bạn nhận thấy

Khi đưa robot sang vật hoặc vị trí thao tác mới, kỹ sư thường phải thu mẫu, kiểm dữ liệu, huấn luyện và chạy thử nhiều lần. Có nhiều video chưa đồng nghĩa robot học tốt: dữ liệu có thể trùng, thiếu action đúng, lệch thời gian hoặc không bao phủ tình huống robot đang làm sai. Chi phí nằm ở người vận hành, reset robot, kiểm mẫu, GPU và những lần thử không tạo cải thiện.

Điểm cần giải là **dùng dữ liệu nào, để model học phần nào và có giúp robot hoàn thành công việc tốt hơn không**. Đội đề xuất kiểm bằng một task thao tác có dataset public tương thích trước; sau đó triển khai trên robot BTC. Công đoạn, tiêu chuẩn và chi phí hiện trạng tại DENSO cần xác nhận với người phụ trách.

## 2. Giải pháp bạn đề xuất

### Mục đích của giải pháp

Xây vòng cải thiện kỹ năng robot từ dữ liệu thực thi. **Trong 30 ngày, mục tiêu là model học được một task, nạp checkpoint chạy lại và hoàn thành một vòng cải thiện từ lỗi. Đích demo là inference trên robot thật**, phụ thuộc BTC cung cấp robot và thông số tích hợp đủ sớm. Dùng dữ liệu có sẵn để phát triển trước khi nhận thiết bị, với một robot/task và miền điều kiện giới hạn. Demo kiểm tính khả thi; lợi ích tiết kiệm và mở rộng cần kiểm tiếp. GR1 public là bước kiểm pipeline, không cam kết chuyển checkpoint sang robot BTC bất kỳ hoặc làm hai task trong tháng.

### Công nghệ sử dụng

Giải pháp gồm **Data Core** và **Model Engine Core**. Data Core kiểm chất lượng, quản lý phiên bản/splits và chọn dữ liệu bổ sung từ lỗi. Model Engine Core kế thừa FluxVLA để nối dataset, fine-tuning, evaluation và deployment. GR00T N1.5 là policy ưu tiên cho tuyến GR1; model đưa lên robot BTC phải tương thích embodiment và GPU thực tế.

Ảnh/lệnh đi qua VLM tạo đặc trưng. Action Expert kết hợp đặc trưng với state robot để học action chunks từ demonstrations. Kế thừa pretrained model, ưu tiên mở Action Expert/adapters và giữ backbone frozen nếu recipe hỗ trợ; manifest xác nhận modules/loss/gradients thực tế. Không pretrain VLM nền từ đầu. RTX 5090 dùng đo khả năng training/inference, RTX 3060 12GB hỗ trợ dữ liệu/kiểm nhỏ. Chưa bảo đảm recipe GR00T vừa bộ nhớ hoặc 3060 chạy toàn model.

### Dữ liệu đầu vào

- **Có sẵn trước:** FluxVLAData, subset RoboCasa GR1. Pilot một task đúng nhãn public, ưu tiên `PnPBottleToCabinetClose` (gắp chai vào tủ và đóng tủ). MP4 RGB, Parquet state/action/timestamps, JSON/JSONL metadata/instruction, LeRobot v2.1. Preview có 30 episodes/task folder, 20fps, state/action 29D; phải audit instruction và metadata split cũ trước dùng. Không đổi nhãn task này thành gắp linh kiện vào khay A1.
- **Khi có robot BTC:** demonstrations/corrections của đúng robot và task, cùng schema logic nhưng profile riêng. Có thể khởi đầu 20–50 train demonstrations hợp lệ nếu cần adaptation; số đủ phải đo. Action space, đơn vị, camera và tần số phải đúng hardware. Dataset GR1 public không mặc nhiên phù hợp robot khác.
- **Augmentation/simulation:** cách tạo mẫu từ train roots, dùng khi bảo toàn nhãn hoặc simulator thực thi để ghi targets mới đã QA. Không là modality/dataset input độc lập. Ưu tiên reuse dữ liệu hợp lệ và expert correction; chưa bắt buộc sim-to-real trong tháng đầu.
- **Cấu hình:** checkpoint nền, processor/stats, camera/controller/calibration và tiêu chuẩn thành công. Chia train/development/final theo phiên/mẫu gốc trước tạo variants. Giữ episode thất bại cho chẩn đoán, không tự biến thành action mẫu đúng.

Human/action-free video và FOCA có objectives riêng, nằm ở hướng mở rộng. Latent vector là output encoder, không phải nguồn dữ liệu độc lập.

### Dữ liệu đầu ra

Checkpoint đã fine-tune kèm recipe, processor/stats và robot profile để nạp lại; dataset có phiên bản/QA; báo cáo baseline/candidate; traces và video task. Đầu ra đích là video **robot thật chạy policy học được**, khi điều kiện hardware đạt. Inference tạo action chunks, controller chuyển thành lệnh, scorer đo outcome riêng. Báo cáo ghi toàn bộ số lần thử, thành công/lỗi/can thiệp, độ trễ và công/GPU thực dùng; phân biệt kết quả sim với hardware.

## 3. Quy trình thực hiện công việc

### Trước cải tiến

Quy trình đối chứng dự kiến: thu mẫu, huấn luyện, chạy thử rồi thu thêm khi robot sai. Thiếu liên kết giữa lỗi, mẫu bổ sung và cấu hình model khiến khó biết gain đến từ dữ liệu hữu ích, nhiều compute hơn hay sửa controller. Đây là giả thuyết cần khảo sát, chưa khẳng định quy trình hiện tại của DENSO.

### Sau cải tiến

1. Dùng dataset public đúng task, kiểm source/rights, nhãn và robot profile. Chốt yêu cầu robot BTC song song.
2. QA/chia tập, tạo batch: RGB/text thành features VLM, state xử lý theo profile, future actions làm target Action Expert. State không mặc định normalize nếu recipe không dùng.
3. Fine-tune, lưu/nạp checkpoint, đánh giá closed-loop trong môi trường tương ứng dataset. Model nhận quan sát mới mỗi lượt thay vì phát lại trajectory.
4. Khi nhận robot BTC, kiểm mapping/controller/camera, chọn policy/profile tương thích và thu adaptation data nếu cần, rồi chạy task thật. Chuyển embodiment là công việc riêng, không chỉ đổi tên robot.
5. Từ lỗi development, kiểm hệ thống trước, chọn dữ liệu/correction cho điều kiện yếu, QA release mới và train với replay. So baseline/candidate, sau đó freeze và final giữ riêng.

Vòng data flywheel: **chạy → bằng chứng lỗi → chọn dữ liệu → model học → chạy và đo lại**. Lỗi mapping/controller dẫn đến sửa tích hợp; chưa đủ bằng chứng thì chưa kết luận phải training.

## 4. Hiệu quả mang lại

Tháng đầu kiểm model học task và pipeline dữ liệu–training–evaluation–inference chạy được. So policy trước adaptation, baseline sau fine-tuning và candidate sau data update để tránh nhận năng lực pretrained là kết quả học mới. Báo cáo full-task, lỗi/can thiệp, độ trễ, unique demonstrations và tổng công.

Khi có hardware, đề xuất final nhỏ **20 lượt robot thật cho mỗi baseline/candidate**, cùng danh sách điều kiện khởi đầu giữ riêng, cân bằng thứ tự và reset. Mục tiêu PoC dự thảo cho candidate: **ít nhất 16/20 lượt hoàn thành không can thiệp trong timeout đã chốt**. Báo cả độ bất định; đây không là chuẩn tin cậy sản xuất. Nếu candidate không cải thiện, báo no-gain. Nếu chỉ hoàn thành sim, ghi rõ chưa đạt mục tiêu demo thật. Train/inference chạy được chưa chứng minh flywheel tiết kiệm hơn cách thu thông thường.

Nguồn lực đã xác nhận: RTX 3060 12GB và RTX 5090; robot phụ thuộc BTC. Chưa chốt giờ người/robot nên chưa có tổng ngân sách hoặc tỷ lệ tiết kiệm xác nhận. Ledger tính công kỹ sư, thu/reset/QA, robot, GPU/điện hoặc thuê, lưu trữ/vật tư và retries. Thiết bị đã có không đồng nghĩa chi phí sử dụng bằng 0.

## 5. Sự vượt trội/độc đáo của ý tưởng

**Mỗi lần robot sai tạo ra một quyết định dữ liệu có thể kiểm lại.** Hệ thống nối điều kiện thất bại, dữ liệu được chọn, phần model cập nhật và kết quả robot sau học để biết mẫu nào thực sự có ích.

Đội kế thừa VLA/FluxVLA, tập trung xây vòng dữ liệu–học–thực thi–đánh giá với chất lượng, nguồn gốc và tổng công rõ ràng. Điểm nhấn demo là một lần cải thiện có trace và so sánh trước/sau. Ưu thế so với thu thêm mẫu thông thường cần đối chứng cùng ngân sách sau PoC; chưa nhận là thuật toán VLA mới. Scale bằng tái sử dụng releases/adapters/QA và lựa chọn coverage, không chỉ tăng số video.

## 6. Kế hoạch triển khai trong bao lâu

**PoC 30 ngày, 13/10–11/11/2026**, dự phòng 12–15/11, hướng tới demo thật trước thuyết trình 16/11. Phát triển bằng dữ liệu public ngay khi chờ BTC; mốc hardware phải thống nhất với BTC.

| Thời gian | Pipeline / công việc | Bằng chứng bàn giao |
|---|---|---|
| Tuần 1 · 13–19/10 | Audit public task, loader/splits, GPU batch/update/reload. Lấy thông số và lịch robot BTC. | Dataset v1 đúng nhãn, receipt update/nạp lại, baseline pretrained. Chốt recipe theo VRAM thực. |
| Tuần 2 · 20–26/10 | Fine-tune từ public data, closed-loop evaluation trong sim tương ứng. Kiểm robot bridge nếu đã có thiết bị. | Checkpoint baseline, video/traces sim, kết quả held-out. 26/10 kiểm quyền truy cập, profile/task, camera/controller I/O và recipe update/reload để chốt lịch physical demo. |
| Tuần 3 · 27/10–02/11 | Robot-compatible adaptation/inference nếu có hardware. Chọn một failure bucket, reuse/correction có mục tiêu, train với replay. | Release v2, candidate, video development và before/after. Ghi rõ sim hay robot thật. |
| Tuần 4 · 03–09/11; hoàn tất 10–11/11 | Freeze checkpoint/profile/scorer rồi final giữ riêng. | Video task, số lần thử/báo cáo chất lượng–công, gói nạp lại. Final robot thật khi hardware gate đạt. |

Robot/controller/camera/collector phù hợp nên có chậm nhất tuần 2 để còn thời gian adaptation và test; đây là **giả định planning cần BTC xác nhận**, không bảo đảm hai tuần đủ cho một robot mới. Nếu chưa có quyền truy cập hoặc profile không tương thích, trình bày PoC sim đã đạt và kế hoạch robot thật có ngày phụ thuộc, không gọi mô phỏng là hoàn thành mục tiêu vật lý.

Từ 17–29/11, củng cố theo phản hồi, tăng số lần kiểm và hoàn thiện real-robot demo cho chung kết 02/12 nếu còn thiếu. Không dồn toàn bộ tích hợp hardware đến cuối. Lịch này là đề xuất nhóm mapping theo mốc BTC, không là yêu cầu BTC bắt buộc robot demo ở vòng 2.

## Tải lên ý tưởng

Đính kèm PowerPoint hiện hành dưới 15MB. Bổ sung tên đội/thành viên, đầu mối và yêu cầu xác nhận robot/task/lịch tiếp cận. Các mục chưa được BTC xác nhận ghi pending, không chờ hardware mới nộp ý tưởng. Chưa gửi lên form.

## Link liên quan

- [Repository dự án](https://github.com/hiwe0305/denso-challenge), khi người chấm có quyền xem. Localhost không phải link nộp.
- Video demo của đội: bổ sung sau khi quay/xuất bản, hiện chưa có.
- [FluxVLA](https://github.com/FluxVLA/FluxVLA), công cụ kế thừa; video tác giả không phải kết quả của đội.

## Đối chiếu lịch

Nguồn chính thức [DENSO Factory Hacks 2026](https://densohackathon.vn/), kiểm 07/10/2026: nộp ý tưởng 12/10, đánh giá online 13–19/10, thuyết trình 16/11, chung kết 02/12. Mapping hồ sơ/ý tưởng → thuyết trình → chung kết. Đoạn 13/10–11/11 có 30 ngày lịch tính cả hai đầu. Làm PoC trong thời gian chờ xét ý tưởng để còn buffer trước 16/11; chờ hết 19/10 mới bắt đầu 30 ngày sẽ lỡ mốc này.

Chi tiết pipeline và gates: [kế hoạch hiện hành](../idea-v3-2026-10-05/08-ke-hoach-trien-khai.md). Kết quả paper và samples public là cơ sở tham khảo, không thay chứng cứ đội đã training hoặc chạy hardware.

### Yêu cầu demo theo thể thức BTC

[Trang thể thức](https://densohackathon.vn/challenges), đọc trực tiếp 07/10/2026: vòng 2 yêu cầu video demo tối đa 15 phút và pitch, thể hiện input/output, environment, thiết bị, data/resource và quy trình xử lý. Vòng 3 ghi mentoring/phát triển 20/10–02/12, hạn nộp trước 23:59:59 ngày 30/11 và demo trực tiếp 02/12. Giai đoạn phát triển hiển thị chồng với vòng 2, không phải ba tháng nối tiếp. Nộp slide PPTX hoặc Canva công khai ở vòng 3. Chưa thấy yêu cầu mọi video vòng 2 bắt buộc phải là robot thật; đây là mục tiêu mạnh hơn do nhóm đề xuất, phụ thuộc BTC cấp thiết bị.
