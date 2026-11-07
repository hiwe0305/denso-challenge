"""Render six offline demo sections from a verified, locally staged evidence bundle."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

SECTIONS: dict[str, tuple[str, tuple[str, ...]]] = {
    "1": ("Tái tạo Ψ₀", ("comparison", "video")),
    "2": ("Ba nguồn dữ liệu", ("egocentric", "teleop", "synthetic_s1", "synthetic_s2", "ledger")),
    "3": (
        "Pipeline dữ liệu",
        (
            "egocentric_stage1",
            "teleop_release",
            "synthetic_release",
            "dataset_report",
            "loader_check",
        ),
    ),
    "4": ("Agent QA/QC", ("benchmark_metrics", "agent_report")),
    "5": ("HE-1 sơ bộ", ("comparison", "video")),
    "6": (
        "Failure → Data",
        (
            "two_table_score",
            "two_table_diagnosis",
            "two_table_card",
            "two_table_proposal",
            "two_table_ledger",
            "tray_score",
            "tray_diagnosis",
            "tray_card",
            "tray_generation",
            "tray_qa",
            "tray_decision",
        ),
    ),
}
KINDS = {"text", "video", "image", "file"}
LABELS = {
    "measured": "Thực đo",
    "preliminary": "Sơ bộ",
    "injected": "Bộ lỗi cấy",
    "reference": "Tài liệu tham chiếu",
}
MAX_TEXT_BYTES = 2_000_000


def reject_answer_key(path: Path, relative: str, root: Path) -> None:
    """Reject recognizable answer-key paths and JSON records in section 4.

    This is a guard against common mistakes, not a content classification boundary.
    """
    components = (*Path(relative).parts, *path.relative_to(root).parts)
    for component in components:
        name = re.sub(r"[^a-z0-9]", "", component.casefold())
        if "defectmanifest" in name or name in {"answers", "answerkeys", "answerkey"}:
            raise ValueError(f"phần 4: không được trình chiếu file đáp án: {relative}")
    if path.suffix.lower() not in {".json", ".jsonl"}:
        return
    if path.stat().st_size > MAX_TEXT_BYTES:
        raise ValueError(f"phần 4: JSON quá lớn để kiểm tra đáp án: {relative}")
    text = path.read_text(encoding="utf-8")
    try:
        records = (
            [json.loads(text)]
            if path.suffix.lower() == ".json"
            else [json.loads(line) for line in text.splitlines() if line.strip()]
        )
    except json.JSONDecodeError as error:
        raise ValueError(f"phần 4: JSON không hợp lệ: {relative}") from error
    if any(
        isinstance(record, dict)
        and ({"dataset_id", "defects"} <= record.keys() or record.get("title") == "DefectManifest")
        for record in records
    ):
        raise ValueError(f"phần 4: không được trình chiếu DefectManifest: {relative}")


def digest(path: Path) -> str:
    sha = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            sha.update(block)
    return sha.hexdigest()


def local_file(root: Path, raw: Any) -> Path:
    if not isinstance(raw, str) or not raw or "\\" in raw:
        raise ValueError("đường dẫn phải là chuỗi tương đối dùng dấu /")
    relative = Path(raw)
    if relative.is_absolute() or relative.drive:
        raise ValueError(f"đường dẫn phải tương đối với bundle: {raw}")
    path = (root / relative).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError(f"không có file trong bundle: {raw}")
    return path


def load_manifest(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("version") != 1:
        raise ValueError("manifest phải là object phiên bản 1")
    if not isinstance(value.get("sections"), dict):
        raise ValueError("manifest thiếu sections")
    return value


def validated_items(manifest: dict[str, Any], root: Path, section: str) -> list[dict[str, Any]]:
    data = manifest["sections"].get(section)
    if not isinstance(data, dict) or not isinstance(data.get("items"), list):
        raise ValueError(f"phần {section}: thiếu danh sách items")
    items = data["items"]
    if not all(isinstance(item, dict) for item in items):
        raise ValueError(f"phần {section}: mỗi item phải là object")
    required = set(SECTIONS[section][1])
    if section == "6":
        if data.get("tray_outcome") not in ("full", "fallback"):
            raise ValueError("phần 6: tray_outcome phải là full hoặc fallback")
        if data["tray_outcome"] == "full":
            required.update(("tray_train", "tray_eval", "tray_comparison"))
    roles = [item.get("role") for item in items]
    if any(not isinstance(role, str) or not role for role in roles):
        raise ValueError(f"phần {section}: item thiếu role")
    missing = required - set(roles)
    if missing:
        raise ValueError(f"phần {section}: thiếu bằng chứng {', '.join(sorted(missing))}")
    checked = []
    for item in items:
        title, kind, expected = item.get("title"), item.get("kind"), item.get("sha256")
        if (
            not isinstance(title, str)
            or not title.strip()
            or not isinstance(kind, str)
            or kind not in KINDS
        ):
            raise ValueError(f"phần {section}: title hoặc kind không hợp lệ")
        label = item.get("label")
        if not isinstance(label, str) or label not in LABELS:
            raise ValueError(f"phần {section}: thiếu nhãn nguồn hợp lệ")
        if section == "4" and label != "injected":
            raise ValueError("phần 4: báo cáo phải ghi nhãn bộ lỗi cấy")
        if section == "5" and label != "preliminary":
            raise ValueError("phần 5: kết quả HE-1 phải ghi nhãn sơ bộ")
        source = item.get("source")
        if not isinstance(source, str) or not source.strip():
            raise ValueError(f"phần {section}: mỗi bằng chứng cần source xác định nguồn gốc")
        if (
            not isinstance(expected, str)
            or len(expected) != 64
            or any(c not in "0123456789abcdef" for c in expected)
        ):
            raise ValueError(f"phần {section}: cần sha256 64 ký tự hex thường")
        path = local_file(root, item.get("path"))
        if section == "4":
            reject_answer_key(path, item["path"], root)
        if digest(path) != expected:
            raise ValueError(f"phần {section}: sha256 không khớp {item['path']}")
        if kind == "text" and path.stat().st_size > MAX_TEXT_BYTES:
            raise ValueError(f"phần {section}: file văn bản quá lớn: {item['path']}")
        if kind == "text":
            path.read_text(encoding="utf-8")
        checked.append({**item, "resolved": path})
    return checked


def render(section: str, items: list[dict[str, Any]], *, tray_outcome: str | None = None) -> str:
    title = SECTIONS[section][0]
    cards = []
    for item in items:
        path: Path = item["resolved"]
        url = html.escape(path.as_uri(), quote=True)
        if item["kind"] == "text":
            body = "<pre>" + html.escape(path.read_text(encoding="utf-8")) + "</pre>"
        elif item["kind"] == "video":
            body = f'<video controls preload="metadata" src="{url}"></video>'
        elif item["kind"] == "image":
            body = f'<img src="{url}" alt="{html.escape(item["title"], quote=True)}">'
        else:
            body = f'<p><a href="{url}">Mở file bằng chứng</a></p>'
        cards.append(
            f"<section><h2>{html.escape(item['title'])}</h2>"
            f"<p>{LABELS[item['label']]}</p>{body}"
            f"<p>Nguồn gốc: {html.escape(item['source'])}<br>"
            f'Bản sao: <a href="{url}">{html.escape(item["path"])}</a><br>'
            f"SHA-256: <code>{item['sha256']}</code></p></section>"
        )
    tray_note = ""
    if section == "6":
        tray_note = (
            "<p>Task khay: đường lui dừng sau QA; C+ chưa được trình bày.</p>"
            if tray_outcome == "fallback"
            else "<p>Task khay: vòng C+ và so sánh đã có file bằng chứng.</p>"
        )
    return (
        '<!doctype html><html lang="vi"><meta charset="utf-8">'
        f"<title>Demo {section} · {html.escape(title)}</title>"
        "<style>body{font:16px system-ui;max-width:1100px;margin:auto;padding:2rem;"
        "background:#f7f8fa;color:#17212b}section{background:white;padding:1.2rem;"
        "margin:1rem 0;border:1px solid #ccd5df;border-radius:8px}pre{white-space:pre-wrap;"
        "overflow-wrap:anywhere}video,img{max-width:100%}code{overflow-wrap:anywhere}</style>"
        f"<h1>Phần {section} · {html.escape(title)}</h1>"
        + tray_note
        + "<p>Dữ liệu dưới đây được đọc từ các file đã kiểm tra hash. Kết quả sơ bộ, "
        "dữ liệu cấy lỗi và giới hạn phải được ghi trong chính báo cáo nguồn.</p>"
        + "".join(cards)
        + "</html>"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("section", choices=[*SECTIONS, "check", "template"])
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--output", type=Path, help="HTML output for a numbered section")
    args = parser.parse_args(argv)
    if args.section == "template":
        sections: dict[str, Any] = {
            key: {
                "items": [
                    {
                        "role": role,
                        "title": role,
                        "kind": "file",
                        "label": None,
                        "source": None,
                        "path": None,
                        "sha256": None,
                    }
                    for role in roles
                ]
            }
            for key, (_, roles) in SECTIONS.items()
        }
        sections["6"]["tray_outcome"] = None
        template = json.dumps({"version": 1, "sections": sections}, ensure_ascii=False, indent=2)
        if args.output is None:
            print(template)
        else:
            try:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                with args.output.open("x", encoding="utf-8") as stream:
                    stream.write(template + "\n")
                print(f"Đã tạo: {args.output}")
            except OSError as error:
                print(f"Không thể tạo manifest: {error}", file=sys.stderr)
                return 2
        return 0
    if args.manifest is None:
        parser.error("--manifest là bắt buộc")
    try:
        manifest_path = args.manifest.resolve(strict=True)
        root = manifest_path.parent
        manifest = load_manifest(manifest_path)
        if args.section == "check":
            errors = []
            for section in SECTIONS:
                try:
                    validated_items(manifest, root, section)
                    print(f"{section}: sẵn sàng")
                except (ValueError, OSError, UnicodeError) as error:
                    errors.append(str(error))
                    print(f"{section}: {error}")
            return 1 if errors else 0
        try:
            items = validated_items(manifest, root, args.section)
        except (ValueError, OSError, UnicodeError) as error:
            print(f"Bằng chứng chưa hợp lệ: {error}", file=sys.stderr)
            return 1
        page = render(
            args.section, items, tray_outcome=manifest["sections"][args.section].get("tray_outcome")
        )
        if args.output is None:
            print(page)
        else:
            output = args.output.resolve()
            if output.is_relative_to(root):
                raise ValueError("file HTML phải nằm ngoài bundle bằng chứng")
            output.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=output.parent, delete=False
            ) as stream:
                temp_path = Path(stream.name)
                try:
                    stream.write(page)
                except BaseException:
                    temp_path.unlink(missing_ok=True)
                    raise
            try:
                os.replace(temp_path, output)
            finally:
                temp_path.unlink(missing_ok=True)
            print(f"Đã tạo: {output}")
        return 0
    except (ValueError, OSError, UnicodeError) as error:
        print(f"Không thể chuẩn bị demo: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
