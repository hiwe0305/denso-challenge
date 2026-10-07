# Rà phần mở đầu và mapping data flywheel · 06/10/2026

Phạm vi: #overview trước thay đổi (`idea-story.js:renderIdeaOverview`, `idea-opening.js:openingIntro/openingArchitecture/openingEvidence`), IDEA.md, canonical01/15, A1 recipes. Đối chiếu fields từ3 screenshots22:56:33/45/54 ngày05/10. Không khảo sát DENSO, reproduce paper/native training hoặc visual audit toàn video. Đây là editorial/design assessment.

| Nhận xét / target | Premises → kết luận scoped | Mapping / next check |
|---|---|---|
| Problem-first · renderIdeaOverview | Solution/map/technical contracts trước evidence/cost; nhiều sections trùng technical routes. Đây là vấn đề trình bày quan sát được. | Renderer mới problem/cost→datasets/training→eval/runtime/errors→flywheel. Owner interview vẫn cần trước DENSO problem claim. |
| Data organization/use là trọng tâm · canonical03/15 | Lineage/QA/acquisition/replay/cost đã có, nhưng intro chưa làm luận đề. FigureIndex filtering/dedup/rebalance là tiền lệ. | Là decision/use loop, không chỉ store. Chưa đo là bottleneck lớn nhất A1; log coverage/QA-yield/cost/gain. |
| Training methods không bottleneck · canonical15 |7recipes có targets/modules/runtime khác; FOCA Table 2 thay supervision tạo gain ở same demo budget. | Phát biểu tuyệt đối không được hỗ trợ. Kế thừa backbone vẫn cần compatible objectives và implementation. |
| Ít data chất lượng · eval node | Nhãn/timing/geometry đúng + coverage cần; FOCA ít robot demos nhưng thêm priors/video/compute. | Same-quality roots/cost curve, CI/ID–OOD/regression; giữ rare/recovery cases. Chưa phổ quát càng ít càng tốt. |
| Synthetic/latent · loader connection | Synthetic là creation method; sim actions ghi sau execute; generatedvideo thiếuaction. Latent từ specificencoder. | Dataset synthetic riêng hợp lệ để version/ablation; capabilities quyết định losses, missingaction khôngzero giả. |
| Actions chỉ expert · gradient connection | Frozen-VLM recipe có tiền lệ; Flux selectedvisualtuning khác, actionloss có thể update upstream. | Pin trainablemanifest/gradient routes, không foundation pretraining lại; targetencoder frozen không toànVLM frozen. |
| Lỗi→train module · diagnosis node | Stagefail có thể từ grasp trước đó/binding/controller/input; oneepisode không causaldiagnosis. | Controlledtest→candidate repair/visual-interface/expert scope, chưa auto diagnosis. |

Thay đổi: `overview-flywheel.json/js/css` làm problem-first; nameddata/status/file/target/module rõ; public GR1 numericrows và transformations chưa chạy tách; source/companybenchmark khác nativeA1 “chưa đo”; cost assumptions sửa được; errorchecks→updatescopes; flywheelartifacts có lineage/cost/replay/no-gain/finaloutside. Canonical01/IDEAintro/formdraft đồng bộ. OldAIstory/3D không dẫn mở đầu và vẫn là minh họa, không evidence.

Nguồn đọc06/10/2026: [FOCA v1](https://arxiv.org/html/2606.20867v1)§3/§5Q2/Table 2/AppendixD.3; [Index](https://www.figure.ai/news/introducing-index)16Muploads/$15Mcreatorpayout; [Helix 2.5](https://www.figure.ai/news/helix-2-5-zero-shot-30-home-generalization)9 → 56%,3 tasks30unseenhomes, samedownstream; [Runpod](https://www.runpod.io/pricing)PodsA100PCIe80 GB1.59 USD/GPUh, Standard<1TB0.07 USD/GBmonth. Figurecompanyreport, không independent replication; LIBERO khácA1. Video prior transcript/description sourceaudit ở `docs/research/video-zKaeODg7xeE-2026-10-06/README.md`, chưa visualaudit toànvideo.

Budgetdefault 5.187,20 USD là phần tính từ planningrates/yield/hours/caps; không quote/saving hoặc fullproductioncost. Nativeusefuldata/transfer/ROI chưa chứng minh. Nextcheck: owner task/cost→pinGR1profile/nativebaseline→20trainrootsproposal→matchedR/R+S development với coverage/yield/cost/fulltask logs. Nếu baseline chưa chạy, ưu tiênintegration/feasibility, chưa mở thêm nguồn.


## Bổ sung sau phản hồi: Model AI chưa được trình bày đủ

Người dùng chỉ ra phần mở đầu đã nghiêng quá mạnh sang data operations. Quan sát đúng ở presentation: ba route file/target đã có nhưng chưa đủ để thấy model nền, encoders, action generation, training phases và World Model roles. Đây là thiếu sót trình bày, không chứng minh native architecture đúng/sai.

Đã bổ sung panel Model AI trong #overview và #learning: GR00T N1.5/FluxVLA, Eagle VLM → DiT Action Expert, training/inference riêng, robot loss/gradient scope, human shared-trunk custom candidate, video future-alignment candidate và World Model roles. Data Core và Model AI thành hai phần gắn trong solution; native execution/transfer vẫn chưa đo. Canonical16 giải thích và dẫn original sources; source recipe freeze VLM khác Flux visual-tuning được giữ rõ.
