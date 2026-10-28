#!/usr/bin/env bash
# Create the labels of docs/product/07-team-workflow.md (section 3.5) and 08-daily-control.md (section 4).
# Run once from the repo root with an authenticated GitHub CLI: bash scripts/repo/setup_labels.sh
set -euo pipefail

label() { gh label create "$1" --color "$2" --description "$3" --force; }

for person in hieu hung chau long thong; do label "person:$person" c5def5 "Người làm"; done
for sprint in 1 2 3 4 5 6; do label "sprint:S$sprint" bfd4f2 "Sprint $sprint"; done
label area:core 1d76db "Lõi flywheel"
label area:adapter 5319e7 "Adapter"
label area:data 0e8a16 "Dữ liệu"
label area:docs 0075ca "Tài liệu"
label contract-change fbca04 "Đổi file dùng chung (07 mục 3.2)"

label type:bug d73a4a "Lỗi"
label type:incident b60205 "Sự cố severity:high, cần postmortem (R7)"
label severity:high b60205 "Sai kết luận, rò holdout, lộ hoặc mất dữ liệu, lỡ cổng"
label severity:medium e99695 "Chặn story hoặc tốn thêm 1-2 ngày"
label severity:low f9d0c4 "Cần sửa cho sạch"
for cause in spec-unclear contract env-gpu ai-generated review-miss test-gap data denso-wait; do
  label "cause:$cause" d4c5f9 "Nguyên nhân lỗi (08 mục 4)"
done
label size:large ededed "PR > 400 dòng (R9)"
label daily-report 0e8a16 "Báo cáo ngày tự động"
