"""The agent that looks at images: Qwen3.5-4B behind a second endpoint (DA-20 AC 7, task 6).

Nemotron reads text only, so the figures code draws are for the engineer. When
`vision.enabled` is true in `agent.yaml`, this second pass shows a few images (the
SIMPLE frames of the stage 1 grid, frames of a replay video) to a VLM and asks
for one short observation each. An observation becomes a text fact
(`vision_observation`, source = the image) that the text agent may cite; like
every other sentence, it may hold no number, or it is dropped with the reason.
The VLM never adds a finding of its own.
"""

from __future__ import annotations

import base64
from collections.abc import Sequence
from pathlib import Path

from flywheel.eval.agentqa.endpoint import ChatModel, EndpointError, Message
from flywheel.eval.agentqa.facts import Analysis
from flywheel.eval.agentqa.inputs import refuse_forbidden
from flywheel.eval.agentqa.numbers import numbers_in

_MIME = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}

QUESTION = (
    "This frame comes from a robot simulation or a person's egocentric video. In one "
    "sentence, say what the robot or hand is doing and anything that looks wrong "
    "(object missed, hand empty, object dropped, view blocked). Do not write any number."
)


def image_message(path: Path, question: str = QUESTION) -> list[Message]:
    refuse_forbidden(path)
    mime = _MIME.get(path.suffix.lower())
    if mime is None:
        raise ValueError(f"{path}: not an image the endpoint takes")
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": question},
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{data}"}},
            ],
        }
    ]


def observe(
    analysis: Analysis, images: Sequence[tuple[Path, str]], model: ChatModel, max_images: int = 6
) -> int:
    """Add one observation fact per image (path, ref); returns how many were kept."""
    kept = 0
    for path, ref in list(images)[:max_images]:
        try:
            text = model.complete(image_message(path)).strip()
        except EndpointError as exc:
            analysis.notes.append(f"vision: {ref}: {exc}")
            continue
        if not text:
            continue
        if numbers_in(text):
            analysis.notes.append(f"vision: {ref}: observation dropped, it states numbers")
            continue
        analysis.book.add(f"vision_observation:{model.name}", text, ref)
        kept += 1
    return kept
