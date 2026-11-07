"""Test that the presenter refuses incomplete or altered evidence bundles."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).with_name("demo.py")


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-X", "utf8", str(SCRIPT), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


def bundle(tmp_path: Path) -> Path:
    tmp_path = tmp_path / "bundle"
    tmp_path.mkdir()
    template = json.loads(run("template").stdout)
    source = tmp_path / "results.txt"
    source.write_text("<script>alert(1)</script>\naccuracy: 12/20", encoding="utf-8")
    sha = hashlib.sha256(source.read_bytes()).hexdigest()
    for key, section in template["sections"].items():
        for item in section["items"]:
            label = "injected" if key == "4" else "preliminary" if key == "5" else "measured"
            item.update(
                path="results.txt",
                sha256=sha,
                kind="text",
                label=label,
                source="RunPlan rp_test / result.json",
            )
    template["sections"]["6"]["tray_outcome"] = "fallback"
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(template), encoding="utf-8")
    return path


def test_offline_section_shows_source_and_escapes_evidence(tmp_path: Path) -> None:
    manifest = bundle(tmp_path)
    output = tmp_path / "part-1.html"
    assert run("check", "--manifest", str(manifest)).returncode == 0
    result = run("1", "--manifest", str(manifest), "--output", str(output))
    assert result.returncode == 0, result.stderr
    page = output.read_text(encoding="utf-8")
    assert "accuracy: 12/20" in page
    assert "RunPlan rp_test / result.json" in page
    assert "&lt;script&gt;" in page and "<script>" not in page
    assert (
        "results.txt" in page
        and hashlib.sha256((manifest.parent / "results.txt").read_bytes()).hexdigest() in page
    )


def test_changed_missing_and_outside_evidence_fails_closed(tmp_path: Path) -> None:
    manifest = bundle(tmp_path)
    (manifest.parent / "results.txt").write_text("changed", encoding="utf-8")
    output = tmp_path / "part.html"
    assert run("1", "--manifest", str(manifest), "--output", str(output)).returncode == 1
    assert not output.exists()
    data = json.loads(manifest.read_text(encoding="utf-8"))
    data["sections"]["1"]["items"][0]["path"] = "../outside.txt"
    manifest.write_text(json.dumps(data), encoding="utf-8")
    assert run("check", "--manifest", str(manifest)).returncode == 1


def test_full_tray_requires_train_eval_and_comparison(tmp_path: Path) -> None:
    manifest = bundle(tmp_path)
    data = json.loads(manifest.read_text(encoding="utf-8"))
    data["sections"]["6"]["tray_outcome"] = "full"
    manifest.write_text(json.dumps(data), encoding="utf-8")
    result = run("6", "--manifest", str(manifest))
    assert result.returncode == 1
    assert "tray_train" in result.stderr and "tray_eval" in result.stderr


def test_cannot_overwrite_source_or_manifest(tmp_path: Path) -> None:
    manifest = bundle(tmp_path)
    original = manifest.read_bytes()
    assert run("1", "--manifest", str(manifest), "--output", str(manifest)).returncode == 2
    assert manifest.read_bytes() == original


def test_required_labels_and_fallback_are_visible(tmp_path: Path) -> None:
    manifest = bundle(tmp_path)
    rendered = run("6", "--manifest", str(manifest))
    assert rendered.returncode == 0
    assert "đường lui dừng sau QA" in rendered.stdout
    data = json.loads(manifest.read_text(encoding="utf-8"))
    data["sections"]["5"]["items"][0]["label"] = "measured"
    manifest.write_text(json.dumps(data), encoding="utf-8")
    result = run("5", "--manifest", str(manifest))
    assert result.returncode == 1 and "sơ bộ" in result.stderr


def test_template_creates_incomplete_manifest_without_overwriting(tmp_path: Path) -> None:
    path = tmp_path / "bundle" / "manifest.json"
    assert run("template", "--output", str(path)).returncode == 0
    first = path.read_bytes()
    assert run("template", "--output", str(path)).returncode == 2
    assert path.read_bytes() == first
    assert run("check", "--manifest", str(path)).returncode == 1


def test_each_item_requires_source_and_html_escapes_it(tmp_path: Path) -> None:
    manifest = bundle(tmp_path)
    data = json.loads(manifest.read_text(encoding="utf-8"))
    data["sections"]["1"]["items"][0]["source"] = "  "
    manifest.write_text(json.dumps(data), encoding="utf-8")
    assert run("1", "--manifest", str(manifest)).returncode == 1
    data["sections"]["1"]["items"][0]["source"] = '<img onerror="bad">'
    manifest.write_text(json.dumps(data), encoding="utf-8")
    result = run("1", "--manifest", str(manifest))
    assert result.returncode == 0
    assert "&lt;img onerror=&quot;bad&quot;&gt;" in result.stdout


def test_part_four_refuses_named_and_structural_answer_keys(tmp_path: Path) -> None:
    manifest = bundle(tmp_path)
    data = json.loads(manifest.read_text(encoding="utf-8"))
    answer = manifest.parent / "Defect_Manifest.json"
    answer.write_text('{"dataset_id":"x","defects":[]}', encoding="utf-8")
    item = data["sections"]["4"]["items"][0]
    item.update(path=answer.name, sha256=hashlib.sha256(answer.read_bytes()).hexdigest())
    manifest.write_text(json.dumps(data), encoding="utf-8")
    assert run("4", "--manifest", str(manifest)).returncode == 1
    renamed = answer.with_name("innocent.json")
    answer.rename(renamed)
    item["path"] = renamed.name
    manifest.write_text(json.dumps(data), encoding="utf-8")
    assert run("4", "--manifest", str(manifest)).returncode == 1
    assert run("check", "--manifest", str(manifest)).returncode == 1


def test_answer_directory_and_missing_file_use_the_same_evidence_exit_code(tmp_path: Path) -> None:
    manifest = bundle(tmp_path)
    data = json.loads(manifest.read_text(encoding="utf-8"))
    folder = manifest.parent / "answers"
    folder.mkdir()
    answer = folder / "report.txt"
    answer.write_text("sealed", encoding="utf-8")
    item = data["sections"]["4"]["items"][0]
    item.update(path="answers/report.txt", sha256=hashlib.sha256(answer.read_bytes()).hexdigest())
    manifest.write_text(json.dumps(data), encoding="utf-8")
    assert run("4", "--manifest", str(manifest)).returncode == 1
    assert run("check", "--manifest", str(manifest)).returncode == 1
    item["path"] = "missing.txt"
    manifest.write_text(json.dumps(data), encoding="utf-8")
    assert run("4", "--manifest", str(manifest)).returncode == 1
    assert run("check", "--manifest", str(manifest)).returncode == 1
