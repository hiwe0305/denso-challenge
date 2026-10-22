"""Print subtask progress for every story file in docs/product/stories/."""

import re
import sys
from pathlib import Path

STORIES = Path(__file__).resolve().parent.parent / "docs" / "product" / "stories"
CHECKBOX = re.compile(r"^\s*- \[( |x|X)\] ", re.MULTILINE)
FIELD = re.compile(r"^\| (Người làm|Trạng thái) \| (.+?) \|$", re.MULTILINE)


def main() -> int:
    rows = []
    for story in sorted(STORIES.glob("*.md")):
        text = story.read_text(encoding="utf-8")
        boxes = CHECKBOX.findall(text)
        done = sum(1 for box in boxes if box.lower() == "x")
        fields = dict(FIELD.findall(text))
        story_id = "-".join(story.stem.split("-")[:2])
        rows.append((story_id, fields.get("Người làm", "?"), done, len(boxes), fields.get("Trạng thái", "?")))
    print(f"{'Story':<8} {'Người làm':<12} {'Xong':>9}  Trạng thái")
    for story_id, owner, done, total, status in rows:
        print(f"{story_id:<8} {owner:<12} {done:>4}/{total:<4}  {status}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
