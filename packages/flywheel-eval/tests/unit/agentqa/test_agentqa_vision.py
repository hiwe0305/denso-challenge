"""DA-20 AC 7: the optional vision pass adds text facts, never numbers."""

from __future__ import annotations

from pathlib import Path

from agentqa_build import ScriptedModel
from flywheel.eval.agentqa.facts import Analysis
from flywheel.eval.agentqa.vision import image_message, observe


def test_the_vision_pass_adds_text_facts_without_numbers(tmp_path: Path) -> None:
    image = tmp_path / "frame.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\nfake")
    message = image_message(image)
    assert message[0]["content"][1]["image_url"]["url"].startswith("data:image/png;base64,")
    analysis = Analysis("s", "stage1", [])
    vlm = ScriptedModel(["The hand holds the box above the second table.",
                         "The robot dropped 2 boxes."])
    kept = observe(analysis, [(image, "frames/0.png"), (image, "frames/1.png")], vlm)
    assert kept == 1
    assert analysis.book.facts[0].source_ref == "frames/0.png"
    assert "states numbers" in analysis.notes[0]


def test_an_image_in_a_forbidden_dir_is_refused(tmp_path: Path) -> None:
    import pytest
    from flywheel.eval.agentqa.inputs import InputRefused

    image = tmp_path / "vault" / "frame.png"
    image.parent.mkdir()
    image.write_bytes(b"\x89PNG\r\n\x1a\nfake")
    link = tmp_path / "frame.png"
    link.symlink_to(image)
    for path in (image, link):
        with pytest.raises(InputRefused, match="vault"):
            image_message(path)
