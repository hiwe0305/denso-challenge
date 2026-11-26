# DA-50 · Train run N: dữ liệu nhắm lỗi đặt và lỗi nghiêng của run M

## Trạng thái

| Trường | Giá trị |
|---|---|
| Trạng thái | Nháp 26/11/2026, chờ Hiếu duyệt |
| Người làm | Hiếu |
| Làn | Ngoài ba làn: adapter `flywheel-psi0` và `flywheel-simple` (task bê khay), không sửa nhân hay làn |
| Nguồn yêu cầu | Hiếu, 26/11/2026, sau kết quả eval run M ("lên planning để training tiếp") |
| Nhãn | `area:train`, `area:data` |
| Sprint | Trước vòng chung kết (khoảng 3/12/2026) |
| Ước lượng | Mã và đo (nhiệm vụ 1, 4, 6) khoảng 8 giờ; sinh dữ liệu khoảng 1 ngày máy; train khoảng 21 giờ và 56 CU; eval khoảng 2,5 giờ và 7 CU. Tất cả là ước lượng, lấy từ số đo của run M |
| Phụ thuộc | DA-47 (PR 228: eval `jig2`, outcome K1) phải merge trước nhiệm vụ 6; DA-48 (run M, đã merge); DA-41, DA-46 (cảnh và planner sinh dữ liệu) |

## Story

Là người train policy Ψ₀ cho task bê khay, tôi muốn train một run mới ("run N") chỉ khác run M ở tập dữ liệu, với dữ liệu thêm nhắm đúng hai lỗi đã đo ở run M, để biết thu dữ liệu theo lỗi có đưa task tới mốc 80 % hay không. Đây là một vòng Failure → Data trên cảnh đồ gá.

Kết quả run M ([tray-jig.md](../../he/tray-jig.md) mục 5, thực đo 26/11/2026): 75,6 % (136/180), khoảng tin cậy 70,0–81,1, chưa đạt mốc 80 %; mức 1 là 85,6 %, mức 2 là 65,6 %. Trong 44 lượt hỏng:

| Lỗi | Số lượt | Điều đo được |
|---|---|---|
| `L-PLACE-POSE` | 28 (mức 2: 20) | 22 lượt khay gác lên thành đồ gá: policy hạ khay khi còn lệch 5–10 cm hoặc 8–15°, ngoài lead-in 4,2 cm của mặt vát. Robot không sửa sau khi buông |
| `L-TRAY-TILT` | 13 (mức 2: 8) | Khay vượt 15° khi hai tay còn cầm; 8 lượt giữa đường đi, 5 lượt lúc hạ |
| Khác | 3 | Mỗi nhãn 1 lượt |

## Cách làm

**[Đề xuất]** Claude, 26/11/2026. Mọi số chưa ghi "thực đo" là ước lượng.

| Phương án | Nội dung | Được | Mất |
|---|---|---|---|
| **A (chọn)** | Train lại từ checkpoint cha, 100 000 bước, cùng recipe như M; chỉ đổi dữ liệu | Hiệu N trừ M đọc được là do dữ liệu; so ghép cặp trên cùng 60 điều kiện | Khoảng 56 CU và 21 giờ |
| B | Train tiếp từ `ckpt_100000` của M thêm 40 000 bước với tập mới | Khoảng 22 CU | Đổi cùng lúc dữ liệu và số bước; không tách được nguyên nhân |
| C | Thêm run đối chứng K (498 episode đầy đủ) song song | Đo được phần của dữ liệu bước đặt trong M | Thêm khoảng 56 CU; số dư 151,8 CU không đủ cho N, K và dự phòng |

Số đo ban đầu của tập train run M (thực đo 26/11/2026, đọc từ nhật ký sinh và phát lại trên `rtx3060`: `quality.jsonl`, `gen_log.jsonl`, `replay_outcomes.jsonl` của bốn lô; chỉ tính episode trong danh sách giữ):

| Phần | Episode | Đỉnh nghiêng khi mang, p50 / p90 / lớn nhất (°) | Lệch đích lúc tới bàn B | Khay cuối không phẳng |
|---|---|---|---|---|
| Đầy đủ, mức 1 | 356 | 5,4 / 7,5 / 9,6 | Không lệch | 3 |
| Đầy đủ, mức 2 | 142 | 5,5 / 7,5 / 9,6 | Không lệch | 3 |
| Đoạn đặt, mức 1 | 377 | 6,0 / 7,7 / 9,9 | Dọc và ngang, mỗi trục trải đều trong ±10 cm; không lệch góc | 10 |
| Đoạn đặt, mức 2 | 162 | 6,1 / 8,1 / 9,9 | Như trên | 2 |

- **Nghiêng.** Không demo nào nghiêng quá 10° khi mang. Lỗi `L-TRAY-TILT` của policy (15° trở lên) không phải do bắt chước demo nghiêng; lọc demo theo độ nghiêng không có gì để lọc.
- **Lệch ngang.** Dữ liệu đoạn đặt đã phủ lệch ngang và dọc tới ±10 cm (539 episode), đúng cỡ lệch của các lượt gác thành (5–10 cm). Policy vẫn đặt lệch, nên đây **không** phải lỗ hổng về khoảng lệch; thêm dữ liệu cùng loại có thể không sửa được.
- **Lệch góc.** Planner chỉ làm lệch hai trục vị trí (`carry_offset` có 2 giá trị); không có demo nào tới bàn B lệch góc rồi xoay lại. 10/28 lượt `L-PLACE-POSE` của M có lệch góc trên 10°.
- **Khay phẳng.** 18/1 037 demo (1,7 %) có khay cuối không phẳng theo số phát lại, so với 58/178 lượt của policy.
- Chưa đo: tư thế khay đúng lúc bắt đầu hạ (nhật ký không ghi quỹ đạo khay; cần chạy lại sim). Tiêu chí 1 mới đạt một phần.

Dữ liệu thêm, theo thứ tự ưu tiên, **đã sửa theo số đo trên** (bản đầu có "bỏ demo có đỉnh nghiêng cao", nay bỏ). Thành phần cuối cùng do Hiếu chốt ở nhiệm vụ 2:

| Ưu tiên | Dữ liệu | Lý do | Điều chưa chắc |
|---|---|---|---|
| 2 | Thêm episode mức 2 (đầy đủ và đoạn đặt cắt) | Tập của M có 304/1 037 episode mức 2 (29 %); mức 2 hỏng nhiều nhất (31/44 lượt hỏng) | Không biết tham số nào của mức 2 gây lỗi |
| 1 | Đoạn đặt có lệch **góc** lúc tới bàn B (thêm trục xoay vào độ lệch của planner) | Chưa có demo nào sửa lệch góc; 10/28 lượt đặt lệch có lệch góc trên 10° | Cần sửa planner (`flywheel_simple/tray/planner.py`, lớp độ lệch CARRY) và đo tỉ lệ thành công của planner khi tới lệch góc |
| 3 | Thêm đoạn đặt lệch ngang cùng loại | Lỗi lệch ngang là nhiều nhất | Số đo trên cho thấy khoảng lệch đã được phủ; lợi ích là giả thuyết yếu |

**Video camera đầu của 28 lượt `L-PLACE-POSE` (xem 26/11/2026, một khung 5 giây trước lỗi và một khung lúc lỗi cho mỗi lượt; đếm bằng mắt, số gần đúng):**

- Tấm đồ gá màu cam còn thấy được dưới mép gần của khay ở khoảng 24/28 lượt, 5 giây trước lỗi. Giả thuyết "khay che mất đồ gá" **không** được ủng hộ.
- Khoảng 9–10 lượt robot tới bàn B lệch hướng rõ (mép bàn chéo trong ảnh), khớp với 10 lượt có lệch góc trên 10°. Policy đặt khay thẳng theo thân robot, không theo đồ gá.
- Các lượt còn lại robot đứng gần vuông với bàn nhưng khay lệch ngang vài cm; policy vẫn hạ dù đồ gá còn trong ảnh.

**Rủi ro của run N.** Lỗi đặt lệch ngang xảy ra dù dữ liệu đã phủ khoảng lệch đó và đồ gá còn thấy được, nên chưa biết thêm dữ liệu có sửa được phần này không. Lệch góc là phần có căn cứ rõ nhất (khoảng 10 lượt), nhưng để cận dưới chạm 80 % cần sửa khoảng 18 lượt (ước lượng): run N có thể cải thiện mà vẫn chưa đạt mốc.

Ngoài phạm vi: demo "gác lên thành rồi nhấc lên đặt lại" (planner chưa có hành vi này); đổi điều kiện thành công thành "khay nằm phẳng trong đồ gá" (cần Decision riêng của Hiếu, xem tray-jig.md mục 5); run K.

Luật đọc: khối `jig-n-rules` ở [tray-jig.md](../../he/tray-jig.md) mục 6, viết trước khi sinh dữ liệu và train. Plan của N ghim sha256 của khối này.

## Tiêu chí chấp nhận

1. Có số đo của tập train run M: độ lệch vị trí và góc của khay so với đích lúc bắt đầu hạ, và đỉnh nghiêng khi mang, theo từng phần của tập.
2. Thành phần dữ liệu của run N do Hiếu chốt, ghi kèm số đo của tiêu chí 1.
3. Seed của dữ liệu thêm không trùng seed eval 1000100–1000129 và không trùng seed đã có trong tập M; kiểm bằng lệnh.
4. Plan `configs/runplans/tray/he-tray-jig-n.yaml` đóng băng, ghim sha256 của khối `jig-n-rules`, cùng recipe, cha, số bước và seed train như plan M.
5. Dòng ledger ước tính ghi **trước** khi mở phiên Colab; dòng thực đo trỏ về nó.
6. `ckpt_100000` của N có sha256 ghi lúc persist; eval 180 rollout trên tập điều kiện của M.
7. Kết quả đọc đúng khối `jig-n-rules`, gồm hiệu ghép cặp N trừ M trên 3 lượt mỗi điều kiện, ghi vào tray-jig.md cùng giới hạn.
8. Kiểm tra của repo qua (ruff, mypy, pytest, import-linter, `check_links.py`, `pr_guard.py`).

## Nhiệm vụ

- [ ] 1. Đo tập train của run M (laptop hoặc `rtx3060`, không GPU)
  - [ ] 1.1 Độ lệch vị trí và góc lúc bắt đầu hạ khay, theo từng phần
  - [ ] 1.2 Đỉnh nghiêng của khay khi mang, theo từng phần
- [ ] 2. Hiếu chốt thành phần dữ liệu của run N từ số đo của nhiệm vụ 1
- [ ] 3. Sinh dữ liệu thêm trên `rtx3060` (Hiếu chạy hoặc cho phép; tối đa 14 worker)
  - [ ] 3.1 Lô mẫu nhỏ, xem trước khi sinh cả lô
  - [ ] 3.2 Sinh cả lô, lọc theo ngưỡng đặt ≤ 3 cm và ≤ 5° như run M
- [ ] 4. Plan của run N
  - [ ] 4.1 Dựng tập ghép, kiểm seed (tiêu chí 3)
  - [ ] 4.2 Viết và đóng băng `he-tray-jig-n.yaml`; dòng ledger ước tính
- [ ] 5. Train run N trên Colab L4 (Hiếu chạy), dừng VM ngay khi xong
- [ ] 6. Eval và đọc
  - [ ] 6.1 Hiệu ghép cặp trên nhiều lượt mỗi điều kiện trong `eval_results` (hiện `paired_diff` chỉ đọc lượt 0), có test CPU
  - [ ] 6.2 Eval 180 rollout theo runbook của DA-47
  - [ ] 6.3 Đọc theo `jig-n-rules`, ghi kết quả và dòng ledger thực đo
- [ ] 7. Kiểm tra cuối và PR

## Phạm vi file

Theo 07 mục 3.1. File story luôn được sửa.

- `packages/flywheel-psi0/src/flywheel_psi0/tray/`
- `packages/flywheel-psi0/tests/tray/`
- `scripts/g0/tray/` (chỉ script đo của nhiệm vụ 1)
- `packages/flywheel-simple/src/flywheel_simple/tray/planner.py` và test của nó (chỉ thêm trục xoay vào độ lệch CARRY, nếu Hiếu chọn dữ liệu lệch góc)
- `configs/runplans/tray/` (chỉ file mới của run N)
- `docs/g0/ledger/DA-50.csv`
- `docs/he/tray-jig.md` (mục 6 trở đi; không sửa khối `jig-m-rules` và, sau khi đóng băng, khối `jig-n-rules`)
- `docs/g0/tray/place-data.md` (chỉ thêm mục về lô dữ liệu mới)

Không sửa `simple_task.py`, hình học đồ gá, bộ chấm, hay `flywheel.contracts`; cần thì dừng và đề xuất PR riêng.

## Ghi chú cho người làm

- Ba lỗi vận hành của run M (tray-jig.md mục 4): tiến trình `guard` thoát sớm chưa sửa; kiểm nó còn sống sau khi phiên Colab được cấp.
- Token CLI Colab hết hạn sau khoảng 16 giờ; run dài khoảng 21 giờ cần đăng nhập lại một lần. Giữ laptop thức.
- Eval: ba server Ψ₀ chạy chung một L4 (khoảng 7 GB mỗi server), ba làn `eval_batch` trên `rtx3060`; mỗi VM chỉ nhận một kết nối `colab ssh`.
- Tập eval là tập dev đã dùng để chọn dữ liệu của N; ghi giới hạn này cùng kết quả (khối luật).

## Kiểm thử

- Test CPU cho hiệu ghép cặp nhiều lượt (nhiệm vụ 6.1): hai lô giả, số lượt mỗi điều kiện khác 1, khoảng tin cậy lặp lại được với seed cố định; từ chối khi hai lô khác tập điều kiện hoặc khác phiên bản bộ chấm.
- Kiểm seed của tập ghép bằng lệnh `mixplan check`.

## Người phụ trách

Hiếu (làm cùng Claude), duyệt cuối: Hiếu.

## Change log

| Ngày | Nội dung | Người |
|---|---|---|
| 26/11/2026 | Tạo từ kết quả eval run M | Hiếu (soạn với Claude) |
| 26/11/2026 | Thêm số đo ban đầu của tập train run M; sửa bảng dữ liệu thêm (bỏ lọc theo độ nghiêng, thêm lệch góc), thêm mục rủi ro | Hiếu (soạn với Claude) |
| 26/11/2026 | Thêm nhận xét từ video camera đầu của 28 lượt đặt lệch; đưa dữ liệu lệch góc lên ưu tiên 1 | Hiếu (soạn với Claude) |
