## Story

- Mã story: <!-- ví dụ DA-03 -->
- File story: <!-- docs/product/stories/DA-03-....md -->
- Issue: Closes #<!-- số issue -->

## Nhiệm vụ con trong PR này

<!-- Mỗi dòng ứng với một commit "<story-id>/<số>: ...". -->

- [ ] <!-- 1 · mô tả ngắn -->

## Phạm vi

- [ ] Diff chỉ chạm các đường dẫn trong mục "Phạm vi file" của story (`git diff --stat origin/master...`)
- [ ] Không đổi file dùng chung (`contracts/`, schema trong `configs/`, `pyproject.toml` gốc, `uv.lock`, `.github/workflows/`), hoặc đã có PR contract riêng: #<!-- số -->
- [ ] Đã rebase lên `origin/master` mới nhất
- [ ] Mỗi commit có dòng đầu `<story-id>/<số>: ...` và dòng `Time-spent: <giờ>h`; `scripts/repo/pr_guard.py` chạy qua tại máy

## Bằng chứng

<!-- Với mỗi tiêu chí chấp nhận: lệnh đã chạy và output, tên test, đường dẫn file số đo. Ghi rõ số nào là ước lượng, số nào là thực đo. -->

| AC | Bằng chứng |
|---|---|
| | |

## Kiểm tra đã chạy

- [ ] Test và lint của package bị sửa
- [ ] `python3 scripts/repo/check_links.py` (nếu sửa tài liệu)
- [ ] `python3 website/build.py` và `python3 website/verify.py` (nếu sửa website)

## Ghi chú cho người review

<!-- Chỗ cần xem kỹ, quyết định đã tự chốt, việc còn để lại. -->
