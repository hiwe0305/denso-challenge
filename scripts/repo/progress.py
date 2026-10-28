"""Print subtask progress for every story file in docs/product/stories/."""

import sys

from storylib import load_stories


def main() -> int:
    print(f"{'Story':<8} {'Người làm':<12} {'Xong':>9}  Trạng thái")
    for story in load_stories().values():
        print(f"{story.id:<8} {story.owner:<12} {story.done:>4}/{story.total:<4}  {story.status}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
