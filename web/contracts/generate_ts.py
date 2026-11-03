"""Sinh ``web/fe/src/contracts/enums.ts`` từ ``enums.py`` (DESIGN.md luật R3).

Chạy: ``uv run python -m web.contracts.generate_ts``. Không tham số; nó ghi
đúng một file và in đường dẫn.

Lý do sinh thay vì gõ hai lần: FE và BE đọc cùng một bộ giá trị, và hai bản
gõ tay sẽ lệch đúng vào lúc không ai để ý — một PR hợp đồng đổi một giá trị,
BE sửa, FE quên. ``test_generated_ts.py`` so file trên đĩa với bản sinh lại,
nên quên chạy lệnh này là test đỏ.

File sinh ra là TypeScript thường, không phải d.ts: mỗi bộ là một mảng
``as const`` để có literal type, cộng một type union lấy từ mảng đó. Nhờ vậy
FE vừa lặp được trên giá trị lúc chạy (dropdown, chip) vừa kiểm được lúc dịch.
"""

from __future__ import annotations

from pathlib import Path

from web.contracts.enums import (
    ACTION_NEEDS_REASON,
    CONTRACT,
    LITERAL_SOURCE,
    MULTI_FILE_SOURCE,
    SCHEMA_SOURCE,
    SPEC,
    SPEC_SOURCE,
    WEB,
)

OUTPUT = Path(__file__).resolve().parents[1] / "fe" / "src" / "contracts" / "enums.ts"

HEADER = """// File sinh ra. Không sửa tay.
// Nguồn: web/contracts/enums.py · sinh lại: uv run python -m web.contracts.generate_ts
//
// Ba nhóm, mức bảo đảm khác nhau (xem web/DESIGN.md Phụ lục A):
//   contract · lõi khai trong flywheel-contracts, test so từng bộ với nguồn
//   spec     · spec v10.5 / design 27/10 chốt, chưa vào hợp đồng, không máy nào kiểm
//   web      · của riêng web
"""


def _camel(name: str) -> str:
    head, *rest = name.split("_")
    return head + "".join(part.capitalize() for part in rest)


def _pascal(name: str) -> str:
    return "".join(part.capitalize() for part in name.split("_"))


def _block(name: str, values: tuple[str, ...], note: str) -> str:
    items = ", ".join(f'"{value}"' for value in values)
    return (
        f"/** {note} */\n"
        f"export const {_camel(name)} = [{items}] as const;\n"
        f"export type {_pascal(name)} = (typeof {_camel(name)})[number];\n"
    )


def _contract_note(name: str) -> str:
    if name in SCHEMA_SOURCE:
        file_name, path = SCHEMA_SOURCE[name]
        return f"contract · {file_name}:{path}"
    if name in LITERAL_SOURCE:
        return f"contract · flywheel.contracts.{LITERAL_SOURCE[name]}"
    files = ", ".join(file_name for file_name, _ in MULTI_FILE_SOURCE[name])
    return f"contract · {files}"


def render() -> str:
    """Nội dung file TS, đúng bytes mà lệnh này sẽ ghi."""
    parts = [HEADER]
    for title, table, note in (
        ("contract", CONTRACT, _contract_note),
        ("spec", SPEC, lambda name: f"spec · {SPEC_SOURCE[name]}"),
        ("web", WEB, lambda name: "web · web/DESIGN.md Phụ lục A.2"),
    ):
        parts.append(f"\n// {'=' * 72}\n// {title}\n// {'=' * 72}\n")
        for name in table:
            parts.append(_block(name, table[name], note(name)))
    reasons = ", ".join(f'"{value}"' for value in ACTION_NEEDS_REASON)
    parts.append(
        "\n/** Hành động bắt buộc có lý do (BR-04, BR-10). */\n"
        f"export const actionNeedsReason = [{reasons}] as const;\n"
    )
    return "".join(parts)


def main() -> int:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(render(), encoding="utf-8", newline="\n")
    print(OUTPUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
