# Flywheel Console · một website cho đội và người ngoài

| Ngày | Phiên bản | Nội dung | Người viết |
|---|---|---|---|
| 15/11/2026 | 0.2 | Đổi từ "chế độ khách" sang một website duy nhất (phương án A, Hiếu chốt 15/11 sau phân tích của Fable 5.2): 6 trạm là menu chính, phần giải thích gắn vào trang kỹ thuật hiện có, cờ `--lock` cho ngày demo. Sửa số liệu theo lượt soát của Fable (cụm c1, bốn đối chứng, phễu bước, 606 hai nghĩa, câu chữ). Ghi các sửa số đã làm trên Console (mục 9) | Hiếu (soạn với Claude) |
| 15/11/2026 | 0.1 | Bản "chế độ khách" (`--guest`, trang khách riêng); bị thay bởi 0.2 | Hiếu (soạn với Claude) |

Thiết kế này sửa [BA Flywheel Console bản 0.5](2026-11-11-flywheel-console-design.md): đổi kiến trúc thông tin (mục 7 của BA) và quy tắc giới hạn chữ (15.1b của BA). Nhãn quyết định theo [docs/CLAUDE.md](../../CLAUDE.md).

## 1. Ý định

Ngày 17/11/2026, Hiếu mang laptop tới DENSO Factory Hacks. Người xem tự mở Console và tự bấm. Họ không biết về robot learning, nhưng phải hiểu được toàn bộ ý tưởng: robot học từ dữ liệu; khi robot hỏng, hệ thống biến chỗ hỏng thành dữ liệu mới, có đối chứng, và dừng theo luật viết trước.

Console hiện tại làm cho AI Engineer (BA 15.1b): nhãn tối đa ba từ, không có câu giải thích. Hiếu đánh giá 15/11: "rất khó hiểu và không có ý nghĩa gì cả" với người ngoài. Trang Datasets hiện 60 dòng theo id, người xem không thấy có ba loại dữ liệu.

Lời của Hiếu ngày 15/11:

- Người xem "tự mở, tự bấm", trên laptop của Hiếu. **[Đã chốt]**
- Có nút chuyển Việt/Anh. **[Đã chốt]**
- Dữ liệu phải có cả synthetic trong mô phỏng và egocentric của người, theo kiểu Egocentric Explorer. **[Đã chốt]**
- Bản đồ 6 trạm, mỗi trạm một trang, mở đầu bằng "Theo chân một lỗi" (bản phác 2 "đúng theo ý tôi"). **[Đã chốt]**
- "Tôi không muốn chia chế độ đâu, vì có thể nó cũng là website tôi dùng lâu dài luôn". Chọn phương án A. **[Đã chốt]**
- Hiếu giao toàn bộ cách làm cho người viết. **[Đã chốt]**

## 2. Mục tiêu, không mục tiêu, phản mục tiêu

**Mục tiêu**

1. Một website, một menu, một bộ trang, dùng lâu dài cho cả đội lẫn người ngoài.
2. Người ngoài ngành tự bấm khoảng 5 phút là kể lại được: robot học từ đâu, hỏng ở đâu, hệ thống làm gì với chỗ hỏng, kết quả ra sao.
3. Thấy và mở được ba nguồn dữ liệu (video người, teleop, mô phỏng), mỗi nguồn có video thật.
4. Nút VI/EN cho cả website.
5. Ngày demo người xem không làm hỏng được gì trên laptop.

**Không mục tiêu**

- Dịch hết bảng số liệu kỹ thuật trước 17/11. Tên cột giữ thuật ngữ tiếng Anh ngắn ở cả hai ngôn ngữ; dịch thân trang để sau.
- Viết lại các trang kỹ thuật. Chúng giữ nguyên, chỉ được gắn phần giải thích ở đầu.
- Chạy job, train hay eval mới cho demo.

**Phản mục tiêu**

- Một con số sai, cộng trùng, hoặc không lần được về file.
- Nói quá kết quả. Vòng Failure → Data đầu tiên **không** làm robot tốt lên: `C70_R1` 4/60, thấp hơn `C_70` 10/60; luật viết trước bảo dừng (F).
- Hình gây hiểu lầm, ví dụ ảnh một bài sinh của planner chú thích "robot đặt khay lệch".
- Bản sao số liệu thứ hai (trang khách riêng) để rồi lệch với trang kỹ thuật.
- Dữ liệu rời laptop: API hosted, CDN lúc chạy, đăng ảnh EgoDex (CC-BY-NC-ND) ra ngoài.

## 3. Ràng buộc

- Mọi ràng buộc của [CLAUDE.md gốc](../../CLAUDE.md), nhất là video egocentric chỉ phục vụ bản đã che mặt (`*.deid.mp4`), trừ mẫu EgoDex có pin; không đọc `vault/`; không commit `fwdata/`.
- Laptop có thể không có mạng. Mọi thư viện JS nằm trong `web/vendor/`, kể cả `three.js` của Egocentric Explorer (mục 11).
- Chat dùng Nemotron qua đường hầm SSH tới `rtx3060` (BA 15.1b); ở hội trường đường hầm có thể đứt.
- Số lấy từ file của `fwdata/` qua indexer; số chỉ có trong tài liệu thì vào `seed/cited.yaml` kèm câu trích nguyên văn.
- Thời gian: còn hai ngày, một người làm. Thứ tự ở mục 8.

## 4. Các cách đã cân nhắc

**Vòng 1 (cách dẫn người xem).** A một trang cuộn theo chương; **B bản đồ 6 trạm, mỗi trạm một trang**; C theo chân một lần hỏng. Hiếu chọn B, lấy phần mở đầu của C.

**Vòng 2 (một hay hai website).** Bản 0.1 làm B thành "chế độ khách" riêng. Hiếu không muốn chia chế độ. Fable 5.2 phân tích ba cách gộp:

| | Cách | Người xem, 60 giây đầu | Đội, hằng ngày | Công đến 17/11 | Rủi ro |
|---|---|---|---|---|---|
| **A** | **6 trạm là menu cho mọi người; mỗi trang kỹ thuật thành thân của một trạm, dưới một phần giải thích** | Trang Bắt đầu, bản đồ 6 trạm; bấm đâu cũng gặp câu hỏi và câu trả lời trước | Vẫn các trang cũ, xếp lại theo trạm; gập phần giải thích | Vừa | Thân trang vẫn dày dưới phần giải thích |
| B | Một menu có hai mục "Câu chuyện" và "Bàn làm việc" | Tốt khi còn ở mục Câu chuyện | Không đổi | Nhiều nhất: 8 trang mới | Số bị chép hai nơi; người xem vẫn lạc sang Bàn làm việc |
| C | Giữ menu cũ, thêm lớp hướng dẫn | Vẫn 60 id và thuật ngữ | Không đổi | Ít nhất | Không giải quyết "không có ý nghĩa" |

Hiếu chọn **A** (15/11). Lý do: phần giải thích và việc thật nằm trên cùng một trang, cùng một số liệu, nên dùng lâu dài được; và rẻ, vì code đã có sẵn 6 khâu `collect`, `process`, `release`, `train`, `eval`, `loop` (`STRIP` trong `app.js`, `ring.js`). **[Đã chốt]**

## 5. Một website cho cả hai nhóm

### 5.1 Menu và route

Sidebar mới: **Bắt đầu** · **1 Thu dữ liệu** · **2 Xử lý và kiểm định** · **3 Đóng gói** · **4 Dạy Ψ₀** · **5 Thi** · **6 Lỗi → Dữ liệu** · **VẬN HÀNH** (Jobs, Máy, Chi phí).

Mọi hash cũ giữ nguyên, để bảng lệnh ⌘K, ngữ cảnh của chat và test còn chạy.

| Route hiện có | Trạm | Đổi gì |
|---|---|---|
| `home` (+ `overview`) | Bắt đầu | Khung "Theo chân một lỗi" và bản đồ 6 trạm thay vòng 9 khâu; ô KPI, danh sách ATTENTION, dòng thời gian job chuyển xuống dưới, mục "Hôm nay" |
| `data` | 1 | Ba thẻ nguồn ở trên; danh mục bên dưới, nhóm theo ba loại |
| `data/:id`, `data/:id/ep/:n` | 1 | Chỉ phần giải thích ngắn và đường dẫn trạm |
| `/ego/`, mới `sim`, `sim/:i` | 1 | Hai thư viện, mở từ thẻ nguồn |
| `jobs?view=pipeline` (+ `process`) | 2 | Phần giải thích; nút chạy giữ nguyên |
| `qa` (+ `agent`) | 2 | Phần giải thích |
| `jobs?panel=export` (+ `data/xuat`) | 3 | Phần giải thích và thẻ bản cắt (`S70`, `ALL`, `C70_R1` kèm sha256) |
| `jobs?panel=import` (+ `data/nhap`) | Vận hành | Không |
| `runs` (+ `training`) | 4 | Phần giải thích có lưới thí nghiệm 2 × 2 + 1 |
| `eval` | 5 | Phần giải thích có bảy bước bằng lời thường |
| `loop` | 6 | Phần giải thích có bảng 23/37 với đối chứng |
| `loop?tab=cost` | Vận hành · Chi phí | Không |
| `jobs`, `jobs?view=machines` | Vận hành | Không |
| mới `follow` | Từ khung trên trang Bắt đầu | 5 màn (mục 6.7) |

### 5.2 Phần giải thích

- Mỗi trang trạm mở bằng một phần giải thích: câu hỏi làm tiêu đề, một câu trả lời, một hình, tối đa ba con số có nguồn, "chỗ có thể sai và cách đội kiểm", nút trạm trước và trạm sau.
- Phần này được chèn một lần trong `route()` từ một bảng route → trạm, không phải sửa từng trang.
- Mặc định mở. Nút "Giải thích" trên thanh trên gập hoặc mở lại, nhớ bằng `localStorage` (bọc `try/catch`). Đây là tùy chọn hiển thị như nút sáng/tối, không phải chế độ: cùng route, cùng menu, cùng dữ liệu, không ẩn trang nào.

### 5.3 An toàn trên laptop

Server chỉ nghe `127.0.0.1`, nên rủi ro là một cú bấm tò mò, không phải tấn công.

1. **Cờ `fw console serve --lock`.** Giao diện và menu không đổi. Server trả 403 cho mọi POST (`/api/jobs`, `/api/jobs/<id>/cancel`, `/api/upload`, `/api/chat`, `/api/models/*`), và cho các GET lộ thứ nội bộ: `/api/fs`, `/api/dir_check`, `/api/tool`, `/api/exports/<zip>`. `/api/status` báo `locked`. Nút ghi hiện ổ khóa và bị tắt. Khung chat hiện "offline", đúng trạng thái nó đã có khi đường hầm đứt. Cờ này là quyền (như bản sao chỉ đọc của một cơ sở dữ liệu), không đổi trang hay menu. **[Đề xuất]**
2. **Hộp xác nhận** trước khi chạy, hủy hoặc xuất job, luôn có, kể cả khi không khóa. Đội cũng cần.
3. **Ẩn đường dẫn máy** trong dòng lệnh của job khi hiển thị.

Trang Training đang gọi `/api/tool` (`run_list`, `run_metrics`). Khi khóa, trang dùng dữ liệu của `story.json`, đã có sẵn đường lùi này trong `loadLive`.

### 5.4 Hai ngôn ngữ

- Phạm vi trước 17/11: menu, thanh trên, phần giải thích của mọi trạm, trang Bắt đầu, Theo chân một lỗi, thư viện mô phỏng. Bảng kỹ thuật giữ tên cột tiếng Anh ngắn.
- Chuỗi nằm trong `web/i18n/vi.js` và `web/i18n/en.js`, gọi qua `t(key)`; chỗ điền số dùng `{n}`. Lựa chọn lưu ở `localStorage` và `?lang=en`; mặc định tiếng Việt; cập nhật `<html lang>`.
- Số định dạng theo ngôn ngữ (`Intl.NumberFormat`). Hiện hai bộ định dạng đang lệch: `fmt` cũ dùng `vi-VN` ("2.572"), `UI.fmt` dùng `en-US` ("2,572"). Gộp về một hàm theo ngôn ngữ đang chọn.
- Test: hai file cùng tập khóa; mọi `t("…")` có khóa.

### 5.5 Giới hạn chữ

- `budget.py` giữ nguyên cho các file `pages_*.js`, `app.js` và các file đang có: nó vẫn giữ thân trang kỹ thuật gọn.
- Thêm luật cho từ điển: câu dẫn tối đa 30 từ, cả phần giải thích của một trang tối đa 90 từ. Đây là sửa BA 15.1b; cần một dòng change log ở BA. **[Đề xuất]**

## 6. Nội dung từng trạm

Chữ dưới đây là nội dung; người làm chuốt lại khi viết từ điển.

### 6.0 Bắt đầu

- Khung "Theo chân một lần robot hỏng" với hình lượt hỏng (mục 6.7), nút "Đi theo lỗi này →".
- Một câu bài toán: đội dạy robot hình người **Unitree G1** mang khay linh kiện từ bàn A sang bàn B, bằng model **Ψ₀** của nhóm tác giả, trong mô phỏng.
- Bản đồ 6 trạm thành vòng, mũi tên từ trạm 6 về trạm 1; mỗi trạm một số chính từ chỉ mục; trạm 6 tô màu nhấn.
- Bên dưới, mục "Hôm nay" cho đội: ô KPI, ATTENTION, job 24 giờ (như trang Tổng quan hiện tại).

### 6.1 Trạm 1 · Thu dữ liệu: "Robot học từ đâu?"

Ba thẻ nguồn, mỗi thẻ có video thật, số lượng, một dòng lợi và giá, nút mở thư viện:

| Nguồn | Số (từ chỉ mục) | Thư viện |
|---|---|---|
| Video người làm (egocentric) | 379 clip: 218 EgoDex, 153 đội quay 480p, 8 đội quay 1080p | Egocentric Explorer ở `/ego/` |
| Người điều khiển robot (teleop) | 99 lượt hai bàn của tác giả Ψ₀ (việc gắp vật, không phải mang khay); thêm 94 lượt "hug container" | Thư viện mô phỏng, nhóm teleop |
| Máy tự sinh trong mô phỏng | S1: 1 032 tập riêng (541 kho + 229 nhắm lỗi vòng C+ + 262 nhắm lỗi vòng C70); S2: 125 tập gốc và 843 biến thể (video nằm trên `rtx3060`) | Thư viện mô phỏng |

Số trong bảng trùng với tổng "tập riêng" của trang Datasets (mục 9.1), cùng một nguồn.

Thanh "lần dạy gần nhất dùng gì": bản cắt `C70_R1` 606 tập, chia theo `flywheel.purpose` và release:

- 301 tập phủ rộng (`coverage`);
- 124 tập nhắm lỗi của vòng trước (C+);
- 181 tập nhắm lỗi của vòng này (chọn từ release `tray_s1_868cc130985d`).

Các dòng egocentric đang dùng đều ghi `data_class: public` trong catalog (đã soát 15/11), nên không cần lọc như `?demo=1` cũ. Thẻ EgoDex ghi nguồn và licence.

### 6.2 Trạm 2 · Xử lý và kiểm định: "Làm sao biết một bài mẫu dùng được?"

- Video người: che mặt → đo tư thế hai bàn tay → chia bước → kiểm tự động. 379 clip → 317 xuất, 54 bị loại khi kiểm, 8 bị loại trước khi kiểm (`story.h1m.decisions`). Lý do loại hàng đầu, mỗi lý do kèm một clip ví dụ (`story.reasons`).
- Mô phỏng: lô nhắm lỗi vòng này 290 lượt sinh → 262 ghi được → 261 qua QA → 204 qua lọc chất lượng (nghiêng ≤ 10°, xê dịch ≤ 20 mm) → chọn 181 (`story.round.chain`, tray.md 20.16).
- Agent QA/QC: bộ kiểm được thử bằng bản sao có lỗi cấy (bench 99 tập, 33 lỗi cấy). Chỉ hiện điểm, không hiện đáp án.

### 6.3 Trạm 3 · Đóng gói: "Vì sao phải đóng băng dữ liệu?"

- Muốn so hai lần dạy cho công bằng thì dữ liệu mỗi lần phải cố định, kiểm được từng byte.
- Thẻ bản cắt có sha256 (8 ký tự đầu), số tập, định dạng LeRobot v2.1. Ghi nhãn rõ: `ALL` = 606 tập (kho + nhắm lỗi C+); `C70_R1` cũng 606 tập nhưng là `S70` (425) + 181 nhắm lỗi vòng C70. Hai số 606 là hai bộ khác nhau.
- `S70` dùng y nguyên từng byte cho `C_70` và `C70_R1`.

### 6.4 Trạm 4 · Dạy Ψ₀: "Đội dạy robot thế nào?"

- Ψ₀ là model có sẵn của nhóm tác giả; đội dạy thêm (fine-tune) trên dữ liệu mang khay, mỗi lần 60 000 bước.
- Lưới thí nghiệm 2 × 2 + 1. Hàng: model nhìn (VLM) gốc (`C`) hay VLM đã xem video người của đội (`B`). Cột: `ALL` (606) hay `S70` (425, 70 %). Ô thứ năm: `C70_R1`.
- Hai câu hỏi: "Cho robot xem video người có giúp không?", "Nhiều dữ liệu hơn có giúp không?". Trả lời ở trạm 5.
- Đường loss của 5 run chính (mục 9.2).

### 6.5 Trạm 5 · Thi: "Robot làm được bao nhiêu?"

- Bài thi: 60 lượt, 2 mức khó × 30 vị trí khay, giống nhau cho mọi run.
- Bảy bước bằng lời thường: tới bàn A, cầm khay, nhấc lên, mang sang, tới bàn B, đặt xuống, buông tay và đứng. Lượt đạt khi khay nằm trong ô đích: lệch ≤ 5 cm và xoay ≤ 10°.
- Hình "tỉ lệ qua từng bước", không gọi là phễu: bộ chấm chấm từng bước riêng và chấm "đạt" theo tư thế khay, nên cột cuối có thể khác số đạt (`C_70` 10 đạt, bước cuối 9; `C_ALL` 5 và 4; `B_ALL` 6 và 4). Có 4 lượt đạt mà bước "tới bàn B" ghi trượt. Trang ghi chú điều này (mục 9.3).
- Bảng 5 run: số đạt trên 60, khoảng tin cậy, nói bằng lời "10/60, khoảng 1 trên 6 lượt".
- Trả lời hai câu hỏi của trạm 4 theo luật đọc: chưa có bằng chứng ở cỡ này (F không phải bằng chứng là không giúp).

### 6.6 Trạm 6 · Lỗi → Dữ liệu: "Robot hỏng thì làm gì?"

1. **Kiểm hệ thống trước.** Độ trễ, đồng bộ, camera: đạt ở chỗ đo được. Hai cụm (c4, c5) thiếu tín hiệu đo và chỉ báo cáo.
2. **Gom lỗi thành cụm** theo bước hỏng và mức khó. Ví dụ cụm c1 "đặt khay, mức 1": 14 lỗi, 10 lỗi nhận dữ liệu (tối đa 10 mỗi cụm).
3. **Chẩn đoán**: kỹ năng yếu (sinh dữ liệu có thể giúp), không khả thi, hay ngoài miền. Chỉ "kỹ năng yếu" nhận dữ liệu.
4. **Sinh bài nhắm lỗi**: 23 lỗi → 290 lượt sinh → 181 tập chọn, theo luật chọn commit trước khi sinh.
5. **Dạy lại, thi lại**: `C70_R1` 4/60.
6. **Luật viết trước**: kết quả F, dừng.

Bảng so trên 23 tình huống đã nhắm và 37 tình huống còn lại (`r3.json`, đã soát 15/11):

| | 23 tình huống nhắm lỗi | 37 còn lại | Tổng |
|---|---|---|---|
| `C_70` (trước vòng) | 0 | 10 | 10/60 |
| `C70_R1` (sau vòng) | 2 | 2 | 4/60 |
| `C_ALL` (đối chứng) | 1 | 4 | 5/60 |
| `B_70` (đối chứng) | 2 | 5 | 7/60 |
| `B_ALL` (đối chứng) | 3 | 3 | 6/60 |

Đối chứng là phần bắt buộc. 23 tình huống được chọn vì `C_70` hỏng ở đó, nên số 0 của `C_70` thấp sẵn; mỗi tình huống thử một lần.

Câu kết: vòng đầu **chưa** cho thấy dữ liệu nhắm lỗi sửa được gì. Mức tăng ở tình huống đã nhắm nằm trong mức các run đối chứng cũng đạt, còn tổng thể kém đi (10/60 → 4/60). Phép so có đối chứng thấy điều đó, và luật viết trước đã cho dừng thay vì đổ thêm dữ liệu. Không viết "dữ liệu nhắm lỗi đã sửa được lỗi", cũng không viết "vòng lặp tự biết…" (mới một vòng, mỗi điều kiện một lần thử).

### 6.7 Theo chân một lỗi (`#/follow`)

Một lượt thi thật: **mức 1, seed 1000107**. Năm màn, có nút "Tiếp" và liên kết tới trạm.

| Màn | Nội dung | Nguồn |
|---|---|---|
| 1 Hỏng | `C_70` mang khay tới bàn B nhưng đặt lệch 7,0 cm và xoay 16,3° (cho phép 5 cm, 10°) | `place-error-C_70.json` |
| 2 Chẩn đoán | Cụm c1 "đặt khay, mức 1": 14 lỗi, 10 nhận dữ liệu, chẩn đoán kỹ năng yếu. Dữ liệu của `C_70` đã có 1 tập nhắm đúng tình huống này từ vòng trước (tập 367, `place-pose-L1-1000107`), vẫn hỏng | tray.md 20.13 qua `cited.yaml`; `episodes.jsonl` |
| 3 Sinh dữ liệu | Planner sinh 6 tập quanh đúng tình huống này; bấm xem video từng tập | `episodes.jsonl` của `C70_R1.tar`, `cluster_id` `place-L1-1000107`, tập 449, 450, 481, 511, 541, 571 |
| 4 Thi lại | Cùng lượt, cả năm run: `C70_R1` đạt (1,0 cm, 3,7°); `B_ALL` đạt (4,0 cm, 7,5°) dù không nhận dữ liệu vòng này, và bộ chấm ghi lượt đó trượt bước "tới bàn B"; `C_ALL`, `B_70` hỏng. Câu dẫn: "đạt một lần chưa chứng minh được gì; phải nhìn cả bài thi" | `place-error-*.json` |
| 5 Tổng thể | 60 lượt: 4/60 (trước 10/60). Bảng 23/37 có đối chứng. Luật viết trước: dừng | `story.pair`, `r3.json` |

Màn 4 và 5 là chỗ quan trọng nhất; không được bỏ.

**Hình lượt hỏng.** File chỉ ghi độ lớn của độ lệch và góc xoay, không ghi hướng. Hình gồm ô đích, vòng bán kính 5 cm (cho phép), vòng bán kính 7,0 cm có chú thích "khay dừng đâu đó trên vòng này; hướng không được ghi", và cung góc 16,3° so với giới hạn 10°. Màn 4 dùng cùng kiểu hình.

## 7. Thư viện mô phỏng (`#/sim`)

Theo khuôn Egocentric Explorer: Thư viện ảnh · Chất lượng · Tất cả tập · trang một tập.

**Chỉ mục.** `index/sim.py` đọc `meta/episodes.jsonl` trong `C70_R1.tar` bằng `tarfile` (không giải nén 5,3 GB). Trường cần dùng nằm trong `environment_config` (chuỗi JSON): `flywheel.purpose`, `flywheel.cluster_id`, `flywheel.seed`, `flywheel.level`, `tray.sample.tray_pose`, `tray.sample.target_pose`, `tray.sample.robot_spawn`, `tray.report.steps`. Ghi `sim.json` vào thư mục chỉ mục.

**Mẫu video.** Trích khoảng 40 video và ảnh đại diện (`cv2`) ra `fwdata/console/media/sim/<8 ký tự đầu sha256 của tar>/`: 6 tập của seed 1000107, tập 367, khoảng 16 tập phủ rộng và 16 tập nhắm lỗi rải theo cụm, chọn bằng seed cố định; thêm 8 lượt teleop từ zip của psi-data. Lần dựng sau thấy file đã có thì bỏ qua. Server thêm `GET /simmedia/` có Range 206 và bộ chặn đường dẫn của `paths.py`.

**Trang.**

- Thư viện ảnh: lưới có nhãn màu "phủ rộng", "nhắm lỗi vòng trước", "nhắm lỗi vòng này", "teleop"; lọc theo nhãn và mức; di chuột thì video chạy.
- Chất lượng: chuỗi sinh → ghi → QA → lọc → chọn; lỗi của planner theo nhãn (`batch_summary.json`).
- Tất cả tập: bảng 606 dòng.
- Một tập: video; hình nhìn từ trên với khay lúc đầu, ô đích, robot (tư thế thật trong `tray.sample`); 7 bước của planner; với tập nhắm lỗi thì "sinh cho lượt thi mức N, seed S" và vòng nào. Tập có `cluster_id` kết thúc bằng `L1-1000107` liên kết sang Theo chân một lỗi.

## 8. Thứ tự làm đến 17/11

| # | Việc | Xong khi |
|---|---|---|
| 1 | `--lock`, nút bị khóa, hộp xác nhận | Test 403 cho mọi POST và các GET nội bộ |
| 2 | `t()`, nút VI/EN, khung phần giải thích, menu theo trạm | Đổi ngôn ngữ, gập/mở, mọi route cũ vẫn mở |
| 3 | Trang Bắt đầu: bản đồ 6 trạm, khung Theo chân một lỗi, mục Hôm nay | |
| 4 | Trạm 1: ba thẻ nguồn; `sim.py`, `/simmedia/`, thư viện ảnh | Rủi ro lịch lớn nhất |
| 5 | `follow` | Năm màn với số thật |
| 6 | Phần giải thích trạm 5, 6 | Số khớp `story.pair`, `r3.json` |
| 7 | Phần giải thích trạm 2, 3, 4 (chữ, ít hình) | |
| 8 | Chép `three.js` cho `/ego/` | Tắt mạng vẫn xem được tư thế tay |
| 9 | Kiểm cả hai ngôn ngữ, tắt mạng, 1 366 × 768 và 1 920 × 1 080 | Không lỗi console |

**Đường cắt** nếu trễ: thư viện mô phỏng chỉ có thư viện ảnh, chưa có trang một tập; trạm 2–4 chỉ có chữ.

**Sau demo:** dịch thân trang kỹ thuật; trang một tập; video S2; chi phí (chờ PR #200); bỏ `?demo=1`, `tour.js`, `ring.js` (chế độ cũ). Bộ chấm 7 bước (mục 9.3) nên xem lại ở gói eval.

## 9. Sửa số đã làm trên Console (15/11, chưa commit)

1. **Đếm trùng tập.** Trang Datasets cộng số tập của cả 60 dòng catalog ("9 007"), trong khi bản xử lý, bản xuất, bản cắt lặp lại tập của dòng cha. Indexer nay gắn `unique` cho dòng mang dữ liệu mới (`raw source` hoặc `release`, đang dùng, ngoài eval) và ghi `totals` theo nhóm. Trang Datasets: 2 572 tập riêng; ô S1 trang Tổng quan: 1 032 (trước là 2 441); nút Nguồn: 2 572 tập. Biểu đồ tập theo loại chỉ cộng dòng gốc.
2. **Catalog thiếu hai dòng**: release vòng C70 `tray_s1_868cc130985d` (262) và bản cắt `C70_R1` (606, tar trên laptop). Đã thêm, catalog 62 dòng.
3. **Training**: bỏ `C70_R1.attempt1`; hai run 40k (C, C+) ẩn sau nút "40k". Còn 5 run.
4. **Eval**: cột "p" của bảng Evals đổi thành "rate", của bảng Compare thành "p McNemar"; hình bước đổi tên "Step pass %"; dấu ⚠ cạnh run có số đạt khác bước cuối (tooltip ghi hai số).

Kiểm: 166 test qua, `ruff`, `mypy`, `lint-imports` sạch; đã xem trên trình duyệt các trang Datasets, Tổng quan, Training, Eval.

## 10. Kiểm tra

- Test CPU: `sim.py` trên tar nhỏ dựng trong test; `--lock` trả 403 đúng danh sách; từ điển cùng khóa; luật chữ mới của từ điển; test hiện có (giới hạn chữ, số cấm trong `pages_story.js`, sankey, không CDN, không đường dẫn máy) vẫn qua.
- Trình duyệt: mọi route, VI và EN, tắt mạng, hai cỡ màn.
- Số: mỗi số trên phần giải thích có trong chỉ mục hoặc `cited.yaml`; một lượt soát tay với file nguồn ở mục 6.

## 11. Khớp với code hiện tại

Đường dẫn tính từ `packages/flywheel-console/src/flywheel/console/` (`PK`).

| Việc | Chỗ |
|---|---|
| Bảng route → trạm, chèn phần giải thích | `web/app.js` `route()`; khung và nút trong file mới `web/explain.js` |
| Menu theo trạm | `SIDE` trong `app.js` |
| Trang Bắt đầu, `follow`, `sim`, `sim/:i` | File mới `web/pages_story2.js` hoặc tên `pages_*` khác, để test cấm mã màu hex quét nó |
| Từ điển | `web/i18n/vi.js`, `web/i18n/en.js`; nạp trước `app.js` trong `index.html` |
| `--lock` | `cli.py serve`; `server/app.py` (POST và GET bị chặn); `runner.status()` thêm `locked` |
| Chỉ mục | `index/sim.py` → `sim.json`; `index/story.py` thêm `r3` và các dòng seed 1000107 từ `place-error-*.json`; `seed/cited.yaml` thêm cụm c1 (14 lỗi, 10 nhận dữ liệu) kèm câu trích tray.md 20.13 |
| `three.js` cho `/ego/` | Chép `three@0.147.0` và `OrbitControls.js` (MIT) vào `web/vendor/three/`; server viết lại hai thẻ `<script>` khi trả `/ego/index.html`. Viewer trong `fwdata` không bị sửa |

Chú ý: `/media/<ds>/` chỉ phục vụ `ALL`, `S70`, mà thư mục của chúng (`fwdata/da34-dryrun/…`) không còn trên laptop; trang episode robot hiện không phát video được. Thư viện mô phỏng không dựa vào route này.

## 12. Để lại cho người làm

Bố cục, màu, chữ cụ thể trong từ điển (theo bản phác 2 và token màu đang có); cách chọn mẫu video, miễn cố định và rải đều; dùng lại thành phần nào của trang kỹ thuật.

## 13. Câu hỏi còn mở

1. Teleop bàn phím của đội: chưa thấy trong `fwdata/`.
2. Video S2 nằm trên `rtx3060`; thiết kế chỉ hiện số. Người viết không chạy gì trên `rtx3060` khi chưa được bảo.

## 14. Quyết định của người viết

Theo ủy quyền của Hiếu 15/11, cần soát khi duyệt:

1. Cờ `--lock` cho ngày demo (quyền, không phải chế độ); chat "offline" khi khóa.
2. Phần giải thích mặc định mở, gập được, nhớ theo trình duyệt.
3. Luật chữ riêng cho từ điển (30 từ một câu dẫn, 90 từ một trang); BA 15.1b giữ cho thân trang.
4. Bỏ bộ lọc `public` của `?demo=1` trên website chung (các dòng egocentric đang dùng đều `public`).
5. Hình lượt hỏng là vòng bán kính, không bịa hướng lệch.
6. Bốn sửa số ở mục 9, nhất là luật `unique` để đếm tập.
7. Video mẫu nằm ngoài thư mục chỉ mục, phục vụ qua `/simmedia/`.
