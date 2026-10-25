# 08 · Kiểm soát dự án theo ngày

_Ngày 23/10/2026. Vai trò BMAD: Scrum Master cộng Product Owner. Trưởng nhóm duyệt dùng ngưỡng mặc định ngày 23/10/2026. Đầu vào: [04 · Kế hoạch](04-delivery-plan.md) (hệ số k, mục 4.8–4.9), [07 · Chia việc và quy trình git](07-team-workflow.md), quyết định 11.8 ở [06](06-review-round-1-decisions.md)._

| Ngày | Phiên bản | Thay đổi | Tác giả |
|---|---|---|---|
| 25/10/2026 | 0.2 | Theo [design ngày 25/10/2026](../superpowers/specs/2026-10-25-denso-mujoco-and-stage-qa-design.md) mục 10: Hiếu là người duyệt và merge duy nhất, R2 đổi hành động (mục 3.2); thêm lịch tracking tự động và tổng kết cuối ngày (mục 5, 7) | PO (Hiếu) |
| 23/10/2026 | 0.1 | Bản đầu: quy ước dữ liệu, chỉ số, 9 rule, phân loại lỗi, nhịp, sổ can thiệp, công cụ | SM, PO |

## 1. Mục đích và nguyên tắc

Mỗi ngày biết ba điều: đội đang đi nhanh hay chậm so với ước lượng, lỗi đang sinh ra ở đâu, và cần sửa quy trình chỗ nào. Cách làm là áp chính tinh thần Failure → Data cho quy trình của đội: thu tín hiệu tự động, phân loại lỗi theo nguyên nhân, và lỗi lặp lại thì sinh ra một can thiệp (rule, test, sửa CLAUDE.md) có ghi lại.

1. **Tự động trước.** Mọi chỉ số lấy từ git, file story và GitHub. Việc nhập tay duy nhất là dòng `Time-spent:` trong commit.
2. **Đo quy trình, không xếp hạng người.** Số liệu dùng để gỡ chặn và chỉnh kế hoạch, không dùng để so ai giỏi hơn. Một người k cao thường do story bị ước thấp hoặc bị chặn, không phải do làm chậm.
3. **Ngưỡng có thể chỉnh.** Ngưỡng ở mục 3 là mặc định; đổi ở review cổng, ghi change log ở đây và hằng số trong `scripts/daily_report.py`.

## 2. Quy ước dữ liệu đầu vào

| Nguồn | Quy ước | Ai giữ |
|---|---|---|
| Nhánh | `<story-id>-<mô-tả>` (ví dụ `DA-03-teleop-pipeline`), hoặc `docs-…`, `chore-…`, `hotfix-…` cho việc ngoài story | Người làm |
| Commit trên nhánh story | Dòng đầu `<story-id>/<nhiệm vụ con>: <việc đã làm>`; thân có dòng `Time-spent: 1.5h` (giờ tập trung thực, số thập phân) | Người làm |
| File story | Bảng trạng thái có `Người làm` và `Ước lượng` (giờ); mục `## Phạm vi file` liệt kê đường dẫn tính từ gốc repo, mỗi dòng một đường dẫn trong dấu backtick; nhiệm vụ con là dòng `- [ ]` | SM viết, người làm đánh dấu |
| Issue lỗi | Template "Lỗi"; label `type:bug` hoặc `type:incident`, một label `severity:*`, một label `cause:*` khi đã rõ nguyên nhân | Người phát hiện; người sửa gắn nguyên nhân |

Ví dụ commit:

```text
DA-03/2: Resample teleop state to control rate

AC 2: timestamps aligned within tau_sync on 40 psi-data episodes (pytest tests/ingest/test_sync.py).

Time-spent: 2.5h
```

## 3. Chỉ số và rule

### 3.1 Chỉ số

| Chỉ số | Cách tính | Nguồn |
|---|---|---|
| Nhiệm vụ con xong | Số commit `<story>/<số>:` vào `master` trong cửa sổ "hôm qua" (24 giờ; thứ Hai lấy 72 giờ), gán cho người làm của story | git |
| Giờ thực | Tổng `Time-spent` của các commit đó | git |
| Hệ số k của người, 7 ngày | Giờ thực ÷ giờ ước đã "kiếm được". Mỗi commit nhiệm vụ con kiếm được `Ước lượng của story ÷ số dòng - [ ] của story` | git, file story |
| Tiến độ story | Số `[x]` ÷ tổng số dòng nhiệm vụ trên `master` | file story |
| Story đứng yên | Story đã có commit nhưng chưa xong, không có commit mới trên bất kỳ nhánh nào trong N ngày làm việc | git (mọi nhánh) |
| PR chờ review | PR không phải bản nháp, chưa có review nào; tuổi tính bằng ngày làm việc | GitHub API |
| WIP | Số PR đang mở theo tác giả | GitHub API |
| Kích thước PR | Số dòng thêm cộng xóa, trừ lock file và fixture | GitHub API, git |
| CI `master` | Lần chạy gần nhất của mỗi workflow trên `master` khi push | GitHub API |
| Lỗi theo nguyên nhân | Số issue lỗi mở trong 7 ngày, theo label `cause:*` | GitHub API |

### 3.2 Rule

| # | Điều kiện | Phát hiện bởi | Hành động | Ai |
|---|---|---|---|---|
| R1 | CI trên `master` đỏ | Báo cáo ngày | Ngừng merge; người gây lỗi sửa trong 4 giờ hoặc revert | Người gây lỗi; Long theo dõi |
| R2 | PR chờ review quá 1 ngày làm việc | Báo cáo ngày, tracking tự động | Bản 0.2: Hiếu duyệt hoặc ghi lý do chờ dưới PR; tổng kết 21:30 xếp thứ tự duyệt, ưu tiên PR đang chặn người khác; quá 2 ngày thì nêu ở check-in. Không còn người review dự phòng | Hiếu; Thông |
| R3 | Một người có quá 2 PR đang mở | Báo cáo ngày | Không mở story mới tới khi về ≤ 2 | Người làm |
| R4 | Story đã bắt đầu, không có commit 2 ngày làm việc | Báo cáo ngày | Ghi vào issue của story đang bị chặn ở đâu; Thông gỡ hoặc báo Hiếu | Người làm; Thông |
| R5 | k của một người (7 ngày) > 1,3 | Báo cáo ngày | Xét chuyển phần trễ sang API theo từng phần (06 mục 11.8); nếu không chuyển được, ước lại story | Hiếu, Thông |
| R6 | PR sửa file ngoài "Phạm vi file", sai tên nhánh, commit sai định dạng hoặc thiếu `Time-spent` | `pr-guard` (chặn PR) | Sửa commit hoặc phạm vi; cần sửa file dùng chung thì theo 07 mục 3.2 | Người làm |
| R7 | Issue `severity:high` đang mở (rò holdout, gửi dữ liệu `restricted` ra ngoài, sai kết luận HS/HT/HD, mất dữ liệu) | Báo cáo ngày | Đổi thành `type:incident`; postmortem 1 trang trong 2 ngày, ghi vào mục 6 | Người phát hiện; Hiếu |
| R8 | Cùng một `cause:*` có ≥ 3 issue trong 7 ngày | Báo cáo ngày | Bắt buộc một can thiệp (rule, test, sửa CLAUDE.md hoặc template), ghi vào mục 6 | Thông chủ trì |
| R9 | PR > 400 dòng | `pr-guard` (gắn `size:large`), báo cáo ngày | Đề nghị tách story; không chặn | Người làm, người review |

Ngưỡng mặc định: k 1,3; chờ review 1 ngày làm việc; WIP 2; đứng yên 2 ngày làm việc; lặp nguyên nhân 3 lần trong 7 ngày; PR 400 dòng.

## 4. Phân loại lỗi

| Label | Nghĩa | Can thiệp thường gặp khi lặp lại |
|---|---|---|
| `type:bug` | Lỗi trong mã, dữ liệu hoặc tài liệu | — |
| `type:incident` | Lỗi `severity:high` đã xảy ra, cần postmortem | — |
| `severity:high` | Có thể làm sai kết luận HS/HT/HD, rò holdout, lộ dữ liệu, mất dữ liệu, lỡ cổng | — |
| `severity:medium` | Chặn một story hoặc tốn thêm 1–2 ngày | — |
| `severity:low` | Cần sửa cho sạch | — |
| `cause:spec-unclear` | Spec, design hoặc story mơ hồ, mâu thuẫn | Sửa tài liệu; thêm ví dụ vào AC |
| `cause:contract` | Đổi contract hoặc file dùng chung làm vỡ việc khác | Siết 07 mục 3.2; thêm contract test |
| `cause:env-gpu` | Môi trường, phiên bản, GPU, Isaac Sim, flash-attn | Ghim phiên bản; thêm bước vào runbook |
| `cause:ai-generated` | Mã do Claude sinh sai mà không ai bắt được trước merge | Thêm quy tắc vào CLAUDE.md; thêm test cho chỗ đó |
| `cause:review-miss` | Review bỏ sót | Thêm câu vào checklist PR |
| `cause:test-gap` | Thiếu test cho trường hợp đó | Thêm test; thêm vào DoD |
| `cause:data` | Dữ liệu sai, thiếu, lệch đồng bộ | Thêm phép kiểm QA (bảng F-DATA của design) |
| `cause:denso-wait` | Chờ thông tin từ DENSO, BTC, mentor | Nêu ở buổi với DENSO; dùng phương án thay thế (robot thay thế, dữ liệu công khai) |

Lỗi kỹ thuật của chính flywheel (D1–D8, T1–T8, O1–O4, R1–R6 ở design mục 7.2) là kết quả thí nghiệm, không phải lỗi quy trình; chúng nằm trong ledger và báo cáo vòng, không mở issue trừ khi do mã sai.

## 5. Nhịp

| Khi nào | Việc | Ai |
|---|---|---|
| 9:00 giờ Việt Nam, thứ Hai đến thứ Sáu | Workflow `daily-report` đăng báo cáo vào issue có label `daily-report`; trang Tiến độ trên website cập nhật | Tự động |
| Trước 10:00 | Mỗi người trả lời dưới báo cáo 3 dòng: **Xong**, **Tiếp theo**, **Bị chặn** | Cả đội |
| Trong ngày | Xử lý rule đã kích hoạt theo cột "Hành động" | Theo cột "Ai" |
| Thứ Sáu | Thông tổng hợp tuần: xu hướng k, top nguyên nhân lỗi, can thiệp mới ở mục 6, đề xuất chỉnh ngưỡng | Thông |
| 10:00, 14:00, 18:00 mỗi ngày (bản 0.2) | Tracking tự động trên máy của Hiếu (scheduled task `denso-tracking` của Claude desktop, chỉ đọc): chạy `daily_report.py`, `pr_guard.py` cho từng nhánh, liệt kê PR chờ Hiếu, ai bị chặn, vi phạm rule; ghi `~/denso-tracking/YYYY-MM-DD-HHMM.md` | Tự động |
| 21:30 mỗi ngày (bản 0.2) | Tổng kết cuối ngày (`denso-cuoi-ngay`): việc đã xong, PR chờ duyệt kèm thứ tự đề xuất, rủi ro, câu hỏi cần Hiếu quyết; Hiếu và Claude thảo luận | Tự động, Hiếu |
| Review mỗi cổng G | Xem lại ngưỡng và hệ số k của đội cho quyết định ở 04 mục 4.8–4.9 | Hiếu, Thông |

## 6. Sổ can thiệp

Mỗi lần R7 hoặc R8 kích hoạt, thêm một dòng. Đây là chỗ các "hướng phát triển thêm" của quy trình được ghi lại.

| Ngày | Rule | Nguyên nhân hoặc sự cố | Can thiệp | Đổi ở đâu | Kiểm lại sau 1 tuần |
|---|---|---|---|---|---|
| | | | | | |

## 7. Công cụ

| Công cụ | Làm gì | Ở đâu |
|---|---|---|
| `pr-guard` | Kiểm tên nhánh, định dạng commit, `Time-spent`, phạm vi file (R6); gắn `size:large` (R9) | `.github/workflows/pr-guard.yml`, `scripts/pr_guard.py` |
| `daily-report` | Tính chỉ số mục 3.1, kiểm R1–R5, R7–R9, đăng báo cáo vào issue | `.github/workflows/daily-report.yml`, `scripts/daily_report.py` |
| Trang Tiến độ | Hiển thị báo cáo ngày mới nhất: rule kích hoạt, theo người, PR, story | `website/dist/progress.html`; dữ liệu `data/progress.json` sinh khi build Pages |
| Label | Tạo đủ label ở mục 4 và 07 mục 3.5 | `bash scripts/setup_labels.sh` (chạy một lần, cần `gh` đã đăng nhập) |
| Tiến độ story tại máy | In tiến độ nhiệm vụ con theo story | `python3 scripts/progress.py` |
| Tracking và tổng kết cuối ngày (bản 0.2) | Đọc repo và GitHub, không đăng gì; báo cáo nằm trên máy của Hiếu | `~/.claude/scheduled-tasks/denso-tracking/`, `denso-cuoi-ngay/`; báo cáo ở `~/denso-tracking/` |

Chạy thử báo cáo tại máy (không có token thì bỏ qua phần GitHub API):

```bash
python3 scripts/daily_report.py
```

Kiểm một nhánh trước khi mở PR:

```bash
python3 scripts/pr_guard.py --base origin/master --head HEAD --branch "$(git branch --show-current)"
```

Việc Hiếu làm trên GitHub một lần: chạy `scripts/setup_labels.sh`; tạo một issue tiêu đề "Báo cáo ngày" gắn label `daily-report` (workflow tự tạo nếu chưa có); thêm `pr-guard` vào status check bắt buộc của luật bảo vệ `master`; trong Settings → Pages chọn nguồn GitHub Actions nếu chưa chọn.

## 8. Giới hạn

- k chỉ đúng khi mọi commit nhiệm vụ con có `Time-spent`; `pr-guard` chặn commit thiếu dòng này. Giờ của việc ngoài story (họp, DENSO, review) không vào k.
- Nhiệm vụ con được gán cho **người làm của story**, kể cả khi người khác commit giúp.
- Ước lượng mỗi nhiệm vụ con chia đều từ ước lượng của story; story có nhiệm vụ con lệch nhau nhiều thì k theo ngày dao động, nên nhìn trung bình 7 ngày.
- Ngày làm việc chỉ trừ thứ Bảy và Chủ nhật; ngày lễ chưa trừ.
- Báo cáo đọc tối đa 100 PR mở và 100 issue mới mỗi lần; đủ cho quy mô đội.
