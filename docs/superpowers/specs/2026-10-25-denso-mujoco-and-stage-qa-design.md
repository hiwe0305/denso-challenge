# Design: robot DENSO trên MuJoCo, pipeline dữ liệu theo stage và Agent QA/QC

_Ngày 25/10/2026. Trạng thái: **đã duyệt** (trưởng nhóm, 25/10/2026), chưa có code. Tài liệu này đổi trọng tâm của [spec v10.2](../../spec-v10-failure-to-data.md) và [design ngày 23/10/2026](2026-10-23-data-pipeline-and-failure-eval-design.md); phần bị thay liệt kê ở mục 13. Đã đưa vào spec v10.3, 03 bản 0.5, 04, 07, 08, RULE và file story ngày 25/10/2026 Người làm ở mục 11 và cấu trúc package đã được thay bởi [design chia làn](2026-10-25-lanes-and-code-structure-design.md)._

Quy ước: **[Đã chốt]** là câu trả lời của trưởng nhóm (Hiếu) ngày 25/10/2026. **[Đề xuất]** là lựa chọn của người viết, cần duyệt. **[Option]** là nhiều phương án song song, chờ thông tin. Số liệu chưa đo ghi là ước lượng.

## 0. Đọc nhanh

1. **SIMPLE chỉ còn là benchmark** để kiểm Ψ₀ chạy được và chạy thế nào (G0). Thí nghiệm có đối chứng (HS, HT, HD) chuyển sang **robot DENSO trên MuJoCo**. G1 phát triển sau [Đã chốt].
2. **MuJoCo là simulator chính**: dựng robot DENSO tương đương, task khay → máy, teleop bằng bàn phím trong sim để thu dataset, và **phát lại action** để kiểm dữ liệu trước khi train. Isaac Sim chỉ thêm khi có cảnh nhà máy rõ ràng, dùng vật lý MuJoCo [Đã chốt].
3. **Code train cả 3 stage lấy từ GitHub của tác giả Ψ₀**; log train lấy bằng cách đọc code của họ để biết họ log gì, rồi bọc thêm phần còn thiếu [Đã chốt].
4. **Ba pipeline tách riêng**: video egocentric thô → dữ liệu fine-tune stage 1 (VLM); synthetic theo bốn tầng; teleop → LeRobotDataset v2.1, có bộ export v3 [Đã chốt].
5. **Agent QA/QC** dùng Nemotron 3.5 Bolt E4B 4GB chạy cục bộ: đọc log và output của từng stage, dựng hình cho người hiểu, đưa insight và ước lượng; AI Engineer quyết [Đã chốt].
6. Mục tiêu demo: robot làm được task khay → máy trên MuJoCo với tỉ lệ thành công **đạt tiêu chí của BTC** trước; Isaac Sim không cần cho demo [Đã chốt].

## 1. Bối cảnh và lý do

Design 23/10/2026 giữ G1 trong SIMPLE làm bàn thử cho HS, HT, HD và dựng robot DENSO trong Isaac Sim. Phần lớn rủi ro của spec đến từ SIMPLE: teleop chạy decoupled WBC (`g1_sonic`) còn motion planning chạy AMO (`g1_wholebody`), nên cần câu V3, bốn tuyến T1–T4 và kịch bản "V3 âm cộng Q6 âm thì HT sụp" (spec mục 10). Mọi thí nghiệm lại xoay quanh một robot không phải của DENSO.

Ngày 25/10/2026 trưởng nhóm trả lời 8 câu hỏi và chốt:

| # | Câu hỏi | Trả lời [Đã chốt] |
|---|---|---|
| 1 | Thí nghiệm có đối chứng chạy ở đâu | Phần lớn chuyển sang DENSO trên MuJoCo (sau này thêm Isaac); G1 phát triển sau |
| 2 | Ngân sách GPU | RTX 3060 12 GB, cộng Colab Pro chạy được qua CLI khi cần (A100, H100) |
| 3 | Stage 1 | Fine-tune trên bộ dữ liệu hợp với task DENSO, từ video egocentric thô; cần pipeline để xử lý ra dữ liệu train VLM |
| 4 | Agent QA/QC | Chỉ đánh giá log train và output của từng bước; phải biểu diễn cho người hiểu: stage 1 ra ảnh và chữ, stage 2 ra action biểu diễn trên MuJoCo, log inference (Real-Time Action Chunking…) để xử lý bài toán bất đồng bộ |
| 5 | Ai thu teleop | Đội tự điều khiển; chưa ước lượng giờ; có thêm bộ dataset của BTC DENSO |
| 6 | Robot thay thế | Dựng model tương đương rồi tinh chỉnh; đang làm việc với BTC để lấy dữ liệu và URDF/USD |
| 7 | Quy trình duyệt | Hiếu là người duyệt và merge duy nhất; Claude bật lịch tracking thường xuyên, cuối ngày thảo luận |
| 8 | Demo | Không cần Isaac Sim; cần demo làm được task với tỉ lệ thành công đạt tiêu chuẩn trước |

Cùng ngày người viết kiểm repo [Psi0](https://github.com/physical-superintelligence-lab/Psi0) (nhánh `main`):

- **Có code train đủ 3 stage.** Stage 1: `scripts/train/psi0/pretrain-{egodex,egoverse,he,mix}-psi0-fast.sh`, config `pretrain_*_qwen3vl_config`, trainer `src/psi/trainers/pretrain.py`. Stage 2: `posttrain-{he,mix}-psi0.sh`, trainer `posttrain.py`. Stage 3: `finetune-*-psi0.sh`, trainer `finetune.py`. Thêm `scripts/save_pretrain_qwen3vl_backbone.py`, `scripts/save_posttrain_action_expert.py`, và baseline ACT, DP, GR00T, π0.5 trong `baselines/`.
- **Log qua `accelerate` tới W&B** (`--log.report_to=wandb`): `train/loss`, `lr`, `epoch`, `grad_norm_vlm` (stage 1), `grad_norm_<nhóm>` và `grad_norm_act` (stage 2–3), `eval/*`. Không log mặc định: loss theo nhóm action, loss theo vị trí trong chunk, phương sai action dự đoán, phân bố độ mở gripper.
- **Checkpoint công bố không kèm log train**: mỗi run trên Hugging Face chỉ có `argv.txt`, `run_config.json`, `envs.txt` và trọng số (docs/g0/psi0-eval.md của S1-03).
- **Định dạng LeRobot**: Ψ₀ dùng fork `songlin/lerobot@09929d8` có `CODEBASE_VERSION = "v2.1"`, cùng `datasets==3.6.0`.
- **RTC**: `real/deploy/psi-inference_rtc.py` và `scripts/deploy/serve_psi0-rtc-*.sh` chạy client gửi quan sát qua WebSocket, nhận action chunk, một luồng điều khiển đọc action từ buffer theo chu kỳ cố định. Finetune SIMPLE dùng `--model.rtc` với `max-delay 8`.
- **EgoDex**: loader `src/psi/data/egodex/egodex_dataset.py` (đọc biến đổi khớp tay và video), `scripts/data/calc_egodex_stats.py`, `utils/draw_utils.py` vẽ khung xương tay.

Nemotron 3.5 Bolt E4B 4GB ([NVIDIA](https://research.nvidia.com/labs/nemotron/Nemotron-3.5-Bolt-E4B-4GB/), ra ngày 23/10/2026): dựng trên Gemma-4-E4B-it, 8B tham số tổng, 4B hiệu dụng, ngữ cảnh 64K, chỉ nhận chữ theo tài liệu của NVIDIA, gọi tool được, bản Q4 cần khoảng 3–4 GB VRAM, giấy phép OpenMDW-1.1.

## 2. Mục tiêu, không làm, phản mục tiêu

**Mục tiêu**

- M1. Robot DENSO tương đương trong MuJoCo (MJCF) với cảnh trạm và task khay → máy 6 bước, 10 kiểu lỗi (design 23/10 mục 7.1); chấm được độ giống theo design 23/10 mục 3.1.
- M2. Teleop bàn phím trong MuJoCo ghi ra episode đúng định dạng chung; đọc được dataset của BTC DENSO vào cùng định dạng.
- M3. Phát lại action trên MuJoCo cho mọi episode có action robot, là một bước QA bắt buộc trước khi train.
- M4. Ba pipeline: egocentric thô → dữ liệu fine-tune stage 1; synthetic S1–S4 với đầu vào, đầu ra và công cụ cụ thể; teleop → LeRobotDataset v2.1 (bắt buộc) và v3 (tùy chọn).
- M5. Train 3 stage của Ψ₀ bằng code của tác giả, ghim commit; mỗi lần train có log đủ để chấm riêng từng stage.
- M6. Agent QA/QC đọc log và output của từng stage, dựng hình cho người đọc, đưa insight và ước lượng có khoảng; không tự quyết.
- M7. Chạy các nhánh A, A₀.₇, B, B-fail, C và holdout trên robot DENSO trong MuJoCo; báo HS, HT, HD và tiêu chí 3 cấp của BTC.
- M8. Người trong đội không phải chờ nhau; Hiếu duyệt và merge duy nhất; tiến độ được theo dõi tự động mỗi ngày.

**Không làm**

- Thí nghiệm có đối chứng trên G1 trong SIMPLE; SIMPLE chỉ dùng cho G0 (S1-03) và smoke test serve, eval của Ψ₀.
- Isaac Sim trước khi demo trên MuJoCo đạt tiêu chí.
- Train lại stage 1 từ đầu; chỉ fine-tune từ checkpoint `pre.*`.
- Robot DENSO thật; giao diện web. Báo cáo vẫn là HTML tĩnh (03 mục 2.4).

**Phản mục tiêu** (kỹ thuật vẫn chạy nhưng coi là hỏng)

- Dữ liệu DENSO đi ra một dịch vụ bên ngoài khi chưa có quyền ghi bằng văn bản (mục 9).
- Agent QA/QC tự đưa ra con số không có trong log, hoặc tự chọn dữ liệu thay kỹ sư.
- Đạt tỉ lệ thành công nhờ môi trường dễ hơn task thật: dung sai đồ gá rộng hơn thông số máy, vật lý tiếp xúc nới lỏng, hoặc điều kiện holdout trùng train.
- Đánh giá closed-loop chỉ ở chế độ đồng bộ, che mất lỗi bất đồng bộ của action chunking (mục 7.3).

## 3. Phân vai simulator

| Simulator | Vai trò | Khi nào |
|---|---|---|
| MuJoCo | Vật lý, teleop bàn phím, phát lại action, closed-loop eval, chạy các nhánh, video demo | Từ Sprint 1 |
| Isaac Sim | Render cảnh nhà máy cho synthetic S3 và video đẹp; vật lý dùng MuJoCo để kết quả không đổi khi đổi renderer | Khi DENSO gửi layout và hình ảnh nhà máy rõ ràng, và sau khi demo MuJoCo đạt tiêu chí |
| SIMPLE | Benchmark G0: tái tạo số công bố của Ψ₀, kiểm serve và eval | Sprint 1, giữ làm smoke test |

**Một file mô hình duy nhất** [Đề xuất]: robot và cảnh mô tả bằng MJCF, là nguồn sự thật. Khi có Isaac, file USD sinh từ cùng thông số; không chỉnh tay hai nơi. SIMPLE đã dùng đúng mẫu này (MuJoCo lo vật lý 500 Hz, Isaac Sim chỉ render, `BaseDualSim`, 03 mục 3.2). Phiên bản Isaac có tích hợp vật lý MuJoCo cần kiểm khi tới bước này.

**Robot tương đương** [Đã chốt]: dựng từ hình vẽ DENSO (`docs/challenge/`) trước, tinh chỉnh khi BTC gửi URDF/USD. Cách dựng giữ như `denso_mm_proxy` của design 23/10 mục 3.1 (một file tham số cho mọi kích thước, tay kiểu Kinova Gen3 là phán đoán chưa xác nhận), chỉ đổi đích xuất từ USD sang MJCF. Khi có URDF: chuyển sang MJCF, chấm lại độ giống theo design 23/10 mục 3.1, ghi `Decision`. Nhóm action giữ như design: `base`, `lift`, `arm_l`, `arm_r`, `gripper_l`, `gripper_r`, `head`, đệm vào khung 36 chiều của Ψ₀.

**Camera** [Đề xuất, lựa chọn của người viết]: một camera RGB trên đỉnh cột như hình vẽ, độ phân giải ảnh vào policy theo config Ψ₀ (240 × 320 ở finetune sonic, 180 × 320 ở finetune simple). Camera cổ tay khai sẵn trong MJCF nhưng tắt, bật khi thông số DENSO cho biết có.

**Môi trường không được dễ hơn task thật** [Đề xuất]: dung sai đồ gá, khối lượng linh kiện, ma sát và giới hạn khớp lấy từ thông số DENSO khi có; trước đó ghi giá trị giả định vào `configs/embodiments/` kèm nguồn, và mọi kết quả ghi rõ "trên tham số giả định".

## 4. Teleop trong MuJoCo

### 4.1 Teleop bàn phím

| Phần | Cách làm |
|---|---|
| Không gian điều khiển | Đầu tay (EEF) qua IK, không lái từng khớp [Đề xuất]; đế điều khiển bằng vận tốc; cột nâng và gripper bằng phím riêng |
| Chế độ | Chuyển chế độ theo nhóm: đế, cột nâng, tay trái, tay phải, đầu; gripper luôn có phím riêng |
| Tần số | Ghi ở tần số điều khiển của robot (khai trong `control_spec`); ảnh theo fps của camera, mỗi khung có `t_image` riêng |
| Ghi | Mỗi episode thành một bundle định dạng chung (03 mục 4, `frames.parquet`, `signals.parquet`, `videos/*.mp4`, `meta.json`); `source = teleop_keyboard`, người điều khiển, hạt giống điều kiện, phiên bản MJCF |
| Kết thúc episode | Người điều khiển bấm phím thành công hoặc thất bại; scorer tự chấm lại sau, nhãn của người chỉ để đối chiếu |
| Reset | Đặt lại về trạng thái đầu từ hạt giống điều kiện; MuJoCo đặt state trực tiếp nên khôi phục giữa episode (Q3) có sẵn |
| Giờ người | Mỗi phiên ghi một mục sổ chi phí: phút người, số episode, số episode đạt |

Giới hạn phải nêu: demo bàn phím chậm và giật hơn teleop thật; dùng tốt để so phương pháp với nhau, không dùng để nói số tuyệt đối về dữ liệu nhà máy. Thiết bị khác (gamepad, SpaceMouse, VR) cắm vào cùng giao diện sau [Đề xuất].

### 4.2 Dataset của BTC DENSO

Đội có thêm dataset của BTC [Đã chốt]. Một bộ đọc trong adapter `TeleopSource` chuyển nó về định dạng chung, qua cùng QA và phát lại. Nội dung, định dạng, robot, giấy phép và `data_class` của dataset này chưa biết; mục 12 câu Q-A.

### 4.3 Số demo cần

E1 cần ít nhất 50 demo teleop đạt QA (spec Q1); với lưới 10–100% và holdout riêng, ước lượng 100–200 demo. Dataset của BTC có thể bù phần lớn nếu cùng robot và cùng task. Giờ người đo ở tuần 1 bằng 20 demo thử, rồi mới chốt kế hoạch thu [Đề xuất].

## 5. Ba pipeline dữ liệu

Cả ba nguồn vẫn đi qua sáu tầng của design 23/10 mục 5 (Ingest → Normalize → Annotate → QA → Release → Export). Mục này ghi phần mới.

### 5.1 Teleop → LeRobotDataset v2.1 và v3

| Tầng | Việc |
|---|---|
| Ingest | Bàn phím (mục 4.1), dataset BTC (mục 4.2), sau này teleop thật của DENSO |
| Normalize | Đồng bộ về đồng hồ chung, SI và radian, ánh xạ khớp vào `action_layout`, đệm 36 chiều |
| QA | 7 phép kiểm của spec mục 4.4, phép kiểm riêng của teleop (design 23/10 mục 5.1), **phát lại trên MuJoCo** (mục 5.4) |
| Export v2.1 | Bắt buộc. Đúng `CODEBASE_VERSION = "v2.1"` của fork lerobot mà Ψ₀ dùng; `stats_psi0.json`; contract test đọc lại bằng loader Ψ₀ ở commit đã ghim |
| Export v3 | Tùy chọn. Chuyển từ bản v2.1 bằng script chuyển đổi chính thức của LeRobot; contract test đọc lại bằng `lerobot` bản mới. Không xử lý lại dữ liệu, vì bundle nội bộ là nguồn sự thật (03 ADR-03) |

**Checklist chuẩn hóa LeRobot** [Đề xuất], chạy tự động trong contract test:

1. `meta/info.json`: `codebase_version`, `fps`, `robot_type`, `features` khớp shape và tên từng chiều với `action_layout`.
2. `episode_index` và `index` liên tục; `frame_index` bắt đầu từ 0 mỗi episode.
3. `timestamp` khớp `frame_index / fps` trong dung sai nửa chu kỳ.
4. Video giải mã được, số khung khớp số dòng; codec và độ phân giải đúng khai báo.
5. `tasks` có câu lệnh ngôn ngữ cho mọi episode.
6. Stats tính trên đúng release, không có NaN; chiều đệm có mask.
7. Đọc lại bằng loader Ψ₀ ra đúng một batch mẫu đã lưu (so từng giá trị).

### 5.2 Egocentric thô → dữ liệu fine-tune stage 1

Mục tiêu [Đã chốt]: fine-tune VLM stage 1 (Qwen3-VL-2B trong Ψ₀) trên video egocentric hợp với task DENSO, từ video thô.

```text
video thô ─► che danh tính ─► cắt đoạn theo bước task ─► pose tay 3D + tư thế camera
          ─► định dạng EgoDex (biến đổi khớp tay + mp4) + câu lệnh ngôn ngữ
          ─► stats (calc_egodex_stats.py) ─► EgoDexDataConfig của Ψ₀ ─► pretrain_egodex_qwen3vl_config
```

| Bước | Cách làm | Ghi chú |
|---|---|---|
| Che danh tính | Khuôn mặt, thẻ tên, màn hình; bắt buộc trước mọi bước khác (`deid_status`) | Bất biến kiến trúc |
| Cắt đoạn | Theo 6 bước của task khay → máy; luật trước, Cosmos Reason gợi ý khi luật mơ hồ, người duyệt mẫu | Cosmos Reason tự host chỉ khi đủ GPU (mục 9) |
| Pose | E-B: đọc từ thiết bị có hand tracking. E-A (video RGB thường): ước lượng bằng model hand pose và SLAM, gắn `action_quality = pseudo` | E-A nhiễu; báo riêng |
| Định dạng | Đúng cấu trúc mà `src/psi/data/egodex/egodex_dataset.py` đọc; khớp `chunk_size`, `upsample_rate`, delta action như config gốc | Contract test bằng loader Ψ₀ |
| Ngôn ngữ | Câu lệnh mỗi đoạn; thêm cặp hỏi đáp về linh kiện, khay, máy, bước đang làm | Hỏi đáp dùng cho probe P1 |

**Mục tiêu train** [Đề xuất, lựa chọn của người viết]: fine-tune theo đúng mục tiêu gốc của stage 1 (dự đoán token FAST của chuyển động tay), vì đó là thứ stage 2 kế thừa. Cặp hỏi đáp dùng để chấm (P1) trước, chỉ đưa vào train khi P1 cho thấy VLM yếu trên cảnh nhà máy. Fine-tune kiểu LoRA hay toàn bộ, và trên máy nào, quyết sau khi đo (mục 6.3).

**Đo trước và sau fine-tune**: P1 (hiểu cảnh), P2 (loss token FAST trên egocentric giữ lại), P4 (quên: chạy lại P1, P2 trên EgoDex gốc). Fine-tune chỉ được giữ khi P1 hoặc P2 trên dữ liệu DENSO tốt lên mà P4 không tụt quá ngưỡng ghi trước trong RunPlan.

### 5.3 Synthetic

| Tầng | Sinh ở đâu | Đầu vào | Đầu ra | Action |
|---|---|---|---|---|
| S1 · Planner | MuJoCo, IK cộng planner cho robot DENSO | Điều kiện ngẫu nhiên trong miền train | Episode rollout đạt scorer | `planned` |
| S2 · Biến thể từ teleop | MuJoCo | Đoạn teleop bàn phím hoặc BTC; trạng thái lỗi đã lưu | Biến thể theo tư thế linh kiện kiểu MimicGen; correction bắt đầu từ trạng thái lỗi | `planned` |
| S3 · Đổi ngoại hình | Cosmos Transfer, điều khiển bằng depth và segmentation render từ MuJoCo | Video render của episode S1, S2 hoặc teleop; ảnh tham chiếu nhà máy | Cùng quỹ đạo, ngoại hình mới | Giữ nguyên |
| S4 · Video task mới | Cosmos Predict | Ảnh đầu cộng câu lệnh | Video, action suy ra bằng inverse dynamics | `pseudo`; chỉ khi RunPlan cho phép |

Quy tắc của design 23/10 mục 5.2 giữ nguyên: S1 → S2 → S3, S4 sau cùng; mỗi tầng có đơn giá và tỉ lệ sửa được riêng; không sinh bằng tham số của Level 1 hoặc Level 2. Mọi mẫu S1, S2 qua phát lại MuJoCo (mục 5.4). S3, S4 cần GPU lớn; chạy ở đâu phụ thuộc mục 9.

### 5.4 Phát lại action trên MuJoCo

Áp cho mọi nguồn có action robot: teleop bàn phím, dataset BTC, S1, S2, và action dự đoán của policy (mục 7.2). Video egocentric chỉ phát lại được sau khi chuyển sang robot.

| Chế độ | Cách chạy | Bắt được | Đầu ra |
|---|---|---|---|
| Động học | Đặt `qpos` theo state đã ghi, từng khung | Sai ánh xạ khớp, sai đơn vị, vượt giới hạn khớp, tự va chạm, ảnh lệch thời gian với state | Video ghép cạnh video gốc; danh sách khung lỗi |
| Động lực học | Từ state đầu, áp action đã ghi qua bộ điều khiển của sim | Action không tái tạo được state (sai tần số, sai delta hay tuyệt đối, sai dấu), thời điểm đóng mở gripper lệch, linh kiện không vào đồ gá | Sai lệch state theo thời gian, theo nhóm action; kết quả task khi phát lại |

Sai lệch ở chế độ động lực học là bình thường khi có tiếp xúc; ngưỡng hiệu chỉnh từ các episode thành công (phân vị 99), như các ngưỡng khác của spec mục 4.4. Episode trượt ở chế độ động học bị loại; trượt ở động lực học bị đánh dấu cho kỹ sư xem. Protocol `SimulatorAdapter.replay()` (03 mục 5.2) là chỗ cắm.

## 6. Training: dùng code của tác giả

### 6.1 Ba stage

| Stage | Code của tác giả | Đội thay gì | Dữ liệu |
|---|---|---|---|
| 1 · VLM | `pretrain-egodex-psi0-fast.sh`, `pretrain_egodex_qwen3vl_config`, `trainers/pretrain.py` | Khởi tạo từ `pre.*`; trỏ dữ liệu về output của mục 5.2; số bước, LR theo đo | Egocentric đã xử lý |
| 2 · Action expert | `posttrain-*-psi0.sh`, `posttrain_*_psi0_config`, `trainers/posttrain.py` | `action_layout` DENSO đệm 36 chiều, stats của release; S2-A (từ `postpre.*`), S2-B (khởi tạo lại) theo design 23/10 mục 6.2 | Teleop bàn phím, BTC, S1–S3 |
| 3 · Task | `finetune-*-psi0.sh`, `finetune_*_psi0_config`, `trainers/finetune.py` | Task khay → máy; cấu hình RTC | Release của từng nhánh |
| Baseline | `baselines/act`, `baselines/dp` | Cấu hình cho robot DENSO | Như stage 3 |

Code của tác giả được ghim commit trong RunPlan; adapter `TrainerAdapter` gọi script của họ, không sửa repo của họ. Khi tác giả cập nhật, đổi commit ghim là một `Decision`.

### 6.2 Lấy log bằng cách đọc code

Bước **đọc code** [Đã chốt] chạy mỗi khi đổi commit ghim: một script liệt kê mọi chỗ trainer gọi `log`, `accelerator.log`, `init_trackers`, `evaluate`, `save_checkpoint` và tên metric, so với bảng log cần có của design 23/10 mục 6.3, rồi ghi bảng "có sẵn / thiếu / cách lấy" vào `docs/g0/`. Kết quả đọc ngày 25/10/2026:

| Nhóm log | Có sẵn trong code tác giả | Cách lấy phần thiếu |
|---|---|---|
| Loss tổng, LR, epoch, eval loss | Có | Ghi thêm vào `metrics.jsonl` qua tracker riêng của `accelerate`, song song W&B offline |
| Chuẩn gradient | Có: `grad_norm_vlm`, theo nhóm, `grad_norm_act` | Như trên |
| Loss theo nhóm action, theo vị trí trong chunk | Không | Lớp bọc tính lại trên batch val từ output của model; không sửa code gốc |
| Phương sai action dự đoán, phân bố gripper | Không | Như trên |
| VRAM, thông lượng, GPU-giờ | Một phần | Đo từ adapter |
| Checkpoint trung gian chạy probe | Không | Adapter chạy P1–P4 sau mỗi lần lưu checkpoint |

Log của các checkpoint tác giả đã công bố vẫn không có; output stage của chúng lấy bằng probe (design 23/10 mục 6.1). Email gửi PSI Lab hỏi thêm link W&B của các run gốc.

### 6.3 Máy chạy

| Máy | Dùng cho |
|---|---|
| RTX 3060 12 GB | Dev, MuJoCo, teleop, phát lại, Agent QA/QC (Nemotron Q4), ACT và DP, thử inference Ψ₀ |
| Colab Pro (A100, H100, chạy qua CLI) | Train Ψ₀ stage 1–3 |

**Rủi ro ngân sách lớn nhất của tài liệu này.** Spec mục 9 tính khoảng 22 lần train Ψ₀ cho phạm vi mặc định, cộng stage 2 cho robot DENSO, cộng fine-tune stage 1. Script finetune của tác giả mặc định 8 GPU × batch 16 trong 40.000 bước; trên một GPU phải tích lũy gradient nên thời gian tăng nhiều lần. Gói Colab Pro tính theo compute unit mỗi tháng; theo bảng giá người viết biết (cần kiểm lại), gói Pro chỉ đủ khoảng vài chục giờ A100 mỗi tháng. S1-04 phải đo giờ một lần train trên một A100 hoặc H100 trước review G0; nếu tổng vượt ngân sách, chạy phần lớn vòng lặp trên ACT và DP (đã là thiết kế của F-ACT, spec mục 7.8), giữ Ψ₀ cho các nhánh cuối, và cân nhắc LoRA.

Colab có giới hạn thời gian phiên, nên mọi job train phải tiếp tục được từ checkpoint (code tác giả có `--train.resume_from_checkpoint=latest`), lưu checkpoint ra kho bền định kỳ, và ghi compute unit vào sổ chi phí. Inference Ψ₀ trên 3060 cần đo ở G0: VRAM và độ trễ so với chu kỳ điều khiển. Dữ liệu nào được lên Colab: mục 9.

## 7. Agent QA/QC

### 7.1 Vị trí trong quy trình

```text
job train / eval / infer ─► code tính số và dựng hình ─► Agent QA/QC (Nemotron) viết báo cáo ─► AI Engineer duyệt (fw review)
```

| Điểm | Quyết định |
|---|---|
| Model | Nemotron 3.5 Bolt E4B 4GB, chạy cục bộ trên 3060, ghim revision trên Hugging Face [Đã chốt model; ghim là Đề xuất] |
| Phạm vi | Chỉ đánh giá log train và output từng bước của train, eval, inference [Đã chốt] |
| Không được | Đọc `vault/`; tự chạy job; tự chọn dữ liệu; đưa số không có trong đầu vào |
| Số liệu | Mọi con số (CI, xu hướng loss, độ trễ p99, tỉ lệ sửa được, ước lượng lợi ích) do code tính; agent diễn giải, xếp hạng, viết đề xuất và trích dẫn số |
| Ước lượng | Mỗi ước lượng có khoảng và được lưu; khi có kết quả đo, so lại để biết agent đáng tin tới đâu (như cặp ước tính và thực đo của sổ chi phí) |
| Đầu ra | Báo cáo HTML tĩnh mỗi job: phát hiện, bằng chứng (đường dẫn hình và số), insight, ước lượng, đề xuất [Đề xuất]; kỹ sư ghi đồng ý hoặc ghi đè kèm lý do |
| Kiểm agent | Trước khi dùng: bộ ca mẫu có đáp án (log train bình thường, loss phân kỳ, chiều action chết, độ trễ vượt ngưỡng, chunk giật) để chấm agent; chạy lại khi đổi model hoặc prompt |

Nemotron chỉ đọc chữ, nên agent không nhìn ảnh hay video; nó đọc metadata, số và chú thích đi kèm hình do code dựng. Kiểm thị giác vẫn thuộc Cosmos Reason hoặc người.

### 7.2 Biểu diễn output từng stage cho người

| Stage | Code dựng gì | Agent đọc gì |
|---|---|---|
| 1 · VLM | Bảng ảnh: khung hình, câu hỏi, câu trả lời của VLM, đáp án; khung xương tay dự đoán vẽ chồng lên khung hình (`draw_utils` của Ψ₀) | Tỉ lệ đúng P1 theo loại câu hỏi, loss P2, độ tụt P4, các ca sai tiêu biểu |
| 2–3 · Action | Đồ thị action dự đoán so với thật theo nhóm và theo vị trí trong chunk; **video MuJoCo**: phát lại action dự đoán từ cùng state đầu, đặt cạnh phát lại action thật | Sai số theo nhóm, nhóm tệ nhất, vị trí trong chunk bắt đầu lệch, kết quả task khi phát lại |
| Inference (RTC) | Dòng thời gian: lúc gửi quan sát, độ trễ suy luận, lúc chunk về, số action đã tiêu trong lúc chờ (delay d), mức buffer, bước nhảy action ở ranh giới chunk, lúc buffer cạn | Độ trễ p50, p99 so với chu kỳ điều khiển; tần suất buffer cạn; độ lớn bước nhảy ở ranh giới so với trong chunk |
| Eval closed-loop | Tỉ lệ thành công theo mức, bước hỏng, video các lượt lỗi | Cụm lỗi, gợi ý liên kết tới evidence card của Failure → Data |

### 7.3 Bài toán bất đồng bộ

Ψ₀ cần khoảng 160 ms mỗi lần suy luận (số tác giả báo) và dùng real-time chunking: robot tiếp tục chạy action cũ trong lúc chờ chunk mới. Trong mô phỏng có thể chạy đồng bộ (dừng sim chờ policy), khi đó lỗi do trễ không bao giờ xuất hiện. Vì vậy closed-loop eval trên MuJoCo có hai chế độ [Đề xuất]:

- **Đồng bộ**: dùng để gỡ lỗi và để so với code tác giả.
- **Bất đồng bộ**: sim chạy theo đồng hồ thật hoặc chèn độ trễ đo được từ log inference (phân phối thật, không phải hằng số). Chỉ số chính của mọi nhánh lấy ở chế độ này.

Log inference ghi đủ trường để dựng dòng thời gian ở mục 7.2. Lỗi "bất đồng bộ" (độ trễ, buffer cạn, giật ở ranh giới chunk) đi vào kiểm hệ thống (spec mục 6.4, LỖI RUNTIME) trước khi coi là lỗi dữ liệu.

## 8. Thí nghiệm trên robot DENSO trong MuJoCo

- Giả thuyết HS, HT (HTa, HTb), HD, các nhánh A, A₀.₇, B, B-fail, C, quy tắc công bằng và thống kê giữ như spec mục 3 và 7, đổi môi trường sang task khay → máy trên MuJoCo.
- **Vector điều kiện** [Đề xuất]: tư thế linh kiện trong khay (x, y, yaw), vị trí khay, vị trí đồ gá của máy, độ lệch vị trí xuất phát của đế, ánh sáng, số vật gây nhiễu.
- **Ba mức đánh giá** [Đề xuất]: Level 0 trong miền; Level 1 thêm ánh sáng và vật liệu lạ; Level 2 thêm vị trí linh kiện và khay ngoài dải train. Định nghĩa và dải hạt giống chốt trước khi thu demo đầu tiên, để teleop không vô tình phủ điều kiện holdout.
- **Tiêu chí demo** [Đã chốt hướng, ngưỡng theo BTC]: ≥ 75% trên holdout gộp ba mức (Cấp 2); ≥ 70% riêng trên Level 1 và Level 2 (Cấp 3).
- **Giới hạn phải nêu**: kết quả không so được với số công bố trên SIMPLE; mốc tin cậy là phần tái tạo G0 trên SIMPLE và việc công bố môi trường, dataset cùng log.

## 9. Quy tắc dữ liệu và máy chạy

Bất biến kiến trúc: dữ liệu `restricted` hoặc `internal` (mọi dữ liệu DENSO) không được gửi tới dịch vụ hosted bên ngoài. Colab là máy của Google, nên **chưa được dùng cho dữ liệu DENSO** cho tới khi có quyết định [Option]:

| Phương án | Nội dung | Hệ quả |
|---|---|---|
| D-A | Xin DENSO và BTC cho phép bằng văn bản dùng Colab cho dataset BTC và video nhà máy | Train stage 1–3 trên Colab với mọi dữ liệu |
| D-B | Dữ liệu DENSO chỉ ở máy cục bộ; Colab chỉ nhận dữ liệu `public` và dữ liệu sim mà đội tự sinh từ mô hình không chứa thông số mật của DENSO | Train Ψ₀ trên dữ liệu DENSO cần GPU cục bộ đủ lớn; 3060 12 GB không đủ |

`data_class` của dữ liệu sim do đội sinh [Đề xuất]: `public` khi robot tương đương chỉ dùng thông số công khai hoặc hình vẽ đã được phép dùng; chuyển thành `internal` khi MJCF chứa thông số từ URDF/USD của DENSO. Mỗi release ghi `data_class` gộp theo mức chặt nhất.

## 10. Làm song song và quy trình

### 10.1 Không ai phải chờ ai

1. **Hợp đồng trước**: mỗi chỗ nối có schema trong `contracts` và một bản giả trong `flywheel-fakes`; hai thứ này merge trước mọi việc dùng chúng.
2. **File mẫu ngày đầu**, commit trong `packages/flywheel/tests/fixtures/` [Đề xuất]: một episode bundle, một dataset LeRobot v2.1 nhỏ, một MJCF robot tối thiểu, một `metrics.jsonl` sinh từ `FakeTrainer`, một log inference RTC giả, một đoạn egocentric định dạng EgoDex. Ai cũng code trên file mẫu; PR của người khác merge chậm không chặn ai.
3. **Không nhánh chồng nhánh**: nhánh luôn tạo từ `origin/master`; cần code chưa merge của người khác thì dùng bản giả.
4. **Ngày bàn giao cố định** cho từng chỗ nối, ghi trong file story.

### 10.2 Duyệt và merge

- Hiếu là người duyệt và merge duy nhất vào `master` [Đã chốt]. Ruleset "Only Hiếu merges into master" đã bật trên GitHub ngày 24/10/2026.
- Thay đổi cấu hình GitHub còn chờ Hiếu đồng ý: bật bắt buộc approval từ code owner (CODEOWNERS dòng `*` là Hiếu), và tắt `enforce_admins` để Hiếu merge được PR của chính mình.
- Tài liệu phải sửa: R2 ở 08 và RULE (người review dự phòng), cột "Review mặc định" ở 07 mục 2.1, RULE mục 4 bước 8.

### 10.3 Theo dõi

Đã bật ngày 25/10/2026 trên máy của Hiếu (Claude desktop, scheduled tasks, chỉ đọc, không đăng gì lên GitHub):

- `denso-tracking` lúc 10:00, 14:00, 18:00 mỗi ngày: chạy `scripts/daily_report.py`, `pr_guard.py`, liệt kê PR chờ Hiếu, ai bị chặn, vi phạm rule; ghi `~/denso-tracking/YYYY-MM-DD-HHMM.md`.
- `denso-cuoi-ngay` lúc 21:30: gộp thành chương trình thảo luận cuối ngày `~/denso-tracking/eod-YYYY-MM-DD.md`.

## 11. Chia việc và story

### 11.1 Story Sprint 1 hiện có

| Story | Hướng mới [Đề xuất] |
|---|---|
| S1-01 khung repo | Đã xong |
| S1-02 môi trường SIMPLE | Thu nhỏ: chỉ đủ cho S1-03 |
| S1-03 tái tạo Ψ₀ | Giữ (benchmark G0) |
| S1-04 chi phí fine-tune | Mở rộng: đo stage 2 và stage 3 trên Colab; đo inference trên 3060 |
| S1-05 planner SIMPLE | Bỏ; thay bằng planner MuJoCo trong DA-15 |
| S1-06 khôi phục trạng thái | Thu nhỏ: MuJoCo đặt state trực tiếp; còn phần tách hình ảnh khỏi vật lý |
| S1-07 phân tích psi-data | Đổi sang phân tích dataset BTC (DA-22) |
| S1-08 lõi trên adapter giả | Giữ |
| S1-09 tín hiệu từng bước | Đổi sang task khay → máy trên MuJoCo |
| S1-10 mô hình dữ liệu | Giữ |
| S1-11 bộ điều khiển V3 | Bỏ: teleop, planner và policy chạy cùng bộ điều khiển trên MuJoCo |

### 11.2 Story mới [Đề xuất]

Mã nối tiếp DA-14, không đổi mã đã dùng.

| Mã | Việc | Người | Phụ thuộc thật | Code trên bản giả trong lúc chờ |
|---|---|---|---|---|
| DA-15 | Robot DENSO tương đương (MJCF), cảnh trạm, task khay → máy, planner | Hưng | Không | |
| DA-16 | Teleop bàn phím, ghi episode | Hưng | DA-15 | MJCF tối thiểu |
| DA-17 | Phát lại action hai chế độ, video so sánh | Châu | DA-15 | MJCF tối thiểu, episode mẫu |
| DA-18 | Pipeline egocentric → định dạng EgoDex cho stage 1 | Long | DA-01 | Đoạn EgoDex mẫu |
| DA-19 | Đọc code tác giả, lớp bọc log cho 3 stage, adapter train trên Colab | Hiếu | Không | `FakeTrainer` |
| DA-20 | Agent QA/QC (Nemotron), dựng hình từng stage, bộ ca mẫu | Thông | DA-19 cho log thật | `metrics.jsonl` và log RTC giả |
| DA-21 | Export LeRobot v3 và checklist chuẩn hóa | Thông | DA-02 | Dataset v2.1 mẫu |
| DA-22 | Đọc và phân tích dataset BTC | Thông | Dataset từ BTC | |
| DA-23 | Closed-loop eval bất đồng bộ trên MuJoCo, log inference RTC | Châu | DA-15 | MJCF tối thiểu, policy giả |

Đường đi mới của package [Đề xuất]: `packages/flywheel-mujoco/` (Hưng; review Châu), `packages/flywheel-agentqa/` (Thông; review Long). Bảng giờ ước lượng làm khi viết file story; ghi chú: các story bỏ ở 11.1 bớt khoảng 60 giờ của Hưng và Châu (S1-05 6, S1-11 18, story 5.5 tuyến generator 36), chưa tính phần thu nhỏ.

## 12. Câu hỏi còn mở

| Mã | Câu hỏi | Ai trả lời | Ảnh hưởng |
|---|---|---|---|
| Q-A | Dataset của BTC gồm gì: robot nào, task nào, định dạng, số episode, có video egocentric không, giấy phép và quyền dùng | Hiếu hỏi BTC | Số demo cần thu bằng bàn phím; DA-22 |
| Q-B | Phương án D-A hay D-B cho Colab (mục 9) | Hiếu, DENSO, BTC | Train Ψ₀ trên dữ liệu DENSO ở đâu |
| Q-C | Máy 5090 mà 04 và S1-03 nhắc tới còn dùng được không | Hiếu | Cosmos Reason, S3 tự host, inference Ψ₀ |
| Q-D | Video egocentric thô của DENSO thu bằng thiết bị gì (E-A hay E-B) | DENSO qua BTC | Chất lượng pose cho stage 1 |
| Q-E | Bật code owner review và tắt `enforce_admins` (mục 10.2) | Hiếu | Hiếu là người duyệt duy nhất trên thực tế |
| Q-F | Ngân sách compute unit Colab mỗi tháng, và có mua thêm hoặc lên Pro+ không | Hiếu | Số lần train Ψ₀ làm được (mục 6.3) |
| Q-G | Chạy Colab qua CLI bằng công cụ nào | Hiếu | Cách viết adapter train trên Colab (DA-19) |

**Lựa chọn của người viết** (cần Hiếu xem khi duyệt): một camera đỉnh cột (mục 3); teleop điều khiển theo đầu tay qua IK (mục 4.1); stage 1 fine-tune theo mục tiêu token FAST, hỏi đáp chỉ để chấm (mục 5.2); eval chính ở chế độ bất đồng bộ (mục 7.3); `data_class` của dữ liệu sim (mục 9); file mẫu ngày đầu (mục 10.1); mã DA-15…DA-23 và người làm (mục 11.2).

## 13. Tài liệu bị thay và việc sửa sau khi duyệt

| Tài liệu | Sửa |
|---|---|
| Spec v10.2 → v10.3 | Mục 0, 2, 7, 9, 10: thí nghiệm chuyển sang DENSO trên MuJoCo; SIMPLE còn G0; bỏ V3, T1–T4 khỏi đường găng |
| Design 23/10 | Ghi chú ở đầu: mục 3 (simulator), 5.2, 5.3, 6.3 được thay một phần bởi tài liệu này |
| 03 · Kiến trúc 0.4 → 0.5 | Package `flywheel-mujoco`, `flywheel-agentqa`; chế độ eval bất đồng bộ; Agent QA/QC trong luồng một vòng |
| 04 · Kế hoạch | Story Sprint 1 theo mục 11; tải từng người |
| 07 · Chia việc | Sở hữu đường dẫn mới; DA-15…DA-23; cột review |
| 08 và RULE | R2 và quy trình review theo mục 10.2; lịch tracking |
| File story | Sửa S1-02, S1-04, S1-05, S1-06, S1-07, S1-09, S1-11; tạo DA-15…DA-23 |

## Nguồn

- Repo Psi0, nhánh `main`, đọc ngày 25/10/2026: <https://github.com/physical-superintelligence-lab/Psi0>
- Fork LeRobot của Ψ₀: <https://github.com/songlin/lerobot/tree/09929d8057b044b53aecaf5c6d7eb71f99e8beb9>
- Nemotron 3.5 Bolt E4B 4GB: <https://research.nvidia.com/labs/nemotron/Nemotron-3.5-Bolt-E4B-4GB/>
- Kết quả S1-03 về checkpoint công bố: `docs/g0/psi0-eval.md` trên nhánh `S1-03-psi0-repro`
