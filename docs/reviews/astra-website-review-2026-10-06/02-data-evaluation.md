# Review B — Dữ liệu, data flywheel, kiểm chứng và nguồn lực

Ngày chốt: 07/10/2026. Đối tượng: snapshot website ngày 06/10/2026, Git HEAD `e45cf7f0309f3fe58112c98c10b1111f5bee1864`, working tree theo [snapshot.json](snapshot.json). Reviewer B được phân công review bằng Astra. Đây là audit nguồn và thiết kế; không chạy lại thí nghiệm, không dùng browser UI và không sửa website/dossier. Các đường dẫn và dòng dưới đây thuộc workspace `/home/hiwe/denso-challenge`.

**Nhận định chính:** Data Core hiện có taxonomy và ranh giới bằng chứng tốt. Nó đã phân biệt nguồn dữ liệu, cách tạo, tín hiệu giám sát, representation, engineering reference và native VLA. Phần chưa được giải quyết đủ để quyết định đầu tư tiếp là: chọn dữ liệu nào có ích hơn một lựa chọn khác, độ phủ còn lại sau QA, operating characteristics của gate nghiệm thu, kiểm trùng dữ liệu xuyên nguồn, và ánh xạ ngân sách sang công việc native thật. Những điều này chưa chứng minh idea không hiệu quả; chúng xác định bằng chứng tiếp theo cần tạo.

## 1. Những điểm đã làm đúng và cần giữ

| Điểm mạnh | Căn cứ đã đọc | Kết luận có phạm vi |
|---|---|---|
| Phân loại dữ liệu đúng theo nhiều trục | `03-workflow-du-lieu.md:36–42`; `15-dataset-training-blueprint.md:36–78`; `training-blueprint.json:4–14` | Synthetic là cách tạo; Internet là nơi phân phối; MP4/Parquet là storage; latent là representation. Loader phải dựa vào capability và target thực có. Phù hợp cấu trúc LeRobot v3 [S5]. |
| Ba loại synthetic có quyền dùng nhãn khác nhau | `03-workflow-du-lieu.md:50–56`; `IDEA.md:126–146` | Appearance chỉ kế thừa nhãn sau kiểm semantics; sim execution ghi action/response mới; video sinh chưa có measured actions. Phù hợp MimicGen, DreamGen và FOCA [S2, S4, S8]. |
| Human bridge có target và comparator riêng | `02-recipes-and-data.md:35–76` | Current-camera wrist targets, masks, robot measured FK, native action decoder riêng và `R_common` đối chứng là thiết kế kiểm được. Không lấy human wrist làm robot joint labels. Chưa có bằng chứng transfer, nhưng không có mâu thuẫn chỉ vì hai embodiment khác nhau. |
| Phân biệt development và final | `03-workflow-du-lieu.md:18`; `05-thiet-ke-kiem-chung.md:28–38`; `04-evaluation-and-cost.md:35` | Adaptive reuse của development được cho phép. Final chỉ bị mất vai trò độc lập khi được dùng để chọn/tune cho cùng claim. Chuyển final cũ sang development và tạo final mới là cách khai báo hợp lý. |
| Root counts trung thực | `results/training-receipts.json`; `run.py:155–178` | R: 1 recording/1 root; S: 25 recordings/1 root; C: 2 recordings/2 roots. Không đếm 24 synthetic variants thành 24 robot demonstrations độc lập. |
| Kết quả reference không bị trình bày thành native | `10-example-chay-toan-he-thong.md:3–34,56–62`; `12-bang-kiem-chung.md:5–18`; `results/report.json` | R 0/12, S 12/12, C 0/12 là outcome của model tuyến tính 35×4, idealized state, sequencer và proximity weld. Đây là engineering evidence hữu ích; chưa là visual VLA, contact-valid GR1, human transfer hoặc data-efficiency study. |
| Gate giữ cả thất bại và uncertainty | `04-evaluation-and-cost.md:13–19,25–37`; `results/report.json` | Unknown/intervention/timeout không thành successes. C sửa development nhưng fail final bị giữ ngoài promotion. Tỷ lệ quan sát 90% không bị đồng nhất với chứng minh true success ≥90%. |
| Chi phí được nhận là giả định, không savings | `06-chi-phi-va-kha-thi.md:5–25`; `cost-ledger.template.csv`; `overview-flywheel.json:178–199` | Có chỗ cho rejects, QA, engineer/operator/GPU/robot time, retries và setup. Nguồn tài trợ không xóa economic usage. Chi phí hiện chưa đủ để nhận hiệu quả kinh tế. |

**Counterevidence cần giữ khi phản biện human:** HumanEgo v3 thực sự báo robot-data-free trong cấu hình của họ; không được biến lựa chọn robot anchors của MVP thành định luật mọi human learning cần robot demonstrations. Tuy nhiên HumanEgo dùng interaction-centric object/hand geometry và parallel-jaw retargeting; appendix/main limitations nói tới slip, regrasp và precision. Nó không chứng minh wrist-only shared-trunk GR1 của project. EgoScale cũng có aligned human–robot mid-training và hand articulation, không chỉ một wrist head [S3, S6]. Site hiện thừa nhận các ranh giới này ở `IDEA.md:110–124,174` và `02-recipes-and-data.md:59–76`.

## 2. Findings có thứ tự ưu tiên

Các ID D01–D06 là ID của báo cáo này, không phải database finding IDs. `material` nghĩa là ảnh hưởng đáng kể tới kết luận/thiết kế tiếp theo; không đồng nghĩa lỗi đã được chứng minh. Tất cả còn `open` tại snapshot. Không gán điểm hoặc xác suất tin cậy chủ quan.

### D01 — Vòng chọn dữ liệu chưa có phép kiểm riêng đủ cụ thể để nhận giá trị của lựa chọn

**Priority:** material. **Basis:** inferred_risk / missing_specification. **Category:** causal attribution. **Anchors:** `ACQUIRE → TRAIN → EVAL → ACQUIRE`; routes `#overview`, `#architecture`, `#validation`, `#business`.

**Vị trí:** [data-flywheel.json:22](/home/hiwe/denso-challenge/presentation-site/content/data-flywheel.json:22), các dòng 22–51; [03-workflow-du-lieu.md:20](/home/hiwe/denso-challenge/idea-v3-2026-10-05/03-workflow-du-lieu.md:20), dòng 20–24; [04-evaluation-and-cost.md:33](/home/hiwe/denso-challenge/docs/implementation-plan/skill-a1/04-evaluation-and-cost.md:33), dòng 33–37; `overview-flywheel.json:154–175`.

**Tiền đề nguồn:** DataMIL định nghĩa utility theo *learning algorithm + target metric*, dùng target demonstration loss để chọn dữ liệu, rồi kiểm policy outcomes. §4.2–4.3 còn phân biệt dữ liệu phục vụ selection với dữ liệu phục vụ downstream training [S1]. Điều này không yêu cầu A1 dùng DataMIL; nó cho thấy similarity, QA và utility là các khái niệm khác nhau.

**Tiền đề thiết kế → suy luận:** A1 đã quy định AcquisitionPlan, source eligibility, replay và evaluation, nhưng chưa có một record cụ thể nối failure bucket → những lựa chọn dữ liệu khả thi → lựa chọn bị loại → release → training receipt → gain/cost theo bucket → quyết định vòng sau. Secondary experiment ghi engineer expertise/case familiarity là confounds, chưa chốt đơn vị phân bổ case, treatment access hay cách chống học đáp án từ lượt trước. Do đó R vs R+S có thể chứng minh thêm S giúp recipe, nhưng chưa chứng minh Data Core *chọn S đúng hơn* cách kỹ sư thường làm. Một catalog truy hồi gần đúng cũng chưa chứng minh retrieval có utility cho policy.

**Counterevidence/giới hạn:** `IDEA.md:211`, `03:24` và `04:35–37` đã nói rất rõ source ablation không trả lời thay workflow comparison. `overview-flywheel.json:160` cũng không hứa model tự định giá utility. Đây là phần cần cụ thể hóa trước secondary study, không phải claim giả rằng selector đang hoạt động.

**Sửa cụ thể:** Bổ sung một `AcquisitionDecisionReceipt` tối thiểu gồm bucket/context, allowed supervision, alternatives và anticipated cost, selection rule/reviewer, chosen release, realized train cost, development gain + regression + uncertainty, next acquisition/stop. Với retrieval, ghi cả query/candidate pool/selected IDs; không lấy retrieval similarity làm outcome. Chọn trước một comparison nhỏ: cùng parent, cùng intervention access/cap, engineer thường so với evidence workflow. Counterbalance case/order hoặc giao các case chưa từng thấy cho mỗi người; giữ phần final độc lập.

**Phép kiểm phân biệt và chi phí:** Với K parent–case pairs, hai workflow cần tối thiểu 2K intervention/train/eval paths, ngoài chung baseline; log cả selection và expert time. Giữ recipe/scorer/domain, so full-task gain và tổng công tới acceptance. Finding được giải khi receipt đầy đủ và matched comparison cho thấy selection có ích; nếu hai workflow cùng chọn và cùng tốn công thì báo chưa có added value. Không cần xây learned utility estimator trước phép thử này.

### D02 — QA chấp nhận trajectory chưa kiểm được độ phủ bị mất do quá trình lọc

**Priority:** material. **Basis:** inferred_risk, với limitation trực tiếp từ nghiên cứu tham chiếu. **Category:** robustness / data engineering. **Anchors:** `S_exec → RELEASE`, `RELEASE → TRAIN`; routes `#sources`, `#architecture`, `#overview`.

**Vị trí:** [02-recipes-and-data.md:15](/home/hiwe/denso-challenge/docs/implementation-plan/skill-a1/02-recipes-and-data.md:15), dòng 15–25; [03-workflow-du-lieu.md:50](/home/hiwe/denso-challenge/idea-v3-2026-10-05/03-workflow-du-lieu.md:50), dòng 50–56; `data-flywheel.json:30–35`; `overview-flywheel.json:53–60`; `run.py:197–208`.

**Tiền đề nguồn:** MimicGen v1 p4 chỉ giữ successful executions. Appendix R p42 trực tiếp nghiên cứu bias của accepted reset configurations, ghi nhận support coverage không đầy đủ trong một số tasks và cảnh báo nonuniform counts/repetitive motions. Appendix P p40 cũng tách generation success rate khỏi learned policy success [S2].

**Tiền đề thiết kế → suy luận:** Proposal mạnh hơn success-only QA của MimicGen ở contact/collision/tracking checks và có giữ rejects. Nhưng chưa có định nghĩa đo coverage giữa requested conditions, attempted conditions, accepted conditions và nguồn mà policy sẽ gặp. Một generator có thể đạt nhiều accepted episodes bằng cách liên tục lấy vùng dễ; QA từng episode vẫn pass trong khi bucket gây lỗi gần như vắng trong training. Việc tăng số variants không tự giải rủi ro này.

**Counterevidence/giới hạn:** Tài liệu đã yêu cầu coverage và downstream heldout/regression, không nhận high generation count là savings. Reference 24/24 accepted được công khai và dùng physics đơn giản; không suy từ nó rằng native generation yield bằng 100%, hoặc rằng synthetic hiện đã thiên lệch theo kiểu của MimicGen.

**Sửa cụ thể:** Thêm release-level coverage receipt: phân bố đề nghị/attempted/accepted/rejected theo object, pose/target, appearance, reachability/contact regime và failure bucket; số unique parents; lý do reject; effective sampling weights và khoảng trống còn lại. Không bỏ QA để lấp bucket. Nếu physics không sinh được dữ liệu ở một vùng quan trọng thì defer, dùng expert correction hoặc thu hẹp claim có khai báo.

**Phép kiểm phân biệt và chi phí:** Trong cùng transform domain và cùng attempt cap, so sampling hiện tại với sampling có quota cho buckets yếu; giữ seeds, trainer và evaluation distribution. Đo yield theo bucket, root diversity, full-task/regression, generation + QA + training cost. Falsifier: accepted release đã phủ các buckets được hứa và không có chênh lệch utility đáng kể khi điều chỉnh sampling. Histogram từ logs có chi phí thấp; generation bổ sung và paired training phải vào cap, không được coi miễn phí.

### D03 — Gate 100 trials đúng công thức nhưng chưa có operating characteristics để lập kế hoạch

**Priority:** material. **Basis:** inferred_risk / unresolved planning choice; không phải lỗi công thức. **Category:** experimental design / resource feasibility. **Anchors:** `EVAL → acceptance`, `acceptance → cost`; routes `#validation`, `#overview`, `#business`.

**Vị trí:** [04-evaluation-and-cost.md:13](/home/hiwe/denso-challenge/docs/implementation-plan/skill-a1/04-evaluation-and-cost.md:13), dòng 13–19; [task-spec.proposed.json:23](/home/hiwe/denso-challenge/docs/implementation-plan/skill-a1/task-spec.proposed.json:23); `15-dataset-training-blueprint.md:136–139`.

**Tiền đề nguồn:** Exact binomial interval trong SciPy dùng Clopper–Pearson; sidedness và confidence level là tham số cần giữ đúng [S9]. Site dùng lower bound một phía 95%, `q_min=.90`, n=100, và ghi đúng rằng 96 successes pass còn 95 chưa pass.

**Tính toán analyst → kết luận hẹp:** Dưới chính giả định IID Bernoulli của draft, quy tắc tương đương `X≥96`. Khi policy thật có p=.95, xác suất vượt gate là `sum(k=96..100, C(100,k)*.95^k*.05^(100-k)) = .4359813`. Với p=.97 là .8178548. Đây là operating characteristic của phép nghiệm thu, **không phải ước lượng hiệu năng robot** hoặc xác suất hậu nghiệm policy đúng. Một policy 95% có hơn nửa khả năng chưa vượt gate này; nếu lịch/budget chỉ chứa một final thì rủi ro inconclusive/no-pass là đáng kể.

**Counterevidence/giới hạn:** Draft đã gọi 100 là proposal, yêu cầu chốt sampling/analysis/training-seed plan trước final, và không đồng nhất acceptance với equivalence. Một gate bảo thủ có thể là lựa chọn đúng. Finding không đòi hạ chuẩn hoặc nhận kết quả chưa chắc chắn; nó yêu cầu owner biết xác suất ra quyết định và chi phí tương ứng. Không áp binomial tổng cho fixed/stratified conditions trái giả định.

**Sửa cụ thể:** Bổ sung operating-characteristic table theo p có ý nghĩa nghiệp vụ, mức power mong muốn và nguyên tắc dừng/không pass. Chốt estimand: checkpoint cố định hay training procedure qua seeds; average distribution hay từng safety/coverage stratum. Nếu primary question là source advantage, thêm paired difference/margin/power riêng; việc hai policy đều pass không tự chứng minh equivalent hoặc candidate hơn baseline.

**Phép kiểm phân biệt và chi phí:** Tính power/interval theo sampling design trước final; báo số rollouts mỗi policy × training seeds × strata và reset/annotation time. Finding được giải khi thiết kế đạt operating characteristic owner chọn hoặc owner chấp nhận trade-off hiện tại. Tính toán ở đây chỉ dùng công thức xác suất, không chạy robot hay rerun reference.

### D04 — Lineage theo IDs cần bước nhận diện trùng nội dung trước khi được coi là chống leakage xuyên nguồn

**Priority:** material khi nhập public/multi-source data; minor với reference tự sinh hiện tại. **Basis:** inferred_risk / missing_specification, không có bằng chứng leakage đã xảy ra. **Category:** data engineering / experimental validity. **Anchors:** `source ingest → root graph → split`; routes `#sources`, `#architecture`, `#validation`.

**Vị trí:** [dataset-manifest.proposed.json:19](/home/hiwe/denso-challenge/docs/implementation-plan/skill-a1/dataset-manifest.proposed.json:19), dòng 19, 35, 50; [03-workflow-du-lieu.md:40](/home/hiwe/denso-challenge/idea-v3-2026-10-05/03-workflow-du-lieu.md:40), dòng 40–42,63; `run.py:23–36,155–168`; `test_pipeline.py:69–73`.

**Tiền đề nguồn:** LeRobot v3 dùng nhiều episodes trong cùng shard và metadata để xác định episode boundaries [S5]. Vì thế tên file hoặc hash cả MP4 không tự là danh tính một recording/window. Website cũng đã nhận human clip trên Internet có thể chính là human-origin recording, không hai nguồn độc lập.

**Tiền đề thiết kế → suy luận:** Manifest đã có root/parent/session/scenario và nêu split-before-derivatives, nhưng chưa định nghĩa cross-source duplicate groups, source episode/time-range identity hoặc audit overlap khi cùng video được mirror/cắt/re-encode. Hai nhập liệu cùng nội dung có thể nhận root IDs khác và đi hai split dù rule về descendants vẫn được tuân thủ. Reference validator chỉ kiểm `scenario_id` bắt đầu `final-`; đó là một guard cho fixture đã biết, không kiểm độc lập dữ liệu nói chung.

**Counterevidence/giới hạn:** `03:63` đã nói kiểm duplicates; rights/source revision và final exclusion đều đã có. Không phát hiện actual duplicate hoặc final contamination trong releases reference. Cũng không coi upstream pretrained priors chung giữa arms là lợi ích H/S mới; proposal đã giữ sự phân biệt đó. Không đòi chứng minh toàn bộ pretraining corpus của foundation model sạch khi corpus không được công khai.

**Sửa cụ thể:** Trước split, canonicalize source repository/revision/recording/episode/time range; exact hash cho raw content và duplicate-family ID cho cropped/reencoded windows. Với corpus lớn có thể dùng near-duplicate retrieval rồi review biên; không mặc định similarity là duplicate. Split trên connected components của root/ancestor/duplicate/session graph, phát hành overlap-audit receipt. Ghi riêng vùng pretraining overlap chưa quan sát được và giới hạn novelty claim.

**Phép kiểm phân biệt và chi phí:** Inject cùng recording dưới ID khác, một clip con, một re-encode và một derivative; tất cả phải chung group hoặc quarantine trước split. Đổi tên final scene không được làm hết overlap. Cost gồm hashing/indexing và review ambiguous pairs, ghi theo corpus; không cần near-duplicate infrastructure nặng cho vài seed tự thu. Finding được giải bằng receipt nhóm nội dung và zero prohibited overlap, không chỉ test tên split.

### D05 — Ngân sách công suất chưa trả lời được study native nào hoàn tất trong cap

**Priority:** material; decision-blocking chỉ đối với cam kết ngân sách/lịch native, không ngăn tiếp tục feasibility. **Basis:** unresolved / resource feasibility. **Anchors:** `RunPlan → TRAIN/EVAL`, `resource cap → acquisition choices`; routes `#overview`, `#business`, `#roadmap`.

**Vị trí:** [overview-flywheel.json:178](/home/hiwe/denso-challenge/presentation-site/content/overview-flywheel.json:178), dòng 178–199; [overview-flywheel.js:41](/home/hiwe/denso-challenge/presentation-site/dist/overview-flywheel.js:41); [06-chi-phi-va-kha-thi.md:13](/home/hiwe/denso-challenge/idea-v3-2026-10-05/06-chi-phi-va-kha-thi.md:13), dòng 13–17; `08-ke-hoach-trien-khai.md:5–12`; `native-preflight.json:3–13`; `cost-ledger.template.csv:1–10`.

**Tiền đề nguồn:** Official GR00T phân biệt open-loop prediction với closed-loop environment evaluation và yêu cầu dataset/modality/embodiment configuration [S7]. FOCA v1 p20 báo tài nguyên theo architecture và stage, gồm generator tuning, auxiliary phase và robot phase; chúng không phải một GPU-hour number thay thế lẫn nhau [S4].

**Tiền đề thiết kế → suy luận:** Overview cho 20 seed roots, yield giả định .5, 240 engineer-hours, cap 180 A100 GPU-hours và storage 100GB. Hàm budget nhân công suất với đơn giá; nó chưa có job count cho R/R+S, source preprocessing, training seeds, human controls, retries, final/regression/probes. Preflight chưa có CUDA/native stack/checkpoint. Do đó số tiền minh họa chưa xác định được nhánh native nào vừa đủ memory và chạy xong trong cap. Một cap lớn hơn cũng không tự giải missing binding/loader/scorer hoặc công expert collection.

**Counterevidence/giới hạn:** UI nói rất rõ đây là capacity budget, chưa benchmark hoặc bảo đảm config fits; `06:17` không hứa một người 12 tuần đủ. `pilot-budget.json` core15 T/F/A và `industrial-cost-model.json` 400→280 là lịch sử/stress models: route hiện hành không dùng chúng làm RunPlan native. Không có căn cứ nói 180 GPU-hours chắc chắn thiếu, hay model không thể chạy trên máy khác. Dataset/code quyền non-commercial cũng đã được gắn điều kiện, chưa có commercial receipt.

**Sửa cụ thể:** Sau one-batch/closed-loop gate, tạo `RunPlan` bảng jobs với model/code/data hashes, trainable modules, batch/dtype/horizon/views, measured peak VRAM/throughput, steps, repeats, GPU loại/số lượng/wall time, eval scene counts, CPU/storage và engineer/operator work. Gắn từng job vào source hypothesis. Tách base R/S minimum study, H optional, action-free optional và secondary workflow comparison; cap hết thì stop/defer có receipt.

**Phép kiểm phân biệt và chi phí:** Một bounded native pilot cần loader batch + update/reload + vài development closed-loop trials để lấy memory/time; một bounded generation batch lấy yield/QA time; sau đó dự toán full job set bằng measurement và explicit contingencies. Chỉ khi tổng công/job set nằm trong nguồn lực khả dụng mới nhận lịch/cap. Không dùng chi phí foundation pretraining GR00T/EgoScale để tính vào MVP vốn tận dụng checkpoint; cũng không dùng training time của toy ridge để dự toán native.

### D06 — Guard “nonmonotonic clock” của reference hiện chỉ kiểm step index

**Priority:** minor với claim native; material với câu mô tả guard reference. **Basis:** demonstrated_error qua đọc đường code, chưa chạy reproducer. **Category:** interface validation. **Anchors:** `reference release → fit`; routes `#outcomes`, `#examples`, dossier reference.

**Vị trí:** [run.py:23](/home/hiwe/denso-challenge/examples/engineering-loop/run.py:23), dòng 23–36,155–168; [test_pipeline.py:21](/home/hiwe/denso-challenge/examples/engineering-loop/test_pipeline.py:21); [10-example-chay-toan-he-thong.md:41](/home/hiwe/denso-challenge/idea-v3-2026-10-05/10-example-chay-toan-he-thong.md:41).

**Tiền đề → suy luận:** Records có `timestamp`; validator kiểm shape/finite của features và command, `dt`, và `step`. `fit()` so `step` với step trước theo root, không đọc `timestamp`. Test có tên `test_nonmonotonic_clock_prevents_training` chỉ nhân đôi một row, nên bắt step trùng. Vì vậy một cặp rows với steps tăng nhưng timestamp đảo chiều/NaN không bị guard thời gian này từ chối. Claim “clock không tăng” hiện rộng hơn hành vi được chứng minh. LeRobot cũng phân biệt timestamps/fps/delta sampling trong loader [S5], nên step order không thay temporal alignment.

**Counterevidence/giới hạn:** Generator hiện tự ghi `timestamp=(i+1)*.05`; không có bằng chứng artifacts đã lưu sai clock. Việc hạn chế guard không làm mất các outcomes reference đã ghi, và không được suy ra native loader sẽ có lỗi tương tự.

**Sửa cụ thể và test:** Hoặc đổi mô tả/test thành “nonmonotonic step”; hoặc kiểm timestamp finite, monotonic per episode, spacing/tolerance theo declared dt và consistency step↔time. Test riêng steps tăng/timestamp giảm, duplicate timestamp, missing/NaN timestamp và valid nonzero clock origin. Đây là sửa validator nhỏ, không cần native training/GPU. Finding được giải khi wording khớp code hoặc các temporal cases được kiểm thật.

## 3. Kiểm các claim nhạy cảm và điều không nên kết luận

| Claim/câu hỏi | Verdict trong audit | Lý do và giới hạn |
|---|---|---|
| Human/synthetic có tiền lệ giúp robot learning | Supported by cited sources, trong scope tác giả | HumanEgo/GR00T/FOCA/MimicGen có mechanisms và evaluations liên quan. Không chuyển số liệu sang A1, không xem như reproduction của nhóm. |
| Human wrist branch của A1 sẽ giúp grasp/contact | Unresolved; proposal đã tự giới hạn | Wrist-only thiếu finger/contact; EgoScale §3.6 và HumanEgo limitations là risk prior. Chưa có A1 trial để bác bỏ hoặc xác nhận. |
| Generated video tương đương simulator trajectory | Không phải claim hiện hành | Site đã tách action-free future objective và pseudo-label route khỏi measured robot actions. Giữ sự phân biệt này. |
| QA pass nghĩa là useful data | Unresolved nếu suy luận theo cách đó | Current site dùng downstream eval, nhưng utility/coverage receipt cần D01/D02. Không cần mọi dữ liệu sạch đều có ích như nhau. |
| S 12/12 chứng minh data efficiency | Unsupported ngoài reference scope | R/S dùng cùng root count nhưng model/feature/scenario cực hẹp; không matched acquisition/compute hay native study. Site đã ghi đúng giới hạn. |
| C 0/12 bác bỏ correction | Contradicted as generalization | Artifact chỉ cho biết hai recordings trong basis tuyến tính này không generalize đủ; không kết luận correction native vô ích. |
| 100 trials, q_min=.90 là sai thống kê | Không | Công thức draft đúng dưới assumptions; thiếu power/decision-cost detail ở D03. |
| Reuse development là final contamination | Không | Chỉ coi là contamination khi dùng final đã hứa độc lập cho source choice/tuning/normalization trong cùng claim. |
| Dùng ít roots hơn luôn rẻ hơn | Không phải claim hiện hành | Có rejects, processing, QA, GPU và engineering cost. Savings hiện not_established. |
| Rights đã đủ cho triển khai công nghiệp | Unresolved, không được suy ra từ public access | HumanEgo/GR1 public examples có điều kiện được site nêu; source-specific approval/use receipt chưa có. Không đưa ra tư vấn pháp lý hoặc kết luận quyền đã bị vi phạm. |

## 4. Nguồn chính đã kiểm trước/để đưa ra findings

Coverage dưới đây là các phần đã thực sự đọc; không nhận đã đọc toàn bộ mọi paper. Không trích nguyên văn dài từ nguồn. Các numerical benchmark khác nhau không được ghép thành leaderboard.

| ID | Phiên bản và phần đã đọc | Dùng làm tiền đề |
|---|---|---|
| S1 | [DataMIL arXiv:2505.09603v1](https://arxiv.org/html/2505.09603v1), §3, §4.1–4.3, §5 setup/results; [official code README](https://github.com/UT-Austin-RobIn/datamil). Không có PDF DataMIL trong thư viện local lúc kiểm. | Utility gắn policy/metric; target-set proxy, clustering, selection/training separation. Không yêu cầu project tái lập DataMIL. |
| S2 | Local `MimicGen.pdf`, [arXiv:2310.17596v1](https://arxiv.org/pdf/2310.17596v1), PDF pp3–4,6,19,40,42. | Object-frame/subtask/controller assumptions; execute-and-filter; author limitations và bias sau lọc. Không dùng bảng số để dự báo A1. |
| S3 | Local `HumanEgo.pdf`, [arXiv:2605.24934v3](https://arxiv.org/pdf/2605.24934v3), pp1,4–6,8 và mục limitations. | ICT hand–object representation, robot frontend, parallel-jaw/grasp latching và giới hạn transfer. Các kết quả paper không được xem là receipts của A1. |
| S4 | Local `FOCA.pdf`, [arXiv:2606.20867v1](https://arxiv.org/pdf/2606.20867v1), §method/Q2 p8, limitations p15, D.3/Table10 p20. | Action-free auxiliary khác pseudo-action training; compute theo stage. Phần review này không lập numerical comparison từ Table2; chưa kiểm trực quan Table2 nên không nâng nó thành numerical audit độc lập. |
| S5 | [LeRobotDataset v3 official docs](https://huggingface.co/docs/lerobot/lerobot-dataset-v3), format/layout/loading; [official loader source](https://github.com/huggingface/lerobot/blob/main/src/lerobot/datasets/lerobot_dataset.py). Docs/source `main` đọc trong phiên review, không pinned commit. | Storage/episode boundaries, schema, timestamp/fps. Site đã cảnh báo `tasks.jsonl` trong docs có thể khác actual `tasks.parquet`. |
| S6 | [EgoScale arXiv:2602.16710v1](https://arxiv.org/html/2602.16710v1), §2.1–2.4, §3.6, Appendix B/C/D.1 liên quan; [official project](https://research.nvidia.com/labs/gear/egoscale/), 19/02/2026. | Common wrist representation có hand articulation, alignment và downstream data; wrist-only limitation. Không quy small pilot thành replication 20k-hour pretraining. |
| S7 | [GR00T N1.5 release](https://research.nvidia.com/labs/gear/gr00t-n1_5/), 11/06/2025, architecture/training/data-limited evaluation/human sections; [Isaac-GR00T official README](https://github.com/NVIDIA/Isaac-GR00T), current N1.7 data/finetune/evaluation. | Frozen VLM và FLARE là precedent, không wrist-loss proof. README N1.7 chỉ đối chiếu storage/API/open-vs-closed-loop, không dùng nó thay N1.5 integration đã chọn. |
| S8 | Local `DreamGen.pdf`, pp3–6 method/pipeline, và [official project](https://research.nvidia.com/labs/gear/dreamgen/). | Generator, pseudo-actions và downstream policy là các bước khác nhau; không tự nhận executed success từ video sinh. |
| S9 | [SciPy binomtest](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.binomtest.html), [exact proportion CI](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats._result_classes.BinomTestResult.proportion_ci.html), docs v1.18.0 được trả về trong phiên. | Ý nghĩa exact CI/sidedness. Power ở D03 là tính toán analyst bằng binomial sum, không số trích paper. |

SHA-256 các PDF local được đọc:

```text
MimicGen  7345661fb8e8581981e272e1e043561cbfdaf3f8403d2cb5e28f70797c9bbb16
HumanEgo  d55c8a444478d9a851bfbdb8da7a79835d114e7e1d23c39b7ba29d239f4ba03f
FOCA      0140df8d6e0e6f9234ef45d1c15ebcc0461079d495e9dfe65f0ad817eb1e1ac9
DreamGen  e4e2c5c9e664d9331adb49c230053a76cf5bb4c3501341f4d9b372ecc585684c
```

## 5. Coverage file/route và unknowns còn lại

- Đã đọc nội dung trực tiếp của `IDEA.md`; dossier `03`, `05`, `06`, `07`, `08`, `10`, `12`, `15`; toàn bộ bốn tài liệu A1 `01–04`, README, TaskSpec/manifest/preflight/ledger. Các trích dẫn đối với `01` và `17` chỉ là đoạn liên quan được tìm/đọc, không full audit của hai file đó.
- Đã đọc `data-flywheel.json`, `training-blueprint.json`, `overview-flywheel.json` phần dataset/routes/acquisition/cost; `research-and-media.json` phần methods/media/provenance. `pilot-budget.json` được đọc đầy đủ; `industrial-cost-model.json` được parse toàn bộ inputs/scenarios và đọc boundary/evidence notes liên quan, không kiểm giá thị trường mới hay báo giá DENSO.
- Đã kiểm routing ở `app.js:219–224` và `engineering.js:15–26`. `#sources` dùng training blueprint; `#architecture` dùng data flywheel; `#learning` dùng learning renderer; `#overview` dùng flywheel overview. `#validation/#outcomes/#business/#roadmap` lấy dossier hiện hành. Các hàm cũ core15 T/F/A/75% trong `app.js` không được xem là lỗi live chỉ vì còn trong source. UI live/visual QA thuộc root reviewer.
- Đã đọc toàn `examples/engineering-loop/run.py`, các test liên quan, report/training receipts, final-results và metadata/schema của tất cả `results/*.json`. Releases có 44 seed rows, 1.047 synthetic rows và 49 correction rows; đã đọc các sample/structures liên quan, không nhận đã kiểm thủ công mọi frame và mọi 35×4 weight. Không rerun script, pytest hoặc native model.
- Đã so lại hash với snapshot cho IDEA và sáu content JSON chính được chỉ ra; đều khớp tại lúc ghi báo cáo. Hash nhận diện bản đọc, không chứng minh scientific validity.
- Chưa có native checkpoint/batch/gradient/GR1 rollout, native generator QA-yield, human release geometry audit hoặc activity ledger hoàn chỉnh được nhận diện trong scope audit. Đây là trạng thái hiện có trong hồ sơ, không khẳng định artifact không thể tồn tại ở nơi khác.
- Chưa xác minh quyền thương mại theo hợp đồng, không khảo sát user DENSO, không có đo hardware operations, robot reset/maintenance/downtime hay acceptance tại nhà máy. Không kết luận ROI hoặc production readiness.

**Thứ tự hành động đề xuất:** giữ taxonomy và caveats hiện có; sửa wording/guard D06; trong native feasibility tạo receipts đủ cho D05; trước source release vận hành D02/D04; trước final chốt D03; sau khi source/native usable mới thực hiện comparison D01 để kiểm giá trị riêng của flywheel. Không mở thêm phương pháp chỉ để làm câu chuyện đầy đủ.
