# Review C · Nội dung, sản phẩm và mức sẵn sàng trình bày

Ngày snapshot: 06/10/2026. Hoàn tất tiếp ngày 07/10/2026, theo snapshot đã khóa. Reviewer: Astra, phạm vi nội dung website và hồ sơ, không sửa website.

## Kết luận phục vụ quyết định

Website đã có câu chuyện kỹ thuật đủ cụ thể để trao đổi với kỹ sư robot learning: dữ liệu có loại supervision nào, đi qua model/loss nào, inference xuất gì, khi lỗi kiểm gì trước và can thiệp nào phải được đánh giá lại. Trang Model Engine Core giải thích được lý do chọn FluxVLA; phần lớn ranh giới giữa framework, policy, reference và native A1 được giữ đúng. Không tìm thấy cơ sở để kết luận cả đề xuất chỉ là animation hoặc mô tả model chung chung.

Điểm yếu lớn hiện tại là **đường đọc và phát hành không theo cùng một hệ thống nội dung**. Năm mục menu vẫn đổ thẳng tài liệu engineering vào một tiêu đề giống nhau. Trang “Kết quả kỳ vọng” thực tế là sổ claim của reference; “Chi phí” không đưa dự toán pilot hiện hành lên; “Lộ trình” không cho biết 8–12 tuần. Các liên kết tới authority/pilot quan trọng có lỗi thật. Gói tải “đầy đủ” bỏ sót tài liệu được dẫn, còn bước build dùng PDF local không có trong clean checkout. Những vấn đề này có thể sửa mà không cần tạo thêm nghiên cứu hay thêm route.

Về business case, bằng chứng hiện có chứng minh cơ hội nghiên cứu robot learning, **chưa xác nhận một điểm nghẽn DENSO và chưa giải thích vì sao công đoạn gắp–đặt một tay cần humanoid**. Website đã nói rõ điều đó; đây là khoảng trống thương mại còn mở, không phải gian lận claim. Ở vòng idea, không cần giả vờ đã có deployment hoặc savings. Cần trình bày ai sẽ xác nhận gì, chi phí trước/sau sẽ được đo ra sao, và điều kiện nào khiến đội chọn arm hoặc dừng pilot.

Không chấm điểm tổng bằng con số. Báo cáo phân biệt lỗi tái hiện được, lệch mục đích nội dung và nhận định usability. Không tuyên bố vi phạm WCAG: review này không thực hiện phép kiểm tiêu chuẩn accessibility đầy đủ.

## Cơ sở chuyên môn và giới hạn bằng chứng

Đọc nguồn gốc trước khi đánh giá UI:

- **FluxVLA Engine, arXiv:2609.17210v1, 15/09/2026:** abstract, §1.2–1.3, §2.6, §3.1–3.5 và các đoạn runtime liên quan. Paper trình bày engineering platform và contracts nối data, training, evaluation, inference, operator; không đưa ra một policy architecture phổ quát. Figure 1 ghi rõ ngân sách training/evaluation khác nhau giữa integrations. Đây là cơ sở để đánh giá ranh giới engine/policy và không suy bảng benchmark thành kết quả A1. [Paper gốc](https://arxiv.org/html/2609.17210v1), [repository tác giả](https://github.com/FluxVLA/FluxVLA).
- **GR00T N1.5, NVIDIA, 11/06/2025:** Architecture, Joint Policy Learning and World Modeling Objective, Training, các điều kiện post-training. Eagle tạo embeddings, DiT xử lý state/noised actions; official recipe freeze VLM, FLARE dùng future embeddings. Điều này hỗ trợ cách website tách official recipe với Flux recipe mở visual; không chứng minh custom wrist pilot của đội. [Nguồn NVIDIA](https://research.nvidia.com/labs/gear/gr00t-n1_5/).
- Đã mở ảnh gốc được trích từ Figure 1 tại `docs/assets/fluxvla-paper-figure-1.png` để kiểm có giữ kiến trúc/bảng benchmark/nhãn trục. Không nhận là đã xem screenshot mọi trang. Figures 2–5 được kiểm tên/page/provenance/caption qua catalog và renderer, chưa audit trực quan từng pixel trong review C.
- Đối chiếu authority tại `IDEA.md`, form draft, canonical dossier và A1 implementation proposal. Không dùng paper để thay authority của project, không dùng nội dung project để tự chứng minh paper đúng.
- Browser evidence do reviewer chính thu bằng trình duyệt thật: `browser-*.json`, `browser-all-routes.json`, `browser-resource-link-repro.json`. Review C đọc DOM observations này và kiểm renderer/source; không tự nhận đã trực tiếp bấm mọi control.
- Kiểm hash tất cả file trong `snapshot.json`: không phát hiện file lệch snapshot tại thời điểm kiểm. Không build lại vì builder có ghi đè canonical snapshots; kiểm logic và đọc ZIP hiện hữu.
- Đã thử mở trang challenges chính thức nhưng công cụ trích văn bản chỉ nhận một liên kết ảnh. Vì vậy mapping form bên dưới dựa trên trường đã lưu trong `deliverables/DENSO-Noi-dung-form-y-tuong.md`; không tuyên bố đã tái xác nhận trực tuyến mọi quy định/giới hạn upload mới nhất.

## Những điểm nên giữ

1. **Problem/evidence/cost đã đứng trước anatomy của model trên overview.** Hero nêu công thu/reset/học lại; ba evidence cards có nguồn và phạm vi, rồi mới vào budget, datasets và training. Đây là cải thiện đúng hướng, không cần đảo trang về mở đầu bằng tên model.
2. **Một task A1 xuyên suốt.** Đặt đúng linh kiện vào ô, nhả/rút; phân biệt scene lỗi với claim nguyên nhân. Case “trượt khi chuyển” có thể bắt đầu từ grasp, nên kiểm expert-entry/policy-entry trước update scope. Đây là reasoning hữu ích, vượt mô tả “fail rồi fine-tune”.
3. **Model Engine Core có lý do tồn tại rõ.** `model-engine-core.js:7–16` dẫn training → eval → robot thật, có modules/contracts/artifacts, local/remote runtime và bảng ownership. Giữ Figure 1 gốc làm hình đầu; không thay bằng sơ đồ tự vẽ chỉ có VLM → Action Expert.
4. **Ba trục dễ bị nhầm đã được tách:** nguồn/cách tạo/supervision; pixels/features/action; data target/prediction/issued command/readback. `training-blueprint.json:5–14` và `overview-flywheel.json:85–114` hỗ trợ điều này.
5. **R_sim, S_exec và robot thật không bị đánh đồng ở authority.** `IDEA.md` phần robot demonstrations nói R của MVP thực thi trên robot đích trong sim; native/real acceptance tách riêng. Các public G1/GR1/HumanEgo clips được ghi là dữ liệu tác giả và không ghép giả thành paired A1 pipeline.
6. **Reference có giới hạn nhìn thấy được.** `engineering.js:9–14,40–47` nói idealized state, scripted sequencing, predictor học thật, weld grasp, C local pass/final fail. Không đổi tên reference thành GR00T demo. Đây là điểm đáng giữ khi rút gọn copy.
7. **Cách đo không khuyến khích kết quả đẹp giả.** Giữ all failures/unknown, root lineage, replay, no-gain, development/final riêng; R/R+S không được tự nhận chứng minh adaptive workflow. A1 document04 có controls cụ thể hơn trang validation.

## Findings theo mức ưu tiên

Mức P1: nên giải quyết trước khi gửi một link/gói để người khác tự đánh giá hoặc trước công bố business claim tương ứng. Mức P2: cải thiện tính rõ ràng, sự nhất quán và khả năng tự đọc. “Gap” không có nghĩa implementation sai.

### U01 · P1 · Liên kết authority/A1 trong trình đọc mở sai tài liệu hoặc biến mất

**Loại:** lỗi chức năng đã tái hiện. **Routes:** resources; các route có link vào dossier.

**Anchor:** `presentation-site/dist/app.js:296–304` chọn dossier bằng basename; `:313` xử lý document reader. `idea-v3-2026-10-05/README.md:3,38` dẫn `../IDEA.md`, `../docs/implementation-plan/skill-a1/README.md`, `../examples/engineering-loop/README.md`. Builder chỉ đưa engineering README vào DOSSIER (`build-engineering.py:65–68`); IDEA/A1 Markdown không nằm trong danh sách đó.

**Premise → kết luận:** README tuyên bố IDEA là bản gửi đánh giá và A1 là recipe mới nhất. Người đọc cần theo được liên kết để kiểm định nghĩa hiện hành. Renderer so `path.split('/').pop()` nên cả A1 README và example README đều khớp engineering README đầu tiên. IDEA không khớp thì trả `<span>`, A1 `02-recipes-and-data.md` cũng thành span. Đây không chỉ là thiếu breadcrumb: tài liệu khác bị gán thành cùng một đích.

**Bằng chứng:** root đã bấm resources → “kế hoạch triển khai”; `browser-resource-link-repro.json` ghi `data-document=0`, observedPath vẫn `idea-v3-2026-10-05/README.md`. “examples/engineering-loop” cũng doc0. Kiểm tĩnh xác nhận link IDEA không được tạo anchor.

**Counterevidence:** link từ engine tới doc17 **chạy đúng** nhờ global handler `app.js:226`; đã được root kiểm. Không đưa lỗi crosspage chung vào finding này. A1 files tồn tại tại `dist/data/skill-a1-plan`, nên dữ liệu không mất; lỗi là routing/catalog.

**Sửa cụ thể:** resolve đường dẫn tương đối theo document hiện tại rồi lookup full canonical path. Thêm IDEA/form/A1 vào reader hoặc tạo raw/download links đúng file. Mỗi entry dùng ID không phụ thuộc basename. Đừng âm thầm biến link không nhận diện thành text; hiện “mở file nguồn” nếu file được đóng gói.

**Next test:** từ README, lần lượt mở IDEA, A1 README, example README và recipe02; assert full path/title/content khác nhau. Mở từ product/learning và từ resources; reload trực tiếp tài liệu đã chọn để kiểm khả năng gửi link.

### U02 · P1 · Build để phát hành phụ thuộc PDF bị loại khỏi Git và gói portable

**Loại:** lỗi tái lập phát hành xác định từ code, inventory và reproduction cô lập. **Routes:** toàn website khi rebuild/deploy.

**Anchor:** `presentation-site/build-content.py:10–15`, đặc biệt dòng14; `.gitignore:16`; `.github/workflows/pages.yml:35`; `presentation-site/package.py:8–25`.

**Premise → kết luận:** catalog figures có `provenance.paper=docs/references/papers/FluxVLA.pdf`. Mỗi build đọc PDF này vô điều kiện để kiểm hash dù website đã có extracted PNG có hash. PDF không được track (`git ls-files --error-unmatch` trả lỗi; `git check-ignore -v` trỏ `.gitignore:16`). CI checkout chạy build-content nhưng không tải PDF. Vì vậy clean checkout không có input bắt buộc và sẽ thất bại trước publish; người nhận bundle không kèm bulky papers cũng không rebuild theo hướng dẫn được.

**Counterevidence:** website hiện tại và figures đã có trong dist nên vẫn chạy local/offline. Không kết luận production đang down, chưa chạy remote CI trong review này. Kiểm paper hash là một biện pháp provenance tốt; chỉ đang đặt vào sai mức bắt buộc của normal build.

**Reproduction bổ sung của root:** `build-prerequisite-repro.json` ghi bản copy builder/catalog/Figure1 trong thư mục tạm, cố ý không có ignored PDF, thất bại `FileNotFoundError` đúng dòng14. Đây là kiểm prerequisite, không phải một full hosted CI run. `verify-site.py` vẫn pass13routes/36docs trên dist hiện có; điều đó không bác bỏ lỗi clean build.

**Sửa cụ thể:** tách “extract/reverify from source PDF” khỏi normal publishing. Build thường verify PNG đã track bằng manifest; source-verification command đọc/tải pinned PDF và kiểm hash riêng. Hoặc đưa vào quy trình lấy PDF chính thức có hash trước bước build, nếu đội thật sự muốn build luôn dựa paper.

**Next test:** checkout sạch không có `docs/references/papers` → build → verify → package. Bài test này khác việc rebuild thành công trên máy tác giả có cache PDF.

### U03 · P2 · Gói “folder đầy đủ + example” chưa tự chứa các tài liệu nó dẫn đến

**Loại:** lỗi artifact đã kiểm ZIP. **Route:** resources/download.

**Anchor:** `engineering.js:21` gọi `assets/idea-v3.1.zip` là “Tải folder đầy đủ + example”; `build-engineering.py:69–81` chỉ đóng engineering folder, example và IDEA.

**Bằng chứng:** ZIP hiện hữu có 52 entries, 7 liên kết Markdown nội bộ không có target trong ZIP; root xác nhận độc lập và lưu `portable-link-check.json`. Các đích thiếu gồm `docs/implementation-plan/skill-a1/README.md`, `02-recipes-and-data.md`, `dataset-manifest.proposed.json` và `deliverables/DENSO-Noi-dung-form-y-tuong.md`; một target được dẫn nhiều lần. IDEA có mặt nhưng form mà IDEA dẫn không có.

**Ảnh hưởng:** người nhận tải đúng CTA chính, đọc tới recipe/format hoặc form hiện hành thì bị ngắt đường kiểm chứng. Điều này đặc biệt bất tiện khi website đã xác định A1 là recipe mới nhất.

**Counterevidence:** gói `skill-a1-plan.zip` riêng có tồn tại; bundle lớn do `package.py` có đưa A1/form vào. Không gọi mọi ZIP đều thiếu. Vấn đề là CTA chính không giải thích phải tải nhiều gói và package của nó không tự đủ.

**Sửa cụ thể:** thêm A1/form vào ZIP nhỏ theo đúng relative paths hoặc đổi CTA thành “Engineering reference + code” và đặt ba download rõ vai trò cạnh nhau. Ưu tiên một gói đọc hồ sơ duy nhất, có manifest ngày/phạm vi.

**Next test:** giải nén vào thư mục trống; đi theo toàn bộ Markdown local links từ README/IDEA. Không chỉ `testzip()` vì kiểm CRC không phát hiện target bị bỏ khỏi archive.

### U04 · P1 · Năm route mang câu hỏi sản phẩm nhưng nội dung trả lời câu hỏi engineering khác

**Loại:** lệch thông tin có evidence DOM; mức ưu tiên dành cho submission comprehension, không lỗi chuẩn accessibility.

**Anchor:** `engineering.js:3,24–25` map product→doc01, outcomes→doc12, business→doc06, roadmap→doc08, validation→doc05; tất cả được bọc h1 “Cách làm và điều kiện kiểm chứng.”. Browser observations xác nhận đúng renderer này đang hiển thị. Các hàm cũ đẹp hơn trong `app.js` không phải nội dung live và không được dùng để phủ nhận finding.

**Các trường hợp cụ thể:**

- **outcomes:** doc12 là claim → artifact ledger của reference, không cho người nộp biết native MVP sẽ bàn giao gì hoặc tiêu chí nhận. `12-bang-kiem-chung.md:3–18` hoàn toàn có ích, nhưng nên là “Bằng chứng hiện có”, không thay toàn bộ mục kết quả kỳ vọng.
- **business:** doc06 chỉ có cost taxonomy/resource gate và stress case lịch sử 9.315,89→16.359,98 USD (`06-chi-phi-va-kha-thi.md:19–21`). Dự toán pilot mới 5.187,20 USD và inputs có ở overview/form/doc01, nhưng vắng tại nơi người xem chủ động tìm chi phí. Không phải mâu thuẫn số học vì stress case có ghi lịch sử; là lỗi đặt thông tin khiến số lịch sử trở thành số nổi bật duy nhất của trang business.
- **roadmap:** doc08 là P0→P6 theo artifacts và gates, không hiện 8–12 tuần của form `:89` và doc01 `:84`. H nằm trong một bảng trình tự có thể bị đọc như bước phải làm, dù human/video có lịch riêng sau gate trong form.
- **product:** lặp gần trọn overview dưới dạng dài hơn; thiếu phần tóm tắt “người dùng nhận bộ gì, lần dùng đầu ra sao” ở đầu route. Persona có ở IDEA/A1; không phải chưa xác định persona ở toàn bộ hồ sơ.
- **validation:** nội dung protocol có giá trị, nhưng người đọc phải tự nối bảng R/H/S/HS tổng quát với R_common/R_common+H và acceptance draft trong A1 document04. Giao diện không dẫn họ tới recipe mới nhất một cách tin cậy do U01.

**Counterevidence:** URL, sidebar active item và document title có tên route riêng. Overview đã có form mapping, pilot budget và 8–12 tuần. Người đọc chịu khó vẫn tìm được phần lớn câu trả lời; finding không nói hồ sơ hoàn toàn thiếu.

**Sửa cụ thể:** mỗi route có một trang tóm tắt chuyên trách, dùng cùng authority rồi giữ full doc trong details. H1 nên trả lời câu hỏi route: “MVP bàn giao bốn thứ gì?”, “Pilot đầu cần bao nhiêu nguồn lực?”, “Bốn chặng trong 8–12 tuần”. Business đưa budget hiện hành cùng exclusions; historical case nằm trong details. Outcomes tách hai khối **Dự kiến bàn giao** và **Đã có bằng chứng gì**. Roadmap dùng bốn chặng và gate, human/video đặt nhánh riêng.

**Next test:** cho người chưa đọc repo bắt đầu ở từng route, hỏi trong 60 giây: nhận được gì, tốn bao nhiêu, kéo dài bao lâu, bằng chứng nào là của đội. Không cho đọc overview trước để che lỗi information scent.

### U05 · P1 khi chốt business case · Nhu cầu DENSO và lựa chọn humanoid vẫn là giả thuyết chưa có kế hoạch khảo sát nhìn thấy được

**Loại:** khoảng trống bằng chứng đã được hồ sơ thừa nhận; không kết luận sai kỹ thuật.

**Anchor:** `IDEA.md` phần2–3; `01-idea-va-pitch.md:8–18,84`; form `:17,57`; A1 README `:9`; overview hero/scope và `overview-flywheel.json:4–27`.

**Premise → kết luận:** Figure payout, FOCA LIBERO và household generalization cho thấy acquisition/method/data có giá trị nghiên cứu. Chúng không đo số lần đổi SKU, giờ reset/QA, tần suất dạy skill hoặc tổn thất chất lượng tại một công đoạn DENSO. A1 một tay, thân cố định, rigid pick-and-place chưa tự chứng minh lợi ích của humanoid so với arm. Chọn GR1 do có framework/data phù hợp là lý do cho research vehicle, chưa là lý do mua humanoid để vận hành.

**Counterevidence:** website nói rõ proxy, chưa khảo sát, chưa savings; đây là sự trung thực cần giữ. Một đề xuất H1 có thể hợp lệ trước native execution. Không nên “sửa” bằng số tiết kiệm giả hoặc tự suy humanoid không phù hợp.

**Sửa cụ thể:** thêm một card nghiệp vụ trước model: “Người cần giải: kỹ sư thêm/đổi skill; hiện chưa có công đoạn DENSO xác nhận. Pilot xác nhận: một task owner, một công đoạn, tần suất đổi thao tác, thời gian thu/reset/QA/debug, giải pháp hiện có. Chọn humanoid nếu có nhu cầu dùng nhiều vị trí/đồ gá phù hợp người và lợi ích vượt arm; A1 trước mắt kiểm phương pháp trên GR1 sim.” Những ví dụ lợi ích là tiêu chí khảo sát, không kết quả đã có.

**Next test:** phỏng vấn/task walk-through với owner; đo vài lượt phát triển skill thật hoặc surrogate có operator; lập bảng cùng task giữa workflow hiện có, robot arm và humanoid. Chưa có dữ liệu thì trạng thái “cần xác nhận”, kèm người chịu trách nhiệm và ngày quyết định.

### U06 · P2 · Thí nghiệm chính kiểm source utility; lời hứa nổi bật lại là quyết định dữ liệu tốt hơn

**Loại:** lệch trọng tâm giữa value proposition và thứ tự kiểm chứng; hồ sơ có counterevidence mạnh, chưa là sai claim.

**Anchor:** overview phần flywheel/form mapping; `01-idea-va-pitch.md:22–24,80,90`; A1 `04-evaluation-and-cost.md:5–9,33–37`; `data-flywheel.js:9`.

**Premise → kết luận:** R vs R+S có thể kiểm ích lợi của accepted synthetic ở một protocol, nhưng chưa kiểm kỹ sư dùng EvidenceCard/acquisition workflow có ra quyết định nhanh/đúng/rẻ hơn workflow thường. FluxVLA bản thân đã có data→train→eval→deploy và correction loop; “đóng vòng” chung chưa đủ để phân biệt đóng góp của đội. A1 document04 đã thừa nhận workflow evaluation là secondary experiment sau source/native feasibility, nhưng trang pitch chưa làm thứ tự bằng chứng này đủ nổi bật.

**Counterevidence:** `data-flywheel.js` và canonical03 ghi source pilots khác acquisition study; form không tự nhận thuật toán mới. Finding là cần nối đóng góp với phép kiểm, không yêu cầu chạy factorial grid lớn ngay.

**Sửa cụ thể:** một bảng ba hàng “Kế thừa / Đội xây / Cách chứng minh”: FluxVLA lifecycle → task/QA/trace integration → native receipts; sim generation prior → A1 coverage recipe → R/R+S; engineer decision support → evidence/cost templates → cùng case/cap/intervention access so workflow thường. Viết lời hứa thành hai nấc: “Pilot đầu chứng minh data route chạy và có ích; pilot tiếp theo đo liệu quy trình chọn data có giảm tổng công.”

**Next test:** sau native failures, thu các cases và so engineer-assisted task completion/accepted plan time/total work với comparator có năng lực thật. Trước đó báo khả năng triển khai và giả thuyết utility, không nhận superiority workflow từ S thắng R.

### U07 · P2 · Bản trình bày còn mang ngôn ngữ hội thoại nội bộ và chữ viết tắt vượt ngưỡng cần thiết

**Loại:** nhận định usability/editorial, có anchor câu chữ; không tiêu chuẩn vi phạm.

**Anchor:** `overview-flywheel.js:12–14` có “video anh gửi”, “Mapping nhận xét của anh”; doc01 `:18,74–80` được render trực tiếp ở product. `06-chi-phi-va-kha-thi.md:5–17` dày đặc scope/receipt/root/cap/quality; `engineering.js:25` đẩy nguyên văn ra mặt trang. Root đo visible words: overview1919, product1513, engine1487; không dùng độ dài này tự động kết luận trang xấu.

**Ảnh hưởng:** giám khảo ngoài cuộc trò chuyện không biết “anh” là ai, phản hồi nào đang được giải thích, và tại sao trang sản phẩm dành nhiều diện tích cho quyết định nội bộ. Trộn “receipt”, “artifact”, “root”, “binding”, “gate”, “same-quality” trong cùng một đoạn buộc người không chuyên giải mã ngôn ngữ trước khi hiểu lợi ích.

**Counterevidence:** learning chỉ khoảng235 visible words, sources350, architecture479; những trang này cho thấy progressive disclosure đã làm được. Người kỹ thuật vẫn cần thuật ngữ chính xác trong tài liệu sâu, không nên Việt hóa mất nghĩa tensor/action.

**Sửa mẫu:** “Mapping nhận xét của anh…” → “Các giả định đã chọn cho MVP”; “same-quality + total-cost” → “cùng mức chất lượng, tính đủ tổng công”; “root” ở lần đầu → “lần ghi nguồn độc lập (root)”; “binding” → “cấu hình nối camera, action và controller (binding)”. Đưa hội thoại nguồn vào review history, không live pitch. Một glossary gọn truy cập được từ mọi trang tốt hơn glossary chỉ nằm trong hàm resources cũ không còn render.

**Next test:** một người nghiệp vụ và một kỹ sư chưa đọc repo giải thích lại trong 90 giây: vấn đề, input/output, đoạn nào đội xây, đã chạy gì. Ghi thuật ngữ gây dừng đọc; rút từng đoạn theo bằng chứng comprehension.

### U08 · P2 · Ưu tiên hình tác giả đã làm tốt cho FluxVLA, chưa được áp dụng cho policy GR00T đang chọn

**Loại:** mức đáp ứng sở thích trình bày của người dùng; không khẳng định technical content sai.

**Anchor:** `model-engine-core.js:8–12` Figure1 + own model panel; `overview-flywheel.js:5–6` renderModelAI; `training-blueprint.js:9–13` model survey. `research-and-media.json:330–499` chứa original Flux figures, chưa có original GR00T architecture figure.

**Premise → kết luận:** người dùng ưu tiên paper/author diagrams trước. Engine page tuân thủ rất tốt cho framework; đến policy N1.5 lại chủ yếu là cards/sơ đồ do đội dựng. Nguồn NVIDIA có architecture diagram phân biệt VLM/DiT/future alignment. Một hình nguồn chọn đúng sẽ giúp người đọc hiểu cái gì pretrained, cái gì custom, thay vì thêm một sơ đồ chung nữa.

**Counterevidence:** current cards có nội dung đúng và dễ đọc, nguồn NVIDIA được dẫn; không nhất thiết đưa đủ hình của cả bảy methods lên trang đầu. Flux original figures đã có credits/version/page/hash và caption benchmark limits. Không đề nghị thay toàn bộ UI bằng paper figures nhỏ khó đọc.

**Sửa cụ thể:** trong engine/policy, đặt original N1.5 architecture figure có credit/source/phiên bản, rồi một sơ đồ A1 nhỏ bên dưới chỉ đánh dấu phần kế thừa và custom candidates. Human wrist route và FOCA branch phải ở trạng thái candidate riêng, không sửa nhãn hình gốc khiến chúng trông như upstream component.

**Next test:** hỏi người xem chỉ vào đâu là pretrained Eagle, action policy, loss chỉ lúc train và custom branch. Chỉ thêm hình nếu tăng đúng hiểu biết đó; giữ đầy đủ source caption.

### U09 · P2 · README và kiểm tra phát hành mô tả UI cũ; dữ liệu cũ vẫn có thể quay lại khi refactor

**Loại:** documentation/test coverage defect, tác động bảo trì nội dung; không nhận UI live đang dùng các số cũ.

**Anchor:** `presentation-site/README.md` đoạn “overview … interactive architecture, robot motion demo … 72-second film”, “14 current docs”, “HISTORY-v2.md”; `engineering.js:15–25` renderer live đã đổi; `app.js:30–180` còn nhiều route bodies cũ; `verify-site.py:30–35,58–110` kiểm đủ function names/legacy artifacts hơn là route thực render gì.

**Premise → kết luận:** app khởi động qua `renderEngineeringPage`, nên `function business/outcomes/roadmap` tồn tại không chứng minh chúng là trang đang dùng. Current verify check đủ13 functions vẫn pass khi route business hiện thiếu current budget hoặc route outcomes chỉ hiện ledger. Build đồng bộ Markdown bytes không phát hiện cùng một nội dung đang phục vụ sai mục đích ở menu.

**Counterevidence:** verify có giá trị rõ cho integrity/media/plan hashes và dossier freshness. Đây không phải lý do bỏ nó hay thêm tests mirror implementation. Không ghi 38k/27jobs/75% trong app.js legacy là claim live hiện hành.

**Sửa cụ thể:** một route registry khai renderer, authority và reader purpose; ghi README theo UI thực. Legacy modules/data dùng export riêng hoặc archive rõ ràng. Chỉ thêm vài user-level assertions có ý nghĩa: business có current-budget identifier, outcomes có expected deliverables, roadmap có gated duration, primary document links resolve đúng paths.

**Next test:** build sạch, mở13 routes qua public navigation, so route heading/authority IDs và thử link nghiệp vụ chính. Không chỉ kiểm source chứa `function route()`.

### U10 · P1 trước khi nộp · Website chưa có một bộ hồ sơ nộp hiện hành, truy cập được từ ngoài và được đánh dấu rõ

**Loại:** gap submission readiness tự khai; chưa audit hình thức slide/PDF.

**Anchor:** form `:93–103` ghi cần xuất/kiểm PDF/DOCX/PPTX đồng bộ, deck cũ chưa cập nhật, localhost không dùng từ xa; `engineering.js:21` resources chủ yếu là archive/reader; `overview-flywheel.js` cuối trang chỉ download Markdown form. Deliverables hiện có PPTX ngày05/10 trong khi form/engine cập nhật06/10.

**Ảnh hưởng:** người dùng có thể có website nội dung tốt nhưng chưa có artifact chính thức cùng phiên bản để điền/nộp. ZIP website/hồ sơ lớn là gói tham khảo, không tự thay submission file. Không kết luận PPTX chắc chắn sai mọi phần chỉ dựa ngày; form tự xác nhận chưa đồng bộ là bằng chứng đủ cho trạng thái chưa sẵn sàng.

**Counterevidence:** form draft đã trả lời đủ field và ghi chưa gửi. Không có hành động submit trái phép. Source/canonical docs tồn tại; đây là bước đóng gói cuối, không cần làm lại ý tưởng.

**Sửa cụ thể:** resources có ba lối rõ: “Bản để nộp · ngày/phiên bản/phạm vi”, “Hồ sơ kỹ thuật”, “Reference code & artifacts”. Sau cập nhật deck/PDF, kiểm lại form requirements ở nguồn chính thức và mở link public bằng phiên không đăng nhập. Giữ status “draft” đến khi review xong.

**Next test:** từ một máy/phiên ngoài localhost, tải được đúng file hiện hành; đối chiếu 8 field nội dung với website; các số budget/scope/timeline/native-status nhất quán; file theo định dạng/dung lượng thật của form. Review C chưa thực hiện bước xuất hay submit.

## Mapping vào câu hỏi của form

| Câu hỏi | Nội dung hiện có | Vấn đề trong đường đọc | Cách thể hiện nên dùng |
|---|---|---|---|
| Vấn đề | Overview + form01 + IDEA02 | Bằng chứng ngành chưa bằng pain point DENSO | Một pain point, một persona, một baseline cần đo; evidence ngoài có nhãn |
| Mục đích | Flywheel, quality/cost, cùng chất lượng | Goal nghiên cứu và value workflow dễ hòa vào nhau | Hai nấc source feasibility → workflow advantage |
| Công nghệ | Engine page tốt; N1.5/FluxVLA được phân biệt | Quá nhiều technical candidates nếu đọc toàn catalog như scope | Main path R→R+S; H/video có gate, WM alternatives ở phụ lục |
| Input | Source views/blueprint/A1 manifests | Link latest recipe bị lỗi U01 | File → tensor → conditioning/target → loss, nhãn R_sim/S_exec/H rõ |
| Output | Native checkpoint/bundle/QA/report đã nêu trong form | Outcomes đang là ledger reference | Bốn deliverables, tiêu chí chấp nhận, trạng thái từng deliverable |
| Trước/sau | Form03 rõ; overview có mapping nhỏ | Chưa phải workflow nhà máy đo được | Hai cột giả thuyết workflow, cùng task/operator/cost boundaries |
| Hiệu quả | Same-quality + all cost; chưa savings | Business thiếu budget mới; chưa annual-use basis | Current pilot budget + unknowns; metric sẽ đo; chưa ROI |
| Độc đáo | Không nhận model/algorithm mới; workflow integration | Engine cũng có closed loop; advantage cần comparator | Kế thừa/đội xây/phép kiểm riêng như U06 |
| Thời gian | Form8–12tuần, bốn chặng 2–3tuần | Roadmap không hiển thị thời lượng; H có vẻ trong main line | Timeline có assumptions, baseline gate, optional branches |

## Đánh giá đủ 13 routes và hành động cụ thể

| Route | Thực đang render / điểm mạnh | Đề xuất tiếp theo, với loại kết luận |
|---|---|---|
| `overview` | `renderFlywheelOverview`; problem→external evidence→pilot cost→datasets→model→eval/errors→flywheel→form. Scope sim/native pending rõ. | Giữ trật tự; rút hội thoại nội bộ; cho “Đọc nhanh để đánh giá idea” và “Đọc sâu kỹ thuật”. Đưa link current business/roadmap cạnh budget. U05–U07 là gap/usability, không cần thêm số giả. |
| `product` | Doc01 được render đầy đủ; contribution/boundary/source có. | Mở đầu bằng persona, job-to-be-done, bốn đầu ra và một working session; original docs trong details. Hiện lặp overview và h1 chung: U04/U07. |
| `learning` | Workbench inference/training, R/video/H tách; target branch chỉ train; case update module có điều kiện. | Không thấy defect nội dung độc lập cần ép tạo. Thêm đường đọc native R trước, candidate badge nhất quán; giữ source ở engine và một data sample link. Root phụ trách responsive/dynamic visual. |
| `engine` | Original Flux Figures, lifecycle tabs, modules, recipe scope, real-runtime và ownership. | Giữ trang riêng. Đưa trạng thái “upstream đã có / A1 chưa tích hợp” gần hero hơn nếu người đọc chỉ xem đầu trang; thêm original N1.5 figure theo U08. Crosspage doc17 link đã kiểm là hoạt động. |
| `outcomes` | Claim ledger giữ đúng reference/native/savings boundaries. | Bổ sung expected deliverables + acceptance draft/status trước ledger. S12/12 reference chỉ là một hàng evidence, không headline thành công MVP. U04. |
| `business` | All-cost taxonomy, unknown≠0, setup không double-count, historical stress case có nhãn. | Đưa pilot5.187,20USD lên đúng route và reuse cùng dữ liệu overview; tách giả định/đã đo/chưa gồm. Giữ historical case trong details; không biến nó thành estimate mới. U04/U05. |
| `roadmap` | P0–P6 gates/artifacts, failure routes rõ. | Thêm8–12tuần có điều kiện và bốn chặng; P2-H/video thành optional branch; owner role có người nhận sau kickoff. U04; đây là planning estimate không lịch cam kết. |
| `sources` | Taxonomy origin/creation/signal, file→tensor→loss, latency/latent semantics tách. | Không tìm thấy lỗi nội dung quyết định riêng. Thêm một ví dụ “R_A1: expert trong sim; S_exec: variants cũng trong sim” cạnh robot view để đọc thẳng không cần quay overview. Full schema ở details và link A1 đúng U01. |
| `examples` | Public GR1 first, raw inspector, native transform proposal, reference receipts và countercases. Không pretend video/state tất cả aligned. | Tách nhãn cố định trên hai nửa “Nguồn public · schema” và “Team reference · measured”, giữ bản báo cáo để kiểm. Đừng cắt qualifiers quan trọng khi rút ngắn. Không tìm thấy cơ sở gọi replay này là giả native. |
| `research` | Bảy mechanisms so input/target/train/inference, catalog20 trong details, prior results không leaderboard. | Một câu đầu “MVP chọn N1.5; sáu mục còn lại giải thích lựa chọn/extension”. Policy selected + optional + alternative groups có thể giúp stakeholder, nhưng không phải defect research hiện tại. Original model figure khi mở sâu theo U08. |
| `architecture` | Data Core flywheel sáu bước, repair/data/defer, no-gain, source vs adaptive study được tách. | Giữ custom diagram của đội; link rõ sang engine tại handoff release/checkpoint, tránh người đọc tưởng page này là toàn system architecture. Không thấy claim auto-cause/auto-retrain cần sửa. |
| `validation` | Native/reference tách, final độc lập, controls/cost/uncertainty có. | Đưa “pilot đầu R/R+S”, “H riêng R_common”, acceptance proposal và source vs workflow experiments lên summary; full protocol dưới. Sửa link tới A1; không khôi phục grid27 cũ. U01/U04/U06. |
| `resources` | Current engineering docs đứng đầu; source/history và hashes có. | Ưu tiên IDEA/form/A1, sửa basename, gói tải đúng scope, chỉ phiên bản có hiệu lực dẫn ở đầu; history trong nhóm riêng. U01–U03/U10. |

## Đường đọc theo người dùng

**Giám khảo/người quyết định, khoảng 5 phút:** overview rút gọn → product → outcomes → business → roadmap. Trong mỗi trang chỉ cần biết vấn đề, ai dùng, đổi cách làm ở đâu, đầu ra, cost/time và điều kiện còn mở. “Tìm bằng chứng” dẫn sang resources; không ép họ đọc tensor29D để hiểu ý tưởng.

**Kỹ sư triển khai:** engine → sources → learning → examples → architecture → validation → A1 files. Dùng cùng task/profile IDs nhưng phân biệt public sample, native proposal và measured reference.

**Người kiểm nguồn:** claim card → paper đúng version/figure hoặc receipt đúng run → limits/conditions. Với code main cần pin trước implementation; không biến ngày đọc thành commit pin. Root xác nhận data-document crosspage có hoạt động; còn stable URL theo document ID là cải thiện chia sẻ nên kiểm thêm, không nhận là mọi deep link đã hỏng.

Có thể giữ đủ13 routes. Thêm hai nhóm menu “Đánh giá ý tưởng” và “Kiểm kỹ thuật” sẽ dễ scan hơn; đây là đề xuất IA, không buộc gộp/xóa trang.

## Mẫu sửa tóm tắt có thể triển khai

**Opening cho người quyết định:**

> Đội phát triển robot thường phải thu mẫu, kiểm dữ liệu và thử lại khi vật hoặc điều kiện thao tác thay đổi. Chúng tôi thử một quy trình dùng bằng chứng lỗi để chọn dữ liệu bổ sung và đo tổng công đến khi kỹ năng đạt yêu cầu. Pilot đầu dùng GR1 gắp–đặt trong mô phỏng; chưa có công đoạn DENSO hay lợi ích tiết kiệm được xác nhận. FluxVLA/GR00T cung cấp nền tảng; đội xây phần dữ liệu, kiểm task và quyết định cải thiện.

**Outcomes summary:**

> Bốn đầu ra dự kiến: một policy A1 chạy trong mô phỏng, bộ dữ liệu có nguồn gốc và QA, bộ trace/scorer để kiểm mọi lượt, và báo cáo chất lượng–chi phí so với robot-only baseline. Đã có reference pipeline nhỏ để kiểm logic; native GR1 và savings còn phải đo. Acceptance theo A1 proposal cần task owner chốt trước final.

**Business summary:**

> Pilot minh họa đang tính 5.187,20USD cho các khoản đã khai; đây là capacity budget, chưa tổng triển khai hay ROI. Phần lớn là240giờ kỹ sư. Robot/cell, CPU riêng và quyền dữ liệu chưa nằm trong số này. Sau compatibility pilot, đội thay thời lượng giả định bằng logs, chốt cap và chỉ so tiết kiệm khi hai cách đạt cùng yêu cầu chất lượng.

Những mẫu này là gợi ý editorial, không phải nội dung đã sửa trên website hoặc budget được duyệt.

## Kiểm tra tiếp theo theo thứ tự

1. **Đóng lỗi đọc/phát hành:** U01 resolution; U02 clean checkout; U03 ZIP link closure. Giữ hashes/provenance đã có.
2. **Khôi phục đúng chức năng các mục pitch:** U04 outcomes/business/roadmap/product; một current authority registry; tránh sửa song song ba bản text giống nhau.
3. **Đóng gói bản nộp:** U10 file hiện hành, remote-access check, field mapping. Không suy local preview thành link BTC truy cập được.
4. **Kiểm hiểu:** hai persona, năm câu hỏi, không hướng dẫn trước; dùng kết quả để giảm jargon/độ dài chứ không đặt word cap tùy tiện.
5. **Đóng gap kinh doanh/nghiên cứu:** owner/use-case/arm comparator; native feasibility; source study; rồi workflow utility experiment. Các gate này thuộc thực hiện idea, không điều kiện giả tạo để cho phép sửa website.

## Coverage đã kiểm và những gì không nhận đã làm

| Nhóm | File/nguồn đã kiểm | Mức kiểm |
|---|---|---|
| Authority | `IDEA.md`; form draft; engineering README; docs01–13,15–17; A1 README và01–04 | Đọc/reconcile các phần vấn đề, task/data, recipe, architecture, controls/cost/boundaries; docs15 là blueprint/schema/mapping check, không tái lập cả7 papers |
| Route dispatch | `dist/index.html`, `dist/app.js`, `dist/engineering.js` | Theo load order và `renderEngineeringPage`; phân biệt active/legacy; navigation/reader/media source review |
| Active renderers | overview-flywheel, model-engine-core, learning-core, training-blueprint, data-flywheel JS | Đọc flow/markup/handlers nội dung chính và dynamic branches; chỉ kiểm tương tác qua code trừ live observations root |
| Content stores | overview-flywheel, model-engine-core, training-blueprint, data-flywheel, research-and-media JSON | Kiểm cấu trúc/trạng thái/caption/source/claim anchors; generated data đối chiếu authority/snapshot |
| Legacy/media support | idea-opening, idea-story, skill-plan, task-improvement, pilot-budget, cost-model; solution-story/task-improvement/budget JSON | Kiểm vai trò hiện tại/legacy, không nhận tất cả fields đang live; không rerender film hoặc chạy lại cost experiments |
| Dossier/version/package | build-content, build-engineering, sync-docs, package, verify-site, README, Git ignore/workflow; idea-v3.1.zip, skill-a1-plan publication inventory | Kiểm inclusion, routing, relative paths, ZIP entries/link closure, source dependency; không chạy mutating build |
| Browser | browser observations của đủ13routes + resource-link-repro | DOM/h1/visible words/controls/path, do root thu trực tiếp; review C không độc lập lặp browser session |
| Figures/sources | FluxVLA local PDF/text và figure1 PNG; original online report/repo; GR00T official; figure2–5 provenance/captions | Đã thấy ảnh1; không nhận visual QA toàn site hoặc full video; các phương pháp phụ dùng scope của saved source register, không tuyên bố reverified numerical claims tất cả20 papers |
| CSS/layout | index stylesheet inventory, active renderer classes và parent DOM evidence | Không audit tương phản/pixel/keyboard conformance; reviewer chính phụ trách live visual. Không gán `loaded:false` của lazy hidden images là broken asset |

Đã loại bỏ một hypothesis sau phản chứng: crosspage engine→doc17 hoạt động nhờ `app.js:226`. Đã không dùng các copy cũ 38k/27jobs/75% trong hàm app.js không render để tạo lỗi mâu thuẫn giả. Chưa kiểm độc lập all remote media availability, chưa audit deck bằng hình, chưa chạy native VLA hay đo savings. Đây là review nội dung/sản phẩm với phạm vi xác định, không xác nhận toàn bộ nghiên cứu hoặc nghiệm thu robot.
