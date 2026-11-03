"""Inventory the logging in the Psi0 training code at a pinned commit (DA-19 task 1).

Reads the author's files straight from git (`git show <commit>:<path>`), so the clone
does not need to be checked out at the pin. It lists the calls to `log`,
`accelerator.log`, `init_trackers`, `evaluate`, `save_checkpoint` (and the
`save_state` / `load_state` they wrap), the metric keys each stage's
`training_step` and `evaluate` return, and maps them onto the `TrainingMetric`
fields of `flywheel.contracts.training`.

Rerun whenever the pin changes; `--check` fails if the generated block in the
docs file is stale:

    python3 scripts/g0/read_psi0_logging.py --repo fwdata/psi0/Psi0 --commit cda3fdf \
        --write docs/g0/psi0-logging.md
    python3 scripts/g0/read_psi0_logging.py --repo fwdata/psi0/Psi0 --commit cda3fdf \
        --check docs/g0/psi0-logging.md

Standard library only, so it runs with any python3.
"""

from __future__ import annotations

import argparse
import ast
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

BEGIN = "<!-- BEGIN read_psi0_logging.py -->"
END = "<!-- END read_psi0_logging.py -->"

LAUNCHER = "scripts/train.py"
TRAINERS = {
    "1 (pretrain)": "src/psi/trainers/pretrain.py",
    "2 (posttrain)": "src/psi/trainers/posttrain.py",
    "3 (finetune)": "src/psi/trainers/finetune.py",
}
BASE_TRAINER = "src/psi/trainers/trainer.py"
STAGE_SCRIPTS = "scripts/train/psi0"
STAGE3_SCRIPT = "finetune-simple-psi0.sh"

CALL_NAMES = {"log", "init_trackers", "evaluate", "save_checkpoint", "save_state", "load_state"}
# Receivers whose `.log` is arithmetic, not telemetry.
MATH_RECEIVERS = {"torch", "np", "numpy", "math"}

# TrainingMetric field -> (Psi0 key that supplies it, or None; the metrics.jsonl lines
# that carry it; how the wrapper gets it). A key starting with "train/" or "eval/" is
# looked up in the extracted metric keys; a `**splat` key means the names are built at
# run time, so the field is only partly there.
BOTH = "train, val"
FIELD_SOURCES: list[tuple[str, str | None, str, str]] = [
    ("run_plan_id", None, BOTH, "Nhận từ RunPlan"),
    ("job_id", None, BOTH, "Nhận từ RunPlan"),
    ("checkpoint_id", None, BOTH, "Id của checkpoint job sẽ ra, như nhau trên mọi dòng"),
    ("release_id", None, BOTH, "Nhận từ RunPlan"),
    ("attempt", None, BOTH, "Đếm số lần chạy lại từ checkpoint"),
    ("step", "step=", BOTH, "`accelerator.log(..., step=self.global_step)`"),
    ("epoch", "train/epoch", BOTH, "Từ `train/epoch`; dòng val lấy epoch gần nhất"),
    ("split", "train/loss", BOTH, "Tiền tố `train/` thành `train`, `eval/` thành `val`"),
    ("loss", "train/loss", BOTH, '`train/loss` và `eval/loss`; không hữu hạn ghi `"NaN"`'),
    ("lr", "train/lr_act", BOTH, "LR nhóm action header; dòng val lấy LR gần nhất"),
    ("vlm_frozen", None, BOTH, "`model.tune_vlm` trong `run_config.json` (`--model.no-tune-vlm`)"),
    (
        "loss_by_group",
        "eval/**modality_metrics",
        "val",
        "MSE trên batch val theo nhóm của ActionLayout, đã chuẩn hóa. Ψ₀ chỉ có L1 "
        "khử chuẩn hóa `eval/<dataset>/err_l1_<nhóm>`, không dùng",
    ),
    ("loss_by_chunk_pos", None, "val", "MSE trên batch val theo vị trí trong chunk"),
    (
        "grad_norm_vlm",
        "train/grad_norm_vlm",
        "train",
        "Ψ₀ chỉ log khi một nhóm VLM được train; stage 3 đóng băng VLM nên launcher "
        "(nhiệm vụ con 2) tự đo trong `clip_grad_norms()`, trước `zero_grad()`, để T8a kiểm được",
    ),
    ("grad_norm_action", "train/grad_norm_act", "train", "Grad norm của action header"),
    ("pred_var_by_dim", None, "val", "Phương sai action dự đoán theo chiều, trên batch val"),
    ("pred_std", None, "val", "Độ lệch chuẩn action dự đoán theo chiều, trên batch val"),
    ("target_std", None, "val", "Độ lệch chuẩn action đích theo chiều, trên batch val"),
    (
        "hand_open_hist",
        None,
        "val",
        "Độ mở mỗi tay (0 nắm hết cỡ, 1 mở) từ 14 chiều bàn tay (0–13), histogram 10 ngăn (DA-07)",
    ),
    ("vram_gb", None, BOTH, "`torch.cuda.max_memory_allocated()`"),
    ("throughput", None, "train", "Batch toàn cục chia thời gian một bước; trống ngay sau eval"),
    ("wall_time_s", None, BOTH, "Số giây từ lúc lớp bọc khởi động"),
]


@dataclass
class Site:
    path: str
    line: int
    owner: str
    call: str


@dataclass
class Inventory:
    commit: str
    calls: list[Site] = field(default_factory=list)
    metrics: dict[str, dict[str, list[str]]] = field(default_factory=dict)
    stage_scripts: list[str] = field(default_factory=list)


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    ).stdout


def show(repo: Path, commit: str, path: str) -> str:
    return git(repo, "show", f"{commit}:{path}")


def dotted(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{dotted(node.value)}.{node.attr}"
    if isinstance(node, ast.Call):
        return f"{dotted(node.func)}()"
    return "<expr>"


def key_text(node: ast.expr) -> str | None:
    """A dict key as text: plain strings as-is, f-strings with `{...}` for the holes."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return "".join(
            part.value if isinstance(part, ast.Constant) else "{…}" for part in node.values
        )
    return None


class CallFinder(ast.NodeVisitor):
    def __init__(self, path: str) -> None:
        self.path = path
        self.owner: list[str] = []
        self.sites: list[Site] = []

    def _visit_scope(self, node: ast.ClassDef | ast.FunctionDef) -> None:
        self.owner.append(node.name)
        self.generic_visit(node)
        self.owner.pop()

    visit_ClassDef = _visit_scope
    visit_FunctionDef = _visit_scope

    def visit_Call(self, node: ast.Call) -> None:
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr in CALL_NAMES:
            receiver = dotted(func.value)
            if not (func.attr == "log" and receiver.split(".")[0] in MATH_RECEIVERS):
                self.sites.append(
                    Site(self.path, node.lineno, ".".join(self.owner) or "<module>", dotted(func))
                )
        self.generic_visit(node)


def class_methods(tree: ast.Module) -> dict[str, ast.FunctionDef]:
    """Methods of every class in the module, keyed by name (later classes win)."""
    methods: dict[str, ast.FunctionDef] = {}
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, ast.FunctionDef):
                    methods[item.name] = item
    return methods


def dict_keys(
    func: ast.FunctionDef, methods: dict[str, ast.FunctionDef], depth: int = 0
) -> list[str]:
    """Keys of the metric dicts a method builds or returns, following `**self.helper()`."""
    keys: list[str] = []

    def add_dict(node: ast.Dict) -> None:
        for key, value in zip(node.keys, node.values):
            if key is None:  # `**expr` splat
                if (
                    depth < 2
                    and isinstance(value, ast.Call)
                    and isinstance(value.func, ast.Attribute)
                    and dotted(value.func.value) == "self"
                    and value.func.attr in methods
                ):
                    keys.extend(dict_keys(methods[value.func.attr], methods, depth + 1))
                else:
                    keys.append(f"**{dotted(value) if isinstance(value, ast.expr) else '?'}")
            elif (text := key_text(key)) is not None:
                keys.append(text)

    for node in ast.walk(func):
        if isinstance(node, ast.Return) and node.value is not None:
            # `return {...}` or `return sync_gradients, {...}`
            parts = node.value.elts if isinstance(node.value, ast.Tuple) else [node.value]
            for part in parts:
                if isinstance(part, ast.Dict):
                    add_dict(part)
        elif isinstance(node, ast.Assign) and isinstance(node.value, ast.Dict):
            if any(isinstance(t, ast.Name) and t.id == "metrics" for t in node.targets):
                add_dict(node.value)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if (
                    isinstance(target, ast.Subscript)
                    and isinstance(target.value, ast.Name)
                    and target.value.id == "metrics"
                    and (text := key_text(target.slice)) is not None
                ):
                    keys.append(text)
    return list(dict.fromkeys(keys))


def flatten_keys(tree: ast.Module) -> dict[str, list[str]]:
    """Literal keys passed to `flatten({...}, parent_key="<prefix>")`, by prefix."""
    found: dict[str, list[str]] = {}
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and dotted(node.func).split(".")[-1] == "flatten"):
            continue
        prefix = next(
            (
                kw.value.value
                for kw in node.keywords
                if kw.arg == "parent_key" and isinstance(kw.value, ast.Constant)
            ),
            None,
        )
        if isinstance(prefix, str) and node.args and isinstance(node.args[0], ast.Dict):
            keys = [text for key in node.args[0].keys if key and (text := key_text(key))]
            found.setdefault(prefix, []).extend(keys)
    return found


def build(repo: Path, commit: str) -> Inventory:
    full = git(repo, "rev-parse", f"{commit}^{{commit}}").strip()
    inventory = Inventory(commit=full)
    trees = {
        path: ast.parse(show(repo, full, path), filename=path)
        for path in [LAUNCHER, BASE_TRAINER, *TRAINERS.values()]
    }
    for path, tree in trees.items():
        finder = CallFinder(path)
        finder.visit(tree)
        inventory.calls.extend(finder.sites)
    # Keys the launcher adds to every stage, e.g. `{**losses, "epoch": epoch}`.
    launcher_keys = flatten_keys(trees[LAUNCHER])
    for stage, path in TRAINERS.items():
        methods = class_methods(trees[path])
        stage_keys = flatten_keys(trees[path])  # e.g. an overridden `log()`
        inventory.metrics[stage] = {
            prefix: list(
                dict.fromkeys(
                    (dict_keys(methods[name], methods) if name in methods else [])
                    + launcher_keys.get(prefix, [])
                    + stage_keys.get(prefix, [])
                )
            )
            for prefix, name in (("train", "training_step"), ("eval", "evaluate"))
        }
    listing = git(repo, "ls-tree", "--name-only", f"{full}:{STAGE_SCRIPTS}")
    inventory.stage_scripts = sorted(listing.split())
    return inventory


def stage3_keys(inventory: Inventory) -> set[str]:
    stage3 = inventory.metrics["3 (finetune)"]
    return {f"{prefix}/{key}" for prefix, keys in stage3.items() for key in keys}


def render(inventory: Inventory) -> str:
    lines = [
        BEGIN,
        "",
        f"_Sinh bởi `scripts/g0/read_psi0_logging.py` từ commit `{inventory.commit}`. "
        "Không sửa tay; chạy lại script khi đổi commit ghim._",
        "",
        "### Lời gọi log, đánh giá, checkpoint",
        "",
        "| File | Dòng | Trong | Lời gọi |",
        "|---|---|---|---|",
    ]
    for site in inventory.calls:
        lines.append(f"| `{site.path}` | {site.line} | `{site.owner}` | `{site.call}` |")

    lines += [
        "",
        "### Tên metric theo stage",
        "",
        '`scripts/train.py` ghi `flatten({**losses, "epoch": epoch}, parent_key="train")` '
        'sau mỗi bước và `flatten(eval_losses, parent_key="eval")` sau `evaluate()`, '
        "nên khóa dưới đây có tiền tố `train/` hoặc `eval/` trong W&B. "
        "`{…}` là phần tên sinh lúc chạy.",
        "",
        "| Stage | Tiền tố | Khóa |",
        "|---|---|---|",
    ]
    for stage, by_prefix in inventory.metrics.items():
        for prefix, keys in by_prefix.items():
            shown = ", ".join(f"`{key}`" for key in keys) or "(không có)"
            lines.append(f"| {stage} | `{prefix}/` | {shown} |")

    available = stage3_keys(inventory)
    lines += [
        "",
        "### Trường `TrainingMetric` so với stage 3",
        "",
        'Cột "Ψ₀ tự log" chỉ nói code tác giả có sẵn số đó hay không. Mọi trường đều '
        "có trong `metrics.jsonl`: phần Ψ₀ không có do lớp bọc `flywheel_psi0.trainer` "
        'bù, trên các dòng ghi ở cột "Dòng".',
        "",
        "| Trường | Ψ₀ tự log | Nguồn trong Ψ₀ | Dòng | Cách lớp bọc lấy |",
        "|---|---|---|---|---|",
    ]
    for name, source, where, how in FIELD_SOURCES:
        if source is None:
            status, shown = "không", "—"
        elif source == "step=":
            status, shown = "có", "`step=`"
        elif source in available:
            status = "một phần" if "**" in source else "có"
            shown = f"`{source}`"
        else:
            status, shown = "không", f"`{source}` (không thấy)"
        lines.append(f"| `{name}` | {status} | {shown} | {where} | {how} |")

    has_stage3 = STAGE3_SCRIPT in inventory.stage_scripts
    lines += [
        "",
        "### Script train trong `scripts/train/psi0/`",
        "",
        f"`{STAGE3_SCRIPT}` {'có' if has_stage3 else 'không có'} ở commit này. "
        "Các script có: " + ", ".join(f"`{name}`" for name in inventory.stage_scripts) + ".",
        "",
        END,
    ]
    return "\n".join(lines) + "\n"


def splice(document: str, block: str) -> str:
    start, stop = document.find(BEGIN), document.find(END)
    if start < 0 or stop < 0:
        raise SystemExit(f"markers {BEGIN!r} / {END!r} not found")
    return document[:start] + block + document[stop + len(END) + 1 :]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", type=Path, default=Path("fwdata/psi0/Psi0"))
    parser.add_argument("--commit", default="cda3fdf")
    target = parser.add_mutually_exclusive_group()
    target.add_argument("--write", type=Path, help="replace the generated block in this file")
    target.add_argument("--check", type=Path, help="exit 1 if this file's block is stale")
    args = parser.parse_args()

    block = render(build(args.repo, args.commit))
    if args.write:
        args.write.write_text(
            splice(args.write.read_text(encoding="utf-8"), block), encoding="utf-8"
        )
    elif args.check:
        current = args.check.read_text(encoding="utf-8")
        if splice(current, block) != current:
            print(f"{args.check} is stale; rerun with --write", file=sys.stderr)
            return 1
    else:
        sys.stdout.write(block)
    return 0


if __name__ == "__main__":
    sys.exit(main())
