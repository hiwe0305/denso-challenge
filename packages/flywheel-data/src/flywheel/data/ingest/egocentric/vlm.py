"""Labelling models behind small Protocols (D6; design 6.7.2), called with images.

Rules decide first. A model only suggests: RoboBrain 2.5-4B the frame of a step
boundary the rules could not settle, and each segment's sentence; Molmo2-4B the grasp
point. A person reviews a sample (`review.py`). Every result a model gave is recorded
with the model's name (`label_source = model`).

Models run on the rtx3060 host behind an OpenAI-compatible `/v1/chat/completions`
(vLLM or Ollama). `OpenAIVision` posts images as base64 data URLs through `urllib`:
no torch, no client library in the lane. Tests and CI use fakes of `VisionModel`.

Parsing is lenient because each model answers in its own way: Qwen3-VL (RoboBrain's
base) gives points as `[(x, y)]` in 0-1000 coordinates, Molmo2
`<points coords="image point x y">` with x, y scaled by 1000 (seen from Molmo2-4B on
rtx3060, 6/11/2026), Molmo 1 `<point x="" y="">` in percent.
"""

from __future__ import annotations

import base64
import json
import re
import time
import urllib.request
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

Point = tuple[float, float]  # x, y as a share of image width and height, in [0, 1]


class VisionModel(Protocol):
    name: str

    def complete(self, prompt: str, images: Sequence[bytes]) -> str: ...


@dataclass
class OpenAIVision:
    """A chat model served at `endpoint` (".../v1"), images as JPEG data URLs."""

    endpoint: str
    name: str
    timeout_s: float = 120.0
    max_tokens: int = 200
    temperature: float = 0.0
    latencies_s: list[float] = field(default_factory=list)

    def complete(self, prompt: str, images: Sequence[bytes]) -> str:
        content: list[dict[str, Any]] = [
            {"type": "image_url",
             "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(i).decode()}}
            for i in images
        ]
        content.append({"type": "text", "text": prompt})
        body = {"model": self.name, "messages": [{"role": "user", "content": content}],
                "max_tokens": self.max_tokens, "temperature": self.temperature}
        request = urllib.request.Request(
            self.endpoint.rstrip("/") + "/chat/completions",
            data=json.dumps(body).encode(), headers={"Content-Type": "application/json"},
        )
        start = time.monotonic()
        with urllib.request.urlopen(request, timeout=self.timeout_s) as response:
            reply = json.loads(response.read())
        self.latencies_s.append(time.monotonic() - start)
        return str(reply["choices"][0]["message"]["content"] or "")


BOUNDARY_PROMPT = (
    "The {n} images are frames of a first-person video, in time order, numbered 1 to {n}."
    " The person is doing: \"{instruction}\". In which image does the hand {event}?"
    " Answer with only the image number."
)
EVENTS = {"grasp": "first close on the object to pick it up",
          "release": "let go of the object after placing it"}
SENTENCE_PROMPT = (
    "The {n} images are frames of one step of a first-person video, in time order."
    " The whole video shows: \"{instruction}\". This step is \"{step}\"."
    " Write one short imperative sentence, at most 15 words, telling a robot what the"
    " hand does in this step. Answer with only the sentence."
)
POINT_PROMPT = "Point to where the hand grasps the {object}."


@dataclass
class ModelSuggester:
    """RoboBrain: the frame of a grasp or release among the frames shown."""

    model: VisionModel

    def suggest(self, images: Sequence[bytes], frames: Sequence[int], event: str,
                instruction: str) -> int | None:
        prompt = BOUNDARY_PROMPT.format(n=len(images), instruction=instruction,
                                        event=EVENTS[event])
        choice = parse_index(self.model.complete(prompt, images), len(images))
        return None if choice is None else int(frames[choice])


@dataclass
class ModelLabeler:
    """RoboBrain: the sentence of one segment."""

    model: VisionModel

    def describe(self, images: Sequence[bytes], step: str, instruction: str) -> str | None:
        prompt = SENTENCE_PROMPT.format(n=len(images), instruction=instruction, step=step)
        return parse_sentence(self.model.complete(prompt, images))


@dataclass
class ModelPointer:
    """Molmo2: where the hand grasps the object, as a share of width and height."""

    model: VisionModel

    def point(self, image: bytes, obj: str, size: tuple[int, int]) -> Point | None:
        return parse_point(self.model.complete(POINT_PROMPT.format(object=obj), [image]), size)


def parse_index(text: str, n: int) -> int | None:
    """The 0-based image an answer names (1-based in the answer), None if it names none."""
    match = re.search(r"\d+", text)
    if match is None:
        return None
    value = int(match.group())
    return value - 1 if 1 <= value <= n else None


def parse_sentence(text: str) -> str | None:
    lines = [line.strip().strip("\"'*` ") for line in text.strip().splitlines() if line.strip()]
    if not lines:
        return None
    sentence = re.sub(r"^(sentence|answer)\s*:\s*", "", lines[0], flags=re.I).strip()
    words = sentence.split()
    return sentence if 2 <= len(words) <= 30 else None


_COORDS = re.compile(r'coords="([0-9\t:;, .]+)"')
_ATTR = re.compile(r'x\d*\s*=\s*"?([\d.]+)"?\s+y\d*\s*=\s*"?([\d.]+)"?')
_PAIR = re.compile(r"[\[(]\s*([\d.]+)\s*,\s*([\d.]+)\s*[\])]")


def parse_point(text: str, size: tuple[int, int]) -> Point | None:
    """The first point in an answer, as a share of the image (width, height = `size`).

    `<points coords="1 1 523 412">` (Molmo2) is image number, point number, x, y, the
    last two scaled by 1000; a group of three is read as point number, x, y;
    `<point x="61.5" y="40.2">` (Molmo 1) is in percent; a bare pair `[x, y]` (Qwen3-VL)
    is a share when both are at most 1, 0-1000 coordinates when at most 1000, pixels
    otherwise.
    """
    coords = _COORDS.search(text)
    attr = _ATTR.search(text)
    if coords is not None:
        numbers = coords.group(1).split(";")[0].replace(",", " ").split()
        if len(numbers) < 3:
            return None
        first = 2 if len(numbers) >= 4 else 1
        point = (float(numbers[first]) / 1000, float(numbers[first + 1]) / 1000)
    elif attr is not None:
        x, y = float(attr.group(1)), float(attr.group(2))
        point = (x / 100, y / 100) if max(x, y) <= 100 else (x / 1000, y / 1000)
    else:
        pair = _PAIR.search(text)
        if pair is None:
            return None
        x, y = float(pair.group(1)), float(pair.group(2))
        if max(x, y) <= 1:
            point = (x, y)
        elif max(x, y) <= 1000:
            point = (x / 1000, y / 1000)
        else:
            point = (x / size[0], y / size[1])
    if not (0 <= point[0] <= 1 and 0 <= point[1] <= 1):
        return None
    return point
