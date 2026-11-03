"""Bản TS sinh ra còn khớp nguồn Python (DESIGN.md luật R3).

Quên chạy `uv run python -m web.contracts.generate_ts` sau khi sửa `enums.py`
là lỗi im lặng tệ nhất của thiết lập này: BE dùng giá trị mới, FE dùng giá trị
cũ, và không chỗ nào báo. Test này là chỗ báo.
"""

from __future__ import annotations

from web.contracts.generate_ts import OUTPUT, render


def test_the_generated_file_is_up_to_date() -> None:
    assert OUTPUT.is_file(), (
        f"chưa có `{OUTPUT.name}`; chạy "
        f"`uv run python -m web.contracts.generate_ts`"
    )
    assert OUTPUT.read_text(encoding="utf-8") == render(), (
        "`enums.ts` lệch khỏi `enums.py`; chạy lại "
        "`uv run python -m web.contracts.generate_ts` rồi commit cả hai file"
    )


def test_the_generated_file_says_it_is_generated() -> None:
    # Người mở file phải biết ngay sửa tay là vô ích.
    first = OUTPUT.read_text(encoding="utf-8").splitlines()[0]
    assert "sinh ra" in first and "Không sửa tay" in first
