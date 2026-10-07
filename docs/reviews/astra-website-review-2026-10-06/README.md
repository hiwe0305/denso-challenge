# Đánh giá toàn bộ website — Model Engine Core × Data Flywheel

Chốt ngày **07/10/2026**, trên bản website được quan sát ngày 06/10/2026. Ba reviewer **Astra** phụ trách model/robotics, dữ liệu/kiểm chứng và nội dung/sản phẩm; root đối chiếu kết luận, kiểm website đang hiển thị và tái hiện các lỗi có thể kiểm tra riêng. Đây là **báo cáo đánh giá**, chưa sửa website và chưa thực nghiệm native VLA.

**Kết luận:** idea có hướng hợp lý và phần Model AI đã hiện diện thực chất. Website đã nối dữ liệu → objective → model → controller → evaluation, đồng thời phân biệt khá tốt thiết kế dự kiến với reference đã chạy. Điểm cần làm mạnh hơn là biến Data Flywheel thành một **quy trình quyết định dữ liệu có giá trị đo được**, rồi chứng minh nó trên native policy. Hiện chưa đủ bằng chứng để nhận hiệu quả native, human transfer, tiết kiệm hay khả năng vận hành robot thật của chính dự án. Điều này phù hợp các caveat đang có; không phải phát hiện website giả mạo những kết quả ấy.

Đọc cùng ba báo cáo chuyên môn:

- [Astra — Model và robotics](01-model-robotics.md).
- [Astra — Dữ liệu, flywheel, kiểm chứng và nguồn lực](02-data-evaluation.md).
- [Astra — Nội dung, sản phẩm và triển khai website](03-content-product.md).

## 1. Phạm vi và cách kiểm

Đối tượng là **working tree**, không chỉ Git HEAD `e45cf7f0309f3fe58112c98c10b1111f5bee1864`. [snapshot.json](snapshot.json) cố định SHA-256 của 61 file nội dung/render chính. Các file này được đối chiếu lại ngày 07/10; không thay đổi so với snapshot. Các báo cáo chuyên môn ghi thêm đường dẫn, phiên bản và hash của nguồn đã đọc.

Root đã mở đủ **13 route** trên desktop ngày 06/10 và lưu [quan sát theo route](browser-all-routes.json), kèm các file `browser-*.json` có nội dung/controls. Đã thử riêng liên kết hồ sơ và đường từ Model Engine sang tài liệu kỹ thuật. Đây không phải kiểm mọi nút, mọi trạng thái, mobile hoặc khảo sát người dùng. Một số accessibility snapshot phản ánh trạng thái trước khi hash navigation hoàn tất; kết luận route dựa vào DOM text/H1 sau chuyển trang và kiểm code tương ứng.

Ngày 07/10, kết nối lại browser bị chính sách browser từ chối; không dùng đường khác để vượt chặn. Báo cáo dùng quan sát đã lưu và bản nội dung có hash không đổi, cùng kiểm tĩnh/tái hiện cục bộ. Không nhận có thêm lượt kiểm UI trực tiếp ngày 07/10.

Đã chạy: kiểm website tĩnh đạt **13 routes / 36 documents / 18 story scenes / 5 improvement cases**; kiểm cú pháp ba renderer chính đạt; `git diff --check` đạt. Các kiểm này không chứng minh nội dung khoa học đúng hoặc mọi liên kết mở đúng tài liệu. Root còn kiểm ZIP, tái hiện phụ thuộc PDF bị thiếu và kiểm riêng temporal guard; không chạy lại reference study hay native training.

Các nhãn dùng trong báo cáo:

- **Lỗi xác nhận:** có đường code/bằng chứng tái hiện cụ thể.
- **Rủi ro thiết kế:** có cơ chế gây vấn đề hợp lý, chưa quan sát thất bại trong native system.
- **Chưa xác minh:** thiếu phép đo/artifact trong phạm vi kiểm; không đồng nghĩa không thể làm được.
- **Trade-off chấp nhận được:** có chi phí/giới hạn nhưng phù hợp phạm vi đã khai báo.

Không chấm điểm tổng tùy ý; mức ưu tiên được tách khỏi mức chắc chắn của bằng chứng.

## 2. Nhận xét của anh: đúng ở đâu, cần điều chỉnh ở đâu?

| Nhận xét | Đánh giá và cách mapping vào idea |
|---|---|
| Phải bắt đầu bằng vấn đề thực tế, có dẫn chứng và chi phí | **Đúng.** Paper/video cho thấy vấn đề có tiền lệ, nhưng chưa xác nhận pain point hoặc chi phí tại DENSO. Cần một task owner, workflow hiện tại và các khoản công cần giảm. Không dùng kết quả công ty khác làm ROI của mình. |
| Data organization/use/scale mới là trọng tâm | **Đúng như thesis cần kiểm.** Chưa có căn cứ khẳng định đây luôn là bottleneck lớn nhất. Binding, controller, pretrained policy, inference latency và objective cũng có thể chặn task. Bắt đầu bằng useful native baseline để biết dữ liệu có cơ hội tạo khác biệt. |
| Ít nhưng chất lượng tốt sẽ giúp model | **Đúng có điều kiện.** Đúng nhãn và QA là điều kiện cần; usefulness còn phụ thuộc coverage, task, parent checkpoint và cách sampling. Một bộ rất sạch nhưng chỉ chứa trường hợp dễ có thể không giải failure bucket. Xem D01/D02 trong báo cáo dữ liệu. |
| Synthetic không phải một input modality riêng | **Đúng.** Synthetic là cách tạo: appearance augmentation, sim-executed trajectories và neural-generated video có supervision khác nhau. Có thể phát hành thành dataset/release riêng để truy vết, nhưng loader/loss phải dựa vào capability thực có. Không cần ép mọi synthetic vào cùng một route. |
| VLM nhận ảnh + text; video có thể tách frames | **Đúng ở mức mô tả phổ biến.** Cần ghi thêm sampling thời gian, views/history và objective. Tách video thành frames không tự tạo motion/action labels; VLM/VLA cụ thể có thể dùng temporal modules khác nhau. |
| Latent là vector encode từ VLM hoặc encoder khác | **Đúng nhưng chưa đủ contract.** Phải pin encoder, preprocessing, layer/token, time indexing, normalization và cache revision. Latent representation, latent action và predicted future latent có vai trò khác nhau; không tự thay thế nhau. |
| Robot actions chỉ dùng để train Action Expert, VLM không pretrain lại | **Cần điều chỉnh.** Có thể freeze VLM để post-train Action Expert, nhưng action loss cũng có thể cập nhật visual/interface parameters nếu recipe mở chúng. “Không pretrain từ đầu” khác “freeze mọi VLM parameters”. Website đã nêu khác biệt giữa official N1.5 và config FluxVLA được chọn. |
| FOCA action-free phù hợp few-shot | **Đúng trong scope của paper.** Action-free video supervision không xóa nhu cầu robot action supervision ở downstream control. Lợi ích trong cấu hình tác giả không chứng minh few-shot A1; nhánh này vẫn là extension có gate riêng. |
| Chọn FluxVLA vì hỗ trợ training → eval → inference robot thật | **Lý do hợp lệ ở cấp framework.** Báo cáo FluxVLA mô tả lifecycle và hardware deployment; điều đó chưa chứng minh A1/GR1 binding của dự án đã chạy. Cần tách platform capability, policy recipe và project receipts. [FluxVLA v1](https://arxiv.org/html/2609.17210v1). |
| Phải giữ cả Model AI và Data Flywheel | **Hoàn toàn phù hợp.** Model Engine thực thi learning/evaluation/inference; Data Core quản lý dữ liệu, evidence và quyết định vòng sau. Cả hai cùng cần thiết. Đóng góp dự kiến nằm ở quyết định và hiệu quả sử dụng dữ liệu theo task, không chỉ ghép tên nhiều model. |

Hai bằng chứng hữu ích để mở câu chuyện vấn đề: Figure báo một pipeline thu video với công lọc, review, dedup và annotation đáng kể; con số **15 triệu USD** là tiền trả creator, không phải tổng chi phí data pipeline. Trong báo cáo Helix 2.5, tác giả công bố tăng success từ **9% lên 56%** trên ba hành vi ở 30 nhà chưa thấy, với điều kiện comparison họ mô tả. Đây là tiền lệ đáng chú ý về dữ liệu, không phải dự báo gain/cost cho A1. [Index](https://www.figure.ai/news/introducing-index), [Helix 2.5](https://www.figure.ai/news/helix-2-5-zero-shot-30-home-generalization).

Một câu hỏi nghiệp vụ còn mở là **vì sao cần humanoid cho A1 gắp–đặt một tay, torso cố định, thay vì robot arm**. GR1 có thể là research vehicle phù hợp vì integration/dataset sẵn có; đó chưa là bằng chứng lợi thế vận hành nhà máy. Cần owner xác nhận công đoạn, tần suất đổi skill, công thu/reset/QA/debug và các lựa chọn hiện có. Không được kết luận humanoid sai chỉ từ task pilot hẹp; cũng không được dùng lý do thuận tiện nghiên cứu làm lý do đầu tư thiết bị.

## 3. Những phần tốt cần giữ

1. **Taxonomy sạch hơn trước:** origin, creation method, supervision và representation tách riêng; file extension không bị đồng nhất với ý nghĩa dữ liệu.
2. **Đường model đã có nội dung:** VLM features, Action Expert/DiT, state/embodiment/noise/time, flow objective, action chunk, binding/controller và scorer được phân biệt. Framework, policy và simulator không bị gom thành một model.
3. **Human không bị biến thành robot joint labels:** motion target, geometry/time/masks, adapter và comparator `R_common` được nêu. Wrist-only thiếu finger/contact là giới hạn đã nhận.
4. **Không tự động suy nguyên nhân lỗi:** evidence → giả thuyết → controlled test; command mapping sai đi repair, không mặc định thêm data/train.
5. **Development/final, roots/variants và negative cases được giữ:** reference C local pass nhưng final fail không được promote. R 0/12, S 12/12, C 0/12 được ghi đúng scope model thu nhỏ.
6. **Ưu tiên hình paper gốc:** FluxVLA Figures 1–5 có credit/provenance và cách mở xem; không cần thay bằng hình tự dựng đẹp nhưng làm sai cơ chế.

Không có căn cứ từ audit này để kết luận phương pháp human transfer nói chung không thể làm, synthetic vô ích, correction vô ích, hoặc model native chắc chắn không chạy được. Các báo cáo chuyên môn giữ counterevidence và điều kiện của từng nguồn.

## 4. Các vấn đề cần xử lý theo ưu tiên

### R01 — Nối mô tả model với một native run kiểm được

**Trạng thái:** chưa xác minh; chặn claim native/real-robot, không chặn nghiên cứu tiếp. **Vị trí:** model training → inference/controller → evaluation; `#learning/#engine/#examples/#validation`.

Website có architecture hợp lý, nhưng reference đang chạy là predictor tuyến tính **35×4**, idealized state, scripted sequencer và proximity weld. Native loader/gradient/reload/GR1 rollout chưa được chứng minh trong hồ sơ. Vì vậy reference kiểm được plumbing và gates, chưa kiểm được visual grounding, flow matching, contact-valid grasp hay transfer. Website đã ghi rõ; cần giữ nhãn này ngay cạnh mỗi kết quả, không thêm disclaimer dài ở mọi chỗ.

**Làm cụ thể:** đưa một bảng “selected native run” lên Engine: pinned code/checkpoint, task/profile, tensors thật, target/loss, modules được mở, action semantics và receipt còn thiếu. Bước đầu là upstream smoke → A1 expert replay → one-batch update/reload → learned closed-loop baseline, trước source study. Một batch backward thành công chưa chứng minh skill; một expert replay thành công chưa chứng minh policy học.

**Kiểm phân biệt:** cùng binding/scorer/domain, kiểm learned policy từ natural starts, predicted action → sent command → measured response → outcome. Giữ debug/optimized inference parity. Chi phí là native integration và vài pilot runs có cap; không cần mở H/FOCA trước khi baseline dùng được.

### R02 — Chứng minh giá trị của quyết định dữ liệu, không chỉ chứng minh thêm nguồn có ích

**Trạng thái:** rủi ro/missing specification; D01. **Vị trí:** ACQUIRE → release → train → development eval → quyết định vòng sau.

R vs R+S trả lời “S giúp recipe này không?”. Nó chưa trả lời “Data Core chọn can thiệp tốt hơn workflow kỹ sư thường không?”. QA, retrieval similarity và số accepted samples cũng chưa trả lời utility. Site đã thừa nhận khác biệt này ở `03-workflow-du-lieu.md:24`; điểm cần thêm là receipt và study đủ cụ thể để kiểm được.

**Làm cụ thể:** mỗi vòng ghi failure bucket, facts/alternatives, supervision cần, các lựa chọn reuse/augmentation/correction/generation/repair, lý do chọn, cap, release IDs, parent/candidate, gain/regression và actual cost. Giữ cả no-gain/stop. Sau native/source feasibility, so workflow có evidence với workflow thường trên matched cases, cùng intervention access/cap; kiểm case/order/engineer familiarity. Không cần xây learned selector trước.

**Kiểm phân biệt:** downstream full-task gain và total work tới quality threshold, không loss/retrieval score đơn lẻ. Đây là phần làm thesis data flywheel mạnh hơn việc chỉ có vòng mũi tên. [DataMIL v1 §4](https://arxiv.org/html/2505.09603v1) là tiền lệ về utility gắn algorithm/metric, không thuật toán đã tích hợp của dự án.

### R03 — QA phải đi kèm coverage và chống trùng nội dung

**Trạng thái:** rủi ro, chưa phát hiện native bias/leakage thực tế; D02/D04. **Vị trí:** ingest/root graph/split và S_exec → release.

Lọc successful executions có thể giữ nhiều vùng dễ, bỏ vùng khó mà policy cần. MimicGen trực tiếp khảo sát bias sau filtering trong Appendix R; đây là risk prior, không chứng minh generator A1 đã mắc cùng lỗi. Tương tự, root IDs đúng chưa đủ nếu một recording bị mirror/crop/re-encode rồi nhận ID mới. [MimicGen v1, App. P/R](https://arxiv.org/pdf/2310.17596v1).

**Làm cụ thể:** release có requested/attempted/accepted/rejected coverage theo bucket, unique parents và sampling weights. Canonical source recording/episode/time range, exact hashes và duplicate-family grouping trước split; corpus nhỏ không cần hạ tầng near-duplicate quá nặng. QA fail không được bỏ qua chỉ để lấp quota.

**Kiểm phân biệt:** cùng attempt cap, so sampling hiện tại với coverage-aware sampling; downstream eval và total generation/QA cost. Inject duplicate/crop/re-encode dưới IDs khác để kiểm split grouping. Chi phí gồm logging/hashing và review ambiguous pairs; generation/train bổ sung phải vào ledger.

### R04 — Gate thống kê hợp lý nhưng trade-off quyết định chưa đủ rõ

**Trạng thái:** lựa chọn chưa chốt, không phải lỗi công thức; D03. **Vị trí:** final evaluation → acceptance → budget.

Draft đề nghị 100 independent starts, lower bound exact một phía 95% ≥90%. Dưới giả định IID Bernoulli, cần ít nhất 96 successes; 95 chưa đủ. Với true success 95%, xác suất vượt gate chỉ khoảng **43,6%**; với 97% khoảng **81,8%**. Đây là tính toán operating characteristic của reviewer, không số đo robot. Gate bảo thủ có thể đúng, nhưng owner cần hiểu nguy cơ no-pass/inconclusive và chi phí.

**Làm cụ thể:** chốt estimand, sampling/strata, training-seed plan, operating characteristics và rule khi không pass trước final. Nếu cần chứng minh source advantage/equivalence, cần paired difference/margin/power riêng; hai policies cùng pass không tự là equivalent. Không điều chỉnh n/ngưỡng sau khi thấy final. Xem công thức và giới hạn trong D03; [SciPy exact CI](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats._result_classes.BinomTestResult.proportion_ci.html).

### R05 — Đồng bộ chi phí, lịch, kết quả kỳ vọng và authority

**Trạng thái:** lệch nội dung xác nhận; native resource feasibility còn chưa xác minh; D05 và báo cáo nội dung. **Vị trí:** `#overview/#business/#roadmap/#outcomes/#resources`.

Overview/form có **5.187,20 USD** subtotal pilot giả định, trong khi trang Chi phí chủ yếu hiển thị stress model lịch sử **9.315,89 → 16.359,98 USD** và ledger chưa đo. Các con số không sai chỉ vì khác nhau, nhưng người đọc chưa thấy current planning budget tại đúng trang. Form/overview dự kiến **8–12 tuần có điều kiện**, roadmap chỉ có gates. Outcomes mở claim ledger thay vì trình bày bàn giao/acceptance trước. Recipe A1 lại tự ghi chưa thay website/authority trong khi nhiều trang đã tham chiếu nó.

**Làm cụ thể:** một authority map và dữ liệu chung cho current scope/budget/timeline; history chỉ nằm phần tham khảo. Trên business hiển thị subtotal hiện tại, assumptions/exclusions và actual ledger riêng. Roadmap có 4 chặng 2–3 tuần là planning assumption sau resource gate, H/action-free là nhánh tùy chọn. Outcomes: bàn giao cụ thể → tiêu chuẩn nghiệm thu → current evidence → phần chưa chạy.

Subtotal $5.187,20 gồm $4.800 integration/preparation/report, $40 capture/reset, $40 QA, $286,20 GPU cap và $21 storage. Không gồm robot/cell, CPU riêng, license/data fees, thuế/downtime/production; không phải quote hay savings. Không kiểm lại giá thị trường trong audit này. Cap **180 A100 GPU-hours** chưa cho biết job set hoàn tất: cần measured VRAM/throughput, steps/repeats/eval/retries và công người. Không có cơ sở kết luận cap chắc chắn thiếu hoặc đủ.

### R06 — Luồng đọc chưa đồng đều giữa các trang

**Trạng thái:** nhận định UX từ cấu trúc và quan sát desktop, chưa user-tested. **Vị trí:** navigation và nội dung từng route.

Các trang trực quan mới (`learning/sources/engine/architecture`) cùng tồn tại với các trang in nguyên tài liệu. `product/outcomes/business/roadmap/validation` dùng chung H1 “Cách làm và điều kiện kiểm chứng”, làm mất câu hỏi riêng của trang. Overview chứa nhiều tầng giải pháp, source, model, benchmark và form; examples có 36 headings, research có 41 ở trạng thái quan sát. Số headings không tự là lỗi, nhưng trùng nội dung/thuật ngữ làm tăng công tìm câu trả lời.

**Làm cụ thể:** mỗi trang có một câu hỏi chính, một visual/table quyết định, một evidence/status block; bản kỹ thuật đầy đủ nằm details/resources. Giữ original paper figures, dùng chú thích chỉ đúng 2–3 phần liên quan và nút mở lớn. Một episode xuyên suốt phải giữ cùng task/profile/release/checkpoint; public videos khác task được ghi “minh họa nguồn”, không đóng vai bằng chứng A1. Cải thiện không đồng nghĩa xóa schema/loss/params khỏi phụ lục.

**Kiểm phân biệt:** người đọc mới có tìm được trong vài phút: vấn đề gì, model học gì từ dataset nào, đã chạy gì, chi phí gì, lỗi nào cần repair/train phần nào? Kiểm thêm mobile, keyboard/focus, media fallback và các trạng thái expand; audit hiện chưa xác nhận toàn bộ các mặt này.

Sở thích dùng ảnh tác giả đã được đáp ứng tốt ở framework FluxVLA. Ở phần policy, nên ưu tiên thêm **architecture figure gốc N1.5** có source/credit/version, rồi để custom A1 branches trong sơ đồ riêng. Không chỉnh hình gốc khiến common wrist hoặc FOCA candidate trông như component upstream. Chỉ thêm hình nếu người đọc phân biệt được pretrained VLM, Action Expert và training-only loss rõ hơn.

### R07 — Liên kết hồ sơ có thể mở nhầm README hoặc thành chữ không bấm được

**Trạng thái:** lỗi xác nhận. **Vị trí:** resources Markdown resolver, `app.js:296–304`.

Resolver tìm tài liệu bằng **basename** trước khi xác định đường dẫn. Link “kế hoạch triển khai” tới README A1 và `examples/engineering-loop/README.md` cùng trỏ doc0, tức README hồ sơ tổng. Root đã tái hiện trên UI; [receipt](browser-resource-link-repro.json). Các `.md` không có trong DOSSIER rơi về span. Đây là lỗi định tuyến tài liệu, không phải thiếu click handler chung: đường Engine → hồ sơ kỹ thuật **đã hoạt động** và nhận xét ngược lại đã bị loại.

**Làm cụ thể:** resolve relative path theo document hiện tại, normalize path, rồi tra full canonical path; manifest cho tài liệu chưa đưa vào reader, hoặc link tải đúng file. Test hai README khác nhau và IDEA/A1 recipe. Thêm kiểm đích tài liệu, vì kiểm “link có href” không bắt được lỗi này.

ZIP chính “folder đầy đủ” có 52 entries và **7 relative Markdown links thiếu đích**, tới form/A1 recipe/manifest/README. [Danh sách](portable-link-check.json). Gói A1/full bundle khác có tồn tại; không kết luận mọi package hỏng. Cần đóng gói dependency closure hoặc ghi phạm vi gói rõ, rồi kiểm links trong chính ZIP.

### R08 — Build phụ thuộc PDF local bị ignore

**Trạng thái:** lỗi xác nhận khi thiếu prerequisite; chưa quan sát một hosted CI run thất bại. **Vị trí:** `build-content.py:14`, `.gitignore:16`, workflow Pages.

Builder bắt buộc đọc `docs/references/papers/FluxVLA.pdf` để kiểm hash, nhưng thư mục PDF bị ignore và workflow không provision nó. Root tái hiện trong thư mục tạm với catalog/figure hợp lệ, PDF vắng như clean checkout: **FileNotFoundError tại dòng 14**. [Receipt](build-prerequisite-repro.json). Đây là kiểm prerequisite có giới hạn, không phải chạy toàn bộ CI.

**Làm cụ thể:** giữ kiểm hash/provenance ảnh bắt buộc; tách full-PDF verification thành research check tùy chọn, hoặc provision đúng PDF pinned/hash/license trước build. Thêm clean-checkout build check. Không cần bỏ original figures để giải lỗi; vấn đề là nguồn phụ thuộc của builder.

### R09 — Reference temporal guard kiểm step, chưa kiểm timestamp

**Trạng thái:** lỗi xác nhận trong reference; D06. **Vị trí:** `examples/engineering-loop/run.py:23–36,162–168` và claim temporal validation.

`fit()` từ chối step không tăng nhưng không đọc `timestamp`. Root giữ hai rows hợp lệ có steps 0/1 và chỉ thay timestamp thành đảo chiều, trùng hoặc NaN; cả ba vẫn fit/reload được. [Receipt](reference-clock-repro.json). Không có bằng chứng artifacts đang lưu bị clock sai; finding không phủ định outcomes reference hoặc quy lỗi cho native loader.

**Làm cụ thể:** đổi wording thành “step order” hoặc bổ sung finite/monotonic/spacing checks theo episode và dt, với tests timestamp riêng. Đây là sửa nhỏ, không cần GPU/native training. Không nên dùng test tên “clock” nhưng chỉ duplicate step làm bằng chứng temporal QA đầy đủ.

### R10 — Nếu mở FOCA, single-task A1 cần negative-pool contract

**Trạng thái:** rủi ro có điều kiện, chỉ material khi chọn nhánh này; M02. **Vị trí:** optional video-future objective, không phải baseline native đang chạy.

FOCA v1 §3.3, Eq. (10)–(11), trang 5 chọn negatives từ episodes có task description khác. Nếu pool chỉ chứa đúng một task A1 và tuân thủ nguyên điều kiện đó, tập negatives rỗng; mẫu số chỉ còn positive, nên mỗi hạng InfoNCE là `−log(1)=0`. Đây là suy luận đại số, chưa phải kết quả A1. Nếu dùng mọi mẫu cùng task làm negatives để tránh rỗng, objective đã được thay đổi và có nguy cơ false negatives. Đổi cách viết một instruction không tự tạo nhiều semantic tasks. [FOCA v1](https://arxiv.org/html/2606.20867v1).

**Phản chứng:** có thể dùng train-only multitask pool từ nguồn video/pretraining; thiết kế chưa cấm điều đó. Site đã ghi đây là candidate, nên không được gọi là loss A1 đang hoạt động bị hỏng. Cần pin semantic task IDs, pool/provenance/sampling, minimum negatives và zero-negative handling; nếu đổi objective thì ghi rõ adaptation.

**Kiểm phân biệt:** trước training lớn, kiểm batch đơn task và multitask, eligible-negative counts, loss/gradient/source–target paths; rồi mới so action-only với action+implicit và control gain cùng protocol. Chi phí gồm data pool/sampling/QA và extra compute. Một cảnh báo slicing trong mã upstream `main` được Astra giữ ở **phụ lục M05**, chưa pin commit/chưa chạy forward; không dùng nó để kết luận website hoặc FOCA nói chung lỗi.

Một chỉnh sửa nhỏ khác: catalog gọi “auxiliary human heads” nên ghi rõ **common wrist18D + shared Action Expert trunk, custom candidate**, thống nhất recipe chi tiết. Đây là làm rõ nhãn, chưa có bằng chứng hai kiến trúc thực thi mâu thuẫn.

## 5. Đánh giá đủ 13 trang

| Trang | Giữ | Ưu tiên sửa |
|---|---|---|
| Ý tưởng & vấn đề | Pain point, evidence boundary, cả Model AI và flywheel | Một workflow/task/người dùng; nêu công cần giảm trước nhiều nhánh model; paper evidence không thay DENSO evidence |
| Sản phẩm & khác biệt | Thesis evidence → acquisition → quality/cost | Ghi đóng góp, người dùng và deliverables; bỏ câu phản hồi hội thoại khỏi bản trình bày chính; H1 riêng |
| Solution · Cách robot học | Luồng trực quan observation → features → action | Một native run card có shapes/loss/params; tách train/inference rõ, phần kỹ thuật mở dần |
| Model Engine Core | FluxVLA lifecycle, hình gốc, policy/controller boundary | Phân biệt upstream supported vs project integrated; binding/reload/parity receipts; chốt phiên bản |
| Kết quả kỳ vọng | Claim/evidence/scope trung thực | Bàn giao và acceptance trước claim ledger; phân biệt target, measured và pending |
| Chi phí & tính khả thi | Total cost, unknown ≠0, stop rules | Current subtotal + exclusions + resource RunPlan; history xuống phụ lục |
| Lộ trình thực hiện | Artifact gates và dependency | Planning durations có điều kiện, owners và optional branches; không biểu diễn H như bắt buộc |
| Dataset & cách tạo | Bốn trục taxonomy, formats, target/gradient | Một sample record→batch thực; coverage/dedup receipts; source IDs không thay data capabilities |
| Dữ liệu & video thật | Episode walkthrough, raw previews, negative cases | Giảm đổi task/embodiment trong luồng chính; phân biệt upstream video, project replay và native result |
| Khảo sát phương pháp | Đã rộng hơn FOCA; khác objective/runtime | Decision matrix chọn/không chọn theo A1; pin nguồn/version; không leaderboard chéo benchmark |
| Kiến trúc & Data Core | Repair khác training, manual decisions, final isolation | AcquisitionDecisionReceipt, realized utility/cost, reuse skill2; không tự động chẩn đoán nguyên nhân |
| Thiết kế kiểm chứng | Source contrasts, full-task/regression/final | Expose A1 statistical plan/power; workflow study riêng; scope/source/compute controls |
| Hồ sơ & nguồn gốc | Source/receipt access, historical labels | Full-path links, authority map, dependency-complete ZIP và clean build |

## 6. Cấu trúc nội dung nên hướng tới

Một luồng đọc chính:

**Vấn đề + người dùng + công hiện tại → task pilot và tiêu chuẩn → dataset/release cụ thể → training steps và params/loss → benchmark/eval → inference trace → failure hypotheses và controlled tests → quyết định repair/data/update → gain/regression/cost → vòng sau.**

Trong phần model, bốn bước nên giữ rõ:

| Bước | Dữ liệu đi qua | Model học/chạy gì | Receipt cần có |
|---|---|---|---|
| 0. Khóa native baseline | RGB/views, instruction, state/profile; actions cho train | Checkpoint pretrained; loader/controller/scorer tương thích | Config/data/code hashes, tensors, expert replay và smoke trace |
| 1. Robot-only | Target-robot demonstrations/corrections hợp lệ | Action objective; actual trainable modules theo selected recipe | Loss/grad/update/reload, full-task baseline, roots và công thu |
| 2. R+S pilot | Cùng robot roots + variants thực thi/QA, hoặc appearance giữ nghĩa | Cùng policy/recipe controls; không biến video sinh thành actions thật | Coverage/yield/rejects, same-budget comparison, total work |
| 3. Nhánh đủ điều kiện | H motion có geometry/masks hoặc video action-free với objective riêng | Một route đã implement; comparator đúng; không mở mọi nhánh cùng lúc | Batch/gradient route, downstream robot eval và extra compute/cost |

Sau mỗi candidate, inference chỉ dùng thông tin triển khai được; future targets/outcome oracle chỉ ở training/evaluation. Không lấy giảm future-prediction loss làm bằng chứng control gain. Nếu thêm World Model vào runtime, phải xác định model dự đoán gì, action conditioning/goal/candidate access và controller chọn action thế nào; đó là một nhánh nghiên cứu khác cần controls tương ứng, không tính năng mặc định của VLA hiện tại.

## 7. Thứ tự hành động khả thi

**Đợt A — sửa tính nhất quán và khả năng xem/đóng gói:** R07/R08/R09, authority map, current budget/timeline/outcomes và H1/reading hierarchy. Những việc này nhỏ hơn native integration và có check rõ; không tạo claim khoa học mới.

Trước khi nộp, cần đồng bộ deck/PDF/DOCX với current scope/budget/native status và kiểm lại yêu cầu form tại nguồn chính thức. Hồ sơ tự ghi deck cũ chưa cập nhật, localhost không truy cập được từ ngoài. Đây là trạng thái draft, chưa phải bộ nộp đã được kiểm; audit này không xuất hoặc gửi form.

**Đợt B — native critical path:** task/profile/checkpoint rights và feasibility → upstream smoke/A1 expert replay → batch/update/reload → learned baseline closed-loop → measured resource plan. Sau đó mới source eligibility/generation pilot và R vs R+S. Không lấy 8–12 tuần hoặc 180 GPU-hours làm cam kết trước measured gates.

**Đợt C — chứng minh flywheel:** decision/coverage/cost receipts trong development, final protocol phù hợp, comparison với workflow kỹ sư thường và reuse skill2. H motion/FOCA/World Model chỉ mở khi có hypothesis và cap riêng. Kết quả no-transfer/no-saving/no-added-value vẫn là kết quả hợp lệ để điều chỉnh idea.

Phép kiểm có giá trị nhất tiếp theo là **một native baseline end-to-end có receipts và cost measurements**, tiếp theo một can thiệp dữ liệu matched và downstream eval. Viết thêm nhiều method hoặc vẽ thêm vòng lặp không thay được hai bước đó.

## 8. Bản đồ kiểm định và giới hạn

[Sơ đồ kiểm định có finding IDs](architecture-review.svg) là **bản tái dựng của reviewer từ thiết kế dự án**, không phải hình paper, không phải kiến trúc đã thực thi đầy đủ và không phải redesign được áp dụng. Training, inference/control, evaluation và website delivery được đặt thành các lane riêng. [Graph và structured findings](architecture-review.json) giữ stable node/edge IDs và scope của từng nhận xét; đây là artifact local, không được ghi vào Research Workspace database.

Các báo cáo Astra là các góc nhìn chuyên môn độc lập của agent, không phải peer review của tác giả paper hay chứng nhận của DENSO. Nguồn tác giả được dùng làm tiền đề có phạm vi; audit không tái lập kết quả paper. Chưa có khảo sát DENSO, báo giá/hợp đồng, đo robot thật, clean hosted CI run hay mobile/accessibility audit đầy đủ. Không nâng absence trong hồ sơ thành kết luận artifact không tồn tại ở nơi khác.

Website và hồ sơ gốc được giữ để anh có thể đối chiếu với báo cáo. Các sửa đổi và phép thử trên đây vẫn là **đề xuất**, trừ những bounded checks có receipt đã chỉ rõ.
