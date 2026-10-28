"""Check that relative Markdown links in the repo point to existing files."""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SKIP_DIRS = {".git", "node_modules", "dist", "papers", ".remember", ".agents", ".codex"}
LINK = re.compile(r"\]\(([^)\s]+)\)")


def iter_markdown(root: Path):
    for path in root.rglob("*.md"):
        if not SKIP_DIRS.intersection(path.relative_to(root).parts):
            yield path


def main() -> int:
    broken = []
    for md in iter_markdown(ROOT):
        for match in LINK.finditer(md.read_text(encoding="utf-8")):
            target = match.group(1).split("#", 1)[0]
            if not target or target.startswith(("http://", "https://", "mailto:")):
                continue
            if not (md.parent / target).exists():
                broken.append(f"{md.relative_to(ROOT)}: {match.group(1)}")
    for line in broken:
        print(f"BROKEN {line}")
    print(f"{len(broken)} broken link(s)")
    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main())
