# Danh sách kiểm trước khi quay · Flywheel Console (28/11/2026)

| Ngày | Phiên bản | Nội dung | Người viết |
|---|---|---|---|
| 28/11/2026 | 0.2 | Câu "run nào tốt nhất" đã sửa (PR #263, xếp theo kết quả thi): bỏ dòng "tránh hỏi khi quay", thêm câu này vào bảng câu đã thử | Hiếu (soạn với Claude) |
| 28/11/2026 | 0.1 | Bản đầu, sau đợt đánh giá console ngày 28/11/2026 và các PR #258–#261. Thay mục 6 của [kịch bản 17/11](2026-11-17-kich-ban-video.md) về cách bật server, chat và những gì không được lộ | Hiếu (soạn với Claude) |

File này chỉ thay phần chuẩn bị máy, server và chat. Lời nói và thứ tự cảnh vẫn ở [kịch bản 17/11](2026-11-17-kich-ban-video.md), nhưng chưa được soát lại theo câu chữ mới ở mục 4.

## 1. Bật server

**[Đã chốt]** Một server duy nhất, bật bằng script `scripts/console/console-demo.sh`. Script chạy `fw console serve --lock --chat` trên cổng 4178: mọi việc ghi bị từ chối, chat vẫn trả lời. Script không in khóa API hay nội dung `.env`.

- [ ] Dựng lại index nếu `fwdata` vừa đổi: `uv run fw console index`. Index dựng ngày 28/11/2026 đã gồm CI của bước đặt cho run M.
- [ ] Đóng các phiên Claude và trình duyệt khác. Script cảnh báo nếu RAM trống dưới 4 GB hoặc có console khác đang chạy. Ngày 28/11/2026 laptop từng treo khi chạy nhiều server cùng lúc.
- [ ] Ở thư mục gốc của repo, bật server bằng lệnh dưới đây. Lệnh chỉ in `OK` khi mọi kiểm tra đều qua.

```bash
scripts/console/console-demo.sh start
```

Lệnh `start` tự chạy `check` sau khi bật. `check` dừng với dòng `FAIL` nếu:

- server không khóa, hoặc chat tắt;
- `/data/catalog.json`, `story.json` hay `tasks.json` có nhắc DA-50;
- một đường dẫn của `story.json` (kể cả `story.json/`, `./story.json`) trả kết quả đang giữ;
- model chat không trả lời.

Chạy lại `check` bất cứ lúc nào bằng lệnh sau:

```bash
scripts/console/console-demo.sh check
```

Tắt server khi quay xong (server đóng tunnel ssh tới `rtx3060` khi nhận tín hiệu dừng):

```bash
scripts/console/console-demo.sh stop
```

## 2. Chat

- Model: `sypham98/claude-opus-5-5` qua cổng CKEY, đặt bằng `CKEY_MODEL` trong `.env`. Model dự phòng là `sypham98/claude-fable-5`. Mỗi câu hỏi tốn khoảng 6–45 VND (ước lượng từ lượt đo ngày 28/11/2026).
- Dữ liệu demo (sim G1, tray) là `public` nên được gửi tới API hosted. Không đưa dữ liệu `internal` hay `restricted` vào console khi chat đang dùng model hosted.
- Nếu cổng CKEY lỗi: `CHAT=nemotron scripts/console/console-demo.sh start` dùng Nemotron tự host trên `rtx3060`. Cách này không đọc `.env` và không dùng khóa hosted.
- [ ] Nhãn khung chat là "Trợ lý phân tích". Tên cổng và tên model không hiện trên các trang quay; chỉ trang cấu hình chat có, nên không mở trang đó khi quay.
- [ ] Khung chat đóng khi tải trang. Chỉ mở ở cảnh hỏi trợ lý.
- [ ] Hỏi thử từng câu của cảnh một lượt, rồi bấm "new" để xóa trước khi quay.

Các câu đã hỏi thử trên bản khóa ngày 28/11/2026. Câu trả lời có thể đổi vài chữ giữa các lần hỏi, nhưng phải giữ đúng ý ở cột phải:

| Vòng | Câu hỏi | Câu trả lời phải có |
|---|---|---|
| `tray-jig-r1` | Run M đạt mốc ở những mức nào? | 75,6 % (136/180), CI 70,0–81,1, chưa đạt mốc 80 %; mức 1 đạt mốc 70 %; mức 2 chưa đạt mốc 70 %; bước đặt CI 85,0–93,9, đạt mốc 50 % |
| `tray-r1` | Vòng 1 so với vòng đồ gá khác nhau thế nào? | "chỉ đặt cạnh nhau, không so như một kết quả"; bốn bản của vòng 1 có khoảng tin cậy chồng nhau |
| `tray-r1` | Vì sao run C_70 hỏng nhiều ở bước đặt? | 32 trong 50 lượt hỏng của C_70 là đặt lệch; cụm c1, c2; "chưa kiểm… phỏng đoán"; đóng phiếu DA-38, DA-37 |
| `tray-r1` | Tổng chi phí cả dự án là bao nhiêu? | Ước tính và thực đo tách riêng, không cộng gộp |
| `tray-r1` | Run nào tốt nhất? | (bản 0.2) Xếp theo kết quả thi, không theo loss train: "C_70 có số lượt thành công cao nhất, 10/60, nhưng khoảng tin cậy của bốn bản chồng nhau, nên chưa phân biệt được"; không có C70_R1 |

## 3. Trình duyệt

- [ ] Mở một tab mới sau khi bật server. Tab cũ có thể còn giữ file JS của bản trước dù server trả `no-store`.
- [ ] Ngôn ngữ VI, nền sáng, zoom 125 % ở màn 1920×1080 như kịch bản 17/11.
- [ ] **[Đã chốt]** Vòng mặc định là `tray-r1`. Mạch quay đi `tray-r1` trước, rồi đổi ô "Vòng" sang `tray-jig-r1`.
- [ ] Mở sẵn mỗi trang một lần ở cả hai vòng để video và ảnh vào bộ đệm, ít nhất `#/tasks`, `#/report`, `#/eval`, `#/diagnose`, `#/loop`, `#/cost`, `#/sim`.

## 4. Không được lộ trên màn hình

- [ ] Kết quả thi lại của C70_R1. Web và chat chỉ nói "Kết quả thi lại của lượt này không trình bày ở bản demo." Tên C70_R1 chỉ được hiện ở tiến độ train và tên bản cắt dữ liệu.
- [ ] Run N, story DA-50, phiên `da50-*`, thư mục `jig-n*`. Trên trang Chi phí, phần này nằm trong dòng "Thí nghiệm khác (không trình bày)". Hỏi trợ lý thì nó trả lời "Trong dữ liệu trình bày ở bản demo không có tập dữ liệu hay run nào như vậy."
- [ ] Terminal, `.env`, đường dẫn máy, tài khoản W&B hay Colab, token, email.
- [ ] Câu chữ cũ đã đổi ngày 28/11/2026. Nếu lời nói của kịch bản 17/11 còn những câu này thì sửa trước khi quay:
  - "Bản tốt nhất là bản gốc C_70": nay nói "C_70 cao nhất 10/60, các khoảng chồng nhau".
  - "đạt" dùng cho số lượt thành công: nay "đạt" chỉ dùng khi cận dưới của CI vượt mốc.

## 5. Chưa kiểm ở lượt này

- Lời nói từng cảnh của kịch bản 17/11 so với trang mới.
- Bản tiếng Anh của từng trang.
- Phát video ở `#/follow` và trình xem 180 rollout của run M khi khóa.
