"""Steps B0 (pack) and B1 (admit) of the round pipeline (DA-43 task 4.1, AC 7)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from flywheel.contracts.entities import Score, Source
from flywheel.eval.agentqa.cli import app
from flywheel.eval.agentqa.round.admit import admit, write_admission
from flywheel.eval.agentqa.round.pack import (
    PackRefused,
    build_pack,
    read_pack,
    write_pack,
)
from typer.testing import CliRunner

SHA = "0" * 64


def score_line(episode: str, success: bool) -> str:
    return Score(episode_id=episode, task_id="tray", config_sha256=SHA, trace_sha256=SHA,
                 success=success, level=1).model_dump_json()


def source_line(data_class: str) -> str:
    return Source(uri="hf://psi-data", sha256=SHA, downloaded_at="2026-11-01",
                  data_class=data_class).model_dump_json()  # type: ignore[arg-type]


def declare(root: Path, *, source_class: str | None = "public", link: bool = True,
            default_class: str | None = "public", extra: list[dict[str, object]] | None = None,
            ) -> Path:
    """A round of one run: its scores, and (unless None) the source record behind them."""
    (root / "C_70").mkdir(parents=True, exist_ok=True)
    (root / "C_70" / "scores.jsonl").write_text(
        score_line("C_70/l1-s1", True) + "\n" + score_line("C_70/l1-s2", False) + "\n")
    entries: list[dict[str, object]] = [
        {"path": "C_70/scores.jsonl", "kind": "scores", "subject": {"run": "C_70"}}]
    links = []
    if source_class is not None:
        (root / "sources.jsonl").write_text(source_line(source_class) + "\n")
        entries.append({"path": "sources.jsonl", "kind": "sources"})
        if link:
            links.append({"source": "C_70/scores.jsonl", "target": "sources.jsonl",
                          "relation": "data_of"})
    entries.extend(extra or [])
    body: dict[str, object] = {"task_id": "tray", "declared_by": "test", "entries": entries,
                               "links": links}
    if default_class is not None:
        body["data_class"] = default_class
    path = root / "round.yaml"
    path.write_text(yaml.safe_dump(body))
    return path


def packed(root: Path, **kwargs: object) -> Path:
    return write_pack(build_pack(declare(root, **kwargs)), root)  # type: ignore[arg-type]


def test_pack_hashes_every_file_and_is_stable(tmp_path: Path) -> None:
    decl = declare(tmp_path)
    pack = build_pack(decl)
    assert [e.ref for e in pack.entries] == ["C_70/scores.jsonl", "sources.jsonl"]
    assert pack.entries[0].subject == {"run": "C_70"} and pack.entries[0].bytes > 0
    assert pack.pack_id == build_pack(decl).pack_id
    out = write_pack(pack, tmp_path)
    assert read_pack(out) == pack
    with pytest.raises(PackRefused, match="immutable"):
        write_pack(pack, tmp_path)


def test_an_unclassified_file_is_restricted(tmp_path: Path) -> None:
    pack = build_pack(declare(tmp_path, default_class=None))
    assert {e.data_class for e in pack.entries} == {"restricted"}


@pytest.mark.parametrize("path", ["docs/he/tray.jsonl", "vault/scores.jsonl",
                                  "answers/key.jsonl", "../outside.jsonl"])
def test_pack_refuses_paths_the_agent_must_not_read(tmp_path: Path, path: str) -> None:
    root = tmp_path / "round"
    target = (root / path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(score_line("x", True) + "\n")
    with pytest.raises(PackRefused):
        build_pack(declare(root, extra=[{"path": path, "kind": "scores"}]))


def test_pack_refuses_a_link_out_of_the_root(tmp_path: Path) -> None:
    root = tmp_path / "round"
    root.mkdir()
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "diagnosis.jsonl").write_text(score_line("x", True) + "\n")
    (root / "extra.jsonl").symlink_to(tmp_path / "docs" / "diagnosis.jsonl")
    with pytest.raises(PackRefused, match="leaves the pack root"):
        build_pack(declare(root, extra=[{"path": "extra.jsonl", "kind": "scores"}]))


def test_a_missing_file_refuses_the_declaration(tmp_path: Path) -> None:
    with pytest.raises(PackRefused, match="no such file"):
        build_pack(declare(tmp_path, extra=[{"path": "gone.jsonl", "kind": "scores"}]))


def test_a_public_pack_with_its_source_record_may_go_hosted(tmp_path: Path) -> None:
    got = admit(packed(tmp_path))
    a = got.admission
    assert a.accepted == ["C_70/scores.jsonl", "sources.jsonl"] and not a.rejected
    assert (a.data_class, a.data_class_basis, a.unconfirmed) == ("public", ["sources.jsonl"], [])
    assert a.hosted_allowed
    assert len(got.records["C_70/scores.jsonl"]) == 2
    assert write_admission(a, tmp_path).name == "admission.json"


def test_declared_public_alone_is_not_enough_for_hosted(tmp_path: Path) -> None:
    # `Score` carries no data class: nothing in the pack confirms the declaration
    a = admit(packed(tmp_path, source_class=None)).admission
    assert a.data_class == "public" and a.unconfirmed == ["C_70/scores.jsonl"]
    assert not a.hosted_allowed


def test_a_source_record_must_be_linked_to_vouch_for_a_file(tmp_path: Path) -> None:
    a = admit(packed(tmp_path, link=False)).admission
    assert a.data_class_basis == ["sources.jsonl"] and a.unconfirmed == ["C_70/scores.jsonl"]
    assert not a.hosted_allowed


def test_a_real_robot_source_keeps_the_pack_internal_whatever_is_declared(
        tmp_path: Path) -> None:
    # a robot-log adapter stamps its records internal; declaring the round public
    # in round.yaml does not lower it (design 19/11 section 8, block 4)
    a = admit(packed(tmp_path, source_class="internal")).admission
    assert a.data_class == "internal" and not a.hosted_allowed and not a.data_class_basis


def test_a_pack_nobody_classified_is_restricted(tmp_path: Path) -> None:
    a = admit(packed(tmp_path, default_class=None)).admission
    assert a.data_class == "restricted" and not a.hosted_allowed


def test_a_file_changed_after_packing_refuses_the_pack(tmp_path: Path) -> None:
    pack_path = packed(tmp_path)
    with (tmp_path / "C_70" / "scores.jsonl").open("a") as f:
        f.write(score_line("C_70/l1-s3", True) + "\n")
    with pytest.raises(PackRefused, match="changed after it was packed"):
        admit(pack_path)


def test_bad_files_are_rejected_alone_with_a_reason(tmp_path: Path) -> None:
    (tmp_path / "notes.jsonl").write_text('{"free": "text"}\n')
    (tmp_path / "odd.bin").write_text("x")
    pack_path = packed(tmp_path, extra=[{"path": "notes.jsonl", "kind": "scores"},
                                       {"path": "odd.bin", "kind": "rosbag"}])
    a = admit(pack_path, expected_kinds=["scores", "trace", "metrics"]).admission
    reasons = {r.ref: r.reason for r in a.rejected}
    assert "does not parse as scores" in reasons["notes.jsonl"]
    assert "no contract" in reasons["odd.bin"]
    assert a.accepted == ["C_70/scores.jsonl", "sources.jsonl"]
    assert a.missing_kinds == ["trace", "metrics"]


def test_a_pack_with_nothing_readable_is_refused(tmp_path: Path) -> None:
    (tmp_path / "only.jsonl").write_text("not json\n")
    decl = tmp_path / "round.yaml"
    decl.write_text(yaml.safe_dump({"task_id": "tray", "declared_by": "t", "entries": [
        {"path": "only.jsonl", "kind": "scores"}]}))
    with pytest.raises(PackRefused, match="no entry was accepted"):
        admit(write_pack(build_pack(decl), tmp_path))


def test_fw_agentqa_pack_writes_the_manifest_and_fails_cleanly(tmp_path: Path) -> None:
    decl = declare(tmp_path)
    runner = CliRunner()
    done = runner.invoke(app, ["pack", "--round", str(decl)])
    assert done.exit_code == 0 and "2 files, 1 links" in done.output
    assert (tmp_path / "pack.json").is_file()
    again = runner.invoke(app, ["pack", "--round", str(decl)])
    assert again.exit_code == 2
