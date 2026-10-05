# 07 · Chi phí từ dữ liệu tới nghiệm thu và vận hành

_Dự toán engineering, cập nhật thiết kế 05/10/2026; đơn giá giữ snapshot có ngày nguồn. Đơn giá công khai có nguồn; số lượng và thời gian là giả định. Chưa có time-motion, báo giá cell DENSO, checkpoint hoặc saving thực nghiệm. USD; không tự dùng lương Mỹ làm lương Việt Nam._

## Đọc nhanh cho hồ sơ idea

Lợi ích kỳ vọng đến từ giảm thu mẫu robot và thử nghiệm lặp lại, chọn dữ liệu phù hợp và tái dùng quy trình. Tổng công phải tính cả xử lý video, QA, train/eval và retry. Bật nhiều nguồn không tự rẻ hơn.

| Phạm vi | Snapshot mặc định làm tròn | Cách đọc |
|---|---|---|
| R&D mô phỏng 12 tuần | Khoảng 38.000 USD subtotal | 480 engineer-hours dùng labor proxy Mỹ + compute/storage; chưa gồm acquisition chưa báo giá |
| Một skill sau pipeline | Khoảng 9.300 → 16.400 USD/skill đầu ở full-source stress scenario | Không là recipe được chọn; giảm30% mẫu trong giả định này chưa bù overhead |
| Robot thật/nhà máy | Cần báo giá và time-motion riêng | Không cộng chồng chi phí giữa các phạm vi |

Các số là dự toán giả định, không phải báo giá Việt Nam/DENSO hoặc saving thực nghiệm. Bộ tính website cho phép khảo sát nhưng giữ nguyên công thức và dữ liệu nguồn. Chưa thể kết luận lợi ích kinh tế; cần đo tổng công ở cùng quality và mức reuse thực tế.

## Cùng quality, cùng nền tảng đối chứng

Baseline: cùng pretrained VLA + target-robot teleop → post-training; có thể thêm augmentation thường và nhập khoản này. Kịch bản full-source tham chiếu bật human/internet bridge và appearance synthetic đồng thời; đây là stress scenario chi phí, không recipe core bắt buộc sau review. Core so T/F/A từ R0 theo Protocol. Không khẳng định mọi workflow công nghiệp chỉ dùng teleop. Đối chứng có tiền lệ ở [FluxVLA](https://github.com/FluxVLA/FluxVLA); robot collection ở [DROID](https://droid-dataset.github.io/).

Giảm robot demonstrations chỉ có ý nghĩa khi hai arms thực sự đạt cùng accepted quality. 400 → 280 accepted roots là giả thuyết mục tiêu 30%, không kết quả learning curve. Human clips/frames/synthetic variants không đếm thành robot demonstrations độc lập. Mọi failed attempts, rejected synthetic, retry, calibration, corrections và evaluation đều có cost.

## Ba phạm vi ngân sách sau review

| Phạm vi | Đơn vị / nội dung | Không được suy ra |
|---|---|---|
| R&D mô phỏng 12 tuần | Engineering toàn study + từng train/bridge/generation/eval job + storage + acquisition thực tế | Không dùng tổng một skill thay toàn study hoặc cộng cả study vào skill |
| Một skill sau pipeline | Collection/QA/train/eval + phần integration phân bổ theo reuse thực tế | Không giả mọi adapter đã có sẵn hoặc mọi task dùng đủ bốn nguồn |
| Production / real cell | Hardware đúng cấu hình, plant integration, commissioning, latency/reliability, vận hành/downtime | Sim pass không là production acceptance; cần báo giá và time-motion |

Website có planner riêng tại [pilot-budget.json](../presentation-site/content/pilot-budget.json), dùng chung đơn giá với mô hình skill. Minh họa 480 engineer-hours (1 người ×12 tuần ×40h), 15 target train jobs, 6 bridge jobs, 1 generation batch, 15 eval jobs và 3 tháng storage. Đây là **giả định chưa benchmark**, không staffing/budget đã duyệt. Bridge/generation có thể tắt sau gate. Mỗi job kế thừa GPU-hours tham chiếu: train120, bridge50, generation20, eval20; retry theo model gốc. Engineering gồm implementation/QA/selection/debug/analysis, không cộng lại giờ engineer acquisition cùng activity.

Subtotal planner chưa gồm operator capture, acquisition fees/licensing, cell, CPU/network và khoản chưa quote. Ghi missing rõ; không gọi subtotal là total đủ của 12 tuần. Các inputs và trường scope đi cùng output.

T/F/A có acquisition ledger riêng: engineer planning/selection/QA, operator/reset, GPU và other costs. **Ô trống là unknown; chỉ số 0 đã xác nhận mới là không phát sinh.** Cap500 USD/arm/parent chỉ minh họa, khóa lại sau E0; đầy đủ cap và rẻ hơn chưa chứng minh cùng quality. Total incremental ledger thêm train/eval/analysis sau acquisition, ghi scope/activity IDs để tránh double-count. Lựa chọn do engineer duyệt; không tự gán gain cho gói chưa thử.

## Kết luận kinh tế cần giữ

Kịch bản full-source gốc giữ nguyên: 9.315,89 →16.359,98 USD/skill đầu, tăng7.044,09 USD; recurring tăng1.415,52 USD. Giảm30% từ400 robot roots chỉ tiết kiệm khoảng400,24 USD collection trong assumptions này; source overhead lớn hơn. Không sửa các assumptions để tạo saving đẹp hơn. Robot/GPU giảm không đủ nếu engineering/QA tăng.

Hòa vốn theo số robot roots trong cùng mô hình, **nếu** quality và giảm30% được chứng minh: khoảng7.440 baseline roots với một skill hoặc2.377 roots khi integration dùng lại10 skills. Đây là sensitivity có điều kiện, chưa learning curve hoặc khuyến nghị thu từng đó dữ liệu. Kịch bản2.000 →1.400 với reuse10 vẫn đắt hơn377,41 USD/skill.

## Đơn giá và bằng chứng công khai

| Tham chiếu | Loại | Cách sử dụng / giới hạn |
|---|---|---|
| [Runpod Pods: A100 PCIe 80GB 1,59; H100 SXM 3,49; RTX4090 0,74 USD/GPU-giờ](https://www.runpod.io/pricing) | Giá công khai | Giá trang hiển thị 02/10/2026. Không dùng serverless rate. Giờ là toàn thời gian thuê; số GPU phải nhân vào GPU-giờ. Chưa xác nhận vùng/SLA/khả dụng hay config model. |
| [Runpod Network Storage Standard: dưới 1TB, 0,07 USD/GB-tháng](https://www.runpod.io/pricing) | Giá công khai | Mô hình dùng đơn giá này làm proxy và cho sửa khi dung lượng/tier thay đổi; không áp cho Volume Disk hoặc mặc định mọi dung lượng. |
| [BLS assemblers/fabricators: median 21,85 USD/giờ, tháng 5/2025](https://www.bls.gov/ooh/production/assemblers-and-fabricators.htm) | Tham chiếu nghề nghiệp Mỹ | Proxy lương người vận hành, không phải khảo sát teleoperator, báo giá DENSO hoặc mức lương Việt Nam. |
| [BLS industrial engineers: median 49,25 USD/giờ, tháng 5/2025](https://www.bls.gov/ooh/architecture-and-engineering/industrial-engineers.htm) | Tham chiếu nghề nghiệp Mỹ | Proxy QA/tích hợp kỹ thuật; không là lương robotics engineer đã đo tại DENSO. |
| [BLS ECEC private industry, tháng 6/2026: wages 70%, benefits 30% tổng chi phí](https://www.bls.gov/news.release/ecec.t01.htm) | Tỷ lệ tham chiếu + suy luận | Loaded proxy = lương / (1 − 0,30). Áp tỷ lệ chung vào median nghề là giả định mô hình, không mức loaded wage nghề đã được BLS đo. |
| [DROID: 76.000 demonstrations, 350 giờ interaction, 564 scenes, 86 tasks](https://droid-dataset.github.io/) | Bằng chứng collection robot thật | Khoảng 16,6 giây interaction/demo từ phép chia. Không bao gồm mọi setup/reset/QA hoặc tiền công, không dùng nó làm chi phí trọn gói một demo. |
| [FluxVLA: pretrained policies, target-robot post-training, SDG/HITL và evaluation](https://github.com/FluxVLA/FluxVLA) | Phương pháp đối chứng có tiền lệ | Baseline ở đây là cùng pretrained base + target-robot teleop, có thể bật augmentation thường. Không khẳng định tất cả ngành hiện chỉ dùng teleop. |

Loaded operator proxy = 21,85/(1−0,30) = 31,2143 USD/h; engineer = 49,25/(1−0,30) = 70,3571 USD/h. Tỷ lệ benefits chung áp vào median nghề là suy luận mô hình, không BLS đo loaded rates riêng cho nghề. Có thể thay wage và burden bằng payroll địa phương.

DROID 350h/76.000 ≈16,6s recorded interaction/demo chỉ minh họa duration; chưa là person-time sau setup/reset/QA hoặc chi phí/demo. Public source không công bố tổng collection USD để dùng làm benchmark giá.

## Công thức chi tiết

- Attempts = accepted demos / QA yield. Reject vẫn trả capture/reset/QA.
- Capture hours = attempts × (record minutes + setup/reset minutes) /60.
- Robot QA hours = attempts × QA minutes /60.
- Economic robot-use USD/h = cell capex/(lifetime years ×12× useful h/month) + maintenance/month/useful h/month + kW×electricity USD/kWh.
- Human capture và human/internet curation tính riêng operator và engineer hours; quyền license không mặc định free cho mọi clip.
- Synthetic generation dùng GPU-hours gồm retries/reject; QA ghi engineering hours. Không suy số outputs hữu ích từ GPU price.
- Post-train/bridge GPU-hours × train price × (1+retry reserve). Preprocess, generation, evaluation có giờ riêng; không áp retry hai lần. Giờ thuê gồm idle, số GPUs nhân vào GPU-hours.
- Per-skill recurring = tổng collection, QA, calibration/debug, source overhead, preprocess/generation/train/eval, real acceptance, storage và chi phí còn thiếu.
- Per-skill total = recurring + one-time integration / reuse skill count.
- Break-even skills = ceil(extra one-time integration / recurring saving) khi recurring saving >0. Nếu không, chưa có điểm hòa vốn trong model.

## Kịch bản pilot tham chiếu

| Khoản | Baseline USD | Đa nguồn USD |
|---|---:|---:|
| Thu robot: ghi + setup/reset, gồm failed attempts (recurring) | 650.30 | 455.21 |
| QA robot, gồm mọi attempt bị reject (recurring) | 586.31 | 410.42 |
| Sử dụng robot trong collection (recurring) | 97.53 | 68.27 |
| Task/scorer/calibration (recurring) | 1,266.43 | 1,266.43 |
| Debug/correction review (recurring) | 422.14 | 703.57 |
| Thu human clips (recurring) | 0.00 | 104.05 |
| Human tracking/stage + internet rights/relevance QA (recurring) | 0.00 | 820.83 |
| Phí quyền dữ liệu (recurring) | 0.00 | 0.00 |
| Generation, gồm sinh lại và reject (recurring) | 0.00 | 69.80 |
| QA synthetic (recurring) | 0.00 | 422.14 |
| Target post-train, gồm retry reserve (recurring) | 219.42 | 219.42 |
| Bridge, gồm retry reserve (recurring) | 0.00 | 91.42 |
| GPU preprocessing bổ sung (recurring) | 0.00 | 19.08 |
| Sim / development evaluation (recurring) | 14.80 | 14.80 |
| Real acceptance trials: execute/reset (recurring) | 260.12 | 260.12 |
| Review acceptance trials (recurring) | 117.26 | 117.26 |
| Robot trong acceptance trials (recurring) | 39.01 | 39.01 |
| Storage trong pilot (recurring) | 14.00 | 21.00 |
| Chi phí còn thiếu / augmentation đối chứng (recurring) | 0.00 | 0.00 |
| Tích hợp nền chung, một lần (oneoff) | 5,628.57 | 5,628.57 |
| Source adapters / heads / QA mới, một lần (oneoff) | 0.00 | 5,628.57 |
| Recurring mỗi skill | 3,687.32 | 5,102.83 |
| Tổng skill đầu, một lần tích hợp tính đủ | 9,315.89 | 16,359.98 |

Với inputs tham chiếu, đa nguồn **tăng 7,044.09 USD/skill** và recurring cũng cao hơn. Không có break-even do dùng lại tích hợp khi recurring chưa rẻ hơn. Đây là kết quả công thức có điều kiện, không so sánh chất lượng đã đo.

## Khảo sát quy mô và độ nhạy

| Quy mô giả định | Baseline /skill | Đa nguồn /skill | Chênh lệch giảm USD |
|---|---:|---:|---:|
| Pilot 400 → 280 · 1 skill | 9,315.89 | 16,359.98 | -7,044.09 |
| Collection lớn 2.000 → 1.400 · dùng lại 10 skills | 9,586.71 | 9,964.12 | -377.41 |
| Không giảm robot demos · 400 → 400 | 9,315.89 | 16,760.22 | -7,444.33 |
| Đối chứng có augmentation thường | 9,565.89 | 16,359.98 | -6,794.09 |

Sensitivity thuận lợi/khó thay yield, reset, QA, human/internet curation, bridge/generation và tích hợp. Trường hợp khó không giảm robot demos. Khoảng là phạm vi kế hoạch, không CI/statistical forecast; không ghép baseline best với candidate worst để claim saving. Toàn bộ inputs/scenarios/ranges trong [mô hình duy nhất](../presentation-site/content/industrial-cost-model.json). Website cho sửa 53 inputs và tải kết quả JSON, không có annual ROI toy model thứ hai.

## Vận hành và TCO công nghiệp có phạm vi

| Economic cost vận hành mỗi phương án | USD/tháng |
|---|---:|
| GPU dedicated, tính cả idle | 532.80 |
| Monitoring / model maintenance | 562.86 |
| Robot capital phân bổ tháng | 1,250.00 |
| Cell maintenance cố định | 200.00 |
| Cell electricity khi hoạt động | 48.00 |
| Storage + backup | 21.00 |
| OPEX chưa mô hình hóa | 0.00 |
| Tổng | 2,614.66 |

Tham chiếu cash mua cell + triển khai một skill +12 tháng vận hành sau pilot: baseline 100,577.84; đa nguồn 107,646.34 USD. Loại allocated capital trong development/ops trước khi cộng tiền mua robot một lần. Không cộng purchase và depreciation hai lần.

OPEX ngang nhau khi hai policy cùng inference/runtime; không giả human/video/generator phải chạy trong mỗi chu kỳ. Cloud dedicated GPU 720h/tháng tính cả idle; local compute và real-cell latency cần benchmark riêng. Operator sản xuất, downtime, monitoring ngoài giả định cần bổ sung.

Cell 75.000 USD, 5 năm, 320h hữu ích/tháng, maintenance 200 USD/tháng, power 1kW, điện 0,15 USD/kWh là **planning assumptions, không giá robot đã xác minh**. Cần báo giá robot đúng developer/hand/controller/camera/cell cấu hình, không lấy giá base robot làm cell turnkey. Chưa có landed costs, thuế, vận chuyển, fixture mới, kiểm định, plant downtime, bảo hiểm, CPU/network/egress/SLA/consumables ngoài các ô “chi phí còn thiếu”. Mô hình là scoped estimate, chưa đủ để ký investment decision.

## Đo tại pilot để thay giả định

Thu time-motion theo activity và vai trò; attempts/yield và reasons reject; public data rights/licensing receipts; GPU count×allocated wall-hours (kể cả failed jobs); storage GB-month; controller/task integration hours; all acceptance trials và ID/OOD quality. Chi phí sponsored compute vẫn có economic cost; datasets đã có và thu mới báo riêng. Khóa same-task/same-quality trước cost claim.

[Protocol E0–E4](06-validation-and-roadmap.md) · [Kết quả dự kiến](13-expected-outcomes.md) · [Điểm idea](reviews/idea-review.md).

12 contrast runs chỉ áp khi comparator/parent phù hợp đã có trong core; nếu cần train thêm parents hoặc rerun health baseline, phải cập nhật run grid và study budget trước. 27 không là trần tuyệt đối của mọi thí nghiệm.
