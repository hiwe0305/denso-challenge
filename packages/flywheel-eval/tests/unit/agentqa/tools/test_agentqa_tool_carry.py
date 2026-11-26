"""`signal_presence` v3: how the tray was held when L-TRAY-TILT was raised (tools/carry.py).

The label, its signals and the value meaning "on no table" are the tray task view's.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml
from flywheel.contracts.outcome import RolloutOutcome
from flywheel.eval.agentqa.facts import FactBook
from flywheel.eval.agentqa.tools.base import RunOutcomes, RunScores, ToolResult
from flywheel.eval.agentqa.tools.signals import signal_presence
from flywheel.eval.agentqa.tools.task import TaskView, load_task
from helpers_tools import labelled, outcome, outcomes_of

TILT = "L-TRAY-TILT"
PLACE = "L-PLACE-POSE"
KINDS = ["scores", "outcomes"]
C1 = "R_cluster_carry_L-TRAY-TILT_l1"  # first failed step 4 is `carry`


def named(book: FactBook, result: ToolResult) -> dict[str, Any]:
    return {book.get(f).name: book.get(f).value for f in result.facts}


def tilted(run: str, name: str, *, t: float = 5.0, tilt: float | None = 16.0,
           left: object = True, right: object = True, table: object = "none") -> RolloutOutcome:
    at: dict[str, object] = {"hand_contact_left": left, "hand_contact_right": right,
                             "tray_on_table": table}
    if tilt is not None:
        at["tilt_deg"] = tilt
    at = {k: v for k, v in at.items() if v is not None}
    base = outcome(run, name, False, TILT, failure_t=t)
    verdict = base.verdict.model_copy(update={"at_failure": at})
    return base.model_copy(update={"verdict": verdict})


def tilt_set(rows: list[RolloutOutcome], run: str = "R") -> tuple[RunScores, RunOutcomes]:
    scores = [labelled(run, "ok", True)]
    scores += [labelled(run, o.episode_id.split("/", 1)[1], False, TILT, first_failed=3)
               for o in rows]
    return (RunScores(run, f"{run}/scores.jsonl", tuple(scores)),
            outcomes_of(run, [outcome(run, "ok", True), *rows]))


def sweep(tray: TaskView, run: RunScores, held: RunOutcomes | None,
          labels: list[str] | None = None) -> tuple[ToolResult, dict[str, Any], FactBook]:
    book = FactBook()
    result = signal_presence(book, tray, KINDS, labels or [TILT], [run],
                             {} if held is None else {run.run: held})
    return result, named(book, result), book


def test_the_carry_facts_of_a_cluster(tray: TaskView) -> None:
    run, held = tilt_set([
        tilted("R", "a", t=2.0, tilt=15.1),
        tilted("R", "b", t=4.0, tilt=15.3),
        tilted("R", "c", t=6.0, tilt=19.6, right=False),  # one hand let go
        tilted("R", "d", t=8.0, tilt=17.0, table="B"),    # on table B
    ])
    result, got, book = sweep(tray, run, held)
    units = {book.get(f).name: book.get(f).unit for f in result.facts}
    assert result.judged
    assert got[f"{C1}_carried_judged"] == 4
    assert got[f"{C1}_both_hands_at_failure"] == 3
    assert got[f"{C1}_off_table_at_failure"] == 3
    assert got[f"{C1}_carried_at_failure"] == 2
    assert got[f"{C1}_tilt_at_failure_median"] == pytest.approx(16.15)
    assert got[f"{C1}_failure_time_median"] == pytest.approx(5.0)
    assert got[f"{C1}_tilted_while_carried"] is False          # 2 of 4 is not a majority
    assert (units[f"{C1}_carried_at_failure"], units[f"{C1}_tilt_at_failure_median"],
            units[f"{C1}_failure_time_median"]) == ("rollouts", "deg", "s")


def test_a_majority_carried_is_tilted_while_carried(tray: TaskView) -> None:
    run, held = tilt_set([tilted("R", n) for n in "abc"] + [tilted("R", "d", table="A")])
    _, got, _ = sweep(tray, run, held)
    assert got[f"{C1}_carried_at_failure"] == 3 and got[f"{C1}_tilted_while_carried"] is True


def test_members_without_a_measure_are_left_out_of_the_counts(tray: TaskView) -> None:
    run, held = tilt_set([tilted("R", "a"), tilted("R", "b", tilt=None),
                          tilted("R", "c", left="yes"), tilted("R", "d", table="none")])
    result, got, _ = sweep(tray, run, held)
    assert got[f"{C1}_carried_judged"] == 2
    assert got[f"{C1}_tilted_while_carried"] is True
    assert got[f"{TILT}_judgeable"] is False   # the presence facts still say what is missing


def test_a_cluster_without_the_measures_is_not_judged(tray: TaskView) -> None:
    run, held = tilt_set([tilted("R", "a", tilt=None)])
    result, got, _ = sweep(tray, run, held)
    reason = ("no failure of the cluster carries at_failure.tilt_deg, "
              "at_failure.hand_contact_left, at_failure.hand_contact_right, "
              "at_failure.tray_on_table, verdict.failure_t")
    assert got[f"signal_presence_{C1}_carry_not_judged"] == reason
    assert reason in result.not_judged
    assert not any(n.startswith(C1) for n in got)


def test_old_outcomes_leave_the_presence_facts_as_they_were(tray: TaskView) -> None:
    run, held = tilt_set([tilted("R", "a")])
    bare = tuple(o.model_copy(update={"verdict": o.verdict.model_copy(
        update={"at_failure": None})}) for o in held.outcomes)
    _, got, _ = sweep(tray, run, RunOutcomes("R", held.ref, bare))
    presence = {k: v for k, v in got.items() if "carry" not in k}
    book = FactBook()
    v2 = signal_presence(book, tray.model_copy(update={"carry": None}), KINDS, [TILT], [run],
                         {"R": RunOutcomes("R", held.ref, bare)})
    assert presence == named(book, v2)


def test_a_run_without_outcomes_entry_is_not_judged_for_the_carry(tray: TaskView) -> None:
    run, _ = tilt_set([tilted("R", "a")])
    result, got, _ = sweep(tray, run, None)
    assert "no outcomes entry" in got["signal_presence_R_carry_not_judged"]


def test_no_carry_facts_unless_the_label_is_asked_or_outcomes_are_loaded(
        tray: TaskView) -> None:
    run, held = tilt_set([tilted("R", "a")])
    _, got, _ = sweep(tray, run, held, labels=[PLACE])
    assert not any("carr" in n for n in got)
    book = FactBook()
    got = named(book, signal_presence(book, tray, ["scores"], [TILT], [run], {"R": held}))
    assert not any("carr" in n for n in got)


def test_the_carry_block_names_its_signals(tray: TaskView) -> None:
    assert tray.carry is not None and tray.carry.label == TILT
    assert tray.carry_measures() == {
        "tilt": ("at_failure", ["tilt_deg"]),
        "contact": ("at_failure", ["hand_contact_left", "hand_contact_right"]),
        "table": ("at_failure", ["tray_on_table"]),
        "time": ("verdict", ["failure_t"])}


@pytest.mark.parametrize("edit, match", [
    (lambda raw: raw["carry"].update(label="L-GHOST"), "not a label"),
    (lambda raw: raw["carry"].update(tilt_signal="ghost"), "signal_measures"),
    (lambda raw: raw["carry"].update(tilt_signal="final_tray_pose"), "not a signal of"),
    (lambda raw: raw["signal_measures"]["tray_tilt_at_failure"].update(names=["tilt_rad"]),
     "_deg"),
    (lambda raw: raw["carry"].pop("off_table"), "off_table"),
])
def test_a_wrong_carry_block_is_refused(tmp_path: Path, edit: Any, match: str) -> None:
    src = Path("configs/eval/agentqa/tasks/tray.yaml")
    raw = yaml.safe_load(src.read_text())
    raw["scorer_config"] = str(Path("configs/eval/scorer/tray.yaml").resolve())
    edit(raw)
    (tmp_path / "tray.yaml").write_text(yaml.safe_dump(raw))
    with pytest.raises(ValueError, match=match):
        load_task("tray", tmp_path)
