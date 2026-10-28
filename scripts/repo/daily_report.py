"""Build the daily control report of docs/product/08-daily-control.md (rules R1-R5, R7-R9).

Reads git history, story files and, when GITHUB_TOKEN is set, the GitHub API. Writes a Markdown
report and a JSON file for website/dist/progress.html. Each section is collected on its own, so a
failing source is listed under "errors" instead of hiding the rest of the report.
"""

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict

from storylib import ROOT, STORY_ID, load_stories

ICT = dt.timezone(dt.timedelta(hours=7))
SUBJECT = re.compile(rf"^({STORY_ID})/(\d+(?:\.\d+)*): (.+)$")
TRAILER = re.compile(r"^Time-spent:\s*(\d+(?:\.\d+)?)\s*h\s*$", re.MULTILINE | re.IGNORECASE)

# Default thresholds, section 3.2 of docs/product/08-daily-control.md.
K_LIMIT = 1.3
REVIEW_WAIT_DAYS = 1
WIP_LIMIT = 2
STALE_DAYS = 2
CAUSE_REPEAT = 3
PR_SIZE_LIMIT = 400


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True, text=True).stdout


def business_days(start: dt.datetime, end: dt.datetime) -> int:
    """Weekdays strictly after start's date, up to and including end's date."""
    day, count = start.astimezone(ICT).date(), 0
    while day < end.astimezone(ICT).date():
        day += dt.timedelta(days=1)
        count += day.weekday() < 5
    return count


def subtask_commits(ref: str, since: dt.datetime | None = None):
    args = ["log", "--no-merges", "--format=%H%x1f%ct%x1f%an%x1f%s%x1f%b%x1e"]
    if since:
        args.append(f"--since=@{int(since.timestamp())}")
    for record in git(*args, ref).split("\x1e"):
        record = record.strip("\n")
        if not record:
            continue
        sha, stamp, author, subject, body = record.split("\x1f")
        match = SUBJECT.match(subject)
        if not match:
            continue
        hours = TRAILER.search(body)
        yield {
            "sha": sha[:8],
            "time": dt.datetime.fromtimestamp(int(stamp), dt.timezone.utc),
            "author": author,
            "story": match.group(1),
            "subtask": match.group(2),
            "title": match.group(3),
            "hours": float(hours.group(1)) if hours else 0.0,
        }


class GitHub:
    def __init__(self, token: str, repo: str):
        self.token, self.repo = token, repo

    def get(self, path: str, **params):
        query = f"?{urllib.parse.urlencode(params)}" if params else ""
        request = urllib.request.Request(
            f"https://api.github.com/repos/{self.repo}{path}{query}",
            headers={"Authorization": f"Bearer {self.token}", "Accept": "application/vnd.github+json"},
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)


def repo_from_remote() -> str | None:
    try:
        url = git("remote", "get-url", "origin").strip()
    except subprocess.CalledProcessError:
        return None
    match = re.search(r"github\.com[:/](.+?)(?:\.git)?$", url)
    return match.group(1) if match else None


def collect(now: dt.datetime) -> dict:
    stories = load_stories()
    report = {"generated_at": now.isoformat(), "repo": None, "rules": [], "errors": []}

    def rule(code: str, text: str):
        report["rules"].append({"rule": code, "text": text})

    def section(name: str, func):
        try:
            func()
        except Exception as error:  # one failing source must not hide the others
            report["errors"].append(f"{name}: {error}")

    window_start = now - dt.timedelta(days=3 if now.astimezone(ICT).weekday() == 0 else 1)
    report["window"] = {"from": window_start.isoformat(), "to": now.isoformat()}

    def yesterday():
        people = defaultdict(lambda: {"subtasks": [], "hours": 0.0})
        for commit in subtask_commits("HEAD", window_start):
            owner = stories[commit["story"]].owner if commit["story"] in stories else "?"
            people[owner]["subtasks"].append(f"{commit['story']}/{commit['subtask']}: {commit['title']}")
            people[owner]["hours"] += commit["hours"]
        report["yesterday"] = dict(people)

    def k_factor():
        totals = defaultdict(lambda: {"hours": 0.0, "earned": 0.0})
        for commit in subtask_commits("HEAD", now - dt.timedelta(days=7)):
            story = stories.get(commit["story"])
            if not story or not story.estimate_hours or not story.total:
                continue
            totals[story.owner]["hours"] += commit["hours"]
            totals[story.owner]["earned"] += story.estimate_hours / story.total
        report["k"] = {}
        for owner, value in totals.items():
            k = value["hours"] / value["earned"] if value["earned"] else None
            report["k"][owner] = {**value, "k": k}
            if k is not None and k > K_LIMIT:
                rule("R5", f"k 7 ngày của {owner} là {k:.2f} (> {K_LIMIT}).")

    def story_progress():
        report["stories"] = [
            {"id": s.id, "owner": s.owner, "done": s.done, "total": s.total, "status": s.status}
            for s in stories.values()
        ]
        report["stale"] = []
        for story in stories.values():
            if story.finished:
                continue
            last = git("log", "--all", "-1", "--format=%ct", f"--grep=^{story.id}/", "-E").strip()
            if not last:
                continue
            idle = business_days(dt.datetime.fromtimestamp(int(last), dt.timezone.utc), now)
            if idle >= STALE_DAYS:
                report["stale"].append({"id": story.id, "owner": story.owner, "idle_days": idle})
                rule("R4", f"{story.id} ({story.owner}) không có commit {idle} ngày làm việc.")

    section("yesterday", yesterday)
    section("k", k_factor)
    section("stories", story_progress)

    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY") or repo_from_remote()
    report["repo"] = repo
    if not token or not repo:
        report["errors"].append("github: chưa có GITHUB_TOKEN hoặc không xác định được repo, bỏ qua PR, CI và issue.")
        return report
    gh = GitHub(token, repo)

    def pull_requests():
        report["prs"], wip = [], Counter()
        for pr in gh.get("/pulls", state="open", per_page=100):
            author = pr["user"]["login"]
            wip[author] += 1
            created = dt.datetime.fromisoformat(pr["created_at"].replace("Z", "+00:00"))
            detail = gh.get(f"/pulls/{pr['number']}")
            reviewed = bool(gh.get(f"/pulls/{pr['number']}/reviews", per_page=1))
            size = detail["additions"] + detail["deletions"]
            age = business_days(created, now)
            report["prs"].append({"number": pr["number"], "title": pr["title"], "author": author,
                                  "draft": pr["draft"], "age_days": age, "reviewed": reviewed, "size": size})
            if not pr["draft"] and not reviewed and age > REVIEW_WAIT_DAYS:
                rule("R2", f"PR #{pr['number']} của {author} chờ review {age} ngày làm việc.")
            if size > PR_SIZE_LIMIT:
                rule("R9", f"PR #{pr['number']} thay đổi {size} dòng (> {PR_SIZE_LIMIT}).")
        for author, count in wip.items():
            if count > WIP_LIMIT:
                rule("R3", f"{author} có {count} PR đang mở (> {WIP_LIMIT}).")

    def ci_master():
        report["ci"], seen = [], set()
        for run in gh.get("/actions/runs", branch="master", event="push", per_page=30)["workflow_runs"]:
            if run["name"] in seen or run["status"] != "completed":
                continue
            seen.add(run["name"])
            report["ci"].append({"workflow": run["name"], "conclusion": run["conclusion"], "url": run["html_url"]})
            if run["conclusion"] not in ("success", "skipped", "neutral"):
                rule("R1", f"CI `{run['name']}` trên master: {run['conclusion']}.")

    def issues():
        since = now - dt.timedelta(days=7)
        causes, high = Counter(), []
        for issue in gh.get("/issues", state="all", since=since.isoformat(), per_page=100):
            if "pull_request" in issue:
                continue
            labels = {label["name"] for label in issue["labels"]}
            created = dt.datetime.fromisoformat(issue["created_at"].replace("Z", "+00:00"))
            if created >= since:
                causes.update(label for label in labels if label.startswith("cause:"))
            if issue["state"] == "open" and "severity:high" in labels:
                high.append({"number": issue["number"], "title": issue["title"]})
                rule("R7", f"Issue #{issue['number']} severity:high đang mở: {issue['title']}.")
        for cause, count in causes.items():
            if count >= CAUSE_REPEAT:
                rule("R8", f"`{cause}` có {count} issue trong 7 ngày; cần một can thiệp (08 mục 6).")
        report["issues"] = {"causes_7d": dict(causes), "high_open": high}

    section("pull_requests", pull_requests)
    section("ci", ci_master)
    section("issues", issues)
    return report


def render(report: dict) -> str:
    local = dt.datetime.fromisoformat(report["generated_at"]).astimezone(ICT)
    out = [f"# Báo cáo ngày {local:%d/%m/%Y}", "", f"Sinh lúc {local:%H:%M} giờ Việt Nam. Rule và ngưỡng: docs/product/08-daily-control.md.", ""]
    out += ["## Rule kích hoạt", ""]
    out += [f"- **{r['rule']}** · {r['text']}" for r in report["rules"]] or ["- Không có."]
    out += ["", "## Hôm qua theo người", ""]
    yesterday = report.get("yesterday", {})
    for owner, value in sorted(yesterday.items()):
        out.append(f"- **{owner}**: {len(value['subtasks'])} nhiệm vụ con, {value['hours']:g} giờ")
        out += [f"  - {item}" for item in value["subtasks"]]
    if not yesterday:
        out.append("- Chưa có nhiệm vụ con nào vào master.")
    out += ["", "## Hệ số k, 7 ngày", "", "| Người | Giờ thực | Giờ ước kiếm được | k |", "|---|---|---|---|"]
    for owner, value in sorted(report.get("k", {}).items()):
        k = f"{value['k']:.2f}" if value["k"] is not None else "—"
        out.append(f"| {owner} | {value['hours']:g} | {value['earned']:.1f} | {k} |")
    if prs := report.get("prs"):
        out += ["", "## PR đang mở", "", "| PR | Tác giả | Tuổi (ngày làm việc) | Đã review | Dòng |", "|---|---|---|---|---|"]
        for pr in prs:
            title = f"#{pr['number']} {pr['title']}" + (" (nháp)" if pr["draft"] else "")
            out.append(f"| {title} | {pr['author']} | {pr['age_days']} | {'có' if pr['reviewed'] else 'chưa'} | {pr['size']} |")
    if ci := report.get("ci"):
        out += ["", "## CI trên master", ""] + [f"- {c['workflow']}: {c['conclusion']}" for c in ci]
    if issues := report.get("issues"):
        causes = ", ".join(f"{k} {v}" for k, v in sorted(issues["causes_7d"].items())) or "không có"
        out += ["", "## Lỗi 7 ngày theo nguyên nhân", "", f"- {causes}"]
    out += ["", "## Tiến độ story", "", "| Story | Người làm | Xong |", "|---|---|---|"]
    out += [f"| {s['id']} | {s['owner']} | {s['done']}/{s['total']} |" for s in report.get("stories", [])]
    if report["errors"]:
        out += ["", "## Nguồn không đọc được", ""] + [f"- {e}" for e in report["errors"]]
    out += ["", "Trả lời dưới bình luận này 3 dòng: **Xong**, **Tiếp theo**, **Bị chặn**."]
    return "\n".join(out) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--markdown", help="write the Markdown report here instead of stdout")
    parser.add_argument("--json", help="write the JSON data for the progress page here")
    parser.add_argument("--now", help="ISO timestamp to use as 'now' (for testing)")
    args = parser.parse_args()

    now = dt.datetime.fromisoformat(args.now) if args.now else dt.datetime.now(dt.timezone.utc)
    report = collect(now)
    markdown = render(report)
    if args.markdown:
        with open(args.markdown, "w", encoding="utf-8") as handle:
            handle.write(markdown)
    elif not args.json:
        print(markdown)
    if args.json:
        with open(args.json, "w", encoding="utf-8") as handle:
            json.dump(report, handle, ensure_ascii=False, indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
