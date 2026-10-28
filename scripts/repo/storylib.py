"""Parse story files in docs/product/stories/ for the progress, PR guard and daily report scripts."""

import re
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
STORIES = ROOT / "docs" / "product" / "stories"
STORY_ID = r"(?:S\d+-\d{2}|DA-\d{2})"

CHECKBOX = re.compile(r"^\s*- \[( |x|X)\] ", re.MULTILINE)
FIELD = re.compile(r"^\| ([^|]+?) \| (.+?) \|$", re.MULTILINE)
SECTION = re.compile(r"^## (.+?)\s*$", re.MULTILINE)
CODE = re.compile(r"`([^`]+)`")
NUMBER = re.compile(r"\d+(?:[.,]\d+)?")


@dataclass
class Story:
    id: str
    path: Path
    owner: str
    status: str
    estimate_hours: float | None
    done: int
    total: int
    scope: list[str]

    @property
    def relpath(self) -> str:
        return self.path.relative_to(ROOT).as_posix()

    @property
    def finished(self) -> bool:
        return self.total > 0 and self.done == self.total


def _section(text: str, title: str) -> str | None:
    headings = list(SECTION.finditer(text))
    for i, match in enumerate(headings):
        if match.group(1).strip() == title:
            end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
            return text[match.end():end]
    return None


def parse_story(path: Path) -> Story:
    text = path.read_text(encoding="utf-8")
    boxes = CHECKBOX.findall(text)
    fields = {key.strip(): value.strip() for key, value in FIELD.findall(text)}
    estimate = NUMBER.search(fields.get("Ước lượng", ""))
    scope_text = _section(text, "Phạm vi file")
    scope = []
    if scope_text:
        for line in scope_text.splitlines():
            if line.lstrip().startswith("- "):
                scope += [item.strip().removeprefix("./") for item in CODE.findall(line)]
    return Story(
        id="-".join(path.stem.split("-")[:2]),
        path=path,
        owner=fields.get("Người làm", "?"),
        status=fields.get("Trạng thái", "?"),
        estimate_hours=float(estimate.group().replace(",", ".")) if estimate else None,
        done=sum(1 for box in boxes if box.lower() == "x"),
        total=len(boxes),
        scope=scope,
    )


def load_stories() -> dict[str, Story]:
    stories = (parse_story(path) for path in sorted(STORIES.glob("*.md")))
    return {story.id: story for story in stories}
