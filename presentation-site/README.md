# Website trình bày ý tưởng

Luồng đọc chính: ý tưởng → sản phẩm → solution/cách học → kết quả kỳ vọng → chi phí/tính khả thi → lộ trình. Đọc sâu: bốn nguồn → mẫu thật → khảo sát → kiến trúc → kiểm chứng → hồ sơ. Giữ đủ 12 routes và URL cũ.

Task một tay đưa linh kiện cứng vào ô khay là case đề xuất. Đường chính FluxVLA/GR00T N1.5/GR1 robot baseline trước; human/internet heads và Cosmos có gate, basic augmentation ưu tiên. T/F/A từ R0 là core. Public samples/media thuộc tác giả, khác robot/task, không paired hoặc kết quả đội. Website tĩnh chưa kết nối backend ML hay robot thật.

## Mở trên máy

```bash
python3 -m http.server 4175 --bind 127.0.0.1 --directory presentation-site/dist
```

Mở [bản xem trước](http://127.0.0.1:4175/#overview). Địa chỉ này dùng trên máy chạy website. Tạo gói chuyển sang máy khác bằng `python3 presentation-site/package.py`; ZIP lưu local ở `deliverables/`, không commit.

## GitHub Pages

Workflow tại `.github/workflows/pages.yml` dựng lại nội dung, kiểm asset/tài liệu và xuất bản `presentation-site/dist`. Trong repository, chọn Settings → Pages → Source: GitHub Actions, rồi Actions → Deploy website to GitHub Pages → Run workflow trên `master`. URL sau deploy: https://hiwe0305.github.io/denso-challenge/. Khi source chưa bật đúng, deploy được bỏ qua; các lần push sau khi bật tự cập nhật.

Website dùng URL tương đối cho script, asset và dữ liệu để chạy dưới `/denso-challenge/`. Không cần domain riêng hoặc backend để đọc hồ sơ; media remote vẫn cần internet.

## Câu chuyện trực quan ở phần mở đầu

Phần đầu dùng `idea-opening.js` / `idea-opening.css`: sơ đồ có hình dữ liệu–học–robot,
vòng phản hồi và ví dụ lỗi với hai nhánh xử lý. `humanoid-demo.js` dựng humanoid 3D
chuyển động theo kịch bản, sáu bước trong 30 giây, có dừng/tiếp tục và đổi góc nhìn.
Phần giải thích bên cạnh làm nổi bước xử lý tương ứng. Không có physics simulation,
FluxVLA inference hoặc kết quả policy trong demo. Three.js 0.160.1 được pin local,
giữ MIT license và checksum trong vendor; không có WebGL thì dùng ảnh / giải thích 2D.
Hướng tham khảo và phạm vi minh họa ở [VISUAL-DIRECTION.md](VISUAL-DIRECTION.md).

`idea-story.js` / `idea-story.css` dựng sơ đồ solution và chín bước cho hai tình huống:
đổi ánh sáng → gắp hụt, và gắp → tuột vật. Có chọn cảnh, phát/tạm dừng, gallery,
video 72 giây và bộ ảnh tải xuống. Điều khiển dùng bàn phím được; chuyển trang hoặc
ẩn tab sẽ dừng câu chuyện. Không có số đo giả hoặc backend huấn luyện được giả lập.

Ảnh trong `dist/assets/story/` được tạo bằng built-in image_gen, từ một cảnh tham chiếu.
Humanoid trên ảnh là minh họa chung, không là mô hình chính xác của GR1. Toàn bộ hình,
màn hình workflow và video là giải thích thiết kế, chưa kết quả huấn luyện của đội.
Prompts ở `content/story-image-prompts.json`; nội dung cảnh ở `content/solution-story.json`.

`story-export.html?scene=0&condition=visual` xuất một cảnh có chú thích; scene=0–8,
condition=visual/contact. Chụp bằng browser ở 1280×720, ghi các JPEG `scene-{condition}-{01..09}.jpg`.
Sau thay đổi nội dung hoặc hình, xuất lại các cảnh liên quan và cập nhật content JSON từ `ideaSteps()`.
Chạy `python3 presentation-site/build-story-media.py` để dựng MP4, VTT, ZIP và manifest hashes.
FFmpeg chỉ cần lúc dựng video; CI và website sử dụng bản đã xuất. Video không lời đọc,
có chuyển cảnh nhẹ và chú thích tiếng Việt trên hình. Validator kiểm đủ hai bộ cảnh và hashes.

## Cập nhật

- Sửa nội dung trang trong `dist/app.js`, giao diện trong `dist/styles.css`.
- Sửa sơ đồ Mermaid tại tài liệu sở hữu, sau đó chạy `python3 presentation-site/sync-docs.py` để tạo lại SVG.
- Các đường dẫn cũ như `#skill-core` vẫn mở phần chi tiết tương ứng.
- Kết quả kiểm tra hiện hành được gộp ở phần dưới; không duy trì một file lịch sử QA lặp nội dung.
- Chạy `python3 presentation-site/verify-site.py` và kiểm cú pháp các file JavaScript trước khi publish. CI chạy lại các kiểm tra này. Sync sơ đồ cần Graphviz (`dot`); build nội dung/kiểm Pages chỉ dùng Python standard library.

## Bản đầy đủ đa nguồn

Website có 12 mục, 13 phương pháp, numerical previews GR1 (6 rows từ pinned Parquet), G1 (620 frames), HumanEgo (1002 rows), LIBERO (6 rows), GIF/video có nguồn. Trình đọc chứa 12 tài liệu canonical, bản review và pitch =14 mục. Bỏ team/risk document riêng (risks gộp protocol), biểu mẫu chưa xác minh và file QA cũ; không xóa unique PRD/TDD/contracts.

Research/media catalog được sửa tại `content/research-and-media.json`; numerical previews và provenance ở `dist/data/`. Chạy `python3 presentation-site/sync-docs.py` để render năm SVG nguồn và ba SVG giải thích và rebuild `evidence.js`, `dossier.js`, source manifest cùng docs11–12. Đây là outputs generated, không sửa chúng rồi bỏ qua catalog/canonical docs.

Clip GR1 episode 0 và ảnh xem trước thật được lưu trong assets, giữ nguồn tác giả và giấy phép CC BY-NC 4.0; MP4 chỉ remux faststart, không đổi frames. Các video/ảnh remote khác tải trực tiếp từ máy chủ tác giả. Figure 1 FluxVLA được trích từ PDF gốc, lưu cùng hồ sơ và dùng được offline. numerical preview và hồ sơ đọc được offline, media remote cần internet. HLS dùng player hls.js 1.6.13/MIT được pin trong vendor. Website là hồ sơ minh họa, chưa backend ML đã tích hợp.

## Kiểm tra và đóng gói bản 05/10/2026

Kiểm các route ở browser hiện tại, đọc 14 docs trong reader, ví dụ tương tác source decision, controls numerical samples và dự toán chi phí có nguồn. Kiểm syntax JavaScript, schema/weights/score math, canonical-to-dossier parity, local links/assets và ZIP integrity. Đây là kiểm website/tài liệu, không E0 hoặc kết quả huấn luyện. Không dùng kết quả QA giao diện cũ để nhận rollout/task success mới.

Build `python3 presentation-site/sync-docs.py`; package `python3 presentation-site/package.py`. Không sửa dossier/evidence generated riêng. Bảng chấm6,5 được giữ làm tham chiếu nội bộ trước PoC trong hồ sơ, không hiển thị như điểm vòng idea. Website dùng nhận định định tính và liên kết tiêu chí BTC.

## Nội dung theo góp ý browser

- Slogan và phần mở đầu sửa trong `dist/app.js` ở `overview`/`status`; không cần một CMS riêng cho hồ sơ tĩnh.
- Sơ đồ giải thích: `render-presentation-diagrams.py`; sơ đồ canonical kỹ thuật: Mermaid trong docs và `render-diagrams.py`. Hai loại có vai trò riêng và có nút đổi view.
- Dự toán duy nhất: `content/industrial-cost-model.json` (53 inputs, nguồn, scenarios, sensitivity), công thức `dist/cost-model.js`, đặc tả/phạm vi trong docs07. Mô hình annual ROI cũ đã bỏ; score riêng ở `docs/reviews/idea-score.json`.
- Benchmark ưu tiên RoboCasa GR1; real teleop dùng G1/Dex3; LIBERO/Panda nằm trong phần tham chiếu format. Public GR1 sample v2.1 không bị đổi nhãn thành v3. Dataset NVIDIA NC là public research reference, không tự đủ quyền commercial cho derivatives.
- Mục Kết quả dự kiến và docs13 chứa task example/acceptance; không fabricated team rollout hoặc số ML.

Cache version hiện hành bao gồm cả numeric samples, tránh đọc preview JSON cũ khi metadata thay đổi. Server local không upload dữ liệu ra bên ngoài; video/ảnh stream từ nguồn được dẫn.

QA bản 03/10: đã mở đủ 12 routes và 14 tài liệu bằng browser hiện tại; đã đổi tình huống trên overview, đọc các frame LIBERO/GR1, phát LIBERO và GR1 từ nguồn, tải architecture FluxVLA, đổi sơ đồ giải thích/bản nguồn/fullscreen và đổi kịch bản/inputs chi phí. Phép kiểm cost gồm bằng nhau khi workflow bằng nhau, failed attempts theo yield, GPU rate đúng stage, one-time integration chia skills, dedicated idle và cash capital không double-count. Không là E0 hoặc kiểm chứng quality/savings của policy.

Architecture tại Learning Core dùng nguyên Figure 1, trang 2 của paper FluxVLA arXiv:2609.17210v1. PNG 3060×1290 được render từ PDF local bằng PyMuPDF (clip [51,51,561,266] points, scale 6); source PDF/asset SHA-256 được ghi trong media catalog và manifest. Sync giữ bản PNG canonical trong docs/assets; ZIP kèm hình và nguồn. Sơ đồ FluxVLA tự vẽ đã bỏ. Phần giải thích platform/proposal nằm bên dưới hình; bảng kết quả trong hình được ghi rõ thuộc tác giả với budgets khác nhau.

## Cải thiện05/10/2026

Core15 runs (6R0 +9T/F/A); extensions có gate. `content/pilot-budget.json` và `dist/pilot-budget.js` thêm R&D-sim partial planner và acquisition T/F/A ledger dùng chung rates. Blank giữ unknown, không tự zero; nonnegative/integer validation; cap không là quality. JSON export gồm cả scopes R&D/acquisition, null cho cost unknown và invalid status nếu study input lỗi. Original53-input skill/cash/ops model giữ assumptions và kết quả. Tách study/skill/production, không cộng scopes. DataMIL bổ sung vào catalog, source date riêng05/10.

QA thực hiện sau build: syntax/calculation/unknown/cap/invalid-input, browser routes và interactions, dossier parity/local assets/ZIP. Chỉ là kiểm website/tài liệu; chưa E0 hoặc policy gain.

## Biên tập hồ sơ vòng idea · 05/10/2026

Trang đầu nêu ai dùng/đầu vào/đầu ra, ví dụ đặt linh kiện vào ô A1 và cơ chế video người bổ sung trải nghiệm, mẫu robot dạy điều khiển. Luồng đọc ưu tiên sản phẩm/solution/kết quả/chi phí/lộ trình; giữ các phần chuyên sâu trong mục đọc thêm. Targets, dữ liệu tác giả, dự toán và kết quả thực nghiệm được phân biệt rõ. Lịch vòng thi và kế hoạch kỹ thuật12 tuần có phạm vi riêng.

Đã kiểm12 routes trong browser, mở chi tiết FluxVLA và bộ dự toán, đổi480→240→480 giờ kỹ sư và kiểm ledger trống giữ unknown. Kiểm cú pháp JavaScript, luồng nút tiếp theo12 trang,20 local references và parity14 tài liệu với nguồn canonical. ZIP được đóng lại và kiểm integrity. Đây là QA nội dung/giao diện, không kiểm chất lượng policy hoặc savings.

## Task improvement revision2

Canonical semantics: `docs/14-task-improvement.md`; scoped audit: `docs/reviews/full-idea-audit-2026-10-05.md` and JSON. `content/task-improvement.json` holds five declared examples, generated into evidence.js/data. The website computes counts/coverage and shows reviewed example plans; it does not classify real robot failures, run a verifier or train a policy.

`task-improvement.js` validates count conservation, stage reach and outcome semantics; meaningful edge-case checks run with `node presentation-site/test-improvement.js`. Diagnosis/probe/bootstrap planning fields initially unmeasured zero placeholders, not evidence of complete costing. E0/D0/E1/E4 and independent whole-task/regression remain required.

Older 9-scene images/video are an introductory overview, not the full revision2 method; provenance and source prompts are preserved. Rebuild canonical docs/data with `python3 presentation-site/build-content.py`, verify site, then `python3 presentation-site/package.py` for offline handover.
