# 12 · Public data examples và media provenance

_Website đã có numerical previews, Figures 1–5 FluxVLA lưu cùng hồ sơ và remote media; public previews không là training result của đội; executed reference artifacts v3.1 lưu riêng, chưa native VLA/human transfer. Clip GR1 episode 0 (18,8 giây) và ảnh xem trước thật lưu cùng website/ZIP để phát ổn định; media còn lại tải từ nguồn tác giả._

## Mẫu robot thật · Unitree G1/Dex3

Dataset: [G1_Dex3_ToastedBread_Dataset](https://huggingface.co/datasets/unitreerobotics/G1_Dex3_ToastedBread_Dataset). Repository revision quan sát: `02cb29161f5adb2981a072aa35b408d82a556d07`.

Metadata hiện tại: **v3.0**, 30fps, episode 0 có **620 frames** và segment video 0–20,6667 giây trong file ghép nhiều episodes. Mỗi frame có 28 `observation.state` và 28 `action` values; khớp tay và bàn tay được ghi tên. Không tự nhận force/contact/outcome labels không có trong mẫu.

Nguồn số: [Hugging Face Rows API](https://datasets-server.huggingface.co/rows?dataset=unitreerobotics%2FG1_Dex3_ToastedBread_Dataset&config=default&split=train&offset=0&length=100). API lấy current revision, không có pin SHA trong request; video/metadata URLs pin SHA. Đã kiểm episode index, frame order, timestamp, chiều tensor; chưa claim bitwise equality với pinned parquet.

Giá trị state và action khác nhau là sự khác nhau giữa observation và action target của dataset; độ lệch không tự chứng minh controller lỗi. Card có ví dụ v2, metadata hiện v3.0; integration phải pin loader thích hợp. Dataset card mô tả current state và next action; collector/controller timing chưa kiểm nên inspector không tự gọi action là command đã gửi. Dataset card ghi Apache-2.0, kiểm riêng quyền assets/downstream trước deployment.

## Mẫu human thật · HumanEgo

Dataset: [Leo-TX/HumanEgo](https://huggingface.co/datasets/Leo-TX/HumanEgo). Revision: `f0aa87fade6a41316d65322512f56f066dec62e3`. Recording `serve_bread/aria/mps_serve_bread_000_vrs`, 1002 tracking rows.

CSV `hand_tracking/hand_tracking_results.csv`; camera config `preprocess/aria_cam_rgb_config.json`. Preview giữ timestamp, confidence và wrist translations. Raw row 0: right confidence=-1, raw wrist=[0,0,0], normalized wrist=null. Đây là ví dụ thực về missing tracking và validity mask, không giả bàn tay ở tọa độ gốc.

CSV timestamps ở microseconds; camera config first_ts ở nanoseconds. Visualization và raw tracking là cùng recording nhưng frontend không giả frame-paired alignment chưa kiểm. Không coi human wrist là robot joint action. Data CC BY-NC 4.0 và code PolyForm Noncommercial khác nhau; đây là public research reference.

## Media credits

Mỗi asset có evidence type, caption và source page. Các samples không phải paired demonstrations của task DENSO. Task gắp chi tiết vào khay là ví dụ đề xuất, chưa dữ liệu thực của đội.

### Người thao tác, camera góc nhìn thứ nhất

Video thu dữ liệu · HumanEgo. Video minh họa collection do tác giả HumanEgo công bố. Camera và tracking bổ sung tín hiệu tay; đây chưa là lệnh điều khiển humanoid.

[Nguồn chính thức](https://humanego-ai.github.io/) · [Remote asset](https://humanego-ai.github.io/static/videos/data_collection_1.mp4)

### HumanEgo · serve_bread_000

Mẫu dataset công khai · HumanEgo. GIF visualization từ preprocessing của một recording thật. Tín hiệu CSV bên cạnh được lấy cùng recording; không giả frame-paired alignment. Dùng GIF tác giả công bố để xem overlay; video collection có player riêng bên dưới.

[Nguồn chính thức](https://huggingface.co/datasets/Leo-TX/HumanEgo) · [Remote asset](https://huggingface.co/datasets/Leo-TX/HumanEgo/resolve/f0aa87fade6a41316d65322512f56f066dec62e3/serve_bread/aria/mps_serve_bread_000_vrs/preprocess/vis/aria_vis.gif)

### Video con người đã có trên internet

Hình nguồn dữ liệu · LAPA. Hình do LAPA công bố về Something-Something V2. Minh họa dữ liệu video không có robot-action labels; website không chứa một corpus internet đã được cấp phép để train.

[Nguồn chính thức](https://latentactionpretraining.github.io/) · [Remote asset](https://latentactionpretraining.github.io/static/images/sthv2.png)

### MimicGen · biến thể môi trường

Demo nghiên cứu · Physics simulation. Quỹ đạo được thực thi trong mô phỏng với điều kiện reset khác. Robot arms trong nghiên cứu tham khảo, chưa là humanoid của đội.

[Nguồn chính thức](https://mimicgen.github.io/) · [Remote asset](https://mimicgen.github.io/resources/new_reset_dists/d2.mp4)

### MimicGen · các seed demonstrations

Demo nghiên cứu · Input cho generation. Demo nguồn của tác giả để tạo thêm quỹ đạo. Tăng số biến thể không làm tăng số roots độc lập tương ứng.

[Nguồn chính thức](https://mimicgen.github.io/) · [Remote asset](https://mimicgen.github.io/resources/new_reset_dists/src.mp4)

### DreamGen · video được sinh

Demo nghiên cứu · World-model generation. Video đóng cửa lò vi sóng được tác giả sinh bằng model. Muốn train action policy phải có bridge/IDM và QA; video này chưa là executed success.

[Nguồn chính thức](https://research.nvidia.com/labs/gear/dreamgen/) · [Remote asset](https://research.nvidia.com/labs/gear/videos//behavior/dreams/hsl/microwave_fast2.m3u8)

### DreamGen · robot thực thi sau học

Demo nghiên cứu · Policy rollout. Rollout do tác giả DreamGen công bố, tách khỏi video được sinh. Đây là bằng chứng của nghiên cứu, không phải kết quả của đội.

[Nguồn chính thức](https://research.nvidia.com/labs/gear/dreamgen/) · [Remote asset](https://research.nvidia.com/labs/gear/videos//behavior/policy/ours/hsl/microwave_fast.m3u8)

### EgoVLA · humanoid xếp lon

Demo nghiên cứu · Humanoid simulation. Policy rollout trong benchmark H1 của EgoVLA. Cho thấy đích thao tác humanoid; không dùng làm demo đã huấn luyện của project.

[Nguồn chính thức](https://rchalyang.github.io/EgoVLA/) · [Remote asset](https://rchalyang.github.io/EgoVLA/videos/compressed_480P/short_horizons/Stack-Can_room_2_table_5.mp4)

### Tay người → biểu diễn cho robot

Hình phương pháp · HumanEgo. Hình của HumanEgo minh họa xử lý khác biệt tay người và gripper. Với G1/Dex3 hoặc robot khác phải kiểm mapping riêng.

[Nguồn chính thức](https://humanego-ai.github.io/) · [Remote asset](https://humanego-ai.github.io/static/images/hand2gripper.png)

### Unitree G1/Dex3 · toasted bread, episode 0

Mẫu teleop robot thật · Unitree Robotics. Camera trái phía trên; chỉ xem segment episode 0 dài 20,67 giây trong file video ghép nhiều episodes. Mẫu numeric: 620 frames, 28 state và 28 action values mỗi frame.

[Nguồn chính thức](https://huggingface.co/datasets/unitreerobotics/G1_Dex3_ToastedBread_Dataset) · [Remote asset](https://huggingface.co/datasets/unitreerobotics/G1_Dex3_ToastedBread_Dataset/resolve/02cb29161f5adb2981a072aa35b408d82a556d07/videos/observation.images.cam_left_high/chunk-000/file-000.mp4)

### FluxVLA · Figure 1 từ paper gốc

Hình gốc trong paper · Figure 1, trang 2 · arXiv v1. Hình trích trực tiếp từ Figure 1, trang 2 của paper FluxVLA Engine (Li và cộng sự, 2026), giữ nguyên kiến trúc và bảng kết quả bên phải. Các số liệu là kết quả tác giả, với ngân sách training/evaluation khác nhau giữa integrations; không phải kết quả của đề xuất.

[Nguồn chính thức](https://arxiv.org/abs/2609.17210v1) · [Hình lưu cùng hồ sơ](assets/fluxvla-paper-figure-1.png)

Crédit : Li et al., FluxVLA Engine (2026), arXiv:2609.17210v1. [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Figure trích nguyên vùng hình từ PDF; không vẽ lại. Chú thích tiếng Việt đặt ngoài hình.

Provenance: `{"paper": "docs/references/papers/FluxVLA.pdf", "paperSha256": "072b043efcd9126baec332b746c335b3bab3312b8e0ead6974e261bfc6e04acc", "figure": 1, "page": 2, "cropPoints": [51, 51, 561, 266], "renderScale": 6, "assetSha256": "9a3d3458ffb1915c634eca04c7f1dcdf3564075823a52d8e0136ae2e4f7a658b", "checked": "2026-10-03"}`

### LIBERO · Panda · episode 0

Simulation demonstration · public LeRobotDataset v3. Task public: đặt cốc trắng lên đĩa trái, cốc vàng-trắng lên đĩa phải. Episode 0 có 214 frames, 10fps, segment 0–21,4s trong file ghép nhiều episodes. Đây là demonstration trong sim, không real-humanoid teleop hoặc rollout của đội.

[Nguồn chính thức](https://huggingface.co/datasets/lerobot/libero) · [Remote asset](https://huggingface.co/datasets/lerobot/libero/resolve/a1aaacb7f6cd6ee5fb43120f673cebb0cfea7dd4/videos/observation.images.image/chunk-000/file-000.mp4)

### RoboCasa GR1 · đưa chai vào tủ và đóng cửa

Humanoid simulation demonstration · public FluxVLA dataset. GR1 arms/waist/Fourier hands, camera egocentric 20fps. Episode 0 có 376 frames (~18,8s). Task household có waist unlocked; khác task khay fixed-torso của proposal. Dataset demonstration, không policy rollout của đội.

[Nguồn chính thức](https://huggingface.co/datasets/limxdynamics/FluxVLAData/tree/7998ab57bc70be66234b5374800705e2b6c14545/robocasa_gr1_24tasks_first30ep) · [Remote asset](https://huggingface.co/datasets/limxdynamics/FluxVLAData/resolve/7998ab57bc70be66234b5374800705e2b6c14545/robocasa_gr1_24tasks_first30ep/PnPBottleToCabinetClose/videos/chunk-000/observation.images.ego_view/episode_000000.mp4)

Clip xem trong website: `assets/gr1-episode-0.mp4`; poster: `assets/gr1-episode-0-poster.jpg`. Nguồn gốc NVIDIA/RoboCasa qua FluxVLA subset, [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/); chỉ minh họa hồ sơ nghiên cứu/idea. MP4 được remux faststart, không đổi frames; poster trích tại t=0. Không phải kết quả của đội.

Provenance: `{"revision": "7998ab57bc70be66234b5374800705e2b6c14545", "sourceSha256": "c9250ff66dd30a52a9dc5e2b44cb817f8703087d576030df0532e24c96cc55e9", "playbackSha256": "f110cc1c6d5adafb3bde97952d7def0b50e1a00d8a8d5d201eb81b0f5e9e98c0", "posterSha256": "fdca99291b73253f4c17098109175847f7787016634fe03261c41f1bad9ca3de", "changes": "MP4 remux with faststart; H.264 frames unchanged. Poster extracted at t=0. No training result of this project.", "upstream": "https://huggingface.co/datasets/nvidia/PhysicalAI-Robotics-GR00T-Teleop-Sim", "checked": "2026-10-05"}`

### FluxVLA · Data pipeline

Hình gốc trong paper · Figure 2, trang 8 · arXiv v1. Episode → temporal sample → transforms → batch → model. Hình của Li và cộng sự (2026); không phải kết quả triển khai A1 của đội.

[Nguồn chính thức](https://arxiv.org/pdf/2609.17210v1#page=8) · [Hình lưu cùng hồ sơ](assets/fluxvla-paper-figure-2.png)

Crédit : Li et al., FluxVLA Engine (2026), arXiv:2609.17210v1. [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Figure trích nguyên vùng hình từ PDF; không vẽ lại. Chú thích tiếng Việt đặt ngoài hình.

Provenance: `{"paper": "docs/references/papers/FluxVLA.pdf", "paperSha256": "072b043efcd9126baec332b746c335b3bab3312b8e0ead6974e261bfc6e04acc", "figure": 2, "page": 8, "cropPoints": [51, 51, 561, 256], "renderScale": 6, "assetSha256": "1cb05d9ed8d2ad2a9b2272f3d1a4ae530f3faa444a036defc510b33493bf3711", "checked": "2026-10-06", "credit": "Li và cộng sự, FluxVLA Engine (2026)", "extraction": "Trích nguyên vùng figure từ PDF; giữ nội dung/nhãn/mũi tên, không vẽ lại; chú thích tiếng Việt nằm ngoài ảnh."}`

### FluxVLA · Model composition

Hình gốc trong paper · Figure 3, trang 9 · arXiv v1. Config → registry → các model families; phân biệt forward/loss và predict_action. Hình của Li và cộng sự (2026); không phải kết quả triển khai A1 của đội.

[Nguồn chính thức](https://arxiv.org/pdf/2609.17210v1#page=9) · [Hình lưu cùng hồ sơ](assets/fluxvla-paper-figure-3.png)

Crédit : Li et al., FluxVLA Engine (2026), arXiv:2609.17210v1. [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Figure trích nguyên vùng hình từ PDF; không vẽ lại. Chú thích tiếng Việt đặt ngoài hình.

Provenance: `{"paper": "docs/references/papers/FluxVLA.pdf", "paperSha256": "072b043efcd9126baec332b746c335b3bab3312b8e0ead6974e261bfc6e04acc", "figure": 3, "page": 9, "cropPoints": [51, 51, 561, 303], "renderScale": 6, "assetSha256": "99ceea3991a547ed371a9acf5de6e12c763126e5abbaca73461b25fffe9bedfb", "checked": "2026-10-06", "credit": "Li và cộng sự, FluxVLA Engine (2026)", "extraction": "Trích nguyên vùng figure từ PDF; giữ nội dung/nhãn/mũi tên, không vẽ lại; chú thích tiếng Việt nằm ngoài ảnh."}`

### FluxVLA · Closed-loop simulation evaluation

Hình gốc trong paper · Figure 4, trang 12 · arXiv v1. Reload checkpoint → observe / predict / execute → đo kết quả và lưu artifacts. Hình của Li và cộng sự (2026); không phải kết quả triển khai A1 của đội.

[Nguồn chính thức](https://arxiv.org/pdf/2609.17210v1#page=12) · [Hình lưu cùng hồ sơ](assets/fluxvla-paper-figure-4.png)

Crédit : Li et al., FluxVLA Engine (2026), arXiv:2609.17210v1. [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Figure trích nguyên vùng hình từ PDF; không vẽ lại. Chú thích tiếng Việt đặt ngoài hình.

Provenance: `{"paper": "docs/references/papers/FluxVLA.pdf", "paperSha256": "072b043efcd9126baec332b746c335b3bab3312b8e0ead6974e261bfc6e04acc", "figure": 4, "page": 12, "cropPoints": [51, 51, 561, 322], "renderScale": 6, "assetSha256": "bae402c0dc3c38445b03c9d5abee9a50677b015deab985d2709374c847c58d11", "checked": "2026-10-06", "credit": "Li và cộng sự, FluxVLA Engine (2026)", "extraction": "Trích nguyên vùng figure từ PDF; giữ nội dung/nhãn/mũi tên, không vẽ lại; chú thích tiếng Việt nằm ngoài ảnh."}`

### FluxVLA · Inference acceleration

Hình gốc trong paper · Figure 5, trang 14 · arXiv v1. Thay modules cho inference và tối ưu execution; đây là kiến trúc tăng tốc model, không phải sơ đồ controller robot. Hình của Li và cộng sự (2026); không phải kết quả triển khai A1 của đội.

[Nguồn chính thức](https://arxiv.org/pdf/2609.17210v1#page=14) · [Hình lưu cùng hồ sơ](assets/fluxvla-paper-figure-5.png)

Crédit : Li et al., FluxVLA Engine (2026), arXiv:2609.17210v1. [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Figure trích nguyên vùng hình từ PDF; không vẽ lại. Chú thích tiếng Việt đặt ngoài hình.

Provenance: `{"paper": "docs/references/papers/FluxVLA.pdf", "paperSha256": "072b043efcd9126baec332b746c335b3bab3312b8e0ead6974e261bfc6e04acc", "figure": 5, "page": 14, "cropPoints": [51, 51, 561, 345], "renderScale": 6, "assetSha256": "1d9a7c7a333f6c4c19896898dad4aea88f5b123b021601242f26ff5daefdf743", "checked": "2026-10-06", "credit": "Li và cộng sự, FluxVLA Engine (2026)", "extraction": "Trích nguyên vùng figure từ PDF; giữ nội dung/nhãn/mũi tên, không vẽ lại; chú thích tiếng Việt nằm ngoài ảnh."}`

## Integrity và phân phối

Numerical samples, Figures 1–5 FluxVLA và clip GR1 đọc được offline; các video/ảnh remote khác cần internet và codec browser. Source hash dưới đây giúp nhận diện preview đã đóng gói, không thay hash raw dataset.

- `g1-episode-0.json` · SHA-256 `25bbc482e031cd59d9c2f9e2563a5020f825826d374d3cd127216c12f7861639`
- `gr1-preview.json` · SHA-256 `b3f219f882e244a272b34cc74faffb16f72eaec4707c35658c8c1759c3455706`
- `humanego-hands.json` · SHA-256 `c8b177f34c0d1f37da11338484bc094b72afd1deaf1cd0cf717a6324d9e7f37b`
- `libero-preview.json` · SHA-256 `5bab7450a882daa869fb65c4553e3ea8feda5de68bf05d175f82d486d7b13ff4`

[Data Core](03-data-core.md) · [SOP](10-data-collection-sop.md) · [Khảo sát](11-method-survey.md).

## Mẫu LeRobotDataset v3 · LIBERO simulation demonstrations

[lerobot/libero](https://huggingface.co/datasets/lerobot/libero). Dataset revision `a1aaacb7f6cd6ee5fb43120f673cebb0cfea7dd4`. Panda simulation demonstrations, không real-humanoid teleop. Metadata: v3.0, 1693 episodes, 273465 frames, 40 tasks, 10fps; 2 cameras 256×256, state float32[8], action float32[7].

Instruction task 0 trong tasks.parquet: put the white mug on the left plate and put the yellow and white mug on the right plate. Episode 0 có 214 frames, segment hai camera 0–21,4s. Preview `libero-preview.json` giữ 6 rows đầu episode 0 từ Rows API ngày 02/10/2026, không toàn episode. Numeric API đọc current revision, chưa bitwise đối chiếu pinned parquet. Metadata URL pin SHA; không tự gán tên/units các dimensions chỉ ghi generic state/actions.

LeRobot v3: meta/info.json, meta/tasks.parquet, meta/episodes/chunk-000/file-000.parquet, data/chunk-000/file-000.parquet và videos/{video_key}/chunk-000/file-000.mp4. Episode metadata chỉ vị trí episode trong các file ghép; không giả mỗi episode một MP4. [Đặc tả chính thức](https://huggingface.co/docs/lerobot/main/en/lerobot-dataset-v3). Dataset viewer/video là của tác giả; không cặp human–robot đã align với G1/HumanEgo.

## Humanoid benchmark · RoboCasa GR1 và FluxVLA subset

[Benchmark chính thức](https://github.com/robocasa/robocasa-gr1-tabletop-tasks): 24 tabletop tasks. [NVIDIA teleop-sim](https://huggingface.co/datasets/nvidia/PhysicalAI-Robotics-GR00T-Teleop-Sim) công bố 1000 demos/task, CC BY-NC 4.0. [FluxVLA subset](https://huggingface.co/datasets/limxdynamics/FluxVLAData/tree/7998ab57bc70be66234b5374800705e2b6c14545/robocasa_gr1_24tasks_first30ep) có 24 task folders và 720 episode Parquets (30/task), kiểm repository API ngày 03/10/2026. HumanoidBench là whole-body RL benchmark, không tự có expert LeRobot demonstrations như LIBERO.

Ví dụ pinned subset PnPBottleToCabinetClose: LeRobot v2.1, robot GR1ArmsAndWaistFourierHands, 20fps, ego camera 256×256, state/action float64[29]. Folder metadata: 30 episodes, 10772 frames. Episode 0: 376 frames. JSON giữ 6 rows đầu trích trực tiếp từ pinned Parquet, URL và SHA-256 của raw Parquet; không Rows API current mismatch.

Instruction mô tả đưa chai vào tủ rồi đóng cửa; waist unlocked, khác fixed-torso task khay. metadata splits.train=0:100 chưa khớp subset 30 episodes; tasks indices 0 và 1 lặp instruction. Preview giữ nguyên, tra task index của row, không gọi duplicate labels là hai task khác nhau. Loader/binding/normalization phải kiểm theo actual episode list và selected model config.

Card FluxVLAData Apache-2.0 không tự thay quyền gốc NVIDIA CC BY-NC 4.0 cho assets/data dẫn xuất. Đây là public research preview; chưa tự kết luận đủ quyền commercial. Số chiều 29 của subset không áp cho mọi release GR1 hay robot G1.
