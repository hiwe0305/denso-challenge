# Pipeline egocentric: EgoDex qua sáu tầng, E-A so với E-B, vòng thử model gán nhãn

_Ngày 6/11/2026; sửa theo review PR 152 ngày 7/11/2026 (mục 3, 5, 6, 1.2, 10.5; các bước chạy lại trên laptop); thêm bước làm mờ ngày 8/11/2026 (nhiệm vụ 8, mục 3.1). Story [DA-04](../product/stories/DA-04-pipeline-egocentric.md), nhiệm vụ 1–8. Người làm: Claude (phiên DA-04) theo phân công của Hiếu; Hiếu duyệt. Mọi số trong file này là output của `fw egocentric` trên 20 episode EgoDex thật, trừ chỗ ghi là giả định. Dữ liệu và kết quả nằm trong `fwdata/` (không commit). Job E-A và lần cắt có RoboBrain chạy trên `rtx3060:~/denso-da04` trước 10:20 ngày 6/11/2026. Sau đó máy được giữ cho eval C, nên các bước còn lại chạy trên laptop, còn bước nào không chạy được thì để lại cách chạy ở mục 10._

## Kết luận

- Pipeline chạy hết sáu tầng trên 20 episode EgoDex thật: ingest, cổng che danh tính (EgoDex được miễn khi video khớp sha256 đã ghim), pose E-B, pose E-A, cắt đoạn kèm câu lệnh, QA, báo cáo. Sau các sửa theo review PR 152 (7/11/2026), QA cho **8 `pass`, 11 `flag`, 1 `reject`**. Ngày 6/11/2026 là 13, 7, 0; số đổi vì câu trả lời ở mép cửa sổ không còn được tính (mục 5) và có phép kiểm `segment_count` mới (mục 6).
- E-A chỉ từ RGB đặt đầu ngón lệch 43–51 px, điểm 3D lệch khoảng 7 cm so với tracking của Vision Pro. Tư thế camera của E-A chưa dùng được: sai số xoay (0,20° mỗi khung) lớn hơn chính chuyển động (0,12°), còn phần tịnh tiến chưa đo được.
- Luật để mở 13 trên 21 sự kiện gắp, thả. RoboBrain trả lời cả 13, nhưng 6 trên 13 câu trả lời là ảnh đầu tiên. Từ 7/11/2026, câu trả lời ở mép cửa sổ bị bỏ, nên 6 sự kiện vẫn mở và chờ người duyệt. **[Đề xuất]** chưa dùng ranh giới của model cho tới khi vòng thử đo xong sai số.
- **Vòng thử model gán nhãn (D3) chưa có kết quả và chưa có `Decision`.** Lần chạy dừng giữa chừng lúc 10:20 ngày 6/11/2026, vì Hiếu giữ `rtx3060` cho eval C của DA-34. Laptop không đủ bộ nhớ để chạy hai model. Cách chạy lại ở mục 10.
- Video đội tự quay dừng ở cổng che danh tính cho tới khi chạy `fw egocentric deid` (từ 8/11/2026, mục 3.1). Bước này che mặt trên laptop bằng YuNet của OpenCV, ghi bản sao `<i>.deid.mp4` cạnh video gốc, và mọi bước sau chỉ đọc bản sao. Thử trên một clip EgoDex có dán một khuôn mặt: mặt bị che ở cả 80 trên 80 khung có mặt, 0 khung báo nhầm trên clip không có người, và pipeline qua cổng tới tận `report`.

## 1. Cách chạy

Cài: `uv sync --extra egocentric` (h5py, OpenCV headless; commit `c11b88a6`). Gốc kho `FW_ROOT` (mặc định `./fwdata`). Cấu hình duy nhất là [`configs/data/egocentric.yaml`](../../configs/data/egocentric.yaml): tập con EgoDex, luật cắt đoạn, ngưỡng QA, tham số E-A, model và revision. `threshold_version` của mỗi `QAReport` là `version` cộng 12 ký tự đầu sha256 của file này.

```bash
fw egocentric ingest egodex                       # in ra thư mục làm việc $W
fw egocentric deid $W                             # video tự quay: che mặt trước mọi bước khác (mục 3.1)
fw egocentric pose $W                             # E-B từ HDF5
fw egocentric pose $W --job ea_jobs.json          # manifest cho job E-A
fw egocentric pose $W --estimates <thư mục .npz>  # đọc E-A, làm sạch (mục 4.1), so với E-B
fw egocentric annotate $W --endpoint http://127.0.0.1:11434/v1
fw egocentric qa $W
fw egocentric report $W
fw egocentric review $W --sample                  # rồi --apply <sheet đã điền>
fw egocentric trial $W --simple <psi-data hai bàn> --reference <điểm gắp đã đánh dấu> \
  --robobrain <url> --molmo <url> --vram robobrain=... --vram molmo=... \
  --timeout-s 1200 --boundary robobrain           # mục 10.3
fw egocentric ingest video --root <thư mục video tự quay>
```

Mỗi lệnh là một job có hai dòng `LedgerEntry` (ước tính, thực đo) dưới `$FW_ROOT/sites/local/runs/g0-DA-04-<ngày>/`. Ước tính là giả định số giây mỗi khung, ghi trong `note`. Lệnh bị từ chối (cổng che danh tính, file nguồn đổi sau ingest, cấu hình sai) trả mã 2 sau khi đã ghi dòng thực đo.

Thư mục làm việc giữ đúng bố cục mà DA-18 đọc (kế hoạch 6/11/2026 mục 4.2a): `source.json`, `episodes.jsonl`, `egocentric/<id>/bundle.json`, `pose.npz` (thêm `intrinsic` (3, 3) theo yêu cầu của DA-18 ngày 6/11/2026), `segments.parquet` (cột của `Segment` thêm `frame_start`, `frame_end`), `qa/egocentric.jsonl`. Thêm: `pose_ea.npz`, `labels.json`, `compare.json`, `report/`, `review/`, `trial/`. Test hợp đồng: `packages/flywheel-data/tests/contract/egocentric/test_ego_workdir_contract.py`.

### 1.1 Job E-A trên `rtx3060`

MediaPipe không vào `uv.lock` (D5). Job là một file độc lập, chạy trong venv riêng:

```bash
uv venv ~/denso-da04/venv-ea && uv pip install -p ~/denso-da04/venv-ea mediapipe==1.2.2 opencv-python-headless==5.0.0.93 numpy==2.2.6
nohup setsid systemd-run --user --scope -p MemoryMax=8G -p MemorySwapMax=0 \
  ~/denso-da04/venv-ea/bin/python estimate_job.py --manifest ea_jobs.json --root egodex \
  --out out-ea --model hand_landmarker.task > ea.log 2>&1 < /dev/null &
```

`hand_landmarker.task` là bản float16/1 của MediaPipe, sha256 `fbc2a30080c3c557093b5ddfc334698132eb341044ccee322ccf8bcf3607cde1`.

### 1.2 Model gán nhãn trên `rtx3060`

| Vai | Model | Phục vụ | Revision |
|---|---|---|---|
| Gợi ý ranh giới, viết câu | RoboBrain 2.5-4B (BAAI) | Ollama 0.32.14, `hf.co/mradermacher/RoboBrain2.5-4B-GGUF:Q4_K_M` | repo GGUF `4967565e14c9` |
| Chỉ điểm gắp | Molmo2-4B (AllenAI) | transformers 4.57.1, torch 2.15.0+cpu trên CPU, bf16, 16 luồng, server OpenAI tối giản `serve_molmo2.py` | `042abfa7a388` |

Endpoint chỉ được là máy của đội (review PR 152, 7/11/2026), vì khung hình là video có người. Điều kiện:

- scheme `http` hoặc `https`;
- host là `localhost`, IP loopback hoặc IP mạng riêng, hoặc một tên khai trong `models.local_hosts` của cấu hình (mặc định rỗng).

Client bỏ qua `HTTP(S)_PROXY` và từ chối chuyển hướng; endpoint khác thì lệnh trả mã 2. Cách kiểm theo client DA-20 của Hưng (commit `cbdfc295`).

Bản GGUF của Molmo2 (`mu2solutions`, `c21183cb41da`) không chạy được trên Ollama: lỗi "Failed to load CLIP model". GPU 12 GB còn bị server Ψ₀ của DA-34 giữ 7,2 GB, nên Molmo2 chạy CPU. Lane gọi cả hai qua endpoint OpenAI bằng `urllib`, ảnh JPEG cạnh dài 640 px; test dùng model giả.

## 2. Ingest (nhiệm vụ 1, câu Q-27H)

Tập con ghim **[Đề xuất]**: 10 task gắp và đặt có trong mẫu EgoDex của DA-30 (`fwdata/egodex-da30/part1`, lấy từ `test.zip`), mỗi task 2 episode có số thứ tự nhỏ nhất và đủ cả `.hdf5` lẫn `.mp4`. Task: `basic_pick_place`, `insert_remove_cups_from_rack`, `pick_place_food`, `pick_up_and_put_down_case_or_bag`, `put_in_take_out_glasses`, `stack_unstack_bowls`, `stack_unstack_cups`, `stack_unstack_plates`, `stock_unstock_fridge`, `vertical_pick_place`.

| Trường | Giá trị |
|---|---|
| `source_id` | `src_050b9bf56a4e843c` (sha256 của nguồn, giấy phép, `data_class` và sha256 từng file) |
| Episode, file | 20 episode, 40 file, 100,1 MB |
| Khung, thời lượng | 4.143 khung ở 30 Hz, 138,1 giây (2,3 phút) video |
| Giấy phép, `data_class` | `CC-BY-NC-ND-4.0` (câu Q-EGO-LIC vẫn mở), `public` |
| `Episode` | `source_kind = egocentric`, `action_quality = retargeted`, `deid_status = raw`, `embodiment_id = human_hands@egodex` |
| Job | ước tính 6,0 s (giả định 1 ms × 6.000 khung), thực đo 0,46 s; cả tiến trình 1,62 s, RSS 145 MB |

Câu Q-27H: 20 episode, 2,3 phút video. Đủ để đo thời gian chạy pipeline (mục 6) và cho một lần chạy stage 1 ngắn của DA-18; mở rộng tập con chỉ là sửa `tasks`, `episodes_per_task` trong cấu hình.

Chạy lại `ingest` vào một thư mục khác cho đúng `source_id` và đúng 40 sha256. Sửa một byte của một file HDF5 sau ingest thì `pose`, `annotate` và `qa` từ chối với mã 2 (test `test_a_changed_source_file_is_refused` kiểm `annotate`). `EpisodeMetadata.source_detail` để `None`, vì Literal của hợp đồng chưa có `egodex`, `ego_video` (mục 9).

## 3. Che danh tính (nhiệm vụ 2, quyết định D2)

**[Đã chốt]** (Hiếu, 6/11/2026): chưa làm bước làm mờ. Chỉ mẫu EgoDex công bố (`egodex`, `public`) được miễn, mở rộng quyết định "Waive for EgoDex" của DA-30. Episode EgoDex giữ `deid_status = raw`, qua cổng Annotate, và `source.json` ghi lý do miễn. Mọi nguồn khác, trước hết là video đội tự quay, bị `deid_blocks_annotate` chặn trước job E-A, trước Annotate và trước vòng thử. Danh sách miễn nằm trong code (`annotate/deid/gate.py`), không trong cấu hình, để một lần chạy không tự nới quyết định của PO.

**Miễn theo file, không theo nhãn** (review PR 152, 7/11/2026). Nhãn (`egodex`, `public`) đến từ lệnh `ingest egodex` và thư mục gốc trong cấu hình, nên trỏ gốc vào thư mục có video tự quay cạnh file HDF5 của EgoDex cũng mang đủ nhãn. Vì vậy cổng chỉ miễn khi **mọi video** của nguồn có tên và sha256 nằm trong `annotate/deid/egodex_pin.json`. Ngoài ra:

- `source.json` có thêm trường `deid_waiver_manifest`: id của pin đã dùng để kiểm, hoặc `null` khi không được miễn.
- Cổng kiểm lại sha256 ở mỗi bước; `check_unchanged` buộc các sha256 đó vào file trên đĩa.

| Pin | Giá trị |
|---|---|
| Id | `egodex-test-da30-part1@4b4ad209ee99` (tên, cộng 12 ký tự đầu sha256 của file pin) |
| Nội dung | 218 mp4 của mẫu DA-30, `{"<task>/<i>.mp4": sha256}`, 22 KB |
| Cách dựng | `python -m flywheel.data.annotate.deid.pin fwdata/egodex-da30 <pin>`: kiểm kích thước và CRC-32 của từng video với `manifest.json` của DA-30 (lấy từ thư mục của `test.zip` của Apple), rồi mới tính sha256; 3,0 s |
| Vì sao chỉ ghim video | Manifest của DA-30 không có sha256, chỉ có tên, kích thước, CRC-32. Cả 218 HDF5 của DA-30 đã khác zip, vì bước H-RDT thêm `actions_48d`; cả 218 mp4 đều khớp (kiểm 7/11/2026). Che danh tính là việc của hình ảnh; HDF5 không chứa ảnh |

Kiểm trên laptop ngày 7/11/2026:

- 20 episode của tập con được miễn, cùng `source_id`.
- Thư mục gốc có HDF5 thật và một mp4 bị thay: không được miễn ("1 videos not in the pinned sample"); `pose --job` và `annotate` trả mã 2.
- Sửa tay `source.json` để ghi lý do miễn: `annotate` vẫn trả mã 2 và nêu tên video lạ.

Câu Q-27I phần che danh tính: từ 8/11/2026 trả lời bằng YuNet (mục 3.1).

### 3.1 Bước làm mờ (nhiệm vụ 8, 8/11/2026)

Hiếu quay video task hai bàn ngày 8/11/2026 và cần dùng ngay, nên bước làm mờ không chờ tới sau 13/11/2026 như dòng 4 của mục 9 cũ. `fw egocentric deid <thư mục làm việc>` chạy ngay sau `ingest`, trước mọi bước đọc khung hình:

1. Kiểm sha256 của video gốc với `source.json` (`check_unchanged`). Nguồn được miễn theo D2 thì không làm gì.
2. Mỗi video giải mã hai lượt. Lượt 1 dò mặt trên khung thu về cạnh dài 960 px, nới mỗi hộp thêm 25 % mỗi phía. Lượt 2 che mỗi hộp bằng khảm 8 ô theo cạnh dài, làm mịn, trên chính khung đó và 5 khung trước, 5 khung sau (detector hay sót một hai khung khi mặt quay hoặc nhòe).
3. Ghi `<task>/<i>.deid.mp4` cạnh video gốc, mp4v, cùng fps và kích thước, ghi trọn hoặc không ghi (file tạm, đổi tên khi xong). OpenCV không ghi tiếng, nên giọng nói cũng mất. Số khung phải bằng lượt 1; kích thước sau khi OpenCV xoay theo thẻ xoay phải bằng `width`, `height` của `device.json`, sai thì từ chối.
4. Chỉ khi mọi video đã ghi xong mới ghi bản ghi, theo thứ tự: `bundle.json` trỏ `mp4` sang bản sao, `source.json` thêm `deid_copies` (bản sao → sha256) và `deid_method` (model, revision, sha256 model, tham số, số khung có mặt, số khung bị che, thời gian của từng video), rồi `episodes.jsonl` đổi `deid_status` sang `blurred`. Dừng giữa chừng thì episode vẫn bị cổng chặn.
5. Một job, hai dòng `LedgerEntry`; ước tính là giả định 0,05 s mỗi khung.

| Model | Giá trị |
|---|---|
| Tên | YuNet `face_detection_yunet_2023mar` (OpenCV Zoo, giấy phép MIT), ONNX 227 KB |
| Chạy | `cv2.FaceDetectorYN` của OpenCV 5.0 trên CPU. OpenCV đã có trong extra `egocentric`, nên `uv.lock` không đổi (giống MediaPipe ở D5) |
| Revision | commit `f12e12798e83` của `opencv/opencv_zoo`, commit cuối sửa file này |
| sha256 | `8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4`; file khác sha256 thì lệnh từ chối |
| Nơi để | `$FW_ROOT/models/yunet/face_detection_yunet_2023mar.onnx`, ngoài git; thiếu file thì lệnh in câu `curl` để tải |
| Tham số (`deid` trong cấu hình) | `score_threshold` 0,6 (mặc định của YuNet là 0,9; hạ để sót ít mặt hơn), `nms_threshold` 0,3, `detect_side_px` 960, `pad` 0,25, `hold_frames` 5, `mosaic_cells` 8. Trừ `nms_threshold`, các số đều là giả định |

Bước làm mờ chạy cục bộ, nên khung gốc chưa che không rời máy. Dữ liệu `internal` không tới API hosted nào (CLAUDE.md); video tự quay là `public` từ 9/11/2026 (mục 8.1), nhưng chỉ bản sao đã che đi tiếp.

**Cổng kiểm bản sao, không kiểm nhãn.** `episodes.jsonl` là file văn bản, nên `deid_status = blurred` một mình không đủ: trước đây cổng cho episode `blurred` qua ngay. Từ 8/11/2026, episode egocentric không ở `raw` chỉ qua khi **mọi** video của nguồn có bản sao trong `deid_copies`, và sha256 của bản sao trên đĩa (băm lại ở mỗi bước) đúng bằng số `deid` đã ghi. Episode `raw` vẫn chỉ qua bằng miễn D2 theo pin, như cũ. `api.video_of` từ chối mọi `bundle.mp4` không phải bản sao của một nguồn cần làm mờ, nên manifest E-A, `annotate` và `trial` không đọc được video gốc. `ingest` lại thì mất `deid_copies`, episode về `raw`, phải chạy `deid` lại. Test: `tests/unit/egocentric/test_ego_blur.py`, `test_ego_deid.py`.

**Chạy thử trên laptop, 8/11/2026.** Thư mục giả làm video tự quay (`fwdata/egocentric-deid-e2e/`, không commit). Có hai video 1920 × 1080, mỗi video 126 khung: `two_table/0.mp4` là `basic_pick_place/0.mp4` của EgoDex, giữ nguyên. `two_table/1.mp4` là cùng video đó, có dán một khuôn mặt thật ở góc phải trên, từ khung 20 tới 99. Ảnh mặt là `astronaut.png` của scikit-image, ảnh NASA thuộc phạm vi công cộng. Log: `run.log`.

| Bước | Kết quả |
|---|---|
| `ingest video` | `src_fa9bcf457f85ccaf`, 2 episode, 3 file, 5,3 MB, không miễn |
| `pose --job` trước `deid` | mã 2 ở cổng: "it is not waived … until `fw egocentric deid` blurs it" |
| `deid` | 2 video, 252 khung, 11,0 s (ước tính 12,6 s, ledger thực đo 9,98 s), RSS 315 MB. Video 1: mặt tìm thấy ở 80 trên 80 khung có dán mặt, 90 khung bị che (80 cộng 5 mỗi phía). Video 0: 0 khung có mặt, tay không bị che |
| `pose --job` | manifest trỏ tới `two_table/0.deid.mp4`, `two_table/1.deid.mp4` |
| Job E-A (MediaPipe, venv riêng trên laptop, mục 1.1) | 18,8 s, RSS 526 MB. Tay phải NaN ở 84 trên 126 khung của bản sao; trên video gốc, E-A chạy ở `rtx3060` ngày 6/11/2026 cho 82 trên 126. Mã hóa lại làm mất khoảng 2 khung |
| `pose --estimates`, `annotate`, `qa` | 4 đoạn, 2 sự kiện để mở; QA 0 `pass`, 2 `flag` (`hand_pose_nan`, `segment_ambiguous`), `deid_gate` qua ở cả hai |
| `report` | trang có dòng "De-identified: 2 videos copied with their faces covered by opencv_zoo/face_detection_yunet_2023mar" |
| Xuất stage 1 của DA-18 | từ chối vì pose tay không hữu hạn ("4 not finite"), không phải vì cổng che danh tính |

Ảnh khung 50 trước và sau: mặt thành một khối màu mịn; hộp YuNet ôm sát mặt nên còn thấy phần tóc phía trên.

**Chạy trên video quay hôm nay** (máy có OpenCV, ví dụ laptop):

```bash
export FW_ROOT=<gốc kho>
mkdir -p $FW_ROOT/models/yunet && curl -L -o $FW_ROOT/models/yunet/face_detection_yunet_2023mar.onnx \
  https://github.com/opencv/opencv_zoo/raw/f12e12798e8314f7c074a6656816c048dcc95b7a/models/face_detection_yunet/face_detection_yunet_2023mar.onnx
fw egocentric ingest video --root <thư mục: device.json + two_table/<i>.mp4>   # in ra $W
fw egocentric deid $W
fw egocentric pose $W --job ea_jobs.json        # rồi job E-A (mục 1.1) với --root là thư mục video
fw egocentric pose $W --estimates <thư mục .npz>
fw egocentric annotate $W && fw egocentric qa $W && fw egocentric report $W
```

`width`, `height` trong `device.json` là kích thước khung **sau khi xoay**: quay dọc thì cao lớn hơn rộng. Sai thì `deid` từ chối và nêu kích thước đúng.

Chưa làm: che thẻ tên, màn hình, giấy tờ (AC 2 có nêu), và chưa có người duyệt mẫu để đặt `verified` (mục 9).

## 4. Pose (nhiệm vụ 4, 5)

**E-B** (nhiệm vụ 4) đọc thẳng tracking của Vision Pro trong HDF5: camera, hai cổ tay (T, 4, 4), năm đầu ngón mỗi tay (T, 5, 3), khung thế giới ARKit. Độ tin mỗi tay là trung bình độ tin của cổ tay và năm đầu ngón. 11 trong 218 file của mẫu DA-30 không có nhóm `confidences`; khi đó độ tin là NaN (không ghi), không phải 0, và QA gắn `flag`. Khung camera sau `inv(camera) @ p` theo quy ước OpenCV (x phải, y xuống, z trước), đã kiểm bằng cách chiếu cổ tay lên khung hình.

**E-A** (nhiệm vụ 5, câu Q-27I phần pose, **[Đã chốt]** D5): chỉ dùng RGB, `action_quality = pseudo`.

- Tay: MediaPipe Tasks HandLandmarker (21 điểm mỗi tay). Điểm 3D trong khung camera có được bằng bình phương tối thiểu: tịnh tiến các điểm "world" (mét, gốc ở tay) sao cho chiếu khớp với điểm ảnh.
- Camera: odometry thị giác OpenCV, ORB 1.500 điểm, che vùng tay. Nếu homography giải thích được ít nhất 80% inlier của essential matrix thì coi bước đó chỉ xoay; ngược lại lấy `recoverPose`, mỗi bước di chuyển giả định 5 mm (VO một camera không biết tỉ lệ).
- Bên tay lấy theo vị trí trong ảnh, không theo nhãn của MediaPipe. Trên góc nhìn EgoDex nhãn trái phải của MediaPipe sai theo cả hai chiều: lần chạy đầu (giữ nhãn) gán tay phải của E-B cho tay trái E-A ở `ep_bd159d0c`, đảo nhãn thì sai ở `ep_1618e7be`.

Job chạy CPU trên `rtx3060`, ảnh thu về cạnh dài 960 px: 20 episode, 4.143 khung trong 553,9 s, khoảng 7,5 khung/s.

So E-A với E-B trên cùng khung (`compare.json`), trung vị theo episode rồi trung vị qua 20 episode. Pixel là của ảnh 1920 × 1080.

| Đại lượng | Tay trái | Tay phải |
|---|---|---|
| Tỉ lệ khung E-A thấy tay, trong các khung E-B thấy tay trong ảnh | 67% | 96% |
| Sai số chiếu đầu ngón | 43 px | 51 px |
| Sai số chiếu cổ tay | 63 px | 115 px |
| Sai số điểm 3D | 7,2 cm | 6,8 cm |
| Sai số độ sâu | 6,3 cm | 4,9 cm |

| Camera | Giá trị |
|---|---|
| Sai số xoay mỗi khung, trung vị | 0,20° (p90 1,07°) |
| Chuyển động xoay thật mỗi khung của E-B, trung vị | 0,12° |
| Hướng tịnh tiến | Không đo được: VO coi 164/4.143 khung là có tịnh tiến, chỉ 1 trong số đó trùng bước E-B dịch ít nhất 2 mm |

Đọc số: đầu ngón lệch khoảng 2,5% bề ngang ảnh, độ sâu lệch 5–6 cm. Cổ tay lệch nhiều hơn đầu ngón, nhiều khả năng vì điểm cổ tay của MediaPipe (nếp cổ tay) và khớp cổ tay của ARKit không cùng định nghĩa; chưa kiểm. Trên EgoDex người ngồi trước bàn nên camera gần như chỉ xoay; sai số xoay của VO lớn hơn chính chuyển động, tức tư thế camera E-A chưa dùng được để tính action trong khung thế giới. Video hai bàn có đi bộ sẽ là phép thử thật của phần tịnh tiến.

### 4.1 Làm sạch E-A (nhiệm vụ 10, 9/11/2026)

Lý do: bản xuất thử `egx_fb3d1401dac0bd4c` của 132 clip khay có 41,6 % giá trị action bị cắt ở ±1 khi chuẩn hóa bằng stats EgoDex (`loader_check`, [docs/he/stage1.md](../he/stage1.md) mục 2.7 ở PR 171; EgoDex 2,2 %). Phép đo ngoài repo ở mục 2.8 cho thấy chỉ tổ hợp "camera đơn vị + làm sạch tay, cửa sổ 21" xuống dưới 5 %. Hiếu giao làm trong DA-04 ngày 9/11/2026.

Làm ở bước `fw egocentric pose --estimates` trên laptop (`ingest/egocentric/clean.py`, tham số `pose_ea.clean` của cấu hình), nên không cần chạy lại job E-A trên `rtx3060`. E-B không bao giờ bị làm sạch: với EgoDex chỉ `pose_ea.npz` đổi, `pose.npz` và `bundle.json` giữ nguyên; `compare.json` vẫn so ước lượng thô, và thêm khóa `pose_ea` ghi hệ tọa độ và báo cáo làm sạch của `pose_ea.npz` (như `pose_cleaning` của `bundle.json` với episode chỉ có E-A), vì `trial.py` đọc file đó. Không bỏ hay thêm khung nào; khung không thấy tay vẫn là NaN.

| Bước | Làm gì | Tham số (giả định, từ mục 2.8) |
|---|---|---|
| Hệ tọa độ | Tay ở trong hệ camera của từng khung, `camera` là ma trận đơn vị. Quỹ đạo VO không phải số đo: tịnh tiến là bước cố định `vo_step_m` (0,005 m) mỗi khung "di chuyển", quay trôi. `bundle.json` ghi `pose_frame = camera` và `pose_cleaning` (tham số, số khung đã sửa) | `frame: camera` |
| Liên tục góc | Khung cổ tay xoay π quanh một trục của nó khi việc đó làm nó gần khung thấy trước đó hơn 30°, nối qua khung không thấy tay | `flip_deg: 30` |
| Dấu của cả track | Sau bước trên, hai phiếu trên các khung thấy tay: bốn đầu ngón ở đúng phía lòng bàn tay (+z của khung cổ tay với tay phải, −z với tay trái) và đầu ngón theo +y từ cổ tay. Cả track xoay π quanh đúng một trục x, y hoặc z để thỏa cả hai phiếu; `pose_cleaning` ghi `track_turn`. Xoay cả track không đổi delta nào | |
| Khung nhảy | Bước giữa hai khung (tịnh tiến cổ tay, quay cổ tay, hoặc bước trung bình của đầu ngón) trên trung vị + 5 × MAD (nhân 1,4826) của clip cắt mỗi đoạn thấy tay thành mảnh. Mảnh dài tối đa 4 khung mà không phải mảnh dài nhất của đoạn là khung xấu, kể cả mảnh ở đầu hay cuối đoạn; cả mảnh được nội suy từ hai khung tốt gần nhất: vị trí, đầu ngón tuyến tính, quay bằng slerp; ở mép đoạn giữ khung tốt gần nhất. Một bước lớn đơn lẻ giữa hai mảnh dài (chuyển động nhanh thật) không đánh dấu khung nào | `jump_mad: 5.0`, `jump_burst: 4` |
| Làm mượt | Savitzky–Golay trên từng đoạn thấy tay: vị trí cổ tay, đầu ngón, quaternion cổ tay (giữ dấu liên tục, chuẩn hóa lại). Đoạn ngắn hơn cửa sổ dùng cửa sổ lẻ dài nhất nó chứa. Viết bằng numpy (scipy không là phụ thuộc của `flywheel-data`); test so khớp `scipy.signal.savgol_filter(mode="interp")` tới 1e-12 | `savgol_window: 21`, `savgol_order: 2` |

**Dấu trục cổ tay.** Đề xuất ở mục 2.8 là sửa dấu ngay khi dựng trục. `estimate_job.wrist_frame` đã có dấu cố định theo landmark: x từ khớp gốc ngón út tới ngón trỏ, z = x × y. Trên 153 file E-A của clip khay (trong hệ camera), 1 052 trên 21 474 bước giữa hai khung thấy tay (4,9 %) là lật π, 856 quanh y, 87 % kèm đổi chirality của bộ điểm: MediaPipe trả về tay phản chiếu. Ép mỗi khung theo chirality của bên tay cho 6,4 % bước lật (dùng bốn đầu ngón; 6,7 % với ngón cái, 6,9 % với khớp giữa ngón), tức tệ hơn. Vì vậy chirality chỉ dùng để bỏ phiếu cho cả track, còn bước giữ liên tục làm việc theo từng khung.

Chạy trên 153 clip khay (`src_805804635f9af7f7`, 9/11/2026, 4 s), lần hai sau review của PR 174 (phép thử khung nhảy theo mảnh, dấu track theo hai phiếu). Bản lưu trước lần một: `fwdata/pipeline/backup/src_805804635f9af7f7-before-DA-04-10-20261109.tar`; trước lần hai: `...-before-DA-04-10-review-20261109.tar` cùng thư mục.

| Đại lượng | Tay trái | Tay phải |
|---|---|---|
| Khung thấy tay | 10 960 | 11 324 |
| Khung bị xoay π (gồm cả các khung theo sau một lần lật) | 4 095 | 4 201 |
| Track xoay cả (quanh y / x / z) | 66 / 153 (53 / 11 / 2) | 56 / 153 (40 / 14 / 2) |
| Khung nhảy được nội suy | 673 | 1 012 |
| Đoạn thấy tay được làm mượt | 290 | 294 |

- Mẫu NaN không đổi ở 612 / 612 mảng; `segments.parquet` không đổi byte nào; 132 đoạn vẫn trùng đoạn pose hữu hạn dài nhất, nên không cần áp lại phiếu duyệt.
- QA, chạy bằng mã của nhánh này gộp tạm với PR 173 ở `d592a5bd` (chưa merge; không có PR 173 thì `segment_count` từ chối cả 153): **10 `pass`, 122 `flag`, 21 `reject`**, `threshold_version` `ego-1@024bb1b5a624` (cấu hình gộp của hai PR). `camera_jitter_deg_s` không còn hỏng vì camera là đơn vị; `flag` còn lại do `hand_pose_nan` (143).
- Xuất stage 1 (`--include-flag`): **`egx_7b43c30dc5d88cd7`**, 132 mẫu, 7 804 khung, 47 MB, ở `fwdata/egocentric-export/tray-ego-b-480p-clean2`. `export_source verify` của PR 171 (`6226664d`): `OK`. Bản của lần một, `egx_b6e974e46e8222e8` ở `tray-ego-b-480p-clean`, được giữ để so, không dùng để ghim.

Phần action bị cắt, đo bằng đúng script của mục 2.8 (dựng lại delta như loader ở `cda3fdf`, stats `egodex_stat_all.json`, mỗi clip trọng số bằng nhau):

| Bản xuất | Giá trị bị cắt | Mẫu có chiều bị cắt | \|Δ\| cổ tay trái x, trung vị / p90 (m) | \|Δ\| roll trái, trung vị / p90 (rad) |
|---|---|---|---|---|
| Thử `egx_fb3d1401dac0bd4c` | 42,7 % | 92,5 % | 0,027 / 0,215 | 0,287 / 2,12 |
| Lần một `egx_b6e974e46e8222e8` | 3,8 % | 56,5 % | 0,005 / 0,013 | 0,077 / 0,289 |
| Sau review `egx_7b43c30dc5d88cd7` | **3,3 %** | 54,4 % | 0,005 / 0,013 | 0,074 / 0,266 |

Theo nhóm chiều, gộp mọi delta (lần một → sau review): vị trí cổ tay 5,4 → 4,8 %, góc cổ tay 13,6 → 11,6 %, đầu ngón x/y 1,0 → 0,9 %, đầu ngón z 2,7 → 2,2 %. `stats_coverage` của lần một: tỉ lệ độ rộng khoảng q01–q99 so với của tác giả có trung vị 1,06, lớn nhất 4,6 (chiều 4, pitch cổ tay trái); bản thử là 11,9 và 26,0. Đo lại bằng một script gộp mọi delta (không cùng cách tính nên số khác một chút): lần một trung vị 0,98, lớn nhất 4,5; sau review 0,86 và 4,4, vẫn ở chiều 4. Bản mới qua ngưỡng 5 % đề xuất ở mục 2.7. **Chưa chạy `loader_check` trong image Ψ₀** (cần Docker trên `rtx3060`); trên bản thử, script này lệch `loader_check` 1,1 điểm (42,7 % so với 41,6 %). Vẫn nhiễu hơn EgoDex: 54,4 % mẫu có ít nhất một chiều bị cắt (EgoDex 19,5 %).

Còn lại, ghi lại chứ không sửa: đầu ngón không xoay theo cổ tay, nên 14,9 % khung thấy tay có đầu ngón ở sai phía của khung cổ tay đã làm sạch (33 % số khung bị xoay, 8 % các khung khác; trung vị 2,6 cm khỏi mặt phẳng lòng bàn tay). Thử phản chiếu các đầu ngón đó theo chiều sâu quanh cổ tay làm phần bị cắt tăng từ 3,5 % lên 4,0 %, nên không làm (docstring của `clean.py`).

Hệ quả cần biết (mục 9, dòng 19–20):

- Delta là chuyển động tay so với đầu, không bù chuyển động đầu. Trên EgoDex, bỏ phần bù gần như không đổi phần bị cắt (mục 2.8).
- `camera_jitter_deg_s` bằng 0 với E-A trong hệ camera: phép kiểm chỉ còn nghĩa với E-B.
- Luật cắt đoạn `two_table` tìm bước `walk` từ tốc độ camera; với camera đơn vị, cắt lại sẽ không thấy bước đó. Clip khay dùng phiếu duyệt cả clip nên không bị ảnh hưởng; quỹ đạo VO thô vẫn ở file `.npz` của job.
- `trial.py` đọc `pose_ea.npz` của EgoDex: chạy lại vòng thử (mục 10.3) sẽ dùng E-A đã làm sạch trong hệ camera.

## 5. Cắt đoạn và câu lệnh (nhiệm vụ 3)

Luật trước, model khi luật mơ hồ, người duyệt mẫu (**[Đã chốt]** D6). Tham số trong mục `segment` của cấu hình; mọi ngưỡng là giả định đọc từ 20 episode.

1. Tay chính là tay có cổ tay đi xa nhất, tối thiểu 0,2 m; cả hai tay đều qua ngưỡng thì ghi `two_hands`.
2. Điểm dừng là đoạn tốc độ cổ tay (trung bình trượt 5 khung) dưới 0,12 m/s, dài ít nhất 3 khung, trừ đoạn dừng ở đầu và cuối video.
3. Khoảng thumb–index đóng lại qua một điểm dừng là gắp, mở ra là thả. Các điểm dừng liền nhau cùng loại gộp thành một, giữ điểm có thay đổi lớn nhất; lần thả đứng trước mọi lần gắp bị bỏ.
4. Lý do mơ hồ: `low_confidence` (độ tin trung bình dưới 0,3), `close_to_previous` (cách sự kiện trước dưới 6 khung), `two_hands`, `aperture_flat` (khoảng đổi dưới 1 cm), `no_dwell` (không thấy điểm dừng, dùng điểm dừng dài nhất làm gắp tạm).
5. Sự kiện mơ hồ gửi RoboBrain 8 khung trong cửa sổ ±30 khung và hỏi khung nào tay bắt đầu nắm (hoặc buông). Câu trả lời đọc được thì thay khung của luật và ghi `source = model`. Riêng câu trả lời là khung đầu hoặc khung cuối được cho xem thì không tính (review PR 152, 7/11/2026): sự kiện giữ khung của luật, câu trả lời lưu ở `model_frame` với lý do `model_at_edge`, và sự kiện vẫn mở.
6. EgoDex cắt thành `pick`, `place` theo sự kiện; đoạn sau lần thả cuối gộp vào `place`. Video hai bàn cắt thành 6 bước của design: tiếp cận, gắp, đi, tới, đặt, thả; bước đi là đoạn camera di chuyển trên 30% tốc độ đỉnh của nó.
7. Mỗi đoạn có một câu lệnh: RoboBrain viết từ các khung của đoạn (`label_source = model`), không thì dùng mẫu câu trong cấu hình (`rule`). `fw egocentric review --sample` lấy 20% số đoạn theo seed 7; người điền `accept`, `fix` hoặc `reject`, `--apply` ghi lại với `label_source = human`. Mỗi dòng của phiếu chỉ đoạn bằng `match` (`step_id`, `frame_start`, `frame_end` lúc lấy mẫu), không bằng vị trí. Các trường hợp sau làm cả phiếu bị từ chối trước khi ghi file nào: đoạn đã bị bỏ, sửa hay cắt lại; episode không có trong `episodes.jsonl`; một đoạn duyệt hai lần; đoạn chồng nhau.

Kết quả trên 20 episode:

| Lần chạy | Đoạn | Sự kiện luật để mở | Câu lệnh | Thời gian job |
|---|---|---|---|---|
| Chỉ luật | 41 (22 `pick`, 19 `place`) | 13 trên 21 | mẫu câu (`rule`) | 1,26 s |
| Luật + RoboBrain, 6/11/2026 | 38 (20 `pick`, 18 `place`) | 0 (model trả lời cả 13) | 38 câu do model viết | 1.125,5 s (ước tính 20,7 s) |
| Luật + câu trả lời của RoboBrain phát lại, bỏ câu ở mép, 7/11/2026 | 39 | 6 (bỏ 6 câu ở mép) | 27 câu của model, 12 mẫu câu | 22,2 s trên laptop |

Lý do mơ hồ của 13 sự kiện: `aperture_flat` 11, `two_hands` 6, `low_confidence` 1 (một sự kiện có thể có nhiều lý do). Câu RoboBrain viết đọc hợp lý và gọi đúng vật, ví dụ "Pick up the green grapes from the plate.", "Place the sunglasses into the black case."; chưa có người chấm.

Ranh giới RoboBrain đề xuất đáng ngờ: 6 trong 13 câu trả lời là ảnh đầu tiên được cho xem. Ở `ep_603d1475` model chọn khung 0, nên episode chỉ còn một đoạn `pick` (0–81, `model`) mà QA vẫn cho `pass`. Nhiều khả năng đây là thiên lệch vị trí của model, không phải ranh giới thật. Vòng thử ở mục 7 là để đo sai số ranh giới trên khung có đáp án, nhưng chưa chạy xong.

Lần chạy lại ngày 7/11/2026 dùng lại đúng câu trả lời RoboBrain đã cho ngày 6/11/2026, vì `rtx3060` đang giữ cho eval C:

- Khung ranh giới lấy từ `labels.json` cũ: cùng câu lệnh, cùng loại sự kiện, nằm trong các khung được cho xem.
- Câu lệnh lấy từ `segments.parquet` cũ khi đoạn cho xem đúng các ảnh cũ (so sha256 của JPEG); đoạn đổi thì dùng mẫu câu.
- Kịch bản `~/.cache/denso-da04-check/replay.py` gọi thẳng `api.annotate`, nên không có dòng ledger.

Kết quả: 13 câu trả lời phát lại đủ, 6 câu ở mép bị bỏ. `ep_603d1475` thành `pick` 0–12 và `place` 12–81 (`rule`), và bị QA gắn `flag` (`segment_ambiguous`).

## 6. QA và báo cáo (nhiệm vụ 6)

Mỗi episode một `QAReport` của hợp đồng (`qa/egocentric.jsonl`), ngưỡng trong mục `qa` của cấu hình, `threshold_version = ego-1@2b0b593722be` (7/11/2026; ngày 6/11/2026 là `ego-1@f52e55c158ab`). Episode egocentric không có action robot hay bản phát lại, nên QA của nó có phép kiểm riêng:

| Phép kiểm | Giá trị | Ngưỡng | Hỏng thì | Qua | Hỏng | Trung vị |
|---|---|---|---|---|---|---|
| `deid_gate` | 1 khi cổng chặn | 0 | `reject` | 20 | 0 | 0 |
| `min_frames` | số khung của pose | ≥ 30 | `reject` | 20 | 0 | 179 |
| `video_frames` | lệch số khung mp4 và pose | 0 | `reject` | 20 | 0 | 0 |
| `pose_finite` | tỉ lệ khung camera không hữu hạn | 0 | `reject` | 20 | 0 | 0 |
| `hand_pose_nan` (D1, 7/11/2026) | số khung có tay NaN; lý do ghi số khung NaN theo từng tay | 0 | `flag`; `reject` khi không khung nào có tay hữu hạn | 20 | 0 | 0 |
| `pose_low_confidence` | tỉ lệ khung không tay nào đạt độ tin 0,3; nguồn không ghi độ tin thì `flag` | 0,5 | `flag` | 16 | 4 | 0 |
| `hand_out_of_frame` | tỉ lệ khung không cổ tay nào chiếu vào ảnh | 0,3 | `flag` | 17 | 3 | 0,044 |
| `camera_jitter_deg_s` | RMS tốc độ xoay camera trừ trung bình trượt 9 khung | 60°/s | `flag` | 20 | 0 | 1,39°/s |
| `instruction` | 1 khi không có câu lệnh | 0 | `reject` | 20 | 0 | 0 |
| `segments` | 1 khi không có đoạn, hoặc đoạn rỗng, chồng nhau, sai thứ tự, quá khung cuối | 0 | `reject` | 20 | 0 | 0 |
| `segment_count` (7/11/2026) | số đoạn | ≥ 2 | `reject` | 19 | 1 | 2 |
| `segment_ambiguous` | tỉ lệ sự kiện còn mở; 1 khi không có sự kiện | 0 | `flag` | 13 | 7 | 0 |

Kết quả ngày 6/11/2026, sau E-A và lần cắt có RoboBrain: 13 `pass`, 7 `flag`, 0 `reject`. Lần chạy chỉ luật trước đó cho 5 `pass`, 15 `flag`, vì 13 sự kiện còn mở.

Kết quả ngày 7/11/2026, chạy lại trên laptop: **8 `pass`, 11 `flag`, 1 `reject`**.

| Episode | Quyết định | Lý do |
|---|---|---|
| 4 episode | `flag` | file không có nhóm `confidences` |
| 3 episode | `flag` | tay ra khỏi khung 42–52% thời gian |
| 7 episode | `flag` | còn sự kiện mở (6 trong số đó do bỏ câu trả lời ở mép cửa sổ) |
| `ep_2732d666` (2,4 giây) | `reject` | `segment_count` 1 < 2: không tay nào đi đủ 0,2 m nên luật không thấy sự kiện |

Một episode có thể có nhiều lý do. Hai phép kiểm mới:

- `segment_count` chặn trường hợp một model làm mất sự kiện, như `ep_603d1475`.
- `hand_pose_nan` chạy trên `pose.npz`, tức pose DA-18 xuất: E-B với EgoDex, E-A với video tự quay. E-B không có khung NaN, nên 20/20 qua. Trên một bản sao lấy E-A làm `pose.npz`: 20/20 `flag`, không `reject`; ví dụ `ep_813f1b1e` có "NaN hand pose in 197 frames (left 197/266, right 10/266)". QA không cắt, không sửa pose; DA-18 bỏ các đoạn có khung NaN.

`fw egocentric report` ghi `DatasetReport` của hợp đồng (qua `dataset_report`, `render_html` của API làn) và thêm phần egocentric vào trang `report/index.html` và `report/egocentric.json`: số đoạn theo bước và theo nguồn nhãn, pass, flag, reject theo phép kiểm, giờ video, giấy phép và lý do miễn, độ lệch E-A so với E-B. Hợp đồng không thêm trường nào. `qa` chạy 1,15 s (ước tính 4,14 s), `report` 0,85 s (ước tính 0,2 s).

## 7. Vòng thử model gán nhãn (design mục 6.7.4)

Mục tiêu: chọn model cho hai việc trước khi dựa vào nó (D3, D6): gợi ý ranh giới khi luật mơ hồ, và chỉ điểm gắp. Code ở `ingest/egocentric/trial.py`, lệnh `fw egocentric trial`. Test chạy với model giả; trên dữ liệu thật thì vòng thử **chưa xong**.

| Thành phần | Thiết kế |
|---|---|
| Khung | 3 clip × 10 khung mỗi miền, mỗi clip một giây hai bên lần gắp: 30 khung EgoDex, 30 khung render SIMPLE của task hai bàn (psi-data của tác giả, 3 episode, 50 Hz) |
| Đáp án EgoDex | Khung gắp là giữa điểm dừng của luật trên E-B; điểm gắp là trung điểm ngón cái và ngón trỏ, chiếu vào từng khung |
| Đáp án SIMPLE | Khung gắp là khung đầu tiên tay đóng được nửa biên độ khớp (`observation.hand_joints`): 83, 117, 120. Điểm gắp do Claude đánh dấu bằng mắt trên lưới 64 × 36 px (`fwdata/egocentric-trial/simple_reference.json`, trường `marked_by`). **Chưa có người đánh dấu**, nên đáp án SIMPLE yếu hơn đáp án EgoDex |
| Đo | Sai số ranh giới (khung), tỉ lệ điểm trúng (trong 5% đường chéo ảnh), trung vị khoảng cách (px), giây mỗi câu hỏi, VRAM người chạy ghi lại |
| Đối chứng | Luật chạy trên E-A, chấm theo cùng đáp án EgoDex: mức model phải vượt trên video của đội |
| `Decision` | `verdict = open`, Hiếu ký. **[Đề xuất]** ngưỡng: trung vị sai số ranh giới tối đa 10 khung, tỉ lệ điểm trúng tối thiểu 60% |

Lần chạy ngày 6/11/2026:

| Mốc | Số đo |
|---|---|
| Bắt đầu | 10:06:44, job `job_ego_trial_01M6QD5B9SZBE0Z6JVNJJ8ZY9T` (mới có dòng ước tính) |
| RoboBrain, 6 câu ranh giới và 60 câu điểm gắp | xong trong khoảng 6 phút |
| Molmo2 trên CPU | khoảng 40 s mỗi câu điểm gắp; 4 trên 60 câu đã trả lời |
| Dừng | khoảng 10:20, theo quyết định "Giữ máy cho eval C, báo DA-04 hoãn" của Hiếu |
| Kết quả giữ được | không có: `rows.json` chỉ được ghi khi chạy xong (mục 9, dòng 11) |

Số đo lẻ từ trước lần chạy (cùng ngày, cùng máy):

| Model | Một câu chỉ điểm gắp | Một câu ranh giới 10 ảnh | VRAM |
|---|---|---|---|
| RoboBrain 2.5-4B (Ollama, Q4_K_M) | 9,5 s | chưa đo riêng; 66 câu của vòng thử hết khoảng 6 phút | 3,0 GB (nvidia-smi 8.053 → 11.127 MiB, chạy cạnh server Ψ₀ của DA-34); Ollama chia 25% CPU, 75% GPU |
| Molmo2-4B (transformers, CPU, bf16) | 57 s | quá 880 s, hết giờ | 0 GB; khoảng 11,4 GB RAM |

Vì câu ranh giới của Molmo2 quá chậm trên CPU, lệnh chạy lại dùng `--boundary robobrain`: chỉ RoboBrain trả lời ranh giới, cả hai model chỉ điểm gắp. Khi GPU rảnh và Molmo2 chạy được trên GPU thì bỏ tùy chọn này.

Chưa trả lời được câu của D3 ("model nào, có dùng không"). Trong lúc chờ, `annotate` vẫn chạy được với RoboBrain, nhưng ranh giới model đề xuất vẫn bị coi là chưa kiểm (mục 5).

## 8. Video tự quay (nhiệm vụ 7)

`fw egocentric ingest video --root <thư mục>` đọc `device.json` (tên thiết bị, fps, rộng, cao, ma trận nội 3 × 3; `tasks` và `objects` tùy chọn) và `<task>/<i>.mp4`, rồi ghi cùng thư mục làm việc như EgoDex: `source_detail = ego_video`, `data_class = public` (từ 9/11/2026, mục 8.1; trước đó `internal`), không miễn che danh tính, `hdf5 = null`, `pose_source = E-A`, `action_quality = pseudo`, luật cắt đoạn `two_table` (6 bước: tiếp cận, gắp, đi, tới, đặt, thả; bước đi lấy từ tốc độ camera).

```json
{"device": "iphone-15-wide", "fps": 30, "width": 1920, "height": 1080,
 "intrinsic": [[1450, 0, 960], [0, 1450, 540], [0, 0, 1]],
 "tasks": {"two_table": "pick the cup from the left table, place it on the right"},
 "objects": ["cup"]}
```

Tới 7/11/2026 đội chưa quay video nào. Phép thử trên file thật: một thư mục giả làm video tự quay, chứa một mp4 thật của EgoDex (`basic_pick_place/0.mp4`, 126 khung) và `device.json`. `ingest video` ghi `src_20c38abea95118a4` với đúng các nhãn trên; `pose --job` và `annotate` đều trả mã 2 ở cổng che danh tính. Theo D2, video của đội không tới được model nào cho tới khi có bước làm mờ. Từ 8/11/2026 bước đó là `fw egocentric deid` (mục 3.1). Sau bước này, phần còn lại của pipeline chạy như EgoDex trên bản sao đã che: job E-A cho pose, rồi `annotate`, `qa`, `report`.

### 8.1 Video tự quay là `public` (9/11/2026)

**[Đã chốt 9/11/2026, Hiếu]:** "Bỏ cái internal đi được đưa lên colab thì tôi mới train được chứ". Nguồn `ego_video` trong `configs/data/egocentric.yaml` đổi từ `internal` sang `public`, để stage 1 của nhánh B (DA-34 nhiệm vụ 4, DA-30 nhiệm vụ 2) train được trên Colab như C và C+.

- Video là của đội tự quay để làm demo, không phải dữ liệu DENSO; CLAUDE.md chỉ buộc dữ liệu DENSO là `internal` hoặc `restricted`.
- **Không đổi:** bước làm mờ vẫn bắt buộc trước mọi bước khác. Cổng che danh tính xét `source_detail`, không xét `data_class`: miễn chỉ có cho `egodex` + `public` theo pin, nên `ego_video` + `public` vẫn bị chặn tới khi có bản sao `blurred` (test `test_ego_deid.py`). Chỉ bản sao đã che rời máy; video gốc ở lại laptop.
- `source_id` băm cả `data_class`, nên nguồn đã ingest trước ngày này giữ id cũ và nhãn `internal`. Muốn dùng nhãn mới thì ingest lại, rồi chạy lại `deid`.
- **Còn mở:** người xuất hiện trong video đồng ý cho dùng video (đã che mặt) để train trên dịch vụ hosted; Hiếu xác nhận trước lần train đầu.

## 9. Việc còn mở

| # | Việc | Ảnh hưởng | Ai |
|---|---|---|---|
| 1 | Hợp đồng: `EpisodeMetadata.source_detail` chưa có `egodex`, `ego_video`; episode egocentric để trường này `None` | Bộ lọc theo nguồn chỉ đọc được từ `source.json` | **[Đề xuất]** PR hợp đồng của Hiếu thêm hai giá trị |
| 2 | Hợp đồng: `read_segments` từ chối hai cột `frame_start`, `frame_end` mà kế hoạch 4.2a thêm vào `segments.parquet` | DA-18 phải đọc bằng pyarrow, không qua `read_segments` | **[Đề xuất]** PR hợp đồng: cho phép cột khung, hoặc thêm hai trường vào `Segment` |
| 3 | Model và revision nằm trong `configs/data/egocentric.yaml`, story ghi `configs/models/` | Ngoài phạm vi file của story | PR riêng của chủ `configs/models/` |
| 4 | ~~Chưa có bước làm mờ (D2)~~ Đã có từ 8/11/2026: `fw egocentric deid`, YuNet (mục 3.1) | Video đội tự quay qua cổng sau khi chạy `deid` | Xong (nhiệm vụ 8); chờ Hiếu duyệt PR |
| 5 | Mẫu duyệt của người (`fw egocentric review`) chưa có ai điền; `label_source = human` mới chạy trong test | Chưa có số đo độ đúng của nhãn luật và nhãn model | Hiếu hoặc người được giao điền `review/sheet.jsonl` |
| 6 | Ngưỡng luật cắt đoạn và QA là giả định đọc từ 20 episode | Đổi ngưỡng là đổi `threshold_version` | Hiệu chỉnh khi có mẫu duyệt |
| 7 | Cổ tay E-A lệch nhiều hơn đầu ngón (63 và 115 px so với 43 và 51 px); chưa kiểm hai điểm cổ tay có cùng định nghĩa không | Action 48 chiều của DA-18 dùng cổ tay | Kiểm khi DA-18 xuất E-A |
| 8 | Phần tịnh tiến của VO chưa đo được trên EgoDex (người ngồi) | Chưa biết E-A dùng được cho bước đi của task hai bàn | Đo trên video hai bàn đầu tiên |
| 9 | Molmo2 chạy CPU vì GPU dùng chung với server Ψ₀ của DA-34 | Độ trễ của Molmo2 trong mục 7 là của CPU, không phải của GPU | Đo lại khi GPU rảnh nếu chọn Molmo2 |
| 10 | Vòng thử model chưa xong, chưa có `Decision` (D3) | Chưa chọn được model cho ranh giới và điểm gắp | Hiếu chạy theo mục 10.3 khi `rtx3060` trống |
| 11 | `trial` chỉ ghi `rows.json` khi chạy xong, nên lần chạy bị dừng không để lại gì | Mất 6 phút kết quả RoboBrain đã chạy | **[Đề xuất]** ghi theo từng model; việc nhỏ trong `trial.py` |
| 12 | Job `trial` bị dừng chỉ có dòng ledger ước tính, không có dòng thực đo | Sổ chi phí có một ước tính không có thực đo đi kèm | Ghi chú ở đây; sổ append-only nên không xóa dòng |
| 13 | Câu lệnh của 12 đoạn đổi sau khi bỏ câu trả lời ở mép (7/11/2026) đang là mẫu câu, vì RoboBrain chưa chạy lại | 12 trên 39 đoạn có `label_source = rule` | Chạy `annotate --endpoint` khi `rtx3060` trống |
| 14 | Pin chỉ gồm 218 video của mẫu DA-30; mở rộng tập con ra ngoài mẫu đó cần dựng lại pin | Episode mới không được miễn cho tới khi pin có video của nó | Dựng lại bằng `pin.py`; PO duyệt PR |
| 15 | Bước làm mờ chỉ che mặt; thẻ tên, màn hình, giấy tờ (AC 2) chưa che | Video quay trong nhà máy hay văn phòng có thể lộ chữ trên thẻ hoặc màn hình | **[Đề xuất]** quay sao cho không có màn hình, thẻ trong khung; thêm detector chữ (ví dụ EAST của OpenCV) sau demo |
| 16 | Ngưỡng `deid` (0,6, nới 25 %, giữ 5 khung) là giả định; mới đo trên một mặt dán vào video, chưa đo trên người thật đứng xa, nghiêng, đeo khẩu trang | Có thể sót mặt nhỏ hoặc nghiêng | Hiếu xem nhanh `frames_with_faces` trong `source.json` và vài khung của bản sao trước khi dùng; người duyệt mẫu thì đặt `verified` |
| 17 | Xuất stage 1 của DA-18 (`export/egodex.py`) đọc `bundle.mp4`, nên dùng bản sao, nhưng chưa tự kiểm sha256 của bản sao như cổng | Bản sao bị thay sau `deid` mà không chạy lại bước nào của DA-04 thì DA-18 không biết | **[Đề xuất]** DA-18 gọi `annotate_allowed` với `deid_copies`; PR riêng của DA-18 |
| 19 | E-A trong hệ camera (mục 4.1): không có quỹ đạo đầu; luật `two_table` không tìm được bước `walk`; `camera_jitter_deg_s` không đo gì với E-A | Delta stage 1 là tay so với đầu; cắt lại video hai bàn bằng luật sẽ thiếu bước đi | Đo quỹ đạo đầu (IMU của điện thoại, hoặc VO có tỉ lệ) rồi đặt `frame: world`; tới lúc đó dùng phiếu duyệt |
| 20 | Phần bị cắt 3,3 % đo bằng script của DA-30, chưa bằng `loader_check` trong image Ψ₀ | Script lệch `loader_check` khoảng 1 điểm trên bản thử | Phiên DA-30 chạy `loader_check` trên `egx_7b43c30dc5d88cd7` trước khi ghim |

## 10. Việc để chạy sau

Hiếu dặn 6/11/2026: máy local chạy được thì chạy, không thì để lại thông tin. Phần dưới là những gì chưa chạy được, kèm lệnh.

### 10.1 Đã chạy ở đâu

| Việc | Máy | Ghi chú |
|---|---|---|
| Ingest, E-B, nhập E-A, cắt đoạn chỉ luật, QA, báo cáo, mẫu duyệt, ingest video thử | laptop | Mỗi job dưới 2 s, RSS dưới 150 MB |
| Ghi `intrinsic` vào `pose.npz` (theo yêu cầu của DA-18) | laptop | `pose` rồi `pose --estimates`, 1,8 và 1,9 s |
| Job E-A (MediaPipe và VO) | `rtx3060`, CPU | Chạy trước 10:20 ngày 6/11/2026; kết quả ở `fwdata/egocentric-ea/src_050b9bf56a4e843c-v2/` |
| Cắt đoạn có RoboBrain | `rtx3060`, Ollama | Chạy trước 10:20 ngày 6/11/2026 |
| Vòng thử model | `rtx3060` | Dừng giữa chừng, **còn phải chạy** (mục 10.3) |

Laptop không chạy được hai model: RTX 3050 4 GB, RAM 14 GB nhưng chỉ còn khoảng 1–2 GB và swap đã đầy (đo 6/11/2026), chưa cài Ollama, không có trình biên dịch C. Molmo2 cần khoảng 11,4 GB RAM trên CPU. RoboBrain Q4_K_M cần khoảng 3,0 GB VRAM nên có thể vừa 4 GB, nhưng chưa thử, và cài Ollama là việc của chủ máy.

### 10.2 Đầu vào, đều ở trên laptop và không commit

| Đầu vào | Đường dẫn |
|---|---|
| Thư mục làm việc EgoDex | `fwdata/pipeline/src_050b9bf56a4e843c/` |
| psi-data hai bàn (53 MB, đã có video) | `fwdata/psi-data/simple/G1WholebodyLocomotionPickBetweenTablesTeleop-v0/` |
| Đáp án điểm gắp SIMPLE | `fwdata/egocentric-trial/simple_reference.json` |
| Venv, model, server trên `rtx3060` | `~/denso-da04/`: `venv-ea`, `venv-molmo` (torch 2.15.0+cpu, transformers 4.57.1, accelerate 1.15.0, pillow 13.0.0), `serve_molmo2.py`; RoboBrain đã kéo về Ollama. Không xóa |

### 10.3 Vòng thử model, khi `rtx3060` trống

1. Trên `rtx3060`: `free -g` và `nvidia-smi`. Cần khoảng 12 GB RAM trống cho Molmo2 và khoảng 3 GB VRAM cho RoboBrain (đo).
2. Bật Molmo2. Server chỉ mở cổng khi đã nạp xong model. `curl -s -o /dev/null -w '%{http_code}' 127.0.0.1:18431` in `000` khi chưa nạp xong, và `501` khi đã sẵn sàng (server không có GET).

   ```bash
   cd ~/denso-da04 && nohup setsid systemd-run --user --scope -p MemoryMax=24G -p MemorySwapMax=0 \
     venv-molmo/bin/python serve_molmo2.py --port 18431 \
     --revision 042abfa7a38879a376cec03d949eff0aefaa0600 --threads 16 \
     > molmo_serve2.log 2>&1 < /dev/null &
   ```

3. Trên laptop, mở đường hầm tới hai cổng:

   ```bash
   ssh -f -N -L 18431:127.0.0.1:18431 -L 21434:127.0.0.1:11434 rtx3060
   ```

4. Trên laptop, từ worktree của nhánh. Phía client nhẹ: chỉ đọc khung và gửi JPEG. Ollama tự nạp RoboBrain ở câu hỏi đầu.

   ```bash
   W=fwdata/pipeline/src_050b9bf56a4e843c
   FW_ROOT=fwdata uv run fw egocentric trial $W \
     --simple fwdata/psi-data/simple/G1WholebodyLocomotionPickBetweenTablesTeleop-v0 \
     --reference fwdata/egocentric-trial/simple_reference.json \
     --robobrain http://127.0.0.1:21434/v1 --molmo http://127.0.0.1:18431/v1 \
     --timeout-s 1200 --boundary robobrain \
     --vram "robobrain=<nvidia-smi lúc nạp>" --vram "molmo=0 GB: CPU, bf16, 16 threads"
   ```

   Thời gian ước lượng (từ lần chạy dừng giữa chừng): RoboBrain khoảng 6 phút, Molmo2 khoảng 40–60 phút cho 60 câu.
5. Đầu ra: `$W/trial/rows.json` (mọi câu hỏi và câu trả lời), `$W/trial/decision.json` (`Decision`, `verdict = open`), hai dòng ledger của job `trial`. Lệnh in tóm tắt số đo.
6. Dọn máy: `kill` PID của `pgrep -f "[v]env-molmo/bin/python"`, rồi `ollama stop hf.co/mradermacher/RoboBrain2.5-4B-GGUF:Q4_K_M`, rồi đóng đường hầm.
7. Đưa kết quả về: Hiếu đọc `decision.json`, ký và đổi `verdict`; số đo điền vào mục 7 của file này. Nếu RoboBrain qua ngưỡng ranh giới thì giữ `annotate --endpoint`; nếu không, sự kiện mơ hồ đi qua `fw egocentric review`.

Molmo2 trên GPU (bf16) ước lượng cần khoảng 10 GB VRAM (giả định: khoảng 5 tỉ tham số × 2 byte), nên không vừa khi server Ψ₀ của DA-34 giữ 7,2 GB.

### 10.4 Chạy lại E-A, khi có episode mới

1. Trên laptop: `fw egocentric pose $W --job ea_jobs.json` ghi manifest. Chép manifest, các mp4 trong đó (lần trước là một tgz 100 MB) và `ingest/egocentric/estimate_job.py` lên `~/denso-da04/`.
2. Trên `rtx3060`: chạy lệnh của mục 1.1. Lần trước đo được 7,5 khung/s trên CPU và giới hạn bộ nhớ là 8 GB. Mỗi episode cho một `<id>.npz`.
3. Chép thư mục `out-ea/` về `fwdata/egocentric-ea/<source>-v<n>/`, rồi trên laptop chạy `fw egocentric pose $W --estimates <thư mục>` (1,9 s). Lệnh ghi `pose_ea.npz` và `compare.json`; episode không có HDF5 thì ghi cả `pose.npz`.

Chưa thử cài MediaPipe trên laptop. Gói có wheel sẵn nên không cần trình biên dịch, nhưng với 1–2 GB RAM trống thì chạy job dễ làm treo máy.

### 10.5 Mẫu duyệt của người

Điền `decision` (`accept`, `fix` hoặc `reject`; `fix` thì sửa `description`) và `reviewer` cho 8 đoạn trong `$W/review/sheet.jsonl` (phiếu ghi lại ngày 7/11/2026; không sửa `match`), rồi chạy `fw egocentric review $W --apply $W/review/sheet.jsonl`. Đoạn đã duyệt được ghi `label_source = human`. Việc này không cần máy mạnh.

## Change log

| Ngày | Nội dung | Người |
|---|---|---|
| 9/11/2026 | Mục 4.1 sau review PR 174: khung nhảy theo mảnh (gồm đầu ngón, đầu đoạn), dấu track theo hai phiếu, `compare.json` ghi `pose_ea` của EgoDex; chạy lại, bản xuất `egx_7b43c30dc5d88cd7` có 3,3 % action bị cắt; dòng 20 mục 9 | Claude (phiên DA-04 QA), theo review của Hiếu |
| 9/11/2026 | Thêm mục 4.1: làm sạch E-A (nhiệm vụ 10), chạy trên 153 clip khay, bản xuất `egx_b6e974e46e8222e8` có 3,8 % action bị cắt; dòng 19–20 mục 9 | Claude (phiên DA-04 QA), theo giao việc của Hiếu |
| 9/11/2026 | Video tự quay đổi sang `public` theo quyết định của Hiếu (mục 8.1); bước làm mờ không đổi | Claude, theo quyết định của Hiếu |
| 8/11/2026 | Thêm bước làm mờ `fw egocentric deid` (nhiệm vụ 8, mục 3.1); cổng chỉ cho episode `blurred` qua khi mọi video có bản sao đúng sha256; dòng 4 mục 9 xong, thêm dòng 15–17 | Claude (phiên DA-04 deid), theo yêu cầu của Hiếu |
| 7/11/2026 | Sửa theo review PR 152 (mục 3, 5, 6, 1.2, 10.5) | Claude (phiên DA-04), theo review của Hiếu |
| 6/11/2026 | Tạo file: 7 nhiệm vụ trên 20 episode EgoDex | Claude (phiên DA-04), theo phân công của Hiếu |

## Phụ lục A. `serve_molmo2.py`

Server OpenAI tối giản cho Molmo2-4B, dùng ở mục 1.2 và 10.3. File này không nằm trong package vì cần torch, mà làn `flywheel.data` không được import torch. Chép vào `~/denso-da04/` trên máy chạy.

```python
"""Minimal OpenAI-compatible /v1/chat/completions for Molmo2-4B with transformers (DA-04 trial).

Ollama 0.32.14 cannot load Molmo2's vision projector, and the GPU of rtx3060 is
shared, so Molmo2 runs on CPU here. Images arrive as data URLs, as `OpenAIVision`
sends them. Usage: python serve_molmo2.py --port 18431 --revision <sha>
"""

import argparse
import base64
import io
import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import torch
from PIL import Image
from transformers import AutoModelForImageTextToText, AutoProcessor

parser = argparse.ArgumentParser()
parser.add_argument("--model", default="allenai/Molmo2-4B")
parser.add_argument("--revision", required=True)
parser.add_argument("--port", type=int, default=18431)
parser.add_argument("--threads", type=int, default=16)
args = parser.parse_args()
torch.set_num_threads(args.threads)
processor = AutoProcessor.from_pretrained(args.model, revision=args.revision,
                                          trust_remote_code=True)
model = AutoModelForImageTextToText.from_pretrained(
    args.model, revision=args.revision, trust_remote_code=True, dtype=torch.bfloat16,
    device_map="cpu")
model.eval()


def answer(body: dict) -> str:
    content = []
    for part in body["messages"][-1]["content"]:
        if part["type"] == "image_url":
            data = part["image_url"]["url"].split(",", 1)[1]
            content.append({"type": "image",
                            "image": Image.open(io.BytesIO(base64.b64decode(data))).convert("RGB")})
        elif part["type"] == "text":
            content.append({"type": "text", "text": part["text"]})
    messages = [{"role": "user", "content": content}]
    inputs = processor.apply_chat_template(messages, tokenize=True, add_generation_prompt=True,
                                           return_tensors="pt", return_dict=True)
    with torch.inference_mode():
        ids = model.generate(**inputs, max_new_tokens=int(body.get("max_tokens", 200)),
                             do_sample=False)
    return processor.tokenizer.decode(ids[0, inputs["input_ids"].size(1):],
                                      skip_special_tokens=True)


class Handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        start = time.monotonic()
        text = answer(body)
        reply = {"object": "chat.completion", "model": body.get("model"),
                 "choices": [{"index": 0, "message": {"role": "assistant", "content": text},
                              "finish_reason": "stop"}],
                 "seconds": round(time.monotonic() - start, 2)}
        data = json.dumps(reply).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()
```
