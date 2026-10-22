# CLAUDE.md · tài liệu

Áp cho mọi file trong `docs/`. Quy tắc chung của repo ở [CLAUDE.md gốc](../CLAUDE.md).

## Văn phong

- Tiếng Việt, câu ngắn, ý chính trước. Thuật ngữ theo glossary của spec mục 12; thuật ngữ mới thêm vào glossary.
- Bảng cho so sánh và danh sách có nhiều trường; đoạn văn cho lập luận.
- Đánh dấu nguồn của quyết định: **[Đã chốt]** (trưởng nhóm quyết), **[Đề xuất]** (người viết đề xuất, cần duyệt), **[Option]** (nhiều phương án song song).
- Số liệu của tác giả paper ghi rõ là số tác giả báo. Số liệu chưa đo ghi là giả định hoặc ước lượng.
- Ngày viết dạng `23/10/2026`; tên file dùng `YYYY-MM-DD`.

## Sửa tài liệu có phiên bản

Spec, 00–06 và design có bảng change log.

1. Tăng phiên bản theo thói quen của file (spec: v10.1 → v10.2; 03: 0.3 → 0.4).
2. Thêm một dòng change log ở đầu bảng: ngày, phiên bản, mục đã sửa, người sửa.
3. Ghi phần mới bằng nhãn phiên bản trong tiêu đề hoặc câu đầu (ví dụ "(v10.2)", "bản 0.4") để người đọc thấy chỗ đổi.
4. Sửa spec hoặc 03 cần quyết định của Product Owner (Hiếu).

## Liên kết

- Dùng đường dẫn tương đối giữa các file trong repo.
- Chạy `python3 scripts/check_links.py` trước khi commit; lệnh trả mã khác 0 nếu có liên kết hỏng.

## Story

File story nằm trong `docs/product/stories/`, đặt tên `<id>-<mô-tả>.md`. Story mới theo mẫu của story hiện có và thêm hai mục: "Người làm" trong bảng trạng thái, và "Phạm vi file" liệt kê đường dẫn story được sửa (07 mục 3.1).
