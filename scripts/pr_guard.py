"""Check a pull request branch against rules R6 and R9 of docs/product/08-daily-control.md.

R6: branch name, commit subject format, Time-spent trailer and file scope of the story.
R9: warn (never fail) when the diff is larger than SIZE_LIMIT lines.
"""

import argparse
import os
import re
import subprocess
import sys

from storylib import ROOT, STORY_ID, load_stories

BRANCH_STORY = re.compile(rf"^({STORY_ID})-[a-z0-9][a-z0-9-]*$")
BRANCH_FREE = re.compile(r"^(docs|chore|hotfix)-[a-z0-9][a-z0-9-]*$")
TRAILER = re.compile(r"^Time-spent:\s*\d+(?:\.\d+)?\s*h\s*$", re.MULTILINE | re.IGNORECASE)
DOCS_PREFIXES = ("docs/", "website/")
SIZE_LIMIT = 400
SIZE_EXEMPT = re.compile(r"(^|/)(uv\.lock|package-lock\.json)$|(^|/)fixtures/")


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True, text=True).stdout


def commits(base: str, head: str):
    log = git("log", "--no-merges", "--format=%H%x1f%s%x1f%b%x1e", f"{base}..{head}")
    for record in log.split("\x1e"):
        record = record.strip("\n")
        if record:
            sha, subject, body = record.split("\x1f")
            yield sha[:8], subject, body


def changed_files(base: str, head: str) -> list[str]:
    return [name for name in git("diff", "--name-only", "-z", f"{base}...{head}").split("\0") if name]


def diff_size(base: str, head: str) -> int:
    total = 0
    for line in git("diff", "--numstat", f"{base}...{head}").splitlines():
        added, deleted, path = line.split("\t", 2)
        if added != "-" and not SIZE_EXEMPT.search(path):
            total += int(added) + int(deleted)
    return total


def in_scope(path: str, scope: list[str]) -> bool:
    return any(path == entry.rstrip("/") or path.startswith(entry.rstrip("/") + "/") for entry in scope)


def check(base: str, head: str, branch: str) -> tuple[list[str], list[str], int]:
    errors, warnings = [], []
    story_match = BRANCH_STORY.match(branch)
    free_match = BRANCH_FREE.match(branch)
    if not story_match and not free_match:
        errors.append(f"R6 · Tên nhánh `{branch}` không theo `<story-id>-<mô-tả>` hoặc `docs-`, `chore-`, `hotfix-`.")
    story_id = story_match.group(1) if story_match else None

    if story_id:
        subject_rule = re.compile(rf"^{re.escape(story_id)}/\d+(?:\.\d+)*: \S")
        for sha, subject, body in commits(base, head):
            if not subject_rule.match(subject):
                errors.append(f"R6 · Commit {sha} `{subject}`: dòng đầu phải là `{story_id}/<nhiệm vụ con>: <việc>`.")
            if not TRAILER.search(body):
                errors.append(f"R6 · Commit {sha} thiếu dòng `Time-spent: <giờ>h` trong thân commit.")

    files = changed_files(base, head)
    if story_id:
        story = load_stories().get(story_id)
        if story is None:
            errors.append(f"R6 · Không có file story `docs/product/stories/{story_id}-*.md` trên nhánh này.")
        elif not story.scope:
            errors.append(f"R6 · Story {story_id} chưa có mục `## Phạm vi file`.")
        else:
            allowed = story.scope + [story.relpath]
            outside = [name for name in files if not in_scope(name, allowed)]
            errors += [f"R6 · `{name}` nằm ngoài Phạm vi file của {story_id}." for name in outside]
    elif free_match and free_match.group(1) == "docs":
        outside = [name for name in files if not (name.startswith(DOCS_PREFIXES) or name.endswith(".md"))]
        errors += [f"R6 · Nhánh docs- không được sửa `{name}`." for name in outside]

    size = diff_size(base, head)
    if size > SIZE_LIMIT:
        warnings.append(f"R9 · PR thay đổi {size} dòng (ngưỡng {SIZE_LIMIT}); nên tách story.")
    return errors, warnings, size


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True, help="base commit or ref, e.g. origin/master")
    parser.add_argument("--head", required=True, help="head commit or ref, e.g. HEAD")
    parser.add_argument("--branch", required=True, help="name of the PR branch")
    args = parser.parse_args()

    errors, warnings, size = check(args.base, args.head, args.branch)
    lines = [f"## pr-guard · `{args.branch}`", "", f"Kích thước: {size} dòng.", ""]
    lines += [f"- ❌ {item}" for item in errors] + [f"- ⚠️ {item}" for item in warnings]
    if not errors and not warnings:
        lines.append("- ✅ Đạt mọi kiểm tra.")
    report = "\n".join(lines)
    print(report)

    if summary := os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(summary, "a", encoding="utf-8") as handle:
            handle.write(report + "\n")
    if output := os.environ.get("GITHUB_OUTPUT"):
        with open(output, "a", encoding="utf-8") as handle:
            handle.write(f"size_large={'true' if size > SIZE_LIMIT else 'false'}\n")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
