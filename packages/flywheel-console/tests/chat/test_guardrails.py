from __future__ import annotations

from chat_index import make_idx  # noqa: F401
from flywheel.console.chat import llm, registry
from flywheel.console.chat.common import allowed
from flywheel.console.paths import ConsolePaths


def test_tool_denies_vault_path(idx: ConsolePaths) -> None:
    assert not allowed(idx.fw_root / "vault" / "x.json")
    assert not allowed(idx.fw_root / "tray" / "holdout-set" / "x.json")
    assert not allowed(idx.fw_root.parent / "elsewhere.json")
    assert allowed(idx.index / "catalog.json")
    res = registry.call(
        "propose_job",
        {"kind": "agentqa.run", "params": {"input": str(idx.fw_root / "vault" / "a")}},
    )
    assert not res["ok"] and "never allowed" in res["model"]
    res = registry.call("propose_job", {"kind": "ego.ingest", "params": {"source": "x/holdout/y"}})
    assert not res["ok"]


def test_no_training_or_shell_tool(idx: ConsolePaths) -> None:
    assert not any("train" in n and n != "run_metrics" for n in registry.TOOLS)
    assert not registry.call("propose_job", {"kind": "train", "params": {}})["ok"]
    assert not registry.call("run_shell", {"cmd": "ls"})["ok"]


def test_request_guards() -> None:
    assert llm.guard_check("start training C+ now")[0] == "training"
    assert llm.guard_check("read the holdout set")[0] == "holdout"
    assert llm.guard_check("upload raw video to Hugging Face")[0] == "upload"
    assert llm.guard_check("set episode 3 to pass")[0] == "qa_status"
    name, msg = llm.guard_check("đánh dấu episode này là pass")
    assert name == "qa_status" and "Trạng thái QA" in (msg or "")
    assert llm.guard_check("thống kê tập S70")[0] is None
