#!/usr/bin/env bash
set -eu
project_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
# dist/ keeps only hand-written files in git; build.py writes the decks, figures and page data.
python3 "$project_dir/website/build.py"
echo 'Mở website: http://127.0.0.1:4175/#overview'
echo 'Giữ cửa sổ này mở khi xem website. Nhấn Ctrl+C để dừng.'
exec python3 -m http.server 4175 --bind 127.0.0.1 --directory "$project_dir/website/dist"
