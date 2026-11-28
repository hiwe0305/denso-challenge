# Danh sách kiểm trước khi quay · Flywheel Console (28/11/2026)

| Ngày | Phiên bản | Nội dung | Người viết |
|---|---|---|---|
| 28/11/2026 | 0.3 | Theo PR #265–#267 và quyết định tối 28/11 của Hiếu: vòng mặc định đổi sang `tray-jig-r1`, mạch quay đi vòng đồ gá trước; thêm bảng so sánh 60 lượt, tập train run M ở trang Dữ liệu và khối "Quá trình suy luận"; bảng câu đã thử hỏi lại trên bản `dea4e6de` | Hiếu (soạn với Claude) |
| 28/11/2026 | 0.2 | Câu "run nào tốt nhất" đã sửa (PR #263, xếp theo kết quả thi): bỏ dòng "tránh hỏi khi quay", thêm câu này vào bảng câu đã thử | Hiếu (soạn với Claude) |
| 28/11/2026 | 0.1 | Bản đầu, sau đợt đánh giá console ngày 28/11/2026 và các PR #258–#261. Thay mục 6 của [kịch bản 17/11](2026-11-17-kich-ban-video.md) về cách bật server, chat và những gì không được lộ | Hiếu (soạn với Claude) |

File này chỉ thay phần chuẩn bị máy, server và chat. Lời nói và thứ tự cảnh vẫn ở [kịch bản 17/11](2026-11-17-kich-ban-video.md), nhưng chưa được soát lại theo câu chữ mới ở mục 4.

## 1. Bật server

**[Đã chốt]** Một server duy nhất, bật bằng script `scripts/console/console-demo.sh`. Script chạy `fw console serve --lock --chat` trên cổng 4178: mọi việc ghi bị từ chối, chat vẫn trả lời. Script không in khóa API hay nội dung `.env`.

- [ ] Dựng lại index nếu `fwdata` vừa đổi: `uv run fw console index`. Index dựng ngày 28/11/2026 từ bản `dea4e6de` đã gồm CI của bước đặt cho run M, bảng so sánh 60 lượt và tập train run M.
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
- [ ] Hỏi thử từng câu của cảnh một lượt, rồi bấm "Phiên làm việc" → "+ Phiên mới" để bắt đầu sạch trước khi quay.
- [ ] Mỗi câu trả lời mở đầu bằng khối "Quá trình suy luận · N bước · M số đã đối chiếu", gập sẵn. Khi đang trả lời khối mở ra và hiện từng bước tra dữ liệu, không có prompt hay suy nghĩ ẩn của model. Muốn cho người xem thấy cách trợ lý suy luận thì bấm mở khối sau khi câu trả lời xong.
- [ ] Hai chế độ: "Hỏi nhanh" trả lời ngắn (dòng đầu trả lời thẳng, bảng, một dòng "Lưu ý"); "Phân tích sâu" trả lời theo khuôn Kết luận, Bằng chứng (bảng, biểu đồ), Diễn giải, Giới hạn, Hướng tiếp theo.

Các câu đã hỏi lại trên server 4178 khóa, bản `dea4e6de`, tối 28/11/2026. Câu trả lời có thể đổi vài chữ giữa các lần hỏi, nhưng phải giữ đúng ý ở cột phải:

| Vòng | Chế độ | Câu hỏi | Câu trả lời phải có |
|---|---|---|---|
| `tray-jig-r1` | Hỏi nhanh | Run M đạt mốc ở những mức nào? | 136/180 lượt thành công (75,6 %), CI 70,0–81,1, chưa đạt mốc 80 %; mức 1 đạt mốc 70 %; mức 2 chưa đạt mốc 70 %; bước đặt CI 85,0–93,9, đạt mốc 50 % |
| `tray-jig-r1` | Hỏi nhanh | Run nào tốt nhất, vì sao? | "M: 136/180 lượt thành công (75,6 %)", chưa đạt mốc 80 %; bảng năm run, không có C70_R1; dòng "M đến từ đâu" (C_70 tới bàn B 50/60 nhưng đặt đúng 10/60; đồ gá jig2, dữ liệu bước đặt, 100 000 bước); "Lưu ý" chỉ đặt cạnh nhau, chưa có run đối chứng K |
| `tray-jig-r1` | Phân tích sâu | So sánh run M với các run vòng 1 trên 60 lượt: thành công, nới ≤ 7,5/10/15/20 cm, tới bàn B và độ lệch | Bảng có số lượt và phần trăm, M 47/60 (78,3 %), tới bàn B 60/60; bảng độ lệch p50/p90; biểu đồ cột; "M khác cảnh (jig2) và bộ chấm (bản 2), chỉ đặt cạnh nhau; ba lượt lặp của M: 42–47/60" |
| `tray-r1` | Hỏi nhanh | Vòng 1 so với vòng đồ gá khác nhau thế nào? | Khác cảnh, tập eval, bộ chấm và số bước train nên "chỉ đứng cạnh nhau, không so sánh trực tiếp"; chưa có run đối chứng K |
| `tray-r1` | Hỏi nhanh | Vì sao run C_70 hỏng nhiều ở bước đặt? | 32/50 lượt thất bại là đặt lệch; tới bàn B 50/60 nhưng đặt đúng 10/60; "nguyên nhân… chưa được kiểm tra… phỏng đoán". Không còn khuyên đóng phiếu DA-38, DA-37 (đã đóng) |
| `tray-r1` | Hỏi nhanh | Tổng chi phí cả dự án là bao nhiêu? | Ước tính và đo được tách riêng, không cộng gộp; dòng "Thí nghiệm khác (không trình bày)" |
| `tray-r1` | Hỏi nhanh | Trong vòng 1, run nào có số lượt thành công cao nhất? | "C_70 có số lượt thành công cao nhất: 10/60 (16,7 %)"; bảng bốn run, không có C70_R1; "khoảng tin cậy của bốn run chồng lấp… chưa thể phân biệt" |

**Lưu ý khi quay:** hỏi "Run nào tốt nhất?" khi ô "Vòng" đang là `tray-r1` thì trợ lý vẫn dẫn bằng run M của vòng đồ gá (kết quả trình bày mới nhất), không còn trả lời "C_70 cao nhất 10/60" như bản 0.2. Muốn nói riêng về vòng 1 thì dùng câu "Trong vòng 1, run nào có số lượt thành công cao nhất?" ở bảng trên.

## 3. Trình duyệt

- [ ] Mở một tab mới sau khi bật server. Tab cũ có thể còn giữ file JS của bản trước dù server trả `no-store`.
- [ ] Ngôn ngữ VI, nền sáng, zoom 125 % ở màn 1920×1080 như kịch bản 17/11.
- [ ] **[Đã chốt]** (Hiếu, tối 28/11/2026, thay quyết định sáng cùng ngày) Vòng mặc định là `tray-jig-r1` (run M, kết quả trình bày mới nhất). Trang Tổng quan có lối nối hai chiều giữa hai vòng: muốn kể vòng 1 tìm ra lỗi bước đặt thì bấm lối "Vòng trước", rồi quay lại vòng đồ gá.
- [ ] Trang Đánh giá của vòng đồ gá có bảng "So sánh 60 lượt: run M (lượt 0) và bốn run vòng 1" và biểu đồ cột đi kèm. Bảng rộng: ở zoom 125 % kiểm cả năm cột hiện hết hoặc cuộn ngang trước khi quay.
- [ ] Trang Dữ liệu có "Tập train run M · 4 phần, lọc ≤ 3 cm, ≤ 5° (1037)" và chuỗi nguồn gốc bốn phần → M → Run DA-48.
- [ ] Mở sẵn mỗi trang một lần ở cả hai vòng để video và ảnh vào bộ đệm, ít nhất `#/tasks`, `#/report`, `#/eval`, `#/diagnose`, `#/loop`, `#/cost`, `#/sim`.

## 4. Không được lộ trên màn hình

- [ ] Kết quả thi lại của C70_R1. Web và chat chỉ nói "Kết quả thi lại của lượt này không trình bày ở bản demo." Tên C70_R1 chỉ được hiện ở tiến độ train và tên bản cắt dữ liệu.
- [ ] Run N, story DA-50, phiên `da50-*`, thư mục `jig-n*`. Trên trang Chi phí, phần này nằm trong dòng "Thí nghiệm khác (không trình bày)". Hỏi trợ lý thì nó trả lời "Trong dữ liệu trình bày ở bản demo không có tập dữ liệu hay run nào như vậy."
- [ ] Terminal, `.env`, đường dẫn máy, tài khoản W&B hay Colab, token, email.
- [ ] Câu chữ cũ đã đổi ngày 28/11/2026. Nếu lời nói của kịch bản 17/11 còn những câu này thì sửa trước khi quay:
  - "Bản tốt nhất là bản gốc C_70": nay nói "C_70 cao nhất 10/60, các khoảng chồng nhau".
  - "đạt" dùng cho số lượt thành công: nay "đạt" chỉ dùng khi cận dưới của CI vượt mốc.

## 5. Chưa kiểm ở lượt này

- Lời nói từng cảnh của kịch bản 17/11 so với trang mới, nhất là thứ tự cảnh: kịch bản còn đi vòng 1 trước.
- Bản tiếng Anh của từng trang.
- Phát video ở `#/follow` và trình xem 180 rollout của run M khi khóa.
