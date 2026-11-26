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

Dữ liệu thêm, theo thứ tự ưu tiên. Thành phần cuối cùng chốt ở nhiệm vụ 2, sau số đo của nhiệm vụ 1:

| Ưu tiên | Dữ liệu | Lý do | Giả thuyết cần đo trước |
|---|---|---|---|
| 1 | Thêm episode mức 2 (đầy đủ và đoạn đặt cắt) | Tập của M có 304/1 037 episode mức 2 (29 %), mức 2 hỏng nhiều nhất | Không |
| 2 | Đoạn đặt có lệch ngang và lệch góc lúc tới bàn B | 22 lượt gác thành đều lệch ngang hoặc lệch góc | Lô DA-46 (lệch đích CARRY ±10 cm) đã phủ lệch ngang và lệch góc 8–15° tới đâu |
| 3 | Bỏ demo có đỉnh nghiêng cao khi mang | 11/13 lượt nghiêng chỉ vừa chạm 15° | Phân phối đỉnh nghiêng của demo trong tập M |

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
